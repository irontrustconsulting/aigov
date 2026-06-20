"""
AssessmentReviewService — AIIA review & sign-off (Sprint 6a,
sprints/SPRINT_AUTHORIZATION_6A.md WI-4, design doc §4.1).

Tenant-plane pattern, same shape as assessment_service.py: stage business
rows + AuditEvent, single db.flush(), no mid-request commit (get_tenant_db
commits once at request end). Every status write is a single conditional
UPDATE keyed on (id, tenant_id, lock_version, status IN allowed-from-states);
zero rows affected is disambiguated by re-reading the row: a changed
lock_version is a stale If-Match (412), an unchanged lock_version with a
status outside the allowed set is a bad from-state (409) — design doc §4.1,
STATE inv 14.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.context import TenantContext
from app.models.assessment import Assessment, AssessmentReview
from app.models.base import AssessmentStatus, AssessmentType, ReviewDecision
from app.models.domain import UseCase
from app.models.identity import Membership, User
from app.models.lifecycle import AuditEvent
from app.schemas.assessment import ReviewQueueEntryRead
from app.services.assessment_service import load_assessment
from app.services.governance import assert_distinct_workflow_actor
from app.services.lifecycle_gates import structural_assessment_readiness, treatment_gate
from app.services.lifecycle_service import advance_use_case

_SUBMITTABLE_STATUSES = (AssessmentStatus.DRAFT, AssessmentStatus.NEEDS_REFRESH)


def _now() -> datetime:
    return datetime.now(UTC)


def _conditional_status_update(
    db: Session,
    assessment: Assessment,
    ctx: TenantContext,
    *,
    expected_lock_version: int,
    from_statuses: tuple[AssessmentStatus, ...],
    values: dict[str, object],
) -> None:
    """The shared conditional-UPDATE shape every status write in this module
    uses. Mutates `values` to also bump lock_version, applies it to `assessment`
    in-session on success. Raises 412/409 on a zero-row update."""
    values = {**values, "lock_version": Assessment.lock_version + 1}
    result = db.execute(
        update(Assessment)
        .where(
            Assessment.id == assessment.id,
            Assessment.tenant_id == ctx.tenant_id,
            Assessment.lock_version == expected_lock_version,
            Assessment.status.in_(from_statuses),
        )
        .values(**values)
    )
    if result.rowcount == 0:
        db.refresh(assessment)
        if assessment.lock_version != expected_lock_version:
            raise HTTPException(
                status.HTTP_412_PRECONDITION_FAILED,
                detail="Stale If-Match: assessment was modified by another request",
            )
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"Assessment status is {assessment.status.value}; "
                f"expected one of {[s.value for s in from_statuses]}"
            ),
        )
    db.refresh(assessment)


def submit_for_review(
    assessment_id: uuid.UUID,
    expected_lock_version: int,
    ctx: TenantContext,
    db: Session,
) -> Assessment:
    """system_owner act (design doc §4.1 / §5). Pre-check: structurally
    complete AND every dispositioned risk has a treatment decision (D5) —
    submit happens only once the AIIA is both structurally ready and
    treated, so the reviewer never reviews an untreated assessment."""
    assessment = load_assessment(assessment_id, ctx, db)
    use_case = db.get(UseCase, assessment.use_case_id)

    structural = structural_assessment_readiness(use_case, db)
    if structural.verdict != "advance":
        raise HTTPException(status.HTTP_409_CONFLICT, detail=structural.reason)
    treatment = treatment_gate(use_case, db)
    if treatment.verdict != "advance":
        raise HTTPException(status.HTTP_409_CONFLICT, detail=treatment.reason)

    new_round = assessment.submission_round + 1
    _conditional_status_update(
        db,
        assessment,
        ctx,
        expected_lock_version=expected_lock_version,
        from_statuses=_SUBMITTABLE_STATUSES,
        values={
            "status": AssessmentStatus.IN_REVIEW,
            "submission_round": new_round,
            "submitted_by_user_id": ctx.user_id,
            "submitted_at": _now(),
        },
    )

    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user_id,
            action="assessment.submitted",
            entity_type="assessment",
            entity_id=assessment.id,
            detail={"submission_round": new_round},
        )
    )
    db.flush()
    return assessment


def record_review(
    assessment_id: uuid.UUID,
    decision: ReviewDecision,
    note: str | None,
    expected_lock_version: int,
    ctx: TenantContext,
    db: Session,
) -> Assessment:
    """reviewer act (design doc §4.1 / D4 / D6). APPROVED advances the use
    case in the same transaction (single-hop through treatment_pending,
    design §6.2 NB1); CHANGES_REQUESTED bounces to DRAFT, no advance call."""
    assessment = load_assessment(assessment_id, ctx, db)

    assert_distinct_workflow_actor(
        actor_user_id=ctx.user_id,
        excluded_user_ids={assessment.submitted_by_user_id},
        action="review",
    )
    if assessment.status != AssessmentStatus.IN_REVIEW:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"Assessment status is {assessment.status.value}; "
                f"expected in_review"
            ),
        )
    if decision == ReviewDecision.CHANGES_REQUESTED and not (note or "").strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="note is required when requesting changes",
        )

    submission_round = assessment.submission_round
    if decision == ReviewDecision.APPROVED:
        _conditional_status_update(
            db,
            assessment,
            ctx,
            expected_lock_version=expected_lock_version,
            from_statuses=(AssessmentStatus.IN_REVIEW,),
            values={
                "status": AssessmentStatus.APPROVED,
                "approved_by_user_id": ctx.user_id,
                "approved_at": _now(),
            },
        )
    else:
        _conditional_status_update(
            db,
            assessment,
            ctx,
            expected_lock_version=expected_lock_version,
            from_statuses=(AssessmentStatus.IN_REVIEW,),
            values={"status": AssessmentStatus.DRAFT},
        )

    db.add(
        AssessmentReview(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            assessment_id=assessment.id,
            reviewer_user_id=ctx.user_id,
            decision=decision,
            note=note,
            submission_round=submission_round,
        )
    )
    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user_id,
            action="assessment.review_recorded",
            entity_type="assessment",
            entity_id=assessment.id,
            detail={"decision": decision.value, "submission_round": submission_round},
        )
    )
    db.flush()

    if decision == ReviewDecision.APPROVED:
        use_case = db.get(UseCase, assessment.use_case_id)
        advance_use_case(db, use_case, ctx.user_id)

    return assessment


def list_review_queue(ctx: TenantContext, db: Session) -> list[ReviewQueueEntryRead]:
    """status = IN_REVIEW AND submitted_by != caller (design doc §5), AIIAs
    only (parent_aiia_id IS NULL — feeders are never independently
    submitted). Submitter identity resolved by joining Membership -> User,
    scoped to ctx.tenant_id — app_user is never queried bare (STATE inv 2,
    extended by inv 34)."""
    rows = list(
        db.execute(
            select(
                Assessment.id,
                Assessment.use_case_id,
                Assessment.tier_snapshot,
                Assessment.submitted_at,
                User.display_name,
                User.email,
            )
            .join(Membership, Membership.user_id == Assessment.submitted_by_user_id)
            .join(User, User.id == Membership.user_id)
            .where(
                Assessment.tenant_id == ctx.tenant_id,
                Assessment.status == AssessmentStatus.IN_REVIEW,
                Assessment.type == AssessmentType.AIIA,
                Assessment.parent_aiia_id.is_(None),
                Assessment.submitted_by_user_id != ctx.user_id,
                Membership.tenant_id == ctx.tenant_id,
            )
            .order_by(Assessment.submitted_at)
        ).all()
    )
    return [
        ReviewQueueEntryRead(
            assessment_id=row.id,
            use_case_id=row.use_case_id,
            tier_snapshot=row.tier_snapshot,
            submitted_by_name=row.display_name,
            submitted_by_email=row.email,
            submitted_at=row.submitted_at,
        )
        for row in rows
    ]


def reopen(
    assessment_id: uuid.UUID,
    expected_lock_version: int,
    ctx: TenantContext,
    db: Session,
) -> Assessment:
    """system_owner act (design doc §4.1 / D7). APPROVED -> NEEDS_REFRESH.
    No advance/regression call here — the use case's loss of
    assessment_approved() is caught lazily by the next re_evaluate or
    consequential write (design §6.3); no scheduler exists to force it."""
    assessment = load_assessment(assessment_id, ctx, db)

    _conditional_status_update(
        db,
        assessment,
        ctx,
        expected_lock_version=expected_lock_version,
        from_statuses=(AssessmentStatus.APPROVED,),
        values={"status": AssessmentStatus.NEEDS_REFRESH},
    )

    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user_id,
            action="assessment.reopened",
            entity_type="assessment",
            entity_id=assessment.id,
            detail={},
        )
    )
    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user_id,
            action="assessment.needs_refresh",
            entity_type="assessment",
            entity_id=assessment.id,
            detail={},
        )
    )
    db.flush()
    return assessment
