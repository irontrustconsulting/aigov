"""
Tests for draft-registration endpoints (DM-S3, D-66, INV-79).

Covers:
  POST /v1/draft-registrations — get-or-create (idempotent)
  GET  /v1/draft-registrations/active — caller's draft or 204
  PATCH /v1/draft-registrations/{id} — last-write-wins blob update
  DELETE /v1/draft-registrations/{id} — owner-filtered discard
  Cross-user isolation: second user in same tenant cannot read/patch/delete
  Cross-tenant isolation: RLS returns nothing across tenants
  Atomic discard via POST /v1/registrations with draft_id
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.main import app
from app.models.domain import DraftRegistration, System
from app.models.base import UserRole
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Membership, Tenant, User
from app.models.taxonomy import (
    EUAIActCategory,
    EUAIActSubcategory,
    ProductCategory,
    ProductCategoryEUMapping,
    ProductCategoryMembership,
)
from app.models.domain import CatalogueProduct, CatalogueVendor
from app.models.base import EUAIActTier


# ---------------------------------------------------------------------------
# Helpers (mirrored from test_registrations.py)
# ---------------------------------------------------------------------------

def _ctx_override(ctx: TenantContext):
    def _dep():
        return ctx
    return _dep


def _db_override(session: Session):
    def _dep():
        yield session
        session.flush()
    return _dep


def _db_override_savepoint(session: Session):
    def _dep():
        sp = session.begin_nested()
        try:
            yield session
            session.flush()
        except Exception:
            sp.rollback()
            raise
    return _dep


def _make_member(db: Session, tenant: Tenant, role: UserRole = UserRole.MEMBER):
    u = User(id=uuid.uuid4(), cognito_sub=f"sub-{uuid.uuid4()}", email=f"{uuid.uuid4()}@t.local")
    m = Membership(id=uuid.uuid4(), user_id=u.id, tenant_id=tenant.id, role=role)
    db.add_all([u, m])
    db.flush()
    return u, m


def _grant(db: Session, tenant: Tenant, membership: Membership, gov_role: GovernanceRole):
    a = GovernanceRoleAssignment(
        id=uuid.uuid4(), tenant_id=tenant.id,
        membership_id=membership.id, governance_role_id=gov_role.id,
    )
    db.add(a)
    db.flush()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tenant(db_session: Session):
    t = Tenant(id=uuid.uuid4(), name="Draft Corp", slug=f"draft-{uuid.uuid4().hex[:6]}")
    db_session.add(t)
    db_session.flush()
    return t


@pytest.fixture
def gov_roles(db_session: Session):
    roles = {}
    for key, name, line in [
        ("system_owner", "System Owner", 1),
        ("reviewer", "Reviewer", 2),
    ]:
        r = GovernanceRole(id=uuid.uuid4(), key=key, name=name, line_of_defence=line)
        db_session.add(r)
        roles[key] = r
    db_session.flush()
    return roles


@pytest.fixture
def owner_ctx(db_session: Session, tenant: Tenant, gov_roles):
    u, m = _make_member(db_session, tenant)
    _grant(db_session, tenant, m, gov_roles["system_owner"])
    return TenantContext(user_id=u.id, membership_id=m.id, tenant_id=tenant.id, role="member")


@pytest.fixture
def second_owner_ctx(db_session: Session, tenant: Tenant, gov_roles):
    """A second system_owner in the same tenant."""
    u, m = _make_member(db_session, tenant)
    _grant(db_session, tenant, m, gov_roles["system_owner"])
    return TenantContext(user_id=u.id, membership_id=m.id, tenant_id=tenant.id, role="member")


@pytest.fixture
def other_tenant_ctx(db_session: Session, gov_roles):
    """A system_owner in a completely different tenant."""
    t2 = Tenant(id=uuid.uuid4(), name="Other Corp", slug=f"other-{uuid.uuid4().hex[:6]}")
    db_session.add(t2)
    db_session.flush()
    u, m = _make_member(db_session, t2)
    _grant(db_session, t2, m, gov_roles["system_owner"])
    return TenantContext(user_id=u.id, membership_id=m.id, tenant_id=t2.id, role="member")


# ---------------------------------------------------------------------------
# TestDraftCRUD
# ---------------------------------------------------------------------------

class TestDraftCRUD:
    def test_post_creates_draft(self, client, db_session, tenant, owner_ctx):
        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/draft-registrations")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        body = r.json()
        assert "id" in body
        assert body["owner_user_id"] == str(owner_ctx.user_id)
        assert body["tenant_id"] == str(owner_ctx.tenant_id)
        assert body["draft_blob"] == {}

    def test_post_returns_existing_draft_not_second_row(self, client, db_session, tenant, owner_ctx):
        """Second POST returns the same draft row — get-or-create is idempotent (DF-D3-5)."""
        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r1 = client.post("/v1/draft-registrations")
            r2 = client.post("/v1/draft-registrations")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]
        # Only one row in the DB
        rows = db_session.scalars(
            select(DraftRegistration).where(DraftRegistration.tenant_id == tenant.id)
        ).all()
        assert len(rows) == 1

    def test_unique_constraint_is_present(self, db_session, tenant, owner_ctx):
        """UniqueConstraint(tenant_id, owner_user_id) is enforced as the backstop (INV-79)."""
        d1 = DraftRegistration(
            id=uuid.uuid4(), tenant_id=owner_ctx.tenant_id,
            owner_user_id=owner_ctx.user_id, draft_blob={},
        )
        db_session.add(d1)
        db_session.flush()

        d2 = DraftRegistration(
            id=uuid.uuid4(), tenant_id=owner_ctx.tenant_id,
            owner_user_id=owner_ctx.user_id, draft_blob={"step": "intake"},
        )
        db_session.add(d2)
        import sqlalchemy.exc
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_get_active_returns_draft(self, client, db_session, tenant, owner_ctx):
        # Create first
        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            client.post("/v1/draft-registrations")
            r = client.get("/v1/draft-registrations/active")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        assert r.json()["owner_user_id"] == str(owner_ctx.user_id)

    def test_get_active_returns_204_when_no_draft(self, client, db_session, tenant, owner_ctx):
        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get("/v1/draft-registrations/active")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 204

    def test_patch_updates_draft_blob(self, client, db_session, tenant, owner_ctx):
        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            create_r = client.post("/v1/draft-registrations")
            draft_id = create_r.json()["id"]
            r = client.patch(
                f"/v1/draft-registrations/{draft_id}",
                json={"draft_blob": {"step": "intake", "name": "Test System"}},
            )
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        assert r.json()["draft_blob"]["step"] == "intake"
        assert r.json()["draft_blob"]["name"] == "Test System"

    def test_delete_removes_draft(self, client, db_session, tenant, owner_ctx):
        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            create_r = client.post("/v1/draft-registrations")
            draft_id = create_r.json()["id"]
            r = client.delete(f"/v1/draft-registrations/{draft_id}")
            active_r = client.get("/v1/draft-registrations/active")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 204
        assert active_r.status_code == 204

    def test_second_user_cannot_patch_first_users_draft(
        self, client, db_session, tenant, owner_ctx, second_owner_ctx
    ):
        """Owner filter: second user cannot patch first user's draft (DF-D3-4)."""
        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            create_r = client.post("/v1/draft-registrations")
            draft_id = create_r.json()["id"]
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        # Now second user tries to patch
        app.dependency_overrides[get_tenant_context] = _ctx_override(second_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.patch(
                f"/v1/draft-registrations/{draft_id}",
                json={"draft_blob": {"step": "intake"}},
            )
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 404

    def test_second_user_cannot_delete_first_users_draft(
        self, client, db_session, tenant, owner_ctx, second_owner_ctx
    ):
        """Owner filter: second user cannot delete first user's draft (DF-D3-4)."""
        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            create_r = client.post("/v1/draft-registrations")
            draft_id = create_r.json()["id"]
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        app.dependency_overrides[get_tenant_context] = _ctx_override(second_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.delete(f"/v1/draft-registrations/{draft_id}")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 404


# ---------------------------------------------------------------------------
# TestDraftRLS — cross-tenant isolation
# ---------------------------------------------------------------------------

class TestDraftRLS:
    def test_cross_tenant_get_active_returns_204(
        self, client, db_session, tenant, owner_ctx, other_tenant_ctx
    ):
        """RLS: cross-tenant GET /active returns 204 — the other tenant's draft is invisible."""
        # Owner creates a draft in their tenant
        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            client.post("/v1/draft-registrations")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        # Other tenant sees nothing
        app.dependency_overrides[get_tenant_context] = _ctx_override(other_tenant_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get("/v1/draft-registrations/active")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 204


# ---------------------------------------------------------------------------
# TestDraftAtomicDiscard — POST /v1/registrations with draft_id
# ---------------------------------------------------------------------------

class TestDraftAtomicDiscard:
    """Atomic discard on POST /v1/registrations (D-66, SV-3)."""

    @pytest.fixture
    def product_for_reg(self, db_session):
        """Minimal catalogue product to satisfy the registration handler."""
        v = CatalogueVendor(id=uuid.uuid4(), name="DraftVendor")
        db_session.add(v)
        p = CatalogueProduct(id=uuid.uuid4(), vendor_id=v.id, name="DraftProduct")
        db_session.add(p)
        db_session.flush()
        return p

    def test_successful_registration_discards_draft(
        self, client, db_session, tenant, owner_ctx, product_for_reg
    ):
        """POST /v1/registrations with draft_id removes the draft row on success (D-66)."""
        draft = DraftRegistration(
            id=uuid.uuid4(), tenant_id=owner_ctx.tenant_id,
            owner_user_id=owner_ctx.user_id, draft_blob={"step": "use-case"},
        )
        db_session.add(draft)
        db_session.flush()
        draft_id = draft.id

        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/registrations", json={
                "name": "Draft Discard Test",
                "is_custom": True,
                "title": "Draft use case",
                "draft_id": str(draft_id),
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        remaining = db_session.scalar(
            select(DraftRegistration).where(DraftRegistration.id == draft_id)
        )
        assert remaining is None, "Atomic discard failed: draft still present after registration"

    def test_rolled_back_registration_leaves_draft_intact(
        self, client, db_session, tenant, owner_ctx, monkeypatch
    ):
        """A forced rollback during registration leaves the draft intact (SV-3)."""
        from app.routers.v1 import registrations as reg_module

        original_replace = reg_module._replace_data_categories

        def _failing_replace(db, use_case_id, tenant_id, ids):
            raise RuntimeError("Simulated mid-transaction failure")

        monkeypatch.setattr(reg_module, "_replace_data_categories", _failing_replace)

        draft = DraftRegistration(
            id=uuid.uuid4(), tenant_id=owner_ctx.tenant_id,
            owner_user_id=owner_ctx.user_id, draft_blob={"step": "use-case"},
        )
        db_session.add(draft)
        db_session.flush()
        draft_id = draft.id

        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override_savepoint(db_session)
        try:
            client.post("/v1/registrations", json={
                "name": "Should Roll Back",
                "is_custom": True,
                "title": "Doomed use case",
                "data_category_ids": [str(uuid.uuid4())],
                "draft_id": str(draft_id),
            })
        except Exception:
            pass
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        # Draft must survive the rollback
        surviving_draft = db_session.scalar(
            select(DraftRegistration).where(DraftRegistration.id == draft_id)
        )
        assert surviving_draft is not None, "Draft was deleted despite registration rollback"

    def test_registration_without_draft_id_still_works(
        self, client, db_session, tenant, owner_ctx
    ):
        """draft_id is optional — registrations without it behave as before (SV-3 additive)."""
        app.dependency_overrides[get_tenant_context] = _ctx_override(owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/registrations", json={
                "name": "No Draft",
                "is_custom": True,
                "title": "Plain use case",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
