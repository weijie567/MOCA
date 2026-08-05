# Phase 59: Approval Resume Terminal Memory Finalization - Pattern Map

**Mapped:** 2026-07-08  
**Files analyzed:** 10  
**Analogs found:** 10 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/api/routers/approvals.py` | route/controller | request-response + event-driven graph resume + DB persistence | `src/api/routers/agent_runs.py` terminal completion + current approval resume lifecycle | exact |
| `src/api/routers/agent_runs.py` | route/controller | streaming + request-response + terminal side effects | existing `_complete_run(...)` / `_persist_finalizer_trace_steps(...)` in same file | exact |
| `src/api/services/agent_run_memory.py` | service | batch/transform + DB side effects + isolated memory I/O | existing `finalize_completed_agent_run_memory(...)` in same file | exact |
| `src/agent/nodes/memory_write.py` | graph node | transform + DB write | existing `memory_write(...)` skip/write paths in same file | exact |
| `tests/test_approval_api.py` | test | request-response + event-driven approval resume | existing approval resume tests in same file; finalizer assertions from `tests/test_agent_runs_api.py` | exact |
| `tests/test_agent_runs_api.py` | test | streaming + terminal finalizer side effects | existing finalizer/idempotency tests in same file | exact |
| `tests/agent/test_memory_write_node.py` | test | transform/unit | existing memory write skip/write tests in same file | role-match |
| `tests/architecture/test_canonical_graph_baseline.py` | test | static/architecture guard | existing Phase 58 canonical vocabulary tests in same file | exact, verification-only |
| `.planning/ARCHITECTURE-DEBT.md` | planning ledger | append-only documentation | existing Memory ledger entries in same file | exact, conditional |
| `.planning/LOCAL-VALIDATION-ISSUES.md` | validation ledger | append-only documentation | existing local validation issue entries in same file | exact, conditional |

## Pattern Assignments

### `src/api/routers/approvals.py` (route/controller, request-response + event-driven graph resume)

**Analog:** `src/api/routers/agent_runs.py` normal terminal finalizer lifecycle, plus existing approval resume helpers in `approvals.py`.

**Imports pattern** (`src/api/routers/approvals.py` lines 7-20, 30-43):
```python
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from langgraph.errors import GraphInterrupt
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.action_draft import action_draft
from src.agent.trace import append_agent_steps, update_agent_run_status
from src.auth.permissions import get_current_user
from src.db.models import AgentRun, ApprovalRequest, User
from src.db.session import get_session
```

**Auth/guard pattern** (`src/api/routers/approvals.py` lines 57-65, 109-112):
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
```

**Resume lifecycle pattern** (`src/api/routers/approvals.py` lines 239-263):
```python
await _record_resume_event(session=session, result=result, actor_id=actor_id, resume_status="attempted")
await session.commit()

await _resume_graph_after_decision(
    request=request,
    session=session,
    result=result,
    actor_user=actor_user,
)
await _record_resume_event(session=session, result=result, actor_id=actor_id, resume_status="completed")
await session.commit()
```

**Correct insertion point** (`src/api/routers/approvals.py` lines 318-349):
```python
final_response_text = final_state.get("final_response")
final_status = "completed"
if final_state.get("node_errors") or not final_response_text:
    final_status = "error"
run = await session.get(AgentRun, result.run_id)
...
await update_agent_run_status(..., final_status=final_status, final_response=final_response_text, ...)

trace_steps = final_state.get("trace_steps") or []
pre_interrupt_count = next(
    (idx + 1 for idx, step in enumerate(trace_steps) if step.get("node") == "approval_gate"),
    len(trace_steps),
)
if pre_interrupt_count < len(trace_steps):
    await append_agent_steps(session, run_id=run_id, trace_steps=trace_steps, start_index=pre_interrupt_count)
```

Apply the shared finalizer only after this status/trace persistence succeeds and only when `final_status == "completed"` and `final_response_text` is present.

**Interrupted skip pattern** (`src/api/routers/approvals.py` lines 351-407):
```python
await update_agent_run_status(
    session,
    run_id=str(result.run_id),
    final_status="interrupted",
    final_response=None,
    completed_at=datetime.now(UTC),
    total_latency_ms=total_latency_ms,
    trace_id=getattr(request.state, "trace_id", None),
    reason_code="approval_resume_interrupted",
    emit_if_unchanged=True,
)
```

Do not run terminal memory finalization in this branch.

**Error handling pattern** (`src/api/routers/approvals.py` lines 264-280):
```python
except Exception as exc:
    await session.rollback()
    await _record_resume_event(
        session=session,
        result=result,
        actor_id=actor_id,
        resume_status="failed",
        error=exc,
    )
    await session.commit()
    raise HTTPException(status_code=500, detail={"code": "APPROVAL_RESUME_FAILED", ...}) from exc
```

