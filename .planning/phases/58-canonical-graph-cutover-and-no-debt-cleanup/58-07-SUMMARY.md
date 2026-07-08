---
phase: 58-canonical-graph-cutover-and-no-debt-cleanup
plan: 07
subsystem: testing
tags: [canonical-graph, architecture-tests, integration-tests, static-guards, tdd]

requires:
  - phase: 58-06
    provides: canonical routing test cleanup before integration and architecture guard retargeting
provides:
  - canonical recommendation_generation and risk_gate integration patch seams
  - static wrapper resurrection guards for current src/tests/scripts/eval references
  - strict legacy-hit classifier guard that permits classified historical rows
affects: [CAGM-09, canonical-agent-graph, architecture-guards, integration-coverage]

tech-stack:
  added: []
  patterns:
    - current tests construct deleted legacy paths from path parts instead of preserving literal resurrection strings
    - RED/GREEN test retargeting commits for canonical graph cleanup

key-files:
  created:
    - .planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-07-SUMMARY.md
  modified:
    - tests/agent/test_phase22_recommendation_integration.py
    - tests/agent/test_phase22_action_boundary.py
    - tests/test_interception_rate.py
    - tests/knowledge/test_facade_integration.py
    - tests/agent/test_memory_evidence_boundary.py
    - tests/architecture/test_phase32_static_contract.py
    - tests/architecture/test_memory_contract_delta.py
    - tests/architecture/test_phase33_rag_claim_boundaries.py
    - eval/replay/dev-contract-manifest.v1.json
    - tests/agent/test_memory_context_load.py
    - tests/agent/test_nodes/test_contextual_intent_resolve.py
    - tests/agent/test_nodes/test_session_context_load.py
    - tests/agent/test_nodes/test_slot_resolution_gate.py
    - tests/architecture/test_canonical_graph_baseline.py
    - tests/knowledge/test_phase21_boundaries.py
    - tests/test_approval_gate.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

key-decisions:
  - "Use canonical module aliases `recommendation_generation_module` and `risk_gate_module` in current integration tests."
  - "Keep deleted wrapper/file deletion tests without contiguous legacy path strings by constructing paths from parts."
  - "Strict legacy-hit classification remains keyed to active_runtime/current_docs/unclassified counts, not `total_hits == 0`."

patterns-established:
  - "Current-reference guards scan `src`, `tests`, `scripts`, and `eval` for deleted wrapper imports and legacy direct test paths."
  - "Historical graph-name rows may remain only when classified; current imports and command paths must be canonical."

requirements-completed: [CAGM-09]

duration: 14min
completed: 2026-07-08
---

# Phase 58 Plan 07: Canonical Integration and Architecture Guard Cleanup Summary

**Canonical graph integration tests now patch `recommendation_generation` and `risk_gate`, while architecture guards block deleted wrapper imports, legacy direct test paths, and active Phase 52-57 alias markers.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-07-08T02:36:32Z
- **Completed:** 2026-07-08T02:49:13Z
- **Tasks:** 2
- **Files modified:** 17 before summary

## Accomplishments

- Retargeted recommendation, action-boundary, interception, knowledge facade, and memory evidence tests to canonical current seams and data.
- Added static architecture guards that scan current `src`, `tests`, `scripts`, and `eval` references for deleted wrapper imports and legacy direct test paths.
- Removed active Phase 56/57 compatibility-alias marker expectations from plan-owned architecture coverage and preserved strict classifier semantics without requiring zero total legacy hits.

## Task Commits

1. **Task 1 RED:** `f98365a` - `test(58-07): add failing canonical integration seam guards`
2. **Task 1 GREEN:** `7db367e` - `feat(58-07): retarget integration coverage to canonical seams`
3. **Task 2 RED:** `4fc89d9` - `test(58-07): add failing static wrapper resurrection guards`
4. **Task 2 GREEN:** `da028f6` - `feat(58-07): retarget architecture guards to canonical contracts`

## Files Created/Modified

- `tests/agent/test_phase22_recommendation_integration.py` - canonical recommendation module patch guard and alias.
- `tests/agent/test_phase22_action_boundary.py` - canonical risk module patch guard and `risk_gate` resume-route test data.
- `tests/test_interception_rate.py` - canonical `risk_gate_module` patch seam guard.
- `tests/knowledge/test_facade_integration.py` - canonical recommendation module patch seam.
- `tests/agent/test_memory_evidence_boundary.py` - canonical `recommendation_generation` material-claim source data.
- `tests/architecture/test_phase33_rag_claim_boundaries.py` - current-reference scans, legacy alias marker guard, and strict classifier semantics guard.
- `tests/architecture/test_phase32_static_contract.py` and `tests/architecture/test_memory_contract_delta.py` - canonical-current architecture expectations.
- `eval/replay/dev-contract-manifest.v1.json` and related current tests - stale direct test path references retargeted or constructed from parts.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - recorded non-blocking local tool/validation warnings and the Task 2 stale static assertion failure.

