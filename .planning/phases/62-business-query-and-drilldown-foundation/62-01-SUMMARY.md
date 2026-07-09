---
phase: 62-business-query-and-drilldown-foundation
plan: 01
subsystem: business-query-foundation
tags: [business-query, registry, metric-routing, tool-catalog, tdd]

requires:
  - phase: 61-product-experience-fixes
    provides: Phase 61 `business_metric_query` routing, clarification, and runtime compatibility behavior
provides:
  - Immutable business-query registry for operations, resources, metrics, time presets, status filters, fields, sorts, parser aliases, and compatibility mappings
  - Registry-derived metric slot policy, deterministic parser, prompt enum text, and ToolCatalog metric schema enums
  - Static drift tests preventing agent/catalog metric source-of-truth literals from returning
affects: [business-query-runtime, drilldown, tool-platform-policy, agent-routing, tool-catalog, phase-62]

tech-stack:
  added: []
  patterns:
    - Frozen dataclass descriptors with read-only registry mappings
    - Registry-derived parser/routing/catalog constants with static drift guards

key-files:
  created:
    - src/business/query/__init__.py
    - src/business/query/registry.py
    - tests/business/test_business_query_registry.py
  modified:
    - .planning/ARCHITECTURE-DEBT.md
    - src/agent/routing.py
    - src/agent/nodes/contextual_intent_resolve.py
    - src/agent/nodes/slot_resolution_gate.py
    - src/agent/nodes/investigate.py
    - src/agent/prompts.py
    - src/tools/catalog.py
    - tests/agent/test_required_slots.py
    - tests/agent/test_nodes/test_contextual_intent_resolve.py
    - tests/agent/test_nodes/test_slot_resolution_gate.py
    - tests/agent/test_nodes/test_investigate.py
    - tests/tools/test_catalog.py

key-decisions:
  - "Keep `business_metric_query` as the Phase 61 compatibility tool surface while deriving its metric ids, time presets, status filters, parser aliases, and schema enums from `BUSINESS_QUERY_REGISTRY`."
  - "Model the registry as query-shape allowlist data only; runtime execution, projection formatting, authority scope, cursor tokens, SQL, and UI copy remain outside the registry."
  - "Keep Phase 61 compatibility resource mapping for existing metric outputs, including `coupon_record_count` mapping to `action_draft` while the Phase 62 query resource remains `coupon_record`."
patterns-established:
  - "Business-query descriptors are frozen data objects exposed through read-only registry helpers."
  - "Agent/parser/catalog surfaces consume registry helpers and use static tests to catch reintroduced local source-of-truth literals."
requirements-completed: [BQ-62-01, BQ-62-02]

duration: 26m 41s
completed: 2026-07-09
---

# Phase 62 Plan 01: Business Query Registry Foundation Summary

**Immutable business-query registry with registry-derived Phase 61 metric routing, parser, prompt, and ToolCatalog definitions**

## Performance

- **Duration:** 26m 41s
- **Started:** 2026-07-09T12:40:13Z
- **Completed:** 2026-07-09T13:06:54Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments

- Added `BUSINESS_QUERY_REGISTRY` with frozen descriptors for the Phase 62 read taxonomy, resource taxonomy, metric descriptors, time presets, status filters, field allowlists, sort allowlists, parser aliases, and compatibility mappings.
- Replaced duplicated Phase 61 metric id/resource/status/time/parser constants in routing, deterministic parser nodes, prompts, ToolCatalog schema enums, and investigate fallback with registry-derived values.
- Added TDD and static drift tests proving registry immutability, exact taxonomy coverage, `current_snapshot` descriptor ownership, strict ToolCatalog enums, and no reintroduced local source-of-truth literals in the covered agent/catalog surfaces.

## Task Commits

1. **Task 1 RED: Create immutable business-query registry tests** - `1b754a3` (test)
2. **Task 1 GREEN: Create immutable business-query registry** - `e7b7488` (feat)
3. **Task 2 RED: Add registry derivation drift guards** - `084d6fa` (test)
4. **Task 2 GREEN: Derive metric routing from registry** - `8291e57` (feat)

**Plan metadata:** included in the final docs/state commit for this plan

## Files Created/Modified

