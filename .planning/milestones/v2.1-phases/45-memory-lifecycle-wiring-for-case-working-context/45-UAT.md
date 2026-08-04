---
status: complete
phase: 45-memory-lifecycle-wiring-for-case-working-context
source:
  - 45-01-SUMMARY.md
  - 45-02-SUMMARY.md
  - 45-03-SUMMARY.md
  - 45-04-SUMMARY.md
started: 2026-07-03T07:51:33Z
updated: 2026-07-03T07:51:33Z
mode: self-verified-backend-uat
---

## Current Test

[testing complete]

## Tests

### 1. Active CWC Read And Run-Auto Link
expected: A run with trusted tenant/user/thread/run context and a trusted case ref links the current thread to the canonical refund case with `link_source="run_auto"` and loads active CWC into the memory context bundle before investigate consumes memory.
result: pass
evidence: `tests/agent/test_case_working_context_lifecycle.py` plus `tests/agent/test_reviewed_memory_context_retrieve.py::test_reviewed_memory_context_retrieve_invokes_cwc_lifecycle_adapter_with_trusted_context` and `::test_reviewed_memory_context_retrieve_merges_cwc_into_unified_memory_context_bundle`

### 2. Fail-Closed Case Identity
expected: Missing or unresolved trusted case identity yields explicit skipped status, does not query or backfill from reviewed `case_memories`, and leaves reviewed-memory fallback behavior intact.
result: pass
evidence: `tests/agent/test_case_working_context_lifecycle.py` and `tests/memory/test_phase45_contract_alignment.py`

### 3. Terminal CWC Writeback
expected: A completed terminal run with final response and resolved canonical case identity writes deterministic CWC content through the audited service with `run_auto_terminal` source refs and traceable status fields.
result: pass
evidence: `tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context`

### 4. Memory Failure Isolation
expected: CWC write failure, PII block, or expected-version conflict is reported as CWC status/reason data and does not roll back assistant message, thread summary, existing memory side effects, or user-visible response artifacts.
result: pass
evidence: `tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_failure_preserves_terminal_rows`, `::test_agent_run_finalizer_cwc_blocked_preserves_terminal_rows`, and `::test_agent_run_finalizer_cwc_conflict_preserves_terminal_rows`

### 5. Contextual-Only Red Lines
expected: CWC remains contextual-only memory, not evidence, policy, approval, action, business-fact, long-term memory, reviewed case memory, replay authority, or a graph-global `active_slots` writer.
result: pass
evidence: `tests/memory/test_phase45_contract_alignment.py`

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Verification

`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py tests/agent/test_case_working_context_lifecycle.py tests/agent/test_reviewed_memory_context_retrieve.py::test_reviewed_memory_context_retrieve_invokes_cwc_lifecycle_adapter_with_trusted_context tests/agent/test_reviewed_memory_context_retrieve.py::test_reviewed_memory_context_retrieve_merges_cwc_into_unified_memory_context_bundle tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_failure_preserves_terminal_rows tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_blocked_preserves_terminal_rows tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_conflict_preserves_terminal_rows -q`

Result: `48 passed, 1 warning in 17.17s`.

The warning is the existing LangGraph `allowed_objects` pending deprecation warning and is not a Phase 45 UAT issue.

## Gaps

No UAT gaps.
