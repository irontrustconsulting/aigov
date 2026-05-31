"""
Seed the Control library, with each control's framework mappings nested
inline (PRD 4.6: one control can satisfy several frameworks).

A control entry in controls.yaml looks like:

    - code: AC-01
      title: Access Control Policy
      description: >
        ...
      frameworks:
        - framework: iso_42001
          clause_ref: "A.6.2.1"
          notes: optional
        - framework: eu_ai_act
          clause_ref: "Art. 9"

We upsert the `control` row via the shared machinery, then reconcile its
`control_framework_map` rows (delete-and-recreate the mappings for that
control, so the YAML stays the source of truth and re-runs are idempotent).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Control, ControlFrameworkMap
from app.models.base import Framework
from scripts.seed.common import load_yaml, make_engine, upsert


def transform_control(session: Session, raw: dict) -> dict:
    """Raw YAML -> kwargs for the Control row (frameworks handled separately)."""
    return {
        "code": raw["code"],
        "title": raw["title"],
        "description": raw.get("description"),
    }


def reconcile_frameworks(session: Session, raw: dict) -> None:
    """Make the control's framework mappings match the YAML exactly.

    Strategy: delete existing maps for this control, then insert the ones in
    the YAML. Simple and idempotent for reference data (the YAML is truth)."""
    control = session.scalar(select(Control).where(Control.code == raw["code"]))
    if control is None:
        raise RuntimeError(f"control {raw['code']} not found after upsert")

    # Clear existing mappings for this control.
    for existing in list(control.framework_maps):
        session.delete(existing)
    session.flush()  # apply deletes before re-inserting to avoid uq clashes

    for fm in raw.get("frameworks", []):
        session.add(
            ControlFrameworkMap(
                control_id=control.id,
                framework=Framework(fm["framework"]),
                clause_ref=fm["clause_ref"],
                notes=fm.get("notes"),
            )
        )


def main(session: Session | None = None) -> None:
    entries = load_yaml("controls.yaml")

    own = session is None
    if own:
        session = Session(make_engine())

    try:
        ins, upd = upsert(session, Control, entries, ["code"], transform_control)
        session.flush()  # ensure controls exist before mapping
        for raw in entries:
            reconcile_frameworks(session, raw)
        if own:
            session.commit()
        print(f"  controls: {ins} inserted, {upd} updated ({len(entries)} in file)")
    finally:
        if own:
            session.close()


if __name__ == "__main__":
    main()