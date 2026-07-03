"""
POST /v1/registrations — atomic system + use-case + classification (DM-S2, D-65).

One handler, one transaction; caller (get_tenant_db) commits at request end.
No mid-request commit; INV-27 is preserved.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.auth.context import TenantContext, get_tenant_db, require_governance_role
from app.models.base import ClassificationDisposition, ClassificationStatus, ProvenanceConfidence
from app.models.domain import CatalogueProduct, DraftRegistration, PrefillDisposition, System, UseCase
from app.models.intake import (
    HumanOversightType,
    UsageContext,
    UseCaseAffectedParty,
    UseCaseDataCategory,
)
from app.models.lifecycle import AuditEvent
from app.schemas.registration import RegistrationCreate, RegistrationRead
from app.schemas.system import (
    AffectedPartyOut,
    DataCategoryOut,
    FieldPrefills,
    SystemCreate,
    VocabItemOut,
)
from app.schemas.use_cases import ClassificationRead, UseCaseRead
from app.services import system_service
from app.services.classification import resolve_classification, snapshot_classification
from app.services.prefill_service import get_prefill_by_product

router = APIRouter(prefix="/registrations", tags=["registrations"])


# ---------------------------------------------------------------------------
# Internal helpers
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


def _dispose_intake_prefill(
    db: Session,
    system: System,
    payload: RegistrationCreate,
    field_prefills: FieldPrefills,
    product_name: str | None,
    ctx: TenantContext,
) -> None:
    """Derive and write prefill_disposition rows + audit events for intake fields.

    Derived fields (operator_role_id, lifecycle_stage) require an explicit
    confirm signal — 422 if submitted unchanged without one (INV-83, D-74).
    Catalogue-seeded fields take submit-as-confirmation.
    Must be called inside the active transaction; caller does not commit.
    """
    # Build seed map: {field_key: (seed_value_str, basis)}
    seeds: dict[str, tuple[str, str]] = {}
    if field_prefills.operator_role_id:
        seeds["operator_role_id"] = (field_prefills.operator_role_id.value, field_prefills.operator_role_id.basis)
    if field_prefills.lifecycle_stage:
        seeds["lifecycle_stage"] = (field_prefills.lifecycle_stage.value, field_prefills.lifecycle_stage.basis)
    if field_prefills.hosting_model_id:
        seeds["hosting_model_id"] = (field_prefills.hosting_model_id.value, field_prefills.hosting_model_id.basis)
    if field_prefills.purpose:
        seeds["purpose"] = (field_prefills.purpose.value, field_prefills.purpose.basis)
    if product_name is not None:
        seeds["name"] = (product_name, "catalogue")

    def _submitted(field_key: str) -> str | None:
        match field_key:
            case "operator_role_id":
                return str(payload.operator_role_id) if payload.operator_role_id else None
            case "lifecycle_stage":
                return payload.lifecycle_stage.value if payload.lifecycle_stage else None
            case "hosting_model_id":
                return str(payload.hosting_model_id) if payload.hosting_model_id else None
            case "purpose":
                return payload.purpose
            case "name":
                return payload.name
            case _:
                return None

    undispositioned = [
        fk for fk, (seed_val, basis) in seeds.items()
        if basis == "derived"
        and _submitted(fk) is not None
        and _submitted(fk) == seed_val
        and fk not in payload.confirmed_fields
    ]
    if undispositioned:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"undispositioned_fields": undispositioned},
        )

    for field_key, (seed_val, basis) in seeds.items():
        sv = _submitted(field_key)
        if sv is None:
            continue
        if basis == "derived":
            prov = (
                ProvenanceConfidence.USER_CONFIRMED
                if field_key in payload.confirmed_fields
                else ProvenanceConfidence.USER_AMENDED
            )
        else:
            prov = (
                ProvenanceConfidence.USER_CONFIRMED if sv == seed_val
                else ProvenanceConfidence.USER_AMENDED
            )
        db.add(PrefillDisposition(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            system_id=system.id,
            field_key=field_key,
            provenance=prov,
            actor_user_id=ctx.user_id,
        ))
        action = (
            "system.field_confirmed"
            if prov == ProvenanceConfidence.USER_CONFIRMED
            else "system.field_amended"
        )
        db.add(AuditEvent(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user_id,
            action=action,
            entity_type="system",
            entity_id=system.id,
            detail={"field": field_key, "value": sv},
        ))


def _dispose_fact_prefill(
    db: Session,
    system: System,
    confirmed_fields: list[str],
    ctx: TenantContext,
) -> None:
    """Write prefill_disposition rows for catalogue facts (WI-6).

    'fact:<key>'         → USER_CONFIRMED (accepted as-is)
    'fact_amended:<key>' → USER_AMENDED   (overridden by user)
    Both prefixes store the full entry string as field_key so intake and fact
    namespaces never collide (N4).
    """
    for entry in confirmed_fields:
        if entry.startswith("fact_amended:"):
            prov = ProvenanceConfidence.USER_AMENDED
            action = "system.field_amended"
        elif entry.startswith("fact:"):
            prov = ProvenanceConfidence.USER_CONFIRMED
            action = "system.field_confirmed"
        else:
            continue
        db.add(PrefillDisposition(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            system_id=system.id,
            field_key=entry,
            provenance=prov,
            actor_user_id=ctx.user_id,
        ))
        db.add(AuditEvent(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user_id,
            action=action,
            entity_type="system",
            entity_id=system.id,
            detail={"field": entry},
        ))


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

    Classification branches on disposition (D-71, D-73, INV-82):
      REQUIRES_CONTEXT → gate-2 seam snapshot; off_label=True when product
                         present but no membership category declared (D-72).
      AUTHORITATIVE    → status=APPROVED, eu_tier stamped immediately.
      DOWN_SELECTION   → status=PENDING_REVIEW, eu_tier NOT stamped;
                         reviewer sign-off stamps it (D-73).
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

    # Step 1b — disposition intake prefills (INV-83, D-74, D-75).
    # Custom systems and no-product systems have no seeds — no rows written.
    if not payload.is_custom and payload.catalogue_product_id:
        prefill = get_prefill_by_product(payload.catalogue_product_id, db)
        product = db.get(CatalogueProduct, payload.catalogue_product_id)
        product_name = product.name if product else None
        fp = prefill.field_prefills or FieldPrefills()
        _dispose_intake_prefill(db, system, payload, fp, product_name, ctx)
        _dispose_fact_prefill(db, system, payload.confirmed_fields, ctx)
        db.flush()

    # Step 2 — create use case + link rows (INV-77: tenant_id stamped on links)
    use_case = UseCase(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        system_id=system.id,
        title=payload.title,
        product_category_id=payload.intended_use_category_id,
        context_blob=payload.context_blob,
        usage_context_id=payload.usage_context_id,
        human_oversight_type_id=payload.human_oversight_type_id,
    )
    db.add(use_case)
    db.flush()

    _replace_data_categories(db, use_case.id, ctx.tenant_id, payload.data_category_ids)
    _replace_affected_parties(db, use_case.id, ctx.tenant_id, payload.affected_party_ids)
    db.flush()

    # Step 3 — classify and branch on disposition (D-71, D-73, INV-82)
    proposal = resolve_classification(system.id, use_case.id, db)

    if proposal.requires_context:
        # Gate-2 seam: "Other" = product present + no declared membership (D-72).
        off_label = (
            payload.catalogue_product_id is not None
            and payload.intended_use_category_id is None
        )
        classification = snapshot_classification(
            use_case, proposal, db,
            actor_user_id=ctx.user_id,
            status=ClassificationStatus.PENDING_REVIEW,
            stamp_eu_tier=True,
            off_label=off_label,
        )
    elif proposal.disposition == ClassificationDisposition.AUTHORITATIVE:
        classification = snapshot_classification(
            use_case, proposal, db,
            actor_user_id=ctx.user_id,
            status=ClassificationStatus.APPROVED,
            stamp_eu_tier=True,
        )
    else:
        # DOWN_SELECTION: reviewer sign-off stamps eu_tier (D-73).
        classification = snapshot_classification(
            use_case, proposal, db,
            actor_user_id=ctx.user_id,
            status=ClassificationStatus.PENDING_REVIEW,
            stamp_eu_tier=False,
        )

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
