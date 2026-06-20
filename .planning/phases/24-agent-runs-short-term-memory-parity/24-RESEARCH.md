# Phase 24: Agent Runs Short-term Memory Parity - Research

**Researched:** 2026-06-20  
**Domain:** FastAPI / LangGraph / SSE / PostgreSQL short-term memory persistence  
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

Source for this copied section: [VERIFIED: .planning/phases/24-agent-runs-short-term-memory-parity/24-CONTEXT.md]

### Locked Decisions

#### `/agent-runs` Conversation Persistence
- **D-01:** Persist exactly one user conversation message during `POST /api/v1/agent-runs` creation. This makes run creation the durable "user submitted this query" boundary and avoids duplicate user messages when the SSE endpoint is retried, reopened, or rejected after the pending claim.
- **D-02:** The SSE execution path must resolve and reuse the existing user conversation message for the run, then pass trusted `conversation_thread_id` and `conversation_message_id` into graph config. `investigate` already persists tool call/result rows only when `conversation_message_id` is present, so this config wiring is required for tool summaries to attach to the current turn.
- **D-03:** Completed runs persist exactly one assistant conversation message after graph final state is known and before the final SSE response is emitted. Assistant messages should carry final status metadata, but no private reasoning, raw tool payloads, authority bodies, or debug traces.
- **D-04:** Completed runs update the thread rolling summary from committed user/assistant messages and eligible prompt-safe tool summaries. Rolling summary creation must be idempotent at the run/turn level; retries must not create duplicate assistant messages or duplicate equivalent summaries.

#### Prompt Context Composition
- **D-05:** Enable the full short-term context stack for `/agent-runs`: trusted session slots, recent conversation messages, recent prompt-safe tool summaries, and the latest prior rolling thread summary.
- **D-06:** Prompt context is contextual only. It can help resolve references such as "这个订单" or "刚才那个退款", but it cannot satisfy policy evidence, current business fact, approval/action authority, or replay/audit truth requirements. Any answer that needs current order/refund/ticket facts must still call tools; any policy answer must still retrieve/verify policy evidence.
- **D-07:** Use existing prompt-safe projection boundaries where possible: `ConversationService.load_prompt_context`, `ContextAssembler`, `WorkingStateV1`, and `src/agent/context/projectors.py`. Do not assemble prompt context by stringifying raw dicts, raw tool results, or unprojected business/policy/approval objects.
- **D-08:** Explicit current-turn slots override inherited trusted session slots. Stale, incompatible, cross-tenant, cross-user, or cross-thread memory fails closed to clarification or current-turn-only behavior.

#### Terminal and Failure Semantics
- **D-09:** Only `completed` runs write assistant messages, rolling summaries, and successful session-memory updates. Normal clarification responses are completed responses and should be persisted like other assistant messages.
- **D-10:** `error`, `cancelled`, and `interrupted` runs preserve the user message, run status, trace/tool records, approval request/event records where applicable, and error/interruption metadata, but they must not create false completed assistant messages or false completed rolling summaries.
- **D-11:** Approval interruption is not a completed assistant answer. It may create approval records and trace/replay events, but it should not be summarized as if the agent answered the user. If a later approval resume produces a completed response, that later completed run/revision owns its assistant message and summary.
- **D-12:** SSE retry/reopen semantics do not need to replay the full prior event stream in this phase. The current "claim pending run once" model can stay, but duplicate streams must never re-execute the graph or duplicate user messages, assistant messages, tool result records, summaries, or session-memory writes.

#### Timeline and Memory Write Ordering
- **D-13:** Any persistence stage exposed as running in the Agent Timeline must stay `running` until that stage's actual work is done, then replace itself with `completed`. Do not emit a completed event for a stage whose downstream persistence obligation is still running.
- **D-14:** For `/agent-runs`, terminal memory persistence should be bounded and ordered before the final SSE `final_response` event when that persistence is part of the promised short-term continuity. If a bounded memory write fails or times out, record an explicit skipped/error result and continue with a safe final response; do not silently report memory success.
- **D-15:** The planner may keep low-risk cleanup/background enrichment outside the final-response critical path only if it is not required for the next user turn's short-term continuity and it is clearly not shown as completed in the timeline.

#### Compatibility with Legacy Chat
- **D-16:** `/api/v1/agent/chat` remains the compatibility reference path. Phase 24 should extract shared helpers/services where needed rather than copy divergent persistence logic into `/agent-runs`.
- **D-17:** Legacy chat tests must remain green. If shared persistence behavior changes, both `/agent/chat` and `/agent-runs` should use the same semantics for user/assistant messages, tool summary storage, rolling summary updates, prompt-safe redaction, and session memory boundaries.

### Claude's Discretion
- The planner may choose exact helper names, repository methods, idempotency key shape, and test file split.
- The planner may decide whether conversation message IDs are stored directly on `agent_runs`, resolved by `run_id` lookup in `conversation_messages`, or managed through a small run-memory linkage helper, as long as exactly-once semantics and SSE retry safety are preserved.
- The planner may decide whether the final terminal persistence appears as explicit SSE timeline nodes or remains backend-only, as long as displayed node statuses are truthful and next-turn memory continuity is deterministic.

