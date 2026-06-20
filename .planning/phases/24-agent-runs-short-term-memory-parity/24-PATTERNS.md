# Phase 24: Agent Runs Short-term Memory Parity - Pattern Map

**Mapped:** 2026-06-20  
**Files analyzed:** 24  
**Analogs found:** 24 / 24

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/api/routers/agent_runs.py` | route/controller | request-response + streaming + event-driven | `src/api/routers/agent_runs.py`, `src/api/routers/agent.py` | exact |
| `src/api/routers/agent.py` | route/controller | request-response | `src/api/routers/agent.py` | exact |
| `src/api/services/agent_run_memory.py` *(new, inferred)* | service/finalizer | CRUD + batch + request-response | `src/api/routers/agent.py`, `src/api/routers/agent_runs.py`, `src/agent/nodes/memory_write.py` | role-match |
| `src/conversation/service.py` | service | CRUD + transform | `src/conversation/service.py` | exact |
| `src/conversation/repository.py` | repository | CRUD | `src/conversation/repository.py` | exact |
| `src/db/models.py` | model | schema/CRUD | `src/db/models.py` | exact |
| `src/db/migrations/versions/016_agent_run_memory_idempotency.py` *(name inferred)* | migration/config | schema migration | `src/db/migrations/versions/012_thread_user_scope.py`, `src/db/migrations/versions/011_memory_foundation_v2.py` | role-match |
| `src/memory/thread_summary.py` | service | transform + CRUD | `src/memory/thread_summary.py` | exact |
| `src/agent/nodes/extract_slots.py` *(conditional)* | node/hook | transform + request-response | `src/agent/nodes/generate_recommendation.py`, `src/agent/nodes/extract_slots.py` | role-match |
| `src/agent/nodes/generate_recommendation.py` *(conditional/shared loader)* | node/hook | transform + request-response | `src/agent/nodes/generate_recommendation.py` | exact |
| `src/agent/nodes/investigate.py` *(reference/guard target)* | node/hook | event-driven + CRUD | `src/agent/nodes/investigate.py` | exact |
| `src/agent/nodes/memory_write.py` *(reference/call target)* | node/hook | CRUD + batch | `src/agent/nodes/memory_write.py` | exact |
| `src/agent/nodes/session_memory_load.py` *(reference)* | node/hook | CRUD + transform | `src/agent/nodes/session_memory_load.py` | exact |
| `src/agent/context/assembler.py` | utility | transform | `src/agent/context/assembler.py` | exact |
| `src/agent/context/projectors.py` | utility | transform | `src/agent/context/projectors.py` | exact |
| `tests/test_agent_runs_api.py` | test | request-response + streaming | `tests/test_agent_runs_api.py` | exact |
| `tests/conversation/test_service.py` | test | CRUD + transform | `tests/conversation/test_service.py` | exact |
| `tests/memory/test_thread_summary.py` | test | transform + CRUD | `tests/memory/test_thread_summary.py` | exact |
| `tests/memory/test_session_memory_service.py` | test | CRUD + CAS | `tests/memory/test_session_memory_service.py` | exact |
| `tests/agent/context/test_assembler.py` | test | transform | `tests/agent/context/test_assembler.py` | exact |
| `tests/agent/test_session_memory_integration.py` | test | graph integration + CRUD | `tests/agent/test_session_memory_integration.py` | exact |
| `tests/agent/test_required_slots.py` | test | transform | `tests/agent/test_required_slots.py` | exact |
| `tests/agent/test_memory_evidence_boundary.py` | test | graph integration + boundary | `tests/agent/test_memory_evidence_boundary.py` | exact |
| `tests/agent/rag_context/test_authority_boundaries.py` | test | authority verification | `tests/agent/rag_context/test_authority_boundaries.py` | exact |

## Pattern Assignments

### `src/api/routers/agent_runs.py` (route/controller, request-response + streaming)

**Analog:** `src/api/routers/agent_runs.py` for current POST/SSE lifecycle; `src/api/routers/agent.py` for legacy conversation persistence.

**Imports pattern** (`src/api/routers/agent_runs.py` lines 15-33):
```python
from langgraph.errors import GraphInterrupt
from pydantic import ValidationError
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sse_starlette.sse import EventSourceResponse

from src.agent.nodes.memory_write import memory_write
from src.agent.nodes.final_response import final_response as build_final_response
from src.agent.trace import build_trace_summary, update_agent_run_status, write_agent_run, write_agent_steps
from src.api.schemas.agent_runs import CreateRunRequest, RunStatusResponse
from src.api.schemas.common import ApiResponse
from src.auth.permissions import get_current_user
from src.db.models import AgentRun, User
from src.db.session import get_session
```

**Current create-run gap** (`src/api/routers/agent_runs.py` lines 81-109): `POST /agent-runs` only writes an `AgentRun` and commits. Phase 24 must insert/resolve exactly one user `ConversationMessage` in this same durable boundary.
```python
@router.post("", response_model=ApiResponse)
async def create_agent_run(...):
    run_id = str(uuid.uuid4())
    await write_agent_run(
        session,
        run_id=run_id,
        thread_id=body.thread_id,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        input_query=body.query,
        final_status="pending",
        final_response=None,
        started_at=datetime.now(timezone.utc),
        completed_at=None,
        total_latency_ms=None,
        trace_id=getattr(request.state, "trace_id", None),
    )
    await session.commit()
