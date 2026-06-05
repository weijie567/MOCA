# Phase 7: Tool Registry & Investigation Contracts - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 8
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/agent/tools/contracts.py` | utility | transform | `src/agent/schemas.py` | role-match |
| `src/agent/tools/registry.py` | service | request-response | `src/agent/nodes/retrieve_policy_evidence.py` | partial |
| `src/agent/tools/adapters.py` | utility | request-response | `src/agent/nodes/load_business_context.py` | partial |
| `src/agent/schemas.py` | model | transform | `src/agent/schemas.py` | exact |
| `src/agent/state.py` | model | request-response | `src/agent/state.py` | exact |
| `tests/agent/test_tools/test_tool_contracts.py` | test | transform | `tests/agent/test_graph.py` | partial |
| `tests/agent/test_tools/test_registry.py` | test | request-response | `tests/agent/test_nodes/test_retrieve_policy_evidence.py` | partial |
| `tests/agent/test_tools/test_tool_adapters.py` | test | request-response | `tests/agent/test_tools/test_get_order.py` | role-match |

## Pattern Assignments

### `src/agent/tools/contracts.py` (utility, transform)

**Analog:** `src/agent/schemas.py`

**Imports pattern** (`/Users/ming/projects/MOCA/src/agent/schemas.py` lines 1-5):
```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
```

**Literal + Field bounds pattern** (`/Users/ming/projects/MOCA/src/agent/schemas.py` lines 8-18):
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

**Nested typed schema pattern** (`/Users/ming/projects/MOCA/src/agent/schemas.py` lines 29-34, 36-49):
```python
class EvidenceRefSchema(BaseModel):
    doc_key: str = Field(description="Exact doc_key copied from one retrieved evidence item.")
    chunk_id: str = Field(description="Exact chunk_id copied from the same retrieved evidence item.")
    title: str = Field(description="Exact title copied from the same retrieved evidence item.")
    section: str = Field(description="Exact section copied from the same retrieved evidence item.")

class RecommendationDraft(BaseModel):
    recommended_action: str
    reasoning_summary: str
    evidence_refs: list[EvidenceRefSchema] = Field(
        min_length=1,
        description=(
            "At least one citation object copied from retrieved evidence. "
            "Do not return strings, doc_key-only values, or chunk_id-only values."
        ),
    )
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high"]
    missing_info: list[str] = Field(default_factory=list)
