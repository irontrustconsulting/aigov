"""
Reference-data read endpoints (v1) — the curated global vocabularies the
frontend consumes. Read-only; global tables, so plain `get_db`.

The product-category endpoints form the registration wizard's drill-down:
  list categories  ->  vendors in a category  ->  products in a category.
These return [] cleanly while the taxonomy is unseeded; they come alive once
the taxonomy seed is loaded.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.context import TenantContext, get_tenant_db, require_role
from app.db import get_db
from app.models import (
    CatalogueProduct,
    CatalogueVendor,
    EUAIActSubcategory,
    ProductCategory,
    ProductCategoryMembership,
)
from app.models.base import Framework, RiskLayer
from app.models.knowledge import Control, ControlFrameworkMap, Risk
from app.schemas.reference import (
    ControlRead,
    EUAIActSubcategoryRead,
    ProductCategoryRead,
    ProductRead,
    RiskRead,
    VendorRead,
)
from app.schemas.system import ProductDetailOut
from app.services.reference_service import get_product_detail

router = APIRouter(prefix="/reference", tags=["reference"])

# Risk/control library reads require tenant authentication (any member) —
# unlike the wizard's product/category reads above, these back AIIA item
# authoring and should not be anonymous (design doc §6).
_ANY_MEMBER = ("admin", "member")


@router.get("/product-categories", response_model=list[ProductCategoryRead])
def list_product_categories(
    parent_id: uuid.UUID | None = Query(
        default=None,
        description="If given, return children of this category (drill-down). "
                    "If omitted, return top-level categories.",
    ),
    db: Session = Depends(get_db),
) -> list[ProductCategory]:
    """List product categories. With no parent_id, returns top-level (roots);
    with parent_id, returns that category's children — the wizard drill-down."""
    stmt = select(ProductCategory).order_by(ProductCategory.name)
    if parent_id is None:
        stmt = stmt.where(ProductCategory.parent_id.is_(None))
    else:
        stmt = stmt.where(ProductCategory.parent_id == parent_id)
    return list(db.scalars(stmt))


@router.get("/product-categories/{category_id}/vendors", response_model=list[VendorRead])
def vendors_in_category(category_id: uuid.UUID, db: Session = Depends(get_db)) -> list[CatalogueVendor]:
    """Vendors that have at least one product in this category (wizard step:
    category -> vendors). Distinct vendors via the membership join."""
    stmt = (
        select(CatalogueVendor)
        .join(CatalogueProduct, CatalogueProduct.vendor_id == CatalogueVendor.id)
        .join(ProductCategoryMembership,
              ProductCategoryMembership.catalogue_product_id == CatalogueProduct.id)
        .where(ProductCategoryMembership.product_category_id == category_id)
        .distinct()
        .order_by(CatalogueVendor.name)
    )
    return list(db.scalars(stmt))


@router.get("/product-categories/{category_id}/products", response_model=list[ProductRead])
def products_in_category(
    category_id: uuid.UUID,
    vendor_id: uuid.UUID | None = Query(
        default=None, description="Optionally narrow to one vendor."
    ),
    db: Session = Depends(get_db),
) -> list[CatalogueProduct]:
    """Products in a category (wizard step: -> specific product), optionally
    filtered to a chosen vendor."""
    stmt = (
        select(CatalogueProduct)
        .join(ProductCategoryMembership,
              ProductCategoryMembership.catalogue_product_id == CatalogueProduct.id)
        .where(ProductCategoryMembership.product_category_id == category_id)
        .order_by(CatalogueProduct.name)
    )
    if vendor_id is not None:
        stmt = stmt.where(CatalogueProduct.vendor_id == vendor_id)
    return list(db.scalars(stmt))


@router.get("/eu-ai-act/subcategories", response_model=list[EUAIActSubcategoryRead])
def list_eu_subcategories(db: Session = Depends(get_db)) -> list[EUAIActSubcategory]:
    """The EU AI Act governance subcategories (each carries its tier)."""
    return list(db.scalars(select(EUAIActSubcategory).order_by(EUAIActSubcategory.code)))


@router.get("/products/{product_id}", response_model=ProductDetailOut)
def get_product_detail_endpoint(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ProductDetailOut:
    """Product detail for the selection wizard: vendor, category tags, EU AI Act subcategories."""
    return get_product_detail(product_id, db)


@router.get("/risks", response_model=list[RiskRead])
def list_risks(
    layer: RiskLayer | None = Query(default=None, description="Filter by risk layer."),
    ctx: TenantContext = Depends(require_role(*_ANY_MEMBER)),
    db: Session = Depends(get_tenant_db),
) -> list[Risk]:
    """Risk library reads, gated to any authenticated tenant member (AIIA
    item authoring needs this; the wizard endpoints above do not)."""
    stmt = select(Risk).order_by(Risk.code)
    if layer is not None:
        stmt = stmt.where(Risk.layer == layer)
    return list(db.scalars(stmt))


@router.get("/controls", response_model=list[ControlRead])
def list_controls(
    framework: Framework | None = Query(default=None, description="filter framework"),
    ctx: TenantContext = Depends(require_role(*_ANY_MEMBER)),
    db: Session = Depends(get_tenant_db),
) -> list[Control]:
    """Control library reads, gated to any authenticated tenant member."""
    stmt = (
        select(Control)
        .options(selectinload(Control.framework_maps))
        .order_by(Control.code)
    )
    if framework is not None:
        stmt = (
            stmt.join(ControlFrameworkMap, ControlFrameworkMap.control_id == Control.id)
            .where(ControlFrameworkMap.framework == framework)
        )
    return list(db.scalars(stmt))