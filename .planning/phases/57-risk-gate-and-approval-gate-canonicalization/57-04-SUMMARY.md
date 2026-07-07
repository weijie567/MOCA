---
phase: 57-risk-gate-and-approval-gate-canonicalization
plan: 04
subsystem: agent-graph-risk-projection
tags: [langgraph, risk_gate, trace-projection, frontend, eval, diagnostics]

requires:
  - phase: 57-03
    provides: active approval resume and persisted retry compatibility normalized to `risk_gate`
provides:
  - current runtime/API/frontend/eval/diagnostic projection for `risk_gate`
  - historical `assess_risk_and_approval -> risk_gate` compatibility projection with Phase 58 deletion markers
  - static guardrails for current-run risk node vocabulary in eval, diagnostics, frontend labels, and route parsing
affects: [phase-57, phase-58, canonical-agent-graph, risk-gate, approval-boundary]

tech-stack:
  added: []
  patterns:
    - graph vocabulary runtime entry plus non-runnable compatibility alias
    - canonical node wrapper patch seam for eval harnesses
    - static source guardrails for current-run vocabulary

key-files:
  created:
    - .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-04-SUMMARY.md
  modified:
    - src/agent/graph_vocabulary.py
    - src/api/routers/agent_runs.py
    - src/agent/nodes/risk_gate.py
    - src/agent/nodes/assess_risk_and_approval.py
    - frontend/src/components/timeline/TimelineStep.tsx
    - scripts/eval_agent.py
    - scripts/diagnose_latency.py
    - tests/architecture/graph_baseline.py
    - tests/architecture/test_canonical_graph_baseline.py
    - tests/agent/test_graph_vocabulary.py
    - tests/agent/test_trace.py
    - tests/test_trace_api.py
    - tests/test_agent_runs_api.py
    - .planning/LOCAL-VALIDATION-ISSUES.md
    - .planning/ARCHITECTURE-DEBT.md

key-decisions:
  - "Treat `risk_gate` as the only current runtime risk node while preserving `assess_risk_and_approval` as a non-runnable historical compatibility alias."
  - "Preserve stored historical risk payload readability without rewriting audit history."
  - "Patch the canonical `src.agent.nodes.risk_gate` module in eval harnesses instead of the legacy implementation module."

patterns-established:
  - "Phase 57 projection closeout: runtime identity entry + labeled historical alias + static current-run source scan."
  - "Canonical wrapper seams: expose patchable `_get_llm` and snapshot persistence wrappers while sharing legacy implementation logic until Phase 58."

requirements-completed: [CAGM-08]

duration: 32m
completed: 2026-07-07
---

# Phase 57 Plan 04: Runtime Projection Closeout Summary

**`risk_gate` is now the current runtime/API/frontend/eval/diagnostic risk node, with legacy `assess_risk_and_approval` retained only as labeled historical projection until Phase 58.**

## Performance

- **Duration:** 32m
- **Started:** 2026-07-07T14:33:28Z
- **Completed:** 2026-07-07T15:05:50Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments

- Added `risk_gate` as a runtime graph vocabulary entry and changed `assess_risk_and_approval` into a non-runnable Phase 57 compatibility alias.
- Updated API/SSE projection so current and historical risk trace steps both project to `target_node_name="risk_gate"` while preserving the original implementation node.
- Updated frontend labels, eval graph contract patching/fake keys/expected sequences, and diagnostic mock reports to use current `risk_gate`.
- Added static guardrails that reject legacy risk-node current-run authority across vocabulary, route maps, frontend labels, eval harnesses, and diagnostics.

## Task Commits

1. **Task 1 RED: graph vocabulary and API trace projection tests** - `a972fb6` (test)
2. **Task 1 GREEN: risk_gate projection vocabulary/API implementation** - `b93ff43` (feat)
3. **Task 2 RED: current-run vocabulary guardrail tests** - `e8aee79` (test)
4. **Task 2 GREEN: frontend/eval/diagnostic current-run surfaces** - `1ad2d29` (feat)

## Files Created/Modified

