# Phase 10: State Lifecycle + Routing Migration - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 8 new/modified (state.py, graph.py, routing.py, investigate.py, receive_request.py, events.py, models.py, 006 migration) + 4 test files
**Analogs found:** 11 / 12 (case_memory / event-emitter has only a partial in-repo analog — see No Analog Found)

> All excerpts below are from the live repo at the cited path:line. This phase is a **migration of existing code**, not greenfield — most "new" files have a strong in-repo analog because the target collapses/relocates code that already exists. Read `docs/contract-spec.md` (§8.4, §9.0–9.5, §10.1, §10.4, §12.4, §17.2) as the normative contract; the analogs below show the *house style* to copy, not the target behavior.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/state.py` | model (TypedDict contract) | transform | self (extend in place) — `src/agent/state.py:48-91` | exact |
| `src/agent/nodes/receive_request.py` | node (per-turn reset) | transform | self (extend reset dict) — `src/agent/nodes/receive_request.py:28-53` | exact |
| `src/agent/routing.py` (NEW) | router (pure functions) | transform | `src/agent/graph.py:36-52` (`route_after_risk`/`route_after_approval`) | exact |
| `src/agent/graph.py` | config (graph assembly) | event-driven | self (`build_graph` + `add_conditional_edges`) — `src/agent/graph.py:55-97` | exact |
| `src/agent/nodes/investigate.py` (NEW) | node (bounded tool loop) | request-response (iterated) | `load_business_context.py` (tool calls) + `retrieve_policy_evidence.py` (RAG + status) | role-match (merge of two) |
| `src/agent/events.py` (NEW) | service (event emitter + sequence allocator) | event-driven | `src/agent/trace.py:51-91` (`write_agent_steps` append/flush) | role-match |
| `src/db/models.py` (`AgentTraceEvent` NEW) | model (ORM table) | CRUD | `src/db/models.py:308-339` (`AgentStep`) | exact |
| `src/db/migrations/versions/006_*.py` (NEW) | migration | DDL | `src/db/migrations/versions/005_approval_tables.py` | exact |
| `tests/test_graph_routing.py` (EXTEND) | test | — | self — `tests/test_graph_routing.py:6-43` | exact |
| `tests/agent/test_nodes/test_investigate.py` (NEW) | test | — | `tests/agent/test_nodes/test_retrieve_policy_evidence.py` + `test_receive_request.py` | role-match |
| `tests/test_state_lifecycle.py` (NEW) | test | — | `tests/agent/test_nodes/test_receive_request.py:8-40` | role-match |
| `tests/agent/test_events.py` (NEW) | test | — | (no event-emitter test exists — pattern from `tests/agent/test_trace.py`) | partial |

## Pattern Assignments

### `src/agent/routing.py` (NEW — router, pure functions) — ROUTE-01/02

**Analog:** `src/agent/graph.py:36-52` — the two existing routers are already pure, side-effect-free, `state -> str`. Copy this shape exactly for the 5 new routers (`route_after_intent`, `route_after_slots`, `route_after_investigate`, and any Phase-10-owned remainder). RESEARCH recommends extracting routers into `routing.py` so they are unit-importable; the existing routers currently live in `graph.py` and are imported by tests as `from src.agent.graph import route_after_risk` (`tests/test_graph_routing.py:3`). If you move them, keep a re-export in `graph.py` or update the test import.

**Core router pattern** (`src/agent/graph.py:36-44`):
```python
def route_after_risk(state: AgentState) -> str:
    """Route based on risk assessment and proposed action."""
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action")
    if risk.get("approval_required"):
        return "approval_gate"
    if proposed:
        return "execute_action"
    return "final_response"