- `src/business/query/__init__.py` - Exports the registry API for business-query consumers.
- `src/business/query/registry.py` - Defines immutable descriptors and `BUSINESS_QUERY_REGISTRY`.
- `src/agent/routing.py` - Derives supported metrics, resource mapping, status policy, and time policy from the registry.
- `src/agent/nodes/contextual_intent_resolve.py` - Uses registry parser aliases and metric descriptors for deterministic metric candidate slots and pending metric time answers.
- `src/agent/nodes/slot_resolution_gate.py` - Uses registry parser aliases and time preset aliases for deterministic metric slot extraction.
- `src/agent/nodes/investigate.py` - Uses registry metric/time policy for deterministic metric fallback tool calls.
- `src/agent/prompts.py` - Derives metric/resource/time enum text in slot extraction prompts from the registry.
- `src/tools/catalog.py` - Derives `query_business_metric` metric and time preset schema enums from the registry while preserving strict schemas.
- `tests/business/test_business_query_registry.py` - Covers registry taxonomy, immutability, data-only constraints, metric compatibility, and parser metadata.
- `tests/agent/test_required_slots.py` - Guards routing source-of-truth derivation from the registry.
- `tests/agent/test_nodes/test_contextual_intent_resolve.py` - Guards contextual parser and prompt enum derivation.
- `tests/agent/test_nodes/test_slot_resolution_gate.py` - Guards slot-resolution parser derivation.
- `tests/agent/test_nodes/test_investigate.py` - Guards investigate metric fallback derivation.
- `tests/tools/test_catalog.py` - Guards ToolCatalog enum derivation.
- `.planning/ARCHITECTURE-DEBT.md` - Records the verified Phase 62 metric registry migration status and remaining service/runtime boundary risk.

## Decisions Made

- Preserved `query_business_metric` and `business_metric_query` compatibility for Phase 61 instead of introducing the future `business_query` tool in this plan.
- Kept the registry free of SQL, ORM expressions, tenant or merchant authority fields, raw cursor tokens, projection templates, frontend layout facts, and UI copy.
- Left `src/business/service.py` metric runtime branches untouched because service/runtime migration belongs to later Phase 62 BusinessQuerySpec/runtime plans.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Derived investigate metric fallback from registry**
- **Found during:** Task 2 (Derive parser, routing, and catalog constants from registry)
- **Issue:** The plan listed routing, parser nodes, prompts, and ToolCatalog, but `src/agent/nodes/investigate.py` still had a local metric time-policy allowlist for deterministic `query_business_metric` fallback.
- **Fix:** Replaced the local fallback allowlist and `pending_ticket_count` branch with registry metric validation, time preset compatibility checks, and default snapshot preset lookup; added a static guard test.
- **Files modified:** `src/agent/nodes/investigate.py`, `tests/agent/test_nodes/test_investigate.py`, `.planning/ARCHITECTURE-DEBT.md`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q --tb=short` -> `57 passed, 1 warning`; expanded focused suite -> `185 passed, 1 warning`
- **Committed in:** `8291e57`

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Necessary to make the covered agent metric fallback surface consume the registry consistently. No new tool, runtime, schema boundary, or architectural approach was introduced.

## Issues Encountered

- Expected TDD RED failures occurred before implementation:
  - Task 1 RED failed with missing `src.business.query` module.
  - Task 2 RED failed the new static registry-derivation guards.
- No authentication gates, blockers, or unresolved validation failures occurred.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_registry.py -q --tb=short` -> `5 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q --tb=short` -> `57 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_registry.py tests/agent/test_required_slots.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/tools/test_catalog.py tests/agent/test_nodes/test_investigate.py -q --tb=short` -> `185 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_business_query_registry.py tests/agent/test_required_slots.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/tools/test_catalog.py -q --tb=short` -> `128 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/business/query/registry.py src/business/query/__init__.py src/agent/routing.py src/agent/nodes/contextual_intent_resolve.py src/agent/nodes/slot_resolution_gate.py src/agent/nodes/investigate.py src/agent/prompts.py src/tools/catalog.py tests/business/test_business_query_registry.py tests/agent/test_required_slots.py tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_nodes/test_investigate.py tests/tools/test_catalog.py` -> `All checks passed!`
- `rg -n "BUSINESS_QUERY_REGISTRY|BusinessQueryRegistry" src/agent/routing.py src/agent/nodes/contextual_intent_resolve.py src/agent/nodes/slot_resolution_gate.py src/tools/catalog.py` -> registry references found in all required files

## Known Stubs

None. The stub scan only found legitimate empty containers/default values in existing initialization and test assertions; no placeholder UI/data-source stub was introduced.

## Threat Flags

None. No new network endpoint, auth path, file access pattern, schema trust boundary, SQL surface, tenant authority field, merchant-scope field, raw cursor, draft operation, or execute operation was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Later Phase 62 plans can build BusinessQuerySpec schemas, ToolPlatform policy, runtime execution, drilldown state, projection, eval, and UI behavior against `BUSINESS_QUERY_REGISTRY` instead of adding new metric/resource/time/status literals.

Remaining boundary: `src/business/service.py` still owns Phase 61 metric runtime behavior and should be migrated only when the service/runtime plan introduces BusinessQuerySpec execution.

## Self-Check: PASSED

- Created/modified files claimed in this summary exist.
- Task commits found: `1b754a3`, `e7b7488`, `084d6fa`, `8291e57`.
- No unexpected tracked file deletions were detected after task commits.

---
*Phase: 62-business-query-and-drilldown-foundation*
*Completed: 2026-07-09*