**Retry/idempotency gate pattern** (`src/api/routers/approvals.py` lines 445-475, 478-495):
```python
latest_resume_status = await _latest_resume_status(session, approval)
if latest_resume_status not in RESUME_INCOMPLETE_STATUSES:
    return None

run = await session.get(AgentRun, approval.run_id)
if run is not None and run.final_status not in {"interrupted", "running", "pending"}:
    return None
```

If Phase 59 creates terminal finalizer surfaces before the final `approval_resumed/completed` event, tests must prove retry does not duplicate assistant message, summary, finalizer step, memory writes, or action drafts.

**Trusted resume identity pattern** (`src/api/routers/approvals.py` lines 729-749):
```python
trusted_context = TrustedContextFactory.create_from_request(
    user=actor_user,
    verified_token_scopes=frozenset(),
    thread_id=result.graph_thread_id,
    run_id=str(result.run_id),
    trace_id=getattr(request.state, "trace_id", "") or "",
    server_tool_permissions=permissions,
)
```

This is reviewer/admin identity for trusted graph resume only. The terminal finalizer must fetch the requester from `run.user_id` and pass that requester as `user`.

**Action-draft reconciliation boundary** (`src/api/routers/approvals.py` lines 638-693):
```python
existing = (
    await session.execute(
        select(ActionDraft.id).where(
            ActionDraft.run_id == result.run_id,
            ActionDraft.approval_request_id == result.approval_id,
        )
    )
).scalar_one_or_none()
if existing is not None:
    return final_state
```

Do not change this behavior unless a Phase 59 test proves it is required.

---

### `src/api/routers/agent_runs.py` (route/controller, streaming + terminal side effects)

**Analog:** existing normal run completion and finalizer trace persistence.

**Imports pattern** (`src/api/routers/agent_runs.py` lines 17-31):
```python
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sse_starlette.sse import EventSourceResponse

from src.agent.trace import append_agent_steps, build_trace_summary, update_agent_run_status, write_agent_run, write_agent_steps
from src.api.services.agent_run_memory import finalize_completed_agent_run_memory
```

**Normal graph-updates finalizer pattern** (`src/api/routers/agent_runs.py` lines 383-410):
```python
await _complete_run(..., trace_steps=trace_steps, final_state=final_state)
finalizer_result = await finalize_completed_agent_run_memory(
    session=session,
    run=run,
    user=user,
    input_state=input_state,
    final_state=final_state,
    final_status=str(final_status),
    final_response=str(final_response) if final_response else None,
    trace_steps=trace_steps,
    trace_id=config.get("configurable", {}).get("trace_id"),
    conversation_service=config.get("configurable", {}).get("conversation_service"),
)
await _persist_finalizer_trace_steps(session=session, run=run, prior_trace_steps=trace_steps, finalizer_trace_steps=finalizer_result.trace_steps)
```

The lifecycle-events generator uses the same pattern (`src/api/routers/agent_runs.py` lines 547-574). Keep both call sites aligned if moving `_persist_finalizer_trace_steps(...)` to a shared service helper.

**Complete-and-commit pattern** (`src/api/routers/agent_runs.py` lines 1037-1065):
```python
try:
    await update_agent_run_status(..., final_state=final_state)
    run.total_tokens = _count_tokens(trace_steps)
    if trace_steps:
        await write_agent_steps(session, run_id=str(run.id), trace_steps=trace_steps)
    await session.commit()
except Exception:
    await session.rollback()
    raise
```

Approval resume should preserve this ordering: durable run completion + graph trace first, then terminal memory finalizer.

**Existing trace persistence pattern requiring hardening** (`src/api/routers/agent_runs.py` lines 1068-1087):
```python
async def _persist_finalizer_trace_steps(...):
    if not finalizer_trace_steps:
        return
    try:
        await append_agent_steps(
            session,
            run_id=str(run.id),
            trace_steps=[*prior_trace_steps, *finalizer_trace_steps],
            start_index=len(prior_trace_steps),
        )
        await session.commit()
    except Exception:
        await session.rollback()
```

This is only a partial analog. Phase 59 should move/share this helper and add a duplicate guard for `node_name == "agent_run_memory_finalize"` before appending.

---

### `src/api/services/agent_run_memory.py` (service, terminal finalizer side effects)

**Analog:** existing `finalize_completed_agent_run_memory(...)`.

**Imports/constants/dataclasses pattern** (`src/api/services/agent_run_memory.py` lines 8-24, 29-50):
```python
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.memory_write import memory_write
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.db.models import AgentRun, User
from src.memory.case_working_context_lifecycle import CaseWorkingContextLifecycleAdapter
from src.memory.write_isolation import run_memory_side_effect_in_isolated_session
from src.memory.thread_summary import ThreadRollingSummaryService

FINALIZER_NODE = "agent_run_memory_finalize"
FINALIZER_SOURCE = "agent_runs.finalizer"
```

