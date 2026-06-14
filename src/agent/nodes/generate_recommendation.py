from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.prompts import GENERATE_RECOMMENDATION_SYSTEM
from src.agent.nodes.retrieve_policy_evidence import _merge_evidence_refs
from src.agent.schemas import RecommendationDraft
from src.agent.state import AgentState
from src.config import settings
from src.knowledge.citation import validate_membership
from src.knowledge.config import (
    MAX_EVIDENCE_TEXT_CHARS,
    MAX_PROMPT_EVIDENCE_ITEMS,
    MAX_PROMPT_EVIDENCE_TOTAL_CHARS,
)
from src.knowledge.retrieval import PolicyRetrievalEngine
from src.knowledge.schemas import EvidenceRefV1
from src.knowledge.service import PolicyKnowledgeService

logger = logging.getLogger(__name__)


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


def _trace_step(
    status: str,
    started_at: str,
    evidence_refs: list[dict[str, Any]] | None = None,
    provider_latency_ms: int | None = None,
    retry_count: int = 0,
    context_chars: int = 0,
) -> dict[str, Any]:
    step = {
        "node": "generate_recommendation",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "model_name": settings.llm_model,
        "prompt_tokens": None,
        "completion_tokens": None,
        "provider_latency_ms": provider_latency_ms,
        "retry_count": retry_count,
        "metrics_json": {
            "model": settings.llm_model,
            "provider": "dashscope",
            "context_chars": context_chars,
        },
    }
    if evidence_refs:
        step["evidence_refs"] = evidence_refs
    return step


def _retrieval_data(state: AgentState) -> dict[str, Any]:
    retrieved = state.get("retrieved_evidence") or {}
    return retrieved.get("data") or retrieved


def _summarize_business_context(context: dict[str, Any]) -> str:
    return json.dumps(context, ensure_ascii=False, sort_keys=True)[:2000]


def _summarize_evidence(
    evidence: list[dict[str, Any]],
    text_by_evidence_id: dict[str, str],
) -> str:
    items = []
    remaining_chars = MAX_PROMPT_EVIDENCE_TOTAL_CHARS
    for item in evidence[:MAX_PROMPT_EVIDENCE_ITEMS]:
        text = text_by_evidence_id.get(item.get("evidence_id") or "", "")
        bounded_text = text[: min(MAX_EVIDENCE_TEXT_CHARS, remaining_chars)]
        remaining_chars -= len(bounded_text)
        items.append(
            {
                "doc_key": item.get("doc_key"),
                "chunk_id": item.get("chunk_id"),
                "evidence_id": item.get("evidence_id"),
                "policy_version": item.get("policy_version"),
                "score": item.get("score"),
                "text": bounded_text,
            }
        )
    return json.dumps(items, ensure_ascii=False, sort_keys=True)


def _allowed_citation_objects(
    evidence: list[dict[str, Any]],
) -> str:
    refs = []
    for item in evidence[:MAX_PROMPT_EVIDENCE_ITEMS]:
        refs.append(
            {
                "doc_key": item.get("doc_key"),
                "chunk_id": item.get("chunk_id"),
                "evidence_id": item.get("evidence_id"),
                "title": "",
                "section": "",
            }
        )
    return json.dumps(refs, ensure_ascii=False, sort_keys=True)


