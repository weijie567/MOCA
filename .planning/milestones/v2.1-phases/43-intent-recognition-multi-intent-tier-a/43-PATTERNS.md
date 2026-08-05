# Phase 43: Intent Recognition Multi-Intent Tier A - Pattern Map

**Mapped:** 2026-07-02
**Files analyzed:** 10
**Analogs found:** 10 / 10
**Source scope scanned:** `src/agent`, `tests/agent` (99 Python files)
**Inputs read:** `43-CONTEXT.md`, `43-RESEARCH.md`, `43-VALIDATION.md`, `AGENTS.md`, `CLAUDE.md`

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/intent_policy.py` | service/utility | transform | `src/agent/intent_policy.py` | exact |
| `src/agent/nodes/classify_intent.py` | controller/node | request-response + transform | `src/agent/nodes/classify_intent.py` | exact |
| `src/agent/state.py` | model | request-response state | `src/agent/state.py` | exact |
| `src/agent/nodes/receive_request.py` | middleware/node | request-response reset | `src/agent/nodes/receive_request.py` | exact |
| `src/agent/nodes/final_response.py` | controller/node | request-response | `src/agent/nodes/final_response.py` | exact |
| `tests/agent/test_intent_task_plan.py` | test | transform | `tests/agent/test_intent_routing.py` + `tests/agent/test_intent_policy_registry.py` | role-match |
| `tests/agent/test_intent_routing.py` | test | request-response + transform | `tests/agent/test_intent_routing.py` | exact |
| `tests/agent/test_nodes/test_classify_intent.py` | test | request-response | `tests/agent/test_nodes/test_classify_intent.py` | exact |
| `tests/agent/test_nodes/test_final_response.py` | test | request-response | `tests/agent/test_nodes/test_final_response.py` | exact |
| `tests/agent/test_nodes/test_receive_request.py` | test | request-response reset | `tests/agent/test_nodes/test_receive_request.py` | exact |

## Pattern Assignments

### `src/agent/intent_policy.py` (service/utility, transform)

**Analog:** `src/agent/intent_policy.py`

**Imports pattern** (lines 1-12):
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.agent.schemas import IntentLiteral, RequiredSlotExpression, RequestedOperationLiteral, RiskTierLiteral
```

**Frozen contract pattern** (lines 47-69):
```python
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
```

**Copy for Phase 43:** add frozen `TaskStep` and `TaskPlan` beside these contracts. Use existing `IntentLiteral`, `RequestedOperationLiteral`, and the current five-value `RiskTierLiteral`; do not add a new risk enum.

**Registry wrapper pattern** (lines 257-271):
```python
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
```

**Copy for Phase 43:** if exposing plan helpers through `IntentPolicyRegistry`, keep methods thin and delegate to module-level helpers. Existing consumers and tests prefer registry-owned policy access.

**Keyword + semantic transform pattern** (lines 571-665):
```python
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
```

**Copy for Phase 43:** build `TaskPlan` from the existing `IntentResultV3` fields, `SemanticIntent`, and keyword signals. Keep deterministic logic here; do not add another LLM call.

**Risk gate pattern** (lines 722-745):
```python
def resolve_risk_decision(
    primary_intent: str,
    requested_operation: str,
    role: str | None = None,
    channel: str | None = None,
    routing_hints: dict[str, Any] | None = None,
) -> RiskDecision:
    """Resolve ordinary-chat safety tier from effective policy state."""
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
```

**Copy for Phase 43:** executable-prefix selection must call `resolve_risk_decision(...).tier == "read_only"` per step. Do not infer safety from operation names only.

**Pre-route multi-target guard to account for** (lines 521-528):
```python
multi_target = any(token in lowered for token in (" and also ", "同时", "以及", "顺便"))
if multi_target:
    return PreRouteDecision(
        disposition="multi_target_request",
        requested_operation=None,
        reason_codes=["multi_target_request"],
        requires_clarification=True,
    )
```