**Finalizer signature and skip behavior** (`src/api/services/agent_run_memory.py` lines 53-77):
```python
async def finalize_completed_agent_run_memory(
    *,
    session: AsyncSession,
    run: AgentRun,
    user: User,
    input_state: dict[str, Any],
    final_state: dict[str, Any],
    final_status: str,
    final_response: str | None,
    trace_steps: list[dict[str, Any]],
    trace_id: str | None = None,
    conversation_service: ConversationService | None = None,
) -> AgentRunMemoryFinalizeResult:
    if final_status != "completed" or not _has_final_response(final_response):
        return AgentRunMemoryFinalizeResult(..., memory_write_result={"status": "skipped", "reason_code": "not_completed_path"}, trace_steps=[])
```

**Assistant message + summary idempotent surface** (`src/api/services/agent_run_memory.py` lines 79-97):
```python
assistant_message = await conversation_service.append_or_get_assistant_message_for_run(
    tenant_id=run.tenant_id,
    user_id=run.user_id,
    thread_id=run.thread_id,
    run_id=run.id,
    content=str(final_response),
    trace_id=trace_id,
    metadata_json={"status": "completed", "source": FINALIZER_SOURCE},
)
thread_summary = await ThreadRollingSummaryService(conversation_repository).persist_thread_summary(
    tenant_id=run.tenant_id,
    user_id=run.user_id,
    thread_id=run.thread_id,
    run_id=run.id,
)
await session.commit()
```

**Memory/CWC side-effect pattern** (`src/api/services/agent_run_memory.py` lines 97-138):
```python
memory_write_execution = await _run_terminal_memory_write(...)
memory_write_result = memory_write_execution.result
memory_write_status = _canonical_memory_write_status(memory_write_result)
case_working_context_execution = await _run_terminal_case_working_context_write(...)
case_working_context_status = _canonical_case_working_context_status(case_working_context_result)
trace_step = _trace_step(...)
return AgentRunMemoryFinalizeResult(..., trace_steps=[trace_step])
```

**Isolated memory write pattern** (`src/api/services/agent_run_memory.py` lines 151-197):
```python
memory_state = _memory_state(...)
try:
    result_state = await run_memory_side_effect_in_isolated_session(
        session,
        lambda memory_session: memory_write(
            memory_state,
            {"configurable": {"session": memory_session, "trace_id": trace_id or ""}},
        ),
    )
except TimeoutError:
    return TerminalMemoryWriteExecution(result={"status": "skipped", "reason_code": "write_timeout"}, ...)
except Exception as exc:
    return TerminalMemoryWriteExecution(result={"status": "error", "reason_code": "write_failed", "error_type": type(exc).__name__}, ...)
```

If using a state sanitizer, apply it only to `memory_state` before this call. Preserve the original `final_state` for CWC projection.

**CWC writeback pattern** (`src/api/services/agent_run_memory.py` lines 199-217):
```python
lifecycle_result = await CaseWorkingContextLifecycleAdapter().write_after_terminal_success(
    session=session,
    tenant_id=run.tenant_id,
    user_id=user.id,
    thread_id=run.thread_id,
    run_id=run.id,
    final_state=final_state,
    final_response=final_response,
)
```

**Canonical identity merge pattern** (`src/api/services/agent_run_memory.py` lines 255-276):
```python
memory_state = {
    **input_state,
    **final_state,
    "final_response": final_response,
}
memory_state["tenant_id"] = str(run.tenant_id)
memory_state["user_id"] = str(user.id)
memory_state["thread_id"] = run.thread_id
memory_state["current_run_id"] = str(run.id)
memory_state["role"] = user.role
```

This is why approval resume must pass the requester, not the reviewer/admin actor.

**Trace metrics pattern** (`src/api/services/agent_run_memory.py` lines 299-334):
```python
return {
    "node": FINALIZER_NODE,
    "status": memory_write_status,
    "metrics_json": {
        "assistant_message_id": assistant_message_id,
        "thread_summary_id": thread_summary_id,
        "memory_write_status": memory_write_status,
        "case_working_context_status": case_working_context_status,
        "case_working_context_memory_id": case_working_context_result.get("memory_id"),
        "case_working_context_version": case_working_context_result.get("version"),
    },
}
```

---

### `src/agent/nodes/memory_write.py` (graph node, transform + DB write)

**Analog:** existing `memory_write(...)` skip/write behavior.

**Imports/constants pattern** (`src/agent/nodes/memory_write.py` lines 9-31):
```python
from langchain_core.runnables import RunnableConfig

from src.agent.events import emit_event
from src.agent.state import AgentState
from src.config import settings
from src.memory.context_service import MemoryContextService
from src.memory.write_service import MemoryWriteCandidate, MemoryWriteResult, MemoryWriteService
```

