"""
API schemas for reference-data reads consumed by the frontend (the
registration wizard's drill-down, governance taxonomy display, etc.).

Read-only shapes for now — these tables are curated reference data, maintained
by seed/admin, not created through these endpoints.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class ProductCategoryRead(BaseModel):
    """A user-facing product category (wizard drill-down node)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    parent_id: uuid.UUID | None = None


class VendorRead(BaseModel):
    """A catalogue vendor (a step in the wizard funnel)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    logo_url: str | None = None


class ProductRead(BaseModel):
    """A catalogue product (the wizard's destination — a specific system)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    vendor_id: uuid.UUID
    logo_url: str | None = None


class EUAIActSubcategoryRead(BaseModel):
    """A governance subcategory — carries the tier."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    category_id: uuid.UUID
    tier: str   # serialized from the EUAIActTier enum