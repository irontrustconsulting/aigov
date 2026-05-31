"""
Seed everything, in dependency order, in a single transaction.

Order matters:
  1. risks          (independent)
  2. controls       (independent; writes control_framework_map too)
  3. risk_control_map  (needs risks + controls)
  4. catalogue      (needs risks for product-risk links)

Run from the project root (venv active):
    python -m scripts.seed.seed_all

One transaction for the whole run: if any seed fails, nothing commits, so you
never end up half-seeded. Each sub-loader is also runnable on its own.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from scripts.seed.common import make_engine
from scripts.seed import (
    seed_risks, seed_controls, seed_risk_control_map, seed_catalogue,
)


def main() -> None:
    engine = make_engine()
    with Session(engine) as session:
        print("Seeding (single transaction):")
        seed_risks.main(session)
        seed_controls.main(session)
        seed_risk_control_map.main(session)
        seed_catalogue.main(session)
        session.commit()
        print("Done.")


if __name__ == "__main__":
    main()