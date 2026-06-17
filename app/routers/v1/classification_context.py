"""
Classification Gate (gate 2) — context-based EU AI Act classification endpoints.

All routes are RLS-scoped to the caller's tenant via get_tenant_db.

  GET  /v1/use-cases/{id}/classification/context
       Returns the residual question set plus the current classification
       snapshot. Open to all five governance roles.

  POST /v1/use-cases/{id}/classification/context/preview
       Resolves supplied answers without persisting. Returns the outcome.
       Open to all five governance roles.

  POST /v1/use-cases/{id}/classification/context
       Submits answers, resolves, and writes a PENDING_REVIEW snapshot.
       Gated to system_owner and contributor. Override (when chosen tier ≠
       computed tier) is additionally asserted to system_owner.

  POST /v1/use-cases/{id}/classification/sign-off
       Reviewer approves the current pending classification.
       Gated to reviewer.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import (
    TenantContext,
    get_tenant_db,
    require_governance_role,
)
from app.models.domain import UseCase
from app.schemas.classification import (
    ClassificationContextRead,
    ClassificationStatusRead,
    ComputeRequest,
    ComputeResultRead,
    ContextOutcomeRead,
    OptionRead,
    PreviewRequest,
    QuestionRead,
    QuestionSetRead,
    SignOffRead,
)
from app.services.context_classification import (
    AnswerIn,
    compute_and_record_classification,
    get_context_questions,
    get_latest_tree_version,
    resolve_context_classification,
    sign_off_classification,
)

router = APIRouter(prefix="/use-cases", tags=["classification-context"])

_ALL_GOVERNANCE_ROLES = (
    "system_owner", "contributor", "reviewer", "authoriser", "auditor"
)


def _get_use_case(use_case_id: uuid.UUID, ctx: TenantContext, db: Session) -> UseCase:
    use_case = db.scalar(
        select(UseCase).where(
            UseCase.id == use_case_id,
            UseCase.tenant_id == ctx.tenant_id,
        )
    )
    if use_case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Use case not found")
    return use_case


def _answers_from_request(raw: list) -> list[AnswerIn]:
    return [
        AnswerIn(
            question_code=a.question_code,
            option_code=a.option_code,
            provenance=a.provenance,
        )
        for a in raw
    ]


def _outcome_read(outcome) -> ContextOutcomeRead:
    return ContextOutcomeRead(
        kind=outcome.kind,
        tier=outcome.tier,
        subcategory_code=outcome.subcategory_code,
        rationale=outcome.rationale,
        missing=outcome.missing,
    )


def _question_set_read(qs) -> QuestionSetRead:
    return QuestionSetRead(
        tree_version=qs.tree_version,
        questions=[
            QuestionRead(
                code=q.code,
                text=q.text,
                legal_ref=q.legal_ref,
                sort_order=q.sort_order,
                options=[OptionRead(code=o.code, label=o.label) for o in q.options],
            )
            for q in qs.questions
        ],
    )


# ── GET /classification/context ─────────────────────────────────────────────

@router.get(
    "/{use_case_id}/classification/context",
    response_model=ClassificationContextRead,
)
def get_classification_context(
    use_case_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> ClassificationContextRead:
    """Residual question set and current classification snapshot.

    Returns the full tree as residual when no answers have been submitted yet.
    Open to all five governance roles — read-only, no writes.
    """
    _get_use_case(use_case_id, ctx, db)

    from app.models.assessment import Classification
    snapshot = db.scalar(
        select(Classification).where(
            Classification.use_case_id == use_case_id,
            Classification.is_current.is_(True),
        )
    )

    # Determine tree version from existing snapshot, or latest.
    tree_version: str | None = None
    if snapshot and snapshot.answers_blob:
        tree_version = snapshot.answers_blob.get("tree_version")
    if not tree_version:
        tree_version = get_latest_tree_version(db)

    # Residual = all questions (no supplied answers for GET).
    qs = get_context_questions([], db, tree_version)

    return ClassificationContextRead(
        current_classification=(
            ClassificationStatusRead.model_validate(snapshot) if snapshot else None
        ),
        residual_questions=_question_set_read(qs),
    )


# ── POST /classification/context/preview ─────────────────────────────────────

@router.post(
    "/{use_case_id}/classification/context/preview",
    response_model=ContextOutcomeRead,
)
def preview_classification(
    use_case_id: uuid.UUID,
    payload: PreviewRequest,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> ContextOutcomeRead:
    """Resolve supplied answers without persisting. Pure read.

    Open to all five governance roles. No snapshot is created; eu_tier is
    not touched.
    """
    _get_use_case(use_case_id, ctx, db)  # existence + tenant check
    answers = _answers_from_request(payload.answers)
    outcome = resolve_context_classification(answers, payload.tree_version, db)
    return _outcome_read(outcome)


# ── POST /classification/context ─────────────────────────────────────────────

@router.post(
    "/{use_case_id}/classification/context",
    response_model=ComputeResultRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_classification(
    use_case_id: uuid.UUID,
    payload: ComputeRequest,
    ctx: TenantContext = Depends(
        require_governance_role("system_owner", "contributor")
    ),
    db: Session = Depends(get_tenant_db),
) -> ComputeResultRead:
    """Submit answers, resolve, and write a PENDING_REVIEW classification snapshot.

    When payload.override_tier is set and differs from the computed tier, the
    caller must hold system_owner (contributor alone cannot override — 403).

    UNRESOLVED outcomes return 200 with no snapshot (no write happens).
    """
    use_case = _get_use_case(use_case_id, ctx, db)
    answers = _answers_from_request(payload.answers)

    # Override gating: only system_owner may propose a tier different from the
    # computed result. contributor can compute but cannot override.
    if payload.override_tier is not None:
        held_keys = _held_governance_keys(ctx, db)
        if "system_owner" not in held_keys:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=(
                    "Overriding the computed tier requires"
                    " the system_owner governance role."
                ),
            )

    outcome, snapshot = compute_and_record_classification(
        use_case=use_case,
        answers=answers,
        tree_version=payload.tree_version,
        db=db,
        actor_user_id=ctx.user_id,
        override_tier=payload.override_tier,
        justification=payload.justification,
    )

    return ComputeResultRead(
        outcome=_outcome_read(outcome),
        classification=(
            ClassificationStatusRead.model_validate(snapshot) if snapshot else None
        ),
    )


# ── POST /classification/sign-off ─────────────────────────────────────────────

@router.post(
    "/{use_case_id}/classification/sign-off",
    response_model=SignOffRead,
)
def reviewer_sign_off(
    use_case_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role("reviewer")),
    db: Session = Depends(get_tenant_db),
) -> SignOffRead:
    """Reviewer approves the current PENDING_REVIEW classification.

    Stamps use_case.eu_tier with the approved tier (the authoritative
    ratification). Stages classification.signed_off AuditEvent atomically.
    """
    use_case = _get_use_case(use_case_id, ctx, db)
    snapshot = sign_off_classification(
        use_case=use_case,
        db=db,
        reviewer_user_id=ctx.user_id,
    )
    return SignOffRead.model_validate(snapshot)


# ── Internal helper ──────────────────────────────────────────────────────────

def _held_governance_keys(ctx: TenantContext, db: Session) -> set[str]:
    from sqlalchemy import select as sa_select

    from app.models.governance import GovernanceRole, GovernanceRoleAssignment
    return set(db.scalars(
        sa_select(GovernanceRole.key)
        .join(
            GovernanceRoleAssignment,
            GovernanceRole.id == GovernanceRoleAssignment.governance_role_id,
        )
        .where(GovernanceRoleAssignment.membership_id == ctx.membership_id)
    ))
