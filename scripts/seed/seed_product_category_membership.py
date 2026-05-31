"""
Seed product -> product-category membership (M:N).
Resolves product by name and category by code. Depends on catalogue + product_category.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CatalogueProduct, ProductCategory, ProductCategoryMembership
from scripts.seed.common import run_seed


def _resolve_product(session: Session, name: str):
    row = session.scalar(select(CatalogueProduct).where(CatalogueProduct.name == name))
    if row is None:
        raise RuntimeError(f"catalogue product '{name}' not found — seed the catalogue first")
    return row.id


def _resolve_category(session: Session, code: str):
    row = session.scalar(select(ProductCategory).where(ProductCategory.code == code))
    if row is None:
        raise RuntimeError(f"product category '{code}' not found — seed product_category first")
    return row.id


def transform_membership(session: Session, raw: dict) -> dict:
    return {
        "catalogue_product_id": _resolve_product(session, raw["product_name"]),
        "product_category_id": _resolve_category(session, raw["product_category_code"]),
    }


def main(session: Session | None = None) -> None:
    run_seed(
        label="product_category_membership",
        filename="product_category_membership.yaml",
        model=ProductCategoryMembership,
        key_fields=["catalogue_product_id", "product_category_id"],
        transform=transform_membership,
        session=session,
    )


if __name__ == "__main__":
    main()