"""
Tests for apply_transition — the sole mutator of UseCase.state
(sprints/SPRINT_LIFECYCLE.md WI-2, §8 "apply_transition / state machine").
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app.models.base import LifecycleState
from app.models.domain import System, UseCase
from app.models.lifecycle import AuditEvent, LifecycleTransition
from app.services.lifecycle_service import apply_transition
from tests.lifecycle_helpers import (  # noqa: F401
    _make_system,
    _make_use_case,
    member,
    tenant,
)


@pytest.fixture
def system(db_session: Session, tenant) -> System:
    return _make_system(db_session, tenant)


@pytest.fixture
def use_case(db_session: Session, tenant, system: System) -> UseCase:
    return _make_use_case(db_session, tenant, system)


class TestLegalTransitions:
    def test_advance_persists_state_transition_and_audit_atomically(
        self,
        db_session: Session,
        tenant,
        use_case: UseCase,
        member,
    ):
        user, _ = member
        result = apply_transition(
            db_session,
            use_case,
            "created",
            LifecycleState.VENDOR_CHECK,
            actor_user_id=user.id,
            reason="use case created",
        )

        assert result.state == LifecycleState.VENDOR_CHECK
        assert use_case.state == LifecycleState.VENDOR_CHECK

        transition = db_session.scalar(
            select(LifecycleTransition).where(
                LifecycleTransition.use_case_id == use_case.id
            )
        )
        assert transition is not None
        assert transition.from_state == LifecycleState.REQUESTED
        assert transition.to_state == LifecycleState.VENDOR_CHECK
        assert transition.actor_user_id == user.id
        assert transition.reason == "use case created"

        audit = db_session.scalar(
            select(AuditEvent).where(
                AuditEvent.entity_id == use_case.id,
                AuditEvent.entity_type == "use_case",
            )
        )
        assert audit is not None
        assert audit.action == "lifecycle.advanced"
        assert audit.detail == {
            "from_state": "REQUESTED",
            "to_state": "VENDOR_CHECK",
            "event": "created",
        }

    def test_halt_fires_from_any_non_terminal_state(
        self,
        db_session: Session,
        use_case: UseCase,
        member,
    ):
        user, _ = member
        apply_transition(
            db_session,
            use_case,
            "halt",
            LifecycleState.HALTED_PROHIBITED,
            actor_user_id=user.id,
            reason="prohibited practice",
        )
        assert use_case.state == LifecycleState.HALTED_PROHIBITED

        audit = db_session.scalar(
            select(AuditEvent).where(AuditEvent.entity_id == use_case.id)
        )
        assert audit.action == "lifecycle.halted_prohibited"

    def test_hold_sets_hint_and_restore_clears_it(
        self,
        db_session: Session,
        use_case: UseCase,
        member,
    ):
        user, _ = member
        apply_transition(
            db_session,
            use_case,
            "created",
            LifecycleState.VENDOR_CHECK,
            actor_user_id=user.id,
            reason="advance",
        )

        apply_transition(
            db_session,
            use_case,
            "hold",
            LifecycleState.HELD,
            actor_user_id=user.id,
            reason="vendor approval expired",
            held_reason="vendor approval expired",
        )
        assert use_case.state == LifecycleState.HELD
        assert use_case.held_from_state == LifecycleState.VENDOR_CHECK
        assert use_case.held_reason == "vendor approval expired"

        apply_transition(
            db_session,
            use_case,
            "restore",
            LifecycleState.PRODUCT_CHECK,
            actor_user_id=user.id,
            reason="vendor re-cleared, product not yet",
        )
        assert use_case.state == LifecycleState.PRODUCT_CHECK
        assert use_case.held_from_state is None
        assert use_case.held_reason is None

        audit_actions = db_session.scalars(
            select(AuditEvent.action)
            .where(AuditEvent.entity_id == use_case.id)
            .order_by(AuditEvent.occurred_at)
        ).all()
        assert audit_actions == [
            "lifecycle.advanced",
            "lifecycle.held",
            "lifecycle.advanced",
        ]


class TestConcurrencyGuard:
    def test_stale_from_state_raises_409(
        self,
        db_session: Session,
        use_case: UseCase,
        member,
    ):
        user, _ = member
        # Simulate a concurrent writer moving the DB row without going
        # through apply_transition. synchronize_session=False is required:
        # the ORM-enabled UPDATE otherwise also patches use_case.state in
        # the session's identity map, defeating the staleness this test
        # means to simulate (a real concurrent writer on another connection
        # would never touch this session's in-memory object at all).
        db_session.execute(
            update(UseCase)
            .where(UseCase.id == use_case.id)
            .values(state=LifecycleState.VENDOR_CHECK)
            .execution_options(synchronize_session=False)
        )
        db_session.flush()

        with pytest.raises(HTTPException) as exc_info:
            apply_transition(
                db_session,
                use_case,
                "created",
                LifecycleState.VENDOR_CHECK,
                actor_user_id=user.id,
                reason="stale",
            )
        assert exc_info.value.status_code == 409


class TestIllegalTransitions:
    def test_skipping_a_gate_is_rejected(
        self,
        db_session: Session,
        use_case: UseCase,
        member,
    ):
        user, _ = member
        with pytest.raises(ValueError):
            apply_transition(
                db_session,
                use_case,
                "advance",
                LifecycleState.INTAKE,
                actor_user_id=user.id,
                reason="skip ahead",
            )

    def test_hold_from_requested_is_rejected(
        self,
        db_session: Session,
        use_case: UseCase,
        member,
    ):
        # REQUESTED has not passed any gate yet — nothing to regress from.
        user, _ = member
        with pytest.raises(ValueError):
            apply_transition(
                db_session,
                use_case,
                "hold",
                LifecycleState.HELD,
                actor_user_id=user.id,
                reason="bogus",
                held_reason="bogus",
            )

    def test_restore_to_a_non_canonical_state_is_rejected(
        self,
        db_session: Session,
        use_case: UseCase,
        member,
    ):
        user, _ = member
        apply_transition(
            db_session,
            use_case,
            "created",
            LifecycleState.VENDOR_CHECK,
            actor_user_id=user.id,
            reason="advance",
        )
        apply_transition(
            db_session,
            use_case,
            "hold",
            LifecycleState.HELD,
            actor_user_id=user.id,
            reason="held",
            held_reason="held",
        )
        with pytest.raises(ValueError):
            apply_transition(
                db_session,
                use_case,
                "restore",
                LifecycleState.HALTED_PROHIBITED,
                actor_user_id=user.id,
                reason="not a forward state",
            )


class TestEnumBinding:
    def test_state_round_trips_by_member_name_not_value(
        self,
        db_session: Session,
        use_case: UseCase,
        member,
    ):
        """STATE.md inv 23: the lifecycle_state Postgres enum stores member
        NAMES ('VENDOR_CHECK'), not LifecycleState's lowercase .value
        ('vendor_check'). A raw .value bind would silently match zero rows."""
        user, _ = member
        apply_transition(
            db_session,
            use_case,
            "created",
            LifecycleState.VENDOR_CHECK,
            actor_user_id=user.id,
            reason="advance",
        )
        db_session.flush()

        raw_state = db_session.execute(
            text("SELECT state::text FROM use_case WHERE id = :id"),
            {"id": str(use_case.id)},
        ).scalar_one()
        assert raw_state == "VENDOR_CHECK"
        assert raw_state != LifecycleState.VENDOR_CHECK.value

        raw_to_state = db_session.execute(
            text(
                "SELECT to_state::text FROM lifecycle_transition "
                "WHERE use_case_id = :id"
            ),
            {"id": str(use_case.id)},
        ).scalar_one()
        assert raw_to_state == "VENDOR_CHECK"
