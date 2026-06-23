"""
Platform-plane audit trail.

Separate from the tenant-plane audit_event table — platform operator actions
have no tenant_id at write time and must not pollute the tenant compliance log.
Append-only: the writer roles hold INSERT + SELECT (SELECT needed for
    INSERT ... RETURNING); a DB trigger enforces no UPDATE/DELETE.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, uuid_pk


class PlatformAuditEvent(Base):
    """Append-only record of every privileged platform-operator action.

    actor_sub / actor_email are denormalised from the operator row at write
    time so the record survives if the operator is later deleted or disabled.
    No FK to operator — evidence must be immutable and self-contained.
    """
    __tablename__ = "platform_audit_event"

    id: Mapped[uuid.UUID] = uuid_pk()
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    # Verified operator identity — from the resolved CurrentOperator, never
    # self-asserted. NULL only for the genesis bootstrap (first create-operator).
    actor_sub: Mapped[str | None] = mapped_column(String(255))
    actor_email: Mapped[str | None] = mapped_column(String(320))
    # Action key — e.g. PROVISION_TENANT, CREATE_OPERATOR
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    # Which kind of entity was created / affected
    target_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # UUID of the created/affected entity (nullable: not all actions have one yet)
    target_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    # Human-readable reference for quick log scanning without joins
    target_ref: Mapped[str | None] = mapped_column(String(255))
    # Extra context: org name, role granted, etc.
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # "http" | "cli"
    source: Mapped[str] = mapped_column(String(20), nullable=False)
