from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
import re
from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict

from src.agent.schemas import IntentLiteral, RequiredSlotExpression, RequestedOperationLiteral, RiskTierLiteral


IntentRouteLiteral = Literal["investigate", "slot_resolution_gate", "final_response"]
TaskStepRelationLiteral = Literal["root", "dependency", "modifier", "parallel"]


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


@dataclass(frozen=True)
class SlotInheritanceContext:
    tenant_id: str | None
    user_id: str | None
    thread_id: str | None
    intent: str | None
    max_age_seconds: int
    current_time: datetime | None = None


@dataclass(frozen=True)
class SlotInheritanceDecision:
    accepted: bool
    reason_code: str
    source: str | None = None


@dataclass(frozen=True)
class SemanticIntent:
    intent: IntentLiteral
    operation: RequestedOperationLiteral
    entities: Mapping[str, Any]
    raw_confidence: float | None
    keyword_signals: tuple[IntentLiteral, ...]
    arbitration: tuple[str, ...]


@dataclass(frozen=True)
class RiskDecision:
    tier: RiskTierLiteral
    evidence_required: bool
    approval_required: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ClarificationDecision:
    requires_clarification: bool
    reason: str | None
    threshold_applied: float | None


@dataclass(frozen=True)
class TaskStep:
    step_id: str
    intent: IntentLiteral
    operation: RequestedOperationLiteral
    entities: Mapping[str, Any]
    depends_on: tuple[str, ...]
    relation: TaskStepRelationLiteral

    def __post_init__(self) -> None:
        if not self.step_id:
            raise ValueError("task step requires step_id")
        if self.intent not in INTENT_DEFINITIONS:
            raise ValueError(f"unknown task step intent: {self.intent}")
        if self.operation not in REQUESTED_OPERATIONS:
            raise ValueError(f"unknown task step operation: {self.operation}")
        if self.relation not in {"root", "dependency", "modifier", "parallel"}:
            raise ValueError(f"unknown task step relation: {self.relation}")
        if not isinstance(self.entities, Mapping):
            raise ValueError("task step entities must be a mapping")
        object.__setattr__(self, "depends_on", tuple(self.depends_on))


