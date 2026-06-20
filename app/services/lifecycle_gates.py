"""
Lifecycle gate predicates (Sprint 5, WI-3) — pure reads, never mutate.

Three callers need the same gate logic — advance_use_case, the status read,
and the rollup — so it lives here once rather than inline in the advance
path (docs/STATE_MACHINE.md §1, "predicate/mutator separation"). Every gate
returns a GateResult; nothing here writes to the DB or calls db.flush()/commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

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
    EUAIActTier,
    ProvenanceConfidence,
    SectionApplicability,
    TreatmentDecision,
)
from app.models.domain import ProductApproval, System, UseCase, VendorApproval
from app.models.lifecycle import DeploymentAuthorisation

_DISPOSITIONED = (
    ProvenanceConfidence.USER_CONFIRMED,
    ProvenanceConfidence.USER_AMENDED,
)

Verdict = Literal["advance", "park", "halt"]
ResponsibleParty = Literal["user", "reviewer", "authoriser", "vendor", "system"]


@dataclass(frozen=True)
class GateResult:
    verdict: Verdict
    reason_code: str
    reason: str
    responsible_party: ResponsibleParty


def _now() -> datetime:
    return datetime.now(UTC)


def vendor_gate(use_case: UseCase, db: Session) -> GateResult:
    system = db.get(System, use_case.system_id)
    if system is None or system.catalogue_vendor_id is None:
        return GateResult(
            "advance",
            "vendor_not_applicable",
            "No vendor link on this system",
            "system",
        )
    approval = db.scalar(
        select(VendorApproval).where(
            VendorApproval.tenant_id == use_case.tenant_id,
            VendorApproval.catalogue_vendor_id == system.catalogue_vendor_id,
        )
    )
    return _approval_verdict(approval, kind="Vendor")


def product_gate(use_case: UseCase, db: Session) -> GateResult:
    system = db.get(System, use_case.system_id)
    if system is None or system.catalogue_product_id is None:
        return GateResult(
            "advance",
            "product_not_applicable",
            "No product link on this system",
            "system",
        )
    approval = db.scalar(
        select(ProductApproval).where(
            ProductApproval.tenant_id == use_case.tenant_id,
            ProductApproval.catalogue_product_id == system.catalogue_product_id,
        )
    )
    return _approval_verdict(approval, kind="Product")


def _approval_verdict(
    approval: VendorApproval | ProductApproval | None,
    *,
    kind: str,
) -> GateResult:
    if approval is None:
        return GateResult(
            "park",
            f"{kind.lower()}_not_started",
            f"{kind} clearance not yet requested",
            "authoriser",
        )
    if approval.status != ApprovalStatus.APPROVED:
        return GateResult(
            "park",
            f"{kind.lower()}_{approval.status.value}",
            f"{kind} clearance is {approval.status.value}",
            "authoriser",
        )
    if approval.valid_until is not None and approval.valid_until < _now():
        return GateResult(
            "park",
            f"{kind.lower()}_expired",
            f"{kind} clearance has expired",
            "authoriser",
        )
    return GateResult(
        "advance",
        f"{kind.lower()}_approved",
        f"{kind} clearance approved and valid",
        "system",
    )


def classification_readiness(use_case: UseCase, db: Session) -> GateResult:
    """The single readiness definition (STATE.md inv 11, design doc §5.2),
    shared by create_aiia (WI-4) and the intake gate. Read set = the current
    classification snapshot + use_case.eu_tier — prohibition reads the
    snapshot's tier (immediate on both the bridge and context paths);
    assessable-readiness reads eu_tier (only ratified at sign-off on the
    context path)."""
    snapshot = db.scalar(
        select(Classification).where(
            Classification.use_case_id == use_case.id,
            Classification.is_current.is_(True),
        )
    )
    if snapshot is None:
        # Fail-closed: shouldn't occur post-creation, every creation path
        # writes a snapshot in the same transaction.
        return GateResult(
            "park",
            "no_classification_snapshot",
            "No current classification snapshot",
            "user",
        )
    if snapshot.tier == EUAIActTier.PROHIBITED:
        return GateResult(
            "halt",
            "prohibited_practice",
            "Current classification snapshot resolves PROHIBITED",
            "system",
        )
    if use_case.eu_tier in (EUAIActTier.REQUIRES_CONTEXT, EUAIActTier.UNCLASSIFIED):
        is_pending = snapshot.status == ClassificationStatus.PENDING_REVIEW
        court: ResponsibleParty = "reviewer" if is_pending else "user"
        return GateResult(
            "park",
            "tier_not_ratified",
            "Classification tier not yet ratified (eu_tier pending)",
            court,
        )
    return GateResult(
        "advance",
        "tier_ratified",
        f"Classification tier ratified as {use_case.eu_tier.value}",
        "system",
    )


def structural_assessment_readiness(use_case: UseCase, db: Session) -> GateResult:
    """Structural completeness only (design doc §5.3, extracted Sprint 6a
    WI-2): AIIA exists, required feeders present, no still-AI_SUGGESTED item.
    The single locus for this check — shared by assessment_gate and
    create_aiia's submit-readiness pre-check (Sprint 6a design doc §4.1 D5).

    Deferred import: assessment_service imports classification_readiness
    from this module (WI-4), so a top-level import the other way would be
    circular. Both modules are fully loaded by the time any gate is called.
    """
    from app.services.assessment_service import feeder_recommendations_for

    aiia = db.scalar(
        select(Assessment).where(
            Assessment.use_case_id == use_case.id,
            Assessment.tenant_id == use_case.tenant_id,
            Assessment.type == AssessmentType.AIIA,
            Assessment.parent_aiia_id.is_(None),
        )
    )
    if aiia is None:
        return GateResult(
            "park",
            "no_aiia",
            "No assessment started for this use case",
            "user",
        )

    recs = feeder_recommendations_for(aiia, db)
    missing = [
        r
        for r in recs
        if r.applicability == SectionApplicability.REQUIRED and not r.exists
    ]
    if missing:
        names = ", ".join(r.type.value for r in missing)
        return GateResult(
            "park",
            "required_feeder_missing",
            f"Required feeder(s) missing: {names}",
            "user",
        )

    # Any still-AI_SUGGESTED item anywhere under this use case (the AIIA or
    # one of its feeders — all share use_case_id) blocks advance.
    undispositioned = db.scalar(
        select(AssessmentItem.id)
        .join(Assessment, AssessmentItem.assessment_id == Assessment.id)
        .where(
            Assessment.use_case_id == use_case.id,
            Assessment.tenant_id == use_case.tenant_id,
            AssessmentItem.provenance == ProvenanceConfidence.AI_SUGGESTED,
        )
        .limit(1)
    )
    if undispositioned is not None:
        return GateResult(
            "park",
            "undispositioned_proposed_risk",
            "A proposed risk has not been confirmed or amended",
            "user",
        )

    return GateResult(
        "advance",
        "assessment_structurally_complete",
        "Required assessment structure complete",
        "system",
    )


def assessment_approved(use_case: UseCase, db: Session) -> GateResult:
    """The reviewer sign-off term (Sprint 6a, design doc §6.1) — a human-act
    gate, never auto-satisfied. Reads the current AIIA's status directly;
    structural_assessment_readiness already established that one exists."""
    aiia = db.scalar(
        select(Assessment).where(
            Assessment.use_case_id == use_case.id,
            Assessment.tenant_id == use_case.tenant_id,
            Assessment.type == AssessmentType.AIIA,
            Assessment.parent_aiia_id.is_(None),
        )
    )
    if aiia is None or aiia.status != AssessmentStatus.APPROVED:
        return GateResult(
            "park",
            "assessment_not_approved",
            "AIIA has not been reviewed and approved",
            "reviewer",
        )
    return GateResult(
        "advance",
        "assessment_approved",
        "AIIA reviewed and approved",
        "system",
    )


def assessment_gate(use_case: UseCase, db: Session) -> GateResult:
    """structural_assessment_readiness() AND assessment_approved() (Sprint 6a
    design doc §6.1, D5) — single locus for structural readiness, AND-ed with
    the reviewer's human-act sign-off. First non-advance verdict wins."""
    structural = structural_assessment_readiness(use_case, db)
    if structural.verdict != "advance":
        return structural
    return assessment_approved(use_case, db)