```

**Current SSE config gap** (`src/api/routers/agent_runs.py` lines 139-169): keep `_claim_pending_run_for_stream`; after claim, resolve the persisted user message and add trusted `conversation_message_id`, `conversation_thread_id`, and `conversation_service` into `config["configurable"]`.
```python
run = await _claim_pending_run_for_stream(session, run_uuid, user)
...
config = {
    "configurable": {
        "thread_id": _checkpoint_thread_id(user=user, thread_id=run.thread_id),
        "session": session,
        **_trusted_tool_config(user, verified_token_scopes, getattr(request.state, "trace_id", None)),
    }
}

return EventSourceResponse(_event_generator(graph, input_state, config, run=run, session=session, user=user))
```

**Pending claim pattern** (`src/api/routers/agent_runs.py` lines 782-809): preserve this duplicate execution guard.
```python
select(AgentRun).where(AgentRun.id == run_id, AgentRun.tenant_id == user.tenant_id).with_for_update()
...
if run.final_status != "pending":
    await session.rollback()
    raise HTTPException(status_code=409, detail={"code": "RUN_ALREADY_STARTED", ...})
...
await update_agent_run_status(session, run_id=str(run.id), final_status="running", trace_id=None)
await session.commit()
```

**Terminal persistence currently too thin** (`src/api/routers/agent_runs.py` lines 812-838): extend/delegate this, but keep status + step persistence via existing helpers.
```python
await update_agent_run_status(
    session,
    run_id=str(run.id),
    final_status=final_status,
    final_response=final_response,
    completed_at=completed_at,
    total_latency_ms=total_latency_ms,
    reason_code=_reason_code_for_final_status(final_status),
)
run.total_tokens = _count_tokens(trace_steps)
if trace_steps:
    await write_agent_steps(session, run_id=str(run.id), trace_steps=trace_steps)
await session.commit()
```

**Old ordering to replace** (`src/api/routers/agent_runs.py` lines 316-338 and 472-485): current code emits `final_response` and then schedules memory. Phase 24 must run bounded required memory finalization before this event.
```python
await _complete_run(...)
if final_response:
    yield _sse_event(event_type="final_response", ...)
    _schedule_memory_write_after_response(
        {**input_state, **final_state, "final_response": str(final_response)},
        session_factory=_session_factory_from_session(session),
        trace_id=config.get("configurable", {}).get("trace_id"),
    )
```

**Background task helper** (`src/api/routers/agent_runs.py` lines 1069-1090): keep only for optional post-response cleanup, not Phase 24 continuity.
```python
def _schedule_memory_write_after_response(final_state: dict[str, Any], *, session_factory, trace_id: str | None = None):
    state_snapshot = dict(final_state)

    async def run_memory_write() -> None:
        async with session_factory() as memory_session:
            try:
                await memory_write(
                    state_snapshot,
                    {"configurable": {"session": memory_session, "trace_id": trace_id or ""}},
                )
                await memory_session.commit()
            except Exception:
                await memory_session.rollback()
```

---

### `src/api/routers/agent.py` (route/controller, request-response)

**Analog:** legacy `/api/v1/agent/chat` parity reference.

**Legacy user message + trusted config pattern** (`src/api/routers/agent.py` lines 72-100):
```python
conversation_repository = ConversationRepository(session)
conversation_service = ConversationService(conversation_repository)
await write_agent_run(... final_status="running", ...)
user_message = await conversation_service.append_user_message(
    tenant_id=user.tenant_id,
    user_id=user.id,
    thread_id=body.thread_id,
    run_id=UUID(str(run_id)),
    content=body.query,
    trace_id=getattr(request.state, "trace_id", None),
    prompt_template_version="chat.request.v1",
)
config["configurable"]["conversation_message_id"] = str(user_message.message_id)
config["configurable"]["conversation_thread_id"] = str(user_message.conversation_thread_id)
final_state = await graph.ainvoke(input_state, config)
```

**Legacy completed turn pattern** (`src/api/routers/agent.py` lines 170-202): this is the closest copy source for `/agent-runs` completed finalization, except Phase 24 needs idempotent helpers.
```python
await write_agent_run(... final_status=final_status, final_response=final_response_text, ...)
await write_agent_steps(session, run_id=run_id, trace_steps=trace_steps)
await conversation_service.append_assistant_message(
    tenant_id=user.tenant_id,
    user_id=user.id,
    thread_id=body.thread_id,
    run_id=UUID(str(run_id)),
    content=final_response_text,
    trace_id=getattr(request.state, "trace_id", None),
    metadata_json={"status": final_status},
)
await ThreadRollingSummaryService(conversation_repository).persist_thread_summary(
    tenant_id=user.tenant_id,
    user_id=user.id,
    thread_id=body.thread_id,
    run_id=UUID(str(run_id)),
)
await session.commit()
```

**Legacy behavior warning** (`src/api/routers/agent.py` lines 316-324 and 400-408): legacy chat appends assistant messages for interrupted/error fallback. Do not copy this behavior into `/agent-runs`; Phase 24 gates assistant/summary/session writes to completed runs only.

---

### `src/api/services/agent_run_memory.py` (new service/finalizer, CRUD + batch)

**Analog:** extracted from `src/api/routers/agent.py` completed-turn block, `src/api/routers/agent_runs.py::_complete_run`, `src/agent/nodes/memory_write.py`, and `src/agent/trace.py`.

**Recommended shape:** create a small service/helper with explicit inputs: `session`, `run`, `user`, `final_state`, `final_response`, `final_status`, `trace_steps`, `trace_id`, `conversation_service`, `conversation_repository`. It should not import FastAPI request/response types.

**Completed-only guard source** (`src/agent/nodes/memory_write.py` lines 37-65):
```python
final_response = state.get("final_response")
if not final_response:
    return _skipped(state, started_at, "not_completed_path")