**Current terminal eligibility gate** (`src/agent/nodes/memory_write.py` lines 42-50):
```python
async def memory_write(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    final_response = state.get("final_response")
    if not final_response:
        return _skipped(state, started_at, "not_completed_path")
    if _approval_or_interrupted(state):
        return _skipped(state, started_at, "not_completed_path")
    if settings.session_memory_enabled is False:
        return _skipped(state, started_at, "disabled")
```

**Approval/interrupted skip predicate** (`src/agent/nodes/memory_write.py` lines 354-360):
```python
def _approval_or_interrupted(state: AgentState) -> bool:
    if state.get("approval_result") or state.get("approval_required"):
        return True
    risk = state.get("risk_assessment")
    if isinstance(risk, dict) and risk.get("approval_required") is True:
        return True
    return state.get("final_status") == "interrupted"
```

Phase 59 must not globally weaken this predicate. Either add a narrow terminal-finalizer flag accepted here, or sanitize the state passed by `_run_terminal_memory_write(...)` while keeping pending/interrupted approval states skipped.

**Skipped output shape** (`src/agent/nodes/memory_write.py` lines 175-196):
```python
result = {
    "status": "skipped",
    "decision": "skip",
    "reason_code": reason_code,
    "pii_classification": "none",
}
return {
    "final_response": final_response if final_response is not None else state.get("final_response"),
    "memory_write_result": result,
    "memory_write_decision": decision,
    "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, result, decision)],
}
```

**Completed output shape** (`src/agent/nodes/memory_write.py` lines 152-172):
```python
result_dict = result.model_dump(mode="json")
decision = _memory_write_decision(state, result_dict, candidate=candidate)
output = {
    "final_response": state.get("final_response"),
    "memory_write_candidates": [_candidate_projection(item) for item in (candidates or [candidate])],
    "memory_write_result": result_dict,
    "memory_write_decision": decision,
    "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, result_dict, decision)],
}
```

---

### `tests/test_approval_api.py` (integration test, request-response + approval resume)

**Analogs:** existing approval resume tests in same file and finalizer assertions from `tests/test_agent_runs_api.py`.

**Imports/fake graph pattern** (`tests/test_approval_api.py` lines 1-20, 32-46):
```python
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.api.main import app
from src.api.routers import approvals as approvals_router
from src.db.models import AgentRun, ApprovalAssignment, ApprovalDecision, ApprovalEvent, ApprovalLevel, ApprovalRequest, User

class FakeResumeGraph:
    async def ainvoke(self, command, config):
        self.calls.append((command, config))
        return {"final_response": self.final_response, "trace_steps": [...]}
```

For finalizer assertions, copy imports from `tests/test_agent_runs_api.py` lines 36-48:
```python
from src.db.models import (
    AgentRun,
    AgentStep,
    CaseWorkingContext,
    ConversationMessage,
    ConversationSummary,
    MemoryWriteEvent,
    User,
)
```

**Factory/auth pattern** (`tests/test_approval_api.py` lines 139-216, 230-240, 1529-1536):
```python
def _auth_header(user: User, scopes: list[str]) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role, "scopes": scopes})
    return {"Authorization": f"Bearer {token}"}

async def _create_approval(...):
    run_id = await _create_run(session, tenant_id=tenant.id, user_id=requester.id, thread_id=thread_id)
    created = await ApprovalService(session).create_request(_create_command(...))
    ...
    await session.commit()
    return ApprovalBundle(approval=approval, level=level, assignment=assignment)
```

**Trusted resume assertions to preserve** (`tests/test_approval_api.py` lines 414-453):
```python
response = await client.post(
    f"/api/v1/approvals/{bundle.approval.id}/decide",
    json=_decision_body(bundle, "approve"),
    headers=await _admin_headers(client),
)
...
trusted_context = config["configurable"]["trusted_context"]
assert trusted_context["user_id"] == str(admin.id)
assert trusted_context["role"] == "admin"
assert trusted_context["permissions"] == [approvals_router.ACTION_DRAFT_PERMISSION]
```

Add separate Phase 59 assertions that finalizer memory identity uses `bundle.approval.requested_by` / `run.user_id`, not this admin `trusted_context`.

**Commit-before-resume pattern** (`tests/test_approval_api.py` lines 456-493):
```python
async def spy_commit():
    nonlocal commit_count
    commit_count += 1
    await original_commit()

async def spy_ainvoke(command, config):
    graph_commit_counts.append(commit_count)
    return await FakeResumeGraph.ainvoke(graph, command, config)

assert graph_commit_counts == [2]
assert commit_count == 3
```

Update expected commit counts only if Phase 59 intentionally adds a new durable finalizer commit before `approval_resumed/completed`; make that change explicit in the test.

