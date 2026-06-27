"""Schemas for the export / audit pack (sprints/SPRINT_AUDIT_PACK.md,
Sprint 7b; docs/AUDIT_PACK_DESIGN.md). All response-only — a pack is
assembled live per request, never persisted (D1), so none of these carry
`from_attributes` at the top level; nested reuse of existing ORM-bound
schemas (`AssessmentItemRead`, `DeploymentAuthorisationRead`, `SystemDetail`)
keeps their own `from_attributes` binding.

`content_hash` is computed over a canonical serialization of the body
sections only (sorted keys, no insignificant whitespace) — see
`export_service._content_hash` — so it is stable across identical-state
regenerations and independent of `generated_at`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.base import (
    AssessmentStatus,
    AssessmentType,
    ClassificationStatus,
    EUAIActTier,
    Framework,
    LifecycleState,
)
from app.schemas.assessment import (
    AssessmentItemRead,
    AssessmentRead,
    ControlLinkRead,
    EvidenceLinkRead,
)
from app.schemas.coverage import CoverageMatrixRead
from app.schemas.lifecycle import DeploymentAuthorisationRead
from app.schemas.system import AffectedPartyOut, DataCategoryOut, SystemDetail, VocabItemOut


class ActorRef(BaseModel):
    """A nullable actor projection — `actor_user_id` is genuinely nullable
    on both `LifecycleTransition` and `AuditEvent` (background-triggered
    rows, future anonymisation), so this stays optional end-to-end rather
    than dropping the row."""

    user_id: uuid.UUID | None
    name: str | None
    email: str | None


class ClassificationHistoryEntryRead(BaseModel):
    tier: EUAIActTier
    proposed_tier: EUAIActTier | None
    overridden: bool
    rationale: str
    basis_subcategory_code: str | None
    basis_legal_ref: str | None
    status: ClassificationStatus
    version: int
    # Not a row column — sourced from the classification.signed_off audit
    # event (§4.2 item 2).
    signed_off_by: ActorRef | None


class ExportAssessmentItemRead(AssessmentItemRead):
    """Native AIIA items and feeder items alike (D3) — `surfaces_into` is
    the AIIA section_key this item maps into via
    AssessmentSectionTemplate.aiia_target_section_key, or None when private
    (always None for native AIIA items, which have no surfacing concept)."""

    surfaces_into: str | None = None
    control_links: list[ControlLinkRead] = []
    evidence_links: list[EvidenceLinkRead] = []


class FeederExportRead(BaseModel):
    assessment_id: uuid.UUID
    type: AssessmentType
    status: AssessmentStatus
    items: list[ExportAssessmentItemRead]


class AssessmentExportRead(BaseModel):
    # None when the use case has no AIIA yet — the record still emits with
    # empty sections rather than 404ing (§9 edge case).
    aiia_id: uuid.UUID | None
    status: AssessmentStatus | None
    native_items: list[ExportAssessmentItemRead]
    feeders: list[FeederExportRead]


class EvidenceManifestEntryRead(BaseModel):
    """By reference only — never bytes, never an embedded presigned URL
    (D2/inv 40). Retrieval stays on the hardened GET /v1/evidence/{id}."""

    id: uuid.UUID
    sha256: str | None
    title: str
    content_type: str | None
    size_bytes: int | None
    back_refs: list[uuid.UUID]


class LifecycleTrailEntryRead(BaseModel):
    from_state: LifecycleState | None
    to_state: LifecycleState
    occurred_at: datetime
    actor: ActorRef | None
    reason: str | None
    triggered_by: str | None


class AuditTrailEntryRead(BaseModel):
    """source_ip is deliberately omitted (D12) — exporting it into a
    deliverable that leaves the system is a privacy expansion."""

    action: str
    occurred_at: datetime
    actor: ActorRef | None
    entity_type: str
    entity_id: uuid.UUID | None
    detail: dict


class UseCaseExportSectionsRead(BaseModel):
    """The reusable use-case-record body (§4.2 items 1-7) — shared between
    the standalone use-case export and each entry nested under a system
    export. Audit trail (item 8) is deliberately excluded here: the system
    pack computes one combined closure across all its use cases rather than
    one per use case (§4.4)."""

    use_case_id: uuid.UUID
    system: SystemDetail
    # Use-distinguishing context (relocated from system in DM-S1)
    usage_context: VocabItemOut | None = None
    human_oversight_type: VocabItemOut | None = None
    data_categories: list[DataCategoryOut] = []
    affected_parties: list[AffectedPartyOut] = []
    classification_history: list[ClassificationHistoryEntryRead]
    assessment: AssessmentExportRead
    evidence_manifest: list[EvidenceManifestEntryRead]
    coverage: CoverageMatrixRead
    lifecycle_trail: list[LifecycleTrailEntryRead]
    atos: list[DeploymentAuthorisationRead]


class UseCaseExportRead(UseCaseExportSectionsRead):
    audit_trail: list[AuditTrailEntryRead]
    generated_at: datetime
    content_hash: str


class SystemExportRead(BaseModel):
    system_id: uuid.UUID
    system: SystemDetail
    use_cases: list[UseCaseExportSectionsRead]
    system_coverage: CoverageMatrixRead
    audit_trail: list[AuditTrailEntryRead]
    generated_at: datetime
    content_hash: str


class AtoDocumentRead(BaseModel):
    ato: DeploymentAuthorisationRead
    current_assessment_summary: AssessmentRead
    current_classification_summary: ClassificationHistoryEntryRead | None
    # Always True (D5) — the referenced assessment/classification are read
    # live and may have drifted since authorisation; never reconstructed.
    basis_is_current_state_not_authorisation_snapshot: bool = True


class FrameworkExportRead(BaseModel):
    framework: Framework
    coverage: CoverageMatrixRead
    substantiation_manifest: list[EvidenceManifestEntryRead]
    generated_at: datetime
    content_hash: str
