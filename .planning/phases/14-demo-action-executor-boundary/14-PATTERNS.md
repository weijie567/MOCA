# Phase 14: Demo Action Executor Boundary - Pattern Map

**Mapped:** 2026-06-16
**Files analyzed:** 29
**Analogs found:** 29 / 29

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/db/models.py` | model | CRUD | `src/db/models.py::ActionDraft`, `ActionSafetySnapshot`, `AgentTraceEvent` | exact |
| `src/db/migrations/versions/009_action_draft_v2.py` | migration | CRUD/schema expand | `src/db/migrations/versions/008_approval_state_machine.py`, `005_approval_tables.py` | exact |
| `src/actions/schemas.py` | schema | transform | `src/actions/schemas.py`, `src/api/schemas/approvals.py` | role-match |
| `src/actions/service.py` | service | CRUD + request-response + event-driven | `src/actions/service.py` | exact |
| `src/actions/drafts.py` | service adapter | CRUD | `src/actions/drafts.py` | exact |
| `src/repositories/action_draft_repo.py` | repository | CRUD + idempotency | `src/repositories/action_draft_repo.py` | exact |
| `src/agent/state.py` | schema/state | event-driven graph state | `src/agent/state.py` | exact |
| `src/agent/nodes/action_draft.py` | graph node | request-response + CRUD | `src/agent/nodes/execute_action.py` | exact rename |
| `src/agent/nodes/execute_action.py` | compatibility shim | request-response | `src/agent/nodes/execute_action.py`, architecture shim pattern in `tests/architecture/test_approval_boundaries.py` | partial |
| `src/agent/graph.py` | route/graph config | event-driven | `src/agent/graph.py` | exact |
| `src/tools/catalog.py` | config | request-response/tool dispatch | `src/tools/catalog.py` | exact |
| `src/tools/manager.py` | service/guard | request-response/tool dispatch | `src/tools/manager.py` | exact |
| `src/tools/executors/action.py` | executor adapter | request-response | `src/tools/executors/action.py` | exact |
| `src/api/routers/approvals.py` | controller | request-response + resume reconciliation | `src/api/routers/approvals.py` | exact |
| `src/agent/nodes/final_response.py` | graph node | transform/request-response | `src/agent/nodes/final_response.py` | exact |
| `src/agent/events.py` | event utility | event-driven | `src/agent/events.py` | exact |
| `src/api/routers/traces.py` | controller | request-response/read model | `src/api/routers/traces.py` | exact |
| `src/repositories/trace_repo.py` | repository | read model transform | `src/repositories/trace_repo.py` | exact |
| `tests/actions/test_action_draft_v2.py` | test | CRUD + migration contract | `tests/approvals/test_migration_contract.py`, `tests/agent/test_tools/test_create_coupon_grant_draft.py` | role-match |
| `tests/architecture/test_action_draft_boundaries.py` | test | static architecture | `tests/architecture/test_approval_boundaries.py` | exact |
| `tests/test_action_draft_node.py` or `tests/test_execute_action.py` | test | request-response graph node | `tests/test_execute_action.py` | exact rewrite |
| `tests/agent/test_tools/test_create_coupon_grant_draft.py` | test | CRUD + binding validation | `tests/agent/test_tools/test_create_coupon_grant_draft.py` | exact |
| `tests/test_graph_routing.py` | test | routing | `tests/test_graph_routing.py` | exact |
| `tests/agent/test_graph.py` | test | graph config | `tests/agent/test_graph.py` | exact |
| `tests/test_approval_api.py` | test | request-response + resume retry | `tests/test_approval_api.py` | exact |
| `tests/test_approval_integration.py` | test | request-response + CRUD integration | `tests/test_approval_integration.py` | exact |
| `tests/agent/test_events.py` | test | event-driven | `tests/agent/test_events.py` | exact |
| `tests/test_trace_api.py` | test | request-response/read model | `tests/test_trace_api.py` | exact |
| `tests/agent/test_nodes/test_final_response.py` | test | transform/wording | `tests/agent/test_nodes/test_final_response.py` | exact |

## Pattern Assignments

### `src/db/models.py` (model, CRUD)

**Analog:** `src/db/models.py`

**Current ActionDraft pattern** (`src/db/models.py` lines 579-596):
```python
class ActionDraft(TimestampMixin, Base):
    __tablename__ = "action_drafts"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_action_drafts_idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_requests.id")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft_created")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by_agent_run: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
```

**V2 field style analog** (`src/db/models.py` lines 279-307):
```python
class ActionSafetySnapshot(Base):
    __tablename__ = "action_safety_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "immutable_hash", name="uq_action_safety_snapshots_tenant_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schema_version: Mapped[str] = mapped_column(String(48), nullable=False, default="action_safety_snapshot.v1")
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    immutable_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    action_payload_hash: Mapped[str | None] = mapped_column(String(128))
```

**Event model analog** (`src/db/models.py` lines 632-657):
```python
class AgentTraceEvent(TimestampMixin, Base):
    """Phase 10 minimal event envelope (schema_version=minimal_event_envelope.v1)."""

    __tablename__ = "agent_trace_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_agent_trace_events_run_seq"),)

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(nullable=False)
    operation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
