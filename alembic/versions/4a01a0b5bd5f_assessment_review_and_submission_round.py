"""assessment_review_and_submission_round

Revision ID: 4a01a0b5bd5f
Revises: 3a5b36bdd37a
Create Date: 2026-06-20 17:07:47.694675

Sprint 6a (sprints/SPRINT_AUTHORIZATION_6A.md WI-1, design doc §3.1/§3.2):
`AssessmentReview` table + `Assessment.submitted_by_user_id/submitted_at/
submission_round`. Hand-edited per CLAUDE §4: RLS policy on
`assessment_review` (autogenerate never emits this) + the mandatory-note
CHECK. No explicit GRANT needed — irontrustai_app already holds blanket
ALTER DEFAULT PRIVILEGES for new tables (alembic/sql/00_roles.sh).
`review_decision` enum labels come out uppercase from autogenerate (no
hand-typed DDL), so this doesn't repeat the 3a5b36bdd37a case bug.
`submission_round` gets a server_default so it backfills existing rows.

Unrelated drift detected by autogenerate (stray index/constraint toggles on
affected_party/data_category/decision_tree/eu_operator_role/hosting_model/
human_oversight_type/usage_context, pre-existing before this sprint)
intentionally excluded — same convention as 256ff244cc13.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = '4a01a0b5bd5f'
down_revision: str | Sequence[str] | None = '3a5b36bdd37a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'assessment_review',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('assessment_id', sa.UUID(), nullable=False),
        sa.Column('reviewer_user_id', sa.UUID(), nullable=False),
        sa.Column(
            'decision',
            sa.Enum('APPROVED', 'CHANGES_REQUESTED', name='review_decision'),
            nullable=False,
        ),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('submission_round', sa.Integer(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['assessment_id'], ['assessment.id'], ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['reviewer_user_id'], ['app_user.id'], ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_assessment_review_assessment_id'), 'assessment_review',
        ['assessment_id'], unique=False,
    )
    op.create_index(
        op.f('ix_assessment_review_tenant_id'), 'assessment_review',
        ['tenant_id'], unique=False,
    )
    op.create_check_constraint(
        'ck_assessment_review_note_required',
        'assessment_review',
        "decision <> 'CHANGES_REQUESTED' OR note IS NOT NULL",
    )
    op.execute("ALTER TABLE assessment_review ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON assessment_review
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    op.add_column(
        'assessment', sa.Column('submitted_by_user_id', sa.UUID(), nullable=True),
    )
    op.add_column(
        'assessment',
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'assessment',
        sa.Column('submission_round', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_foreign_key(
        None, 'assessment', 'app_user', ['submitted_by_user_id'], ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint(None, 'assessment', type_='foreignkey')
    op.drop_column('assessment', 'submission_round')
    op.drop_column('assessment', 'submitted_at')
    op.drop_column('assessment', 'submitted_by_user_id')

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON assessment_review")
    op.execute("ALTER TABLE assessment_review DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        op.f('ix_assessment_review_tenant_id'), table_name='assessment_review',
    )
    op.drop_index(
        op.f('ix_assessment_review_assessment_id'), table_name='assessment_review',
    )
    op.drop_table('assessment_review')
    op.execute("DROP TYPE IF EXISTS review_decision")
