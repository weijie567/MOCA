---
phase: 59-approval-resume-terminal-memory-finalization
verified: 2026-07-08T10:27:13Z
status: passed
score: 18/18 must-haves verified
overrides_applied: 0
---

# Phase 59: Approval Resume Terminal Memory Finalization Verification Report

**Phase Goal:** Wire approval-resume completed runs through the same terminal assistant-message/thread-summary/memory/CWC finalizer as ordinary agent-run completion while preserving interrupted/error skip boundaries, requester-vs-reviewer identity separation, retry idempotency, and canonical approval/graph semantics.
**Verified:** 2026-07-08T10:27:13Z
**Status:** passed
**Re-verification:** No - initial verification. No prior `59-VERIFICATION.md` existed.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Approval-resume completed runs call shared terminal finalization with idempotency-compatible behavior. | VERIFIED | `approvals.py:377-402` calls `finalize_completed_agent_run_memory(...)` and `persist_agent_run_memory_finalize_trace_steps(..., suppress_errors=False)` after completed status/trace handling; `agent_run_memory.py:66-101` dedupes existing `agent_run_memory_finalize` rows. |
| 2 | Approval-resume completed path persists/reuses assistant message, thread summary, terminal memory write, and finalizer trace with CWC status. | VERIFIED | `agent_run_memory.py:132-147` writes assistant/summary, `148-168` runs memory/CWC, `169-188` returns trace metrics; `tests/test_approval_api.py:1900-1937` asserts one assistant message, summary, `MemoryWriteEvent`, finalizer step, completed memory status, and CWC status metric. |
| 3 | Interrupted-again and failed approval-resume paths explicitly skip terminal finalization. | VERIFIED | `approvals.py:307-326` and `405-460` route interrupts to `approval_resume_interrupted`; `348-356` marks errors as `approval_resume_error`; no finalizer call exists inside `_handle_resume_interrupt(...)`. Tests at `tests/test_approval_api.py:1192-1263` and `1267-1312` assert zero terminal surfaces. |
| 4 | Regression tests use MOCA-approved test entrypoints only. | VERIFIED | `59-VALIDATION.md` final and review-fix evidence uses `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` and ruff. Verifier spot check reran the same approved entrypoint: 6 passed, 1 warning in 8.72s. |
| 5 | Trusted graph resume keeps reviewer/admin identity, terminal finalizer uses original requester identity. | VERIFIED | `_resume_graph_config(...)` builds trusted graph config with `actor_user` at `approvals.py:849-869`; completed finalizer fetches `requester = session.get(User, run.user_id)` and passes `user=requester` at `380-387`. Test asserts message thread requester ownership at `tests/test_approval_api.py:1900-1905`. |
| 6 | Approval trusted-resume semantics, action-draft reconciliation, and canonical graph vocabulary remain unchanged. | VERIFIED | `_reconcile_approved_action_draft(...)` still gates accept/approve and existing draft by run/approval at `approvals.py:758-813`; canonical retry mapping remains bounded at `899-905`; architecture tests assert final 15-node set and no active legacy risk aliases at `tests/architecture/test_canonical_graph_baseline.py:68-105`, `143-182`, `249-270`. |
| 7 | Completed approval-resume memory write can avoid approval-marker `not_completed_path` only through terminal sanitizer. | VERIFIED | `_terminal_memory_write_state(...)` strips only top-level approval markers and `risk_assessment.approval_required` at `agent_run_memory.py:331-340`; `_run_terminal_memory_write(...)` applies it immediately before `memory_write(...)` at `214-228`; direct `memory_write(...)` predicate remains unchanged at `memory_write.py:354-360`. |
| 8 | Finalizer trace persistence is retry-idempotent and does not duplicate finalizer rows. | VERIFIED | `persist_agent_run_memory_finalize_trace_steps(...)` checks existing `AgentStep` with `FINALIZER_NODE` before append at `agent_run_memory.py:77-88`; test `tests/test_agent_runs_api.py:1014-1057` calls helper twice and asserts one row. |
| 9 | Ordinary `agent-runs` completion keeps the same finalizer lifecycle. | VERIFIED | Both normal SSE completion paths call `finalize_completed_agent_run_memory(...)` then shared trace persistence at `agent_runs.py:396-413` and `560-577`; normal finalizer tests remain in `tests/test_agent_runs_api.py:1728-1760`, `2850-2897`, and duplicate stream regression `3255-3335`. |
| 10 | Approval-resume completed finalizer runs after status and post-approval graph trace rows are persisted. | VERIFIED | `_resume_graph_after_decision(...)` updates `AgentRun` at `approvals.py:358-362`, appends post-approval steps at `364-375`, then enters completed-only finalizer at `377-402`. |
| 11 | Completed-run retry after post-finalizer event failure records missing completion without graph/action side effects. | VERIFIED | `_run_resume_lifecycle(...)` first attempts completed reconciliation at `249-255`, records attempt, resumes graph, then records completion through `_record_resume_completed_event_once(...)` at `273-279`; retry readiness requires finalizer evidence at `573-595`. Test `tests/test_approval_api.py:557-715` asserts one graph call, one finalizer step, one action draft, and one completed event after retry. |
| 12 | Review fix WR-01 is closed: finalizer trace persistence failure fails closed after terminal surfaces. | VERIFIED | `agent_run_memory.py:72-101` adds `suppress_errors`; approval resume passes `False` and commits surfaces before trace persistence at `approvals.py:395-402`. Test `tests/test_approval_api.py:720-820` asserts HTTP 500, no completed event, no finalizer trace, but assistant/summary/memory/CWC surfaces remain durable. |
| 13 | Review fix WR-02 is closed: completed-run retry reconciliation rechecks under lock. | VERIFIED | `_lock_approval_request_for_resume(...)` uses `select(...).with_for_update()` at `approvals.py:536-542`; `_record_resume_completed_event_once(...)` locks, rechecks latest status, and skips duplicate completed event at `545-570`. Test `tests/test_approval_api.py:824-859` asserts lock and latest-status recheck prevent duplicate event recording. |
| 14 | Approval resume error paths never create terminal finalizer rows. | VERIFIED | Error status is selected when node errors or missing final response exist at `approvals.py:335-356`; completed finalizer branch is guarded by `final_status == "completed" and final_response_text` at `377`; test `tests/test_approval_api.py:1267-1312` monkeypatches finalizer to fail if called and asserts zero surfaces. |
| 15 | Regression tests prove completed approval-resume surfaces with approval markers. | VERIFIED | `tests/test_approval_api.py:1856-1937` injects `approval_result`, `approval_required`, and `risk_assessment.approval_required`, then verifies memory write is `completed` and reason is not `not_completed_path`. |
| 16 | Regression tests prove interrupted-again path writes no terminal assistant/summary/memory/finalizer surface. | VERIFIED | `tests/test_approval_api.py:1192-1263` asserts interrupted run final status and zero assistant messages, summaries, `MemoryWriteEvent`, and finalizer steps. |
| 17 | Direct `memory_write(...)` approval-marker skip boundary remains protected. | VERIFIED | `memory_write.py:42-48` still skips when `_approval_or_interrupted(...)` is true; `tests/agent/test_memory_write_node.py:57-73` covers `approval_result`, `approval_required`, and `risk_assessment.approval_required` as `not_completed_path`. |
| 18 | Required architecture-debt/local-validation ledger entries exist. | VERIFIED | `.planning/ARCHITECTURE-DEBT.md:379-411` records Phase 59 Plans 01-03 and WR fixes in Chinese with status/evidence/risk; `.planning/LOCAL-VALIDATION-ISSUES.md:19025-19207` records Phase 59 local validation incidents and approved rerun commands. |

