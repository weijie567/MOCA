from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.prompts import INSUFFICIENT_EVIDENCE_RESPONSE
from src.agent.state import AgentState
from src.knowledge.adapters import LegacyRagKnowledgeAdapter
from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import KnowledgeContext, KnowledgeSearchFilters, KnowledgeSearchRequest
from src.knowledge.service import PolicyKnowledgeService

MIN_EVIDENCE_SCORE = 0.55


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _trace_step(status: str, started_at: str, evidence_refs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    step = {
        "node": "retrieve_policy_evidence",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "tools_called": ["knowledge_service.search"],
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


def _knowledge_merchant_scope(value: object) -> list[str]:
    """Project trusted merchant scope into a validated string list for KnowledgeContext.

    Handles three input shapes from the router:
    - Structured dict: ``{"merchant_ids": ["m1", "m2"], ...}`` — extract only ``merchant_ids``.
    - Legacy list: ``["m1", "m2"]`` — validate directly.
    - Anything else (None, wrong type, missing keys): fail closed with ``[]``.

    Every ID must be a non-empty string. Non-string or empty entries cause the
    entire projection to fail closed.  Returns a copied list so the caller
    cannot mutate the original.
    """
    raw_ids: object = None
    if isinstance(value, dict):
        raw_ids = value.get("merchant_ids")
    elif isinstance(value, list):
        raw_ids = value

    if not isinstance(raw_ids, list) or len(raw_ids) == 0:
        return []

    validated: list[str] = []
    for item in raw_ids:
        if not isinstance(item, str) or not item:
            return []
        validated.append(item)
    return list(validated)


async def retrieve_policy_evidence(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    effective_at = state.get("run_started_at") or _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable["session"]
    active_slots = state.get("active_slots") or {}
    merchant_scope = _knowledge_merchant_scope(configurable.get("merchant_scope"))

    # Spec Consistency Finding: structured merchant_scope.merchant_ids is projected
    # into KnowledgeContext via _knowledge_merchant_scope.  Dedicated trace_id and
    # broader MerchantScopeV1 plumbing remain owned by Phase 10.
    context = KnowledgeContext(
        tenant_id=state["tenant_id"],
        user_id=state["user_id"],
        role=state["role"],
        merchant_scope=merchant_scope,
        run_id=state.get("current_run_id") or "",
        trace_id=state.get("current_run_id") or "",
        locale=None,
        effective_at=effective_at,
    )
    request = KnowledgeSearchRequest(
        query=_build_search_query(state),
        primary_intent=state.get("current_intent"),
        filters=KnowledgeSearchFilters(
            tenant_id=state["tenant_id"],
            merchant_id=active_slots.get("merchant_id"),
            effective_at=effective_at,
            locale=None,
        ),
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        max_results=5,
        allow_partial_evidence=True,
    )
    service = PolicyKnowledgeService(LegacyRagKnowledgeAdapter(session))
    result = await service.search(request, context)

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