### Deferred Ideas (OUT OF SCOPE)
- Full memory inspection/management UI remains future scope (`STM-FUT-01`).
- Retention, archival, deletion policy controls remain future scope (`STM-FUT-02`).
- Admin review workflow for promoting conversation patterns into reviewed long-term or case memory remains future scope (`STM-FUT-03`).
- Full SSE event replay/reconnect UX is not required for Phase 24; this phase only requires no duplicate execution or duplicate memory writes.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STM-01 | `/api/v1/agent-runs` creates/resolves a conversation thread and persists exactly one user message before graph execution. [VERIFIED: .planning/REQUIREMENTS.md] | Implement in `create_agent_run` using `ConversationService.append_user_message` plus idempotent lookup/unique guard. [VERIFIED: src/api/routers/agent_runs.py, src/conversation/service.py, src/db/models.py] |
| STM-02 | Graph execution receives trusted `conversation_thread_id` and `conversation_message_id`. [VERIFIED: .planning/REQUIREMENTS.md] | Resolve the run's user message in `stream_agent_run_events` before `_event_generator`; `investigate` persists tool rows only when `conversation_message_id` is present. [VERIFIED: src/api/routers/agent_runs.py, src/agent/nodes/investigate.py] |
| STM-03 | Completed runs persist exactly one assistant message with final response and status metadata. [VERIFIED: .planning/REQUIREMENTS.md] | Move legacy chat's assistant append pattern into a shared completed-run finalizer and guard by run/role. [VERIFIED: src/api/routers/agent.py, src/conversation/service.py] |
| STM-04 | Completed runs update rolling summary from committed messages and eligible prompt-safe tool summaries. [VERIFIED: .planning/REQUIREMENTS.md] | Use `ThreadRollingSummaryService.persist_thread_summary`; add turn-level idempotency because current service can insert another summary for the same source end message. [VERIFIED: src/memory/thread_summary.py, src/conversation/repository.py] |
| STM-05 | Same-thread follow-ups load recent messages, latest prior rolling summary, and prompt-safe tool summaries. [VERIFIED: .planning/REQUIREMENTS.md] | Existing `ConversationService.load_prompt_context` provides this window and is already used by recommendation/risk nodes; slot extraction still passes empty recent/summary context. [VERIFIED: src/conversation/service.py, src/agent/nodes/generate_recommendation.py, src/agent/nodes/assess_risk_and_approval.py, src/agent/nodes/extract_slots.py] |
| STM-06 | PostgreSQL session slots remain active and current-turn explicit slots override inherited slots. [VERIFIED: .planning/REQUIREMENTS.md] | Existing `session_memory_load`, `MemoryService`, and routing tests cover load/fallback/override semantics. [VERIFIED: src/agent/nodes/session_memory_load.py, src/memory/service.py, tests/agent/test_required_slots.py] |
| STM-07 | Tool prompt summaries exclude raw payloads, private reasoning, authority bodies, debug traces, secrets, and excess PII. [VERIFIED: .planning/REQUIREMENTS.md] | Keep `ConversationService.append_tool_result`, `ContextAssembler`, and projector allowlists as the only prompt-facing path. [VERIFIED: src/conversation/service.py, src/agent/context/assembler.py, src/agent/context/projectors.py] |
| STM-08 | Legacy `/api/v1/agent/chat` remains compatible with shared infrastructure. [VERIFIED: .planning/REQUIREMENTS.md] | Extract helpers without changing legacy chat semantics unless tests are updated deliberately. [VERIFIED: src/api/routers/agent.py, tests/conversation/test_service.py] |
| STM-09 | Error, cancelled, and approval-interrupted runs do not create false completed assistant messages or summaries. [VERIFIED: .planning/REQUIREMENTS.md] | `_handle_approval_required` already marks `interrupted` without final response in `/agent-runs`; completed-memory finalizer must be status-gated. [VERIFIED: src/api/routers/agent_runs.py] |
| STM-10 | Retried/reopened/duplicate SSE streams do not duplicate memory records. [VERIFIED: .planning/REQUIREMENTS.md] | Current pending-claim model blocks duplicate graph execution; persistence helpers still need run/role/summary idempotency. [VERIFIED: src/api/routers/agent_runs.py, src/db/models.py] |
| STM-11 | Memory writes are ordered so incomplete stages stay running until persistence is done. [VERIFIED: .planning/REQUIREMENTS.md] | Current SSE schedules session memory after yielding final response, so Phase 24 must reverse that ordering or explicitly record a backend-only terminal persistence result before final SSE. [VERIFIED: src/api/routers/agent_runs.py, tests/test_agent_runs_api.py] |
| STM-12 | Memory remains contextual only and cannot satisfy policy evidence/business fact/approval/action/replay truth. [VERIFIED: .planning/REQUIREMENTS.md] | Preserve `ContextAssembler` safety constraints, session-memory boundaries, and BusinessToolService/KnowledgeService authority separation. [VERIFIED: src/agent/context/assembler.py, docs/contract-spec.md §§13.6-13.7] |
| STM-13 | Regression tests cover all parity, idempotency, context, and legacy compatibility behavior. [VERIFIED: .planning/REQUIREMENTS.md] | Extend `tests/test_agent_runs_api.py`, `tests/conversation/test_service.py`, and memory/context tests; existing files already have fixtures and fake graphs. [VERIFIED: tests/test_agent_runs_api.py, tests/conversation/test_service.py] |
| STM-14 | Live or integration smoke verifies a three-turn Agent Console conversation uses slot continuity and rolling summary context. [VERIFIED: .planning/REQUIREMENTS.md] | Use DB-backed API/SSE integration or a scripted smoke against local docker compose; existing session-memory integration tests are graph-level but not run/SSE three-turn smoke. [VERIFIED: tests/agent/test_session_memory_integration.py, docker-compose.yml] |
</phase_requirements>

## Project Constraints (from CLAUDE.md / AGENTS.md)

- Phase-level planning and larger changes must use the MOCA dual-review workflow: GSD-native review first, then independent Codex cross-check, with findings verified against real repo code/tests. [VERIFIED: CLAUDE.md, AGENTS.md]
- Debug/startup/API/UI/RAG/agent/memory/tool-call failures discovered during local validation must be appended to `.planning/LOCAL-VALIDATION-ISSUES.md` in Chinese with symptom, reproduction, evidence, current root-cause judgment, handling, residual issue, and next entry point. [VERIFIED: CLAUDE.md, AGENTS.md]
- `docs/contract-spec.md` is normative for contract semantics but not implementation scope; Phase implementation may scope MVP behavior, but any spec divergence must be recorded instead of silent. [VERIFIED: CLAUDE.md, AGENTS.md]
- Plan revisions or code changes that add/delete/reorder tasks, cross at least three files, affect task dependencies/waves, or require code rereads are classified as large changes for the MOCA workflow. [VERIFIED: CLAUDE.md, AGENTS.md]
- `study_plan/` documents default to Chinese, while code identifiers and technical names stay as-is; this Phase 24 artifact is outside `study_plan/` but the user explicitly requested Chinese output. [VERIFIED: AGENTS.md, user prompt]

## Summary

Phase 24 is not a new memory system; it is a parity/finalization phase for the current Agent Console path, because `/api/v1/agent-runs + SSE` is the active frontend path while legacy `/api/v1/agent/chat` already writes conversation messages and rolling summaries. [VERIFIED: .planning/ROADMAP.md, .planning/PROJECT.md, src/api/routers/agent.py, src/api/routers/agent_runs.py]

The highest-risk implementation gap is terminal ordering: current `/agent-runs` updates run state and emits `final_response`, then schedules session memory as a background task after the generator resumes; a disconnect after `final_response` can prevent the scheduled write, and existing tests currently assert that old ordering. [VERIFIED: src/api/routers/agent_runs.py, tests/test_agent_runs_api.py] The plan must replace this with a bounded completed-run finalizer that persists assistant message, rolling summary, and required session-memory continuity before the final SSE `final_response` event, while recording explicit skipped/error memory results when bounded persistence fails. [VERIFIED: 24-CONTEXT.md, src/agent/nodes/memory_write.py]

The second highest-risk gap is idempotency: `conversation_messages` has a unique constraint only on `(conversation_thread_id, message_index)`, `summaries` has no unique source-range guard, and `ThreadRollingSummaryService.persist_thread_summary` currently ignores the `run_id` argument. [VERIFIED: src/db/models.py, src/memory/thread_summary.py] The plan should add DB-backed or repository-backed idempotent helpers for user message, assistant message, and rolling summary creation, then use those helpers from both `/agent-runs` and legacy chat where shared behavior is required. [VERIFIED: src/conversation/repository.py, src/conversation/service.py, 24-CONTEXT.md]

