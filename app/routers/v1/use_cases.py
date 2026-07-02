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
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.auth.context import (
    TenantContext,
    get_tenant_context,
    get_tenant_db,
    require_governance_role,
)
from app.models.assessment import Classification
from app.models.base import EUAIActTier
from app.models.domain import System, UseCase
from app.models.intake import (
    AffectedParty, DataCategory, HumanOversightType, UsageContext,
    UseCaseAffectedParty, UseCaseDataCategory,
)
from app.models.taxonomy import EUAIActSubcategory
from app.schemas.system import AffectedPartyOut, DataCategoryOut, VocabItemOut
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


def _replace_use_case_data_categories(
    db: Session,
    use_case_id: uuid.UUID,
    tenant_id: uuid.UUID,
    data_category_ids: list[uuid.UUID],
) -> None:
    db.execute(delete(UseCaseDataCategory).where(UseCaseDataCategory.use_case_id == use_case_id))
    for dc_id in data_category_ids:
        db.add(UseCaseDataCategory(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            use_case_id=use_case_id,
            data_category_id=dc_id,
        ))


def _replace_use_case_affected_parties(
    db: Session,
    use_case_id: uuid.UUID,
    tenant_id: uuid.UUID,
    affected_party_ids: list[uuid.UUID],
) -> None:
    db.execute(delete(UseCaseAffectedParty).where(UseCaseAffectedParty.use_case_id == use_case_id))
    for ap_id in affected_party_ids:
        db.add(UseCaseAffectedParty(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            use_case_id=use_case_id,
            affected_party_id=ap_id,
        ))


def _build_use_case_read(use_case: UseCase, db: Session) -> UseCaseRead:
    """Build UseCaseRead with resolved vocab labels for the four context fields."""
    uc_vocab = db.get(UsageContext, use_case.usage_context_id) if use_case.usage_context_id else None
    hot_vocab = db.get(HumanOversightType, use_case.human_oversight_type_id) if use_case.human_oversight_type_id else None

    dc_links = list(db.scalars(
        select(UseCaseDataCategory)
        .where(UseCaseDataCategory.use_case_id == use_case.id)
        .options(selectinload(UseCaseDataCategory.data_category))
    ))
    ap_links = list(db.scalars(
        select(UseCaseAffectedParty)
        .where(UseCaseAffectedParty.use_case_id == use_case.id)
        .options(selectinload(UseCaseAffectedParty.affected_party))
    ))

    return UseCaseRead(
        id=use_case.id,
        tenant_id=use_case.tenant_id,
        system_id=use_case.system_id,
        title=use_case.title,
        state=use_case.state,
        eu_tier=use_case.eu_tier,
        usage_context=VocabItemOut(id=uc_vocab.id, code=uc_vocab.code, label=uc_vocab.label) if uc_vocab else None,
        human_oversight_type=VocabItemOut(id=hot_vocab.id, code=hot_vocab.code, label=hot_vocab.label) if hot_vocab else None,
        data_categories=[
            DataCategoryOut(
                id=link.data_category.id,
                code=link.data_category.code,
                label=link.data_category.label,
                is_special_category=link.data_category.is_special_category,
            )
            for link in dc_links
        ],
        affected_parties=[
            AffectedPartyOut(
                id=link.affected_party.id,
                code=link.affected_party.code,
                label=link.affected_party.label,
                is_vulnerable_group=link.affected_party.is_vulnerable_group,
            )
            for link in ap_links
        ],
    )


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
        context_blob=payload.context_blob,
        usage_context_id=payload.usage_context_id,
        human_oversight_type_id=payload.human_oversight_type_id,
    )
    db.add(use_case)
    db.flush()

    _replace_use_case_data_categories(db, use_case.id, ctx.tenant_id, payload.data_category_ids)
    _replace_use_case_affected_parties(db, use_case.id, ctx.tenant_id, payload.affected_party_ids)
    db.flush()

    proposal = resolve_classification(payload.system_id, use_case.id, db)
    classification = snapshot_classification(
        use_case,
        proposal,
        db,
        actor_user_id=ctx.user_id,
    )

    return UseCaseWithClassification(
        use_case=_build_use_case_read(use_case, db),
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
        use_case=_build_use_case_read(use_case, db),
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
