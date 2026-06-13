"""
Seed the governance role catalogue (governance_role).

The SoD conflict matrix (governance_role_conflict) is seeded directly in the
migration — it depends on the role UUIDs and uses LEAST/GREATEST for canonical
ordering, which is easier to express in SQL than here. This script is
idempotent for the catalogue only.

Conflict rows are NOT touched here. Running this after the migration is already
applied is safe: upsert by key means no duplicates, and the conflict matrix is
left as-is.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.governance import GovernanceRole
from scripts.seed.common import load_yaml, make_engine, upsert


def transform(session: Session, raw: dict) -> dict:
    return {
        "key": raw["key"],
        "name": raw["name"],
        "description": raw.get("description"),
        "line_of_defence": int(raw["line_of_defence"]),
    }


def main(session: Session | None = None) -> None:
    entries = load_yaml("governance_roles.yaml")

    own = session is None
    if own:
        session = Session(make_engine())

    try:
        ins, upd = upsert(session, GovernanceRole, entries, ["key"], transform)
        if own:
            session.commit()
        print(f"  governance_roles: {ins} inserted, {upd} updated")
    finally:
        if own:
            session.close()


if __name__ == "__main__":
    main()
