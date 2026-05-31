"""
Seed the BRIDGE: product category -> EU AI Act subcategory (with is_primary).
Resolves both sides by code. Depends on eu_ai_act + product_category.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProductCategory, EUAIActSubcategory, ProductCategoryEUMapping
from scripts.seed.common import run_seed


def _resolve(session: Session, model: type, code: str, kind: str):
    row = session.scalar(select(model).where(model.code == code))
    if row is None:
        raise RuntimeError(f"{kind} '{code}' not found — seed {kind} before the bridge")
    return row.id


def transform_mapping(session: Session, raw: dict) -> dict:
    return {
        "product_category_id": _resolve(session, ProductCategory,
                                        raw["product_category_code"], "product_category"),
        "eu_ai_act_subcategory_id": _resolve(session, EUAIActSubcategory,
                                             raw["eu_ai_act_subcategory_code"], "eu_ai_act_subcategory"),
        "is_primary": raw.get("is_primary", False),
    }


def main(session: Session | None = None) -> None:
    run_seed(
        label="product_category_eu_mapping",
        filename="product_category_eu_mapping.yaml",
        model=ProductCategoryEUMapping,
        key_fields=["product_category_id", "eu_ai_act_subcategory_id"],
        transform=transform_mapping,
        session=session,
    )


if __name__ == "__main__":
    main()