"""
Pydantic v2 schemas for the Classification Gate (gate 2) endpoints.

  AnswerIn              — one (question_code, option_code) answer with provenance.
  OptionRead            — one answer option returned in the question set.
  QuestionRead          — one question with its options.
  QuestionSetRead       — residual question set for the current tree version.
  ContextOutcomeRead    — pure-resolver outcome (kind + tier + rationale + missing).
  ComputeRequest        — POST /context body (answers + optional override).
  PreviewRequest        — POST /context/preview body (answers, no write).
  ClassificationStatusRead — current Classification snapshot (read-side).
  ClassificationContextRead — GET /context response envelope.
  ComputeResultRead     — POST /context response.
  SignOffRead           — POST /sign-off response.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.base import ClassificationStatus, EUAIActTier, ProvenanceConfidence


class AnswerIn(BaseModel):
    question_code: str
    option_code: str
    provenance: ProvenanceConfidence = ProvenanceConfidence.USER_CONFIRMED


class OptionRead(BaseModel):
    code: str
    label: str


class QuestionRead(BaseModel):
    code: str
    text: str
    legal_ref: str | None = None
    sort_order: int
    options: list[OptionRead]


class QuestionSetRead(BaseModel):
    tree_version: str
    questions: list[QuestionRead]


class ContextOutcomeRead(BaseModel):
    kind: Literal["UNRESOLVED", "RESOLVED", "PROHIBITED_HALT"]
    tier: EUAIActTier | None = None
    subcategory_code: str | None = None
    rationale: str
    missing: list[str] = []


class ClassificationStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    use_case_id: uuid.UUID
    tier: EUAIActTier
    status: ClassificationStatus
    overridden: bool
    proposed_tier: EUAIActTier | None = None
    basis_subcategory_code: str | None = None
    basis_legal_ref: str | None = None
    rationale: str
    version: int
    is_current: bool
    created_at: datetime
    updated_at: datetime


class ClassificationContextRead(BaseModel):
    """GET /classification/context response."""
    current_classification: ClassificationStatusRead | None = None
    residual_questions: QuestionSetRead


class ComputeRequest(BaseModel):
    """POST /classification/context — submit answers and compute."""
    answers: list[AnswerIn]
    tree_version: str
    override_tier: EUAIActTier | None = None
    justification: str | None = None


class PreviewRequest(BaseModel):
    """POST /classification/context/preview — resolve without persisting."""
    answers: list[AnswerIn]
    tree_version: str


class ComputeResultRead(BaseModel):
    """POST /classification/context response."""
    outcome: ContextOutcomeRead
    classification: ClassificationStatusRead | None = None


class SignOffRead(BaseModel):
    """POST /classification/sign-off response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    use_case_id: uuid.UUID
    tier: EUAIActTier
    status: ClassificationStatus
    version: int
    updated_at: datetime
