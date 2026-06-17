from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


FORBIDDEN_MESSAGE_KEYS: set[str] = {
    "raw",
    "raw_prompt",
    "raw_args",
    "raw_payload",
    "raw_tool_output",
    "private_reasoning",
    "chain_of_thought",
    "approval_authority_body",
    "action_authority_body",
}


class ConversationThreadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    user_id: UUID
    thread_id: str
    case_id: str | None = None
    status: str = "active"


class ConversationMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    user_id: UUID
    thread_id: str
    run_id: UUID
    role: Literal["user", "assistant", "tool"]
    content: str
    trace_id: str | None = None
    prompt_template_version: str | None = None
    prompt_block_hashes_json: list[str] = Field(default_factory=list)
    context_snapshot_ref: str | None = None
    redacted_prompt_snapshot_ref: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_forbidden_payload_keys(self) -> ConversationMessageCreate:
        guard_forbidden_message_keys({"content": self.content, "metadata_json": self.metadata_json})
        return self


class ConversationMessageView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    conversation_thread_id: UUID
    tenant_id: UUID
    thread_id: str
    run_id: UUID
    trace_id: str | None = None
    message_index: int
    role: Literal["user", "assistant", "tool"]
    content: str
    content_hash: str
    prompt_template_version: str | None = None
    prompt_block_hashes_json: list[str] = Field(default_factory=list)
    context_snapshot_ref: str | None = None
    redacted_prompt_snapshot_ref: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class ConversationAppendResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str
    conversation_thread_id: UUID
    message_id: UUID
    message_index: int
    role: Literal["user", "assistant", "tool"]


def guard_forbidden_message_keys(payload: Any) -> None:
    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in FORBIDDEN_MESSAGE_KEYS:
                    raise ValueError(f"{path} must not carry {key}")
                walk(child, f"{path}.{key}")
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(payload, "conversation_message")
