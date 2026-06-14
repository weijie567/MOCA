# Phase 11: Intent / Clarification - Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 21
**Analogs found:** 19 / 21

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/schemas.py` | model | transform | `src/agent/schemas.py` | exact |
| `src/agent/state.py` | model | request-response | `src/agent/state.py` | exact |
| `src/agent/prompts.py` | config | transform | `src/agent/prompts.py` | exact |
| `src/agent/nodes/classify_intent.py` | node/service | request-response | `src/agent/nodes/classify_intent.py` | exact |
| `src/agent/intent_policy.py` | utility/config | transform | `src/agent/routing.py` | partial |
| `src/agent/routing.py` | route/utility | request-response | `src/agent/routing.py` | exact |
| `src/agent/nodes/extract_slots.py` | node/service | request-response | `src/agent/nodes/extract_slots.py` | exact |
| `src/agent/nodes/clarification_gate.py` | node/service | request-response | `src/agent/nodes/clarification_gate.py` | exact |
| `src/agent/graph.py` | config/route | event-driven | `src/agent/graph.py` | exact |
| `src/agent/intent_manifest.py` | utility | batch/transform | `tests/knowledge/test_citation_membership_eval.py` | partial |
| `tests/agent/test_intent_adapter.py` | test | request-response | `tests/agent/test_nodes/test_classify_intent.py` | role-match |
| `tests/agent/test_nodes/test_classify_intent.py` | test | request-response | `tests/agent/test_nodes/test_classify_intent.py` | exact |
| `tests/agent/test_intent_routing.py` | test | request-response | `tests/test_graph_routing.py` | exact |
| `tests/agent/test_required_slots.py` | test | transform | `tests/test_graph_routing.py` | role-match |
| `tests/agent/test_clarification_gate.py` | test | request-response | `tests/agent/test_nodes/test_receive_request.py` | role-match |
| `tests/agent/test_graph.py` | test | event-driven | `tests/agent/test_graph.py` | exact |
| `tests/agent/test_intent_manifest.py` | test | batch/transform | `tests/knowledge/test_citation_membership_eval.py` | role-match |
| `eval/intent/intent-golden.v1.json` | config/test fixture | batch | `tests/knowledge/datasets/citation_membership_v1.json` | role-match |
| `eval/intent/coverage-manifest.v1.json` | config/test fixture | batch | `tests/knowledge/datasets/citation_membership_v1.json` | partial |
| `eval/intent/intent-consistency.v1.json` | config/test fixture | batch | `docs/contract-spec.md` manifest skeleton | partial |
| `docs/contract-spec.md` | docs/contract | transform | `docs/contract-spec.md` | exact |

## Pattern Assignments

### `src/agent/schemas.py` (model, transform)

**Analog:** `src/agent/schemas.py`

**Imports pattern** (lines 1-5):
```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
```

**Structured output enum pattern** (lines 8-17):
```python
class IntentResult(BaseModel):
    intent: Literal[
        "policy_qa",
        "refund_troubleshooting",
        "compensation_suggestion",
        "approval_request",
        "unknown",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
```

**Strict schema pattern to copy for untrusted model output** (lines 64-80):
```python
class InvestigationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v1"] = "v1"
    facts: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRefSchema] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    candidate_action: dict[str, Any] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    stop_reason: Literal[
        "sufficient_evidence",
        "insufficient_evidence",
        "unsafe_tool_request",
        "tool_error",
        "iteration_budget_exhausted",
    ]
    safety_notes: list[str] = Field(default_factory=list)
```

**Apply:** Define `IntentResultV3`, intent/requested-operation `Literal[...]` aliases, `RequiredSlotExpression`, `ClarificationRequest`, and manifest/eval Pydantic models here or in a small helper module if `schemas.py` becomes crowded. Use `ConfigDict(extra="forbid")` for classifier and manifest contracts because model/test fixtures are untrusted inputs.

---

### `src/agent/state.py` (model, request-response)

**Analog:** `src/agent/state.py`

**TypedDict model pattern** (lines 1-8, 48-60):
```python
from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class ActiveSlots(TypedDict, total=False):
```

```python
class AgentState(TypedDict, total=False):
    """LangGraph state contract split into persistent and ephemeral fields."""

    # Persistent memory: survives across turns via the checkpointer.
    thread_id: str
    tenant_id: str
    user_id: str
    role: str
    active_slots: ActiveSlots
    last_intent: str | None
