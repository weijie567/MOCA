# Phase 52: safety-pre-route-node - Pattern Map

**Mapped:** 2026-07-06
**Files analyzed:** 17
**Analogs found:** 17 / 17

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/nodes/safety_pre_route.py` | component | request-response | `src/agent/nodes/receive_request.py` + `src/agent/nodes/classify_intent.py` | role-match |
| `src/agent/routing.py` | route | request-response | `src/agent/routing.py` | exact |
| `src/agent/graph.py` | config | request-response | `src/agent/graph.py` | exact |
| `src/agent/intent_policy.py` | utility | transform | `src/agent/intent_policy.py` | exact |
| `src/agent/nodes/classify_intent.py` | component | request-response | `src/agent/nodes/classify_intent.py` | exact |
| `src/agent/state.py` | model | transform | `src/agent/state.py` | exact |
| `src/agent/graph_vocabulary.py` | utility | transform | `src/agent/graph_vocabulary.py` | exact |
| `tests/agent/test_nodes/test_safety_pre_route.py` | test | request-response | `tests/agent/test_nodes/test_receive_request.py` + `tests/agent/test_nodes/test_classify_intent.py` | role-match |
| `tests/agent/test_nodes/test_classify_intent.py` | test | request-response | `tests/agent/test_nodes/test_classify_intent.py` | exact |
| `tests/agent/test_graph.py` | test | request-response | `tests/agent/test_graph.py` | exact |
| `tests/test_graph_routing.py` | test | request-response | `tests/test_graph_routing.py` | exact |
| `tests/architecture/graph_baseline.py` | test | transform | `tests/architecture/graph_baseline.py` | exact |
| `tests/architecture/test_canonical_graph_baseline.py` | test | transform | `tests/architecture/test_canonical_graph_baseline.py` | exact |
| `tests/agent/test_graph_vocabulary.py` | test | transform | `tests/agent/test_graph_vocabulary.py` | exact |
| `docs/current-langgraph-architecture.md` | documentation | batch/static verification | `docs/current-langgraph-architecture.md` + Phase 50 documentation sync checklist | role-match |
| `.planning/ARCHITECTURE-DEBT.md` | config | batch | `.planning/ARCHITECTURE-DEBT.md` | exact |
| `.planning/phases/52-safety-pre-route-node/52-VALIDATION.md` | validation artifact | batch/static verification | `.planning/phases/51-canonical-graph-baseline-guardrails-and-migration-matrix/51-VALIDATION.md` + current `52-VALIDATION.md` | role-match |

## Pattern Assignments

### `src/agent/nodes/safety_pre_route.py` (component, request-response)

**Analog:** `src/agent/nodes/receive_request.py` for deterministic node/trace shape; `src/agent/nodes/classify_intent.py` and `src/agent/intent_policy.py` for existing safety logic.

**Imports pattern** (`src/agent/nodes/receive_request.py` lines 1-8):
```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.agent.intent_policy import INTENT_POLICY_REGISTRY, SLOT_POLICY_REGISTRY
from src.agent.state import AgentState
```

Use the same lightweight imports style. For the new node, prefer `PreRouteDecision`, `detect_pre_route`, and any extracted short-reply helper from `src.agent.intent_policy`; do not import LLM, repositories, services, tools, or memory modules.

**Trace append pattern** (`src/agent/nodes/receive_request.py` lines 45-61, 147-150):
```python
async def receive_request(state: AgentState) -> dict:
    """Reset per-turn state so checkpointed graph context cannot leak stale context."""
    started_at = _now_iso()
    active_flow_state = _project_active_flow_state(state)
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
```
```python
        "current_run_id": state.get("current_run_id") or str(uuid4()),
        "run_started_at": started_at,
        "trace_steps": trace_steps,
```

`safety_pre_route` should append to existing `state.get("trace_steps") or []`, not replace the `receive_request` step. Set `"node": "safety_pre_route"`, `provider_latency_ms: None`, `retry_count: 0`, and a small `metrics_json` with disposition/reason codes.

**Existing pre-route detector** (`src/agent/intent_policy.py` lines 566-622):
```python
class PreRouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: Literal["none", "approval_chat_not_trusted", "safety_sensitive", "multi_target_request"] = "none"
    requested_operation: RequestedOperationLiteral | None = None
    reason_codes: list[str] = []
    requires_clarification: bool = False
