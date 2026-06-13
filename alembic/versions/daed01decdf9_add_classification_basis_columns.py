"""add_classification_basis_columns

Adds 'requires_context' to the eu_ai_act_tier Postgres enum and two
basis-stamping columns to the classification table.

Basis columns store the subcategory code and legal reference TEXT at
snapshot time — not a FK — so later reference-data edits cannot rewrite
history. Null when tier is REQUIRES_CONTEXT (no subcategory resolved).

ALTER TYPE ... ADD VALUE can run inside a transaction in PostgreSQL 9.1+;
the new value is available after commit. We do not use the new value within
this migration, so no isolation trick is needed.

Downgrade drops the two columns. The enum value cannot be removed without
a full type-swap (CREATE/ALTER/DROP/RENAME), which is out of scope for a
downgrade; 'requires_context' is left in the type (it is harmless if
unused and avoids unnecessary DDL churn during rollback).

Revision ID: daed01decdf9
Revises: 291d940c97ae
Create Date: 2026-06-13 15:22:14.130350
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'daed01decdf9'
down_revision: str | Sequence[str] | None = '291d940c97ae'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("ALTER TYPE eu_ai_act_tier ADD VALUE IF NOT EXISTS 'requires_context'")
    )
    op.add_column(
        'classification',
        sa.Column('basis_subcategory_code', sa.String(length=80), nullable=True),
    )
    op.add_column(
        'classification',
        sa.Column('basis_legal_ref', sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('classification', 'basis_legal_ref')
    op.drop_column('classification', 'basis_subcategory_code')
    # 'requires_context' is intentionally left in eu_ai_act_tier — see docstring.