```

**Current Phase 10 intent fields to extend** (lines 62-83):
```python
    # Ephemeral context: reset by receive_request at the start of each turn.
    user_query: str | None
    normalized_query: str | None
    current_intent: str | None
    extracted_slots: dict[str, Any] | None
    business_context: dict[str, Any] | None
    retrieved_evidence: dict[str, Any] | None
    recommendation_draft: dict[str, Any] | None
    risk_assessment: dict[str, Any] | None

    # Phase 10: §10.1 canonical ephemeral fields reset each turn by receive_request.
    primary_intent: str | None
    requested_operation: str | None
```

**Approval boundary fields** (lines 84-87):
```python
    # Phase 4: approval workflow fields.
    proposed_action: dict[str, Any] | None
    approval_result: dict[str, Any] | None
    action_result: dict[str, Any] | None
```

**Apply:** Add `intent_confidence`, `secondary_intents`, `required_slots`, `candidate_slots`, `routing_hints`, and `clarification_request` as ephemeral fields. Keep `approval_result` separate and never write it from ordinary intent/clarification nodes.

---

### `src/agent/prompts.py` (config, transform)

**Analog:** `src/agent/prompts.py`

**Prompt constant style** (lines 1-10):
```python
CLASSIFY_INTENT_SYSTEM = """You classify merchant operations and support questions into exactly one intent.

Allowed intents:
- policy_qa: the user asks about platform refund, return, compensation, or support rules.
- refund_troubleshooting: the user asks why a specific order or refund case is stuck, failed, delayed, or abnormal.
- compensation_suggestion: the user asks what compensation, coupon, refund override, or appeasement action should be proposed.
- approval_request: the user asks to approve, reject, escalate, or review a risky action.
- unknown: the question is outside refund/order/support policy operations or lacks enough context.

Respond only as JSON with fields: intent, confidence, reasoning.
```

**Slot prompt style** (lines 27-38):
```python
EXTRACT_SLOTS_SYSTEM = """Extract structured identifiers and issue type from a merchant operations or support query.

Fields to extract:
- order_id
- refund_case_id
- ticket_id
- merchant_id
- customer_id
- issue_type

