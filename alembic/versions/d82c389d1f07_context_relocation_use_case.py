"""context_relocation_use_case

Relocates usage_context_id, human_oversight_type_id, data categories, and
affected parties from the system table / system-level link tables to use_case.

Changes:
- use_case: 2 new FK columns (usage_context_id, human_oversight_type_id)
- use_case_data_category: new link table with tenant_id + RLS (D-64/INV-77)
- use_case_affected_party: new link table with tenant_id + RLS (D-64/INV-77)
- Backfill: copies system-level values to every child use case (DF-D1-3)
- system: drops usage_context_id, human_oversight_type_id columns
- Drops system_data_category and system_affected_party tables (DF-D1-1)

Down-path is best-effort dev reversal — aggregates per-use-case rows back to
system level. Lossy if use cases have diverged post-migration.

Revision ID: d82c389d1f07
Revises: ff6654ebd569
Create Date: 2026-06-27
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd82c389d1f07'
down_revision: str | Sequence[str] | None = 'c8f3a2e91bd5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. New FK columns on use_case
    # ------------------------------------------------------------------
    op.add_column('use_case', sa.Column('usage_context_id', sa.UUID(), nullable=True))
    op.add_column('use_case', sa.Column('human_oversight_type_id', sa.UUID(), nullable=True))

    op.create_foreign_key(
        'fk_use_case_usage_context', 'use_case', 'usage_context',
        ['usage_context_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_use_case_human_oversight_type', 'use_case', 'human_oversight_type',
        ['human_oversight_type_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index(op.f('ix_use_case_usage_context_id'), 'use_case', ['usage_context_id'])
    op.create_index(op.f('ix_use_case_human_oversight_type_id'), 'use_case', ['human_oversight_type_id'])

    # ------------------------------------------------------------------
    # 2. use_case_data_category — tenant-scoped with RLS (D-64/INV-77)
    # ------------------------------------------------------------------
    op.create_table(
        'use_case_data_category',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('use_case_id', sa.UUID(), nullable=False),
        sa.Column('data_category_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE',
                                name='fk_use_case_data_category_tenant'),
        sa.ForeignKeyConstraint(['use_case_id'], ['use_case.id'], ondelete='CASCADE',
                                name='fk_use_case_data_category_use_case'),
        sa.ForeignKeyConstraint(['data_category_id'], ['data_category.id'], ondelete='CASCADE',
                                name='fk_use_case_data_category_data_category'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('use_case_id', 'data_category_id', name='uq_use_case_data_category'),
    )
    op.create_index(op.f('ix_use_case_data_category_tenant_id'), 'use_case_data_category', ['tenant_id'])
    op.create_index(op.f('ix_use_case_data_category_use_case_id'), 'use_case_data_category', ['use_case_id'])
    op.create_index(op.f('ix_use_case_data_category_data_category_id'), 'use_case_data_category', ['data_category_id'])

    op.execute("ALTER TABLE use_case_data_category ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON use_case_data_category
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # ------------------------------------------------------------------
    # 3. use_case_affected_party — tenant-scoped with RLS (D-64/INV-77)
    # ------------------------------------------------------------------
    op.create_table(
        'use_case_affected_party',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('use_case_id', sa.UUID(), nullable=False),
        sa.Column('affected_party_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ondelete='CASCADE',
                                name='fk_use_case_affected_party_tenant'),
        sa.ForeignKeyConstraint(['use_case_id'], ['use_case.id'], ondelete='CASCADE',
                                name='fk_use_case_affected_party_use_case'),
        sa.ForeignKeyConstraint(['affected_party_id'], ['affected_party.id'], ondelete='CASCADE',
                                name='fk_use_case_affected_party_affected_party'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('use_case_id', 'affected_party_id', name='uq_use_case_affected_party'),
    )
    op.create_index(op.f('ix_use_case_affected_party_tenant_id'), 'use_case_affected_party', ['tenant_id'])
    op.create_index(op.f('ix_use_case_affected_party_use_case_id'), 'use_case_affected_party', ['use_case_id'])
    op.create_index(op.f('ix_use_case_affected_party_affected_party_id'), 'use_case_affected_party', ['affected_party_id'])

    op.execute("ALTER TABLE use_case_affected_party ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON use_case_affected_party
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # ------------------------------------------------------------------
    # 4. Backfill: copy system-level values to every child use case (DF-D1-3)
    #    usage_context_id / human_oversight_type_id: direct column copy.
    #    data_category / affected_party link rows: fan-out from system rows.
    # ------------------------------------------------------------------
    op.execute("""
        UPDATE use_case uc
        SET usage_context_id = s.usage_context_id,
            human_oversight_type_id = s.human_oversight_type_id
        FROM system s
        WHERE s.id = uc.system_id
          AND (s.usage_context_id IS NOT NULL OR s.human_oversight_type_id IS NOT NULL)
    """)

    op.execute("""
        INSERT INTO use_case_data_category (id, tenant_id, use_case_id, data_category_id)
        SELECT gen_random_uuid(), uc.tenant_id, uc.id, sdc.data_category_id
        FROM use_case uc
        JOIN system_data_category sdc ON sdc.system_id = uc.system_id
        ON CONFLICT (use_case_id, data_category_id) DO NOTHING
    """)

    op.execute("""
        INSERT INTO use_case_affected_party (id, tenant_id, use_case_id, affected_party_id)
        SELECT gen_random_uuid(), uc.tenant_id, uc.id, sap.affected_party_id
        FROM use_case uc
        JOIN system_affected_party sap ON sap.system_id = uc.system_id
        ON CONFLICT (use_case_id, affected_party_id) DO NOTHING
    """)

    # ------------------------------------------------------------------
    # 5. Drop system-level FK indexes + constraints + columns
    # ------------------------------------------------------------------
    op.drop_index(op.f('ix_system_usage_context_id'), table_name='system')
    op.drop_index(op.f('ix_system_human_oversight_type_id'), table_name='system')
    op.drop_constraint('fk_system_usage_context', 'system', type_='foreignkey')
    op.drop_constraint('fk_system_human_oversight_type', 'system', type_='foreignkey')
    op.drop_column('system', 'usage_context_id')
    op.drop_column('system', 'human_oversight_type_id')

    # ------------------------------------------------------------------
    # 6. Drop system link tables (data already migrated above)
    # ------------------------------------------------------------------
    op.drop_index(op.f('ix_system_affected_party_affected_party_id'), table_name='system_affected_party')
    op.drop_index(op.f('ix_system_affected_party_system_id'), table_name='system_affected_party')
    op.drop_table('system_affected_party')

    op.drop_index(op.f('ix_system_data_category_data_category_id'), table_name='system_data_category')
    op.drop_index(op.f('ix_system_data_category_system_id'), table_name='system_data_category')
    op.drop_table('system_data_category')


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Best-effort dev reversal — aggregates use-case rows back to system.
    # Lossy once use cases have diverged from each other post-migration.
    # ------------------------------------------------------------------

    # Re-create system link tables
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

    # Aggregate link rows back to system level (distinct — first use case wins)
    op.execute("""
        INSERT INTO system_data_category (id, system_id, data_category_id)
        SELECT DISTINCT ON (uc.system_id, ucdc.data_category_id)
            gen_random_uuid(), uc.system_id, ucdc.data_category_id
        FROM use_case_data_category ucdc
        JOIN use_case uc ON uc.id = ucdc.use_case_id
        ON CONFLICT (system_id, data_category_id) DO NOTHING
    """)

    op.execute("""
        INSERT INTO system_affected_party (id, system_id, affected_party_id)
        SELECT DISTINCT ON (uc.system_id, ucap.affected_party_id)
            gen_random_uuid(), uc.system_id, ucap.affected_party_id
        FROM use_case_affected_party ucap
        JOIN use_case uc ON uc.id = ucap.use_case_id
        ON CONFLICT (system_id, affected_party_id) DO NOTHING
    """)

    # Re-add system FK columns
    op.add_column('system', sa.Column('usage_context_id', sa.UUID(), nullable=True))
    op.add_column('system', sa.Column('human_oversight_type_id', sa.UUID(), nullable=True))

    op.create_foreign_key(
        'fk_system_usage_context', 'system', 'usage_context',
        ['usage_context_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_system_human_oversight_type', 'system', 'human_oversight_type',
        ['human_oversight_type_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index(op.f('ix_system_usage_context_id'), 'system', ['usage_context_id'])
    op.create_index(op.f('ix_system_human_oversight_type_id'), 'system', ['human_oversight_type_id'])

    # Aggregate FK values back (first use case per system wins)
    op.execute("""
        UPDATE system s
        SET usage_context_id = sub.usage_context_id,
            human_oversight_type_id = sub.human_oversight_type_id
        FROM (
            SELECT DISTINCT ON (system_id)
                system_id,
                usage_context_id,
                human_oversight_type_id
            FROM use_case
            WHERE usage_context_id IS NOT NULL OR human_oversight_type_id IS NOT NULL
            ORDER BY system_id, created_at
        ) sub
        WHERE s.id = sub.system_id
    """)

    # Drop new use_case link tables
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON use_case_affected_party")
    op.execute("ALTER TABLE use_case_affected_party DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f('ix_use_case_affected_party_affected_party_id'), table_name='use_case_affected_party')
    op.drop_index(op.f('ix_use_case_affected_party_use_case_id'), table_name='use_case_affected_party')
    op.drop_index(op.f('ix_use_case_affected_party_tenant_id'), table_name='use_case_affected_party')
    op.drop_table('use_case_affected_party')

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON use_case_data_category")
    op.execute("ALTER TABLE use_case_data_category DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f('ix_use_case_data_category_data_category_id'), table_name='use_case_data_category')
    op.drop_index(op.f('ix_use_case_data_category_use_case_id'), table_name='use_case_data_category')
    op.drop_index(op.f('ix_use_case_data_category_tenant_id'), table_name='use_case_data_category')
    op.drop_table('use_case_data_category')

    # Drop use_case FK columns
    op.drop_index(op.f('ix_use_case_human_oversight_type_id'), table_name='use_case')
    op.drop_index(op.f('ix_use_case_usage_context_id'), table_name='use_case')
    op.drop_constraint('fk_use_case_human_oversight_type', 'use_case', type_='foreignkey')
    op.drop_constraint('fk_use_case_usage_context', 'use_case', type_='foreignkey')
    op.drop_column('use_case', 'human_oversight_type_id')
    op.drop_column('use_case', 'usage_context_id')
