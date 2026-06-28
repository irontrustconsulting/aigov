"""
Draft-registration endpoints (DM-S3, D-66, INV-79).

Four endpoints under /v1/draft-registrations, all gated gov:system_owner.
RLS isolates by tenant; every handler additionally filters owner_user_id
so two users in the same tenant cannot cross-read each other's drafts (DF-D3-4).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_db, require_governance_role
from app.models.domain import DraftRegistration
from app.schemas.draft_registration import DraftRegistrationPatch, DraftRegistrationRead

router = APIRouter(prefix="/draft-registrations", tags=["draft-registrations"])


@router.post(
    "",
    response_model=DraftRegistrationRead,
    status_code=status.HTTP_200_OK,
)
def get_or_create_draft(
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> DraftRegistrationRead:
    """SELECT-first get-or-create the caller's active draft (DF-D3-5).

    Returns the existing draft if one exists, else creates and returns a new
    one. Idempotent — always 200; the unique constraint is the backstop.
    """
    existing = db.scalar(
        select(DraftRegistration).where(
            DraftRegistration.tenant_id == ctx.tenant_id,
            DraftRegistration.owner_user_id == ctx.user_id,
        )
    )
    if existing:
        return DraftRegistrationRead.model_validate(existing)

    draft = DraftRegistration(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        owner_user_id=ctx.user_id,
        draft_blob={},
    )
    db.add(draft)
    db.flush()
    return DraftRegistrationRead.model_validate(draft)


@router.get(
    "/active",
    status_code=status.HTTP_200_OK,
)
def get_active_draft(
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> Response:
    """Return the caller's active draft or 204 if none exists (DF-D3-4)."""
    draft = db.scalar(
        select(DraftRegistration).where(
            DraftRegistration.tenant_id == ctx.tenant_id,
            DraftRegistration.owner_user_id == ctx.user_id,
        )
    )
    if not draft:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return Response(
        content=DraftRegistrationRead.model_validate(draft).model_dump_json(),
        media_type="application/json",
        status_code=status.HTTP_200_OK,
    )


@router.patch(
    "/{draft_id}",
    response_model=DraftRegistrationRead,
    status_code=status.HTTP_200_OK,
)
def patch_draft(
    draft_id: uuid.UUID,
    payload: DraftRegistrationPatch,
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> DraftRegistrationRead:
    """Replace draft_blob (last-write-wins, DF-D3-6). Owner-filtered (DF-D3-4)."""
    draft = db.scalar(
        select(DraftRegistration).where(
            DraftRegistration.id == draft_id,
            DraftRegistration.owner_user_id == ctx.user_id,
        )
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    draft.draft_blob = payload.draft_blob
    db.flush()
    return DraftRegistrationRead.model_validate(draft)


@router.delete(
    "/{draft_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def discard_draft(
    draft_id: uuid.UUID,
    ctx: TenantContext = Depends(require_governance_role("system_owner")),
    db: Session = Depends(get_tenant_db),
) -> Response:
    """Discard the draft. Owner-filtered (DF-D3-4)."""
    draft = db.scalar(
        select(DraftRegistration).where(
            DraftRegistration.id == draft_id,
            DraftRegistration.owner_user_id == ctx.user_id,
        )
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    db.delete(draft)
    db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