Return JSON only. Use null for every missing field. Do not invent identifiers. Preserve the exact identifier text found in the user message.
"""
```

**Apply:** Replace the obsolete `approval_request` ordinary intent with the Phase 11 taxonomy and explicit `IntentResultV3` field contract. The prompt should instruct that approval-looking ordinary chat is not a trusted approval decision and must not output `approval_decision`.

---

### `src/agent/nodes/classify_intent.py` (node/service, request-response)

**Analog:** `src/agent/nodes/classify_intent.py`

**Imports and LLM seam** (lines 1-13, 20-28):
```python
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.prompts import CLASSIFY_INTENT_SYSTEM
from src.agent.schemas import IntentResult
from src.agent.state import AgentState
from src.config import settings
```

```python
def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.dashscope_api_key,
        openai_api_base=settings.embedding_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )
```

**Trace helper pattern** (lines 31-54):
```python
def _trace_step(
    node: str,
    status: str,
    started_at: str,
    provider_latency_ms: int | None,
    retry_count: int,
    context_chars: int,
) -> dict[str, Any]:
    return {
        "node": node,
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "model_name": settings.llm_model,
        "prompt_tokens": None,
        "completion_tokens": None,
        "provider_latency_ms": provider_latency_ms,
        "retry_count": retry_count,
        "metrics_json": {
            "model": settings.llm_model,
            "provider": "dashscope",
            "context_chars": context_chars,
        },
    }
```

**Structured-output node pattern** (lines 57-91):
```python
async def classify_intent(state: AgentState) -> dict:
    started_at = _now_iso()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": CLASSIFY_INTENT_SYSTEM},
        {"role": "user", "content": state.get("user_query") or ""},
    ]
    structured_llm = _get_llm().with_structured_output(IntentResult)
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
            outputs = {**(state.get("llm_outputs") or {}), "classify_intent": result.model_dump()}
            return {
                "current_intent": result.intent,
                "last_intent": result.intent,
                "llm_outputs": outputs,
                "trace_steps": (state.get("trace_steps") or [])
```

**Error fallback pattern** (lines 92-118):
```python
        except (ValidationError, ValueError, TimeoutError, Exception) as exc:
            provider_latency_ms = round((time.perf_counter() - t0) * 1000)
            last_error = str(exc)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Validation failed: {last_error}. Respond with valid JSON.",
                    }
                )

    return {
        "current_intent": "unknown",
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "classify_intent", "error": last_error, "retry_count": 2}],
```

**Apply:** Keep `_get_llm`, `_trace_step`, async node shape, two-attempt validation retry, and `llm_outputs` merge. Replace current whole-node return with an explicit `IntentResultV3 -> AgentState` adapter. Do not whole-object merge `result.model_dump()` into state.

---

### `src/agent/intent_policy.py` (utility/config, transform)

**Analog:** `src/agent/routing.py` plus `docs/contract-spec.md`

**Pure helper style** (routing lines 65-81):
```python
def _intent(state: AgentState) -> str:
    value = state.get("primary_intent") or state.get("current_intent")
    return value if isinstance(value, str) else "unknown"


def _facts_from_business_context(business_context: dict[str, Any]) -> dict[str, Any]:
    facts = business_context.get("facts")
    if isinstance(facts, dict):
        return facts
    ignored = {"missing_required_facts", "errors", "status", "schema_version", "tool_results", "business_fact_refs"}
    return {key: value for key, value in business_context.items() if key not in ignored}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
```

**Normative taxonomy and precedence source** (`docs/contract-spec.md` lines 700-735):
```python
Intent = Literal[
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
]
```

**Required-slot table source** (`docs/contract-spec.md` lines 746-758):
```markdown
| `refund_troubleshooting` | `{"all_of":[],"any_of":[["refund_case_id","order_id"]],"optional":["ticket_id","merchant_id"]}` | refund_case_id, order_id, ticket_id | current thread, must match same case context |
| `action_request` | `{"all_of":["action_type"],"any_of":[["order_id","refund_case_id","ticket_id","merchant_id"]],"optional":["amount","currency","reason"]}` | target id only if same action context | current run/revision only for approvals |
| `small_talk` | `{"all_of":[],"any_of":[],"optional":[]}` | (none) | n/a |
| `unsupported` | `{"all_of":[],"any_of":[],"optional":[]}` | (none) | n/a |
```

**Apply:** If adding `intent_policy.py`, keep it as deterministic constants/helpers only: taxonomy, requested-operation literals, precedence resolution, required-slot expressions, and confidence thresholds. Do not make it a runtime `IntentRegistry`; the manifest is a consistency checker, not runtime source of truth.

---

### `src/agent/routing.py` (route/utility, request-response)

**Analog:** `src/agent/routing.py`

**Total router wrapper pattern** (lines 8-23):
```python
MIN_EVIDENCE_SCORE = 0.55
_FACT_ONLY_INTENTS = {"order_status_inquiry"}
_PERMISSION_CODES = {"FORBIDDEN", "permission_denied"}
_INVESTIGATE_ROUTES = {"final_response", "clarification_gate", "recommendation_generation"}


def route_after_investigate(state: AgentState) -> str:
    """Route after the merged investigate node using state only."""
    try:
        route = _route_after_investigate(state)
    except Exception:
        return "final_response"
    if route in _INVESTIGATE_ROUTES:
        return route
    return "final_response"
```

**Decision precedence pattern** (lines 25-62):
```python
def _route_after_investigate(state: AgentState) -> str:
    bc_value = state.get("business_context")
    business_context = bc_value if isinstance(bc_value, dict) else {}
    missing = _string_list(business_context.get("missing_required_facts"))
    errors = business_context.get("errors") if isinstance(business_context.get("errors"), list) else []
    facts = _facts_from_business_context(business_context)
    retrieval_status = state.get("retrieval_status")
    best_score = state.get("best_score")
    claim_dependency_map = state.get("claim_dependency_map") or []
    intent = _intent(state)
```

**Fail-closed validation helper** (lines 111-127):
```python
def _valid_claim_dependency_map(claim_dependency_map: Any) -> bool:
    if not isinstance(claim_dependency_map, list) or not claim_dependency_map:
        return False
    for entry in claim_dependency_map:
        if not isinstance(entry, dict):
            return False
        if not isinstance(entry.get("claim_id"), str):
            return False
        refs = entry.get("depends_on_refs")
        if not isinstance(refs, list):
            return False
        for ref in refs:
            if not isinstance(ref, dict):
                return False
            if not isinstance(ref.get("resource_type"), str) or not isinstance(ref.get("resource_id"), str):
                return False
    return True
```

**Normative router contract** (`docs/contract-spec.md` lines 403-410):
```markdown
Router functions are deterministic and side-effect free. They must return a valid node key for every valid state shape and must not call LLMs, tools, repositories, external APIs, or services.

| `route_after_intent` | ordinary-chat `primary_intent`, `requested_operation`, `intent_confidence`, `required_slots`, `routing_hints` | low confidence -> domain-specific high-risk route -> requested write/escalation operation -> direct response/policy/slots path | `clarification_gate`, `final_response`, `investigate`, `session_memory_load` | route to `clarification_gate`；任何 `approval_decision` 值均视为 untrusted invalid state |
| `route_after_slots` | `required_slots: RequiredSlotExpression`, `extracted_slots`, `session_memory.active_slots` | resolve current explicit slots first; inherit session slots only if fresh/scope-compatible; every `all_of` member and at least one member of each `any_of` group must be present | `clarification_gate`, `investigate`, `long_term_memory_retrieve` | route to `clarification_gate` |
```

**Apply:** Implement `route_after_intent` and `route_after_slots` with the same total-wrapper shape and valid-key allowlists. Use helpers for type normalization. Route invalid approval-decision-like ordinary state to `clarification_gate`.

---

### `src/agent/nodes/extract_slots.py` (node/service, request-response)

**Analog:** `src/agent/nodes/extract_slots.py`

**Structured-output slot node pattern** (lines 57-94):
```python
async def extract_slots(state: AgentState) -> dict:
    started_at = _now_iso()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": EXTRACT_SLOTS_SYSTEM},
        {"role": "user", "content": state.get("normalized_query") or state.get("user_query") or ""},
    ]
    structured_llm = _get_llm().with_structured_output(SlotExtractionResult)
    last_error: str | None = None
    provider_latency_ms: int | None = None
    retry_count = 0
```

**Current explicit-slot merge pattern** (lines 75-82):
```python
            extracted = result.model_dump()
            new_slots = {key: value for key, value in extracted.items() if value is not None}
            merged = {**(state.get("active_slots") or {}), **new_slots}
            outputs = {**(state.get("llm_outputs") or {}), "extract_slots": extracted}
            return {
                "extracted_slots": extracted,
                "active_slots": merged,
                "llm_outputs": outputs,
```

**Error fallback pattern** (lines 106-121):
```python
    return {
        "extracted_slots": {},
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "extract_slots", "error": last_error, "retry_count": 2}],
        "trace_steps": (state.get("trace_steps") or [])
```

**Apply:** Preserve the structured-output and trace pattern. When adding candidate-slot hints, they may inform the prompt only; do not merge `candidate_slots` into `extracted_slots` or `active_slots`. Slot completeness belongs in deterministic resolver/router helpers.

---

### `src/agent/nodes/clarification_gate.py` (node/service, request-response)

**Analog:** `src/agent/nodes/clarification_gate.py`

**Minimal ordinary clarification node pattern** (lines 14-32):
```python
async def clarification_gate(state: AgentState, config: RunnableConfig) -> dict:
    """Minimal safe clarification fallback. Phase 11 owns full logic."""
    del config
    started_at = _now_iso()
    missing = state.get("missing_info") or state.get("required_slots") or []
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
        "clarification_request": {"reason": "missing_required_information", "missing": missing},
        "final_response": "Could you provide a bit more information so I can help?",
        "trace_steps": (state.get("trace_steps") or []) + [step],
    }
```

**Normative output shape** (`docs/contract-spec.md` lines 803-812):
```json
{
  "reason": "missing_required_slots",
  "clarification_request_id": "clarify_123",
  "questions": ["请提供订单号或退款单号。"],
  "blocked_nodes": ["investigate", "action_draft"],
  "resume_policy": "same_thread_only"
}
```

**Apply:** Upgrade the return object with `clarification_request_id`, minimal question list, `blocked_nodes`, and `resume_policy`. Keep it ordinary-chat only; it must not write `approval_result`, approval versions, or LangGraph resume commands.

---

### `src/agent/graph.py` (config/route, event-driven)

**Analog:** `src/agent/graph.py`

**Imports and node registration pattern** (lines 16-32, 57-71):
```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from src.agent.nodes.assess_risk_and_approval import assess_risk_and_approval
from src.agent.nodes.approval_gate import approval_gate
from src.agent.nodes.classify_intent import classify_intent
from src.agent.nodes.clarification_gate import clarification_gate
```

```python
def build_graph(checkpointer: AsyncPostgresSaver):
    """Build and compile the refund agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node("receive_request", receive_request)
    builder.add_node("classify_intent", classify_intent, retry_policy=_llm_retry)
    builder.add_node("session_memory_load", session_memory_load)
    builder.add_node("extract_slots", extract_slots, retry_policy=_llm_retry)
