"""
Evidence, audit trail, and lifecycle transitions.

Decisions
---------
* EVIDENCE FILES live in S3; Postgres holds the POINTER + integrity hash
  (PRD: evidence artifacts -> S3, queryable records -> Postgres). Turn on
  S3 bucket versioning; store the object version id + sha256 so an artifact
  can be proven unaltered. Never store the bytes in Postgres.
* AUDITEVENT is the append-only compliance trail (EVD-2). It is INSERT-ONLY:
  no updates, no deletes (enforce with a Postgres trigger / revoked perms +
  RLS; see migration notes). Every state transition, approval, and override
  writes a row here. This is distinct from TimestampMixin convenience fields.
* LIFECYCLETRANSITION records each state machine move for a use case
  (who/what/when/why), so the lifecycle itself is fully traceable and the
  status UI (IXN-4) can show "why are we here / what's next".
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    String, Text, ForeignKey, Enum as SAEnum, DateTime, Integer, func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from .base import Base, TimestampMixin, uuid_pk, LifecycleState

from sqlalchemy.orm import Mapped, mapped_column, relationship


class Evidence(Base, TimestampMixin):
    """A pointer to an evidence artifact stored in S3, plus integrity data.
    Reusable across assessment items / controls (PRD 4.8)."""
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # S3 location:
    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    s3_version_id: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    # Integrity: prove the artifact has not been altered.
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL")
    )
    # Freshness/expiry flag support (EVD-4):
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    """APPEND-ONLY compliance audit trail. Insert only — never update/delete.
    Use a dedicated DB role with no UPDATE/DELETE on this table, plus a
    trigger that raises on UPDATE/DELETE, to enforce immutability in the DB,
    not just in app code."""
    __tablename__ = "audit_event"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    # Immutable wall-clock; set server-side, not by the client.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app_user.id", ondelete="RESTRICT")
    )
    # e.g. "classification.overridden", "use_case.state_changed",
    # "assessment.approved", "evidence.added"
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    # Polymorphic target: which entity this concerns.
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), index=True)
    # Before/after for overrides and edits (the "tracked deviation" of 1.5).
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    source_ip: Mapped[str | None] = mapped_column(INET)


class LifecycleTransition(Base):
    """One move of a use case through the state machine (PRD 4.1.1).
    Append-only in spirit; also mirrored into AuditEvent."""
    __tablename__ = "lifecycle_transition"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    use_case_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("use_case.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    from_state: Mapped[LifecycleState | None] = mapped_column(
        SAEnum(LifecycleState, name="lifecycle_state")
    )
    to_state: Mapped[LifecycleState] = mapped_column(
        SAEnum(LifecycleState, name="lifecycle_state"), nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL")
    )
    # Why the transition fired (e.g. "all gates satisfied", "prohibited
    # practice detected", "vendor not cleared") — feeds the status UI (IXN-4).
    reason: Mapped[str | None] = mapped_column(Text)
    # If a background worker drove it (IXN-2/5) vs a user action.
    triggered_by: Mapped[str | None] = mapped_column(String(60))
    use_case: Mapped["UseCase"] = relationship(back_populates="transitions")
