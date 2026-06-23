"""fix_operator_provisioner_grants

Revision ID: 47d06b509b30
Revises: 98279f35e917
Create Date: 2026-06-22 23:19:46.152243

Two grant gaps in the original platform_audit_event migration (099104f68fc0)
and the operator table setup:

1. platform_audit_event — INSERT ... RETURNING requires SELECT when SQLAlchemy
   fetches server-default columns (occurred_at) after insert.  Both provisioner
   roles lacked SELECT, causing InsufficientPrivilege on every ORM insert.

2. operator — irontrustai_operator_provisioner must UPDATE the operator row to
   flip cognito_sub from the __pending__ placeholder to the real Cognito sub
   after AdminCreateUser returns. UPDATE was never granted.
"""
from collections.abc import Sequence

from alembic import op


revision: str = '47d06b509b30'
down_revision: str | Sequence[str] | None = '98279f35e917'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fix 1: SELECT on audit table for INSERT ... RETURNING
    op.execute(
        "GRANT SELECT ON platform_audit_event "
        "TO irontrustai_provisioner, irontrustai_operator_provisioner"
    )
    # Fix 2: UPDATE on operator so cognito_sub can be written after Cognito call
    op.execute(
        "GRANT UPDATE ON operator TO irontrustai_operator_provisioner"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE UPDATE ON operator FROM irontrustai_operator_provisioner"
    )
    op.execute(
        "REVOKE SELECT ON platform_audit_event "
        "FROM irontrustai_provisioner, irontrustai_operator_provisioner"
    )