@dataclass(frozen=True)
class TaskPlan:
    steps: tuple[TaskStep, ...]
    terminal_step_id: str

    def __post_init__(self) -> None:
        steps = tuple(self.steps)
        object.__setattr__(self, "steps", steps)
        if not steps:
            raise ValueError("task plan requires at least one step")
        if len(steps) > TASK_PLAN_MAX_STEPS:
            raise ValueError("task plan exceeds maximum step count")
        if steps[0].relation != "root":
            raise ValueError("task plan first step must be root")
        if any(step.relation == "modifier" for step in steps):
            raise ValueError("modifier steps must be normalized before final task plan")
        step_ids = [step.step_id for step in steps]
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("task plan step ids must be unique")
        if self.terminal_step_id not in step_ids:
            raise ValueError("task plan terminal_step_id must reference a step")
        step_id_set = set(step_ids)
        for step in steps:
            if any(dependency not in step_id_set for dependency in step.depends_on):
                raise ValueError("task step dependency must reference a known step")
            if step.step_id in step.depends_on:
                raise ValueError("task step cannot depend on itself")


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
        initial_route="slot_resolution_gate",
        precedence=6,
    ),
    "refund_troubleshooting": IntentDefinition(
        name="refund_troubleshooting",
        required_slots=RequiredSlotExpression(any_of=[["order_id", "refund_case_id"]]),
        initial_route="slot_resolution_gate",
        precedence=5,
    ),
    "compensation_suggestion": IntentDefinition(
        name="compensation_suggestion",
        required_slots=RequiredSlotExpression(
            all_of=["action_type"],
            any_of=[["order_id", "refund_case_id", "ticket_id"]],
            optional=["amount"],
        ),
        initial_route="slot_resolution_gate",
        precedence=3,
    ),
    "ticket_reply_draft": IntentDefinition(
        name="ticket_reply_draft",
        required_slots=RequiredSlotExpression(all_of=["ticket_id"]),
        initial_route="slot_resolution_gate",
        precedence=4,
    ),
    "appeal_or_unban": IntentDefinition(
        name="appeal_or_unban",
        required_slots=RequiredSlotExpression(any_of=[["ticket_id", "order_id", "merchant_id"]]),
        initial_route="slot_resolution_gate",
        precedence=1,
        high_risk=True,
        critical_route_class=True,
    ),
    "complaint_escalation": IntentDefinition(
        name="complaint_escalation",
        required_slots=RequiredSlotExpression(any_of=[["ticket_id", "order_id", "merchant_id"]]),
        initial_route="slot_resolution_gate",
        precedence=2,
        high_risk=True,
        critical_route_class=True,
    ),
    "action_request": IntentDefinition(
        name="action_request",
        required_slots=RequiredSlotExpression(all_of=["action_type"], any_of=[["order_id", "refund_case_id"]]),
        initial_route="slot_resolution_gate",
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
ORDINARY_CONFIDENCE_THRESHOLD = 0.65
SAFETY_CONFIDENCE_THRESHOLD = 0.85
TASK_PLAN_MAX_STEPS = 3
COMPLAINT_MODIFIER_ROOT_INTENTS = frozenset(
    {
        "compensation_suggestion",
        "refund_troubleshooting",
        "ticket_reply_draft",
        "order_status_inquiry",
        "policy_qa",
    }
)
TASK_PLAN_ENTITY_IDENTIFIER_KEYS = frozenset(
    {
        "order_id",
        "refund_case_id",
        "ticket_id",
        "merchant_id",
        "customer_id",
        "action_type",
    }
)
CROSS_INTENT_SLOT_GROUPS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "order_id": frozenset(
            {
                "order_status_inquiry",
                "refund_troubleshooting",
                "compensation_suggestion",
                "action_request",
                "appeal_or_unban",
                "complaint_escalation",
            }
        ),
        "refund_case_id": frozenset(
            {
                "order_status_inquiry",
                "refund_troubleshooting",
                "compensation_suggestion",
                "action_request",
            }
        ),
        "ticket_id": frozenset(
            {
                "order_status_inquiry",
                "ticket_reply_draft",
                "appeal_or_unban",
                "complaint_escalation",
                "compensation_suggestion",
            }
        ),
    }
)


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

    def resolve_risk_decision(
        self,
        primary_intent: str,
        requested_operation: str,
        role: str | None = None,
        channel: str | None = None,
        routing_hints: dict[str, Any] | None = None,
    ) -> RiskDecision:
        return resolve_risk_decision(
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
        raw_confidence: float | None = None,
    ) -> tuple[IntentLiteral, RequestedOperationLiteral, list[str]]:
        resolved_intent, resolved_operation, reason_codes = resolve_intent_precedence(
            primary_intent,
            requested_operation,
            query,
            secondary_intents,
            raw_confidence=raw_confidence,
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

    def missing_required_slots(
        self,
        required_slots: dict[str, Any] | RequiredSlotExpression | None,
        resolved_slots: Mapping[str, Any] | None,
    ) -> list[dict[str, list[str]]]:
        expression = _required_slot_expression(required_slots)
        slots = {key: value for key, value in (resolved_slots or {}).items() if value not in (None, "")}
        missing: list[dict[str, list[str]]] = []
        for slot in expression.all_of:
            if slot not in slots:
                missing.append({"all_of": [slot]})
        for group in expression.any_of:
            if group and not any(slot in slots for slot in group):
                missing.append({"any_of": list(group)})
        return missing

    def accepts_inherited_slot(
        self,
        slot: str,
        metadata: Mapping[str, Any] | None,
        context: SlotInheritanceContext,
        *,
        invalidation: Mapping[str, Any] | None = None,
    ) -> SlotInheritanceDecision:
        if not isinstance(metadata, Mapping):
            return SlotInheritanceDecision(False, "missing_metadata")
        source = metadata.get("source") if isinstance(metadata.get("source"), str) else None
        if source is None:
            return SlotInheritanceDecision(False, "missing_metadata")
        if source != "trusted_session_memory":
            return SlotInheritanceDecision(False, "untrusted_source", source)
        for field, reason_code in (
            ("tenant_id", "tenant_mismatch"),
            ("user_id", "user_mismatch"),
            ("thread_id", "thread_mismatch"),
        ):
            expected = getattr(context, field)
            observed = metadata.get(field)
            if expected is not None or observed is not None:
                if str(observed) != str(expected):
                    return SlotInheritanceDecision(False, reason_code, source)
        if invalidation:
            return SlotInheritanceDecision(False, "slot_invalidated", source)
        if not _slot_metadata_is_fresh(metadata, context):
            return SlotInheritanceDecision(False, "stale_slot", source)
        if _slot_metadata_is_intent_compatible(slot, metadata, context.intent):
            return SlotInheritanceDecision(True, "accepted", source)
        return SlotInheritanceDecision(False, "intent_incompatible", source)

    def intents_with_required_slots(self) -> tuple[str, ...]:
        return tuple(
            intent
            for intent, expression in REQUIRED_SLOT_POLICY.items()
            if expression.all_of or expression.any_of
        )


def _required_slot_expression(value: dict[str, Any] | RequiredSlotExpression | None) -> RequiredSlotExpression:
    if isinstance(value, RequiredSlotExpression):
        return value
    if isinstance(value, dict):
        return RequiredSlotExpression.model_validate(value)
    return RequiredSlotExpression()


def _slot_metadata_is_fresh(metadata: Mapping[str, Any], context: SlotInheritanceContext) -> bool:
    now = context.current_time or datetime.now(UTC)
    expires_at = metadata.get("expires_at")
    if isinstance(expires_at, str):
        parsed = _parse_policy_datetime(expires_at)
        if parsed is None or parsed <= now:
            return False
    elif metadata.get("fresh") is not True:
        return False
    observed_at = metadata.get("observed_at") or metadata.get("updated_at")
    if isinstance(observed_at, str) and context.max_age_seconds > 0:
        parsed_observed = _parse_policy_datetime(observed_at)
        if parsed_observed is None:
            return False
        if (now - parsed_observed).total_seconds() > context.max_age_seconds:
            return False
    return True


def _parse_policy_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def slot_intent_compatible(slot_name: str, compatible_intents: list[str], current_intent: str | None) -> bool:
    if current_intent is None:
        return True
    if current_intent in compatible_intents:
        return True
    intent_group = CROSS_INTENT_SLOT_GROUPS.get(slot_name)
    if intent_group is None:
        return False
    return current_intent in intent_group and any(intent in intent_group for intent in compatible_intents)


def _slot_metadata_is_intent_compatible(
    slot_name: str,
    metadata: Mapping[str, Any],
    intent: str | None,
) -> bool:
    compatible_intents = metadata.get("compatible_intents")
    if intent and isinstance(compatible_intents, list):
        return slot_intent_compatible(slot_name, compatible_intents, intent)
    if metadata.get("intent_filter_applied") is False:
        return False
    return metadata.get("intent_compatible") is True


INTENT_POLICY_REGISTRY = IntentPolicyRegistry()
SLOT_POLICY_REGISTRY = SlotPolicyRegistry()

ORDINARY_CHAT_CHANNELS = {"ordinary_chat", "chat", "agent_chat", "agent_runs"}
RISK_POLICY_TABLE: Mapping[tuple[str, str, str], RiskDecision] = MappingProxyType(
    {
        ("approval_decision", "*", "*"): RiskDecision(
            tier="forbidden_in_chat",
            evidence_required=False,
            approval_required=False,
            reason_codes=("approval_chat_not_trusted",),
        ),
        ("read_status", "*", "*"): RiskDecision(
            tier="read_only",
            evidence_required=True,
            approval_required=False,
            reason_codes=("operation_read_status",),
        ),
        ("draft_reply", "*", "*"): RiskDecision(
            tier="draft_only",
            evidence_required=True,
            approval_required=False,
            reason_codes=("operation_draft_reply",),
        ),
        ("draft_action", "*", "*"): RiskDecision(
            tier="suggest_action",
            evidence_required=True,
            approval_required=False,
            reason_codes=("operation_draft_action",),
        ),
        ("execute_action", "*", "ordinary_chat"): RiskDecision(
            tier="approval_required",
            evidence_required=True,
            approval_required=True,
            reason_codes=("operation_execute_action", "ordinary_chat"),
        ),
        ("execute_action", "*", "non_chat"): RiskDecision(
            tier="approval_required",
            evidence_required=True,
            approval_required=True,
            reason_codes=("operation_execute_action", "non_chat"),
        ),
        ("escalate", "*", "ordinary_chat"): RiskDecision(
            tier="approval_required",
            evidence_required=True,
            approval_required=True,
            reason_codes=("operation_escalate", "ordinary_chat"),
        ),
        ("escalate", "*", "non_chat"): RiskDecision(
            tier="approval_required",
            evidence_required=True,
            approval_required=True,
            reason_codes=("operation_escalate", "non_chat"),
        ),
        ("*", "compensation_suggestion", "*"): RiskDecision(
            tier="suggest_action",
            evidence_required=True,
            approval_required=False,
            reason_codes=("intent_compensation_suggestion",),
        ),
        ("*", "action_request", "*"): RiskDecision(
            tier="approval_required",
            evidence_required=True,
            approval_required=True,
            reason_codes=("intent_action_request",),
        ),
        ("*", "high_risk", "*"): RiskDecision(
            tier="approval_required",
            evidence_required=True,
            approval_required=True,
            reason_codes=("intent_high_risk",),
        ),
        ("*", "direct_response", "*"): RiskDecision(
            tier="read_only",
            evidence_required=False,
            approval_required=False,
            reason_codes=("intent_direct_response",),
        ),
        ("*", "*", "*"): RiskDecision(
            tier="read_only",
            evidence_required=True,
            approval_required=False,
            reason_codes=("default_read_only",),
        ),
    }
)


class PreRouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: Literal["none", "approval_chat_not_trusted", "safety_sensitive", "multi_target_request"] = "none"
    requested_operation: RequestedOperationLiteral | None = None
    reason_codes: list[str] = []
    requires_clarification: bool = False


APPROVAL_OR_ACTION_SHORT_REPLY_KEYS = frozenset(
    {
        "同意",
        "批准",
        "确认",
        "执行",
        "approve",
        "approved",
        "accept",
        "accepted",
        "yes",
        "goahead",
        "doit",
    }
)
AMBIGUOUS_SHORT_REPLY_KEYS = frozenset(
    {
        "继续",
        "继续吧",
        "就按上面",
        "就按上面的处理",
        "按上面处理",
        "好的",
        "好",
        "可以",
        "行",
        "嗯",
        "ok",
        *APPROVAL_OR_ACTION_SHORT_REPLY_KEYS,
    }
)
_APPROVAL_ID_RE = re.compile(r"\b(?:APR|APPROVAL|审批)[-_]?\d+\b", re.IGNORECASE)


def short_text_key(text: str) -> str:
    return re.sub(r"[\s。！!,.，、；;：:]+", "", text.strip()).lower()


def is_short_approval_or_action_reply(text: str) -> bool:
    return short_text_key(text) in APPROVAL_OR_ACTION_SHORT_REPLY_KEYS


def is_ambiguous_short_reply(text: str) -> bool:
    return short_text_key(text) in AMBIGUOUS_SHORT_REPLY_KEYS


def detect_pre_route(query: str) -> PreRouteDecision:
    text = query or ""
    lowered = text.lower()
    if is_short_approval_or_action_reply(text):
        return PreRouteDecision(
            disposition="approval_chat_not_trusted",
            requested_operation="advise",
            reason_codes=["approval_chat_not_trusted"],
            requires_clarification=True,
        )

    approval_command = any(token in lowered for token in ("approval", "apr-")) or "审批" in text
    approval_action = any(
        token in lowered
        for token in (
            "approve",
            "approved",
            "accept",
            "accepted",
            "reject",
            "rejected",
            "yes",
            "goahead",
            "go ahead",
            "doit",
            "do it",
        )
    ) or any(token in text for token in ("同意", "批准", "确认", "通过", "拒绝"))
    approval_context = bool(_APPROVAL_ID_RE.search(text)) or "approval" in lowered or "审批" in text
    if approval_command or (approval_action and approval_context):
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
    *,
    raw_confidence: float | None = None,
) -> tuple[str, str, list[str]]:
    keyword_signals = derive_keyword_signals(query)
    return arbitrate_intent(
        primary_intent,
        secondary_intents or [],
        keyword_signals,
        raw_confidence,
        requested_operation,
        query=query,
    )