```

**Apply:** Add nullable-for-legacy `action_draft.v2` columns to `ActionDraft`: `schema_version`, `action_payload_hash`, `safety_snapshot_ref`, `safety_snapshot_hash`, `draft_outcome`, lifecycle/version/retention fields, and any chosen `target_id`/revision marker fields. Keep global `uq_action_drafts_idempotency_key`.

---

### `src/db/migrations/versions/009_action_draft_v2.py` (migration, CRUD/schema expand)

**Analogs:** `src/db/migrations/versions/008_approval_state_machine.py`, `src/db/migrations/versions/005_approval_tables.py`

**Migration header pattern** (`008_approval_state_machine.py` lines 1-20):
```python
"""Add approval state machine schema.

Revision ID: 008_approval_state_machine
Revises: 007_session_memories
Create Date: 2026-06-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "008_approval_state_machine"
down_revision: str | None = "007_session_memories"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None
```

**Add nullable columns pattern** (`008_approval_state_machine.py` lines 42-57):
```python
def upgrade() -> None:
    for column in (
        sa.Column("schema_version", sa.String(length=48)),
        sa.Column("approval_policy_id", sa.String(length=64)),
        sa.Column("policy_version", sa.String(length=64)),
        sa.Column("revision", sa.Integer()),
        sa.Column("version", sa.Integer()),
        sa.Column("action_payload_hash", sa.String(length=128)),
        sa.Column("safety_snapshot_ref", sa.String(length=128)),
        sa.Column("safety_snapshot_hash", sa.String(length=128)),
        sa.Column("legacy_non_executable", sa.Boolean(), nullable=False, server_default=sa.false()),
    ):
        op.add_column("approval_requests", column)
```

**Create existing action_drafts table analog** (`005_approval_tables.py` lines 65-85):
```python
op.create_table(
    "action_drafts",
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
    sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
    sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approval_requests.id")),
    sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("idempotency_key", sa.String(length=256), nullable=False),
    sa.Column("action_type", sa.String(length=64), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("payload", postgresql.JSONB, nullable=False),
    sa.Column("created_by_agent_run", postgresql.UUID(as_uuid=True)),
    sa.UniqueConstraint("idempotency_key", name="uq_action_drafts_idempotency_key"),
)
op.create_index("ix_action_drafts_run_id", "action_drafts", ["run_id"])
op.create_index("ix_action_drafts_tenant_id", "action_drafts", ["tenant_id"])
```

**Apply:** `009` should revise `008_approval_state_machine`, expand `action_drafts`, and downgrade by dropping added indexes/columns in reverse order. Do not create `action_executions`, outbox, reconciliation, or compensation tables.

---

### `src/actions/schemas.py` (schema, transform)

**Analog:** `src/actions/schemas.py`

**Pydantic schema style** (`src/actions/schemas.py` lines 5-23):
```python
from pydantic import BaseModel, ConfigDict


class ActionDraftData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    idempotency_key: str
    status: str
    created: bool
    idempotent_reused: bool


class ActionToolCompatResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    data: dict[str, Any]
    error: dict[str, Any]
```

**Apply:** Add typed `ActionDraftV2Data` / `DraftOutcomeV1` models here if the planner wants schema validation for service output. Keep `extra="forbid"`. `DraftOutcomeV1.status` should be `not_executed_demo`, and `external_side_effect` should be false.

---

### `src/actions/service.py` (service, CRUD + request-response + event-driven)

**Analog:** `src/actions/service.py`

**Imports and service owner pattern** (`src/actions/service.py` lines 3-12, 27-33):
```python
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.drafts import ActionDraftStore
from src.db.models import ActionSafetySnapshot, ApprovalRequest

class ActionService:
    """Business owner for durable action draft creation."""

    def __init__(self, session: AsyncSession, *, draft_store: ActionDraftStore | None = None) -> None:
        self.session = session
        self.draft_store = draft_store or ActionDraftStore(session)
```

**Transaction and binding validation pattern** (`src/actions/service.py` lines 56-79):
```python
if not action_payload_hash or not safety_snapshot_ref or not safety_snapshot_hash:
    return _tool_error("ACTION_BINDING_REQUIRED", "Action draft requires exact safety binding", retryable=False)

try:
    async with self.session.begin_nested():
        binding_error = await self._validate_action_binding(
            tenant_id=tenant_uuid,
            run_id=run_uuid,
            approval_request_id=approval_uuid,
            action_payload_hash=action_payload_hash,
            safety_snapshot_ref=safety_snapshot_ref,
            safety_snapshot_hash=safety_snapshot_hash,
        )
        if binding_error is not None:
            return binding_error
        draft, created = await self.draft_store.create_or_get(
            run_id=run_uuid,
            tenant_id=tenant_uuid,
            approval_request_id=approval_uuid,
            idempotency_key=idempotency_key,
            action_type=action_type,
            payload=payload,
        )
```

**Phase 13 snapshot/approval guard to reuse** (`src/actions/service.py` lines 99-147):
```python
snapshot = (
    await self.session.execute(
        select(ActionSafetySnapshot).where(
            ActionSafetySnapshot.tenant_id == tenant_id,
            ActionSafetySnapshot.run_id == run_id,
            ActionSafetySnapshot.snapshot_ref == safety_snapshot_ref,
            ActionSafetySnapshot.immutable_hash == safety_snapshot_hash,
            ActionSafetySnapshot.action_payload_hash == action_payload_hash,
            ActionSafetySnapshot.deleted_at.is_(None),
        )
    )
).scalar_one_or_none()
if snapshot is None:
    return _tool_error("ACTION_BINDING_MISMATCH", "Action safety snapshot binding is invalid", retryable=False)
...
if (
    approval.legacy_non_executable
    or approval.schema_version != "approval_request.v2"
    or approval.status != "approved"
    or approval.action_payload_hash != action_payload_hash
    or approval.safety_snapshot_ref != safety_snapshot_ref
    or approval.safety_snapshot_hash != safety_snapshot_hash
):
    return _tool_error("APPROVAL_BINDING_MISMATCH", "Approved request binding is invalid", retryable=False)
```

**Error envelope pattern** (`src/actions/service.py` lines 88-97):
```python
except ValueError as exc:
    if str(exc) == _IDEMPOTENCY_CONFLICT:
        return _tool_error(
            "IDEMPOTENCY_CONFLICT",
            "Action draft idempotency key conflicts with another tenant",
            retryable=False,
        )
    return _tool_error("INVALID_REQUEST", "Action draft request is invalid", retryable=False)
except Exception:
    return _tool_error("DRAFT_CREATION_FAILED", "Action draft creation failed", retryable=True)
```

**Apply:** Move idempotency key construction into this trusted boundary. Reject missing `target_id`. Build `{tenant_id}:{run_id}:{approval_revision_or_auto}:{action_type}:{target_id}:{action_payload_hash}`. On success, return `action_draft` and `draft_outcome`, with any `action_result` compatibility set to draft-only/not-executed semantics. Emit `action_draft_created` after the draft is created or exactly reused.

---

### `src/actions/drafts.py` and `src/repositories/action_draft_repo.py` (adapter/repository, CRUD + idempotency)

**Analogs:** `src/actions/drafts.py`, `src/repositories/action_draft_repo.py`

**Store pass-through pattern** (`src/actions/drafts.py` lines 12-36):
```python
class ActionDraftStore:
    """Persistence adapter for durable action drafts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ActionDraftRepository(session)

    async def create_or_get(
        self,
        *,
        run_id: UUID,
        tenant_id: UUID,
        approval_request_id: UUID | None,
        idempotency_key: str,
        action_type: str,
        payload: dict[str, Any],
    ) -> tuple[ActionDraft, bool]:
        return await self.repository.create_or_get(...)