**Recoverable retry pattern** (`tests/test_approval_api.py` lines 495-573):
```python
async def fail_final_resume_commit():
    nonlocal commit_count
    commit_count += 1
    if commit_count == 3:
        raise RuntimeError("simulated final commit failure")
    await original_commit()
...
assert first_response.status_code == 500
assert {"attempted", "failed"} <= resume_statuses
...
assert retry_response.status_code == 200
assert run.final_status == "completed"
assert completed_statuses.count("completed") == 1
assert len(graph.calls) == 2
```

Extend this style to simulate failure after finalizer surfaces are created and assert counts stay idempotent.

**Re-interrupt regression pattern** (`tests/test_approval_api.py` lines 906-963):
```python
graph = ReinterruptResumeGraph(target_merchant_id=str(seeded_session["merchant"].id))
monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
...
assert payload["data"]["status"] == "superseded"
assert replacement.status == "pending"
assert str(replacement.id) in manager_ids
assert str(bundle.approval.id) not in manager_ids
```

Add Phase 59 assertions that interrupted-again paths have zero assistant messages, summaries, `MemoryWriteEvent` rows, and `agent_run_memory_finalize` steps.

**Canonical route guard pattern** (`tests/test_approval_api.py` lines 1233-1249):
```python
assert approvals_router._should_resume_graph(canonical) is True
assert approvals_router._should_resume_graph(legacy) is False
assert legacy_lines == ['HISTORICAL_RETRY_ROUTE_TO_CANONICAL = {"assess_risk_and_approval": CANONICAL_RISK_ROUTE}']
```

Keep this guard in the Phase 59 verification set.

**Current completed-status test to extend** (`tests/test_approval_api.py` lines 1505-1526):
```python
monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph("approved final"), raising=False)
response = await client.post(..., json=_decision_body(bundle), headers=await _admin_headers(client))
run = await session.get(AgentRun, bundle.approval.run_id)
assert run.final_status == "completed"
assert run.final_response == "approved final"
```

Use this as the base for the new completed finalizer regression: add approval markers and CWC-eligible final state to the fake graph, then assert assistant message, summary, finalizer step, memory-write status, and CWC metrics.

---

### `tests/test_agent_runs_api.py` (integration test, streaming + terminal finalizer)

**Analog:** existing finalizer tests.

**Imports pattern** (`tests/test_agent_runs_api.py` lines 12-54):
```python
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.services.agent_run_memory import finalize_completed_agent_run_memory
from src.db.models import AgentRun, AgentStep, CaseWorkingContext, ConversationMessage, ConversationSummary, MemoryWriteEvent
from src.memory.case_working_context_lifecycle import CaseWorkingContextLifecycleResult, lifecycle_status
```

**Input-state and CWC terminal state pattern** (`tests/test_agent_runs_api.py` lines 846-890):
```python
def _stream_input(run: AgentRun, user: User) -> dict[str, str]:
    return {
        "user_query": run.input_query,
        "thread_id": run.thread_id,
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.id),
        "role": user.role,
        "current_run_id": str(run.id),
    }

def _cwc_terminal_state(seeded_session: dict, *, user_query: str = "请帮我看看退款进度") -> dict:
    return {"active_slots": {"refund_case_id": refund_case.refund_case_no, "issue_type": "refund_status"}, ...}
```

Approval resume should reconstruct the same input-state shape from the persisted `AgentRun` and requester.

**DB assertion helpers** (`tests/test_agent_runs_api.py` lines 935-945):
```python
async def _messages_for_run(session: AsyncSession, *, run_id: UUID, role: str | None = None) -> list[ConversationMessage]:
    filters = [ConversationMessage.run_id == run_id, ConversationMessage.deleted_at.is_(None)]
    ...

async def _count_rows(session: AsyncSession, model, *filters) -> int:
    result = await session.execute(select(func.count()).select_from(model).where(*filters))
    return int(result.scalar_one())
```

Copy these helpers or equivalent local assertions into `tests/test_approval_api.py` if not importing from another test module.

**Assistant/finalizer trace assertions** (`tests/test_agent_runs_api.py` lines 1485-1518):
```python
assistant_messages = await _messages_for_run(session, run_id=run_id, role="assistant")
assert len(assistant_messages) == 1
assert assistant_messages[0].metadata_json["status"] == "completed"
assert assistant_messages[0].metadata_json["source"] == "agent_runs.finalizer"
finalizer_step = (
    await session.execute(select(AgentStep).where(AgentStep.run_id == run_id, AgentStep.node_name == "agent_run_memory_finalize"))
).scalar_one()
metrics = finalizer_step.metrics_json or {}
assert metrics["assistant_message_id"] == str(assistant_messages[0].id)
```