```

**Current linear edges to replace** (lines 73-78):
```python
    builder.add_edge(START, "receive_request")
    builder.add_edge("receive_request", "classify_intent")
    builder.add_edge("classify_intent", "session_memory_load")
    builder.add_edge("session_memory_load", "extract_slots")
    builder.add_edge("extract_slots", "investigate")
    builder.add_conditional_edges(
```

**Conditional edge pattern** (lines 78-86, 90-106):
```python
    builder.add_conditional_edges(
        "investigate",
        route_after_investigate,
        {
            "final_response": "final_response",
            "clarification_gate": "clarification_gate",
            "recommendation_generation": "generate_recommendation",
        },
    )
```

```python
    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {
            "execute_action": "execute_action",
            "final_response": "final_response",
        },
    )
```

**Apply:** Replace `classify_intent -> session_memory_load` with `add_conditional_edges("classify_intent", route_after_intent, ...)`. Replace `extract_slots -> investigate` with `add_conditional_edges("extract_slots", route_after_slots, ...)`. Extend graph tests so every router return key maps to a registered node.

---

### `src/agent/intent_manifest.py` (utility, batch/transform)

**Analog:** `tests/knowledge/test_citation_membership_eval.py` and `docs/contract-spec.md`

**Dataset path/hash gate style** (test lines 9-24, 41-44):
```python
import hashlib
import json
from pathlib import Path

