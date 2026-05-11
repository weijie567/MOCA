from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.prompts import GENERATE_RECOMMENDATION_SYSTEM
from src.agent.schemas import RecommendationDraft
from src.agent.state import AgentState
from src.config import settings
from src.rag.citation_validator import validate_citations
from src.rag.schemas import RetrievalResult


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.dashscope_api_key,
        openai_api_base=settings.embedding_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )


def _trace_step(status: str, started_at: str) -> dict[str, Any]:
    return {
        "node": "generate_recommendation",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "model_name": settings.llm_model,
        "prompt_tokens": None,
        "completion_tokens": None,
    }


def _retrieval_data(state: AgentState) -> dict[str, Any]:
    retrieved = state.get("retrieved_evidence") or {}
    return retrieved.get("data") or retrieved


def _retrieval_result(state: AgentState) -> RetrievalResult:
    data = _retrieval_data(state)
    return RetrievalResult(
        query=state.get("user_query") or "",
        retrieval_status=data.get("retrieval_status") or "no_evidence",
        evidence=data.get("evidence") or [],
        best_score=float(data.get("best_score") or 0.0),
        fallback_message=data.get("fallback_message"),
    )


def _summarize_business_context(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, sort_keys=True)[:2000]


def _summarize_evidence(evidence: list[dict[str, Any]]) -> str:
    items = []
    for item in evidence[:5]:
        items.append(
            {
                "doc_key": item.get("doc_key"),
                "chunk_id": item.get("chunk_id"),
                "title": item.get("title"),
                "section": item.get("section"),
                "score": item.get("score"),
                "text": (item.get("text") or "")[:1600],
            }
        )
    return json.dumps(items, ensure_ascii=False, sort_keys=True)


async def generate_recommendation(state: AgentState) -> dict:
    started_at = _now_iso()
    existing_draft = state.get("recommendation_draft") or {}
    if existing_draft.get("recommended_action") in {"insufficient_evidence", "retrieval_error"}:
        return {"trace_steps": (state.get("trace_steps") or []) + [_trace_step("skipped", started_at)]}

    retrieval = _retrieval_result(state)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": GENERATE_RECOMMENDATION_SYSTEM},
        {
            "role": "user",
            "content": (
                f"User query: {state.get('user_query') or ''}\n"
                f"Business context: {_summarize_business_context(state.get('business_context') or {})}\n"
                f"Policy evidence: {_summarize_evidence([item.model_dump() for item in retrieval.evidence])}"
            ),
        },
    ]
    structured_llm = _get_llm().with_structured_output(RecommendationDraft)
    last_error: str | None = None

    for attempt in range(2):
        try:
            result = await structured_llm.ainvoke(messages)
            draft = result.model_dump()
            cited_chunk_ids = [item["chunk_id"] for item in draft.get("evidence_refs") or []]
            validation = validate_citations(cited_chunk_ids, retrieval)
            if not validation.is_valid:
                invalid = set(validation.invalid_citations)
                draft["evidence_refs"] = [
                    item for item in draft.get("evidence_refs") or [] if item.get("chunk_id") not in invalid
                ]
                if not draft["evidence_refs"]:
                    draft["recommended_action"] = "citation_invalid"
                    draft["missing_info"] = [validation.reason or "Citation validation failed"]
                    draft["confidence"] = 0.0
            outputs = {**(state.get("llm_outputs") or {}), "generate_recommendation": draft}
            return {
                "recommendation_draft": draft,
                "llm_outputs": outputs,
                "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
            }
        except (ValidationError, ValueError, TimeoutError, Exception) as exc:
            last_error = str(exc)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Validation failed: {last_error}. Respond with valid JSON.",
                    }
                )

    return {
        "recommendation_draft": {
            "recommended_action": "insufficient_evidence",
            "reasoning_summary": "Recommendation generation failed validation.",
            "evidence_refs": [],
            "confidence": 0.0,
            "risk_level": "low",
            "missing_info": ["Recommendation generation failed"],
        },
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "generate_recommendation", "error": last_error, "retry_count": 2}],
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
    }
