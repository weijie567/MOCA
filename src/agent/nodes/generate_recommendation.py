from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.context import ContextAssembler, PromptAssembly
from src.agent.prompts import GENERATE_RECOMMENDATION_SYSTEM
from src.agent.schemas import RecommendationDraft
from src.agent.state import AgentState
from src.agent.working_state import project_working_state
from src.config import settings
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.knowledge.citation import validate_membership
from src.knowledge.config import (
    MAX_EVIDENCE_TEXT_CHARS,
    MAX_PROMPT_EVIDENCE_ITEMS,
    MAX_PROMPT_EVIDENCE_TOTAL_CHARS,
)
from src.knowledge.retrieval import PolicyRetrievalEngine
from src.knowledge.schemas import EvidenceRefV1
from src.knowledge.service import PolicyKnowledgeService
from src.tools.contracts import ToolResultPromptSummary

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


def _policy_snippets(
    evidence: list[dict[str, Any]],
    text_by_evidence_id: dict[str, str],
) -> list[dict[str, Any]]:
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
    return items


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
    prompt_assembly = await _assemble_recommendation_prompt(
        state=state,
        config=config,
        allowed_citations=allowed_citations,
        policy_snippets=_policy_snippets(evidence_items, text_by_evidence_id),
    )
    messages = prompt_assembly.to_messages()
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
                        _messages_chars(messages),
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
                context_chars=_messages_chars(messages),
            )
        ],
    }


async def _assemble_recommendation_prompt(
    *,
    state: AgentState,
    config: RunnableConfig | None,
    allowed_citations: str,
    policy_snippets: list[dict[str, Any]],
) -> PromptAssembly:
    prompt_context = await _load_prompt_context(state, config)
    return ContextAssembler().assemble(
        system_prompt=GENERATE_RECOMMENDATION_SYSTEM,
        current_user_message=str(state.get("user_query") or ""),
        working_state=project_working_state(state),
        thread_rolling_summary=prompt_context["thread_rolling_summary"],
        recent_messages=prompt_context["recent_messages"],
        verified_policy_snippets=policy_snippets,
        profile_memory_snippets=state.get("long_term_memory") or [],
        case_memory_snippets=state.get("case_memory") or [],
        tool_result_summaries=[
            *prompt_context["tool_result_summaries"],
            *(state.get("tool_results") or []),
        ],
        business_context=state.get("business_context") or {},
        node_hints=[
            f"Allowed citation objects: {allowed_citations}",
            "For evidence_refs, copy one or more complete objects from Allowed citation objects.",
            "For each material claim, rely only on the evidence_id in those objects.",
            "Do not return strings, doc_key-only values, or chunk_id-only values.",
        ],
    )


async def _load_prompt_context(state: AgentState, config: RunnableConfig | None) -> dict[str, Any]:
    configurable = ((config or {}).get("configurable") or {}) if config else {}
    session = configurable.get("session")
    run_id = state.get("current_run_id") or state.get("run_id")
    if session is None or not state.get("tenant_id") or not state.get("user_id") or not state.get("thread_id") or not run_id:
        return _empty_prompt_context()

    service = configurable.get("conversation_service")
    if service is None:
        if not hasattr(session, "execute"):
            return _empty_prompt_context()
        service = ConversationService(ConversationRepository(session))

    try:
        context = await service.load_prompt_context(
            tenant_id=state["tenant_id"],
            user_id=state["user_id"],
            thread_id=str(state["thread_id"]),
            run_id=run_id,
        )
    except Exception:
        logger.warning("Prompt context load failed; continuing with current state only")
        return _empty_prompt_context()

    latest_summary = getattr(context, "latest_thread_summary", None)
    return {
        "thread_rolling_summary": getattr(latest_summary, "summary_text", None) or "",
        "recent_messages": [
            {"role": getattr(message, "role", "message"), "content": getattr(message, "content", "")}
            for message in getattr(context, "recent_messages", [])
        ],
        "tool_result_summaries": [
            summary
            for summary in (
                _tool_prompt_summary_from_record(record)
                for record in getattr(context, "tool_prompt_summaries", [])
            )
            if summary is not None
        ],
    }


def _empty_prompt_context() -> dict[str, Any]:
    return {"thread_rolling_summary": "", "recent_messages": [], "tool_result_summaries": []}


def _tool_prompt_summary_from_record(record: Any) -> ToolResultPromptSummary | None:
    if isinstance(record, ToolResultPromptSummary):
        return record
    payload = {
        "tool_call_id": getattr(record, "tool_call_id", ""),
        "tool_result_id": getattr(record, "tool_result_id", "") or str(getattr(record, "id", "")),
        "tool_name": getattr(record, "tool_name", "tool"),
        "status": getattr(record, "status", "success"),
        "summary": getattr(record, "summary", "") or "",
        "prompt_summary": getattr(record, "prompt_summary", "") or getattr(record, "summary", "") or "",
        "business_fact_refs": getattr(record, "business_fact_refs_json", []) or [],
        "policy_evidence_refs": getattr(record, "policy_evidence_refs_json", []) or [],
        "raw_result_ref": getattr(record, "raw_result_ref", None),
        "audit_ref": getattr(record, "audit_ref", None),
    }
    try:
        return ToolResultPromptSummary.model_validate(payload)
    except ValidationError:
        return None


def _messages_chars(messages: list[dict[str, str]]) -> int:
    return sum(len(message.get("content") or "") for message in messages)
