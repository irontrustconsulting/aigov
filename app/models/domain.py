"""
Core domain: vendors, products, the catalogue, systems, use cases,
and the three inheriting approval scopes.

Key modelling decisions (from the PRD)
--------------------------------------
* CATALOGUE is global (cross-tenant): a Vendor/Product and its curated facts
  are the same for everyone — that is the moat (PRD 4.3). So CatalogueVendor /
  CatalogueProduct are NOT tenant-scoped. They are reference data you curate.
* A Tenant's actual inventory is Systems and UseCases, which ARE tenant-scoped
  and reference the global catalogue where applicable (or are custom/in-house).
* APPROVAL is layered and inheriting (PRD 4.1.4):
    - VendorApproval         (tenant + vendor)
    - ProductApproval        (tenant + product)        inherits vendor
    - use-case authorisation (the UseCase lifecycle)   inherits product
  Approvals are tenant-scoped: Acme approving a vendor says nothing about
  whether Globex has. The catalogue facts are shared; the approval decision
  is the tenant's own.
* A System is the registered entity; a UseCase is the unit of assessment.
  One System -> many UseCases. Classification + AIIA attach to the UseCase.
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import (
    String, Text, ForeignKey, Enum as SAEnum, UniqueConstraint, DateTime,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from .base import (
    Base, TimestampMixin, uuid_pk,
    ApprovalStatus, EUAIActTier, LifecycleState, ProvenanceConfidence,
)


# ---------------------------------------------------------------------------
# GLOBAL CATALOGUE (reference data, cross-tenant, curated by you)
# ---------------------------------------------------------------------------

class CatalogueVendor(Base, TimestampMixin):
    __tablename__ = "catalogue_vendor"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Curated, source-attributed vendor-level facts (certs, breach history
    # summary, financial/legal entity info). Each fact in the blob carries
    # its own provenance; see ProvenanceMixin pattern in CatalogueFact.
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    products: Mapped[List["CatalogueProduct"]] = relationship(
        back_populates="vendor", cascade="all, delete-orphan"
    )
    logo_url: Mapped[str | None] = mapped_column(Text)


class CatalogueProduct(Base, TimestampMixin):
    __tablename__ = "catalogue_product"

    id: Mapped[uuid.UUID] = uuid_pk()
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("catalogue_vendor.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(Text)
    # EU AI Act use-case taxonomy tags this product *commonly* maps to.
    # NOTE: tags inform classification but never assert the tier — tier is
    # always derived from the tenant's deployment context (PRD 4.3 CAT-3).
    taxonomy_tags: Mapped[list] = mapped_column(JSONB, default=list)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    vendor: Mapped["CatalogueVendor"] = relationship(back_populates="products")
    facts: Mapped[List["CatalogueFact"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    typical_risks: Mapped[List["CatalogueProductRisk"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class CatalogueFact(Base, TimestampMixin):
    """A single source-attributed factual attribute of a product (or vendor),
    e.g. 'data residency = EU', 'trains on customer data = no'. Provenance is
    first-class: every fact knows its source and last-checked date. When this
    prefills a tenant's assessment, the tenant confirms/amends (PRD 4.3 CAT-4)."""
    __tablename__ = "catalogue_fact"

    id: Mapped[uuid.UUID] = uuid_pk()
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("catalogue_product.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_label: Mapped[str | None] = mapped_column(String(255))  # e.g. "Adobe DPA"
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[ProvenanceConfidence] = mapped_column(
        SAEnum(ProvenanceConfidence, name="provenance_confidence"),
        default=ProvenanceConfidence.CATALOGUE_CURATED,
    )

    product: Mapped["CatalogueProduct"] = relationship(back_populates="facts")


class CatalogueProductRisk(Base):
    """Typical risks associated with a catalogue product (PRD 4.7 RSK-4),
    so selecting a product can prefill a likely risk set."""
    __tablename__ = "catalogue_product_risk"
    __table_args__ = (
        UniqueConstraint("product_id", "risk_id", name="uq_cat_product_risk"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("catalogue_product.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    risk_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("risk.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    product: Mapped["CatalogueProduct"] = relationship(back_populates="typical_risks")


# ---------------------------------------------------------------------------
# TENANT INVENTORY: systems and use cases
# ---------------------------------------------------------------------------

class System(Base, TimestampMixin):
    """The registered AI system (PRD 4.2). Either backed by a catalogue
    product (SaaS) or custom/in-house (catalogue_product_id NULL)."""
    __tablename__ = "system"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL")
    )
    # If sourced from the catalogue, link both for inheritance of approvals:
    catalogue_vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalogue_vendor.id", ondelete="SET NULL"),
        index=True,
    )
    catalogue_product_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalogue_product.id", ondelete="SET NULL"),
        index=True,
    )
    # Free metadata captured at intake (lifecycle stage, data used, etc.)
    metadata_blob: Mapped[dict] = mapped_column(JSONB, default=dict)

    use_cases: Mapped[List["UseCase"]] = relationship(
        back_populates="system", cascade="all, delete-orphan"
    )


class UseCase(Base, TimestampMixin):
    """The UNIT OF ASSESSMENT (PRD 4.1a). One System has many UseCases;
    each UseCase has exactly one AIIA, its own classification, its own
    lifecycle state, its own authorisation."""
    __tablename__ = "use_case"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    system_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("system.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text)

    # Lifecycle state (PRD 4.1.1). Transitions recorded in LifecycleTransition.
    state: Mapped[LifecycleState] = mapped_column(
        SAEnum(LifecycleState, name="lifecycle_state"),
        default=LifecycleState.REQUESTED, nullable=False, index=True,
    )
    # Current EU AI Act tier for THIS use case (PRD 4.4). Derived from context,
    # never from the product alone. Full rationale lives on Classification.
    eu_tier: Mapped[EUAIActTier] = mapped_column(
        SAEnum(EUAIActTier, name="eu_ai_act_tier"),
        default=EUAIActTier.UNCLASSIFIED, nullable=False,
    )
    # Captured deployment context (who is affected, data touched, etc.) —
    # the universal up-front capture (PRD 4.1.3 IXN-1).
    context_blob: Mapped[dict] = mapped_column(JSONB, default=dict)

    system: Mapped["System"] = relationship(back_populates="use_cases")
    classifications: Mapped[List["Classification"]] = relationship(
        back_populates="use_case", cascade="all, delete-orphan"
    )
    assessments: Mapped[List["Assessment"]] = relationship(
        back_populates="use_case", cascade="all, delete-orphan"
    )
    transitions: Mapped[List["LifecycleTransition"]] = relationship(
        back_populates="use_case", cascade="all, delete-orphan"
    )
    
    eu_ai_act_subcategory_id: Mapped[uuid.UUID | None] = mapped_column(
    PGUUID(as_uuid=True),
    ForeignKey("eu_ai_act_subcategory.id", ondelete="RESTRICT"),
    nullable=True, index=True,
)


# ---------------------------------------------------------------------------
# THREE INHERITING APPROVAL SCOPES (PRD 4.1.4)
# ---------------------------------------------------------------------------

class VendorApproval(Base, TimestampMixin):
    """Tenant's clearance of a vendor (outer gate). One per tenant+vendor."""
    __tablename__ = "vendor_approval"
    __table_args__ = (
        UniqueConstraint("tenant_id", "catalogue_vendor_id",
                         name="uq_vendor_approval"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    catalogue_vendor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalogue_vendor.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus, name="approval_status"),
        default=ApprovalStatus.NOT_STARTED, nullable=False,
    )
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Thin vendor-level diligence record (APR-5). Full workflow deferred.
    diligence_blob: Mapped[dict] = mapped_column(JSONB, default=dict)


class ProductApproval(Base, TimestampMixin):
    """Tenant's clearance of a product. Inherits vendor clearance (APR-2).
    Much of this is the ROLLUP of use-case assessment evidence (APR-4),
    so it is largely a view/aggregate rather than a separate questionnaire."""
    __tablename__ = "product_approval"
    __table_args__ = (
        UniqueConstraint("tenant_id", "catalogue_product_id",
                         name="uq_product_approval"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    catalogue_product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalogue_product.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus, name="approval_status"),
        default=ApprovalStatus.NOT_STARTED, nullable=False,
    )
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    diligence_blob: Mapped[dict] = mapped_column(JSONB, default=dict)
