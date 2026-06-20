"""
Shared fixtures/helpers for the lifecycle test suite (sprints/SPRINT_LIFECYCLE.md).

Not a pytest conftest.py on purpose — imported explicitly so each test
file's fixture set stays visible at the import line (this codebase's
existing per-file convention; see tests/aiia_helpers.py).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.main import app
from app.models.assessment import (
    Assessment,
    AssessmentItem,
    AssessmentItemControl,
    Classification,
)
from app.models.base import (
    ApprovalStatus,
    AssessmentStatus,
    AssessmentType,
    ClassificationStatus,
    CoverageStatus,
    EUAIActTier,
    ProvenanceConfidence,
    RiskLayer,
    RiskSource,
    TreatmentDecision,
    UserRole,
)
from app.models.domain import (
    CatalogueProduct,
    CatalogueVendor,
    ProductApproval,
    System,
    UseCase,
    VendorApproval,
)
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Membership, Tenant, User
from app.models.intake import EUOperatorRole
from app.models.knowledge import Control, Risk


@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    t = Tenant(id=uuid.uuid4(), name="Acme Corp", slug="acme-corp")
    db_session.add(t)
    db_session.flush()
    return t


def _make_member(
    db: Session,
    tenant: Tenant,
    role: UserRole = UserRole.MEMBER,
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
        ("authoriser", "Authoriser", 2),
        ("auditor", "Auditor", 3),
    ]:
        r = GovernanceRole(id=uuid.uuid4(), key=key, name=name, line_of_defence=line)
        db_session.add(r)
        roles[key] = r
    db_session.flush()
    return roles


def _grant(
    db: Session,
    tenant: Tenant,
    membership: Membership,
    role: GovernanceRole,
) -> None:
    db.add(
        GovernanceRoleAssignment(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            membership_id=membership.id,
            governance_role_id=role.id,
        )
    )
    db.flush()


def _make_system(
    db: Session,
    tenant: Tenant,
    product: CatalogueProduct | None = None,
    *,
    vendor: CatalogueVendor | None = None,
    operator_role_id: uuid.UUID | None = None,
) -> System:
    s = System(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=f"System-{uuid.uuid4().hex[:6]}",
        metadata_blob={},
        catalogue_product_id=product.id if product else None,
        catalogue_vendor_id=vendor.id if vendor else None,
        operator_role_id=operator_role_id,
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


def _make_vendor(db: Session) -> CatalogueVendor:
    v = CatalogueVendor(id=uuid.uuid4(), name=f"Vendor-{uuid.uuid4().hex[:6]}")
    db.add(v)
    db.flush()
    return v


def _make_product(db: Session, vendor: CatalogueVendor) -> CatalogueProduct:
    p = CatalogueProduct(
        id=uuid.uuid4(),
        vendor_id=vendor.id,
        name=f"Product-{uuid.uuid4().hex[:6]}",
    )
    db.add(p)
    db.flush()
    return p


def _make_vendor_approval(
    db: Session,
    tenant: Tenant,
    vendor: CatalogueVendor,
    *,
    status: ApprovalStatus = ApprovalStatus.APPROVED,
    valid_until=None,
) -> VendorApproval:
    va = VendorApproval(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        catalogue_vendor_id=vendor.id,
        status=status,
        valid_until=valid_until,
        diligence_blob={},
    )
    db.add(va)
    db.flush()
    return va


def _make_product_approval(
    db: Session,
    tenant: Tenant,
    product: CatalogueProduct,
    *,
    status: ApprovalStatus = ApprovalStatus.APPROVED,
    valid_until=None,
) -> ProductApproval:
    pa = ProductApproval(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        catalogue_product_id=product.id,
        status=status,
        valid_until=valid_until,
        diligence_blob={},
    )
    db.add(pa)
    db.flush()
    return pa


def _make_operator_role(db: Session, code: str = "deployer") -> EUOperatorRole:
    r = EUOperatorRole(id=uuid.uuid4(), code=code, label=code.capitalize())
    db.add(r)
    db.flush()
    return r


def _make_classification(
    db: Session,
    tenant: Tenant,
    use_case: UseCase,
    tier: EUAIActTier,
    *,
    status: ClassificationStatus = ClassificationStatus.APPROVED,
    version: int = 1,
) -> Classification:
    c = Classification(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        use_case_id=use_case.id,
        tier=tier,
        rationale="test rationale",
        version=version,
        is_current=True,
        status=status,
    )
    db.add(c)
    db.flush()
    return c


def _make_aiia(
    db: Session,
    tenant: Tenant,
    use_case: UseCase,
    tier_snapshot: EUAIActTier,
    *,
    classification_version: int = 1,
) -> Assessment:
    a = Assessment(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        use_case_id=use_case.id,
        type=AssessmentType.AIIA,
        parent_aiia_id=None,
        status=AssessmentStatus.DRAFT,
        tier_snapshot=tier_snapshot,
        classification_version=classification_version,
    )
    db.add(a)
    db.flush()
    return a


def _make_feeder(
    db: Session,
    tenant: Tenant,
    aiia: Assessment,
    feeder_type: AssessmentType,
) -> Assessment:
    f = Assessment(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        use_case_id=aiia.use_case_id,
        type=feeder_type,
        parent_aiia_id=aiia.id,
        status=AssessmentStatus.DRAFT,
        tier_snapshot=aiia.tier_snapshot,
        classification_version=aiia.classification_version,
    )
    db.add(f)
    db.flush()
    return f


def _make_item(
    db: Session,
    tenant: Tenant,
    assessment: Assessment,
    *,
    provenance: ProvenanceConfidence = ProvenanceConfidence.USER_CONFIRMED,
    risk_id: uuid.UUID | None = None,
    section_key: str = "risk_identification",
    treatment_decision: TreatmentDecision | None = None,
    treatment_rationale: str | None = None,
    mitigation_plan: str | None = None,
) -> AssessmentItem:
    i = AssessmentItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        assessment_id=assessment.id,
        section_key=section_key,
        risk_id=risk_id,
        provenance=provenance,
        treatment_decision=treatment_decision,
        treatment_rationale=treatment_rationale,
        mitigation_plan=mitigation_plan,
    )
    db.add(i)
    db.flush()
    return i


# ---------------------------------------------------------------------------
# API request context override (mirrors tests/aiia_helpers.py)
# ---------------------------------------------------------------------------


def _make_ctx(user: User, membership: Membership, tenant: Tenant) -> TenantContext:
    return TenantContext(
        user_id=user.id,
        membership_id=membership.id,
        tenant_id=tenant.id,
        role=membership.role.value,
    )


def _ctx_override(ctx: TenantContext):
    def _dep():
        return ctx

    return _dep


def _db_override(session: Session):
    def _dep():
        yield session
        session.flush()

    return _dep


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


# ---------------------------------------------------------------------------
# Risk / control (treatment gate, Sprint 5 WI-10)
# ---------------------------------------------------------------------------


def _make_risk(db: Session) -> Risk:
    r = Risk(
        id=uuid.uuid4(),
        code=f"RISK-{uuid.uuid4().hex[:6]}",
        title="Test risk",
        layer=RiskLayer.TECHNICAL_SECURITY,
        source=RiskSource.OWASP_LLM,
    )
    db.add(r)
    db.flush()
    return r


def _make_control(db: Session) -> Control:
    c = Control(
        id=uuid.uuid4(),
        code=f"CTRL-{uuid.uuid4().hex[:6]}",
        title="Test control",
    )
    db.add(c)
    db.flush()
    return c


def _make_control_link(
    db: Session,
    tenant: Tenant,
    item: AssessmentItem,
    control: Control,
    *,
    coverage: CoverageStatus = CoverageStatus.PARTIAL,
) -> AssessmentItemControl:
    link = AssessmentItemControl(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        item_id=item.id,
        control_id=control.id,
        coverage=coverage,
    )
    db.add(link)
    db.flush()
    return link