- `src/agent/graph_vocabulary.py` - Adds `risk_gate` runtime identity and Phase 57 legacy alias metadata.
- `src/api/routers/agent_runs.py` - Adds `risk_gate` API/SSE label and risk payload extraction for current and historical risk nodes.
- `frontend/src/components/timeline/TimelineStep.tsx` - Adds current `risk_gate` label and labels legacy fallback as historical.
- `scripts/eval_agent.py` - Patches/fakes/expected node sequences now use `risk_gate` for current graph contract runs.
- `scripts/diagnose_latency.py` - Diagnostic synthetic risk step now uses `risk_gate`.
- `src/agent/nodes/risk_gate.py` and `src/agent/nodes/assess_risk_and_approval.py` - Expose canonical patch seams while preserving shared risk implementation and legacy import behavior.
- `tests/architecture/graph_baseline.py` - Static route parser now resolves module-level string constants.
- `tests/architecture/test_canonical_graph_baseline.py` - Adds current-run risk vocabulary guardrails.
- `tests/agent/test_graph_vocabulary.py`, `tests/agent/test_trace.py`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py` - Add current and historical trace projection coverage.
- `.planning/LOCAL-VALIDATION-ISSUES.md` and `.planning/ARCHITECTURE-DEBT.md` - Record verified validation findings and architecture-debt closure.

## Decisions Made

- Legacy `assess_risk_and_approval` remains readable in stored traces but is not runnable/current vocabulary authority.
- Eval graph contract tests patch `src.agent.nodes.risk_gate` so CI exercises the canonical current node.
- Frontend keeps the old label only as a clearly marked historical display fallback with `DELETE_BY_PHASE_58`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking static parser issue] Route constant returns were unsupported**
- **Found during:** Task 2 RED verification.
- **Issue:** `test_router_return_values_are_covered_by_registered_path_maps` failed on `route_after_approval` because `tests/architecture/graph_baseline.py` could not parse `return CANONICAL_RISK_ROUTE`.
- **Fix:** Added module-level string constant extraction and threaded it through router return collection.
- **Files modified:** `tests/architecture/graph_baseline.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/test_agent_runs_api.py -q --tb=short` -> `134 passed, 1 skipped, 1 warning`
- **Committed in:** `1ad2d29`

**2. [Rule 3 - Blocking eval seam issue] Canonical risk wrapper was not patchable by eval harness**
- **Found during:** Task 2 GREEN implementation.
- **Issue:** The eval harness needed to patch the current `risk_gate` module, but the wrapper delegated directly into the legacy module without local `_get_llm` or snapshot persistence seams.
- **Fix:** Added patchable wrapper seams in `risk_gate.py` and lazy dependency injection in the shared implementation so legacy monkeypatches still work.
- **Files modified:** `src/agent/nodes/risk_gate.py`, `src/agent/nodes/assess_risk_and_approval.py`, `scripts/eval_agent.py`
- **Verification:** focused risk-node tests -> `20 passed, 1 warning`; plan guardrail command -> `134 passed, 1 skipped, 1 warning`
- **Committed in:** `1ad2d29`

**3. [Rule 1 - Test expectation correction] Guardrail over-required risk_gate for a low-risk synthetic category**
- **Found during:** Task 2 GREEN verification.
- **Issue:** The new static test required `risk_gate` for `compensation_suggestion` even when the synthetic eval case set `expected_approval_required=False`.
- **Fix:** Kept the all-sequence legacy rejection, required `risk_gate` for the approval-required base case and `approval_approved` category.
- **Files modified:** `tests/architecture/test_canonical_graph_baseline.py`
- **Verification:** Task 2 command passed with `134 passed, 1 skipped, 1 warning`.
- **Committed in:** `1ad2d29`

**Total deviations:** 3 auto-fixed (1 Rule 1, 2 Rule 3)
**Impact on plan:** All fixes were required to complete the planned current-run vocabulary closeout; no new product scope was added.

## Issues Encountered

- Task 1 RED failed as expected on missing `risk_gate` vocabulary/API projection: `8 failed, 167 passed, 1 warning`.
- Task 2 RED failed as expected on frontend/eval/diagnostic legacy risk-node surfaces, plus the parser limitation above: `4 failed, 130 passed, 1 skipped, 1 warning`.
- Initial static closeout scan failed because the ad hoc scan read `diagnose_latency.mock_report()["steps"]`; the actual key is `nodes`. The corrected scan passed.
- `gsd-sdk query roadmap.update-plan-progress "57"` still could not match the Phase 57 roadmap checkbox, and `state.update-progress` overcounted aggregate completion because Phase 50 has a spec-only summary while 57-05 is still pending. ROADMAP and STATE were manually corrected to Phase 57 `4/5` and aggregate `68/69` / `99%`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py -q --tb=short` -> `175 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/test_agent_runs_api.py -q --tb=short` -> `134 passed, 1 skipped, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q --tb=short` -> `20 passed, 1 warning`
- `npm --prefix frontend run build` -> pass
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c '...'` static closeout -> `phase57-risk-gate-static-closeout: pass`

## TDD Gate Compliance

- RED gate commits exist: `a972fb6`, `e8aee79`.
- GREEN gate commits exist after RED gates: `b93ff43`, `1ad2d29`.
- No refactor-only commit was needed.

## Known Stubs

None. Stub-pattern scan hits are existing optional API fields and test/eval fixtures (`None`, empty lists, empty dict payloads), not user-facing placeholder data introduced by this plan.

## Threat Flags

None. This plan touched existing trace projection, frontend display, eval, diagnostic, and static-test surfaces; it did not add new network endpoints, auth paths, file access patterns, or schema trust boundaries beyond the planned threat model mitigations.

## User Setup Required

None.

## Next Phase Readiness

Phase 58 can now focus on no-debt cleanup: remove remaining `assess_risk_and_approval` wrapper/import/test/historical display fallback surfaces after compatibility deletion is explicitly in scope.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-04-SUMMARY.md`
- Task commits found: `a972fb6`, `b93ff43`, `e8aee79`, `1ad2d29`

---
*Phase: 57-risk-gate-and-approval-gate-canonicalization*
*Completed: 2026-07-07*