def derive_keyword_signals(query: str) -> tuple[IntentLiteral, ...]:
    text = query or ""
    lowered = text.lower()
    signals: list[IntentLiteral] = []
    if any(token in lowered for token in ("appeal", "unban")) or any(token in text for token in ("申诉", "解封")):
        _append_signal(signals, "appeal_or_unban")
    if any(token in lowered for token in ("complaint", "escalate")) or any(token in text for token in ("投诉", "升级", "主管")):
        _append_signal(signals, "complaint_escalation")
    if _has_compensation_action_cue(text, lowered):
        _append_signal(signals, "compensation_suggestion")
    if any(token in lowered for token in ("reply", "draft")) or any(token in text for token in ("回复", "话术")):
        _append_signal(signals, "ticket_reply_draft")
    return tuple(signals)


def arbitrate_intent(
    llm_primary: str,
    llm_secondary: list[str] | tuple[str, ...],
    keyword_signals: tuple[str, ...],
    raw_confidence: float | None,
    requested_operation: str = "advise",
    *,
    query: str = "",
) -> tuple[IntentLiteral, RequestedOperationLiteral, list[str]]:
    primary_was_valid = llm_primary in ORDINARY_INTENTS
    primary_intent = llm_primary if primary_was_valid else "unsupported"
    secondary_intents = [intent for intent in llm_secondary if intent in ORDINARY_INTENTS]
    text = query or ""
    lowered = text.lower()
    operation = _valid_operation(requested_operation)
    compensation_action_requested = primary_intent == "compensation_suggestion" or "compensation_suggestion" in keyword_signals

    if primary_intent == "action_request" and operation == "advise" and _is_next_step_advice_query(text, lowered):
        return "refund_troubleshooting", "read_status", ["next_step_advice_normalized"]

    llm_candidates = {primary_intent, *secondary_intents}
    confidence_allows_keyword_override = raw_confidence is None or raw_confidence < ORDINARY_CONFIDENCE_THRESHOLD
    eligible_keyword_signals = [
        signal
        for signal in keyword_signals
        if signal in ORDINARY_INTENTS and (signal in llm_candidates or confidence_allows_keyword_override)
    ]
    candidates = [primary_intent, *secondary_intents, *eligible_keyword_signals]

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
    for intent in PRECEDENCE_INTENTS:
        if intent in valid_candidates:
            if not primary_was_valid and intent == "unsupported":
                reason_codes = ["unsupported_intent"]
            else:
                reason_codes = [] if intent == primary_intent else ["intent_precedence_applied"]
            return intent, _operation_for_selected_intent(intent, requested_operation), reason_codes
    return "unsupported", "advise", ["unsupported_intent"]


