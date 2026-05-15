---
phase: "03"
slug: langgraph-core
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-15T13:23:27Z
updated: 2026-05-15T13:23:27Z
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | `pyproject.toml` (`tool.pytest.ini_options.asyncio_mode = "auto"`) |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/ -q --tb=short -m "not live"` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` |
| **Lint command** | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests scripts` |
| **Estimated runtime** | quick: ~7s; full: ~47s |

Note: DB-backed pytest suites share a test schema and must be run serially. Running two full/agent pytest processes at the same time can deadlock concurrent schema create/drop setup.

---

## Sampling Rate

- **After every task commit:** Run the narrow command listed in that task's `<verify>` block.
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` plus scoped `ruff check`.
- **Before `$gsd-verify-work`:** Full suite and live smoke must be green.
- **Max feedback latency:** ~60 seconds for the local full suite.

---

## Requirement Coverage Summary

| Requirement | Coverage Status | Primary Automated Evidence |
|-------------|-----------------|----------------------------|
| AGNT-01 | COVERED | `tests/agent/test_nodes/test_classify_intent.py`; `tests/agent/test_graph.py::test_happy_path_policy_qa`; `test_happy_path_refund_troubleshooting` |
| AGNT-02 | COVERED | `tests/agent/test_graph.py` validates the compiled 8-node path and trace node count |
| AGNT-03 | COVERED | `tests/agent/test_tools/test_get_order.py`; `test_get_refund_case.py`; `test_get_ticket.py`; graph business-context tests |
| AGNT-04 | COVERED | `tests/agent/test_nodes/test_retrieve_policy_evidence.py`; `test_generate_recommendation.py`; `test_final_response.py` |
| AGNT-05 | COVERED | `tests/agent/test_graph.py::test_cross_turn_context_isolation`; `test_same_thread_evidence_refs_survive_next_turn` |
| AGNT-06 | COVERED | `tests/agent/test_trace.py`; `tests/agent/test_graph.py::test_trace_summary_shape` |
| AGNT-08 | COVERED | `tests/agent/test_nodes/test_retrieve_policy_evidence.py::test_evidence_gate_no_evidence`; `tests/agent/test_graph.py::test_insufficient_evidence_path` |
| INFR-09 | COVERED | LLM parse/fallback tests in `tests/agent/test_graph.py`; tool timeout tests in `tests/agent/test_tools/*`; API fallback evidence in `03-VERIFICATION.md` |
| RAG-05 | COVERED | `tests/agent/test_nodes/test_generate_recommendation.py`; `tests/agent/test_nodes/test_final_response.py`; `tests/agent/test_trace.py` |
| SAFE-06 | COVERED | DB-backed `tests/agent/test_trace.py` verifies AgentRun/AgentStep replay by run_id |
| SAFE-08 | COVERED | Same-tenant cross-merchant denial tests in `tests/agent/test_tools/test_get_order.py`, `test_get_refund_case.py`, and `test_get_ticket.py` |

No Phase 3 requirement is classified MISSING or PARTIAL.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | AGNT-02, AGNT-05, AGNT-06, INFR-09, SAFE-06 | T-03-01 | Settings expose LLM/checkpointer config without leaking provider secrets. | import/lint | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.config import settings; assert hasattr(settings, 'llm_model'); assert settings.checkpointer_database_url.startswith('postgresql://')"` | yes | green |
| 03-01-02 | 01 | 1 | AGNT-06, SAFE-06 | T-03-02 | AgentRun/AgentStep schema exists and migrates cleanly. | migration/import | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.db.models import AgentRun, AgentStep"`; `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` | yes | green |
| 03-02-01 | 02 | 2 | AGNT-04, RAG-05 | - | Agent state and structured output schemas exist for safe typed LLM outputs. | import/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.agent.state import AgentState; from src.agent.schemas import RecommendationDraft"` | yes | green |
| 03-02-02 | 02 | 2 | AGNT-03, SAFE-08 | T-03-03, T-03-04, T-03-05 | Read-only tools enforce tenant/merchant scoping and omit ticket messages. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools -q --tb=short` | yes | green |
| 03-03-01 | 03 | 3 | AGNT-01, AGNT-03, AGNT-04, AGNT-08, INFR-09 | T-03-06, T-03-07, T-03-08, T-03-09 | Nodes reset ephemeral state, gate no-evidence, validate citations, and fall back on provider errors. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes -q --tb=short` | yes | green |
| 03-03-02 | 03 | 3 | AGNT-02, AGNT-05 | - | Graph compiles with deterministic read-only 8-node path and no approval interrupts. | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py -q --tb=short -m "not live"` | yes | green |
| 03-04-01 | 04 | 4 | AGNT-06, SAFE-06 | T-03-10, T-03-13 | Trace summary is minimal and AgentRun/AgentStep rows persist replayable audit data. | unit/db | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py -q --tb=short` | yes | green |
| 03-04-02 | 04 | 4 | AGNT-02, AGNT-05, INFR-09, SAFE-08 | T-03-11, T-03-12 | Agent API scopes checkpointer thread IDs by tenant/user and returns structured fallback on graph errors. | import/full suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` | yes | green |
| 03-05-01 | 05 | 5 | AGNT-01, AGNT-03, AGNT-04, AGNT-08, SAFE-08 | T-03-15 | FakeLLM-backed CI tests cover tools and nodes without live provider calls. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/ -q --tb=short -m "not live"` | yes | green |
| 03-05-02 | 05 | 5 | AGNT-02, AGNT-05, AGNT-06, RAG-05, SAFE-06 | T-03-14, T-03-15 | Graph integration, failure paths, live smoke script syntax, and synthetic golden set are present. | integration/data | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py -q --tb=short -m "not live"` | yes | green |
| 03-06-01 | 06 | 6 | AGNT-06, SAFE-06 | T-03-GAP-02, T-03-GAP-03 | AgentStep rows preserve tool names and evidence refs by run_id. | db regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py -q --tb=short` | yes | green |
| 03-06-02 | 06 | 6 | AGNT-04, AGNT-05, RAG-05 | T-03-GAP-01, T-03-GAP-04 | Retrieval and recommendation write compact, validated evidence refs only. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_retrieve_policy_evidence.py tests/agent/test_nodes/test_generate_recommendation.py -q --tb=short` | yes | green |
| 03-06-03 | 06 | 6 | AGNT-05, AGNT-06, SAFE-06 | T-03-GAP-04, T-03-GAP-05 | Same-thread evidence memory persists for audit but does not override current-turn no-evidence behavior. | graph regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_trace.py -q --tb=short -m "not live"` | yes | green |

---

## Wave 0 Requirements

Existing infrastructure covers all Phase 3 requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live external LLM/provider smoke | AGNT-01, AGNT-04, RAG-05, INFR-09 | CI intentionally uses FakeLLM and cannot depend on local DashScope credentials or local operator database state. | Recorded in `03-HUMAN-UAT.md`: `set -a; source .env; set +a; LIVE_SMOKE_CASE_TIMEOUT_SECONDS=420 UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/smoke_agent_live.py` passed 3/3. |

Manual-only count: 1, already resolved by Phase 3 human UAT.

---

## Validation Audit 2026-05-15

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

### Commands Run

- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests scripts` — passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/ -q --tb=short -m "not live"` — 39 passed, 1 warning
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` — 89 passed, 1 warning

### Notes

- An attempted concurrent run of the agent suite and full suite produced Postgres schema setup deadlocks. This was an execution-mode issue, not a product failure; serial reruns passed.
- The remaining warning is the existing LangGraph checkpointer serde deprecation warning.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-15
