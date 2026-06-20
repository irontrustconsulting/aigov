"""
Lifecycle status + manual lever + approval endpoints (v1, tenant plane).

  GET  /v1/use-cases/{id}/lifecycle               state + full-vector
                                                    GateResult; recompute,
                                                    do not persist
  POST /v1/use-cases/{id}/lifecycle/re-evaluate    recompute and move to the
                                                    correct resting gate
  PUT  /v1/vendors/{vendor_id}/approval            set/update vendor clearance
                                                    + fan out to affected use
                                                    cases
  PUT  /v1/products/{product_id}/approval          set/update product
                                                    clearance + fan out
  GET  /v1/systems/{id}/rollup                     use cases + states +
                                                    highest tier + obligations
  GET  /v1/portfolio                               tenant-wide rollup
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_db, require_governance_role
from app.models.domain import CatalogueProduct, CatalogueVendor, System, UseCase
from app.models.lifecycle import DeploymentAuthorisation
from app.schemas.lifecycle import (
    AuthoriseRequest,
    DeploymentAuthorisationRead,
    GateResultRead,
    ProductApprovalCreate,
    ProductApprovalRead,
    SystemRollupRead,
    UseCaseLifecycleRead,
    VendorApprovalCreate,
    VendorApprovalRead,
)
from app.services.authorisation_service import authorise_use_case
from app.services.lifecycle_service import (
    fan_out_product_approval,
    fan_out_vendor_approval,
    full_vector,
    portfolio_rollup,
    re_evaluate,
    set_product_approval,
    set_vendor_approval,
    system_rollup,
)

router = APIRouter(prefix="/use-cases", tags=["lifecycle"])
approvals_router = APIRouter(tags=["lifecycle"])
rollup_router = APIRouter(prefix="/systems", tags=["lifecycle"])

_ALL_GOVERNANCE_ROLES = (
    "system_owner",
    "contributor",
    "reviewer",
    "authoriser",
    "auditor",
)


def _get_use_case(use_case_id: uuid.UUID, ctx: TenantContext, db: Session) -> UseCase:
    use_case = db.scalar(
        select(UseCase).where(
            UseCase.id == use_case_id,
            UseCase.tenant_id == ctx.tenant_id,
        )
    )
    if use_case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Use case not found")
    return use_case


def _lifecycle_read(use_case: UseCase, db: Session) -> UseCaseLifecycleRead:
    vector = full_vector(use_case, db)
    gates = [
        GateResultRead(
            state=state,
            verdict=result.verdict,
            reason_code=result.reason_code,
            reason=result.reason,
            responsible_party=result.responsible_party,
        )
        for state, result in vector
    ]
    blocking = next((g for g in gates if g.verdict != "advance"), None)
    return UseCaseLifecycleRead(
        use_case_id=use_case.id,
        state=use_case.state,
        held_from_state=use_case.held_from_state,
        held_reason=use_case.held_reason,
        gates=gates,
        blocking=blocking,
    )


@router.get("/{use_case_id}/lifecycle", response_model=UseCaseLifecycleRead)
def get_lifecycle_status(
    use_case_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> UseCaseLifecycleRead:
    """Recomputes the full gate vector and shows it — never persists
    (design doc §7: a status read shows the computed verdict, it never
    mutates persisted state)."""
    use_case = _get_use_case(use_case_id, ctx, db)
    return _lifecycle_read(use_case, db)


@router.post(
    "/{use_case_id}/lifecycle/re-evaluate", response_model=UseCaseLifecycleRead
)
def post_re_evaluate(
    use_case_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> UseCaseLifecycleRead:
    """Recomputes the full vector and moves the use case to its correct
    resting gate — advancing, un-holding, or regressing to held (design doc
    §1.1 "Manual lever"). The manual fix for stale-after-expiry state."""
    use_case = _get_use_case(use_case_id, ctx, db)
    re_evaluate(db, use_case, ctx.user_id)
    return _lifecycle_read(use_case, db)


def _authorisation_read(
    ato: DeploymentAuthorisation, use_case: UseCase,
) -> DeploymentAuthorisationRead:
    return DeploymentAuthorisationRead(
        id=ato.id,
        use_case_id=ato.use_case_id,
        assessment_id=ato.assessment_id,
        submission_round=ato.submission_round,
        tier=ato.tier,
        assessment_version=ato.assessment_version,
        authorised_by_name=ato.authorised_by_name,
        authorised_by_email=ato.authorised_by_email,
        authorised_at=ato.authorised_at,
        residual_risk_statement=ato.residual_risk_statement,
        live_state=use_case.state.value,
    )


@router.post("/{use_case_id}/authorise", response_model=DeploymentAuthorisationRead)
def post_authorise(
    use_case_id: uuid.UUID,
    payload: AuthoriseRequest,
    ctx: TenantContext = Depends(require_governance_role("authoriser")),
    db: Session = Depends(get_tenant_db),
) -> DeploymentAuthorisationRead:
    """The authoriser's act (design doc §4.2): recomputes the vector,
    act-SoD against the AIIA's approver/submitter, writes a cycle-stamped
    ATO, and transitions the use case into authorised."""
    ato = authorise_use_case(
        use_case_id, payload.residual_risk_statement, ctx, db,
    )
    use_case = _get_use_case(use_case_id, ctx, db)
    return _authorisation_read(ato, use_case)


@router.get("/{use_case_id}/authorisation", response_model=DeploymentAuthorisationRead)
def get_authorisation(
    use_case_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> DeploymentAuthorisationRead:
    """Returns the most recent ATO plus a computed live_state (design doc
    §5/NB4, inv 32) — an ATO's existence is never read as "currently
    authorised"; live_state reflects the current vector/state, e.g. `held`
    after a regression while the ATO row itself persists unchanged."""
    use_case = _get_use_case(use_case_id, ctx, db)
    ato = db.scalar(
        select(DeploymentAuthorisation)
        .where(
            DeploymentAuthorisation.use_case_id == use_case_id,
            DeploymentAuthorisation.tenant_id == ctx.tenant_id,
        )
        .order_by(DeploymentAuthorisation.authorised_at.desc())
        .limit(1)
    )
    if ato is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Use case has never been authorised",
        )
    return _authorisation_read(ato, use_case)


@approvals_router.put(
    "/vendors/{vendor_id}/approval", response_model=VendorApprovalRead
)
def put_vendor_approval(
    vendor_id: uuid.UUID,
    payload: VendorApprovalCreate,
    ctx: TenantContext = Depends(require_governance_role("authoriser")),
    db: Session = Depends(get_tenant_db),
) -> VendorApprovalRead:
    """Set/update the tenant's clearance of a vendor; fans out to every
    affected use case (design doc §6). No delete — withdrawal is a status
    change (set REJECTED/EXPIRED), preserving history."""
    if db.get(CatalogueVendor, vendor_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Vendor not found")

    approval = set_vendor_approval(
        db,
        ctx.tenant_id,
        vendor_id,
        approval_status=payload.status,
        valid_until=payload.valid_until,
        note=payload.note,
        actor_user_id=ctx.user_id,
    )
    fan_out_vendor_approval(db, ctx.tenant_id, vendor_id, ctx.user_id)
    return approval


@approvals_router.put(
    "/products/{product_id}/approval", response_model=ProductApprovalRead
)
def put_product_approval(
    product_id: uuid.UUID,
    payload: ProductApprovalCreate,
    ctx: TenantContext = Depends(require_governance_role("authoriser")),
    db: Session = Depends(get_tenant_db),
) -> ProductApprovalRead:
    """Set/update the tenant's clearance of a product; fans out to every
    affected use case."""
    if db.get(CatalogueProduct, product_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Product not found")

    approval = set_product_approval(
        db,
        ctx.tenant_id,
        product_id,
        approval_status=payload.status,
        valid_until=payload.valid_until,
        note=payload.note,
        actor_user_id=ctx.user_id,
    )
    fan_out_product_approval(db, ctx.tenant_id, product_id, ctx.user_id)
    return approval


@rollup_router.get("/{system_id}/rollup", response_model=SystemRollupRead)
def get_system_rollup(
    system_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> SystemRollupRead:
    """Per-system use cases + states + highest tier + outstanding
    obligations (REG-3) — recomputed live, never a stored/cached rollup."""
    system = db.scalar(
        select(System).where(System.id == system_id, System.tenant_id == ctx.tenant_id)
    )
    if system is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="System not found")
    return system_rollup(db, ctx.tenant_id, system)


@approvals_router.get("/portfolio", response_model=list[SystemRollupRead])
def get_portfolio(
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> list[SystemRollupRead]:
    """Tenant-wide rollup — one entry per system with at least one use case."""
    return portfolio_rollup(db, ctx.tenant_id)
