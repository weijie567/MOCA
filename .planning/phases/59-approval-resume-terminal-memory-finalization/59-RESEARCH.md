# Phase 59: Approval Resume Terminal Memory Finalization - Research

**Researched:** 2026-07-08 [VERIFIED: system date]  
**Domain:** FastAPI approval resume lifecycle, agent-run terminal memory finalizer, session memory, thread summary, Case Working Context finalization [VERIFIED: .planning/ROADMAP.md:516-529]  
**Confidence:** HIGH, because the gap, target code path, normal lifecycle path, and regression surfaces were verified from current source and tests. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:64] [VERIFIED: src/api/routers/approvals.py:283-349] [VERIFIED: src/api/routers/agent_runs.py:393-410]

## Summary

Phase 59 exists because normal `agent-runs` terminal completion calls `finalize_completed_agent_run_memory(...)`, while approval-resume completion in `approvals.py` updates `AgentRun` status and appends post-approval trace steps without invoking the same terminal finalizer. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:64] [VERIFIED: src/api/routers/agent_runs.py:393-410] [VERIFIED: src/api/routers/approvals.py:318-349]

The approval-resume completed branch should invoke the same terminal finalization boundary after the run is durably marked completed and post-resume trace steps are appended, but before the lifecycle records `approval_resumed` as completed. [VERIFIED: src/api/routers/approvals.py:239-263] [VERIFIED: src/api/routers/approvals.py:325-349] The finalizer must use the original run requester, not the reviewer/admin actor used for trusted graph resume, because the finalizer writes assistant messages, session memory state, and CWC writeback under `run.user_id` / requester context. [VERIFIED: src/api/routers/approvals.py:729-749] [VERIFIED: src/api/services/agent_run_memory.py:81-95] [VERIFIED: src/api/services/agent_run_memory.py:199-217]

The main planning trap is that the existing `memory_write` node skips any state containing `approval_result`, `approval_required`, or `risk_assessment.approval_required is True`; approval-resume terminal states commonly carry those markers, so simply calling the finalizer may still skip the terminal memory write. [VERIFIED: src/agent/nodes/memory_write.py:42-50] [VERIFIED: src/agent/nodes/memory_write.py:354-360] The plan must add a targeted terminal-finalizer path or state sanitizer that lets completed approval-resume finalization write memory without making pending/interrupted approval states memory-eligible. [VERIFIED: src/api/services/agent_run_memory.py:151-178] [VERIFIED: src/agent/nodes/memory_write.py:354-360]

**Primary recommendation:** implement a shared terminal-finalization helper for approval resume that fetches the requester, reconstructs normal-run input identity, invokes `finalize_completed_agent_run_memory(...)`, and persists finalizer trace steps with an explicit duplicate guard. [VERIFIED: src/api/services/agent_run_memory.py:53-65] [VERIFIED: src/api/routers/agent_runs.py:1068-1087] [VERIFIED: src/agent/trace.py:176-217]

## Project Constraints

