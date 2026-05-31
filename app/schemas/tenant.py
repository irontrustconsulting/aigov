"""
API schemas for Tenant — the request/response shapes, deliberately SEPARATE
from the ORM model in app/models/identity.py.

Why separate: the API contract and the database shape should evolve
independently. The client never sees internal columns it shouldn't, and you can
reshape responses (nesting, renaming, omitting) without touching persistence.

Pydantic v2: `model_config = ConfigDict(from_attributes=True)` lets a response
schema be built directly from an ORM object (reads attributes off the model).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenantCreate(BaseModel):
    """What the client sends to create a tenant."""
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100,
                      description="URL-safe identifier, unique across tenants")


class TenantRead(BaseModel):
    """What the API returns for a tenant."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime