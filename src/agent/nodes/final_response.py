from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.agent.prompts import INSUFFICIENT_EVIDENCE_RESPONSE
from src.agent.state import AgentState

DEMO_NOT_EXECUTED_TEXT = "演示模式未执行优惠券发放、退款、工单关闭或任何外部动作"
_POLICY_QA_DISPLAYABLE_VERIFIER_REASONS = frozenset({"level2_partial_overlap_ambiguous"})
_INTERNAL_MISSING_INFO = frozenset(
    {
        "Citation membership validation failed",
        "Recommendation generation failed",
        "Verification did not allow recommendation",
    }
)
_VERIFICATION_REASON_TEXT = {
    "business_fact_missing": "业务事实不足",
    "build_error": "证据校验暂时不可用",
    "conflicting_evidence": "政策证据存在冲突",
    "invalid_hash": "政策证据校验未通过",
    "invalid_scope": "政策证据范围未通过校验",
    "level2_partial_overlap_ambiguous": "政策证据和处理动作之间仍有歧义",
    "missing_citation": "建议缺少可核验政策引用",
    "no_evidence": "当前政策证据不足",
    "ocr_low_confidence": "政策证据识别置信度偏低",
    "semantic_ambiguous": "政策证据和处理动作之间仍有歧义",
    "stale_evidence": "政策证据可能不是最新版本",
    "stale": "政策证据可能不是最新版本",
    "text_hash_mismatch": "政策证据校验未通过",
    "unauthorized": "当前政策证据不足",
    "unsupported": "建议没有被当前证据充分支持",
}
_BLOCKING_RAG_CONTEXT_STATUSES = frozenset(
    {
        "no_evidence",
        "unauthorized",
        "stale",
        "conflict",
        "invalid_hash",
        "invalid_scope",
        "build_error",
    }
)
_SAFE_PROJECTION_SOURCES = frozenset({"claim_verification_bundle", "verified_evidence_package"})
_ACTION_BOUNDARY_FIELDS = (
    "approval_result",
    "action_result",
    "action_draft",
    "draft_outcome",
    "proposed_action",
)
_SAFE_EVIDENCE_REF_KEYS = frozenset(
    {
        "evidence_id",
        "doc_key",
        "doc_id",
        "chunk_id",
        "title",
        "section",
        "section_title",
        "confidence",
        "score",
        "risk_level",
        "policy_version",
        "text_hash",
        "retrieved_at",
    }
)
_INTENT_DISPLAY_LABELS = {
    "policy_qa": "政策问题查询",
    "order_status_inquiry": "订单状态查询",
    "refund_troubleshooting": "退款问题排查",
    "compensation_suggestion": "补偿方案建议",
    "ticket_reply_draft": "工单回复草稿",
    "appeal_or_unban": "申诉/解封处理",
    "complaint_escalation": "投诉升级",
    "action_request": "执行动作请求",
    "small_talk": "闲聊",
    "unsupported": "未支持请求",
}
_OPERATION_DISPLAY_LABELS = {
    "read_status": "查询",
    "advise": "建议",
    "draft_reply": "拟回复",
    "draft_action": "拟动作",
    "execute_action": "执行动作",
    "escalate": "升级处理",
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _trace_step(
    status: str,
    started_at: str,
    evidence_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    step = {
        "node": "final_response",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "model_name": "deterministic-template",
        "prompt_tokens": None,
        "completion_tokens": None,
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": None,
    }
    safe_refs = _safe_display_evidence_refs(evidence_refs)
    if safe_refs:
        step["evidence_refs"] = safe_refs
    return step


def _safe_display_evidence_refs(evidence_refs: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    safe_refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ref in evidence_refs or []:
        if not isinstance(ref, dict):
            continue
        safe_ref = {key: value for key, value in ref.items() if key in _SAFE_EVIDENCE_REF_KEYS and value is not None}
        if not safe_ref:
            continue
        key = str(safe_ref.get("evidence_id") or f"{safe_ref.get('doc_key')}:{safe_ref.get('chunk_id')}")
        if key in seen:
            continue
        seen.add(key)
        safe_refs.append(safe_ref)
    return safe_refs


def _final_response_evidence_refs(state: AgentState, draft: dict[str, Any]) -> list[dict[str, Any]]:
    draft_refs = [ref for ref in draft.get("evidence_refs") or [] if isinstance(ref, dict)]
    if not draft_refs:
        return []

    full_refs_by_citation: dict[tuple[str, str], dict[str, Any]] = {}
    for ref in _state_evidence_ref_candidates(state):
        doc_key = str(ref.get("doc_key") or ref.get("doc_id") or "")
        chunk_id = str(ref.get("chunk_id") or "")
        if doc_key and chunk_id:
            full_refs_by_citation.setdefault((doc_key, chunk_id), ref)

    resolved_refs: list[dict[str, Any]] = []
    for ref in draft_refs:
        doc_key = str(ref.get("doc_key") or ref.get("doc_id") or "")
        chunk_id = str(ref.get("chunk_id") or "")
        resolved_refs.append(full_refs_by_citation.get((doc_key, chunk_id), ref))
    return resolved_refs


def _state_evidence_ref_candidates(state: AgentState) -> list[dict[str, Any]]:
    current_package_refs = _current_verified_package_evidence_refs(state)
    if current_package_refs:
        return current_package_refs

    candidates: list[dict[str, Any]] = []
    for value in (
        state.get("evidence_refs"),
        state.get("policy_evidence"),
        _retrieved_evidence_refs(state.get("retrieved_evidence")),
    ):
        if isinstance(value, list):
            candidates.extend(ref for ref in value if isinstance(ref, dict))
    return candidates


def _current_verified_package_evidence_refs(state: AgentState) -> list[dict[str, Any]]:
    package = _mapping(state.get("verified_evidence_package"))
    if package.get("status") not in {"verified", "partial"}:
        return []

    evidence_map = _mapping(package.get("evidence_map"))
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in (_mapping(state.get("claim_verification_bundle")).get("safe_support_refs"), state.get("safe_support_refs")):
        refs.extend(_resolve_package_evidence_refs(value, evidence_map, seen))
    refs.extend(_resolve_package_evidence_refs(list(evidence_map.values()), evidence_map, seen))
    return refs


def _resolve_package_evidence_refs(value: Any, evidence_map: dict[str, Any], seen: set[str]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list | tuple | set):
        items = list(value)
    else:
        items = []

    for item in items:
        raw_ref = evidence_map.get(item) if isinstance(item, str) else item
        ref = _mapping(raw_ref)
        if not ref:
            continue
        key = str(ref.get("evidence_id") or f"{ref.get('doc_key')}:{ref.get('chunk_id')}")
        if key in seen:
            continue
        seen.add(key)
        refs.append(ref)
    return refs


def _retrieved_evidence_refs(retrieved: Any) -> list[dict[str, Any]]:
    if not isinstance(retrieved, dict):
        return []
    data = retrieved.get("data")
    if isinstance(data, dict) and isinstance(data.get("evidence_refs"), list):
        return data["evidence_refs"]
    refs = retrieved.get("evidence_refs")
    return refs if isinstance(refs, list) else []


def _insufficient_response(draft: dict[str, Any]) -> str:
    missing_info = draft.get("missing_info") or []
    if not missing_info:
        return INSUFFICIENT_EVIDENCE_RESPONSE
    return f"{INSUFFICIENT_EVIDENCE_RESPONSE}\n缺少信息：{'、'.join(str(item) for item in missing_info)}"


def _retrieval_error_response(draft: dict[str, Any]) -> str:
    missing_info = draft.get("missing_info") or []
    suffix = f"原因：{'、'.join(str(item) for item in missing_info)}" if missing_info else ""
    return f"系统暂时无法检索政策依据，请稍后重试或联系人工客服。{suffix}"


def _business_context_summary(context: dict[str, Any]) -> str:
    parts: list[str] = []
    facts = _business_context_facts(context)
    order = _dict_value(facts.get("order"))
    refund_case = _dict_value(facts.get("refund_case"))
    ticket = _dict_value(facts.get("ticket"))

    if order:
        order_fields = [
            f"订单号 {order.get('order_no') or '未知'}",
            f"状态 {order.get('status') or '未知'}",
        ]
        if order.get("item_name"):
            order_fields.append(f"商品 {order['item_name']}")
        if order.get("amount"):
            currency = order.get("currency") or ""
            order_fields.append(f"金额 {order['amount']} {currency}".strip())
        hints = order.get("relation_hints") or {}
        hint_parts = []
        if hints.get("has_active_refund"):
            hint_parts.append("存在关联退款")
        if hints.get("has_open_ticket"):
            hint_parts.append("存在未关闭工单")
        if hint_parts:
            order_fields.append("；".join(hint_parts))
        parts.append(f"已查询到订单信息：{'，'.join(order_fields)}。")

    if refund_case:
        refund_fields = [
            f"退款单 {refund_case.get('refund_case_no') or '未知'}",
            f"状态 {refund_case.get('status') or '未知'}",
        ]
        reason = refund_case.get("reason_text") or refund_case.get("reason_code")
        if reason:
            refund_fields.append(f"原因 {reason}")
        if refund_case.get("requested_amount"):
            refund_fields.append(f"申请金额 {refund_case['requested_amount']}")
        if refund_case.get("approved_amount"):
            refund_fields.append(f"已批金额 {refund_case['approved_amount']}")
        parts.append(f"已查询到退款单信息：{'，'.join(refund_fields)}。")

    if ticket:
        ticket_fields = [
            f"工单 {ticket.get('ticket_no') or '未知'}",
            f"状态 {ticket.get('status') or '未知'}",
        ]
        if ticket.get("channel"):
            ticket_fields.append(f"渠道 {ticket['channel']}")
        if ticket.get("summary"):
            ticket_fields.append(f"摘要 {ticket['summary']}")
        parts.append(f"已查询到工单信息：{'，'.join(ticket_fields)}。")

    return "\n".join(parts)


def _business_context_facts(context: dict[str, Any]) -> dict[str, Any]:
    facts = context.get("facts")
    if isinstance(facts, dict):
        return facts
    return context


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _insufficient_response_with_context(draft: dict[str, Any], context: dict[str, Any]) -> str:
    evidence_text = _insufficient_response(draft)
    fact_summary = _business_context_summary(context)
    if not fact_summary:
        return evidence_text
    return f"{fact_summary}\n关于退款风险：{evidence_text}"


def _business_fact_response(context: dict[str, Any]) -> str:
    fact_summary = _business_context_summary(context)
    if not fact_summary:
        return ""
    return f"当前查询结果：\n{fact_summary}"


def _business_fact_llm_output(response_text: str) -> dict[str, Any]:
    return {
        "response_text": response_text,
        "evidence_citations": [],
        "final_status": "completed",
        "mode": "deterministic-template",
        "approval_context": None,
    }


def _decorate_deferred_response(response_text: str, state: AgentState) -> str:
    additions: list[str] = []
    deferred_labels = _deferred_step_labels(state.get("deferred_steps"))
    if deferred_labels:
        listed = "\n".join(f"{index}. {label}" for index, label in enumerate(deferred_labels, start=1))
        additions.append(f"我还注意到你想继续处理：\n{listed}\n要我接着做哪一项吗？")
    if _has_plan_normalization(state, "modifier_folded:complaint_as_severity"):
        additions.append("已按「投诉情绪」处理本次诉求；如果你需要正式升级投诉，请告诉我。")
    if not additions:
        return response_text
    return "\n\n".join([response_text, *additions])


def _deferred_step_labels(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    for step in value:
        if not isinstance(step, dict):
            continue
        intent = str(step.get("intent") or "").strip()
        operation = str(step.get("operation") or "").strip()
        if not intent and not operation:
            continue
        intent_label = _INTENT_DISPLAY_LABELS.get(intent, intent or "后续请求")
        operation_label = _OPERATION_DISPLAY_LABELS.get(operation, operation)
        labels.append(f"{intent_label}（{operation_label}）" if operation_label else intent_label)
    return labels


def _has_plan_normalization(state: AgentState, expected: str) -> bool:
    trace = _classification_trace(state)
    records = trace.get("plan_normalization")
    if not isinstance(records, list):
        return False
    for record in records:
        if record == expected:
            return True
        if isinstance(record, dict) and expected in {str(value) for value in record.values()}:
            return True
    return False


def _classification_trace(state: AgentState) -> dict[str, Any]:
    trace = _mapping(state.get("classification_trace"))
    if trace:
        return trace
    llm_outputs = _mapping(state.get("llm_outputs"))
    intent_output = _mapping(llm_outputs.get("intent_classification"))
    return _mapping(intent_output.get("classification_trace"))


def _citation_summary(evidence_refs: list[dict[str, Any]]) -> str:
    if not evidence_refs:
        return ""
    citations = []
    for ref in evidence_refs[:3]:
        doc_key = ref.get("doc_key") or "unknown_doc"
        chunk_id = ref.get("chunk_id") or "unknown_chunk"
        citation = f"根据 {doc_key} / {chunk_id}"
        display_parts = [part for part in (ref.get("title"), ref.get("section")) if part]
        if display_parts:
            citation = f"{citation}，{' - '.join(str(part) for part in display_parts)}"
        citations.append(citation)
    return "；".join(citations)


def _completed_response(draft: dict[str, Any], risk_assessment: dict[str, Any]) -> str:
    action = draft.get("recommended_action") or "建议按已检索到的政策依据处理。"
    reasoning = draft.get("reasoning_summary") or "已根据当前知识库证据生成建议。"
    citations = _citation_summary(draft.get("evidence_refs") or [])
    parts = [f"建议：{action}", f"理由：{reasoning}"]
    if citations:
        parts.append(f"依据：{citations}。")
    if risk_assessment.get("approval_required"):
        risk_reason = risk_assessment.get("risk_reason") or "命中风险规则"
        parts.append(f"风险提示：{risk_reason}，需要人工审批后才能创建动作草稿。")
    return "\n".join(parts)


def _verification_route_payload(state: AgentState) -> dict[str, Any] | None:
    claim_verification = _claim_verification_route_payload(state)
    if claim_verification is not None:
        return claim_verification
    rag_context = _rag_context_route_payload(state)
    if rag_context is not None:
        return rag_context
    rag_verification = state.get("rag_verification")
    if isinstance(rag_verification, dict):
        route = rag_verification.get("route")
        if isinstance(route, dict) and route.get("route") and route.get("route") != "allow":
            return rag_verification
    route_value = state.get("verification_route")
    if isinstance(route_value, str) and route_value and route_value != "allow":
        return {
            "overall_outcome": state.get("verifier_status") or "unknown",
            "route": {
                "route": route_value,
                "selected_by": "backend",
                "model_selected": False,
                "decision_source": "phase22_verifier",
            },
            "reason_codes": state.get("verifier_reason_codes") or [],
        }
    return None


def _claim_verification_route_payload(state: AgentState) -> dict[str, Any] | None:
    bundle = _mapping(state.get("claim_verification_bundle"))
    blocked_claims = _string_values(state.get("blocked_claims")) or _string_values(bundle.get("blocked_claims"))
    route = str(bundle.get("route") or "")
    overall_status = str(bundle.get("overall_status") or state.get("verifier_status") or "")
    if not bundle and not blocked_claims:
        return None
    if route == "continue" and overall_status in {"verified", "not_required"} and not blocked_claims:
        return None
    selected_route = "manual_review" if route == "manual_review" or blocked_claims else "refuse"
    return {
        "overall_outcome": overall_status or "blocked",
        "route": {
            "route": selected_route,
            "selected_by": "backend",
            "model_selected": False,
            "decision_source": "claim_verify",
        },
        "reason_codes": _string_values(bundle.get("reason_codes")) or ["claim_verification_blocked"],
        "blocked_claims": blocked_claims,
        "safe_projection_source": "claim_verification_bundle",
    }


def _rag_context_route_payload(state: AgentState) -> dict[str, Any] | None:
    status = _rag_context_status(state)
    if status not in _BLOCKING_RAG_CONTEXT_STATUSES:
        return None
    route = "insufficient_evidence" if status == "no_evidence" else "manual_review"
    package = _mapping(state.get("verified_evidence_package"))
    return {
        "overall_outcome": status,
        "route": {
            "route": route,
            "selected_by": "backend",
            "model_selected": False,
            "decision_source": "rag_context_build",
        },
        "reason_codes": _string_values(package.get("reason_codes")) or [status],
        "safe_projection_source": "verified_evidence_package",
    }


def _rag_context_status(state: AgentState) -> str:
    status = state.get("rag_context_status")
    if isinstance(status, str) and status:
        return status
    package_status = _mapping(state.get("verified_evidence_package")).get("status")
    return package_status if isinstance(package_status, str) else ""


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _string_values(value: Any) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    return [text for item in value if (text := str(item).strip())]


def _verification_route_value(verification: dict[str, Any]) -> str:
    route = verification.get("route")
    if isinstance(route, dict):
        return str(route.get("route") or "manual_review")
    return "manual_review"


def _verification_final_status(route: str) -> str:
    if route == "manual_review":
        return "manual_review"
    if route == "refuse":
        return "refused"
    return "insufficient_evidence"


def _safe_verification_response(verification: dict[str, Any]) -> str:
    route = _verification_route_value(verification)
    reason_codes = {str(code) for code in verification.get("reason_codes") or []}
    if route == "regenerate_route":
        return "当前建议未通过证据支持校验，需要重新生成后再继续处理。"
    if route == "manual_review":
        return "当前证据状态需要人工复核，暂不能创建审批请求或动作草稿。"
    if route == "refuse":
        return "无法基于当前政策证据支持该建议，请补充有效证据或交由人工处理。"
    if "business_fact_missing" in reason_codes:
        return "业务事实不足，当前不能给出动作建议或创建审批请求。"
    return "没有找到足够证据支持该建议，当前不能继续创建审批请求或动作草稿。"


def _displayable_missing_info(draft: dict[str, Any]) -> list[str]:
    displayable: list[str] = []
    seen: set[str] = set()
    for item in draft.get("missing_info") or []:
        text = str(item).strip()
        if not text or text in _INTERNAL_MISSING_INFO or _looks_internal_missing_info(text):
            continue
        if text in seen:
            continue
        seen.add(text)
        displayable.append(text)
    return displayable


def _looks_internal_missing_info(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "context_builder",
            "membership",
            "verification",
            "verifier",
            "trace",
        )
    )


def _verification_reason_texts(verification: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for code in verification.get("reason_codes") or []:
        text = _VERIFICATION_REASON_TEXT.get(str(code))
        if not text or text in seen:
            continue
        seen.add(text)
        texts.append(text)
    return texts


def _manual_review_response(
    draft: dict[str, Any],
    verification: dict[str, Any],
    context: dict[str, Any],
    *,
    include_draft_missing_info: bool = True,
) -> str:
    fact_summary = _business_context_summary(context)
    parts: list[str] = []
    if fact_summary:
        parts.append(f"当前查询结果：\n{fact_summary}")
    parts.append("当前还不能给出具体处理动作：证据状态需要人工复核，系统未创建审批请求或动作草稿。")
    reasons = (_displayable_missing_info(draft) if include_draft_missing_info else []) or _verification_reason_texts(
        verification
    )
    if reasons:
        parts.append(f"需要补充或复核：{'、'.join(reasons)}。")
    return "\n".join(parts)


def _verification_llm_output(response_text: str, verification: dict[str, Any]) -> dict[str, Any]:
    route = _verification_route_value(verification)
    route_payload = verification.get("route") if isinstance(verification.get("route"), dict) else {}
    return {
        "response_text": response_text,
        "evidence_citations": [],
        "final_status": _verification_final_status(route),
        "mode": "deterministic-template",
        "approval_context": None,
        "verification_route": route,
        "route_selected_by": route_payload.get("selected_by") or "backend",
        "model_selected_route": bool(route_payload.get("model_selected")),
    }


def _state_intent(state: AgentState) -> str:
    value = state.get("primary_intent") or state.get("current_intent")
    return value if isinstance(value, str) else ""


def _has_action_boundary_state(state: AgentState) -> bool:
    return any(bool(state.get(field)) for field in _ACTION_BOUNDARY_FIELDS)


def _citation_validation_passed(draft: dict[str, Any]) -> bool:
    validation = draft.get("citation_validation")
    return isinstance(validation, dict) and validation.get("is_valid") is True


def _can_render_policy_qa_partial_overlap(
    state: AgentState,
    draft: dict[str, Any],
    verification: dict[str, Any],
) -> bool:
    if _state_intent(state) != "policy_qa":
        return False
    if state.get("requested_operation") not in (None, "advise", "read_status"):
        return False
    if _verification_route_value(verification) != "manual_review":
        return False
    if state.get("retrieval_status") != "strong_evidence":
        return False
    if _has_action_boundary_state(state):
        return False
    reason_codes = {str(code) for code in verification.get("reason_codes") or []}
    if not reason_codes or not reason_codes <= _POLICY_QA_DISPLAYABLE_VERIFIER_REASONS:
        return False
    return bool(draft.get("evidence_refs")) and _citation_validation_passed(draft)


def _can_render_business_fact_response(state: AgentState, draft: dict[str, Any]) -> bool:
    if _state_intent(state) != "order_status_inquiry":
        return False
    if state.get("requested_operation") not in (None, "read_status", "advise"):
        return False
    if _has_action_boundary_state(state):
        return False
    if draft.get("recommended_action"):
        return False
    return bool(_business_context_summary(state.get("business_context") or {}))


def _policy_qa_partial_overlap_response(draft: dict[str, Any]) -> str:
    reasoning = draft.get("reasoning_summary") or "已根据当前知识库证据生成政策说明。"
    citations = _citation_summary(draft.get("evidence_refs") or [])
    parts = [f"政策说明：{reasoning}"]
    if citations:
        parts.append(f"依据：{citations}。")
    return "\n".join(parts)


def _policy_qa_partial_overlap_llm_output(
    response_text: str,
    draft: dict[str, Any],
    verification: dict[str, Any],
) -> dict[str, Any]:
    output = _verification_llm_output(response_text, verification)
    output["final_status"] = "completed"
    output["evidence_citations"] = [
        f"{ref.get('doc_key')} / {ref.get('chunk_id')}" for ref in draft.get("evidence_refs") or []
    ]
    return output


def _is_successful_demo_draft_outcome(draft_outcome: object) -> bool:
    return (
        isinstance(draft_outcome, dict)
        and draft_outcome.get("status") == "not_executed_demo"
        and draft_outcome.get("external_side_effect") is False
    )


def _draft_id(action_draft: object, draft_outcome: object) -> str:
    if isinstance(draft_outcome, dict) and draft_outcome.get("draft_id"):
        return str(draft_outcome["draft_id"])
    if isinstance(action_draft, dict):
        draft_id = action_draft.get("draft_id") or action_draft.get("id")
        if draft_id:
            return str(draft_id)
    return "unknown"


def _draft_created_text(prefix: str, draft_id: str) -> str:
    return f"{prefix}：补偿草稿已创建（草稿ID：{draft_id}），{DEMO_NOT_EXECUTED_TEXT}。"


def _approval_outcome_text(
    approval_result: dict[str, Any] | None,
    action_result: dict[str, Any] | None,
    action_draft: dict[str, Any] | None,
    draft_outcome: dict[str, Any] | None,
) -> str:
    if approval_result:
        decision_type = approval_result.get("decision_type") or approval_result.get("decision")
        if decision_type in {"accept", "approve"}:
            if _is_successful_demo_draft_outcome(draft_outcome):
                return _draft_created_text("审批结果：操作已审批通过", _draft_id(action_draft, draft_outcome))
            if action_result:
                message = (action_result.get("error") or {}).get("message", "unknown error")
                return f"审批结果：操作已审批通过，但草稿创建失败：{message}。"
            return ""
        if decision_type in {"reject", "ignore"}:
            reason = approval_result.get("reason") or "No reason provided"
            if decision_type == "ignore":
                return f"审批结果：操作被取消。原因：{reason}。"
            return f"审批结果：操作被审核人拒绝。拒绝原因：{reason}。"

    if not approval_result and _is_successful_demo_draft_outcome(draft_outcome):
        draft_id = _draft_id(action_draft, draft_outcome)
        return _draft_created_text("草稿结果：该操作在政策范围内，无需审批", draft_id)

    return ""


async def final_response(state: AgentState) -> dict:
    started_at = _now_iso()
    draft = state.get("recommendation_draft") or {}
    approval_result = state.get("approval_result")
    action_result = state.get("action_result")
    action_draft = state.get("action_draft")
    draft_outcome = state.get("draft_outcome")
    clarification_request = state.get("clarification_request")
    blocked_response = state.get("final_response")
    if blocked_response and state.get("safety_snapshot_verified") is False:
        response_text = _decorate_deferred_response(str(blocked_response), state)
        return {
            "final_response": response_text,
            "llm_outputs": {
                **(state.get("llm_outputs") or {}),
                "final_response": {
                    "response_text": response_text,
                    "evidence_citations": [],
                    "final_status": "error",
                    "mode": "deterministic-template",
                    "approval_context": None,
                },
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }
    if isinstance(clarification_request, dict):
        questions = clarification_request.get("questions")
        fallback = questions[0] if isinstance(questions, list) and questions else "请补充必要信息后我再继续处理。"
        response_text = state.get("final_response") or fallback
        response_text = _decorate_deferred_response(response_text, state)
        return {
            "final_response": response_text,
            "llm_outputs": {
                **(state.get("llm_outputs") or {}),
                "final_response": {
                    "response_text": response_text,
                    "evidence_citations": [],
                    "final_status": "insufficient_evidence",
                    "mode": "deterministic-template",
                    "approval_context": None,
                },
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
        }
    verification = _verification_route_payload(state)
    if verification is not None:
        if _can_render_policy_qa_partial_overlap(state, draft, verification):
            response_text = _policy_qa_partial_overlap_response(draft)
            response_text = _decorate_deferred_response(response_text, state)
            return {
                "final_response": response_text,
                "llm_outputs": {
                    **(state.get("llm_outputs") or {}),
                    "final_response": _policy_qa_partial_overlap_llm_output(response_text, draft, verification),
                },
                "trace_steps": (state.get("trace_steps") or [])
                + [_trace_step("completed", started_at, _final_response_evidence_refs(state, draft))],
            }
        if _verification_route_value(verification) == "manual_review":
            include_draft_missing_info = verification.get("safe_projection_source") not in _SAFE_PROJECTION_SOURCES
            response_text = _manual_review_response(
                draft,
                verification,
                state.get("business_context") or {},
                include_draft_missing_info=include_draft_missing_info,
            )
        else:
            response_text = _safe_verification_response(verification)
        response_text = _decorate_deferred_response(response_text, state)
        return {
            "final_response": response_text,
            "llm_outputs": {
                **(state.get("llm_outputs") or {}),
                "final_response": _verification_llm_output(response_text, verification),
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
        }
    if draft.get("recommended_action") == "retrieval_error":
        response_text = _decorate_deferred_response(_retrieval_error_response(draft), state)
        return {
            "final_response": response_text,
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }
    if draft.get("recommended_action") in {"insufficient_evidence", "citation_invalid"}:
        response_text = _insufficient_response_with_context(draft, state.get("business_context") or {})
        response_text = _decorate_deferred_response(response_text, state)
        return {
            "final_response": response_text,
            "llm_outputs": {
                **(state.get("llm_outputs") or {}),
                "final_response": {
                    "response_text": response_text,
                    "evidence_citations": [],
                    "final_status": "insufficient_evidence",
                    "mode": "deterministic-template",
                    "approval_context": None,
                },
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
        }
    if _can_render_business_fact_response(state, draft):
        response_text = _business_fact_response(state.get("business_context") or {})
        response_text = _decorate_deferred_response(response_text, state)
        return {
            "final_response": response_text,
            "llm_outputs": {
                **(state.get("llm_outputs") or {}),
                "final_response": _business_fact_llm_output(response_text),
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
        }
    response_text = _completed_response(draft, state.get("risk_assessment") or {})
    approval_context = _approval_outcome_text(approval_result, action_result, action_draft, draft_outcome)
    if approval_context:
        response_text = f"{response_text}\n{approval_context}"
    response_text = _decorate_deferred_response(response_text, state)
    return {
        "final_response": response_text,
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "final_response": {
                "response_text": response_text,
                "evidence_citations": [
                    f"{ref.get('doc_key')} / {ref.get('chunk_id')}" for ref in draft.get("evidence_refs") or []
                ],
                "final_status": "completed",
                "mode": "deterministic-template",
                "approval_context": approval_context or None,
            },
        },
        "trace_steps": (state.get("trace_steps") or [])
        + [_trace_step("completed", started_at, _final_response_evidence_refs(state, draft))],
    }