import pytest

from src.knowledge.citation import validate_membership
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1

DATASET_PATH = Path(__file__).parent / "datasets" / "citation_membership_v1.json"
DATASET_SHA256 = "sha256:3ac980b66024b2e4ebd404690aa22722a3818ff22c2f9015134f1eda57ac681b"
```

```python
def test_dataset_hash_pinned():
    actual = f"sha256:{hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()}"

    assert actual == DATASET_SHA256
```

**Manifest contract source** (`docs/contract-spec.md` lines 852-864):
```markdown
必须维护一份 machine-readable intent consistency manifest，逐项列出 §11.1 taxonomy 的每个 ordinary-chat intent。该 manifest 只声明并校验跨表覆盖完整性；它不是运行时 `IntentRegistry`...

Consistency check 的 normative 规则如下。每个 taxonomy intent 必须按以下覆盖规则具有对应条目，缺少任一 required 条目即 consistency check fail，并由 CI/contract test 阻断：

1. §11.2 precedence 表有该 intent 的 primary intent 行。
2. §11.3 required-slot 表有该 intent 的 required-slot expression。
3. §9.3 intent-level routing 表必须有所有 taxonomy intent 的路由行。
4. §11.4 intent golden set 有该 intent 的正样例和负样例。
```

**Apply:** If a source utility is added, keep it deterministic and file-based. It should load JSON, validate with Pydantic, compute SHA-256, and return structured gate statuses. Do not wire manifest data into runtime routing.

---

## Test Pattern Assignments

### `tests/agent/test_intent_adapter.py` and `tests/agent/test_nodes/test_classify_intent.py` (test, request-response)

**Analog:** `tests/agent/test_nodes/test_classify_intent.py`

**Async node test style** (lines 10-17):
```python
@pytest.mark.asyncio
async def test_classify_intent_success(monkeypatch, base_state, fake_llm_intent):
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: fake_llm_intent)

    result = await classify_intent_module.classify_intent(base_state)

    assert result["current_intent"] == "refund_troubleshooting"
