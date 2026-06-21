"""Schemas for the control coverage view (sprints/SPRINT_APPLICABILITY.md,
Sprint 7a). All response-only — coverage is recomputed per request, never
persisted (D1), so none of these carry `from_attributes`/ORM binding.

`verdict` fields are plain `str`, not `CoverageStatus`: the rolled-up
UNADDRESSED value has no DB enum label (D6) — binding it to the typed
column's enum would be wrong.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.base import AssessmentStatus, Framework


class ContributingRefRead(BaseModel):
    item_id: uuid.UUID
    assessment_id: uuid.UUID
    governing_status: AssessmentStatus


class FrameworkMappingRead(BaseModel):
    framework: Framework
    clause_ref: str


class CoverageBreakdownRead(BaseModel):
    satisfied: int
    partial: int
    open: int
    # SATISFIED links downgraded to effective PARTIAL by
    # require_evidence_for_satisfied (7b D13) — never folded into `partial`.
    downgraded_unsubstantiated: int
    contributing_refs: list[ContributingRefRead]


class ControlCoverageRead(BaseModel):
    control_id: uuid.UUID
    code: str
    title: str
    verdict: str
    breakdown: CoverageBreakdownRead
    framework_mappings: list[FrameworkMappingRead]


class FrameworkClauseCoverageRead(BaseModel):
    framework: Framework
    clause_ref: str
    verdict: str
    control_ids: list[uuid.UUID]


class UnaddressedControlRead(BaseModel):
    control_id: uuid.UUID
    code: str
    title: str
    framework_mappings: list[FrameworkMappingRead]


class CoverageMatrixRead(BaseModel):
    scope: str
    scope_id: uuid.UUID | None
    framework_filter: Framework | None
    include_unapproved: bool
    controls: list[ControlCoverageRead]
    frameworks: list[FrameworkClauseCoverageRead]
    unaddressed_controls: list[UnaddressedControlRead]
    not_an_obligation_set: bool
    generated_at: datetime