**Non-completed skip assertions** (`tests/test_agent_runs_api.py` lines 2548-2605):
```python
result = await finalize_completed_agent_run_memory(..., final_status="error", final_response="x", ...)
assert result.status == "skipped"
assert result.case_working_context_result == {"status": "skipped", "reason_code": "not_completed_path"}
assert await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run.id, ConversationMessage.role == "assistant") == 0
assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 0
assert await _count_rows(session, MemoryWriteEvent, MemoryWriteEvent.run_id == run.id) == 0
```

**CWC writeback assertions** (`tests/test_agent_runs_api.py` lines 2608-2655):
```python
result = await finalize_completed_agent_run_memory(
    session=session,
    run=run,
    user=user,
    input_state=_stream_input(run, user),
    final_state=_cwc_terminal_state(seeded_session),
    final_status="completed",
    final_response="退款单还在审核中。",
    trace_steps=[],
    trace_id=None,
)
...
assert result.case_working_context_status == "written"
assert cwc.source_ref_json["source_type"] == "run_auto_terminal"
assert metrics["case_working_context_status"] == "written"
```

**Isolated memory rollback assertions** (`tests/test_agent_runs_api.py` lines 2821-2878):
```python
async def fake_memory_write(final_state, config):
    memory_session = config["configurable"]["session"]
    assert memory_session is not session
    await memory_session.rollback()
    return {**final_state, "memory_write_result": {"status": "fallback", "reason_code": "unavailable", ...}, "trace_steps": []}
...
assert result.memory_write_status == "failed"
assert await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run.id, ConversationMessage.role == "assistant") == 1
assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 1
```

**Interrupted path no-finalizer pattern** (`tests/test_agent_runs_api.py` lines 2931-3010):
```python
events = [event async for event in generator]
assert any('"event_type": "approval_required"' in event.get("data", "") for event in interrupted_events)
for run in (error_run, cancelled_run, interrupted_run):
    await session.refresh(run)
    assert run.final_status in {"error", "interrupted"}
    assert await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run.id, ConversationMessage.role == "assistant") == 0
    assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 0
```

**Duplicate stream/idempotency style** (`tests/test_agent_runs_api.py` lines 3013-3117):
```python
calls = {"assistant_message": 0, "finalizer": 0, "graph": 0, "memory_write": 0, "summary": 0, "user_message": 0}
...
assert calls_after_first == {
    "assistant_message": 1,
    "finalizer": 1,
    "graph": 1,
    "memory_write": 1,
    "summary": 1,
    "user_message": 1,
}
assert counts_after_duplicate == counts_after_first
assert calls == calls_after_first
```

Reuse this count-based pattern for approval-resume retry/idempotency.

---

### `tests/agent/test_memory_write_node.py` (unit test, transform)

**Analog:** existing skip/write tests. There is no exact approval-marker test yet; add one if Phase 59 changes `_approval_or_interrupted(...)`.

**Imports/state fixture pattern** (`tests/agent/test_memory_write_node.py` lines 1-20, 20-41):
```python
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes import memory_write as memory_write_module
from src.agent.nodes.memory_write import memory_write

def _state(**updates: object) -> dict:
    values: dict[str, object] = {
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "thread_id": "thread-memory-write",
        "current_run_id": str(uuid4()),
        "final_response": "最终回复已经生成。",
        ...
    }
```

**Skipped assertion shape** (`tests/agent/test_memory_write_node.py` lines 44-54):
```python
result = await memory_write(_state(final_response=None), {"configurable": {"session": object()}})

assert result["memory_write_result"]["status"] == "skipped"
assert result["memory_write_result"]["reason_code"] == "not_completed_path"
assert result["memory_write_decision"]["schema_version"] == "memory_write_decision.v2"
assert result["memory_write_decision"]["authority_class"] == "contextual_only"
assert result["trace_steps"][-1]["node"] == "memory_write"
```

**Successful write assertion shape** (`tests/agent/test_memory_write_node.py` lines 57-103):
```python
class FakeMemoryService:
    async def write_session_memory(self, candidate):
        candidates.append(candidate)
        return SessionMemoryWriteResult(status="written", version=4, decision="write", reason_code="eligible", pii_classification="none")

monkeypatch.setattr(memory_write_module, "MemoryService", FakeMemoryService)
result = await memory_write(_state(), {"configurable": {"session": object()}})
assert result["memory_write_result"]["status"] == "written"
assert result["memory_write_decision"]["memory_type"] == "session"
assert candidate.expected_version == 3
```

Recommended additions if changing the node:
- `approval_result` / `approval_required` / `risk_assessment.approval_required=True` without terminal-finalizer mode still returns `skipped/not_completed_path`.
- completed terminal-finalizer mode, if implemented as a flag, writes like the existing success path.

---

### `tests/architecture/test_canonical_graph_baseline.py` (architecture guard, verification-only)

**Analog:** Phase 58 canonical vocabulary guard.

