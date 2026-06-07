"""platform_audit_event

Revision ID: 099104f68fc0
Revises: cef7211ddfe4
Create Date: 2026-06-07 09:35:35.361730
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '099104f68fc0'
down_revision: str | Sequence[str] | None = 'cef7211ddfe4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'platform_audit_event',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('actor_sub', sa.String(255), nullable=True),
        sa.Column('actor_email', sa.String(320), nullable=True),
        sa.Column('action', sa.String(120), nullable=False),
        sa.Column('target_type', sa.String(60), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('target_ref', sa.String(255), nullable=True),
        sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  server_default='{}'),
        sa.Column('source', sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_platform_audit_event_occurred_at',
                    'platform_audit_event', ['occurred_at'])
    op.create_index('ix_platform_audit_event_action',
                    'platform_audit_event', ['action'])
    op.create_index('ix_platform_audit_event_target_id',
                    'platform_audit_event', ['target_id'])

    # --- Immutability: revoke mutation rights, then add a trigger guard --------
    # irontrustai_provisioner and irontrustai_operator_provisioner are granted
    # INSERT below; explicitly revoke UPDATE/DELETE so the table can never be
    # mutated even if a future GRANT broadens their privileges.
    op.execute(
        "REVOKE UPDATE, DELETE ON platform_audit_event "
        "FROM irontrustai_provisioner, irontrustai_operator_provisioner"
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION platform_audit_no_mutate()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'platform_audit_event is append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER platform_audit_no_mutate
        BEFORE UPDATE OR DELETE ON platform_audit_event
        FOR EACH ROW EXECUTE FUNCTION platform_audit_no_mutate()
    """)

    # --- Grants ----------------------------------------------------------------
    # Write path: provisioner (tenant provision events) and operator_provisioner
    # (create-operator events). INSERT only — no UPDATE/DELETE per above.
    op.execute(
        "GRANT INSERT ON platform_audit_event "
        "TO irontrustai_provisioner, irontrustai_operator_provisioner"
    )
    # Read path: platform_ro for future audit-log endpoints.
    op.execute(
        "GRANT SELECT ON platform_audit_event TO irontrustai_platform_ro"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS platform_audit_no_mutate ON platform_audit_event")
    op.execute("DROP FUNCTION IF EXISTS platform_audit_no_mutate()")
    op.drop_index('ix_platform_audit_event_target_id',
                  table_name='platform_audit_event')
    op.drop_index('ix_platform_audit_event_action',
                  table_name='platform_audit_event')
    op.drop_index('ix_platform_audit_event_occurred_at',
                  table_name='platform_audit_event')
    op.drop_table('platform_audit_event')
