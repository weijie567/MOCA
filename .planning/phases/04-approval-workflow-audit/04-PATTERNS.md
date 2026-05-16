# Phase 4: Approval Workflow & Audit — Pattern Map

**Generated:** 2026-05-16

## Files to Create/Modify

### New Files

| File | Role | Closest Analog |
|------|------|---------------|
| `src/agent/nodes/approval_gate.py` | Graph node — interrupt + resume | `src/agent/nodes/assess_risk_and_approval.py` |
| `src/agent/nodes/execute_action.py` | Graph node — write tool orchestration | `src/agent/nodes/load_business_context.py` |
| `src/agent/tools/create_coupon_grant_draft.py` | Write tool — draft creation | `src/agent/tools/get_order.py` |
| `src/agent/tools/create_approval_request.py` | Write tool — approval record | `src/agent/tools/get_order.py` |
| `src/api/routers/approvals.py` | REST API — decide + list + get | `src/api/routers/orders.py` |
| `src/api/routers/traces.py` | REST API — run trace/timeline | `src/api/routers/agent.py` |
| `src/repositories/approval_repo.py` | Data access — approval CRUD | `src/repositories/order_repo.py` |
| `src/repositories/action_draft_repo.py` | Data access — draft CRUD | `src/repositories/order_repo.py` |
| `scripts/diagnose_latency.py` | CLI diagnostic script | `scripts/seed_data.py` |
| `tests/test_approval_gate.py` | Unit tests — approval node | `tests/test_assess_risk.py` |
| `tests/test_execute_action.py` | Unit tests — execute node | `tests/test_load_business_context.py` |
| `tests/test_approval_api.py` | Integration tests — approval endpoints | `tests/test_agent_chat.py` |

### Modified Files

| File | Change | Pattern Source |
|------|--------|---------------|
| `src/agent/state.py` | Add `proposed_action`, `approval_result`, `action_result` fields | Existing TypedDict pattern |
| `src/agent/graph.py` | Replace linear edges with conditional edges after `assess_risk_and_approval` | LangGraph `add_conditional_edges` |
| `src/db/models.py` | Add `ApprovalRequest`, `ApprovalStep`, `ActionDraft` models | Existing `AgentRun`/`AgentStep` pattern |
| `src/agent/trace.py` | Extend to handle approval events in timeline | Existing `write_agent_steps` |
| `src/auth/permissions.py` | Add `approvals:decide` scope (or reuse `approvals:review`) | Existing scope dict |
| `src/api/routers/agent.py` | Handle `GraphInterrupt` exception from `ainvoke` | Existing error handling |

## Key Patterns to Follow

### 1. Node Pattern (from `assess_risk_and_approval.py`)
```python
async def node_name(state: AgentState) -> dict:
    started_at = _now_iso()
    # ... logic ...
    return {
        "state_field": value,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(...)],
    }
```

### 2. Tool Pattern (from `get_order.py`)
```python
async def tool_name(tenant_id: str, user_id: str, role: str, session: AsyncSession, ...) -> dict:
    # Returns: {"status": "success"|"error", "data": {...}, "error": {...}}
    return _tool_success(data) or _tool_error(code, msg, retryable)
```

### 3. Router Pattern (from `orders.py`)
```python
router = APIRouter(tags=["approvals"])

@router.post("/{id}/decide", response_model=ApiResponse)
async def decide(
    id: str,
    body: DecideRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    ...
```

### 4. Model Pattern (from `AgentRun`)
```python
class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # ... fields ...
```

### 5. Repository Pattern (from `OrderRepository`)
```python
class ApprovalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, approval_id: UUID, tenant_id: UUID) -> ApprovalRequest | None:
        ...
```

## Data Flow

```
assess_risk_and_approval
  → sets: risk_assessment, proposed_action (if action needed)
  → routes to: approval_gate | execute_action | final_response

approval_gate (if approval_required)
  → creates: approval_request record
  → calls: interrupt(payload)
  → on resume: receives decision → sets approval_result
  → routes to: execute_action | final_response

execute_action (if approved or no-approval-needed action)
  → reads: proposed_action, approval_result
  → calls: create_coupon_grant_draft (with idempotency_key)
  → sets: action_result

final_response
  → reads: action_result, approval_result
  → generates response incorporating outcome
```
