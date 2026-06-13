"""
Tests for use-case registration and EU AI Act classification.

Sprint acceptance criteria:
  1. Product with a primary mapping → expected tier, basis stamped on the row.
  2. Product spanning categories with differing tiers → highest governs.
  3. Product in a no-primary category → REQUIRES_CONTEXT, not an error.
  4. Override → new current snapshot; prior preserved; uq_current_classification holds.
  5. POST /v1/use-cases without system_owner → 403; with it → 201.
  6. Cross-tenant isolation: one tenant cannot see another's use cases/classifications.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.main import app
from app.models.assessment import Classification
from app.models.base import EUAIActTier, UserRole
from app.models.domain import CatalogueProduct, CatalogueVendor, System, UseCase
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Membership, Tenant, User
from app.models.taxonomy import (
    EUAIActCategory,
    EUAIActSubcategory,
    ProductCategory,
    ProductCategoryEUMapping,
    ProductCategoryMembership,
)
from app.services.classification import (
    ClassificationProposal,
    resolve_classification,
    snapshot_classification,
)

# ---------------------------------------------------------------------------
# Reference data fixtures (global, no tenant_id, no RLS)
# ---------------------------------------------------------------------------

@pytest.fixture
def eu_category(db_session: Session) -> EUAIActCategory:
    cat = EUAIActCategory(id=uuid.uuid4(), code="TEST-EMPLOYMENT", name="Employment AI")
    db_session.add(cat)
    db_session.flush()
    return cat


@pytest.fixture
def high_subcategory(
    db_session: Session, eu_category: EUAIActCategory
) -> EUAIActSubcategory:
    sub = EUAIActSubcategory(
        id=uuid.uuid4(),
        category_id=eu_category.id,
        code="EMP-RECRUIT-TEST",
        name="Recruitment screening",
        tier=EUAIActTier.HIGH,
        legal_ref="Annex III(4)(a)",
    )
    db_session.add(sub)
    db_session.flush()
    return sub


@pytest.fixture
def limited_subcategory(
    db_session: Session, eu_category: EUAIActCategory
) -> EUAIActSubcategory:
    sub = EUAIActSubcategory(
        id=uuid.uuid4(),
        category_id=eu_category.id,
        code="TRANS-SYNTH-TEST",
        name="Synthetic content",
        tier=EUAIActTier.LIMITED,
        legal_ref="Art. 50(2)",
    )
    db_session.add(sub)
    db_session.flush()
    return sub


@pytest.fixture
def product_cat_high(db_session: Session) -> ProductCategory:
    pc = ProductCategory(id=uuid.uuid4(), code="TEST-HR-HIRING", name="Hiring Tools")
    db_session.add(pc)
    db_session.flush()
    return pc


@pytest.fixture
def product_cat_limited(db_session: Session) -> ProductCategory:
    pc = ProductCategory(
        id=uuid.uuid4(), code="TEST-WRITING", name="Writing Assistants"
    )
    db_session.add(pc)
    db_session.flush()
    return pc


@pytest.fixture
def product_cat_no_mapping(db_session: Session) -> ProductCategory:
    """A category with no primary EU mapping — simulates ML platform / IDP etc."""
    pc = ProductCategory(id=uuid.uuid4(), code="TEST-PLAT-ML", name="ML Platform")
    db_session.add(pc)
    db_session.flush()
    return pc


@pytest.fixture
def vendor(db_session: Session) -> CatalogueVendor:
    v = CatalogueVendor(id=uuid.uuid4(), name="TestVendor Inc")
    db_session.add(v)
    db_session.flush()
    return v


@pytest.fixture
def product_high(
    db_session: Session,
    vendor: CatalogueVendor,
    product_cat_high: ProductCategory,
    high_subcategory: EUAIActSubcategory,
) -> CatalogueProduct:
    """Product in a single HIGH-tier category."""
    p = CatalogueProduct(id=uuid.uuid4(), vendor_id=vendor.id, name="ATS Pro")
    db_session.add(p)
    db_session.flush()
    db_session.add(ProductCategoryMembership(
        id=uuid.uuid4(),
        catalogue_product_id=p.id,
        product_category_id=product_cat_high.id,
    ))
    db_session.add(ProductCategoryEUMapping(
        id=uuid.uuid4(),
        product_category_id=product_cat_high.id,
        eu_ai_act_subcategory_id=high_subcategory.id,
        is_primary=True,
    ))
    db_session.flush()
    return p


@pytest.fixture
def product_multi_tier(
    db_session: Session,
    vendor: CatalogueVendor,
    product_cat_high: ProductCategory,
    product_cat_limited: ProductCategory,
    high_subcategory: EUAIActSubcategory,
    limited_subcategory: EUAIActSubcategory,
) -> CatalogueProduct:
    """Product in TWO categories: one HIGH, one LIMITED → highest governs."""
    p = CatalogueProduct(id=uuid.uuid4(), vendor_id=vendor.id, name="AI Suite")
    db_session.add(p)
    db_session.flush()
    db_session.add_all([
        ProductCategoryMembership(
            id=uuid.uuid4(),
            catalogue_product_id=p.id,
            product_category_id=product_cat_high.id,
        ),
        ProductCategoryMembership(
            id=uuid.uuid4(),
            catalogue_product_id=p.id,
            product_category_id=product_cat_limited.id,
        ),
        ProductCategoryEUMapping(
            id=uuid.uuid4(),
            product_category_id=product_cat_high.id,
            eu_ai_act_subcategory_id=high_subcategory.id,
            is_primary=True,
        ),
        ProductCategoryEUMapping(
            id=uuid.uuid4(),
            product_category_id=product_cat_limited.id,
            eu_ai_act_subcategory_id=limited_subcategory.id,
            is_primary=True,
        ),
    ])
    db_session.flush()
    return p


@pytest.fixture
def product_no_mapping(
    db_session: Session,
    vendor: CatalogueVendor,
    product_cat_no_mapping: ProductCategory,
) -> CatalogueProduct:
    """Product whose category has NO primary EU mapping."""
    p = CatalogueProduct(id=uuid.uuid4(), vendor_id=vendor.id, name="ML Platform")
    db_session.add(p)
    db_session.flush()
    db_session.add(ProductCategoryMembership(
        id=uuid.uuid4(),
        catalogue_product_id=p.id,
        product_category_id=product_cat_no_mapping.id,
    ))
    # No ProductCategoryEUMapping for product_cat_no_mapping → REQUIRES_CONTEXT
    db_session.flush()
    return p


# ---------------------------------------------------------------------------
# Tenant-side fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="Acme Corp", slug="acme-corp")
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
def member(db_session: Session, tenant: Tenant) -> tuple[User, Membership]:
    return _make_member(db_session, tenant)


@pytest.fixture
def gov_roles(db_session: Session) -> dict[str, GovernanceRole]:
    roles = {}
    for key, name, line in [
        ("system_owner", "System Owner", 1),
        ("contributor", "Contributor", 1),
        ("reviewer", "Reviewer", 2),
    ]:
        r = GovernanceRole(id=uuid.uuid4(), key=key, name=name, line_of_defence=line)
        db_session.add(r)
        roles[key] = r
    db_session.flush()
    return roles


def _grant_gov_role(
    db: Session, tenant: Tenant, membership: Membership, gov_role: GovernanceRole
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


def _make_system(
    db: Session, tenant: Tenant, product: CatalogueProduct | None = None
) -> System:
    s = System(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=f"System-{uuid.uuid4().hex[:6]}",
        metadata_blob={},
        catalogue_product_id=product.id if product else None,
    )
    db.add(s)
    db.flush()
    return s


def _make_use_case(db: Session, tenant: Tenant, system: System) -> UseCase:
    uc = UseCase(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        system_id=system.id,
        title="Test use case",
        context_blob={},
    )
    db.add(uc)
    db.flush()
    return uc


def _ctx_override(ctx: TenantContext):
    def _dep():
        return ctx
    return _dep


def _db_override(session: Session):
    def _dep():
        yield session
        session.flush()
    return _dep


def _make_ctx(user: User, membership: Membership, tenant: Tenant) -> TenantContext:
    return TenantContext(
        user_id=user.id,
        membership_id=membership.id,
        tenant_id=tenant.id,
        role=membership.role.value,
    )


# ---------------------------------------------------------------------------
# 1. Resolver unit tests
# ---------------------------------------------------------------------------

class TestResolver:
    def test_primary_mapping_returns_expected_tier(
        self, db_session, tenant, product_high
    ):
        system = _make_system(db_session, tenant, product_high)
        proposal = resolve_classification(system.id, db_session)

        assert proposal.tier == EUAIActTier.HIGH
        assert proposal.subcategory_code == "EMP-RECRUIT-TEST"
        assert proposal.legal_ref == "Annex III(4)(a)"
        assert not proposal.requires_context

    def test_highest_tier_governs_multi_category(
        self, db_session, tenant, product_multi_tier
    ):
        """Product in HIGH + LIMITED categories → HIGH governs."""
        system = _make_system(db_session, tenant, product_multi_tier)
        proposal = resolve_classification(system.id, db_session)

        assert proposal.tier == EUAIActTier.HIGH
        assert proposal.subcategory_code == "EMP-RECRUIT-TEST"
        assert not proposal.requires_context

    def test_no_primary_mapping_returns_requires_context(
        self, db_session, tenant, product_no_mapping
    ):
        """Product with no primary EU mapping → REQUIRES_CONTEXT, not an error."""
        system = _make_system(db_session, tenant, product_no_mapping)
        proposal = resolve_classification(system.id, db_session)

        assert proposal.tier == EUAIActTier.REQUIRES_CONTEXT
        assert proposal.subcategory_code is None
        assert proposal.legal_ref is None
        assert proposal.requires_context

    def test_no_catalogue_product_returns_requires_context(self, db_session, tenant):
        """System with no catalogue_product_id → REQUIRES_CONTEXT."""
        system = _make_system(db_session, tenant, product=None)
        proposal = resolve_classification(system.id, db_session)

        assert proposal.tier == EUAIActTier.REQUIRES_CONTEXT
        assert proposal.requires_context


# ---------------------------------------------------------------------------
# 2. Snapshot unit tests
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_snapshot_creates_current_classification(
        self, db_session, tenant, member, product_high
    ):
        user, m = member
        system = _make_system(db_session, tenant, product_high)
        use_case = _make_use_case(db_session, tenant, system)
        proposal = resolve_classification(system.id, db_session)

        classification = snapshot_classification(
            use_case, proposal, db_session, actor_user_id=user.id
        )

        assert classification.is_current is True
        assert classification.tier == EUAIActTier.HIGH
        assert classification.basis_subcategory_code == "EMP-RECRUIT-TEST"
        assert classification.basis_legal_ref == "Annex III(4)(a)"
        assert classification.version == 1
        assert use_case.eu_tier == EUAIActTier.HIGH

    def test_snapshot_unsets_prior_current(
        self, db_session, tenant, member, product_high
    ):
        """Re-classifying creates a new current row; prior is preserved."""
        user, m = member
        system = _make_system(db_session, tenant, product_high)
        use_case = _make_use_case(db_session, tenant, system)
        proposal = resolve_classification(system.id, db_session)

        first = snapshot_classification(
            use_case, proposal, db_session, actor_user_id=user.id
        )
        db_session.flush()
        second = snapshot_classification(
            use_case, proposal, db_session, actor_user_id=user.id
        )
        db_session.flush()

        db_session.refresh(first)
        assert first.is_current is False
        assert second.is_current is True
        assert second.version == 2

    def test_override_records_proposed_tier(
        self, db_session, tenant, member, product_high, limited_subcategory
    ):
        user, m = member
        system = _make_system(db_session, tenant, product_high)
        use_case = _make_use_case(db_session, tenant, system)
        original_proposal = resolve_classification(system.id, db_session)
        first = snapshot_classification(
            use_case, original_proposal, db_session, actor_user_id=user.id
        )
        db_session.flush()

        # Override to LIMITED.
        override_proposal = ClassificationProposal(
            tier=EUAIActTier.LIMITED,
            subcategory_code=limited_subcategory.code,
            subcategory_name=limited_subcategory.name,
            legal_ref=limited_subcategory.legal_ref,
            rationale="Override: TRANS-SYNTH-TEST — Synthetic content",
        )
        second = snapshot_classification(
            use_case,
            override_proposal,
            db_session,
            actor_user_id=user.id,
            overridden=True,
            proposed_tier=first.tier,
            justification="Context shows low-risk deployment",
        )
        db_session.flush()

        db_session.refresh(first)
        assert first.is_current is False
        assert second.is_current is True
        assert second.overridden is True
        assert second.proposed_tier == EUAIActTier.HIGH
        assert second.tier == EUAIActTier.LIMITED
        assert "Context shows low-risk deployment" in second.rationale

    def test_requires_context_snapshot_has_null_basis(self, db_session, tenant, member):
        """REQUIRES_CONTEXT snapshot stores no subcategory code or legal ref."""
        user, m = member
        system = _make_system(db_session, tenant, product=None)
        use_case = _make_use_case(db_session, tenant, system)
        proposal = resolve_classification(system.id, db_session)

        classification = snapshot_classification(
            use_case, proposal, db_session, actor_user_id=user.id
        )

        assert classification.tier == EUAIActTier.REQUIRES_CONTEXT
        assert classification.basis_subcategory_code is None
        assert classification.basis_legal_ref is None


# ---------------------------------------------------------------------------
# 3. HTTP integration tests — POST /v1/use-cases
# ---------------------------------------------------------------------------

class TestRegisterUseCase:
    def test_system_owner_can_register(
        self, client, db_session, tenant, member, gov_roles, product_high
    ):
        user, m = member
        _grant_gov_role(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant, product_high)

        ctx = _make_ctx(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/use-cases", json={
                "system_id": str(system.id),
                "title": "Resume screening",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        body = r.json()
        assert body["use_case"]["title"] == "Resume screening"
        assert body["classification"]["tier"] == "high_risk"
        assert body["classification"]["basis_subcategory_code"] == "EMP-RECRUIT-TEST"
        assert body["classification"]["basis_legal_ref"] == "Annex III(4)(a)"
        assert body["classification"]["requires_context"] is False

    def test_member_without_governance_role_gets_403(
        self, client, db_session, tenant, member, gov_roles, product_high
    ):
        user, m = member
        # No governance role assigned.
        system = _make_system(db_session, tenant, product_high)

        ctx = _make_ctx(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/use-cases", json={
                "system_id": str(system.id),
                "title": "Blocked",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403

    def test_wrong_governance_role_gets_403(
        self, client, db_session, tenant, member, gov_roles, product_high
    ):
        user, m = member
        _grant_gov_role(db_session, tenant, m, gov_roles["reviewer"])
        system = _make_system(db_session, tenant, product_high)

        ctx = _make_ctx(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/use-cases", json={
                "system_id": str(system.id),
                "title": "Blocked by reviewer",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 403

    def test_unknown_system_returns_404(
        self, client, db_session, tenant, member, gov_roles
    ):
        user, m = member
        _grant_gov_role(db_session, tenant, m, gov_roles["system_owner"])

        ctx = _make_ctx(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/use-cases", json={
                "system_id": str(uuid.uuid4()),
                "title": "No such system",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 404

    def test_no_catalogue_product_returns_requires_context(
        self, client, db_session, tenant, member, gov_roles
    ):
        user, m = member
        _grant_gov_role(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant, product=None)

        ctx = _make_ctx(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/use-cases", json={
                "system_id": str(system.id),
                "title": "Bespoke in-house tool",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        body = r.json()
        assert body["classification"]["tier"] == "requires_context"
        assert body["classification"]["requires_context"] is True
        assert body["classification"]["basis_subcategory_code"] is None

    def test_no_primary_mapping_returns_requires_context(
        self, client, db_session, tenant, member, gov_roles, product_no_mapping
    ):
        user, m = member
        _grant_gov_role(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant, product_no_mapping)

        ctx = _make_ctx(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/use-cases", json={
                "system_id": str(system.id),
                "title": "ML platform use case",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        assert r.json()["classification"]["tier"] == "requires_context"

    def test_multi_category_highest_tier_governs(
        self, client, db_session, tenant, member, gov_roles, product_multi_tier
    ):
        user, m = member
        _grant_gov_role(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant, product_multi_tier)

        ctx = _make_ctx(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/use-cases", json={
                "system_id": str(system.id),
                "title": "Multi-tier product",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 201
        assert r.json()["classification"]["tier"] == "high_risk"


# ---------------------------------------------------------------------------
# 4. Override tests — POST /v1/use-cases/{id}/classify/override
# ---------------------------------------------------------------------------

class TestOverride:
    def _register(self, client, db_session, tenant, user, m, gov_roles, system):
        """Register a use case via the API, return the use_case_id."""
        _grant_gov_role(db_session, tenant, m, gov_roles["system_owner"])
        ctx = _make_ctx(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/use-cases", json={
                "system_id": str(system.id),
                "title": "To be overridden",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)
        assert r.status_code == 201
        return r.json()["use_case"]["id"]

    def test_override_creates_new_current_snapshot(
        self, client, db_session, tenant, member, gov_roles,
        product_high, limited_subcategory,
    ):
        user, m = member
        system = _make_system(db_session, tenant, product_high)
        uc_id = self._register(client, db_session, tenant, user, m, gov_roles, system)

        ctx = _make_ctx(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post(f"/v1/use-cases/{uc_id}/classify/override", json={
                "tier": "limited_risk",
                "subcategory_code": limited_subcategory.code,
                "justification": "Deployment context shows low-risk",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        body = r.json()
        assert body["classification"]["tier"] == "limited_risk"
        assert body["classification"]["overridden"] is True
        assert body["classification"]["proposed_tier"] == "high_risk"

        uc_uuid = uuid.UUID(uc_id)

        # Exactly one is_current=True row.
        current_count = db_session.execute(
            select(func.count(Classification.id)).where(
                Classification.use_case_id == uc_uuid,
                Classification.is_current.is_(True),
            )
        ).scalar()
        assert current_count == 1

        # Prior snapshot preserved with is_current=False.
        total = db_session.execute(
            select(func.count(Classification.id)).where(
                Classification.use_case_id == uc_uuid,
            )
        ).scalar()
        assert total == 2

    def test_override_unknown_subcategory_gets_422(
        self, client, db_session, tenant, member, gov_roles, product_high
    ):
        user, m = member
        system = _make_system(db_session, tenant, product_high)
        uc_id = self._register(client, db_session, tenant, user, m, gov_roles, system)

        ctx = _make_ctx(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post(f"/v1/use-cases/{uc_id}/classify/override", json={
                "tier": "limited_risk",
                "subcategory_code": "DOES-NOT-EXIST",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 422

    def test_override_tier_mismatch_gets_422(
        self, client, db_session, tenant, member, gov_roles,
        product_high, limited_subcategory,
    ):
        """Requesting tier=prohibited with a limited_risk subcategory → 422."""
        user, m = member
        system = _make_system(db_session, tenant, product_high)
        uc_id = self._register(client, db_session, tenant, user, m, gov_roles, system)

        ctx = _make_ctx(user, m, tenant)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post(f"/v1/use-cases/{uc_id}/classify/override", json={
                "tier": "prohibited",
                "subcategory_code": limited_subcategory.code,  # tier is limited_risk
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 5. Cross-tenant isolation test
# ---------------------------------------------------------------------------

class TestCrossTenantIsolation:
    def test_tenant_cannot_see_other_tenants_use_cases(
        self, client, db_session, gov_roles, product_high
    ):
        """Tenant A's use cases are not returned to Tenant B's session."""
        # Set up tenant A.
        tenant_a = Tenant(id=uuid.uuid4(), name="Tenant A", slug="tenant-a")
        db_session.add(tenant_a)
        db_session.flush()
        user_a, m_a = _make_member(db_session, tenant_a)
        _grant_gov_role(db_session, tenant_a, m_a, gov_roles["system_owner"])
        system_a = _make_system(db_session, tenant_a, product_high)

        # Set up tenant B.
        tenant_b = Tenant(id=uuid.uuid4(), name="Tenant B", slug="tenant-b")
        db_session.add(tenant_b)
        db_session.flush()
        user_b, m_b = _make_member(db_session, tenant_b)

        # Register a use case under tenant A.
        ctx_a = _make_ctx(user_a, m_a, tenant_a)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx_a)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.post("/v1/use-cases", json={
                "system_id": str(system_a.id),
                "title": "Tenant A use case",
            })
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)
        assert r.status_code == 201

        # Tenant B lists use cases — must see none of tenant A's.
        ctx_b = _make_ctx(user_b, m_b, tenant_b)
        app.dependency_overrides[get_tenant_context] = _ctx_override(ctx_b)
        app.dependency_overrides[get_tenant_db] = _db_override(db_session)
        try:
            r = client.get("/v1/use-cases")
        finally:
            app.dependency_overrides.pop(get_tenant_context, None)
            app.dependency_overrides.pop(get_tenant_db, None)

        assert r.status_code == 200
        assert r.json() == []
