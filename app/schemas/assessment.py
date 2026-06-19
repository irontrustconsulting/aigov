"""Schemas for the AIIA core sprint (sprints/SPRINT_AIIA.md).

Provenance is never an accepted input field on any schema here — it is
always server-derived (design doc §4 invariant). Mutating-response schemas
expose `lock_version` so the client can build the next `If-Match` header.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.base import (
    AssessmentStatus,
    AssessmentType,
    CoverageStatus,
    EUAIActTier,
    ProvenanceConfidence,
    SectionApplicability,
)


class AssessmentItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    assessment_id: uuid.UUID
    section_key: str | None
    risk_id: uuid.UUID | None
    prompt: str | None
    response: str | None
    likelihood: int | None
    severity: int | None
    residual_likelihood: int | None
    residual_severity: int | None
    mitigation_plan: str | None
    provenance: ProvenanceConfidence
    selection_basis: str | None
    source_ref: str | None
    lock_version: int
    created_at: datetime
    updated_at: datetime
    # Set only on items surfaced into an AIIA's detail read from a feeder
    # (Phase B propagation, design doc §5.6) — None for native AIIA items
    # and for a feeder's own GET /assessments/{feeder_id} view. Computed at
    # read time, never stored; section_key above is also re-keyed to the
    # AIIA's target section in that case, not the feeder's own section_key.
    source_assessment_id: uuid.UUID | None = None
    source_type: AssessmentType | None = None


class AssessmentItemCreate(BaseModel):
    """Instantiates a section from the template (required or recommended)
    by section_key. response is optional — most callers create-then-amend."""
    section_key: str = Field(min_length=1, max_length=120)
    response: str | None = None


class AssessmentItemAmend(BaseModel):
    """PATCH body — authoring fields only. A request with every field None
    is a content-less no-op (no event, no provenance change, design doc §4)."""
    response: str | None = None
    likelihood: int | None = None
    severity: int | None = None
    residual_likelihood: int | None = None
    residual_severity: int | None = None
    mitigation_plan: str | None = None


class ControlLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    control_id: uuid.UUID
    coverage: CoverageStatus


class ControlLinkCreate(BaseModel):
    control_id: uuid.UUID
    coverage: CoverageStatus = CoverageStatus.PARTIAL


class EvidenceLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    evidence_id: uuid.UUID


class EvidenceLinkCreate(BaseModel):
    evidence_id: uuid.UUID


class AssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    use_case_id: uuid.UUID
    type: AssessmentType
    parent_aiia_id: uuid.UUID | None
    status: AssessmentStatus
    version: int
    tier_snapshot: EUAIActTier
    classification_version: int
    is_current: bool
    lock_version: int
    created_at: datetime
    updated_at: datetime


class AssessmentDetail(AssessmentRead):
    items: list[AssessmentItemRead] = Field(default_factory=list)


class SectionRead(BaseModel):
    """A tier-scoped section template row, joined against whether it has
    already been instantiated as an item on this assessment."""
    section_key: str
    title: str
    applicability: SectionApplicability
    prompt: str | None
    iso_42005_clause: str | None
    instantiated: bool
    item_id: uuid.UUID | None = None


class FeederCreate(BaseModel):
    """type must be FRIA, DPIA, or MODEL_RISK — AIIA is rejected (422)."""
    type: AssessmentType


class FeederRecommendationRead(BaseModel):
    """Strong default + shown reasoning for one feeder type (design doc
    §5.3) — the user confirms by creating; the platform never auto-creates."""
    type: AssessmentType
    applicability: SectionApplicability
    basis: str
    exists: bool
