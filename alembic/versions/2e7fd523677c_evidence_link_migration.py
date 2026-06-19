"""evidence_link_migration

Revision ID: 2e7fd523677c
Revises: 256ff244cc13
Create Date: 2026-06-19 08:49:01.657014

Phase B of sprints/SPRINT_EVIDENCE_REPOSITORY.md (WI-6): adds
UNIQUE(item_id, evidence_id) to assessment_item_evidence (the constraint the
disposition-gated link endpoint relies on for its duplicate -> 409), and
drops the now-redundant single-column index on item_id -- the new unique
constraint's composite index already serves item_id as its leftmost prefix.
ix_assessment_item_evidence_evidence_id is untouched: it backs the WI-4
pristine-delete guard's NOT EXISTS and the WI-3 link_count subquery, neither
of which the item_id-leading composite can serve.

Hand-edited: autogenerate also picked up unrelated pre-existing drift on
other tables (affected_party, data_category, decision_tree, eu_operator_role,
hosting_model, human_oversight_type, usage_context) -- not part of this
sprint, left untouched here per CLAUDE.md's "always hand-edit the generated
revision" convention.
"""
from collections.abc import Sequence

from alembic import op

revision: str = '2e7fd523677c'
down_revision: str | Sequence[str] | None = '256ff244cc13'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        op.f('ix_assessment_item_evidence_item_id'),
        table_name='assessment_item_evidence',
    )
    op.create_unique_constraint(
        'uq_assessment_item_evidence',
        'assessment_item_evidence',
        ['item_id', 'evidence_id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_assessment_item_evidence', 'assessment_item_evidence', type_='unique',
    )
    op.create_index(
        op.f('ix_assessment_item_evidence_item_id'),
        'assessment_item_evidence',
        ['item_id'],
        unique=False,
    )
