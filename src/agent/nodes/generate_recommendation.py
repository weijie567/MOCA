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
from src.agent.rag_context import (
    ContextBuilder,
    MaterialClaim,
    MaterialClaimAuthorityClass,
    MaterialClaimVerifier,
    RagContextBudget,
    determine_verification_route,
)
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
from src.tools.contracts import BusinessFactRefV1, ToolResultPromptSummary

logger = logging.getLogger(__name__)
_TRUNCATION_MARKER = " [truncated]"
_ACTIONABLE_RECOMMENDATIONS = {
    "issue_coupon",
    "approve_refund",
    "full_refund",
    "partial_refund",
    "compensation",
}


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
    rag_bundle = await _build_rag_context_bundle(state, config, evidence_models)
    evidence_by_id = {item["evidence_id"]: item for item in evidence_items}
    evidence_id_by_citation = _evidence_id_by_citation(rag_bundle, evidence_items)
    allowed_citations = _allowed_citation_objects(_evidence_items_from_bundle(rag_bundle, evidence_items))
    prompt_assembly = await _assemble_recommendation_prompt(
        state=state,
        config=config,
        allowed_citations=allowed_citations,
        policy_snippets=_policy_snippets_from_bundle(rag_bundle),
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
            cited_evidence_ids = [
                evidence_id_by_citation.get(
                    (item.get("doc_key"), item.get("chunk_id")),
                    f"unresolved:{item.get('doc_key')}:{item.get('chunk_id')}",
                )
                for item in draft.get("evidence_refs") or []
            ]
            membership_claims = [
                {
                    "claim_id": "rec-1",
                    "claim_text": draft["reasoning_summary"],
                    "cited_evidence_ids": cited_evidence_ids,
                }
            ]
            validation = validate_membership(membership_claims, evidence_models)
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
                    cited_evidence_ids = []
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
            material_claims = _material_claims_from_draft(draft, cited_evidence_ids, rag_bundle)
            verification = await _verify_recommendation_with_shared_kernel(
                draft=draft,
                claims=material_claims,
                context_bundle=rag_bundle,
                citation_validation=validation.model_dump(),
            )
            route_value = _verification_route_value(verification)
            _apply_verification_to_draft(draft, verification, material_claims)
            validated_refs = _validated_evidence_refs(cited_evidence_ids, evidence_by_id)
            if route_value != "allow":
                validated_refs = []
            merged_refs = _merge_evidence_refs(state.get("evidence_refs"), validated_refs)
            outputs = {**(state.get("llm_outputs") or {}), "generate_recommendation": draft}
            return {
                "recommendation_draft": draft,
                "rag_context_bundle": _state_safe_rag_context_bundle(rag_bundle),
                "rag_verification": verification,
                "verifier_status": str(verification.get("overall_outcome") or ""),
                "verification_route": route_value,
                "verifier_reason_codes": [str(code) for code in verification.get("reason_codes") or [] if str(code)],
                "verifier_safe_citation_refs": [
                    str(ref) for ref in verification.get("safe_citation_refs") or [] if str(ref)
                ],
                "verifier_metrics": _safe_verifier_metrics(verification.get("metrics")),
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
        "verification_route": "insufficient_evidence",
        "verifier_status": "insufficient",
        "verifier_reason_codes": ["recommendation_generation_failed"],
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


async def _build_rag_context_bundle(
    state: AgentState,
    config: RunnableConfig | None,
    evidence_models: list[EvidenceRefV1],
) -> Any:
    builder = ContextBuilder(
        policy_service=_policy_service(config),
        budget=RagContextBudget(
            max_prompt_chars=MAX_PROMPT_EVIDENCE_TOTAL_CHARS,
            max_snippet_chars=MAX_EVIDENCE_TEXT_CHARS + len(_TRUNCATION_MARKER),
            max_evidence_items=MAX_PROMPT_EVIDENCE_ITEMS,
        ),
    )
    return await builder.build(
        candidate_evidence_refs=evidence_models,
        business_fact_refs=_business_fact_refs_from_state(state),
        trusted_context={
            "tenant_id": state.get("tenant_id"),
            "run_id": state.get("current_run_id") or state.get("run_id"),
            "thread_id": state.get("thread_id"),
            "effective_at": state.get("effective_at") or _now_iso(),
            "context_builder_mode": _context_builder_mode(config),
        },
        risk_hints=_risk_hints_from_state(state),
    )


def _policy_service(config: RunnableConfig | None) -> Any:
    session = ((config or {}).get("configurable") or {}).get("session")
    if session is None:
        logger.warning("Policy evidence content re-fetch skipped because no session is available")
        return _NoopPolicyService()
    return PolicyKnowledgeService(PolicyRetrievalEngine(session))


def _context_builder_mode(config: RunnableConfig | None) -> str:
    session = ((config or {}).get("configurable") or {}).get("session")
    return "missing_session_compat" if session is None else "verified"


class _NoopPolicyService:
    async def get_verified_evidence_contents(
        self, *, tenant_id: str, evidence_refs: list[EvidenceRefV1]
    ) -> dict[str, str]:
        return {}


async def _verify_recommendation_with_shared_kernel(
    *,
    draft: dict[str, Any],
    claims: list[MaterialClaim],
    context_bundle: Any,
    citation_validation: dict[str, Any],
) -> dict[str, Any]:
    verifier = MaterialClaimVerifier()
    if hasattr(verifier, "verify_recommendation"):
        result = await verifier.verify_recommendation(
            draft=draft,
            claims=claims,
            context_bundle=context_bundle,
            citation_validation=citation_validation,
        )
        return _normalize_recommendation_verification(result)

    if claims and citation_validation.get("is_valid") is True and _missing_session_compat(context_bundle):
        route = determine_verification_route({"overall_outcome": "supported", "reason_codes": []})
        return _normalize_recommendation_verification(
            {
                "overall_outcome": "supported",
                "allows_recommendation": True,
                "route": route,
                "material_claims": _safe_material_claims(claims),
                "reason_codes": [],
                "safe_citation_refs": [evidence_id for claim in claims for evidence_id in claim.cited_evidence_ids],
                "metrics": route.metrics,
            }
        )

    verification_results = []
    for claim in claims:
        dependency_results = [result.model_dump(mode="json") for result in verification_results]
        verification_results.append(
            await verifier.verify_claim(
                claim,
                context_bundle=context_bundle,
                dependency_results=dependency_results,
            )
        )
    if not verification_results:
        route = determine_verification_route(
            {"overall_outcome": "insufficient", "reason_codes": ["policy_evidence_required"]}
        )
        return _normalize_recommendation_verification(
            {
                "overall_outcome": "insufficient",
                "allows_recommendation": False,
                "route": route,
                "material_claims": [],
                "reason_codes": ["policy_evidence_required"],
                "safe_citation_refs": [],
                "metrics": route.metrics,
            }
        )

    reason_codes = _unique_text(code for result in verification_results for code in result.reason_codes)
    safe_refs = _unique_text(ref for result in verification_results for ref in result.safe_support_refs)
    overall = (
        "supported"
        if all(result.allows_claim for result in verification_results)
        else verification_results[0].outcome.value
    )
    route = determine_verification_route(
        {
            "overall_outcome": overall,
            "reason_codes": reason_codes,
            "risk_level": draft.get("risk_level"),
            "safe_citation_refs": safe_refs,
            "metrics": {
                "claim_count": len(verification_results),
                "supported_claim_count": sum(1 for result in verification_results if result.allows_claim),
            },
        }
    )
    return _normalize_recommendation_verification(
        {
            "overall_outcome": overall,
            "allows_recommendation": route.allow_recommendation,
            "route": route,
            "material_claims": _safe_material_claims(claims),
            "reason_codes": reason_codes,
            "safe_citation_refs": safe_refs,
            "metrics": route.metrics,
        }
    )


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
    if (
        session is None
        or not state.get("tenant_id")
        or not state.get("user_id")
        or not state.get("thread_id")
        or not run_id
    ):
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
                _tool_prompt_summary_from_record(record) for record in getattr(context, "tool_prompt_summaries", [])
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


def _business_fact_refs_from_state(state: AgentState) -> list[BusinessFactRefV1]:
    raw_refs: list[Any] = []
    business_context = state.get("business_context")
    if isinstance(business_context, dict):
        raw_refs.extend(business_context.get("business_fact_refs") or [])
    for tool_result in state.get("tool_results") or []:
        if isinstance(tool_result, dict):
            raw_refs.extend(tool_result.get("business_fact_refs") or [])
    refs: list[BusinessFactRefV1] = []
    for item in raw_refs:
        try:
            refs.append(BusinessFactRefV1.model_validate(item))
        except Exception:
            continue
    return refs


def _risk_hints_from_state(state: AgentState) -> list[dict[str, Any]]:
    hints = state.get("risk_hints")
    if isinstance(hints, list):
        return [dict(item) for item in hints if isinstance(item, dict)]
    return []


def _evidence_id_by_citation(
    context_bundle: Any, fallback_items: list[dict[str, Any]]
) -> dict[tuple[str | None, str | None], str]:
    mapping: dict[tuple[str | None, str | None], str] = {}
    for item in _evidence_items_from_bundle(context_bundle, fallback_items):
        evidence_id = item.get("evidence_id")
        if evidence_id:
            mapping[(item.get("doc_key"), item.get("chunk_id"))] = evidence_id
    return mapping


def _evidence_items_from_bundle(context_bundle: Any, fallback_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in _citation_map_entries(context_bundle):
        evidence_ref = _get_value(entry, "evidence_ref")
        ref = _dump_json(evidence_ref)
        if isinstance(ref, dict):
            items.append(ref)
    return items or fallback_items


def _policy_snippets_from_bundle(context_bundle: Any) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    for entry in _citation_map_entries(context_bundle):
        evidence_ref = _dump_json(_get_value(entry, "evidence_ref"))
        if not isinstance(evidence_ref, dict):
            continue
        snippets.append(
            {
                "doc_key": evidence_ref.get("doc_key"),
                "chunk_id": evidence_ref.get("chunk_id"),
                "evidence_id": evidence_ref.get("evidence_id"),
                "policy_version": evidence_ref.get("policy_version"),
                "score": evidence_ref.get("score"),
                "text": str(_get_value(entry, "snippet") or ""),
            }
        )
    return snippets


def _material_claims_from_draft(
    draft: dict[str, Any], cited_evidence_ids: list[str], context_bundle: Any
) -> list[MaterialClaim]:
    cited = [evidence_id for evidence_id in cited_evidence_ids if not evidence_id.startswith("unresolved:")]
    claim_text = _draft_claim_text(draft)
    if not cited or not claim_text:
        return []
    claims = [
        MaterialClaim(
            claim_id="claim-policy-1",
            claim_text=claim_text,
            authority_class=MaterialClaimAuthorityClass.POLICY_CLAIM,
            source_node="generate_recommendation",
            risk_level=draft.get("risk_level"),
            cited_evidence_ids=cited,
        )
    ]
    business_refs = _business_fact_refs_from_context_bundle(context_bundle)
    if _is_actionable_recommendation(draft.get("recommended_action")):
        if business_refs:
            claims.append(
                MaterialClaim(
                    claim_id="claim-business-1",
                    claim_text=claim_text,
                    authority_class=MaterialClaimAuthorityClass.BUSINESS_FACT_CLAIM,
                    source_node="generate_recommendation",
                    risk_level=draft.get("risk_level"),
                    business_fact_refs=business_refs,
                )
            )
        claims.append(
            MaterialClaim(
                claim_id="claim-action-1",
                claim_text=f"{draft.get('recommended_action')}: {claim_text}",
                authority_class=MaterialClaimAuthorityClass.ACTION_RECOMMENDATION_CLAIM,
                source_node="generate_recommendation",
                risk_level=draft.get("risk_level"),
                cited_evidence_ids=cited,
                business_fact_refs=business_refs,
                dependency_claim_ids=["claim-policy-1", "claim-business-1"],
            )
        )
    return claims


def _draft_claim_text(draft: dict[str, Any]) -> str:
    return str(draft.get("reasoning_summary") or draft.get("recommended_action") or "").strip()


def _is_actionable_recommendation(action: Any) -> bool:
    action_text = str(action or "").casefold()
    return any(token in action_text for token in _ACTIONABLE_RECOMMENDATIONS)


def _business_fact_refs_from_context_bundle(context_bundle: Any) -> list[BusinessFactRefV1]:
    verifier_context = _get_value(context_bundle, "verifier_context")
    raw_refs = _get_value(verifier_context, "business_fact_refs")
    if not isinstance(raw_refs, list):
        return []
    refs: list[BusinessFactRefV1] = []
    for item in raw_refs:
        try:
            refs.append(BusinessFactRefV1.model_validate(item))
        except Exception:
            continue
    return refs


def _normalize_recommendation_verification(value: Any) -> dict[str, Any]:
    raw = _dump_json(value)
    data = raw if isinstance(raw, dict) else {}
    route = _normalize_route(data.get("route"), data)
    return {
        "overall_outcome": str(data.get("overall_outcome") or data.get("outcome") or "unknown"),
        "allows_recommendation": bool(data.get("allows_recommendation") or route.get("route") == "allow"),
        "route": route,
        "material_claims": list(data.get("material_claims") or []),
        "reason_codes": [str(code) for code in data.get("reason_codes") or [] if str(code)],
        "safe_citation_refs": [
            str(ref) for ref in data.get("safe_citation_refs") or data.get("safe_support_refs") or [] if str(ref)
        ],
        "metrics": _safe_verifier_metrics(data.get("metrics")),
    }


def _normalize_route(route_value: Any, data: dict[str, Any]) -> dict[str, Any]:
    route_data = _dump_json(route_value)
    if isinstance(route_data, dict) and route_data.get("route"):
        return {
            "route": str(route_data.get("route")),
            "selected_by": "backend",
            "model_selected": False,
            "decision_source": str(route_data.get("decision_source") or "phase22_verifier"),
        }
    decision = determine_verification_route(data)
    return {
        "route": decision.route.value,
        "selected_by": decision.selected_by,
        "model_selected": decision.model_selected,
        "decision_source": decision.decision_source,
    }


def _apply_verification_to_draft(
    draft: dict[str, Any],
    verification: dict[str, Any],
    claims: list[MaterialClaim],
) -> None:
    route = _verification_route_value(verification)
    draft["verification_route"] = route
    draft["verification_status"] = verification.get("overall_outcome")
    draft["verification_reason_codes"] = verification.get("reason_codes") or []
    draft["material_claims"] = verification.get("material_claims") or [
        claim.model_dump(mode="json") for claim in claims
    ]
    if route != "allow":
        if draft.get("recommended_action") == "citation_invalid":
            return
        draft["recommended_action"] = route
        draft["confidence"] = 0.0
        missing = list(draft.get("missing_info") or [])
        if "Verification did not allow recommendation" not in missing:
            missing.append("Verification did not allow recommendation")
        draft["missing_info"] = missing


def _verification_route_value(verification: dict[str, Any]) -> str:
    route = verification.get("route")
    if isinstance(route, dict):
        return str(route.get("route") or "manual_review")
    return "manual_review"


def _state_safe_rag_context_bundle(context_bundle: Any) -> dict[str, Any]:
    citation_map: dict[str, Any] = {}
    for entry in _citation_map_entries(context_bundle):
        citation_id = str(_get_value(entry, "citation_id") or "")
        if not citation_id:
            continue
        citation_map[citation_id] = {
            "citation_id": citation_id,
            "source_evidence_ids": [
                str(value) for value in _get_value(entry, "source_evidence_ids") or [] if str(value)
            ],
            "risk_labels": [str(value) for value in _get_value(entry, "risk_labels") or [] if str(value)],
            "metadata": {
                str(key): str(value)
                for key, value in (_get_value(entry, "metadata") or {}).items()
                if key in {"doc_key", "chunk_id", "policy_version"}
            },
        }
    return {
        "schema_version": "rag_context_bundle_state_safe.v1",
        "citation_map": citation_map,
        "risk_labels": _safe_risk_labels(context_bundle),
    }


def _citation_map_entries(context_bundle: Any) -> list[Any]:
    citation_map = _get_value(context_bundle, "citation_map")
    if isinstance(citation_map, dict):
        return list(citation_map.values())
    return []


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _missing_session_compat(context_bundle: Any) -> bool:
    trusted = _get_value(context_bundle, "trusted_context")
    return isinstance(trusted, dict) and trusted.get("context_builder_mode") == "missing_session_compat"


def _safe_material_claims(claims: list[MaterialClaim]) -> list[dict[str, Any]]:
    return [
        {
            "claim_id": claim.claim_id,
            "authority_class": claim.authority_class.value,
            "source_node": claim.source_node,
            "risk_level": claim.risk_level,
            "cited_evidence_ids": list(claim.cited_evidence_ids),
            "business_fact_refs": [ref.model_dump(mode="json") for ref in claim.business_fact_refs],
            "dependency_claim_ids": list(claim.dependency_claim_ids),
        }
        for claim in claims
    ]


def _safe_risk_labels(context_bundle: Any) -> list[str]:
    prompt_context = _get_value(context_bundle, "prompt_context")
    labels = _get_value(prompt_context, "risk_labels")
    if isinstance(labels, list):
        return [str(label) for label in labels if str(label)]
    return []


def _dump_json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _dump_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_dump_json(item) for item in value]
    if hasattr(value, "__dict__"):
        return {key: _dump_json(item) for key, item in vars(value).items() if not key.startswith("_")}
    return value


def _safe_verifier_metrics(value: Any) -> dict[str, int | float | bool | str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): metric for key, metric in value.items() if isinstance(metric, int | float | bool | str)}


def _unique_text(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result