def _append_signal(signals: list[IntentLiteral], intent: IntentLiteral) -> None:
    if intent not in signals:
        signals.append(intent)


def resolve_semantic_intent(
    primary_intent: str,
    requested_operation: str,
    query: str,
    secondary_intents: list[str] | None = None,
    *,
    candidate_slots: Mapping[str, Any] | None = None,
    raw_confidence: float | None = None,
) -> SemanticIntent:
    keyword_signals = derive_keyword_signals(query)
    intent, operation, arbitration = arbitrate_intent(
        primary_intent,
        secondary_intents or [],
        keyword_signals,
        raw_confidence,
        requested_operation,
        query=query,
    )
    return SemanticIntent(
        intent=intent,
        operation=operation,
        entities=dict(candidate_slots or {}),
        raw_confidence=raw_confidence,
        keyword_signals=keyword_signals,
        arbitration=tuple(arbitration),
    )


def build_task_plan(
    semantic: SemanticIntent,
    secondary_intents: list[str] | tuple[str, ...] | None = None,
    requested_operation: str | None = None,
    candidate_slots: Mapping[str, Any] | None = None,
) -> tuple[TaskPlan, tuple[str, ...]]:
    entities = dict(candidate_slots or semantic.entities)
    normalization: list[str] = []
    operation = semantic.operation if semantic.operation in REQUESTED_OPERATIONS else "advise"
    root_intent = semantic.intent if semantic.intent in INTENT_DEFINITIONS else "unsupported"
    if root_intent != semantic.intent or operation != semantic.operation:
        normalization.append("plan_invalid_fallback_single")
    root = TaskStep(
        step_id="s1",
        intent=cast(IntentLiteral, root_intent),
        operation=cast(RequestedOperationLiteral, operation),
        entities=entities,
        depends_on=(),
        relation="root",
    )
    if "plan_invalid_fallback_single" in normalization:
        return TaskPlan(steps=(root,), terminal_step_id=root.step_id), tuple(normalization)

    steps: list[TaskStep] = [root]
    planned_intents: dict[str, TaskStep] = {root.intent: root}
    terminal_step_id = root.step_id

    for raw_intent in secondary_intents or ():
        if raw_intent not in INTENT_DEFINITIONS:
            return _fallback_task_plan(semantic, entities, normalization)
        if raw_intent == "small_talk":
            normalization.append("modifier_dropped:small_talk")
            continue
        if raw_intent == "complaint_escalation" and root.intent in COMPLAINT_MODIFIER_ROOT_INTENTS:
            normalization.append("modifier_folded:complaint_as_severity")
            continue
        if raw_intent in planned_intents:
            normalization.append(_same_intent_merge_record(entities))
            continue
        if len(steps) >= TASK_PLAN_MAX_STEPS:
            return _fallback_task_plan(semantic, entities, normalization)

        step_operation = _operation_for_task_step(raw_intent, requested_operation or semantic.operation)
        relation = _relation_for_task_step(root.operation, step_operation)
        step = TaskStep(
            step_id=f"s{len(steps) + 1}",
            intent=cast(IntentLiteral, raw_intent),
            operation=step_operation,
            entities=entities,
            depends_on=(root.step_id,) if relation == "dependency" else (),
            relation=relation,
        )
        steps.append(step)
        planned_intents[step.intent] = step
        if relation == "dependency":
            terminal_step_id = step.step_id

    try:
        return TaskPlan(steps=tuple(steps), terminal_step_id=terminal_step_id), tuple(normalization)
    except ValueError:
        return _fallback_task_plan(semantic, entities, normalization)