```

**What to copy:** Keep contract models as small Pydantic `BaseModel` classes with `Literal[...]`, `Field(...)`, and nested typed models. Phase 7-specific `extra="forbid"` should be added on top of this style for prompt-facing contracts.

---

### `src/agent/tools/registry.py` (service, request-response)

**Analog:** `src/agent/nodes/retrieve_policy_evidence.py`

**Invocation + structured result pattern** (`/Users/ming/projects/MOCA/src/agent/nodes/retrieve_policy_evidence.py` lines 107-145):
```python
async def retrieve_policy_evidence(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    retrieved_at = _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable["session"]
    result = await search_policy(
        query=_build_search_query(state),
        tenant_id=state["tenant_id"],
        user_id=state["user_id"],
        role=state["role"],
        session=session,
        top_k=5,
        doc_type=None,
        risk_level=None,
    )

    data = result.get("data") or {}
    retrieval_failed = result.get("status") == "error"
    gate_triggered = (
        data.get("retrieval_status") == "no_evidence" or float(data.get("best_score") or 0.0) < MIN_EVIDENCE_SCORE
    )
    new_refs = [] if retrieval_failed or gate_triggered else _evidence_refs_from_result(result, retrieved_at)
    merged_refs = _merge_evidence_refs(state.get("evidence_refs"), new_refs)
    output: dict[str, Any] = {
        "retrieved_evidence": result,
        "trace_steps": (state.get("trace_steps") or [])
        + [_trace_step("error" if retrieval_failed else "completed", started_at, new_refs)],
        "evidence_refs": merged_refs,
    }
    if retrieval_failed:
        error = result.get("error") or {}
        output["recommendation_draft"] = _retrieval_error_draft(error)
        output["node_errors"] = (state.get("node_errors") or []) + [
            {"node": "retrieve_policy_evidence", "error": error, "retry_count": 0}
        ]
    elif gate_triggered:
        output["recommendation_draft"] = _insufficient_evidence_draft()
    return output
```

**Evidence sanitization extraction pattern** (`/Users/ming/projects/MOCA/src/agent/nodes/retrieve_policy_evidence.py` lines 72-89):
```python
def _evidence_refs_from_result(result: dict[str, Any], retrieved_at: str) -> list[dict[str, Any]]:
    data = result.get("data") or {}
    refs: list[dict[str, Any]] = []
    for item in data.get("evidence") or []:
        doc_key = item.get("doc_key")
        chunk_id = item.get("chunk_id")
        if not doc_key or not chunk_id:
            continue
        refs.append(
            {
                "doc_key": str(doc_key),
                "chunk_id": str(chunk_id),
                "title": item.get("title"),
                "confidence": item.get("score"),
                "retrieved_at": retrieved_at,
            }
        )
    return refs
```

**Disallowed write path boundary reference** (`/Users/ming/projects/MOCA/src/agent/nodes/execute_action.py` lines 63-75, 84-99):
```python
if risk.get("approval_required") and approval.get("decision") != "approve":
    return {
        "action_result": {
            "status": "error",
            "data": {},
            "error": {
                "error_code": "NOT_APPROVED",
                "message": "Action requires approval but was not approved",
                "retryable": False,
            },
        },
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
    }

result = await create_coupon_grant_draft(
    tenant_id=state.get("tenant_id", ""),
    user_id=state.get("user_id", ""),
    run_id=run_id,
    approval_request_id=approval.get("approval_id"),
    idempotency_key=idempotency_key,
    action_type=action_type,
    payload=proposed,
    session=session,
)
```

**What to copy:** Build `ToolRegistry.invoke(...)` as a thin async boundary that validates first, calls underlying adapter only after allowlist/schema checks, and always returns structured result objects rather than raising on routine invalid requests.

---

### `src/agent/tools/adapters.py` (utility, request-response)

**Analog:** `src/agent/nodes/load_business_context.py`

**Adapter call-shape pattern** (`/Users/ming/projects/MOCA/src/agent/nodes/load_business_context.py` lines 31-73):
```python
async def load_business_context(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable["session"]
    tenant_id = state["tenant_id"]
    user_id = state["user_id"]
    role = state["role"]
    intent = state.get("current_intent") or "unknown"
    extracted_slots = state.get("extracted_slots") or {}
    has_current_identifier = any(extracted_slots.get(key) for key in ("order_id", "refund_case_id", "ticket_id"))
    slots = extracted_slots if has_current_identifier else state.get("active_slots") or {}
    ctx: dict[str, Any] = {}
    refs: dict[str, Any] = {"loaded_at": _now_iso()}
    results: list[dict[str, Any]] = []
    tools_called: list[str] = []

    should_load_context = intent in {"refund_troubleshooting", "compensation_suggestion"} or has_current_identifier

    if should_load_context:
        if slots.get("order_id"):
            tools_called.append("get_order")
            result = await get_order(slots["order_id"], tenant_id, user_id, role, session)
            results.append({"tool": "get_order", **result})
            if result.get("status") == "success":
                ctx["order"] = result["data"]
                refs["order_id"] = slots["order_id"]
```

**Existing raw tool signature pattern** (`/Users/ming/projects/MOCA/src/agent/tools/get_order.py` lines 29-35):
```python
async def get_order(
    order_no: str,
    tenant_id: str,
    user_id: str,
    role: str,
    session: AsyncSession,
) -> dict:
```

**Search adapter signature pattern** (`/Users/ming/projects/MOCA/src/agent/tools/search_policy.py` lines 30-39):
```python
async def search_policy(
    query: str,
    tenant_id: str,
    user_id: str,
    role: str,
    session: AsyncSession,
    top_k: int = 5,
    doc_type: str | None = None,
    risk_level: str | None = None,
) -> dict:
```

**What to copy:** Adapters should accept typed Pydantic input models, unpack validated fields, then call existing async tool functions with explicit `tenant_id`, `user_id`, `role`, and `session` from context. Keep existing tool functions unchanged.

---

### `src/agent/schemas.py` (model, transform)

**Analog:** `src/agent/schemas.py`

**Current local schema style** (`/Users/ming/projects/MOCA/src/agent/schemas.py` lines 29-62):
```python
class EvidenceRefSchema(BaseModel):
    doc_key: str = Field(description="Exact doc_key copied from one retrieved evidence item.")
    chunk_id: str = Field(description="Exact chunk_id copied from the same retrieved evidence item.")
    title: str = Field(description="Exact title copied from the same retrieved evidence item.")
    section: str = Field(description="Exact section copied from the same retrieved evidence item.")

class RecommendationDraft(BaseModel):
    recommended_action: str
    reasoning_summary: str
    evidence_refs: list[EvidenceRefSchema] = Field(
        min_length=1,
        description=(
            "At least one citation object copied from retrieved evidence. "
            "Do not return strings, doc_key-only values, or chunk_id-only values."
        ),
    )
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high"]
    missing_info: list[str] = Field(default_factory=list)

class RiskAssessment(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    risk_reason: str
    approval_required: bool
    rule_ref: str | None = None
```

**What to copy:** Add `InvestigationResult` adjacent to these structured output models, using the same `BaseModel` + `Literal` + bounded `Field` style. Reuse `EvidenceRefSchema` rather than inventing a parallel citation model.

---

### `src/agent/state.py` (model, request-response)

**Analog:** `src/agent/state.py`

**TypedDict optional-field pattern** (`/Users/ming/projects/MOCA/src/agent/state.py` lines 8-18, 26-41):
```python
class ActiveSlots(TypedDict, total=False):
    order_id: str | None
    refund_case_id: str | None
    ticket_id: str | None
    merchant_id: str | None
    customer_id: str | None
    issue_type: str | None

class EvidenceRef(TypedDict, total=False):
    doc_key: str
    chunk_id: str
    title: str
    confidence: float
    retrieved_at: str

class AgentState(TypedDict, total=False):
    """LangGraph state contract split into persistent and ephemeral fields."""
```

**Existing field grouping pattern** (`/Users/ming/projects/MOCA/src/agent/state.py` lines 44-77):
```python
    # Persistent memory: survives across turns via the checkpointer.
    thread_id: str
    tenant_id: str
    user_id: str
    role: str
    active_slots: ActiveSlots
    last_intent: str | None
    last_recommendation_summary: LastRecommendationSummary | None
    evidence_refs: list[EvidenceRef]
    last_business_context_refs: LastBusinessContextRefs | None

    # Ephemeral context: reset by receive_request at the start of each turn.
    user_query: str | None
    normalized_query: str | None
    current_intent: str | None
    extracted_slots: dict[str, Any] | None
    business_context: dict[str, Any] | None
    retrieved_evidence: dict[str, Any] | None
    recommendation_draft: dict[str, Any] | None
    risk_assessment: dict[str, Any] | None

    # Phase 4: approval workflow fields.
    proposed_action: dict[str, Any] | None
    approval_result: dict[str, Any] | None
    action_result: dict[str, Any] | None

    final_response: str | None
    tool_results: list[dict[str, Any]] | None
    llm_outputs: dict[str, Any] | None
    node_errors: list[dict[str, Any]] | None
    retry_count: int | None
    current_run_id: str | None
    trace_steps: list[dict[str, Any]] | None
```

**What to copy:** Add dormant investigation fields as more optional TypedDict keys only. Preserve grouping comments and do not change runtime consumers.

---

### `tests/agent/test_tools/test_tool_contracts.py` (test, transform)

**Analog:** `tests/agent/test_graph.py`

**Pydantic validation assertion pattern** (`/Users/ming/projects/MOCA/tests/agent/test_graph.py` lines 101-117):
```python
class SequencedFakeLLM:
    def __init__(self, responses: Sequence[dict]):
        self._responses = list(responses)
        self._index = 0

    def with_structured_output(self, schema):
        fake = self

        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                response = fake._responses[min(fake._index, len(fake._responses) - 1)]
                fake._index += 1
                if issubclass(schema, BaseModel):
                    return schema.model_validate(response)
                return response

        return _Wrapper()
```

**Literal contract pattern source** (`/Users/ming/projects/MOCA/src/agent/schemas.py` lines 8-18, 51-62):
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

class RiskAssessment(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    risk_reason: str
    approval_required: bool
    rule_ref: str | None = None
```

**What to copy:** Use direct `model_validate(...)` style assertions for schema acceptance/rejection. Keep tests focused on one contract rule each rather than end-to-end registry behavior.

---

### `tests/agent/test_tools/test_registry.py` (test, request-response)

**Analog:** `tests/agent/test_nodes/test_retrieve_policy_evidence.py`

**AsyncMock + monkeypatch structure** (`/Users/ming/projects/MOCA/tests/agent/test_nodes/test_retrieve_policy_evidence.py` lines 35-69):
```python
@pytest.mark.asyncio
async def test_retrieve_policy_evidence_writes_persistent_evidence_refs(monkeypatch, base_state):
    monkeypatch.setattr(
        retrieve_policy_evidence_module,
        "search_policy",
        AsyncMock(return_value=_policy_result(best_score=0.82, evidence=_evidence())),
    )

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {"session": AsyncMock()}},
    )

    assert result["evidence_refs"][0]["doc_key"] == "policy_refund_timeout"
    assert result["evidence_refs"][0]["chunk_id"] == "chunk_001"
    assert result["evidence_refs"][0]["title"] == "退款超时规则"
    assert result["evidence_refs"][0]["confidence"] == 0.82
    assert result["evidence_refs"][0]["retrieved_at"]
    assert result["trace_steps"][-1]["evidence_refs"][0]["doc_key"] == "policy_refund_timeout"
    assert result["trace_steps"][-1]["evidence_refs"][0]["chunk_id"] == "chunk_001"
```

**Non-execution / call-count assertion pattern** (`/Users/ming/projects/MOCA/tests/agent/test_graph.py` lines 128-145, 166-182):
```python
def _patch_graph_dependencies(...):
    get_order = AsyncMock(...)
    search_policy = AsyncMock(return_value=search_result or _policy_result())
    ...
    monkeypatch.setattr(load_business_context_module, "get_order", get_order)
    ...
    monkeypatch.setattr(retrieve_policy_evidence_module, "search_policy", search_policy)
    return {"get_order": get_order, "search_policy": search_policy}

...

mocks["search_policy"].assert_awaited_once()
```

**What to copy:** Registry tests should use `AsyncMock` to prove disallowed/invalid invocations do not await the underlying adapter. Keep one behavior per test: allowlist set, exclusion, validation failure, not-found, disallowed caller, invalid input, sanitization.

---

### `tests/agent/test_tools/test_tool_adapters.py` (test, request-response)

**Analog:** `tests/agent/test_tools/test_get_order.py`

**Local patch helper pattern** (`/Users/ming/projects/MOCA/tests/agent/test_tools/test_get_order.py` lines 31-34):
```python
def _patch_repo(monkeypatch: pytest.MonkeyPatch, result=None, side_effect=None):
    repo = SimpleNamespace(get_with_hints=AsyncMock(return_value=result, side_effect=side_effect))
    monkeypatch.setattr("src.agent.tools.get_order.OrderRepository", lambda session: repo)
    return repo
```

**Focused async test pattern** (`/Users/ming/projects/MOCA/tests/agent/test_tools/test_get_order.py` lines 47-66):
```python
@pytest.mark.asyncio
async def test_get_order_success(monkeypatch):
    _patch_repo(
        monkeypatch,
        result={
            "order": _order(),
            "relation_hints": {
                "has_active_refund": True,
                "latest_refund_case_id": uuid4(),
                "has_open_ticket": False,
                "latest_ticket_id": None,
            },
        },
    )

    result = await get_order("ORD-001", str(uuid4()), str(uuid4()), "support_agent", AsyncMock())

    assert result["status"] == "success"
    assert "order_no" in result["data"]
```

**Retriever patch pattern for search adapter** (`/Users/ming/projects/MOCA/tests/agent/test_tools/test_search_policy.py` lines 24-29):
```python
def _patch_retriever(monkeypatch: pytest.MonkeyPatch, result: RetrievalResult):
    retriever = SimpleNamespace(search=AsyncMock(return_value=result))
    monkeypatch.setattr("src.agent.tools.search_policy.PolicyChunkRepository", lambda session: object())
    monkeypatch.setattr("src.agent.tools.search_policy.EmbeddingService", lambda: object())
    monkeypatch.setattr("src.agent.tools.search_policy.Retriever", lambda chunk_repo, embedder: retriever)
    return retriever
```

**What to copy:** Adapter tests should patch the wrapped tool function itself with `AsyncMock`, pass a typed context object plus typed input model, and assert exact forwarding of `tenant_id`, `user_id`, `role`, `session`, plus tool-specific parameters.

## Shared Patterns

### Tool result shape
**Sources:**
- `/Users/ming/projects/MOCA/src/agent/tools/get_order.py` lines 12-26
- `/Users/ming/projects/MOCA/src/agent/tools/get_refund_case.py` lines 12-26
- `/Users/ming/projects/MOCA/src/agent/tools/get_ticket.py` lines 12-26
- `/Users/ming/projects/MOCA/src/agent/tools/search_policy.py` lines 13-27

```python
def _tool_success(data: dict) -> dict:
    return {"status": "success", "data": data, "error": {}}


def _tool_error(error_code: str, message: str, retryable: bool, should_stop: bool = False) -> dict:
    return {
        "status": "error",
        "data": {},
        "error": {
            "error_code": error_code,
            "message": message,
            "retryable": retryable,
            "should_stop": should_stop,
        },
    }
```

**Apply to:** `src/agent/tools/adapters.py`, `src/agent/tools/registry.py`

Use this as the internal raw tool contract baseline. Registry should translate from this raw dict shape into prompt-facing `ToolExecutionResult` without exposing raw `data` wholesale.

### Read-only tool auth and tenant scoping
**Sources:**
- `/Users/ming/projects/MOCA/src/agent/tools/get_order.py` lines 53-67
- `/Users/ming/projects/MOCA/src/agent/tools/get_refund_case.py` lines 56-70
- `/Users/ming/projects/MOCA/src/agent/tools/get_ticket.py` lines 61-75

```python
if not await merchant_can_access(
    session,
    tenant_id=tenant_uuid,
    user_id=user_id,
    role=role,
    merchant_id=order.merchant_id,
):
    return _tool_error(
        "FORBIDDEN",
        "Merchant access is limited to the merchant's own orders",
        retryable=False,
        should_stop=True,
    )
```

**Apply to:** `src/agent/tools/adapters.py`, `src/agent/tools/registry.py`

Do not bypass this logic in adapters. Adapters should delegate to existing tools so existing authz behavior remains authoritative.

### Evidence-ref sanitization
**Source:** `/Users/ming/projects/MOCA/src/agent/nodes/retrieve_policy_evidence.py` lines 72-89

```python
for item in data.get("evidence") or []:
    doc_key = item.get("doc_key")
    chunk_id = item.get("chunk_id")
    if not doc_key or not chunk_id:
        continue
    refs.append(
        {
            "doc_key": str(doc_key),
            "chunk_id": str(chunk_id),
            "title": item.get("title"),
            "confidence": item.get("score"),
            "retrieved_at": retrieved_at,
        }
    )
```

**Apply to:** `src/agent/tools/registry.py`, `src/agent/schemas.py`

Registry success sanitization should extract `evidence_refs` from raw retrieval output using this pattern and omit raw evidence `text`.

### Unsafe write/action boundary
**Sources:**
- `/Users/ming/projects/MOCA/src/agent/nodes/execute_action.py` lines 56-100
- `/Users/ming/projects/MOCA/src/agent/tools/create_coupon_grant_draft.py` lines 22-54

```python
async def create_coupon_grant_draft(
    *,
    tenant_id: str,
    user_id: str,
    run_id: str,
    approval_request_id: str | None,
    idempotency_key: str,
    action_type: str,
    payload: dict,
    session: AsyncSession,
) -> dict:
```

**Apply to:** `src/agent/tools/contracts.py`, `src/agent/tools/registry.py`, `tests/agent/test_tools/test_registry.py`

This is the concrete unsafe/write-side tool signature to exclude from investigator allowlists and to use in explicit exclusion tests.

## No Exact Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/agent/tools/registry.py` | service | request-response | No existing schema-first registry or caller-aware tool boundary exists in the repo yet. Closest partial analog is `retrieve_policy_evidence.py` because it validates tool output shape and derives sanitized `evidence_refs`. |
| `src/agent/tools/contracts.py` | utility | transform | No existing tool-contract module exists. Closest analog is `src/agent/schemas.py` because it holds typed Pydantic output contracts. |
| `tests/agent/test_tools/test_tool_contracts.py` | test | transform | No existing dedicated contract-validation test file exists. Closest analog is graph schema validation via `BaseModel.model_validate(...)` in `tests/agent/test_graph.py`. |

## Metadata

**Analog search scope:**
- `/Users/ming/projects/MOCA/src/agent/`
- `/Users/ming/projects/MOCA/tests/agent/`
- `/Users/ming/projects/MOCA/tests/test_agent_runs_api.py`

**Files scanned:** 15
**Pattern extraction date:** 2026-06-04