```

**Mandatory conventions to copy:**
- Read state defensively with `state.get(key) or {}` / `or default` — never index. This is what makes the router **total** for partial/old-checkpoint state (state is `total=False`, `src/agent/state.py:48`).
- Return only string literals that appear as keys in the corresponding `add_conditional_edges` mapping (`graph.py:80-84`). ROUTE-01 totality test = every branch returns a key present in that dict.
- Last `return` is the unconditional **safe default** (ROUTE-02). For `route_after_investigate` the safe-final default is the insufficient/error path (contract-spec.md:389); for `route_after_intent`/`route_after_slots` it is `clarification_gate` (which may be a Phase-10 stub — see Open Questions in RESEARCH).
- No `await`, no service/DB calls, no `config` param — routers take `state` only. (Contrast the nodes below, which take `(state, config)`.)

**`route_after_investigate` reads STATE only (D-11):** it must read `termination_reason`, `retrieval_status`, `best_score`, `business_context.errors`/`missing_required_facts` from state — never from trace payload. Model permission-denial fine-grained (D-08): separate `errors` (denied/failed resources) from `facts` present, as `BusinessContextV1` already carries both (contract-spec.md:173-177). Do not collapse to one boolean.

---

### `src/agent/nodes/investigate.py` (NEW — node, bounded tool loop) — D-03/D-04/D-06/D-08

**Analogs (merge of two live nodes):** `src/agent/nodes/load_business_context.py` (read-tool calls + `tool_results`) and `src/agent/nodes/retrieve_policy_evidence.py` (RAG via `PolicyKnowledgeService` + `retrieval_status`/`best_score`). The new node absorbs both; the loop iterates tool selection instead of the current fixed `if slots.get(...)` chain.

**Node signature + trusted-context read** (`load_business_context.py:31-38` — identity from STATE, session from config, never from LLM):
```python
async def load_business_context(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable["session"]
    tenant_id = state["tenant_id"]
    user_id = state["user_id"]
    role = state["role"]
    intent = state.get("current_intent") or "unknown"
```
Copy this verbatim for STATE-02: `tenant_id/user_id/role` come from trusted state keys, `session`/`merchant_scope` from `config["configurable"]` (`retrieve_policy_evidence.py:93-98`). The LLM loop must never write these.

**Read-tool call pattern the loop wraps** (`load_business_context.py:50-56`) — note the uniform tool-result contract and per-resource success gating:
```python
if slots.get("order_id"):
    tools_called.append("get_order")
    result = await get_order(slots["order_id"], tenant_id, user_id, role, session)
    results.append({"tool": "get_order", **result})
    if result.get("status") == "success":
        ctx["order"] = result["data"]
        refs["order_id"] = slots["order_id"]
```
The loop replaces the fixed chain with bounded tool selection from the §12.4 allowlist (D-04). Keep the allowlist as a hard manager-visible contract; reject any tool not in it (D-04/D-06 — never a write tool). `investigate` must call one node-facing `UnifiedToolManager.invoke(...)` path. Business fact tools are delegated by the manager to `BusinessToolService.invoke_tool(...)`; policy evidence is delegated by a knowledge executor to `PolicyKnowledgeService.search`; future memory tools remain declared-but-unavailable. Tools without repo backing should surface as unavailable through the same manager contract — do not build them in Phase 10.

**RAG retrieval + status mapping** (`retrieve_policy_evidence.py:125-130`):
```python
service = PolicyKnowledgeService(LegacyRagKnowledgeAdapter(session))
result = await service.search(request, context)
retrieval_failed = result.status == "error"
gate_triggered = result.status == "no_evidence" or result.best_score < MIN_EVIDENCE_SCORE
# result.status ∈ {strong_evidence | partial_evidence | no_evidence | error} → §10.1 retrieval_status
```
`result.status`/`result.best_score` feed the state fields `retrieval_status`/`best_score`. **Do not** force `retrieval_status=no_evidence` when `max_iterations` is hit — that is `termination_reason`, a separate field (RESEARCH Anti-Patterns; contract-spec.md:183,374).

**Return-dict / state-merge convention** (`retrieve_policy_evidence.py:132-137`) — append to list fields, never clobber:
```python
output: dict[str, Any] = {
    "retrieved_evidence": result.model_dump(),
    "trace_steps": (state.get("trace_steps") or []) + [_trace_step(...)],
    "evidence_refs": merged_refs,
}
```
**Hard rule (Anti-Pattern):** `investigate` writes `business_context`, `policy_evidence`/`retrieved_evidence`, `retrieval_status`, `best_score`, `case_memory`, `tool_results`, `termination_reason` — but **never `evidence_refs`** as authoritative citations; that stays with `recommendation_generation`/citation validator (contract-spec.md:378,624). (Note `retrieve_policy_evidence.py:131` currently does merge `evidence_refs` — the merge node behavior here is governed by spec §10.1, confirm with planner.)

**max_iterations (D-03/D-12):** hard cap read per-intent (GAD-02 field) with a global ceiling backstop. On cap: keep lifecycle status `completed`, write `termination_reason="max_iterations_reached"`. Pick concrete default/ceiling at plan time (D-12 discussion-only 3/5 are not normative).

---

### `src/agent/nodes/receive_request.py` (MODIFY — per-turn reset) — STATE-01

**Analog:** itself. The reset dict at `receive_request.py:28-53` already nulls every ephemeral field. The Phase-10 task is to **add the new §10.1 ephemeral fields to this dict in lockstep with the TypedDict additions** so stale context cannot leak across turns (cross-scope isolation, STATE-01).

**Current reset shape** (`receive_request.py:28-49`):
```python
return {
    "user_query": state.get("user_query"),
    "normalized_query": None,
    "current_intent": None,
    "business_context": None,
    "retrieved_evidence": None,
    ...
    "current_run_id": state.get("current_run_id") or str(uuid4()),
    "run_started_at": started_at,
    "trace_steps": trace_steps,
}
```
Add `termination_reason`, `retrieval_status`, `best_score`, `policy_evidence`, `case_memory` (and `primary_intent`/`requested_operation` if the rename lands — RESEARCH Pitfall 4, hand to Codex as one atomic edit). Preserve the two carried-forward keys exactly: `user_query` (passthrough) and `current_run_id` (preserve-or-mint). The dormant Phase-7 `investigation_*` fields (`receive_request.py:41-44`) may be repurposed/removed per spec.

---

### `src/agent/state.py` (MODIFY — TypedDict contract) — STATE-01

**Analog:** itself. Add new ephemeral fields in the `# Ephemeral context` block (`state.py:62-71`) following the existing `field: type | None` style. Keep `total=False` (`state.py:48`) — this is what makes added fields default-absent and tolerant of old checkpoints (RESEARCH Runtime State Inventory A5). Persistent vs ephemeral split is load-bearing: identity fields `thread_id/tenant_id/user_id/role` (`state.py:52-55`) are the trusted-replace-only group (STATE-02) — do not move them into the ephemeral/reset set.

---

### `src/agent/graph.py` (MODIFY — graph assembly)

**Analog:** itself — `build_graph` (`graph.py:55-97`). Register the new `investigate` node and replace the linear edges `load_business_context → retrieve_policy_evidence → generate_recommendation` (`graph.py:73-76`) with `investigate → route_after_investigate`.

**conditional-edges pattern to copy** (`graph.py:77-85`) — the router's return strings MUST match these dict keys exactly (ROUTE-01):
```python
builder.add_conditional_edges(
    "assess_risk_and_approval",
    route_after_risk,
    {
        "approval_gate": "approval_gate",
        "execute_action": "execute_action",
        "final_response": "final_response",
    },
)
```
Fallback targets that belong to later phases (`clarification_gate` = Phase 11) need a minimal stub node so the mapping is valid (RESEARCH Open Question 2). LLM nodes get `retry_policy=_llm_retry` (`graph.py:33,60`); the `investigate` loop owns its own iteration, so decide whether node-level RetryPolicy applies or the loop handles retries internally.

---

### `src/db/models.py` — `AgentTraceEvent` (NEW ORM model) + `006` migration — 10c, §17.2

**Model analog:** `AgentStep` (`src/db/models.py:308-339`). Copy the column conventions: `UUID(as_uuid=True)` PK with `default=uuid.uuid4`, `run_id` FK to `agent_runs.id` with `index=True`, `JSONB` for payload (here: `redacted_payload`), `TimestampMixin` base. Add the §17.2-owned columns: a strictly-monotonic `sequence` per `run_id`, `event_type` (`tool_call_*` / `rag_retrieval_*`, D-09/D-10), and the `redacted_payload` JSONB carrying `iteration` (CD-02). `redacted_payload` must hold no raw tool output / secret / PII (§17.2).

**Migration analog:** `src/db/migrations/versions/005_approval_tables.py`. Copy verbatim: the revision header block (`revision`/`down_revision`/`branch_labels`/`depends_on`, lines 17-20 — set `down_revision = "005_approval_tables"`), `op.create_table` with `postgresql.UUID`/`JSONB`/`sa.func.now()` server defaults, `op.create_index` on `run_id` and `tenant_id`, and a symmetric `downgrade()` that drops indexes then table. For the monotonic per-run sequence add a `UniqueConstraint(run_id, sequence)` (analog: `uq_action_drafts_idempotency_key`, line 82) so the allocator's monotonicity is DB-enforced.

---

### `src/agent/events.py` (NEW — emitter + sequence allocator) — 10c, D-05

**Analog:** `src/agent/trace.py:51-91` (`write_agent_steps`). Copy the async-session insert/flush pattern: build the ORM row, `session.add(row)`, `await session.flush()`. For the allocator, the spec requires "strictly monotonic per `run_id`, continues after resume" — the `enumerate(..., start=start_index)` resume pattern in `append_agent_steps` (`trace.py:126`) is the in-repo precedent for "continue numbering after resume," but a counter in Python is not concurrency-safe; use a DB-side sequence (e.g. `SELECT max(sequence)+1 ... FOR UPDATE` or a Postgres sequence) and let the `UniqueConstraint` above be the backstop. Emit one event per loop tool/RAG call (D-05), classified by call nature (D-09): `get_* → tool_call_*`, `search_* → rag_retrieval_*`, `search_case_memory → rag_retrieval_*` (D-10). A single op emits exactly one event family — never both.

## Shared Patterns

### Trusted context from `config["configurable"]`, never from LLM/state-merge (STATE-02)
**Source:** `src/agent/nodes/load_business_context.py:33-37`, `retrieve_policy_evidence.py:93-98`
**Apply to:** `investigate.py`, and the STATE-02 tests.
```python
configurable = config.get("configurable") or {}
session = configurable["session"]
tenant_id = state["tenant_id"]   # trusted state key
user_id = state["user_id"]
role = state["role"]
merchant_scope = configurable.get("merchant_scope")
```
Identity/scope is injected by the API/auth boundary, read by nodes, and must never be writable by LLM output. Tests must assert an LLM/user-supplied `tenant_id`/`role`/`approval_decision` cannot reach these fields.

### Uniform tool-result contract (drives D-08 permission detection)
**Source:** `src/agent/tools/get_order.py:12-26`
**Apply to:** every tool call inside `investigate.py`.
```python
def _tool_success(data: dict) -> dict:
    return {"status": "success", "data": data, "error": {}}

def _tool_error(error_code, message, retryable, should_stop=False) -> dict:
    return {"status": "error", "data": {},
            "error": {"error_code": error_code, "message": message,
                      "retryable": retryable, "should_stop": should_stop}}
```
Permission denial surfaces as `error_code="FORBIDDEN"` with `should_stop=True` (`get_order.py:61-66`). D-08 fine-grained: record the denial per-resource, keep other successful `facts`, and ensure the denied resource neither appears in the reply nor is inferable.

### Trace-step / list-field append convention
**Source:** `load_business_context.py:74-79`, `retrieve_policy_evidence.py:134`
**Apply to:** every node return dict.
```python
"trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at, tools_called)],
```
Never replace list-typed state fields — always read-or-empty then concatenate. `_trace_step` is a per-node local helper (`load_business_context.py:18-28`) that stamps `node`, `status`, `started_at`/`completed_at` via `_now_iso()`.

### Defensive state reads = router/node totality
**Source:** every router (`graph.py:38-39`) and node (`load_business_context.py:38-41`)
**Apply to:** all routers (ROUTE-01) and `investigate`.
`state.get(k) or {}` / `or "unknown"` / `or []` everywhere. Because `AgentState` is `total=False` and old checkpoints lack new keys, indexing (`state[k]`) on an ephemeral key would raise — defensive reads are what make routers total for valid state and safe for invalid/partial state (ROUTE-02).

## Test Patterns

### Router totality/fallback test — `tests/test_graph_routing.py:6-43`
Plain sync functions, construct a partial `state` dict literal, assert the returned key. Extend with: (a) one test per branch of each new router, (b) a totality test that the return value is always in the `add_conditional_edges` mapping, (c) explicit invalid/empty-state → safe-default tests (ROUTE-02). RESEARCH suggests `hypothesis` for fuzzed totality (not currently a dep — decide at plan time; table tests are the fallback).
```python
def test_route_after_risk_returns_final_response_for_policy_qa_no_action():
    state = {"current_intent": "policy_qa",
             "risk_assessment": {"approval_required": False}, "proposed_action": None}
    assert route_after_risk(state) == "final_response"
```

### Reset / lifecycle test — `tests/agent/test_nodes/test_receive_request.py:8-40`
Uses the `base_state` fixture, overlays stale values, calls the async node, asserts ephemeral keys are `None` and `current_run_id` behavior (mint-new vs preserve-API-supplied). Copy this shape for `tests/test_state_lifecycle.py` (STATE-01 reset/isolation) and extend it to assert the **new** ephemeral fields reset to `None`/absent each turn.
```python
@pytest.mark.asyncio
async def test_receive_request_resets_ephemeral(base_state):
    state = {**base_state, "current_intent": "old_intent", "business_context": {"old": "data"}}
    result = await receive_request(state)
    assert result["current_intent"] is None
    assert result["business_context"] is None
```

### Node behavior test — `tests/agent/test_nodes/test_retrieve_policy_evidence.py`
Analog for `test_investigate.py` (D-03/D-04/D-06/D-08): async node test with a fake/seeded session in `config["configurable"]`. The `tests/conftest.py` `seeded_session` already seeds order/refund_case/ticket (RESEARCH Wave-0, conftest.py:183-215) for integration coverage.

## No Analog Found

| File / concern | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `case_memory` retrieval (`search_case_memory`) | service | request-response | No `MemoryService` and no `search_case_memory` tool exist (RESEARCH Env Availability). CD-01 keeps long-term memory separate; case memory is Phase 16 territory — empty/seam only in Phase 10. |
| `tests/agent/test_events.py` (sequence/concurrency) | test | — | No existing test exercises a monotonic per-run sequence allocator. `tests/agent/test_trace.py` is the nearest structural analog for DB-backed trace assertions, but the concurrency/monotonic-after-resume property is net-new (10c). Use spec §17.2 as the contract. |
| `get_logistics` / `get_merchant_risk` / `search_sop` tools | tool | request-response | Do not exist and Phase 10 should NOT build them (RESEARCH Pitfall 2 / A3). Register in the §12.4 allowlist contract as unavailable; analog for *shape* if ever built is `get_order.py`. |
| `UnifiedToolManager` | manager/service adapter | request-response | Plan 04 creates the node-facing unified dispatch layer. `investigate` calls this only; manager executors delegate business reads to `BusinessToolService`, policy retrieval to `PolicyKnowledgeService`, and future memory tools to unavailable/future executors. |
| `BusinessToolService` facade | service | request-response | Phase 9 implemented. It is the business executor dependency behind `UnifiedToolManager`; `investigate` must not import/call it directly and must not bypass it with raw `get_order`/`get_refund_case`/`get_ticket` calls. |

## Metadata

**Analog search scope:** `src/agent/` (graph, state, nodes, tools, trace), `src/db/` (models, migrations/versions), `src/knowledge/service.py`, `tests/` (test_graph_routing, agent/test_nodes, agent/test_trace, conftest)
**Files scanned:** ~14 source/test files read in full or targeted; directory inventories of nodes/tools/migrations/tests
**Pattern extraction date:** 2026-06-11
**Caveat:** This is a migration phase — "new" files largely relocate/merge existing code, so analogs are unusually exact. The behavioral contract is `docs/contract-spec.md` (not the analogs); analogs supply the house coding style only. Field-rename scope (`current_intent→primary_intent`) remains a planning question; the Phase-9 facade dependency is resolved and should be consumed behind the Plan-04 UnifiedToolManager business executor, not directly from `investigate`.
