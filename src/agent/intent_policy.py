from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.agent.schemas import IntentLiteral, RequiredSlotExpression, RequestedOperationLiteral, RiskTierLiteral


IntentRouteLiteral = Literal["investigate", "session_memory_load", "final_response"]


@dataclass(frozen=True)
class IntentDefinition:
    name: IntentLiteral
    required_slots: RequiredSlotExpression
    initial_route: IntentRouteLiteral
    precedence: int
    direct_response: bool = False
    evidence_required: bool = True
    high_risk: bool = False
    critical_route_class: bool = False


REQUESTED_OPERATIONS: tuple[str, ...] = (
    "read_status",
    "advise",
    "draft_reply",
    "draft_action",
    "execute_action",
    "escalate",
)

INTENT_DEFINITIONS: dict[str, IntentDefinition] = {
    "policy_qa": IntentDefinition(
        name="policy_qa",
        required_slots=RequiredSlotExpression(),
        initial_route="investigate",
        precedence=7,
    ),
    "order_status_inquiry": IntentDefinition(
        name="order_status_inquiry",
        required_slots=RequiredSlotExpression(any_of=[["order_id", "refund_case_id", "ticket_id"]]),
        initial_route="session_memory_load",
        precedence=6,
    ),
    "refund_troubleshooting": IntentDefinition(
        name="refund_troubleshooting",
        required_slots=RequiredSlotExpression(any_of=[["order_id", "refund_case_id"]]),
        initial_route="session_memory_load",
        precedence=5,
    ),
    "compensation_suggestion": IntentDefinition(
        name="compensation_suggestion",
        required_slots=RequiredSlotExpression(
            all_of=["action_type"],
            any_of=[["order_id", "refund_case_id", "ticket_id"]],
            optional=["amount"],
        ),
        initial_route="session_memory_load",
        precedence=3,
    ),
    "ticket_reply_draft": IntentDefinition(
        name="ticket_reply_draft",
        required_slots=RequiredSlotExpression(all_of=["ticket_id"]),
        initial_route="session_memory_load",
        precedence=4,
    ),
    "appeal_or_unban": IntentDefinition(
        name="appeal_or_unban",
        required_slots=RequiredSlotExpression(any_of=[["ticket_id", "order_id", "merchant_id"]]),
        initial_route="session_memory_load",
        precedence=1,
        high_risk=True,
        critical_route_class=True,
    ),
    "complaint_escalation": IntentDefinition(
        name="complaint_escalation",
        required_slots=RequiredSlotExpression(any_of=[["ticket_id", "order_id", "merchant_id"]]),
        initial_route="session_memory_load",
        precedence=2,
        high_risk=True,
        critical_route_class=True,
    ),
    "action_request": IntentDefinition(
        name="action_request",
        required_slots=RequiredSlotExpression(all_of=["action_type"], any_of=[["order_id", "refund_case_id"]]),
        initial_route="session_memory_load",
        precedence=8,
        high_risk=True,
    ),
    "small_talk": IntentDefinition(
        name="small_talk",
        required_slots=RequiredSlotExpression(),
        initial_route="final_response",
        precedence=9,
        direct_response=True,
        evidence_required=False,
    ),
    "unsupported": IntentDefinition(
        name="unsupported",
        required_slots=RequiredSlotExpression(),
        initial_route="final_response",
        precedence=10,
        direct_response=True,
        evidence_required=False,
    ),
}

ORDINARY_INTENTS: tuple[str, ...] = tuple(INTENT_DEFINITIONS)
REQUIRED_SLOT_POLICY: dict[str, RequiredSlotExpression] = {
    name: definition.required_slots for name, definition in INTENT_DEFINITIONS.items()
}
PRECEDENCE_INTENTS: tuple[str, ...] = tuple(
    name for name, _definition in sorted(INTENT_DEFINITIONS.items(), key=lambda item: item[1].precedence)
)
INTENT_ROUTE_POLICY: dict[str, IntentRouteLiteral] = {
    name: definition.initial_route for name, definition in INTENT_DEFINITIONS.items()
}
DIRECT_RESPONSE_INTENTS = {name for name, definition in INTENT_DEFINITIONS.items() if definition.direct_response}
EVIDENCE_REQUIRED_INTENTS = {name for name, definition in INTENT_DEFINITIONS.items() if definition.evidence_required}
HIGH_RISK_INTENTS = {name for name, definition in INTENT_DEFINITIONS.items() if definition.high_risk}
CRITICAL_ROUTE_CLASSES = {
    "critical_write",
    "approval_decision",
    *(name for name, definition in INTENT_DEFINITIONS.items() if definition.critical_route_class),
}


