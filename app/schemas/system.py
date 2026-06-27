"""Schemas for system registration, intake, and prefill."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.base import LifecycleState, ProvenanceConfidence, SystemLifecycleStage


# ---------------------------------------------------------------------------
# Shared small refs (embedded in responses)
# ---------------------------------------------------------------------------

class CatalogueProductRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class CatalogueVendorRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    logo_url: str | None = None


class VocabItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    label: str


class DataCategoryOut(VocabItemOut):
    is_special_category: bool


class AffectedPartyOut(VocabItemOut):
    is_vulnerable_group: bool


class UseCaseStateSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    use_case_id: uuid.UUID
    state: LifecycleState


# ---------------------------------------------------------------------------
# System request schemas
# ---------------------------------------------------------------------------

class SystemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_custom: bool = False
    catalogue_product_id: uuid.UUID | None = None
    catalogue_vendor_id: uuid.UUID | None = None  # overridden when product present
    owner_user_id: uuid.UUID | None = None
    operator_role_id: uuid.UUID | None = None
    hosting_model_id: uuid.UUID | None = None
    lifecycle_stage: SystemLifecycleStage | None = None
    purpose: str | None = None


class SystemUpdate(BaseModel):
    """All fields optional. Link arrays replace the full set when supplied."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_custom: bool | None = None
    catalogue_product_id: uuid.UUID | None = None
    catalogue_vendor_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None
    operator_role_id: uuid.UUID | None = None
    hosting_model_id: uuid.UUID | None = None
    lifecycle_stage: SystemLifecycleStage | None = None
    purpose: str | None = None


# ---------------------------------------------------------------------------
# System response schemas
# ---------------------------------------------------------------------------

class SystemRead(BaseModel):
    """Lean list-view schema — avoids N+1 vocab label loading on GET /systems."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    is_custom: bool
    lifecycle_stage: SystemLifecycleStage | None
    created_at: datetime
    updated_at: datetime


class SystemDetail(BaseModel):
    """Full detail view — assembled by system_service.get_system_detail()."""
    id: uuid.UUID
    name: str
    is_custom: bool
    catalogue_product: CatalogueProductRef | None
    catalogue_vendor: CatalogueVendorRef | None
    owner_user_id: uuid.UUID | None
    operator_role: VocabItemOut | None
    hosting_model: VocabItemOut | None
    lifecycle_stage: SystemLifecycleStage | None
    purpose: str | None
    use_case_count: int
    use_case_lifecycle_states: list[UseCaseStateSummary]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Prefill response
# ---------------------------------------------------------------------------

class CatalogueFactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    value: dict
    source_url: str | None
    source_label: str | None
    last_checked_at: datetime | None
    provenance: ProvenanceConfidence


class PrefillResponse(BaseModel):
    catalogue_product_id: uuid.UUID | None
    facts: list[CatalogueFactOut]


# ---------------------------------------------------------------------------
# Reference product detail
# ---------------------------------------------------------------------------

class CategoryRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class EUAIActSubcategoryRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    label: str


class ProductDetailOut(BaseModel):
    id: uuid.UUID
    name: str
    logo_url: str | None = None
    vendor: CatalogueVendorRef
    categories: list[CategoryRef]
    eu_ai_act_subcategories: list[EUAIActSubcategoryRef]
