"""
Use-case registration and EU AI Act classification endpoints (v1, tenant plane).

All routes are RLS-scoped to the caller's tenant via get_tenant_db.

  POST /v1/use-cases                         register a use case and auto-classify
  GET  /v1/use-cases                         list use cases (any authenticated member)
  GET  /v1/use-cases/{id}                    get a single use case with its current
                                              classification
  POST /v1/use-cases/{id}/classify/override  structured tier override (§1.5)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import (
    TenantContext,
    get_tenant_context,
    get_tenant_db,
    require_governance_role,
)
from app.models.assessment import Classification
from app.models.base import EUAIActTier
from app.models.domain import System, UseCase
from app.models.taxonomy import EUAIActSubcategory
from app.schemas.use_cases import (
    ClassificationRead,
    OverrideRequest,
    UseCaseCreate,
    UseCaseRead,
    UseCaseWithClassification,
)
from app.services.classification import (
    ClassificationProposal,
    resolve_classification,
    snapshot_classification,
)

router = APIRouter(prefix="/use-cases", tags=["use-cases"])


def _current_classification(
    use_case_id: uuid.UUID, db: Session
) -> Classification | None:
    return db.scalar(
        select(Classification)
        .where(
            Classification.use_case_id == use_case_id,
            Classification.is_current.is_(True),
        )
    )


def _classification_read(c: Classification) -> ClassificationRead:
    return ClassificationRead.from_orm_with_flag(c)


@router.post(
    "", response_model=UseCaseWithClassification, status_code=status.HTTP_201_CREATED
)
def register_use_case(
    payload: UseCaseCreate,
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> UseCaseWithClassification:
    """Register a use case under a system and derive its EU AI Act classification.

    The system must belong to the caller's tenant (enforced by RLS — querying
    the system within the tenant session ensures isolation). The classification
    is derived live from the seeded bridge and snapshotted immediately.
    """
    # Verify system exists and belongs to this tenant (RLS enforces the latter).
    system = db.scalar(
        select(System).where(
            System.id == payload.system_id,
            System.tenant_id == ctx.tenant_id,
        )
    )
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="System not found")

    use_case = UseCase(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        system_id=payload.system_id,
        title=payload.title,
        purpose=payload.purpose,
        context_blob=payload.context_blob,
    )
    db.add(use_case)
    db.flush()

    proposal = resolve_classification(payload.system_id, db)
    classification = snapshot_classification(
        use_case,
        proposal,
        db,
        actor_user_id=ctx.user_id,
    )

    return UseCaseWithClassification(
        use_case=UseCaseRead.model_validate(use_case),
        classification=_classification_read(classification),
    )


@router.get("", response_model=list[UseCaseRead])
def list_use_cases(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> list[UseCase]:
    """List use cases in the caller's tenant. RLS scopes this automatically;
    explicit tenant_id filter provides belt-and-suspenders isolation in test
    environments without RLS. Open to any authenticated tenant member — role-scoped
    read access is deferred to the assessment sprint.
    """
    return list(
        db.scalars(
            select(UseCase)
            .where(UseCase.tenant_id == ctx.tenant_id)
            .order_by(UseCase.created_at)
        )
    )


@router.get("/{use_case_id}", response_model=UseCaseWithClassification)
def get_use_case(
    use_case_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> UseCaseWithClassification:
    use_case = db.scalar(
        select(UseCase).where(
            UseCase.id == use_case_id,
            UseCase.tenant_id == ctx.tenant_id,
        )
    )
    if use_case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Use case not found")

    classification = _current_classification(use_case_id, db)
    if classification is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No current classification for this use case",
        )

    return UseCaseWithClassification(
        use_case=UseCaseRead.model_validate(use_case),
        classification=_classification_read(classification),
    )


@router.post(
    "/{use_case_id}/classify/override",
    response_model=UseCaseWithClassification,
)
def override_classification(
    use_case_id: uuid.UUID,
    payload: OverrideRequest,
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> UseCaseWithClassification:
    """Override the proposed tier with a structured choice (§1.5 tracked deviation).

    Inserts a new current Classification snapshot recording the chosen tier,
    the prior proposed tier, and the justification. The prior snapshot is
    preserved with is_current=False.
    """
    use_case = db.get(UseCase, use_case_id)
    if use_case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Use case not found")

    # The subcategory_code must resolve to an existing subcategory — never free-typed.
    subcategory = db.scalar(
        select(EUAIActSubcategory).where(
            EUAIActSubcategory.code == payload.subcategory_code
        )
    )
    if subcategory is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown subcategory code: {payload.subcategory_code!r}",
        )

    # Enforce tier consistency: the requested tier must match the subcategory's tier.
    if EUAIActTier(subcategory.tier) != payload.tier:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Subcategory {payload.subcategory_code!r} has tier "
                f"'{subcategory.tier}', but request specifies '{payload.tier.value}'"
            ),
        )

    prior = _current_classification(use_case_id, db)
    prior_tier = prior.tier if prior else None

    override_proposal = ClassificationProposal(
        tier=payload.tier,
        subcategory_code=subcategory.code,
        subcategory_name=subcategory.name,
        legal_ref=subcategory.legal_ref,
        rationale=f"Override: {subcategory.code} — {subcategory.name}",
    )

    classification = snapshot_classification(
        use_case,
        override_proposal,
        db,
        actor_user_id=ctx.user_id,
        overridden=True,
        proposed_tier=prior_tier,
        justification=payload.justification,
    )

    return UseCaseWithClassification(
        use_case=UseCaseRead.model_validate(use_case),
        classification=_classification_read(classification),
    )
