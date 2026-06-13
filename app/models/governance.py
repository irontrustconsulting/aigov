"""
Tenant governance role model — catalogue, SoD conflict matrix, assignments.

Three tables, two scopes:

  PLATFORM REFERENCE (no tenant_id, no RLS — like operator role/permission):
    governance_role         — the five governance roles (system_owner, contributor,
                              reviewer, authoriser, auditor).
    governance_role_conflict — the SoD conflict matrix. One row per conflicting
                              UNORDERED pair, canonical ordering role_a_id < role_b_id
                              enforced by a DB check constraint to prevent symmetric
                              duplicates. The matrix is policy as data — never hardcode
                              conflict logic in application code.

  TENANT DATA (tenant_id, RLS by app.current_tenant):
    governance_role_assignment — one row per member×role grant, within a tenant.
                              Unique (tenant_id, membership_id, governance_role_id).

Object-scope seam: governance_role_assignment is the ONLY home of governance
grants. The future per-object scope is additive: a nullable scope_id column on
this table (NULL = tenant-wide, preserving every existing grant). Do not add it
now; the shape is chosen to not foreclose it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from .identity import Membership


class GovernanceRole(Base, TimestampMixin):
    """Platform reference: the governance role catalogue.
    Seeded via migration; never created at runtime."""
    __tablename__ = "governance_role"

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # 1 = first line (system_owner, contributor)
    # 2 = second line (reviewer, authoriser)
    # 3 = third line (auditor)
    line_of_defence: Mapped[int] = mapped_column(Integer, nullable=False)

    conflict_a_links: Mapped[list[GovernanceRoleConflict]] = relationship(
        back_populates="role_a",
        foreign_keys="GovernanceRoleConflict.role_a_id",
    )
    conflict_b_links: Mapped[list[GovernanceRoleConflict]] = relationship(
        back_populates="role_b",
        foreign_keys="GovernanceRoleConflict.role_b_id",
    )
    assignment_links: Mapped[list[GovernanceRoleAssignment]] = relationship(
        back_populates="governance_role",
    )


class GovernanceRoleConflict(Base):
    """Platform reference: the SoD conflict matrix.
    One row per conflicting UNORDERED pair. Canonical ordering (role_a_id <
    role_b_id as UUID bytes) is enforced by the DB check constraint below —
    a symmetric duplicate (b, a) is rejected at the constraint level.
    Seeded via migration alongside the role catalogue."""
    __tablename__ = "governance_role_conflict"
    __table_args__ = (
        UniqueConstraint("role_a_id", "role_b_id", name="uq_governance_role_conflict"),
        # Canonical ordering prevents symmetric duplicates without application
        # logic: the DB rejects any row where role_a_id >= role_b_id.
        CheckConstraint(
            "role_a_id < role_b_id", name="ck_governance_role_conflict_canonical"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    role_a_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("governance_role.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    role_b_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("governance_role.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    role_a: Mapped[GovernanceRole] = relationship(
        back_populates="conflict_a_links", foreign_keys=[role_a_id]
    )
    role_b: Mapped[GovernanceRole] = relationship(
        back_populates="conflict_b_links", foreign_keys=[role_b_id]
    )


class GovernanceRoleAssignment(Base):
    """Tenant data: a governance role grant for one member within a tenant.
    Under RLS scoped by app.current_tenant. granted_at is set server-side."""
    __tablename__ = "governance_role_assignment"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "membership_id", "governance_role_id",
            name="uq_governance_role_assignment",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("membership.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    governance_role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("governance_role.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    # NULL = system/provisioning bootstrap; SET NULL to retain the grant record
    # if the granting admin's membership is later removed.
    granted_by_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("membership.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    governance_role: Mapped[GovernanceRole] = relationship(
        back_populates="assignment_links",
    )
    membership: Mapped[Membership] = relationship(  # type: ignore[name-defined]
        foreign_keys=[membership_id],
    )
    granted_by: Mapped[Membership | None] = relationship(  # type: ignore[name-defined]
        foreign_keys=[granted_by_membership_id],
    )
