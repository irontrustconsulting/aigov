"""
Tests for the lifecycle gate predicates (sprints/SPRINT_LIFECYCLE.md WI-3,
§8 "vendor/product gates", "assessment gate", "intake / readiness").
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.base import (
    ApprovalStatus,
    AssessmentStatus,
    AssessmentType,
    ClassificationStatus,
    EUAIActTier,
    ProvenanceConfidence,
)
from app.services.lifecycle_gates import (
    assessment_approved,
    assessment_gate,
    authorisation_gate,
    classification_readiness,
    product_gate,
    structural_assessment_readiness,
    vendor_gate,
)
from tests.lifecycle_helpers import (  # noqa: F401
    _make_aiia,
    _make_ato,
    _make_classification,
    _make_feeder,
    _make_item,
    _make_member,
    _make_operator_role,
    _make_product,
    _make_product_approval,
    _make_system,
    _make_use_case,
    _make_vendor,
    _make_vendor_approval,
    tenant,
)


def _future() -> datetime:
    return datetime.now(UTC) + timedelta(days=30)


def _past() -> datetime:
    return datetime.now(UTC) - timedelta(days=1)


class TestVendorGate:
    def test_no_vendor_link_advances(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        result = vendor_gate(use_case, db_session)
        assert result.verdict == "advance"
        assert result.reason_code == "vendor_not_applicable"

    def test_no_approval_row_parks(self, db_session: Session, tenant):
        vendor = _make_vendor(db_session)
        system = _make_system(db_session, tenant, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)
        result = vendor_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "vendor_not_started"
        assert result.responsible_party == "authoriser"

    def test_pending_approval_parks(self, db_session: Session, tenant):
        vendor = _make_vendor(db_session)
        system = _make_system(db_session, tenant, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)
        _make_vendor_approval(
            db_session,
            tenant,
            vendor,
            status=ApprovalStatus.UNDER_REVIEW,
        )
        result = vendor_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "vendor_under_review"

    def test_expired_approval_parks(self, db_session: Session, tenant):
        vendor = _make_vendor(db_session)
        system = _make_system(db_session, tenant, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)
        _make_vendor_approval(
            db_session,
            tenant,
            vendor,
            status=ApprovalStatus.APPROVED,
            valid_until=_past(),
        )
        result = vendor_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "vendor_expired"

    def test_approved_and_valid_advances(self, db_session: Session, tenant):
        vendor = _make_vendor(db_session)
        system = _make_system(db_session, tenant, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)
        _make_vendor_approval(
            db_session,
            tenant,
            vendor,
            status=ApprovalStatus.APPROVED,
            valid_until=_future(),
        )
        result = vendor_gate(use_case, db_session)
        assert result.verdict == "advance"
        assert result.reason_code == "vendor_approved"

    def test_approved_no_expiry_advances(self, db_session: Session, tenant):
        vendor = _make_vendor(db_session)
        system = _make_system(db_session, tenant, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)
        _make_vendor_approval(
            db_session,
            tenant,
            vendor,
            status=ApprovalStatus.APPROVED,
            valid_until=None,
        )
        result = vendor_gate(use_case, db_session)
        assert result.verdict == "advance"


class TestProductGate:
    def test_no_product_link_advances(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        result = product_gate(use_case, db_session)
        assert result.verdict == "advance"
        assert result.reason_code == "product_not_applicable"

    def test_no_approval_row_parks(self, db_session: Session, tenant):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        system = _make_system(db_session, tenant, product=product)
        use_case = _make_use_case(db_session, tenant, system)
        result = product_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "product_not_started"

    def test_expired_approval_parks(self, db_session: Session, tenant):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        system = _make_system(db_session, tenant, product=product)
        use_case = _make_use_case(db_session, tenant, system)
        _make_product_approval(
            db_session,
            tenant,
            product,
            status=ApprovalStatus.APPROVED,
            valid_until=_past(),
        )
        result = product_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "product_expired"

    def test_approved_and_valid_advances(self, db_session: Session, tenant):
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        system = _make_system(db_session, tenant, product=product)
        use_case = _make_use_case(db_session, tenant, system)
        _make_product_approval(
            db_session,
            tenant,
            product,
            status=ApprovalStatus.APPROVED,
            valid_until=_future(),
        )
        result = product_gate(use_case, db_session)
        assert result.verdict == "advance"
        assert result.reason_code == "product_approved"


class TestClassificationReadiness:
    def test_no_snapshot_parks_fail_closed(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        result = classification_readiness(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "no_classification_snapshot"

    def test_prohibited_snapshot_halts(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        _make_classification(db_session, tenant, use_case, EUAIActTier.PROHIBITED)
        result = classification_readiness(use_case, db_session)
        assert result.verdict == "halt"
        assert result.reason_code == "prohibited_practice"

    def test_requires_context_pending_review_courts_reviewer(
        self,
        db_session: Session,
        tenant,
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        use_case.eu_tier = EUAIActTier.REQUIRES_CONTEXT
        _make_classification(
            db_session,
            tenant,
            use_case,
            EUAIActTier.REQUIRES_CONTEXT,
            status=ClassificationStatus.PENDING_REVIEW,
        )
        db_session.flush()
        result = classification_readiness(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "tier_not_ratified"
        assert result.responsible_party == "reviewer"

    def test_requires_context_no_pending_review_courts_user(
        self,
        db_session: Session,
        tenant,
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        use_case.eu_tier = EUAIActTier.REQUIRES_CONTEXT
        # Current snapshot already approved (e.g. a stale tier reference) —
        # not awaiting reviewer action, so the court is the user.
        _make_classification(
            db_session,
            tenant,
            use_case,
            EUAIActTier.LIMITED,
            status=ClassificationStatus.APPROVED,
        )
        db_session.flush()
        result = classification_readiness(use_case, db_session)
        assert result.verdict == "park"
        assert result.responsible_party == "user"

    def test_signed_off_high_advances(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        use_case.eu_tier = EUAIActTier.HIGH
        _make_classification(
            db_session,
            tenant,
            use_case,
            EUAIActTier.HIGH,
            status=ClassificationStatus.APPROVED,
        )
        db_session.flush()
        result = classification_readiness(use_case, db_session)
        assert result.verdict == "advance"
        assert result.reason_code == "tier_ratified"


class TestStructuralAssessmentReadiness:
    """The structural-only term (Sprint 6a WI-2 extraction) — exactly the
    behaviour assessment_gate had before the reviewer-approval AND-term."""

    def test_no_aiia_parks(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        result = structural_assessment_readiness(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "no_aiia"

    def test_required_fria_missing_parks(self, db_session: Session, tenant):
        deployer = _make_operator_role(db_session, "deployer")
        system = _make_system(db_session, tenant, operator_role_id=deployer.id)
        use_case = _make_use_case(db_session, tenant, system)
        _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        result = structural_assessment_readiness(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "required_feeder_missing"
        assert "fria" in result.reason.lower()

    def test_undispositioned_proposed_risk_parks(
        self,
        db_session: Session,
        tenant,
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.AI_SUGGESTED,
        )
        result = structural_assessment_readiness(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "undispositioned_proposed_risk"

    def test_dispositioned_items_no_required_feeders_advances(
        self,
        db_session: Session,
        tenant,
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED,
        )
        result = structural_assessment_readiness(use_case, db_session)
        assert result.verdict == "advance"
        assert result.reason_code == "assessment_structurally_complete"

    def test_required_fria_present_advances(self, db_session: Session, tenant):
        deployer = _make_operator_role(db_session, "deployer")
        system = _make_system(db_session, tenant, operator_role_id=deployer.id)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        _make_feeder(db_session, tenant, aiia, AssessmentType.FRIA)
        result = structural_assessment_readiness(use_case, db_session)
        assert result.verdict == "advance"


class TestAssessmentApproved:
    def test_aiia_draft_parks(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        result = assessment_approved(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "assessment_not_approved"
        assert result.responsible_party == "reviewer"

    def test_aiia_approved_advances(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        aiia.status = AssessmentStatus.APPROVED
        db_session.flush()
        result = assessment_approved(use_case, db_session)
        assert result.verdict == "advance"
        assert result.reason_code == "assessment_approved"


class TestAssessmentGate:
    """assessment_gate = structural_assessment_readiness() AND
    assessment_approved() (Sprint 6a, design doc §6.1, D5)."""

    def test_no_aiia_parks(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        result = assessment_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "no_aiia"

    def test_structurally_complete_but_not_approved_blocks(
        self, db_session: Session, tenant
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED,
        )
        result = assessment_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "assessment_not_approved"

    def test_structurally_complete_and_approved_advances(
        self, db_session: Session, tenant
    ):
        deployer = _make_operator_role(db_session, "deployer")
        system = _make_system(db_session, tenant, operator_role_id=deployer.id)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        _make_feeder(db_session, tenant, aiia, AssessmentType.FRIA)
        aiia.status = AssessmentStatus.APPROVED
        db_session.flush()
        result = assessment_gate(use_case, db_session)
        assert result.verdict == "advance"


class TestAuthorisationGate:
    """assessment_approved() AND a cycle-matched DeploymentAuthorisation
    (Sprint 6b, design doc §6.1, D11) — existence alone is not sufficient."""

    def test_not_approved_parks(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        result = authorisation_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "assessment_not_approved"

    def test_approved_no_ato_parks(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        aiia.status = AssessmentStatus.APPROVED
        db_session.flush()
        result = authorisation_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "no_current_authorisation"

    def test_round_mismatched_ato_parks(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        aiia.status = AssessmentStatus.APPROVED
        aiia.submission_round = 2
        db_session.flush()
        authoriser, _m = _make_member(db_session, tenant)
        # Stale ATO from a prior cycle — existence alone must not pass.
        _make_ato(db_session, tenant, use_case, aiia, authoriser, submission_round=1)

        result = authorisation_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "no_current_authorisation"

    def test_round_matched_ato_advances(self, db_session: Session, tenant):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        aiia.status = AssessmentStatus.APPROVED
        aiia.submission_round = 2
        db_session.flush()
        authoriser, _m = _make_member(db_session, tenant)
        _make_ato(db_session, tenant, use_case, aiia, authoriser, submission_round=2)

        result = authorisation_gate(use_case, db_session)
        assert result.verdict == "advance"
        assert result.reason_code == "authorised_for_current_cycle"