**Primary recommendation:** build a small completed-run memory finalizer around existing `ConversationService`, `ThreadRollingSummaryService`, `memory_write`, and `ContextAssembler`; do not create a parallel prompt/memory stack. [VERIFIED: src/api/routers/agent.py, src/conversation/service.py, src/memory/thread_summary.py, src/agent/nodes/memory_write.py, src/agent/context/assembler.py]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Run creation and user message persistence | API / Backend | Database / Storage | `create_agent_run` owns the trusted user/run boundary and already writes `agent_runs`; conversation rows persist in PostgreSQL. [VERIFIED: src/api/routers/agent_runs.py, src/db/models.py] |
| SSE pending claim and graph execution | API / Backend | LangGraph runtime | `_claim_pending_run_for_stream` gates one execution and `stream_agent_run_events` builds trusted config for the graph. [VERIFIED: src/api/routers/agent_runs.py, src/agent/graph.py] |
| Tool call/result prompt summaries | API / Backend | Database / Storage | `investigate` writes tool conversation records through `ConversationService` only when trusted `conversation_message_id` exists. [VERIFIED: src/agent/nodes/investigate.py, src/conversation/service.py] |
| Rolling thread summary | API / Backend service | Database / Storage | `ThreadRollingSummaryService` derives summaries from conversation messages and tool result prompt summaries, then stores `thread_rolling` rows. [VERIFIED: src/memory/thread_summary.py, src/conversation/repository.py] |
| Session slot continuity | API / Backend service | Database / Storage | `session_memory_load` and `memory_write` use `MemoryService(SessionMemoryRepository)` against PostgreSQL-backed `session_memories`. [VERIFIED: src/agent/nodes/session_memory_load.py, src/agent/nodes/memory_write.py, src/memory/service.py] |
| Prompt-safe assembly | Agent node layer | API / Backend service | Recommendation/risk nodes load `ConversationService.load_prompt_context` and pass projected blocks through `ContextAssembler`; raw stringification is not the owner. [VERIFIED: src/agent/nodes/generate_recommendation.py, src/agent/nodes/assess_risk_and_approval.py, src/agent/context/assembler.py] |
| Authority boundaries | API / Backend service | Database / Storage | Business facts come from tool services, policy evidence from `EvidenceRefV1`/KnowledgeService, approval/action authority from approval/action tables, and replay truth from run/trace/event records. [VERIFIED: .planning/PROJECT.md, docs/contract-spec.md §§13.7, 17.6-17.7] |

## Standard Stack

### Core

| Library / Component | Version | Purpose | Why Standard |
|---------------------|---------|---------|--------------|
| Python | 3.13.3 local CLI; project requires `>=3.12` | Backend runtime and test runtime. [VERIFIED: `python3 --version`, pyproject.toml] | Existing project runtime. [VERIFIED: pyproject.toml] |
| FastAPI | 0.136.1 | API routers, dependency injection, security dependencies. [VERIFIED: `uv run importlib.metadata`, src/api/routers/agent_runs.py] | Existing API stack; no new router framework needed. [VERIFIED: pyproject.toml, src/api/main.py] |
| sse-starlette | 3.4.4 | `EventSourceResponse` for SSE stream responses. [VERIFIED: `uv run importlib.metadata`, src/api/routers/agent_runs.py] | Existing SSE implementation; do not replace with a custom streaming protocol. [VERIFIED: src/api/routers/agent_runs.py] |
| LangGraph | 1.1.10 | Agent graph execution, stream updates/events, checkpointed graph flow. [VERIFIED: `uv run importlib.metadata`, src/agent/graph.py] | Existing orchestration stack and graph nodes already implement memory load/investigation/final response. [VERIFIED: src/agent/graph.py] |
| SQLAlchemy asyncio | 2.0.49 | Async ORM models/repositories/transactions. [VERIFIED: `uv run importlib.metadata`, src/db/models.py, src/conversation/repository.py] | Existing repository pattern and async fixtures depend on it. [VERIFIED: tests/conftest.py] |
| PostgreSQL + pgvector image | `pgvector/pgvector:pg16` | Authoritative storage for runs, conversation, summaries, session memories, tests. [VERIFIED: docker-compose.yml, docs/contract-spec.md §13.6] | Contract requires PostgreSQL as authoritative memory/audit storage. [CITED: docs/contract-spec.md §13.6] |

### Supporting

| Library / Component | Version | Purpose | When to Use |
|---------------------|---------|---------|-------------|
| pytest | 9.0.3 | Unit/integration test runner. [VERIFIED: `uv run importlib.metadata`] | All Phase 24 validation. [VERIFIED: pyproject.toml, tests/conftest.py] |
| pytest-asyncio | 1.3.0 | Async test support. [VERIFIED: `uv run importlib.metadata`] | DB/API/SSE async tests. [VERIFIED: pyproject.toml, tests/test_agent_runs_api.py] |
| httpx | 0.28.1 | ASGI/API test client. [VERIFIED: `uv run importlib.metadata`] | `/agent-runs` and `/agent/chat` API tests. [VERIFIED: tests/conftest.py, tests/test_agent_runs_api.py] |
| Alembic | 1.18.4 | Schema migrations. [VERIFIED: `uv run importlib.metadata`, alembic.ini] | Use only if adding unique indexes or link columns for idempotency. [VERIFIED: src/db/migrations/versions/011_memory_foundation_v2.py] |
| Ruff | 0.15.12 | Lint/format. [VERIFIED: `uv run importlib.metadata`] | Phase gate lint. [VERIFIED: Makefile, pyproject.toml] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing `ConversationService` + `ThreadRollingSummaryService` | New run-specific memory tables/service | Duplicates Phase 15.1 memory foundation and increases divergence from legacy chat. [VERIFIED: .planning/milestones/v1.1-phases/15.1-memory-foundation-v2/15.1-CONTEXT.md, src/conversation/service.py] |
| PostgreSQL-backed idempotency | Redis-only dedupe keys | Redis is explicitly non-authoritative for memory correctness; PostgreSQL remains the source of truth. [CITED: docs/contract-spec.md §13.6] |
| Existing `EventSourceResponse` | Custom SSE/event replay implementation | Full SSE replay/reconnect UX is out of Phase 24 scope; current pending-claim model can stay. [VERIFIED: 24-CONTEXT.md, src/api/routers/agent_runs.py] |
| `ContextAssembler` projectors | Raw `dict`/tool-result stringification | Projectors already enforce allowlists/redaction; raw stringification is a known forbidden pattern. [VERIFIED: src/agent/context/projectors.py, tests/agent/context/test_assembler.py] |

**Installation / Sync:**

```bash
uv sync --extra dev
```

Version verification used `uv run python -c "import importlib.metadata as m; ..."` and local CLI probes. [VERIFIED: local command output]

## Architecture Patterns

### System Architecture Diagram

```mermaid
flowchart TD
    A[POST /api/v1/agent-runs] --> B[write AgentRun pending]
    B --> C[append/get exactly-one user ConversationMessage]
    C --> D[commit run + user message]
    D --> E[GET /api/v1/agent-runs/{run_id}/events]
    E --> F{claim pending run?}
    F -- no --> G[409 no graph execution]
    F -- yes --> H[resolve user message + conversation_thread_id]
    H --> I[LangGraph stream with trusted config]
    I --> J[investigate persists tool call/result summaries]
    I --> K{terminal state}
    K -- completed --> L[completed-run memory finalizer]
    L --> M[append/get assistant message]
    M --> N[persist/get rolling summary]
    N --> O[bounded session memory_write]
    O --> P[update run/steps with explicit memory result]
    P --> Q[emit final_response SSE]
    K -- error/cancel/interrupted --> R[write terminal run/trace/approval state only]
    R --> S[emit error or approval_required SSE]
```

This flow uses the current POST/SSE split, the current pending-claim gate, and the existing conversation/memory services. [VERIFIED: src/api/routers/agent_runs.py, src/conversation/service.py, src/memory/thread_summary.py, src/agent/nodes/memory_write.py]

### Recommended Project Structure

