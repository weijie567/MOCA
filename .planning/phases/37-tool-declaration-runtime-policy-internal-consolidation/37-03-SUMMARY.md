---
phase: 37-tool-declaration-runtime-policy-internal-consolidation
plan: 03
subsystem: tools
tags: [tool-policy, runtime-auth, contract-shape, regression-sweep, pytest, ruff]

requires:
  - phase: 37-01
    provides: single-source catalog declarations and drift guards
  - phase: 37-02
    provides: shared ToolRuntime._fail helper and runtime event redaction coverage
provides:
  - declarative RuntimeAuthGate sequence for ToolPolicyEngine.runtime_auth
  - gate-order and multi-denial reason-code regression tests
  - final Phase 37 contract-shape and generic output schema verification
affects: [phase-37, phase-38, phase-39, tool-policy, tool-platform]

tech-stack:
  added: []
  patterns:
    - frozen RuntimeAuthGate declarations evaluated in order
    - final contract-shape verification with uv run python

key-files:
  created:
    - .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-03-SUMMARY.md
  modified:
    - src/tools/policy.py
    - tests/tools/test_tool_platform.py

key-decisions:
  - "Keep descriptor missing and runtime unavailable as preflight tool_unavailable denials before normal runtime-auth gates."
  - "Build resource_scope_binding once before gate evaluation and keep BusinessFactService ownership proof outside ToolPolicyEngine."
  - "Close TPH-04 after runtime failure helper and declarative runtime_auth gate sequence are both in place."

patterns-established:
  - "Runtime auth policy checks should be added by extending _runtime_auth_gates only when a future phase explicitly introduces a new gate."
  - "Final phase sweeps should verify external model field sets and spec/contracts empty diffs before marking contract-sensitive work complete."

requirements-completed: [TPH-03, TPH-04]

duration: 4 min
completed: 2026-07-02
---

# Phase 37 Plan 03: Runtime Auth Gate Summary

**Runtime authorization now evaluates a named gate sequence while preserving existing reason-code order and contract fields.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-02T00:18:09Z
- **Completed:** 2026-07-02T00:21:37Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added tests for exact runtime-auth gate order: `caller_allowlist`, `permission`, `side_effect`, `resource_scope`, `approval`, `safety_snapshot`, `idempotency`.
- Added a multi-denial regression for `create_coupon_grant_draft` preserving reason order: caller, permission, side-effect, scope, safety snapshot, idempotency.
- Introduced `RuntimeAuthGate` and `_runtime_auth_gates` in `ToolPolicyEngine`.
- Replaced the runtime-auth hardcoded if-chain with ordered gate evaluation after preflight descriptor/availability checks.
- Ran final contract-shape, generic output schema, spec/contracts diff, and ruff sweeps.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add declarative gate order and semantic preservation tests** - `824c613` (test)
2. **Task 2: Implement ordered RuntimeAuthGate declarations** - `9f060e6` (refactor)
3. **Task 3: Run final Phase 37 contract and regression sweep** - documented in this summary

## Files Created/Modified

- `src/tools/policy.py` - Adds `RuntimeAuthGate`, predicate functions, and ordered `_runtime_auth_gates`.
- `tests/tools/test_tool_platform.py` - Adds declarative gate-order and multi-denial reason-code tests.

## Decisions Made

- Kept `tool_unavailable` preflight behavior outside the normal gate sequence for missing descriptors and unavailable tools.
- Kept BusinessFactService merchant ownership/domain proof out of `ToolPolicyEngine`; policy continues to mark domain-scope lookup needs with `requires_domain_scope_check`.
- Marked TPH-04 complete only after both 37-02 runtime helper consolidation and 37-03 policy gate sequencing were complete.

## Deviations from Plan

None - implementation scope matched the plan. The only incomplete automated gate is environmental: local PostgreSQL is unavailable for DB-backed pytest setup.

## Issues Encountered

- Task 2 exact focused pytest and final full relevant pytest are blocked by local PostgreSQL absence. The final full command reached `66 passed, 1 warning, 14 errors`; every error is a DB fixture setup connection refusal to `localhost:5432`.
- The PostgreSQL blocker and its evidence are recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `uv run pytest tests/tools/test_tool_platform.py::test_runtime_auth_gate_sequence_is_declarative_and_ordered tests/tools/test_tool_platform.py::test_runtime_auth_declarative_gates_preserve_multi_denial_reason_order tests/tools/test_tool_platform.py::test_runtime_auth_rechecks_visible_tool_before_dispatch tests/tools/test_tool_platform.py::test_runtime_auth_handles_legacy_list_merchant_scope tests/tools/test_tool_platform.py::test_tool_runtime_failure_paths_use_shared_fail_helper tests/agent/test_tools/test_unified_tool_manager.py -q` -> `35 passed, 1 warning`
- `uv run ruff check src/tools/policy.py tests/tools/test_tool_platform.py` -> passed
- `git diff -- docs/contract-spec.md src/tools/contracts.py` -> empty
- contract-shape `uv run python -c ...` -> `contract shape checks passed`
- generic output schema `uv run python -c ...` -> `generic output schemas preserved`
- `uv run ruff check src/tools tests/tools tests/agent/test_tools tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py` -> passed
- `uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_unified_tool_manager.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py -q` -> blocked by local PostgreSQL connection refusal

## User Setup Required

Local PostgreSQL must be installed/running and reachable at `moca:moca_dev@localhost:5432` to complete the DB-backed final pytest gate.

## Next Phase Readiness

Phase 37 implementation is complete except for the environment-blocked DB-backed pytest rerun. Phase 38 can plan against the consolidated catalog declarations and shared runtime failure path; Phase 39 can reconcile spec after Phase 38 finalizes output schema semantics.

---
*Phase: 37-tool-declaration-runtime-policy-internal-consolidation*
*Completed: 2026-07-02*
