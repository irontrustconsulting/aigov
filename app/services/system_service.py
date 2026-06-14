"""
System service — create, update, and read AI system registrations.

Service ordering (sprint §11):
  1. Resolve ctx.tenant_id.
  2. Pre-checks (fail fast, 422/409 before any write).
  3. Derive catalogue_vendor_id from product when product present.
  4. Upsert system row + replace link rows.
  5. Write metadata_blob (purpose, etc.).
  6. Stage audit_event in the SAME session.
  7. db.flush() — caller (router via get_tenant_db) commits.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.auth.context import TenantContext
from app.models import Membership, System, User
from app.models.domain import CatalogueProduct, CatalogueVendor
from app.models.intake import (
    AffectedParty, DataCategory, EUOperatorRole,
    HostingModel, HumanOversightType, SystemAffectedParty,
    SystemDataCategory, UsageContext,
)
from app.models.lifecycle import AuditEvent
from app.schemas.system import (
    AffectedPartyOut, CatalogueProductRef, CatalogueVendorRef,
    DataCategoryOut, SystemCreate, SystemDetail, SystemUpdate,
    UseCaseStateSummary, VocabItemOut,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assert_active(db: Session, model, id_: uuid.UUID, label: str) -> object:
    """Load a vocab row and reject if missing or inactive."""
    row = db.get(model, id_)
    if row is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} {id_} not found",
        )
    if not row.active:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} {id_} is inactive",
        )
    return row


def _validate_vocab_fks(db: Session, payload: SystemCreate | SystemUpdate) -> None:
    if payload.operator_role_id is not None:
        _assert_active(db, EUOperatorRole, payload.operator_role_id, "operator_role_id")
    if payload.hosting_model_id is not None:
        _assert_active(db, HostingModel, payload.hosting_model_id, "hosting_model_id")
    if payload.usage_context_id is not None:
        _assert_active(db, UsageContext, payload.usage_context_id, "usage_context_id")
    if payload.human_oversight_type_id is not None:
        _assert_active(db, HumanOversightType, payload.human_oversight_type_id, "human_oversight_type_id")
    for dc_id in (payload.data_category_ids or []):
        _assert_active(db, DataCategory, dc_id, "data_category_id")
    for ap_id in (payload.affected_party_ids or []):
        _assert_active(db, AffectedParty, ap_id, "affected_party_id")


def _validate_owner(db: Session, owner_user_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    user = db.get(User, owner_user_id)
    if user is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"owner_user_id {owner_user_id} not found",
        )
    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == owner_user_id,
            Membership.tenant_id == tenant_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"owner_user_id {owner_user_id} is not a member of this tenant",
        )


def _derive_vendor_id(
    db: Session,
    catalogue_product_id: uuid.UUID,
) -> uuid.UUID:
    """Load the product and return its vendor_id. Raises 422 if not found."""
    product = db.get(CatalogueProduct, catalogue_product_id)
    if product is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"catalogue_product_id {catalogue_product_id} not found",
        )
    return product.vendor_id


def _replace_data_categories(
    db: Session,
    system_id: uuid.UUID,
    data_category_ids: list[uuid.UUID],
) -> None:
    db.execute(delete(SystemDataCategory).where(SystemDataCategory.system_id == system_id))
    for dc_id in data_category_ids:
        db.add(SystemDataCategory(
            id=uuid.uuid4(),
            system_id=system_id,
            data_category_id=dc_id,
        ))


def _replace_affected_parties(
    db: Session,
    system_id: uuid.UUID,
    affected_party_ids: list[uuid.UUID],
) -> None:
    db.execute(delete(SystemAffectedParty).where(SystemAffectedParty.system_id == system_id))
    for ap_id in affected_party_ids:
        db.add(SystemAffectedParty(
            id=uuid.uuid4(),
            system_id=system_id,
            affected_party_id=ap_id,
        ))


def _stage_audit(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    action: str,
    system: System,
) -> None:
    db.add(AuditEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type="system",
        entity_id=system.id,
        detail={"name": system.name},
    ))


def _build_detail(
    system: System,
    *,
    product=None,
    vendor=None,
    op_role=None,
    hm=None,
    uc=None,
    hot=None,
) -> SystemDetail:
    """Assemble a SystemDetail from a loaded System ORM object and pre-fetched refs."""
    use_cases = system.use_cases or []
    return SystemDetail(
        id=system.id,
        name=system.name,
        is_custom=system.is_custom,
        catalogue_product=CatalogueProductRef(
            id=product.id, name=product.name,
        ) if product else None,
        catalogue_vendor=CatalogueVendorRef(
            id=vendor.id, name=vendor.name,
        ) if vendor else None,
        owner_user_id=system.owner_user_id,
        operator_role=VocabItemOut(
            id=op_role.id, code=op_role.code, label=op_role.label,
        ) if op_role else None,
        hosting_model=VocabItemOut(
            id=hm.id, code=hm.code, label=hm.label,
        ) if hm else None,
        usage_context=VocabItemOut(
            id=uc.id, code=uc.code, label=uc.label,
        ) if uc else None,
        human_oversight_type=VocabItemOut(
            id=hot.id, code=hot.code, label=hot.label,
        ) if hot else None,
        lifecycle_stage=system.lifecycle_stage,
        data_categories=[
            DataCategoryOut(
                id=link.data_category.id,
                code=link.data_category.code,
                label=link.data_category.label,
                is_special_category=link.data_category.is_special_category,
            )
            for link in (system.data_categories or [])
        ],
        affected_parties=[
            AffectedPartyOut(
                id=link.affected_party.id,
                code=link.affected_party.code,
                label=link.affected_party.label,
                is_vulnerable_group=link.affected_party.is_vulnerable_group,
            )
            for link in (system.affected_parties or [])
        ],
        purpose=system.metadata_blob.get("purpose") if system.metadata_blob else None,
        use_case_count=len(use_cases),
        use_case_lifecycle_states=[
            UseCaseStateSummary(use_case_id=uc_row.id, state=uc_row.state)
            for uc_row in use_cases
        ],
        created_at=system.created_at,
        updated_at=system.updated_at,
    )


def _load_system_full(system_id: uuid.UUID, db: Session) -> System:
    """Load a system with all relationships needed for SystemDetail."""
    system = db.scalar(
        select(System)
        .where(System.id == system_id)
        .options(
            selectinload(System.data_categories).selectinload(SystemDataCategory.data_category),
            selectinload(System.affected_parties).selectinload(SystemAffectedParty.affected_party),
            selectinload(System.use_cases),
        )
    )
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="System not found")
    return system


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_system(
    payload: SystemCreate,
    ctx: TenantContext,
    db: Session,
) -> System:
    """
    Create a new system and stage an audit event. Caller commits.
    Returns the new System ORM object (without relationships loaded).
    """
    # 1. Pre-checks
    if payload.is_custom and (payload.catalogue_product_id or payload.catalogue_vendor_id):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="is_custom=true cannot be combined with catalogue_product_id or catalogue_vendor_id",
        )
    if payload.owner_user_id is not None:
        _validate_owner(db, payload.owner_user_id, ctx.tenant_id)
    _validate_vocab_fks(db, payload)

    # 2. Derive vendor from product
    vendor_id = None
    if payload.catalogue_product_id is not None:
        vendor_id = _derive_vendor_id(db, payload.catalogue_product_id)
    elif payload.catalogue_vendor_id is not None:
        vendor_id = payload.catalogue_vendor_id

    # 3. Build metadata_blob
    metadata_blob: dict = {}
    if payload.purpose is not None:
        metadata_blob["purpose"] = payload.purpose

    # 4. Insert system row
    system = System(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        name=payload.name,
        is_custom=payload.is_custom,
        catalogue_product_id=payload.catalogue_product_id,
        catalogue_vendor_id=vendor_id,
        owner_user_id=payload.owner_user_id,
        operator_role_id=payload.operator_role_id,
        hosting_model_id=payload.hosting_model_id,
        usage_context_id=payload.usage_context_id,
        human_oversight_type_id=payload.human_oversight_type_id,
        lifecycle_stage=payload.lifecycle_stage,
        metadata_blob=metadata_blob,
    )
    db.add(system)
    db.flush()  # get system.id before inserting link rows

    # 5. Insert link rows
    _replace_data_categories(db, system.id, payload.data_category_ids)
    _replace_affected_parties(db, system.id, payload.affected_party_ids)

    # 6. Stage audit event
    _stage_audit(db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
                 action="system.created", system=system)

    db.flush()
    return system


def update_system(
    system_id: uuid.UUID,
    payload: SystemUpdate,
    ctx: TenantContext,
    db: Session,
) -> System:
    """
    Update an existing system. Caller commits.
    Returns the updated System ORM object.
    """
    # Load existing (RLS scopes to tenant)
    system = db.scalar(select(System).where(System.id == system_id))
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="System not found")

    # Pre-checks
    if payload.is_custom is not None:
        new_is_custom = payload.is_custom
    else:
        new_is_custom = system.is_custom

    # Detect product change
    product_changed = (
        payload.catalogue_product_id is not None
        and payload.catalogue_product_id != system.catalogue_product_id
    )
    if product_changed:
        from app.models.domain import UseCase
        has_use_case = db.scalar(
            select(UseCase.id).where(UseCase.system_id == system_id).limit(1)
        )
        if has_use_case is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Cannot change catalogue_product_id when use cases exist",
            )

    effective_product_id = (
        payload.catalogue_product_id
        if payload.catalogue_product_id is not None
        else system.catalogue_product_id
    )
    if new_is_custom and effective_product_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="is_custom=true cannot be combined with catalogue_product_id",
        )

    if payload.owner_user_id is not None:
        _validate_owner(db, payload.owner_user_id, ctx.tenant_id)

    _validate_vocab_fks(db, payload)

    # Derive vendor if product changed
    if product_changed and payload.catalogue_product_id is not None:
        system.catalogue_vendor_id = _derive_vendor_id(db, payload.catalogue_product_id)
    elif payload.catalogue_vendor_id is not None and not product_changed:
        system.catalogue_vendor_id = payload.catalogue_vendor_id

    # Apply field updates (only supplied non-None values)
    if payload.name is not None:
        system.name = payload.name
    if payload.is_custom is not None:
        system.is_custom = payload.is_custom
    if payload.catalogue_product_id is not None:
        system.catalogue_product_id = payload.catalogue_product_id
    if payload.owner_user_id is not None:
        system.owner_user_id = payload.owner_user_id
    if payload.operator_role_id is not None:
        system.operator_role_id = payload.operator_role_id
    if payload.hosting_model_id is not None:
        system.hosting_model_id = payload.hosting_model_id
    if payload.usage_context_id is not None:
        system.usage_context_id = payload.usage_context_id
    if payload.human_oversight_type_id is not None:
        system.human_oversight_type_id = payload.human_oversight_type_id
    if payload.lifecycle_stage is not None:
        system.lifecycle_stage = payload.lifecycle_stage

    # Update metadata_blob
    blob = dict(system.metadata_blob or {})
    if payload.purpose is not None:
        blob["purpose"] = payload.purpose
    system.metadata_blob = blob

    # Replace link rows if supplied
    if payload.data_category_ids is not None:
        _replace_data_categories(db, system.id, payload.data_category_ids)
    if payload.affected_party_ids is not None:
        _replace_affected_parties(db, system.id, payload.affected_party_ids)

    # Stage audit event
    _stage_audit(db, tenant_id=ctx.tenant_id, actor_user_id=ctx.user_id,
                 action="system.updated", system=system)

    db.flush()
    return system


def get_system_detail(
    system_id: uuid.UUID,
    db: Session,
) -> SystemDetail:
    """
    Load a system with all relationships and assemble SystemDetail.
    Emits no audit event. RLS-scoped session handles tenant isolation.
    """
    system = _load_system_full(system_id, db)

    return _build_detail(
        system,
        product=db.get(CatalogueProduct, system.catalogue_product_id) if system.catalogue_product_id else None,
        vendor=db.get(CatalogueVendor, system.catalogue_vendor_id) if system.catalogue_vendor_id else None,
        op_role=db.get(EUOperatorRole, system.operator_role_id) if system.operator_role_id else None,
        hm=db.get(HostingModel, system.hosting_model_id) if system.hosting_model_id else None,
        uc=db.get(UsageContext, system.usage_context_id) if system.usage_context_id else None,
        hot=db.get(HumanOversightType, system.human_oversight_type_id) if system.human_oversight_type_id else None,
    )
