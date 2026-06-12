---
phase: 10
slug: state-lifecycle-routing-migration
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-11
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (`asyncio_mode="auto"`) `[VERIFIED: pyproject.toml:29-48]` |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_graph_routing.py tests/test_state_lifecycle.py tests/agent/test_nodes/ -x -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~60-120 seconds (full suite; quick subset < 30s) |

Decision: no new dependency. Property/totality coverage uses hand-rolled `@pytest.mark.parametrize` table tests over enumerated/degenerate states (RESEARCH A1 alternative; `hypothesis` NOT added).

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_graph_routing.py tests/test_state_lifecycle.py tests/agent/test_nodes/ -x -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | STATE-01 | — | New §10.1 ephemeral fields declared; total=False preserved | unit | `python -c "from src.agent.state import AgentState; ..."` | ✅ exists | ⬜ pending |
| 10-01-02 | 01 | 1 | STATE-01/02 | T-10-01 | Ephemeral reset each turn; identity fields excluded from reset | unit | `pytest tests/agent/test_nodes/test_receive_request.py -x -q` | ✅ exists | ⬜ pending |
| 10-01-03 | 01 | 1 | STATE-01/02 | T-10-01/02 | Cross-turn isolation; identity not LLM-mergeable | unit/table | `pytest tests/test_state_lifecycle.py -x -q` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 1 | ROUTE-02 | T-10-05 | event_id is single PK; (run_id,sequence) DB-unique; base table chains from 005 | unit | `python -c "from src.db.models import AgentTraceEvent; ..."` | ✅ exists | ⬜ pending |
| 10-02-02 | 02 | 1 | ROUTE-02 | T-10-04/06 | Classify by nature; redaction guard; non-allowlist rejected | unit | `python -c "from src.agent.events import classify_event_family ..."` | ✅ exists | ⬜ pending |
| 10-02-03 | 02 | 1 | ROUTE-02 | T-10-04/05/06 | Monotonic+resume sequence; one family/op; iteration in payload | unit/integration | `pytest tests/agent/test_events.py -x -q` | ❌ W0 | ⬜ pending |
| 10-03-01 | 03 | 2 | ROUTE-01/02 | T-10-08/09/10 | Pure router; state-only; canonical keys; safe default | unit | `python -c "import inspect; from src.agent.routing import route_after_investigate ..."` | ✅ exists | ⬜ pending |
| 10-03-02 | 03 | 2 | ROUTE-01/02 | T-10-08/09/10 | Branch+totality+claim_dependency_map fail-closed permission precedence | unit/table | `pytest tests/test_graph_routing.py -x -q` | ✅ exists (extend) | ⬜ pending |
| 10-04-01 | 04 | 2 | ROUTE-02 | T-10-11/12/13/14/15 | Bounded loop; three resource caps; allowlist; no write/gate; no evidence_refs | unit | `pytest tests/agent/test_nodes/test_investigate.py -x -q` | ❌ W0 | ⬜ pending |
| 10-04-02 | 04 | 2 | ROUTE-02 | T-10-11/12/13/14/15 | D-03/D-04/D-06/D-08 including claim_dependency_map each proven by executable test | unit/integration | `pytest tests/agent/test_nodes/test_investigate.py -x -q` | ❌ W0 | ⬜ pending |
| 10-05-01 | 05 | 3 | ROUTE-02 | T-10-17/18 | clarification stub safe; empty session no continuity claim | unit | `python -c "...session_memory_load/clarification_gate..."` | ✅ exists | ⬜ pending |
| 10-05-02 | 05 | 3 | ROUTE-01 | T-10-16 | investigate wired; old linear edges removed; graph compiles | unit | `python -c "from src.agent.graph import build_graph; ..."` | ✅ exists | ⬜ pending |
| 10-05-03 | 05 | 3 | ROUTE-01/02 | T-10-16/18 | Every router key is a real edge target; SC-3 empty adapter | unit/integration | `pytest tests/agent/test_graph.py tests/agent/test_empty_session_adapter.py -x -q` | ❌ W0 (partial) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_state_lifecycle.py` — NEW: STATE-01/02 reset/isolation/trusted-field tests (Plan 01 Task 3 creates it).
- [ ] `tests/agent/test_events.py` — NEW: sequence/classification/redaction tests (Plan 02 Task 3 creates it).
- [ ] `tests/agent/test_nodes/test_investigate.py` — NEW: D-03/D-04/D-06/D-08 guardrail tests (Plan 04 Task 2 creates it).
- [ ] `tests/agent/test_empty_session_adapter.py` — NEW: SC-3 empty session adapter (Plan 05 Task 3 creates it).
- [ ] `tests/test_graph_routing.py` — EXTEND: route_after_investigate branch/totality/fallback (Plan 03 Task 2).
- [ ] `tests/agent/test_graph.py` — EXTEND: wiring-layer totality (Plan 05 Task 3).
- [ ] Fixtures: `tests/conftest.py` seeded_session already seeds order/refund_case/ticket (conftest.py:183-215) — reused; agent_run row needed for AgentTraceEvent FK (confirm fixture during Plan 02 Task 3).
- [ ] Framework: no install — hand-rolled parametrized table tests (no hypothesis dependency).

These NEW test files are created by their owning plan's task (not a separate Wave-0-only pass), since each is co-located with the code it verifies. Each task that introduces production code carries `tdd="true"` and a `<behavior>` block, so test scaffolds precede implementation within the task.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end investigate loop against real BusinessToolService facade + full 8-tool allowlist | ROUTE-02 / TOOL-01 | BusinessToolService (Phase 9) not yet implemented; only the 4 available read tools + interim seam are exercisable now | After Phase 9 lands: swap interim `_run_read_tool` for `BusinessToolService.fetch_context`, then run `pytest tests/agent/test_nodes/test_investigate.py -q` plus an integration run exercising logistics/merchant_risk |

All other phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (new test files owned by their plans)
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-11