if _approval_or_interrupted(state):
    return _skipped(state, started_at, "not_completed_path")
...
try:
    result = await asyncio.wait_for(
        _write_with_service(state, session, configurable, started_at),
        timeout=settings.session_memory_write_timeout_seconds,
    )
    return result
except TimeoutError:
    ...
    return _skipped(state, started_at, "write_timeout", final_response=final_response)
```

**Trace-step result pattern** (`src/agent/nodes/memory_write.py` lines 227-259): finalizer should merge `memory_write` result trace steps into the persisted `trace_steps` before `_complete_run` writes agent steps.
```python
return {
    "final_response": state.get("final_response"),
    "memory_write_candidates": [_candidate_projection(candidate)],
    "memory_write_result": result_dict,
    "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, result_dict)],
}
```

**Run lifecycle helper source** (`src/agent/trace.py` lines 124-161): continue to use `update_agent_run_status`; it emits lifecycle events.
```python
async def update_agent_run_status(...):
    stmt = select(AgentRun).where(AgentRun.id == uuid.UUID(run_id))
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run:
        previous_status = run.final_status
        run.final_status = final_status
        ...
        await session.flush()
        if emit_if_unchanged or previous_status != final_status:
            await _append_lifecycle_status(...)
```

**Planner instruction:** finalizer should return a structured result such as `{assistant_message, thread_summary, memory_write_result, trace_steps}` so router code can emit truthful SSE timeline/final events without duplicating persistence decisions.

---

### `src/conversation/service.py` (service, CRUD + transform)

**Analog:** same file.

**Append APIs pattern** (`src/conversation/service.py` lines 35-85): add get-or-create variants beside these methods; keep role-specific wrappers.
```python
async def append_user_message(..., metadata_json: dict[str, Any] | None = None) -> ConversationAppendResult:
    return await self._append_message(... role="user", ...)

async def append_assistant_message(..., metadata_json: dict[str, Any] | None = None) -> ConversationAppendResult:
    return await self._append_message(... role="assistant", ...)
```

**Safe message guard** (`src/conversation/service.py` lines 264-305): all new append/get-once helpers must call this path or preserve the same guard.
```python
if self.repository is None:
    raise RuntimeError("ConversationRepository is required for append operations")
