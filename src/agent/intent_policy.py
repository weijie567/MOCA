from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.agent.schemas import RequiredSlotExpression, RequestedOperationLiteral


ORDINARY_INTENTS: tuple[str, ...] = (
    "policy_qa",
    "order_status_inquiry",
    "refund_troubleshooting",
    "compensation_suggestion",
    "ticket_reply_draft",
    "appeal_or_unban",
    "complaint_escalation",
    "action_request",
    "small_talk",
    "unsupported",
)

REQUESTED_OPERATIONS: tuple[str, ...] = (
    "read_status",
    "advise",
    "draft_reply",
    "draft_action",
    "execute_action",
    "escalate",
)

REQUIRED_SLOT_POLICY: dict[str, RequiredSlotExpression] = {
    "policy_qa": RequiredSlotExpression(),
    "order_status_inquiry": RequiredSlotExpression(any_of=[["order_id", "refund_case_id", "ticket_id"]]),
    "refund_troubleshooting": RequiredSlotExpression(any_of=[["order_id", "refund_case_id"]]),
    "compensation_suggestion": RequiredSlotExpression(
        all_of=["action_type"], any_of=[["order_id", "refund_case_id", "ticket_id"]], optional=["amount"]
    ),
    "ticket_reply_draft": RequiredSlotExpression(all_of=["ticket_id"]),
    "appeal_or_unban": RequiredSlotExpression(any_of=[["ticket_id", "order_id", "merchant_id"]]),
    "complaint_escalation": RequiredSlotExpression(any_of=[["ticket_id", "order_id", "merchant_id"]]),
    "action_request": RequiredSlotExpression(all_of=["action_type"], any_of=[["order_id", "refund_case_id"]]),
    "small_talk": RequiredSlotExpression(),
    "unsupported": RequiredSlotExpression(),
}

PRECEDENCE_INTENTS: tuple[str, ...] = (
    "appeal_or_unban",
    "complaint_escalation",
    "compensation_suggestion",
    "ticket_reply_draft",
    "refund_troubleshooting",
    "order_status_inquiry",
    "policy_qa",
    "action_request",
    "small_talk",
    "unsupported",
)

INTENT_ROUTE_POLICY: dict[str, str] = {
    "policy_qa": "investigate",
    "order_status_inquiry": "session_memory_load",
    "refund_troubleshooting": "session_memory_load",
    "compensation_suggestion": "session_memory_load",
    "ticket_reply_draft": "session_memory_load",
    "appeal_or_unban": "session_memory_load",
    "complaint_escalation": "session_memory_load",
    "action_request": "session_memory_load",
    "small_talk": "final_response",
    "unsupported": "final_response",
}

DIRECT_RESPONSE_INTENTS = {"small_talk", "unsupported"}
EVIDENCE_REQUIRED_INTENTS = set(ORDINARY_INTENTS) - DIRECT_RESPONSE_INTENTS
HIGH_RISK_INTENTS = {"appeal_or_unban", "complaint_escalation", "action_request"}
CRITICAL_ROUTE_CLASSES = {"critical_write", "approval_decision", "appeal_or_unban", "complaint_escalation"}


class PreRouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: Literal["none", "approval_chat_not_trusted", "safety_sensitive", "multi_target_request"] = "none"
    requested_operation: RequestedOperationLiteral | None = None
    reason_codes: list[str] = []
    requires_clarification: bool = False


_APPROVAL_ID_RE = re.compile(r"\b(?:APR|APPROVAL|审批)[-_]?\d+\b", re.IGNORECASE)


