"""
Application-layer authorization for platform operators (authZ).

Kept separate from operator_auth.py (authN). operator_auth.py answers "who is
this?" by verifying the Cognito token. This module answers "are they allowed?"
by resolving the operator from the DB, checking status, and loading permissions.

All DB access here runs on irontrustai_platform_ro — reads only, no writes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, status
from sqlalchemy import select, distinct
from sqlalchemy.orm import Session

from app.auth.operator_auth import OperatorClaims, verify_operator_token
from app.db.session import get_platform_ro_db
from app.models.platform_rbac import Operator, OperatorRole, RolePermission, Permission
from app.models.base import OperatorStatus


@dataclass(frozen=True)
class CurrentOperator:
    """Fully-materialized operator identity with effective permissions.

    Plain object — no live ORM references. Safe to use after the DB session
    has closed.
    """
    id: uuid.UUID
    cognito_sub: str
    email: str
    display_name: str | None
    permissions: frozenset[str] = field(default_factory=frozenset)


def get_current_operator(
    claims: OperatorClaims = Depends(verify_operator_token),
    db: Session = Depends(get_platform_ro_db),
) -> CurrentOperator:
    """FastAPI dependency: resolve the authenticated operator from the DB.

    Contract:
      - Unknown cognito_sub  → 403
      - status != ACTIVE     → 403
      - Otherwise            → returns CurrentOperator with effective permissions
    """
    row = db.execute(
        select(Operator).where(Operator.cognito_sub == claims.sub)
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a recognized operator",
        )

    if row.status != OperatorStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator account is disabled",
        )

    # Load effective permissions: operator_role → role_permission → permission.key
    perm_rows = db.execute(
        select(distinct(Permission.key))
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(OperatorRole, OperatorRole.role_id == RolePermission.role_id)
        .where(OperatorRole.operator_id == row.id)
    ).scalars().all()

    return CurrentOperator(
        id=row.id,
        cognito_sub=row.cognito_sub,
        email=row.email,
        display_name=row.display_name,
        permissions=frozenset(perm_rows),
    )


def require_permission(key: str):
    """Dependency factory: gate a route on a specific permission key.

    Usage:
        @router.post("/platform/provision")
        def provision(op: CurrentOperator = Depends(require_permission("tenant:provision"))):
            ...
    """
    def _check(
        operator: CurrentOperator = Depends(get_current_operator),
    ) -> CurrentOperator:
        if key not in operator.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {key}",
            )
        return operator

    return _check
