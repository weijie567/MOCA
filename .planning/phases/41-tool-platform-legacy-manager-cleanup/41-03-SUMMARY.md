---
phase: 41-tool-platform-legacy-manager-cleanup
plan: 03
subsystem: tool-platform
tags: [tool-platform, api-cleanup, tests, architecture]
requires:
  - phase: 41-tool-platform-legacy-manager-cleanup
    provides: 41-02 production seam and fake migration
provides:
  - src/tools/manager.py deleted
  - src.tools public export no longer exposes UnifiedToolManager
  - manager compatibility tests deleted after ToolPlatform coverage migration
  - architecture guard prevents legacy manager imports from returning
affects: [phase-41, TPH-06, public-api, ToolPlatform]
tech-stack:
  added: []
  patterns: [ToolPlatform-only public tool facade, AST import guard for removed compatibility APIs]
key-files:
  created:
    - .planning/phases/41-tool-platform-legacy-manager-cleanup/41-03-SUMMARY.md
  modified:
    - .planning/phases/41-tool-platform-legacy-manager-cleanup/41-03-PLAN.md
    - .planning/phases/41-tool-platform-legacy-manager-cleanup/41-04-PLAN.md
    - src/tools/__init__.py
    - tests/tools/test_tool_platform.py
    - tests/architecture/test_tool_boundaries.py
    - tests/architecture/test_action_draft_boundaries.py
    - tests/architecture/test_phase33_rag_claim_boundaries.py
  deleted:
    - src/tools/manager.py
    - tests/agent/test_tools/test_unified_tool_manager.py
key-decisions:
  - "Keep src.tools.manager_results; it is a result helper, not the legacy manager API."
  - "Use exact legacy-manager import/symbol grep and AST architecture guards so manager_results is not a false positive."
requirements-completed:
  - TPH-06
duration: 16min
completed: 2026-07-02
---

# Phase 41 Plan 03 Summary: Legacy Manager Deletion

The `UnifiedToolManager` compatibility adapter and public export are gone; `ToolPlatform` coverage now owns the remaining behavior.

## Performance

- **Duration:** 16 min
- **Started:** 2026-07-02T06:16:00Z
- **Completed:** 2026-07-02T06:32:00Z
- **Tasks:** 2
- **Files modified:** 7
- **Files deleted:** 2

## Accomplishments

- Added ToolPlatform coverage for catalog-derived investigate visibility and custom descriptor catalogs.
- Deleted `src/tools/manager.py`.
- Removed `UnifiedToolManager` from `src/tools/__init__.py`.
- Deleted the legacy compatibility test file after migration/redundancy review.
- Added architecture guard coverage for removed legacy manager imports/symbols.
- Updated verification commands to distinguish removed `src.tools.manager` from allowed `src.tools.manager_results`.

## Task Commits

1. **Task 1: Migrate non-redundant manager tests to ToolPlatform tests** - `3297aff`
2. **Task 2: Delete manager.py and public export** - `3e1c1da`

## Verification

Passed:

```bash
rg -n "UnifiedToolManager|from src\\.tools\\.manager(\\s|$)|import src\\.tools\\.manager(\\s|$)|src\\.tools\\.manager(\\s|$|\\.)" src tests docs/contract-spec.md --glob '!**/.planning/**'
uv run pytest tests/tools/test_tool_platform.py tests/architecture/test_tool_boundaries.py -q
uv run ruff check src/tools/__init__.py tests/tools/test_tool_platform.py tests/architecture/test_tool_boundaries.py
test ! -e src/tools/manager.py
test ! -e tests/agent/test_tools/test_unified_tool_manager.py
```

Results:

- Exact legacy manager grep: no matches.
- Targeted tests: 46 passed.
- Ruff: all checks passed.
- Deleted files are absent.

## Deviations from Plan

The planned broad grep pattern was narrowed to exact legacy-manager import/symbol matching because `src.tools.manager_results` remains an allowed helper and must not be treated as the removed adapter.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

Ready for 41-04 code review and final verification. Production seams, targeted tests, public exports, and adapter files are now ToolPlatform-only.

---
*Phase: 41-tool-platform-legacy-manager-cleanup*
*Completed: 2026-07-02*
