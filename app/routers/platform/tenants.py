from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.operator_authz import CurrentOperator, require_permission
from app.db.session import get_provisioner_db
from app.models import Tenant
from app.schemas.platform import ProvisionRequest, ProvisionResponse, TenantListItem
from app.services.provisioning import AlreadyProvisioned, provision_tenant

router = APIRouter(tags=["platform"])


@router.post("/provision", response_model=ProvisionResponse, status_code=201)
def provision(
    body: ProvisionRequest,
    operator: CurrentOperator = Depends(require_permission("tenant:provision")),
) -> ProvisionResponse:
    """Provision a new tenant and its first owner."""
    try:
        tenant_id, owner_id = provision_tenant(
            org_name=body.org_name,
            slug=body.slug,
            owner_email=body.owner_email,
            owner_name=body.owner_name,
            actor=operator,
            source="http",
        )
    except AlreadyProvisioned as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return ProvisionResponse(tenant_id=tenant_id, owner_id=owner_id)


@router.get("/tenants", response_model=list[TenantListItem])
def list_tenants(
    operator: CurrentOperator = Depends(require_permission("tenant:provision")),
    db: Session = Depends(get_provisioner_db),
) -> list[TenantListItem]:
    """List all tenants (cross-tenant read, platform operators only)."""
    rows = db.scalars(select(Tenant).order_by(Tenant.created_at)).all()
    return [TenantListItem.model_validate(t) for t in rows]
