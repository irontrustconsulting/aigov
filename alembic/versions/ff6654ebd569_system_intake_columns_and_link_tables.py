"""system_intake_columns_and_link_tables

Extends the system table with structured intake metadata columns and adds two
link tables for multi-select vocabulary associations.

Changes:
- system: 6 new columns (4 vocab FKs, lifecycle_stage enum, is_custom bool)
- system: check constraint enforcing catalogue-or-custom invariant
- system_data_category: link table (system ↔ data_category)
- system_affected_party: link table (system ↔ affected_party)

Link tables follow the AssessmentItemControl convention — no tenant_id, no RLS.
Cross-tenant isolation is satisfied via the parent system table's existing RLS.

Existing system rows are back-filled: is_custom=false, all new FKs NULL.

Revision ID: ff6654ebd569
Revises: 05ff13cdcdc3
Create Date: 2026-06-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = 'ff6654ebd569'
down_revision: str | Sequence[str] | None = '05ff13cdcdc3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. New columns on system
    #    server_default on is_custom back-fills existing rows to false.
    # ------------------------------------------------------------------
    op.add_column('system', sa.Column(
        'operator_role_id', sa.UUID(), nullable=True,
    ))
    op.add_column('system', sa.Column(
        'hosting_model_id', sa.UUID(), nullable=True,
    ))
    op.add_column('system', sa.Column(
        'usage_context_id', sa.UUID(), nullable=True,
    ))
    op.add_column('system', sa.Column(
        'human_oversight_type_id', sa.UUID(), nullable=True,
    ))
    op.add_column('system', sa.Column(
        'lifecycle_stage',
        postgresql.ENUM(name='system_lifecycle_stage', create_type=False),
        nullable=True,
    ))
    op.add_column('system', sa.Column(
        'is_custom', sa.Boolean(), nullable=False, server_default='false',
    ))

    # ------------------------------------------------------------------
    # 2. FK constraints for the four vocab columns
    # ------------------------------------------------------------------
    op.create_foreign_key(
        'fk_system_eu_operator_role', 'system', 'eu_operator_role',
        ['operator_role_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_system_hosting_model', 'system', 'hosting_model',
        ['hosting_model_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_system_usage_context', 'system', 'usage_context',
        ['usage_context_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_system_human_oversight_type', 'system', 'human_oversight_type',
        ['human_oversight_type_id'], ['id'], ondelete='SET NULL',
    )

    # Indexes for the new FK columns
    op.create_index(op.f('ix_system_operator_role_id'), 'system', ['operator_role_id'])
    op.create_index(op.f('ix_system_hosting_model_id'), 'system', ['hosting_model_id'])
    op.create_index(op.f('ix_system_usage_context_id'), 'system', ['usage_context_id'])
    op.create_index(op.f('ix_system_human_oversight_type_id'), 'system', ['human_oversight_type_id'])

    # ------------------------------------------------------------------
    # 3. Check constraint: is_custom=true must not carry catalogue FKs
    # ------------------------------------------------------------------
    op.create_check_constraint(
        'ck_system_custom_no_catalogue',
        'system',
        'NOT (is_custom = true AND '
        '(catalogue_product_id IS NOT NULL OR catalogue_vendor_id IS NOT NULL))',
    )

    # ------------------------------------------------------------------
    # 4. system_data_category link table
    #    No tenant_id / no RLS — follows AssessmentItemControl convention.
    #    Cross-tenant isolation provided by parent system table's RLS.
    # ------------------------------------------------------------------
    op.create_table(
        'system_data_category',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('system_id', sa.UUID(), nullable=False),
        sa.Column('data_category_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['system_id'], ['system.id'], ondelete='CASCADE',
                                name='fk_system_data_category_system'),
        sa.ForeignKeyConstraint(['data_category_id'], ['data_category.id'], ondelete='CASCADE',
                                name='fk_system_data_category_data_category'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('system_id', 'data_category_id', name='uq_system_data_category'),
    )
    op.create_index(op.f('ix_system_data_category_system_id'), 'system_data_category', ['system_id'])
    op.create_index(op.f('ix_system_data_category_data_category_id'), 'system_data_category', ['data_category_id'])

    # ------------------------------------------------------------------
    # 5. system_affected_party link table (same convention)
    # ------------------------------------------------------------------
    op.create_table(
        'system_affected_party',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('system_id', sa.UUID(), nullable=False),
        sa.Column('affected_party_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['system_id'], ['system.id'], ondelete='CASCADE',
                                name='fk_system_affected_party_system'),
        sa.ForeignKeyConstraint(['affected_party_id'], ['affected_party.id'], ondelete='CASCADE',
                                name='fk_system_affected_party_affected_party'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('system_id', 'affected_party_id', name='uq_system_affected_party'),
    )
    op.create_index(op.f('ix_system_affected_party_system_id'), 'system_affected_party', ['system_id'])
    op.create_index(op.f('ix_system_affected_party_affected_party_id'), 'system_affected_party', ['affected_party_id'])


def downgrade() -> None:
    # Link tables first (depend on system)
    op.drop_index(op.f('ix_system_affected_party_affected_party_id'), table_name='system_affected_party')
    op.drop_index(op.f('ix_system_affected_party_system_id'), table_name='system_affected_party')
    op.drop_table('system_affected_party')

    op.drop_index(op.f('ix_system_data_category_data_category_id'), table_name='system_data_category')
    op.drop_index(op.f('ix_system_data_category_system_id'), table_name='system_data_category')
    op.drop_table('system_data_category')

    # Check constraint
    op.drop_constraint('ck_system_custom_no_catalogue', 'system', type_='check')

    # FK column indexes
    op.drop_index(op.f('ix_system_human_oversight_type_id'), table_name='system')
    op.drop_index(op.f('ix_system_usage_context_id'), table_name='system')
    op.drop_index(op.f('ix_system_hosting_model_id'), table_name='system')
    op.drop_index(op.f('ix_system_operator_role_id'), table_name='system')

    # FK constraints
    op.drop_constraint('fk_system_human_oversight_type', 'system', type_='foreignkey')
    op.drop_constraint('fk_system_usage_context', 'system', type_='foreignkey')
    op.drop_constraint('fk_system_hosting_model', 'system', type_='foreignkey')
    op.drop_constraint('fk_system_eu_operator_role', 'system', type_='foreignkey')

    # Columns
    op.drop_column('system', 'is_custom')
    op.drop_column('system', 'lifecycle_stage')
    op.drop_column('system', 'human_oversight_type_id')
    op.drop_column('system', 'usage_context_id')
    op.drop_column('system', 'hosting_model_id')
    op.drop_column('system', 'operator_role_id')
