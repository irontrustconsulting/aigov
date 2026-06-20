"""Schemas for the lifecycle status/re-evaluate surface (Sprint 5, WI-6)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.base import ApprovalStatus, EUAIActTier, LifecycleState


class GateResultRead(BaseModel):
    state: LifecycleState
    verdict: str
    reason_code: str
    reason: str
    responsible_party: str


class UseCaseLifecycleRead(BaseModel):
    use_case_id: uuid.UUID
    state: LifecycleState
    held_from_state: LifecycleState | None
    held_reason: str | None
    gates: list[GateResultRead]
    blocking: GateResultRead | None


class VendorApprovalCreate(BaseModel):
    status: ApprovalStatus
    valid_until: datetime | None = None
    note: str | None = None


class VendorApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    catalogue_vendor_id: uuid.UUID
    status: ApprovalStatus
    valid_until: datetime | None
    decided_by_user_id: uuid.UUID | None
    decided_at: datetime | None
    note: str | None


class ProductApprovalCreate(BaseModel):
    status: ApprovalStatus
    valid_until: datetime | None = None
    note: str | None = None


class ProductApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    catalogue_product_id: uuid.UUID
    status: ApprovalStatus
    valid_until: datetime | None
    decided_by_user_id: uuid.UUID | None
    decided_at: datetime | None
    note: str | None


class UseCaseRollupEntry(BaseModel):
    use_case_id: uuid.UUID
    title: str
    state: LifecycleState
    eu_tier: EUAIActTier
    blocking: GateResultRead | None


class SystemRollupRead(BaseModel):
    """Per-system rollup (REG-3) — use cases, states, highest tier present
    (computed in Python over the precedence ladder, never SQL on the enum),
    and outstanding obligations (each use case's blocking GateResult)."""

    system_id: uuid.UUID
    system_name: str
    use_case_count: int
    highest_tier: EUAIActTier | None
    use_cases: list[UseCaseRollupEntry]
