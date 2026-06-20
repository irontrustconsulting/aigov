"""
Tests for the lifecycle status/re-evaluate endpoints and full_vector/
re_evaluate (sprints/SPRINT_LIFECYCLE.md WI-6, §8 "full-vector / cursor /
expiry").
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.base import ApprovalStatus, EUAIActTier, LifecycleState
from app.services.classification import ClassificationProposal, snapshot_classification
from app.services.lifecycle_service import full_vector, re_evaluate
from tests.lifecycle_helpers import (  # noqa: F401
    _ApiCtx,
    _grant,
    _make_ctx,
    _make_product,
    _make_product_approval,
    _make_system,
    _make_use_case,
    _make_vendor,
    _make_vendor_approval,
    gov_roles,
    member,
    tenant,
)


def _past() -> datetime:
    return datetime.now(UTC) - timedelta(days=1)


def _future() -> datetime:
    return datetime.now(UTC) + timedelta(days=30)


def _bridge_proposal(tier: EUAIActTier) -> ClassificationProposal:
    return ClassificationProposal(
        tier=tier,
        subcategory_code="TEST-CODE",
        subcategory_name="Test",
        legal_ref=None,
        rationale="test rationale",
    )


class TestStatusEndpoint:
    def test_get_recomputes_and_does_not_mutate_state(
        self,
        client,
        db_session: Session,
        tenant,
        member,
        gov_roles,
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT

        # Now drop the use case's eu_tier back to simulate a regression
        # without re-running advance — proves the GET shows the live
        # computed verdict, not whatever apply_transition last wrote.
        # (We don't actually need to fabricate park/halt here: the point is
        # a GET must never itself change use_case.state.)
        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.get(f"/v1/use-cases/{use_case.id}/lifecycle")
        assert r.status_code == 200
        body = r.json()
        assert body["state"] == "under_assessment"
        assert len(body["gates"]) == 5
        assert body["blocking"]["reason_code"] == "no_aiia"

        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT  # unchanged


class TestReEvaluateEndpoint:
    def test_post_advances_and_persists(
        self,
        client,
        db_session: Session,
        tenant,
        member,
        gov_roles,
    ):
        user, m = member
        _grant(db_session, tenant, m, gov_roles["system_owner"])
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        system = _make_system(db_session, tenant, product, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)
        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        # Parked at VENDOR_CHECK — no approval rows yet.
        assert use_case.state == LifecycleState.VENDOR_CHECK

        _make_vendor_approval(db_session, tenant, vendor)
        _make_product_approval(db_session, tenant, product)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/lifecycle/re-evaluate")
        assert r.status_code == 200
        assert r.json()["state"] == "under_assessment"
        db_session.refresh(use_case)
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT

    def test_non_system_owner_403(
        self,
        client,
        db_session: Session,
        tenant,
        member,
    ):
        user, m = member  # plain MEMBER role, no governance grant
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)

        ctx = _make_ctx(user, m, tenant)
        with _ApiCtx(ctx, db_session):
            r = client.post(f"/v1/use-cases/{use_case.id}/lifecycle/re-evaluate")
        assert r.status_code == 403


class TestExpiryAndHold:
    def test_approval_expires_post_advance_get_shows_held_then_re_evaluate_persists(
        self,
        db_session: Session,
        tenant,
        member,
    ):
        user, _ = member
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        va = _make_vendor_approval(
            db_session,
            tenant,
            vendor,
            status=ApprovalStatus.APPROVED,
            valid_until=_future(),
        )
        _make_product_approval(db_session, tenant, product)
        system = _make_system(db_session, tenant, product, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)

        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT

        # Time passes, the vendor approval lapses — no event fires.
        va.valid_until = _past()
        db_session.flush()

        # GET-equivalent: full_vector shows the gap without persisting.
        vector = full_vector(use_case, db_session)
        blocking = next(r for s, r in vector if r.verdict != "advance")
        assert blocking.reason_code == "vendor_expired"
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT  # not yet moved

        # Consequential write: re-evaluate regresses it to held.
        re_evaluate(db_session, use_case, user.id)
        assert use_case.state == LifecycleState.HELD
        assert use_case.held_from_state == LifecycleState.UNDER_ASSESSMENT
        assert "vendor" in use_case.held_reason.lower()

    def test_unhold_with_second_lapse_rests_at_earliest_unsatisfied_gate(
        self,
        db_session: Session,
        tenant,
        member,
    ):
        """held at under_assessment (vendor revoked); product then expires;
        vendor re-cleared; re-evaluate rests at product_check, not
        under_assessment (design doc §4.4, the v1 bug #3 this closes)."""
        user, _ = member
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        va = _make_vendor_approval(
            db_session,
            tenant,
            vendor,
            status=ApprovalStatus.APPROVED,
            valid_until=None,
        )
        pa = _make_product_approval(
            db_session,
            tenant,
            product,
            status=ApprovalStatus.APPROVED,
            valid_until=_future(),
        )
        system = _make_system(db_session, tenant, product, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)

        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT

        # Vendor revoked -> held at under_assessment.
        va.status = ApprovalStatus.REJECTED
        db_session.flush()
        re_evaluate(db_session, use_case, user.id)
        assert use_case.state == LifecycleState.HELD
        assert use_case.held_from_state == LifecycleState.UNDER_ASSESSMENT

        # Product then ALSO expires while held.
        pa.valid_until = _past()
        db_session.flush()

        # Vendor re-cleared.
        va.status = ApprovalStatus.APPROVED
        db_session.flush()

        re_evaluate(db_session, use_case, user.id)
        # Rests at product_check (the earliest still-unsatisfied gate) —
        # NOT a forward advance straight back to under_assessment.
        assert use_case.state == LifecycleState.PRODUCT_CHECK
        assert use_case.held_from_state is None
        assert use_case.held_reason is None

    def test_fully_cleared_unhold_advances_through_to_ceiling(
        self,
        db_session: Session,
        tenant,
        member,
    ):
        user, _ = member
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        va = _make_vendor_approval(db_session, tenant, vendor)
        _make_product_approval(db_session, tenant, product)
        system = _make_system(db_session, tenant, product, vendor=vendor)
        use_case = _make_use_case(db_session, tenant, system)

        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT

        va.status = ApprovalStatus.REJECTED
        db_session.flush()
        re_evaluate(db_session, use_case, user.id)
        assert use_case.state == LifecycleState.HELD

        va.status = ApprovalStatus.APPROVED
        db_session.flush()
        re_evaluate(db_session, use_case, user.id)
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT
        assert use_case.held_from_state is None