## Decisions Made

- Canonical tests use `recommendation_generation_module` and `risk_gate_module`; legacy-flavored aliases are now guarded against.
- Current deletion guards no longer keep contiguous deleted wrapper/test paths in source; paths are constructed from parts so static scans can enforce no current references.
- The Phase 58 classifier strict gate remains focused on active runtime, current-docs authority, and unclassified rows. Classified historical rows are allowed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Retargeted stale references outside the initial plan-owned file list**
- **Found during:** Task 2 final static guard work
- **Issue:** The required no-hit scans covered all `src`, `tests`, `scripts`, and `eval`, but stale direct test paths and wrapper path strings remained in `eval/replay/dev-contract-manifest.v1.json`, current wrapper-deletion tests, `tests/knowledge/test_phase21_boundaries.py`, and negative architecture assertions.
- **Fix:** Retargeted manifests to canonical tests and converted current deletion guards to path-part construction.
- **Files modified:** `eval/replay/dev-contract-manifest.v1.json`, `tests/agent/test_nodes/test_contextual_intent_resolve.py`, `tests/agent/test_nodes/test_session_context_load.py`, `tests/agent/test_nodes/test_slot_resolution_gate.py`, `tests/agent/test_memory_context_load.py`, `tests/knowledge/test_phase21_boundaries.py`, `tests/test_approval_gate.py`, `tests/architecture/test_canonical_graph_baseline.py`
- **Verification:** Final no-hit `rg` scans passed.
- **Committed in:** `da028f6`

**2. [Rule 1 - Bug] Fixed stale Phase 32 architecture assertion against deleted `classify_intent.py`**
- **Found during:** Task 2 RED verification
- **Issue:** `test_phase32_consumers_do_not_reference_direct_policy_constants` tried to read deleted `src/agent/nodes/classify_intent.py`, causing `FileNotFoundError`.
- **Fix:** Retargeted the check to canonical `src/agent/nodes/contextual_intent_resolve.py`.
- **Files modified:** `tests/architecture/test_phase32_static_contract.py`
- **Verification:** Focused architecture pytest passed.
- **Committed in:** `da028f6`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both were necessary to satisfy the plan's current-reference cleanup and final verification commands. No production data rewrite or runtime graph change was made.

## Issues Encountered

- Task 1 validation emitted existing non-blocking local warnings and a repeated Perl locale warning; both were recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Task 2 RED exposed stale architecture coverage against deleted paths; fixed and recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- No architecture-debt entry was added because this plan retargeted tests/guards only and did not discover or change core tool/RAG/memory/intent subsystem design debt.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/test_interception_rate.py tests/knowledge/test_facade_integration.py tests/agent/test_memory_evidence_boundary.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_memory_contract_delta.py tests/architecture/test_phase33_rag_claim_boundaries.py -q --tb=short` - `79 passed, 1 skipped, 8 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/test_interception_rate.py tests/knowledge/test_facade_integration.py tests/agent/test_memory_evidence_boundary.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_memory_contract_delta.py tests/architecture/test_phase33_rag_claim_boundaries.py` - passed
- No-hit wrapper import scan over `src tests scripts eval` - passed
- No-hit legacy direct test path scan over `src tests scripts eval` - passed
- `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict` - passed with `active_runtime_legacy=0`, `current_docs_legacy_authority=0`, `unclassified_rows=0`
- `git diff --check` - passed

## Known Stubs

None. Stub-pattern scan only found existing test fixture empty lists/dicts and historical validation-log command snippets; none are product/UI stubs introduced by this plan.

## Threat Flags

None. The plan changed tests, manifests, and planning logs only; it introduced no new endpoints, auth paths, file-access runtime surface, or schema trust boundary.

## User Setup Required

None.

## Next Phase Readiness

Plan 58-07 leaves current integration and architecture coverage aligned to canonical graph modules. Plan 58-08 can rely on static guards to catch resurrection of deleted wrapper imports and legacy direct command paths.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/58-canonical-graph-cutover-and-no-debt-cleanup/58-07-SUMMARY.md`
- Task commits found in git history: `f98365a`, `7db367e`, `4fc89d9`, `da028f6`

---
*Phase: 58-canonical-graph-cutover-and-no-debt-cleanup*
*Completed: 2026-07-08*