**Copy for Phase 43:** after a valid `TaskPlan` is built, neutralize only this legacy `multi_target_request` clarification path for the current turn. Do not neutralize `approval_chat_not_trusted` or `safety_sensitive`.

---

### `src/agent/nodes/classify_intent.py` (controller/node, request-response + transform)

**Analog:** `src/agent/nodes/classify_intent.py`

**Imports pattern** (lines 11-25):
```python
from src.agent.intent_policy import (
    ClarificationDecision,
    INTENT_POLICY_REGISTRY,
    RiskDecision,
    SLOT_POLICY_REGISTRY,
    SemanticIntent,
    PreRouteDecision,
    decide_clarification,
    derive_keyword_signals,
    detect_pre_route,
)
from src.agent.prompts import CLASSIFY_INTENT_SYSTEM
from src.agent.schemas import IntentResultV3, RequiredSlotExpression
from src.agent.routing import route_after_intent
from src.agent.state import AgentState
```

**Serialization pattern** (lines 129-155):
```python
def _semantic_payload(semantic: SemanticIntent) -> dict[str, Any]:
    return {
        "intent": semantic.intent,
        "operation": semantic.operation,
        "entities": dict(semantic.entities),
        "raw_confidence": semantic.raw_confidence,
        "keyword_signals": list(semantic.keyword_signals),
        "arbitration": list(semantic.arbitration),
    }


def _risk_payload(risk: RiskDecision) -> dict[str, Any]:
    return {
        "tier": risk.tier,
        "evidence_required": risk.evidence_required,
        "approval_required": risk.approval_required,
        "reason_codes": list(risk.reason_codes),
    }
```

**Copy for Phase 43:** add explicit `_task_step_payload`, `_task_plan_payload`, and prefix/deferred serializers. Store only plain dict/list values in `AgentState` and `classification_trace`.

**Main conversion flow** (lines 323-366):
```python
semantic_before_pre_route = _semantic_from_llm_result(result, user_query)
semantic, pre_route_overrides = _apply_pre_route_to_semantic(semantic_before_pre_route, pre_route)
primary_intent = semantic.intent
requested_operation = semantic.operation
policy_overrides: list[dict[str, Any]] = []
...
routing_hints = dict(result.routing_hints)
reason_codes = list(result.reason_codes) + list(semantic.arbitration)
if pre_route and pre_route.disposition != "none":
    routing_hints["pre_route_disposition"] = pre_route.disposition
    routing_hints["requires_clarification"] = pre_route.requires_clarification
    if pre_route.requires_clarification:
        routing_hints["clarification_reason"] = pre_route.disposition
    reason_codes.extend(pre_route.reason_codes)

semantic, risk_decision, clarification_decision = _classify_layers(
    semantic,
    role=role,
    channel=channel,
    routing_hints=routing_hints,
    pre_route=pre_route,
    calibrated_confidence=result.calibrated_confidence,
)
```

**Copy for Phase 43:** build/normalize/select the `TaskPlan` after the effective root semantic is known and before `route_after_intent(update)`. If the executable prefix is non-empty, replace the effective single-intent fields with the prefix tail. If empty, keep `s1` effective and defer later steps.

**State update + trace pattern** (lines 367-414):
```python
update = {
    "primary_intent": primary_intent,
    "requested_operation": requested_operation,
    "intent_confidence": result.confidence,
    "risk_tier": risk_decision.tier,
    "secondary_intents": [str(intent) for intent in result.secondary_intents],
    "required_slots": policy_required_slots,
    "candidate_slots": dict(result.candidate_slots),
    "routing_hints": routing_hints,
    "current_intent": primary_intent,
    "last_intent": primary_intent,
}
route_decision = route_after_intent(update)
classification_trace = {
    "raw_llm_classification": raw,
    "candidate_classification": raw,
    "policy_owner": "IntentPolicyRegistry",
    "pre_route_decision": pre_route.model_dump() if pre_route else None,
    "policy_overrides": policy_overrides,
    "semantic_intent": _semantic_payload(semantic),
    "risk_decision": _risk_payload(risk_decision),
    "clarification_decision": _clarification_payload(clarification_decision),
    "effective_classification": {
        "primary_intent": primary_intent,
        "requested_operation": requested_operation,
        "required_slots": policy_required_slots,
    },
    "risk_tier": risk_decision.tier,
    "route_decision": route_decision,
    "reason_codes": reason_codes,
}
...
return {key: value for key, value in update.items() if key not in FORBIDDEN_STATE_WRITES}
```

