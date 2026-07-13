"""
Tests for the treatment gate + amend path (sprints/SPRINT_LIFECYCLE.md
WI-10, §8 "treatment gate").
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.base import (
    EUAIActTier,
    LifecycleState,
    ProvenanceConfidence,
    TreatmentDecision,
)
from app.schemas.assessment import AssessmentItemAmend
from app.services.assessment_service import amend_item
from app.services.lifecycle_gates import treatment_gate
from app.services.lifecycle_service import apply_transition
from tests.lifecycle_helpers import (  # noqa: F401
    _ApiCtx,
    _grant,
    _make_aiia,
    _make_control,
    _make_control_link,
    _make_ctx,
    _make_item,
    _make_risk,
    _make_system,
    _make_use_case,
    gov_roles,
    member,
    tenant,
)


class TestTreatmentGate:
    def test_no_dispositioned_risk_items_advances(self, db_session, tenant, member):
        user, _ = member
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        result = treatment_gate(use_case, db_session)
        assert result.verdict == "advance"

    def test_dispositioned_risk_no_decision_parks(self, db_session, tenant, member):
        user, _ = member
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        risk = _make_risk(db_session)
        _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED,
            risk_id=risk.id,
        )
        result = treatment_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "treatment_decision_missing"

    def test_mitigate_without_control_or_plan_parks(self, db_session, tenant, member):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        risk = _make_risk(db_session)
        _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED,
            risk_id=risk.id,
            treatment_decision=TreatmentDecision.MITIGATE,
        )
        result = treatment_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "mitigation_unsubstantiated"

    def test_mitigate_with_control_link_advances(self, db_session, tenant, member):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        risk = _make_risk(db_session)
        item = _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED,
            risk_id=risk.id,
            treatment_decision=TreatmentDecision.MITIGATE,
        )
        control = _make_control(db_session)
        _make_control_link(db_session, tenant, item, control)
        result = treatment_gate(use_case, db_session)
        assert result.verdict == "advance"

    def test_mitigate_with_plan_advances(self, db_session, tenant, member):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        risk = _make_risk(db_session)
        _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED,
            risk_id=risk.id,
            treatment_decision=TreatmentDecision.MITIGATE,
            mitigation_plan="Rotate credentials quarterly",
        )
        result = treatment_gate(use_case, db_session)
        assert result.verdict == "advance"

    def test_accept_without_rationale_parks(self, db_session, tenant, member):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        risk = _make_risk(db_session)
        _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED,
            risk_id=risk.id,
            treatment_decision=TreatmentDecision.ACCEPT,
        )
        result = treatment_gate(use_case, db_session)
        assert result.verdict == "park"
        assert result.reason_code == "acceptance_unjustified"

    def test_accept_with_rationale_advances(self, db_session, tenant, member):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        risk = _make_risk(db_session)
        _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED,
            risk_id=risk.id,
            treatment_decision=TreatmentDecision.ACCEPT,
            treatment_rationale=(
                "Low residual likelihood; cost of mitigation exceeds benefit"
            ),
        )
        result = treatment_gate(use_case, db_session)
        assert result.verdict == "advance"

    def test_proposed_risk_no_risk_id_or_ai_suggested_ignored(
        self, db_session, tenant, member
    ):
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        risk = _make_risk(db_session)
        # AI_SUGGESTED, not yet dispositioned -> not in treatment scope.
        _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.AI_SUGGESTED,
            risk_id=risk.id,
        )
        # No risk_id at all (a curated section prompt) -> not in scope either.
        _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED,
            risk_id=None,
        )
        result = treatment_gate(use_case, db_session)
        assert result.verdict == "advance"


class TestAmendItemTreatmentPath:
    def test_treatment_write_is_provenance_neutral(
        self,
        db_session,
        tenant,
        member,
        gov_roles,
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        risk = _make_risk(db_session)
        item = _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED,
            risk_id=risk.id,
        )
        ctx = _make_ctx(user, m, tenant)

        updated = amend_item(
            item.id,
            AssessmentItemAmend(
                treatment_decision=TreatmentDecision.ACCEPT,
                treatment_rationale="Acceptable residual risk",
            ),
            item.lock_version,
            ctx,
            db_session,
        )
        assert updated.treatment_decision == TreatmentDecision.ACCEPT
        assert updated.treatment_rationale == "Acceptable residual risk"
        # Provenance untouched (#9 / design doc §5.4, #5) — still
        # USER_CONFIRMED, never flipped toward USER_AMENDED.
        assert updated.provenance == ProvenanceConfidence.USER_CONFIRMED

    def test_treatment_write_on_ai_suggested_item_409(
        self,
        db_session,
        tenant,
        member,
        gov_roles,
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        risk = _make_risk(db_session)
        item = _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.AI_SUGGESTED,
            risk_id=risk.id,
        )
        ctx = _make_ctx(user, m, tenant)

        with pytest.raises(HTTPException) as exc_info:
            amend_item(
                item.id,
                AssessmentItemAmend(treatment_decision=TreatmentDecision.ACCEPT),
                item.lock_version,
                ctx,
                db_session,
            )
        assert exc_info.value.status_code == 409

    def test_treatment_complete_advances_to_pending_authorisation(
        self,
        db_session,
        tenant,
        member,
        gov_roles,
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        # Manually place the use case at TREATMENT_PENDING (as advance_use_case
        # would have, post assessment_gate) so the amend's wiring is isolated
        # from the rest of the auto-advance chain.
        apply_transition(
            db_session,
            use_case,
            "created",
            LifecycleState.VENDOR_CHECK,
            actor_user_id=user.id,
            reason="t",
        )
        apply_transition(
            db_session,
            use_case,
            "advance",
            LifecycleState.PRODUCT_CHECK,
            actor_user_id=user.id,
            reason="t",
        )
        apply_transition(
            db_session,
            use_case,
            "advance",
            LifecycleState.INTAKE,
            actor_user_id=user.id,
            reason="t",
        )
        apply_transition(
            db_session,
            use_case,
            "advance",
            LifecycleState.UNDER_ASSESSMENT,
            actor_user_id=user.id,
            reason="t",
        )
        apply_transition(
            db_session,
            use_case,
            "advance",
            LifecycleState.TREATMENT_PENDING,
            actor_user_id=user.id,
            reason="t",
        )

        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.HIGH)
        risk = _make_risk(db_session)
        item = _make_item(
            db_session,
            tenant,
            aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED,
            risk_id=risk.id,
        )
        ctx = _make_ctx(user, m, tenant)

        amend_item(
            item.id,
            AssessmentItemAmend(
                treatment_decision=TreatmentDecision.ACCEPT,
                treatment_rationale="Low impact",
            ),
            item.lock_version,
            ctx,
            db_session,
        )

        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.PENDING_AUTHORISATION
