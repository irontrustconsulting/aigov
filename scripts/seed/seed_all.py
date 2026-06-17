"""
Seed everything, in dependency order, in a single transaction.

Dependency order:
  Independent reference tables first:
    1. risks
    2. controls            (writes control_framework_map too)
    3. eu_ai_act           (categories + subcategories carrying tiers)
    4. product_category    (hierarchical, user-facing)
    5. catalogue           (vendors -> products -> facts; needs risks)
  Then the cross-references (need the above to exist):
    6. risk_control_map                 (needs risks + controls)
    7. product_category_membership      (needs catalogue + product_category)
    8. product_category_eu_mapping      (needs eu_ai_act + product_category)

Run from the project root (venv active):
    python -m scripts.seed.seed_all

One transaction for the whole run: any failure rolls back everything, so you
are never left half-seeded.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from scripts.seed import (
    seed_aiia_section_template,
    seed_catalogue,
    seed_controls,
    seed_decision_tree,
    seed_eu_ai_act,
    seed_governance_roles,
    seed_product_category,
    seed_product_category_eu_mapping,
    seed_product_category_membership,
    seed_risk_control_map,
    seed_risks,
)
from scripts.seed.common import make_engine


def main() -> None:
    engine = make_engine()
    with Session(engine) as session:
        print("Seeding (single transaction):")
        # independent reference data
        seed_risks.main(session)
        seed_controls.main(session)
        seed_eu_ai_act.main(session)
        seed_product_category.main(session)
        seed_catalogue.main(session)
        # cross-references
        seed_risk_control_map.main(session)
        seed_product_category_membership.main(session)
        seed_product_category_eu_mapping.main(session)
        # platform reference: governance role catalogue
        seed_governance_roles.main(session)
        # classification gate: EU AI Act decision tree (version-aware)
        seed_decision_tree.main(session)
        # AIIA core: tier-scoped section template (AIIA + feeders)
        seed_aiia_section_template.main(session)
        session.commit()
        print("Done.")


if __name__ == "__main__":
    main()