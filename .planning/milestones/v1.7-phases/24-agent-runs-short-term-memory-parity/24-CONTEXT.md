# Phase 24: Agent Runs Short-term Memory Parity - Context

**Gathered:** 2026-06-20  
**Status:** Ready for planning  
**Source:** `$gsd-discuss-phase 24` with Codex fallback defaults after `request_user_input` was unavailable in Default mode

<domain>
## Phase Boundary

Phase 24 completes the short-term memory chain for the current Agent Console main path, `/api/v1/agent-runs + SSE`.

It must bring the run-based path to parity with the legacy `/api/v1/agent/chat` conversation persistence path: user messages, assistant messages, prompt-safe tool call/result records, rolling thread summaries, and PostgreSQL-backed session slots must work together for same-thread follow-up turns.

This phase must not redesign long-term memory, case memory, approval/action execution, replay truth, policy evidence identity, or the frontend UX. Memory remains contextual assistance only. Business facts still come from current BusinessToolService/tool records, policy evidence still comes from KnowledgeService/`EvidenceRefV1`, approval/action authority still comes from approval/action tables and snapshots, and replay/audit truth still comes from run/step/tool/event records.

</domain>

<decisions>
## Implementation Decisions

### `/agent-runs` Conversation Persistence
- **D-01:** Persist exactly one user conversation message during `POST /api/v1/agent-runs` creation. This makes run creation the durable "user submitted this query" boundary and avoids duplicate user messages when the SSE endpoint is retried, reopened, or rejected after the pending claim.
- **D-02:** The SSE execution path must resolve and reuse the existing user conversation message for the run, then pass trusted `conversation_thread_id` and `conversation_message_id` into graph config. `investigate` already persists tool call/result rows only when `conversation_message_id` is present, so this config wiring is required for tool summaries to attach to the current turn.
- **D-03:** Completed runs persist exactly one assistant conversation message after graph final state is known and before the final SSE response is emitted. Assistant messages should carry final status metadata, but no private reasoning, raw tool payloads, authority bodies, or debug traces.
- **D-04:** Completed runs update the thread rolling summary from committed user/assistant messages and eligible prompt-safe tool summaries. Rolling summary creation must be idempotent at the run/turn level; retries must not create duplicate assistant messages or duplicate equivalent summaries.

### Prompt Context Composition
- **D-05:** Enable the full short-term context stack for `/agent-runs`: trusted session slots, recent conversation messages, recent prompt-safe tool summaries, and the latest prior rolling thread summary.
- **D-06:** Prompt context is contextual only. It can help resolve references such as "这个订单" or "刚才那个退款", but it cannot satisfy policy evidence, current business fact, approval/action authority, or replay/audit truth requirements. Any answer that needs current order/refund/ticket facts must still call tools; any policy answer must still retrieve/verify policy evidence.
- **D-07:** Use existing prompt-safe projection boundaries where possible: `ConversationService.load_prompt_context`, `ContextAssembler`, `WorkingStateV1`, and `src/agent/context/projectors.py`. Do not assemble prompt context by stringifying raw dicts, raw tool results, or unprojected business/policy/approval objects.
- **D-08:** Explicit current-turn slots override inherited trusted session slots. Stale, incompatible, cross-tenant, cross-user, or cross-thread memory fails closed to clarification or current-turn-only behavior.

### Terminal and Failure Semantics
- **D-09:** Only `completed` runs write assistant messages, rolling summaries, and successful session-memory updates. Normal clarification responses are completed responses and should be persisted like other assistant messages.
- **D-10:** `error`, `cancelled`, and `interrupted` runs preserve the user message, run status, trace/tool records, approval request/event records where applicable, and error/interruption metadata, but they must not create false completed assistant messages or false completed rolling summaries.
- **D-11:** Approval interruption is not a completed assistant answer. It may create approval records and trace/replay events, but it should not be summarized as if the agent answered the user. If a later approval resume produces a completed response, that later completed run/revision owns its assistant message and summary.
- **D-12:** SSE retry/reopen semantics do not need to replay the full prior event stream in this phase. The current "claim pending run once" model can stay, but duplicate streams must never re-execute the graph or duplicate user messages, assistant messages, tool result records, summaries, or session-memory writes.

