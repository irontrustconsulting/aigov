"""
Controlled vocabularies / taxonomies (global reference data — no RLS).

Two distinct vocabularies plus the bridge between them:

  USER-FACING (familiar business language — drives the registration wizard):
    ProductCategory          hierarchical (self-referencing) categories the
                             wizard drills through; a product belongs to MANY
                             via ProductCategoryMembership.

  GOVERNANCE (EU AI Act aligned — anchors the whole assessment):
    EUAIActCategory          organisational grouping. No tier here.
    EUAIActSubcategory       the specific regulated practice. CARRIES the tier
                             (fixed, essentially by law). The anchor a use case
                             points at.

  BRIDGE (the translation — the core product idea):
    ProductCategoryEUMapping product category -> EU AI Act subcategory, M:N
                             with an is_primary default. Resolving a user's
                             familiar product-category choice through this
                             yields the subcategory, whose tier becomes the use
                             case's PROPOSED tier (confirmed later in
                             classification).

All of these are global reference data (cross-tenant), like risk / control /
catalogue: no tenant_id, no RLS. Seeded via YAML loaders.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    String, Text, Boolean, ForeignKey, Enum as SAEnum, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, uuid_pk, EUAIActTier

if TYPE_CHECKING:
    # Imported for type-checkers only (avoids any runtime circular import);
    # SQLAlchemy resolves the string class names via its registry at runtime.
    from .domain import CatalogueProduct, UseCase  # noqa: F401


# ---------------------------------------------------------------------------
# Governance vocabulary (EU AI Act aligned)
# ---------------------------------------------------------------------------

class EUAIActCategory(Base, TimestampMixin):
    """EU AI Act use-case category — organisational grouping only.
    The tier lives on the subcategory, not here."""
    __tablename__ = "eu_ai_act_category"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    subcategories: Mapped[list["EUAIActSubcategory"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class EUAIActSubcategory(Base, TimestampMixin):
    """The specific regulated practice. THIS is where the EU AI Act tier is
    fixed. A use case anchors to one of these; its tier becomes the proposed
    tier for classification."""
    __tablename__ = "eu_ai_act_subcategory"

    id: Mapped[uuid.UUID] = uuid_pk()
    category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("eu_ai_act_category.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Reuses the SAME Postgres enum type as use_case.eu_tier / classification.tier
    # (one logical enum, one type — name must match exactly).
    tier: Mapped[EUAIActTier] = mapped_column(
        SAEnum(EUAIActTier, name="eu_ai_act_tier"), nullable=False, index=True,
    )

    category: Mapped["EUAIActCategory"] = relationship(back_populates="subcategories")
    eu_mappings: Mapped[list["ProductCategoryEUMapping"]] = relationship(
        back_populates="eu_ai_act_subcategory", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# User-facing vocabulary (product taxonomy)
# ---------------------------------------------------------------------------

class ProductCategory(Base, TimestampMixin):
    """User-facing product category (familiar business language). Hierarchical
    via self-referencing parent_id, so the wizard can drill at whatever depth
    the taxonomy needs (category -> subcategory -> use-case)."""
    __tablename__ = "product_category"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("product_category.id", ondelete="SET NULL"),
        index=True,
    )

    # Self-referential hierarchy. remote_side marks the "one" side (the parent).
    parent: Mapped["ProductCategory | None"] = relationship(
        "ProductCategory", remote_side="ProductCategory.id", back_populates="children"
    )
    children: Mapped[list["ProductCategory"]] = relationship(
        "ProductCategory", back_populates="parent"
    )

    memberships: Mapped[list["ProductCategoryMembership"]] = relationship(
        back_populates="product_category", cascade="all, delete-orphan"
    )
    eu_mappings: Mapped[list["ProductCategoryEUMapping"]] = relationship(
        back_populates="product_category", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Association objects
# ---------------------------------------------------------------------------

class ProductCategoryMembership(Base):
    """M:N — a catalogue product belongs to one or more product categories.
    (One product can surface under several familiar groupings.)"""
    __tablename__ = "product_category_membership"
    __table_args__ = (
        UniqueConstraint(
            "catalogue_product_id", "product_category_id",
            name="uq_product_category_membership",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    catalogue_product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("catalogue_product.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("product_category.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    product_category: Mapped["ProductCategory"] = relationship(back_populates="memberships")
    # No relationship back to CatalogueProduct here, to keep cross-module
    # coupling minimal. Add `categories`/`memberships` on CatalogueProduct later
    # if you want to navigate product -> categories in code.


class ProductCategoryEUMapping(Base):
    """BRIDGE: product category -> EU AI Act subcategory (M:N, with a primary
    default). The primary mapping's subcategory yields the proposed tier when a
    user picks this product category in the wizard."""
    __tablename__ = "product_category_eu_mapping"
    __table_args__ = (
        UniqueConstraint(
            "product_category_id", "eu_ai_act_subcategory_id",
            name="uq_product_category_eu_mapping",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    product_category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("product_category.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    eu_ai_act_subcategory_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("eu_ai_act_subcategory.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # The proposed default for this product category. At most one primary per
    # product category — enforced by a hand-added partial unique index in the
    # migration (see migration notes), not expressible as a column constraint.
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    product_category: Mapped["ProductCategory"] = relationship(back_populates="eu_mappings")
    eu_ai_act_subcategory: Mapped["EUAIActSubcategory"] = relationship(back_populates="eu_mappings")