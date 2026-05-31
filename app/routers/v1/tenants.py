"""
Tenant management endpoints (v1).

Tenants are NOT tenant-scoped (a tenant IS the scope), so these use the plain
`get_db` session — no RLS, no tenant context. This is the registry the
onboarding flow will create into.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Tenant
from app.schemas.tenant import TenantCreate, TenantRead

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)) -> Tenant:
    """Create a tenant. `slug` is unique; a duplicate returns 409."""
    tenant = Tenant(name=payload.name, slug=payload.slug)
    db.add(tenant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A tenant with slug '{payload.slug}' already exists.",
        )
    db.refresh(tenant)
    return tenant


@router.get("", response_model=list[TenantRead])
def list_tenants(db: Session = Depends(get_db)) -> list[Tenant]:
    """List all tenants. (Returns [] when none exist.)"""
    return list(db.scalars(select(Tenant).order_by(Tenant.created_at)))


@router.get("/{tenant_id}", response_model=TenantRead)
def get_tenant(tenant_id: uuid.UUID, db: Session = Depends(get_db)) -> Tenant:
    """Fetch a single tenant by id, or 404."""
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant