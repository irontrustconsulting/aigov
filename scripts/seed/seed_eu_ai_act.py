"""
Seed the EU AI Act governance taxonomy: categories with nested subcategories.
Subcategories carry the tier and a legal_ref citation (for defensibility).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EUAIActCategory, EUAIActSubcategory
from app.models.base import EUAIActTier
from scripts.seed.common import load_yaml, make_engine, upsert


def transform_category(session: Session, raw: dict) -> dict:
    return {
        "code": raw["code"],
        "name": raw["name"],
        "description": raw.get("description"),
        # "legal_ref": raw.get("legal_ref"),
    }


def upsert_subcategories(session: Session, raw: dict) -> tuple[int, int]:
    """Upsert subcategories under one category, keyed on code. Persisted (not
    delete-and-recreate) because use cases may FK-reference them."""
    category = session.scalar(
        select(EUAIActCategory).where(EUAIActCategory.code == raw["code"])
    )
    if category is None:
        raise RuntimeError(f"category {raw['code']} not found after upsert")

    ins = upd = 0
    for sub in raw.get("subcategories", []):
        existing = session.scalar(
            select(EUAIActSubcategory).where(EUAIActSubcategory.code == sub["code"])
        )
        fields = {
            "category_id": category.id,
            "code": sub["code"],
            "name": sub["name"],
            "description": sub.get("description"),
            "legal_ref": sub.get("legal_ref"),
            "tier": EUAIActTier(sub["tier"]),
        }
        if existing is None:
            session.add(EUAIActSubcategory(**fields))
            ins += 1
        else:
            for k, v in fields.items():
                setattr(existing, k, v)
            upd += 1
    return ins, upd


def main(session: Session | None = None) -> None:
    entries = load_yaml("eu_ai_act.yaml")

    own = session is None
    if own:
        session = Session(make_engine())

    try:
        c_ins, c_upd = upsert(session, EUAIActCategory, entries, ["code"], transform_category)
        session.flush()
        s_ins = s_upd = 0
        for raw in entries:
            i, u = upsert_subcategories(session, raw)
            s_ins += i; s_upd += u
        if own:
            session.commit()
        print(f"  eu_ai_act: categories {c_ins} ins/{c_upd} upd, "
              f"subcategories {s_ins} ins/{s_upd} upd")
    finally:
        if own:
            session.close()


if __name__ == "__main__":
    main()