### Timeline and Memory Write Ordering
- **D-13:** Any persistence stage exposed as running in the Agent Timeline must stay `running` until that stage's actual work is done, then replace itself with `completed`. Do not emit a completed event for a stage whose downstream persistence obligation is still running.
- **D-14:** For `/agent-runs`, terminal memory persistence should be bounded and ordered before the final SSE `final_response` event when that persistence is part of the promised short-term continuity. If a bounded memory write fails or times out, record an explicit skipped/error result and continue with a safe final response; do not silently report memory success.
- **D-15:** The planner may keep low-risk cleanup/background enrichment outside the final-response critical path only if it is not required for the next user turn's short-term continuity and it is clearly not shown as completed in the timeline.

### Compatibility with Legacy Chat
- **D-16:** `/api/v1/agent/chat` remains the compatibility reference path. Phase 24 should extract shared helpers/services where needed rather than copy divergent persistence logic into `/agent-runs`.
- **D-17:** Legacy chat tests must remain green. If shared persistence behavior changes, both `/agent/chat` and `/agent-runs` should use the same semantics for user/assistant messages, tool summary storage, rolling summary updates, prompt-safe redaction, and session memory boundaries.

### the agent's Discretion
- The planner may choose exact helper names, repository methods, idempotency key shape, and test file split.
- The planner may decide whether conversation message IDs are stored directly on `agent_runs`, resolved by `run_id` lookup in `conversation_messages`, or managed through a small run-memory linkage helper, as long as exactly-once semantics and SSE retry safety are preserved.
- The planner may decide whether the final terminal persistence appears as explicit SSE timeline nodes or remains backend-only, as long as displayed node statuses are truthful and next-turn memory continuity is deterministic.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 24 Scope
- `.planning/ROADMAP.md` — Phase 24 goal, success criteria, and requirement mapping.
- `.planning/REQUIREMENTS.md` — STM-01 through STM-14 requirements and out-of-scope boundaries.
- `.planning/STATE.md` — Current v1.7 milestone state and decisions.
- `.planning/PROJECT.md` — Core value, v1.7 target features, and memory authority boundaries.

### Prior Memory and Replay Decisions
- `.planning/milestones/v1.1-phases/12-session-memory/12-CONTEXT.md` — PostgreSQL-authoritative session memory, safe slot inheritance, CAS/fallback, and memory-is-not-evidence decisions.
- `.planning/milestones/v1.1-phases/15.1-memory-foundation-v2/15.1-CONTEXT.md` — Conversation log, tool result layering, thread rolling summary, ContextAssembler, and prompt-safe projection decisions.
- `.planning/milestones/v1.1-phases/15-replay-event-contract/15-CONTEXT.md` — Replay records what happened and must not become business truth or action authority.
- `docs/contract-spec.md` §§9.2-10.1, 13, 17-18 — Canonical graph/memory/replay/evidence/action boundaries. Treat this as target contract guidance; current implementation facts must still be verified in code.

