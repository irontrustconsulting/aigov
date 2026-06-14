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
from app.models.domain import CatalogueFact
from app.schemas.system import CatalogueFactOut, PrefillResponse


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

    facts = db.scalars(
        select(CatalogueFact)
        .where(CatalogueFact.product_id == system.catalogue_product_id)
        .order_by(CatalogueFact.key)
    ).all()

    return PrefillResponse(
        catalogue_product_id=system.catalogue_product_id,
        facts=[CatalogueFactOut.model_validate(f) for f in facts],
    )
