"""
Governance role management endpoints (v1, tenant-scoped).

All routes run on the RLS-scoped tenant session from get_tenant_db.
The acting user's membership is available via TenantContext (ctx.membership_id).

Assignment endpoints require require_role("admin") — only a tenant admin may
grant or revoke governance roles. Reading the catalogue and listing assignments
is open to any authenticated member.

Governance grants live ONLY in governance_role_assignment; they never appear on
membership.role (which remains administrative-only).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import (
    TenantContext,
    get_tenant_context,
    get_tenant_db,
    require_role,
)
from app.models.governance import (
    GovernanceRole,
    GovernanceRoleAssignment,
    GovernanceRoleConflict,
)
from app.schemas.governance import (
    GovernanceCatalogueRead,
    GovernanceRoleAssignmentCreate,
    GovernanceRoleAssignmentRead,
    GovernanceRoleConflictRead,
    GovernanceRoleRead,
)
from app.services.governance import (
    assert_governance_assignable,
    record_governance_event,
)

router = APIRouter(prefix="/governance-roles", tags=["governance-roles"])


@router.get("/catalogue", response_model=GovernanceCatalogueRead)
def get_catalogue(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> GovernanceCatalogueRead:
    """Return the full governance role catalogue and SoD conflict matrix.
    Intended for the assignment UI — no role gate, open to any tenant member."""
    roles = list(db.scalars(
        select(GovernanceRole).order_by(
            GovernanceRole.line_of_defence, GovernanceRole.key
        )
    ))
    conflicts = list(db.scalars(select(GovernanceRoleConflict)))
    return GovernanceCatalogueRead(
        roles=[GovernanceRoleRead.model_validate(r) for r in roles],
        conflicts=[GovernanceRoleConflictRead.model_validate(c) for c in conflicts],
    )


@router.get("/assignments", response_model=list[GovernanceRoleAssignmentRead])
def list_assignments(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> list[GovernanceRoleAssignment]:
    """List all governance role assignments in this tenant.
    RLS ensures only the caller's tenant is visible."""
    return list(db.scalars(
        select(GovernanceRoleAssignment).order_by(GovernanceRoleAssignment.granted_at)
    ))


@router.get(
    "/assignments/member/{membership_id}",
    response_model=list[GovernanceRoleAssignmentRead],
)
def list_member_assignments(
    membership_id: uuid.UUID,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_tenant_db),
) -> list[GovernanceRoleAssignment]:
    """List governance roles held by one specific member in this tenant."""
    return list(db.scalars(
        select(GovernanceRoleAssignment).where(
            GovernanceRoleAssignment.membership_id == membership_id,
        ).order_by(GovernanceRoleAssignment.granted_at)
    ))


@router.post(
    "/assignments",
    response_model=GovernanceRoleAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_role(
    payload: GovernanceRoleAssignmentCreate,
    ctx: TenantContext = Depends(require_role("admin")),
    db: Session = Depends(get_tenant_db),
) -> GovernanceRoleAssignment:
    """Assign a governance role to a member.

    Guards:
      - require_role("admin") — only admins may assign governance roles.
      - assert_governance_assignable — blocks SoD conflicts and self-assignment.
    """
    # Validate the role exists (governance_role is a platform reference table,
    # not under RLS, so this query bypasses RLS naturally via the same session).
    gov_role = db.get(GovernanceRole, payload.governance_role_id)
    if gov_role is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Governance role not found"
        )

    assert_governance_assignable(
        acting_membership_id=ctx.membership_id,
        subject_membership_id=payload.membership_id,
        governance_role_id=payload.governance_role_id,
        db=db,
    )

    assignment = GovernanceRoleAssignment(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        membership_id=payload.membership_id,
        governance_role_id=payload.governance_role_id,
        granted_by_membership_id=ctx.membership_id,
    )
    db.add(assignment)
    db.flush()  # populate assignment.id before audit

    record_governance_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user_id,
        action="governance_role.granted",
        assignment_id=assignment.id,
        subject_membership_id=payload.membership_id,
        governance_role_key=gov_role.key,
    )

    return assignment


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_role(
    assignment_id: uuid.UUID,
    ctx: TenantContext = Depends(require_role("admin")),
    db: Session = Depends(get_tenant_db),
) -> None:
    """Revoke a governance role assignment.

    RLS on governance_role_assignment ensures the assignment belongs to the
    caller's tenant — no explicit tenant_id filter needed.
    """
    assignment = db.get(GovernanceRoleAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    gov_role = db.get(GovernanceRole, assignment.governance_role_id)

    record_governance_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user_id,
        action="governance_role.revoked",
        assignment_id=assignment.id,
        subject_membership_id=assignment.membership_id,
        governance_role_key=gov_role.key if gov_role else "unknown",
    )

    db.delete(assignment)