```text
src/api/routers/agent_runs.py        # Keep routing/SSE; delegate memory finalization. [VERIFIED: current file]
src/api/routers/agent.py             # Legacy compatibility reference; reuse helpers. [VERIFIED: current file]
src/conversation/repository.py       # Add run/role message lookup + summary idempotency lookup. [VERIFIED: current file]
src/conversation/service.py          # Add append/get-once helpers and keep prompt-safe guards. [VERIFIED: current file]
src/memory/thread_summary.py         # Add idempotent persist behavior for source range/end message. [VERIFIED: current file]
src/api/services/agent_run_memory.py # Recommended new helper module for completed-run finalizer. [VERIFIED: inferred from router-thin pattern in src/api/routers]
tests/test_agent_runs_api.py         # Main API/SSE parity and idempotency coverage. [VERIFIED: existing test file]
tests/conversation/test_service.py   # Service-level idempotency/prompt-context regression. [VERIFIED: existing test file]
tests/memory/test_thread_summary.py  # Summary source-range/idempotency/prompt-safety regression. [VERIFIED: existing test file]
```

### Pattern 1: Idempotent Run Conversation Link

**What:** Add repository/service helpers that return the existing run/role message when present and append only when absent; prefer DB-backed partial unique indexes for `role='user'` and `role='assistant'` by `(tenant_id, run_id)` where `deleted_at is null`. [VERIFIED: src/db/models.py shows no existing run/role unique guard]

**When to use:** Use for `POST /agent-runs` user message creation and completed-run assistant message finalization. [VERIFIED: 24-CONTEXT.md]

**Example:**

```python
# Source pattern: src/api/routers/agent.py + src/conversation/service.py [VERIFIED]
user_message = await conversation_service.append_user_message(
    tenant_id=user.tenant_id,
    user_id=user.id,
    thread_id=body.thread_id,
    run_id=run_uuid,
    content=body.query,
    trace_id=trace_id,
    prompt_template_version="agent-runs.request.v1",
)
config["configurable"]["conversation_message_id"] = str(user_message.message_id)
config["configurable"]["conversation_thread_id"] = str(user_message.conversation_thread_id)
```

### Pattern 2: Completed-Only Finalizer

**What:** Route completed terminal persistence through one helper that appends/gets assistant message, persists/gets rolling summary, runs bounded `memory_write`, records explicit memory result, then permits `final_response` SSE. [VERIFIED: 24-CONTEXT.md, src/api/routers/agent_runs.py, src/agent/nodes/memory_write.py]

**When to use:** Use after graph final state has a safe `final_response`; never use for `error`, `cancelled`, or `interrupted`. [VERIFIED: 24-CONTEXT.md]

**Example:**

```python
# Source pattern: src/api/routers/agent.py legacy terminal flow + Phase 24 ordering decision [VERIFIED]
assistant_message = await conversation_service.append_assistant_message(
    tenant_id=user.tenant_id,
    user_id=user.id,
    thread_id=run.thread_id,
    run_id=run.id,
    content=final_response,
    trace_id=trace_id,
    metadata_json={"status": "completed"},
)
summary = await ThreadRollingSummaryService(conversation_repository).persist_thread_summary(
    tenant_id=user.tenant_id,
    user_id=user.id,
    thread_id=run.thread_id,
    run_id=run.id,
)
memory_result = await memory_write(final_state, {"configurable": {"session": session, "trace_id": trace_id}})
```

### Pattern 3: Prompt Context Through Existing Projectors

**What:** Load `ConversationService.load_prompt_context`, convert rows to prompt-safe dicts/models, and pass them into `ContextAssembler`. [VERIFIED: src/conversation/service.py, src/agent/nodes/generate_recommendation.py, src/agent/nodes/assess_risk_and_approval.py]

**When to use:** Use in recommendation/risk prompts now; add a shared loader for slot extraction if STM-05 requires prior messages/summary to resolve ambiguous references before slot routing. [VERIFIED: src/agent/nodes/extract_slots.py currently passes empty context]

### Anti-Patterns to Avoid

- **Appending conversation rows inline in the router without lookup/idempotency:** current tables do not prevent duplicate run/role messages by themselves. [VERIFIED: src/db/models.py]
- **Leaving session memory as post-final-response background work for `/agent-runs`:** current code schedules memory after `final_response`, which does not satisfy Phase 24 ordering. [VERIFIED: src/api/routers/agent_runs.py, tests/test_agent_runs_api.py]
- **Summarizing interrupted/error runs as if the assistant answered:** Phase 24 explicitly forbids false completed assistant messages and false rolling summaries for those statuses. [VERIFIED: 24-CONTEXT.md]
- **Using memory as evidence/business/action/replay authority:** docs and requirements keep memory contextual only. [VERIFIED: .planning/REQUIREMENTS.md, docs/contract-spec.md §13.7]
- **Stringifying raw tool/business/policy objects into prompts:** projectors already block unsafe keys/markers and tests assert raw values stay out. [VERIFIED: src/agent/context/projectors.py, tests/agent/context/test_assembler.py]

## Implementation Anchors

| Area | File / Function / Class | What Exists Now | Phase 24 Planning Implication |
|------|--------------------------|-----------------|-------------------------------|
| Legacy reference path | `src/api/routers/agent.py::chat` | Writes `AgentRun`, appends user message, injects `conversation_message_id`/`conversation_thread_id`, appends assistant message, persists thread summary, then schedules session memory. [VERIFIED: src/api/routers/agent.py] | Extract shared helpers from this path; do not copy divergent logic. [VERIFIED: 24-CONTEXT.md] |
| Run creation | `src/api/routers/agent_runs.py::create_agent_run` | Creates only `AgentRun` with `final_status="pending"` and commits; it does not append a user conversation message. [VERIFIED: src/api/routers/agent_runs.py] | Add user message persistence in the same creation transaction. [VERIFIED: STM-01] |
| SSE claim | `src/api/routers/agent_runs.py::_claim_pending_run_for_stream` | Locks run with `FOR UPDATE`, rejects non-`pending` runs with 409, updates to `running`, commits. [VERIFIED: src/api/routers/agent_runs.py] | Keep this duplicate execution guard; add conversation identity resolution after claim. [VERIFIED: 24-CONTEXT.md] |
| SSE graph config | `src/api/routers/agent_runs.py::stream_agent_run_events` | Passes checkpoint `thread_id`, session, permissions, merchant scope, and trace id; no conversation IDs are passed. [VERIFIED: src/api/routers/agent_runs.py] | Resolve user message and inject trusted conversation IDs before graph streaming. [VERIFIED: STM-02] |
| Terminal persistence | `src/api/routers/agent_runs.py::_complete_run` | Updates run status, token count, steps, and commits; it does not append assistant messages, summaries, or synchronous memory results. [VERIFIED: src/api/routers/agent_runs.py] | Replace/extend with completed-only memory finalizer. [VERIFIED: STM-03, STM-04, STM-11] |
| Background memory scheduling | `src/api/routers/agent_runs.py::_schedule_memory_write_after_response` | Runs `memory_write` in an async task after `final_response` yield in current SSE path. [VERIFIED: src/api/routers/agent_runs.py] | Do not use this as the required continuity path for `/agent-runs`; keep only for optional cleanup if any. [VERIFIED: 24-CONTEXT.md] |
| Conversation API | `ConversationService.append_user_message`, `append_assistant_message`, `append_tool_result`, `load_prompt_context` | Provides append methods, prompt summary creation, forbidden key guard, and prompt context window loading. [VERIFIED: src/conversation/service.py] | Reuse these APIs; add idempotent helpers rather than bypassing service guards. [VERIFIED: src/conversation/service.py] |
| Conversation repository | `ConversationRepository` | Has thread get/create, append/list messages, list prompt summaries, insert summary; no run/role get-once helper. [VERIFIED: src/conversation/repository.py] | Add run/role and summary-source lookup methods. [VERIFIED: src/conversation/repository.py] |
| Tool persistence gate | `src/agent/nodes/investigate.py::_can_persist_conversation_tool_records` | Requires session with `execute`/`flush` and `conversation_message_id`. [VERIFIED: src/agent/nodes/investigate.py] | Graph config wiring is mandatory for STM-02/STM-07. [VERIFIED: 24-CONTEXT.md] |
| Rolling summary | `ThreadRollingSummaryService.persist_thread_summary` | Builds from latest summary, messages after previous summary, and tool results after previous summary; ignores `run_id`; inserts a new row when new messages exist. [VERIFIED: src/memory/thread_summary.py] | Add idempotency by source end/range/hash before using in retriable finalization. [VERIFIED: STM-04, STM-10] |
| Session memory read | `session_memory_load` | Loads same tenant/user/thread session memory through `MemoryService`; fallback is observable. [VERIFIED: src/agent/nodes/session_memory_load.py] | Keep active for `/agent-runs`; no new storage layer needed. [VERIFIED: STM-06] |
| Session memory write | `memory_write` | Skips if no final response or approval/interrupted state; uses timeout, PII guard, `MemoryService.write_session_memory`, and emits memory events. [VERIFIED: src/agent/nodes/memory_write.py] | Call it in bounded terminal persistence for completed runs and persist explicit result. [VERIFIED: STM-09, STM-11] |
| Prompt context | `ContextAssembler` and projectors | Assembles protected blocks and redacts/allowlists prompt-facing fields. [VERIFIED: src/agent/context/assembler.py, src/agent/context/projectors.py] | Use this boundary for all newly loaded prompt context. [VERIFIED: STM-07, STM-12] |

