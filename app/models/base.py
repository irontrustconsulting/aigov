"""
Base declarative class, shared mixins, and enums.

Design notes
------------
* SQLAlchemy 2.0 typed ORM (Mapped / mapped_column).
* UUID primary keys everywhere (Postgres `uuid` type). UUIDs avoid leaking
  row counts and make multi-tenant references safe to expose in URLs/APIs.
* Every tenant-scoped table carries `tenant_id`. Enforce isolation with
  Postgres Row-Level Security (RLS) in addition to app-layer filtering
  (see migrations/notes). App code must never be the *only* thing standing
  between tenants.
* `TimestampMixin` gives created/updated; the immutable audit trail
  (AuditEvent) is separate and append-only — these timestamps are
  convenience, not the compliance record.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base. Keep ORM models here; keep Pydantic
    API schemas in a *separate* module tree (e.g. app/schemas/) so the
    persistence shape and the API shape can diverge without pain."""
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """Mix into every tenant-scoped table. The FK + index is what RLS
    policies and all queries filter on."""

    @staticmethod
    def tenant_fk() -> Mapped[uuid.UUID]:
        return mapped_column(
            PGUUID(as_uuid=True),
            ForeignKey("tenant.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )


# ---------------------------------------------------------------------------
# Enums  (stored as native Postgres enums via SQLAlchemy Enum in the models)
# ---------------------------------------------------------------------------

class Framework(str, enum.Enum):
    ISO_42001 = "iso_42001"
    ISO_42005 = "iso_42005"
    EU_AI_ACT = "eu_ai_act"
    # Reserved for post-MVP without schema change:
    NIST_AI_RMF = "nist_ai_rmf"


class EUAIActTier(str, enum.Enum):
    PROHIBITED = "prohibited"
    HIGH = "high_risk"
    LIMITED = "limited_risk"
    MINIMAL = "minimal_risk"
    UNCLASSIFIED = "unclassified"


class RiskLayer(str, enum.Enum):
    """Which layer of the seed risk taxonomy an entry belongs to (PRD 4.7)."""
    TECHNICAL_SECURITY = "technical_security"      # OWASP Top 10 for LLMs
    GOVERNANCE_RIGHTS = "governance_rights"        # NIST / ISO themes
    ADVERSARIAL_THREAT = "adversarial_threat"      # MITRE ATLAS (post-MVP)


class RiskSource(str, enum.Enum):
    OWASP_LLM = "owasp_llm"
    NIST_AI_RMF = "nist_ai_rmf"
    ISO_42001 = "iso_42001"
    ISO_42005 = "iso_42005"
    MITRE_ATLAS = "mitre_atlas"      # reserved, post-MVP
    INTERNAL = "internal"


class ApprovalStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class LifecycleState(str, enum.Enum):
    """The fixed, opinionated use-case lifecycle (PRD 4.1.1).
    Implemented as a determinate state machine — these are the only states."""
    REQUESTED = "requested"
    VENDOR_CHECK = "vendor_check"
    PRODUCT_CHECK = "product_check"
    INTAKE = "intake"                      # context capture + classification
    HALTED_PROHIBITED = "halted_prohibited"  # terminal: prohibited practice
    UNDER_ASSESSMENT = "under_assessment"
    TREATMENT_PENDING = "treatment_pending"
    PENDING_AUTHORISATION = "pending_authorisation"
    AUTHORISED = "authorised"
    DEPLOYED = "deployed"
    HELD = "held"                          # blocked on an upstream gate
    RETIRED = "retired"


class AssessmentType(str, enum.Enum):
    AIIA = "aiia"            # the primary record
    FRIA = "fria"            # feeds the AIIA
    DPIA = "dpia"            # feeds the AIIA
    MODEL_RISK = "model_risk"  # feeds the AIIA


class AssessmentStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    NEEDS_REFRESH = "needs_refresh"


class CoverageStatus(str, enum.Enum):
    OPEN = "open"
    PARTIAL = "partial"
    SATISFIED = "satisfied"


class ProvenanceConfidence(str, enum.Enum):
    """For catalogue-prefilled facts (PRD 4.3 / 1.5): every asserted fact
    carries where it came from and whether a human confirmed it."""
    AI_SUGGESTED = "ai_suggested"
    CATALOGUE_CURATED = "catalogue_curated"
    USER_CONFIRMED = "user_confirmed"
    USER_AMENDED = "user_amended"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    CONTRIBUTOR = "contributor"
    AUDITOR_READONLY = "auditor_readonly"
