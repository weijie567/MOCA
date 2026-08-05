---
phase: 45-memory-lifecycle-wiring-for-case-working-context
verified: 2026-07-03T06:11:12Z
status: passed
score: "15/15 must-haves verified"
overrides_applied: 0
---

# Phase 45: Memory Lifecycle Wiring for Case Working Context Verification Report

**Phase Goal:** Wire the Phase 44 Case Working Context foundation into the real agent-run lifecycle through a stable lifecycle adapter: resolve canonical `refund_cases.id`, link the current thread with `link_source="run_auto"`, load active CWC as contextual-only memory input before investigation/recommendation, and write deterministic CWC updates after successful completed terminal runs without making memory authority for policy/risk/approval/action/replay.
**Verified:** 2026-07-03T06:11:12Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

Phase 45 achieved the goal. The current codebase has a substantive `CaseWorkingContextLifecycleAdapter`, active CWC read/link wiring at `reviewed_memory_context_retrieve`, terminal completed-run writeback through the audited CWC service, contextual-only state/bundle exposure, contract/red-line tests, and final validation evidence.

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | CWC lifecycle status and refs are contextual-only and cannot be confused with evidence, policy, approval, action, or replay authority. | VERIFIED | `CaseWorkingContextRef` and `CaseWorkingContextLifecycleStatusV1` set `authority_class="contextual_only"` in `src/memory/context_refs.py:40` and `src/memory/context_refs.py:88`; tests forbid authority DTO imports at `tests/memory/test_context_refs.py:314`. |
| 2 | Lifecycle adapter inputs resolve canonical `refund_cases.id` through the Phase 44 resolver and fail closed without a trusted case ref. | VERIFIED | Adapter defaults to `resolve_case_id` at `src/memory/case_working_context_lifecycle.py:65`; skip paths for no/unresolved case are at lines 106-130 and 200-226; tests cover candidate/session/case-memory rejection. |
| 3 | Lifecycle adapter outputs expose explicit skip/error/status reasons for read/link/write callers. | VERIFIED | `CaseWorkingContextLifecycleStatusV1` carries resolve/link/read/write/reason fields at `src/memory/context_refs.py:88`; helper constructors are at `src/memory/case_working_context_lifecycle.py:811`. |
| 4 | When a trusted canonical case ref is resolved, the current thread is linked to `refund_cases.id` with `link_source=run_auto` and `linked_by_run_id=current_run_id`. | VERIFIED | Read seam link uses `ConversationRepository.link_case(... link_source="run_auto", linked_by_run_id=run_id)` at `src/memory/case_working_context_lifecycle.py:145`; terminal link uses the same at lines 371-378. |
| 5 | Active CWC is loaded before investigate/recommendation consumes memory context. | VERIFIED | `reviewed_memory_context_retrieve` calls `_load_case_working_context` before returning the memory context output at `src/agent/nodes/reviewed_memory_context_retrieve.py:83`; contract maps `memory_context_load` to CWC before `investigate` in `docs/contract-spec.md:642`. |
| 6 | No trusted case identity produces an explicit skipped status and does not query or backfill from `case_memories`. | VERIFIED | No-case and unresolved paths return skipped before read/link at `src/memory/case_working_context_lifecycle.py:106` and `:118`; red-line test rejects `CaseMemoryRepository`, `CaseMemoryService`, and `case_memories` in lifecycle/finalizer code at `tests/memory/test_phase45_contract_alignment.py:136`. |
| 7 | CWC context is exposed only through additive `AgentState` and `memory_context_bundle` fields. | VERIFIED | `AgentState` has `case_working_context` and `case_working_context_lifecycle_status` at `src/agent/state.py:124`; receive reset is at `src/agent/nodes/receive_request.py:116`; bundle merge is at `src/agent/nodes/reviewed_memory_context_retrieve.py:295`. |
| 8 | Successful completed terminal runs with final_response and resolved canonical case id write deterministic CWC updates. | VERIFIED | Finalizer gates non-completed/no-response at `src/api/services/agent_run_memory.py:67`, then calls `_run_terminal_case_working_context_write` after terminal commit and memory write at lines 96-115; integration test asserts CWC row and source refs at `tests/test_agent_runs_api.py:2396`. |
| 9 | Approval-pending, interrupted, cancelled, error, missing-final-response, unresolved-case, and clarification-only paths skip CWC content write with explicit reason code. | VERIFIED | Non-completed/missing response returns `not_completed_path` in `src/api/services/agent_run_memory.py:67`; terminal no/unresolved/clarification skips are in `src/memory/case_working_context_lifecycle.py:200`, `:213`, and `:450`; tests cover skip matrix. |
| 10 | CWC conflicts and PII blocks do not overwrite active CWC and do not roll back assistant message/thread summary/action/approval/user response artifacts. | VERIFIED | Writeback runs after assistant message/thread summary commit at `src/api/services/agent_run_memory.py:81-96`; PII/conflict preservation tests are at `tests/test_agent_runs_api.py:2490` and `:2533`. |
| 11 | CWC projection uses deterministic refs/summaries only and never introduces an LLM summarizer. | VERIFIED | Projection uses typed source refs and prompt-safe summaries at `src/memory/case_working_context_lifecycle.py:463-493` and `:539-593`; static test rejects LLM/summarizer dependencies at `tests/memory/test_phase45_contract_alignment.py:127`. |
| 12 | `docs/contract-spec.md` records Phase 45 CWC lifecycle fields, active read, `run_auto` link, and terminal finalizer writeback semantics. | VERIFIED | Contract has `case_working_context_lifecycle_status` in node/state tables at `docs/contract-spec.md:642` and `:898`; CWC lifecycle text is at `docs/contract-spec.md:1529-1533`. |
| 13 | Contract tests lock CWC contextual-only authority, no graph-global `active_slots` writer, no `case_memories` backfill, no LLM summarizer, and no destructive legacy table/column changes. | VERIFIED | `tests/memory/test_phase45_contract_alignment.py` includes red-line tests for LLM, case-memory backfill, `active_slots`, graph topology, legacy schema retention, and approved pytest entrypoints at lines 127-209. |
| 14 | Phase 45 validation strategy rows are satisfied by automated tests using only the MOCA-approved uv entrypoint. | VERIFIED | `45-VALIDATION.md` marks compliance true and records exact approved commands/results at lines 82-89. Quick re-run of `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py -x -q` passed: `11 passed, 1 warning`. |
| 15 | Memory architecture debt and redesign decision records distinguish implemented lifecycle wiring from remaining out-of-scope memory redesign ideas. | VERIFIED | `.planning/MEMORY-REDESIGN-DECISIONS.md:101` records Phase 45 closed defers; `:103` preserves remaining DEFER-1/2/3. `.planning/ARCHITECTURE-DEBT.md:362` records the Phase 45 memory ledger entry and final validation evidence. |