```

**Repository idempotent create pattern** (`src/repositories/action_draft_repo.py` lines 16-45):
```python
stmt = select(ActionDraft).where(ActionDraft.idempotency_key == idempotency_key)
existing = (await self.session.execute(stmt)).scalar_one_or_none()
if existing:
    if existing.tenant_id != tenant_id:
        raise ValueError("idempotency_key_conflict")
    return existing, False

draft = ActionDraft(
    run_id=run_id,
    tenant_id=tenant_id,
    approval_request_id=approval_request_id,
    idempotency_key=idempotency_key,
    action_type=action_type,
    status="draft_created",
    payload=payload,
    created_by_agent_run=run_id,
)
self.session.add(draft)
await self.session.flush()
return draft, True
```

**Apply:** Extend signatures to persist v2 binding fields and `draft_outcome`. On key hit, return existing only if tenant/run/action/payload hash/snapshot hash match. Raise a conflict for mismatched `safety_snapshot_hash`; tenant comparison stays as defense-in-depth.

---

### `src/agent/nodes/action_draft.py` (graph node, request-response + CRUD)

**Analog:** `src/agent/nodes/execute_action.py`

**Imports and constants pattern** (`src/agent/nodes/execute_action.py` lines 3-17):
```python
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from src.agent.state import AgentState
from src.approvals.schemas import TrustedApprovalResultV1
from src.tools.contracts import ToolCallContext, ToolResultV2
from src.tools.executors.action import ActionToolExecutor
from src.tools.manager import UnifiedToolManager

ACTION_TOOL_NAME = "create_coupon_grant_draft"
```

**Approval binding trust pattern** (`src/agent/nodes/execute_action.py` lines 95-112):
```python
def _trusted_approval_result(state: AgentState, approval: dict[str, Any]) -> TrustedApprovalResultV1 | None:
    if any(not approval.get(field) for field in REQUIRED_APPROVAL_RESULT_FIELDS):
        return None
    try:
        trusted = TrustedApprovalResultV1.model_validate(approval)
    except ValidationError:
        return None
    if str(trusted.tenant_id) != str(state.get("tenant_id") or ""):
        return None
    if str(trusted.run_id) != str(state.get("current_run_id") or ""):
        return None
    if (
        trusted.action_payload_hash != state.get("action_payload_hash")
        or trusted.safety_snapshot_ref != state.get("safety_snapshot_ref")
        or trusted.safety_snapshot_hash != state.get("safety_snapshot_hash")
    ):
        return None
    return trusted
