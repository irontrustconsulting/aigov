"""
Tests for POST /v1/registrations — the atomic system + use-case + classification
endpoint (DM-S2, D-65, INV-78).

Covers:
  POST /v1/registrations — happy path, gate (403), atomicity/rollback,
    requires_context branch, prefill by product (WI-2).
  GET  /v1/catalogue/products/{id}/prefill — by-product prefill (WI-2).
  INV-78 route-absence — POST /v1/systems returns 404 or 405.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.main import app
from app.models.assessment import Classification
from app.models.base import EUAIActTier, UserRole
from app.models.domain import CatalogueProduct, CatalogueVendor, CatalogueFact, System, UseCase
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Membership, Tenant, User
from app.models.lifecycle import AuditEvent
from app.models.taxonomy import (
    EUAIActCategory,
    EUAIActSubcategory,
    ProductCategory,
    ProductCategoryEUMapping,
    ProductCategoryMembership,
)
from app.models.base import ProvenanceConfidence


# ---------------------------------------------------------------------------
# Helpers
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
    """SAVEPOINT-backed override: rolls back to the savepoint on exception.
    Fixture rows in the outer transaction are preserved; only work done inside
    the request is undone — mirrors real get_tenant_db rollback behaviour."""
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
    t = Tenant(id=uuid.uuid4(), name="Registration Corp", slug=f"reg-{uuid.uuid4().hex[:6]}")
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
def system_owner_ctx(db_session: Session, tenant: Tenant, gov_roles):
    u, m = _make_member(db_session, tenant)
    _grant(db_session, tenant, m, gov_roles["system_owner"])
    return TenantContext(user_id=u.id, membership_id=m.id, tenant_id=tenant.id, role="member")


@pytest.fixture
def no_role_ctx(db_session: Session, tenant: Tenant):
    u, m = _make_member(db_session, tenant)
    return TenantContext(user_id=u.id, membership_id=m.id, tenant_id=tenant.id, role="member")


# --- Classification bridge fixtures ---

@pytest.fixture
def eu_category(db_session: Session):
    cat = EUAIActCategory(id=uuid.uuid4(), code="REG-EMPLOYMENT", name="Employment AI")
    db_session.add(cat)
    db_session.flush()
    return cat


@pytest.fixture
def high_subcategory(db_session: Session, eu_category):
    sub = EUAIActSubcategory(
        id=uuid.uuid4(),
        category_id=eu_category.id,
        code="REG-EMP-RECRUIT",
        name="Recruitment screening",
        tier=EUAIActTier.HIGH,
        legal_ref="Annex III(4)(a)",
    )
    db_session.add(sub)
    db_session.flush()
    return sub


@pytest.fixture
def product_cat(db_session: Session):
    pc = ProductCategory(id=uuid.uuid4(), code="REG-HR-HIRING", name="Hiring Tools")
    db_session.add(pc)
    db_session.flush()
    return pc


@pytest.fixture
def vendor(db_session: Session):
    v = CatalogueVendor(id=uuid.uuid4(), name="RegVendor")
    db_session.add(v)
    db_session.flush()
    return v


@pytest.fixture
def product_high(db_session: Session, vendor, product_cat, high_subcategory):
    """Product mapped to a HIGH-tier EU subcategory."""
    p = CatalogueProduct(id=uuid.uuid4(), vendor_id=vendor.id, name="ATS Pro")
    db_session.add(p)
    db_session.flush()
    db_session.add(ProductCategoryMembership(
        id=uuid.uuid4(), catalogue_product_id=p.id, product_category_id=product_cat.id,
    ))
    db_session.add(ProductCategoryEUMapping(
        id=uuid.uuid4(), product_category_id=product_cat.id,
        eu_ai_act_subcategory_id=high_subcategory.id, is_primary=True,
    ))
    db_session.flush()
    return p


@pytest.fixture
def product_no_mapping(db_session: Session, vendor):
    """Product with no EU mapping → REQUIRES_CONTEXT."""
    pc = ProductCategory(id=uuid.uuid4(), code="REG-ML-PLATFORM", name="ML Platform")
    db_session.add(pc)
    db_session.flush()
    p = CatalogueProduct(id=uuid.uuid4(), vendor_id=vendor.id, name="ML Platform")
    db_session.add(p)
    db_session.flush()
    db_session.add(ProductCategoryMembership(
        id=uuid.uuid4(), catalogue_product_id=p.id, product_category_id=pc.id,
    ))
    db_session.flush()
    return p


@pytest.fixture
def catalogue_fact(db_session: Session, product_high):
    f = CatalogueFact(
        id=uuid.uuid4(), product_id=product_high.id,
        key="data_residency", value={"text": "EU"},
        source_label="Vendor DPA",
        provenance=ProvenanceConfidence.CATALOGUE_CURATED,
    )
    db_session.add(f)
    db_session.flush()
    return f


# ---------------------------------------------------------------------------
# INV-78 route-absence test
# ---------------------------------------------------------------------------

class TestPostSystemsAbsent:
    def test_post_systems_returns_404_or_405(self, client, db_session, tenant, system_owner_ctx):
        """INV-78: POST /v1/systems is removed; must return 404 or 405."""
        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/systems", json={"name": "Should not exist"})
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code in (404, 405)


# ---------------------------------------------------------------------------
# POST /v1/registrations — gate tests
# ---------------------------------------------------------------------------

class TestRegistrationGate:
    def test_member_without_governance_role_gets_403(self, client, db_session, tenant, no_role_ctx):
        app.dependency_overrides[get_tenant_context] = _ctx_override(no_role_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/registrations", json={"name": "Blocked", "title": "Use case", "is_custom": True})
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403

    def test_reviewer_gets_403(self, client, db_session, tenant, no_role_ctx, gov_roles):
        u_id = no_role_ctx.user_id
        # Find the membership
        from app.models.identity import Membership
        m = db_session.scalar(select(Membership).where(Membership.user_id == u_id))
        _grant(db_session, tenant, m, gov_roles["reviewer"])

        app.dependency_overrides[get_tenant_context] = _ctx_override(no_role_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/registrations", json={"name": "Blocked", "title": "Use case", "is_custom": True})
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /v1/registrations — happy path
# ---------------------------------------------------------------------------

class TestRegisterHappyPath:
    def test_custom_system_returns_requires_context(
        self, client, db_session, tenant, system_owner_ctx,
    ):
        """Custom system with no product → REQUIRES_CONTEXT (requires_context=True)."""
        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/registrations", json={
                "name": "Custom AI",
                "is_custom": True,
                "title": "Internal automation",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        body = r.json()
        assert body["system"]["name"] == "Custom AI"
        assert body["system"]["is_custom"] is True
        assert body["use_case"]["title"] == "Internal automation"
        assert body["classification"]["requires_context"] is True

    def test_mapped_product_returns_tier(
        self, client, db_session, tenant, system_owner_ctx, product_high, vendor,
    ):
        """Product with a HIGH primary mapping → classification.tier == high_risk."""
        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/registrations", json={
                "name": "ATS System",
                "is_custom": False,
                "catalogue_product_id": str(product_high.id),
                "title": "Resume screening",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        body = r.json()
        assert body["system"]["catalogue_vendor"]["id"] == str(vendor.id)
        assert body["classification"]["tier"] == "high_risk"
        assert body["classification"]["requires_context"] is False

    def test_product_no_mapping_returns_requires_context(
        self, client, db_session, tenant, system_owner_ctx, product_no_mapping,
    ):
        """Product with no primary EU mapping → REQUIRES_CONTEXT."""
        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/registrations", json={
                "name": "ML Platform",
                "is_custom": False,
                "catalogue_product_id": str(product_no_mapping.id),
                "title": "Fraud detection",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        assert r.json()["classification"]["requires_context"] is True

    def test_response_shape(
        self, client, db_session, tenant, system_owner_ctx,
    ):
        """RegistrationRead has system, use_case, classification at the top level."""
        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/registrations", json={
                "name": "Shape Test",
                "is_custom": True,
                "title": "Test use case",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        body = r.json()
        assert "system" in body
        assert "use_case" in body
        assert "classification" in body
        assert body["use_case"]["system_id"] == body["system"]["id"]
        assert body["classification"]["use_case_id"] == body["use_case"]["id"]

    def test_audit_events_created(
        self, client, db_session, tenant, system_owner_ctx,
    ):
        """Registration stages system.created audit event (D-6)."""
        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/registrations", json={
                "name": "Audit Test",
                "is_custom": True,
                "title": "Audit use case",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        events = db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "system.created",
                AuditEvent.tenant_id == tenant.id,
            )
        ).all()
        assert len(events) == 1


# ---------------------------------------------------------------------------
# POST /v1/registrations — atomicity
# ---------------------------------------------------------------------------

class TestRegistrationAtomicity:
    def test_rollback_leaves_no_system(
        self, client, db_session, tenant, system_owner_ctx, monkeypatch,
    ):
        """Force exception after system flush → transaction rolls back, no orphan System row."""
        from app.routers.v1 import registrations as reg_module

        original_replace = reg_module._replace_data_categories

        call_count = {"n": 0}

        def _failing_replace(db, use_case_id, tenant_id, ids):
            call_count["n"] += 1
            raise RuntimeError("Simulated mid-transaction failure")

        monkeypatch.setattr(reg_module, "_replace_data_categories", _failing_replace)

        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override_savepoint(db_session)
        try:
            r = client.post("/v1/registrations", json={
                "name": "Should Roll Back",
                "is_custom": True,
                "title": "Doomed use case",
                "data_category_ids": [str(uuid.uuid4())],  # triggers the patched call
            })
        except Exception:
            pass  # server-side exception propagated through raise_server_exceptions
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        # Either the response is 500 (server error) or the test client raised — either way
        # the transaction must have rolled back; no System row should exist.
        systems = db_session.scalars(
            select(System).where(System.tenant_id == tenant.id)
        ).all()
        assert systems == [], "Atomicity breach: system was persisted despite exception"


# ---------------------------------------------------------------------------
# GET /v1/catalogue/products/{id}/prefill — by-product prefill (WI-2)
# ---------------------------------------------------------------------------

class TestProductPrefill:
    def test_returns_facts_for_product(
        self, client, db_session, tenant, system_owner_ctx, product_high, catalogue_fact,
    ):
        """By-product prefill returns the product's catalogue facts."""
        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get(f"/v1/catalogue/products/{product_high.id}/prefill")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        body = r.json()
        assert body["catalogue_product_id"] == str(product_high.id)
        assert len(body["facts"]) == 1
        assert body["facts"][0]["key"] == "data_residency"

    def test_unknown_product_returns_empty(
        self, client, db_session, tenant, system_owner_ctx,
    ):
        """Product with no facts (or unknown) → empty facts list (not 404)."""
        unknown_id = uuid.uuid4()
        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get(f"/v1/catalogue/products/{unknown_id}/prefill")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        assert r.json()["facts"] == []

    def test_by_system_prefill_still_works(
        self, client, db_session, tenant, system_owner_ctx, product_high, catalogue_fact,
    ):
        """GET /v1/systems/{id}/prefill still works via the shared resolver (DF-D2-2)."""
        # Create a system linked to product_high
        system = System(
            id=uuid.uuid4(), tenant_id=tenant.id,
            name="Prefill Test System", metadata_blob={},
            catalogue_product_id=product_high.id,
        )
        db_session.add(system)
        db_session.flush()

        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get(f"/v1/systems/{system.id}/prefill")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        body = r.json()
        assert body["catalogue_product_id"] == str(product_high.id)
        assert len(body["facts"]) == 1
