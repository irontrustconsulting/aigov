"""
Tenancy, identity and authorization.

Design notes
------------
* Cognito is the IDENTITY provider; this schema owns AUTHORIZATION.
  We store the Cognito `sub` claim on User and never store passwords.
* A User belongs to one or more Tenants via Membership, and the *role*
  lives on the Membership (a person can be an admin in one org and a
  read-only auditor in another). Do NOT model roles as Cognito groups.
* Multi-tenancy: pooled (shared DB) with tenant_id on every business
  table + Postgres RLS. Membership is the bridge that authorizes a
  Cognito-authenticated user into a given tenant.
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import String, ForeignKey, UniqueConstraint, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, uuid_pk, UserRole


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenant"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    memberships: Mapped[List["Membership"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class User(Base, TimestampMixin):
    """A human identity. Authenticated by Cognito; `cognito_sub` is the
    stable link to the Cognito user pool. Users are global; their access
    to a tenant is via Membership."""
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = uuid_pk()
    cognito_sub: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))

    memberships: Mapped[List["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Membership(Base, TimestampMixin):
    """User <-> Tenant with a role. The unit of authorization."""
    __tablename__ = "membership"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"), nullable=False,
        default=UserRole.CONTRIBUTOR,
    )

    user: Mapped["User"] = relationship(back_populates="memberships")
    tenant: Mapped["Tenant"] = relationship(back_populates="memberships")
