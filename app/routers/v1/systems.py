"""
Systems endpoints (v1) — tenant-scoped AI system reads and updates.

Gate rules:
  GET  / (list):        any authenticated member (RLS scopes)
  GET  /{id}:           any authenticated member (RLS scopes)
  PATCH /{id}:          require_governance_role("system_owner")
  GET  /{id}/prefill:   any authenticated member (RLS scopes)

POST / (create) was removed in DM-S2 (INV-78). System creation now happens
only through POST /v1/registrations — see app/routers/v1/registrations.py.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_db, require_governance_role
from app.models import System
from app.schemas.system import (
    PrefillResponse,
    SystemDetail,
    SystemRead,
    SystemUpdate,
)
from app.services import prefill_service, system_service

router = APIRouter(prefix="/systems", tags=["systems"])


@router.get("", response_model=list[SystemRead])
def list_systems(db: Session = Depends(get_tenant_db)) -> list[System]:
    """List systems in the caller's tenant. RLS scopes this automatically."""
    return list(db.scalars(select(System).order_by(System.created_at)))


@router.get("/{system_id}/prefill", response_model=PrefillResponse)
def get_system_prefill(
    system_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
) -> PrefillResponse:
    """Return catalogue facts for a system's linked product. Any tenant member."""
    return prefill_service.get_prefill(system_id, db)


@router.get("/{system_id}", response_model=SystemDetail)
def get_system(
    system_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
) -> SystemDetail:
    """Full system detail — any authenticated tenant member."""
    return system_service.get_system_detail(system_id, db)


@router.patch("/{system_id}", response_model=SystemDetail)
def update_system(
    system_id: uuid.UUID,
    payload: SystemUpdate,
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> SystemDetail:
    """Update system metadata. Gated by the system_owner governance role."""
    system_service.update_system(system_id, payload, ctx, db)
    return system_service.get_system_detail(system_id, db)
