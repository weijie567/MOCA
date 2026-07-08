---
phase: 58-canonical-graph-cutover-and-no-debt-cleanup
plan: 08
subsystem: canonical-agent-graph
tags: [canonical-graph, trace-projection, sse, frontend-timeline, eval-harness, tdd]

requires:
  - phase: 58-01
    provides: canonical-only current graph vocabulary and historical stored-row projection boundary
  - phase: 58-07
    provides: canonical integration seams and wrapper resurrection guards
provides:
  - canonical current-run trace/API/SSE/frontend projection labels
  - historical stored-row trace readability narrowed to explicit projection fields
  - eval graph-contract harness with canonical fake LLM patch targets only
  - dev-contract manifest guard against deleted legacy node test paths
affects: [CAGM-09, trace-api, agent-runs-sse, frontend-timeline, eval-replay]

tech-stack:
  added: []
  patterns:
    - current-run payload extraction branches only on canonical graph node names
    - legacy stored names remain readable through trace projection, not SSE/current label maps
    - eval graph-contract fakes expose canonical node keys only

key-files:
  created:
    - .planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-08-SUMMARY.md
  modified:
    - src/api/routers/agent_runs.py
    - frontend/src/components/timeline/TimelineStep.tsx
    - scripts/eval_agent.py
    - tests/agent/test_trace.py
    - tests/test_trace_api.py
    - tests/test_agent_runs_api.py
    - tests/eval/test_phase35_replay_eval_gates.py

key-decisions:
  - "Current SSE payload extraction no longer interprets legacy node names as canonical target nodes."
  - "Historical stored-row readability remains in trace projection fields: implementation_node, target_node, and target_graph_status."
  - "No dedicated frontend TimelineStep unit test exists; Plan 58-08 verifies timeline behavior through backend payload/source guards plus frontend build/test sanity."

patterns-established:
  - "RED/GREEN commits for projection cleanup: failing guards first, then minimal current-surface cleanup."
  - "Manifest cleanup that is already satisfied remains guarded by tests instead of rewriting unchanged JSON."

requirements-completed: [CAGM-09]

duration: 16min
completed: 2026-07-08
---

# Phase 58 Plan 08: Trace, Frontend, Eval Projection Cleanup Summary

**Current trace/API/SSE/frontend/eval surfaces now use canonical graph names, while legacy stored trace names remain readable only through historical projection fields.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-07-08T02:53:22Z
- **Completed:** 2026-07-08T03:09:31Z
- **Tasks:** 2
- **Files modified:** 7 plus this summary

## Accomplishments

- Removed legacy current-run node labels and payload extraction branches from agent-run SSE projection.
- Removed legacy current-run labels from the frontend timeline label map and added backend/source guards for canonical frontend labels.
- Retargeted current agent-run tests and trace summary tests to canonical current names, with old names explicitly scoped as historical stored-row readability.
- Removed the eval graph-contract legacy node registry and fake LLM compatibility keys.
- Added manifest guards proving deleted legacy node test paths are absent.

## Task Commits

1. **Task 1 RED:** `60194f6` - `test(58-08): add failing canonical projection guards`
2. **Task 1 GREEN:** `761e448` - `feat(58-08): canonicalize current trace projections`
3. **Task 2 RED:** `e13e40e` - `test(58-08): add failing eval canonical surface guards`
4. **Task 2 GREEN:** `810208d` - `feat(58-08): canonicalize eval graph contract harness`

## Files Created/Modified

- `src/api/routers/agent_runs.py` - removed legacy current-run labels and legacy `_extract_step_payload` branches.
- `frontend/src/components/timeline/TimelineStep.tsx` - canonical frontend timeline label map.
- `scripts/eval_agent.py` - canonical-only graph-contract patched node set and fake LLM keys.
- `tests/agent/test_trace.py` - historical projection assertions now use `historical_projection` status and canonical SSE label guards.
- `tests/test_trace_api.py` - trace API timeline test names clarify historical stored-row readability.
- `tests/test_agent_runs_api.py` - current-run graph fakes use canonical nodes; SSE/frontend/payload guards enforce canonical surfaces.
- `tests/eval/test_phase35_replay_eval_gates.py` - eval harness and manifest guards for canonical current surfaces.