- `CLAUDE.md` requires local debug, startup, validation, API, RAG, agent, memory, or tool-call issues discovered during work to be appended to `.planning/LOCAL-VALIDATION-ISSUES.md` with evidence and follow-up entry points. [VERIFIED: CLAUDE.md:5-15]
- `CLAUDE.md` requires memory subsystem architecture bugs, design debt, or fixes discovered while changing memory code to be appended to `.planning/ARCHITECTURE-DEBT.md`. [VERIFIED: CLAUDE.md:9-15]
- `AGENTS.md` forbids bare `pytest` and bare `python -m pytest`; valid test entrypoints are `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` or the current repo `.venv/bin/...` equivalents. [VERIFIED: AGENTS.md:24-29]
- Phase-level planning must explicitly check plan granularity and split broad work by ownership boundary, wave, and verification gate when needed. [VERIFIED: AGENTS.md:55-60]
- Project graph context was unavailable because graphify is disabled in this workspace. [VERIFIED: `node /Users/ming/.codex/get-shit-done/bin/gsd-tools.cjs graphify status`]
- No Phase 59 `CONTEXT.md` exists, and `init.phase-op 59` reports `has_context: false`. [VERIFIED: `gsd-sdk query init.phase-op 59`]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Approval decision and trusted graph resume | API / Backend | Database / Storage | The `/approvals/{id}/decide` router calls `ApprovalService.decide`, records resume lifecycle events, invokes LangGraph resume, and updates `AgentRun`. [VERIFIED: src/api/routers/approvals.py:67-150] [VERIFIED: src/api/routers/approvals.py:239-349] |
| Terminal assistant message and thread summary persistence | API / Backend | Database / Storage | `finalize_completed_agent_run_memory(...)` owns assistant-message append/reuse and thread-summary persistence through conversation services. [VERIFIED: src/api/services/agent_run_memory.py:79-96] |
| Terminal session memory write | API / Backend | Database / Storage | The finalizer runs `memory_write(...)` in an isolated child session after terminal completion. [VERIFIED: src/api/services/agent_run_memory.py:151-178] [VERIFIED: src/memory/write_isolation.py:11-24] |
| Terminal Case Working Context writeback | API / Backend | Database / Storage | The finalizer calls `CaseWorkingContextLifecycleAdapter.write_after_terminal_success(...)`, which resolves case identity, links thread-case, projects a terminal candidate, and calls the CWC write service. [VERIFIED: src/api/services/agent_run_memory.py:199-217] [VERIFIED: src/memory/case_working_context_lifecycle.py:189-343] |
| Canonical graph vocabulary preservation | API / Backend | Test / Architecture guardrails | Phase 59 should not register or revive graph node aliases; current tests assert the exact final 15-node vocabulary and no legacy runtime aliases. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:68-88] [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:102-114] |

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MEM-01 | Durable case-scoped working context remains contextual-only, versioned, trusted-run-bound, and prompt-safe. [VERIFIED: .planning/REQUIREMENTS.md:36] | Approval resume must call CWC terminal writeback through the finalizer and preserve CWC source refs/status trace metrics. [VERIFIED: src/api/services/agent_run_memory.py:109-127] [VERIFIED: src/memory/case_working_context_lifecycle.py:461-492] |
| MEM-02 | Thread-case many-to-many association is the linkage surface for case working context. [VERIFIED: .planning/REQUIREMENTS.md:37] | CWC terminal writeback links the run thread to the resolved case and dedupes existing links. [VERIFIED: src/memory/case_working_context_lifecycle.py:228-236] [VERIFIED: src/memory/case_working_context_lifecycle.py:345-388] |
| MEM-03 | `session_memories` remains thread-scoped short-lived conversational context and must not become authority for case/business/policy/approval/action truth. [VERIFIED: .planning/REQUIREMENTS.md:38] | Terminal session memory should write under requester/run/thread identity and stay separate from CWC and approval/action authority. [VERIFIED: src/api/services/agent_run_memory.py:255-276] [VERIFIED: src/agent/nodes/memory_write.py:42-55] |
| CAGM-08 | `risk_gate` must preserve separation between deterministic risk/action policy and `approval_gate` pending/trusted-resume state. [VERIFIED: .planning/REQUIREMENTS.md:60] | The plan must not change trusted resume payload validation, reviewer trusted context, action-draft reconciliation, or approval retry semantics. [VERIFIED: src/api/routers/approvals.py:638-693] [VERIFIED: src/api/routers/approvals.py:729-749] |
| CAGM-09 | Active runtime graph is the final 15 canonical nodes with no active legacy aliases. [VERIFIED: .planning/REQUIREMENTS.md:61] | Tests already guard that `risk_gate` is active and `assess_risk_and_approval` is not active runtime vocabulary. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:45-55] [VERIFIED: tests/test_approval_api.py:1233-1249] |

</phase_requirements>

## Implementation Surface

The approval route entry point is `decide_approval`, which either uses a persisted retry result from `_recoverable_resume_retry_result(...)` or calls `ApprovalService.decide(...)`; when `_should_resume_graph(result)` is true, it commits the approval decision before invoking `_run_resume_lifecycle(...)`. [VERIFIED: src/api/routers/approvals.py:67-150] `_run_resume_lifecycle(...)` records `approval_resumed` with `resume_status="attempted"`, commits, calls `_resume_graph_after_decision(...)`, then records `resume_status="completed"` and commits. [VERIFIED: src/api/routers/approvals.py:239-263]

`_resume_graph_after_decision(...)` builds the trusted resume config, invokes `graph.ainvoke(Command(resume=result.resume_payload), config)`, handles `GraphInterrupt` or `__interrupt__` by delegating to `_handle_resume_interrupt(...)`, reconciles action drafts, derives `final_status`, updates `AgentRun`, and appends trace steps after the first `approval_gate` step. [VERIFIED: src/api/routers/approvals.py:283-349]