def select_executable_prefix(
    plan: TaskPlan,
    *,
    role: str | None = None,
    channel: str | None = None,
    routing_hints: dict[str, Any] | None = None,
) -> tuple[tuple[TaskStep, ...], tuple[TaskStep, ...]]:
    root = plan.steps[0]
    root_risk = resolve_risk_decision(
        root.intent,
        root.operation,
        role=role,
        channel=channel,
        routing_hints=routing_hints,
    )
    executable_prefix = (root,) if root_risk.tier == "read_only" else ()
    return executable_prefix, plan.steps[1:]


def task_step_payload(step: TaskStep) -> dict[str, Any]:
    return {
        "step_id": step.step_id,
        "intent": step.intent,
        "operation": step.operation,
        "entities": _plain_policy_payload(dict(step.entities)),
        "depends_on": list(step.depends_on),
        "relation": step.relation,
    }


def task_steps_payload(steps: tuple[TaskStep, ...] | list[TaskStep]) -> list[dict[str, Any]]:
    return [task_step_payload(step) for step in steps]


def task_plan_payload(plan: TaskPlan | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {
        "steps": task_steps_payload(plan.steps),
        "terminal_step_id": plan.terminal_step_id,
    }


def _fallback_task_plan(
    semantic: SemanticIntent,
    entities: Mapping[str, Any],
    normalization: list[str],
) -> tuple[TaskPlan, tuple[str, ...]]:
    if "plan_invalid_fallback_single" not in normalization:
        normalization.append("plan_invalid_fallback_single")
    root_intent = semantic.intent if semantic.intent in INTENT_DEFINITIONS else "unsupported"
    root_operation = semantic.operation if semantic.operation in REQUESTED_OPERATIONS else "advise"
    root = TaskStep(
        step_id="s1",
        intent=cast(IntentLiteral, root_intent),
        operation=cast(RequestedOperationLiteral, root_operation),
        entities=dict(entities),
        depends_on=(),
        relation="root",
    )
    return TaskPlan(steps=(root,), terminal_step_id=root.step_id), tuple(normalization)


def _same_intent_merge_record(entities: Mapping[str, Any]) -> str:
    if any(
        key in TASK_PLAN_ENTITY_IDENTIFIER_KEYS and isinstance(value, list) and len(value) > 1
        for key, value in entities.items()
    ):
        return "same_intent_entities_merged"
    return "same_intent_entity_merge_limited"


def _relation_for_task_step(
    root_operation: RequestedOperationLiteral,
    step_operation: RequestedOperationLiteral,
) -> TaskStepRelationLiteral:
    if root_operation == "read_status" and step_operation in {
        "draft_reply",
        "draft_action",
        "execute_action",
        "escalate",
    }:
        return "dependency"
    return "parallel"


def _operation_for_task_step(intent: str, requested_operation: str) -> RequestedOperationLiteral:
    operation = _valid_operation(requested_operation)
    if intent == "action_request" and operation in {"read_status", "advise"}:
        return "execute_action"
    return _operation_for_selected_intent(intent, requested_operation)


def _plain_policy_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_policy_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_policy_payload(item) for item in value]
    return value