```
```python
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
```

Reuse this model/detector instead of creating a second DTO or detector.

**Short approval/action reply pattern** (`src/agent/nodes/classify_intent.py` lines 118-130, 483-503, 701-743):
```python
_SHORT_APPROVAL_OR_ACTION_REPLIES = {
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
```
```python
def _short_text_key(text: str) -> str:
    return re.sub(r"[\s。！!,.，、；;：:]+", "", text.strip()).lower()

def _is_short_approval_or_action(text: str) -> bool:
    return _short_text_key(text) in _SHORT_APPROVAL_OR_ACTION_REPLIES
```
```python
if _is_ambiguous_short_reply(user_text):
    return _short_reply_clarification_update(
        state,
        user_text,
        pre_route,
        started_at,
        _is_short_approval_or_action(user_text),
    )
```
```python
reason = "approval_chat_not_trusted" if approval_like else "unsupported_or_ambiguous"
routing_hints = {
    "requires_clarification": True,
    "clarification_reason": reason,
    "short_reply_without_active_flow": True,
}
if approval_like:
    routing_hints["pre_route_disposition"] = "approval_chat_not_trusted"
```

Phase 52 should extract only the approval/action-like short reply guard into safety. Leave pending-slot identifier and ordinary active-flow ambiguity behavior in `classify_intent` compatibility unless a plan explicitly scopes a split.

**Forbidden write pattern** (`src/agent/nodes/classify_intent.py` lines 74-87, 627-632):
```python
FORBIDDEN_STATE_WRITES = {
    "approval_result",
    "approval_revision_refs",
    "trusted_approval_result",
    "resume",
    "command",
    "extracted_slots",
    "active_slots",
    "risk_signals",
    "final_response",
    "tool_results",
    "action_result",
    "proposed_action",
}
```
```python
update["trace_steps"] = (state.get("trace_steps") or []) + [
    _trace_step_without_llm(started_at, len(str(state.get("user_query") or "")), source, reason_codes)
]
return {key: value for key, value in update.items() if key not in FORBIDDEN_STATE_WRITES}
```

For `safety_pre_route`, keep the allowed write set smaller: safety decision field, `routing_hints`, and `trace_steps`. Tests should assert no `proposed_action`, `approval_result`, `action_draft`, memory, evidence, tool, or risk/approval fields are produced.

---

### `src/agent/routing.py` (route, request-response)

**Analog:** `src/agent/routing.py`

**Imports and allowlist pattern** (lines 1-15, 21-38):
```python
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from src.agent.intent_policy import (
    INTENT_POLICY_REGISTRY,
    SLOT_POLICY_REGISTRY,
    PreRouteDecision,
    SlotInheritanceContext,
    confidence_requires_clarification,
)
from src.agent.state import AgentState
```
```python
_INVESTIGATE_ROUTES = {"final_response", "clarification_gate", "rag_context_build", "recommendation_generation"}
_RECOMMENDATION_ROUTES = {"claim_verify", "final_response"}
_RAG_CONTEXT_ROUTES = {"recommendation_generation", "clarification_gate", "final_response"}
_CLAIM_VERIFY_ROUTES = {"assess_risk_and_approval", "final_response"}
INTENT_ROUTES = {"clarification_gate", "final_response", "investigate", "session_memory_load"}
SLOT_ROUTES = {"clarification_gate", "investigate", "long_term_memory_retrieve"}
```

Add `SAFETY_ROUTES = {"classify_intent", "clarification_gate", "final_response"}` in this same style for Phase 52 compatibility.

**Fail-closed wrapper pattern** (lines 71-84):
```python
def route_after_intent(state: AgentState) -> str:
    try:
        route = _route_after_intent(state)
    except Exception:
        return "clarification_gate"
    return route if route in INTENT_ROUTES else "clarification_gate"

def route_after_slots(state: AgentState) -> str:
    try:
        route = _route_after_slots(state)
    except Exception:
        return "clarification_gate"
    return route if route in SLOT_ROUTES else "clarification_gate"
```

`route_after_safety` should follow this wrapper style, returning `clarification_gate` on exceptions or unknown route keys.

**Existing pre-route routing guard** (lines 233-255):
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
```

Move ownership of these fail-closed pre-route dispositions into `_route_after_safety`. Keep any remaining checks in `route_after_intent` only as Phase 52 compatibility until Phase 53.

---

### `src/agent/graph.py` (config, request-response)

**Analog:** `src/agent/graph.py`

**Imports pattern** (lines 23-45):
```python
from src.agent.nodes.assess_risk_and_approval import assess_risk_and_approval
from src.agent.nodes.approval_gate import approval_gate
from src.agent.nodes.action_draft import action_draft
from src.agent.nodes.classify_intent import classify_intent
from src.agent.nodes.clarification_gate import clarification_gate
from src.agent.nodes.claim_verify import claim_verify
from src.agent.nodes.extract_slots import extract_slots
from src.agent.nodes.final_response import final_response
from src.agent.nodes.generate_recommendation import generate_recommendation
from src.agent.nodes.investigate import investigate
from src.agent.nodes.long_term_memory_retrieve import long_term_memory_retrieve
from src.agent.nodes.rag_context_build import rag_context_build
from src.agent.nodes.receive_request import receive_request
from src.agent.nodes.session_memory_load import session_memory_load
from src.agent.routing import (
    route_after_claim_verify,
    route_after_intent,
    route_after_investigate,
    route_after_rag_context,
    route_after_recommendation,
    route_after_slots,
)
from src.agent.state import AgentState
```

Add `from src.agent.nodes.safety_pre_route import safety_pre_route` and `route_after_safety` in the existing grouped import style.

**Node registration and active entry path pattern** (lines 276-306):
```python
def build_graph(checkpointer: AsyncPostgresSaver):
    """Build and compile the refund agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node("receive_request", receive_request)
    builder.add_node("classify_intent", classify_intent, retry_policy=_llm_retry)
    builder.add_node("session_memory_load", session_memory_load)
```
```python
    builder.add_edge(START, "receive_request")
    builder.add_edge("receive_request", "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        route_after_intent,
        {
            "clarification_gate": "clarification_gate",
            "final_response": "final_response",
            "investigate": "investigate",
            "session_memory_load": "session_memory_load",
        },
    )
```

Phase 52 should change the entry edge to `receive_request -> safety_pre_route` and add a conditional edge map from `safety_pre_route` using `route_after_safety`. Safe compatibility may target `classify_intent`; unsafe dispositions should target `clarification_gate` or tested deterministic `final_response`.

---

### `src/agent/intent_policy.py` (utility, transform)

**Analog:** `src/agent/intent_policy.py`

**Imports pattern** (lines 1-12):
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
import re
from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict

from src.agent.schemas import IntentLiteral, RequiredSlotExpression, RequestedOperationLiteral, RiskTierLiteral
```

If short-reply helpers move out of `classify_intent`, put them here next to `PreRouteDecision` / `detect_pre_route` and keep them deterministic/pure.

**Risk policy and pre-route relationship** (lines 481-489, 959-978):
```python
ORDINARY_CHAT_CHANNELS = {"ordinary_chat", "chat", "agent_chat", "agent_runs"}
RISK_POLICY_TABLE: Mapping[tuple[str, str, str], RiskDecision] = MappingProxyType(
    {
        ("approval_decision", "*", "*"): RiskDecision(
            tier="forbidden_in_chat",
            evidence_required=False,
            approval_required=False,
            reason_codes=("approval_chat_not_trusted",),
        ),
```
```python
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
```

Do not broaden semantic unsupported handling here for Phase 52 unless a plan records a scoped MVP/spec delta.

---

### `src/agent/nodes/classify_intent.py` (component, request-response)

**Analog:** `src/agent/nodes/classify_intent.py`

**Current thick-node imports to slim** (lines 11-29):
```python
from src.agent.intent_policy import (
    ClarificationDecision,
    INTENT_POLICY_REGISTRY,
    RiskDecision,
    SLOT_POLICY_REGISTRY,
    SemanticIntent,
    PreRouteDecision,
    build_task_plan,
    decide_clarification,
    derive_keyword_signals,
    detect_pre_route,
    select_executable_prefix,
    task_plan_payload,
    task_steps_payload,
)
from src.agent.prompts import CLASSIFY_INTENT_SYSTEM
from src.agent.schemas import IntentResultV3, RequiredSlotExpression
from src.agent.routing import route_after_intent
from src.agent.state import AgentState
```

After `safety_pre_route` exists, direct `classify_intent` calls may still need compatibility, but graph runs should not rely on this file as the canonical pre-route owner.

**Classification trace compatibility pattern** (lines 442-463):
```python
classification_trace = {
    "raw_llm_classification": raw,
    "candidate_classification": raw,
    "policy_owner": "IntentPolicyRegistry",
    "pre_route_decision": pre_route.model_dump() if pre_route else None,
    "policy_overrides": policy_overrides,
    "semantic_intent": _semantic_payload(semantic),
    "risk_decision": _risk_payload(risk_decision),
    "clarification_decision": _clarification_payload(clarification_decision),
    "task_plan": task_plan_state,
    "executable_prefix": executable_prefix_ids,
    "deferred_steps": deferred_step_payloads,
    "plan_normalization": list(plan_normalization),
    "effective_classification": {
        "primary_intent": primary_intent,
        "requested_operation": requested_operation,
        "required_slots": policy_required_slots,
    },
    "risk_tier": risk_decision.tier,
    "route_decision": route_decision,
    "reason_codes": reason_codes,
}
```

Keep `classification_trace.pre_route_decision` only as a migration artifact with Phase 53 delete metadata in the plan.

**Current pre-route call site to migrate** (lines 746-777):
```python
async def classify_intent(state: AgentState) -> dict:
    started_at = _now_iso()
    user_text = state.get("user_query") or ""
    pre_route = detect_pre_route(user_text)
    context_update = _deterministic_context_update(state, user_text, pre_route, started_at)
    if context_update is not None:
        return context_update
```
```python
            update = intent_result_to_state(
                result,
                prior_llm_outputs=state.get("llm_outputs") or {},
                pre_route=pre_route,
                user_query=user_text,
                role=state.get("role"),
                channel="ordinary_chat",
            )
```

Phase 52 should stop graph runs from depending on this initial `detect_pre_route(...)` call as the canonical decision. If kept for direct unit compatibility, it should not conflict with `state["pre_route_decision"]` emitted by `safety_pre_route`.

---

### `src/agent/state.py` (model, transform)

**Analog:** `src/agent/state.py`

**Typed state field placement** (lines 55-85):
```python
class AgentState(TypedDict, total=False):
    """LangGraph state contract split into persistent and ephemeral fields."""

    # Durable graph/checkpoint context: survives across turns via the checkpointer.
    thread_id: str
    tenant_id: str
    user_id: str
    role: str
    active_slots: ActiveSlots
    active_slot_metadata: dict[str, Any] | None
    last_intent: str | None
    last_recommendation_summary: LastRecommendationSummary | None
    evidence_refs: list[EvidenceRef]
    last_business_context_refs: LastBusinessContextRefs | None

    # Ephemeral context: reset by receive_request at the start of each turn.
    user_query: str | None
    normalized_query: str | None
    current_intent: str | None
    intent_confidence: float | None
    risk_tier: str | None
    classification_trace: dict[str, Any] | None
    task_plan: dict[str, Any] | None
    deferred_steps: list[dict[str, Any]]
    target_merchant_context: dict[str, Any] | None
    active_flow_state: dict[str, Any] | None
    secondary_intents: list[str]
    required_slots: dict[str, Any]
    candidate_slots: dict[str, Any]
    routing_hints: dict[str, Any]
```

If the planner chooses a top-level state field, add `pre_route_decision: dict[str, Any] | None` near `classification_trace` / `routing_hints` and reset it in `receive_request`.

**Trace field pattern** (lines 168-175):
```python
    final_response: str | None
    tool_results: list[dict[str, Any]] | None
    llm_outputs: dict[str, Any] | None
    node_errors: list[dict[str, Any]] | None
    retry_count: int | None
    current_run_id: str | None
    run_started_at: str | None
    trace_steps: list[dict[str, Any]] | None
```

Do not model safety decision as approval/action authority; keep it a pre-route trace/routing hint.

---

### `src/agent/graph_vocabulary.py` (utility, transform)

**Analog:** `src/agent/graph_vocabulary.py`

**Vocabulary entries pattern** (lines 41-53, 98-103):
```python
_ENTRIES: tuple[GraphVocabularyEntry, ...] = (
    _entry("receive_request", "receive_request", "node", "runtime", True),
    _entry("investigate", "investigate", "node", "runtime", True),
    _entry("clarification_gate", "clarification_gate", "node", "runtime", True),
    _entry("approval_gate", "approval_gate", "node", "runtime", True),
    _entry("action_draft", "action_draft", "node", "runtime", True),
    _entry("final_response", "final_response", "node", "runtime", True),
    _entry("memory_write", "memory_write", "node", "runtime", True),
    _entry("classify_intent", "contextual_intent_resolve", "node", "compatibility_alias", True),
    _entry("intent_classification", "contextual_intent_resolve", "node", "compatibility_alias", True),
    _entry("contextual_intent_resolve", "contextual_intent_resolve", "node", "compatibility_alias", True),
    _entry("classify_intent:pre_route", "safety_pre_route", "node", "compatibility_alias", True),
    _entry("safety_pre_route", "safety_pre_route", "node", "compatibility_alias", True),
```
```python
    _entry("route_after_intent", "route_after_contextual_intent", "router", "compatibility_alias", True),
    _entry("route_after_contextual_intent", "route_after_contextual_intent", "router", "compatibility_alias", True),
    _entry("route_after_slots", "route_after_slot_resolution", "router", "compatibility_alias", True),
    _entry("route_after_slot_resolution", "route_after_slot_resolution", "router", "compatibility_alias", True),
    _entry("route_after_risk", "route_after_risk", "router", "runtime", True),
```

Phase 52 should change the real `safety_pre_route` entry to `"runtime"` and add `route_after_safety` as a runtime router if graph vocabulary tracks it.

**Trace projection pattern** (lines 129-139):
```python
def project_trace_step_for_contract(step: Mapping[str, Any]) -> dict[str, Any]:
    implementation_node = str(step.get("node") or "unknown")
    entry = graph_vocabulary_entry(implementation_node, kind="node") or graph_vocabulary_entry(
        implementation_node, kind="router"
    )
    projected = dict(step)
    projected["implementation_node"] = implementation_node
    projected["target_node"] = implementation_node if entry is None else entry.target_name
    projected["target_graph_status"] = "unknown_passthrough" if entry is None else entry.status
    projected["target_graph_runnable"] = True if entry is None else entry.runnable
    return projected
```

Tests should prove new graph traces project `safety_pre_route` as runtime, while any `classify_intent:pre_route` alias remains compatibility-only.

---

### `tests/agent/test_nodes/test_safety_pre_route.py` (test, request-response)

**Analog:** `tests/agent/test_nodes/test_receive_request.py` and `tests/agent/test_nodes/test_classify_intent.py`

**Async node test pattern** (`tests/agent/test_nodes/test_receive_request.py` lines 11-59):
```python
@pytest.mark.asyncio
async def test_receive_request_resets_ephemeral(base_state):
    state = {
        **base_state,
        "current_intent": "old_intent",
        "intent_confidence": 0.99,
        "risk_tier": "read_only",
        "classification_trace": {"old": "trace"},
        "task_plan": {"steps": [{"step_id": "s1"}], "terminal_step_id": "s1"},
        "deferred_steps": [{"step_id": "s2", "intent": "ticket_reply_draft"}],
        "target_merchant_context": {"status": "resolved", "source": "spoofed"},
        "active_flow_state": {"old": "flow"},
        "secondary_intents": ["policy_qa"],
        "required_slots": {"all_of": ["order_id"], "any_of": [], "optional": []},
        "candidate_slots": {"order_id": "ORD-OLD"},
        "routing_hints": {"pre_route_disposition": "old"},
        "clarification_request": {"reason": "old"},
        "last_business_context_refs": {"business_fact_refs": [{"resource_id": "ORD-OLD"}]},
        "business_context": {"old": "data"},
        "action_draft": {"draft_id": "old-draft"},
        "draft_outcome": {"status": "not_executed_demo"},
        "execution_mode": "demo",
        "action_result": {"status": "draft_created"},
        "trace_steps": [{"node": "old_node"}],
    }

    result = await receive_request(state)
```
```python
    assert [step["node"] for step in result["trace_steps"]] == ["receive_request"]
```

For `safety_pre_route`, use `base_state` plus `trace_steps=[{"node": "receive_request"}]`, call the node directly, and assert the trace ends with `"safety_pre_route"`.

**Safety behavior tests to move/duplicate** (`tests/agent/test_nodes/test_classify_intent.py` lines 304-345, 407-420):
```python
@pytest.mark.asyncio
async def test_approval_chat_pre_route_overrides_llm(monkeypatch, base_state):
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: FakeLLM(_intent_v3(primary_intent="policy_qa")))

    result = await classify_intent_module.classify_intent({**base_state, "user_query": "approve APR-1"})

    assert result["current_intent"] == "unsupported"
    assert result["requested_operation"] == "advise"
    assert result["risk_tier"] == "forbidden_in_chat"
    assert result["routing_hints"]["pre_route_disposition"] == "approval_chat_not_trusted"
    assert result["routing_hints"]["clarification_reason"] == "approval_chat_not_trusted"
    assert "approval_result" not in result
    assert "resume" not in result
```
```python
@pytest.mark.asyncio
async def test_short_approval_reply_without_flow_is_not_classified_by_llm(monkeypatch, base_state):
    def fail_llm():
        raise AssertionError("LLM should not be called for a standalone approval-like short reply")

    monkeypatch.setattr(classify_intent_module, "_get_llm", fail_llm)

    result = await classify_intent_module.classify_intent({**base_state, "user_query": "同意"})

    assert result["primary_intent"] == "unsupported"
    assert result["requested_operation"] == "advise"
    assert result["risk_tier"] == "forbidden_in_chat"
    assert result["routing_hints"]["clarification_reason"] == "approval_chat_not_trusted"
    assert result["classification_trace"]["route_decision"] == "clarification_gate"
```

New tests should assert no LLM seam is present/called, no memory/tool/action/approval fields are written, and safety-sensitive supported requests can continue to safe compatibility without creating action authority.

---

### `tests/agent/test_nodes/test_classify_intent.py` (test, request-response)

**Analog:** `tests/agent/test_nodes/test_classify_intent.py`

**Compatibility test pattern** (lines 182-209):
```python
def test_multi_target_request_is_neutralized_only_after_valid_task_plan():
    result = IntentResultV3.model_validate(
        _intent_v3(
            primary_intent="order_status_inquiry",
            requested_operation="read_status",
            secondary_intents=["policy_qa"],
            candidate_slots={"order_id": "ORD-001"},
        )
    )
    pre_route = PreRouteDecision(
        disposition="multi_target_request",
        reason_codes=["multi_target_request"],
        requires_clarification=True,
    )

    update = intent_result_to_state(result, pre_route=pre_route, user_query="查订单状态，同时看政策")
    trace = update["classification_trace"]
```

Keep direct `intent_result_to_state(..., pre_route=...)` coverage for compatibility. Add assertions that the new canonical graph/node tests, not classifier-only tests, own safety pre-route behavior.

**Forbidden authority assertion pattern** (lines 239-258, 261-281):
```python
for forbidden_key in ("proposed_action", "action_draft", "approval_result", "action_result"):
    assert forbidden_key not in update
```

Reuse this loop in both classifier compatibility tests and `test_safety_pre_route.py`.

---

### `tests/agent/test_graph.py` (test, request-response)

**Analog:** `tests/agent/test_graph.py`

**Imports and router key registry** (lines 15-30, 52-66):
```python
from src.agent.graph import build_graph, route_after_approval, route_after_risk
from src.agent.graph_vocabulary import target_graph_name
from src.agent.nodes import assess_risk_and_approval as assess_risk_module
from src.agent.nodes import classify_intent as classify_intent_module
from src.agent.nodes import extract_slots as extract_slots_module
from src.agent.nodes import generate_recommendation as generate_recommendation_module
from src.agent.nodes import long_term_memory_retrieve as memory_retrieve_module
from src.agent.routing import (
    route_after_claim_verify,
    route_after_intent,
    route_after_investigate,
    route_after_rag_context,
    route_after_recommendation,
    route_after_slots,
)
```
```python
ROUTER_EDGE_KEYS = {
    "route_after_intent": {"clarification_gate", "final_response", "investigate", "session_memory_load"},
    "route_after_slots": {"clarification_gate", "investigate", "long_term_memory_retrieve"},
    "route_after_risk": {"approval_gate", "final_response"},
    "route_after_approval": {"assess_risk_and_approval", "action_draft", "final_response"},
    "route_after_investigate": {
        "final_response",
        "clarification_gate",
        "rag_context_build",
        "recommendation_generation",
    },
```

Add `route_after_safety` import and `ROUTER_EDGE_KEYS["route_after_safety"] = {"classify_intent", "clarification_gate", "final_response"}`.

**Graph dependency seam** (lines 508-535):
```python
def _patch_graph_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    intent: str = "policy_qa",
    order_id: str | None = None,
    policy_status: str = "strong_evidence",
    ticket_id: str | None = None,
):
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: FakeLLM(_intent(intent)))
    monkeypatch.setattr(extract_slots_module, "_get_llm", lambda: FakeLLM(_slots(order_id)))
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_recommendation()))
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: FakeLLM(_risk()))
```

For unsafe safety graph tests, patch classifier LLM to raise or track calls when the route must fail before `classify_intent`.

**Graph compile and route coverage pattern** (lines 922-938, 1010-1057):
```python
def test_graph_compiles_with_investigate():
    graph = build_graph(MemorySaver())
    nodes = set(graph.get_graph().nodes)

    assert {
        "classify_intent",
        "investigate",
        "rag_context_build",
        "claim_verify",
        "clarification_gate",
        "session_memory_load",
        "long_term_memory_retrieve",
    } <= nodes