The correct insertion point for terminal memory finalization is the completed branch of `_resume_graph_after_decision(...)` after `update_agent_run_status(...)` and post-resume `append_agent_steps(...)` have succeeded, because normal `agent-runs` commits run completion and graph trace before invoking the terminal finalizer. [VERIFIED: src/api/routers/approvals.py:325-349] [VERIFIED: src/api/routers/agent_runs.py:1037-1065] [VERIFIED: src/api/routers/agent_runs.py:393-410]

`_handle_resume_interrupt(...)` creates a replacement approval wait payload, updates the run to `final_status="interrupted"`, and appends post-interrupt trace steps when present; this branch must explicitly skip terminal memory finalization because it is not a terminal completed path. [VERIFIED: src/api/routers/approvals.py:351-407] [VERIFIED: .planning/ROADMAP.md:523-529]

`_resume_graph_config(...)` intentionally uses the reviewer/admin actor as `trusted_context.user_id` and grants action-draft permission only for approved accept/approve decisions; this trusted resume identity should not be reused as the finalizer `user`. [VERIFIED: src/api/routers/approvals.py:729-749] The finalizer should fetch `User` by `run.user_id`, because finalizer assistant messages are written with `run.user_id` and CWC writeback receives `user.id`. [VERIFIED: src/api/services/agent_run_memory.py:81-95] [VERIFIED: src/api/services/agent_run_memory.py:199-217]

The approval resume action-draft reconciliation branch already checks for an existing `ActionDraft` by `run_id` and `approval_request_id` before invoking `action_draft(...)`; Phase 59 should not change that reconciliation contract. [VERIFIED: src/api/routers/approvals.py:638-693]

## Existing Lifecycle Evidence

Normal stream completion in `agent_runs.py` calls `_complete_run(...)`, then `finalize_completed_agent_run_memory(...)`, then `_persist_finalizer_trace_steps(...)` in both graph update and graph event generator paths. [VERIFIED: src/api/routers/agent_runs.py:383-410] [VERIFIED: src/api/routers/agent_runs.py:547-574]

`_complete_run(...)` updates `AgentRun`, writes graph trace steps, and commits before finalization starts. [VERIFIED: src/api/routers/agent_runs.py:1037-1065] `_persist_finalizer_trace_steps(...)` appends finalizer trace steps after the prior graph trace and commits, but it suppresses exceptions after rollback. [VERIFIED: src/api/routers/agent_runs.py:1068-1087]

The finalizer skips all non-completed or missing-response cases with `status="skipped"` and `reason_code="not_completed_path"`, and it returns no finalizer trace steps for those skipped paths. [VERIFIED: src/api/services/agent_run_memory.py:66-77] Existing normal-run tests assert error, cancelled, and interrupted paths do not write assistant messages or summaries. [VERIFIED: tests/test_agent_runs_api.py:2548-2605] [VERIFIED: tests/test_agent_runs_api.py:2957-3010]

The finalizer appends or reuses an assistant message with metadata `{"status": "completed", "source": "agent_runs.finalizer"}` and persists a thread rolling summary before running memory side effects. [VERIFIED: src/api/services/agent_run_memory.py:79-96] Existing normal-run tests assert exactly one assistant message, finalizer trace metrics, and thread summary idempotency. [VERIFIED: tests/test_agent_runs_api.py:1485-1518] [VERIFIED: tests/test_agent_runs_api.py:1521-1558]

The finalizer runs terminal session memory in an isolated child session and maps missing/fallback/error results to canonical `completed`, `skipped`, `failed`, or `error` statuses. [VERIFIED: src/api/services/agent_run_memory.py:151-197] [VERIFIED: src/api/services/agent_run_memory.py:279-289] Existing tests assert child memory rollback does not remove assistant-message or summary rows. [VERIFIED: tests/test_agent_runs_api.py:2821-2878]

The finalizer runs terminal CWC writeback after session memory and includes CWC status, reason code, memory id, version, and duration in the finalizer trace metrics. [VERIFIED: src/api/services/agent_run_memory.py:109-127] [VERIFIED: src/api/services/agent_run_memory.py:299-334] Existing tests assert successful CWC writeback, blocked PII handling, conflict handling, and CWC failure preservation of terminal conversation rows. [VERIFIED: tests/test_agent_runs_api.py:2608-2655] [VERIFIED: tests/test_agent_runs_api.py:2658-2819]