class IntentPolicyRegistry:
    """Read-only view over current intent policy constants."""

    def definitions(self) -> Mapping[str, IntentDefinition]:
        return MappingProxyType(INTENT_DEFINITIONS)

    def get_definition(self, name: str) -> IntentDefinition | None:
        return INTENT_DEFINITIONS.get(name)

    def definition_for(self, name: str) -> IntentDefinition | None:
        return self.get_definition(name)

    def ordinary_intents(self) -> tuple[str, ...]:
        return ORDINARY_INTENTS

    def intent_names(self) -> tuple[str, ...]:
        return self.ordinary_intents()

    def route_policy(self) -> Mapping[str, IntentRouteLiteral]:
        return MappingProxyType(INTENT_ROUTE_POLICY)

    def precedence_intents(self) -> tuple[str, ...]:
        return PRECEDENCE_INTENTS

    def precedence_order(self) -> tuple[str, ...]:
        return self.precedence_intents()

    def direct_response_intents(self) -> frozenset[str]:
        return frozenset(DIRECT_RESPONSE_INTENTS)

    def evidence_required_intents(self) -> frozenset[str]:
        return frozenset(EVIDENCE_REQUIRED_INTENTS)

    def high_risk_intents(self) -> frozenset[str]:
        return frozenset(HIGH_RISK_INTENTS)

    def critical_route_intents(self) -> frozenset[str]:
        return frozenset(
            name for name, definition in INTENT_DEFINITIONS.items() if definition.critical_route_class
        )

    def route_for_intent(self, intent: str) -> IntentRouteLiteral | None:
        return INTENT_ROUTE_POLICY.get(intent)

    def is_known_intent(self, intent: str) -> bool:
        return intent in INTENT_DEFINITIONS

    def is_direct_response_intent(self, intent: str) -> bool:
        return intent in DIRECT_RESPONSE_INTENTS

    def requires_evidence(self, intent: str) -> bool:
        definition = self.get_definition(intent)
        if definition is None:
            return True
        return definition.evidence_required

    def is_high_risk_intent(self, intent: str) -> bool:
        return intent in HIGH_RISK_INTENTS

    def is_critical_route_intent(self, intent: str) -> bool:
        return intent in CRITICAL_ROUTE_CLASSES

    def resolve_risk_tier(
        self,
        primary_intent: str,
        requested_operation: str,
        role: str | None = None,
        channel: str | None = None,
        routing_hints: dict[str, Any] | None = None,
    ) -> RiskTierLiteral:
        return resolve_risk_tier(
            primary_intent,
            requested_operation,
            role=role,
            channel=channel,
            routing_hints=routing_hints,
        )

    def resolve_precedence(
        self,
        primary_intent: str,
        secondary_intents: list[str],
        requested_operation: str,
        *,
        query: str = "",
    ) -> tuple[IntentLiteral, RequestedOperationLiteral, list[str]]:
        resolved_intent, resolved_operation, reason_codes = resolve_intent_precedence(
            primary_intent,
            requested_operation,
            query,
            secondary_intents,
        )
        if resolved_intent not in INTENT_DEFINITIONS:
            resolved_intent = "unsupported"
        return resolved_intent, _valid_operation(resolved_operation), reason_codes  # type: ignore[return-value]


class SlotPolicyRegistry:
    """Read-only view over required slot policy constants."""

    def required_slot_policy(self) -> Mapping[str, RequiredSlotExpression]:
        return MappingProxyType(REQUIRED_SLOT_POLICY)

    def required_slots_for(self, intent: str) -> RequiredSlotExpression:
        return REQUIRED_SLOT_POLICY.get(intent, RequiredSlotExpression())

    def intents_with_required_slots(self) -> tuple[str, ...]:
        return tuple(
            intent
            for intent, expression in REQUIRED_SLOT_POLICY.items()
            if expression.all_of or expression.any_of
        )


INTENT_POLICY_REGISTRY = IntentPolicyRegistry()
SLOT_POLICY_REGISTRY = SlotPolicyRegistry()

