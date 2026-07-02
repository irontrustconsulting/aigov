"""
Prefill service — returns catalogue facts for the confirm/amend UX.

Pure read: no audit event, no writes. A system without a linked product
returns 200 with an empty facts list (sprint invariant 6: prefill is not 404).
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import System
from app.models.domain import CatalogueFact, CatalogueProduct
from app.models.intake import EUOperatorRole
from app.models.base import SystemLifecycleStage
from app.schemas.system import (
    CatalogueFactOut, FieldPrefill, FieldPrefills, PrefillResponse,
)


def _build_field_prefills(product: CatalogueProduct, db: Session) -> FieldPrefills:
    """Compute typed field prefills for a catalogue-linked product.

    Derived fields (operator_role_id, lifecycle_stage) are always returned.
    Catalogue fields (hosting_model_id, purpose) are omitted when the product
    has no curated value.
    """
    deployer = db.scalar(
        select(EUOperatorRole).where(EUOperatorRole.code == "deployer")
    )

    fp: dict[str, FieldPrefill] = {}

    if deployer is not None:
        fp["operator_role_id"] = FieldPrefill(
            value=str(deployer.id), basis="derived"
        )

    fp["lifecycle_stage"] = FieldPrefill(
        value=SystemLifecycleStage.PRODUCTION.value, basis="derived"
    )

    if product.hosting_model_id is not None:
        fp["hosting_model_id"] = FieldPrefill(
            value=str(product.hosting_model_id), basis="catalogue"
        )

    if product.intended_use is not None:
        fp["purpose"] = FieldPrefill(value=product.intended_use, basis="catalogue")

    return FieldPrefills(**fp)


def get_prefill_by_product(
    catalogue_product_id: uuid.UUID | None,
    db: Session,
) -> PrefillResponse:
    """Return catalogue facts and typed field prefills for a product.

    Empty response when product is None (custom / no-product path).
    """
    if catalogue_product_id is None:
        return PrefillResponse(catalogue_product_id=None, facts=[])

    product = db.scalar(
        select(CatalogueProduct).where(CatalogueProduct.id == catalogue_product_id)
    )
    if product is None:
        return PrefillResponse(catalogue_product_id=catalogue_product_id, facts=[])

    facts = db.scalars(
        select(CatalogueFact)
        .where(CatalogueFact.product_id == catalogue_product_id)
        .order_by(CatalogueFact.key)
    ).all()

    return PrefillResponse(
        catalogue_product_id=catalogue_product_id,
        facts=[CatalogueFactOut.model_validate(f) for f in facts],
        field_prefills=_build_field_prefills(product, db),
    )


def get_prefill(
    system_id: uuid.UUID,
    db: Session,
) -> PrefillResponse:
    """
    Return catalogue facts for a system's linked product.
    Empty list when no product is linked or system is custom.
    """
    system = db.scalar(select(System).where(System.id == system_id))
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="System not found")

    if not system.catalogue_product_id or system.is_custom:
        return PrefillResponse(catalogue_product_id=None, facts=[])

    return get_prefill_by_product(system.catalogue_product_id, db)