Approval retry semantics already allow retry only when the latest resume status is incomplete and the run is still `interrupted`, `running`, or `pending`; a run already in another final status is not eligible for recoverable retry. [VERIFIED: src/api/routers/approvals.py:445-475] `_latest_resume_status(...)` uses approval events keyed by `resume_key` and recognizes `attempted`, `failed`, and `completed`. [VERIFIED: src/api/routers/approvals.py:478-495]

Existing approval tests cover approval resume trusted context, commit-before-graph ordering, recoverable terminal retry, edit re-interrupt retry, historical retry route mapping, and current completed status. [VERIFIED: tests/test_approval_api.py:383-453] [VERIFIED: tests/test_approval_api.py:456-573] [VERIFIED: tests/test_approval_api.py:906-1113] [VERIFIED: tests/test_approval_api.py:1233-1249] [VERIFIED: tests/test_approval_api.py:1505-1526]

## Finalizer Input/Idempotency Requirements

`finalize_completed_agent_run_memory(...)` requires `session`, `run`, `user`, `input_state`, `final_state`, `final_status`, `final_response`, `trace_steps`, and optional `trace_id` / `conversation_service`. [VERIFIED: src/api/services/agent_run_memory.py:53-65]

Approval resume can reconstruct `input_state` from the persisted run and requester using the same shape as normal stream tests: `user_query`, `thread_id`, `tenant_id`, `user_id`, `role`, and `current_run_id`. [VERIFIED: tests/test_agent_runs_api.py:846-854] The requester should be fetched by `run.user_id`, not by the reviewer actor, because `_memory_state(...)` overwrites state identity with `run.tenant_id`, `user.id`, `run.thread_id`, `run.id`, and `user.role`. [VERIFIED: src/api/services/agent_run_memory.py:255-276]

The normal finalizer memory state merges `input_state` and `final_state`, then sets `final_response` and canonical identity fields. [VERIFIED: src/api/services/agent_run_memory.py:255-276] If approval resume passes a `final_state` containing `approval_result` or `risk_assessment.approval_required=True`, current `memory_write(...)` returns skipped `not_completed_path`. [VERIFIED: src/agent/nodes/memory_write.py:42-50] [VERIFIED: src/agent/nodes/memory_write.py:354-360]

The plan must therefore include one targeted fix for terminal completed approval finalization: either add an explicit terminal-finalizer flag accepted by `_approval_or_interrupted(...)`, or sanitize only the memory-write state while preserving the original `final_state` for CWC projection. [VERIFIED: src/api/services/agent_run_memory.py:151-178] [VERIFIED: src/memory/case_working_context_lifecycle.py:277-284] The plan should prefer a narrow terminal-finalizer flag or scoped sanitizer over globally weakening `_approval_or_interrupted(...)`, because pending/interrupted approval states must continue to skip memory write. [VERIFIED: src/agent/nodes/memory_write.py:354-360] [VERIFIED: tests/test_agent_runs_api.py:2931-3010]

Assistant message idempotency is already implemented by `ConversationService.append_or_get_assistant_message_for_run(...)`, which checks an existing message for the same tenant/user/thread/run/role and reloads on `IntegrityError`. [VERIFIED: src/conversation/service.py:119-139] [VERIFIED: src/conversation/service.py:381-439] The database has a unique active tenant/run/role index for user and assistant messages. [VERIFIED: src/db/models.py:1305-1354]

Thread summary idempotency is already implemented by `ThreadRollingSummaryService.persist_thread_summary(...)`, which returns an existing run-end summary when no new messages exist and reloads an existing source-end summary on `IntegrityError`. [VERIFIED: src/memory/thread_summary.py:118-188] The database has a unique active thread rolling summary index by tenant, conversation thread, summary type, and source-end message. [VERIFIED: src/db/models.py:1448-1493]

CWC thread-case linking is deduped before linking, and terminal writeback reports blocked/conflict/skipped/error statuses rather than treating all non-writes as hard failures. [VERIFIED: src/memory/case_working_context_lifecycle.py:345-388] [VERIFIED: src/api/services/agent_run_memory.py:292-296] CWC terminal source refs use `source_type="run_auto_terminal"` and bind both `run_id` and `agent_run_id` to the run. [VERIFIED: src/memory/case_working_context_lifecycle.py:506-513]

