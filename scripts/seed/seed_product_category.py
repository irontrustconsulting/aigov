"""
Seed user-facing product categories (hierarchical via `parent` code).

Two-pass: upsert all categories first (so every code exists), then resolve
parent references. This avoids ordering problems — a child can appear before
its parent in the file.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProductCategory
from scripts.seed.common import load_yaml, make_engine, upsert


def transform_category(session: Session, raw: dict) -> dict:
    # Parent resolved in a second pass; insert/update the row's own fields here.
    return {
        "code": raw["code"],
        "name": raw["name"],
        "description": raw.get("description"),
    }


def resolve_parents(session: Session, entries: list[dict]) -> None:
    for raw in entries:
        parent_code = raw.get("parent")
        if not parent_code:
            continue
        child = session.scalar(select(ProductCategory).where(ProductCategory.code == raw["code"]))
        parent = session.scalar(select(ProductCategory).where(ProductCategory.code == parent_code))
        if parent is None:
            raise RuntimeError(
                f"product category '{raw['code']}' references unknown parent '{parent_code}'"
            )
        child.parent_id = parent.id


def main(session: Session | None = None) -> None:
    entries = load_yaml("product_category.yaml")

    own = session is None
    if own:
        session = Session(make_engine())

    try:
        ins, upd = upsert(session, ProductCategory, entries, ["code"], transform_category)
        session.flush()
        resolve_parents(session, entries)
        if own:
            session.commit()
        print(f"  product_category: {ins} inserted, {upd} updated ({len(entries)} in file)")
    finally:
        if own:
            session.close()


if __name__ == "__main__":
    main()