```

**Tool manager handoff pattern** (`src/agent/nodes/execute_action.py` lines 150-193):
```python
tool_ctx = ToolCallContext(
    tenant_id=state.get("tenant_id", ""),
    user_id=state.get("user_id", ""),
    role=state.get("role") or "",
    permissions=permissions,
    merchant_scope=configurable.get("merchant_scope") or {},
    session_id=configurable.get("session_id"),
    thread_id=state.get("thread_id") or "",
    run_id=run_id,
    trace_id=configurable.get("trace_id") or state.get("current_run_id") or "",
    request_id=configurable.get("request_id") or run_id,
    tool_call_id=f"{run_id}:{ACTION_TOOL_NAME}",
    caller_node="execute_action",
    deadline_at=configurable.get("deadline_at"),
    attempt=1,
    max_attempts=1,
    idempotency_key=idempotency_key,
    approval_ref=approval.get("approval_id"),
    safety_snapshot_ref=state.get("safety_snapshot_ref") or approval.get("safety_snapshot_ref"),
    policy_snapshot_ref=None,
)
manager = configurable.get("action_tool_manager") or UnifiedToolManager(executors=[ActionToolExecutor(session)])
tool_result = await manager.invoke(ACTION_TOOL_NAME, args, tool_ctx)
```

**Obsolete pattern to replace** (`src/agent/nodes/execute_action.py` lines 140-144, 196-200):
```python
approval_id = approval.get("approval_id") or "no_approval"
idempotency_key = f"{run_id}_{approval_id}_{action_type}_{proposed.get('target_id', 'unknown')}"
...
status = "completed" if result.get("status") == "success" else "error"
return {
    "action_result": result,
    "trace_steps": (state.get("trace_steps") or []) + [_trace_step(status, started_at, ACTION_TOOL_NAME)],
}
```

**Apply:** Rename node function and trace node to `action_draft`. Let the service construct the idempotency key; do not pass caller-shaped key except through a compatibility route if the manager contract still requires `ctx.idempotency_key`. Return `action_draft` and `draft_outcome`. Keep `create_coupon_grant_draft` tool name.

---

### `src/agent/nodes/execute_action.py` (compatibility shim, request-response)

**Analog:** current file plus architecture test pattern.

**Shim constraints pattern** (`tests/architecture/test_approval_boundaries.py` lines 49-63):
```python
def test_approval_transition_methods_are_not_imported_outside_approvals_package() -> None:
    violations: list[tuple[str, str]] = []
    compatibility_path = ROOT / "src" / "repositories" / "approval_repo.py"
    for base in (ROOT / "src", ROOT / "tests"):
        for path in sorted(base.glob("**/*.py")):
            if path == compatibility_path:
                continue
            for module in _import_targets(path):
                if module in {
                    "src.repositories.approval_repo",
                    "src.repositories.approval_repo.ApprovalRepository",
                }:
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []
```

**Apply:** If legacy checkpoint resume must keep `execute_action`, make it a named shim that forwards to `action_draft`, document owner/removal gate in the plan, and add an architecture test forbidding new imports except the shim/intent taxonomy.

---

### `src/agent/graph.py` (route/graph config, event-driven)

**Analog:** `src/agent/graph.py`

**Route after risk pattern** (`src/agent/graph.py` lines 53-66):
```python
def route_after_risk(state: AgentState) -> str:
    """Route based on risk assessment and proposed action."""
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action")
    if not proposed:
        return "final_response"
    if not _snapshot_binding_ready(state):
        return "final_response"
    if state.get("safety_snapshot_verified") is not True:
        return "final_response"
    if risk.get("approval_required"):
        return "approval_gate"
    return "execute_action"
```

**Route after approval pattern** (`src/agent/graph.py` lines 68-86):
```python
def route_after_approval(state: AgentState) -> str:
    """Route after a trusted ApprovalService resume result."""
    result = _trusted_approval_result(state)
    if result is None:
        return "final_response"
    ...
    if decision_type in {"accept", "approve"} and status == "approved":
        return "execute_action"
    if decision_type in {"accept", "approve"} and status == "pending":
        return "approval_gate"
    return "final_response"