**Canonical node set pattern** (`tests/architecture/test_canonical_graph_baseline.py` lines 68-88):
```python
assert TARGET_CANONICAL_GRAPH_NODES == frozenset(
    {
        "receive_request",
        "safety_pre_route",
        ...
        "risk_gate",
        "approval_gate",
        "action_draft",
        "clarification_gate",
        "final_response",
    }
)
```

**No legacy alias pattern** (`tests/architecture/test_canonical_graph_baseline.py` lines 102-114):
```python
assert "assess_risk_and_approval" not in MIGRATION_MODE_LEGACY_NODE_MAP
assert MIGRATION_MODE_LEGACY_NODE_MAP == {}
for name in LEGACY_GRAPH_NAMES:
    assert graph_vocabulary.graph_vocabulary_entry(name, kind="node") is None, name
    assert graph_vocabulary.target_graph_name(name, kind="node") == name
assert all(entry.status != "compatibility_alias" for entry in graph_vocabulary._ENTRIES)
```

Phase 59 should not modify this file unless implementation unexpectedly touches graph vocabulary. It should remain in the verification command set.

---

### `.planning/ARCHITECTURE-DEBT.md` (conditional planning ledger)

**Analog:** existing Memory section entries. Update only if implementation discovers or fixes memory subsystem architecture debt.

**Ledger rules** (`.planning/ARCHITECTURE-DEBT.md` lines 6-18):
```markdown
## 写入规则

- 修改**工具调用 / RAG / 记忆 / 意图识别**这几个核心子系统时，检测出的 bug 或架构不完善点、以及做了哪些修复，**默认追加到本文件**对应子系统章节。
- 每条目尽量给：问题现象 / 根因、影响、处理状态、证据（phase / commit / 文件:行）、剩余风险。
```

**Memory section format** (`.planning/ARCHITECTURE-DEBT.md` lines 373-402):
```markdown
# 4. 记忆（Memory）

**范围**：短期/会话记忆、thread summary、ContextAssembler、记忆边界与 fail-closed。

## Phase 48 Plan 02 — long-term 自动来源过宽与 semantic episode 投影过宽 ✅已修复验证

**问题 / 根因**
...
**影响**
...
**修复**
...
**证据**
...
**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`
```

**CWC/finalizer precedent** (`.planning/ARCHITECTURE-DEBT.md` lines 788-805):
```markdown
- `finalize_completed_agent_run_memory(...)` 在 assistant message + thread summary commit 和原有 `memory_write` side effect 之后调用 CWC lifecycle adapter...

**证据**
- Phase / plan：`45-03`
- 文件：`src/memory/case_working_context_lifecycle.py`、`src/api/services/agent_run_memory.py`、`tests/agent/test_case_working_context_lifecycle.py`、`tests/test_agent_runs_api.py`

**验证**
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`
```

---

### `.planning/LOCAL-VALIDATION-ISSUES.md` (conditional validation ledger)

**Analog:** existing validation issue entries. Update only for actual local validation/debug issues found during implementation or verification.

**Entry format** (`.planning/LOCAL-VALIDATION-ISSUES.md` lines 1-42):
```markdown
# 本地验证问题记录

## 20. Phase 56-02 Task 2 acceptance grep 被负向断言文本误触发

日期：2026-07-07

### 问题现象
...
### 如何检测 / 复现
...
### 关键证据或命令
...
### 当前判断 / 根因
...
### 已做处理
...
### 剩余问题
...
### 下次继续排查入口
...
```

Use Chinese by default for these ledger entries, per MOCA project rules.

## Shared Patterns

### Requester vs Reviewer Identity

**Source:** `src/api/routers/approvals.py` lines 729-749 and `src/api/services/agent_run_memory.py` lines 81-95, 199-217, 255-276  
**Apply to:** `src/api/routers/approvals.py`, `src/api/services/agent_run_memory.py`, approval tests

- Reviewer/admin `actor_user` belongs to trusted graph resume and action-draft permission.
- Terminal finalizer must use the persisted run requester: fetch `AgentRun`, then fetch `User` by `run.user_id`, then build input state from `run` + requester.
- `_memory_state(...)` overwrites identity fields with `run.tenant_id`, `user.id`, `run.thread_id`, `run.id`, and `user.role`; passing the reviewer would silently bind memory/CWC side effects to the wrong user.

### Terminal Completion Ordering

**Source:** `src/api/routers/agent_runs.py` lines 1037-1065 and `src/api/routers/approvals.py` lines 318-349  
**Apply to:** approval completed resume path

Order to preserve:
1. Graph resume returns final state.
2. Derive `final_status` and `final_response`.
3. Persist `AgentRun` terminal status and post-approval graph trace.
4. Invoke finalizer for completed response only.
5. Persist finalizer trace step with duplicate guard.
6. Record `approval_resumed/completed`.

