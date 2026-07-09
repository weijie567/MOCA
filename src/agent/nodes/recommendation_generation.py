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
from src.agent.context.session_memory_bundle import load_session_prompt_context
from src.agent.intent_policy import INTENT_POLICY_REGISTRY
from src.agent.prompts import GENERATE_RECOMMENDATION_SYSTEM
from src.agent.routing import _partial_rag_context_can_generate
from src.agent.schemas import RecommendationDraft
from src.agent.state import AgentState
from src.agent.working_state import project_working_state
from src.config import settings
from src.knowledge.citation import validate_membership
from src.knowledge.config import (
    MAX_EVIDENCE_TEXT_CHARS,
    MAX_PROMPT_EVIDENCE_ITEMS,
    MAX_PROMPT_EVIDENCE_TOTAL_CHARS,
)
from src.knowledge.schemas import EvidenceRefV1, MaterialClaimV1, VerifiedEvidencePackageV1
from src.tools.contracts import BusinessFactRefV1

logger = logging.getLogger(__name__)
_TRUNCATION_MARKER = " [truncated]"
_ACTIONABLE_RECOMMENDATIONS = {
    "issue_coupon",
    "approve_refund",
    "full_refund",
    "partial_refund",
    "compensation",
}
_SAFE_EVIDENCE_RISK_LABELS = frozenset(
    {
        "authority_checked",
        "conflict",
        "freshness_risk",
        "high_risk",
        "latest_version_checked",
        "manual_review_sensitive",
        "ocr_low_confidence",
        "provenance_available",
        "source_locator_available",
        "stale_evidence",
    }
)
_ROUTING_RISK_LABELS = frozenset({"conflict", "manual_review_sensitive", "ocr_low_confidence", "stale_evidence"})


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
    *,
    trace_node: str = "recommendation_generation",
) -> dict[str, Any]:
    step = {
        "node": trace_node,
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
    evidence_by_id: dict[str, EvidenceRefV1],
) -> list[dict[str, Any]]:
    return [
        evidence_by_id[evidence_id].model_dump(mode="json")
        for evidence_id in cited_evidence_ids
        if evidence_id in evidence_by_id
    ]


def _merge_evidence_refs(
    existing: list[dict[str, Any]] | None,
    new: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str | None] = set()
    for ref in [*(existing or []), *(new or [])]:
        ref_payload = ref.model_dump(mode="json") if hasattr(ref, "model_dump") else ref
        if not isinstance(ref_payload, dict):
            continue
        key = ref_payload.get("evidence_id")
        if key in seen:
            continue
        seen.add(key)
        merged.append(ref_payload)
    return merged


async def recommendation_generation(state: AgentState, config: RunnableConfig = None) -> dict:
    """Canonical recommendation generation graph node."""
    started_at = _now_iso()
    existing_draft = state.get("recommendation_draft") or {}
    if existing_draft.get("recommended_action") in {"insufficient_evidence", "retrieval_error"}:
        return {"trace_steps": (state.get("trace_steps") or []) + [_trace_step("skipped", started_at)]}

    package = _verified_package_from_state(state)
    if not _package_allows_generation(state, package):
        return _insufficient_verified_package_result(
            state,
            started_at,
            reason_codes=_verified_package_reason_codes(state, package),
        )

    evidence_by_id = _evidence_by_id_from_package(state, package)
    evidence_models = list(evidence_by_id.values())
    evidence_id_by_citation = _evidence_id_by_citation(state, package)
    allowed_citations = _allowed_citation_objects_from_package(state, package)
    prompt_assembly = await _assemble_recommendation_prompt(
        state=state,
        config=config,
        allowed_citations=allowed_citations,
        policy_snippets=_policy_snippets_from_package(state, package),
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
            material_claims = _material_claims_from_draft(draft, cited_evidence_ids, state)
            material_claim_payloads = [claim.model_dump(mode="json") for claim in material_claims]
            draft["material_claims"] = material_claim_payloads
            validated_refs = _validated_evidence_refs(cited_evidence_ids, evidence_by_id)
            merged_refs = _merge_evidence_refs(None, validated_refs)
            outputs = {**(state.get("llm_outputs") or {}), "recommendation_generation": draft}
            return {
                "recommendation_draft": draft,
                "material_claims": material_claim_payloads,
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
        "material_claims": [],
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "recommendation_generation", "error": last_error, "retry_count": 2}],
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


