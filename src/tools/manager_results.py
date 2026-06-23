from __future__ import annotations

from typing import Literal

from src.tools.contracts import ToolError, ToolResultV2


def result(
    status: Literal["not_found", "permission_denied", "unavailable", "invalid_request", "invalid_response", "error"],
    summary: str,
    *,
    code: str,
    source: Literal["caller", "tool", "adapter", "policy"] = "caller",
    source_system: str = "unified_tool_manager",
) -> ToolResultV2:
    return ToolResultV2(
        status=status,
        data=None,
        summary=summary,
        source_system=source_system,
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=ToolError(code=code, safe_message=summary, retryable=False, source=source),
        retryable=False,
        retry_after_ms=None,
        latency_ms=0,
        audit_ref=None,
    )