```

**Graph registration pattern** (`src/agent/graph.py` lines 117-132, 168-188):
```python
builder = StateGraph(AgentState)
...
builder.add_node("approval_gate", approval_gate)
builder.add_node("execute_action", execute_action)
builder.add_node("final_response", final_response, retry_policy=_llm_retry)
...
builder.add_conditional_edges(
    "assess_risk_and_approval",
    route_after_risk,
    {
        "approval_gate": "approval_gate",
        "execute_action": "execute_action",
        "final_response": "final_response",
    },
)
...
builder.add_edge("execute_action", "final_response")
```

**Apply:** Replace registered node/import/route keys with `action_draft`. Add a named `execute_action` compatibility edge only if legacy checkpoint policy requires it.

---

### `src/tools/catalog.py`, `src/tools/manager.py`, `src/tools/executors/action.py` (tool config/guard/executor)

**Analogs:** existing tool path.

**Node-only tool descriptor pattern** (`src/tools/catalog.py` lines 88-99, 210-221):
```python
"create_coupon_grant_draft": {
    "type": "object",
    "properties": {
        "approval_request_id": {"type": "string", "minLength": 1},
        "action_type": {"type": "string", "minLength": 1},
        "payload": {"type": "object"},
        "action_payload_hash": {"type": "string", "minLength": 1},
        "safety_snapshot_ref": {"type": "string", "minLength": 1},
        "safety_snapshot_hash": {"type": "string", "minLength": 1},
    },
    "required": ["action_type", "payload", "action_payload_hash", "safety_snapshot_ref", "safety_snapshot_hash"],
}
...
_descriptor(
    "create_coupon_grant_draft",
    kind="write",
    side_effect="write",
    caller_allowlist=["execute_action"],
    event_family="action",
    executor="action",
    exposure="node_only",
    requires_safety_snapshot=True,
    requires_idempotency_key=True,
)
```

**Manager guard pattern** (`src/tools/manager.py` lines 73-98, 162-167):
```python
if ctx.caller_node not in descriptor.caller_allowlist:
    return result("permission_denied", "Caller is not allowed to invoke this tool", code="CALLER_NOT_ALLOWED")
...
if descriptor.requires_safety_snapshot and ctx.safety_snapshot_ref is None:
    return result("permission_denied", "Required safety snapshot is missing", code="SAFETY_SNAPSHOT_REQUIRED")
if descriptor.requires_idempotency_key and not ctx.idempotency_key:
    return result("invalid_request", "Required idempotency key is missing", code="IDEMPOTENCY_KEY_REQUIRED")
...
if caller_node == "execute_action":
    return descriptor.kind == "write" and descriptor.side_effect == "write"
```

**Executor pattern** (`src/tools/executors/action.py` lines 13-45):
```python
class ActionToolExecutor:
    executor_name = "action"

    def __init__(self, session: AsyncSession, service: ActionService | None = None) -> None:
        self.service = service or ActionService(session)

    def has_tool(self, name: str) -> bool:
        return name == "create_coupon_grant_draft"

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        ...
        raw_result = await self.service.create_coupon_grant_draft(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            run_id=ctx.run_id,
            approval_request_id=args.get("approval_request_id"),
            idempotency_key=ctx.idempotency_key or "",
            action_type=str(args["action_type"]),
            payload=dict(args["payload"]),
            action_payload_hash=str(args.get("action_payload_hash") or ""),
            safety_snapshot_ref=str(args.get("safety_snapshot_ref") or ""),
            safety_snapshot_hash=str(args.get("safety_snapshot_hash") or ""),
        )