self.validate_safe_message_payload(content=content, metadata_json=metadata_json)
row = await self.repository.append_message(ConversationMessageCreate(...))
return ConversationAppendResult(
    thread_id=row.thread_id,
    conversation_thread_id=row.conversation_thread_id,
    message_id=row.id,
    message_index=row.message_index,
    role=row.role,
)
```

**Prompt-safe tool result pattern** (`src/conversation/service.py` lines 147-217): tool records store normalized data separately, while prompt context receives `ToolResultPromptSummary`.
```python
prompt_summary = _build_prompt_summary(...)
await self.repository.append_tool_result(... prompt_summary=prompt_summary, ...)
return ToolResultPromptSummary(
    tool_call_id=tool_call_id,
    tool_result_id=stored_tool_result_id,
    tool_name=tool_name,
    status=result.status,
    summary=result.summary,
    prompt_summary=prompt_summary,
    business_fact_refs=business_fact_refs,
    policy_evidence_refs=policy_evidence_refs,
    raw_result_ref=raw_result_ref,
    audit_ref=result.audit_ref,
)
```

**Prompt context loader pattern** (`src/conversation/service.py` lines 219-262): reuse this for `/agent-runs`; do not build raw prompt strings in the router.
```python
recent_messages = await self.repository.list_recent_messages(...)
tool_prompt_summaries = await self.repository.list_recent_tool_prompt_summaries(...)
latest_prior_summary = await self._latest_prior_thread_summary(...)
return PromptContextWindow(
    thread_id=thread_id,
    run_id=run_uuid,
    latest_thread_summary=latest_prior_summary,
    recent_messages=recent_messages,
    tool_prompt_summaries=tool_prompt_summaries,
)
```

**Needed new methods:** `append_or_get_user_message_for_run(...)`, `append_or_get_assistant_message_for_run(...)`, and possibly `get_run_message(..., role=...)`. Implement through repository lookups and preserve `ConversationAppendResult` return shape.

---

### `src/conversation/repository.py` (repository, CRUD)

**Analog:** same file.

**Thread identity + message append pattern** (`src/conversation/repository.py` lines 42-93): copy advisory lock + thread lock style before calculating `message_index`.
```python
await self._lock_thread_identity(tenant_id=tenant_id, user_id=user_id, thread_id=thread_id)
thread = await self.get_thread(...)
...
await self._lock_thread(thread.id)
next_index = await self._next_message_index(conversation_thread_id=thread.id)
row = ConversationMessage(... message_index=next_index, role=message.role, ...)
self.session.add(row)
await self.session.flush()
```

**Scoped read pattern** (`src/conversation/repository.py` lines 121-144, 219-262): all lookups are tenant/user/thread/deleted scoped.
```python
thread = await self.get_thread(tenant_id=tenant_id, user_id=user_id, thread_id=thread_id)
if thread is None:
    return []
...
ConversationMessage.conversation_thread_id == thread.id,
ConversationMessage.deleted_at.is_(None),
```

**Summary insert pattern** (`src/conversation/repository.py` lines 314-350): add a lookup before this insert for idempotency by `summary_type`, `source_end_message_id`, and/or `summary_hash`.
```python
row = ConversationSummary(
    id=uuid.uuid4(),
    tenant_id=tenant_id,
    thread_id=thread_id,
    conversation_thread_id=thread.id,
    summary_type="thread_rolling",
    source_start_message_id=source_start_message_id,
    source_end_message_id=source_end_message_id,
    source_message_ids_json=list(source_message_ids_json),
    source_tool_result_ids_json=list(source_tool_result_ids_json),
    summary_hash=summary_hash,
)
self.session.add(row)
await self.session.flush()
```

**Tool record pattern** (`src/conversation/repository.py` lines 352-451): keep `conversation_message_id` wired through both call and result rows.
```python
conversation_message_id=conversation_message_id,
...
tool_call_id=tool_call_id,
tool_result_id=tool_result_id,
prompt_summary=prompt_summary,
business_fact_refs_json=list(business_fact_refs_json),
policy_evidence_refs_json=list(policy_evidence_refs_json),
```

**Needed new repository methods:** `get_message_by_run_role(...)`, `get_or_create_message_for_run_role(...)` or separate read+append helpers; `get_thread_summary_by_source_end(...)`; optional `get_latest_summary_for_run(...)` if planner chooses run-keyed idempotency.

---

### `src/db/models.py` (model, schema/CRUD)

**Analog:** same file plus migration `012_thread_user_scope.py`.

**Conversation thread uniqueness pattern** (`src/db/models.py` lines 998-1027):
```python
class ConversationThread(TimestampMixin, Base):
    __tablename__ = "conversation_threads"
    __table_args__ = (CheckConstraint("status IN ('active', 'archived')", name="ck_conversation_threads_status"),)
...
Index(
    "uq_conversation_threads_active_tenant_user_thread",
    ConversationThread.tenant_id,
    ConversationThread.user_id,
    ConversationThread.thread_id,
    unique=True,
    postgresql_where=ConversationThread.deleted_at.is_(None),
)
```

**Conversation message current constraints** (`src/db/models.py` lines 1037-1078): currently unique only by `(conversation_thread_id, message_index)`. Phase 24 likely needs run/role idempotency.
```python
class ConversationMessage(TimestampMixin, Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint("conversation_thread_id", "message_index", name="uq_conversation_messages_thread_index"),
        CheckConstraint("role IN ('user', 'assistant', 'tool')", name="ck_conversation_messages_role"),
        CheckConstraint("message_index > 0", name="ck_conversation_messages_index_positive"),
    )
...
Index("ix_conversation_messages_tenant_run", ConversationMessage.tenant_id, ConversationMessage.run_id)
```

**Tool rows attach to user message** (`src/db/models.py` lines 1081-1169): do not invent another link table unless planner explicitly chooses it; the schema already has `conversation_message_id`.
```python
conversation_message_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("conversation_messages.id"), index=True
)
...
Index("ix_tool_results_tool_result_id", ToolResultRecord.tool_result_id)
```

**Summary model current constraints** (`src/db/models.py` lines 1172-1206): no source-end uniqueness exists yet.
```python
class ConversationSummary(TimestampMixin, Base):
    __tablename__ = "summaries"
    __table_args__ = (CheckConstraint("summary_type IN ('thread_rolling', 'case_current')", name="ck_summaries_type"),)
