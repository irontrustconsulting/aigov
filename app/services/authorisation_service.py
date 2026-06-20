"""
AuthorisationService — deployment authorisation / ATO (Sprint 6b,
sprints/SPRINT_AUTHORIZATION.md WI-4, design doc §4.2).

Tenant-plane pattern, same shape as assessment_review_service.py (6a): one
transaction, no mid-request commit (get_tenant_db commits at request end).
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext
from app.models.assessment import Assessment
from app.models.base import AssessmentType, LifecycleState
from app.models.domain import UseCase
from app.models.identity import Membership, User
from app.models.lifecycle import AuditEvent, DeploymentAuthorisation
from app.services.governance import assert_distinct_workflow_actor
from app.services.lifecycle_service import apply_transition, full_vector


def _load_use_case(use_case_id: uuid.UUID, ctx: TenantContext, db: Session) -> UseCase:
    use_case = db.scalar(
        select(UseCase).where(
            UseCase.id == use_case_id,
            UseCase.tenant_id == ctx.tenant_id,
        )
    )
    if use_case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Use case not found")
    return use_case


def _load_current_aiia(use_case: UseCase, db: Session) -> Assessment:
    aiia = db.scalar(
        select(Assessment).where(
            Assessment.use_case_id == use_case.id,
            Assessment.tenant_id == use_case.tenant_id,
            Assessment.type == AssessmentType.AIIA,
            Assessment.parent_aiia_id.is_(None),
        )
    )
    if aiia is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="No assessment started for this use case",
        )
    return aiia


def _resolve_actor_identity(
    db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID,
) -> tuple[str | None, str | None]:
    """Durable attribution (D13) resolved via Membership -> User, never bare
    app_user (inv 2/34) — same join shape as 6a's review-queue."""
    row = db.execute(
        select(User.display_name, User.email)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.tenant_id == tenant_id, User.id == user_id)
    ).first()
    return (row.display_name, row.email) if row is not None else (None, None)


def authorise_use_case(
    use_case_id: uuid.UUID,
    residual_risk_statement: str,
    ctx: TenantContext,
    db: Session,
) -> DeploymentAuthorisation:
    """authoriser act (design doc §4.2): recompute the vector, reject unless
    the use case is currently pending_authorisation with every gate below
    authorisation passing; act-SoD against the AIIA's approver/submitter;
    write a cycle-stamped, identity-stamped ATO; apply_transition into
    authorised (inv 24) in the same transaction."""
    use_case = _load_use_case(use_case_id, ctx, db)
    aiia = _load_current_aiia(use_case, db)

    vector = full_vector(use_case, db)
    gates_below_authorisation = vector[:-1]
    if use_case.state != LifecycleState.PENDING_AUTHORISATION or not all(
        result.verdict == "advance" for _, result in gates_below_authorisation
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Use case is not ready for authorisation; recompute and retry",
        )

    assert_distinct_workflow_actor(
        actor_user_id=ctx.user_id,
        excluded_user_ids={aiia.approved_by_user_id, aiia.submitted_by_user_id},
        action="authorise",
    )

    authorised_by_name, authorised_by_email = _resolve_actor_identity(
        db, ctx.tenant_id, ctx.user_id,
    )
    ato = DeploymentAuthorisation(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        use_case_id=use_case.id,
        assessment_id=aiia.id,
        submission_round=aiia.submission_round,
        tier=use_case.eu_tier.value,
        assessment_version=aiia.version,
        authorised_by_user_id=ctx.user_id,
        authorised_by_name=authorised_by_name,
        authorised_by_email=authorised_by_email,
        residual_risk_statement=residual_risk_statement,
    )
    db.add(ato)
    db.flush()

    db.add(
        AuditEvent(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user_id,
            action="authorisation.granted",
            entity_type="deployment_authorisation",
            entity_id=ato.id,
            detail={
                "use_case_id": str(use_case.id),
                "submission_round": ato.submission_round,
                "tier": ato.tier,
                "assessment_version": ato.assessment_version,
            },
        )
    )

    # Emits lifecycle.authorised automatically (_AUDIT_ACTION_BY_EVENT).
    apply_transition(
        db,
        use_case,
        "authorise",
        LifecycleState.AUTHORISED,
        ctx.user_id,
        "Deployment authorisation granted",
    )

    db.flush()
    return ato