**Score:** 15/15 truths verified

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/memory/context_refs.py` | CWC contextual ref/status contracts and bundle fields | VERIFIED | Classes and additive bundle fields exist at lines 40, 88, and 150. |
| `src/memory/case_working_context_lifecycle.py` | Stable adapter boundary, read/link/write orchestration, terminal projection | VERIFIED | Adapter, `link_and_load_active`, `write_after_terminal_success`, deterministic projection, and status helpers exist at lines 61, 96, 189, 409, and 857. |
| `tests/agent/test_case_working_context_lifecycle.py` | Adapter contract tests | VERIFIED | Covers trusted case extraction, active payload projection, read/link dedupe, skip/error paths, terminal projection, writeback, PII, and conflict behavior. |
| `src/agent/state.py` | Additive CWC state fields | VERIFIED | Fields exist at lines 124-125. |
| `src/agent/nodes/receive_request.py` | Per-turn reset for CWC state | VERIFIED | Reset entries exist at lines 116-117. |
| `src/agent/nodes/reviewed_memory_context_retrieve.py` | `memory_context_load` seam CWC read/link wiring | VERIFIED | Calls adapter at lines 83-140 and merges outputs at lines 260-264 and 295-303. |
| `src/api/services/agent_run_memory.py` | Completed-run CWC writeback hook after terminal response persistence | VERIFIED | Terminal rows commit before memory side effects at line 96; CWC write helper is called at lines 109-115. |
| `tests/test_agent_runs_api.py` | Finalizer integration coverage | VERIFIED | Tests cover successful write, skip, failure preservation, PII block, and conflict preservation at lines 2337-2605. |
| `docs/contract-spec.md` | Normative lifecycle and AgentState alignment | VERIFIED | Contract includes Phase 45 CWC read/link/writeback and contextual-only wording. |
| `tests/memory/test_phase45_contract_alignment.py` | Red-line and contract alignment tests | VERIFIED | Substantive 11-test contract/red-line suite. `gsd-sdk verify.artifacts` reported missing exact string `Phase 45`; manually classified non-blocking because the file uses `phase45` test names and fully covers the required behavior. |
| `.planning/MEMORY-REDESIGN-DECISIONS.md` | Phase 45 defer closure trace | VERIFIED | Phase 45 completion trace and remaining defers are recorded. |
| `.planning/ARCHITECTURE-DEBT.md` | Chinese memory-subsystem ledger entry | VERIFIED | Phase 45 entries include completed validation evidence and residual risks. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `case_working_context_lifecycle.py` | `case_identity.py` | `resolve_case_id` | WIRED | Adapter default resolver is `resolve_case_id` at line 65. |
| `case_working_context_lifecycle.py` | `context_refs.py` | contextual status/ref models | WIRED | Imports `CaseWorkingContextLifecycleStatusV1` and `CaseWorkingContextRef` at line 26. |
| `reviewed_memory_context_retrieve.py` | `case_working_context_lifecycle.py` | `link_and_load_active` | WIRED | `_load_case_working_context` calls `adapter.link_and_load_active` at lines 131-140. |
| `case_working_context_lifecycle.py` | `conversation/repository.py` | `link_case(... run_auto ...)` | WIRED | Read and terminal paths call `ConversationRepository.link_case`; repository delegates to `ThreadCaseLinkRepository.link_thread_to_case`. |
| `agent_run_memory.py` | `case_working_context_lifecycle.py` | `write_after_terminal_success` | WIRED | Finalizer helper invokes adapter at lines 199-217. |
| `case_working_context_lifecycle.py` | `case_working_context_service.py` | `write_case_working_context` | WIRED | Adapter calls audited service at lines 301-306. |
| `docs/contract-spec.md` | `src/agent/state.py` | AgentState field registry | WIRED | Contract and implementation use `case_working_context` and `case_working_context_lifecycle_status`. |
| `test_phase45_contract_alignment.py` | `case_working_context_lifecycle.py` | static red-line sweeps | WIRED | Tests read the lifecycle/finalizer source and assert prohibited dependencies/patterns are absent. |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `src/agent/nodes/reviewed_memory_context_retrieve.py` | `case_working_context` / `case_working_context_lifecycle_status` | `CaseWorkingContextLifecycleAdapter.link_and_load_active(...)` | Yes - resolves tenant/case, links thread, reads `CaseWorkingContextRepository.read_active`, projects `hydrate_content(row)` | FLOWING |
| `src/memory/case_working_context_lifecycle.py` | `case_id` / active CWC payload | `resolve_case_id` and `CaseWorkingContextRepository.read_active` | Yes - resolver and repository are called before payload/status return | FLOWING |
| `src/memory/case_working_context_lifecycle.py` | terminal write candidate | deterministic projection from `final_state` + current `run_id` + active `expected_version` | Yes - builds `CaseWorkingContextWriteCandidate` with `run_auto_terminal` source ref and calls audited service | FLOWING |
| `src/api/services/agent_run_memory.py` | `case_working_context_result` / trace metrics | `CaseWorkingContextLifecycleAdapter.write_after_terminal_success(...)` | Yes - result dict is normalized into finalizer result and trace metrics | FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 45 red-line contract suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py -x -q` | `11 passed, 1 warning in 0.03s` | PASS |
| Ruff over touched code/test surface | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check ...` | `All checks passed!` | PASS |
| Alembic single head | `UV_CACHE_DIR=/tmp/uv-cache uv run alembic heads` | `022_case_working_context (head)` | PASS |
| Module export/import sanity | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c ...` | `CaseWorkingContextLifecycleAdapter True contextual_only` | PASS |

