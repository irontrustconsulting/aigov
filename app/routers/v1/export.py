"""
Export / audit pack (v1, tenant plane). Read-assembled + one disclosure
write (`export.generated`) — PRD §4.10 EXP-1/EXP-1a.

  GET /v1/systems/{id}/export                      system pack
  GET /v1/use-cases/{id}/export                     use-case pack
  GET /v1/use-cases/{id}/authorisation/document     ATO basis document
  GET /v1/export?framework=                         framework pack

Every route depends only on `get_tenant_context` (no `get_tenant_db`) — the
export service owns its own REPEATABLE READ session and runs the
governance-role gate inside it (see app/services/export_service.py
`_export_session`), the same shape evidence upload uses to avoid holding a
request-scoped session open for the whole request.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.auth.context import TenantContext, get_tenant_context
from app.models.base import Framework
from app.schemas.export import (
    AtoDocumentRead,
    FrameworkExportRead,
    SystemExportRead,
    UseCaseExportRead,
)
from app.services.export_service import (
    build_ato_document,
    build_framework_export,
    build_system_export,
    build_use_case_export,
)

router = APIRouter(tags=["export"])


@router.get("/systems/{system_id}/export", response_model=SystemExportRead)
def get_system_export(
    system_id: uuid.UUID,
    framework: Framework | None = None,
    ctx: TenantContext = Depends(get_tenant_context),
) -> SystemExportRead:
    return build_system_export(ctx, system_id, framework=framework)


@router.get("/use-cases/{use_case_id}/export", response_model=UseCaseExportRead)
def get_use_case_export(
    use_case_id: uuid.UUID,
    framework: Framework | None = None,
    ctx: TenantContext = Depends(get_tenant_context),
) -> UseCaseExportRead:
    return build_use_case_export(ctx, use_case_id, framework=framework)


@router.get(
    "/use-cases/{use_case_id}/authorisation/document", response_model=AtoDocumentRead
)
def get_ato_document(
    use_case_id: uuid.UUID,
    round: int | None = None,
    ctx: TenantContext = Depends(get_tenant_context),
) -> AtoDocumentRead:
    return build_ato_document(ctx, use_case_id, round=round)


@router.get("/export", response_model=FrameworkExportRead)
def get_framework_export(
    framework: Framework,
    ctx: TenantContext = Depends(get_tenant_context),
) -> FrameworkExportRead:
    return build_framework_export(ctx, framework)
