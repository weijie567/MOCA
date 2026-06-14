"""Compatibility exports for unified tool contracts and business context."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.tools.contracts import (
    BusinessFactRefV1,
    ToolCallContext,
    ToolError,
    ToolRequest,
    ToolResult,
    ToolResultV2,
)


class BusinessContextV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_context.v1"] = "business_context.v1"
    tenant_id: str
    status: Literal["complete", "partial", "insufficient", "error"]
    facts: dict[str, Any]
    business_fact_refs: list[BusinessFactRefV1]
    tool_results: list[ToolResultV2]
    missing_required_facts: list[str]
    errors: list[ToolError]
    data_freshness_at: datetime | None


__all__ = [
    "BusinessContextV1",
    "BusinessFactRefV1",
    "ToolCallContext",
    "ToolError",
    "ToolRequest",
    "ToolResult",
    "ToolResultV2",
]
