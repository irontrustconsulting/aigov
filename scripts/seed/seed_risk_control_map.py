"""
Seed the Risk<->Control cross-map (PRD 4.7: a risk links to its mitigating
controls). Depends on risks AND controls already being loaded.

YAML references the human-readable codes, not UUIDs:

    - risk_code: LLM01
      control_code: AC-01
      strength: partial

The transform resolves each code to its row id at load time, erroring clearly
if a referenced code is missing (catches typos / missing dependencies).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Control, Risk, RiskControlMap
from scripts.seed.common import run_seed


def _resolve_id(session: Session, model: type, code: str, kind: str):
    row = session.scalar(select(model).where(model.code == code))
    if row is None:
        raise RuntimeError(
            f"{kind} with code '{code}' not found — seed {kind}s before cross-maps"
        )
    return row.id


def transform_map(session: Session, raw: dict) -> dict:
    return {
        "risk_id": _resolve_id(session, Risk, raw["risk_code"], "risk"),
        "control_id": _resolve_id(session, Control, raw["control_code"], "control"),
        "strength": raw.get("strength"),
    }


def main(session: Session | None = None) -> None:
    run_seed(
        label="risk_control_map",
        filename="risk_control_map.yaml",
        model=RiskControlMap,
        key_fields=["risk_id", "control_id"],   # composite natural key
        transform=transform_map,
        session=session,
    )


if __name__ == "__main__":
    main()