...
source_start_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
source_end_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
summary_hash: Mapped[str | None] = mapped_column(String(80))
```

**Partial unique index pattern** (`src/db/models.py` lines 351-383, 434-442, 570-579): use `Index(..., unique=True, postgresql_where=...)` for active-row uniqueness.
```python
Index(
    "uq_session_memories_active_scope",
    SessionMemory.tenant_id,
    SessionMemory.user_id,
    SessionMemory.thread_id,
    unique=True,
    postgresql_where=SessionMemory.deleted_at.is_(None),
)
```

---

### `src/db/migrations/versions/016_agent_run_memory_idempotency.py` (migration/config, schema)

**Analog:** `src/db/migrations/versions/012_thread_user_scope.py` for focused index migration; `011_memory_foundation_v2.py` for table/index naming.

**Focused migration pattern** (`src/db/migrations/versions/012_thread_user_scope.py` lines 16-30):
```python
revision: str = "012_thread_user_scope"
down_revision: str | None = "011_memory_foundation_v2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

def upgrade() -> None:
    op.drop_index("uq_conversation_threads_active_tenant_thread", table_name="conversation_threads")
    op.create_index(
        "uq_conversation_threads_active_tenant_user_thread",
        "conversation_threads",
        ["tenant_id", "user_id", "thread_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
```

**Downgrade duplicate guard pattern** (`src/db/migrations/versions/012_thread_user_scope.py` lines 33-70): if adding unique indexes to existing data, copy the pre-downgrade duplicate check style where necessary.

**Likely indexes to add if planner chooses DB-backed idempotency:**
- `uq_conversation_messages_active_tenant_run_role` on `conversation_messages(tenant_id, run_id, role)` where `deleted_at IS NULL AND role IN ('user','assistant')`.
- `uq_summaries_thread_rolling_source_end` on `summaries(tenant_id, conversation_thread_id, summary_type, source_end_message_id)` where `deleted_at IS NULL AND summary_type = 'thread_rolling' AND source_end_message_id IS NOT NULL`.

---

### `src/memory/thread_summary.py` (service, transform + CRUD)

**Analog:** same file.

**Build input pattern** (`src/memory/thread_summary.py` lines 51-83): summary input comes from latest summary, messages after prior summary, and prompt-safe tool results.
```python
old_summary = await self.repository.get_latest_thread_summary(...)
effective_since = since_message_id
if effective_since is None and old_summary is not None:
    effective_since = old_summary.source_end_message_id
new_messages = await self.repository.list_messages_after(... since_message_id=effective_since)
tool_results = await self.repository.list_tool_results_after_summary(... previous_summary=old_summary)
```

**Persist pattern needing idempotency** (`src/memory/thread_summary.py` lines 116-155):
```python
if not update_input.new_messages:
    return None
derived = self.derive_summary(...)
source_message_ids = [str(message.id) for message in update_input.new_messages]
source_tool_result_ids = [str(result.id) for result in update_input.important_tool_results]
return await self.repository.insert_thread_summary(
    source_start_message_id=update_input.new_messages[0].id,
    source_end_message_id=update_input.new_messages[-1].id,
    source_message_ids_json=source_message_ids,
    source_tool_result_ids_json=source_tool_result_ids,
    summary_hash=derived.summary_hash,
)
```

**Sanitizer pattern** (`src/memory/thread_summary.py` lines 158-176): preserve this; do not summarize raw refs or authority bodies.
```python
segments = [segment.strip() for segment in compact.split(" | ") if segment.strip()]
kept_segments = [segment for segment in segments if not segment.lower().startswith(_RAW_REF_PREFIX)]
...
sanitized = re.sub(rf"\b{re.escape(key)}\b\s*[:=]?", "[redacted]", sanitized, flags=re.IGNORECASE)
```

**Needed change:** use `run_id` or source range instead of `del run_id` (line 125) for idempotent completed-turn summaries.

---

### `src/agent/nodes/investigate.py` (node/hook, event-driven + CRUD)

**Analog:** same file. Usually no code change needed if `/agent-runs` supplies config correctly.

**Tool conversation persistence gate** (`src/agent/nodes/investigate.py` lines 264-343):
```python
if not _can_persist_conversation_tool_records(configurable, session):
    return None
...
conversation_message_id=configurable.get("conversation_message_id"),
...
def _can_persist_conversation_tool_records(configurable: dict[str, Any], session: Any) -> bool:
    return (
        session is not None
        and hasattr(session, "execute")
        and hasattr(session, "flush")
        and configurable.get("conversation_message_id") is not None
    )
```

**Safe projection pattern** (`src/agent/nodes/investigate.py` lines 355-407, 612-629): fallback projection strips raw payloads and prompt summary only uses safe refs.
```python
prompt_summary = _safe_prompt_summary(...)
...
forbidden = {
    "raw",
    "raw_args",
    "raw_payload",
    "raw_tool_output",
    "replay_blob",
    "approval_authority_body",
    "action_authority_body",
}
```

---

### `src/agent/nodes/memory_write.py` and `src/agent/nodes/session_memory_load.py` (nodes, CRUD + transform)

**Analogs:** same files; `src/memory/service.py`.

**Session load pattern** (`src/agent/nodes/session_memory_load.py` lines 18-47): same-thread PostgreSQL memory load fails closed to observable fallback.
```python
if settings.session_memory_enabled is False:
    return _fallback(state, started_at, source="disabled", fallback_reason="disabled")
if session is None:
    return _fallback(state, started_at, source="unavailable", fallback_reason="missing_async_session")
...
view = await service.load_session_memory(
    tenant_id=state["tenant_id"],
    user_id=state["user_id"],
    thread_id=state["thread_id"],
    current_intent=state.get("primary_intent") or state.get("current_intent"),
)
```

**Memory service CAS/override pattern** (`src/memory/service.py` lines 116-200 and 289-341): explicit current candidate slots overwrite loaded slots; CAS retry can conflict if concurrent different slot value appears.
```python
existing = await self.repository.get_active(... include_expired=True)
...
merge = _merge_memory(existing, candidate, now=now, cas_retry=False)
updated = await self.repository.cas_update(existing.id, expected_version, merge.values)
...
for slot_name, candidate_slot in candidate.explicit_slots.items():
    existing_slot = merged_slots.get(slot_name)
    if cas_retry and existing_slot is not None and existing_slot.value != candidate_slot.value:
        return _MergeResult({}, "explicit_slot_conflict")
    merged_slots[slot_name] = candidate_slot
```

---

### `src/agent/nodes/extract_slots.py` and `src/agent/nodes/generate_recommendation.py` (nodes, prompt context)

**Analog:** `generate_recommendation.py` already loads conversation prompt context safely; `extract_slots.py` currently passes empty prior context.

**Existing empty slot prompt context** (`src/agent/nodes/extract_slots.py` lines 125-144): if STM-05 requires ambiguous reference resolution before routing, replace these empty values only through `ConversationService.load_prompt_context` + `ContextAssembler`.
```python
return ContextAssembler().assemble(
    system_prompt=EXTRACT_SLOTS_SYSTEM,
    current_user_message=str(state.get("normalized_query") or state.get("user_query") or ""),
    working_state=project_working_state(state),
    thread_rolling_summary="",
    recent_messages=[],
    verified_policy_snippets=[],
    profile_memory_snippets=state.get("long_term_memory") or [],
    case_memory_snippets=state.get("case_memory") or [],
    tool_result_summaries=[],
    business_context={},
    node_hints=node_hints,
)
```

**Safe prompt context loader to copy** (`src/agent/nodes/generate_recommendation.py` lines 567-596 and 598-667):
```python
prompt_context = await _load_prompt_context(state, config)
return ContextAssembler().assemble(
    system_prompt=GENERATE_RECOMMENDATION_SYSTEM,
    current_user_message=str(state.get("normalized_query") or state.get("user_query") or ""),
    working_state=project_working_state(state),
    thread_rolling_summary=prompt_context["thread_rolling_summary"],
    recent_messages=prompt_context["recent_messages"],
    tool_result_summaries=[*prompt_context["tool_result_summaries"], *(state.get("tool_results") or [])],
    business_context=state.get("business_context") or {},
)
...
context = await service.load_prompt_context(
    tenant_id=state["tenant_id"],
    user_id=state["user_id"],
    thread_id=str(state["thread_id"]),
    run_id=run_id,
)
```

---

### `src/agent/context/assembler.py` and `src/agent/context/projectors.py` (utilities, transform)

**Analog:** same files.

**Assembler safety constraints** (`src/agent/context/assembler.py` lines 20-24):
```python
DEFAULT_SAFETY_CONSTRAINTS = (
    "Use only prompt-safe summaries and refs.",
    "Do not expose private reasoning, upstream payloads, authority objects, or debug traces.",
    "Require policy evidence before recommending material action.",
)
```

**Assembler block order** (`src/agent/context/assembler.py` lines 31-105): current user/system/policy blocks are protected and memory/recent/tool context stays projected.
```python
blocks: list[PromptBlock] = [PromptBlock("system_prompt", system_prompt, priority=100, protected=True)]
...
if thread_rolling_summary:
    blocks.append(PromptBlock("thread_rolling_summary", thread_rolling_summary, priority=70))
...
recent_block = _project_recent_messages(recent_messages)
if recent_block:
    blocks.append(PromptBlock("recent_messages", recent_block, priority=60))
blocks.append(PromptBlock("current_user_message", current_user_message, priority=100, protected=True))
```

**Projector allowlist/denylist** (`src/agent/context/projectors.py` lines 13-27, 144-170, 252-257, 360-380): copy projector usage, not raw dict stringification.
```python
_UNSAFE_KEY_TOKENS = ("raw", "payload", "body", "full", "private", "reasoning", "debug", "trace", "snapshot", "hash", "completion", "authority")
...
def project_tool_result_summary(...):
    ...
    if summary.raw_result_ref:
        lines.append(f"raw_result_ref={_bounded(summary.raw_result_ref, 160)}")
...
def project_recent_message_for_prompt(message: Mapping[str, Any], *, max_chars: int = 500) -> str:
    role = _safe_scalar(message.get("role")) or "message"
    content = _safe_scalar(message.get("content")) or ""
    return _bounded(f"{role}: {content}", max_chars)
```

## Test Pattern Assignments

### `tests/test_agent_runs_api.py` (API/SSE tests)

**Analog:** same file.

**Fake graph fixtures** (`tests/test_agent_runs_api.py` lines 25-50): extend `CaptureConfigGraph` to assert conversation IDs in graph config.
```python
class CaptureConfigGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict]] = []

    async def astream(self, input_state, config, stream_mode):
        self.calls.append((input_state, config))
        yield ("final_response", {"final_response": "done", "trace_steps": []})
