"""
Control coverage view (v1, tenant plane). Read-only — PRD §4.6 CTL-3.

  GET /v1/coverage                       tenant-wide coverage matrix
  GET /v1/systems/{id}/coverage          per-system coverage matrix
  GET /v1/assessments/{id}/coverage      per-AIIA coverage matrix (422 on a
                                          feeder id)
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_db, require_governance_role
from app.models.base import Framework
from app.schemas.coverage import CoverageMatrixRead
from app.services.coverage_service import compute_coverage

router = APIRouter(tags=["coverage"])

_ALL_GOVERNANCE_ROLES = (
    "system_owner",
    "contributor",
    "reviewer",
    "authoriser",
    "auditor",
)


@router.get("/coverage", response_model=CoverageMatrixRead)
def get_tenant_coverage(
    framework: Framework | None = None,
    include_unapproved: bool = False,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> CoverageMatrixRead:
    return compute_coverage(
        db,
        tenant_id=ctx.tenant_id,
        scope="tenant",
        scope_id=None,
        framework=framework,
        include_unapproved=include_unapproved,
    )


@router.get("/systems/{system_id}/coverage", response_model=CoverageMatrixRead)
def get_system_coverage(
    system_id: uuid.UUID,
    framework: Framework | None = None,
    include_unapproved: bool = False,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> CoverageMatrixRead:
    return compute_coverage(
        db,
        tenant_id=ctx.tenant_id,
        scope="system",
        scope_id=system_id,
        framework=framework,
        include_unapproved=include_unapproved,
    )


@router.get("/assessments/{assessment_id}/coverage", response_model=CoverageMatrixRead)
def get_assessment_coverage(
    assessment_id: uuid.UUID,
    framework: Framework | None = None,
    include_unapproved: bool = False,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> CoverageMatrixRead:
    return compute_coverage(
        db,
        tenant_id=ctx.tenant_id,
        scope="assessment",
        scope_id=assessment_id,
        framework=framework,
        include_unapproved=include_unapproved,
    )
