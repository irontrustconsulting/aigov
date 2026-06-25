"""
Caller's-own-identity read (v1, tenant-scoped).

Self-scoped only: there is no membership_id path param, so there is nothing to
gate beyond "is this an authenticated tenant member" — reading one's own roles
carries no SoD concern. This fills the gap that
governance-roles/assignments/member/{membership_id} leaves: that route takes a
foreign membership_id with no admin gate and no self-check, so it cannot serve
as a caller self-read (B1, sprints/UI-F0-FOUNDATION.md §0-1b).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db
from app.models.governance import GovernanceRole, GovernanceRoleAssignment
from app.models.identity import Tenant
from app.schemas.governance import GovernanceRoleRead, MeRead

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeRead)
def get_me(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> MeRead:
    """Return the caller's own membership + administrative role + governance
    roles held. Scoped to ctx.membership_id only — never a path param."""
    roles = list(db.scalars(
        select(GovernanceRole)
        .join(
            GovernanceRoleAssignment,
            GovernanceRole.id == GovernanceRoleAssignment.governance_role_id,
        )
        .where(GovernanceRoleAssignment.membership_id == ctx.membership_id)
        .order_by(GovernanceRole.line_of_defence, GovernanceRole.key)
    ))
    tenant = db.get(Tenant, ctx.tenant_id)
    return MeRead(
        membership_id=ctx.membership_id,
        tenant_id=ctx.tenant_id,
        role=ctx.role,
        email=ctx.email,
        name=ctx.name,
        tenant_name=tenant.name,
        governance_roles=[GovernanceRoleRead.model_validate(r) for r in roles],
    )