### Finalizer Idempotency

**Source:** `src/conversation/service.py` lines 381-439; `src/memory/thread_summary.py` lines 118-188; `src/agent/trace.py` lines 176-217; `src/db/models.py` lines 1178-1209  
**Apply to:** shared finalizer trace helper and approval retry tests

Already idempotent:
```python
existing = await self.repository.get_message_by_run_role(...)
if existing is not None:
    return _append_result_from_message(existing)
...
except IntegrityError:
    existing = await self.repository.get_message_by_run_role(...)
```

Already idempotent:
```python
existing = await self.repository.get_thread_summary_by_source_end(...)
if existing is not None:
    return existing
...
except IntegrityError:
    existing = await self.repository.get_thread_summary_by_source_end(...)
```

Not idempotent yet:
```python
for idx, step in enumerate(trace_steps[start_index:], start=start_index):
    agent_step = AgentStep(..., node_name=str(step.get("node") or "unknown"), step_index=idx, ...)
    session.add(agent_step)
```

`AgentStep` has `run_id`, `node_name`, and `step_index` fields but no model-level unique constraint for finalizer steps. Add an explicit query guard for `AgentStep.run_id == run.id` and `AgentStep.node_name == FINALIZER_NODE` before appending finalizer trace rows.

### Terminal Memory Write Eligibility

**Source:** `src/agent/nodes/memory_write.py` lines 42-50, 354-360; `src/api/services/agent_run_memory.py` lines 151-178  
**Apply to:** `memory_write` or finalizer state sanitizer

Current pending/interrupted approval states are intentionally skipped:
```python
if state.get("approval_result") or state.get("approval_required"):
    return True
if isinstance(risk, dict) and risk.get("approval_required") is True:
    return True
return state.get("final_status") == "interrupted"
```

Phase 59 must prove completed approval-resume finalization is memory-eligible without making pending/interrupted approval states eligible.

### CWC Terminal Writeback

**Source:** `src/memory/case_working_context_lifecycle.py` lines 189-238, 345-388, 461-513  
**Apply to:** finalizer invocation and tests

```python
raw_case_ref = trusted_case_ref_from_state(final_state, include_business_context=True)
if raw_case_ref is None:
    return CaseWorkingContextLifecycleResult(..., reason_code="skipped_no_case")
...
link_status = await self._link_terminal_thread_case(...)
```

```python
was_already_linked = await _has_active_thread_case_link(...)
if was_already_linked:
    return "deduped"
...
await conversation_repository.link_case(..., link_source="run_auto", linked_by_run_id=run_id)
```

```python
source_ref = MemorySourceRefV1(
    source_type="run_auto_terminal",
    run_id=str(run_id),
    agent_run_id=str(run_id),
    business_object_type="refund_case",
    business_object_id=str(case_id),
)
```

Use approval-resume tests with CWC-eligible `active_slots.refund_case_id` to assert these metrics surface through `agent_run_memory_finalize`.

### Canonical Graph Vocabulary

**Source:** `src/api/routers/approvals.py` lines 771-785; `tests/architecture/test_canonical_graph_baseline.py` lines 68-114  
**Apply to:** approval retry and verification

```python
def _should_resume_graph(result) -> bool:
    if not result.resume_payload:
        return False
    if result.decision_type == "edit":
        return result.resume_payload.get("resume_route") == CANONICAL_RISK_ROUTE
    return result.decision_type in {"accept", "approve", "reject", "ignore"}
```

Only historical persisted retry metadata maps `assess_risk_and_approval` to `risk_gate`. Do not add active runtime aliases or revive legacy graph vocabulary.

### Approved Test Entrypoint

**Source:** MOCA `AGENTS.md` and Phase 59 research  
**Apply to:** all plan verification commands

Use:
```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...
```

Do not recommend bare `pytest` or bare `python -m pytest`.

## No Analog Found

None. Every planned or conditional file has an existing local analog. The only partial analog is finalizer trace persistence: existing `_persist_finalizer_trace_steps(...)` shows shape and error handling, but must be hardened with a duplicate guard before reuse by approval resume.

## Metadata

**Analog search scope:** `src/api/routers`, `src/api/services`, `src/agent/nodes`, `src/agent/trace.py`, `src/memory`, `src/conversation/service.py`, `src/db/models.py`, `tests/test_approval_api.py`, `tests/test_agent_runs_api.py`, `tests/agent/test_memory_write_node.py`, `tests/architecture/test_canonical_graph_baseline.py`, `.planning/ARCHITECTURE-DEBT.md`, `.planning/LOCAL-VALIDATION-ISSUES.md`  
**Files scanned:** 450 files under `src` and `tests`; 53 role-filtered candidate files inspected by name/search; 16 files read with targeted excerpts  
**Pattern extraction date:** 2026-07-08