**Copy for Phase 43:** add `task_plan`, `deferred_steps`, `executable_prefix`, and `plan_normalization` into this trace shape. Keep `llm_outputs["intent_classification"]["classification_trace"]` synchronized with `update["classification_trace"]`.

**Deterministic no-LLM path pattern** (lines 497-546):
```python
update = {
    "primary_intent": primary_intent,
    "requested_operation": requested_operation,
    "intent_confidence": intent_confidence,
    "risk_tier": risk_decision.tier,
    "secondary_intents": [],
    "required_slots": required_slots,
    "candidate_slots": candidate_slots,
    "routing_hints": routing_hints,
    "current_intent": primary_intent,
    "last_intent": primary_intent,
}
route_decision = route_after_intent(update)
classification_trace = {
    "raw_llm_classification": None,
    "candidate_classification": None,
    "policy_owner": "IntentPolicyRegistry",
    ...
}
```

**Copy for Phase 43:** preserve active-flow/short-reply deterministic behavior. If adding plan keys here, keep them N=1-equivalent or empty so active-slot continuation does not become a multi-intent path.

**Fallback pattern** (lines 743-786):
```python
classification_trace = {
    "raw_llm_classification": None,
    "candidate_classification": None,
    "policy_owner": "IntentPolicyRegistry",
    "pre_route_decision": pre_route.model_dump(),
    "policy_overrides": [{"source": "classifier_validation_failed", "reason_codes": [*pre_route.reason_codes]}],
    ...
    "route_decision": route_after_intent(fallback_state),
    "reason_codes": ["classifier_validation_failed", *pre_route.reason_codes],
}
return {
    "primary_intent": "unsupported",
    "requested_operation": "advise",
    "intent_confidence": 0.0,
    "risk_tier": risk_decision.tier,
    "classification_trace": classification_trace,
    ...
}
```

**Copy for Phase 43:** invalid plans should fail closed to existing single-intent state and trace `plan_invalid_fallback_single` without changing `IntentResultV3`.

---

### `src/agent/state.py` (model, request-response state)

**Analog:** `src/agent/state.py`

**TypedDict pattern** (lines 55-89):
```python
class AgentState(TypedDict, total=False):
    """LangGraph state contract split into persistent and ephemeral fields."""

    # Durable graph/checkpoint context: survives across turns via the checkpointer.
    thread_id: str
    tenant_id: str
    user_id: str
    role: str
    active_slots: ActiveSlots
    ...

    # Ephemeral context: reset by receive_request at the start of each turn.
    user_query: str | None
    normalized_query: str | None
    current_intent: str | None
    intent_confidence: float | None
    risk_tier: str | None
    classification_trace: dict[str, Any] | None
    target_merchant_context: dict[str, Any] | None
    active_flow_state: dict[str, Any] | None
    secondary_intents: list[str]
    required_slots: dict[str, Any]
    candidate_slots: dict[str, Any]
    routing_hints: dict[str, Any]
```

**Copy for Phase 43:** add only:

```python
task_plan: dict[str, Any] | None
deferred_steps: list[dict[str, Any]]
```

Place them in the ephemeral section near `classification_trace` / `secondary_intents`. Because `AgentState` is `total=False`, this is an additive optional contract.

---

### `src/agent/nodes/receive_request.py` (middleware/node, request-response reset)

**Analog:** `src/agent/nodes/receive_request.py`

**Imports and reset owner pattern** (lines 1-8, 45-47):
```python
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.agent.intent_policy import INTENT_POLICY_REGISTRY, SLOT_POLICY_REGISTRY
from src.agent.state import AgentState

async def receive_request(state: AgentState) -> dict:
    """Reset per-turn state so checkpointed graph context cannot leak stale context."""
```

