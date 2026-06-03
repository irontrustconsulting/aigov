"""
Systems endpoints (v1) — the first TENANT-SCOPED resource.

Unlike /tenants and /reference (global), these run on get_tenant_db, so every
query is RLS-filtered to the caller's membership-verified tenant. A user can
only ever see/create systems within their own tenant — enforced at the database
level, not in this code.

Demonstrates the full chain:
  bearer token -> verify -> resolve user+tenant+membership -> tenant session
  -> RLS isolation.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field

from app.auth.context import TenantContext, get_tenant_context, get_tenant_db, require_role
from app.models import System

router = APIRouter(prefix="/systems", tags=["systems"])


class SystemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class SystemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str


@router.get("", response_model=list[SystemRead])
def list_systems(db: Session = Depends(get_tenant_db)) -> list[System]:
    """List systems in the caller's tenant. RLS scopes this automatically —
    no explicit WHERE tenant_id needed; the session is already tenant-bound."""
    return list(db.scalars(select(System).order_by(System.created_at)))


@router.post("", response_model=SystemRead, status_code=status.HTTP_201_CREATED)
def create_system(
    payload: SystemCreate,
    ctx: TenantContext = Depends(require_role("admin", "contributor")),
    db: Session = Depends(get_tenant_db),
) -> System:
    """Create a system in the caller's tenant. Guarded by require_role (admins
    and contributors). tenant_id is set from the verified context, never from
    client input."""
    system = System(
        tenant_id=ctx.tenant_id,
        name=payload.name,
        metadata_blob={},
    )
    db.add(system)
    db.flush()
    db.refresh(system)
    return system