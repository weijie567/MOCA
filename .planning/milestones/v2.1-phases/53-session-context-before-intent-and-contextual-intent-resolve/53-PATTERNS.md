# Phase 53: Session Context Before Intent and Contextual Intent Resolve - Pattern Map

**Mapped:** 2026-07-06
**Files analyzed:** 21
**Analogs found:** 21 / 21

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/nodes/contextual_intent_resolve.py` | service (LangGraph node) | event-driven transform | `src/agent/nodes/classify_intent.py` | role-match |
| `src/agent/nodes/classify_intent.py` | service/helper compatibility | event-driven transform | `src/agent/nodes/session_memory_load.py` for wrapper pattern; current `classify_intent.py` for helper extraction | role-match |
| `src/agent/nodes/session_memory_load.py` | service compatibility wrapper | event-driven transform | `src/agent/nodes/session_memory_load.py` | exact |
| `src/agent/routing.py` | route | request-response transform | `src/agent/routing.py` | exact |
| `src/agent/intent_policy.py` | service/config | transform | `src/agent/intent_policy.py` | exact |
| `src/agent/graph.py` | config/route | event-driven graph assembly | `src/agent/graph.py` | exact |
| `src/agent/graph_vocabulary.py` | utility/config | transform | `src/agent/graph_vocabulary.py` | exact |
| `src/api/routers/agent_runs.py` | controller | streaming | `src/api/routers/agent_runs.py` | exact |
| `tests/agent/test_nodes/test_contextual_intent_resolve.py` | test | event-driven node/unit | `tests/agent/test_nodes/test_classify_intent.py` | role-match |
| `tests/agent/test_nodes/test_classify_intent.py` | test | event-driven node/unit | `tests/agent/test_nodes/test_classify_intent.py` | exact |
| `tests/test_graph_routing.py` | test | request-response route/unit | `tests/test_graph_routing.py` | exact |
| `tests/agent/test_intent_routing.py` | test | request-response route/unit | `tests/agent/test_intent_routing.py` | exact |
| `tests/agent/test_intent_policy_registry.py` | test | transform/config | `tests/agent/test_intent_policy_registry.py` | exact |
| `tests/architecture/graph_baseline.py` | test utility | static analysis transform | `tests/architecture/graph_baseline.py` | exact |
| `tests/architecture/test_canonical_graph_baseline.py` | test | static analysis transform | `tests/architecture/test_canonical_graph_baseline.py` | exact |
| `tests/agent/test_graph_vocabulary.py` | test | transform/static | `tests/agent/test_graph_vocabulary.py` | exact |
| `tests/agent/test_graph.py` | test | event-driven graph integration | `tests/agent/test_graph.py` | exact |
| `tests/agent/test_session_memory_load.py` | test | event-driven node/unit | `tests/agent/test_session_memory_load.py` | exact |
| `tests/agent/test_session_memory_integration.py` | test | event-driven integration + DB I/O | `tests/agent/test_session_memory_integration.py` | exact |
| `docs/current-langgraph-architecture.md` | documentation | source-fact snapshot | `docs/current-langgraph-architecture.md` | exact |
| `.planning/ARCHITECTURE-DEBT.md` | documentation/ledger | append-only decision log | `.planning/ARCHITECTURE-DEBT.md` | exact |

## Pattern Assignments

### `src/agent/nodes/contextual_intent_resolve.py` (service/LangGraph node, event-driven transform)

**Analog:** `src/agent/nodes/classify_intent.py`

**Imports pattern** (lines 1-31):
```python
from __future__ import annotations

