from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.prompts import INSUFFICIENT_EVIDENCE_RESPONSE
from src.agent.state import AgentState
from src.agent.tools.search_policy import search_policy

MIN_EVIDENCE_SCORE = 0.55


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _trace_step(status: str, started_at: str) -> dict[str, Any]:
    return {
        "node": "retrieve_policy_evidence",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "tools_called": ["search_policy"],
    }


def _build_search_query(state: AgentState) -> str:
    context = state.get("business_context") or {}
    order = context.get("order") or {}
    refund_case = context.get("refund_case") or {}
    parts = [
        state.get("current_intent") or "unknown",
        state.get("user_query") or "",
        f"order_status={order.get('status')}" if order.get("status") else "",
        f"refund_reason={refund_case.get('reason_code') or refund_case.get('reason_text')}"
        if refund_case.get("reason_code") or refund_case.get("reason_text")
        else "",
    ]
    return " ".join(part for part in parts if part).strip()


def _insufficient_evidence_draft(missing_info: list[str] | None = None) -> dict[str, Any]:
    return {
        "recommended_action": "insufficient_evidence",
        "reasoning_summary": INSUFFICIENT_EVIDENCE_RESPONSE,
        "evidence_refs": [],
        "confidence": 0.0,
        "risk_level": "low",
        "missing_info": missing_info or ["No relevant policy found"],
    }


async def retrieve_policy_evidence(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable["session"]
    result = await search_policy(
        query=_build_search_query(state),
        tenant_id=state["tenant_id"],
        user_id=state["user_id"],
        role=state["role"],
        session=session,
        top_k=5,
        doc_type=None,
        risk_level=None,
    )

    data = result.get("data") or {}
    gate_triggered = (
        result.get("status") == "error"
        or data.get("retrieval_status") == "no_evidence"
        or float(data.get("best_score") or 0.0) < MIN_EVIDENCE_SCORE
    )
    output: dict[str, Any] = {
        "retrieved_evidence": result,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
    }
    if gate_triggered:
        output["recommendation_draft"] = _insufficient_evidence_draft()
    return output
