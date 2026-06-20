"""
Shared fixtures/helpers for the AIIA test suite:
  tests/test_aiia.py          (Phase A — sprints/SPRINT_AIIA.md)
  tests/test_aiia_feeders.py  (Phase B — sprints/SPRINT_AIIA_FEEDERS.md)

Not a pytest conftest.py on purpose — imported explicitly so each test
file's fixture set stays visible at the import line (this codebase's
existing per-file convention; see test_use_case_classification.py).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.main import app
from app.models.assessment import AssessmentSectionTemplate, Classification
from app.models.base import (
    AssessmentType,
    ClassificationStatus,
    EUAIActTier,
    RiskLayer,
    RiskSource,
    SectionApplicability,
    UserRole,
)
from app.models.domain import (
    CatalogueProduct,
    CatalogueProductRisk,
    CatalogueVendor,
    System,
    UseCase,
)
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Membership, Tenant, User
from app.models.knowledge import Control, Risk

RISK_SECTION_KEY = "risk_identification"
OVERVIEW_SECTION_KEY = "system_overview"
STAKEHOLDERS_SECTION_KEY = "stakeholders_affected_parties"
MODEL_RISK_RISK_SECTION_KEY = "model_risk_identified_risks"
FRIA_AFFECTED_PERSONS_SECTION_KEY = "fria_affected_persons"
DPIA_DATA_CATEGORIES_SECTION_KEY = "dpia_data_categories"
MODEL_RISK_DESCRIPTION_SECTION_KEY = "model_risk_model_description"


# ---------------------------------------------------------------------------
# Tenant / membership / governance fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="Acme Corp", slug="acme-corp")
    db_session.add(t)
    db_session.flush()
    return t


def _make_member(
    db: Session, tenant: Tenant, role: UserRole = UserRole.MEMBER,
) -> tuple[User, Membership]:
    u = User(
        id=uuid.uuid4(), cognito_sub=f"sub-{uuid.uuid4()}",
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
def admin_member(db_session: Session, tenant: Tenant) -> tuple[User, Membership]:
    """An admin with zero governance roles — proves admin != governance."""
    return _make_member(db_session, tenant, role=UserRole.ADMIN)


@pytest.fixture
def gov_roles(db_session: Session) -> dict[str, GovernanceRole]:
    roles = {}
    for key, name, line in [
        ("system_owner", "System Owner", 1),
        ("contributor", "Contributor", 1),
        ("reviewer", "Reviewer", 2),
        ("authoriser", "Authoriser", 2),
        ("auditor", "Auditor", 3),
    ]:
        r = GovernanceRole(id=uuid.uuid4(), key=key, name=name, line_of_defence=line)
        db_session.add(r)
        roles[key] = r
    db_session.flush()
    return roles


def _grant(
    db: Session, tenant: Tenant, membership: Membership, role: GovernanceRole,
) -> None:
    db.add(GovernanceRoleAssignment(
        id=uuid.uuid4(), tenant_id=tenant.id,
        membership_id=membership.id, governance_role_id=role.id,
    ))
    db.flush()


# ---------------------------------------------------------------------------
# System / use case / classification
# ---------------------------------------------------------------------------

def _make_system(
    db: Session, tenant: Tenant, product: CatalogueProduct | None = None,
) -> System:
    s = System(
        id=uuid.uuid4(), tenant_id=tenant.id, name=f"System-{uuid.uuid4().hex[:6]}",
        metadata_blob={}, catalogue_product_id=product.id if product else None,
    )
    db.add(s)
    db.flush()
    return s


def _make_use_case(
    db: Session, tenant: Tenant, system: System,
    purpose: str | None = "Test purpose",
) -> UseCase:
    uc = UseCase(
        id=uuid.uuid4(), tenant_id=tenant.id, system_id=system.id,
        title="Test use case", purpose=purpose, context_blob={},
    )
    db.add(uc)
    db.flush()
    return uc


def _make_classification(
    db: Session, tenant: Tenant, use_case: UseCase, tier: EUAIActTier,
    version: int = 1,
) -> Classification:
    """Ratified classification: stamps use_case.eu_tier the same way
    snapshot_classification/sign_off_classification do in production
    (Sprint 5 WI-4 — create_aiia/classification_readiness read eu_tier, not
    the snapshot's tier, for assessable-readiness). Tests specifically
    simulating an *unsigned* context classification should stamp the
    Classification row directly instead of going through this helper."""
    c = Classification(
        id=uuid.uuid4(), tenant_id=tenant.id, use_case_id=use_case.id,
        tier=tier, rationale="test rationale", version=version, is_current=True,
        status=ClassificationStatus.APPROVED,
    )
    db.add(c)
    use_case.eu_tier = tier
    db.flush()
    return c


# ---------------------------------------------------------------------------
# Section template seeding (test DB has no seed data — Base.metadata.create_all
# only, no migrations/scripts.seed run)
# ---------------------------------------------------------------------------

def _seed_template(db: Session, tier: EUAIActTier) -> None:
    """Minimal AIIA-only template: overview + risk (required), stakeholders
    (recommended). Sufficient for Phase A tests."""
    rows = [
        (OVERVIEW_SECTION_KEY, "System Overview", SectionApplicability.REQUIRED),
        (RISK_SECTION_KEY, "Identified Risks", SectionApplicability.REQUIRED),
        (STAKEHOLDERS_SECTION_KEY, "Affected Parties",
         SectionApplicability.RECOMMENDED),
    ]
    for section_key, title, applicability in rows:
        db.add(AssessmentSectionTemplate(
            id=uuid.uuid4(), type=AssessmentType.AIIA, tier=tier,
            section_key=section_key, title=title, applicability=applicability,
            prompt=f"Prompt for {section_key}", sort_order=0,
        ))
    db.flush()


def _seed_feeder_template(
    db: Session, tier: EUAIActTier, feeder_type: AssessmentType,
) -> None:
    """Minimal section rows for one feeder type, mirroring
    data/seed/aiia_section_template.yaml's structure closely enough for
    Phase B tests: a pre-fill-target section mapped into the AIIA, plus
    (MODEL_RISK only) a risk-bearing section mapped into risk_identification."""
    if feeder_type == AssessmentType.FRIA:
        rows = [
            (FRIA_AFFECTED_PERSONS_SECTION_KEY, "Affected Persons & Groups",
             SectionApplicability.REQUIRED, STAKEHOLDERS_SECTION_KEY),
            ("fria_internal_complaint_process", "Internal Complaint Process",
             SectionApplicability.RECOMMENDED, None),
        ]
    elif feeder_type == AssessmentType.DPIA:
        rows = [
            (DPIA_DATA_CATEGORIES_SECTION_KEY, "Personal Data Categories",
             SectionApplicability.REQUIRED, OVERVIEW_SECTION_KEY),
        ]
    elif feeder_type == AssessmentType.MODEL_RISK:
        rows = [
            (MODEL_RISK_DESCRIPTION_SECTION_KEY, "Model Description",
             SectionApplicability.REQUIRED, OVERVIEW_SECTION_KEY),
            (MODEL_RISK_RISK_SECTION_KEY, "Identified Technical Risks",
             SectionApplicability.REQUIRED, RISK_SECTION_KEY),
        ]
    else:
        raise ValueError(f"not a feeder type: {feeder_type}")

    for section_key, title, applicability, target in rows:
        db.add(AssessmentSectionTemplate(
            id=uuid.uuid4(), type=feeder_type, tier=tier,
            section_key=section_key, title=title, applicability=applicability,
            prompt=f"Prompt for {section_key}", sort_order=0,
            aiia_target_section_key=target,
        ))
    db.flush()


# ---------------------------------------------------------------------------
# Catalogue / risk / control fixtures
# ---------------------------------------------------------------------------

def _make_vendor_product_risk(db: Session) -> tuple[CatalogueProduct, Risk]:
    vendor = CatalogueVendor(id=uuid.uuid4(), name=f"Vendor-{uuid.uuid4().hex[:6]}")
    db.add(vendor)
    db.flush()
    product = CatalogueProduct(id=uuid.uuid4(), vendor_id=vendor.id, name="Product X")
    db.add(product)
    db.flush()
    risk = Risk(
        id=uuid.uuid4(), code=f"RISK-{uuid.uuid4().hex[:6]}", title="Test risk",
        layer=RiskLayer.TECHNICAL_SECURITY, source=RiskSource.OWASP_LLM,
    )
    db.add(risk)
    db.flush()
    db.add(CatalogueProductRisk(
        id=uuid.uuid4(), product_id=product.id, risk_id=risk.id,
    ))
    db.flush()
    return product, risk


def _make_control(db: Session) -> Control:
    c = Control(
        id=uuid.uuid4(), code=f"CTRL-{uuid.uuid4().hex[:6]}", title="Test control",
    )
    db.add(c)
    db.flush()
    return c


# ---------------------------------------------------------------------------
# API request context override
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


def _make_ctx(user: User, membership: Membership, tenant: Tenant) -> TenantContext:
    return TenantContext(
        user_id=user.id, membership_id=membership.id,
        tenant_id=tenant.id, role=membership.role.value,
    )


class _ApiCtx:
    """Context manager: override auth deps for one request, then pop them."""

    def __init__(self, ctx: TenantContext, db: Session):
        self.ctx = ctx
        self.db = db

    def __enter__(self):
        app.dependency_overrides[get_tenant_context] = _ctx_override(self.ctx)
        app.dependency_overrides[get_tenant_db] = _db_override(self.db)
        return self

    def __exit__(self, *exc):
        app.dependency_overrides.pop(get_tenant_context, None)
        app.dependency_overrides.pop(get_tenant_db, None)
