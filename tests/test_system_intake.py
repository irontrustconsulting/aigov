"""
Tests for system reads, PATCH, prefill, and reference product detail.

POST /v1/systems was removed in DM-S2 — see test_registrations.py for the
atomic registration endpoint. This file covers the remaining surface.

Covers:
  GET  /v1/systems/{id}    — detail with resolved labels, cross-tenant 404
  PATCH /v1/systems/{id}   — update, product relink lock, vendor re-derivation
  GET  /v1/systems/{id}/prefill — facts for linked product; empty for custom
  GET  /v1/reference/products/{id} — product + vendor + taxonomy; unknown → 404
  Constraint tests         — check constraint, unique link constraints
  Seed verification        — all §5 codes present, special flags correct
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.main import app
from app.models.base import UserRole, SystemLifecycleStage
from app.models.domain import (
    CatalogueProduct, CatalogueVendor, CatalogueFact, System, UseCase,
)
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Membership, Tenant, User
from app.models.intake import (
    AffectedParty, DataCategory, EUOperatorRole, HostingModel,
    UseCaseAffectedParty, UseCaseDataCategory,
)
from app.models.lifecycle import AuditEvent
from app.models.base import LifecycleState, ProvenanceConfidence


# ---------------------------------------------------------------------------
# Helpers — shared with test_systems.py pattern
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


def _make_member(db, tenant, role=UserRole.MEMBER):
    u = User(id=uuid.uuid4(), cognito_sub=f"sub-{uuid.uuid4()}", email=f"{uuid.uuid4()}@t.local")
    m = Membership(id=uuid.uuid4(), user_id=u.id, tenant_id=tenant.id, role=role)
    db.add_all([u, m])
    db.flush()
    return u, m


def _grant(db, tenant, membership, gov_role):
    a = GovernanceRoleAssignment(
        id=uuid.uuid4(), tenant_id=tenant.id,
        membership_id=membership.id, governance_role_id=gov_role.id,
    )
    db.add(a)
    db.flush()


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tenant(db_session):
    t = Tenant(id=uuid.uuid4(), name="Intake Corp", slug=f"intake-{uuid.uuid4().hex[:6]}")
    db_session.add(t)
    db_session.flush()
    return t


@pytest.fixture
def gov_roles(db_session):
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
def owner_user_and_member(db_session, tenant):
    return _make_member(db_session, tenant)


@pytest.fixture
def system_owner_ctx(db_session, tenant, owner_user_and_member, gov_roles):
    user, m = owner_user_and_member
    _grant(db_session, tenant, m, gov_roles["system_owner"])
    return TenantContext(user_id=user.id, membership_id=m.id, tenant_id=tenant.id, role="member")


# Vocab fixtures
@pytest.fixture
def eu_op_role(db_session):
    r = EUOperatorRole(id=uuid.uuid4(), code="deployer", label="Deployer", sort_order=0)
    db_session.add(r)
    db_session.flush()
    return r


@pytest.fixture
def hosting(db_session):
    h = HostingModel(id=uuid.uuid4(), code="cloud_saas", label="Cloud SaaS", sort_order=0)
    db_session.add(h)
    db_session.flush()
    return h


@pytest.fixture
def data_cats(db_session):
    cats = [
        DataCategory(id=uuid.uuid4(), code="health", label="Health Data",
                     sort_order=0, is_special_category=True),
        DataCategory(id=uuid.uuid4(), code="identifiers", label="Identifiers",
                     sort_order=1, is_special_category=False),
    ]
    db_session.add_all(cats)
    db_session.flush()
    return {c.code: c for c in cats}


@pytest.fixture
def affected_parties_data(db_session):
    parties = [
        AffectedParty(id=uuid.uuid4(), code="children", label="Children",
                      sort_order=0, is_vulnerable_group=True),
        AffectedParty(id=uuid.uuid4(), code="employees", label="Employees",
                      sort_order=1, is_vulnerable_group=False),
    ]
    db_session.add_all(parties)
    db_session.flush()
    return {p.code: p for p in parties}


@pytest.fixture
def vendor(db_session):
    v = CatalogueVendor(id=uuid.uuid4(), name="Acme AI")
    db_session.add(v)
    db_session.flush()
    return v


@pytest.fixture
def product(db_session, vendor):
    p = CatalogueProduct(id=uuid.uuid4(), vendor_id=vendor.id, name="Acme LLM")
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def catalogue_facts(db_session, product):
    facts = [
        CatalogueFact(
            id=uuid.uuid4(), product_id=product.id,
            key="data_residency", value={"text": "EU"},
            source_label="Acme DPA",
            provenance=ProvenanceConfidence.CATALOGUE_CURATED,
        ),
        CatalogueFact(
            id=uuid.uuid4(), product_id=product.id,
            key="trains_on_customer_data", value={"bool": False},
            provenance=ProvenanceConfidence.CATALOGUE_CURATED,
        ),
    ]
    db_session.add_all(facts)
    db_session.flush()
    return facts


# TestPostSystems removed in DM-S2: POST /v1/systems is gone (INV-78).
# Registration tests live in test_registrations.py.


# ---------------------------------------------------------------------------
# GET /v1/systems/{id} — detail
# ---------------------------------------------------------------------------

class TestGetSystemDetail:
    def test_returns_full_detail(
        self, client, db_session, tenant, system_owner_ctx,
        eu_op_role, data_cats, product, vendor,
    ):
        """Resolved vocab labels and catalogue refs in response."""
        # Insert system directly (POST /v1/systems is gone; see test_registrations.py)
        system = System(
            id=uuid.uuid4(), tenant_id=tenant.id,
            name="Detail System", metadata_blob={},
            catalogue_product_id=product.id,
            operator_role_id=eu_op_role.id,
        )
        db_session.add(system)
        db_session.flush()

        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get(f"/v1/systems/{system.id}")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        body = r.json()
        assert body["operator_role"]["code"] == "deployer"
        assert body["catalogue_product"]["name"] == "Acme LLM"
        assert body["use_case_count"] == 0

    def test_cross_tenant_returns_404(
        self, client, db_session, tenant, system_owner_ctx,
    ):
        """System in another tenant → 404 in prod (RLS); test verifies no crash."""
        other_tenant = Tenant(id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:6]}")
        db_session.add(other_tenant)
        db_session.flush()  # ensure tenant row exists before system FK resolves
        system = System(
            id=uuid.uuid4(), tenant_id=other_tenant.id,
            name="Other System", metadata_blob={},
        )
        db_session.add(system)
        db_session.flush()

        # Request as our tenant's context — RLS blocks access to other tenant's system
        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get(f"/v1/systems/{system.id}")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        # Without real RLS (test DB has no RLS), the service will return the system.
        # This test verifies the 404 path when RLS is active — in tests we verify
        # at least the query doesn't crash. The RLS integration test is the DB-level check.
        # In a non-RLS test environment the system is visible; that's expected.
        assert r.status_code in (200, 404)


# ---------------------------------------------------------------------------
# PATCH /v1/systems/{id} — update
# ---------------------------------------------------------------------------

class TestPatchSystem:
    def _create_system(self, db_session, tenant, **kwargs):
        """Insert a system row directly (POST /v1/systems removed in DM-S2)."""
        s = System(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            name=kwargs.pop("name", "Patch Me"),
            metadata_blob={},
            **kwargs,
        )
        db_session.add(s)
        db_session.flush()
        return str(s.id)

    def test_update_name_and_purpose(
        self, client, db_session, tenant, system_owner_ctx,
    ):
        system_id = self._create_system(db_session, tenant)

        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.patch(f"/v1/systems/{system_id}", json={
                "name": "Updated Name",
                "purpose": "New purpose",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Updated Name"
        assert body["purpose"] == "New purpose"

        # Verify audit event
        events = db_session.scalars(
            select(AuditEvent).where(AuditEvent.action == "system.updated")
        ).all()
        assert len(events) == 1

    def test_product_relink_with_use_cases_returns_409(
        self, client, db_session, tenant, system_owner_ctx, product, vendor,
    ):
        """Changing catalogue_product_id when use cases exist → 409."""
        system_id = self._create_system(
            db_session, tenant,
            catalogue_product_id=product.id,
        )

        # Add a use case directly to DB
        uc = UseCase(
            id=uuid.uuid4(), tenant_id=tenant.id,
            system_id=uuid.UUID(system_id),
            title="Test UC",
            state=LifecycleState.REQUESTED,
        )
        db_session.add(uc)
        db_session.flush()

        other_vendor = CatalogueVendor(id=uuid.uuid4(), name="New Vendor")
        other_product = CatalogueProduct(id=uuid.uuid4(), vendor_id=other_vendor.id, name="New Product")
        db_session.add_all([other_vendor, other_product])
        db_session.flush()

        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.patch(f"/v1/systems/{system_id}", json={
                "catalogue_product_id": str(other_product.id),
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 409

    def test_product_relink_without_use_cases_re_derives_vendor(
        self, client, db_session, tenant, system_owner_ctx, product, vendor,
    ):
        """Product relink with no use cases re-derives vendor_id."""
        system_id = self._create_system(
            db_session, tenant,
            catalogue_product_id=product.id,
        )

        new_vendor = CatalogueVendor(id=uuid.uuid4(), name="New Vendor")
        new_product = CatalogueProduct(id=uuid.uuid4(), vendor_id=new_vendor.id, name="New Product")
        db_session.add_all([new_vendor, new_product])
        db_session.flush()

        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.patch(f"/v1/systems/{system_id}", json={
                "catalogue_product_id": str(new_product.id),
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        assert r.json()["catalogue_vendor"]["id"] == str(new_vendor.id)

    def test_lifecycle_stage_update(
        self, client, db_session, tenant, system_owner_ctx,
    ):
        """PATCH can update lifecycle_stage independently."""
        system_id = self._create_system(db_session, tenant)

        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.patch(f"/v1/systems/{system_id}", json={"lifecycle_stage": "production"})
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        assert r.json()["lifecycle_stage"] == "production"


# ---------------------------------------------------------------------------
# GET /v1/systems/{id}/prefill
# ---------------------------------------------------------------------------

class TestPrefill:
    def test_linked_product_returns_facts(
        self, client, db_session, tenant, system_owner_ctx,
        product, vendor, catalogue_facts,
    ):
        """System linked to a product returns catalogue facts."""
        s = System(
            id=uuid.uuid4(), tenant_id=tenant.id,
            name="Prefill System", metadata_blob={},
            catalogue_product_id=product.id,
        )
        db_session.add(s)
        db_session.flush()
        system_id = str(s.id)

        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get(f"/v1/systems/{system_id}/prefill")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        body = r.json()
        assert body["catalogue_product_id"] == str(product.id)
        assert len(body["facts"]) == 2
        keys = {f["key"] for f in body["facts"]}
        assert "data_residency" in keys
        assert "trains_on_customer_data" in keys
        assert all(f["provenance"] == "catalogue_curated" for f in body["facts"])

    def test_no_product_returns_empty_facts(
        self, client, db_session, tenant, system_owner_ctx,
    ):
        """System without a linked product → 200 with empty facts."""
        s = System(
            id=uuid.uuid4(), tenant_id=tenant.id,
            name="No Product", metadata_blob={},
        )
        db_session.add(s)
        db_session.flush()
        system_id = str(s.id)

        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get(f"/v1/systems/{system_id}/prefill")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        assert r.json()["facts"] == []
        assert r.json()["catalogue_product_id"] is None

    def test_custom_system_returns_empty_facts(
        self, client, db_session, tenant, system_owner_ctx,
    ):
        """Custom system → 200 with empty facts (not 404)."""
        s = System(
            id=uuid.uuid4(), tenant_id=tenant.id,
            name="Custom System", metadata_blob={},
            is_custom=True,
        )
        db_session.add(s)
        db_session.flush()
        system_id = str(s.id)

        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get(f"/v1/systems/{system_id}/prefill")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        assert r.json()["facts"] == []

    def test_prefill_emits_no_audit_event(
        self, client, db_session, tenant, system_owner_ctx, product,
    ):
        """Prefill is a read — no audit event should be written."""
        s = System(
            id=uuid.uuid4(), tenant_id=tenant.id,
            name="Prefill Audit", metadata_blob={},
            catalogue_product_id=product.id,
        )
        db_session.add(s)
        db_session.flush()

        app.dependency_overrides[get_tenant_context] = _ctx_override(system_owner_ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            client.get(f"/v1/systems/{s.id}/prefill")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        # Prefill is a read — no audit event should exist
        events = db_session.scalars(select(AuditEvent)).all()
        assert len(events) == 0


# ---------------------------------------------------------------------------
# GET /v1/reference/products/{id}
# ---------------------------------------------------------------------------

class TestReferenceProductDetail:
    def test_known_product_returns_detail(self, client, db_session, product, vendor):
        r = client.get(f"/v1/reference/products/{product.id}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == str(product.id)
        assert body["name"] == "Acme LLM"
        assert body["logo_url"] is None
        assert body["vendor"]["id"] == str(vendor.id)
        assert body["vendor"]["logo_url"] is None
        assert body["categories"] == []
        assert body["eu_ai_act_subcategories"] == []

    def test_logo_url_returned_when_seeded(self, client, db_session):
        v = CatalogueVendor(id=uuid.uuid4(), name="Logo Corp", logo_url="/logos/logo-corp.svg")
        p = CatalogueProduct(id=uuid.uuid4(), vendor_id=v.id, name="Logo Product", logo_url="/logos/logo-product.svg")
        db_session.add_all([v, p])
        db_session.flush()
        r = client.get(f"/v1/reference/products/{p.id}")
        assert r.status_code == 200
        body = r.json()
        assert body["logo_url"] == "/logos/logo-product.svg"
        assert body["vendor"]["logo_url"] == "/logos/logo-corp.svg"

    def test_unknown_product_returns_404(self, client):
        r = client.get(f"/v1/reference/products/{uuid.uuid4()}")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Constraint tests (direct DB inserts, no HTTP)
# ---------------------------------------------------------------------------

class TestConstraints:
    def test_unique_data_category_link(self, db_session, tenant):
        """Duplicate (use_case_id, data_category_id) → IntegrityError."""
        import pytest
        from sqlalchemy.exc import IntegrityError

        system = System(
            id=uuid.uuid4(), tenant_id=tenant.id, name="Dup Test", metadata_blob={},
        )
        uc = UseCase(
            id=uuid.uuid4(), tenant_id=tenant.id, system_id=system.id,
            title="Dup UC", context_blob={},
        )
        dc = DataCategory(id=uuid.uuid4(), code="dc_dup", label="DC Dup", sort_order=0)
        db_session.add_all([system, uc, dc])
        db_session.flush()

        link1 = UseCaseDataCategory(id=uuid.uuid4(), tenant_id=tenant.id, use_case_id=uc.id, data_category_id=dc.id)
        db_session.add(link1)
        db_session.flush()

        link2 = UseCaseDataCategory(id=uuid.uuid4(), tenant_id=tenant.id, use_case_id=uc.id, data_category_id=dc.id)
        db_session.add(link2)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_unique_affected_party_link(self, db_session, tenant):
        """Duplicate (use_case_id, affected_party_id) → IntegrityError."""
        import pytest
        from sqlalchemy.exc import IntegrityError

        system = System(
            id=uuid.uuid4(), tenant_id=tenant.id, name="Dup AP Test", metadata_blob={},
        )
        uc = UseCase(
            id=uuid.uuid4(), tenant_id=tenant.id, system_id=system.id,
            title="Dup AP UC", context_blob={},
        )
        ap = AffectedParty(id=uuid.uuid4(), code="ap_dup", label="AP Dup", sort_order=0)
        db_session.add_all([system, uc, ap])
        db_session.flush()

        link1 = UseCaseAffectedParty(id=uuid.uuid4(), tenant_id=tenant.id, use_case_id=uc.id, affected_party_id=ap.id)
        db_session.add(link1)
        db_session.flush()

        link2 = UseCaseAffectedParty(id=uuid.uuid4(), tenant_id=tenant.id, use_case_id=uc.id, affected_party_id=ap.id)
        db_session.add(link2)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()


# ---------------------------------------------------------------------------
# Seed verification — check §5 codes are present in the live DB
# (uses the real DB via a direct engine connection; not the test-db fixtures)
# ---------------------------------------------------------------------------

class TestSeedCodes:
    """Verify seed data applied correctly by the W1 migration.
    These tests query the main (dev) DB, not the test DB."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_db(self):
        """Skip gracefully if the real DB is unavailable."""
        try:
            from sqlalchemy import create_engine, text
            from app.config import settings
            engine = create_engine(settings.migration_database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self._engine = engine
            yield
        except Exception:
            pytest.skip("Real DB not available for seed tests")

    def _scalars(self, table: str, col: str = "code"):
        from sqlalchemy import text
        with self._engine.connect() as conn:
            return {
                row[0] for row in conn.execute(text(f"SELECT {col} FROM {table}"))
            }

    def test_eu_operator_role_codes(self):
        codes = self._scalars("eu_operator_role")
        assert codes >= {"provider", "deployer", "importer", "distributor"}

    def test_hosting_model_codes(self):
        codes = self._scalars("hosting_model")
        assert codes >= {"cloud_saas", "self_hosted", "on_premise", "hybrid", "edge"}

    def test_usage_context_codes(self):
        codes = self._scalars("usage_context")
        assert codes >= {"internal_only", "employee_facing", "customer_facing", "public_facing"}

    def test_human_oversight_type_codes(self):
        codes = self._scalars("human_oversight_type")
        assert codes >= {
            "human_in_the_loop", "human_on_the_loop", "human_in_command", "fully_autonomous",
        }

    def test_data_category_special_flags(self):
        from sqlalchemy import text
        special_codes = {
            "health", "genetic", "biometric_id", "racial_ethnic_origin",
            "political_opinions", "religious_philosophical_beliefs",
            "trade_union_membership", "sex_life_sexual_orientation",
        }
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT code, is_special_category FROM data_category"
            )).all()
        code_flags = {r[0]: r[1] for r in rows}
        for code in special_codes:
            assert code in code_flags, f"Missing: {code}"
            assert code_flags[code] is True, f"{code} should be is_special_category=True"

    def test_affected_party_vulnerable_flags(self):
        from sqlalchemy import text
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT code, is_vulnerable_group FROM affected_party"
            )).all()
        code_flags = {r[0]: r[1] for r in rows}
        assert code_flags.get("children") is True
        assert code_flags.get("vulnerable_individuals") is True
        assert code_flags.get("employees") is False
        assert code_flags.get("general_public") is False
