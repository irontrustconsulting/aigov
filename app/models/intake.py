"""
Controlled-vocabulary reference tables and use-case link tables.

Reference tables (EUOperatorRole, HostingModel, UsageContext,
HumanOversightType, DataCategory, AffectedParty) are GLOBAL — no tenant_id,
no RLS. Tenants select from them; they cannot create vocabulary entries.

Link tables (UseCaseDataCategory, UseCaseAffectedParty) are TENANT-SCOPED
with tenant_id + DB-enforced RLS (D-64/INV-77). Use-distinguishing context
lives at use-case level (D-63/INV-76).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, uuid_pk


# ---------------------------------------------------------------------------
# REFERENCE VOCABULARY TABLES (global, no tenant_id, no RLS)
# ---------------------------------------------------------------------------

class EUOperatorRole(Base, TimestampMixin):
    """Legal posture of the deploying organisation under EU AI Act Art. 3.
    Named eu_operator_role to avoid collision with the platform RBAC
    operator_role join table."""
    __tablename__ = "eu_operator_role"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    framework_ref: Mapped[str | None] = mapped_column(String(120))


class HostingModel(Base, TimestampMixin):
    """Where the AI system runs (cloud SaaS, self-hosted, on-premise, …)."""
    __tablename__ = "hosting_model"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    framework_ref: Mapped[str | None] = mapped_column(String(120))


class UsageContext(Base, TimestampMixin):
    """Who is exposed to the AI system (internal, employee-facing, …)."""
    __tablename__ = "usage_context"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    framework_ref: Mapped[str | None] = mapped_column(String(120))


class HumanOversightType(Base, TimestampMixin):
    """Level of human control in the loop (EU AI Act Art. 14)."""
    __tablename__ = "human_oversight_type"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    framework_ref: Mapped[str | None] = mapped_column(String(120))


class DataCategory(Base, TimestampMixin):
    """Personal data category processed by the AI system.
    is_special_category=True → GDPR Art. 9 / EU AI Act heightened duty."""
    __tablename__ = "data_category"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    framework_ref: Mapped[str | None] = mapped_column(String(120))
    is_special_category: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AffectedParty(Base, TimestampMixin):
    """Party affected by the AI system.
    is_vulnerable_group=True → EU AI Act Art. 27 heightened duty."""
    __tablename__ = "affected_party"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    framework_ref: Mapped[str | None] = mapped_column(String(120))
    is_vulnerable_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


# ---------------------------------------------------------------------------
# LINK TABLES (tenant-scoped, tenant_id + RLS — D-64/INV-77)
# ---------------------------------------------------------------------------

class UseCaseDataCategory(Base):
    """Many-to-many: use_case ↔ data_category.
    Tenant-scoped with DB-enforced RLS (D-64/INV-77)."""
    __tablename__ = "use_case_data_category"
    __table_args__ = (
        UniqueConstraint("use_case_id", "data_category_id", name="uq_use_case_data_category"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    use_case_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("use_case.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    data_category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("data_category.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    data_category: Mapped["DataCategory"] = relationship()


class UseCaseAffectedParty(Base):
    """Many-to-many: use_case ↔ affected_party.
    Tenant-scoped with DB-enforced RLS (D-64/INV-77)."""
    __tablename__ = "use_case_affected_party"
    __table_args__ = (
        UniqueConstraint("use_case_id", "affected_party_id", name="uq_use_case_affected_party"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    use_case_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("use_case.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    affected_party_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("affected_party.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    affected_party: Mapped["AffectedParty"] = relationship()