**Per-turn reset pattern** (lines 61-84):
```python
return {
    "user_query": state.get("user_query"),
    "normalized_query": None,
    "current_intent": None,
    "intent_confidence": None,
    "risk_tier": None,
    "classification_trace": None,
    "target_merchant_context": None,
    "active_flow_state": active_flow_state,
    "secondary_intents": [],
    "required_slots": {"all_of": [], "any_of": [], "optional": []},
    "candidate_slots": {},
    "routing_hints": {},
    "extracted_slots": None,
    "active_slots": {},
    ...
    "primary_intent": None,
    "requested_operation": None,
}
```

**Copy for Phase 43:** add `"task_plan": None` and `"deferred_steps": []` to the returned reset dict near `classification_trace` / `secondary_intents`. This is the stale-state prevention owner; do not rely on absent fields.

**Trace pattern** (lines 49-59, 143-145):
```python
trace_steps = [
    {
        "node": "receive_request",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": None,
    }
]
...
"current_run_id": state.get("current_run_id") or str(uuid4()),
"run_started_at": started_at,
"trace_steps": trace_steps,
```

**Copy for Phase 43:** keep reset deterministic and side-effect free.

---

### `src/agent/nodes/final_response.py` (controller/node, request-response)

**Analog:** `src/agent/nodes/final_response.py`

**Imports pattern** (lines 1-7):
```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.agent.prompts import INSUFFICIENT_EVIDENCE_RESPONSE
from src.agent.state import AgentState
```

**Safe mapping helper pattern** (lines 409-421):
```python
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
```

**Copy for Phase 43:** use local helper functions to parse `state.get("deferred_steps")` and `classification_trace.plan_normalization` defensively. Do not assume persisted state is well-typed.

**LLM-output sync pattern** (lines 293-300, 513-525):
```python
def _business_fact_llm_output(response_text: str) -> dict[str, Any]:
    return {
        "response_text": response_text,
        "evidence_citations": [],
        "final_status": "completed",
        "mode": "deterministic-template",
        "approval_context": None,
    }
```

```python
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
```

**Copy for Phase 43:** route all visible text through one decorator helper before returning. When `llm_outputs["final_response"]` exists, its `response_text` must match decorated `final_response`.

**Early-return branches to decorate** (lines 656-688, 689-719, 720-750, 751-770):
```python
if blocked_response and state.get("safety_snapshot_verified") is False:
    return {
        "final_response": blocked_response,
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "final_response": {
                "response_text": blocked_response,
                ...
            },
        },
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
    }
if isinstance(clarification_request, dict):
    ...
    response_text = state.get("final_response") or fallback
    return {
        "final_response": response_text,
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "final_response": {
                "response_text": response_text,
                ...
            },
        },
        ...
    }
```

```python
if verification is not None:
    if _can_render_policy_qa_partial_overlap(state, draft, verification):
        response_text = _policy_qa_partial_overlap_response(draft)
        return {
            "final_response": response_text,
            "llm_outputs": {
                **(state.get("llm_outputs") or {}),
                "final_response": _policy_qa_partial_overlap_llm_output(response_text, draft, verification),
            },
            ...
        }
    ...
    return {
        "final_response": response_text,
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "final_response": _verification_llm_output(response_text, verification),
        },
        ...
    }
```

```python
if _can_render_business_fact_response(state, draft):
    response_text = _business_fact_response(state.get("business_context") or {})
    return {
        "final_response": response_text,
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "final_response": _business_fact_llm_output(response_text),
        },
        ...
    }
response_text = _completed_response(draft, state.get("risk_assessment") or {})
...
return {
    "final_response": response_text,
    "llm_outputs": {
        **(state.get("llm_outputs") or {}),
        "final_response": {
            "response_text": response_text,
            ...
        },
    },
    ...
}
```

**Copy for Phase 43:** deferred-step presentation must be separate from `clarification_request`. Add the complaint-folding safety note through the same decorator so it appears even when no deferred steps exist.

---