def _validated_evidence_refs(
    cited_evidence_ids: list[str],
    evidence_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [evidence_by_id[evidence_id] for evidence_id in cited_evidence_ids if evidence_id in evidence_by_id]


async def generate_recommendation(state: AgentState, config: RunnableConfig = None) -> dict:
    started_at = _now_iso()
    existing_draft = state.get("recommendation_draft") or {}
    if existing_draft.get("recommended_action") in {"insufficient_evidence", "retrieval_error"}:
        return {"trace_steps": (state.get("trace_steps") or []) + [_trace_step("skipped", started_at)]}

    evidence_items = list(_retrieval_data(state).get("evidence_refs") or [])
    evidence_models = [EvidenceRefV1(**item) for item in evidence_items]
    text_by_evidence_id: dict[str, str] = {}
    session = ((config or {}).get("configurable") or {}).get("session")
    if session is None:
        logger.warning("Policy evidence content re-fetch skipped because no session is available")
    else:
        try:
            text_by_evidence_id = await PolicyKnowledgeService(
                PolicyRetrievalEngine(session)
            ).get_verified_evidence_contents(
                tenant_id=state["tenant_id"],
                evidence_refs=evidence_models,
            )
        except Exception:
            logger.warning("Policy evidence content re-fetch failed; continuing without grounded text")
    evidence_by_id = {item["evidence_id"]: item for item in evidence_items}
    evidence_id_by_citation = {
        (item.get("doc_key"), item.get("chunk_id")): item["evidence_id"] for item in evidence_items
    }
    allowed_citations = _allowed_citation_objects(evidence_items)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": GENERATE_RECOMMENDATION_SYSTEM},
        {
            "role": "user",
            "content": (
                f"User query: {state.get('user_query') or ''}\n"
                f"Business context: {_summarize_business_context(state.get('business_context') or {})}\n"
                f"Policy evidence: {_summarize_evidence(evidence_items, text_by_evidence_id)}\n"
                f"Allowed citation objects: {allowed_citations}\n"
                "For evidence_refs, copy one or more complete objects from Allowed citation objects. "
                "For each material claim, rely only on the evidence_id in those objects. "
                "Do not return strings, doc_key-only values, or chunk_id-only values."
            ),
        },
    ]
    structured_llm = _get_llm().with_structured_output(RecommendationDraft)
    last_error: str | None = None
    provider_latency_ms: int | None = None
    retry_count = 0

    # retry_count records this node's manual structured-output retry loop, not LangGraph node retries.
    for attempt in range(2):
        retry_count = attempt
        try:
            t0 = time.perf_counter()
            result = await structured_llm.ainvoke(messages)
            provider_latency_ms = round((time.perf_counter() - t0) * 1000)
            draft = result.model_dump()
            # RecommendationDraft stays stable; deterministically project its citations into one material claim.
            cited_evidence_ids = [
                evidence_id_by_citation.get(
                    (item.get("doc_key"), item.get("chunk_id")),
                    f"unresolved:{item.get('doc_key')}:{item.get('chunk_id')}",
                )
                for item in draft.get("evidence_refs") or []
            ]
            claims = [
                {
                    "claim_id": "rec-1",
                    "claim_text": draft["reasoning_summary"],
                    "cited_evidence_ids": cited_evidence_ids,
                }
            ]
            validation = validate_membership(claims, evidence_models)
            if not validation.is_valid:
                invalid = {
                    evidence_id
                    for claim_result in validation.claim_results
                    for evidence_id in claim_result.missing_evidence_ids
                }
                draft["evidence_refs"] = [
                    item
                    for item, evidence_id in zip(draft.get("evidence_refs") or [], cited_evidence_ids, strict=True)
                    if evidence_id not in invalid
                ]
                cited_evidence_ids = [evidence_id for evidence_id in cited_evidence_ids if evidence_id not in invalid]
                if not draft["evidence_refs"]:
                    draft["recommended_action"] = "citation_invalid"
                    draft["missing_info"] = ["Citation membership validation failed"]
                    draft["confidence"] = 0.0
                else:
                    validation = validate_membership(
                        [
                            {
                                "claim_id": "rec-1",
                                "claim_text": draft["reasoning_summary"],
                                "cited_evidence_ids": cited_evidence_ids,
                            }
                        ],
                        evidence_models,
                    )
            draft["citation_validation"] = validation.model_dump()
            validated_refs = _validated_evidence_refs(cited_evidence_ids, evidence_by_id)
            merged_refs = _merge_evidence_refs(state.get("evidence_refs"), validated_refs)
            outputs = {**(state.get("llm_outputs") or {}), "generate_recommendation": draft}
            return {
                "recommendation_draft": draft,
                "llm_outputs": outputs,
                "evidence_refs": merged_refs,
                "trace_steps": (state.get("trace_steps") or [])
                + [
                    _trace_step(
                        "completed",
                        started_at,
                        validated_refs,
                        provider_latency_ms,
                        retry_count,
                        len(str(messages)),
                    )
                ],
            }
        except (ValidationError, ValueError, TimeoutError) as exc:
            provider_latency_ms = round((time.perf_counter() - t0) * 1000)
            last_error = str(exc)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Validation failed: {last_error}. Respond with valid JSON. "
                            f"evidence_refs must be complete objects copied from: {allowed_citations}"
                        ),
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
        "trace_steps": (state.get("trace_steps") or [])
        + [
            _trace_step(
                "error",
                started_at,
                provider_latency_ms=provider_latency_ms,
                retry_count=retry_count,
                context_chars=len(str(messages)),
            )
        ],
    }
