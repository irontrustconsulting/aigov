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
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.auth.context import TenantContext
from app.models import Membership, System, User
from app.models.base import ProvenanceConfidence
from app.models.domain import CatalogueProduct, CatalogueVendor, PrefillDisposition
from app.models.intake import EUOperatorRole, HostingModel
from app.models.lifecycle import AuditEvent
from app.schemas.system import (
    CatalogueProductRef, CatalogueVendorRef,
    SystemCreate, SystemDetail, SystemUpdate,
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
    field_provenance: dict[str, str] | None = None,
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
        lifecycle_stage=system.lifecycle_stage,
        purpose=system.metadata_blob.get("purpose") if system.metadata_blob else None,
        use_case_count=len(use_cases),
        use_case_lifecycle_states=[
            UseCaseStateSummary(use_case_id=uc_row.id, state=uc_row.state)
            for uc_row in use_cases
        ],
        created_at=system.created_at,
        updated_at=system.updated_at,
        field_provenance=field_provenance or None,
    )


def _load_system_full(system_id: uuid.UUID, db: Session) -> System:
    """Load a system with all relationships needed for SystemDetail."""
    system = db.scalar(
        select(System)
        .where(System.id == system_id)
        .options(selectinload(System.use_cases))
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
        lifecycle_stage=payload.lifecycle_stage,
        metadata_blob=metadata_blob,
    )
    db.add(system)
    db.flush()

    # 5. Stage audit event
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

    # Capture provenance-bearing field changes before applying (WI-PATCH, D-75).
    changed_provenance: list[tuple[str, str]] = []
    if payload.name is not None and payload.name != system.name:
        changed_provenance.append(("name", payload.name))
    if payload.operator_role_id is not None and payload.operator_role_id != system.operator_role_id:
        changed_provenance.append(("operator_role_id", str(payload.operator_role_id)))
    if payload.hosting_model_id is not None and payload.hosting_model_id != system.hosting_model_id:
        changed_provenance.append(("hosting_model_id", str(payload.hosting_model_id)))
    if payload.lifecycle_stage is not None and payload.lifecycle_stage != system.lifecycle_stage:
        changed_provenance.append(("lifecycle_stage", payload.lifecycle_stage.value))
    if payload.purpose is not None and payload.purpose != (system.metadata_blob or {}).get("purpose"):
        changed_provenance.append(("purpose", payload.purpose))

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
    if payload.lifecycle_stage is not None:
        system.lifecycle_stage = payload.lifecycle_stage

    # Update metadata_blob
    blob = dict(system.metadata_blob or {})
    if payload.purpose is not None:
        blob["purpose"] = payload.purpose
    system.metadata_blob = blob

    # Upsert prefill_disposition to USER_AMENDED for each changed provenance field.
    for field_key, new_val in changed_provenance:
        db.execute(
            pg_insert(PrefillDisposition).values(
                id=uuid.uuid4(),
                tenant_id=ctx.tenant_id,
                system_id=system_id,
                field_key=field_key,
                provenance=ProvenanceConfidence.USER_AMENDED,
                actor_user_id=ctx.user_id,
            ).on_conflict_do_update(
                constraint="uq_prefill_disposition_system_field",
                set_={
                    "provenance": ProvenanceConfidence.USER_AMENDED.value,
                    "actor_user_id": ctx.user_id,
                },
            )
        )
        db.add(AuditEvent(
            id=uuid.uuid4(),
            tenant_id=ctx.tenant_id,
            actor_user_id=ctx.user_id,
            action="system.field_amended",
            entity_type="system",
            entity_id=system_id,
            detail={"field": field_key, "value": new_val},
        ))

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

    dispositions = db.scalars(
        select(PrefillDisposition).where(PrefillDisposition.system_id == system_id)
    ).all()
    fp = {d.field_key: d.provenance.value for d in dispositions} if dispositions else None

    return _build_detail(
        system,
        product=db.get(CatalogueProduct, system.catalogue_product_id) if system.catalogue_product_id else None,
        vendor=db.get(CatalogueVendor, system.catalogue_vendor_id) if system.catalogue_vendor_id else None,
        op_role=db.get(EUOperatorRole, system.operator_role_id) if system.operator_role_id else None,
        hm=db.get(HostingModel, system.hosting_model_id) if system.hosting_model_id else None,
        field_provenance=fp,
    )
