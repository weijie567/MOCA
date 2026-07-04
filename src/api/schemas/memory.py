from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


MemoryReviewType = Literal["long_term", "case"]


class MemoryReviewActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    reason_code: str | None = Field(default=None, min_length=1, max_length=64)
    review_reason: str | None = Field(default=None, max_length=1500)


class MemoryPendingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: MemoryReviewType
    memory_id: str
    scope_type: str
    scope_id: str
    review_status: str
    pii_classification: str
    source_type: str
    content: str | None = None
    summary: str | None = None
    excerpt: str | None = None
    created_by_run_id: str | None = None
    created_at: datetime | None = None


class MemoryPendingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MemoryPendingItem]
    total: int


class LongTermPreferenceSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    scope_type: Literal["tenant", "merchant"]
    scope_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=4000)
    reason_code: str | None = Field(default=None, min_length=1, max_length=64)


class LongTermPreferenceSaveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: Literal["long_term"]
    memory_id: str | None
    event_id: str | None
    decision: str
    reason_code: str
    review_status: str | None
    source_type: Literal["explicit_admin_preference"]
