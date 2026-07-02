"""Schemas for use-case registration and EU AI Act classification."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.base import ClassificationStatus, EUAIActTier, LifecycleState
from app.schemas.system import AffectedPartyOut, DataCategoryOut, VocabItemOut


class UseCaseCreate(BaseModel):
    system_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    context_blob: dict = Field(default_factory=dict)
    # Use-distinguishing context (D-63/INV-76) — relocated from system in DM-S1
    usage_context_id: uuid.UUID | None = None
    human_oversight_type_id: uuid.UUID | None = None
    data_category_ids: list[uuid.UUID] = Field(default_factory=list)
    affected_party_ids: list[uuid.UUID] = Field(default_factory=list)


class UseCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    system_id: uuid.UUID
    title: str
    state: LifecycleState
    eu_tier: EUAIActTier
    # Use-distinguishing context (resolved on read; populated by the router)
    usage_context: VocabItemOut | None = None
    human_oversight_type: VocabItemOut | None = None
    data_categories: list[DataCategoryOut] = Field(default_factory=list)
    affected_parties: list[AffectedPartyOut] = Field(default_factory=list)


class ClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    use_case_id: uuid.UUID
    tier: EUAIActTier
    rationale: str
    version: int
    is_current: bool
    overridden: bool
    proposed_tier: EUAIActTier | None
    basis_subcategory_code: str | None
    basis_legal_ref: str | None
    status: ClassificationStatus
    requires_context: bool = False

    @classmethod
    def from_orm_with_flag(cls, obj) -> ClassificationRead:
        data = cls.model_validate(obj)
        data.requires_context = obj.tier == EUAIActTier.REQUIRES_CONTEXT
        return data


class UseCaseWithClassification(BaseModel):
    use_case: UseCaseRead
    classification: ClassificationRead


class OverrideRequest(BaseModel):
    """Structured override — tier and subcategory must be explicit choices,
    never free-typed strings, to preserve the §1.5 tracked-deviation contract."""
    tier: EUAIActTier
    subcategory_code: str = Field(
        min_length=1,
        max_length=80,
        description="Must match an existing eu_ai_act_subcategory.code",
    )
    justification: str | None = None