def confidence_requires_clarification(
    primary_intent: str,
    requested_operation: str,
    confidence: float | None,
    pre_route: PreRouteDecision | None = None,
    *,
    calibrated_confidence: float | None = None,
) -> bool:
    return decide_clarification(
        primary_intent,
        requested_operation,
        confidence,
        pre_route,
        calibrated_confidence=calibrated_confidence,
    ).requires_clarification


def decide_clarification(
    primary_intent: str,
    requested_operation: str,
    confidence: float | None,
    pre_route: PreRouteDecision | None = None,
    *,
    calibrated_confidence: float | None = None,
) -> ClarificationDecision:
    del calibrated_confidence
    if pre_route and pre_route.requires_clarification:
        return ClarificationDecision(
            requires_clarification=True,
            reason=pre_route.disposition,
            threshold_applied=None,
        )
    safety_sensitive = (
        primary_intent in HIGH_RISK_INTENTS
        or requested_operation in {"draft_action", "execute_action", "escalate"}
        or (
            primary_intent in {"refund_troubleshooting", "compensation_suggestion"}
            and requested_operation != "read_status"
        )
    )
    threshold = SAFETY_CONFIDENCE_THRESHOLD if safety_sensitive else ORDINARY_CONFIDENCE_THRESHOLD
    if confidence is None or confidence < threshold:
        return ClarificationDecision(
            requires_clarification=True,
            reason="low_confidence",
            threshold_applied=threshold,
        )
    return ClarificationDecision(
        requires_clarification=False,
        reason=None,
        threshold_applied=threshold,
    )


