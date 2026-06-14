from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig

from src.agent.prompts import INSUFFICIENT_EVIDENCE_RESPONSE
from src.agent.state import AgentState
from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import KnowledgeSearchResult
from src.tools.contracts import ToolCallContext, ToolResultV2
from src.tools.manager import UnifiedToolManager

MIN_EVIDENCE_SCORE = 0.55
POLICY_SEARCH_TOOL = "search_policy"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _trace_step(
    status: str,
    started_at: str,
    evidence_refs: list[dict[str, Any]] | None = None,
    *,
    tool_called: bool = True,
) -> dict[str, Any]:
    step = {
        "node": "retrieve_policy_evidence",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "tools_called": [POLICY_SEARCH_TOOL] if tool_called else [],
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": None,
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


def _merge_evidence_refs(
    existing: list[dict[str, Any]] | None,
    new: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str | None] = set()
    for ref in [*(existing or []), *(new or [])]:
        key = ref.get("evidence_id")
        if key in seen:
            continue
        seen.add(key)
        merged.append(ref)
    return merged


def _build_tool_context(state: AgentState, configurable: dict[str, Any], effective_at: str) -> ToolCallContext:
    run_id = state.get("current_run_id") or str(uuid4())
    merchant_scope = configurable.get("merchant_scope")
    if not isinstance(merchant_scope, (dict, list)):
        merchant_scope = {}
    return ToolCallContext(
        tenant_id=state["tenant_id"],
        user_id=state["user_id"],
        role=state["role"],
        permissions=list(configurable.get("permissions") or []),
        merchant_scope=merchant_scope,
        session_id=configurable.get("session_id"),
        thread_id=state["thread_id"],
        run_id=run_id,
        trace_id=configurable.get("trace_id") or run_id,
        request_id=configurable.get("request_id") or str(uuid4()),
        tool_call_id=str(uuid4()),
        caller_node="investigate",
        deadline_at=configurable.get("deadline_at"),
        effective_at=effective_at,
        attempt=1,
        max_attempts=1,
        idempotency_key=None,
        policy_snapshot_ref=None,
    )


def _build_tool_args(state: AgentState) -> dict[str, Any]:
    active_slots = state.get("active_slots") or {}
    args: dict[str, Any] = {
        "query": _build_search_query(state),
        "max_results": 5,
        "allow_partial_evidence": True,
    }
    if state.get("current_intent"):
        args["primary_intent"] = state["current_intent"]
    if active_slots.get("merchant_id"):
        args["merchant_id"] = active_slots["merchant_id"]
    return args


def _knowledge_result_from_tool_result(result: ToolResultV2) -> KnowledgeSearchResult:
    data = result.data or {}
    error = None
    status = data.get("retrieval_status")
    if result.error is not None:
        error = {
            "error_code": result.error.code,
            "message": result.error.safe_message,
            "retryable": result.error.retryable,
        }
        status = "error"
    if status not in {"strong_evidence", "partial_evidence", "no_evidence", "error"}:
        error = error or {
            "error_code": result.status.upper(),
            "message": result.summary,
            "retryable": result.retryable,
        }
        status = "error"
    best_score = data.get("best_score")
    threshold = data.get("threshold")
    return KnowledgeSearchResult(
        status=status,
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        best_score=float(best_score) if isinstance(best_score, (int, float)) else 0.0,
        threshold=float(threshold) if isinstance(threshold, (int, float)) else MIN_EVIDENCE_SCORE,
        evidence_refs=[] if error else result.policy_evidence_refs,
        summary=data.get("summary") if isinstance(data.get("summary"), str) else None,
        error=error,
    )


async def retrieve_policy_evidence(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    effective_at = state.get("run_started_at") or _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable.get("session")
    manager = configurable.get("tool_manager") or UnifiedToolManager.with_defaults(session)
    tool_result = await manager.invoke(
        POLICY_SEARCH_TOOL,
        _build_tool_args(state),
        _build_tool_context(state, configurable, effective_at),
    )
    result = _knowledge_result_from_tool_result(tool_result)

    retrieval_failed = result.status == "error"
    gate_triggered = result.status == "no_evidence" or result.best_score < MIN_EVIDENCE_SCORE
    new_refs = [] if retrieval_failed or gate_triggered else [ref.model_dump() for ref in result.evidence_refs]
    merged_refs = _merge_evidence_refs(state.get("evidence_refs"), new_refs)
    output: dict[str, Any] = {
        "retrieved_evidence": result.model_dump(),
        "trace_steps": (state.get("trace_steps") or [])
        + [_trace_step("error" if retrieval_failed else "completed", started_at, new_refs)],
        "evidence_refs": merged_refs,
    }
    if retrieval_failed:
        error = result.error or {}
        output["recommendation_draft"] = _retrieval_error_draft(error)
        output["node_errors"] = (state.get("node_errors") or []) + [
            {"node": "retrieve_policy_evidence", "error": error, "retry_count": 0}
        ]
    elif gate_triggered:
        output["recommendation_draft"] = _insufficient_evidence_draft()
    return output