ORDINARY_CHAT_CHANNELS = {"ordinary_chat", "chat", "agent_chat", "agent_runs"}


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
    broad_approval = any(token in lowered for token in ("accept", "reject")) or any(
        token in text for token in ("通过", "拒绝")
    )
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
    candidates = [primary_intent, *(secondary_intents or [])]
    text = query or ""
    lowered = text.lower()
    compensation_action_requested = primary_intent == "compensation_suggestion" or _has_compensation_action_cue(
        text,
        lowered,
    )
    if any(token in lowered for token in ("appeal", "unban")) or any(token in text for token in ("申诉", "解封")):
        candidates.append("appeal_or_unban")
    if any(token in lowered for token in ("complaint", "escalate")) or any(token in text for token in ("投诉", "升级", "主管")):
        candidates.append("complaint_escalation")
    if compensation_action_requested:
        candidates.append("compensation_suggestion")
    if any(token in lowered for token in ("reply", "draft")) or any(token in text for token in ("回复", "话术")):
        candidates.append("ticket_reply_draft")

    valid_candidates = [candidate for candidate in candidates if candidate in ORDINARY_INTENTS]
    if not compensation_action_requested:
        valid_candidates = [candidate for candidate in valid_candidates if candidate != "compensation_suggestion"]
    if (
        primary_intent == "policy_qa"
        and requested_operation == "advise"
        and not any(candidate in {"appeal_or_unban", "complaint_escalation", "compensation_suggestion"} for candidate in valid_candidates)
        and (any(token in lowered for token in ("policy", "rule")) or any(token in text for token in ("政策", "规则")))
    ):
        return "policy_qa", "advise", []
    if (
        primary_intent == "action_request"
        and requested_operation == "advise"
        and _is_next_step_advice_query(text, lowered)
    ):
        return "refund_troubleshooting", "read_status", ["next_step_advice_normalized"]
    for intent in PRECEDENCE_INTENTS:
        if intent in valid_candidates:
            reason_codes = [] if intent == primary_intent else ["intent_precedence_applied"]
            return intent, _operation_for_selected_intent(intent, requested_operation), reason_codes
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
        or (
            primary_intent in {"refund_troubleshooting", "compensation_suggestion"}
            and requested_operation != "read_status"
        )
    )
    if safety_sensitive and confidence < 0.85:
        return True
    return False


def resolve_risk_tier(
    primary_intent: str,
    requested_operation: str,
    role: str | None = None,
    channel: str | None = None,
    routing_hints: dict[str, Any] | None = None,
) -> RiskTierLiteral:
    """Resolve ordinary-chat safety tier from effective policy state.

    The role is accepted for policy expansion but does not grant chat approval
    authority in this phase.
    """
    del role
    hints = routing_hints or {}
    effective_channel = channel or str(hints.get("channel") or "ordinary_chat")
    if (
        requested_operation == "approval_decision"
        or hints.get("pre_route_disposition") == "approval_chat_not_trusted"
        or hints.get("clarification_reason") == "approval_chat_not_trusted"
    ):
        return "forbidden_in_chat"
    if requested_operation == "read_status":
        return "read_only"
    if requested_operation == "draft_reply":
        return "draft_only"
    if requested_operation == "draft_action" or primary_intent == "compensation_suggestion":
        return "suggest_action"
    if requested_operation in {"execute_action", "escalate"}:
        return "approval_required" if effective_channel in ORDINARY_CHAT_CHANNELS else "approval_required"
    if primary_intent in HIGH_RISK_INTENTS or primary_intent == "action_request":
        return "approval_required"
    return "read_only"


def _valid_operation(value: str) -> RequestedOperationLiteral:
    if value in REQUESTED_OPERATIONS:
        return value  # type: ignore[return-value]
    return "advise"


def _operation_for_selected_intent(intent: str, requested_operation: str) -> RequestedOperationLiteral:
    operation = _valid_operation(requested_operation)
    if intent in {"appeal_or_unban", "complaint_escalation"}:
        return "escalate"
    if intent == "compensation_suggestion" and operation in {"read_status", "advise"}:
        return "draft_action"
    if intent == "ticket_reply_draft" and operation in {"read_status", "advise"}:
        return "draft_reply"
    return operation


def _has_compensation_action_cue(text: str, lowered: str) -> bool:
    has_compensation_term = any(token in lowered for token in ("compensation", "coupon")) or any(
        token in text for token in ("补偿", "券", "赔付")
    )
    if not has_compensation_term:
        return False

    has_policy_rule_question = any(token in lowered for token in ("policy", "rule", "usage")) or any(
        token in text for token in ("政策", "规则", "使用")
    )
    has_business_reference = any(
        token in lowered for token in ("ord", "order", "rf", "refund", "tkt", "ticket")
    ) or any(token in text for token in ("订单", "退款", "工单", "这个", "该"))
    if has_policy_rule_question and not has_business_reference:
        return False

    return any(
        token in lowered
        for token in (
            "suggest",
            "proposal",
            "propose",
            "offer",
            "issue",
            "grant",
            "amount",
            "how much",
        )
    ) or any(token in text for token in ("建议", "方案", "给", "发券", "创建", "金额", "多少", "要补偿", "该给"))


def _is_next_step_advice_query(text: str, lowered: str) -> bool:
    if any(token in lowered for token in ("execute", "refund now", "override", "compensation", "coupon")):
        return False
    if any(token in text for token in ("直接退款", "执行", "发券", "创建", "补偿", "券", "赔付")):
        return False
    has_business_reference = any(token in lowered for token in ("order", "refund", "ticket", "that", "this")) or any(
        token in text for token in ("订单", "退款", "工单", "这个", "该", "那")
    )
    asks_for_next_step = any(token in lowered for token in ("next step", "handle", "what should")) or any(
        token in text for token in ("下一步", "怎么处理", "如何处理", "怎么处置", "处理建议")
    )
    return has_business_reference and asks_for_next_step
