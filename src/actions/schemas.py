from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ActionDraftData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    idempotency_key: str
    status: str
    created: bool
    idempotent_reused: bool


class ActionToolCompatResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    data: dict[str, Any]
    error: dict[str, Any]