import time
import re
from datetime import UTC, datetime
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

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
    is_ambiguous_short_reply,
    is_short_approval_or_action_reply,
    select_executable_prefix,
    task_plan_payload,
    task_steps_payload,
)
from src.agent.prompts import CLASSIFY_INTENT_SYSTEM
from src.agent.schemas import IntentResultV3, RequiredSlotExpression
from src.agent.routing import route_after_intent
from src.agent.state import AgentState
from src.config import settings
```

**Required Phase 53 adaptation:** keep this import style and local helper structure, but import/use `route_after_contextual_intent` instead of `route_after_intent` if a canonical router is introduced. If the prompt constant remains named `CLASSIFY_INTENT_SYSTEM`, ledger that as helper compatibility or rename only if the blast radius is small.

**Forbidden state write guard** (lines 76-89):
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

**Explicit AgentState adapter pattern** (lines 390-443):
```python
update = {
    "primary_intent": primary_intent,
    "requested_operation": requested_operation,
    "intent_confidence": result.confidence,
    "risk_tier": risk_decision.tier,
    "task_plan": task_plan_state,
    "deferred_steps": deferred_step_payloads,
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
llm_outputs = {
    **(prior_llm_outputs or {}),
    "intent_classification": {
        "raw": raw,
        "classification_trace": classification_trace,
        "eval_metadata": {
            "calibrated_confidence": result.calibrated_confidence,
            "classifier_version": result.classifier_version,
            "calibration_version": result.calibration_version,
            "reason_codes": reason_codes,
            "llm_required_slots": raw.get("required_slots"),
        },
    },
}
update["classification_trace"] = classification_trace
update["llm_outputs"] = llm_outputs
return {key: value for key, value in update.items() if key not in FORBIDDEN_STATE_WRITES}
```

**Required Phase 53 adaptation:** do not wholesale merge `IntentResultV3` into state. Copy this adapter shape, but make the active owner canonical:
- use canonical `llm_outputs["contextual_intent_resolve"]`;
- remove `classification_trace["pre_route_decision"]` from canonical contextual intent traces;
- compute `route_decision` with the deterministic contextual router;
- keep `candidate_slots` candidate-only and do not write `extracted_slots`, `active_slots`, memory, tool, approval, action, evidence, or final response authority fields.

**Deterministic short-reply pattern** (lines 584-620):
```python
def _deterministic_context_update(
    state: AgentState,
    user_text: str,
    pre_route: PreRouteDecision,
    started_at: str,
) -> dict[str, Any] | None:
    flow = state.get("active_flow_state") if isinstance(state.get("active_flow_state"), dict) else None
    if flow and flow.get("kind") == "pending_required_slot":
        primary_intent = str(flow.get("last_effective_intent") or "unsupported")
        requested_operation = str(flow.get("last_requested_operation") or "advise")
        required_slots = _required_slots_from_flow(flow, primary_intent)
        candidate_slots = flow.get("candidate_slots") if isinstance(flow.get("candidate_slots"), dict) else {}
        if _is_identifier_like_answer(user_text):
            reason_codes = ["active_flow_pending_slot_answered"]
            return _deterministic_classification_update(
                state,
                started_at=started_at,
                pre_route=pre_route,
                primary_intent=primary_intent,
                requested_operation=requested_operation,
                intent_confidence=1.0,
                required_slots=required_slots,
                candidate_slots=candidate_slots,
                routing_hints={
                    "workflow_state_resolution": "answered_pending_required_slot",
                    "clarification_request_id": flow.get("clarification_request_id"),
                },
                policy_overrides=[
                    {
                        "source": "active_flow_state",
                        "reason_codes": reason_codes,
                        "clarification_request_id": flow.get("clarification_request_id"),
                    }
                ],
                reason_codes=reason_codes,
                source="active_flow_state",
            )
```

**LLM structured-output node pattern** (lines 695-736):
```python
async def classify_intent(state: AgentState) -> dict:
    started_at = _now_iso()
    user_text = state.get("user_query") or ""
    pre_route = detect_pre_route(user_text)
    context_update = _deterministic_context_update(state, user_text, pre_route, started_at)
    if context_update is not None:
        return context_update
    messages: list[dict[str, str]] = [
        {"role": "system", "content": CLASSIFY_INTENT_SYSTEM},
        {"role": "user", "content": user_text},
    ]
    structured_llm = _get_llm().with_structured_output(IntentResultV3)
    last_error: str | None = None
    provider_latency_ms: int | None = None
    retry_count = 0

    # retry_count records this node's manual structured-output retry loop, not LangGraph node retries.
    for attempt in range(2):
        retry_count = attempt
        try:
            t0 = time.perf_counter()
            result = await structured_llm.ainvoke(messages)
            provider_latency_ms = round((time.perf_counter() - t0) * 1000)
            update = intent_result_to_state(
                result,
                prior_llm_outputs=state.get("llm_outputs") or {},
                pre_route=pre_route,
                user_query=user_text,
                role=state.get("role"),
                channel="ordinary_chat",
            )
            update["trace_steps"] = (state.get("trace_steps") or []) + [
                _trace_step(
                    "classify_intent",
                    "completed",
                    started_at,
                    provider_latency_ms,
                    retry_count,
                    len(str(messages)),
                )
            ]
            return update
```

**Required Phase 53 adaptation:** active function name and trace step must be `contextual_intent_resolve`; the node should read already-loaded same-thread context from state if needed, but must not load long-term/case memory, RAG, approval, action, or tools.

---

### `src/agent/nodes/classify_intent.py` (service/helper compatibility, event-driven transform)

**Analog:** current `src/agent/nodes/classify_intent.py`; wrapper analog `src/agent/nodes/session_memory_load.py`

**Compatibility wrapper pattern** (`src/agent/nodes/session_memory_load.py`, lines 16-29):
```python
async def session_memory_load(state: AgentState, config: RunnableConfig) -> dict:
    """Compatibility wrapper for the target session_context_load node."""
    return await session_context_load(
        state,
        config,
        node_name="session_memory_load",
        settings_obj=settings,
        memory_service_cls=MemoryService,
        session_memory_repository_cls=SessionMemoryRepository,
        session_memory_bundle_service_cls=SessionMemoryBundleService,
        conversation_repository_cls=ConversationRepository,
        conversation_service_cls=ConversationService,
        memory_context_service_cls=MemoryContextService,
    )
```

**Apply to:** if `classify_intent.py` remains importable, make it helper/compat-only and ledger it. Do not leave `classify_intent` as an active `build_graph()` node or route destination.

**Helper extraction guard** (`src/agent/nodes/classify_intent.py`, lines 441-443):
```python
update["classification_trace"] = classification_trace
update["llm_outputs"] = llm_outputs
return {key: value for key, value in update.items() if key not in FORBIDDEN_STATE_WRITES}
```

**Required Phase 53 adaptation:** any shared helper extracted from this file must preserve the filtered-update contract and must not preserve classifier-owned `pre_route_decision` in canonical contextual traces.

---

### `src/agent/nodes/session_memory_load.py` (service compatibility wrapper, event-driven transform)

**Analog:** `src/agent/nodes/session_memory_load.py`

**Wrapper pattern** (lines 16-29):
```python
async def session_memory_load(state: AgentState, config: RunnableConfig) -> dict:
    """Compatibility wrapper for the target session_context_load node."""
    return await session_context_load(
        state,
        config,
        node_name="session_memory_load",
        settings_obj=settings,
        memory_service_cls=MemoryService,
        session_memory_repository_cls=SessionMemoryRepository,
        session_memory_bundle_service_cls=SessionMemoryBundleService,
        conversation_repository_cls=ConversationRepository,
        conversation_service_cls=ConversationService,
        memory_context_service_cls=MemoryContextService,
    )
```

**Apply to:** retain only for import/test compatibility if needed. It must not be registered in `src/agent/graph.py` after Phase 53. Any retained wrapper needs a compatibility ledger row with owner, reason, validation, and delete phase.

---

### `src/agent/routing.py` (route, request-response transform)

**Analog:** `src/agent/routing.py`

**Route allowlist and fail-closed wrapper pattern** (lines 37-85):
```python
SAFETY_ROUTES = {"classify_intent", "clarification_gate", "final_response"}
INTENT_ROUTES = {"clarification_gate", "final_response", "investigate", "session_memory_load"}
SLOT_ROUTES = {"clarification_gate", "investigate", "long_term_memory_retrieve"}

def route_after_intent(state: AgentState) -> str:
    try:
        route = _route_after_intent(state)
    except Exception:
        return "clarification_gate"
    return route if route in INTENT_ROUTES else "clarification_gate"

def route_after_safety(state: AgentState) -> str:
    try:
        route = _route_after_safety(state)
    except Exception:
        return "clarification_gate"
    return route if route in SAFETY_ROUTES else "clarification_gate"
```

**Safety continuation pattern to change** (lines 192-213):
```python
def _route_after_safety(state: AgentState) -> str:
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    raw_pre_route = state.get("pre_route_decision")
    if hasattr(raw_pre_route, "model_dump"):
        raw_pre_route = raw_pre_route.model_dump(mode="python")
    pre_route = raw_pre_route if isinstance(raw_pre_route, dict) else {}
    disposition = pre_route.get("disposition") or routing_hints.get("pre_route_disposition") or "none"
    requires_clarification = bool(pre_route.get("requires_clarification")) or (
        routing_hints.get("requires_clarification") is True
    )

    if state.get("requested_operation") == "approval_decision":
        return "clarification_gate"
    if disposition in {"approval_chat_not_trusted", "multi_target_request"}:
        return "clarification_gate"
    if routing_hints.get("clarification_reason") == "approval_chat_not_trusted":
        return "clarification_gate"
    if requires_clarification:
        return "clarification_gate"
    if disposition in {"none", "safety_sensitive"}:
        return "classify_intent"
    return "clarification_gate"
```

**Intent route pattern to canonicalize** (lines 266-297):
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
    pre_route = PreRouteDecision(
        disposition=routing_hints.get("pre_route_disposition", "none")
        if routing_hints.get("pre_route_disposition")
        in {"none", "approval_chat_not_trusted", "safety_sensitive", "multi_target_request"}
        else "none",
        requested_operation=requested_operation
        if requested_operation in {"read_status", "advise", "draft_reply", "draft_action", "execute_action", "escalate"}
        else None,
        reason_codes=[],
        requires_clarification=bool(routing_hints.get("requires_clarification")),
    )
    if confidence_requires_clarification(intent, requested_operation, state.get("intent_confidence"), pre_route):
        return "clarification_gate"
    if INTENT_POLICY_REGISTRY.is_direct_response_intent(intent):
        return "final_response"
    route = INTENT_POLICY_REGISTRY.route_for_intent(intent)
    if route is None:
        return "clarification_gate"
    policy = SLOT_POLICY_REGISTRY.required_slots_for(intent)
    if not policy.all_of and not policy.any_of:
        return route
    return route
```

**Required Phase 53 adaptation:** update `SAFETY_ROUTES` and `_route_after_safety()` so safe / `safety_sensitive` continue to `session_context_load`. Introduce or rename `route_after_contextual_intent` with allowlist values `clarification_gate`, `final_response`, `investigate`, and `extract_slots`; do not allow active `session_memory_load`. Preserve exception-to-`clarification_gate` fail-closed behavior.

---

### `src/agent/intent_policy.py` (service/config, transform)

**Analog:** `src/agent/intent_policy.py`

**Route literal and intent definition pattern** (lines 15-24):
```python
IntentRouteLiteral = Literal["investigate", "session_memory_load", "final_response"]

@dataclass(frozen=True)
class IntentDefinition:
    name: IntentLiteral
    required_slots: RequiredSlotExpression
    initial_route: IntentRouteLiteral
    precedence: int
```

**Slot-bearing route values to update or translate** (lines 141-188):
```python
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
...
"action_request": IntentDefinition(
    name="action_request",
    required_slots=RequiredSlotExpression(all_of=["action_type"], any_of=[["order_id", "refund_case_id"]]),
    initial_route="session_memory_load",
```

**Slot metadata validation pattern to preserve** (lines 392-424):
```python
def accepts_inherited_slot(
    self,
    slot: str,
    metadata: Mapping[str, Any] | None,
    context: SlotInheritanceContext,
    *,
    invalidation: Mapping[str, Any] | None = None,
) -> SlotInheritanceDecision:
    del slot
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
    if _slot_metadata_is_intent_compatible(metadata, context.intent):
        return SlotInheritanceDecision(True, "accepted", source)
    return SlotInheritanceDecision(False, "intent_incompatible", source)
```

**Required Phase 53 adaptation:** slot-bearing `initial_route` values need to become `extract_slots` or be translated by `route_after_contextual_intent`; changing only `graph.py` leaves deterministic policy returning a removed node. Do not implement Phase 54 slot provenance/freshness cutover here.

---

### `src/agent/graph.py` (config/route, event-driven graph assembly)

**Analog:** `src/agent/graph.py`

**Imports pattern** (lines 23-46):
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
from src.agent.nodes.safety_pre_route import safety_pre_route
from src.agent.nodes.session_memory_load import session_memory_load
from src.agent.routing import (
    route_after_claim_verify,
    route_after_intent,
    route_after_investigate,
    route_after_rag_context,
    route_after_recommendation,
    route_after_safety,
    route_after_slots,
)
```

**Active graph wiring pattern** (lines 278-319):
```python
def build_graph(checkpointer: AsyncPostgresSaver):
    """Build and compile the refund agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node("receive_request", receive_request)
    builder.add_node("safety_pre_route", safety_pre_route)
    builder.add_node("classify_intent", classify_intent, retry_policy=_llm_retry)
    builder.add_node("session_memory_load", session_memory_load)
    builder.add_node("extract_slots", extract_slots, retry_policy=_llm_retry)
    ...
    builder.add_edge(START, "receive_request")
    builder.add_edge("receive_request", "safety_pre_route")
    builder.add_conditional_edges(
        "safety_pre_route",
        route_after_safety,
        {
            "classify_intent": "classify_intent",
            "clarification_gate": "clarification_gate",
            "final_response": "final_response",
        },
    )
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
    builder.add_edge("session_memory_load", "extract_slots")
```

**Required Phase 53 adaptation:** register `session_context_load` and `contextual_intent_resolve`, not active `session_memory_load` / `classify_intent`. Wire `safety_pre_route` conditional map to `session_context_load`, fixed edge `session_context_load -> contextual_intent_resolve`, and `contextual_intent_resolve` conditional map through `route_after_contextual_intent` with slot-required paths to `extract_slots`. Keep `extract_slots` active because Phase 54 owns `slot_resolution_gate`.

---

### `src/agent/graph_vocabulary.py` (utility/config, transform)

**Analog:** `src/agent/graph_vocabulary.py`

**Vocabulary entry pattern** (lines 41-55):
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
    _entry("safety_pre_route", "safety_pre_route", "node", "runtime", True),
    _entry("session_memory_load", "session_context_load", "node", "compatibility_alias", True),
    _entry("session_context_load", "session_context_load", "node", "runtime", True),
```

**Router vocabulary pattern** (lines 98-101):
```python
_entry("route_after_intent", "route_after_contextual_intent", "router", "compatibility_alias", True),
_entry("route_after_contextual_intent", "route_after_contextual_intent", "router", "compatibility_alias", True),
_entry("route_after_slots", "route_after_slot_resolution", "router", "compatibility_alias", True),
_entry("route_after_slot_resolution", "route_after_slot_resolution", "router", "compatibility_alias", True),
```

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

**Required Phase 53 adaptation:** `contextual_intent_resolve` and `route_after_contextual_intent` become `runtime`; `classify_intent`, `intent_classification`, and `session_memory_load` remain compatibility aliases only if ledgered. Keep `extract_slots` as compatibility alias until Phase 54.

---

### `src/api/routers/agent_runs.py` (controller, streaming)

**Analog:** `src/api/routers/agent_runs.py`

**Node message label pattern** (lines 56-66):
```python
NODE_MESSAGES: dict[str, str] = {
    "receive_request": "正在接收请求",
    "classify_intent": "正在识别意图",
    "extract_slots": "正在提取关键信息",
    "investigate": "正在调查订单和规则",
    "generate_recommendation": "正在生成处理建议",
    "assess_risk_and_approval": "正在评估风险",
    "approval_gate": "需要审批，等待人工决策",
    "execute_action": "正在执行操作",
    "final_response": "已完成",
}
```

**Streaming lookup pattern** (lines 336-338 and 484-486):
```python
step_index += 1
message = NODE_MESSAGES.get(node_name, f"正在执行 {node_name}")
payload = _extract_step_payload(node_name, update)
```

```python
event_kind, _node_key, node_name, step_index, update = parsed
last_step_index = max(last_step_index, step_index)
message = NODE_MESSAGES.get(node_name, f"正在执行 {node_name}")
```

**Apply to:** if API stream labels are updated in Phase 53, add a canonical `contextual_intent_resolve` label and optionally `session_context_load`. Do not rely on this file as graph authority; it is presentation-only.

---

### `tests/agent/test_nodes/test_contextual_intent_resolve.py` (test, event-driven node/unit)

**Analog:** `tests/agent/test_nodes/test_classify_intent.py`

**Fake LLM pattern** (`tests/agent/conftest.py`, lines 11-35):
```python
class FakeLLM:
    """Deterministic fake LLM for CI. Returns predetermined structured outputs.
    Implements the ChatOpenAI interface used by nodes (ainvoke + with_structured_output).
    Per D-11b: CI must not depend on real LLM API.
    """

    def __init__(self, response_dict: dict[str, Any]):
        """response_dict: maps to a dict that will be returned as structured output."""
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
```

**Node success + monkeypatch pattern** (`tests/agent/test_nodes/test_classify_intent.py`, lines 33-65):
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
    assert result["classification_trace"]["candidate_classification"]["primary_intent"] == "refund_troubleshooting"
    assert result["classification_trace"]["policy_owner"] == "IntentPolicyRegistry"
    assert result["classification_trace"]["effective_classification"]["primary_intent"] == "refund_troubleshooting"
    assert result["classification_trace"]["route_decision"] == "session_memory_load"
    ...
    assert (
        result["llm_outputs"]["intent_classification"]["classification_trace"]
        == result["classification_trace"]
    )
```

**Forbidden schema/state pattern** (lines 87-89 and 260-281):
```python
def test_intent_result_v3_rejects_approval_result_extra_field():
    with pytest.raises(ValidationError):
        IntentResultV3.model_validate(_intent_v3(approval_result={"decision": "approve"}))
```

```python
for forbidden_key in ("proposed_action", "action_draft", "approval_result", "action_result"):
    assert forbidden_key not in update
```

**Pending-slot no-LLM pattern** (lines 348-377):
```python
@pytest.mark.asyncio
async def test_pending_required_slot_identifier_reply_uses_active_flow_state(monkeypatch, base_state):
    def fail_llm():
        raise AssertionError("LLM should not be called for a pending slot identifier reply")

    monkeypatch.setattr(classify_intent_module, "_get_llm", fail_llm)
    state = {
        **base_state,
        "user_query": "OD-12345",
        "active_flow_state": {
            "kind": "pending_required_slot",
            "last_effective_intent": "refund_troubleshooting",
            "last_requested_operation": "read_status",
            "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
            "candidate_slots": {},
            "clarification_request_id": "clarify_run-001",
        },
    }

    result = await classify_intent_module.classify_intent(state)

    assert result["primary_intent"] == "refund_troubleshooting"
    assert result["requested_operation"] == "read_status"
    assert result["intent_confidence"] == 1.0
    assert result["risk_tier"] == "read_only"
    assert result["routing_hints"]["workflow_state_resolution"] == "answered_pending_required_slot"
    assert result["classification_trace"]["raw_llm_classification"] is None
    assert result["classification_trace"]["route_decision"] == "session_memory_load"
    assert result["classification_trace"]["policy_overrides"][0]["source"] == "active_flow_state"
```

**Required Phase 53 tests:** assert canonical node name in trace, `llm_outputs["contextual_intent_resolve"]`, no `classification_trace.pre_route_decision`, route decision `extract_slots` for slot-required paths, no forbidden authority writes, and deterministic pending-slot reply without LLM/tool/memory calls.

---

### `tests/agent/test_nodes/test_classify_intent.py` (test, event-driven node/unit)

**Analog:** `tests/agent/test_nodes/test_classify_intent.py`

**Apply to:** if the file is renamed, move tests into `test_contextual_intent_resolve.py`; if retained, convert it to compatibility/helper tests only. Existing assertions expecting `session_memory_load`, `classify_intent`, `intent_classification`, or `classification_trace.pre_route_decision` are Phase 52 compatibility facts and should not remain as active canonical expectations after Phase 53.

**Concrete old expectations to update** (lines 44-64 and 337-342):
```python
assert result["classification_trace"]["raw_llm_classification"]["primary_intent"] == "refund_troubleshooting"
assert result["classification_trace"]["candidate_classification"]["primary_intent"] == "refund_troubleshooting"
assert result["classification_trace"]["policy_owner"] == "IntentPolicyRegistry"
assert result["classification_trace"]["effective_classification"]["primary_intent"] == "refund_troubleshooting"
assert result["classification_trace"]["route_decision"] == "session_memory_load"
...
assert (
    result["llm_outputs"]["intent_classification"]["classification_trace"]
    == result["classification_trace"]
)
```

```python
assert result["primary_intent"] == "action_request"
assert result["requested_operation"] == "execute_action"
assert result["risk_tier"] == "approval_required"
assert result["routing_hints"]["pre_route_disposition"] == "safety_sensitive"
assert result["classification_trace"]["pre_route_decision"]["disposition"] == "safety_sensitive"
assert result["classification_trace"]["executable_prefix"] == []
```

---

### `tests/test_graph_routing.py` (test, request-response route/unit)

**Analog:** `tests/test_graph_routing.py`

**Parametrized safety routing pattern** (lines 260-305):
```python
@pytest.mark.parametrize(
    "state",
    [
        {"pre_route_decision": {"disposition": "none"}, "routing_hints": {}},
        {
            "pre_route_decision": {
                "disposition": "safety_sensitive",
                "requested_operation": "execute_action",
                "reason_codes": ["critical_write"],
                "requires_clarification": False,
            },
            "routing_hints": {"pre_route_disposition": "safety_sensitive"},
        },
    ],
)
def test_route_after_safety_continues_safe_phase52_compatibility_to_classify_intent(state):
    assert route_after_safety(state) == "classify_intent"

@pytest.mark.parametrize(
    "state",
    [
        {"pre_route_decision": {"disposition": "approval_chat_not_trusted", ...}},
        {"pre_route_decision": {"disposition": "multi_target_request", ...}},
        {"routing_hints": {"pre_route_disposition": "approval_chat_not_trusted"}},
        {"routing_hints": {"clarification_reason": "approval_chat_not_trusted"}},
        {"routing_hints": {"requires_clarification": True}},
        {"requested_operation": "approval_decision"},
    ],
)
def test_route_after_safety_fails_closed_for_unsafe_or_clarifying_dispositions(state):
    assert route_after_safety(state) == "clarification_gate"
```

**Fail-closed monkeypatch pattern** (lines 308-316):
```python
def test_route_after_safety_fails_closed_for_exceptions_or_unregistered_route(monkeypatch):
    monkeypatch.setattr(routing_module, "_route_after_safety", lambda _state: "session_context_load")
    assert route_after_safety({}) == "clarification_gate"

    def raise_error(_state):
        raise RuntimeError("bad safety state")

    monkeypatch.setattr(routing_module, "_route_after_safety", raise_error)
    assert route_after_safety({}) == "clarification_gate"
```

**Required Phase 53 adaptation:** old test name and expectation should change to `session_context_load`; the unregistered-route monkeypatch should use a truly unregistered value after the allowlist changes. Add `route_after_contextual_intent` tests for direct/final, clarify, investigate, slot-required to `extract_slots`, registry exception, and no `session_memory_load`.

---

### `tests/agent/test_intent_routing.py` (test, request-response route/unit)

**Analog:** `tests/agent/test_intent_routing.py`

**Import and route constant pattern** (lines 30-32):
```python
from src.agent.nodes import classify_intent as classify_intent_module
from src.agent.nodes.classify_intent import intent_result_to_state
from src.agent.routing import INTENT_ROUTES, SLOT_ROUTES, resolve_slots_with_metadata, route_after_intent, route_after_slots
```

**Old slot-required route expectations to update** (lines 208-216 and 453-459):
```python
update = intent_result_to_state(result, user_query="那这个订单下一步应该怎么处理？")

assert update["primary_intent"] == "refund_troubleshooting"
assert update["requested_operation"] == "read_status"
assert update["required_slots"] == {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []}
assert (
    "next_step_advice_normalized" in update["llm_outputs"]["intent_classification"]["eval_metadata"]["reason_codes"]
)
assert route_after_intent(update) == "session_memory_load"
```

```python
update = intent_result_to_state(result, pre_route=pre_route, user_query="TKT-6001要不要转主管")

assert update["primary_intent"] == "complaint_escalation"
assert update["requested_operation"] == "escalate"
assert update["risk_tier"] == "approval_required"
assert update["required_slots"]["any_of"] == [["ticket_id", "order_id", "merchant_id"]]
assert route_after_intent(update) == "session_memory_load"
```

**Totality/fail-closed pattern** (lines 462-475 and 524-535):
```python
@pytest.mark.parametrize(
    "state",
    [
        {},
        {"primary_intent": "small_talk", "requested_operation": "advise", "intent_confidence": 0.9},
        {"primary_intent": "unsupported", "requested_operation": "advise", "intent_confidence": 0.9},
        {"primary_intent": "policy_qa", "requested_operation": "advise", "intent_confidence": 0.9},
        {"primary_intent": "refund_troubleshooting", "requested_operation": "read_status", "intent_confidence": 0.9},
        {"routing_hints": {"pre_route_disposition": "approval_chat_not_trusted"}},
    ],
)
def test_route_after_intent_totality(state):
    assert route_after_intent(state) in INTENT_ROUTES
```

```python
def test_route_after_intent_fails_closed_for_registry_exception(monkeypatch):
    class RaisingIntentRegistry:
        def is_direct_response_intent(self, intent: str) -> bool:
            raise RuntimeError("registry unavailable")

    monkeypatch.setattr(routing_module, "INTENT_POLICY_REGISTRY", RaisingIntentRegistry(), raising=False)

    assert (
        routing_module.route_after_intent(
            {"primary_intent": "refund_troubleshooting", "requested_operation": "read_status", "intent_confidence": 0.9}
        )
        == "clarification_gate"
    )
```

**Required Phase 53 adaptation:** import/use `contextual_intent_resolve` helpers or canonical adapter if renamed. Route expectations for slot-required paths should become `extract_slots` through `route_after_contextual_intent`; `INTENT_ROUTES` must not contain `session_memory_load` if it remains the active allowlist.

---

### `tests/agent/test_intent_policy_registry.py` (test, transform/config)

**Analog:** `tests/agent/test_intent_policy_registry.py`

**Registry mirror pattern** (lines 23-35):
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
    assert registry.definition_for("refund_troubleshooting") == INTENT_DEFINITIONS["refund_troubleshooting"]
```

**Effective API pattern** (lines 38-55):
```python
def test_module_level_policy_registries_expose_effective_policy_api() -> None:
    assert isinstance(INTENT_POLICY_REGISTRY, IntentPolicyRegistry)
    assert isinstance(SLOT_POLICY_REGISTRY, SlotPolicyRegistry)

    assert INTENT_POLICY_REGISTRY.route_for_intent("policy_qa") == "investigate"
    assert INTENT_POLICY_REGISTRY.route_for_intent("small_talk") == "final_response"
    assert INTENT_POLICY_REGISTRY.route_for_intent("unknown_intent") is None
    assert INTENT_POLICY_REGISTRY.is_known_intent("refund_troubleshooting") is True
```

**Readonly policy pattern** (lines 88-99):
```python
def test_registries_are_read_only() -> None:
    intent_registry = IntentPolicyRegistry()
    slot_registry = SlotPolicyRegistry()

    with pytest.raises(TypeError):
        intent_registry.definitions()["policy_qa"] = INTENT_DEFINITIONS["unsupported"]
    with pytest.raises(TypeError):
        intent_registry.route_policy()["policy_qa"] = "final_response"
    with pytest.raises(TypeError):
        slot_registry.required_slot_policy()["policy_qa"] = RequiredSlotExpression(all_of=["merchant_id"])

    assert INTENT_DEFINITIONS["policy_qa"].initial_route == "investigate"
```

**Required Phase 53 adaptation:** add assertions that slot-bearing intent definitions route to `extract_slots` or that the contextual router translates them. Keep immutability tests.

---

### `tests/architecture/graph_baseline.py` (test utility, static analysis transform)

**Analog:** `tests/architecture/graph_baseline.py`

**Current/target baseline constants pattern** (lines 11-49):
```python
TARGET_CANONICAL_GRAPH_NODES = frozenset(
    {
        "receive_request",
        "safety_pre_route",
        "session_context_load",
        "contextual_intent_resolve",
        "slot_resolution_gate",
        ...
    }
)

CURRENT_ACTIVE_GRAPH_NODES_BASELINE = frozenset(
    {
        "receive_request",
        "safety_pre_route",
        "classify_intent",
        "session_memory_load",
        "extract_slots",
        ...
    }
)
```

**Migration ledger baseline pattern** (lines 51-82):
```python
MIGRATION_MODE_LEGACY_NODE_MAP = {
    "classify_intent": {
        "target": "contextual_intent_resolve",
        "delete_phase": "Phase 53",
        "owner_requirement": "CAGM-04",
    },
    "session_memory_load": {
        "target": "session_context_load",
        "delete_phase": "Phase 53",
        "owner_requirement": "CAGM-04",
    },
    "extract_slots": {
        "target": "slot_resolution_gate",
        "delete_phase": "Phase 54",
        "owner_requirement": "CAGM-05",
    },
```

**Conditional edge baseline pattern** (lines 88-104):
```python
CURRENT_CONDITIONAL_EDGE_BASELINE = {
    ("safety_pre_route", "route_after_safety"): {
        "classify_intent": "classify_intent",
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
    },
    ("classify_intent", "route_after_intent"): {
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
        "investigate": "investigate",
        "session_memory_load": "session_memory_load",
    },
    ("extract_slots", "route_after_slots"): {
        "clarification_gate": "clarification_gate",
        "investigate": "investigate",
        "long_term_memory_retrieve": "long_term_memory_retrieve",
    },
```

**AST graph extraction pattern** (lines 163-219):
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
        ...
        source = _string_literal(node.args[0], context="add_conditional_edges source")
        router = _name(node.args[1], context="add_conditional_edges router")
```

**Router route-value scanner pattern** (lines 408-422):
```python
def graph_router_route_values() -> dict[str, frozenset[str]]:
    routing_router_names = {
        "route_after_safety",
        "route_after_intent",
        "route_after_slots",
        "route_after_investigate",
        "route_after_rag_context",
        "route_after_recommendation",
        "route_after_claim_verify",
    }
    graph_router_names = {"route_after_risk", "route_after_approval"}
    return {
        **_router_route_values(ROUTING_PATH, routing_router_names),
        **_router_route_values(GRAPH_PATH, graph_router_names),
    }
```

**Required Phase 53 adaptation:** update active baseline to include `session_context_load` and `contextual_intent_resolve`, remove active `classify_intent` and `session_memory_load`, update conditional edge maps, and include `route_after_contextual_intent` in router scanning. Keep `extract_slots` as Phase 54 compatibility.

---

### `tests/architecture/test_canonical_graph_baseline.py` (test, static analysis transform)

**Analog:** `tests/architecture/test_canonical_graph_baseline.py`

**Active node baseline assertion pattern** (lines 19-21):
```python
def test_current_active_graph_node_set_matches_phase52_baseline() -> None:
    assert "safety_pre_route" in CURRENT_ACTIVE_GRAPH_NODES_BASELINE
    assert graph_add_node_names() == CURRENT_ACTIVE_GRAPH_NODES_BASELINE
```

**Migration map pattern** (lines 55-95):
```python
def test_migration_mode_maps_every_active_legacy_node_to_target() -> None:
    active_legacy_nodes = CURRENT_ACTIVE_GRAPH_NODES_BASELINE - TARGET_CANONICAL_GRAPH_NODES

    assert active_legacy_nodes == frozenset(MIGRATION_MODE_LEGACY_NODE_MAP)
    assert MIGRATION_MODE_LEGACY_NODE_MAP == {
        "classify_intent": {
            "target": "contextual_intent_resolve",
            "delete_phase": "Phase 53",
            "owner_requirement": "CAGM-04",
        },
        "session_memory_load": {
            "target": "session_context_load",
            "delete_phase": "Phase 53",
            "owner_requirement": "CAGM-04",
        },
        "extract_slots": {
            "target": "slot_resolution_gate",
            "delete_phase": "Phase 54",
            "owner_requirement": "CAGM-05",
        },
        ...
    }
```

**Router coverage pattern** (lines 105-124):
```python
def test_current_router_mappings_match_source_baseline() -> None:
    assert graph_conditional_edge_mappings() == CURRENT_CONDITIONAL_EDGE_BASELINE

def test_router_return_values_are_covered_by_registered_path_maps() -> None:
    route_maps = graph_conditional_edge_mappings()
    router_routes = graph_router_route_values()
    registered_nodes = graph_add_node_names()

    assert set(router_routes) == {router for _source, router in route_maps}
    assert router_routes["route_after_safety"] == frozenset(
        CURRENT_CONDITIONAL_EDGE_BASELINE[("safety_pre_route", "route_after_safety")]
    )
    for source, router in route_maps:
        path_map = route_maps[(source, router)]
        assert source in registered_nodes, (source, router)
        assert path_map, (source, router)
        assert set(path_map.values()) <= registered_nodes, (source, router)
        assert router_routes[router], router
        assert router_routes[router] <= frozenset(path_map), router
```

**Required Phase 53 adaptation:** rename Phase 52 baseline test names to Phase 53, remove `classify_intent`/`session_memory_load` from active legacy migration map, and assert route maps have no active path-map destinations to those nodes. Leave final exact canonical no-debt gate skipped for Phase 58.

---

### `tests/agent/test_graph_vocabulary.py` (test, transform/static)

**Analog:** `tests/agent/test_graph_vocabulary.py`

**Parameterized vocabulary test pattern** (lines 13-27):
```python
@pytest.mark.parametrize(
    ("name", "kind", "target_name", "status", "runnable"),
    [
        ("classify_intent", "node", "contextual_intent_resolve", "compatibility_alias", True),
        ("intent_classification", "node", "contextual_intent_resolve", "compatibility_alias", True),
        ("classify_intent:pre_route", "node", "safety_pre_route", "compatibility_alias", True),
        ("session_memory_load", "node", "session_context_load", "compatibility_alias", True),
        ("session_context_load", "node", "session_context_load", "runtime", True),
        ...
        ("route_after_intent", "router", "route_after_contextual_intent", "compatibility_alias", True),
        ("route_after_slots", "router", "route_after_slot_resolution", "compatibility_alias", True),
    ],
)
def test_legacy_graph_names_project_to_target_vocabulary(...):
```

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

    assert entry is not None
    assert entry.target_name == name
    assert entry.status == "runtime"
    assert entry.runnable is True
    assert projected["implementation_node"] == name
    assert projected["target_node"] == name
    assert projected["target_graph_status"] == "runtime"
    assert projected["target_graph_runnable"] is True
```

**Unknown passthrough pattern** (lines 135-145):
```python
def test_unknown_graph_name_is_safe_passthrough() -> None:
    assert graph_vocabulary_entry("custom_debug_node", kind="node") is None
    assert target_graph_name("custom_debug_node", kind="node") == "custom_debug_node"

    projected = project_trace_step_for_contract({"node": "custom_debug_node", "status": "completed"})

    assert projected["implementation_node"] == "custom_debug_node"
    assert projected["target_node"] == "custom_debug_node"
    assert projected["target_graph_status"] == "unknown_passthrough"
    assert projected["target_graph_runnable"] is True
```

**Required Phase 53 adaptation:** add/modify tests so `contextual_intent_resolve` and `route_after_contextual_intent` are runtime. Keep legacy aliases explicit and ledgered; keep `extract_slots` compatibility until Phase 54.

---

### `tests/agent/test_graph.py` (test, event-driven graph integration)

**Analog:** `tests/agent/test_graph.py`

**Graph test config pattern** (lines 83-119):
```python
def _config(
    tool_platform,
    events: list[dict[str, Any]],
    thread_id: str = "graph-test-thread",
    session: Any = None,
    investigate_planner: Any | None = None,
) -> dict:
    async def event_emitter(**payload):
        events.append(payload)

    permissions = [f"tool:{descriptor.name}" for descriptor in ToolCatalog().descriptors()]
    trusted_context = TrustedContext(
        tenant_id=GRAPH_TEST_TENANT_ID,
        user_id=GRAPH_TEST_USER_ID,
        role="support",
        permissions=permissions,
        merchant_scope=MerchantScopeV1(merchant_ids=["merchant-primary"]),
        session_id=None,
        thread_id=thread_id,
        run_id=str(uuid4()),
        trace_id="graph-trace",
        locale=None,
    )

    configurable = {
        "thread_id": thread_id,
        "session": session,
        "tool_platform": tool_platform,
        "event_emitter": event_emitter,
        "trusted_context": trusted_context.model_dump(mode="json"),
```

**Dependency patch pattern** (lines 510-537):
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
    ...
    tool_platform = FakeGraphToolPlatform(order_id=order_id, policy_status=policy_status, ticket_id=ticket_id)
    events: list[dict[str, Any]] = []
    return {"tool_platform": tool_platform, "events": events}
```

**Session memory fake pattern** (lines 573-600):
```python
def _session_memory_bundle_service(
    *,
    order_id: str = "ORD-SESSION-001",
    wrong_thread: bool = False,
    stale: bool = False,
):
    memory_service_type = _session_memory_service(order_id=order_id, wrong_thread=wrong_thread, stale=stale)

    class FakeBundleService:
        def __init__(self, *, conversation_service, memory_service) -> None:
            pass

        async def load_session_memory_bundle(self, **kwargs):
            view = await memory_service_type(None).load_session_memory(
                kwargs["tenant_id"],
                kwargs["user_id"],
                kwargs["thread_id"],
                kwargs.get("current_intent"),
            )
            return SessionMemoryBundle(
                tenant_id=str(kwargs["tenant_id"]),
                user_id=str(kwargs["user_id"]),
                thread_id=kwargs["thread_id"],
                run_id=str(kwargs["run_id"]),
                slot_continuity=view,
            )

    return FakeBundleService
```

**Graph path assertions to update** (lines 744-762 and 924-955):
```python
@pytest.mark.asyncio
async def test_same_thread_session_memory_active_slots_feed_investigate(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    from src.agent.nodes import session_memory_load as session_memory_load_module

    monkeypatch.setattr(session_memory_load_module, "SessionMemoryBundleService", _session_memory_bundle_service())
    graph = build_graph(MemorySaver())
    ...
    assert final_state["business_context"]["facts"]["order"]["order_no"] == "ORD-SESSION-001"
    assert "session_memory_load" in [step["node"] for step in final_state["trace_steps"]]
```

```python
def test_graph_compiles_with_investigate():
    graph = build_graph(MemorySaver())
    nodes = set(graph.get_graph().nodes)

    assert {
        "safety_pre_route",
        "classify_intent",
        "investigate",
        "rag_context_build",
        "claim_verify",
        "clarification_gate",
        "session_memory_load",
        "long_term_memory_retrieve",
    } <= nodes
```

**Unsafe pre-route stop pattern** (lines 1100-1112):
```python
@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["approve APR-1", "approve APR1", "同意"])
async def test_unsafe_pre_route_inputs_stop_before_classifier_memory_tools_or_action(monkeypatch, query):
    deps = _patch_graph_dependencies(monkeypatch, intent="policy_qa")
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(_state(query), _config(deps["tool_platform"], deps["events"]))

    nodes = [step["node"] for step in final_state["trace_steps"]]
    assert nodes[:2] == ["receive_request", "safety_pre_route"]
    assert "classify_intent" not in nodes
    assert "session_memory_load" not in nodes
    assert "long_term_memory_retrieve" not in nodes
```

**Required Phase 53 adaptation:** patch the new contextual intent module in `_patch_graph_dependencies`, update graph compile/node assertions, assert safe path trace starts `receive_request`, `safety_pre_route`, `session_context_load`, `contextual_intent_resolve`, and keep unsafe pre-route tests proving no intent/session memory/tool/action nodes run after unsafe inputs.

---

### `tests/agent/test_session_memory_load.py` (test, event-driven node/unit)

**Analog:** `tests/agent/test_session_memory_load.py`

**Direct canonical node test pattern** (lines 223-278):
```python
async def test_session_context_load_direct_node_returns_target_and_legacy_fields(monkeypatch):
    from src.agent.nodes import session_context_load as session_context_load_module
    from src.agent.nodes.session_context_load import session_context_load

    monkeypatch.setattr(session_context_load_module.settings, "session_memory_enabled", True)
    run_id = str(uuid.uuid4())

    class FakeSession:
        async def execute(self, *args, **kwargs):
            raise AssertionError("bundle service should not hit the repository in this test")

    class FakeBundleService:
        def __init__(self, *, conversation_service, memory_service) -> None:
            self.conversation_service = conversation_service
            self.memory_service = memory_service

        async def load_session_memory_bundle(self, **kwargs):
            slot_continuity = SessionMemoryView(
                source="postgres_session_memory",
                continuity_claimed=True,
                active_slots={"order_id": "ORD-CONTEXT-DIRECT"},
                slot_metadata={"order_id": {"source": "trusted_session_memory"}},
                version=11,
            )
            return SessionMemoryBundle(
                tenant_id=str(kwargs["tenant_id"]),
                user_id=str(kwargs["user_id"]),
                thread_id=kwargs["thread_id"],
                run_id=str(kwargs["run_id"]),
                rolling_summary={
                    "summary_id": "summary-context-direct",
                    "summary_text": "direct target node rolling summary",
                },
                recent_messages=[],
                tool_summaries=[],
                slot_continuity=slot_continuity,
            )

    monkeypatch.setattr(session_context_load_module, "SessionMemoryBundleService", FakeBundleService)

    result = await session_context_load(
        {**_state(), "current_run_id": run_id},
        {"configurable": {"session": FakeSession()}},
    )

    assert result["session_context"]["active_slots"] == {"order_id": "ORD-CONTEXT-DIRECT"}
    assert result["session_context_bundle"]["schema_version"] == "session_context_bundle.v1"
    assert result["session_context_load_status"]["schema_version"] == "session_context_load_status.v1"
    assert result["session_context_load_status"]["authority_class"] == "contextual_only"
    status = SessionContextLoadStatusV1.model_validate(result["session_context_load_status"])
    assert status.status == "loaded"
    assert status.filter_reasons == []
    assert result["session_memory"]["active_slots"] == {"order_id": "ORD-CONTEXT-DIRECT"}
    assert result["session_memory_bundle"]["schema_version"] == "session_memory_bundle.v1"
    assert result["trace_steps"][-1]["node"] == "session_context_load"
```

**Fallback/error pattern** (lines 320-356):
```python
result = await session_memory_load(
    {**_state(), "current_run_id": run_id},
    {"configurable": {"session": FakeSession()}},
)

assert result["session_memory"]["active_slots"] == {}
assert result["session_memory"]["continuity_claimed"] is False
assert result["session_memory"]["fallback_reason"] == "unavailable"
assert "session_memory_bundle" not in result
```

**Required Phase 53 adaptation:** add or update a direct `session_context_load` pre-intent test where state has no `primary_intent`/`current_intent`; fake service should prove `current_intent` can be `None`. Preserve canonical fields plus legacy projection.

---

### `tests/agent/test_session_memory_integration.py` (test, event-driven integration + DB I/O)

**Analog:** `tests/agent/test_session_memory_integration.py`

**Same-thread context integration pattern** (lines 129-177):
```python
@pytest.mark.asyncio
async def test_same_thread_vague_turn_inherits_session_order_and_reruns_investigation(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    thread_id = "integration-same-thread"
    await _write_order_memory(session, user, thread_id)
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state(user, "what about that refund?", thread_id),
        _config(deps["tool_platform"], deps["events"], thread_id, session=session),
    )

    assert final_state["active_slots"]["order_id"] == "ORD-1001"
    assert final_state["active_slot_metadata"]["order_id"]["source"] == "trusted_session_memory"
    assert final_state["active_slot_metadata"]["order_id"]["explicit_current_turn"] is False
    assert final_state["business_context"]["facts"]["order"]["order_no"] == "ORD-1001"
    assert [call[0] for call in deps["tool_platform"].calls] == ["get_order", "search_policy"]
```

**Explicit current turn override pattern** (lines 153-177):
```python
await _write_order_memory(session, user, thread_id, order_id="ORD-INHERITED-001")
current_run_id = await _persist_run(session, user, thread_id, "current run ORD-CURRENT-001")
deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-CURRENT-001")
graph = build_graph(MemorySaver())

final_state = await graph.ainvoke(
    _state(user, "订单是 ORD-CURRENT-001，继续查这笔退款", thread_id, run_id=current_run_id),
    _config(deps["tool_platform"], deps["events"], thread_id, session=session),
)

assert final_state["session_memory"]["active_slots"]["order_id"] == "ORD-INHERITED-001"
assert final_state["session_memory"]["slot_metadata"]["order_id"]["source"] == "trusted_session_memory"
assert final_state["active_slots"]["order_id"] == "ORD-CURRENT-001"
assert final_state["active_slot_metadata"]["order_id"]["source"] == "current_turn"
assert final_state["active_slot_metadata"]["order_id"]["explicit_current_turn"] is True
```

**Wrong scope fail-closed pattern** (lines 179-251):
```python
cases = [
    (user.tenant_id, user.id, "integration-agent-runs-memory-wrong-thread"),
    (uuid4(), user.id, source_thread_id),
    (user.tenant_id, uuid4(), source_thread_id),
    (user.tenant_id, user.id, expired_thread_id),
    (user.tenant_id, user.id, incompatible_thread_id),
]
for tenant_id, user_id, thread_id in cases:
    view = await service.load_session_memory(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        current_intent="refund_troubleshooting",
    )
    state = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "thread_id": thread_id,
        "primary_intent": "refund_troubleshooting",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "extracted_slots": {},
        "session_memory": view.model_dump(mode="json"),
    }

    assert view.continuity_claimed is False or view.active_slots == {}
    assert resolve_slots_for_completeness(state) == {}
    assert route_after_slots(state) == "clarification_gate"
```

**Required Phase 53 adaptation:** add same-thread pending-slot short-reply coverage for `session_context_load` before `contextual_intent_resolve`, proving no reviewed memory/RAG/approval/action/tool services are called before intent. Keep explicit-current-turn override and wrong-scope fail-closed assertions.

---

### `docs/current-langgraph-architecture.md` (documentation, source-fact snapshot)

**Analog:** `docs/current-langgraph-architecture.md`

**Current-source disclaimer pattern** (lines 1-5):
```markdown
# 当前 LangGraph Graph/Node 架构图

> 本图只根据当前仓库源码绘制，主要依据 `src/agent/graph.py` 的 `build_graph()` 节点/边定义，以及 `src/agent/routing.py` 和 `src/agent/graph.py` 中的条件路由函数。未把 planning 文档、README 描述或测试断言当作已实现事实。
>
> 读法边界：本文件是当前源码快照，不是目标架构。目标 canonical runtime graph 以 `docs/target-agent-platform-architecture-plan.md` §6.1 和 `docs/contract-spec.md` §9 为当前主要契约参考；本图中的 `classify_intent`、`extract_slots`、`long_term_memory_retrieve`、`generate_recommendation`、`assess_risk_and_approval` 等名称属于当前实现/迁移期 legacy alias，不代表目标完成后的 registered node key。
```

**Compatibility ledger table pattern** (lines 84-90):
```markdown
## Phase 52 兼容面

| Legacy surface | Canonical owner | Reason | Trace projection | Validation | Delete phase |
|----------------|-----------------|--------|------------------|------------|--------------|
| Safe-route continuation `safety_pre_route -> classify_intent` and `classify_intent` active graph node | `contextual_intent_resolve` / Phase 53 CAGM-04 | Phase 52 only extracts pre-route safety; session context before intent and contextual intent cutover are Phase 53 | `classify_intent` continues to project to `contextual_intent_resolve`; new `safety_pre_route` projects as runtime canonical | Architecture graph baseline + graph tests prove unsafe pre-route cases stop before `classify_intent` and safe cases use compatibility only | Phase 53 |
| `classification_trace.pre_route_decision` inside `classify_intent` | `safety_pre_route` for runtime pre-route ownership; Phase 53 removes classifier-owned duplicate | Safe-path compatibility may still need classifier trace parity until contextual intent cutover | `classify_intent:pre_route` remains a compatibility alias to `safety_pre_route`; `safety_pre_route` itself is runtime | `test_graph_vocabulary.py`, `test_safety_pre_route.py`, and classifier parity tests | Phase 53 |
```

**Required Phase 53 adaptation:** update the graph and facts from source after code changes. Close Phase 52 compatibility rows that are resolved. Ledger any retained helper/module/output mirror compatibility with a delete phase. Keep `extract_slots` as Phase 54 compatibility, not a Phase 53 failure.

---

### `.planning/ARCHITECTURE-DEBT.md` (documentation/ledger, append-only decision log)

**Analog:** `.planning/ARCHITECTURE-DEBT.md`

**Ledger rule pattern** (lines 6-18):
```markdown
## 写入规则

- 修改**工具调用 / RAG / 记忆 / 意图识别**这几个核心子系统时，检测出的 bug 或架构不完善点、以及做了哪些修复，**默认追加到本文件**对应子系统章节。
- 每条目尽量给：问题现象 / 根因、影响、处理状态、证据（phase / commit / 文件:行）、剩余风险。
- 只写「基于仓库真实代码、测试、planning artifact 核对过」的内容。未核实的写「未确认」，不编。
- 目标态 vs 已实现要分清：`docs/contract-spec.md` 是目标契约，不等于已实现事实。
```

**Existing Phase 52 debt to close or carry forward** (lines 42-56):
```markdown
## 2026-07-06 — Phase 52 safety_pre_route runtime pre-route 已落地，intent 兼容面留给 Phase 53 ⚠️

- **子系统**：Agent Graph / 意图识别
- **问题现象/根因**：Phase 51 之前的 runtime graph 把 request-risk / untrusted approval pre-route 行为藏在厚 `classify_intent` 节点与 `classification_trace.pre_route_decision` 中。
...
| Safe-route continuation `safety_pre_route -> classify_intent` and `classify_intent` active graph node | `contextual_intent_resolve` / Phase 53 CAGM-04 | ... | Phase 53 |
| `classification_trace.pre_route_decision` inside `classify_intent` | `safety_pre_route` for runtime pre-route ownership; Phase 53 removes classifier-owned duplicate | ... | Phase 53 |
...
- **剩余风险**：Phase 52 只完成 safety pre-route extraction；Phase 53 必须删除 active `classify_intent` graph-node compatibility，把 safe path 切到 `session_context_load -> contextual_intent_resolve`，并清理 classifier-owned duplicate `classification_trace.pre_route_decision`。
```

**Required Phase 53 adaptation:** append a verified Phase 53 entry in Chinese. State what was closed, what remains as intentional compatibility, evidence files/tests, and residual risk. Do not claim Phase 54/55/58 cleanup completed.

## Shared Patterns

### Fail-Closed Routers

**Source:** `src/agent/routing.py` lines 72-85
**Apply to:** `src/agent/routing.py`, `src/agent/graph.py`, `tests/test_graph_routing.py`, `tests/architecture/graph_baseline.py`

```python
def route_after_intent(state: AgentState) -> str:
    try:
        route = _route_after_intent(state)
    except Exception:
        return "clarification_gate"
    return route if route in INTENT_ROUTES else "clarification_gate"

def route_after_safety(state: AgentState) -> str:
    try:
        route = _route_after_safety(state)
    except Exception:
        return "clarification_gate"
    return route if route in SAFETY_ROUTES else "clarification_gate"
```

### Explicit LLM Output Adapter

**Source:** `src/agent/nodes/classify_intent.py` lines 390-443
**Apply to:** `src/agent/nodes/contextual_intent_resolve.py`, node tests

Copy the explicit `update = {...}` mapping and filtered return pattern. Do not merge raw structured output into state. Canonicalize `llm_outputs` owner and remove duplicate pre-route trace ownership.

### Candidate-Only Authority Boundary

**Source:** `src/agent/nodes/classify_intent.py` lines 76-89 and 441-443
**Apply to:** contextual intent node and tests

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

### Same-Thread Session Context Before Intent

**Source:** `src/agent/nodes/session_context_load.py` lines 31-43, 88-94, 302-328
**Apply to:** graph wiring, session context tests, graph integration tests

```python
async def session_context_load(
    state: AgentState,
    config: RunnableConfig,
    *,
    node_name: str = "session_context_load",
    ...
) -> dict:
    """Load same-thread session context through the MemoryContextService facade."""
```

```python
context, status_ref = await context_service.load_session_context_for_intent(
    tenant_id=state["tenant_id"],
    user_id=state["user_id"],
    thread_id=str(state["thread_id"]),
    run_id=run_id,
    current_intent=state.get("primary_intent") or state.get("current_intent"),
)
```

```python
result = {
    "session_context": session_context,
    "session_context_bundle": SessionContextBundle(session_context=context).model_dump(mode="json"),
    "session_context_load_status": status,
    "session_memory": session_memory,
    "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, node_name, session_memory, status)],
}
if include_legacy_bundle:
    result["session_memory_bundle"] = _legacy_session_memory_bundle_dump(context)
```

### Graph Baseline Uses AST, Not String Matching

**Source:** `tests/architecture/graph_baseline.py` lines 163-219 and 408-422
**Apply to:** architecture tests and graph route-map guardrails

Keep AST extraction for `add_node`, `add_edge`, `add_conditional_edges`, and router return values. Add `route_after_contextual_intent` to router scanning rather than using ad hoc text assertions as primary guardrails.

### Current Source Facts vs Target Contract

**Source:** `docs/current-langgraph-architecture.md` lines 1-5 and `.planning/ARCHITECTURE-DEBT.md` lines 6-12
**Apply to:** docs, debt, plan wording

Documentation must distinguish current source facts from target contract docs. `docs/contract-spec.md` is target semantics, not proof of current implementation. Phase 53 should not claim Phase 54 `slot_resolution_gate`, Phase 55 `memory_context_load`, or Phase 58 no-debt cleanup.

### MOCA Validation Entrypoint

**Source:** `AGENTS.md` lines 24-29 and `53-VALIDATION.md` lines 22-24
**Apply to:** all plan verification commands

Use only project-scoped commands, for example:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent tests/agent tests/architecture
```

Do not use bare `pytest` or bare `python -m pytest` in any plan, review, or verification command.

## No Analog Found

None. The only new code file, `src/agent/nodes/contextual_intent_resolve.py`, has a direct role/data-flow analog in `src/agent/nodes/classify_intent.py`; the planner should copy the adapter/LLM/deterministic short-reply patterns while changing ownership keys and removing legacy trace ownership.

## Metadata

**Analog search scope:** `src/agent`, `src/api/routers`, `tests/agent`, `tests/architecture`, `tests/test_graph_routing.py`, `docs/current-langgraph-architecture.md`, `.planning/ARCHITECTURE-DEBT.md`
**Files scanned:** 173
**Analog files read:** 19
**Pattern extraction date:** 2026-07-06
**Phase boundaries enforced:** no Phase 54 `slot_resolution_gate` cutover, no Phase 55 `memory_context_load` cutover, no Phase 58 final no-debt cleanup.
