---
phase: 04-approval-workflow-audit
plan: 01
subsystem: observability
tags: [latency, tracing, diagnostics, alembic, langgraph]

requires:
  - phase: 03-langgraph-core
    provides: agent graph nodes, AgentRun/AgentStep trace persistence, Phase 3 test suite
provides:
  - Per-node provider latency, retry count, and sanitized metrics persistence on agent_steps
  - Diagnostic CLI for run_id latency bottleneck analysis
  - Phase 4 receive_request reset coverage for approval workflow state fields
affects: [approval-workflow-audit, evaluation, agent-tracing]

tech-stack:
  added: []
  patterns:
    - Sanitized trace metrics with model/provider/context_chars allowlist
    - CLI diagnostics using existing async SQLAlchemy session factory

key-files:
  created:
    - src/db/migrations/versions/004_latency_metrics.py
    - scripts/diagnose_latency.py
    - tests/test_latency_instrumentation.py
  modified:
    - src/db/models.py
    - src/agent/trace.py
    - src/agent/state.py
    - src/agent/nodes/assess_risk_and_approval.py
    - src/agent/nodes/classify_intent.py
    - src/agent/nodes/extract_slots.py
    - src/agent/nodes/final_response.py
    - src/agent/nodes/generate_recommendation.py
    - src/agent/nodes/load_business_context.py
    - src/agent/nodes/receive_request.py
    - src/agent/nodes/retrieve_policy_evidence.py

key-decisions:
  - "Latency metrics store only model, provider, and context_chars; prompt/message text is never persisted in metrics_json."
  - "The Alembic migration was hand-written after autogenerate detected unrelated checkpoint table drops and failed on a missing script.py.mako template."

patterns-established:
  - "Node trace steps include provider_latency_ms, retry_count, and metrics_json consistently across LLM, deterministic, and tool nodes."
  - "Diagnostic scripts expose pure report-building functions so bottleneck logic can be unit tested without database access."

requirements-completed: []

duration: 18min
completed: 2026-05-16
---

# Phase 4 Plan 1: Latency Instrumentation & Diagnostic Script Summary

**Agent trace rows now capture per-node provider latency, local retry count, and sanitized context-size metrics, with a CLI report for identifying slow graph nodes by run_id.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-16T07:17:16Z
- **Completed:** 2026-05-16T07:35:33Z
- **Tasks:** 5
- **Files modified:** 14

## Accomplishments

- Added `provider_latency_ms`, `retry_count`, and `metrics_json` to `agent_steps`, plus trace persistence mapping and timestamp-derived `latency_ms`.
- Instrumented all graph node trace steps with consistent metrics keys while keeping `metrics_json` free of prompt text and PII.
- Added `scripts/diagnose_latency.py` with DB-backed run analysis, mock JSON mode, bottleneck detection, and suspected-cause reporting.
- Reset Phase 4 approval workflow fields at the start of each turn to prevent checkpointer state leakage.
- Added five targeted tests covering metric persistence, latency computation, metrics allowlisting, mock diagnostics, and bottleneck detection.

## Task Commits

Each task was committed atomically:

1. **Task 01-01: Add provider_latency_ms, retry_count, metrics_json columns** - `37a8e97` (feat)
2. **Task 01-02: Instrument graph nodes with latency metrics** - `9448a8b` (feat)
3. **Task 01-03: Reset Phase 4 approval state fields** - `b9507b5` (fix)
4. **Task 01-04: Create diagnostic script** - `b24e34d` (feat)
5. **Task 01-05: Unit tests for latency instrumentation** - `c6ac415` (test)

## Files Created/Modified

- `src/db/migrations/versions/004_latency_metrics.py` - Adds and removes the three latency metric columns on `agent_steps`.
- `src/db/models.py` - Adds nullable metric columns to `AgentStep`.
- `src/agent/trace.py` - Persists metric fields and computes `latency_ms` from timestamps when absent.
- `src/agent/state.py` - Adds approval workflow state fields to the typed graph state.
- `src/agent/nodes/*.py` - Adds trace metric keys and LLM provider timing around structured output calls.
- `scripts/diagnose_latency.py` - Emits per-run JSON latency reports and mock reports.
- `tests/test_latency_instrumentation.py` - Covers metric persistence, allowlisting, mock CLI output, and bottleneck detection.

## Decisions Made

- `metrics_json` is intentionally limited to `model`, `provider`, and `context_chars`; prompts, messages, content, and natural-language text are not stored.
- `retry_count` means the node-local manual structured-output retry loop count, not LangGraph graph-level retry policy attempts.
- `final_response` remains deterministic-template based, so it records trace metric keys with no provider latency instead of pretending to be an LLM call.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used a safe hand-written migration after Alembic autogenerate failure**
- **Found during:** Task 01-01 (Add provider_latency_ms, retry_count, metrics_json columns)
- **Issue:** `uv run alembic revision --autogenerate` connected to the database and detected the intended new columns, but failed because `src/db/migrations/script.py.mako` is missing. The generated diff also detected unrelated LangGraph checkpoint table drops and unrelated index/constraint removals.
- **Fix:** Added a narrow migration matching the repository's existing migration style, limited to the three planned `agent_steps` columns.
- **Files modified:** `src/db/migrations/versions/004_latency_metrics.py`
- **Verification:** `uv run ruff check src/db/models.py src/agent/trace.py src/db/migrations/versions/004_latency_metrics.py`; migration file exists with `latency_metrics` in filename.
- **Committed in:** `37a8e97`

**2. [Rule 2 - Missing Critical] Added approval workflow fields to AgentState**
- **Found during:** Task 01-03 (Update receive_request to reset Phase 4 state fields)
- **Issue:** The plan required `receive_request` to return `proposed_action`, `approval_result`, and `action_result`, but the `AgentState` TypedDict did not define those fields.
- **Fix:** Added the three approval workflow fields to the ephemeral state contract.
- **Files modified:** `src/agent/state.py`
- **Verification:** `uv run ruff check src/agent/nodes/receive_request.py src/agent/state.py`; grep acceptance checks for all three reset fields passed.
- **Committed in:** `b9507b5`

---

**Total deviations:** 2 auto-fixed (Rule 2: 1, Rule 3: 1)
**Impact on plan:** Both fixes were required for correctness and safe execution. No optimization behavior was introduced.

## Issues Encountered

- Running `tests/test_latency_instrumentation.py` and `tests/agent` in parallel caused a shared `moca_test` database fixture collision during table teardown/setup. Rerunning the two pytest commands sequentially passed.
- The system `python` binary is broken on this machine, so Python verification used `uv run python`.

## Verification

- `uv run pytest tests/test_latency_instrumentation.py -q` - 5 passed, 1 warning
- `uv run python scripts/diagnose_latency.py --mock` - emitted valid JSON with `run_id`, `total_latency_ms`, `nodes`, `bottleneck`, and `suspected_causes`
- `uv run ruff check src/agent/nodes/ src/agent/trace.py scripts/diagnose_latency.py` - passed
- `uv run pytest tests/agent -q` - 39 passed, 1 warning

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 04-02 can use the diagnostic script against live `agent_runs` to identify whether latency is dominated by provider calls, retries, retrieval, context size, or deterministic processing before choosing optimizations.

## Self-Check: PASSED

- Verified summary, migration, diagnostic script, and test file exist.
- Verified task commits are reachable: `37a8e97`, `9448a8b`, `b9507b5`, `b24e34d`, `c6ac415`.

---
*Phase: 04-approval-workflow-audit*
*Completed: 2026-05-16*