### `tests/agent/test_intent_task_plan.py` (test, transform)

**Analog:** `tests/agent/test_intent_routing.py` and `tests/agent/test_intent_policy_registry.py`

**Import style** (from `tests/agent/test_intent_routing.py` lines 1-33):
```python
from __future__ import annotations

import inspect

import pytest

from tests.agent.conftest import FakeLLM

from src.agent import routing as routing_module
from src.agent.intent_policy import (
    DIRECT_RESPONSE_INTENTS,
    EVIDENCE_REQUIRED_INTENTS,
    HIGH_RISK_INTENTS,
    INTENT_DEFINITIONS,
    ...
    resolve_risk_decision,
    resolve_risk_tier,
)
from src.agent.nodes import classify_intent as classify_intent_module
from src.agent.nodes.classify_intent import intent_result_to_state
from src.agent.routing import INTENT_ROUTES, SLOT_ROUTES, route_after_intent, route_after_slots
from src.agent.schemas import IntentResultV3, RequiredSlotExpression
```

**Policy registry test shape** (from `tests/agent/test_intent_policy_registry.py` lines 23-35):
```python
def test_intent_policy_registry_mirrors_existing_constants() -> None:
    registry = IntentPolicyRegistry()

    assert registry.definitions() == INTENT_DEFINITIONS
    assert registry.intent_names() == tuple(INTENT_DEFINITIONS)
    assert registry.precedence_order() == PRECEDENCE_INTENTS
    assert registry.route_policy() == INTENT_ROUTE_POLICY
    assert registry.direct_response_intents() == frozenset(DIRECT_RESPONSE_INTENTS)
    assert registry.evidence_required_intents() == frozenset(EVIDENCE_REQUIRED_INTENTS)
    assert registry.high_risk_intents() == frozenset(HIGH_RISK_INTENTS)
```

**Payload helper pattern** (from `tests/agent/test_nodes/test_classify_intent.py` lines 14-30):
```python
def _intent_v3(**overrides):
    payload = {
        "schema_version": "intent_result.v3",
        "primary_intent": "refund_troubleshooting",
        "requested_operation": "read_status",
        "confidence": 0.95,
        "calibrated_confidence": 0.92,
        "secondary_intents": [],
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "candidate_slots": {"order_id": "ORD-001"},
        "routing_hints": {},
        "classifier_version": "intent_classifier.v2",
        "calibration_version": "calibration.unverified",
        "reason_codes": ["test"],
    }
    payload.update(overrides)
    return payload
```

**Risk matrix pattern** (from `tests/agent/test_intent_routing.py` lines 225-241):
```python
@pytest.mark.parametrize(
    ("primary_intent", "requested_operation", "routing_hints", "expected"),
    [
        ("refund_troubleshooting", "read_status", {}, "read_only"),
        ("refund_troubleshooting", "draft_reply", {}, "draft_only"),
        ("compensation_suggestion", "draft_action", {}, "suggest_action"),
        ("complaint_escalation", "escalate", {}, "approval_required"),
        ...
    ],
)
def test_resolve_risk_tier(primary_intent, requested_operation, routing_hints, expected):
    assert resolve_risk_tier(primary_intent, requested_operation, channel="ordinary_chat", routing_hints=routing_hints) == expected
```

**Copy for Phase 43:** create focused non-DB unit tests for:

- N=1 plan preserves effective fields and route decision.
- read -> draft dependency defers second step.
- complaint secondary folds only on whitelist and records safety note metadata.
- independent secondary intents remain explicit steps.
- high-risk secondary steps defer.
- invalid plan fails closed and traces `plan_invalid_fallback_single`.
- `small_talk` secondary drops and traces `modifier_dropped:small_talk`.

---

### `tests/agent/test_intent_routing.py` (test, request-response + transform)

**Analog:** `tests/agent/test_intent_routing.py`

