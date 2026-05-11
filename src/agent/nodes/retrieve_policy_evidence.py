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


def _trace_step(status: str, started_at: str, evidence_refs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    step = {
        "node": "retrieve_policy_evidence",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "tools_called": ["search_policy"],
    }
    if evidence_refs:
        step["evidence_refs"] = evidence_refs
    return step


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


def _retrieval_error_draft(error: dict[str, Any]) -> dict[str, Any]:
    return {
        "recommended_action": "retrieval_error",
        "reasoning_summary": "Policy retrieval failed due to an infrastructure error.",
        "evidence_refs": [],
        "confidence": 0.0,
        "risk_level": "low",
        "missing_info": [error.get("message") or "Policy retrieval failed"],
    }


def _evidence_refs_from_result(result: dict[str, Any], retrieved_at: str) -> list[dict[str, Any]]:
    data = result.get("data") or {}
    refs: list[dict[str, Any]] = []
    for item in data.get("evidence") or []:
        doc_key = item.get("doc_key")
        chunk_id = item.get("chunk_id")
        if not doc_key or not chunk_id:
            continue
        refs.append(
            {
                "doc_key": str(doc_key),
                "chunk_id": str(chunk_id),
                "title": item.get("title"),
                "confidence": item.get("score"),
                "retrieved_at": retrieved_at,
            }
        )
    return refs


def _merge_evidence_refs(
    existing: list[dict[str, Any]] | None,
    new: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for ref in [*(existing or []), *(new or [])]:
        key = (ref.get("doc_key"), ref.get("chunk_id"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(ref)
    return merged


async def retrieve_policy_evidence(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    retrieved_at = _now_iso()
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
    retrieval_failed = result.get("status") == "error"
    gate_triggered = data.get("retrieval_status") == "no_evidence" or float(data.get("best_score") or 0.0) < MIN_EVIDENCE_SCORE
    new_refs = [] if retrieval_failed or gate_triggered else _evidence_refs_from_result(result, retrieved_at)
    merged_refs = _merge_evidence_refs(state.get("evidence_refs"), new_refs)
    output: dict[str, Any] = {
        "retrieved_evidence": result,
        "trace_steps": (state.get("trace_steps") or [])
        + [_trace_step("error" if retrieval_failed else "completed", started_at, new_refs)],
        "evidence_refs": merged_refs,
    }
    if retrieval_failed:
        error = result.get("error") or {}
        output["recommendation_draft"] = _retrieval_error_draft(error)
        output["node_errors"] = (state.get("node_errors") or []) + [
            {"node": "retrieve_policy_evidence", "error": error, "retry_count": 0}
        ]
    elif gate_triggered:
        output["recommendation_draft"] = _insufficient_evidence_draft()
    return output
