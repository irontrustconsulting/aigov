"""Schemas for the evidence repository (sprints/SPRINT_EVIDENCE_REPOSITORY.md).

sha256 and content_type/size_bytes are always server-derived — never an
accepted input field on any create schema here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    content_type: str | None
    size_bytes: int | None
    sha256: str | None
    uploaded_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class EvidenceListItem(EvidenceRead):
    link_count: int


class EvidenceListResponse(BaseModel):
    items: list[EvidenceListItem]
    next_cursor: str | None


class EvidenceDetailRead(EvidenceRead):
    download_url: str