```

**Apply:** Change caller allowlist/side-effect guard from `execute_action` to `action_draft` unless a compatibility shim is explicitly retained. Keep tool name `create_coupon_grant_draft`. If the service owns key construction, update manager/executor requirements so callers cannot supply arbitrary key shape.

---

### `src/api/routers/approvals.py` (controller, request-response + resume reconciliation)

**Analog:** `src/api/routers/approvals.py`

**Authenticated controller pattern** (`src/api/routers/approvals.py` lines 46-67):
```python
@router.post("/{approval_id}/decide", response_model=ApiResponse)
async def decide_approval(
    approval_id: str,
    body: DecideRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    _assert_approval_reviewer(user)

    approval_uuid = _parse_approval_id(approval_id)
    service = ApprovalService(session)
    try:
        retry_result = await _recoverable_resume_retry_result(...)
    except ApprovalTransitionError as exc:
        raise _approval_http_error(exc) from exc
```

**Resume event and retry pattern** (`src/api/routers/approvals.py` lines 216-254):
```python
async def _run_resume_lifecycle(...):
    try:
        await _record_resume_event(..., resume_status="attempted")
        await session.commit()

        await _resume_graph_after_decision(...)
        await _record_resume_event(..., resume_status="completed")
        await session.commit()
    except Exception as exc:
        await session.rollback()
        await _record_resume_event(..., resume_status="failed", error=exc)
        await session.commit()
        raise HTTPException(
            status_code=500,
            detail={
                "code": "APPROVAL_RESUME_FAILED",
                "message": "Approval decision was saved, but graph resume did not complete. Retry the decision to reconcile.",
            },
        ) from exc
```

**Obsolete reconciliation sentinel to replace** (`src/api/routers/approvals.py` lines 488-533):
```python
update = await execute_action(state, config)
reconciled = {**final_state, **update}
if update.get("action_result", {}).get("status") != "success":
    reconciled["node_errors"] = (final_state.get("node_errors") or []) + [
        {"node": "execute_action", "error": "action_draft_reconcile_failed"}
    ]
return reconciled
```

**Apply:** Import/call `action_draft`, not `execute_action`, unless using a named shim. Reconciliation success should inspect `draft_outcome.status == "not_executed_demo"` and `external_side_effect is False`, not `action_result.status == "success"`.

---

### `src/agent/nodes/final_response.py` (graph node, transform/request-response)

**Analog:** `src/agent/nodes/final_response.py`

**Template helper pattern** (`src/agent/nodes/final_response.py` lines 119-129):
```python
def _completed_response(draft: dict[str, Any], risk_assessment: dict[str, Any]) -> str:
    action = draft.get("recommended_action") or "建议按已检索到的政策依据处理。"
    reasoning = draft.get("reasoning_summary") or "已根据当前知识库证据生成建议。"
    citations = _citation_summary(draft.get("evidence_refs") or [])
    parts = [f"建议：{action}", f"理由：{reasoning}"]
    if citations:
        parts.append(f"依据：{citations}。")
    if risk_assessment.get("approval_required"):
        risk_reason = risk_assessment.get("risk_reason") or "命中风险规则"
        parts.append(f"风险提示：{risk_reason}，需要人工审批后执行。")
    return "\n".join(parts)
```

**Obsolete wording/sentinel to replace** (`src/agent/nodes/final_response.py` lines 132-154):
```python
if decision_type in {"accept", "approve"} and action_result:
    if action_result.get("status") == "success":
        draft_id = (action_result.get("data") or {}).get("draft_id", "unknown")
        return f"审批结果：操作已审批通过，补偿草稿已创建（草稿ID：{draft_id}），等待最终发放。"
    message = (action_result.get("error") or {}).get("message", "unknown error")
    return f"审批结果：操作已审批通过，但执行失败：{message}。"
...
if not approval_result and action_result and action_result.get("status") == "success":
    draft_id = (action_result.get("data") or {}).get("draft_id", "unknown")
    return f"执行结果：该操作在政策范围内，无需审批，补偿草稿已创建（草稿ID：{draft_id}）。"
```

**Apply:** Add `_draft_outcome_text(approval_result, draft_outcome)` or equivalent. Positive text must say draft created and no coupon/refund/ticket action was executed. Forbidden: "waiting for final issuance", issued coupon, refunded, closed ticket, executed, external success.

---

### `src/agent/events.py` (event utility, event-driven)

**Analog:** `src/agent/events.py`

**Event registry pattern** (`src/agent/events.py` lines 15-40):
```python
MINIMAL_EVENT_TYPES = {
    "node_started",
    "node_completed",
    ...
    "approval_requested",
    "approval_decided",
    "approval_expired",
    "approval_resumed",
}
EVENT_RETENTION_CLASSIFICATION = {event_type: "minimal_event" for event_type in MINIMAL_EVENT_TYPES}
SCHEMA_VERSION = "minimal_event_envelope.v1"
```

**Emit helper pattern** (`src/agent/events.py` lines 87-136):
```python
async def emit_event(
    session: AsyncSession,
    *,
    run_id: uuid.UUID | str,
    tenant_id: uuid.UUID | str,
    thread_id: str,
    event_type: str,
    actor: dict[str, Any],
    resource_refs: dict[str, Any],
    redacted_payload: dict[str, Any],
    trace_id: str | None = None,
    operation_id: uuid.UUID | str | None = None,
    iteration: int | None = None,
    redaction_policy_version: str = "redaction.v1",
) -> dict[str, Any]:
    if event_type not in MINIMAL_EVENT_TYPES:
        raise ValueError(f"event_type {event_type!r} is not registered for the minimal envelope")

    _guard_redacted_payload(redacted_payload)
    ...
    session.add(AgentTraceEvent(**envelope))
    await session.flush()
    return envelope
```

**Redaction guard pattern** (`src/agent/events.py` lines 41-55, 139-151):
```python
FORBIDDEN_REDACTED_PAYLOAD_KEYS = {
    "data",
    "raw",
    "arguments",
    "prompt",
    "raw_prompt",
    "raw_args",
    "raw_payload",
    "raw_tool_output",
    "secret",
    ...
}
...
if key.lower() in FORBIDDEN_REDACTED_PAYLOAD_KEYS:
    raise ValueError(f"{path} must not carry {key}")
```

**Apply:** Add `action_draft_created` to `MINIMAL_EVENT_TYPES`. Emit only safe refs: `draft_id`, `target_id`, `action_payload_hash`, `safety_snapshot_hash`. Redacted payload should include `action_type`, `execution_mode: "demo"`, and `external_side_effect: false`.

---

### `src/api/routers/traces.py` and `src/repositories/trace_repo.py` (trace output/read model)

**Analogs:** existing trace router/repository.

**Router read model pattern** (`src/api/routers/traces.py` lines 38-70):
```python
steps = await repo.get_steps(run_uuid)
approvals = await repo.get_approvals(run_uuid)
approval_steps = await repo.get_approval_steps([approval.id for approval in approvals])
drafts = await repo.get_action_drafts(run_uuid)
timeline = repo.build_timeline(steps, approvals, approval_steps, drafts)

trace_data = TraceResponse(
    run_id=str(run.id),
    thread_id=run.thread_id,
    final_status=run.final_status,
    ...
    action_drafts=[
        {
            "id": str(draft.id),
            "action_type": draft.action_type,
            "status": draft.status,
        }
        for draft in drafts
    ],
    timeline=timeline,
)
```

**Timeline action draft pattern** (`src/repositories/trace_repo.py` lines 96-108):
```python
for draft in drafts:
    timeline.append(
        {
            "type": "action_draft",
            "time": draft.created_at.isoformat(),
            "title": f"Action: {draft.action_type}",
            "status": draft.status,
            "detail": {
                "draft_id": str(draft.id),
                "idempotency_key": draft.idempotency_key,
            },
        }
    )
```

**Safe proposed action projection** (`src/repositories/trace_repo.py` lines 114-120):
```python
def _safe_proposed_action(action: dict[str, Any] | None) -> dict[str, Any]:
    action = action or {}
    return {
        "action_type": action.get("action_type"),
        "amount": action.get("amount"),
        "currency": action.get("currency"),
    }
```

**Apply:** Add `draft_outcome` to trace `action_drafts[]` and timeline detail. Do not include raw `ActionDraft.payload`. Do not build a new replay API.

---

### Tests (test, CRUD/request-response/event-driven/static)

**Node test analog** (`tests/test_execute_action.py` lines 74-85):
```python
@pytest.mark.asyncio
async def test_execute_action_with_service_approval_result_creates_draft(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    session = object()
    state = _approved_state()

    result = await execute_action_module.execute_action(state, {"configurable": {"session": session}})

    assert result["action_result"]["status"] == "success"
    assert result["trace_steps"][-1]["tool_name"] == "create_coupon_grant_draft"
    create_draft.assert_awaited_once()
```

**Rewrite note:** Keep the fixture/monkeypatch structure, but change assertions to `draft_outcome.status == "not_executed_demo"`, `external_side_effect is False`, node name `action_draft`, and no caller-built idempotency key.

**Service binding test analog** (`tests/agent/test_tools/test_create_coupon_grant_draft.py` lines 158-178, 206-227):
```python
result = await create_coupon_grant_draft(
    tenant_id=str(request.tenant_id),
    user_id=str(user_id),
    run_id=str(request.run_id),
    idempotency_key="approved-draft-key",
    action_type="issue_coupon",
    payload={"target_id": "refund-1"},
    session=session,
    **_binding_kwargs(request),
)

assert result["status"] == "success"
...
result = await create_coupon_grant_draft(
    ...
    **_binding_kwargs(request, action_payload_hash="sha256:" + "9" * 64),
)

assert result["status"] == "error"
assert result["error"]["error_code"] == "ACTION_BINDING_MISMATCH"
assert result["error"]["retryable"] is False
```

**Migration contract test analog** (`tests/approvals/test_migration_contract.py` lines 19-45, 75-107):
```python
MIGRATION_PATH = Path("src/db/migrations/versions/008_approval_state_machine.py")

def _table(name: str):
    assert name in Base.metadata.tables
    return Base.metadata.tables[name]

def _column_names(table_name: str) -> set[str]:
    return set(_table(table_name).c.keys())

def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), "migration 008 must exist"
    return MIGRATION_PATH.read_text(encoding="utf-8")
...
assert {
    "schema_version",
    "approval_policy_id",
    "policy_version",
    "revision",
    "version",
    "action_payload_hash",
    "safety_snapshot_ref",
    "safety_snapshot_hash",
}.issubset(_column_names("approval_requests"))
```

**Architecture boundary test analog** (`tests/architecture/test_approval_boundaries.py` lines 1-18, 66-81):
```python
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    imports: list[str] = []
    ...

def test_graph_nodes_do_not_import_raw_action_or_business_adapters_for_approval() -> None:
    violations: list[tuple[str, str]] = []
    forbidden_prefixes = (
        "src.actions.drafts",
        "src.actions.service",
        "src.business",
        "src.business_tools",
        "src.integrations",
    )
    for path in sorted((ROOT / "src" / "agent" / "nodes").glob("*.py")):
        for module in _imports(path):
            if module.startswith(forbidden_prefixes):
                violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []
```

**Event tests analog** (`tests/agent/test_events.py` lines 143-149, 197-252):
```python
def test_approval_event_types_and_retention_are_registered():
    assert {"approval_requested", "approval_decided", "approval_expired", "approval_resumed"} <= MINIMAL_EVENT_TYPES
    assert EVENT_RETENTION_CLASSIFICATION["approval_requested"] == "minimal_event"
    ...

@pytest.mark.asyncio
async def test_redaction_guard(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)

    with pytest.raises(ValueError):
        await _emit(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            redacted_payload={"data": {"raw": "tool output"}},
        )
```

**Trace API test analog** (`tests/test_trace_api.py` lines 17-53, 131-184):
```python
response = await client.get(
    f"/api/v1/agent-runs/{run_id}/trace",
    headers=await _support_headers(client),
)
payload = response.json()

assert response.status_code == 200
assert payload["success"] is True
assert payload["data"]["action_drafts"][0]["action_type"] == "issue_coupon"
assert "input_query" not in payload["data"]
assert "final_response" not in payload["data"]
assert "secret" not in str(payload["data"])
...
assert [item["type"] for item in timeline] == [
    "approval_request",
    "agent_step",
    "approval_decision",
    "action_draft",
]
```

**Approval resume retry test analog** (`tests/test_approval_api.py` lines 243-313):
```python
first_response = await client.post(
    f"/api/v1/approvals/{bundle.approval.id}/decide",
    json=decision_body,
    headers=headers,
)
...
assert first_response.status_code == 500
assert first_response.json()["error"]["code"] == "APPROVAL_RESUME_FAILED"
assert bundle.approval.status == "approved"
assert run.final_status == "interrupted"
assert {"attempted", "failed"} <= resume_statuses
assert "completed" not in resume_statuses

retry_response = await client.post(...)
...
assert retry_response.status_code == 200
assert run.final_status == "completed"
assert completed_statuses.count("completed") == 1
```

**Final wording test analog** (`tests/agent/test_nodes/test_final_response.py` lines 39-57, 99-116):
```python
state = {
    **base_state,
    "approval_result": {"decision": "approve"},
    "action_result": {"status": "success", "data": {"draft_id": "draft-001"}, "error": {}},
}

result = await final_response(state)

assert "审批结果" in result["final_response"]
assert "draft-001" in result["final_response"]
```

**Rewrite note:** Preserve the state-driven final response pattern, but replace `action_result.status == "success"` with `draft_outcome`. Add forbidden-phrase assertions for backend/final/API strings.

## Shared Patterns

### Phase 13 Binding Is Reused, Not Recomputed
**Source:** `src/actions/service.py` lines 99-147
**Apply to:** `src/actions/service.py`, repository tests, action node tests.

Use `_validate_action_binding` as the service guard. Do not create a new snapshot builder or canonical hash profile in Phase 14.

### Trusted Idempotency Boundary
**Source:** current anti-pattern in `src/agent/nodes/execute_action.py` lines 140-144 and repository create-or-get in `src/repositories/action_draft_repo.py` lines 16-45.
**Apply to:** `src/actions/service.py`, `src/actions/drafts.py`, `src/repositories/action_draft_repo.py`, node/tool tests.

Move key construction out of the graph node. Reject missing `target_id`; use `auto_allowed` for no-approval drafts; key hits require exact binding, especially `safety_snapshot_hash`.

### Node-Only Write Tool Path
**Source:** `src/tools/catalog.py` lines 210-221, `src/tools/manager.py` lines 73-98, `src/tools/executors/action.py` lines 13-45.
**Apply to:** `src/agent/nodes/action_draft.py`, `src/tools/catalog.py`, `src/tools/manager.py`.

Keep `UnifiedToolManager -> ActionToolExecutor -> ActionService`; do not call raw action repositories from graph nodes.

### Draft Outcome Is Success Signal
**Source:** obsolete current sentinels in `src/api/routers/approvals.py` lines 527-532 and `src/agent/nodes/final_response.py` lines 138-152.
**Apply to:** action node, approval resume reconciliation, final response, API tests.

Planner should replace these checks with `draft_outcome.status == "not_executed_demo"` and `external_side_effect is False`.

### Minimal Safe Event Emission
**Source:** `src/agent/events.py` lines 87-136 and tests in `tests/agent/test_events.py` lines 143-252.
**Apply to:** `src/agent/events.py`, action service/node event emission, event tests.

Register `action_draft_created`; keep redaction guard; add negative tests for no `action_execution_*` event types in demo mode.

### Trace Output Redaction
**Source:** `src/api/routers/traces.py` lines 61-68, `src/repositories/trace_repo.py` lines 96-120, `tests/test_trace_api.py` lines 17-53.
**Apply to:** trace router/repository/tests.

Extend current output with `draft_outcome`; never expose raw `ActionDraft.payload`.

## No Analog Found

All Phase 14 files have a close local analog. The only intentionally absent surface is Phase 17 external execution:

| File/Surface | Role | Data Flow | Reason |
|--------------|------|-----------|--------|
| `action_executions`, outbox, reconciliation, compensation tables | model/migration/service | external side-effect/event-driven | Explicitly out of scope for Phase 14; add negative tests instead of code. |

## Metadata

**Analog search scope:** `src/actions`, `src/agent`, `src/api/routers`, `src/repositories`, `src/db/models.py`, `src/db/migrations/versions`, `src/tools`, `tests`, `docs/phase-13-17-architecture-plan.md`.
**Files scanned:** 40+ source/test files plus Phase 14 context/research and mandatory architecture doc.
**Pattern extraction date:** 2026-06-16
