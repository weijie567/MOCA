---
phase: 27-trustedcontextfactory-and-projections
plan: 27-02
subsystem: platform
tags:
  - trusted-context
  - projections
  - merchant-scope
  - intent-policy
  - registries
requires:
  - phase: 27-trustedcontextfactory-and-projections
    provides: Wave 0 RED tests from 27-01 for trusted context, projections, registries, and boundaries
provides:
  - Canonical `TrustedContext`, `MerchantScopeV1`, and `TrustedContextFactory`
  - Service-safe projection helpers for tool, knowledge, memory, approval, replay, intent policy, and AgentState identity
  - Read-only `IntentPolicyRegistry` and `SlotPolicyRegistry` wrappers over existing intent policy constants
affects:
  - phase-27-03-current-seam-migrations
  - phase-29-tool-platform-boundary
  - phase-31-memory-platform-boundary
  - phase-32-intent-graph-migration
tech-stack:
  added: []
  patterns:
    - strict Pydantic platform contracts with `extra="forbid"`
    - canonical-to-legacy projection adapters
    - read-only registry wrappers using immutable views
key-files:
  created:
    - src/platform/__init__.py
    - src/platform/trusted_context.py
    - src/platform/context_projections.py
  modified:
    - src/agent/intent_policy.py
    - .planning/LOCAL-VALIDATION-ISSUES.md
key-decisions:
  - "Preserved `KnowledgeContext.merchant_scope` as the existing list shape through `project_merchant_scope_for_knowledge`."
  - "Kept `safety_snapshot_ref` and `policy_snapshot_ref` as ToolCallContext compatibility fields only; target ToolCallContext schema reconciliation remains Phase 29 scope."
  - "Kept current search, agent route, graph node, and tool executor seam migration out of 27-02; 27-03 owns those call sites."
patterns-established:
  - "Factory APIs accept only explicit trusted API/auth/run inputs and reject generic override kwargs."
  - "Canonical AgentState identity projection returns `run_id`; `current_run_id` exists only in an explicit legacy adapter."
  - "Projection-local metadata fields stay on projection contexts, never on `TrustedContext`."
requirements-completed:
  - APF-03
  - APF-04
duration: 6 min
completed: 2026-06-23
---

# Phase 27 Plan 02: Platform Trusted Context Contracts and Registries Summary

**Canonical trusted context factory, exact MerchantScopeV1 semantics, service-safe projection helpers, and read-only intent/slot registries**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-22T16:55:35Z
- **Completed:** 2026-06-22T17:01:46Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Implemented `TrustedContext`, `MerchantScopeV1`, and `TrustedContextFactory.create_from_request` under `src/platform`.
- Added projection helpers for `ToolCallContext`, `KnowledgeContext`, memory, approval, replay, intent policy, canonical AgentState identity, and explicit legacy `current_run_id` compatibility.
- Added read-only `IntentPolicyRegistry` and `SlotPolicyRegistry` without changing existing routing helper behavior.
- Preserved `KnowledgeContext.merchant_scope` as `list[str] | None` through a central adapter.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement canonical TrustedContextFactory and exact MerchantScopeV1** - `8bd74e2` (feat)
2. **Task 2: Implement projections and read-only intent/slot registries** - `a64307c` (feat)

## Files Created/Modified

- `src/platform/__init__.py` - Public exports for trusted context contracts and projection helpers.
- `src/platform/trusted_context.py` - Canonical `TrustedContext`, `MerchantScopeV1`, permission derivation, merchant-scope semantics, and factory.
- `src/platform/context_projections.py` - Tool, knowledge, memory, approval, replay, intent policy, and AgentState projection helpers.
- `src/agent/intent_policy.py` - Read-only registry wrappers over existing intent/slot policy constants.
- `.planning/LOCAL-VALIDATION-ISSUES.md` - Recorded that the extra seam-migration boundary test remains RED by 27-03 design.

## Decisions Made

- `KnowledgeContext.merchant_scope` remains the current list projection shape; canonical `MerchantScopeV1` is adapted centrally by `project_merchant_scope_for_knowledge`.
- `safety_snapshot_ref` is preserved only because current `src/tools/contracts.py::ToolCallContext` supports it. This is a compatibility delta from the narrower normative §12.5 target text, and target ToolCallContext schema reconciliation is routed to Phase 29.
- Search, agent routes, graph nodes, and tool executors were not migrated in this plan; that is the explicit 27-03 boundary.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The required 27-02 gates passed.
- I additionally ran `tests/architecture/test_trusted_context_boundaries.py::test_current_seams_use_projection_helpers_not_direct_trusted_context_constructors`; it remains RED as planned because 27-03 owns current seam migrations. This was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
- Pytest emits a third-party `LangChainPendingDeprecationWarning` from `langgraph.checkpoint.serde.encrypted`; it did not affect test results.

## Verification

- `uv run pytest tests/platform/test_trusted_context.py tests/platform/test_trusted_context_factory.py tests/platform/test_merchant_scope.py -q` passed.
- `uv run ruff check src/platform/trusted_context.py src/platform/__init__.py tests/platform/test_trusted_context.py tests/platform/test_trusted_context_factory.py tests/platform/test_merchant_scope.py` passed.
- `uv run pytest tests/platform/test_context_projections.py tests/agent/test_intent_policy_registry.py tests/architecture/test_trusted_context_boundaries.py::test_only_platform_module_defines_trusted_context_models tests/architecture/test_trusted_context_boundaries.py::test_prompt_projectors_do_not_import_trusted_context_authority -q` passed.
- `uv run pytest tests/platform -q` passed.
- `uv run pytest tests/agent/test_intent_policy_registry.py tests/architecture/test_trusted_context_boundaries.py::test_only_platform_module_defines_trusted_context_models tests/architecture/test_trusted_context_boundaries.py::test_prompt_projectors_do_not_import_trusted_context_authority -q` passed.
- `uv run ruff check src/platform src/agent/intent_policy.py tests/platform tests/agent/test_intent_policy_registry.py tests/architecture/test_trusted_context_boundaries.py` passed.

## Known Stubs

None. Stub-pattern scan only matched intentional nullable fields, deny-all empty scope cases, and default empty collections in contracts/tests.

## Threat Flags

None. The new security-relevant trust boundaries are the ones already listed in the plan threat model: factory trusted inputs, merchant-scope enforcement, projection no-widening, AgentState identity isolation, and read-only registries.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `27-03-PLAN.md` to migrate the current search, agent route, graph node, and tool executor seams to consume these helpers. The known RED boundary test for direct seam constructors should become green in 27-03.

## Self-Check: PASSED

- Found created files: `src/platform/__init__.py`, `src/platform/trusted_context.py`, `src/platform/context_projections.py`.
- Found modified file: `src/agent/intent_policy.py`.
- Found task commits `8bd74e2` and `a64307c` in git log.
- Confirmed required 27-02 verification gates passed; seam-migration boundary RED remains documented 27-03 scope.

---
*Phase: 27-trustedcontextfactory-and-projections*
*Completed: 2026-06-23*