Recorded final evidence from phase artifacts:

| Evidence | Result |
|---|---|
| Phase 45 final targeted suite | `172 passed, 1 warning` |
| Phase 44 regression suite | `51 passed, 5 warnings` |
| Ruff | `All checks passed!` |
| Alembic heads | `022_case_working_context (head)` |
| Code review | `issues_found`, 0 critical / 1 warning |

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| MEM-01 | 45-01, 45-02, 45-03, 45-04 | CWC durable working-context layer with contextual-only, versioned, audited writes; Phase 44 deferred graph run-completion lifecycle hooks to Phase 45. | SATISFIED | Phase 45 implements active read/link and terminal writeback through Phase 44 repository/service surfaces. Finalizer integration writes through `CaseWorkingContextService.write_case_working_context(...)` and preserves failure isolation. |
| MEM-02 | 45-01, 45-02, 45-03, 45-04 | Thread<->case explicit many-to-many association, preserving legacy single-FK columns. | SATISFIED | Read and terminal paths call `ConversationRepository.link_case` with `link_source="run_auto"`; repository dedupes via `thread_case_links`; red-line tests verify legacy table/column retention. |

No orphaned Phase 45 requirement IDs were found. `.planning/REQUIREMENTS.md` maps MEM-01/MEM-02 to Phase 44, while the Phase 45 roadmap and plans explicitly name Phase 45 as the lifecycle-hook closure for those deferred parts.

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `src/memory/case_working_context_lifecycle.py` and tests | multiple | Empty collections / `None` statuses | Info | These are typed skip/missing/default states and test fixtures, not production stubs. |
| `src/memory/case_working_context_lifecycle.py` | 345 | Terminal link status can report `linked` when repository returns an existing link from an earlier run | Warning | Code review WR-01. Does not create duplicate data and does not violate lifecycle wiring; residual trace-label risk only. |
| `tests/memory/test_phase45_contract_alignment.py` | n/a | Missing exact artifact pattern `Phase 45` | Info | GSD artifact literal check only. File is substantive and covers the intended Phase 45 contract/red-line behavior through `phase45` tests. |

## Human Verification Required

None. This phase is backend memory lifecycle wiring with DB/API/static contract tests. No UI, external service, or visual/manual user flow is required for goal verification.

## Gaps Summary

No blocking gaps found. All 15 plan must-have truths are verified against actual code, tests, contract docs, and validation evidence. The single code-review warning is retained as residual risk but does not block the phase goal because the underlying repository dedupes active `thread_case_links` and the issue is limited to lifecycle trace wording.

---

_Verified: 2026-07-03T06:11:12Z_
_Verifier: Codex (gsd-verifier)_
