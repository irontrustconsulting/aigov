"""
Platform-operator identity and RBAC authorization.

Mirrors the tenant-side philosophy in identity.py: Cognito is the IDENTITY
provider, this schema owns AUTHORIZATION. An Operator is authenticated by Cognito
(`cognito_sub`) and authorized purely through ROLES — never a Cognito group,
never a permission baked into code.

Model (textbook RBAC):

    Operator --< OperatorRole >-- Role --< RolePermission >-- Permission

An operator's EFFECTIVE permissions are the union of the permissions of the roles
they hold. require_permission() checks a permission key against that set.

A note on the word "role": the `role` TABLE here (application authorization) is a
different namespace from PostgreSQL DB roles (irontrustai_app, _provisioner, …).
DB roles say how a *connection* may touch the database; these rows say what a
*person* may do. They never meet.

Permissions reach an operator ONLY through a role — there are no direct
operator→permission grants. Direct grants are the escape hatch that quietly rots
an RBAC model; if a one-off is ever needed, you make a role for it.
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import String, ForeignKey, UniqueConstraint, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, uuid_pk, OperatorStatus


class Operator(Base, TimestampMixin):
    """A platform-staff identity. Authenticated by Cognito (operator pool);
    `cognito_sub` is the stable link. Belongs to no tenant. Authorization is via
    OperatorRole, never read from the token."""
    __tablename__ = "operator"

    id: Mapped[uuid.UUID] = uuid_pk()
    cognito_sub: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    # active | disabled. Disabling rejects the operator even while their Cognito
    # token is still technically valid — a deliberate kill-switch independent of
    # token expiry.
    status: Mapped[OperatorStatus] = mapped_column(
        SAEnum(OperatorStatus, name="operator_status"),
        nullable=False, default=OperatorStatus.ACTIVE,
    )

    # An operator's role grants. foreign_keys is explicit because OperatorRole
    # has TWO FKs back to operator (operator_id and granted_by_id).
    role_links: Mapped[List["OperatorRole"]] = relationship(
        back_populates="operator",
        cascade="all, delete-orphan",
        foreign_keys="OperatorRole.operator_id",
    )


class Permission(Base, TimestampMixin):
    """A discrete, checkable capability, identified by a stable `key`
    (e.g. "tenant:provision"). The key is what require_permission() checks and
    what code references by literal, so Permission rows are DEPLOYMENT DATA seeded
    via migration — not created at runtime."""
    __tablename__ = "permission"

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(String(255))

    role_links: Mapped[List["RolePermission"]] = relationship(
        back_populates="permission", cascade="all, delete-orphan"
    )


class Role(Base, TimestampMixin):
    """A named bundle of permissions (e.g. "provisioner"). Operators are granted
    roles; permissions reach an operator only through a role. Base roles are
    seeded via migration alongside permissions."""
    __tablename__ = "role"

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(String(255))

    permission_links: Mapped[List["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    operator_links: Mapped[List["OperatorRole"]] = relationship(
        back_populates="role"
    )


class RolePermission(Base, TimestampMixin):
    """role <-> permission: which capabilities a role grants."""
    __tablename__ = "role_permission"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # CASCADE: removing a role removes its permission links.
    role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("role.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # RESTRICT: a permission still granted by any role cannot be deleted — the
    # catalogue can't be pulled out from under a live role.
    permission_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("permission.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    role: Mapped["Role"] = relationship(back_populates="permission_links")
    permission: Mapped["Permission"] = relationship(back_populates="role_links")


class OperatorRole(Base, TimestampMixin):
    """operator <-> role, with grant lineage. The unit of operator authorization —
    the platform-plane analogue of Membership. Grant time is `created_at` (from
    TimestampMixin); `granted_by` records who made the grant."""
    __tablename__ = "operator_role"
    __table_args__ = (
        UniqueConstraint("operator_id", "role_id", name="uq_operator_role"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # CASCADE: deleting an operator cleans up their role grants.
    operator_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("operator.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # RESTRICT: a role still assigned to an operator cannot be deleted.
    role_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("role.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    # Who granted this role. NULL = system/genesis bootstrap (no prior operator).
    # SET NULL: keep the grant record even if the granting operator is later removed.
    granted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("operator.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    operator: Mapped["Operator"] = relationship(
        back_populates="role_links", foreign_keys=[operator_id]
    )
    role: Mapped["Role"] = relationship(back_populates="operator_links")
    granted_by: Mapped["Operator | None"] = relationship(foreign_keys=[granted_by_id])