def _verified_package_from_state(state: AgentState) -> VerifiedEvidencePackageV1 | None:
    value = state.get("verified_evidence_package")
    if value is None:
        return None
    try:
        return value if isinstance(value, VerifiedEvidencePackageV1) else VerifiedEvidencePackageV1.model_validate(value)
    except Exception:
        return None


def _package_allows_generation(state: AgentState, package: VerifiedEvidencePackageV1 | None) -> bool:
    if package is None:
        return not _policy_evidence_required_for_generation(state)
    if package.status == "verified":
        return True
    if package.status == "not_required":
        return not _policy_evidence_required_for_generation(state)
    if package.status == "partial":
        return _partial_package_can_generate(state, package)
    return False


def _verified_package_reason_codes(
    state: AgentState,
    package: VerifiedEvidencePackageV1 | None,
) -> list[str]:
    if package is None:
        return ["verified_evidence_package_required"] if _policy_evidence_required_for_generation(state) else []
    if package.reason_codes:
        return list(package.reason_codes)
    return [f"rag_context_{package.status}"]


def _policy_evidence_required_for_generation(state: AgentState) -> bool:
    evidence_policy = state.get("evidence_policy")
    if isinstance(evidence_policy, dict) and isinstance(evidence_policy.get("evidence_required"), bool):
        return bool(evidence_policy["evidence_required"])
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    if isinstance(routing_hints.get("policy_evidence_required"), bool):
        return bool(routing_hints["policy_evidence_required"])
    requested_operation = state.get("requested_operation")
    if requested_operation in {"draft_action", "execute_action", "escalate"}:
        return True
    intent = str(state.get("primary_intent") or state.get("current_intent") or "")
    try:
        return INTENT_POLICY_REGISTRY.requires_evidence(intent)
    except Exception:
        return True


def _partial_package_can_generate(state: AgentState, package: VerifiedEvidencePackageV1) -> bool:
    if not package.evidence_map:
        return False
    router_state = {**state, "verified_evidence_package": package.model_dump(mode="python")}
    return _partial_rag_context_can_generate(router_state)


def _insufficient_verified_package_result(
    state: AgentState,
    started_at: str,
    *,
    reason_codes: list[str],
) -> dict[str, Any]:
    missing_info = ["Verified policy evidence is required before recommendation generation."]
    if reason_codes:
        missing_info.append(f"RAG context status blocked generation: {', '.join(reason_codes)}")
    draft = {
        "recommended_action": "insufficient_evidence",
        "reasoning_summary": "Recommendation generation requires a usable verified evidence package.",
        "evidence_refs": [],
        "confidence": 0.0,
        "risk_level": "low",
        "missing_info": missing_info,
        "material_claims": [],
    }
    outputs = {**(state.get("llm_outputs") or {}), "recommendation_generation": draft}
    return {
        "recommendation_draft": draft,
        "material_claims": [],
        "llm_outputs": outputs,
        "evidence_refs": [],
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("insufficient_evidence", started_at, context_chars=0)],
    }


async def _assemble_recommendation_prompt(
    *,
    state: AgentState,
    config: RunnableConfig | None,
    allowed_citations: str,
    policy_snippets: list[dict[str, Any]],
) -> PromptAssembly:
    prompt_context = await load_session_prompt_context(state, config)
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
        memory_context_bundle=state.get("memory_context_bundle") or state.get("session_context_bundle"),
        node_hints=[
            f"Allowed citation objects: {allowed_citations}",
            "For evidence_refs, copy one or more complete objects from Allowed citation objects.",
            "For each material claim, rely only on the evidence_id in those objects.",
            "Do not return strings, doc_key-only values, or chunk_id-only values.",
        ],
    )


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
    result: list[dict[str, Any]] = []
    hints = state.get("risk_hints")
    if isinstance(hints, list):
        result.extend(dict(item) for item in hints if isinstance(item, dict))
    result.extend(_risk_hints_from_evidence_items(list(_retrieval_data(state).get("evidence_refs") or [])))
    return _merge_risk_hints(result)


