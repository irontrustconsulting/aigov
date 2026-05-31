"""
Knowledge assets: Control Library (PRD 4.6), Risk Library (PRD 4.7),
and the cross-maps that connect them. These are largely GLOBAL reference
data you curate (not tenant-scoped) — the moat. Tenants reference them;
they do not own copies.

The cross-maps are the technical heart of the product:
* Control <-> Framework : one control can satisfy several frameworks
  (ISO 42001 <-> EU AI Act <-> ISO 42005) — this is what lets one piece of
  evidence cover multiple obligations (PRD 4.6 CTL-2).
* Risk <-> Control       : a risk links to its mitigating controls
  (PRD 4.7 RSK-1), so identifying a risk surfaces the controls that treat it.

Both are many-to-many, modelled with explicit association objects (not bare
Tables) so the relationship itself can carry attributes (e.g. mapping
strength, the specific clause reference, who mapped it, version).
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import String, Text, ForeignKey, Enum as SAEnum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import (
    Base, TimestampMixin, uuid_pk, Framework, RiskLayer, RiskSource,
)


# ---------------------------------------------------------------------------
# CONTROL LIBRARY
# ---------------------------------------------------------------------------

class Control(Base, TimestampMixin):
    """A single control/obligation. Framework-agnostic at its core; its
    framework memberships live in ControlFrameworkMap so one control can
    belong to several frameworks at once."""
    __tablename__ = "control"

    id: Mapped[uuid.UUID] = uuid_pk()
    # A stable internal code, e.g. "ACCESS-CONTROL-01"
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(default=1, nullable=False)

    framework_maps: Mapped[List["ControlFrameworkMap"]] = relationship(
        back_populates="control", cascade="all, delete-orphan"
    )
    risk_maps: Mapped[List["RiskControlMap"]] = relationship(
        back_populates="control", cascade="all, delete-orphan"
    )


class ControlFrameworkMap(Base, TimestampMixin):
    """Association object: Control <-> Framework, carrying the specific
    clause/annex reference within that framework. THIS is the cross-walk
    that lets one evidence item satisfy ISO 42001 and the EU AI Act at once."""
    __tablename__ = "control_framework_map"
    __table_args__ = (
        UniqueConstraint("control_id", "framework", "clause_ref",
                         name="uq_control_framework_clause"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    control_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("control.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    framework: Mapped[Framework] = mapped_column(
        SAEnum(Framework, name="framework"), nullable=False, index=True,
    )
    # e.g. "Annex A.6.2.1" (ISO 42001) or "Art. 9 / Annex III(4)" (EU AI Act)
    clause_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    control: Mapped["Control"] = relationship(back_populates="framework_maps")


# ---------------------------------------------------------------------------
# RISK LIBRARY
# ---------------------------------------------------------------------------

class Risk(Base, TimestampMixin):
    """A seed-taxonomy risk entry (PRD 4.7). Human-curated and
    source-attributed; AI may propose relevance/drafts but never authors
    ground truth unconfirmed (RSK-7)."""
    __tablename__ = "risk"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    layer: Mapped[RiskLayer] = mapped_column(
        SAEnum(RiskLayer, name="risk_layer"), nullable=False, index=True,
    )
    source: Mapped[RiskSource] = mapped_column(
        SAEnum(RiskSource, name="risk_source"), nullable=False,
    )
    source_ref: Mapped[str | None] = mapped_column(String(120))  # e.g. "LLM01"
    reference_url: Mapped[str | None] = mapped_column(Text)
    typical_triggers: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(default=1, nullable=False)

    control_maps: Mapped[List["RiskControlMap"]] = relationship(
        back_populates="risk", cascade="all, delete-orphan"
    )


class RiskControlMap(Base, TimestampMixin):
    """Association object: Risk <-> mitigating Control. Identifying a risk in
    an assessment surfaces these controls as candidate treatments."""
    __tablename__ = "risk_control_map"
    __table_args__ = (
        UniqueConstraint("risk_id", "control_id", name="uq_risk_control"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    risk_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("risk.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("control.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Optional qualifier: does this control fully or partially mitigate?
    strength: Mapped[str | None] = mapped_column(String(40))

    risk: Mapped["Risk"] = relationship(back_populates="control_maps")
    control: Mapped["Control"] = relationship(back_populates="risk_maps")
