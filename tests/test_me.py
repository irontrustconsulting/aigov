"""
Tests for GET /v1/me — the caller's-own-identity self-read (W-BE, F0).

Coverage: happy path with no governance roles; happy path with governance
roles; self-scoping proof (two distinct memberships, each sees only their own
roles through the route — there is no foreign-id param to even attempt a
cross-membership read with).

Fixture strategy mirrors tests/test_governance_roles.py: override
get_tenant_context/get_tenant_db so each test controls exactly what
TenantContext the request sees, sharing the test db_session.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.main import app
from app.models.base import UserRole
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Membership, Tenant, User


@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="Acme Corp", slug="acme")
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
def gov_roles(db_session: Session) -> dict[str, GovernanceRole]:
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


def _ctx_override(ctx: TenantContext):
    def _dep():
        return ctx
    return _dep


def _db_override(session: Session):
    def _dep():
        yield session
        session.flush()
    return _dep


def _ctx_for(user: User, membership: Membership, tenant: Tenant) -> TenantContext:
    return TenantContext(
        user_id=user.id,
        membership_id=membership.id,
        tenant_id=tenant.id,
        role=membership.role.value if hasattr(membership.role, "value") else str(membership.role),
        email=user.email,
        name=None,
    )


class TestGetMe:
    def test_no_governance_roles(self, client, db_session, tenant):
        user, m = _make_member(db_session, tenant)
        ctx = _ctx_for(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get("/v1/me")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        body = r.json()
        assert body["membership_id"] == str(m.id)
        assert body["tenant_id"] == str(tenant.id)
        assert body["role"] == "member"
        assert body["tenant_name"] == tenant.name
        assert body["governance_roles"] == []

    def test_with_governance_roles(self, db_session, client, tenant, gov_roles):
        user, m = _make_member(db_session, tenant)
        db_session.add_all([
            GovernanceRoleAssignment(
                id=uuid.uuid4(), tenant_id=tenant.id,
                membership_id=m.id, governance_role_id=gov_roles["system_owner"].id,
            ),
            GovernanceRoleAssignment(
                id=uuid.uuid4(), tenant_id=tenant.id,
                membership_id=m.id, governance_role_id=gov_roles["contributor"].id,
            ),
        ])
        db_session.flush()

        ctx = _ctx_for(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get("/v1/me")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        body = r.json()
        keys = {role["key"] for role in body["governance_roles"]}
        assert keys == {"system_owner", "contributor"}
        assert body["tenant_name"] == tenant.name

    def test_self_scoped_only_no_cross_membership_leak(
        self, db_session, client, tenant, gov_roles
    ):
        """No path param exists to even attempt reading another membership's
        roles — prove the route is wired to ctx, not a foreign id, by flipping
        the override between two distinct memberships and checking each sees
        only its own roles."""
        user_a, m_a = _make_member(db_session, tenant)
        user_b, m_b = _make_member(db_session, tenant)
        db_session.add_all([
            GovernanceRoleAssignment(
                id=uuid.uuid4(), tenant_id=tenant.id,
                membership_id=m_a.id, governance_role_id=gov_roles["reviewer"].id,
            ),
            GovernanceRoleAssignment(
                id=uuid.uuid4(), tenant_id=tenant.id,
                membership_id=m_b.id, governance_role_id=gov_roles["auditor"].id,
            ),
        ])
        db_session.flush()

        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            app.dependency_overrides[get_tenant_context] = _ctx_override(
                _ctx_for(user_a, m_a, tenant)
            )
            r_a = client.get("/v1/me")

            app.dependency_overrides[get_tenant_context] = _ctx_override(
                _ctx_for(user_b, m_b, tenant)
            )
            r_b = client.get("/v1/me")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert {role["key"] for role in r_a.json()["governance_roles"]} == {"reviewer"}
        assert {role["key"] for role in r_b.json()["governance_roles"]} == {"auditor"}
