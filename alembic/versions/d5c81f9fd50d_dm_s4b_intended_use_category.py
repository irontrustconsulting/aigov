"""dm_s4b_intended_use_category

DM-S4b: structured intended-use category per use case.

Changes:
  use_case:       + product_category_id uuid NULL FK(product_category, ON DELETE SET NULL)
  classification: + off_label boolean NOT NULL DEFAULT false
  use_case:       - purpose (destructive; replaced by structured category, R-5)

Revision ID: d5c81f9fd50d
Revises: ff6654ebd569
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa

revision = "d5c81f9fd50d"
down_revision = "cce02cda26a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # use_case: add product_category_id
    op.add_column(
        "use_case",
        sa.Column(
            "product_category_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_category.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_use_case_product_category_id",
        "use_case",
        ["product_category_id"],
    )

    # classification: add off_label, backfill existing rows to false
    op.add_column(
        "classification",
        sa.Column(
            "off_label",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # use_case: drop purpose (irreversible; data loss acceptable per §0.3)
    op.drop_column("use_case", "purpose")


def downgrade() -> None:
    # Restore purpose as nullable (data is gone — downgrade only unblocks schema)
    op.add_column(
        "use_case",
        sa.Column("purpose", sa.Text(), nullable=True),
    )
    op.drop_column("classification", "off_label")
    op.drop_index("ix_use_case_product_category_id", table_name="use_case")
    op.drop_column("use_case", "product_category_id")
