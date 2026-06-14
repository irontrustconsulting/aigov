"""system_intake_vocab_tables

Adds the six controlled-vocabulary reference tables used by the System Intake
sprint plus the system_lifecycle_stage Postgres enum type.

All six tables are GLOBAL (no tenant_id, no RLS) — they are read-only
deployment data readable by any tenant session, curated by migrations only.

Seed data is inserted inline (same pattern as governance_role_model migration)
because these rows are small, immutable, and deployment-coupled: every env must
have exactly these codes after `alembic upgrade head`.

Revision ID: 05ff13cdcdc3
Revises: daed01decdf9
Create Date: 2026-06-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '05ff13cdcdc3'
down_revision: str | Sequence[str] | None = 'daed01decdf9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. system_lifecycle_stage enum — created here, referenced by W2
    #    migration that adds the column to the system table.
    # ------------------------------------------------------------------
    sa.Enum(
        'development', 'pilot', 'production', 'retired',
        name='system_lifecycle_stage',
    ).create(op.get_bind())

    # ------------------------------------------------------------------
    # 2. eu_operator_role  — legal posture of the deploying organisation
    #    under EU AI Act Art. 3 (provider / deployer / importer / distributor).
    #    Named eu_operator_role to avoid collision with the platform RBAC
    #    operator_role join table (operator ↔ role).
    # ------------------------------------------------------------------
    op.create_table(
        'eu_operator_role',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('framework_ref', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_eu_operator_role_code'),
    )
    op.create_index(op.f('ix_eu_operator_role_active'), 'eu_operator_role', ['active'])

    # ------------------------------------------------------------------
    # 3. hosting_model  — where the AI system runs
    # ------------------------------------------------------------------
    op.create_table(
        'hosting_model',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('framework_ref', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_hosting_model_code'),
    )
    op.create_index(op.f('ix_hosting_model_active'), 'hosting_model', ['active'])

    # ------------------------------------------------------------------
    # 4. usage_context  — who is exposed to the AI system
    # ------------------------------------------------------------------
    op.create_table(
        'usage_context',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('framework_ref', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_usage_context_code'),
    )
    op.create_index(op.f('ix_usage_context_active'), 'usage_context', ['active'])

    # ------------------------------------------------------------------
    # 5. human_oversight_type  — level of human control (EU AI Act Art. 14)
    # ------------------------------------------------------------------
    op.create_table(
        'human_oversight_type',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('framework_ref', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_human_oversight_type_code'),
    )
    op.create_index(op.f('ix_human_oversight_type_active'), 'human_oversight_type', ['active'])

    # ------------------------------------------------------------------
    # 6. data_category  — personal data categories processed by the system
    #    is_special_category=true → GDPR Art. 9 / EU AI Act heightened duty
    # ------------------------------------------------------------------
    op.create_table(
        'data_category',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('framework_ref', sa.String(length=120), nullable=True),
        sa.Column('is_special_category', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_data_category_code'),
    )
    op.create_index(op.f('ix_data_category_active'), 'data_category', ['active'])

    # ------------------------------------------------------------------
    # 7. affected_party  — parties affected by the AI system
    #    is_vulnerable_group=true → EU AI Act Art. 27 heightened duty
    # ------------------------------------------------------------------
    op.create_table(
        'affected_party',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('framework_ref', sa.String(length=120), nullable=True),
        sa.Column('is_vulnerable_group', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_affected_party_code'),
    )
    op.create_index(op.f('ix_affected_party_active'), 'affected_party', ['active'])

    # ------------------------------------------------------------------
    # SEED DATA — inline so every environment gets these codes on upgrade.
    # Codes are immutable deployment constants; additions require a new
    # migration (renaming/removing codes would orphan tenant selections).
    # ------------------------------------------------------------------

    op.execute("""
        INSERT INTO eu_operator_role (id, code, label, sort_order, framework_ref)
        VALUES
          (gen_random_uuid(), 'provider',     'Provider',     0, 'EU AI Act Art. 3'),
          (gen_random_uuid(), 'deployer',     'Deployer',     1, 'EU AI Act Art. 3'),
          (gen_random_uuid(), 'importer',     'Importer',     2, 'EU AI Act Art. 3'),
          (gen_random_uuid(), 'distributor',  'Distributor',  3, 'EU AI Act Art. 3')
    """)

    op.execute("""
        INSERT INTO hosting_model (id, code, label, sort_order)
        VALUES
          (gen_random_uuid(), 'cloud_saas',   'Cloud SaaS',  0),
          (gen_random_uuid(), 'self_hosted',  'Self-Hosted', 1),
          (gen_random_uuid(), 'on_premise',   'On-Premise',  2),
          (gen_random_uuid(), 'hybrid',       'Hybrid',      3),
          (gen_random_uuid(), 'edge',         'Edge',        4)
    """)

    op.execute("""
        INSERT INTO usage_context (id, code, label, sort_order)
        VALUES
          (gen_random_uuid(), 'internal_only',   'Internal Only',    0),
          (gen_random_uuid(), 'employee_facing', 'Employee-Facing',  1),
          (gen_random_uuid(), 'customer_facing', 'Customer-Facing',  2),
          (gen_random_uuid(), 'public_facing',   'Public-Facing',    3)
    """)

    op.execute("""
        INSERT INTO human_oversight_type (id, code, label, sort_order, framework_ref)
        VALUES
          (gen_random_uuid(), 'human_in_the_loop',  'Human in the Loop',  0, 'EU AI Act Art. 14'),
          (gen_random_uuid(), 'human_on_the_loop',  'Human on the Loop',  1, 'EU AI Act Art. 14'),
          (gen_random_uuid(), 'human_in_command',   'Human in Command',   2, 'EU AI Act Art. 14'),
          (gen_random_uuid(), 'fully_autonomous',   'Fully Autonomous',   3, 'EU AI Act Art. 14')
    """)

    # Special categories first (is_special_category = true)
    op.execute("""
        INSERT INTO data_category (id, code, label, sort_order, framework_ref, is_special_category)
        VALUES
          (gen_random_uuid(), 'health',                         'Health Data',                        0,  'EU AI Act / GDPR Art. 9', true),
          (gen_random_uuid(), 'genetic',                        'Genetic Data',                       1,  'EU AI Act / GDPR Art. 9', true),
          (gen_random_uuid(), 'biometric_id',                   'Biometric Data for ID',              2,  'EU AI Act / GDPR Art. 9', true),
          (gen_random_uuid(), 'racial_ethnic_origin',           'Racial or Ethnic Origin',            3,  'EU AI Act / GDPR Art. 9', true),
          (gen_random_uuid(), 'political_opinions',             'Political Opinions',                 4,  'EU AI Act / GDPR Art. 9', true),
          (gen_random_uuid(), 'religious_philosophical_beliefs','Religious or Philosophical Beliefs',  5,  'EU AI Act / GDPR Art. 9', true),
          (gen_random_uuid(), 'trade_union_membership',         'Trade Union Membership',             6,  'EU AI Act / GDPR Art. 9', true),
          (gen_random_uuid(), 'sex_life_sexual_orientation',    'Sex Life or Sexual Orientation',     7,  'EU AI Act / GDPR Art. 9', true)
    """)

    # General categories (is_special_category = false, default)
    op.execute("""
        INSERT INTO data_category (id, code, label, sort_order)
        VALUES
          (gen_random_uuid(), 'identifiers',      'Identifiers',     10),
          (gen_random_uuid(), 'contact_details',  'Contact Details', 11),
          (gen_random_uuid(), 'financial_data',   'Financial Data',  12),
          (gen_random_uuid(), 'location_data',    'Location Data',   13),
          (gen_random_uuid(), 'behavioural_data', 'Behavioural Data',14),
          (gen_random_uuid(), 'employment_data',  'Employment Data', 15)
    """)

    # Vulnerable groups (is_vulnerable_group = true)
    op.execute("""
        INSERT INTO affected_party (id, code, label, sort_order, framework_ref, is_vulnerable_group)
        VALUES
          (gen_random_uuid(), 'children',               'Children',               4, 'EU AI Act Art. 27', true),
          (gen_random_uuid(), 'vulnerable_individuals', 'Vulnerable Individuals', 5, 'EU AI Act Art. 27', true)
    """)

    # General parties (is_vulnerable_group = false, default)
    op.execute("""
        INSERT INTO affected_party (id, code, label, sort_order)
        VALUES
          (gen_random_uuid(), 'employees',               'Employees',                 0),
          (gen_random_uuid(), 'job_applicants',          'Job Applicants',            1),
          (gen_random_uuid(), 'customers_service_users', 'Customers / Service Users', 2),
          (gen_random_uuid(), 'general_public',          'General Public',            3)
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_affected_party_active'), table_name='affected_party')
    op.drop_table('affected_party')

    op.drop_index(op.f('ix_data_category_active'), table_name='data_category')
    op.drop_table('data_category')

    op.drop_index(op.f('ix_human_oversight_type_active'), table_name='human_oversight_type')
    op.drop_table('human_oversight_type')

    op.drop_index(op.f('ix_usage_context_active'), table_name='usage_context')
    op.drop_table('usage_context')

    op.drop_index(op.f('ix_hosting_model_active'), table_name='hosting_model')
    op.drop_table('hosting_model')

    op.drop_index(op.f('ix_eu_operator_role_active'), table_name='eu_operator_role')
    op.drop_table('eu_operator_role')

    sa.Enum(name='system_lifecycle_stage').drop(op.get_bind())