```

**Validation failure style** (lines 19-30):
```python
@pytest.mark.asyncio
async def test_classify_intent_llm_failure_returns_unknown(monkeypatch, base_state):
    monkeypatch.setattr(
        classify_intent_module,
        "_get_llm",
        lambda: FakeLLM({"intent": "not_valid", "confidence": 0.95, "reasoning": "bad enum"}),
    )

    result = await classify_intent_module.classify_intent(base_state)

    assert result["current_intent"] == "unknown"
    assert result["node_errors"]
```

**Fake LLM seam** (`tests/agent/conftest.py` lines 11-35):
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
```

**Apply:** Add tests for V3 adapter allowed writes, no whole-object merge, `confidence` vs `calibrated_confidence`, no candidate-slot overwrite, and no forbidden writes (`approval_result`, `active_slots`, `extracted_slots`, final answers, tool/action outputs).

---

### `tests/agent/test_intent_routing.py` and `tests/agent/test_required_slots.py` (test, request-response/transform)

**Analog:** `tests/test_graph_routing.py`

**Pure router test style** (lines 52-86):
```python
def test_missing_required_facts_to_clarification():
    state = {"business_context": {"missing_required_facts": ["order_id"]}}

    assert route_after_investigate(state) == "clarification_gate"


def test_fact_only_intent_with_facts_to_final():
    state = {
        "primary_intent": "order_status_inquiry",
        "business_context": {"facts": {"order": {"status": "delivered"}}},
    }

    assert route_after_investigate(state) == "final_response"
```

**Parametrized totality pattern** (lines 162-179):
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

**Apply:** Keep router tests pure: no LLM, graph, DB, tool manager, or network. Cover precedence conflicts, low confidence, approval-looking invalid ordinary state, `all_of`, `any_of`, `optional`, explicit slots over inherited slots, and candidate-slot non-completeness.

---

### `tests/agent/test_clarification_gate.py` (test, request-response)

**Analog:** `tests/agent/test_nodes/test_receive_request.py`

**Async deterministic-node test style** (lines 8-23):
```python
@pytest.mark.asyncio
async def test_receive_request_resets_ephemeral(base_state):
    state = {
        **base_state,
        "current_intent": "old_intent",
        "business_context": {"old": "data"},
        "trace_steps": [{"node": "old_node"}],
    }

    result = await receive_request(state)

    assert result["current_intent"] is None
    assert result["business_context"] is None
    assert [step["node"] for step in result["trace_steps"]] == ["receive_request"]
    assert result["current_run_id"] is not None
```

**Apply:** Call `clarification_gate` directly with ordinary missing-slot/low-confidence states. Assert exact `clarification_request` shape, minimal questions, trace append, no permission/tool error leakage in user-facing text, and no approval lifecycle keys in result.

---

### `tests/agent/test_graph.py` (test, event-driven)

