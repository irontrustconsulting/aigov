"""
Governance role service: SoD enforcement and audit helpers.

assert_governance_assignable is the SINGLE locus of SoD logic. Every code path
that assigns a governance role calls this function. Object-scope extension later
means adding a nullable scope_id parameter here and filtering current assignments
by it; application code outside this module never reasons about SoD directly.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.governance import (
    GovernanceRole,
    GovernanceRoleAssignment,
    GovernanceRoleConflict,
)
from app.models.lifecycle import AuditEvent


def assert_governance_assignable(
    acting_membership_id: uuid.UUID,
    subject_membership_id: uuid.UUID,
    governance_role_id: uuid.UUID,
    db: Session,
) -> None:
    """Raise HTTPException if the assignment is forbidden.

    Two checks, in order:
      1. Self-assignment: acting admin may not assign to their own membership.
      2. SoD conflict: subject must not already hold a role that conflicts with
         the candidate, per the governance_role_conflict matrix.

    The DB session must already be scoped to the correct tenant (via
    get_tenant_db) so that the assignment query is RLS-filtered automatically.
    """
    if acting_membership_id == subject_membership_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Cannot assign governance roles to your own membership",
        )

    # Load all governance roles the subject currently holds in this tenant.
    # RLS on governance_role_assignment ensures we only see the current tenant.
    held_role_ids: list[uuid.UUID] = list(db.scalars(
        select(GovernanceRoleAssignment.governance_role_id).where(
            GovernanceRoleAssignment.membership_id == subject_membership_id,
        )
    ))

    if not held_role_ids:
        return  # no existing roles — no conflict possible

    # Check the conflict matrix for any (held_role, candidate) pair.
    # Python min/max on UUIDs matches the DB canonical ordering (role_a_id < role_b_id)
    # so the lookup hits the unique index directly.
    for held_id in held_role_ids:
        lo = min(held_id, governance_role_id)
        hi = max(held_id, governance_role_id)
        conflict = db.scalar(
            select(GovernanceRoleConflict).where(
                GovernanceRoleConflict.role_a_id == lo,
                GovernanceRoleConflict.role_b_id == hi,
            )
        )
        if conflict is not None:
            held_role = db.get(GovernanceRole, held_id)
            candidate_role = db.get(GovernanceRole, governance_role_id)
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=(
                    f"Separation of duties conflict: "
                    f"'{candidate_role.key}' conflicts with held role "
                    f"'{held_role.key}'"
                ),
            )


def record_governance_event(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    action: str,
    assignment_id: uuid.UUID,
    subject_membership_id: uuid.UUID,
    governance_role_key: str,
) -> None:
    """Stage a tenant AuditEvent row for a governance grant or revoke.
    Caller must commit (transaction control stays with the router handler).
    """
    db.add(AuditEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type="governance_role_assignment",
        entity_id=assignment_id,
        detail={
            "subject_membership_id": str(subject_membership_id),
            "governance_role_key": governance_role_key,
        },
    ))
