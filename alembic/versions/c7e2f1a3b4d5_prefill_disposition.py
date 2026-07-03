"""prefill_disposition — CAT-4 extension (D-74, D-75, INV-83)

Adds the prefill_disposition table: one row per (system, field_key) recording
the server-derived ProvenanceConfidence for every intake prefill and catalogue
fact disposed at registration or subsequently amended via PATCH /systems.

Revision ID: c7e2f1a3b4d5
Revises: d5c81f9fd50d
Create Date: 2026-07-02
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c7e2f1a3b4d5"
down_revision: str | Sequence[str] | None = "d5c81f9fd50d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prefill_disposition",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("system_id", sa.UUID(), nullable=False),
        sa.Column("field_key", sa.String(120), nullable=False),
        sa.Column(
            "provenance",
            postgresql.ENUM(name="provenance_confidence", create_type=False),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], ondelete="CASCADE",
            name="fk_prefill_disposition_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["system_id"], ["system.id"], ondelete="CASCADE",
            name="fk_prefill_disposition_system",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("system_id", "field_key", name="uq_prefill_disposition_system_field"),
    )
    op.create_index("ix_prefill_disposition_tenant_id", "prefill_disposition", ["tenant_id"])
    op.create_index("ix_prefill_disposition_system_id", "prefill_disposition", ["system_id"])

    op.execute("ALTER TABLE prefill_disposition ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON prefill_disposition
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON prefill_disposition")
    op.execute("ALTER TABLE prefill_disposition DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_prefill_disposition_system_id", table_name="prefill_disposition")
    op.drop_index("ix_prefill_disposition_tenant_id", table_name="prefill_disposition")
    op.drop_table("prefill_disposition")
