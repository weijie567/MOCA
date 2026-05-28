from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.agent.prompts import INSUFFICIENT_EVIDENCE_RESPONSE
from src.agent.state import AgentState


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
        title = ref.get("title") or "政策依据"
        section = ref.get("section") or "相关章节"
        citations.append(f"根据 {doc_key} / {chunk_id}，{title} - {section}")
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
        parts.append(f"风险提示：{risk_reason}，需要人工审批后执行。")
    return "\n".join(parts)


def _approval_outcome_text(
    approval_result: dict[str, Any] | None,
    action_result: dict[str, Any] | None,
) -> str:
    if approval_result:
        if approval_result.get("decision") == "approve" and action_result:
            if action_result.get("status") == "success":
                draft_id = (action_result.get("data") or {}).get("draft_id", "unknown")
                return f"审批结果：操作已审批通过，补偿草稿已创建（草稿ID：{draft_id}），等待最终发放。"
            message = (action_result.get("error") or {}).get("message", "unknown error")
            return f"审批结果：操作已审批通过，但执行失败：{message}。"
        if approval_result.get("decision") == "reject":
            reason = approval_result.get("reason") or "No reason provided"
            return f"审批结果：操作被审核人拒绝。拒绝原因：{reason}。"

    if not approval_result and action_result and action_result.get("status") == "success":
        draft_id = (action_result.get("data") or {}).get("draft_id", "unknown")
        return f"执行结果：该操作在政策范围内，无需审批，补偿草稿已创建（草稿ID：{draft_id}）。"

    return ""


async def final_response(state: AgentState) -> dict:
    started_at = _now_iso()
    draft = state.get("recommendation_draft") or {}
    approval_result = state.get("approval_result")
    action_result = state.get("action_result")
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
    approval_context = _approval_outcome_text(approval_result, action_result)
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
