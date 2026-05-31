"""
Shared seeding machinery.

All seed loaders follow the same shape:
  read YAML  ->  transform each entry into model kwargs  ->  upsert by a
  natural key  ->  commit once.

The bits that VARY per seed (the model, the natural key, how a raw YAML dict
becomes model fields, any reference resolution) are passed in. The bit that is
the SAME (find-or-create, update-in-place, idempotency, batch commit) lives
here, once.

Connects as the ADMIN role: seeding global reference data is administrative,
and these tables are not tenant-scoped (no RLS involved).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings

# Where the YAML data files live (this directory).
def _find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists():
            return p
    raise RuntimeError("project root (pyproject.toml) not found")

PROJECT_ROOT = _find_root(Path(__file__).resolve())
SEED_DIR = PROJECT_ROOT / "data" / "seed"
# SEED_DIR = Path(__file__).parent


def load_yaml(filename: str) -> list[dict]:
    """Read a seed YAML file (a list of entries) into plain dicts."""
    path = SEED_DIR / filename
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        raise ValueError(f"{filename} must be a YAML list of entries")
    return data


def make_engine():
    """One admin engine for seeding. Caller owns the Session lifecycle."""
    return create_engine(settings.migration_database_url)


def upsert(
    session: Session,
    model: type,
    entries: Sequence[dict],
    key_fields: Sequence[str],
    transform: Callable[[Session, dict], dict],
) -> tuple[int, int]:
    """Insert-or-update each entry, keyed on `key_fields` (the natural key).

    Parameters
    ----------
    model        : the ORM class (e.g. Risk, Control).
    entries      : raw dicts from YAML.
    key_fields   : column names forming the natural key (e.g. ["code"], or
                   ["risk_id", "control_id"] for a join table). The lookup
                   matches on the TRANSFORMED values of these fields.
    transform    : turns a raw YAML dict into model kwargs. Receives the
                   session so it can resolve references (look up FKs by code).
                   Must return a dict whose keys include key_fields.

    Returns (inserted_count, updated_count). Idempotent: re-running converges
    to the YAML's described state without duplicating.
    """
    inserted = updated = 0
    for raw in entries:
        kwargs = transform(session, raw)

        # Build the lookup filter from the natural key.
        conditions = [getattr(model, k) == kwargs[k] for k in key_fields]
        existing = session.scalar(select(model).where(*conditions))

        if existing is None:
            session.add(model(**kwargs))
            inserted += 1
        else:
            for field, value in kwargs.items():
                setattr(existing, field, value)
            updated += 1

    return inserted, updated


def run_seed(
    label: str,
    filename: str,
    model: type,
    key_fields: Sequence[str],
    transform: Callable[[Session, dict], dict],
    session: Session | None = None,
) -> None:
    """Convenience wrapper: load a file and upsert it, printing a summary.

    If `session` is provided, uses it and does NOT commit (the caller — e.g.
    the orchestrator — owns the transaction). If not, creates its own session
    and commits.
    """
    entries = load_yaml(filename)

    own_session = session is None
    if own_session:
        engine = make_engine()
        session = Session(engine)

    try:
        inserted, updated = upsert(session, model, entries, key_fields, transform)
        if own_session:
            session.commit()
        print(f"  {label}: {inserted} inserted, {updated} updated "
              f"({len(entries)} in file)")
    finally:
        if own_session:
            session.close()