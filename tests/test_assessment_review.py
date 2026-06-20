"""
Tests for AIIA review & sign-off (Sprint 6a,
sprints/SPRINT_AUTHORIZATION_6A.md WI-4..WI-7).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.base import (
    AssessmentStatus,
    AssessmentType,
    EUAIActTier,
    LifecycleState,
    ProvenanceConfidence,
    ReviewDecision,
)
from app.schemas.assessment import AssessmentItemAmend
from app.services.assessment_review_service import (
    list_review_queue,
    record_review,
    reopen,
    submit_for_review,
)
from app.services.assessment_service import (
    _is_pristine,
    amend_item,
    confirm_item,
    delete_assessment,
)
from app.services.lifecycle_service import re_evaluate
from tests.lifecycle_helpers import (  # noqa: F401
    _grant,
    _make_aiia,
    _make_ctx,
    _make_feeder,
    _make_item,
    _make_member,
    _make_risk,
    _make_system,
    _make_use_case,
    gov_roles,
    member,
    tenant,
)


def _system_owner_ctx(db_session, tenant, gov_roles):
    user, m = _make_member(db_session, tenant)
    _grant(db_session, tenant, m, gov_roles["system_owner"])
    return _make_ctx(user, m, tenant)


def _reviewer_ctx(db_session, tenant, gov_roles):
    user, m = _make_member(db_session, tenant)
    _grant(db_session, tenant, m, gov_roles["reviewer"])
    return _make_ctx(user, m, tenant)


class TestSubmitForReview:
    def test_structurally_incomplete_409(self, db_session, tenant, gov_roles):
        ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        _make_item(
            db_session, tenant, aiia, provenance=ProvenanceConfidence.AI_SUGGESTED,
        )

        with pytest.raises(HTTPException) as exc:
            submit_for_review(aiia.id, aiia.lock_version, ctx, db_session)
        assert exc.value.status_code == 409

    def test_untreated_risk_409(self, db_session, tenant, gov_roles):
        ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        risk = _make_risk(db_session)
        _make_item(
            db_session, tenant, aiia,
            provenance=ProvenanceConfidence.USER_CONFIRMED, risk_id=risk.id,
        )

        with pytest.raises(HTTPException) as exc:
            submit_for_review(aiia.id, aiia.lock_version, ctx, db_session)
        assert exc.value.status_code == 409

    def test_success_bumps_round_and_stamps_submitter(
        self, db_session, tenant, gov_roles
    ):
        ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)

        result = submit_for_review(aiia.id, aiia.lock_version, ctx, db_session)
        assert result.status == AssessmentStatus.IN_REVIEW
        assert result.submission_round == 1
        assert result.submitted_by_user_id == ctx.user_id
        assert result.submitted_at is not None

    def test_stale_lock_412(self, db_session, tenant, gov_roles):
        ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)

        with pytest.raises(HTTPException) as exc:
            submit_for_review(aiia.id, aiia.lock_version + 1, ctx, db_session)
        assert exc.value.status_code == 412

    def test_wrong_from_state_409(self, db_session, tenant, gov_roles):
        ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        submit_for_review(aiia.id, aiia.lock_version, ctx, db_session)

        with pytest.raises(HTTPException) as exc:
            submit_for_review(aiia.id, aiia.lock_version, ctx, db_session)
        assert exc.value.status_code == 409


class TestRecordReview:
    def test_self_review_409(self, db_session, tenant, gov_roles):
        user, m = _make_member(db_session, tenant)
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        _grant(db_session, tenant, m, gov_roles["reviewer"])
        ctx = _make_ctx(user, m, tenant)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        submit_for_review(aiia.id, aiia.lock_version, ctx, db_session)
        db_session.refresh(aiia)

        with pytest.raises(HTTPException) as exc:
            record_review(
                aiia.id, ReviewDecision.APPROVED, None,
                aiia.lock_version, ctx, db_session,
            )
        assert exc.value.status_code == 409

    def test_changes_requested_without_note_422(self, db_session, tenant, gov_roles):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)
        db_session.refresh(aiia)

        with pytest.raises(HTTPException) as exc:
            record_review(
                aiia.id, ReviewDecision.CHANGES_REQUESTED, None,
                aiia.lock_version, reviewer_ctx, db_session,
            )
        assert exc.value.status_code == 422

    def test_changes_requested_bounces_to_draft(self, db_session, tenant, gov_roles):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)
        db_session.refresh(aiia)

        result = record_review(
            aiia.id, ReviewDecision.CHANGES_REQUESTED, "needs more detail",
            aiia.lock_version, reviewer_ctx, db_session,
        )
        assert result.status == AssessmentStatus.DRAFT

    def test_approve_stamps_and_advances_use_case(
        self, db_session, tenant, gov_roles
    ):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)
        db_session.refresh(aiia)

        from app.services.lifecycle_service import apply_transition

        # Place the use case at UNDER_ASSESSMENT (as advance_use_case would
        # have, isolating the approve->advance wiring from the rest of the
        # auto-advance chain — same convention as test_lifecycle_treatment.py).
        apply_transition(
            db_session, use_case, "created", LifecycleState.VENDOR_CHECK,
            actor_user_id=owner_ctx.user_id, reason="t",
        )
        apply_transition(
            db_session, use_case, "advance", LifecycleState.PRODUCT_CHECK,
            actor_user_id=owner_ctx.user_id, reason="t",
        )
        apply_transition(
            db_session, use_case, "advance", LifecycleState.INTAKE,
            actor_user_id=owner_ctx.user_id, reason="t",
        )
        apply_transition(
            db_session, use_case, "advance", LifecycleState.UNDER_ASSESSMENT,
            actor_user_id=owner_ctx.user_id, reason="t",
        )

        result = record_review(
            aiia.id, ReviewDecision.APPROVED, None,
            aiia.lock_version, reviewer_ctx, db_session,
        )
        assert result.status == AssessmentStatus.APPROVED
        assert result.approved_by_user_id == reviewer_ctx.user_id

        db_session.refresh(use_case)
        # Treatment already satisfied (no dispositioned risks) -> single-hop
        # straight through treatment_pending to pending_authorisation.
        assert use_case.state == LifecycleState.PENDING_AUTHORISATION


class TestReopen:
    def test_reopen_approved_to_needs_refresh(self, db_session, tenant, gov_roles):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)
        db_session.refresh(aiia)
        record_review(
            aiia.id, ReviewDecision.APPROVED, None,
            aiia.lock_version, reviewer_ctx, db_session,
        )
        db_session.refresh(aiia)

        result = reopen(aiia.id, aiia.lock_version, owner_ctx, db_session)
        assert result.status == AssessmentStatus.NEEDS_REFRESH

    def test_reopen_non_approved_409(self, db_session, tenant, gov_roles):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)

        with pytest.raises(HTTPException) as exc:
            reopen(aiia.id, aiia.lock_version, owner_ctx, db_session)
        assert exc.value.status_code == 409

    def test_regression_caught_lazily_by_re_evaluate(
        self, db_session, tenant, gov_roles
    ):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)
        db_session.refresh(aiia)

        from app.services.lifecycle_service import apply_transition

        apply_transition(
            db_session, use_case, "created", LifecycleState.VENDOR_CHECK,
            actor_user_id=owner_ctx.user_id, reason="t",
        )
        apply_transition(
            db_session, use_case, "advance", LifecycleState.PRODUCT_CHECK,
            actor_user_id=owner_ctx.user_id, reason="t",
        )
        apply_transition(
            db_session, use_case, "advance", LifecycleState.INTAKE,
            actor_user_id=owner_ctx.user_id, reason="t",
        )
        apply_transition(
            db_session, use_case, "advance", LifecycleState.UNDER_ASSESSMENT,
            actor_user_id=owner_ctx.user_id, reason="t",
        )
        record_review(
            aiia.id, ReviewDecision.APPROVED, None,
            aiia.lock_version, reviewer_ctx, db_session,
        )
        db_session.refresh(aiia)
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.PENDING_AUTHORISATION

        reopen(aiia.id, aiia.lock_version, owner_ctx, db_session)
        # No advance/regression call inside reopen() itself (design §6.3) —
        # the use case still reads PENDING_AUTHORISATION until something
        # consequential re-evaluates it.
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.PENDING_AUTHORISATION

        re_evaluate(db_session, use_case, owner_ctx.user_id)
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.HELD


class TestReviewQueue:
    def test_excludes_own_submission_and_resolves_name_via_membership(
        self, db_session, tenant, gov_roles
    ):
        owner_user, owner_m = _make_member(db_session, tenant)
        owner_user.display_name = "Sam Owner"
        _grant(db_session, tenant, owner_m, gov_roles["system_owner"])
        owner_ctx = _make_ctx(owner_user, owner_m, tenant)

        reviewer_user, reviewer_m = _make_member(db_session, tenant)
        _grant(db_session, tenant, reviewer_m, gov_roles["reviewer"])
        reviewer_ctx = _make_ctx(reviewer_user, reviewer_m, tenant)

        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)
        db_session.flush()

        # The reviewer sees it queued, with the submitter's name resolved.
        queue = list_review_queue(reviewer_ctx, db_session)
        assert len(queue) == 1
        assert queue[0].assessment_id == aiia.id
        assert queue[0].submitted_by_name == "Sam Owner"
        assert queue[0].submitted_by_email == owner_user.email

        # The submitter themself (even if also a reviewer) never sees their
        # own submission in the queue.
        owner_as_reviewer_ctx = _make_ctx(owner_user, owner_m, tenant)
        queue_for_owner = list_review_queue(owner_as_reviewer_ctx, db_session)
        assert queue_for_owner == []


class TestPristineDeleteHistoryAware:
    def test_all_blank_approved_aiia_blocks_delete(
        self, db_session, tenant, gov_roles
    ):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)
        db_session.refresh(aiia)
        record_review(
            aiia.id, ReviewDecision.APPROVED, None,
            aiia.lock_version, reviewer_ctx, db_session,
        )
        db_session.refresh(aiia)

        assert _is_pristine(aiia, db_session) is False
        with pytest.raises(HTTPException) as exc:
            delete_assessment(aiia.id, owner_ctx, db_session)
        assert exc.value.status_code == 409

    def test_reviewed_then_bounced_draft_still_blocks_delete(
        self, db_session, tenant, gov_roles
    ):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)
        db_session.refresh(aiia)
        record_review(
            aiia.id, ReviewDecision.CHANGES_REQUESTED, "fix it",
            aiia.lock_version, reviewer_ctx, db_session,
        )
        db_session.refresh(aiia)

        # Back in DRAFT, but a review row now references it.
        assert aiia.status == AssessmentStatus.DRAFT
        assert _is_pristine(aiia, db_session) is False

    def test_never_reviewed_draft_is_pristine(self, db_session, tenant, gov_roles):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)

        assert _is_pristine(aiia, db_session) is True
        delete_assessment(aiia.id, owner_ctx, db_session)


class TestStatusAwareAuthoringLock:
    def test_amend_item_locked_under_in_review(self, db_session, tenant, gov_roles):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        item = _make_item(
            db_session, tenant, aiia, provenance=ProvenanceConfidence.USER_CONFIRMED,
        )
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)

        with pytest.raises(HTTPException) as exc:
            amend_item(
                item.id,
                AssessmentItemAmend(response="late edit"),
                item.lock_version,
                owner_ctx,
                db_session,
            )
        assert exc.value.status_code == 409

    def test_feeder_item_locked_when_parent_aiia_in_review(
        self, db_session, tenant, gov_roles
    ):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        feeder = _make_feeder(db_session, tenant, aiia, AssessmentType.MODEL_RISK)
        item = _make_item(
            db_session, tenant, feeder, provenance=ProvenanceConfidence.USER_CONFIRMED,
        )
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)

        with pytest.raises(HTTPException) as exc:
            amend_item(
                item.id,
                AssessmentItemAmend(response="late edit"),
                item.lock_version,
                owner_ctx,
                db_session,
            )
        assert exc.value.status_code == 409

    def test_confirm_item_locked_under_approved(self, db_session, tenant, gov_roles):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)
        db_session.refresh(aiia)
        record_review(
            aiia.id, ReviewDecision.APPROVED, None,
            aiia.lock_version, reviewer_ctx, db_session,
        )
        # Added post-approval (a pre-existing AI_SUGGESTED item would have
        # blocked submit's structural-readiness pre-check).
        item = _make_item(
            db_session, tenant, aiia, provenance=ProvenanceConfidence.AI_SUGGESTED,
        )

        with pytest.raises(HTTPException) as exc:
            confirm_item(item.id, item.lock_version, owner_ctx, db_session)
        assert exc.value.status_code == 409

    def test_amend_item_unlocked_under_draft(self, db_session, tenant, gov_roles):
        owner_ctx = _system_owner_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
        item = _make_item(
            db_session, tenant, aiia, provenance=ProvenanceConfidence.USER_CONFIRMED,
        )

        result = amend_item(
            item.id,
            AssessmentItemAmend(response="fine to edit"),
            item.lock_version,
            owner_ctx,
            db_session,
        )
        assert result.response == "fine to edit"