## Current Gaps / Unknowns To Resolve In PLAN

1. `/agent-runs` creation currently does not create a conversation thread/message. [VERIFIED: src/api/routers/agent_runs.py]
2. `/agent-runs` graph config currently lacks `conversation_message_id` and `conversation_thread_id`, so `investigate` will not persist conversation tool records on this path. [VERIFIED: src/api/routers/agent_runs.py, src/agent/nodes/investigate.py]
3. Completed `/agent-runs` currently do not append assistant conversation messages or rolling summaries. [VERIFIED: src/api/routers/agent_runs.py]
4. Current SSE memory write ordering is explicitly post-`final_response`, and the existing test `test_sse_final_response_before_memory_write_schedule` locks in the old behavior. [VERIFIED: tests/test_agent_runs_api.py]
5. `conversation_messages` lacks run/role uniqueness and `summaries` lacks source-end uniqueness, so exactly-once behavior needs service and preferably DB idempotency. [VERIFIED: src/db/models.py]
6. `extract_slots` uses `ContextAssembler` but passes empty `thread_rolling_summary`, `recent_messages`, and `tool_result_summaries`; the plan must decide whether STM-05 requires prior conversation context before slot routing. [VERIFIED: src/agent/nodes/extract_slots.py]
7. Legacy chat currently appends an assistant message for approval interruption and error fallback, while Phase 24 requires `/agent-runs` not to create false completed assistant messages/summaries for interrupted/error states. [VERIFIED: src/api/routers/agent.py, 24-CONTEXT.md]
8. Existing run/SSE tests cover duplicate claim, cancellation, interruption, persistence failure, and memory scheduling, but not `/agent-runs` conversation rows, rolling summaries, or three-turn run/SSE smoke continuity. [VERIFIED: tests/test_agent_runs_api.py]

## Recommended Plan Decomposition

1. **Wave 0 - validation scaffolding:** add failing tests for STM-01 through STM-14 before implementation, especially `/agent-runs` conversation rows, config injection, completed-only finalizer, idempotent duplicate SSE, and three-turn smoke. [VERIFIED: .planning/config.json nyquist_validation=true, tests/test_agent_runs_api.py]
2. **Wave 1 - idempotency primitives:** add repository/service helpers and minimal DB indexes if chosen for run/role message uniqueness and summary source-end uniqueness. [VERIFIED: src/conversation/repository.py, src/db/models.py]
3. **Wave 2 - create/claim config wiring:** update `create_agent_run` to persist the user message in the same transaction, and update `stream_agent_run_events` to resolve that message and inject trusted conversation IDs plus `conversation_service`. [VERIFIED: src/api/routers/agent_runs.py, src/agent/nodes/investigate.py]
4. **Wave 3 - completed-run finalizer:** implement a completed-only finalizer used by both graph stream modes, persisting assistant message, rolling summary, bounded session memory result, run status, and steps before final SSE. [VERIFIED: src/api/routers/agent_runs.py]
5. **Wave 4 - failure semantics:** lock error/cancel/interrupted behavior so only user message plus run/trace/tool/approval/error metadata remains; no assistant message, no rolling summary, no successful session memory write. [VERIFIED: 24-CONTEXT.md, src/api/routers/agent_runs.py]
6. **Wave 5 - prompt context parity:** ensure `/agent-runs` follow-up turns load prompt context through `ConversationService.load_prompt_context` and `ContextAssembler`; add extract-slot context only through the same projector boundary if needed for STM-05. [VERIFIED: src/conversation/service.py, src/agent/context/assembler.py, src/agent/nodes/extract_slots.py]
7. **Wave 6 - legacy compatibility and smoke:** rerun legacy chat tests, `/agent-runs` tests, memory/context tests, and the three-turn smoke; record any local validation issue per project rules. [VERIFIED: CLAUDE.md, tests/conversation/test_service.py, tests/test_agent_runs_api.py]

Dependency order matters because tool summaries require the current-turn user `conversation_message_id`, rolling summaries require committed user/tool/assistant records, and same-thread prompt context depends on prior committed summaries/messages. [VERIFIED: src/agent/nodes/investigate.py, src/memory/thread_summary.py, src/conversation/service.py]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE transport | Custom chunked HTTP/event parser | `EventSourceResponse` | Current router already uses it and tests target generator output. [VERIFIED: src/api/routers/agent_runs.py, tests/test_agent_runs_api.py] |
| Conversation persistence | Raw SQL append logic in routers | `ConversationService` + `ConversationRepository` | Service enforces forbidden message keys and prompt-safe append boundaries. [VERIFIED: src/conversation/service.py, src/conversation/schemas.py] |
| Tool prompt summaries | Raw `ToolResultV2.data` or raw payload refs in prompt | `ConversationService.append_tool_result` and `ToolResultPromptSummary` | Existing summary builder stores normalized data separately and prompt summary separately. [VERIFIED: src/conversation/service.py, src/tools/contracts.py] |
| Rolling summary generation | Ad hoc string concatenation in router | `ThreadRollingSummaryService` | Existing service sanitizes raw markers, preserves source ranges, and extracts summary metadata. [VERIFIED: src/memory/thread_summary.py] |
| Prompt assembly | f-string / `str(dict)` prompt construction | `ContextAssembler` + projectors | Existing tests prove raw nested values and unsafe keys are excluded. [VERIFIED: tests/agent/context/test_assembler.py] |
| Session memory writes | Cache-only writes or last-write-wins | `MemoryService.write_session_memory` with PostgreSQL CAS | Contract and service implement CAS/merge/fallback semantics. [VERIFIED: src/memory/service.py, docs/contract-spec.md §18.1] |
| Evidence/authority resolution | Treating memory references as evidence/action authority | KnowledgeService/BusinessToolService/ApprovalService/replay records | Requirements forbid memory from satisfying these authority boundaries. [VERIFIED: .planning/REQUIREMENTS.md, docs/contract-spec.md §13.7] |

