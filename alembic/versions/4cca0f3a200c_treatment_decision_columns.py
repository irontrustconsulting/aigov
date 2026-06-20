"""treatment_decision_columns

Revision ID: 4cca0f3a200c
Revises: a05d543a6280
Create Date: 2026-06-20 10:40:11.445477

Phase B of sprints/SPRINT_LIFECYCLE.md (WI-9): M2 — new enum type
treatment_decision (MITIGATE, ACCEPT; TRANSFER/AVOID reserved per the
Framework reserve-now pattern) + nullable treatment_decision/
treatment_rationale columns on assessment_item. Stored by-name, same
convention as lifecycle_state (STATE.md inv 23). assessment_item already
carries RLS from the initial migration — no RLS/grant edit needed.

Hand-edited: autogenerate also picked up unrelated pre-existing drift on
other tables (affected_party, data_category, decision_tree, eu_operator_role,
hosting_model, human_oversight_type, usage_context) -- not part of this
sprint, left untouched here per CLAUDE.md's "always hand-edit the generated
revision" convention.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4cca0f3a200c"
down_revision: str | Sequence[str] | None = "a05d543a6280"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_treatment_decision_enum = sa.Enum(
    "MITIGATE",
    "ACCEPT",
    "TRANSFER",
    "AVOID",
    name="treatment_decision",
)


def upgrade() -> None:
    # Unlike lifecycle_state (created inline by the initial migration's
    # create_table), this is a brand-new type added via op.add_column —
    # sa.Enum only auto-creates the Postgres type when bound to
    # create_table, so it must be created explicitly first (same pattern as
    # system_lifecycle_stage in 05ff13cdcdc3). Labels are the uppercase
    # member NAMES, matching every other by-name enum in this schema
    # (STATE.md inv 23) — never the lowercase .value.
    _treatment_decision_enum.create(op.get_bind())
    op.add_column(
        "assessment_item",
        sa.Column("treatment_decision", _treatment_decision_enum, nullable=True),
    )
    op.add_column(
        "assessment_item", sa.Column("treatment_rationale", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("assessment_item", "treatment_rationale")
    op.drop_column("assessment_item", "treatment_decision")
    _treatment_decision_enum.drop(op.get_bind())
