"""
Assessment layer: per-use-case classification and the AIIA (with its
feeding analyses), plus the findings that tie risks, controls and evidence
together.

Decisions (PRD 4.4 / 4.5)
-------------------------
* Classification is per use case, versioned, and ALWAYS carries a rationale
  + the answers that produced it (CLS-3) — defensibility.
* Assessment of type AIIA is the primary record; FRIA/DPIA/MODEL_RISK are
  *also* Assessment rows linked to the same use case via `parent_aiia_id`
  (they feed the AIIA, AIIA-3). One AIIA per use case is enforced by a
  partial unique index (see migration notes).
* AssessmentItem is the workhorse: a single finding/answer that can name a
  Risk, attach Evidence, and link to Controls — so one item can satisfy
  several controls across frameworks (the cross-map pays off here).
* Every place the system asserts a default (classification result, proposed
  risks, drafted text) carries provenance + is overridable + the override is
  tracked (PRD 1.5). Overrides are recorded as AuditEvents and on the item.
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import (
    String, Text, ForeignKey, Enum as SAEnum, Boolean, Integer, DateTime,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from .base import (
    Base, TimestampMixin, uuid_pk,
    EUAIActTier, AssessmentType, AssessmentStatus, ProvenanceConfidence,
    CoverageStatus, ClassificationStatus, SectionApplicability, TreatmentDecision,
)


class Classification(Base, TimestampMixin):
    """A versioned EU AI Act classification of a use case (PRD 4.4)."""
    __tablename__ = "classification"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    use_case_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("use_case.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tier: Mapped[EUAIActTier] = mapped_column(
        SAEnum(EUAIActTier, name="eu_ai_act_tier"), nullable=False,
    )
    # The basis: which Annex/criteria drove it (shown reasoning, CLS-2).
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    # The questionnaire answers that produced the result (CLS-3).
    answers_blob: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Was the system's proposed tier overridden by a human? (1.5 tracked dev.)
    overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    proposed_tier: Mapped[EUAIActTier | None] = mapped_column(
        SAEnum(EUAIActTier, name="eu_ai_act_tier")
    )
    # Basis stamped as VALUES at snapshot time so later reference-data edits
    # cannot rewrite history. Null when tier is REQUIRES_CONTEXT.
    basis_subcategory_code: Mapped[str | None] = mapped_column(String(80))
    basis_legal_ref: Mapped[str | None] = mapped_column(String(120))
    # Gate-2 status: PENDING_REVIEW on compute; APPROVED on Reviewer sign-off.
    # CHANGES_REQUESTED / NEEDS_REFRESH reserved for the review workflow track.
    status: Mapped[ClassificationStatus] = mapped_column(
        SAEnum(ClassificationStatus, name="classification_status"),
        default=ClassificationStatus.PENDING_REVIEW,
        nullable=False,
    )

    use_case: Mapped["UseCase"] = relationship(back_populates="classifications")


class Assessment(Base, TimestampMixin):
    """An assessment record. type=AIIA is primary (one per use case);
    FRIA/DPIA/MODEL_RISK feed the AIIA via parent_aiia_id."""
    __tablename__ = "assessment"
    __table_args__ = (
        # At most one feeder of each type per AIIA (Phase B, design doc §5.2).
        # NULL parent_aiia_id (every AIIA row) is never compared as equal to
        # itself by a unique constraint, so this only constrains feeders.
        UniqueConstraint("parent_aiia_id", "type", name="uq_feeder_type_per_aiia"),
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
    type: Mapped[AssessmentType] = mapped_column(
        SAEnum(AssessmentType, name="assessment_type"), nullable=False,
    )
    # Feeders point at their AIIA; the AIIA itself has parent_aiia_id NULL.
    parent_aiia_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assessment.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[AssessmentStatus] = mapped_column(
        SAEnum(AssessmentStatus, name="assessment_status"),
        default=AssessmentStatus.DRAFT, nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    residual_risk_summary: Mapped[str | None] = mapped_column(Text)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # The tier this assessment was scoped from, frozen at creation (point-in-
    # time + drift detection). Feeders inherit the parent AIIA's values rather
    # than re-resolving (design doc §8.5).
    tier_snapshot: Mapped[EUAIActTier] = mapped_column(
        SAEnum(EUAIActTier, name="eu_ai_act_tier"), nullable=False,
    )
    classification_version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    # Optimistic-concurrency token (If-Match) — distinct from the run-level `version`.
    lock_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL")
    )

    use_case: Mapped["UseCase"] = relationship(back_populates="assessments")
    # passive_deletes=True: trust the FK's ON DELETE CASCADE rather than
    # having the ORM null out children's parent_aiia_id on parent delete —
    # without it, SQLAlchemy's default relationship handling would silently
    # defeat the DB-level cascade whenever this collection is loaded
    # in-session (design doc §5.7: parent-AIIA delete cascades to feeders).
    feeders: Mapped[List["Assessment"]] = relationship(
        backref="parent_aiia", remote_side="Assessment.id", passive_deletes=True,
    )
    items: Mapped[List["AssessmentItem"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class AssessmentItem(Base, TimestampMixin):
    """A single finding/answer within an assessment. The connective tissue:
    optionally names a Risk, can carry several control links (AssessmentItemControl)
    and evidence links (AssessmentItemEvidence). Carries provenance for the
    strong-default/shown-reasoning/override pattern (1.5)."""
    __tablename__ = "assessment_item"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assessment.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Optional link to a library risk being assessed/treated here.
    # RESTRICT (not SET NULL): a still-AI_SUGGESTED item's only substance is
    # this FK; deleting the library risk must not silently orphan it.
    risk_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("risk.id", ondelete="RESTRICT"),
        index=True,
    )
    prompt: Mapped[str | None] = mapped_column(Text)     # the question/section
    response: Mapped[str | None] = mapped_column(Text)   # the human answer
    likelihood: Mapped[int | None] = mapped_column(Integer)
    severity: Mapped[int | None] = mapped_column(Integer)
    mitigation_plan: Mapped[str | None] = mapped_column(Text)  # treatment (PRD 4.1)
    # Provenance of any system-proposed content in this item (1.5):
    provenance: Mapped[ProvenanceConfidence] = mapped_column(
        SAEnum(ProvenanceConfidence, name="provenance_confidence"),
        default=ProvenanceConfidence.USER_CONFIRMED,
    )
    ai_suggested_text: Mapped[str | None] = mapped_column(Text)  # kept for audit

    # The section template key this item belongs to (load-bearing — keys the
    # whole tier-scoped section model, GET /sections, and feeder propagation).
    section_key: Mapped[str | None] = mapped_column(String(120), index=True)
    # Per-item residual — nullable until a mitigation exists; never default
    # to zero or to the inherent likelihood/severity.
    residual_likelihood: Mapped[int | None] = mapped_column(Integer)
    residual_severity: Mapped[int | None] = mapped_column(Integer)
    # Shown reasoning for a proposed risk: why it was proposed for this use case.
    selection_basis: Mapped[str | None] = mapped_column(Text)
    # Origin pointer for snapshotted register facts (e.g. "system.purpose").
    source_ref: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL")
    )
    lock_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Treatment decision for a dispositioned risk (Sprint 5 WI-9/10).
    # Provenance-neutral: writing these never alters `provenance`. Distinct
    # from `mitigation_plan` (the *how*) — this is the *why* for ACCEPT, and
    # any narrative for MITIGATE (design doc §3, #8).
    treatment_decision: Mapped[TreatmentDecision | None] = mapped_column(
        SAEnum(TreatmentDecision, name="treatment_decision"),
    )
    treatment_rationale: Mapped[str | None] = mapped_column(Text)

    assessment: Mapped["Assessment"] = relationship(back_populates="items")
    control_links: Mapped[List["AssessmentItemControl"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    evidence_links: Mapped[List["AssessmentItemEvidence"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class AssessmentItemControl(Base):
    """Link an assessment finding to the control(s) it evidences. Because a
    control maps to multiple frameworks, one link here propagates coverage
    across ISO 42001 + EU AI Act simultaneously."""
    __tablename__ = "assessment_item_control"
    __table_args__ = (
        UniqueConstraint("item_id", "control_id", name="uq_assessment_item_control"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # RLS parity (design doc §13): backfilled from the parent item at
    # migration time; item-first access remains the norm as defense-in-depth.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assessment_item.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # RESTRICT (not CASCADE): deleting a library control must not silently
    # strip coverage records — that's a loss of audit evidence.
    control_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("control.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    coverage: Mapped[CoverageStatus] = mapped_column(
        SAEnum(CoverageStatus, name="coverage_status"),
        default=CoverageStatus.PARTIAL,
    )

    item: Mapped["AssessmentItem"] = relationship(back_populates="control_links")


class AssessmentItemEvidence(Base):
    """Link an assessment finding to a piece of evidence. Evidence is reusable
    across items/controls (PRD 4.8 EVD-1), hence the join table."""
    __tablename__ = "assessment_item_evidence"
    __table_args__ = (
        UniqueConstraint("item_id", "evidence_id", name="uq_assessment_item_evidence"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # RLS parity (design doc §13); backfilled from the parent item.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # No standalone index: the uq_assessment_item_evidence composite serves
    # item_id as its leftmost prefix (evidence_link_migration.py drops the
    # now-redundant single-column index).
    item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assessment_item.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Indexed standalone: backs the WI-4 pristine-delete guard's NOT EXISTS
    # and the WI-3 link_count subquery, neither of which the composite (item_id-
    # leading) index can serve.
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    item: Mapped["AssessmentItem"] = relationship(back_populates="evidence_links")


class AssessmentSectionTemplate(Base, TimestampMixin):
    """Seeded reference data (global, no RLS): the tier-scoped section
    structure for AIIA and its feeders. AIIA creation instantiates required
    sections from this; GET /sections surfaces recommended ones on demand.
    Feeder rows carry aiia_target_section_key for read-time propagation
    (Phase B) — feeder-private when NULL."""
    __tablename__ = "assessment_section_template"
    __table_args__ = (
        UniqueConstraint("type", "tier", "section_key", name="uq_section_template"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    type: Mapped[AssessmentType] = mapped_column(
        SAEnum(AssessmentType, name="assessment_type"), nullable=False, index=True,
    )
    tier: Mapped[EUAIActTier] = mapped_column(
        SAEnum(EUAIActTier, name="eu_ai_act_tier"), nullable=False, index=True,
    )
    section_key: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    applicability: Mapped[SectionApplicability] = mapped_column(
        SAEnum(SectionApplicability, name="section_applicability"), nullable=False,
    )
    prompt: Mapped[str | None] = mapped_column(Text)
    iso_42005_clause: Mapped[str | None] = mapped_column(String(120))
    # Feeder rows only: the AIIA section this feeder section surfaces under.
    # NULL = feeder-private (surfaces in no AIIA section; export includes it).
    aiia_target_section_key: Mapped[str | None] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
