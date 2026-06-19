"""
Evidence repository endpoints (v1, tenant plane) —
sprints/SPRINT_EVIDENCE_REPOSITORY.md, Phase A.

Gating: list/detail -> any of the five governance roles (the auditor
consumes evidence read-only); upload/delete -> {system_owner, contributor}
(evidence provision is a 1st-line act, PRD 4.9.1).

POST /v1/evidence deliberately does NOT depend on get_tenant_db — the
service owns its own short-lived sessions so the slow S3 put never runs
with a DB connection held (see evidence_service._tenant_session).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.context import (
    TenantContext,
    get_tenant_context,
    get_tenant_db,
    require_governance_role,
)
from app.schemas.evidence import (
    EvidenceDetailRead,
    EvidenceListItem,
    EvidenceListResponse,
    EvidenceRead,
)
from app.services import evidence_service as svc

router = APIRouter(prefix="/evidence", tags=["evidence"])

_ALL_GOVERNANCE_ROLES = (
    "system_owner", "contributor", "reviewer", "authoriser", "auditor",
)
_WRITE_ROLES = ("system_owner", "contributor")


@router.post("", response_model=EvidenceRead, status_code=status.HTTP_201_CREATED)
def upload_evidence(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    ctx: TenantContext = Depends(get_tenant_context),
) -> EvidenceRead:
    ev = svc.upload_evidence(ctx, file, title)
    return EvidenceRead.model_validate(ev)


@router.get("", response_model=EvidenceListResponse)
def list_evidence(
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
) -> EvidenceListResponse:
    rows, next_cursor = svc.list_evidence(ctx, db, cursor=cursor, limit=limit)
    items = [
        EvidenceListItem(
            **EvidenceRead.model_validate(ev).model_dump(), link_count=count,
        )
        for ev, count in rows
    ]
    return EvidenceListResponse(items=items, next_cursor=next_cursor)


@router.get("/{evidence_id}", response_model=EvidenceDetailRead)
def get_evidence(
    evidence_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_ALL_GOVERNANCE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> EvidenceDetailRead:
    ev, url = svc.get_evidence(ctx, db, evidence_id)
    return EvidenceDetailRead(
        **EvidenceRead.model_validate(ev).model_dump(), download_url=url,
    )


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_evidence(
    evidence_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role(*_WRITE_ROLES)),
    db: Session = Depends(get_tenant_db),
) -> None:
    svc.delete_evidence(ctx, db, evidence_id)