### Current Implementation Anchors
- `src/api/routers/agent.py` — Legacy `/api/v1/agent/chat` path that already appends user/assistant messages, passes conversation IDs to graph config, persists rolling summary, and schedules session memory write.
- `src/api/routers/agent_runs.py` — Current `/api/v1/agent-runs + SSE` target path: pending run creation, SSE claim, graph stream, terminal persistence, error/interruption handling, and session-memory scheduling.
- `src/conversation/service.py` — ConversationService append APIs, prompt-safe tool result persistence, and `load_prompt_context` behavior.
- `src/conversation/repository.py` — Thread/message/tool/summary persistence and list/query helpers.
- `src/memory/thread_summary.py` — Deterministic rolling summary builder and sanitizer.
- `src/agent/nodes/investigate.py` — Tool call/result persistence wiring gated by `conversation_message_id`.
- `src/agent/nodes/session_memory_load.py` — Same-thread PostgreSQL session memory load and fallback view.
- `src/agent/nodes/memory_write.py` — Session memory write candidate, PII guard, timeout, event emission, and trace step behavior.
- `src/agent/context/assembler.py` — Prompt assembly boundary for working state, thread rolling summary, recent messages, tool summaries, memory snippets, and safety constraints.
- `src/agent/context/projectors.py` — Prompt-safe projection allowlists and leakage guards.
- `tests/test_agent_runs_api.py` — Run/SSE lifecycle, duplicate guard, cancellation, interruption, final response timing, and trusted tool config coverage.
- `tests/conversation/test_service.py` — Prompt context loading, user scoping, current-run recent messages, prior rolling summary, and tool prompt summary coverage.
- `tests/memory/test_thread_summary.py` and `tests/memory/test_session_memory_service.py` — Rolling summary and session memory behavior.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ConversationService.append_user_message`, `append_assistant_message`, `append_tool_call`, `append_tool_result`, and `load_prompt_context` already provide most conversation persistence and prompt-context APIs needed for `/agent-runs`.
- `ThreadRollingSummaryService.persist_thread_summary` already builds deterministic `thread_rolling` summaries from new messages and prompt-safe tool summaries.
- `ContextAssembler` and projector helpers already enforce prompt-safe conversion for thread summaries, recent messages, tool summaries, business context, profile/case memory, and current user message.
- `session_memory_load` and `memory_write` already implement PostgreSQL-backed session slot continuity with fallback, timeout, PII checks, trace steps, and memory write events.
- `tests/test_agent_runs_api.py` already has fake graph classes and SSE generator tests that can be extended for conversation/message/summary/idempotency assertions.

### Established Patterns
- API routers should stay thin and call services/repositories rather than writing raw persistence logic inline.
- Agent nodes should receive trusted config from API/auth/run boundaries; user payload and LLM output must not forge trusted IDs.
- Tool records are persisted by `investigate` only when a valid `conversation_message_id` is present in config.
- Prompt-facing content must go through explicit summaries/projectors and field allowlists. Raw tool payloads, private reasoning, approval/action authority bodies, hashes/snapshots, and debug traces are not prompt context.
- Run lifecycle status and trace/replay records are separate from memory summaries. Memory summaries can help prompts, but they are not audit truth.

### Integration Points
- `create_agent_run` should create or resolve the conversation thread and persist the user message once.
- `stream_agent_run_events` should load/reuse the run's conversation identity and place it into `config["configurable"]` before graph streaming begins.
- `_complete_run` or a new shared finalizer helper should own assistant-message persistence, rolling-summary update, bounded session-memory persistence, run terminal status, and idempotency guards.
- Error/cancel/interruption handlers should explicitly choose the no-assistant/no-summary path while preserving run/tool/trace/approval records.
- Prompt context should be loaded before nodes that need same-thread continuity and then projected through existing safe boundaries; do not introduce a parallel prompt string builder.

</code_context>

<specifics>
## Specific Ideas

- Treat `/agent/chat` as the working reference implementation and `/agent-runs` as the target user-facing path that needs parity.
- Same-thread follow-up should support natural references like "那这个订单下一步怎么办？" after a prior turn mentioned `ORD-2024-001`, but the agent must still re-query current order/refund/ticket facts before asserting status or recommending action.
- A policy-only follow-up can use prior conversation context to understand what "这个规则" refers to, but final policy claims still need current verified policy evidence.
- A failed or interrupted run should be visible in run/trace/approval surfaces, not disguised as a successful assistant conversation turn.

</specifics>

<deferred>
## Deferred Ideas

- Full memory inspection/management UI remains future scope (`STM-FUT-01`).
- Retention, archival, deletion policy controls remain future scope (`STM-FUT-02`).
- Admin review workflow for promoting conversation patterns into reviewed long-term or case memory remains future scope (`STM-FUT-03`).
- Full SSE event replay/reconnect UX is not required for Phase 24; this phase only requires no duplicate execution or duplicate memory writes.

</deferred>

---

*Phase: 24-agent-runs-short-term-memory-parity*  
*Context gathered: 2026-06-20*