**Key insight:** The hard part is not storing text; it is preserving exactly-once and authority boundaries across SSE retry, disconnect, completed/error/interrupted terminal states, and prompt context projection. [VERIFIED: 24-CONTEXT.md, src/api/routers/agent_runs.py]

## Common Pitfalls

### Pitfall 1: Final Response Before Required Memory Persistence
**What goes wrong:** The user sees a final answer, but next-turn continuity is missing because memory persistence was scheduled after the SSE yield and may never run on disconnect. [VERIFIED: src/api/routers/agent_runs.py, tests/test_agent_runs_api.py]  
**How to avoid:** Run bounded completed-turn persistence before emitting `final_response`, and persist explicit skipped/error results. [VERIFIED: 24-CONTEXT.md, src/agent/nodes/memory_write.py]  
**Warning signs:** A test still asserts `scheduled == []` at the moment `final_response` is observed. [VERIFIED: tests/test_agent_runs_api.py]

### Pitfall 2: Duplicate Assistant Messages or Summaries
**What goes wrong:** A retried finalizer or partial failure appends another assistant message or another equivalent rolling summary. [VERIFIED: src/db/models.py lacks run/role unique guard; src/memory/thread_summary.py inserts new summary rows]  
**How to avoid:** Add get-or-create helpers and DB unique/index guards where feasible. [VERIFIED: src/conversation/repository.py patterns]

### Pitfall 3: Tool Summaries Not Attached To Current Turn
**What goes wrong:** `investigate` returns in-state prompt summaries but does not persist conversation tool rows because `conversation_message_id` was not passed in config. [VERIFIED: src/agent/nodes/investigate.py]  
**How to avoid:** Resolve the user message during SSE start and pass trusted conversation IDs. [VERIFIED: 24-CONTEXT.md]

### Pitfall 4: Memory Becomes Authority
**What goes wrong:** Prior summary/session slots are used to answer policy or business status without current tools/evidence. [VERIFIED: .planning/REQUIREMENTS.md, docs/contract-spec.md §13.7]  
**How to avoid:** Keep `ContextAssembler` safety constraints and preserve tool/evidence calls for current facts and policy claims. [VERIFIED: src/agent/context/assembler.py]

### Pitfall 5: Legacy Chat Breakage
**What goes wrong:** Shared helper extraction changes `/agent/chat` persistence semantics or tests without an explicit compatibility decision. [VERIFIED: 24-CONTEXT.md, src/api/routers/agent.py]  
**How to avoid:** Keep legacy tests green and use status-policy parameters if `/agent-runs` completed-only behavior differs from legacy interrupted/error behavior. [VERIFIED: tests/conversation/test_service.py, tests/test_agent_runs_api.py]

## Code Examples

### Resolve Current-Turn Conversation Identity

```python
# Source: src/api/routers/agent.py existing legacy pattern [VERIFIED]
user_message = await conversation_service.append_user_message(
    tenant_id=user.tenant_id,
    user_id=user.id,
    thread_id=body.thread_id,
    run_id=UUID(str(run_id)),
    content=body.query,
    trace_id=trace_id,
    prompt_template_version="chat.request.v1",
)
config["configurable"]["conversation_message_id"] = str(user_message.message_id)
config["configurable"]["conversation_thread_id"] = str(user_message.conversation_thread_id)
```

### Load Prompt Context Safely

```python
# Source: src/agent/nodes/generate_recommendation.py and src/conversation/service.py [VERIFIED]
context = await service.load_prompt_context(
    tenant_id=state["tenant_id"],
    user_id=state["user_id"],
    thread_id=str(state["thread_id"]),
    run_id=state["current_run_id"],
)
assembly = ContextAssembler().assemble(
    system_prompt=SYSTEM_PROMPT,
    current_user_message=str(state.get("user_query") or ""),
    working_state=project_working_state(state),
    thread_rolling_summary=context.latest_thread_summary.summary_text if context.latest_thread_summary else "",
    recent_messages=[{"role": m.role, "content": m.content} for m in context.recent_messages],
    tool_result_summaries=context.tool_prompt_summaries,
)
```

### Completed-Only Memory Write Guard

```python
# Source: src/agent/nodes/memory_write.py [VERIFIED]
if not state.get("final_response"):
    return _skipped(state, started_at, "not_completed_path")
if state.get("approval_result") or state.get("approval_required"):
    return _skipped(state, started_at, "not_completed_path")
if state.get("final_status") == "interrupted":
    return _skipped(state, started_at, "not_completed_path")
```

## State of the Art

| Old / Current Approach | Current Recommended Approach | When Changed / Source | Impact |
|------------------------|------------------------------|-----------------------|--------|
| Legacy `/agent/chat` is the only path with user/assistant message + rolling summary persistence. [VERIFIED: src/api/routers/agent.py] | Bring `/agent-runs + SSE` to parity without changing frontend contract. [VERIFIED: .planning/ROADMAP.md] | v1.7 Phase 24 scope, 2026-06-20. [VERIFIED: .planning/PROJECT.md] | Agent Console follow-up turns can use the same short-term surfaces. [VERIFIED: .planning/REQUIREMENTS.md] |
| `/agent-runs` schedules session memory after final SSE. [VERIFIED: src/api/routers/agent_runs.py] | Required continuity persistence is bounded before `final_response`; optional cleanup may remain background only if not needed for next turn. [VERIFIED: 24-CONTEXT.md] | Phase 24 decision D-14. [VERIFIED: 24-CONTEXT.md] | Fixes disconnect/retry continuity gap. [VERIFIED: tests/test_agent_runs_api.py current ordering test] |
| Prompt context is already loaded in recommendation/risk prompts, but not slot extraction. [VERIFIED: src/agent/nodes/generate_recommendation.py, src/agent/nodes/assess_risk_and_approval.py, src/agent/nodes/extract_slots.py] | Use a shared prompt-context loader/projector if slot/reference resolution needs prior messages before routing. [VERIFIED: STM-05, src/agent/context/assembler.py] | Phase 24 planning decision. [VERIFIED: .planning/REQUIREMENTS.md] | Avoids parallel prompt assembly and preserves safety boundaries. [VERIFIED: src/agent/context/projectors.py] |