**Pre-route and keyword regression pattern** (lines 65-79):
```python
def test_detect_pre_route_approval_chat_and_hard_negatives():
    decision = detect_pre_route("approve APR-1")
    assert decision.disposition == "approval_chat_not_trusted"
    assert decision.requested_operation == "advise"
    assert "approval_chat_not_trusted" in decision.reason_codes

    assert detect_pre_route("通过订单号 ORD-1 查询退款状态").disposition == "none"
    assert detect_pre_route("通过规则判断是否要补偿").disposition == "none"
    assert detect_pre_route("accept language preference").disposition == "none"
```

**Classification adapter regression pattern** (lines 190-216):
```python
result = IntentResultV3.model_validate(
    {
        "schema_version": "intent_result.v3",
        "primary_intent": "action_request",
        "requested_operation": "advise",
        ...
    }
)

update = intent_result_to_state(result, user_query="那这个订单下一步应该怎么处理？")

assert update["primary_intent"] == "refund_troubleshooting"
assert update["requested_operation"] == "read_status"
assert route_after_intent(update) == "session_memory_load"
```

**Async classify-node regression pattern** (lines 373-401):
```python
@pytest.mark.asyncio
async def test_classifier_pre_route_wiring_for_approval_chat(monkeypatch, base_state):
    payload = {
        "schema_version": "intent_result.v3",
        "primary_intent": "policy_qa",
        "requested_operation": "read_status",
        ...
    }
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: FakeLLM(payload))

    update = await classify_intent_module.classify_intent({**base_state, "user_query": "approve APR-1"})

    assert update["routing_hints"]["pre_route_disposition"] == "approval_chat_not_trusted"
    assert update["risk_tier"] == "forbidden_in_chat"
    assert update["classification_trace"]["route_decision"] == "clarification_gate"
    assert "approval_result" not in update
```

**Copy for Phase 43:** if this file is extended, keep it as route-contract coverage. Multi-intent policy detail belongs in `test_intent_task_plan.py`; routing tests should verify valid Tier A multi-target state no longer trips the legacy clarification guard while approval/safety guards still fail closed.

---

### `tests/agent/test_nodes/test_classify_intent.py` (test, request-response)

**Analog:** `tests/agent/test_nodes/test_classify_intent.py`

**Async node + FakeLLM pattern** (lines 33-54):
```python
@pytest.mark.asyncio
async def test_classify_intent_success(monkeypatch, base_state, fake_llm_intent):
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: fake_llm_intent)

    result = await classify_intent_module.classify_intent(base_state)

    assert result["current_intent"] == "refund_troubleshooting"
    assert result["primary_intent"] == "refund_troubleshooting"
    assert result["requested_operation"] == "read_status"
    assert result["intent_confidence"] == 0.95
    assert result["risk_tier"] == "read_only"
    assert result["classification_trace"]["raw_llm_classification"]["primary_intent"] == "refund_troubleshooting"
    assert result["classification_trace"]["route_decision"] == "session_memory_load"
```

**Registry monkeypatch pattern** (lines 104-143):
```python
def test_intent_result_to_state_uses_intent_policy_registry_for_precedence_and_risk(monkeypatch):
    class FakeIntentRegistry:
        def resolve_precedence(
            self,
            primary_intent: str,
            secondary_intents: list[str],
            requested_operation: str,
            *,
            query: str = "",
            raw_confidence: float | None = None,
        ) -> tuple[str, str, list[str]]:
            del raw_confidence
            return "small_talk", "advise", ["fake_registry_precedence"]

        def resolve_risk_decision(
            self,
            primary_intent: str,
            requested_operation: str,
            role: str | None = None,
            channel: str | None = None,
            routing_hints: dict | None = None,
        ) -> RiskDecision:
            del primary_intent, requested_operation, role, channel, routing_hints
            return RiskDecision(
                tier="draft_only",
                evidence_required=True,
                approval_required=False,
                reason_codes=("fake_registry_risk",),
            )

    monkeypatch.setattr(classify_intent_module, "INTENT_POLICY_REGISTRY", FakeIntentRegistry(), raising=False)
    result = IntentResultV3.model_validate(_intent_v3(primary_intent="refund_troubleshooting"))

    update = intent_result_to_state(result, user_query="hi")

    assert update["primary_intent"] == "small_talk"
    assert update["risk_tier"] == "draft_only"
    assert "fake_registry_precedence" in update["classification_trace"]["reason_codes"]
```