```
```python
def test_all_router_return_keys_have_edges():
    assert (
        route_after_intent({"primary_intent": "policy_qa", "requested_operation": "advise", "intent_confidence": 0.9})
        in ROUTER_EDGE_KEYS["route_after_intent"]
    )
```

Update compile tests to include `safety_pre_route` and assert no forbidden internal/lifecycle nodes are introduced.

**Unsafe graph fail-closed pattern** (lines 701-720, 1076-1085):
```python
nodes = [step["node"] for step in final_state["trace_steps"]]
assert planner.calls >= 1
assert [call[0] for call in deps["tool_platform"].calls] == ["search_policy"]
assert "approval_gate" not in nodes
assert "action_draft" not in nodes
assert final_state.get("proposed_action") is None
assert final_state.get("approval_result") is None
assert final_state.get("action_result") is None
```
```python
@pytest.mark.asyncio
async def test_approval_chat_routes_to_clarification_without_tools(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="policy_qa")
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(_state("approve APR-1"), _config(deps["tool_platform"], deps["events"]))

    assert deps["tool_platform"].calls == []
    assert final_state["clarification_request"]["reason"] == "approval_chat_not_trusted"
    assert "审批操作需要通过审批入口处理" in final_state["final_response"]
```

Phase 52 graph tests should add `nodes` assertions: unsafe inputs include `receive_request`, `safety_pre_route`, `clarification_gate`, `final_response`; they must not include `classify_intent`, memory nodes, `investigate`, `approval_gate`, or `action_draft`.

---

### `tests/test_graph_routing.py` (test, request-response)

**Analog:** `tests/test_graph_routing.py`

**Router imports and valid key pattern** (lines 10-23):
```python
from src.agent.graph import route_after_approval, route_after_risk
from src.agent.nodes import assess_risk_and_approval as risk_module
from src.agent.routing import route_after_investigate, route_after_recommendation

