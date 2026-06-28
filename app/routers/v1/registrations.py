"""
POST /v1/registrations — atomic system + use-case + classification (DM-S2, D-65).

One handler, one transaction; caller (get_tenant_db) commits at request end.
No mid-request commit; INV-27 is preserved.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.auth.context import TenantContext, get_tenant_db, require_governance_role
from app.models.domain import DraftRegistration, System, UseCase
from app.models.intake import (
    AffectedParty,
    DataCategory,
    HumanOversightType,
    UsageContext,
    UseCaseAffectedParty,
    UseCaseDataCategory,
)
from app.schemas.registration import RegistrationCreate, RegistrationRead
from app.schemas.system import (
    AffectedPartyOut,
    DataCategoryOut,
    SystemCreate,
    VocabItemOut,
)
from app.schemas.use_cases import ClassificationRead, UseCaseRead
from app.services import system_service
from app.services.classification import resolve_classification, snapshot_classification

router = APIRouter(prefix="/registrations", tags=["registrations"])


# ---------------------------------------------------------------------------
# Internal helpers (mirrors of use_cases.py private helpers)
# ---------------------------------------------------------------------------

def _replace_data_categories(
    db: Session,
    use_case_id: uuid.UUID,
    tenant_id: uuid.UUID,
    ids: list[uuid.UUID],
) -> None:
    db.execute(delete(UseCaseDataCategory).where(UseCaseDataCategory.use_case_id == use_case_id))
    for dc_id in ids:
        db.add(UseCaseDataCategory(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            use_case_id=use_case_id,
            data_category_id=dc_id,
        ))


def _replace_affected_parties(
    db: Session,
    use_case_id: uuid.UUID,
    tenant_id: uuid.UUID,
    ids: list[uuid.UUID],
) -> None:
    db.execute(delete(UseCaseAffectedParty).where(UseCaseAffectedParty.use_case_id == use_case_id))
    for ap_id in ids:
        db.add(UseCaseAffectedParty(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            use_case_id=use_case_id,
            affected_party_id=ap_id,
        ))


def _build_use_case_read(use_case: UseCase, db: Session) -> UseCaseRead:
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
        purpose=use_case.purpose,
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


def _classification_read(c) -> ClassificationRead:
    return ClassificationRead.from_orm_with_flag(c)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("", response_model=RegistrationRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegistrationCreate,
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> RegistrationRead:
    """Atomic system + first use case + classification in one transaction (D-65).

    A forced failure after any flush leaves no orphan rows — get_tenant_db
    rolls back on exception before committing. INV-78: the only route that
    constructs a System.
    """
    # Step 1 — create system (flushes internally; no commit)
    system_payload = SystemCreate(
        name=payload.name,
        is_custom=payload.is_custom,
        catalogue_product_id=payload.catalogue_product_id,
        catalogue_vendor_id=None,  # server derives from product
        owner_user_id=payload.owner_user_id,
        operator_role_id=payload.operator_role_id,
        hosting_model_id=payload.hosting_model_id,
        lifecycle_stage=payload.lifecycle_stage,
        purpose=payload.purpose,
    )
    system: System = system_service.create_system(system_payload, ctx, db)

    # Step 2 — create use case + link rows (INV-77: tenant_id stamped on links)
    use_case = UseCase(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        system_id=system.id,
        title=payload.title,
        purpose=payload.use_case_purpose,
        context_blob=payload.context_blob,
        usage_context_id=payload.usage_context_id,
        human_oversight_type_id=payload.human_oversight_type_id,
    )
    db.add(use_case)
    db.flush()

    _replace_data_categories(db, use_case.id, ctx.tenant_id, payload.data_category_ids)
    _replace_affected_parties(db, use_case.id, ctx.tenant_id, payload.affected_party_ids)
    db.flush()

    # Step 3 — classify (resolve + snapshot; advance_use_case fires inside snapshot)
    proposal = resolve_classification(system.id, db)
    classification = snapshot_classification(use_case, proposal, db, actor_user_id=ctx.user_id)

    # Step 4 — atomically discard the draft if one was supplied (D-66/SV-3).
    # Same transaction: a forced rollback leaves the draft intact.
    if payload.draft_id:
        draft = db.scalar(
            select(DraftRegistration).where(
                DraftRegistration.id == payload.draft_id,
                DraftRegistration.owner_user_id == ctx.user_id,
            )
        )
        if draft:
            db.delete(draft)
            db.flush()

    # Step 5 — assemble response; get_tenant_db commits at request end
    return RegistrationRead(
        system=system_service.get_system_detail(system.id, db),
        use_case=_build_use_case_read(use_case, db),
        classification=_classification_read(classification),
    )
