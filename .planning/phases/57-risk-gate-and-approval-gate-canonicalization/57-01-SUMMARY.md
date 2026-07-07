---
phase: 57-risk-gate-and-approval-gate-canonicalization
plan: 01
subsystem: agent-graph-risk
tags: [langgraph, risk-gate, approval, canonical-agent-graph, compatibility]

requires:
  - phase: 50-canonical-agent-graph-migration-spec-and-guardrails
    provides: canonical graph migration charter and temporary compatibility policy
  - phase: 56-recommendation-generation-and-rag-claim-status-alignment
    provides: claim_verify action route gate and Phase 57 risk-node handoff
provides:
  - canonical risk_gate callable for current-run risk/action identity
  - shared risk/action implementation with output and trace identity hooks
  - Phase 58-scoped assess_risk_and_approval compatibility metadata
  - node-level tests for canonical and legacy identity split
affects: [phase-57, phase-57-02, phase-58, canonical-agent-graph, approval-boundary]

tech-stack:
  added: []
  patterns:
    - canonical node wrapper delegating to shared implementation
    - Phase 58-scoped compatibility alias metadata
    - identity-hooked llm_outputs, trace_steps, and node_errors

key-files:
  created:
    - src/agent/nodes/risk_gate.py
    - tests/agent/test_nodes/test_risk_gate.py
    - .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-01-SUMMARY.md
  modified:
    - src/agent/nodes/assess_risk_and_approval.py
    - tests/agent/test_nodes/test_assess_risk_and_approval.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Created risk_gate as a canonical wrapper over the existing risk/action implementation rather than moving policy logic between modules."
  - "Kept assess_risk_and_approval importable only as Phase 58-scoped import/test compatibility with explicit alias metadata."
  - "Left active graph registration and router cutover untouched for Plan 57-02."

patterns-established:
  - "Risk node identity hook: shared implementation accepts output_key and trace_node for current-run versus compatibility identity."
  - "Compatibility alias metadata records legacy surface, canonical owner, reason, trace projection, validation tests, and delete phase."

requirements-completed: [CAGM-08]

duration: 7min
completed: 2026-07-07
---

# Phase 57 Plan 01: Risk Gate Callable Summary

**Canonical `risk_gate` callable with shared risk/action policy execution and Phase 58-scoped legacy compatibility**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-07T13:18:31Z
- **Completed:** 2026-07-07T13:25:19Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `src/agent/nodes/risk_gate.py` with canonical `risk_gate(...)` delegation.
- Refactored `assess_risk_and_approval.py` so current-run writes can use `risk_gate` while the legacy wrapper preserves import/test compatibility.
- Locked tests for success, blocked, fail-closed binding, and structured-output fallback identity behavior.
- Recorded `PHASE_57_COMPATIBILITY_ALIAS` with `DELETE_BY_PHASE_58` metadata.

## Task Commits

1. **Task 1 RED: Add canonical and compatibility identity tests** - `e712dcb` (test)
2. **Task 2 GREEN: Implement canonical risk_gate wrapper and explicit legacy metadata** - `686adb0` (feat)

## Files Created/Modified

- `src/agent/nodes/risk_gate.py` - Canonical callable delegating to shared risk/action implementation with `_CANONICAL_NODE = "risk_gate"`.
- `src/agent/nodes/assess_risk_and_approval.py` - Shared implementation helper, identity parameters, compatibility wrapper, and Phase 58 alias metadata.
- `tests/agent/test_nodes/test_risk_gate.py` - Canonical current-run identity tests for success, blocked, fail-closed, and expected-error paths.
- `tests/agent/test_nodes/test_assess_risk_and_approval.py` - Legacy compatibility metadata and wrapper identity tests.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Chinese local validation records for the expected RED failure and corrected GREEN test assertion.

## Decisions Made

- Reused the existing risk/action policy implementation to avoid changing risk semantics in this foundation plan.
- Parameterized `llm_outputs`, trace steps, and `node_errors` through `output_key` / `trace_node`; no active graph/router files changed.
- Did not touch `moca.egg-info/SOURCES.txt` because it is not tracked by git.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected fail-closed identity test assertion**
- **Found during:** Task 2 GREEN verification.
- **Issue:** The new canonical fail-closed test incorrectly expected `llm_outputs["risk_gate"]` to equal the final `risk_assessment`. Existing Phase 34 semantics preserve the original LLM assessment while rewriting final risk state to safe manual review.
- **Fix:** Updated the test to assert original canonical LLM output plus final `manual_review` risk state, while preserving no-legacy identity assertions.
- **Files modified:** `tests/agent/test_nodes/test_risk_gate.py`, `.planning/LOCAL-VALIDATION-ISSUES.md`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_phase22_action_boundary.py -q --tb=short` passed with `40 passed, 1 warning`.
- **Committed in:** `686adb0`

**Total deviations:** 1 auto-fixed bug.
**Impact on plan:** No scope change. The fix aligned the new test with existing fail-closed binding behavior.

## Issues Encountered

- Expected TDD RED failure: `tests/agent/test_nodes/test_risk_gate.py` could not import `src.agent.nodes.risk_gate` before implementation.
- One GREEN test assertion was corrected as documented above.
- `gsd-sdk query roadmap.update-plan-progress "57"` returned `updated: false` / `no matching checkbox found`; ROADMAP Phase 57 progress was patched manually and the SDK mismatch was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- `gsd-sdk query requirements.mark-complete CAGM-08` produced an incomplete Markdown update while the traceability table still said Pending; the checkbox was restored to Pending because 57-01 does not complete the full Phase 57 requirement.

## Known Stubs

None. Static placeholder scan over touched files found no `TODO`, `FIXME`, placeholder, coming-soon, or not-available markers.

## Literal Audit

`src/agent/nodes/assess_risk_and_approval.py` has 5 remaining `assess_risk_and_approval` hits:

- `_LEGACY_NODE = "assess_risk_and_approval"` - legacy wrapper/import-test compatibility.
- `tests/agent/test_nodes/test_assess_risk_and_approval.py` validation-test path - compatibility metadata.
- `async def assess_risk_and_approval(...)` - legacy wrapper/import-test compatibility.
- `_assess_risk_and_approval_with_identity` helper call and definition - shared-helper implementation detail.

No remaining hit is a current-run `llm_outputs`, `trace_steps[*].node`, `node_errors`, active graph registration, or active router destination.

## Threat Flags

None. This plan added a canonical module and identity hook inside the planned risk-node trust boundary; it did not introduce a new network endpoint, auth path, file access path, schema boundary, or active graph route.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q --tb=short` - RED: failed as expected with missing `risk_gate` import.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_phase22_action_boundary.py -q --tb=short` - GREEN and plan-local: `40 passed, 1 warning`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.agent.nodes.risk_gate import risk_gate; print(callable(risk_gate))"` - printed `True`.
- `git diff --name-only HEAD~2..HEAD -- src/agent/graph.py src/agent/routing.py` - no output, confirming active graph registration and router cutover remain Plan 57-02 scope.
- Literal audit command found 5 remaining node-module legacy hits, all classified above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 57-02 can now cut active graph registration, claim routing, architecture baseline, and approval edit rerisk route values to `risk_gate` on top of the canonical callable. Phase 58 still owns final compatibility deletion.

## Self-Check: PASSED

- Found `src/agent/nodes/risk_gate.py`.
- Found `tests/agent/test_nodes/test_risk_gate.py`.
- Found `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-01-SUMMARY.md`.
- Found task commits `e712dcb` and `686adb0`.

---
*Phase: 57-risk-gate-and-approval-gate-canonicalization*
*Completed: 2026-07-07*
