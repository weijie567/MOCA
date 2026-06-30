---
phase: 24
slug: agent-runs-short-term-memory-parity
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-20
---

# Phase 24 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | Focused suite ~60-180 seconds; full suite depends on local DB/API state |

---

## Sampling Rate

- **After every task commit:** Run the task's focused pytest command plus `uv run ruff check src/ tests/`.
- **After every plan wave:** Run `uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/memory/test_session_memory_service.py -q`.
- **Before `$gsd-verify-work`:** Full suite `uv run pytest` must be green, or every failure must be recorded with a concrete Phase 24 ownership decision.
- **Max feedback latency:** 180 seconds for focused validation.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 24-W0-01 | Wave 0 tests | 0 | STM-01, STM-02, STM-03, STM-04 | T-24-01, T-24-02, T-24-03 | Tests fail until `/agent-runs` creates one user message, injects trusted conversation IDs, writes one assistant message, and updates summary idempotently | API integration | `uv run pytest tests/test_agent_runs_api.py::test_create_agent_run_persists_exactly_one_user_message tests/test_agent_runs_api.py::test_agent_run_stream_passes_conversation_ids_to_graph_and_tools tests/test_agent_runs_api.py::test_completed_agent_run_persists_exactly_one_assistant_message tests/test_agent_runs_api.py::test_completed_agent_run_updates_thread_summary_idempotently -q` | yes, new tests needed | pending |
| 24-W0-02 | Wave 0 tests | 0 | STM-05, STM-06, STM-07, STM-12 | T-24-04, T-24-05 | Tests prove prompt context uses safe projectors, keeps session slots active, and never treats memory as evidence/business/action/replay authority | service/context integration | `uv run pytest tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/agent/context/test_assembler.py -q` | yes, extension needed | pending |
| 24-W0-03 | Wave 0 tests | 0 | STM-08, STM-09, STM-10, STM-11 | T-24-01, T-24-06 | Tests prove legacy chat stays compatible, non-completed runs do not write completed memory, duplicate SSE streams do not duplicate records, and final response waits for bounded memory result | API/SSE integration | `uv run pytest tests/test_agent_runs_api.py::test_agent_run_error_cancel_interrupted_do_not_write_completed_memory tests/test_agent_runs_api.py::test_duplicate_sse_stream_does_not_duplicate_memory_surfaces tests/test_agent_runs_api.py::test_sse_final_response_after_bounded_memory_persistence_result -q` | yes, new/renamed tests needed | pending |
| 24-W0-04 | Wave 0 tests | 0 | STM-13, STM-14 | T-24-04, T-24-05 | Three-turn Agent Console smoke proves slot continuity and rolling-summary context without authority leakage | integration smoke | `uv run pytest tests/test_agent_runs_api.py::test_three_turn_agent_runs_smoke_uses_slots_and_summary_context -q` | yes, new test needed | pending |
| 24-01-01 | Idempotency primitives | 1 | STM-01, STM-03, STM-04, STM-10 | T-24-01, T-24-02 | DB/repository/service helpers return existing run-role messages and existing equivalent summary instead of appending duplicates | unit/DB integration | `uv run pytest tests/conversation/test_service.py tests/memory/test_thread_summary.py -q` | yes | pending |
| 24-02-01 | Create/claim wiring | 2 | STM-01, STM-02, STM-07 | T-24-03, T-24-05 | Graph config receives only backend-trusted conversation IDs; tool prompt summaries attach to the current user message through existing safe APIs | API/SSE integration | `uv run pytest tests/test_agent_runs_api.py -q` | yes | pending |
| 24-03-01 | Completed finalizer | 3 | STM-03, STM-04, STM-06, STM-11 | T-24-02, T-24-06 | Completed-only finalizer persists assistant message, rolling summary, and bounded session-memory result before `final_response` | API/SSE integration | `uv run pytest tests/test_agent_runs_api.py tests/memory/test_session_memory_service.py -q` | yes | pending |
| 24-04-01 | Failure semantics | 4 | STM-09, STM-10, STM-12 | T-24-01, T-24-06 | Error, cancelled, interrupted, retried, and reopened states preserve audit/run artifacts without false completed memory | API/SSE integration | `uv run pytest tests/test_agent_runs_api.py -q` | yes | pending |
| 24-05-01 | Prompt context parity | 5 | STM-05, STM-06, STM-07, STM-12 | T-24-04, T-24-05 | Same-thread follow-ups load recent messages, latest prior summary, prompt-safe tool summaries, and trusted session slots only through existing projection boundaries | service/graph integration | `uv run pytest tests/conversation/test_service.py tests/agent/test_session_memory_integration.py tests/agent/context/test_assembler.py -q` | yes | pending |
| 24-06-01 | Legacy and smoke | 6 | STM-08, STM-13, STM-14 | T-24-04, T-24-05 | Legacy `/agent/chat` remains green and a three-turn `/agent-runs + SSE` smoke proves continuity | regression/smoke | `uv run pytest tests/test_agent_runs_api.py tests/conversation/test_service.py tests/memory/test_thread_summary.py tests/memory/test_session_memory_service.py -q` | yes | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_agent_runs_api.py` - add failing STM-01/02/03/04/09/10/11/14 run/SSE parity tests before implementation.
- [ ] `tests/conversation/test_service.py` - add or extend run-role idempotency and prompt-context window tests.
- [ ] `tests/memory/test_thread_summary.py` - add rolling-summary idempotency by source end/range if summary persistence changes.
- [ ] `tests/test_agent_runs_api.py` - replace the old-order assertion in `test_sse_final_response_before_memory_write_schedule` with a Phase 24 assertion that bounded memory persistence completes/skips/errors before `final_response`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Local browser Agent Console UX sanity | STM-14 | Automated API/SSE smoke is required; browser sanity is optional because frontend redesign is out of scope | After backend tests pass, run the app locally and submit a three-turn same-thread conversation that references a prior order/refund. Confirm the final answer uses context for reference resolution but still retrieves current facts/evidence. |

---

## Threat Model References

| Ref | Threat | Required Mitigation |
|-----|--------|---------------------|
| T-24-01 | Duplicate SSE retry/reopen duplicates user, assistant, tool, summary, or session-memory records | Keep pending-run claim and add run-role/summary/session finalizer idempotency checks |
| T-24-02 | Partial finalizer failure leaves a final answer visible without promised next-turn continuity | Bound required memory persistence before `final_response`; record explicit skipped/error result |
| T-24-03 | Tool summaries fail to persist because graph config lacks trusted conversation IDs | Resolve stored user message and inject trusted `conversation_thread_id` and `conversation_message_id` before graph execution |
| T-24-04 | Cross-user/thread memory leakage | Scope reads/writes by tenant, user, thread, and trusted run identity |
| T-24-05 | Memory is treated as policy evidence, current business fact, approval/action authority, or replay truth | Keep ContextAssembler/projector boundaries and require current tools/evidence/approval records for authority-bearing claims |
| T-24-06 | Error/cancel/interruption creates false completed assistant message or rolling summary | Gate assistant message, summary, and successful session-memory writes to completed runs only |

---

## Validation Sign-Off

- [x] All planned tasks have automated focused verification targets or Wave 0 dependencies.
- [x] Sampling continuity has no 3 consecutive tasks without automated verification.
- [x] Wave 0 covers all missing Phase 24 validation references.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 180 seconds for focused suites.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending
