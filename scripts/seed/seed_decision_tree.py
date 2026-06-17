"""
Version-aware seed loader for the EU AI Act classification decision tree.

Idempotency rules:
  - version absent in DB      → insert all rows, commit.
  - version present, same hash → no-op (already loaded, content unchanged).
  - version present, diff hash → FAIL LOUD. A frozen version cannot be mutated;
                                  bump the version in the YAML instead.

The hash covers the canonical JSON representation of the questions and their
options (sorted by question code), so whitespace and YAML reformatting
don't cause false positives.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import EUAIActTier
from app.models.decision_tree import (
    DecisionTree,
    DecisionTreeOption,
    DecisionTreeQuestion,
)
from scripts.seed.common import make_engine

_RUNG_MAP: dict[str, EUAIActTier] = {
    "PROHIBITED": EUAIActTier.PROHIBITED,
    "HIGH": EUAIActTier.HIGH,
    "LIMITED": EUAIActTier.LIMITED,
    "MINIMAL": EUAIActTier.MINIMAL,
}


def _load_yaml_mapping(filename: str) -> dict:
    """Load a YAML file that is a mapping (not the list expected by load_yaml)."""
    from scripts.seed.common import SEED_DIR
    path = SEED_DIR / filename
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{filename} must be a YAML mapping")
    return data


def _compute_hash(raw_questions: list[dict]) -> str:
    """SHA-256 of the canonical JSON for all questions + options."""
    canonical = sorted(
        [
            {
                "code": q["code"],
                "text": q["text"],
                "probes_rung": q.get("probes_rung"),
                "legal_ref": q.get("legal_ref"),
                "order": q.get("order", 0),
                "options": sorted(
                    [
                        {
                            "code": o["code"],
                            "label": o["label"],
                            "asserts_rung": o.get("asserts_rung"),
                            "asserts_subcategory_code": (
                                o.get("asserts_subcategory_code")
                            ),
                        }
                        for o in q.get("options", [])
                    ],
                    key=lambda o: o["code"],
                ),
            }
            for q in raw_questions
        ],
        key=lambda q: q["code"],
    )
    blob = json.dumps(canonical, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def _load_tree(session: Session, data: dict) -> None:
    version: str = str(data["version"])
    raw_questions: list[dict] = data.get("questions", [])
    content_hash = _compute_hash(raw_questions)

    existing = session.scalar(
        select(DecisionTree).where(DecisionTree.version == version)
    )

    if existing is not None:
        if existing.content_hash == content_hash:
            print(f"  decision_tree v{version}: unchanged — skipping")
            return
        raise RuntimeError(
            f"Decision tree version '{version}' already exists in the DB with a "
            f"different content hash. Frozen versions cannot be mutated. "
            f"Bump the version field in the YAML to introduce changes."
        )

    tree = DecisionTree(
        id=uuid.uuid4(),
        version=version,
        name=data.get("name", f"Decision Tree v{version}"),
        content_hash=content_hash,
    )
    session.add(tree)
    session.flush()

    for q_raw in raw_questions:
        probes_rung_str: str | None = q_raw.get("probes_rung")
        probes_rung = _RUNG_MAP.get(probes_rung_str) if probes_rung_str else None

        question = DecisionTreeQuestion(
            id=uuid.uuid4(),
            tree_id=tree.id,
            question_code=q_raw["code"],
            text=q_raw["text"].strip(),
            probes_rung=probes_rung,
            legal_ref=q_raw.get("legal_ref"),
            sort_order=q_raw.get("order", 0),
        )
        session.add(question)
        session.flush()

        for o_raw in q_raw.get("options", []):
            asserts_rung_str: str | None = o_raw.get("asserts_rung")
            asserts_rung = _RUNG_MAP.get(asserts_rung_str) if asserts_rung_str else None
            option = DecisionTreeOption(
                id=uuid.uuid4(),
                question_id=question.id,
                option_code=o_raw["code"],
                label=o_raw["label"],
                asserts_rung=asserts_rung,
                asserts_subcategory_code=o_raw.get("asserts_subcategory_code") or None,
            )
            session.add(option)

    q_count = len(raw_questions)
    o_count = sum(len(q.get("options", [])) for q in raw_questions)
    print(
        f"  decision_tree v{version}: inserted {q_count} questions, {o_count} options"
    )


def main(session: Session | None = None) -> None:
    data = _load_yaml_mapping("decision_tree.yaml")

    own = session is None
    if own:
        session = Session(make_engine())

    try:
        _load_tree(session, data)
        if own:
            session.commit()
    finally:
        if own:
            session.close()


if __name__ == "__main__":
    main()