def _risk_hints_from_evidence_items(evidence_items: list[Any]) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for item in evidence_items:
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("evidence_id") or "")
        labels = [str(label) for label in item.get("risk_labels") or [] if str(label) in _SAFE_EVIDENCE_RISK_LABELS]
        if evidence_id and labels:
            hints.append({"evidence_id": evidence_id, "labels": _unique_text(labels)})
    return hints


def _merge_risk_hints(hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels_by_evidence_id: dict[str, list[str]] = {}
    for hint in hints:
        evidence_id = str(hint.get("evidence_id") or "")
        if not evidence_id:
            continue
        labels = labels_by_evidence_id.setdefault(evidence_id, [])
        for label in hint.get("labels") or []:
            label_text = str(label)
            if label_text and label_text not in labels:
                labels.append(label_text)
    return [
        {"evidence_id": evidence_id, "labels": labels}
        for evidence_id, labels in labels_by_evidence_id.items()
        if labels
    ]


def _evidence_by_id_from_package(
    state: AgentState,
    package: VerifiedEvidencePackageV1 | None,
) -> dict[str, EvidenceRefV1]:
    raw_map = package.evidence_map if package is not None else state.get("evidence_map")
    if not isinstance(raw_map, dict):
        return {}
    evidence_by_id: dict[str, EvidenceRefV1] = {}
    for evidence_id, value in raw_map.items():
        try:
            evidence_by_id[str(evidence_id)] = value if isinstance(value, EvidenceRefV1) else EvidenceRefV1.model_validate(value)
        except Exception:
            continue
    return evidence_by_id


def _evidence_id_by_citation(
    state: AgentState,
    package: VerifiedEvidencePackageV1 | None,
) -> dict[tuple[str | None, str | None], str]:
    mapping: dict[tuple[str | None, str | None], str] = {}
    evidence_by_id = _evidence_by_id_from_package(state, package)
    for evidence_id in _citation_evidence_ids(state, package):
        ref = evidence_by_id.get(evidence_id)
        if ref is not None:
            mapping[(ref.doc_key, ref.chunk_id)] = ref.evidence_id
    for ref in evidence_by_id.values():
        mapping.setdefault((ref.doc_key, ref.chunk_id), ref.evidence_id)
    return mapping


def _citation_evidence_ids(state: AgentState, package: VerifiedEvidencePackageV1 | None) -> list[str]:
    citation_map = package.citation_map if package is not None else state.get("citation_map")
    if not isinstance(citation_map, dict):
        return []
    ids: list[str] = []
    for values in citation_map.values():
        if not isinstance(values, list):
            continue
        ids.extend(str(value) for value in values if str(value))
    return _unique_text(ids)


def _allowed_citation_objects_from_package(
    state: AgentState,
    package: VerifiedEvidencePackageV1 | None,
) -> str:
    evidence_by_id = _evidence_by_id_from_package(state, package)
    refs = [
        {
            "doc_key": ref.doc_key,
            "chunk_id": ref.chunk_id,
            "evidence_id": ref.evidence_id,
            "title": "",
            "section": "",
        }
        for ref in evidence_by_id.values()
    ]
    refs.sort(key=lambda item: (item["doc_key"], item["chunk_id"], item["evidence_id"]))
    return json.dumps(refs[:MAX_PROMPT_EVIDENCE_ITEMS], ensure_ascii=False, sort_keys=True)


def _policy_snippets_from_package(
    state: AgentState,
    package: VerifiedEvidencePackageV1 | None,
) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    evidence_by_id = _evidence_by_id_from_package(state, package)
    prompt_projection = package.prompt_projection if package is not None else {}
    citations = prompt_projection.get("citations") if isinstance(prompt_projection, dict) else None
    if not isinstance(citations, list):
        return []
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        metadata = citation.get("metadata") if isinstance(citation.get("metadata"), dict) else {}
        evidence_id = _first_citation_evidence_id(citation, state, package)
        ref = evidence_by_id.get(evidence_id) if evidence_id else None
        snippets.append(
            {
                "doc_key": ref.doc_key if ref is not None else metadata.get("doc_key"),
                "chunk_id": ref.chunk_id if ref is not None else metadata.get("chunk_id"),
                "evidence_id": ref.evidence_id if ref is not None else evidence_id,
                "policy_version": ref.policy_version if ref is not None else metadata.get("policy_version"),
                "title": citation.get("display_label") or "",
                "section": citation.get("citation_id") or "",
                "text": _bounded_policy_text(str(citation.get("snippet") or "")),
            }
        )
    return snippets


def _first_citation_evidence_id(
    citation: dict[str, Any],
    state: AgentState,
    package: VerifiedEvidencePackageV1 | None,
) -> str | None:
    citation_id = str(citation.get("citation_id") or "")
    citation_map = package.citation_map if package is not None else state.get("citation_map")
    if citation_id and isinstance(citation_map, dict):
        values = citation_map.get(citation_id)
        if isinstance(values, list):
            for value in values:
                if str(value):
                    return str(value)
    evidence_id = citation.get("evidence_id")
    return str(evidence_id) if evidence_id else None


def _bounded_policy_text(value: str) -> str:
    if len(value) <= MAX_EVIDENCE_TEXT_CHARS:
        return value
    return value[: max(0, MAX_EVIDENCE_TEXT_CHARS - len(_TRUNCATION_MARKER))] + _TRUNCATION_MARKER


def _material_claims_from_draft(
    draft: dict[str, Any],
    cited_evidence_ids: list[str],
    state: AgentState,
) -> list[MaterialClaimV1]:
    cited = [evidence_id for evidence_id in cited_evidence_ids if not evidence_id.startswith("unresolved:")]
    claim_text = _draft_claim_text(draft)
    if not cited or not claim_text:
        return []
    risk_hints = _claim_risk_hints(draft, state)
    claims = [
        MaterialClaimV1(
            claim_id="claim-policy-1",
            claim_text=claim_text,
            claim_type="policy",
            generated_from_step="recommendation_generation",
            risk_hints=risk_hints,
            cited_evidence_ids=cited,
        )
    ]
    business_refs = _business_fact_refs_from_state(state)
    if _is_actionable_recommendation(draft.get("recommended_action")):
        if business_refs:
            claims.append(
                MaterialClaimV1(
                    claim_id="claim-business-1",
                    claim_text=claim_text,
                    claim_type="business_fact",
                    generated_from_step="recommendation_generation",
                    risk_hints=risk_hints,
                    business_fact_refs=business_refs,
                )
            )
        claims.append(
            MaterialClaimV1(
                claim_id="claim-action-1",
                claim_text=f"{draft.get('recommended_action')}: {claim_text}",
                claim_type="action_recommendation",
                generated_from_step="recommendation_generation",
                risk_hints=risk_hints,
                cited_evidence_ids=cited,
                business_fact_refs=business_refs,
            )
        )
    return claims


def _draft_claim_text(draft: dict[str, Any]) -> str:
    return str(draft.get("reasoning_summary") or draft.get("recommended_action") or "").strip()


def _claim_risk_hints(draft: dict[str, Any], state: AgentState) -> list[str]:
    hints: list[str] = []
    risk_level = draft.get("risk_level")
    if isinstance(risk_level, str) and risk_level:
        hints.append(f"risk_level:{risk_level}")
    requested_operation = state.get("requested_operation")
    if isinstance(requested_operation, str) and requested_operation:
        hints.append(f"requested_operation:{requested_operation}")
    if _is_actionable_recommendation(draft.get("recommended_action")):
        hints.append("action_recommendation")
    return _unique_text(hints)


def _is_actionable_recommendation(action: Any) -> bool:
    action_text = str(action or "").casefold()
    return any(token in action_text for token in _ACTIONABLE_RECOMMENDATIONS)


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


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


def _unique_text(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result
