"""catalogue_product prefill columns — DM-S4a (D-69)

Adds hosting_model_id (FK hosting_model, ON DELETE SET NULL) and
intended_use (text) to catalogue_product, enabling typed field prefills
for the system intake wizard.

Revision ID: cce02cda26a4
Revises: 84d535834a0d
Create Date: 2026-07-02
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'cce02cda26a4'
down_revision: str | Sequence[str] | None = '84d535834a0d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'catalogue_product',
        sa.Column('hosting_model_id', sa.UUID(), nullable=True),
    )
    op.add_column(
        'catalogue_product',
        sa.Column('intended_use', sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        'fk_catalogue_product_hosting_model',
        'catalogue_product', 'hosting_model',
        ['hosting_model_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_catalogue_product_hosting_model_id',
        'catalogue_product', ['hosting_model_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_catalogue_product_hosting_model_id', table_name='catalogue_product')
    op.drop_constraint('fk_catalogue_product_hosting_model', 'catalogue_product', type_='foreignkey')
    op.drop_column('catalogue_product', 'intended_use')
    op.drop_column('catalogue_product', 'hosting_model_id')
