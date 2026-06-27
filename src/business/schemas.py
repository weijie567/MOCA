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


class BusinessFactResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_fact_result.v1"] = "business_fact_result.v1"
    tenant_id: str
    status: Literal[
        "ok",
        "partial",
        "not_found",
        "permission_denied",
        "stale",
        "unavailable",
        "invalid_request",
    ]
    fact: dict[str, Any] | None
    business_fact_refs: list[BusinessFactRefV1]
    resource_version: str | None = None
    data_freshness_at: datetime | None = None
    source_system: str
    scope_check_result: Literal["allowed", "denied", "not_applicable", "unknown"]
    missing_required_facts: list[str]
    safe_errors: list[ToolError]


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
    "BusinessFactResultV1",
    "ToolCallContext",
    "ToolError",
    "ToolRequest",
    "ToolResult",
    "ToolResultV2",
]
