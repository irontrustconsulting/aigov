"""Pydantic v2 schemas for the governance role endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GovernanceRoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    description: str | None
    line_of_defence: int


class GovernanceRoleConflictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role_a_id: uuid.UUID
    role_b_id: uuid.UUID


class GovernanceCatalogueRead(BaseModel):
    roles: list[GovernanceRoleRead]
    conflicts: list[GovernanceRoleConflictRead]


class GovernanceRoleAssignmentCreate(BaseModel):
    membership_id: uuid.UUID
    governance_role_id: uuid.UUID


class GovernanceRoleAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    membership_id: uuid.UUID
    governance_role_id: uuid.UUID
    granted_by_membership_id: uuid.UUID | None
    granted_at: datetime


class MeRead(BaseModel):
    """The caller's own identity: membership + administrative role (membership.role)
    + the governance roles they hold. Self-scoped only — there is no path param,
    by design (B1: a member must be able to read their own roles without an
    admin-gated or foreign-id lookup)."""

    membership_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    email: str | None
    name: str | None
    governance_roles: list[GovernanceRoleRead]
