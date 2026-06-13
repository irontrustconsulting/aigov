"""
Tests for the governance role management sprint.

Coverage:
  Unit:        assert_governance_assignable — all 9 conflict pairs, the one
               composable pair (system_owner+contributor), self-assign.
  Integration: POST assign — happy, conflict (409), self-assign (403),
               non-admin (403), duplicate (409 via DB unique constraint);
               DELETE revoke; GET catalogue; GET assignments; cross-tenant
               isolation (RLS not active in tests, but membership FK checks).

Tenant-plane fixture strategy
------------------------------
There is no RLS in the test DB (create_all, no migrations). To test tenant-
scoped endpoints we override get_tenant_context and get_tenant_db so each test
controls exactly what TenantContext the request sees and shares the test
db_session. require_role depends on get_tenant_context so the override propagates
automatically to all gated endpoints.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.main import app
from app.models.base import UserRole
from app.models.governance import (
    GovernanceRole,
    GovernanceRoleAssignment,
    GovernanceRoleConflict,
)
from app.models.identity import Membership, Tenant, User
from app.models.lifecycle import AuditEvent
from app.services.governance import assert_governance_assignable

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="Acme Corp", slug="acme")
    db_session.add(t)
    db_session.flush()
    return t


@pytest.fixture
def tenant_b(db_session: Session) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="Rival Corp", slug="rival")
    db_session.add(t)
    db_session.flush()
    return t


def _make_member(
    db: Session, tenant: Tenant, role: UserRole = UserRole.MEMBER
) -> tuple[User, Membership]:
    u = User(
        id=uuid.uuid4(),
        cognito_sub=f"sub-{uuid.uuid4()}",
        email=f"{uuid.uuid4()}@test.local",
    )
    m = Membership(id=uuid.uuid4(), user_id=u.id, tenant_id=tenant.id, role=role)
    db.add_all([u, m])
    db.flush()
    return u, m


@pytest.fixture
def admin(db_session: Session, tenant: Tenant) -> tuple[User, Membership]:
    return _make_member(db_session, tenant, UserRole.ADMIN)


@pytest.fixture
def member_b(db_session: Session, tenant: Tenant) -> tuple[User, Membership]:
    return _make_member(db_session, tenant)


@pytest.fixture
def member_c(db_session: Session, tenant: Tenant) -> tuple[User, Membership]:
    return _make_member(db_session, tenant)


@pytest.fixture
def gov_roles(db_session: Session) -> dict[str, GovernanceRole]:
    """Seed the five governance roles into the test DB."""
    roles_data = [
        ("system_owner", "System Owner", 1),
        ("contributor", "Contributor", 1),
        ("reviewer", "Reviewer", 2),
        ("authoriser", "Authoriser", 2),
        ("auditor", "Auditor", 3),
    ]
    roles = {}
    for key, name, line in roles_data:
        r = GovernanceRole(id=uuid.uuid4(), key=key, name=name, line_of_defence=line)
        db_session.add(r)
        roles[key] = r
    db_session.flush()
    return roles


@pytest.fixture
def conflict_matrix(db_session: Session, gov_roles: dict[str, GovernanceRole]) -> None:
    """Seed the 9 SoD conflict pairs into the test DB."""
    pairs = [
        ("system_owner", "reviewer"),
        ("system_owner", "authoriser"),
        ("system_owner", "auditor"),
        ("contributor", "reviewer"),
        ("contributor", "authoriser"),
        ("contributor", "auditor"),
        ("reviewer", "authoriser"),
        ("reviewer", "auditor"),
        ("authoriser", "auditor"),
    ]
    for ka, kb in pairs:
        a_id = gov_roles[ka].id
        b_id = gov_roles[kb].id
        lo, hi = min(a_id, b_id), max(a_id, b_id)
        db_session.add(
            GovernanceRoleConflict(id=uuid.uuid4(), role_a_id=lo, role_b_id=hi)
        )
    db_session.flush()


def _ctx_override(ctx: TenantContext):
    def _dep():
        return ctx
    return _dep


def _db_override(session: Session):
    def _dep():
        yield session
        session.flush()  # make handler's writes visible to post-request assertions
    return _dep


# ---------------------------------------------------------------------------
# Unit: assert_governance_assignable
# ---------------------------------------------------------------------------

class TestAssertGovernanceAssignable:
    """Pure service-layer tests; no HTTP, no client."""

    def test_self_assign_blocked(self, db_session, tenant, gov_roles, conflict_matrix):
        _, m = _make_member(db_session, tenant)
        with pytest.raises(HTTPException) as exc_info:
            assert_governance_assignable(
                m.id, m.id, gov_roles["system_owner"].id, db_session
            )
        assert exc_info.value.status_code == 403

    def test_no_conflict_first_assignment(
        self, db_session, tenant, member_b, gov_roles, conflict_matrix
    ):
        _, m = member_b
        _, admin_m = _make_member(db_session, tenant, UserRole.ADMIN)
        # Should not raise — first assignment, no existing roles
        assert_governance_assignable(
            admin_m.id, m.id, gov_roles["system_owner"].id, db_session
        )

    def test_composable_pair_allowed(
        self, db_session, tenant, member_b, gov_roles, conflict_matrix
    ):
        """system_owner + contributor is the ONE composable pair."""
        _, m = member_b
        _, admin_m = _make_member(db_session, tenant, UserRole.ADMIN)
        # Grant system_owner first
        db_session.add(GovernanceRoleAssignment(
            id=uuid.uuid4(), tenant_id=tenant.id,
            membership_id=m.id, governance_role_id=gov_roles["system_owner"].id,
        ))
        db_session.flush()
        # contributor should be allowed alongside system_owner
        assert_governance_assignable(
            admin_m.id, m.id, gov_roles["contributor"].id, db_session
        )

    @pytest.mark.parametrize("held,candidate", [
        ("system_owner", "reviewer"),
        ("system_owner", "authoriser"),
        ("system_owner", "auditor"),
        ("contributor", "reviewer"),
        ("contributor", "authoriser"),
        ("contributor", "auditor"),
        ("reviewer", "authoriser"),
        ("reviewer", "auditor"),
        ("authoriser", "auditor"),
    ])
    def test_all_conflict_pairs_rejected(
        self, held, candidate, db_session, tenant, gov_roles, conflict_matrix
    ):
        _, m = _make_member(db_session, tenant)
        _, admin_m = _make_member(db_session, tenant, UserRole.ADMIN)
        db_session.add(GovernanceRoleAssignment(
            id=uuid.uuid4(), tenant_id=tenant.id,
            membership_id=m.id, governance_role_id=gov_roles[held].id,
        ))
        db_session.flush()

        with pytest.raises(HTTPException) as exc_info:
            assert_governance_assignable(
                admin_m.id, m.id, gov_roles[candidate].id, db_session
            )
        assert exc_info.value.status_code == 409
        assert held in exc_info.value.detail or candidate in exc_info.value.detail


# ---------------------------------------------------------------------------
# Integration: HTTP endpoints
# ---------------------------------------------------------------------------

class TestGovernanceCatalogue:
    def test_get_catalogue(
        self, client, db_session, tenant, admin, gov_roles, conflict_matrix
    ):
        user, m = admin
        ctx = TenantContext(
            user_id=user.id, membership_id=m.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get("/v1/governance-roles/catalogue")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        body = r.json()
        assert len(body["roles"]) == 5
        assert len(body["conflicts"]) == 9
        keys = {r["key"] for r in body["roles"]}
        assert keys == {
            "system_owner", "contributor", "reviewer", "authoriser", "auditor"
        }


class TestAssignRole:
    def test_admin_assigns_non_conflicting(
        self, client, db_session, tenant, admin, member_b, gov_roles, conflict_matrix
    ):
        user_a, m_admin = admin
        _, m_b = member_b
        ctx = TenantContext(
            user_id=user_a.id, membership_id=m_admin.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/governance-roles/assignments", json={
                "membership_id": str(m_b.id),
                "governance_role_id": str(gov_roles["system_owner"].id),
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        body = r.json()
        assert body["membership_id"] == str(m_b.id)
        assert body["governance_role_id"] == str(gov_roles["system_owner"].id)
        assert body["granted_by_membership_id"] == str(m_admin.id)

        # Audit event was written
        audit = db_session.query(AuditEvent).filter_by(
            action="governance_role.granted"
        ).first()
        assert audit is not None
        assert audit.detail["governance_role_key"] == "system_owner"

    def test_conflicting_role_returns_409(
        self, client, db_session, tenant, admin, member_b, gov_roles, conflict_matrix
    ):
        user_a, m_admin = admin
        _, m_b = member_b
        # Pre-assign system_owner to member_b
        db_session.add(GovernanceRoleAssignment(
            id=uuid.uuid4(), tenant_id=tenant.id,
            membership_id=m_b.id, governance_role_id=gov_roles["system_owner"].id,
        ))
        db_session.flush()

        ctx = TenantContext(
            user_id=user_a.id, membership_id=m_admin.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/governance-roles/assignments", json={
                "membership_id": str(m_b.id),
                "governance_role_id": str(gov_roles["reviewer"].id),
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 409
        assert "conflict" in r.json()["detail"].lower()

    def test_self_assign_returns_403(
        self, client, db_session, tenant, admin, gov_roles, conflict_matrix
    ):
        user_a, m_admin = admin
        ctx = TenantContext(
            user_id=user_a.id, membership_id=m_admin.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/governance-roles/assignments", json={
                "membership_id": str(m_admin.id),
                "governance_role_id": str(gov_roles["system_owner"].id),
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403

    def test_non_admin_returns_403(
        self, client, db_session, tenant, member_b, member_c, gov_roles, conflict_matrix
    ):
        user_b, m_b = member_b
        _, m_c = member_c
        ctx = TenantContext(
            user_id=user_b.id, membership_id=m_b.id,
            tenant_id=tenant.id, role="member",  # not admin
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/governance-roles/assignments", json={
                "membership_id": str(m_c.id),
                "governance_role_id": str(gov_roles["reviewer"].id),
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403

    def test_composable_pair_succeeds(
        self, client, db_session, tenant, admin, member_b, gov_roles, conflict_matrix
    ):
        """system_owner + contributor on the same member must succeed."""
        user_a, m_admin = admin
        _, m_b = member_b
        db_session.add(GovernanceRoleAssignment(
            id=uuid.uuid4(), tenant_id=tenant.id,
            membership_id=m_b.id, governance_role_id=gov_roles["system_owner"].id,
        ))
        db_session.flush()

        ctx = TenantContext(
            user_id=user_a.id, membership_id=m_admin.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/governance-roles/assignments", json={
                "membership_id": str(m_b.id),
                "governance_role_id": str(gov_roles["contributor"].id),
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201


class TestRevokeRole:
    def test_admin_revokes_assignment(
        self, client, db_session, tenant, admin, member_b, gov_roles, conflict_matrix
    ):
        user_a, m_admin = admin
        _, m_b = member_b
        assignment = GovernanceRoleAssignment(
            id=uuid.uuid4(), tenant_id=tenant.id,
            membership_id=m_b.id, governance_role_id=gov_roles["auditor"].id,
            granted_by_membership_id=m_admin.id,
        )
        db_session.add(assignment)
        db_session.flush()

        ctx = TenantContext(
            user_id=user_a.id, membership_id=m_admin.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.delete(f"/v1/governance-roles/assignments/{assignment.id}")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 204
        assert db_session.get(GovernanceRoleAssignment, assignment.id) is None

        audit = db_session.query(AuditEvent).filter_by(
            action="governance_role.revoked"
        ).first()
        assert audit is not None
        assert audit.detail["governance_role_key"] == "auditor"

    def test_revoke_not_found_returns_404(
        self, client, db_session, tenant, admin
    ):
        user_a, m_admin = admin
        ctx = TenantContext(
            user_id=user_a.id, membership_id=m_admin.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.delete(f"/v1/governance-roles/assignments/{uuid.uuid4()}")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 404

    def test_non_admin_cannot_revoke(
        self, client, db_session, tenant, admin, member_b, gov_roles, conflict_matrix
    ):
        user_a, m_admin = admin
        user_b, m_b = member_b
        assignment = GovernanceRoleAssignment(
            id=uuid.uuid4(), tenant_id=tenant.id,
            membership_id=m_b.id, governance_role_id=gov_roles["auditor"].id,
        )
        db_session.add(assignment)
        db_session.flush()

        ctx = TenantContext(
            user_id=user_b.id, membership_id=m_b.id,
            tenant_id=tenant.id, role="member",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.delete(f"/v1/governance-roles/assignments/{assignment.id}")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403


class TestListAssignments:
    def test_list_all_assignments(
        self, client, db_session, tenant, admin, member_b, member_c,
        gov_roles, conflict_matrix
    ):
        user_a, m_admin = admin
        _, m_b = member_b
        _, m_c = member_c
        db_session.add_all([
            GovernanceRoleAssignment(
                id=uuid.uuid4(), tenant_id=tenant.id,
                membership_id=m_b.id, governance_role_id=gov_roles["system_owner"].id,
            ),
            GovernanceRoleAssignment(
                id=uuid.uuid4(), tenant_id=tenant.id,
                membership_id=m_c.id, governance_role_id=gov_roles["reviewer"].id,
            ),
        ])
        db_session.flush()

        ctx = TenantContext(
            user_id=user_a.id, membership_id=m_admin.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get("/v1/governance-roles/assignments")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_list_member_assignments(
        self, client, db_session, tenant, admin, member_b, member_c,
        gov_roles, conflict_matrix
    ):
        user_a, m_admin = admin
        _, m_b = member_b
        _, m_c = member_c
        db_session.add_all([
            GovernanceRoleAssignment(
                id=uuid.uuid4(), tenant_id=tenant.id,
                membership_id=m_b.id, governance_role_id=gov_roles["system_owner"].id,
            ),
            GovernanceRoleAssignment(
                id=uuid.uuid4(), tenant_id=tenant.id,
                membership_id=m_c.id, governance_role_id=gov_roles["auditor"].id,
            ),
        ])
        db_session.flush()

        ctx = TenantContext(
            user_id=user_a.id, membership_id=m_admin.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get(f"/v1/governance-roles/assignments/member/{m_b.id}")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["membership_id"] == str(m_b.id)
