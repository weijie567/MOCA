---
phase: 37-tool-declaration-runtime-policy-internal-consolidation
plan: 01
subsystem: tools
tags: [tool-catalog, unified-tool-manager, drift-guard, pytest, ruff]

requires: []
provides:
  - single-source tool declaration rows in src/tools/catalog.py
  - derived identifier schema compatibility map
  - catalog-derived investigate tool filtering in UnifiedToolManager
  - registry/name/schema drift tests for catalog and manager
affects: [phase-37, phase-38, tool-platform, tool-catalog, unified-tool-manager]

tech-stack:
  added: []
  patterns:
    - frozen internal declaration rows feeding ToolDescriptor creation
    - catalog helper feeding planner-visible investigate tool selection

key-files:
  created:
    - .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-01-SUMMARY.md
  modified:
    - src/tools/catalog.py
    - src/tools/manager.py
    - tests/tools/test_catalog.py
    - tests/agent/test_tools/test_unified_tool_manager.py

key-decisions:
  - "Keep _IDENTIFIER_SCHEMAS as a private compatibility surface, but derive it from _TOOL_DECLARATIONS."
  - "Remove manager.INVESTIGATE_TOOL_NAMES after local review confirmed it was an unused internal compatibility value."
  - "Route UnifiedToolManager.descriptors(\"investigate\") through catalog.investigate_tool_names(...) so manager and tests share the same derived helper."

patterns-established:
  - "Tool declaration edits should happen in _TOOL_DECLARATIONS, with descriptor construction and compatibility maps derived from that table."
  - "Planner-visible investigate tools are identified through catalog.investigate_tool_names(...), not by duplicated manager/test predicates."

requirements-completed: [TPH-03]

duration: 6 min
completed: 2026-07-02
---

# Phase 37 Plan 01: Registry Single-Source Summary

**Tool declarations now flow from one catalog declaration table into descriptor schemas and manager investigate visibility.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-02T00:06:52Z
- **Completed:** 2026-07-02T00:12:37Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added drift guards that compare `_IDENTIFIER_SCHEMAS` to `ToolCatalog().descriptors()` and preserve generic `{"type": "object"}` output schemas for Phase 37.
- Replaced the test-only hand-maintained investigate tool set with a helper derived from `ToolCatalog().descriptors()`.
- Introduced `_ToolDeclaration` and `_TOOL_DECLARATIONS` as the single internal declaration table for the nine current catalog entries.
- Changed manager investigate filtering to call `catalog.investigate_tool_names(self._descriptors.values())` instead of keeping its own name set or inline predicate.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add registry and manager drift tests** - `dee1556` (test)
2. **Task 2: Implement single-source declaration rows and catalog-derived investigate filtering** - `0030380` (refactor)
3. **Post-review cleanup: Remove unused manager tool-name constant** - `38db83c` (refactor)
4. **Post-review fix: Route manager investigate discovery through catalog helper** - `ff72c2d` (fix)

## Files Created/Modified

- `src/tools/catalog.py` - Adds `_ToolDeclaration`, `_TOOL_DECLARATIONS`, derived `_IDENTIFIER_SCHEMAS`, derived descriptor construction, and `investigate_tool_names(...)`.
- `src/tools/manager.py` - Removes the literal investigate tool set and delegates investigate descriptor selection to `investigate_tool_names(...)`.
- `tests/tools/test_catalog.py` - Adds schema/output drift coverage and uses the production `investigate_tool_names(...)` helper.
- `tests/agent/test_tools/test_unified_tool_manager.py` - Replaces the module-level literal investigate set with the production helper and guards manager/helper wiring.

## Decisions Made

- Kept `_IDENTIFIER_SCHEMAS` because tests and local compatibility surfaces still reference it, but made it derived only.
- Removed `INVESTIGATE_TOOL_NAMES` from `manager.py` after local review found no references outside its own definition.
- Fixed a post-review TPH-03 gap where manager and tests still duplicated the investigate-selection predicate instead of consuming `investigate_tool_names(...)`.
- Did not change `ToolDescriptor`, `ToolResultV2`, `ToolCallContext`, `ToolPolicyDecision`, `ToolViewV1`, or `ToolInvocationOutcome` fields.
- Did not implement real per-tool output schemas; all descriptors still use `_GENERIC_OBJECT_SCHEMA`.

## Deviations from Plan

A post-review issue showed the first implementation did not fully meet the TPH-03 single-source intent: `investigate_tool_names(...)` existed but manager/tests were not all consuming it. This has been fixed in `ff72c2d`.

## Issues Encountered

- The Task 1 TDD command passed before Task 2 because the pre-existing duplicated schema/name values were already data-consistent. The structural refactor was still required and completed because production still had duplicated declaration sources.
- Post-review TPH-03 wiring gap: manager had no literal name set, but still kept an inline investigate predicate and tests had local helper copies. The fix routes manager/tests through `catalog.investigate_tool_names(...)` and adds a monkeypatch guard for the manager call.
- The wave-level full relevant suite could not complete because local PostgreSQL was not accepting connections on `localhost:5432`; 61 tests passed before 14 DB-backed fixture setup errors. This was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `uv run pytest tests/tools/test_catalog.py tests/agent/test_tools/test_unified_tool_manager.py -q` -> `41 passed, 1 warning`
- `uv run ruff check src/tools/catalog.py src/tools/manager.py tests/tools/test_catalog.py tests/agent/test_tools/test_unified_tool_manager.py` -> passed
- Post-review cleanup check: `uv run pytest tests/tools/test_catalog.py tests/agent/test_tools/test_unified_tool_manager.py -q` -> `41 passed, 1 warning`; `uv run ruff check src/tools/manager.py tests/agent/test_tools/test_unified_tool_manager.py` -> passed
- Post-review TPH-03 helper wiring check: `uv run pytest tests/tools/test_catalog.py tests/agent/test_tools/test_unified_tool_manager.py -q` -> `42 passed, 1 warning`; `uv run ruff check src/tools/manager.py tests/tools/test_catalog.py tests/agent/test_tools/test_unified_tool_manager.py` -> passed
- `rg -n '"get_order"|"search_sop"|INVESTIGATE_TOOL_NAMES = \{' src/tools/manager.py` -> no matches
- `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py -q` -> blocked by local PostgreSQL connection refusal; not a product-code failure signal

## User Setup Required

None - no external service configuration required for 37-01 itself. Local PostgreSQL must be running before the Phase 37 full relevant suite can be marked fully green.

## Next Phase Readiness

Ready for `37-02-PLAN.md`. The consolidated catalog declaration table gives Phase 38 a stable place to replace generic output schemas later. Before final Phase 37 verification, rerun the full relevant suite with local PostgreSQL available.

---
*Phase: 37-tool-declaration-runtime-policy-internal-consolidation*
*Completed: 2026-07-02*
