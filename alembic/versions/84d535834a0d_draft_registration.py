"""draft_registration — DM-S3 (D-66, INV-79)

Adds the draft_registration table: one active draft per (tenant, user),
tenant-isolated via RLS, both FKs CASCADE on parent delete.

Revision ID: 84d535834a0d
Revises: d82c389d1f07
Create Date: 2026-06-27
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = '84d535834a0d'
down_revision: str | Sequence[str] | None = 'd82c389d1f07'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'draft_registration',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('owner_user_id', sa.UUID(), nullable=False),
        sa.Column('draft_blob', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenant.id'], ondelete='CASCADE',
            name='fk_draft_reg_tenant',
        ),
        sa.ForeignKeyConstraint(
            ['owner_user_id'], ['app_user.id'], ondelete='CASCADE',
            name='fk_draft_reg_user',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'owner_user_id', name='uq_draft_one_per_user'),
    )
    op.create_index('ix_draft_registration_tenant_id', 'draft_registration', ['tenant_id'])
    op.create_index('ix_draft_registration_owner_user_id', 'draft_registration', ['owner_user_id'])

    op.execute("ALTER TABLE draft_registration ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON draft_registration
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # Trigger: keep updated_at current on every row update
    op.execute("""
        CREATE OR REPLACE FUNCTION set_draft_registration_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER draft_registration_updated_at
        BEFORE UPDATE ON draft_registration
        FOR EACH ROW EXECUTE FUNCTION set_draft_registration_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS draft_registration_updated_at ON draft_registration")
    op.execute("DROP FUNCTION IF EXISTS set_draft_registration_updated_at")
    op.drop_index('ix_draft_registration_owner_user_id', table_name='draft_registration')
    op.drop_index('ix_draft_registration_tenant_id', table_name='draft_registration')
    op.drop_table('draft_registration')
