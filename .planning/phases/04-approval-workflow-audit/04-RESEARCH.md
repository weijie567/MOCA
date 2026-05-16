# Phase 4: Approval Workflow & Audit — Research

**Researched:** 2026-05-16
**Status:** Complete

## 1. LangGraph interrupt() / Command(resume=...) API

### Version Compatibility
- Project uses `langgraph>=0.4` with `langgraph-checkpoint-postgres>=2.0`
- `interrupt()` is imported from `langgraph.types`
- `Command` is imported from `langgraph.types`

### Core Pattern: interrupt() Inside a Node

```python
from langgraph.types import interrupt, Command

async def approval_gate(state: AgentState) -> dict:
    # Prepare the payload surfaced to the client
    approval_payload = {
        "approval_id": str(approval_request_id),
        "proposed_action": state["proposed_action"],
        "risk_level": state["risk_assessment"]["risk_level"],
        "risk_reason": state["risk_assessment"]["risk_reason"],
    }
    
    # This pauses execution — checkpointer saves state
    decision = interrupt(approval_payload)
    
    # When resumed via Command(resume=decision_payload), 
    # `decision` receives that payload
    return {"approval_result": decision}
```

### Resume Pattern: Command(resume=payload)

```python
from langgraph.types import Command

# Resume with structured decision payload
result = await graph.ainvoke(
    Command(resume={
        "approval_id": "...",
        "decision": "approve",
        "reason": "Within policy",
        "decided_by": "user-uuid",
        "decided_at": "2026-05-16T10:00:00Z",
    }),
    config={"configurable": {"thread_id": thread_id}},
)
```

### Detecting Interrupted State

```python
state_snapshot = await graph.aget_state(config)
if state_snapshot.next:
    # Graph is paused — state_snapshot.next contains the node(s) waiting
    # For our case: ("approval_gate",)
    pass
```

### Key Findings
1. `interrupt()` return value IS the `Command(resume=...)` payload — no separate state update needed
2. Checkpointer (PostgresSaver) automatically persists interrupted state — survives server restarts
3. Same `thread_id` config is used for both initial invoke and resume invoke
4. The graph re-enters the interrupted node from the beginning, but `interrupt()` returns immediately with the resume value on the second pass

## 2. Conditional Edges for Graph Topology

### Current State
- `src/agent/graph.py`: Linear 8-node chain with `add_edge()` only
- No conditional routing exists

### Required Topology Change (per D-03b)

```python
from langgraph.graph import END, START, StateGraph

def route_after_risk(state: AgentState) -> str:
    risk = state.get("risk_assessment") or {}
    if not risk.get("approval_required"):
        # No action needed OR action allowed without approval
        if state.get("proposed_action"):
            return "execute_action"
        return "final_response"
    return "approval_gate"

def route_after_approval(state: AgentState) -> str:
    result = state.get("approval_result") or {}
    if result.get("decision") == "approve":
        return "execute_action"
    return "final_response"  # rejected — explain in final_response

builder.add_conditional_edges(
    "assess_risk_and_approval",
    route_after_risk,
    {"approval_gate": "approval_gate", "execute_action": "execute_action", "final_response": "final_response"},
)
builder.add_conditional_edges(
    "approval_gate",
    route_after_approval,
    {"execute_action": "execute_action", "final_response": "final_response"},
)
builder.add_edge("execute_action", "final_response")
```

### Impact on Existing Tests
- All Phase 3 tests use the linear graph — they will need the graph to still work for low-risk paths (no approval needed → final_response)
- The conditional edge must default to `final_response` when no `proposed_action` exists (backward compatible with Phase 3 read-only queries)

## 3. State Extensions Required

### New Fields for AgentState (per D-02, D-03)

```python
class AgentState(TypedDict, total=False):
    # ... existing fields ...
    
    # Phase 4 additions:
    proposed_action: dict[str, Any] | None      # From assess_risk: what action to take
    approval_result: dict[str, Any] | None      # From approval_gate: decision payload
    action_result: dict[str, Any] | None        # From execute_action: outcome
```

