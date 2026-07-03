---
phase: 45
slug: memory-lifecycle-wiring-for-case-working-context
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-03
---

# Phase 45 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_identity.py tests/memory/test_thread_case_links.py -q` |
| **Fast smoke command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py -x -q` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_context_refs.py tests/agent/test_case_working_context_lifecycle.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_case_identity.py tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py tests/test_agent_runs_api.py tests/memory/test_phase44_contract_alignment.py tests/memory/test_phase45_contract_alignment.py -q` |
| **Estimated runtime** | Fast smoke target <30 seconds where possible; full targeted suite ~60-180 seconds with local PostgreSQL available |

---

## Sampling Rate

- **After every task commit:** Run the narrow test file touched by that task with `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`; for final contract/ledger tasks, run the fast smoke command before the full DB-backed gate.
- **After every plan wave:** Run the targeted DB-backed suite for the affected surface.
- **Before `$gsd-verify-work`:** Full targeted suite plus all new Phase 45 tests must be green.
- **Max feedback latency:** <30 seconds target for smoke/narrow task-level feedback where possible; 180 seconds is allowed only for focused DB-backed and final targeted gates.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 45-W0-01 | 45-01 / 45-02 / 45-03 | 0 | CWC active lifecycle | T-45-01 / T-45-02 | Tenant-scoped case identity gates CWC read/link/write | unit / DB integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_case_working_context_lifecycle.py -q` | yes | green |
| 45-W0-02 | 45-04 | 0 | CWC contract alignment | T-45-03 | CWC remains contextual-only and distinct from reviewed case memory | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py -q` | yes | green |
| 45-W0-03 | 45-03 | 0 | terminal finalizer writeback | T-45-04 / T-45-06 | CWC failure does not roll back assistant message or thread summary | API / DB integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_failure_preserves_terminal_rows -q` | yes | green |
| 45-W0-04 | 45-04 | 0 | ReAct/memory decoupling red line | T-45-05 | `investigate` does not become graph-global `active_slots` writer | contract / grep-backed | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py -q` | yes | green |
| 45-FINAL-SMOKE | 45-04 | 4 | task-level final feedback | T-45-01..T-45-06 | Fast red-line/entrypoint smoke before long DB-backed final gate | contract / grep-backed | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py -x -q` | yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `tests/agent/test_case_working_context_lifecycle.py` - adapter-level identity, link, active read, write/skip status coverage.
- [x] `tests/memory/test_phase45_contract_alignment.py` - CWC contextual-only, no `case_memories` backfill, no LLM summarizer, no `active_slots` writer expansion.
- [x] `tests/test_agent_runs_api.py` - new finalizer CWC writeback/failure-preservation tests beside existing terminal memory tests.
- [x] Existing infrastructure covers pytest, async DB fixtures, and local PostgreSQL through compose.

---

## Manual-Only Verifications

All planned Phase 45 behaviors should have automated verification. Manual review is limited to reading plan/checker output and confirming intentional defers remain documented.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Fast smoke feedback latency target < 30s where possible; final DB-backed gate may take 60-180s.
- [x] `nyquist_compliant: true` set in frontmatter after execution proves coverage.

**Approval:** passed

## Final Verification Results

Recorded after Phase 45-04 final gates passed:

1. `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py -x -q`
   - Result: `11 passed, 1 warning in 0.03s`
2. `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_context_refs.py tests/agent/test_case_working_context_lifecycle.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_case_identity.py tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py tests/test_agent_runs_api.py tests/memory/test_phase44_contract_alignment.py tests/memory/test_phase45_contract_alignment.py -q`
   - Result: `172 passed, 1 warning in 138.06s (0:02:18)`
3. `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/context_refs.py src/memory/case_working_context_lifecycle.py src/agent/state.py src/agent/nodes/receive_request.py src/agent/nodes/reviewed_memory_context_retrieve.py src/api/services/agent_run_memory.py tests/memory/test_context_refs.py tests/agent/test_case_working_context_lifecycle.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/test_agent_runs_api.py tests/memory/test_phase45_contract_alignment.py`
   - Result: `All checks passed!`
4. `UV_CACHE_DIR=/tmp/uv-cache uv run alembic heads`
   - Result: `022_case_working_context (head)`