def treatment_gate(use_case: UseCase, db: Session) -> GateResult:
    """Met when every dispositioned risk item (risk_id set, provenance
    USER_CONFIRMED/USER_AMENDED — across the AIIA and any feeders, same
    scope as assessment_gate's disposition check) carries a treatment
    decision: MITIGATE needs a control-link or a non-empty mitigation_plan;
    ACCEPT needs a non-empty treatment_rationale (design doc §5.4). The
    upstream assessment gate already guarantees disposition; this only
    checks the decision itself — a 1st-line act, not the Sprint-6
    Authoriser's aggregate residual-risk acceptance."""
    items = list(
        db.scalars(
            select(AssessmentItem)
            .join(Assessment, AssessmentItem.assessment_id == Assessment.id)
            .where(
                Assessment.use_case_id == use_case.id,
                Assessment.tenant_id == use_case.tenant_id,
                AssessmentItem.risk_id.is_not(None),
                AssessmentItem.provenance.in_(_DISPOSITIONED),
            )
        )
    )

    for item in items:
        if item.treatment_decision is None:
            return GateResult(
                "park",
                "treatment_decision_missing",
                f"Risk item {item.id} has no treatment decision",
                "user",
            )
        if item.treatment_decision == TreatmentDecision.MITIGATE:
            has_control_link = db.scalar(
                select(AssessmentItemControl.id)
                .where(AssessmentItemControl.item_id == item.id)
                .limit(1)
            )
            if has_control_link is None and not (item.mitigation_plan or "").strip():
                return GateResult(
                    "park",
                    "mitigation_unsubstantiated",
                    f"Risk item {item.id}: MITIGATE needs a control link or "
                    "a mitigation plan",
                    "user",
                )
        elif item.treatment_decision == TreatmentDecision.ACCEPT:
            if not (item.treatment_rationale or "").strip():
                return GateResult(
                    "park",
                    "acceptance_unjustified",
                    f"Risk item {item.id}: ACCEPT needs a treatment rationale",
                    "user",
                )

    return GateResult(
        "advance",
        "treatment_complete",
        "Every dispositioned risk has a substantiated treatment decision",
        "system",
    )


