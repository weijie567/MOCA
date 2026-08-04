---
phase: 41-tool-platform-legacy-manager-cleanup
plan: 01
subsystem: tool-platform
tags: [tool-platform, contract-spec, policy, architecture-tests]
requires:
  - phase: 40-tool-contract-validation-hardening
    provides: tool contract hardening before legacy manager removal
provides:
  - spec no longer promises UnifiedToolManager compatibility
  - _side_effect_allowed lives in src.tools.policy before manager deletion
  - architecture tests no longer import helper from src.tools.manager
affects: [phase-41, TPH-06, ToolPlatform]
tech-stack:
  added: []
  patterns: [ToolPlatform-only contract ownership, policy-owned side-effect helper]
key-files:
  created:
    - .planning/phases/41-tool-platform-legacy-manager-cleanup/41-01-SUMMARY.md
  modified:
    - docs/contract-spec.md
    - src/tools/catalog.py
    - src/tools/manager.py
    - src/tools/policy.py
    - tests/architecture/test_action_draft_boundaries.py
    - tests/architecture/test_tool_boundaries.py
key-decisions:
  - "Do not返工 41-01 code: current implementation already satisfies the source-backed acceptance criteria."
  - "Keep src/tools/manager.py deletion for 41-03; 41-01 only relocates live helper code and removes normative compatibility promises."
requirements-completed:
  - TPH-06
duration: 12min
completed: 2026-07-02
---

# Phase 41 Plan 01 Summary: Spec/API Cleanup and Side-Effect Helper Relocation

`ToolPlatform` is now the sole normative graph-facing tool contract owner in the spec, and `_side_effect_allowed` has a non-legacy home in `src.tools.policy`.

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-02T05:35:00Z
- **Completed:** 2026-07-02T05:47:53Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Removed all `UnifiedToolManager` references from `docs/contract-spec.md` and the declaration-only catalog error text.
- Moved `_side_effect_allowed` from `src/tools/manager.py` to `src/tools/policy.py`.
- Updated architecture tests to import the helper from policy and removed the manager-specific boundary test that directly read `src/tools/manager.py`.
- Preserved `src/tools/manager.py` and `src/tools/__init__.py` for 41-03; no early deletion or export cleanup happened in this plan.

## Task Commits

1. **Task 1: Update spec and catalog wording away from UnifiedToolManager** - `f2a22c5`
2. **Task 2: Move _side_effect_allowed to policy.py** - `4078ab9`

## Files Created/Modified

- `docs/contract-spec.md` - Replaces legacy manager compatibility wording with ToolPlatform/ToolCatalog ownership.
- `src/tools/catalog.py` - Declaration-only execution message now points callers to `ToolPlatform`.
- `src/tools/policy.py` - New home for `_side_effect_allowed`.
- `src/tools/manager.py` - Helper removed; adapter class left in place for 41-03.
- `tests/architecture/test_action_draft_boundaries.py` - Helper import and source assertion now target policy.
- `tests/architecture/test_tool_boundaries.py` - Removed the manager-specific direct-file import boundary test.

## Verification

Passed:

```bash
rg -n "UnifiedToolManager" docs/contract-spec.md src/tools/catalog.py
git diff -- src/tools/contracts.py
uv run pytest tests/architecture/test_action_draft_boundaries.py tests/architecture/test_tool_boundaries.py -q
uv run ruff check src/tools/policy.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_tool_boundaries.py
git diff -- src/tools/contracts.py src/tools/__init__.py
```

Results:

- `UnifiedToolManager` has no matches in `docs/contract-spec.md` or `src/tools/catalog.py`.
- `src/tools/contracts.py` and `src/tools/__init__.py` have no diff.
- Architecture tests: 23 passed, 1 warning.
- Ruff: all checks passed.

## Deviations from Plan

None - execution stayed within the 41-01 boundary. A later plan-review comment correctly noted the original 41-01 plan text under-specified the five spec references; the implementation already removed all references, and the plan text was corrected after execution.

## Issues Encountered

No product-code issue. The only follow-up was plan hygiene: 41-03/41-04 now explicitly carry the remaining review feedback for manager deletion, descriptor-filter coverage migration, and Claude light closure review.

## User Setup Required

None.

## Next Phase Readiness

Ready for 41-02. The legacy manager file still exists, but it no longer owns `_side_effect_allowed` and the spec no longer promises compatibility. 41-02 can migrate production seams and manager-shaped fakes before 41-03 deletes the adapter.

---
*Phase: 41-tool-platform-legacy-manager-cleanup*
*Completed: 2026-07-02*