VALID_INVESTIGATE_KEYS = {"final_response", "clarification_gate", "recommendation_generation"}
ACTION_HASH = "sha256:" + "1" * 64
SNAPSHOT_HASH = "sha256:" + "2" * 64
```

Add `route_after_safety` from `src.agent.routing` and `VALID_SAFETY_KEYS = {"classify_intent", "clarification_gate", "final_response"}`.

**Fail-closed router test pattern** (lines 215-226, 278-316, 691-708):
```python
def test_route_after_risk_returns_final_response_for_policy_qa_no_action():
    state = {
        "current_intent": "policy_qa",
        "risk_assessment": {"approval_required": False},
        "proposed_action": None,
    }

    assert route_after_risk(state) == "final_response"
```
```python
@pytest.mark.parametrize(
    "missing_field",
    [
        "target_merchant_id",
        "business_fact_refs",
        "verified_evidence_refs",
        "risk_decision_ref",
        "approval_idempotency_key",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
    ],
)
def test_route_after_risk_fails_closed_when_approval_plan_binding_missing(missing_field):
    state = _risk_route_state()
    state["approval_plan"].pop(missing_field)

    assert route_after_risk(state) == "final_response"
```
```python
@pytest.mark.parametrize(
    "state",
    [
        {},
        {"primary_intent": "order_status_inquiry"},
        {"business_context": {"missing_required_facts": ["order_id"]}},
        {"business_context": {"errors": [{"error_code": "FORBIDDEN", "resource": "merchant_risk"}]}},
        {"retrieval_status": "error"},
        {"best_score": 0.1},
        {"primary_intent": 123, "business_context": "not-a-dict", "retrieval_status": object()},
    ],
)
def test_route_after_investigate_totality(state):
    assert route_after_investigate(state) in VALID_INVESTIGATE_KEYS