**Score:** 18/18 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/api/services/agent_run_memory.py` | Shared terminal finalizer utilities, requester input-state builder, sanitizer, trace dedupe helper. | VERIFIED | Exists and substantive. Key functions at `55-101`, completed finalizer at `104-188`, sanitizer at `331-340`; wired from `agent_runs.py` and `approvals.py`. |
| `src/api/routers/agent_runs.py` | Normal completion call sites migrated to shared helper. | VERIFIED | Both graph update/event completion paths call finalizer and shared trace helper at `396-413` and `560-577`; no private `_persist_finalizer_trace_steps` remains. |
| `src/api/routers/approvals.py` | Approval-resume completed finalizer integration and non-completed skip boundary. | VERIFIED | Imports shared helpers at `21-23`; completed branch at `377-402`; interrupt/error boundaries at `348-356` and `405-460`; retry lock/evidence at `536-595`. |
| `tests/test_approval_api.py` | Approval completed/interrupted/retry terminal finalizer regressions. | VERIFIED | Completed DB surface test `1856-1937`; retry/dedupe `557-715`; trace failure fail-closed `720-820`; lock recheck `824-859`; interrupted/error skips `1192-1312`. |
| `tests/test_agent_runs_api.py` | Normal finalizer, sanitizer, trace idempotency coverage. | VERIFIED | Requester helper/sanitizer `895-980`; trace idempotency/fail-closed `1014-1132`; normal finalizer and duplicate SSE tests `1728-1760`, `2850-2897`, `3255-3335`. |
| `tests/agent/test_memory_write_node.py` | Direct approval-marked states still skip. | VERIFIED | Parametrized approval marker skip test at `57-73`; no terminal bypass flag found in memory node/test scan. |
| `.planning/phases/59-approval-resume-terminal-memory-finalization/59-VALIDATION.md` | Complete validation sign-off and approved command evidence. | VERIFIED | Frontmatter `status: complete`, `nyquist_compliant: true`, `wave_0_complete: true`; final/review-fix evidence contains only approved `uv run` commands. |
| `.planning/ARCHITECTURE-DEBT.md` / `.planning/LOCAL-VALIDATION-ISSUES.md` | Required project ledgers. | VERIFIED | Phase 59 memory ledger and local validation incidents are present; historical bare `pytest` mentions in local issue log are incident text, not Phase 59 validation evidence. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `agent_run_memory.py` | `memory_write.py` | `_run_terminal_memory_write(...)` applies sanitized completed-terminal state before `memory_write(...)`. | VERIFIED | `agent_run_memory.py:214-228`, `331-340`; direct node predicate unchanged at `memory_write.py:354-360`. |
| `agent_run_memory.py` | `CaseWorkingContextLifecycleAdapter` | Unsanitized `final_state` passed to `write_after_terminal_success(...)`. | VERIFIED | `agent_run_memory.py:251-269` passes `final_state=final_state`. |
| `agent_runs.py` | `agent_run_memory.py` | Normal completion calls finalizer and shared trace persistence. | VERIFIED | `agent_runs.py:396-413`, `560-577`. |
| `approvals.py` | `agent_run_memory.py` | Completed approval resume calls finalizer and finalizer trace persistence. | VERIFIED | `approvals.py:377-402`. |
| `approvals.py` | `action_draft.py` | `_reconcile_approved_action_draft(...)` remains before finalizer and keeps approved-only guard. | VERIFIED | Called before status/finalizer at `approvals.py:327-332`; guard and existing draft check at `758-776`. |
| `approvals.py` | `ApprovalEvent` | Completed-run reconciliation records missing `approval_resumed/completed` only after evidence. | VERIFIED | `_record_resume_completed_event_once(...)` at `545-570`, evidence gate at `573-595`. |
| `tests/test_approval_api.py` | production approval/memory path | API client + fake resume graph + DB assertions. | VERIFIED | Tests exercise `/api/v1/approvals/{id}/decide` and assert DB surfaces, not just mocks. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `src/api/routers/approvals.py` | `final_state`, `final_response_text`, `trace_steps` | `graph.ainvoke(Command(resume=...))`, then status update and post-approval `append_agent_steps`. | Yes | FLOWING - completed state is routed to finalizer only after durable status/trace handling. |
| `src/api/routers/approvals.py` | requester identity | Persisted `AgentRun.user_id` fetched via `session.get(User, run.user_id)`. | Yes | FLOWING - terminal finalizer uses requester; graph resume uses reviewer/admin `actor_user`. |
| `src/api/services/agent_run_memory.py` | assistant message / summary / memory / CWC result | `ConversationService`, `ThreadRollingSummaryService`, isolated `memory_write(...)`, and `CaseWorkingContextLifecycleAdapter`. | Yes | FLOWING - trace metrics are built from real finalizer results. |
| `src/api/services/agent_run_memory.py` | finalizer trace rows | Existing `AgentStep` query plus `append_agent_steps(...)`. | Yes | FLOWING - duplicate guard prevents retry duplicates; optional fail-closed mode re-raises. |
| `tests/test_approval_api.py` | regression observations | DB queries against `ConversationMessage`, `ConversationSummary`, `MemoryWriteEvent`, `AgentStep`, `ActionDraft`, `ApprovalEvent`. | Yes | FLOWING - assertions inspect persisted rows and side-effect counts. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Completed approval resume finalizes memory, WR-01 fails closed, WR-02 lock recheck, direct approval markers still skip. | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_approval_resume_completed_runs_terminal_memory_finalizer tests/test_approval_api.py::test_approval_resume_trace_persistence_failure_fails_closed_after_terminal_surfaces tests/test_approval_api.py::test_completed_resume_reconciliation_rechecks_status_under_lock tests/agent/test_memory_write_node.py::test_memory_write_node_skips_approval_marked_states -q` | `6 passed, 1 warning in 8.72s` | PASS |
| Phase 59 modified production/tests lint clean. | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/services/agent_run_memory.py src/api/routers/agent_runs.py src/api/routers/approvals.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/agent/test_memory_write_node.py` | `All checks passed!` | PASS |
| Final validation suite evidence from phase artifact. | Commands in `59-VALIDATION.md` final/review-fix evidence. | Final selected suite after review fixes: `196 passed, 1 warning`; ruff passed. | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| MEM-01 | 59-01/02/03 | CWC terminal finalizer/writeback remains durable and contextual-only. | SATISFIED | CWC receives unsanitized final state at `agent_run_memory.py:261-268`; metrics asserted in approval resume test `tests/test_approval_api.py:1933-1937`; architecture ledger records closure. |
| MEM-02 | 59-01/02/03 | Thread-case/CWC linkage and terminal finalizer trace persistence stay correct. | SATISFIED | Thread summary and CWC finalizer trace are produced through shared finalizer; finalizer trace duplicate guard at `agent_run_memory.py:77-88`; tests assert summary and finalizer row counts. |
| MEM-03 | 59-01/02/03 | Session memory remains requester/thread scoped and approval markers do not globally bypass pending skip. | SATISFIED | `build_agent_run_finalizer_input_state(...)` uses requester/run identity; tests assert `ConversationThread.user_id == AgentRun.user_id` and direct approval-marked `memory_write(...)` skips. |
| CAGM-08 | 59-02/03 | `risk_gate` / trusted approval-resume separation remains intact. | SATISFIED | Graph resume trusted context uses reviewer/admin actor; terminal memory uses requester; action-draft permission remains accept/approve-only. |
| CAGM-09 | 59-02/03 | Final canonical graph names and no active legacy aliases remain preserved. | SATISFIED | `tests/architecture/test_canonical_graph_baseline.py` asserts exact 15-node set, no `assess_risk_and_approval` active node/route, and router values within canonical set. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `src/api/routers/agent_runs.py` | 707, 1314, 1375 | `return {}` | Info | Legitimate empty mapping fallback in parser helpers, not a user-visible stub and not Phase 59 incomplete behavior. |
| `.planning/LOCAL-VALIDATION-ISSUES.md` | historical rows | bare `pytest` text | Info | Historical incident log text, including records that bare pytest is invalid in MOCA. Phase 59 validation/summary/review-fix evidence uses approved `UV_CACHE_DIR=/tmp/uv-cache uv run ...` commands. |

### Human Verification Required

None. Phase 59 behavior is backend/API/memory lifecycle behavior with automated DB-backed regressions and code-level wiring evidence; no visual, external-service, or manual UX-only behavior is required for this phase goal.

### Gaps Summary

No gaps found. The milestone-audit integration gap recorded in `.planning/v2.1-MILESTONE-AUDIT.md` is closed for Phase 59: approval-resume completed runs now use the terminal finalizer lifecycle, non-completed paths remain explicit skips, requester/reviewer identity boundaries are preserved, retry reconciliation is idempotent and fail-closed, and canonical approval/graph semantics remain guarded by regression tests.

---

_Verified: 2026-07-08T10:27:13Z_
_Verifier: Codex (gsd-verifier)_