```

**Duplicate SSE guard tests** (`tests/test_agent_runs_api.py` lines 385-428): extend these with counts for conversation messages/summaries/session writes.

**Cancellation/error pattern** (`tests/test_agent_runs_api.py` lines 456-495 and 624-655): assert error/cancel paths keep run/trace state but no assistant message or summary.

**Old ordering test to replace** (`tests/test_agent_runs_api.py` lines 827-858): this currently asserts Phase-23 behavior. Replace with `test_sse_final_response_after_bounded_memory_persistence_result`.
```python
if "data" in event and '"event_type": "final_response"' in event["data"]:
    final_event = event
    assert scheduled == []
    break
...
assert scheduled
```

**Interrupted path no memory write** (`tests/test_agent_runs_api.py` lines 861-885): keep and extend to no assistant message/no summary.

---

### `tests/conversation/test_service.py` (service tests)

**Analog:** same file.

**Append user/assistant message test pattern** (`tests/conversation/test_service.py` lines 36-77): copy for run/role get-once helpers.

**Prompt-context first-turn test** (`tests/conversation/test_service.py` lines 121-152): use for `/agent-runs` first turn after POST creates a user message.

**Completed chat summary test** (`tests/conversation/test_service.py` lines 155-267): copy arrangement for user + tool + assistant + `ThreadRollingSummaryService`.

**Latest prior summary/current recent messages pattern** (`tests/conversation/test_service.py` lines 270-390): this is the direct test analog for STM-05.

**User scoping pattern** (`tests/conversation/test_service.py` lines 393-454): preserve tenant/user/thread isolation in every new context lookup.

---

### `tests/memory/test_thread_summary.py` (thread summary tests)

**Analog:** same file.

**Source range assertions** (`tests/memory/test_thread_summary.py` lines 85-123): extend with idempotent repeat call assertions.

**Safe tool summaries only** (`tests/memory/test_thread_summary.py` lines 126-201): copy forbidden marker style for `/agent-runs` persisted tool summaries.

**Thread summary separation** (`tests/memory/test_thread_summary.py` lines 245-300): keep `thread_rolling` separate from session/case memory.

---

### `tests/memory/test_session_memory_service.py` (session memory CAS tests)

**Analog:** same file.

**Explicit override** (`tests/memory/test_session_memory_service.py` lines 89-119): current explicit slots override existing stored slots.

**CAS merge/conflict** (`tests/memory/test_session_memory_service.py` lines 121-177 and 304-329): use for bounded finalizer session-memory write assertions.

**Fallback/PII observability** (`tests/memory/test_session_memory_service.py` lines 401-468): memory write failures/skips must be explicit, not silent.

**Thread rolling separation** (`tests/memory/test_session_memory_service.py` lines 502-582): summary rows must not become session memory.

---

### `tests/agent/context/test_assembler.py` (prompt projection tests)

**Analog:** same file.

**Block composition** (`tests/agent/context/test_assembler.py` lines 69-103): assert `thread_rolling_summary`, `recent_messages`, `policy_refs`, and `tool_summaries` appear as separate blocks.

**Raw/authority exclusion** (`tests/agent/context/test_assembler.py` lines 105-166): copy forbidden marker assertions for any new prompt context path.

**Memory cannot evict protected authority/user blocks** (`tests/agent/context/test_assembler.py` lines 359-415): preserve priority/protected behavior.

---

### `tests/agent/test_session_memory_integration.py` and `tests/agent/test_required_slots.py` (graph/session tests)

**Analog:** same files.

**Three-turn smoke pattern** (`tests/agent/test_session_memory_integration.py` lines 103-171): copy for STM-14 `/agent-runs` smoke; it verifies same-thread memory resolves vague follow-up while still re-running tools.

**Current-turn override pattern** (`tests/agent/test_session_memory_integration.py` lines 195-232; `tests/agent/test_required_slots.py` lines 45-72, 101-125): explicit current-turn slot wins over inherited session memory.

**Fails-closed pattern** (`tests/agent/test_session_memory_integration.py` lines 235-276; `tests/agent/test_required_slots.py` lines 20-43, 101-138): disabled/unavailable/stale/wrong-scope memory leads to clarification or current-turn-only behavior.

---

### `tests/agent/test_memory_evidence_boundary.py` and `tests/agent/rag_context/test_authority_boundaries.py` (authority boundary tests)

**Analog:** same files.

**Memory write excludes authority/evidence/raw payloads** (`tests/agent/test_memory_evidence_boundary.py` lines 58-133): use this marker style when asserting `/agent-runs` finalizer does not persist authority bodies into memory.

**Memory cannot satisfy policy/action authority** (`tests/agent/test_memory_evidence_boundary.py` lines 168-288; `tests/agent/rag_context/test_authority_boundaries.py` lines 114-209): Phase 24 prompt context tests should assert memory helps references only; current business facts and policy claims still require tool/evidence refs.

## Shared Patterns

### Authentication And Trusted Config

**Source:** `src/api/routers/agent_runs.py` lines 64-78 and 139-169.  
**Apply to:** `src/api/routers/agent_runs.py`, any new finalizer/helper config call sites.

Use `Security(get_current_user, scopes=["agent:chat"])`, verified token scopes from `request.state`, `_trusted_tool_config`, and DB `User` fields. Do not trust tenant/user/thread IDs from request payload beyond the authenticated run boundary.

### Exactly-Once User/Assistant Conversation Rows

**Source:** `src/api/routers/agent.py` lines 89-99 and 187-201; `src/conversation/service.py` lines 35-85 and 264-305; `src/conversation/repository.py` lines 42-93.  
**Apply to:** `create_agent_run`, completed-run finalizer, legacy compatibility helper extraction.

Planner should prefer DB-backed idempotency for `(tenant_id, run_id, role)` on `conversation_messages` plus service-level get-or-create methods. SSE retry must resolve the same user message and completed finalizer must resolve the same assistant message.

### Tool Summary Attachment

**Source:** `src/agent/nodes/investigate.py` lines 264-343; `src/conversation/service.py` lines 147-217.  
**Apply to:** `/agent-runs` SSE graph config.

`investigate` persists tool rows only when `conversation_message_id` exists in trusted config. Phase 24 must wire current-turn user message ID before graph streaming starts.

### Completed-Only Terminal Memory

**Source:** `src/agent/nodes/memory_write.py` lines 37-65 and 306-312; `src/api/routers/agent_runs.py` lines 608-670 for interrupted handling.  
**Apply to:** completed-run finalizer and error/cancel/interruption paths.

Only completed runs with a final response write assistant messages, rolling summaries, and successful session memory. Error/cancel/interrupted paths preserve run/trace/tool/approval records but must not create false completed conversation memory.

### Prompt-Safe Projection Boundary

**Source:** `src/conversation/service.py` lines 219-262; `src/agent/context/assembler.py` lines 20-105; `src/agent/context/projectors.py` lines 13-27 and 144-170.  
**Apply to:** any prompt context loading or slot-reference resolution change.

Use `ConversationService.load_prompt_context` and `ContextAssembler`. Do not stringify raw DB rows, raw tool results, approval/action objects, replay/debug blobs, policy authority bodies, or arbitrary dicts.

### Session Memory CAS And Fallback

**Source:** `src/memory/service.py` lines 52-114 and 116-200; `src/memory/repository.py` lines 26-76 and 121-143.  
**Apply to:** bounded terminal memory persistence and graph same-thread continuity tests.

Session memory is scoped by `tenant_id`, `user_id`, `thread_id`; explicit current-turn slots override inherited slots; CAS conflicts and unavailable storage return typed results rather than silent success.

### Migration Style

**Source:** `src/db/migrations/versions/012_thread_user_scope.py` lines 16-30 and 33-70.  
**Apply to:** any new idempotency migration.

Use focused Alembic revisions, explicit `down_revision`, named indexes, `postgresql_where=sa.text(...)`, and downgrade safety checks when unique constraints can be invalidated by existing data.

## No Analog Found

None. New `src/api/services/agent_run_memory.py` and the inferred idempotency migration do not have exact file-level analogs, but strong role-match patterns exist in legacy chat terminal persistence, current `/agent-runs` lifecycle helpers, memory services, and focused migrations.

## Metadata

**Analog search scope:** `src/api/routers`, `src/conversation`, `src/db/models.py`, `src/db/migrations/versions`, `src/memory`, `src/agent/nodes`, `src/agent/context`, `tests/`  
**Files scanned/read:** 30 source/test/migration files plus Phase 24 context/research and project rules  
**Pattern extraction date:** 2026-06-20  
**Project rules applied:** Chinese artifact output; no source code edits; only `.planning/phases/24-agent-runs-short-term-memory-parity/24-PATTERNS.md` written.
