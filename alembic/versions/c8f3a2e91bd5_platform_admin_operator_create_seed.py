"""platform_admin role and operator:create permission

Revision ID: c8f3a2e91bd5
Revises: 47d06b509b30
Create Date: 2026-06-23

Seed rows for UI-F8-OPERATOR-RBAC: the platform_admin role (full platform
administration) and operator:create permission (manage operators and their
roles). No DDL — the five RBAC tables already exist (cef7211ddfe4).

No new GRANTs needed: irontrustai_platform_ro already has SELECT on all five
RBAC tables (cef7211ddfe4); irontrustai_operator_provisioner already has
SELECT on role.
"""
from collections.abc import Sequence

from alembic import op


revision: str = 'c8f3a2e91bd5'
down_revision: str | Sequence[str] | None = '47d06b509b30'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # New permission: operator:create
    op.execute(
        "INSERT INTO permission (id, key, description) "
        "VALUES (gen_random_uuid(), 'operator:create', "
        "'Manage operators and their roles')"
    )
    # New role: platform_admin (full platform administration)
    op.execute(
        "INSERT INTO role (id, key, description) "
        "VALUES (gen_random_uuid(), 'platform_admin', 'Full platform administration')"
    )
    # Grant platform_admin all permissions: tenant:provision + operator:create
    op.execute(
        "INSERT INTO role_permission (id, role_id, permission_id) "
        "SELECT gen_random_uuid(), "
        "(SELECT id FROM role WHERE key = 'platform_admin'), "
        "(SELECT id FROM permission WHERE key = 'tenant:provision')"
    )
    op.execute(
        "INSERT INTO role_permission (id, role_id, permission_id) "
        "SELECT gen_random_uuid(), "
        "(SELECT id FROM role WHERE key = 'platform_admin'), "
        "(SELECT id FROM permission WHERE key = 'operator:create')"
    )


def downgrade() -> None:
    # Remove operator_role rows for platform_admin before dropping the role
    # (operator_role.role_id has ondelete=RESTRICT; cannot drop role while in use)
    op.execute(
        "DELETE FROM operator_role "
        "WHERE role_id = (SELECT id FROM role WHERE key = 'platform_admin')"
    )
    # Drop role (cascades to its role_permission rows via ondelete=CASCADE)
    op.execute("DELETE FROM role WHERE key = 'platform_admin'")
    # Drop permission (safe now: no role_permission rows reference it)
    op.execute("DELETE FROM permission WHERE key = 'operator:create'")
