from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.agent.prompts import INSUFFICIENT_EVIDENCE_RESPONSE
from src.agent.state import AgentState

DEMO_NOT_EXECUTED_TEXT = "演示模式未执行优惠券发放、退款、工单关闭或任何外部动作"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _trace_step(status: str, started_at: str) -> dict[str, Any]:
    return {
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
    order = context.get("order") or {}
    refund_case = context.get("refund_case") or {}
    ticket = context.get("ticket") or {}

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


def _insufficient_response_with_context(draft: dict[str, Any], context: dict[str, Any]) -> str:
    evidence_text = _insufficient_response(draft)
    fact_summary = _business_context_summary(context)
    if not fact_summary:
        return evidence_text
    return f"{fact_summary}\n关于退款风险：{evidence_text}"


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
        return {
            "final_response": blocked_response,
            "llm_outputs": {
                **(state.get("llm_outputs") or {}),
                "final_response": {
                    "response_text": blocked_response,
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
        response_text = _safe_verification_response(verification)
        return {
            "final_response": response_text,
            "llm_outputs": {
                **(state.get("llm_outputs") or {}),
                "final_response": _verification_llm_output(response_text, verification),
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
        }
    if draft.get("recommended_action") == "retrieval_error":
        return {
            "final_response": _retrieval_error_response(draft),
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }
    if draft.get("recommended_action") in {"insufficient_evidence", "citation_invalid"}:
        response_text = _insufficient_response_with_context(draft, state.get("business_context") or {})
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
    response_text = _completed_response(draft, state.get("risk_assessment") or {})
    approval_context = _approval_outcome_text(approval_result, action_result, action_draft, draft_outcome)
    if approval_context:
        response_text = f"{response_text}\n{approval_context}"
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
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
    }
