---
phase: 63-safety-taxonomy-and-risk-vocabulary
plan: 03
subsystem: action-draft
tags: [action-draft, tool-platform, safety-taxonomy, action-taxonomy, tdd]

requires:
  - phase: 63-safety-taxonomy-and-risk-vocabulary
    plan: 01
    provides: Canonical safety taxonomy registry and action resolver helpers
provides:
  - Action draft consumption of the canonical executable-action taxonomy
  - Non-executable disposition rejection before ToolPlatform invocation
  - Compensation alias compatibility through `issue_coupon` without a new tool
  - Existing approval / auto-allowed / Phase 34 binding behavior preserved
affects: [action-draft, tool-platform, action-service-boundary, phase-63]

key-files:
  modified:
    - src/agent/nodes/action_draft.py
    - tests/test_execute_action.py
    - tests/architecture/test_action_draft_boundaries.py
    - .planning/LOCAL-VALIDATION-ISSUES.md

requirements-completed:
  - SC-63-1
  - SC-63-3
  - D-63-01
  - D-63-02
  - D-63-03
  - D-63-04
  - D-63-07
  - D-63-10
  - D-63-12

completed: 2026-07-10
---

# Phase 63 Plan 03: Action Draft And ToolPlatform Boundary Migration Summary

## Accomplishments

- Migrated `src/agent/nodes/action_draft.py` off local `FULL_REFUND_TERMS`, `ACTIONABLE_ACTIONS`, and `_canonical_action_type(...)`.
- Enforced executable-action validation with `resolve_action_text(...)` after approval/auto-allowed eligibility and before `project_to_tool_context(...)` / ToolPlatform invocation.
- Added stable safe action-result errors:
  - `NON_EXECUTABLE_ACTION_DISPOSITION` for explicit `manual_review` / `blocked` disposition-shaped requests.
  - `NON_EXECUTABLE_ACTION_TYPE` for unsupported non-executable action types.
- Preserved `ACTION_TOOL_NAME = "create_coupon_grant_draft"`, `caller_node="action_draft"`, demo `not_executed_demo` outcomes, and Phase 34 approval / auto-allowed binding checks.
- Narrowed an architecture guard false positive so taxonomy alias helper names are not mistaken for external execution imports.

## Task Commits

1. **Task 1 RED: Pin action draft executable taxonomy boundary** - `8b2a04c` (test)
2. **Task 2 GREEN: Enforce executable action taxonomy in draft node** - `1842316` (feat)

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short` -> `64 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` -> `48 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/action_draft.py tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py` -> `All checks passed!`

## Deviations From Plan

- `tests/architecture/test_action_draft_boundaries.py` had a broad `compensation` substring guard that falsely flagged `src.agent.safety.taxonomy.matches_compensation_alias`. The guard was narrowed to `action_compensation`, and the handled validation issue was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Remaining Scope

- `intent_policy.py`, routing evidence-required/action-bound sets, and safety pre-route keyword handling remain for 63-04.
- Drift guards, parity checks, and final architecture-debt closeout remain for 63-05.
