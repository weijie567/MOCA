from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState
from src.tools.contracts import ToolCallContext
from src.business.service import BusinessToolService


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _trace_step(status: str, started_at: str, tool_names: list[str]) -> dict[str, Any]:
    return {
        "node": "load_business_context",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "tools_called": tool_names,
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": None,
    }


async def load_business_context(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable["session"]
    tenant_id = state["tenant_id"]
    user_id = state["user_id"]
    role = state["role"]
    intent = state.get("current_intent") or "unknown"
    extracted_slots = state.get("extracted_slots") or {}
    has_current_identifier = any(extracted_slots.get(key) for key in ("order_id", "refund_case_id", "ticket_id"))
    slots = extracted_slots if has_current_identifier else state.get("active_slots") or {}
    ctx = ToolCallContext(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
        permissions=configurable.get("permissions", []),
        merchant_scope=configurable.get("merchant_scope", {}),
        session_id=configurable.get("session_id"),
        thread_id=state["thread_id"],
        run_id=state["current_run_id"],
        trace_id=configurable.get("trace_id", ""),
        request_id=str(uuid4()),
        tool_call_id=str(uuid4()),
        caller_node="investigate",
        deadline_at=None,
        attempt=1,
        max_attempts=1,
        idempotency_key=None,
        policy_snapshot_ref=None,
    )
    refs: dict[str, Any] = {"loaded_at": _now_iso()}
    results = []
    tools_called: list[str] = []

    should_load_context = intent in {"refund_troubleshooting", "compensation_suggestion"} or has_current_identifier

    if should_load_context:
        tools_called = [
            tool_name
            for slot_name, tool_name in (
                ("order_id", "get_order"),
                ("refund_case_id", "get_refund_case"),
                ("ticket_id", "get_ticket"),
            )
            if slots.get(slot_name)
        ]
        service = BusinessToolService.with_default_registry(session)
        context = await service.fetch_context(slots, intent, ctx)
        business_context = context.facts
        results = context.tool_results
        refs["business_fact_refs"] = [ref.model_dump(mode="json") for ref in context.business_fact_refs]
        for slot_name, resource_name in (
            ("order_id", "order"),
            ("refund_case_id", "refund_case"),
            ("ticket_id", "ticket"),
        ):
            if slots.get(slot_name) and resource_name in business_context:
                refs[slot_name] = slots[slot_name]
    else:
        business_context = {}

    return {
        "business_context": business_context,
        "tool_results": results,
        "last_business_context_refs": refs,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at, tools_called)],
    }
