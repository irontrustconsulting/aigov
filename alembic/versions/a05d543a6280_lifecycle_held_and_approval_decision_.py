"""lifecycle_held_and_approval_decision_columns

Revision ID: a05d543a6280
Revises: 2e7fd523677c
Create Date: 2026-06-19 22:47:37.468077

Phase A of sprints/SPRINT_LIFECYCLE.md (WI-1): M1 (use_case.held_from_state,
held_reason) + M3 (vendor_approval/product_approval decision metadata —
verified absent against live DDL, STATE_MACHINE.md §15). LifecycleTransition
already carries every column the handoff's §0 checklist asks for, so it is
untouched here. All four touched tables already have a tenant_isolation RLS
policy from the initial migration (alter-table-add-column needs none of its
own).

Hand-edited: autogenerate also picked up unrelated pre-existing drift on
other tables (affected_party, data_category, decision_tree, eu_operator_role,
hosting_model, human_oversight_type, usage_context) -- not part of this
sprint, left untouched here per CLAUDE.md's "always hand-edit the generated
revision" convention.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a05d543a6280'
down_revision: str | Sequence[str] | None = '2e7fd523677c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('product_approval', sa.Column('decided_by_user_id', sa.UUID(), nullable=True))
    op.add_column('product_approval', sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('product_approval', sa.Column('note', sa.Text(), nullable=True))
    op.create_foreign_key(None, 'product_approval', 'app_user', ['decided_by_user_id'], ['id'], ondelete='SET NULL')
    op.add_column('use_case', sa.Column('held_from_state', sa.Enum('REQUESTED', 'VENDOR_CHECK', 'PRODUCT_CHECK', 'INTAKE', 'HALTED_PROHIBITED', 'UNDER_ASSESSMENT', 'TREATMENT_PENDING', 'PENDING_AUTHORISATION', 'AUTHORISED', 'DEPLOYED', 'HELD', 'RETIRED', name='lifecycle_state'), nullable=True))
    op.add_column('use_case', sa.Column('held_reason', sa.Text(), nullable=True))
    op.add_column('vendor_approval', sa.Column('decided_by_user_id', sa.UUID(), nullable=True))
    op.add_column('vendor_approval', sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('vendor_approval', sa.Column('note', sa.Text(), nullable=True))
    op.create_foreign_key(None, 'vendor_approval', 'app_user', ['decided_by_user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('vendor_approval_decided_by_user_id_fkey', 'vendor_approval', type_='foreignkey')
    op.drop_column('vendor_approval', 'note')
    op.drop_column('vendor_approval', 'decided_at')
    op.drop_column('vendor_approval', 'decided_by_user_id')
    op.drop_column('use_case', 'held_reason')
    op.drop_column('use_case', 'held_from_state')
    op.drop_constraint('product_approval_decided_by_user_id_fkey', 'product_approval', type_='foreignkey')
    op.drop_column('product_approval', 'note')
    op.drop_column('product_approval', 'decided_at')
    op.drop_column('product_approval', 'decided_by_user_id')