def resolve_risk_decision(
    primary_intent: str,
    requested_operation: str,
    role: str | None = None,
    channel: str | None = None,
    routing_hints: dict[str, Any] | None = None,
) -> RiskDecision:
    """Resolve ordinary-chat safety tier from effective policy state.

    The role is accepted for policy expansion but does not grant chat approval
    authority in this phase.
    """
    del role
    hints = routing_hints or {}
    if (
        requested_operation == "approval_decision"
        or hints.get("pre_route_disposition") == "approval_chat_not_trusted"
        or hints.get("clarification_reason") == "approval_chat_not_trusted"
    ):
        return _risk_decision_from_template(RISK_POLICY_TABLE[("approval_decision", "*", "*")], primary_intent)

    channel_class = _channel_class(channel or str(hints.get("channel") or "ordinary_chat"))
    template = _lookup_risk_policy(primary_intent, requested_operation, channel_class)
    return _risk_decision_from_template(template, primary_intent)


def resolve_risk_tier(
    primary_intent: str,
    requested_operation: str,
    role: str | None = None,
    channel: str | None = None,
    routing_hints: dict[str, Any] | None = None,
) -> RiskTierLiteral:
    return resolve_risk_decision(
        primary_intent,
        requested_operation,
        role=role,
        channel=channel,
        routing_hints=routing_hints,
    ).tier


