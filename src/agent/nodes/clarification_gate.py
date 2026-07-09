from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig

from src.agent.intent_policy import REQUIRED_SLOT_POLICY
from src.agent.routing import missing_required_slots, resolve_slots_for_completeness
from src.agent.schemas import ClarificationRequest
from src.agent.state import AgentState


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def clarification_gate(state: AgentState, config: RunnableConfig) -> dict:
    """Build ordinary clarification output without touching approval lifecycle state."""
    del config
    started_at = _now_iso()
    reason = _clarification_reason(state)
    missing = _missing_entries(state)
    questions = _questions_for_reason(reason, missing, state)
    blocked_nodes = _blocked_nodes(reason)
    request = ClarificationRequest(
        reason=reason,
        clarification_request_id=_clarification_request_id(state),
        questions=questions,
        blocked_nodes=blocked_nodes,
        resume_policy="same_thread_only",
    )
    response = questions[0] if questions else "请补充必要信息后我再继续处理。"
    step = {
        "node": "clarification_gate",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": None,
    }
    return {
        "clarification_request": request.model_dump(),
        "final_response": response,
        "trace_steps": (state.get("trace_steps") or []) + [step],
    }


def _clarification_request_id(state: AgentState) -> str:
    token = state.get("run_id") or state.get("current_run_id") or state.get("thread_id") or "unknown"
    return f"clarify_{str(token).replace(':', '_')}"


def _clarification_reason(state: AgentState) -> str:
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    reason = routing_hints.get("clarification_reason")
    if reason in {
        "missing_required_slots",
        "low_confidence",
        "unsupported_or_ambiguous",
        "multi_target_request",
        "approval_chat_not_trusted",
    }:
        return reason
    if state.get("missing_required_slots") or routing_hints.get("missing_required_slots"):
        return "missing_required_slots"
    if routing_hints.get("pre_route_disposition") == "approval_chat_not_trusted":
        return "approval_chat_not_trusted"
    if state.get("intent_confidence") is not None and state.get("intent_confidence") < 0.65:
        return "low_confidence"
    if state.get("primary_intent") in {"unsupported", "small_talk"}:
        return "unsupported_or_ambiguous"
    return "missing_required_slots"


def _missing_entries(state: AgentState) -> list[dict[str, list[str]]]:
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    value = state.get("missing_required_slots") or routing_hints.get("missing_required_slots")
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    intent = state.get("primary_intent") or state.get("current_intent")
    policy = REQUIRED_SLOT_POLICY.get(intent) if isinstance(intent, str) else None
    if policy is not None:
        return missing_required_slots(policy, resolve_slots_for_completeness(state))
    return []


def _questions_for_reason(reason: str, missing: list[dict[str, list[str]]], state: AgentState) -> list[str]:
    if _safe_reason(state) == "metric_scope_denied":
        return ["当前权限范围内无法提供该商户指标。你可以查询当前权限范围内的商户指标，或调整为已授权的商家范围。"]
    if reason == "missing_required_slots":
        return _missing_slot_questions(missing) or [
            "我需要订单号、退款单号或工单号来定位具体售后对象；请提供其中至少一个。"
        ]
    if reason == "low_confidence":
        return ["请再补充一下业务背景或要处理的对象，我需要确认后再继续。"]
    if reason == "multi_target_request":
        return ["你这次想优先处理哪一个请求？请先提供一个明确目标。"]
    if reason == "approval_chat_not_trusted":
        return ["审批操作需要通过审批入口处理。请说明你想查询的业务问题或提供需要补充的信息。"]
    return ["这个请求暂不在我可以直接处理的范围内，请换一种业务问题描述。"]


def _safe_reason(state: AgentState) -> str | None:
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    value = routing_hints.get("safe_reason")
    return value if isinstance(value, str) else None


def _missing_slot_questions(missing: list[dict[str, list[str]]]) -> list[str]:
    questions: list[str] = []
    for entry in missing:
        if "all_of" in entry:
            for slot in entry.get("all_of") or []:
                questions.append(_question_for_required_slot(slot))
        if "any_of" in entry:
            labels = [_slot_label(slot) for slot in entry.get("any_of") or []]
            if labels:
                label_text = _join_labels(labels)
                questions.append(f"我需要{label_text}来定位具体售后对象；请提供{label_text}中的至少一个。")
    return questions


def _question_for_required_slot(slot: str) -> str:
    if slot == "metric_time_range":
        return "要统计业务指标，请选择时间范围：今天、本周、本月、本季度、今年，或指定起止时间。"
    if slot == "metric_id":
        return "请说明要统计的指标：订单数、退款单数、待处理工单数、补偿券记录数或商户退款率。"
    if slot == "merchant_filter":
        return "请提供当前权限范围内要统计的商家范围或商家ID。"
    if slot == "metric_status_filter":
        return "这个状态筛选不适用于当前指标；请改用该指标支持的状态，或去掉状态筛选。"
    return f"请提供{_slot_label(slot)}。"


def _join_labels(labels: list[str]) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return "或".join(labels)
    return f"{'、'.join(labels[:-1])}或{labels[-1]}"


def _slot_label(slot: str) -> str:
    labels = {
        "order_id": "订单号",
        "refund_case_id": "退款单号",
        "ticket_id": "工单号",
        "merchant_id": "商家ID",
        "customer_id": "客户ID",
        "action_type": "操作类型",
        "amount": "金额",
        "metric_id": "业务指标",
        "metric_time_range": "时间范围",
        "merchant_filter": "商家范围",
        "metric_status_filter": "指标状态筛选",
    }
    return labels.get(slot, slot)


def _blocked_nodes(reason: str) -> list[str]:
    if reason == "approval_chat_not_trusted":
        return ["investigate", "action_draft", "approval_gate", "execute_action"]
    if reason in {"low_confidence", "multi_target_request"}:
        return ["investigate", "action_draft", "risk_gate", "approval_gate", "execute_action"]
    return ["investigate", "action_draft"]