Finalizer trace persistence is not intrinsically idempotent because `append_agent_steps(...)` inserts new `AgentStep` rows from `trace_steps[start_index:]` and `AgentStep` has no unique run/index/node constraint in the model. [VERIFIED: src/agent/trace.py:176-217] [VERIFIED: src/db/models.py:1178-1209] Phase 59 should add a duplicate guard before appending `agent_run_memory_finalize`, or move trace persistence to a shared helper that checks whether the run already has a finalizer step. [VERIFIED: src/api/routers/agent_runs.py:1068-1087]

The finalizer commits assistant-message and thread-summary rows before isolated memory/CWC side effects begin. [VERIFIED: src/api/services/agent_run_memory.py:90-97] Because isolated memory side effects commit in child sessions, retry tests should assert that a recoverable approval-resume retry does not duplicate terminal surfaces after a failure around finalizer/completed-event boundaries. [VERIFIED: src/memory/write_isolation.py:11-24] [VERIFIED: tests/test_approval_api.py:495-573]

## Test Surface and Verification Commands

Existing focused approval tests to preserve include trusted resume config, commit-before-resume, terminal retry, edit re-interrupt retry, route compatibility, and basic completed status. [VERIFIED: tests/test_approval_api.py:383-453] [VERIFIED: tests/test_approval_api.py:456-573] [VERIFIED: tests/test_approval_api.py:906-1113] [VERIFIED: tests/test_approval_api.py:1233-1249] [VERIFIED: tests/test_approval_api.py:1505-1526]

Existing finalizer tests to preserve include assistant message persistence, thread summary idempotency, skipped non-completed paths, CWC writeback, CWC blocked/conflict/failure preservation, isolated memory rollback, and duplicate SSE protection. [VERIFIED: tests/test_agent_runs_api.py:1485-1558] [VERIFIED: tests/test_agent_runs_api.py:2548-2878] [VERIFIED: tests/test_agent_runs_api.py:2881-3117]

Add a focused approval API regression test for approved completion that uses an approval-resume graph final state with `final_response`, post-approval `trace_steps`, approval markers, and CWC-eligible state such as `active_slots.refund_case_id`. [VERIFIED: tests/test_approval_api.py:32-46] [VERIFIED: tests/test_agent_runs_api.py:857-873] The test should assert one assistant message with source `agent_runs.finalizer`, one thread rolling summary, one `agent_run_memory_finalize` step, terminal memory status not accidentally skipped due to approval markers, and finalizer metrics containing CWC status. [VERIFIED: src/api/services/agent_run_memory.py:79-138] [VERIFIED: tests/test_agent_runs_api.py:1485-1518] [VERIFIED: tests/test_agent_runs_api.py:2608-2655]

Add a focused interrupted-again approval resume regression test using the existing re-interrupt graph pattern; assert the run is `interrupted`, replacement approval exists where applicable, and no assistant message, summary, memory write, or finalizer step is written. [VERIFIED: src/api/routers/approvals.py:351-407] [VERIFIED: tests/test_approval_api.py:906-1113] [VERIFIED: tests/test_agent_runs_api.py:2957-3010]

Add a retry/idempotency regression test that simulates a resume lifecycle failure after some terminal finalizer surfaces have been created, then retries the same approval decision and asserts assistant message count, summary count, finalizer-step count, approval completed event count, graph call count, and action draft count are idempotency-compatible. [VERIFIED: tests/test_approval_api.py:495-573] [VERIFIED: tests/test_approval_integration.py:184-220] [VERIFIED: src/api/routers/approvals.py:445-495]

Use only approved MOCA test entrypoints. [VERIFIED: AGENTS.md:24-29] Suggested commands:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_agent_run_status_updates_to_completed_after_service_resume -q
```

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_decide_records_recoverable_resume_failure_and_retries_terminal_approval tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt tests/test_approval_api.py::test_phase58_retry_route_compatibility_is_historical_persisted_data_read_only -q
```

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_skips_non_completed_status tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces -q
```

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py -q
```

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py tests/test_agent_runs_api.py::test_agent_run_sse_node_messages_cover_exact_canonical_graph_nodes tests/test_agent_runs_api.py::test_frontend_timeline_label_map_covers_exact_canonical_graph_nodes -q
```

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_agent_runs_api.py tests/test_approval_integration.py -q
```

## Risks / Non-goals

