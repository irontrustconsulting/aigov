"""
EU AI Act context-classification decision tree — global reference tables.

Three tables, no tenant_id, no RLS (same pattern as governance_role and
eu_ai_act_subcategory): the tree definition is platform-level data curated by
migrations + seed scripts, readable by any tenant session.

  DecisionTree         — versioned container; version is the audit/legal-review
                         boundary. Frozen once written (seed loader refuses to
                         mutate existing versions).

  DecisionTreeQuestion — one question per row, belonging to a tree. Each
                         question probes exactly one rung of the precedence
                         ladder (PROHIBITED | HIGH | LIMITED) or is NULL when
                         the question is a general-purpose discriminator.

  DecisionTreeOption   — one answer option per row. An option either asserts
                         a tier rung (asserts_rung) or names a specific
                         subcategory (asserts_subcategory_code), or neither
                         (a "no" answer that makes no positive assertion).
                         These two fields are mutually exclusive when populated.

Resolution contract (WI-4): the resolver loads the tree, maps supplied
(question_code, option_code) pairs to their options, collects every positive
assertion, takes the highest-precedence rung, and applies fail-closed rules.
No writes happen inside the resolver.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, EUAIActTier, TimestampMixin, uuid_pk


class DecisionTree(Base, TimestampMixin):
    """Versioned container for one revision of the classification question set.
    Version strings are the legal-review boundary: bump version for any content
    change; the seed loader rejects mutations of a frozen version."""
    __tablename__ = "decision_tree"

    id: Mapped[uuid.UUID] = uuid_pk()
    version: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    questions: Mapped[list[DecisionTreeQuestion]] = relationship(
        back_populates="tree",
        cascade="all, delete-orphan",
        order_by="DecisionTreeQuestion.sort_order",
    )


class DecisionTreeQuestion(Base):
    """One question within a decision tree. Each question probes a single rung
    of the precedence ladder. sort_order controls display sequence only —
    resolution is order-independent (precedence rules, not position)."""
    __tablename__ = "decision_tree_question"
    __table_args__ = (
        UniqueConstraint("tree_id", "question_code", name="uq_dtq_tree_code"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tree_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("decision_tree.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    question_code: Mapped[str] = mapped_column(String(80), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Which tier rung this question helps resolve. NULL = general discriminator.
    probes_rung: Mapped[EUAIActTier | None] = mapped_column(
        SAEnum(EUAIActTier, name="eu_ai_act_tier"), nullable=True,
    )
    legal_ref: Mapped[str | None] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    tree: Mapped[DecisionTree] = relationship(back_populates="questions")
    options: Mapped[list[DecisionTreeOption]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )


class DecisionTreeOption(Base):
    """One answer option for a question. An option makes at most one positive
    assertion: either a tier rung (asserts_rung) or a specific subcategory
    (asserts_subcategory_code). A "no" answer has both fields NULL."""
    __tablename__ = "decision_tree_option"
    __table_args__ = (
        UniqueConstraint("question_id", "option_code", name="uq_dto_question_code"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    question_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("decision_tree_question.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    option_code: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    # Mutually exclusive: either asserts a rung OR names a subcategory.
    asserts_rung: Mapped[EUAIActTier | None] = mapped_column(
        SAEnum(EUAIActTier, name="eu_ai_act_tier"), nullable=True,
    )
    asserts_subcategory_code: Mapped[str | None] = mapped_column(String(80))

    question: Mapped[DecisionTreeQuestion] = relationship(back_populates="options")