def authorisation_gate(use_case: UseCase, db: Session) -> GateResult:
    """assessment_approved() AND a cycle-matched DeploymentAuthorisation
    (Sprint 6b, design doc §6.1, D11) — a human-act gate, never auto-
    satisfied. Existence of an ATO is NOT sufficient: its submission_round
    must equal the current AIIA's submission_round, or a re-submitted cycle
    would silently pass off a stale grant (inv 37)."""
    approved = assessment_approved(use_case, db)
    if approved.verdict != "advance":
        return approved

    aiia = db.scalar(
        select(Assessment).where(
            Assessment.use_case_id == use_case.id,
            Assessment.tenant_id == use_case.tenant_id,
            Assessment.type == AssessmentType.AIIA,
            Assessment.parent_aiia_id.is_(None),
        )
    )
    matching_ato = db.scalar(
        select(DeploymentAuthorisation.id)
        .where(
            DeploymentAuthorisation.use_case_id == use_case.id,
            DeploymentAuthorisation.tenant_id == use_case.tenant_id,
            DeploymentAuthorisation.submission_round == aiia.submission_round,
        )
        .limit(1)
    )
    if matching_ato is None:
        return GateResult(
            "park",
            "no_current_authorisation",
            "No deployment authorisation for the current submission cycle",
            "authoriser",
        )
    return GateResult(
        "advance",
        "authorised_for_current_cycle",
        "Deployment authorisation granted for the current submission cycle",
        "system",
    )
