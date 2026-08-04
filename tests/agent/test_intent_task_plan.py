from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.agent.intent_policy import (
    SemanticIntent,
    TaskPlan,
    TaskStep,
    build_task_plan,
    select_executable_prefix,
    task_plan_payload,
    task_step_payload,
    task_steps_payload,
)
from src.agent.schemas import IntentLiteral, RequestedOperationLiteral


def _semantic(
    intent: IntentLiteral = "refund_troubleshooting",
    operation: RequestedOperationLiteral = "read_status",
    entities: dict[str, object] | None = None,
) -> SemanticIntent:
    return SemanticIntent(
        intent=intent,
        operation=operation,
        entities=entities or {"order_id": "ORD-1"},
        raw_confidence=0.91,
        keyword_signals=(),
        arbitration=(),
    )


def _step(
    step_id: str,
    intent: IntentLiteral = "policy_qa",
    operation: RequestedOperationLiteral = "read_status",
) -> TaskStep:
    return TaskStep(
        step_id=step_id,
        intent=intent,
        operation=operation,
        entities={"order_id": "ORD-1"},
        depends_on=(),
        relation="parallel" if step_id != "s1" else "root",
    )


def test_task_plan_contract_serializes_to_plain_payload() -> None:
    semantic = _semantic(entities={"order_id": ["ORD-1", "ORD-2"], "nested": ("a", "b")})

    plan, normalization = build_task_plan(semantic)

    assert normalization == ()
    assert plan.terminal_step_id == "s1"
    assert plan.steps[0].step_id == "s1"
    assert plan.steps[0].intent == "refund_troubleshooting"
    assert plan.steps[0].operation == "read_status"
    assert plan.steps[0].depends_on == ()
    assert plan.steps[0].relation == "root"
    assert task_step_payload(plan.steps[0]) == {
        "step_id": "s1",
        "intent": "refund_troubleshooting",
        "operation": "read_status",
        "entities": {"order_id": ["ORD-1", "ORD-2"], "nested": ["a", "b"]},
        "depends_on": [],
        "relation": "root",
    }
    assert task_steps_payload(plan.steps) == [task_step_payload(plan.steps[0])]
    assert task_plan_payload(plan) == {
        "steps": [task_step_payload(plan.steps[0])],
        "terminal_step_id": "s1",
    }
    assert task_plan_payload(None) is None

    with pytest.raises(FrozenInstanceError):
        plan.terminal_step_id = "s2"
    with pytest.raises(ValueError):
        TaskPlan(steps=plan.steps, terminal_step_id="missing")
    with pytest.raises(ValueError):
        TaskPlan(
            steps=(
                _step("s1"),
                _step("s2", "order_status_inquiry"),
                _step("s3", "refund_troubleshooting"),
                _step("s4", "policy_qa"),
            ),
            terminal_step_id="s1",
        )
    with pytest.raises(ValueError):
        TaskPlan(
            steps=(
                TaskStep(
                    step_id="s1",
                    intent="complaint_escalation",
                    operation="escalate",
                    entities={},
                    depends_on=(),
                    relation="modifier",
                ),
            ),
            terminal_step_id="s1",
        )


def test_single_intent_plan_preserves_effective_fields() -> None:
    semantic = _semantic("order_status_inquiry", "read_status", {"order_id": "ORD-1"})

    plan, normalization = build_task_plan(semantic)
    executable, deferred = select_executable_prefix(plan)

    assert normalization == ()
    assert len(plan.steps) == 1
    assert plan.steps[0].intent == semantic.intent
    assert plan.steps[0].operation == semantic.operation
    assert plan.steps[0].entities == semantic.entities
    assert [step.step_id for step in executable] == ["s1"]
    assert deferred == ()


def test_read_then_reply_draft_defers_second_step() -> None:
    semantic = _semantic("refund_troubleshooting", "read_status", {"ticket_id": "TKT-1"})

    plan, normalization = build_task_plan(
        semantic,
        secondary_intents=["ticket_reply_draft"],
        requested_operation="read_status",
    )
    executable, deferred = select_executable_prefix(plan)

    assert normalization == ()
    assert [step.step_id for step in executable] == ["s1"]
    assert len(plan.steps) == 2
    assert plan.steps[1].intent == "ticket_reply_draft"
    assert plan.steps[1].operation == "draft_reply"
    assert plan.steps[1].depends_on == ("s1",)
    assert plan.steps[1].relation == "dependency"
    assert deferred == (plan.steps[1],)