- Do not pass the reviewer/admin `actor_user` into the terminal finalizer; reviewer identity belongs to trusted resume and action permission, while terminal memory/CWC writeback must bind to the original run requester. [VERIFIED: src/api/routers/approvals.py:729-749] [VERIFIED: src/api/services/agent_run_memory.py:199-217]
- Do not globally allow `memory_write(...)` for all approval-marked states; only completed terminal finalizer state should bypass the pending/interrupted approval skip. [VERIFIED: src/agent/nodes/memory_write.py:354-360] [VERIFIED: tests/test_agent_runs_api.py:2931-3010]
- Do not finalize `_handle_resume_interrupt(...)`, graph exceptions, missing final responses, or `final_status="error"` as completed memory writes. [VERIFIED: src/api/routers/approvals.py:351-407] [VERIFIED: src/api/services/agent_run_memory.py:66-77]
- Do not rely on `append_agent_steps(...)` alone for retry idempotency; it appends rows and does not check existing finalizer steps. [VERIFIED: src/agent/trace.py:176-217] [VERIFIED: src/db/models.py:1178-1209]
- Do not alter `ApprovalService.decide(...)` terminal decision semantics, optimistic version checks, or retry reconstruction unless a test proves the change is required for finalization. [VERIFIED: src/api/routers/approvals.py:445-475] [VERIFIED: tests/test_approval_api.py:495-573]
- Do not change action-draft reconciliation behavior or widen side-effecting action execution; approval resume currently reconciles missing drafts and records errors when draft outcome is unsafe or missing. [VERIFIED: src/api/routers/approvals.py:638-693] [VERIFIED: tests/test_approval_api.py:577-680]
- Do not revive active `assess_risk_and_approval` route/node names or compatibility aliases; only historical persisted retry metadata maps that legacy route to canonical `risk_gate`. [VERIFIED: src/api/routers/approvals.py:779-785] [VERIFIED: tests/test_approval_api.py:1233-1249] [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:102-114]
- Do not make session memory or CWC authoritative for business facts, policy evidence, approval/action authority, or replay truth. [VERIFIED: .planning/REQUIREMENTS.md:36-38]
- If implementation discovers validation failures or architecture debt while touching memory/approval lifecycle code, update `.planning/LOCAL-VALIDATION-ISSUES.md` and/or `.planning/ARCHITECTURE-DEBT.md` as required. [VERIFIED: CLAUDE.md:5-15] [VERIFIED: AGENTS.md:12-22]

## Validation Architecture

