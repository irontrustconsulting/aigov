from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProvisionRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100,
                      description="URL-safe identifier, unique across tenants")
    owner_email: str = Field(min_length=1, max_length=320)
    owner_name: str = Field(min_length=1, max_length=255)


class ProvisionResponse(BaseModel):
    tenant_id: uuid.UUID
    owner_id: uuid.UUID


class TenantListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    created_at: datetime