**Analog:** `tests/agent/test_graph.py`

**Graph fixture style** (lines 49-63):
```python
def _config(manager, events: list[dict[str, Any]], thread_id: str = "graph-test-thread") -> dict:
    async def event_emitter(**payload):
        events.append(payload)

    return {
        "configurable": {
            "thread_id": thread_id,
            "session": None,
            "tool_manager": manager,
            "event_emitter": event_emitter,
            "permissions": [f"tool:{descriptor.name}" for descriptor in ToolRegistry().descriptors()],
```

**Graph dependency patching** (lines 189-201):
```python
def _patch_graph_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    intent: str = "policy_qa",
    order_id: str | None = None,
):
    monkeypatch.setattr(classify_intent_module, "_get_llm", lambda: FakeLLM(_intent(intent)))
    monkeypatch.setattr(extract_slots_module, "_get_llm", lambda: FakeLLM(_slots(order_id)))
    monkeypatch.setattr(generate_recommendation_module, "_get_llm", lambda: FakeLLM(_recommendation()))
    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: FakeLLM(_risk()))
    manager = FakeGraphToolManager(order_id=order_id)
    events: list[dict[str, Any]] = []
    return {"tool_manager": manager, "events": events}
```

**Router edge coverage style** (lines 320-337):
```python
def test_route_after_investigate_keys_are_edge_targets():
    graph = build_graph(MemorySaver())
    nodes = set(graph.get_graph().nodes)
    states = [
        {},
        {"business_context": {"missing_required_facts": ["order_id"]}},
        {"retrieval_status": "strong_evidence", "best_score": 0.9},
    ]
    mapping = {
        "final_response": "final_response",
        "clarification_gate": "clarification_gate",
        "recommendation_generation": "generate_recommendation",
    }

    for state in states:
        key = route_after_investigate(state)
        assert key in mapping
        assert mapping[key] in nodes
```

**Apply:** Extend dependency patching for V3 fake intent payloads. Add graph tests proving direct-response and low-confidence/approval-looking paths do not always traverse `session_memory_load`/`extract_slots`/`investigate`, and slot-required paths do.

---

### `tests/agent/test_intent_manifest.py` and `eval/intent/*.json` (test/config, batch)

**Analog:** `tests/knowledge/test_citation_membership_eval.py` and `tests/knowledge/datasets/citation_membership_v1.json`

**Pinned dataset test pattern** (lines 19-25, 41-48):
```python
DATASET_PATH = Path(__file__).parent / "datasets" / "citation_membership_v1.json"
DATASET_SHA256 = "sha256:3ac980b66024b2e4ebd404690aa22722a3818ff22c2f9015134f1eda57ac681b"


def _load_dataset() -> dict:
    return json.loads(DATASET_PATH.read_text())
```

```python
def test_dataset_hash_pinned():
    actual = f"sha256:{hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()}"

    assert actual == DATASET_SHA256


@pytest.mark.parametrize("case", _load_dataset()["cases"], ids=lambda case: case["id"])
def test_membership_eval_gate(case):
```

**JSON fixture style** (`tests/knowledge/datasets/citation_membership_v1.json` lines 1-20):
```json
{
  "version": "citation_membership.v1",
  "description": "Phase 8 citation membership gate dataset. Membership = cited evidence_id present in evidence_refs. NOT semantic support.",
  "cases": [
    {
      "id": "valid_membership",
      "evidence_ids": [
        "policy_refund_timeout/chunk_001@v3",
        "policy_refund_timeout/chunk_002@v3"
      ],
      "claims": [
        {
          "claim_id": "c1",
          "claim_text": "Refund timeout handling follows the cited policy.",
          "cited_evidence_ids": [
            "policy_refund_timeout/chunk_001@v3"
          ]
        }
      ],
      "expected_is_valid": true
```

