"""
Seed the AIIA + feeder section template (sprints/SPRINT_AIIA.md WI-2;
expanded for feeders in sprints/SPRINT_AIIA_FEEDERS.md WI-B1).
Thin loader on top of scripts.seed.common.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import AssessmentSectionTemplate
from app.models.base import AssessmentType, EUAIActTier, SectionApplicability
from scripts.seed.common import load_yaml, make_engine, run_seed


def transform_section_template(session: Session, raw: dict) -> dict:
    return {
        "type": AssessmentType(raw["type"]),
        "tier": EUAIActTier(raw["tier"]),
        "section_key": raw["section_key"],
        "title": raw["title"],
        "applicability": SectionApplicability(raw["applicability"]),
        "prompt": raw.get("prompt"),
        "iso_42005_clause": raw.get("iso_42005_clause"),
        "aiia_target_section_key": raw.get("aiia_target_section_key"),
        "sort_order": raw.get("sort_order", 0),
    }


def _validate_targets(session: Session) -> None:
    """Every non-null aiia_target_section_key must resolve to a real AIIA
    section_key at the SAME tier — an orphaned target surfaces nowhere
    (design doc §9.2) and is a seeding bug, not a soft warning. Fail loudly,
    same philosophy as the empty-template guard in create_aiia."""
    entries = load_yaml("aiia_section_template.yaml")
    # Only the tiers actually present in the seed data — PROHIBITED/
    # UNCLASSIFIED/REQUIRES_CONTEXT never have AIIA templates (they're
    # blocked at the classification gate before an AIIA can exist), and
    # querying REQUIRES_CONTEXT specifically hits a pre-existing casing
    # mismatch in the eu_ai_act_tier Postgres enum (added by an older
    # migration as 'requires_context' lowercase, unlike every other label).
    tiers_in_use = {EUAIActTier(raw["tier"]) for raw in entries}
    aiia_keys_by_tier: dict[EUAIActTier, set[str]] = {}
    for tier in tiers_in_use:
        aiia_keys_by_tier[tier] = set(session.scalars(
            select(AssessmentSectionTemplate.section_key).where(
                AssessmentSectionTemplate.type == AssessmentType.AIIA,
                AssessmentSectionTemplate.tier == tier,
            )
        ))

    orphans = []
    for raw in entries:
        target = raw.get("aiia_target_section_key")
        if target is None:
            continue
        tier = EUAIActTier(raw["tier"])
        if target not in aiia_keys_by_tier.get(tier, set()):
            orphans.append((raw["type"], raw["tier"], raw["section_key"], target))

    if orphans:
        raise RuntimeError(
            "aiia_section_template seed has orphaned aiia_target_section_key "
            f"values (no matching AIIA section at that tier): {orphans}"
        )


def main(session: Session | None = None) -> None:
    own = session is None
    if own:
        session = Session(make_engine())

    try:
        run_seed(
            label="aiia_section_template",
            filename="aiia_section_template.yaml",
            model=AssessmentSectionTemplate,
            key_fields=["type", "tier", "section_key"],
            transform=transform_section_template,
            session=session,
        )
        session.flush()
        _validate_targets(session)
        if own:
            session.commit()
    finally:
        if own:
            session.close()


if __name__ == "__main__":
    main()
