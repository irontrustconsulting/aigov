"""
Reference service — product detail read for the selection wizard.

Pure read, no auth gate, no audit. Uses a plain (non-RLS) session since
catalogue data is global reference data.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import CatalogueProduct, CatalogueVendor
from app.models.taxonomy import (
    EUAIActSubcategory,
    ProductCategory,
    ProductCategoryEUMapping,
    ProductCategoryMembership,
)
from app.schemas.system import (
    CatalogueVendorRef,
    CategoryRef,
    EUAIActSubcategoryRef,
    ProductDetailOut,
)


def get_product_detail(product_id: uuid.UUID, db: Session) -> ProductDetailOut:
    """
    Return vendor, category tags, and EU AI Act subcategories for a product.
    Raises 404 if the product is not found.
    """
    product = db.get(CatalogueProduct, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")

    vendor = db.get(CatalogueVendor, product.vendor_id)

    categories = db.scalars(
        select(ProductCategory)
        .join(
            ProductCategoryMembership,
            ProductCategoryMembership.product_category_id == ProductCategory.id,
        )
        .where(ProductCategoryMembership.catalogue_product_id == product_id)
        .distinct()
        .order_by(ProductCategory.name)
    ).all()

    subcategories = db.scalars(
        select(EUAIActSubcategory)
        .join(
            ProductCategoryEUMapping,
            ProductCategoryEUMapping.eu_ai_act_subcategory_id == EUAIActSubcategory.id,
        )
        .join(
            ProductCategoryMembership,
            ProductCategoryMembership.product_category_id == ProductCategoryEUMapping.product_category_id,
        )
        .where(ProductCategoryMembership.catalogue_product_id == product_id)
        .distinct()
        .order_by(EUAIActSubcategory.code)
    ).all()

    return ProductDetailOut(
        id=product.id,
        name=product.name,
        vendor=CatalogueVendorRef(id=vendor.id, name=vendor.name) if vendor else None,
        categories=[CategoryRef(id=c.id, name=c.name) for c in categories],
        eu_ai_act_subcategories=[
            EUAIActSubcategoryRef(id=s.id, code=s.code, label=s.name)
            for s in subcategories
        ],
    )
