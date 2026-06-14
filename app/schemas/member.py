"""
API schemas for the member management endpoints (POST/GET /v1/members).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MemberCreate(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    name: str = Field(min_length=1, max_length=255)


class MemberCreated(BaseModel):
    user_id: uuid.UUID
    membership_id: uuid.UUID
    status: Literal["pending"] = "pending"


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    membership_id: uuid.UUID
    email: str
    name: str | None
    role: str
    status: Literal["pending", "accepted"]
    created_at: datetime


class MemberListResponse(BaseModel):
    items: list[MemberRead]
    next_cursor: str | None = None
