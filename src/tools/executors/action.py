from __future__ import annotations

from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.service import ActionService
from src.tools.contracts import ToolCallContext, ToolError, ToolResultV2
from src.tools.manager_results import result


class ActionToolExecutor:
    executor_name = "action"

    def __init__(self, session: AsyncSession, service: ActionService | None = None) -> None:
        self.service = service or ActionService(session)

    def has_tool(self, name: str) -> bool:
        return name == "create_coupon_grant_draft"

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        if name != "create_coupon_grant_draft":
            return result(
                "unavailable",
                "Tool is declared but unavailable",
                code="TOOL_UNAVAILABLE",
                source="tool",
                source_system="action_tool_executor",
            )

        started_at = perf_counter()
        raw_result = await self.service.create_coupon_grant_draft(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            run_id=ctx.run_id,
            approval_request_id=args.get("approval_request_id"),
            idempotency_key=ctx.idempotency_key or "",
            action_type=str(args["action_type"]),
            payload=dict(args["payload"]),
            action_payload_hash=str(args.get("action_payload_hash") or ""),
            safety_snapshot_ref=str(args.get("safety_snapshot_ref") or ""),
            safety_snapshot_hash=str(args.get("safety_snapshot_hash") or ""),
        )
        return _action_result(raw_result, started_at)


def _action_result(raw_result: dict[str, Any], started_at: float) -> ToolResultV2:
    latency_ms = max(0, int((perf_counter() - started_at) * 1000))
    if not isinstance(raw_result, dict):
        return result(
            "invalid_response",
            "Action executor returned an invalid response",
            code="INVALID_ACTION_RESPONSE",
            source="adapter",
            source_system="action_tool_executor",
        )
    if raw_result.get("status") == "success" and isinstance(raw_result.get("data"), dict):
        return ToolResultV2(
            status="success",
            data=dict(raw_result["data"]),
            summary="Action draft created",
            source_system="action_executor",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=latency_ms,
            audit_ref=None,
        )

    error = raw_result.get("error") if isinstance(raw_result.get("error"), dict) else {}
    retryable = bool(error.get("retryable", False))
    safe_message = "Action draft creation failed"
    return ToolResultV2(
        status="error",
        data=None,
        summary=safe_message,
        source_system="action_executor",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=ToolError(
            code=str(error.get("error_code") or "ACTION_DRAFT_FAILED"),
            safe_message=safe_message,
            retryable=retryable,
            source="adapter",
        ),
        retryable=retryable,
        retry_after_ms=None,
        latency_ms=latency_ms,
        audit_ref=None,
    )
