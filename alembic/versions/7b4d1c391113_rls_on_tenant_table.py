"""rls on tenant table

Revision ID: 7b4d1c391113
Revises: 8eda654f48eb
Create Date: 2026-06-04 22:16:29.040381
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '7b4d1c391113'
down_revision: str | Sequence[str] | None = '8eda654f48eb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE tenant ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON tenant
        USING (id = current_setting('app.current_tenant', true)::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant")
    op.execute("ALTER TABLE tenant DISABLE ROW LEVEL SECURITY")
