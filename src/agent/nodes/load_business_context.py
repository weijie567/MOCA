from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState
from src.agent.tools.get_order import get_order
from src.agent.tools.get_refund_case import get_refund_case
from src.agent.tools.get_ticket import get_ticket


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
    ctx: dict[str, Any] = {}
    refs: dict[str, Any] = {"loaded_at": _now_iso()}
    results: list[dict[str, Any]] = []
    tools_called: list[str] = []

    should_load_context = intent in {"refund_troubleshooting", "compensation_suggestion"} or has_current_identifier

    if should_load_context:
        if slots.get("order_id"):
            tools_called.append("get_order")
            result = await get_order(slots["order_id"], tenant_id, user_id, role, session)
            results.append({"tool": "get_order", **result})
            if result.get("status") == "success":
                ctx["order"] = result["data"]
                refs["order_id"] = slots["order_id"]

        if slots.get("refund_case_id"):
            tools_called.append("get_refund_case")
            result = await get_refund_case(slots["refund_case_id"], tenant_id, user_id, role, session)
            results.append({"tool": "get_refund_case", **result})
            if result.get("status") == "success":
                ctx["refund_case"] = result["data"]
                refs["refund_case_id"] = slots["refund_case_id"]

        if slots.get("ticket_id"):
            tools_called.append("get_ticket")
            result = await get_ticket(slots["ticket_id"], tenant_id, user_id, role, session)
            results.append({"tool": "get_ticket", **result})
            if result.get("status") == "success":
                ctx["ticket"] = result["data"]
                refs["ticket_id"] = slots["ticket_id"]

    return {
        "business_context": ctx,
        "tool_results": results,
        "last_business_context_refs": refs,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at, tools_called)],
    }