### Backward Compatibility
- All new fields use `total=False` and default to `None`
- Phase 3 flows never set `proposed_action`, so `route_after_risk` returns `"final_response"` — preserving existing behavior

## 4. Database Schema Extensions

### New Tables (per D-04)

**approval_requests:**
- id (UUID PK)
- run_id (UUID FK → agent_runs.id)
- tenant_id (UUID, indexed)
- status (String: pending/approved/rejected/expired/cancelled)
- requested_by (UUID FK → users.id)
- assigned_to (UUID FK → users.id, nullable)
- proposed_action (JSONB)
- risk_level (String)
- risk_rule_ref (String)
- risk_reason (String)
- decision (String, nullable)
- reason (Text, nullable)
- decided_by (UUID, nullable)
- decided_at (DateTime, nullable)
- expires_at (DateTime)
- created_at, updated_at (TimestampMixin)

**approval_steps:**
- id (UUID PK)
- approval_request_id (UUID FK → approval_requests.id)
- event_type (String: created/viewed/approved/rejected/expired/resumed)
- actor_id (UUID, nullable)
- metadata_json (JSONB)
- created_at (DateTime)

**action_drafts:**
- id (UUID PK)
- run_id (UUID FK → agent_runs.id)
- approval_request_id (UUID FK → approval_requests.id, nullable)
- tenant_id (UUID, indexed)
- idempotency_key (String, unique)
- action_type (String)
- status (String: draft_created/failed/cancelled)
- payload (JSONB)
- created_by_agent_run (UUID)
- created_at (DateTime)

### Existing Table Extensions

**agent_steps:** Add columns:
- `provider_latency_ms` (Integer, nullable) — LLM provider call time
- `retry_count` (Integer, nullable, default 0)
- `metrics_json` (JSONB, nullable) — model, provider, prompt_tokens, completion_tokens, context_chars

**agent_runs:** Add column:
- `final_status` values extended: "interrupted", "expired" (in addition to existing "completed", "error", "insufficient_evidence")

## 5. Latency Instrumentation Strategy

### Current State
- `trace_steps` list already captures `started_at`, `completed_at`, `model_name`, `prompt_tokens`, `completion_tokens` per node
- `AgentStep.latency_ms` column already exists but is computed from timestamps
- No `provider_latency_ms` or `retry_count` tracked

### Implementation Approach (per D-01)
1. Wrap `_get_llm()` calls to capture provider-level timing:
   ```python
   t0 = time.perf_counter()
   result = await structured_llm.ainvoke(messages)
   provider_latency_ms = round((time.perf_counter() - t0) * 1000)
   ```
2. Add `provider_latency_ms`, `retry_count`, `metrics_json` to each `_trace_step()` dict
3. `write_agent_steps()` already maps these fields — just need the DB columns
4. Diagnostic script reads `agent_steps` table, aggregates by `node_name`, identifies bottleneck

### Diagnostic Script Output Format
```json
{
  "run_id": "...",
  "total_latency_ms": 95000,
  "nodes": [
    {"node": "classify_intent", "latency_ms": 12000, "provider_latency_ms": 11500, "retry_count": 0},
    {"node": "generate_recommendation", "latency_ms": 35000, "provider_latency_ms": 34000, "retry_count": 1}
  ],
  "bottleneck": {"node": "generate_recommendation", "pct_of_total": 36.8},
  "suspected_causes": ["high provider latency", "retry detected"]
}
```

## 6. Approval API Design

### Endpoints (per D-02d, D-04e)

| Method | Path | Scope | Purpose |
|--------|------|-------|---------|
| POST | /api/v1/approvals/{id}/decide | approvals:review | Submit approve/reject |
| GET | /api/v1/approvals/{id} | approvals:review | Get approval details |
| GET | /api/v1/approvals | approvals:review | List pending approvals |
| GET | /api/v1/agent-runs/{run_id}/trace | agent:chat | Full execution timeline |