def test_second_read_step_is_deferred_not_dropped() -> None:
    semantic = _semantic("order_status_inquiry", "read_status", {"order_id": "ORD-1"})

    plan, normalization = build_task_plan(
        semantic,
        secondary_intents=["policy_qa"],
        requested_operation="read_status",
    )
    executable, deferred = select_executable_prefix(plan)

    assert normalization == ()
    assert [step.step_id for step in executable] == ["s1"]
    assert plan.steps[0].intent == "order_status_inquiry"
    assert plan.steps[1].intent == "policy_qa"
    assert plan.steps[1].operation == "read_status"
    assert deferred == (plan.steps[1],)


def test_complaint_modifier_folded_with_safety_note_metadata() -> None:
    semantic = _semantic(
        "compensation_suggestion",
        "draft_action",
        {"order_id": "ORD-1", "action_type": "coupon"},
    )

    plan, normalization = build_task_plan(
        semantic,
        secondary_intents=["complaint_escalation"],
        requested_operation="draft_action",
    )

    assert len(plan.steps) == 1
    assert plan.steps[0].intent == "compensation_suggestion"
    assert normalization == ("modifier_folded:complaint_as_severity",)


@pytest.mark.parametrize(
    "secondary_intent",
    [
        "order_status_inquiry",
        "refund_troubleshooting",
        "policy_qa",
        "ticket_reply_draft",
        "compensation_suggestion",
        "appeal_or_unban",
        "action_request",
    ],
)
def test_independent_secondary_intents_are_not_folded(secondary_intent: IntentLiteral) -> None:
    root_intent: IntentLiteral = "policy_qa" if secondary_intent != "policy_qa" else "order_status_inquiry"
    requested_operation: RequestedOperationLiteral = (
        "execute_action" if secondary_intent == "action_request" else "read_status"
    )
    semantic = _semantic(root_intent, "read_status", {"order_id": "ORD-1", "action_type": "refund"})

    plan, normalization = build_task_plan(
        semantic,
        secondary_intents=[secondary_intent],
        requested_operation=requested_operation,
    )

    assert normalization == ()
    assert len(plan.steps) == 2
    assert plan.steps[1].intent == secondary_intent
    assert plan.steps[1].relation != "modifier"


def test_high_risk_second_step_deferred() -> None:
    semantic = _semantic("order_status_inquiry", "read_status", {"order_id": "ORD-1", "action_type": "refund"})

    plan, normalization = build_task_plan(
        semantic,
        secondary_intents=["action_request"],
        requested_operation="execute_action",
    )
    executable, deferred = select_executable_prefix(plan)

    assert normalization == ()
    assert [step.step_id for step in executable] == ["s1"]
    assert plan.steps[1].intent == "action_request"
    assert plan.steps[1].operation == "execute_action"
    assert deferred == (plan.steps[1],)


def test_invalid_plan_fails_closed_to_single_intent() -> None:
    semantic = _semantic("order_status_inquiry", "read_status", {"order_id": "ORD-1"})

    plan, normalization = build_task_plan(
        semantic,
        secondary_intents=[
            "refund_troubleshooting",
            "policy_qa",
            "ticket_reply_draft",
            "compensation_suggestion",
        ],
        requested_operation="read_status",
    )

    assert len(plan.steps) == 1
    assert plan.steps[0].intent == "order_status_inquiry"
    assert normalization == ("plan_invalid_fallback_single",)


def test_same_intent_secondary_merges_when_entities_are_non_lossy() -> None:
    semantic = _semantic("order_status_inquiry", "read_status", {"order_id": ["ORD-1", "ORD-2"]})

    plan, normalization = build_task_plan(
        semantic,
        secondary_intents=["order_status_inquiry"],
        requested_operation="read_status",
    )

    assert len(plan.steps) == 1
    assert plan.steps[0].entities == {"order_id": ["ORD-1", "ORD-2"]}
    assert normalization == ("same_intent_entities_merged",)


def test_same_intent_scalar_merge_traces_limited_entity_shape() -> None:
    semantic = _semantic("order_status_inquiry", "read_status", {"order_id": "ORD-1"})

    plan, normalization = build_task_plan(
        semantic,
        secondary_intents=["order_status_inquiry"],
        requested_operation="read_status",
    )

    assert len(plan.steps) == 1
    assert plan.steps[0].entities == {"order_id": "ORD-1"}
    assert normalization == ("same_intent_entity_merge_limited",)


def test_small_talk_secondary_dropped() -> None:
    semantic = _semantic("order_status_inquiry", "read_status", {"order_id": "ORD-1"})

    plan, normalization = build_task_plan(
        semantic,
        secondary_intents=["small_talk"],
        requested_operation="read_status",
    )

    assert len(plan.steps) == 1
    assert plan.steps[0].intent == "order_status_inquiry"
    assert normalization == ("modifier_dropped:small_talk",)