**Confidence gate source** (`docs/contract-spec.md` lines 781-789):
```markdown
| `intent-golden.v1` or newer, immutable hash recorded | primary intent accuracy | `>= 0.90` | `<= 0.01` | 不达标时 action/risk intents 进入 clarification 或 deterministic safe route | M6 release blocked |
| same dataset/version | required-slot expression exact match | `>= 0.95` | `0` for missing action target groups | 不达标时 deterministic slot policy 覆盖模型输出 | M6 release blocked |
| same dataset/version | safe-route recall for action/approval/appeal | `>= 0.99` | `<= 0.01` | action path 强制 risk/approval；禁止 confidence-only auto route | M6 release blocked |
```

**Apply:** Place Phase 11 JSON fixtures under `eval/intent/` as requested by research. Tests should pin hashes, validate schema, check per-intent manifest coverage, assert `small_talk`/`unsupported` evidence-table exemptions, and verify Wilson gate status precedence including `statistical_gate_not_demonstrated`.

## Shared Patterns

### Structured LLM Nodes
**Source:** `src/agent/nodes/classify_intent.py` lines 57-118 and `src/agent/nodes/extract_slots.py` lines 57-121  
**Apply to:** `classify_intent`, `extract_slots`, any optional small-LLM clarification implementation

Use `_get_llm().with_structured_output(PydanticModel)`, two-attempt validation retry, `llm_outputs` merge, `trace_steps` append, and node-local fallback state. Do not call real LLMs in tests; patch `_get_llm` to `FakeLLM`.

### Explicit State Writes
**Source:** `docs/contract-spec.md` lines 672-685  
**Apply to:** `classify_intent`, adapter tests, `state.py`

`IntentResultV3` maps field-by-field: `confidence -> intent_confidence`; `calibrated_confidence -> llm_outputs.intent_classification.eval_metadata`; `candidate_slots -> candidate_slots` only; no final response, slots, risk, approval, resume, tool, or action writes from the intent node.

### Router Purity and Totality
**Source:** `src/agent/routing.py` lines 14-23 and `docs/contract-spec.md` lines 403-410  
**Apply to:** `route_after_intent`, `route_after_slots`, router tests

Routers are side-effect-free functions over `AgentState`, catch invalid shapes, and return only graph edge keys. They must not call LLMs, tools, repositories, external APIs, or services.

### Graph Conditional Edges
**Source:** `src/agent/graph.py` lines 78-86 and 90-106  
**Apply to:** `classify_intent` and `extract_slots` graph wiring

Use `builder.add_conditional_edges(node, router, mapping)` when routing without state updates. Do not leave a static edge from the same node that would force every path through the old linear flow.

### Per-Turn Reset
**Source:** `src/agent/nodes/receive_request.py` lines 28-61  
**Apply to:** new ephemeral fields in `state.py`

Every new Phase 11 turn-scoped field must be reset in `receive_request`: `intent_confidence`, `secondary_intents`, `required_slots`, `candidate_slots`, `routing_hints`, and `clarification_request`.

### Ordinary Approval Boundary
**Source:** `docs/contract-spec.md` lines 714-722 and `tests/agent/test_nodes/test_investigate.py` lines 232-244  
**Apply to:** classifier, routers, clarification, graph tests

Ordinary chat cannot produce `approval_result`, trusted approval versions, or resume commands. Existing safety tests already assert adjacent nodes do not write approval/action fields; copy that negative assertion style.

## No Analog Found

Files with no exact close match in the codebase; planner should use `11-RESEARCH.md` and `docs/contract-spec.md` patterns for these pieces.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/agent/intent_policy.py` | utility/config | transform | No existing centralized intent precedence/required-slot policy module. Closest partial analog is pure helper style in `src/agent/routing.py`. |
| `src/agent/intent_manifest.py` | utility | batch/transform | No existing source manifest checker for intent consistency. Closest partial analog is dataset hash testing in `tests/knowledge/test_citation_membership_eval.py`. |

## Metadata

**Analog search scope:** `src/agent/`, `tests/agent/`, `tests/test_graph_routing.py`, `tests/knowledge/`, `eval*/`, `docs/contract-spec.md`  
**Files scanned:** 40+ source/test/eval/doc candidates via `rg`, `find`, and targeted reads  
**Pattern extraction date:** 2026-06-14
