"""deployment_authorisation

Revision ID: 98279f35e917
Revises: 4a01a0b5bd5f
Create Date: 2026-06-20 18:20:01.384478

Sprint 6b (sprints/SPRINT_AUTHORIZATION.md WI-1, design doc §3.3):
`DeploymentAuthorisation` (ATO) table. Hand-edited per CLAUDE §4: RLS
policy (autogenerate never emits this). No explicit GRANT needed —
irontrustai_app already holds blanket ALTER DEFAULT PRIVILEGES for new
tables (alembic/sql/00_roles.sh), confirmed by the same pattern in 6a's
4a01a0b5bd5f migration.

Unrelated drift detected by autogenerate (stray index/constraint toggles on
affected_party/data_category/decision_tree/eu_operator_role/hosting_model/
human_oversight_type/usage_context, pre-existing before this sprint)
intentionally excluded — same convention as 256ff244cc13 / 4a01a0b5bd5f.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '98279f35e917'
down_revision: str | Sequence[str] | None = '4a01a0b5bd5f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'deployment_authorisation',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('use_case_id', sa.UUID(), nullable=False),
        sa.Column('assessment_id', sa.UUID(), nullable=False),
        sa.Column('submission_round', sa.Integer(), nullable=False),
        sa.Column('tier', sa.String(length=40), nullable=False),
        sa.Column('assessment_version', sa.Integer(), nullable=False),
        sa.Column('authorised_by_user_id', sa.UUID(), nullable=False),
        sa.Column('authorised_by_name', sa.String(length=255), nullable=True),
        sa.Column('authorised_by_email', sa.String(length=320), nullable=True),
        sa.Column(
            'authorised_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.Column('residual_risk_statement', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ['assessment_id'], ['assessment.id'], ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['authorised_by_user_id'], ['app_user.id'], ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['use_case_id'], ['use_case.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_deployment_authorisation_assessment_id'),
        'deployment_authorisation', ['assessment_id'], unique=False,
    )
    op.create_index(
        op.f('ix_deployment_authorisation_tenant_id'),
        'deployment_authorisation', ['tenant_id'], unique=False,
    )
    op.create_index(
        op.f('ix_deployment_authorisation_use_case_id'),
        'deployment_authorisation', ['use_case_id'], unique=False,
    )
    op.execute("ALTER TABLE deployment_authorisation ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON deployment_authorisation
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON deployment_authorisation")
    op.execute("ALTER TABLE deployment_authorisation DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        op.f('ix_deployment_authorisation_use_case_id'),
        table_name='deployment_authorisation',
    )
    op.drop_index(
        op.f('ix_deployment_authorisation_tenant_id'),
        table_name='deployment_authorisation',
    )
    op.drop_index(
        op.f('ix_deployment_authorisation_assessment_id'),
        table_name='deployment_authorisation',
    )
    op.drop_table('deployment_authorisation')