Verified unchanged:

- `scripts/diagnose_latency.py` already used canonical mock node names.
- `eval/replay/dev-contract-manifest.v1.json` already referenced canonical risk-gate paths; the plan adds a guard instead of rewriting unchanged JSON.

## Frontend Timeline Coverage

No dedicated frontend `TimelineStep` unit test exists. Plan 58-08 verifies frontend timeline behavior through backend SSE payload tests, a Python source guard against legacy frontend label-map entries, `npm --prefix frontend run build`, and `npm --prefix frontend run test`.

Residual coverage boundary: a dedicated `TimelineStep` node-name rendering unit test is still missing.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py -q --tb=short` - `119 passed, 1 warning`
- `npm --prefix frontend run build` - passed
- `npm --prefix frontend run test` - `2 passed`, `6 tests passed`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase35_replay_eval_gates.py tests/eval/test_phase35_release_monitoring_manifests.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short` - `33 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check scripts/eval_agent.py scripts/diagnose_latency.py tests/eval/test_phase35_replay_eval_gates.py tests/eval/test_phase35_release_monitoring_manifests.py` - passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/eval/test_phase35_replay_eval_gates.py tests/eval/test_phase35_release_monitoring_manifests.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short` - `152 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/api/routers/agent_runs.py src/api/routers/traces.py src/agent/trace.py src/repositories/trace_repo.py scripts/eval_agent.py scripts/diagnose_latency.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/eval/test_phase35_replay_eval_gates.py tests/eval/test_phase35_release_monitoring_manifests.py` - passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` - passed with `active_runtime_legacy=0`, `current_docs_legacy_authority=0`, `unclassified_rows=0`
- `git diff --check` - passed

## Decisions Made

- Current-run SSE payloads are not a historical projection surface. If a legacy node name appears there unexpectedly, `target_node_name` is not translated to a canonical name.
- Trace summaries, trace API responses, and repository timeline details remain the bounded historical stored-row readability path.
- The eval manifest was not rewritten because the deleted wrapper paths were already absent; a test now locks that condition.

## Deviations from Plan

None - plan executed within the intended scope. The final strict classifier did not expose stale current references requiring extra cleanup.

## Issues Encountered

- Expected TDD RED failures occurred before each GREEN implementation and are represented by the RED commits.
- No unexpected local debug/start/verification/UI/API/RAG/agent/memory/tool issue occurred, so `.planning/LOCAL-VALIDATION-ISSUES.md` was not updated.
- No tool calling, RAG, memory, or intent-recognition subsystem debt was found or fixed, so `.planning/ARCHITECTURE-DEBT.md` was not updated.

## Known Stubs

None. Stub-pattern scan found only existing test fixtures and typed empty collection initializers, not UI/product stubs introduced by this plan.

## Threat Flags

None. The plan changed existing projection/eval surfaces and tests only; it introduced no new endpoint, auth path, file-access runtime surface, or schema trust boundary.

## TDD Gate Compliance

- RED commits exist for both TDD tasks: `60194f6`, `e13e40e`.
- GREEN commits follow each RED gate: `761e448`, `810208d`.
- No refactor commit was needed.

## Final Git Status

`git status --short` before this summary file was created: clean.

## User Setup Required

None.

## Next Phase Readiness

Plan 58-08 leaves trace/API/SSE/frontend and eval current surfaces canonical. Plan 58-09 can rely on strict classifier output and the new eval/manifest guards when closing remaining docs or validation surfaces.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-08-SUMMARY.md`.
- Task commits found in git history: `60194f6`, `761e448`, `e13e40e`, `810208d`.
- No tracked file deletions occurred in Task 1 or Task 2 commits.

---
*Phase: 58-canonical-graph-cutover-and-no-debt-cleanup*
*Completed: 2026-07-08*
