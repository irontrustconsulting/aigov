"""
Catalogue-scoped tenant reads (DM-S2, DF-D2-2).

  GET /v1/catalogue/products/{product_id}/prefill
      Member-gated (any tenant member). Returns catalogue facts for the
      product so the prefill step can run before a system exists.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.context import get_tenant_db
from app.schemas.system import PrefillResponse
from app.services import prefill_service

router = APIRouter(prefix="/catalogue", tags=["catalogue"])


@router.get("/products/{product_id}/prefill", response_model=PrefillResponse)
def get_product_prefill(
    product_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
) -> PrefillResponse:
    """Return catalogue facts for a product. Any authenticated tenant member.
    Custom / no-product callers pass a nil UUID and receive an empty 200."""
    return prefill_service.get_prefill_by_product(product_id, db)