def detect_pre_route(query: str) -> PreRouteDecision:
    text = query or ""
    lowered = text.lower()
    approval_command = any(token in lowered for token in ("approval", "apr-")) or "审批" in text
    broad_approval = any(token in lowered for token in ("accept", "reject")) or any(token in text for token in ("通过", "拒绝"))
    approval_context = bool(_APPROVAL_ID_RE.search(text)) or "approval" in lowered or "审批" in text
    if approval_command or (broad_approval and approval_context):
        return PreRouteDecision(
            disposition="approval_chat_not_trusted",
            requested_operation="advise",
            reason_codes=["approval_chat_not_trusted"],
            requires_clarification=True,
        )

    multi_target = any(token in lowered for token in (" and also ", "同时", "以及", "顺便"))
    if multi_target:
        return PreRouteDecision(
            disposition="multi_target_request",
            requested_operation=None,
            reason_codes=["multi_target_request"],
            requires_clarification=True,
        )

    english_action_terms = ("execute", "refund now", "override")
    chinese_action_terms = ("直接退款", "执行", "发券", "创建")
    if any(token in lowered for token in english_action_terms) or any(token in text for token in chinese_action_terms):
        return PreRouteDecision(
            disposition="safety_sensitive",
            requested_operation="execute_action",
            reason_codes=["critical_write"],
            requires_clarification=False,
        )

    escalation_terms = ("escalate", "complaint", "升级", "投诉", "主管")
    if any(token in lowered for token in escalation_terms) or any(token in text for token in escalation_terms):
        return PreRouteDecision(
            disposition="safety_sensitive",
            requested_operation="escalate",
            reason_codes=["complaint_escalation"],
            requires_clarification=False,
        )

    return PreRouteDecision()


def resolve_intent_precedence(
    primary_intent: str,
    requested_operation: str,
    query: str,
    secondary_intents: list[str] | None = None,
) -> tuple[str, str, list[str]]:
    candidates = [primary_intent]
    text = query or ""
    lowered = text.lower()
    if any(token in lowered for token in ("appeal", "unban")) or any(token in text for token in ("申诉", "解封")):
        candidates.append("appeal_or_unban")
        requested_operation = "escalate" if requested_operation == "read_status" else requested_operation
    if any(token in lowered for token in ("complaint", "escalate")) or any(token in text for token in ("投诉", "升级")):
        candidates.append("complaint_escalation")
        requested_operation = "escalate"
    if any(token in lowered for token in ("compensation", "coupon")) or any(token in text for token in ("补偿", "券", "赔付")):
        candidates.append("compensation_suggestion")
        if requested_operation == "read_status":
            requested_operation = "draft_action"
    if any(token in lowered for token in ("reply", "draft")) or any(token in text for token in ("回复", "话术")):
        candidates.append("ticket_reply_draft")
        if requested_operation == "read_status":
            requested_operation = "draft_reply"

    valid_candidates = [candidate for candidate in candidates if candidate in ORDINARY_INTENTS]
    if (
        primary_intent == "policy_qa"
        and requested_operation == "advise"
        and (any(token in lowered for token in ("policy", "rule")) or any(token in text for token in ("政策", "规则")))
    ):
        return "policy_qa", "advise", []
    for intent in PRECEDENCE_INTENTS:
        if intent in valid_candidates:
            reason_codes = [] if intent == primary_intent else ["intent_precedence_applied"]
            return intent, _valid_operation(requested_operation), reason_codes
    return "unsupported", "advise", ["unsupported_intent"]


def confidence_requires_clarification(
    primary_intent: str,
    requested_operation: str,
    confidence: float | None,
    pre_route: PreRouteDecision | None = None,
) -> bool:
    if pre_route and pre_route.requires_clarification:
        return True
    if confidence is None or confidence < 0.65:
        return True
    safety_sensitive = (
        primary_intent in HIGH_RISK_INTENTS
        or requested_operation in {"draft_action", "execute_action", "escalate"}
        or (primary_intent in {"refund_troubleshooting", "compensation_suggestion"} and requested_operation != "read_status")
    )
    if safety_sensitive and confidence < 0.85:
        return True
    return False


def _valid_operation(value: str) -> RequestedOperationLiteral:
    if value in REQUESTED_OPERATIONS:
        return value  # type: ignore[return-value]
    return "advise"
