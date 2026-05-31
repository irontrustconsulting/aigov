"""
Seed the Risk library (OWASP LLM + NIST/ISO governance layer).
Thin loader on top of scripts.seed.common.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Risk
from app.models.base import RiskLayer, RiskSource
from scripts.seed.common import run_seed


def transform_risk(session: Session, raw: dict) -> dict:
    return {
        "code": raw["code"],
        "title": raw["title"],
        "description": raw.get("description"),
        "layer": RiskLayer(raw["layer"]),
        "source": RiskSource(raw["source"]),
        "source_ref": raw.get("source_ref"),
        "reference_url": raw.get("reference_url"),
    }


def main(session: Session | None = None) -> None:
    run_seed(
        label="risks",
        filename="risks.yaml",
        model=Risk,
        key_fields=["code"],
        transform=transform_risk,
        session=session,
    )


if __name__ == "__main__":
    main()