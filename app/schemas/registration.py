"""Schemas for the atomic registration endpoint (DM-S2)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.base import SystemLifecycleStage
from app.schemas.system import SystemDetail
from app.schemas.use_cases import ClassificationRead, UseCaseRead


class RegistrationCreate(BaseModel):
    # ---- system-stable ----
    name: str = Field(min_length=1, max_length=255)
    is_custom: bool = False
    catalogue_product_id: uuid.UUID | None = None
    operator_role_id: uuid.UUID | None = None
    hosting_model_id: uuid.UUID | None = None
    lifecycle_stage: SystemLifecycleStage | None = None
    owner_user_id: uuid.UUID | None = None
    purpose: str | None = None
    # ---- first use case ----
    title: str = Field(min_length=1, max_length=255)
    use_case_purpose: str | None = None
    context_blob: dict = Field(default_factory=dict)
    usage_context_id: uuid.UUID | None = None
    human_oversight_type_id: uuid.UUID | None = None
    data_category_ids: list[uuid.UUID] = Field(default_factory=list)
    affected_party_ids: list[uuid.UUID] = Field(default_factory=list)
    # When present, the draft is deleted in the same transaction (D-66/SV-3).
    draft_id: uuid.UUID | None = None


class RegistrationRead(BaseModel):
    system: SystemDetail
    use_case: UseCaseRead
    classification: ClassificationRead