def _channel_class(channel: str) -> str:
    return "ordinary_chat" if channel in ORDINARY_CHAT_CHANNELS else "non_chat"


def _lookup_risk_policy(primary_intent: str, requested_operation: str, channel_class: str) -> RiskDecision:
    operation = requested_operation if requested_operation in REQUESTED_OPERATIONS else "*"
    intent_classes = _risk_intent_classes(primary_intent)
    for key in _risk_policy_keys(operation, intent_classes, channel_class):
        template = RISK_POLICY_TABLE.get(key)
        if template is not None:
            return template
    return RISK_POLICY_TABLE[("*", "*", "*")]


def _risk_policy_keys(
    operation: str,
    intent_classes: tuple[str, ...],
    channel_class: str,
) -> tuple[tuple[str, str, str], ...]:
    keys: list[tuple[str, str, str]] = []
    if operation in {"read_status", "draft_reply", "draft_action"}:
        for channel_candidate in (channel_class, "*"):
            keys.append((operation, "*", channel_candidate))
    if "compensation_suggestion" in intent_classes:
        for channel_candidate in (channel_class, "*"):
            keys.append(("*", "compensation_suggestion", channel_candidate))
    if operation in {"execute_action", "escalate"}:
        for channel_candidate in (channel_class, "*"):
            keys.append((operation, "*", channel_candidate))
    for intent_class in (item for item in intent_classes if item != "compensation_suggestion"):
        for channel_candidate in (channel_class, "*"):
            keys.append(("*", intent_class, channel_candidate))
    keys.append(("*", "*", "*"))
    return tuple(dict.fromkeys(keys))


def _risk_intent_classes(primary_intent: str) -> tuple[str, ...]:
    classes: list[str] = []
    if primary_intent in INTENT_DEFINITIONS:
        classes.append(primary_intent)
    if primary_intent in HIGH_RISK_INTENTS:
        classes.append("high_risk")
    if primary_intent in DIRECT_RESPONSE_INTENTS:
        classes.append("direct_response")
    return tuple(dict.fromkeys(classes))


def _risk_decision_from_template(template: RiskDecision, primary_intent: str) -> RiskDecision:
    definition = INTENT_DEFINITIONS.get(primary_intent)
    evidence_required = definition.evidence_required if definition is not None else template.evidence_required
    return RiskDecision(
        tier=template.tier,
        evidence_required=evidence_required,
        approval_required=template.approval_required,
        reason_codes=template.reason_codes,
    )


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