**Copy for Phase 43:** add node tests that assert `task_plan`, `deferred_steps`, `classification_trace.task_plan`, `classification_trace.executable_prefix`, and `classification_trace.plan_normalization` are serialized dict/list values. Also assert N=1 fields remain unchanged.

**Shared fixtures** (from `tests/agent/conftest.py` lines 11-35, 112-120):
```python
class FakeLLM:
    """Deterministic fake LLM for CI. Returns predetermined structured outputs."""

    def __init__(self, response_dict: dict[str, Any]):
        self._response = response_dict

    async def ainvoke(self, messages, **kwargs):
        from langchain_core.messages import AIMessage

        return AIMessage(content=json.dumps(self._response, ensure_ascii=False))

    def with_structured_output(self, schema):
        fake = self

        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                if issubclass(schema, BaseModel):
                    return schema.model_validate(fake._response)
                return fake._response

        return _Wrapper()


@pytest.fixture
def base_state():
    return {
        "thread_id": "test-thread",
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "role": "support_agent",
        "user_query": "订单ORD-001为什么还没退款？",
    }
```

---

### `tests/agent/test_nodes/test_final_response.py` (test, request-response)

**Analog:** `tests/agent/test_nodes/test_final_response.py`

**Deterministic final response assertion pattern** (lines 46-97):
```python
@pytest.mark.asyncio
async def test_final_response_uses_deterministic_citation_template(base_state):
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "解释退款超时规则",
            "reasoning_summary": "商家需要在规定时效内处理退款。",
            "evidence_refs": [
                {
                    "doc_key": "refund_policy",
                    "chunk_id": "refund_policy_006",
                    ...
                }
            ],
        },
        ...
    }

    result = await final_response(state)

    assert "根据 refund_policy / refund_policy_006" in result["final_response"]
    assert result["llm_outputs"]["final_response"]["final_status"] == "completed"
    assert result["trace_steps"][-1]["model_name"] == "deterministic-template"
```

**Clarification early-return pattern** (lines 369-406):
```python
@pytest.mark.asyncio
async def test_final_response_preserves_clarification_response(base_state):
    result = await final_response(
        {
            **base_state,
            "clarification_request": {
                "reason": "missing_required_information",
                "missing": ["case_identifier"],
            },
            "final_response": "Could you provide a bit more information so I can help?",
        }
    )

    assert result["final_response"] == "Could you provide a bit more information so I can help?"
    assert result["llm_outputs"]["final_response"]["final_status"] == "insufficient_evidence"
```

**Copy for Phase 43:** add deferred-confirmation tests for representative early-return branches: clarification, verification/manual-review or insufficient evidence, business fact, and completed response. Each should assert the deferred request text is visible and `llm_outputs["final_response"]["response_text"]` is synchronized when present. Add complaint-folding safety-note coverage even with `deferred_steps == []`.

---

### `tests/agent/test_nodes/test_receive_request.py` (test, request-response reset)

**Analog:** `tests/agent/test_nodes/test_receive_request.py`

**Reset test pattern** (lines 11-55):
```python
@pytest.mark.asyncio
async def test_receive_request_resets_ephemeral(base_state):
    state = {
        **base_state,
        "current_intent": "old_intent",
        "intent_confidence": 0.99,
        "risk_tier": "read_only",
        "classification_trace": {"old": "trace"},
        "target_merchant_context": {"status": "resolved", "source": "spoofed"},
        "active_flow_state": {"old": "flow"},
        "secondary_intents": ["policy_qa"],
        ...
    }

    result = await receive_request(state)

    assert result["current_intent"] is None
    assert result["intent_confidence"] is None
    assert result["classification_trace"] is None
    assert result["secondary_intents"] == []
    assert result["routing_hints"] == {}
```

