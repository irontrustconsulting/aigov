"""
Catalogue-scoped tenant reads (DM-S2, DF-D2-2).

  GET /v1/catalogue/products/{product_id}/prefill
      Member-gated (any tenant member). Returns catalogue facts for the
      product so the prefill step can run before a system exists.

  GET /v1/catalogue/products/{product_id}/categories
      Member-gated (any tenant member). Returns the product_category
      memberships for a product — feeds the intended-use category
      SingleSelect in the wizard use-case step (FE-31, WI-3).
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.context import get_tenant_db
from app.models.taxonomy import ProductCategoryMembership
from app.schemas.system import PrefillResponse
from app.services import prefill_service

router = APIRouter(prefix="/catalogue", tags=["catalogue"])


class ProductCategoryRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None


@router.get("/products/{product_id}/prefill", response_model=PrefillResponse)
def get_product_prefill(
    product_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
) -> PrefillResponse:
    """Return catalogue facts for a product. Any authenticated tenant member.
    Custom / no-product callers pass a nil UUID and receive an empty 200."""
    return prefill_service.get_prefill_by_product(product_id, db)


@router.get("/products/{product_id}/categories", response_model=list[ProductCategoryRead])
def get_product_categories(
    product_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
) -> list[ProductCategoryRead]:
    """Return the product_category memberships for a product.

    Any authenticated tenant member. No audit. Returns an empty list for
    a product with no category memberships or for a nil/unknown product_id.
    """
    memberships = db.scalars(
        select(ProductCategoryMembership)
        .where(ProductCategoryMembership.catalogue_product_id == product_id)
        .options(selectinload(ProductCategoryMembership.product_category))
    ).all()

    return [
        ProductCategoryRead(
            id=m.product_category.id,
            code=m.product_category.code,
            name=m.product_category.name,
            description=m.product_category.description,
            parent_id=m.product_category.parent_id,
        )
        for m in memberships
    ]
