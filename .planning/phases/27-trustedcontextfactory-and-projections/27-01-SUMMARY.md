---
phase: 27-trustedcontextfactory-and-projections
plan: 27-01
subsystem: testing
tags:
  - trusted-context
  - projections
  - red-tests
  - pytest
  - platform-boundaries
requires:
  - phase: 26-architecture-contract-baseline
    provides: normative TrustedContext, MerchantScopeV1, projection, and module ownership contracts
provides:
  - Wave 0 RED tests for TrustedContext and MerchantScopeV1 contracts
  - Wave 0 RED tests for service-safe projections and AgentState identity projections
  - RED seam assertions for search, agent-runs, investigate, tool manager, and knowledge scope paths
  - Static boundary tests for trusted-context ownership and prompt projector isolation
affects:
  - phase-27-02-platform-trusted-context-contracts
  - phase-27-03-current-seam-migrations
tech-stack:
  added: []
  patterns:
    - contract-led RED pytest coverage
    - static architecture boundary tests
    - top-level planned-symbol imports for RED collection failures
key-files:
  created:
    - tests/platform/test_trusted_context.py
    - tests/platform/test_trusted_context_factory.py
    - tests/platform/test_merchant_scope.py
    - tests/platform/test_context_projections.py
    - tests/agent/test_intent_policy_registry.py
    - tests/architecture/test_trusted_context_boundaries.py
  modified:
    - tests/test_search_integration.py
    - tests/test_agent_runs_api.py
    - tests/agent/test_nodes/test_investigate.py
    - tests/agent/test_tools/test_unified_tool_manager.py
    - tests/knowledge/test_tenant_scope.py
key-decisions:
  - "27-01 remains RED-only by design: planned production symbols are imported but no src/ files are edited."
  - "Seam integration tests use top-level src.platform imports so current failures are deterministic missing planned production modules, not local database setup."
patterns-established:
  - "TrustedContext contract tests assert exact canonical fields and reject projection-local metadata."
  - "Projection tests assert request_id, effective_at, channel, policy/model/tool versions, artifact refs, and current_run_id stay local or compatibility-only."
  - "Current seam tests encode factory/projection consumption before the implementation lands in 27-02 and 27-03."
requirements-completed:
  - APF-03
  - APF-04
duration: 9 min
completed: 2026-06-23
---

# Phase 27 Plan 01: Wave 0 Trusted Context RED Tests Summary

**Contract-led RED pytest coverage for TrustedContextFactory, MerchantScopeV1, safe projections, registries, and current context-construction seams**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-22T16:39:58Z
- **Completed:** 2026-06-22T16:48:55Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments

- Added platform RED tests for exact `TrustedContext`, `MerchantScopeV1`, factory trusted-source behavior, projection-local metadata, and AgentState identity projection.
- Added RED registry and architecture tests for read-only intent/slot policy wrappers, trusted-context ownership, prompt projector isolation, and current direct-construction seam migration.
- Added seam RED assertions for `/api/v1/search`, `/api/v1/agent-runs`, `investigate`, `UnifiedToolManager`, and knowledge tenant-scope behavior.
- Confirmed this plan changed tests only; no production files under `src/` were modified.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add RED platform contract, projection, registry, and boundary tests** - `c3df370` (test)
2. **Task 2: Add RED seam integration assertions for current context construction paths** - `9fa206c` (test)

## Files Created/Modified

- `tests/platform/test_trusted_context.py` - Canonical `TrustedContext` field set, schema version, and projection-local field rejection.
- `tests/platform/test_trusted_context_factory.py` - Factory trusted-source and no user/LLM override expectations.
- `tests/platform/test_merchant_scope.py` - `MerchantScopeV1` schema, deny-all, wildcard, all-dimensions, and invalid-value tests.
- `tests/platform/test_context_projections.py` - Tool, knowledge, memory, approval, replay, intent, and AgentState projection tests.
- `tests/agent/test_intent_policy_registry.py` - RED tests for read-only intent and slot policy registries.
- `tests/architecture/test_trusted_context_boundaries.py` - Static ownership, projector isolation, and seam migration boundary tests.
- `tests/test_search_integration.py` - RED search route assertion for factory-derived `KnowledgeContext` and request override rejection.
- `tests/test_agent_runs_api.py` - RED graph config assertion for canonical `trusted_context.v1` plus legacy compatibility.
- `tests/agent/test_nodes/test_investigate.py` - RED assertion that tool calls use trusted config, not AgentState permission/scope authority.
- `tests/agent/test_tools/test_unified_tool_manager.py` - RED assertion for `project_to_tool_context` compatibility with invocation.
- `tests/knowledge/test_tenant_scope.py` - RED assertion that factory-projected knowledge scope preserves deny-before-query behavior.

## Decisions Made

- Kept this plan strictly RED-only because the plan explicitly forbids production changes under `src/`.
- Used top-level planned-symbol imports in seam tests to produce deterministic missing-module RED failures until `src.platform` lands.
- Preserved existing integration test fixtures and added narrow assertions instead of rewriting existing test structure.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Pytest failures are expected RED failures from missing planned production symbols:

- `ModuleNotFoundError: No module named 'src.platform'`
- `ImportError: cannot import name 'IntentPolicyRegistry' from 'src.agent.intent_policy'`

## Verification

- `bash -lc 'set +e; uv run pytest tests/platform/test_trusted_context.py tests/platform/test_trusted_context_factory.py tests/platform/test_merchant_scope.py tests/platform/test_context_projections.py tests/agent/test_intent_policy_registry.py tests/architecture/test_trusted_context_boundaries.py -q; status=$?; test "$status" -ne 0'` passed the RED wrapper.
- `uv run ruff check tests/platform tests/agent/test_intent_policy_registry.py tests/architecture/test_trusted_context_boundaries.py` passed.
- `bash -lc 'set +e; uv run pytest tests/test_search_integration.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py -q; status=$?; test "$status" -ne 0'` passed the RED wrapper.
- `uv run ruff check tests/test_search_integration.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/knowledge/test_tenant_scope.py` passed.
- `git diff --name-only c3df370^..HEAD -- src` returned no files.

## Known Stubs

None. Stub-pattern scan only matched intentional empty lists, `None` defaults, and fixture values inside tests.

## TDD Gate Compliance

This is a RED-only Wave 0 plan. Both task commits are `test(27-01)` commits by design; there is no GREEN implementation commit because production files under `src/` were explicitly out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `27-02-PLAN.md` to implement `src.platform.trusted_context`, `src.platform.context_projections`, and read-only intent/slot registries against the RED tests. `27-03-PLAN.md` must migrate current search, agent-run, node, tool-manager, and knowledge seams so the same tests run green without the RED wrapper.

## Self-Check: PASSED

- Found SUMMARY and key created/modified test files on disk.
- Found task commits `c3df370` and `9fa206c` in git log.
- Confirmed no production files under `src/` changed in this plan.

---
*Phase: 27-trustedcontextfactory-and-projections*
*Completed: 2026-06-23*