### Decide Endpoint Flow
1. Validate approval exists, status == "pending", not expired
2. Validate caller has `approvals:review` scope + supervisor/admin/approval_manager role
3. Validate caller != requested_by (can't approve own request)
4. Update approval_request: status, decision, reason, decided_by, decided_at
5. Write approval_step event
6. If approved: resume graph via `graph.ainvoke(Command(resume=payload), config)`
7. If rejected: update agent_run status to "completed" (reject is normal completion)
8. Return updated approval + run status

### Idempotency (per D-06a)
- approved + approve → return existing result (idempotent)
- approved + reject → 409 Conflict
- rejected + reject → return existing result (idempotent)
- rejected + approve → 409 Conflict
- expired + any → 409 Conflict

## 7. Write Tool: create_coupon_grant_draft

### Design (per D-03d, D-03e, D-03f)
- Creates a draft record in `action_drafts` table — NOT actual coupon issuance
- Idempotency key: `{run_id}_{approval_id}_{action_type}_{target_id}`
- Returns unified format: `{"status": "success", "data": {"draft_id": "...", "idempotency_key": "..."}}`
- On duplicate key: returns existing draft, marks as `idempotent_reused`

### Integration with execute_action Node
```python
async def execute_action(state: AgentState) -> dict:
    proposed = state["proposed_action"]
    approval = state.get("approval_result") or {}
    
    # Build idempotency key
    key = f"{state['current_run_id']}_{approval.get('approval_id')}_{proposed['action_type']}_{proposed['target_id']}"
    
    # Call write tool
    result = await create_coupon_grant_draft(
        tenant_id=state["tenant_id"],
        user_id=state["user_id"],
        run_id=state["current_run_id"],
        idempotency_key=key,
        payload=proposed,
    )
    
    return {"action_result": result, "trace_steps": [...]}
```

## 8. Testing Strategy

### CI Tests (mock LLM + mock tools, per D-07i)
- Unit tests per new node: `approval_gate`, `execute_action`
- Integration tests for graph topology: high-risk → interrupt → resume → execute
- Idempotency tests: duplicate approve, duplicate draft creation
- State machine tests: all transitions in D-06a
- Latency instrumentation: verify metrics_json populated

### Live Smoke Tests (optional, per D-07j)
- Real DashScope API call → full graph → interrupt → manual resume
- Verify end-to-end latency with real provider

## 9. Migration Strategy

### Alembic Migration Plan
1. Add columns to `agent_steps`: `provider_latency_ms`, `retry_count`, `metrics_json`
2. Create `approval_requests` table
3. Create `approval_steps` table
4. Create `action_drafts` table
5. All new columns nullable or with defaults — no data migration needed
6. `agent_runs.final_status` already String(32) — new values ("interrupted", "expired") are just new enum values at app level, no schema change needed

## 10. Security Considerations

### Threat Model
- **T-01 (High):** Unauthorized approval — mitigated by role check (supervisor/admin/approval_manager) + scope check (approvals:review)
- **T-02 (High):** Self-approval — mitigated by `requested_by != decided_by` check
- **T-03 (Medium):** Replay attack on approve endpoint — mitigated by idempotency (same decision returns same result, conflicting decision returns 409)
- **T-04 (Medium):** Expired approval resume — mitigated by checking `expires_at` before resume
- **T-05 (Low):** Cross-tenant access — mitigated by tenant_id filtering on all queries (existing pattern)

### Existing Security Assets
- `approvals:review` scope already defined in `src/auth/permissions.py`
- `require_roles()` helper already exists for role-based access
- Tenant isolation pattern established in all existing routers

## 11. Dependencies and Risks

### No New Dependencies Required
- `langgraph>=0.4` already supports `interrupt()` and `Command`
- `langgraph-checkpoint-postgres>=2.0` already supports async PostgresSaver with interrupt persistence
- SQLAlchemy, Alembic, FastAPI — all existing

### Risks
1. **LangGraph interrupt behavior with async:** All existing nodes are async — `interrupt()` works in async context (confirmed in docs)
2. **PostgresSaver thread_id format:** Current code uses `_checkpoint_thread_id()` helper — resume must use same format
3. **Graph recompilation:** Adding conditional edges changes the compiled graph — existing tests need the new graph shape
4. **Latency amplification:** Adding approval_gate + execute_action adds 2 more nodes — but they're non-LLM nodes (fast)

---

## RESEARCH COMPLETE
