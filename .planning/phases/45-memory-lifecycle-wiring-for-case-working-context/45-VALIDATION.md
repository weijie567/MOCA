---
phase: 45
slug: memory-lifecycle-wiring-for-case-working-context
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_identity.py tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py tests/agent/test_reviewed_memory_context_retrieve.py tests/test_agent_runs_api.py tests/memory/test_phase44_contract_alignment.py -q` |
| **Estimated runtime** | ~60-180 seconds with local PostgreSQL available |

---

## Sampling Rate

- **After every task commit:** Run the narrow test file touched by that task with `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.
- **After every plan wave:** Run the targeted DB-backed suite for the affected surface.
- **Before `$gsd-verify-work`:** Full targeted suite plus all new Phase 45 tests must be green.
- **Max feedback latency:** 180 seconds for focused DB-backed tests.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 45-W0-01 | TBD | 0 | CWC active lifecycle | T-45-01 / T-45-02 | Tenant-scoped case identity gates CWC read/link/write | unit / DB integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_case_working_context_lifecycle.py -q` | no | pending |
| 45-W0-02 | TBD | 0 | CWC contract alignment | T-45-03 | CWC remains contextual-only and distinct from reviewed case memory | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py -q` | no | pending |
| 45-W0-03 | TBD | 0 | terminal finalizer writeback | T-45-04 / T-45-06 | CWC failure does not roll back assistant message or thread summary | API / DB integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_failure_preserves_terminal_rows -q` | partial | pending |
| 45-W0-04 | TBD | 0 | ReAct/memory decoupling red line | T-45-05 | `investigate` does not become graph-global `active_slots` writer | contract / grep-backed | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py -q` | no | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/agent/test_case_working_context_lifecycle.py` - adapter-level identity, link, active read, write/skip status coverage.
- [ ] `tests/memory/test_phase45_contract_alignment.py` - CWC contextual-only, no `case_memories` backfill, no LLM summarizer, no `active_slots` writer expansion.
- [ ] `tests/test_agent_runs_api.py` - new finalizer CWC writeback/failure-preservation tests beside existing terminal memory tests.
- [ ] Existing infrastructure covers pytest, async DB fixtures, and local PostgreSQL through compose.

---

## Manual-Only Verifications

All planned Phase 45 behaviors should have automated verification. Manual review is limited to reading plan/checker output and confirming intentional defers remain documented.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing references.
- [ ] No watch-mode flags.
- [ ] Feedback latency < 180s.
- [ ] `nyquist_compliant: true` set in frontmatter after execution proves coverage.

**Approval:** pending
