"""
Tests for the systems endpoints — governance gate and ungated GET.

POST /v1/systems is gated by require_governance_role("system_owner"):
  - member with system_owner governance role → 201
  - member without any governance role → 403
  - admin without governance role → 403 (administrative role alone is not enough)
  - member with a different governance role (e.g. reviewer) → 403

GET /v1/systems is open to any authenticated member. Role-scoped read access
is deferred to the assessment sprint; this test confirms that floor is preserved.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.main import app
from app.models.base import UserRole
from app.models.domain import System
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Membership, Tenant, User

# ---------------------------------------------------------------------------
# Fixtures — mirrors the pattern in test_governance_roles.py
# ---------------------------------------------------------------------------

@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="Systems Corp", slug="sys-corp")
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
def admin_member(db_session: Session, tenant: Tenant) -> tuple[User, Membership]:
    return _make_member(db_session, tenant, UserRole.ADMIN)


@pytest.fixture
def plain_member(db_session: Session, tenant: Tenant) -> tuple[User, Membership]:
    return _make_member(db_session, tenant, UserRole.MEMBER)


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


def _grant(
    db: Session,
    tenant: Tenant,
    membership: Membership,
    gov_role: GovernanceRole,
) -> GovernanceRoleAssignment:
    a = GovernanceRoleAssignment(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        membership_id=membership.id,
        governance_role_id=gov_role.id,
    )
    db.add(a)
    db.flush()
    return a


def _ctx_override(ctx: TenantContext):
    def _dep():
        return ctx
    return _dep


def _db_override(session: Session):
    def _dep():
        yield session
        session.flush()
    return _dep


# ---------------------------------------------------------------------------
# POST /v1/systems — governance gate
# ---------------------------------------------------------------------------

class TestCreateSystem:
    def test_system_owner_can_create(
        self, client, db_session, tenant, plain_member, gov_roles
    ):
        user, m = plain_member
        _grant(db_session, tenant, m, gov_roles["system_owner"])

        ctx = TenantContext(
            user_id=user.id, membership_id=m.id,
            tenant_id=tenant.id, role="member",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/systems", json={"name": "My AI System"})
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        assert r.json()["name"] == "My AI System"
        assert r.json()["tenant_id"] == str(tenant.id)

    def test_member_without_governance_role_gets_403(
        self, client, db_session, tenant, plain_member
    ):
        user, m = plain_member
        # No governance role assigned
        ctx = TenantContext(
            user_id=user.id, membership_id=m.id,
            tenant_id=tenant.id, role="member",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/systems", json={"name": "Blocked"})
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403

    def test_admin_without_governance_role_gets_403(
        self, client, db_session, tenant, admin_member
    ):
        """Administrative role alone does not confer governance power."""
        user, m = admin_member
        ctx = TenantContext(
            user_id=user.id, membership_id=m.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/systems", json={"name": "Admin blocked"})
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403

    def test_wrong_governance_role_gets_403(
        self, client, db_session, tenant, plain_member, gov_roles
    ):
        """A member with reviewer governance role cannot create systems."""
        user, m = plain_member
        _grant(db_session, tenant, m, gov_roles["reviewer"])

        ctx = TenantContext(
            user_id=user.id, membership_id=m.id,
            tenant_id=tenant.id, role="member",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/systems", json={"name": "Reviewer blocked"})
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403

    def test_admin_with_system_owner_can_create(
        self, client, db_session, tenant, admin_member, gov_roles
    ):
        """Admin who also holds system_owner governance role can create."""
        user, m = admin_member
        _grant(db_session, tenant, m, gov_roles["system_owner"])

        ctx = TenantContext(
            user_id=user.id, membership_id=m.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/systems", json={"name": "Admin+owner"})
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201


# ---------------------------------------------------------------------------
# GET /v1/systems — ungated read, any authenticated member
# ---------------------------------------------------------------------------

class TestListSystems:
    def test_plain_member_can_list(
        self, client, db_session, tenant, plain_member
    ):
        """Any authenticated member may list systems — no governance gate."""
        user, m = plain_member
        db_session.add(System(
            id=uuid.uuid4(), tenant_id=tenant.id,
            name="Existing system", metadata_blob={},
        ))
        db_session.flush()

        ctx = TenantContext(
            user_id=user.id, membership_id=m.id,
            tenant_id=tenant.id, role="member",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get("/v1/systems")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_admin_can_list(self, client, db_session, tenant, admin_member):
        user, m = admin_member
        ctx = TenantContext(
            user_id=user.id, membership_id=m.id,
            tenant_id=tenant.id, role="admin",
        )
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get("/v1/systems")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        assert r.json() == []