```

Use the same style to prove `route_after_safety` totality and fail-closed behavior for malformed/missing safety state.

---

### `tests/architecture/graph_baseline.py` (test, transform)

**Analog:** `tests/architecture/graph_baseline.py`

**Baseline constants pattern** (lines 11-48, 87-130):
```python
TARGET_CANONICAL_GRAPH_NODES = frozenset(
    {
        "receive_request",
        "safety_pre_route",
        "session_context_load",
        "contextual_intent_resolve",
        "slot_resolution_gate",
        "memory_context_load",
        "investigate",
        "rag_context_build",
        "recommendation_generation",
        "claim_verify",
        "risk_gate",
        "approval_gate",
        "action_draft",
        "clarification_gate",
        "final_response",
    }
)
```
```python
CURRENT_ACTIVE_GRAPH_NODES_BASELINE = frozenset(
    {
        "receive_request",
        "classify_intent",
        "session_memory_load",
        "extract_slots",
        "long_term_memory_retrieve",
        "investigate",
        "rag_context_build",
        "generate_recommendation",
        "claim_verify",
        "assess_risk_and_approval",
        "clarification_gate",
        "approval_gate",
        "action_draft",
        "final_response",
    }
)
```
```python
CURRENT_CONDITIONAL_EDGE_BASELINE = {
    ("classify_intent", "route_after_intent"): {
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
        "investigate": "investigate",
        "session_memory_load": "session_memory_load",
    },
```

Add `safety_pre_route` to the current active baseline and add `("safety_pre_route", "route_after_safety")` to the conditional edge baseline. Do not remove remaining legacy nodes in Phase 52.

**AST parser pattern** (lines 149-188, 377-390):
```python
def graph_add_node_names(path: Path = GRAPH_PATH) -> frozenset[str]:
    tree = ast.parse(_source(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_node"):
            continue
        if not node.args:
            raise AssertionError("Unsupported graph baseline shape: add_node without positional node name")
        names.add(_string_literal(node.args[0], context="add_node node name"))
    return frozenset(names)
```
```python
def graph_router_route_values() -> dict[str, frozenset[str]]:
    routing_router_names = {
        "route_after_intent",
        "route_after_slots",
        "route_after_investigate",
        "route_after_rag_context",
        "route_after_recommendation",
        "route_after_claim_verify",
    }
    graph_router_names = {"route_after_risk", "route_after_approval"}
```

Include `route_after_safety` in `routing_router_names` once implemented.

---

### `tests/architecture/test_canonical_graph_baseline.py` (test, transform)

**Analog:** `tests/architecture/test_canonical_graph_baseline.py`

**Active baseline and migration pattern** (lines 18-48, 95-112):
```python
def test_current_active_graph_node_set_matches_phase51_baseline() -> None:
    assert graph_add_node_names() == CURRENT_ACTIVE_GRAPH_NODES_BASELINE
```
```python
def test_migration_mode_maps_every_active_legacy_node_to_target() -> None:
    active_legacy_nodes = CURRENT_ACTIVE_GRAPH_NODES_BASELINE - TARGET_CANONICAL_GRAPH_NODES

    assert active_legacy_nodes == frozenset(MIGRATION_MODE_LEGACY_NODE_MAP)
```
```python
def test_current_router_mappings_match_source_baseline() -> None:
    assert graph_conditional_edge_mappings() == CURRENT_CONDITIONAL_EDGE_BASELINE

def test_router_return_values_are_covered_by_registered_path_maps() -> None:
    route_maps = graph_conditional_edge_mappings()
    router_routes = graph_router_route_values()
    registered_nodes = graph_add_node_names()

    assert set(router_routes) == {router for _source, router in route_maps}
```

Rename test names from Phase 51 wording if useful, but preserve the static inspection style.

**Final no-debt stays deferred** (lines 155-158):
```python
def test_final_no_debt_gate_is_marked_phase58_scope() -> None:
    pytest.skip("Phase 58 cutover enforces exact canonical graph node set; Phase 51 records the gate.")
    assert graph_add_node_names() == TARGET_CANONICAL_GRAPH_NODES
```

Keep this skipped in Phase 52. Do not enforce final exact canonical graph set yet.

---

### `tests/agent/test_graph_vocabulary.py` (test, transform)

**Analog:** `tests/agent/test_graph_vocabulary.py`

**Compatibility alias test pattern** (lines 13-28):
```python
@pytest.mark.parametrize(
    ("name", "kind", "target_name", "status", "runnable"),
    [
        ("classify_intent", "node", "contextual_intent_resolve", "compatibility_alias", True),
        ("intent_classification", "node", "contextual_intent_resolve", "compatibility_alias", True),
        ("classify_intent:pre_route", "node", "safety_pre_route", "compatibility_alias", True),
        ("session_memory_load", "node", "session_context_load", "compatibility_alias", True),
        ("session_context_load", "node", "session_context_load", "runtime", True),
        ("long_term_memory_retrieve", "node", "memory_context_load", "compatibility_alias", True),
        ("reviewed_memory_context_retrieve", "node", "memory_context_load", "runtime", True),
        ("extract_slots", "node", "slot_resolution_gate", "compatibility_alias", True),
        ("slot_resolution_gate", "node", "slot_resolution_gate", "compatibility_alias", True),
        ("route_after_intent", "router", "route_after_contextual_intent", "compatibility_alias", True),
        ("route_after_slots", "router", "route_after_slot_resolution", "compatibility_alias", True),
    ],
)
```

Move `safety_pre_route` out of compatibility-only expectations and into runtime expectations.

**Runtime projection pattern** (lines 65-90):
```python
@pytest.mark.parametrize(
    "name",
    [
        "receive_request",
        "investigate",
        "clarification_gate",
        "approval_gate",
        "action_draft",
        "final_response",
        "memory_write",
        "rag_context_build",
        "claim_verify",
    ],
)
def test_canonical_runtime_nodes_project_as_runtime(name: str) -> None:
    entry = graph_vocabulary_entry(name, kind="node")
    projected = project_trace_step_for_contract({"node": name, "status": "completed"})
```

Add `safety_pre_route` to this runtime list after graph registration.

---

### `.planning/ARCHITECTURE-DEBT.md` (config, batch)

**Analog:** `.planning/ARCHITECTURE-DEBT.md`

**Ledger write rules** (lines 1-18):
```markdown
# MOCA 架构债务 / 缺陷发现台账

> 本文件记录 MOCA 各子系统在代码走查、phase 实现、本地验证中**检测出的 bug、设计缺陷、遗留妥协**，以及**已完成的修复**。
> 与 `LOCAL-VALIDATION-ISSUES.md` 的分工：那个记「本地调试/启动/验证时踩到的具体事故」；本文件记「子系统级的架构缺陷与处理台账」，颗粒度更粗、生命周期更长。

## 写入规则

- 修改**工具调用 / RAG / 记忆 / 意图识别**这几个核心子系统时，检测出的 bug 或架构不完善点、以及做了哪些修复，**默认追加到本文件**对应子系统章节。
- 每条目尽量给：问题现象 / 根因、影响、处理状态、证据（phase / commit / 文件:行）、剩余风险。
- 只写「基于仓库真实代码、测试、planning artifact 核对过」的内容。未核实的写「未确认」，不编。
- 目标态 vs 已实现要分清：`docs/contract-spec.md` 是目标契约，不等于已实现事实。
```

**Current graph migration section to update** (lines 33-40):
```markdown
## 2026-07-06 — Phase 51 canonical graph baseline guardrails 已落地 ⚠️

- **子系统**：Agent Graph / 意图识别 / RAG / 记忆 / 风险审批主链
- **问题现象/根因**：Phase 52-58 开始 rewiring 前，需要先把当前源码 graph、目标 15-node graph、迁移期 legacy alias、router route map 和 forbidden registered-node drift 变成机器可验证 guardrails。
...
- **处理状态**：⚠️已完成 Phase 51 guardrail/matrix 覆盖，但 runtime 迁移未完成。
```

Append a Phase 52 update in Chinese by default. It should distinguish implemented `safety_pre_route` runtime facts from remaining Phase 53 `classify_intent` compatibility.

**Evidence/validation style** (lines 905-920):
```markdown
**证据**
- Phase / plans：`49-01`、`49-02`、`49-03`、`49-04`
- 实现文件：`src/agent/nodes/investigate.py`、`src/agent/nodes/investigate_planner.py`、`src/tools/projection.py`、`src/tools/executors/knowledge.py`、`src/agent/events.py`、`src/replay/decision_events.py`
- 测试文件：`tests/agent/test_nodes/test_investigate.py`、`tests/agent/test_graph.py`、`tests/tools/test_tool_platform.py`、`tests/replay/test_operation_pairing.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_nodes/test_investigate.py -q` → `81 passed, 25 warnings`
```

Use only `uv run pytest ...` / `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` commands in ledger validation.

### `docs/current-langgraph-architecture.md` (documentation, batch/static verification)

**Analog:** current `docs/current-langgraph-architecture.md` source-snapshot style plus Phase 50 SPEC documentation sync checklist.

**Current-source boundary pattern** (`docs/current-langgraph-architecture.md` lines 1-5):
```markdown
# 当前 LangGraph Graph/Node 架构图

> 本图只根据当前仓库源码绘制，主要依据 `src/agent/graph.py` 的 `build_graph()` 节点/边定义，以及 `src/agent/routing.py` 和 `src/agent/graph.py` 中的条件路由函数。未把 planning 文档、README 描述或测试断言当作已实现事实。
```

**Phase 50 documentation sync checklist** (`50-SPEC.md` lines 253-266):
```markdown
Any downstream phase that changes graph semantics must check whether each file below needs an update:

- `docs/current-langgraph-architecture.md`
- `.planning/ARCHITECTURE-DEBT.md`
- Current phase `PLAN.md`, `SUMMARY.md`, `VALIDATION.md`, and review artifacts
```

Apply this by updating `docs/current-langgraph-architecture.md` only as a current-source snapshot after graph wiring changes. It should show `receive_request -> safety_pre_route -> classify_intent` as Phase 52 transitional current behavior, and keep target/final canonical claims out of this file unless they are clearly labeled as target references.

### `.planning/phases/52-safety-pre-route-node/52-VALIDATION.md` (validation artifact, batch/static verification)

**Analog:** Phase 51 `51-VALIDATION.md` closeout pattern plus the current Phase 52 validation map.

**Closeout pattern** (`51-03-PLAN.md` lines 144-170):
```markdown
Update `51-VALIDATION.md` after Plan 51-02 tests pass.

Set `wave_0_complete: true` ... only after ... tests exist.
Add a Validation Sign-Off section recording exact command results ...
```

Apply this to Phase 52 by changing `52-VALIDATION.md` from draft to complete only after the focused pytest suite, Ruff, bare-pytest scan, and `git diff --check` pass through approved MOCA entrypoints. The artifact must preserve per-task rows for pre/post parity, negative controls, static graph guardrails, fail-closed router behavior, no authority fields, and no memory/tool/approval/action side effects.

## Shared Patterns

### Deterministic Node Trace
**Source:** `src/agent/nodes/receive_request.py` lines 45-61 and `src/agent/nodes/clarification_gate.py` lines 17-46  
**Apply to:** `src/agent/nodes/safety_pre_route.py`, graph tests
```python
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
```

### Fail-Closed Safety Clarification
**Source:** `src/agent/nodes/clarification_gate.py` lines 54-68, 88-97, 126-131  
**Apply to:** `route_after_safety`, safety node tests, graph tests
```python
if routing_hints.get("pre_route_disposition") == "approval_chat_not_trusted":
    return "approval_chat_not_trusted"
```
```python
if reason == "approval_chat_not_trusted":
    return ["审批操作需要通过审批入口处理。请说明你想查询的业务问题或提供需要补充的信息。"]
```
```python
if reason == "approval_chat_not_trusted":
    return ["investigate", "action_draft", "approval_gate", "execute_action"]
```

### Router Allowlist Totality
**Source:** `src/agent/routing.py` lines 71-84 and `tests/architecture/test_canonical_graph_baseline.py` lines 99-112  
**Apply to:** `route_after_safety`, graph baseline tests, graph routing tests
```python
try:
    route = _route_after_intent(state)
except Exception:
    return "clarification_gate"
return route if route in INTENT_ROUTES else "clarification_gate"
```
```python
assert set(router_routes) == {router for _source, router in route_maps}
for source, router in route_maps:
    path_map = route_maps[(source, router)]
    assert source in registered_nodes, (source, router)
    assert path_map, (source, router)
    assert set(path_map.values()) <= registered_nodes, (source, router)
    assert router_routes[router], router
    assert router_routes[router] <= frozenset(path_map), router
```

### No Authority Fields From Pre-route
**Source:** `tests/agent/test_nodes/test_classify_intent.py` lines 257-258, 344-345; `src/agent/nodes/classify_intent.py` lines 74-87  
**Apply to:** safety node tests, graph unsafe-path tests
```python
for forbidden_key in ("proposed_action", "action_draft", "approval_result", "action_result"):
    assert forbidden_key not in result
```

### Static Architecture Guardrails
**Source:** `tests/architecture/graph_baseline.py` lines 149-188 and 377-390  
**Apply to:** Phase 52 graph baseline updates
```python
def graph_conditional_edge_mappings(path: Path = GRAPH_PATH) -> dict[tuple[str, str], dict[str, str]]:
    tree = ast.parse(_source(path))
    mappings: dict[tuple[str, str], dict[str, str]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_conditional_edges"
        ):
            continue
```

### Approved Verification Commands
**Source:** `AGENTS.md` and `.planning/phases/52-safety-pre-route-node/52-RESEARCH.md`  
**Apply to:** all PLAN.md acceptance criteria and ledger validation
```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/graph.py src/agent/routing.py src/agent/intent_policy.py src/agent/nodes/classify_intent.py src/agent/nodes/safety_pre_route.py tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/test_graph_routing.py
```

## No Analog Found

None. The new `safety_pre_route` node has no exact existing file, but strong local role/behavior analogs exist in `receive_request.py`, `classify_intent.py`, `intent_policy.py`, `routing.py`, and their tests.

## Metadata

**Analog search scope:** `src/agent`, `src/agent/nodes`, `tests/agent`, `tests/agent/test_nodes`, `tests/architecture`, `tests/test_graph_routing.py`, `.planning/ARCHITECTURE-DEBT.md`
**Files scanned:** 20 targeted files plus `rg` searches over source/test planning references
**Pattern extraction date:** 2026-07-06
