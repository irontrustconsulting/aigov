"""
Tests for advance_use_case + trigger wiring (sprints/SPRINT_LIFECYCLE.md
WI-5, §8 "auto-advance" and "prohibited (#1)").
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import EUAIActTier, LifecycleState
from app.models.domain import UseCase
from app.models.lifecycle import AuditEvent, LifecycleTransition
from app.services.classification import ClassificationProposal, snapshot_classification
from app.services.context_classification import (
    AnswerIn,
    compute_and_record_classification,
    sign_off_classification,
)
from app.services.lifecycle_service import advance_use_case
from tests.lifecycle_helpers import (  # noqa: F401
    _make_product,
    _make_product_approval,
    _make_system,
    _make_use_case,
    _make_vendor,
    _make_vendor_approval,
    member,
    tenant,
)
from tests.test_classification_gate import minimal_tree  # noqa: F401


def _bridge_proposal(tier: EUAIActTier) -> ClassificationProposal:
    return ClassificationProposal(
        tier=tier,
        subcategory_code="TEST-CODE",
        subcategory_name="Test",
        legal_ref=None,
        rationale="test rationale",
    )


def _cleared_vendor_product_system(db: Session, tenant):
    vendor = _make_vendor(db)
    product = _make_product(db, vendor)
    _make_vendor_approval(db, tenant, vendor)
    _make_product_approval(db, tenant, product)
    return _make_system(db, tenant, product, vendor=vendor)


class TestAutoAdvance:
    def test_cleared_vendor_and_product_advances_to_under_assessment(
        self,
        db_session: Session,
        tenant,
        member,
    ):
        user, _ = member
        system = _cleared_vendor_product_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)

        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )

        assert use_case.state == LifecycleState.UNDER_ASSESSMENT

        transitions = list(
            db_session.scalars(
                select(LifecycleTransition)
                .where(LifecycleTransition.use_case_id == use_case.id)
                .order_by(LifecycleTransition.occurred_at)
            )
        )
        hops = [(t.from_state, t.to_state) for t in transitions]
        assert hops == [
            (LifecycleState.REQUESTED, LifecycleState.VENDOR_CHECK),
            (LifecycleState.VENDOR_CHECK, LifecycleState.PRODUCT_CHECK),
            (LifecycleState.PRODUCT_CHECK, LifecycleState.INTAKE),
            (LifecycleState.INTAKE, LifecycleState.UNDER_ASSESSMENT),
        ]

        audits = list(
            db_session.scalars(
                select(AuditEvent).where(
                    AuditEvent.entity_id == use_case.id,
                    AuditEvent.entity_type == "use_case",
                )
            )
        )
        assert len(audits) == 4
        assert all(a.action == "lifecycle.advanced" for a in audits)

    def test_no_catalogue_link_advances_for_free(
        self,
        db_session: Session,
        tenant,
        member,
    ):
        user, _ = member
        system = _make_system(db_session, tenant)  # no vendor/product link
        use_case = _make_use_case(db_session, tenant, system)

        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT

    def test_second_use_case_of_cleared_product_inherits_clearance(
        self,
        db_session: Session,
        tenant,
        member,
    ):
        user, _ = member
        vendor = _make_vendor(db_session)
        product = _make_product(db_session, vendor)
        _make_vendor_approval(db_session, tenant, vendor)
        _make_product_approval(db_session, tenant, product)

        system_a = _make_system(db_session, tenant, product, vendor=vendor)
        uc_a = _make_use_case(db_session, tenant, system_a)
        snapshot_classification(
            uc_a,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        assert uc_a.state == LifecycleState.UNDER_ASSESSMENT

        # A second system against the SAME vendor/product, no new approval row.
        system_b = _make_system(db_session, tenant, product, vendor=vendor)
        uc_b = _make_use_case(db_session, tenant, system_b)
        snapshot_classification(
            uc_b,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        assert uc_b.state == LifecycleState.UNDER_ASSESSMENT

    def test_sign_off_atomicity_eu_tier_and_advance_visible_only_post_commit(
        self,
        db_session: Session,
        _test_session_factory,
        tenant,
        member,
        minimal_tree,
    ):
        user, _ = member
        system = _cleared_vendor_product_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)

        compute_and_record_classification(
            use_case=use_case,
            answers=[
                AnswerIn("Q_PROHIBITED", "NO"),
                AnswerIn("Q_HIGH", "YES"),
                AnswerIn("Q_LIMITED", "NO"),
            ],
            tree_version=minimal_tree.version,
            db=db_session,
            actor_user_id=user.id,
        )
        # Parked at INTAKE: vendor/product cleared, eu_tier not yet ratified.
        assert use_case.state == LifecycleState.INTAKE
        assert use_case.eu_tier == EUAIActTier.UNCLASSIFIED

        sign_off_classification(use_case, db_session, reviewer_user_id=user.id)
        assert use_case.eu_tier == EUAIActTier.HIGH
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT

        # Nothing committed yet (not even the use case's own creation) — a
        # second connection sees no row at all, proving every write in this
        # test, eu_tier and state included, rides in one uncommitted txn.
        outside = _test_session_factory()
        try:
            row = outside.execute(
                select(UseCase.eu_tier, UseCase.state).where(UseCase.id == use_case.id)
            ).one_or_none()
            assert row is None
        finally:
            outside.close()

        db_session.commit()

        outside2 = _test_session_factory()
        try:
            row = outside2.execute(
                select(UseCase.eu_tier, UseCase.state).where(UseCase.id == use_case.id)
            ).one()
            assert row.eu_tier == EUAIActTier.HIGH
            assert row.state == LifecycleState.UNDER_ASSESSMENT
        finally:
            outside2.close()


class TestProhibited:
    def test_bridge_prohibited_at_creation_halts_without_entering_diligence(
        self,
        db_session: Session,
        tenant,
        member,
    ):
        user, _ = member
        system = _cleared_vendor_product_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)

        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.PROHIBITED),
            db_session,
            actor_user_id=user.id,
        )

        assert use_case.state == LifecycleState.HALTED_PROHIBITED
        transitions = list(
            db_session.scalars(
                select(LifecycleTransition).where(
                    LifecycleTransition.use_case_id == use_case.id
                )
            )
        )
        assert len(transitions) == 1
        assert transitions[0].from_state == LifecycleState.REQUESTED
        assert transitions[0].to_state == LifecycleState.HALTED_PROHIBITED

    def test_context_prohibited_halts_without_stamping_eu_tier(
        self,
        db_session: Session,
        tenant,
        member,
        minimal_tree,
    ):
        user, _ = member
        system = _make_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)

        outcome, snapshot = compute_and_record_classification(
            use_case=use_case,
            answers=[AnswerIn("Q_PROHIBITED", "YES")],
            tree_version=minimal_tree.version,
            db=db_session,
            actor_user_id=user.id,
        )

        assert outcome.kind == "PROHIBITED_HALT"
        assert use_case.eu_tier == EUAIActTier.UNCLASSIFIED  # never stamped
        assert use_case.state == LifecycleState.HALTED_PROHIBITED

    def test_reclassify_to_prohibited_mid_lifecycle_forces_halt(
        self,
        db_session: Session,
        tenant,
        member,
    ):
        user, _ = member
        system = _cleared_vendor_product_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.HIGH),
            db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.UNDER_ASSESSMENT

        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.PROHIBITED),
            db_session,
            actor_user_id=user.id,
            overridden=True,
            proposed_tier=EUAIActTier.HIGH,
            justification="re-classified",
        )
        assert use_case.state == LifecycleState.HALTED_PROHIBITED

        # occurred_at is transaction-stable in Postgres (now() returns one
        # value for the whole open transaction) — every transition in this
        # test shares a timestamp, so identify the halt row by to_state
        # rather than sorting by occurred_at.
        halt_transition = db_session.scalar(
            select(LifecycleTransition).where(
                LifecycleTransition.use_case_id == use_case.id,
                LifecycleTransition.to_state == LifecycleState.HALTED_PROHIBITED,
            )
        )
        assert halt_transition.from_state == LifecycleState.UNDER_ASSESSMENT

    def test_halted_prohibited_is_terminal(
        self,
        db_session: Session,
        tenant,
        member,
    ):
        user, _ = member
        system = _cleared_vendor_product_system(db_session, tenant)
        use_case = _make_use_case(db_session, tenant, system)
        snapshot_classification(
            use_case,
            _bridge_proposal(EUAIActTier.PROHIBITED),
            db_session,
            actor_user_id=user.id,
        )
        assert use_case.state == LifecycleState.HALTED_PROHIBITED

        transition_count_before = db_session.scalar(
            select(LifecycleTransition.id).where(
                LifecycleTransition.use_case_id == use_case.id
            )
        )
        advance_use_case(db_session, use_case, user.id)
        assert use_case.state == LifecycleState.HALTED_PROHIBITED

        transitions_after = list(
            db_session.scalars(
                select(LifecycleTransition.id).where(
                    LifecycleTransition.use_case_id == use_case.id
                )
            )
        )
        assert len(transitions_after) == 1
        assert transitions_after[0] == transition_count_before
