"""
Member management endpoints (v1, tenant-scoped).

POST /v1/members  -- admin creates a new tenant member (Cognito invite + membership).
GET  /v1/members  -- admin lists all members with Cognito-derived accept status.

Authorization:
* Both endpoints require require_role("admin").
* tenant_id is always pinned from the authenticated context; body values are
  ignored for anything that affects scope or identity.

RLS note: member reads are always driven from `membership` (RLS-scoped),
joined to `app_user`. Never query app_user bare — it is non-RLS and the app
role would see all tenants' users.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.context import TenantContext, get_tenant_db, require_role
from app.models.identity import Membership, User
from app.schemas.member import MemberCreate, MemberCreated, MemberListResponse, MemberRead
from app.services.cognito_helpers import get_cognito_user_status
from app.services.member_provisioning import provision_member
from app.services.provisioning import AlreadyProvisioned, ProvisioningError

router = APIRouter(prefix="/members", tags=["members"])


@router.post("", response_model=MemberCreated, status_code=status.HTTP_201_CREATED)
def create_member(
    payload: MemberCreate,
    ctx: TenantContext = Depends(require_role("admin")),
    db: Session = Depends(get_tenant_db),
) -> MemberCreated:
    """Create a new tenant member.

    Calls provision_member, which owns its own transaction (Cognito → DB →
    commit with compensation). tenant_id is taken from the authenticated
    admin's context, never from the request body.
    """
    try:
        user_id, membership_id = provision_member(
            tenant_id=ctx.tenant_id,
            email=payload.email,
            name=payload.name,
            actor_user_id=ctx.user_id,
            source="api",
        )
    except AlreadyProvisioned as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProvisioningError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return MemberCreated(user_id=user_id, membership_id=membership_id)


def _encode_cursor(created_at: datetime, membership_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{membership_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    ts, mid = raw.split("|", 1)
    return datetime.fromisoformat(ts), uuid.UUID(mid)


def _cognito_status_to_accept(cognito_status: str | None) -> str:
    if cognito_status == "CONFIRMED":
        return "accepted"
    return "pending"


@router.get("", response_model=MemberListResponse)
def list_members(
    ctx: TenantContext = Depends(require_role("admin")),
    db: Session = Depends(get_tenant_db),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
) -> MemberListResponse:
    """List all members in the caller's tenant with their accept status.

    Results are driven from `membership` (RLS-scoped) joined to `app_user` —
    never a bare app_user query. Accept status is derived from Cognito.

    Pagination: keyset cursor on (membership.created_at, membership.id).
    """
    # Build the base query: membership-driven, joined to app_user.
    # RLS on membership enforces tenant isolation in production; the explicit
    # tenant_id filter here adds defense-in-depth and makes test assertions reliable.
    stmt = (
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.tenant_id == ctx.tenant_id)
        .order_by(Membership.created_at, Membership.id)
        .limit(limit + 1)  # fetch one extra to detect next page
    )

    if cursor:
        try:
            after_ts, after_id = _decode_cursor(cursor)
        except Exception:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid cursor")
        stmt = stmt.where(
            (Membership.created_at > after_ts)
            | (
                (Membership.created_at == after_ts)
                & (Membership.id > after_id)
            )
        )

    rows = db.execute(stmt).all()

    has_next = len(rows) > limit
    rows = rows[:limit]

    items: list[MemberRead] = []
    for membership, user in rows:
        cognito_status = get_cognito_user_status(user.email)
        accept_status = _cognito_status_to_accept(cognito_status)

        if status_filter and accept_status != status_filter:
            continue

        items.append(MemberRead(
            user_id=user.id,
            membership_id=membership.id,
            email=user.email,
            name=user.display_name,
            role=membership.role.value if hasattr(membership.role, "value") else str(membership.role),
            status=accept_status,
            created_at=membership.created_at,
        ))

    next_cursor = None
    if has_next and rows:
        last_membership, _ = rows[-1]
        next_cursor = _encode_cursor(last_membership.created_at, last_membership.id)

    return MemberListResponse(items=items, next_cursor=next_cursor)
