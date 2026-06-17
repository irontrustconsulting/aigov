"""feeder_type_unique_constraint

Revision ID: 256ff244cc13
Revises: 18cdd5bd715c
Create Date: 2026-06-17 23:35:27.195084

AIIA Feeders sprint (Phase B), addendum §14 point 5: UNIQUE(parent_aiia_id,
type) so at most one feeder of each type (FRIA/DPIA/MODEL_RISK) exists per
AIIA. parent_aiia_id is NULL on every AIIA row itself, and NULLs are never
equal to each other under a unique constraint, so this only ever constrains
feeders, never AIIA rows. Plain (non-partial) constraint — autogenerate
handles it correctly. Unrelated drift detected by autogenerate (stray index
toggles on eu_operator_role/hosting_model/usage_context/data_category/
affected_party/decision_tree, pre-existing before this sprint) intentionally
excluded — out of scope here, same as the Phase A migration.
"""
from collections.abc import Sequence

from alembic import op

revision: str = '256ff244cc13'
down_revision: str | Sequence[str] | None = '18cdd5bd715c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_feeder_type_per_aiia', 'assessment', ['parent_aiia_id', 'type'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_feeder_type_per_aiia', 'assessment', type_='unique')