| Property | Value |
|----------|-------|
| Validation enabled | Nyquist validation is enabled because `.planning/config.json` sets `workflow.nyquist_validation` to `true`. [VERIFIED: .planning/config.json:15-31] |
| Test framework | `pytest>=8.0` with `pytest-asyncio>=0.23`; `asyncio_mode = "auto"`. [VERIFIED: pyproject.toml:34-55] |
| Runtime/package entry | `uv` is available as `uv 0.11.2`; local `python3` reports `Python 3.13.3`; project requires Python `>=3.12`. [VERIFIED: `uv --version`] [VERIFIED: `python3 --version`] [VERIFIED: pyproject.toml:1-6] |
| Required command prefix | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`. [VERIFIED: AGENTS.md:24-29] |
| Quick approval run | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py -q`. [VERIFIED: tests/test_approval_api.py] |
| Cross-boundary run | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_agent_runs_api.py tests/agent/test_memory_write_node.py tests/agent/test_case_working_context_lifecycle.py tests/memory/test_thread_summary.py -q`. [VERIFIED: tests/test_approval_api.py] [VERIFIED: tests/test_agent_runs_api.py] |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Existing Coverage | Phase 59 Gap |
|--------|----------|-----------|-------------------|--------------|
| MEM-01 | Approval-resume completed runs write or report terminal CWC status through finalizer trace. [VERIFIED: .planning/REQUIREMENTS.md:36] | integration/unit | Normal finalizer CWC tests exist. [VERIFIED: tests/test_agent_runs_api.py:2608-2819] | Add approval-resume completed CWC/finalizer assertion. [VERIFIED: .planning/ROADMAP.md:523-529] |
| MEM-02 | Approval-resume terminal CWC writeback uses thread-case linkage and dedupe. [VERIFIED: .planning/REQUIREMENTS.md:37] | integration | CWC lifecycle link/dedupe logic exists. [VERIFIED: src/memory/case_working_context_lifecycle.py:345-388] | Add approval-resume coverage with CWC-eligible final state. [VERIFIED: tests/test_agent_runs_api.py:857-873] |
| MEM-03 | Approval-resume terminal memory writes under requester/run/thread identity without authority drift. [VERIFIED: .planning/REQUIREMENTS.md:38] | unit/integration | Normal memory finalizer identity tests exist through fake memory write hooks. [VERIFIED: tests/test_agent_runs_api.py:2448-2524] | Add approval-resume memory write spy asserting requester identity and approval-marker handling. [VERIFIED: src/api/services/agent_run_memory.py:255-276] |
| CAGM-08 | Trusted resume semantics and risk/approval/action separation remain unchanged. [VERIFIED: .planning/REQUIREMENTS.md:60] | integration/architecture | Approval trusted config and action draft reconciliation tests exist. [VERIFIED: tests/test_approval_api.py:383-453] [VERIFIED: tests/test_approval_api.py:577-680] | Keep these tests in the Phase 59 verification set. [VERIFIED: .planning/ROADMAP.md:523-529] |
| CAGM-09 | Final canonical graph vocabulary remains exact. [VERIFIED: .planning/REQUIREMENTS.md:61] | architecture | Canonical graph baseline tests exist. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:68-114] | Include architecture tests after touching approval/graph resume code. [VERIFIED: .planning/ROADMAP.md:528] |

### Wave 0 Gaps

- Add approval-resume terminal finalizer tests in `tests/test_approval_api.py` for completed, interrupted-again, and retry/dedupe paths. [VERIFIED: tests/test_approval_api.py:1505-1526] [VERIFIED: tests/test_approval_api.py:495-573]
- Add or update `tests/agent/test_memory_write_node.py` if implementation changes `_approval_or_interrupted(...)` to support an explicit terminal-finalizer mode. [VERIFIED: tests/agent/test_memory_write_node.py:44-90] [VERIFIED: src/agent/nodes/memory_write.py:354-360]
- No new test framework is needed. [VERIFIED: pyproject.toml:34-55]

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | Yes | Existing approval endpoints use authenticated actor headers in tests; Phase 59 should not change auth entrypoints. [VERIFIED: tests/test_approval_api.py:414-418] |
| V3 Session Management | No direct session change | Phase 59 changes backend persistence after approval decision and does not introduce browser/session-cookie behavior. [VERIFIED: src/api/routers/approvals.py:67-150] |
| V4 Access Control | Yes | Preserve reviewer/admin trusted resume identity and action permission separation from requester memory finalization identity. [VERIFIED: src/api/routers/approvals.py:729-749] |
| V5 Input Validation | Yes | Preserve approval decision version/hash checks and retry conflict checks. [VERIFIED: src/api/routers/approvals.py:445-475] |
| V6 Cryptography | No new crypto | Phase 59 should reuse existing action payload/safety snapshot hash validation and add no cryptographic primitive. [VERIFIED: src/api/routers/approvals.py:467-475] |

## Planning Recommendations

Split Phase 59 into three small plans because the work crosses a shared finalizer behavior, an approval router integration point, and regression/verification gates. [VERIFIED: AGENTS.md:55-60] [VERIFIED: src/api/routers/approvals.py:283-349] [VERIFIED: src/api/services/agent_run_memory.py:151-178]

1. Plan 59-01 should harden/shared-factor terminal finalizer utilities: requester input-state reconstruction, terminal-finalizer memory-write eligibility, and deduped finalizer trace persistence. [VERIFIED: src/api/services/agent_run_memory.py:53-138] [VERIFIED: src/agent/nodes/memory_write.py:354-360] [VERIFIED: src/agent/trace.py:176-217]
2. Plan 59-02 should wire approval-resume completed paths through the shared finalizer after run status/trace persistence and explicitly skip interrupted/error paths with a reason. [VERIFIED: src/api/routers/approvals.py:239-349] [VERIFIED: src/api/routers/approvals.py:351-407] [VERIFIED: src/api/services/agent_run_memory.py:66-77]
3. Plan 59-03 should add focused regression tests and run the approval, finalizer, memory, CWC, retry, and canonical graph verification commands through `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`. [VERIFIED: AGENTS.md:24-29] [VERIFIED: tests/test_approval_api.py:495-573] [VERIFIED: tests/test_agent_runs_api.py:2608-2878] [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:68-114]

The implementation should prefer moving the finalizer trace persistence helper into `src/api/services/agent_run_memory.py` or another shared service rather than importing private `_persist_finalizer_trace_steps(...)` from `agent_runs.py`. [VERIFIED: src/api/routers/agent_runs.py:1068-1087] The shared helper should check existing `AgentStep` rows for `node_name == "agent_run_memory_finalize"` before appending, because `AgentStep` has no model-level unique constraint for this purpose. [VERIFIED: src/db/models.py:1178-1209] [VERIFIED: src/agent/trace.py:176-217]

The plan should keep `approval_resumed` event semantics intact while adding terminal-finalization metadata only if needed for explicit skip/diagnostic reasons. [VERIFIED: src/api/routers/approvals.py:409-442] Failed/interrupted paths should be testable without relying on finalizer trace rows because the finalizer returns no trace rows for skipped non-completed paths. [VERIFIED: src/api/services/agent_run_memory.py:66-77]

The plan should include one explicit test proving approval-resume completed memory write is not skipped by approval markers, because this is the gap that can survive a naive finalizer call. [VERIFIED: src/agent/nodes/memory_write.py:354-360] [VERIFIED: src/api/routers/approvals.py:638-693]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| None | All implementation-relevant claims above were verified from current code, tests, planning artifacts, or local command output. [VERIFIED: code/tests/planning artifacts/local commands] | All sections | None recorded. |

## Sources

### Primary

- `.planning/ROADMAP.md` Phase 59 goal and success criteria. [VERIFIED: .planning/ROADMAP.md:516-529]
- `.planning/REQUIREMENTS.md` MEM-01, MEM-02, MEM-03, CAGM-08, CAGM-09. [VERIFIED: .planning/REQUIREMENTS.md:36-38] [VERIFIED: .planning/REQUIREMENTS.md:60-61]
- `.planning/v2.1-MILESTONE-AUDIT.md` approval-resume finalizer gap and recommended closure. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:64] [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:160-170] [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:218]
- `src/api/routers/approvals.py` approval decision, resume lifecycle, retry, action-draft reconciliation, trusted resume config, and canonical route mapping. [VERIFIED: src/api/routers/approvals.py:67-150] [VERIFIED: src/api/routers/approvals.py:239-349] [VERIFIED: src/api/routers/approvals.py:351-407] [VERIFIED: src/api/routers/approvals.py:445-495] [VERIFIED: src/api/routers/approvals.py:638-749] [VERIFIED: src/api/routers/approvals.py:779-785]
- `src/api/routers/agent_runs.py` normal terminal finalizer lifecycle and trace persistence helper. [VERIFIED: src/api/routers/agent_runs.py:383-410] [VERIFIED: src/api/routers/agent_runs.py:547-574] [VERIFIED: src/api/routers/agent_runs.py:1037-1087]
- `src/api/services/agent_run_memory.py` finalizer inputs, skip behavior, assistant/summary persistence, memory/CWC side effects, and trace metrics. [VERIFIED: src/api/services/agent_run_memory.py:53-138] [VERIFIED: src/api/services/agent_run_memory.py:151-240] [VERIFIED: src/api/services/agent_run_memory.py:255-334]
- `src/agent/nodes/memory_write.py` approval/interrupted skip behavior. [VERIFIED: src/agent/nodes/memory_write.py:42-50] [VERIFIED: src/agent/nodes/memory_write.py:354-360]

### Test Evidence

- Approval route tests. [VERIFIED: tests/test_approval_api.py:383-573] [VERIFIED: tests/test_approval_api.py:906-1113] [VERIFIED: tests/test_approval_api.py:1233-1249] [VERIFIED: tests/test_approval_api.py:1505-1526]
- Normal finalizer and memory/CWC tests. [VERIFIED: tests/test_agent_runs_api.py:1485-1558] [VERIFIED: tests/test_agent_runs_api.py:2548-3117]
- Approval integration tests. [VERIFIED: tests/test_approval_integration.py:20-121] [VERIFIED: tests/test_approval_integration.py:184-220]
- Canonical graph architecture tests. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:45-114]

### Environment

- `uv --version`, `python3 --version`, `pyproject.toml`, `.planning/config.json`, `AGENTS.md`, and `CLAUDE.md` were checked for test-entry and workflow constraints. [VERIFIED: pyproject.toml:1-55] [VERIFIED: .planning/config.json:15-31] [VERIFIED: AGENTS.md:24-29] [VERIFIED: CLAUDE.md:5-15]