**Deprecated/outdated for this phase:**
- Treating `/agent/chat` as the user-facing path is outdated for v1.7; the current milestone targets `/agent-runs + SSE`. [VERIFIED: .planning/PROJECT.md, .planning/ROADMAP.md]
- Treating session memory write as best-effort background work is outdated for the continuity promised by STM-06/STM-11 on `/agent-runs`. [VERIFIED: .planning/REQUIREMENTS.md, 24-CONTEXT.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| None | All implementation facts in this research were verified from project files, local commands, or user-provided Phase 24 context. [VERIFIED: sources listed below] | All | No assumption-driven planner decision identified. [VERIFIED: sources listed below] |

## Open Questions

1. **Should Phase 24 add DB partial unique indexes for run/role messages and summary source-end idempotency?**  
   What we know: current ORM has no run/role message uniqueness and no summary source-end uniqueness. [VERIFIED: src/db/models.py]  
   Recommendation: include a minimal Alembic migration unless planner intentionally accepts service-only idempotency. [VERIFIED: src/db/migrations/versions/011_memory_foundation_v2.py migration pattern]

2. **Should legacy chat interrupted/error assistant messages be changed now?**  
   What we know: legacy chat appends assistant messages on interrupt/error, while Phase 24 completed-only semantics are required for `/agent-runs`. [VERIFIED: src/api/routers/agent.py, 24-CONTEXT.md]  
   Recommendation: keep legacy behavior unless shared helper extraction forces a semantic decision; do not silently alter legacy tests. [VERIFIED: 24-CONTEXT.md]

3. **Should slot extraction load prior conversation context?**  
   What we know: `extract_slots` currently passes empty recent/summary/tool context, while recommendation/risk nodes load it. [VERIFIED: src/agent/nodes/extract_slots.py, src/agent/nodes/generate_recommendation.py]  
   Recommendation: if STM-05 three-turn smoke includes ambiguous slot references that session slots cannot resolve, add shared prompt-context loading to `extract_slots` through `ContextAssembler`; otherwise document that slot continuity is owned by session slots. [VERIFIED: .planning/REQUIREMENTS.md, src/agent/context/assembler.py]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Backend/test runtime | yes | 3.13.3 local CLI | Project supports `>=3.12`. [VERIFIED: `python3 --version`, pyproject.toml] |
| uv | Dependency/test commands | yes | 0.11.2 | Use project `.venv` only if uv unavailable. [VERIFIED: `uv --version`] |
| Docker Desktop / Docker Engine | Local DB/API/frontend smoke | yes | server 29.4.2 | None needed locally. [VERIFIED: `docker info --format`] |
| Docker Compose services | Phase 24 smoke | yes | `postgres`, `redis`, `api`, `frontend` healthy | `docker compose up --build` if stopped. [VERIFIED: `docker compose ps --format json`] |
| PostgreSQL connection | DB-backed tests/smoke | yes | `asyncpg` connected to `localhost:5432/moca` | Use docker compose Postgres. [VERIFIED: local asyncpg probe, docker-compose.yml] |
| psql / pg_isready CLI | Manual DB inspection | no | missing | Use `docker exec moca-postgres-1 pg_isready` or asyncpg probes. [VERIFIED: `command -v psql pg_isready`] |
| Redis CLI | Optional manual cache inspection | no | missing | Use docker exec if needed; Phase 24 does not need Redis for correctness. [VERIFIED: `command -v redis-cli`, docs/contract-spec.md §13.6] |

**Missing dependencies with no fallback:** None for planning/research. [VERIFIED: local probes]

**Missing dependencies with fallback:** `psql`, `pg_isready`, and `redis-cli` are absent on host; docker/asyncpg provide viable fallback for this phase. [VERIFIED: local probes]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 [VERIFIED: `uv run importlib.metadata`] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"` [VERIFIED: pyproject.toml] |
| Quick run command | `uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py -q` [VERIFIED: existing files] |
| Full suite command | `uv run pytest` [VERIFIED: Makefile] |
| Lint command | `uv run ruff check src/ tests/` [VERIFIED: Makefile] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| STM-01 | POST `/agent-runs` writes exactly one user message and creates/reuses conversation thread. [VERIFIED: .planning/REQUIREMENTS.md] | API integration | `uv run pytest tests/test_agent_runs_api.py::test_create_agent_run_persists_exactly_one_user_message -q` | Existing file, new test needed. [VERIFIED: tests/test_agent_runs_api.py] |
| STM-02 | SSE config includes trusted conversation IDs and tool records attach to current user message. [VERIFIED: .planning/REQUIREMENTS.md] | API/unit fake graph | `uv run pytest tests/test_agent_runs_api.py::test_agent_run_stream_passes_conversation_ids_to_graph_and_tools -q` | Existing file, new test needed. [VERIFIED: tests/test_agent_runs_api.py] |
| STM-03 | Completed run writes exactly one assistant message with final status metadata. [VERIFIED: .planning/REQUIREMENTS.md] | API integration | `uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message -q` | Existing file, new test needed. [VERIFIED: tests/test_agent_runs_api.py] |
| STM-04 | Completed run updates rolling summary from new messages and safe tool summaries, idempotently. [VERIFIED: .planning/REQUIREMENTS.md] | DB integration | `uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_updates_thread_summary_idempotently -q` | Existing file, new test needed. [VERIFIED: tests/test_agent_runs_api.py] |
| STM-05 | Follow-up loads recent messages, prior summary, and prompt-safe tool summaries into prompt context. [VERIFIED: .planning/REQUIREMENTS.md] | service/node integration | `uv run pytest tests/conversation/test_service.py::test_agent_runs_prompt_context_loads_prior_summary_recent_messages_and_tool_summaries -q` | Existing file, new or extended test needed. [VERIFIED: tests/conversation/test_service.py] |
| STM-06 | Session slot continuity remains active and explicit current-turn slots override inherited slots. [VERIFIED: .planning/REQUIREMENTS.md] | graph/service integration | `uv run pytest tests/agent/test_session_memory_integration.py tests/agent/test_required_slots.py -q` | Existing tests cover base behavior; add run/SSE coverage. [VERIFIED: tests/agent/test_session_memory_integration.py, tests/agent/test_required_slots.py] |
| STM-07 | Tool prompt summaries exclude raw/private/authority/debug/PII markers. [VERIFIED: .planning/REQUIREMENTS.md] | unit/integration | `uv run pytest tests/memory/test_thread_summary.py::test_thread_rolling_summary_includes_safe_tool_summaries_only tests/agent/context/test_assembler.py::test_context_assembler_excludes_raw_tool_business_policy_and_authority_payloads -q` | Existing coverage; add `/agent-runs` persisted-tool assertion. [VERIFIED: tests/memory/test_thread_summary.py, tests/agent/context/test_assembler.py] |
| STM-08 | Legacy `/agent/chat` remains green with shared helpers. [VERIFIED: .planning/REQUIREMENTS.md] | API/regression | `uv run pytest tests/test_agent_runs_api.py::test_agent_chat_only_token_invokes_legacy_chat_with_no_tool_permissions tests/conversation/test_service.py -q` | Existing files. [VERIFIED: tests/test_agent_runs_api.py, tests/conversation/test_service.py] |
| STM-09 | Error/cancel/interrupted runs do not create assistant messages or rolling summaries. [VERIFIED: .planning/REQUIREMENTS.md] | API/SSE integration | `uv run pytest tests/test_agent_runs_api.py::test_agent_run_error_cancel_interrupted_do_not_write_completed_memory -q` | Existing file, new combined test needed. [VERIFIED: tests/test_agent_runs_api.py] |
| STM-10 | Duplicate/reopened SSE streams do not duplicate messages/tools/summaries/session memory. [VERIFIED: .planning/REQUIREMENTS.md] | API/idempotency | `uv run pytest tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces -q` | Existing duplicate tests need extension. [VERIFIED: tests/test_agent_runs_api.py] |
| STM-11 | Required memory persistence completes/skips/errors before final SSE event. [VERIFIED: .planning/REQUIREMENTS.md] | SSE ordering | `uv run pytest tests/test_agent_runs_api.py::test_sse_final_response_after_bounded_memory_persistence_result -q` | Existing old-order test must be replaced. [VERIFIED: tests/test_agent_runs_api.py] |
| STM-12 | Memory context cannot satisfy policy evidence/business fact/approval/action/replay truth. [VERIFIED: .planning/REQUIREMENTS.md] | security/regression | `uv run pytest tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py -q` | Existing files, add Phase 24 run-context case if needed. [VERIFIED: repo grep] |
| STM-13 | Regression coverage spans persistence/context/idempotency/legacy. [VERIFIED: .planning/REQUIREMENTS.md] | suite gate | `uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/memory/test_session_memory_service.py -q` | Existing files. [VERIFIED: listed files] |
| STM-14 | Three-turn Agent Console smoke uses slot continuity and rolling summary context. [VERIFIED: .planning/REQUIREMENTS.md] | live/integration smoke | `uv run pytest tests/test_agent_runs_api.py::test_three_turn_agent_runs_smoke_uses_slots_and_summary_context -q` or scripted docker smoke | Existing file, new smoke needed. [VERIFIED: tests/test_agent_runs_api.py, docker-compose.yml] |

### Sampling Rate

- **Per task commit:** run the focused test(s) for touched behavior plus `uv run ruff check src/ tests/`. [VERIFIED: Makefile]
- **Per wave merge:** run `uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/memory/test_session_memory_service.py -q`. [VERIFIED: existing test files]
- **Phase gate:** run `uv run pytest` and a three-turn smoke against local docker compose or DB-backed ASGI test. [VERIFIED: Makefile, docker-compose.yml]

### Wave 0 Gaps

- [ ] `tests/test_agent_runs_api.py` — add STM-01/02/03/04/09/10/11/14 run/SSE parity tests. [VERIFIED: tests/test_agent_runs_api.py]
- [ ] `tests/conversation/test_service.py` — add/extend run/role idempotency and prompt-context window tests. [VERIFIED: tests/conversation/test_service.py]
- [ ] `tests/memory/test_thread_summary.py` — add summary idempotency by source end/range if implementation changes summary persistence. [VERIFIED: tests/memory/test_thread_summary.py]
- [ ] Update or replace `test_sse_final_response_before_memory_write_schedule` because it asserts pre-Phase-24 ordering. [VERIFIED: tests/test_agent_runs_api.py]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Continue FastAPI `Security(get_current_user, scopes=["agent:chat"])`; do not trust user-provided tenant/user IDs. [VERIFIED: src/api/routers/agent_runs.py] |
| V3 Session Management | partial | JWT/request context scopes are already used; Phase 24 should not add browser session state. [VERIFIED: src/auth/permissions.py via router imports, src/api/routers/agent_runs.py] |
| V4 Access Control | yes | Keep `_ensure_can_view_run` tenant/user/supervisor checks and cross-tenant 404 behavior. [VERIFIED: src/api/routers/agent_runs.py, tests/test_agent_runs_api.py] |
| V5 Input Validation | yes | Keep Pydantic request schemas and conversation forbidden-key guards. [VERIFIED: src/api/schemas/agent_runs.py, src/conversation/schemas.py] |
| V6 Cryptography | no new crypto | Do not introduce new hashes except existing content/summary hash patterns; do not use memory hashes as authority. [VERIFIED: src/memory/thread_summary.py, docs/contract-spec.md §13.7] |

### Known Threat Patterns for Phase 24

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Duplicate SSE stream causes duplicate side effects | Tampering / Repudiation | Keep pending-run claim and add idempotent message/summary/session finalizer guards. [VERIFIED: src/api/routers/agent_runs.py, src/db/models.py] |
| Cross-user/thread memory leakage | Information Disclosure | Scope all conversation/session reads by `tenant_id`, `user_id`, and `thread_id`; preserve existing user-scoped tests. [VERIFIED: src/conversation/repository.py, tests/conversation/test_service.py] |
| Memory poisoning becomes policy/business authority | Elevation of Privilege / Tampering | Require current tools/evidence for business/policy claims; memory remains contextual. [VERIFIED: .planning/REQUIREMENTS.md, docs/contract-spec.md §13.7] |
| Prompt leakage through tool summaries | Information Disclosure | Use `ToolResultPromptSummary`, `ContextAssembler`, and projector allowlists; test forbidden markers. [VERIFIED: src/conversation/service.py, src/agent/context/projectors.py, tests/agent/context/test_assembler.py] |
| False completed answer on error/interruption | Repudiation | Gate assistant message, summary, and successful memory writes to `completed` status only. [VERIFIED: 24-CONTEXT.md] |
| Timeline reports completed before persistence finishes | Repudiation | Emit no completed persistence/timeline event until actual persistence result is done; backend-only persistence is acceptable if not shown as timeline completion. [VERIFIED: 24-CONTEXT.md] |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/24-agent-runs-short-term-memory-parity/24-CONTEXT.md` - locked Phase 24 decisions and boundaries. [VERIFIED]
- `.planning/REQUIREMENTS.md` - STM-01 through STM-14 and out-of-scope items. [VERIFIED]
- `.planning/ROADMAP.md`, `.planning/PROJECT.md`, `.planning/STATE.md` - v1.7 scope, success criteria, current status, and authority boundaries. [VERIFIED]
- `CLAUDE.md`, `AGENTS.md` - MOCA project workflow constraints and local validation issue recording rule. [VERIFIED]
- `src/api/routers/agent.py`, `src/api/routers/agent_runs.py` - legacy reference path and current target path. [VERIFIED]
- `src/conversation/service.py`, `src/conversation/repository.py`, `src/db/models.py` - conversation persistence APIs and schema constraints. [VERIFIED]
- `src/memory/thread_summary.py`, `src/memory/service.py`, `src/memory/repository.py` - rolling summary and PostgreSQL session memory behavior. [VERIFIED]
- `src/agent/nodes/investigate.py`, `src/agent/nodes/session_memory_load.py`, `src/agent/nodes/memory_write.py`, `src/agent/context/assembler.py`, `src/agent/context/projectors.py` - tool persistence, session memory, and prompt-safe context boundaries. [VERIFIED]
- `tests/test_agent_runs_api.py`, `tests/conversation/test_service.py`, `tests/memory/test_thread_summary.py`, `tests/memory/test_session_memory_service.py`, `tests/agent/test_session_memory_integration.py`, `tests/agent/context/test_assembler.py` - existing regression anchors and test gaps. [VERIFIED]
- `docs/contract-spec.md` §§13.6-13.7, 17.6-17.7, 18.1, 18.4 - memory authority, replay redaction, and schema constraints. [CITED: docs/contract-spec.md]

### Secondary (MEDIUM confidence)
- Local environment probes: `uv run importlib.metadata`, `docker compose ps`, `docker info`, asyncpg connection to `localhost:5432/moca`. [VERIFIED: local commands]

### Tertiary (LOW confidence)
- None. [VERIFIED: research did not rely on unverified web/community sources]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions verified from local installed lock/runtime and project files. [VERIFIED: `uv run importlib.metadata`, pyproject.toml]
- Architecture: HIGH - implementation anchors verified directly in code and prior phase context. [VERIFIED: source files listed above]
- Pitfalls: HIGH - risks come from current code paths, current tests, and locked Phase 24 decisions. [VERIFIED: src/api/routers/agent_runs.py, tests/test_agent_runs_api.py, 24-CONTEXT.md]
- Open questions: MEDIUM - they are planning decisions derived from verified gaps, not unresolved code facts. [VERIFIED: src/db/models.py, src/agent/nodes/extract_slots.py]

**Research date:** 2026-06-20  
**Valid until:** 2026-07-20 for codebase-local findings, or until `agent_runs.py` / conversation/memory services change materially. [VERIFIED: current repository state]
