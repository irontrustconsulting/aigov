"""Schemas for draft_registration endpoints (DM-S3, D-66)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DraftRegistrationRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    owner_user_id: uuid.UUID
    draft_blob: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DraftRegistrationPatch(BaseModel):
    draft_blob: dict