**AgentState annotation pattern** (lines 152-168):
```python
def test_agent_state_declares_session_context_target_fields():
    annotations = AgentState.__annotations__

    for field in (
        "session_context",
        "session_context_bundle",
        "session_context_load_status",
        "memory_context",
        "memory_context_bundle",
        "reviewed_memory_context_retrieve_status",
        "memory_write_decision",
    ):
        assert field in annotations


def test_agent_state_declares_target_merchant_context_field():
    assert "target_merchant_context" in AgentState.__annotations__
```

**Copy for Phase 43:** extend the first reset test with stale `"task_plan": {...}` and `"deferred_steps": [{...}]`; assert reset to `None` and `[]`. Add an annotation test for both new fields.

---

## Shared Patterns

### Single-Intent Route Contract

**Source:** `src/agent/routing.py` lines 70-75, 219-250

```python
def route_after_intent(state: AgentState) -> str:
    try:
        route = _route_after_intent(state)
    except Exception:
        return "clarification_gate"
    return route if route in INTENT_ROUTES else "clarification_gate"
```

```python
def _route_after_intent(state: AgentState) -> str:
    intent = _intent(state)
    requested_operation = state.get("requested_operation") or "advise"
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    if requested_operation == "approval_decision":
        return "clarification_gate"
    if routing_hints.get("pre_route_disposition") == "approval_chat_not_trusted":
        return "clarification_gate"
    if routing_hints.get("clarification_reason") == "approval_chat_not_trusted":
        return "clarification_gate"
    ...
    if confidence_requires_clarification(intent, requested_operation, state.get("intent_confidence"), pre_route):
        return "clarification_gate"
    if INTENT_POLICY_REGISTRY.is_direct_response_intent(intent):
        return "final_response"
    route = INTENT_POLICY_REGISTRY.route_for_intent(intent)
    if route is None:
        return "clarification_gate"
    ...
    return route
```

**Apply to:** `classify_intent.py`, policy tests, routing tests.

**Planner note:** preserve these consumers by writing only the effective current-turn single-intent fields into `primary_intent`, `requested_operation`, `risk_tier`, `required_slots`, and `routing_hints`.

### State-Safe Serialization

**Source:** `src/agent/nodes/classify_intent.py` lines 129-155, 380-414

**Apply to:** `intent_policy.py`, `classify_intent.py`, tests for trace/state.

**Pattern:** dataclasses can exist inside policy helpers, but `AgentState`, `classification_trace`, and `llm_outputs` receive only dict/list/scalar values.

### Deferred Response Decoration

**Source:** `src/agent/nodes/final_response.py` lines 647-770

**Apply to:** `final_response.py`, `test_final_response.py`.

**Pattern:** every branch assigns or has a `response_text` before return. Decorate that text through one helper and keep `llm_outputs["final_response"]["response_text"]` synchronized where the branch creates final-response LLM output.

### Per-Turn Reset

**Source:** `src/agent/nodes/receive_request.py` lines 45-146

**Apply to:** `state.py`, `receive_request.py`, `test_receive_request.py`.

**Pattern:** any new ephemeral state field must be reset explicitly by `receive_request`.

### Test Entry Points

**Source:** `AGENTS.md` lines 24-29 and `43-VALIDATION.md` lines 22-24

Use only project-scoped commands:

```bash
uv run pytest tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_final_response.py tests/agent/test_nodes/test_receive_request.py -q
uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/architecture/test_phase32_static_contract.py -q
uv run ruff check src/agent tests/agent
```

Never use bare `pytest` or bare `python -m pytest` in MOCA.

## No Analog Found

None. The new `tests/agent/test_intent_task_plan.py` does not exist yet, but it has strong role-match analogs in `tests/agent/test_intent_routing.py`, `tests/agent/test_intent_policy_registry.py`, and `tests/agent/test_nodes/test_classify_intent.py`.

## Metadata

**Analog search scope:** `src/agent/**/*.py`, `tests/agent/**/*.py`
**Files scanned:** 99
**Pattern extraction date:** 2026-07-02
**Read-only source constraint:** honored; only this PATTERNS artifact should be written in this phase step.
