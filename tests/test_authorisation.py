"""
Tests for deployment authorisation / ATO (Sprint 6b,
sprints/SPRINT_AUTHORIZATION.md WI-2..WI-6).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import update

from app.models.assessment import Classification
from app.models.base import (
    ClassificationStatus,
    EUAIActTier,
    LifecycleState,
    ReviewDecision,
)
from app.models.lifecycle import DeploymentAuthorisation
from app.services.assessment_review_service import (
    record_review,
    reopen,
    submit_for_review,
)
from app.services.assessment_service import _is_pristine, delete_assessment
from app.services.authorisation_service import authorise_use_case
from app.services.lifecycle_service import apply_transition, re_evaluate
from tests.lifecycle_helpers import (  # noqa: F401
    _grant,
    _make_aiia,
    _make_classification,
    _make_ctx,
    _make_member,
    _make_system,
    _make_use_case,
    gov_roles,
    member,
    tenant,
)


def _owner_ctx(db_session, tenant, gov_roles):
    user, m = _make_member(db_session, tenant)
    _grant(db_session, tenant, m, gov_roles["system_owner"])
    return _make_ctx(user, m, tenant)


def _reviewer_ctx(db_session, tenant, gov_roles):
    user, m = _make_member(db_session, tenant)
    _grant(db_session, tenant, m, gov_roles["reviewer"])
    return _make_ctx(user, m, tenant)


def _authoriser_ctx(db_session, tenant, gov_roles):
    user, m = _make_member(db_session, tenant)
    _grant(db_session, tenant, m, gov_roles["authoriser"])
    return _make_ctx(user, m, tenant)


def _to_pending_authorisation(db_session, tenant, owner_ctx, reviewer_ctx):
    """Build a use case + AIIA, drive it through submit/approve to
    PENDING_AUTHORISATION (single-hop, no dispositioned risks so treatment
    is trivially satisfied — same shape as 6a's approve->advance test).

    A real Classification snapshot + ratified eu_tier are required here
    (unlike the 6a test this mirrors) because authorise_use_case
    independently recomputes the FULL vector from scratch, including
    classification_readiness — manually placing the use case past INTAKE
    via apply_transition (as 6a's test does) skips that gate's own check,
    which is fine for advance_use_case's single-state walk but not for a
    fresh full_vector() recompute.
    """
    system = _make_system(db_session, tenant)
    use_case = _make_use_case(db_session, tenant, system)
    use_case.eu_tier = EUAIActTier.LIMITED
    _make_classification(
        db_session, tenant, use_case, EUAIActTier.LIMITED,
        status=ClassificationStatus.APPROVED,
    )
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
    aiia = _make_aiia(db_session, tenant, use_case, EUAIActTier.LIMITED)
    submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)
    db_session.refresh(aiia)
    record_review(
        aiia.id, ReviewDecision.APPROVED, None,
        aiia.lock_version, reviewer_ctx, db_session,
    )
    db_session.refresh(aiia)
    db_session.refresh(use_case)
    assert use_case.state == LifecycleState.PENDING_AUTHORISATION
    return use_case, aiia


class TestAuthoriseUseCase:
    def test_wrong_state_409(self, db_session, tenant, gov_roles):
        owner_ctx = _owner_ctx(db_session, tenant, gov_roles)
        authoriser_ctx = _authoriser_ctx(db_session, tenant, gov_roles)
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)

        with pytest.raises(HTTPException) as exc:
            authorise_use_case(use_case.id, "accepted", authoriser_ctx, db_session)
        assert exc.value.status_code == 409
        del owner_ctx

    def test_lapsed_upstream_gate_409(self, db_session, tenant, gov_roles):
        owner_ctx = _owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        authoriser_ctx = _authoriser_ctx(db_session, tenant, gov_roles)
        use_case, aiia = _to_pending_authorisation(
            db_session, tenant, owner_ctx, reviewer_ctx,
        )
        # Reopen lapses assessment_approved() without touching use_case.state
        # (no advance/regression call inside reopen, design §6.3) — the
        # persisted cursor is now stale; authorise_use_case must recompute,
        # not trust it.
        reopen(aiia.id, aiia.lock_version, owner_ctx, db_session)

        with pytest.raises(HTTPException) as exc:
            authorise_use_case(use_case.id, "accepted", authoriser_ctx, db_session)
        assert exc.value.status_code == 409

    def test_self_authorise_as_approver_409(self, db_session, tenant, gov_roles):
        owner_ctx = _owner_ctx(db_session, tenant, gov_roles)
        reviewer_user, reviewer_m = _make_member(db_session, tenant)
        _grant(db_session, tenant, reviewer_m, gov_roles["reviewer"])
        _grant(db_session, tenant, reviewer_m, gov_roles["authoriser"])
        reviewer_ctx = _make_ctx(reviewer_user, reviewer_m, tenant)

        use_case, aiia = _to_pending_authorisation(
            db_session, tenant, owner_ctx, reviewer_ctx,
        )
        with pytest.raises(HTTPException) as exc:
            authorise_use_case(use_case.id, "accepted", reviewer_ctx, db_session)
        assert exc.value.status_code == 409
        del aiia

    def test_self_authorise_as_submitter_409(self, db_session, tenant, gov_roles):
        owner_user, owner_m = _make_member(db_session, tenant)
        _grant(db_session, tenant, owner_m, gov_roles["system_owner"])
        _grant(db_session, tenant, owner_m, gov_roles["authoriser"])
        owner_ctx = _make_ctx(owner_user, owner_m, tenant)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)

        use_case, aiia = _to_pending_authorisation(
            db_session, tenant, owner_ctx, reviewer_ctx,
        )
        with pytest.raises(HTTPException) as exc:
            authorise_use_case(use_case.id, "accepted", owner_ctx, db_session)
        assert exc.value.status_code == 409
        del aiia

    def test_success_writes_ato_and_transitions(self, db_session, tenant, gov_roles):
        owner_ctx = _owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        authoriser_ctx = _authoriser_ctx(db_session, tenant, gov_roles)
        use_case, aiia = _to_pending_authorisation(
            db_session, tenant, owner_ctx, reviewer_ctx,
        )

        ato = authorise_use_case(
            use_case.id, "Residual risk accepted.", authoriser_ctx, db_session,
        )
        assert ato.submission_round == aiia.submission_round
        assert ato.tier == use_case.eu_tier.value
        assert ato.assessment_version == aiia.version
        assert ato.authorised_by_user_id == authoriser_ctx.user_id
        assert ato.residual_risk_statement == "Residual risk accepted."

        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.AUTHORISED

    def test_reopen_reapprove_reauthorise_new_ato_round(
        self, db_session, tenant, gov_roles
    ):
        owner_ctx = _owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        authoriser_ctx = _authoriser_ctx(db_session, tenant, gov_roles)
        use_case, aiia = _to_pending_authorisation(
            db_session, tenant, owner_ctx, reviewer_ctx,
        )
        ato1 = authorise_use_case(
            use_case.id, "Round 1 acceptance.", authoriser_ctx, db_session,
        )
        assert ato1.submission_round == 1

        reopen(aiia.id, aiia.lock_version, owner_ctx, db_session)
        re_evaluate(db_session, use_case, owner_ctx.user_id)
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.HELD

        db_session.refresh(aiia)
        submit_for_review(aiia.id, aiia.lock_version, owner_ctx, db_session)
        db_session.refresh(aiia)
        record_review(
            aiia.id, ReviewDecision.APPROVED, None,
            aiia.lock_version, reviewer_ctx, db_session,
        )
        re_evaluate(db_session, use_case, owner_ctx.user_id)
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.PENDING_AUTHORISATION

        db_session.refresh(aiia)
        ato2 = authorise_use_case(
            use_case.id, "Round 2 acceptance.", authoriser_ctx, db_session,
        )
        assert ato2.submission_round == 2
        assert ato2.id != ato1.id

        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.AUTHORISED

        # The old ATO row is untouched.
        stale = db_session.get(DeploymentAuthorisation, ato1.id)
        assert stale.submission_round == 1


class TestReEvaluateAuthorisedState:
    def test_never_auto_restores_into_authorised(self, db_session, tenant, gov_roles):
        owner_ctx = _owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        use_case, aiia = _to_pending_authorisation(
            db_session, tenant, owner_ctx, reviewer_ctx,
        )
        del aiia
        # No ATO exists at all yet; re_evaluate must never move
        # PENDING_AUTHORISATION -> AUTHORISED on its own.
        re_evaluate(db_session, use_case, owner_ctx.user_id)
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.PENDING_AUTHORISATION

    def test_noop_when_authorised_and_still_valid(self, db_session, tenant, gov_roles):
        owner_ctx = _owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        authoriser_ctx = _authoriser_ctx(db_session, tenant, gov_roles)
        use_case, _aiia = _to_pending_authorisation(
            db_session, tenant, owner_ctx, reviewer_ctx,
        )
        authorise_use_case(use_case.id, "accepted", authoriser_ctx, db_session)
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.AUTHORISED

        re_evaluate(db_session, use_case, owner_ctx.user_id)
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.AUTHORISED  # untouched, no-op

    def test_regresses_to_held_on_reopen(self, db_session, tenant, gov_roles):
        owner_ctx = _owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        authoriser_ctx = _authoriser_ctx(db_session, tenant, gov_roles)
        use_case, aiia = _to_pending_authorisation(
            db_session, tenant, owner_ctx, reviewer_ctx,
        )
        authorise_use_case(use_case.id, "accepted", authoriser_ctx, db_session)
        db_session.refresh(aiia)

        reopen(aiia.id, aiia.lock_version, owner_ctx, db_session)
        re_evaluate(db_session, use_case, owner_ctx.user_id)
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.HELD
        assert use_case.held_from_state == LifecycleState.AUTHORISED

    def test_restore_lands_at_pending_authorisation_not_authorised(
        self, db_session, tenant, gov_roles
    ):
        """B1's second edge case: same submission cycle, ATO still
        cycle-matches, but inv 35 caps restore at pending_authorisation —
        the authoriser must re-confirm even though nothing else changed."""
        owner_ctx = _owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        authoriser_ctx = _authoriser_ctx(db_session, tenant, gov_roles)
        use_case, aiia = _to_pending_authorisation(
            db_session, tenant, owner_ctx, reviewer_ctx,
        )
        authorise_use_case(use_case.id, "accepted", authoriser_ctx, db_session)

        # Force a hold directly (simulating a transient upstream lapse with
        # no cycle change) rather than via reopen, so the ATO still matches
        # the current submission_round once restored.
        apply_transition(
            db_session, use_case, "hold", LifecycleState.HELD,
            actor_user_id=owner_ctx.user_id, reason="transient lapse",
            held_reason="transient lapse",
        )
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.HELD

        re_evaluate(db_session, use_case, owner_ctx.user_id)
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.PENDING_AUTHORISATION


class TestProhibitedFromAuthorised:
    def test_halt_legal_directly_from_authorised(self, db_session, tenant, gov_roles):
        owner_ctx = _owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        authoriser_ctx = _authoriser_ctx(db_session, tenant, gov_roles)
        use_case, _aiia = _to_pending_authorisation(
            db_session, tenant, owner_ctx, reviewer_ctx,
        )
        authorise_use_case(use_case.id, "accepted", authoriser_ctx, db_session)
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.AUTHORISED

        db_session.execute(
            update(Classification)
            .where(Classification.use_case_id == use_case.id)
            .values(is_current=False)
        )
        _make_classification(
            db_session, tenant, use_case, EUAIActTier.PROHIBITED,
            status=ClassificationStatus.APPROVED, version=2,
        )
        re_evaluate(db_session, use_case, owner_ctx.user_id)
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.HALTED_PROHIBITED


class TestPristineDeleteAtoClause:
    def test_authorised_assessment_blocks_delete(self, db_session, tenant, gov_roles):
        owner_ctx = _owner_ctx(db_session, tenant, gov_roles)
        reviewer_ctx = _reviewer_ctx(db_session, tenant, gov_roles)
        authoriser_ctx = _authoriser_ctx(db_session, tenant, gov_roles)
        use_case, aiia = _to_pending_authorisation(
            db_session, tenant, owner_ctx, reviewer_ctx,
        )
        del use_case
        authorise_use_case(aiia.use_case_id, "accepted", authoriser_ctx, db_session)
        db_session.refresh(aiia)

        assert _is_pristine(aiia, db_session) is False
        with pytest.raises(HTTPException) as exc:
            delete_assessment(aiia.id, owner_ctx, db_session)
        assert exc.value.status_code == 409
