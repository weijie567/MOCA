---
phase: 63-safety-taxonomy-and-risk-vocabulary
plan: 02
subsystem: risk-gate
tags: [risk-gate, safety-taxonomy, action-taxonomy, risk-vocabulary, tdd]

requires:
  - phase: 63-safety-taxonomy-and-risk-vocabulary
    plan: 01
    provides: Canonical safety taxonomy registry and risk vocabulary helpers
provides:
  - Risk gate consumption of the canonical action taxonomy registry
  - Severity-only `risk_level` with explicit `risk_severity` and `risk_disposition`
  - Non-executable dispositions rejected before action snapshot / approval binding
  - Risk decision reason codes carrying severity and disposition facets
affects: [risk-gate, approvals, action-safety-snapshot, phase-63]

key-files:
  modified:
    - src/agent/nodes/risk_gate.py
    - tests/agent/test_nodes/test_risk_gate.py
    - tests/agent/test_phase22_action_boundary.py
    - tests/approvals/test_hash_binding.py

requirements-completed:
  - SC-63-1
  - SC-63-2
  - SC-63-3
  - D-63-01
  - D-63-02
  - D-63-03
  - D-63-04
  - D-63-07
  - D-63-08
  - D-63-13

completed: 2026-07-10
---

# Phase 63 Plan 02: Risk Gate Risk Vocabulary And Action Proposal Migration Summary

## Accomplishments

- Migrated `src/agent/nodes/risk_gate.py` off local `FULL_REFUND_TERMS`, `ACTIONABLE_ACTIONS`, `_is_actionable_recommendation`, and `_canonical_action_type` copies.
- Normalized risk gate outputs through `risk_assessment_with_disposition(...)`, preserving legal severity while moving `manual_review` / `blocked` into `risk_disposition`.
- Rejected `manual_review` and other non-executable disposition-like recommendations before action snapshot binding, preventing them from becoming proposed action types.
- Added `risk_severity:*` and `risk_disposition:*` reason codes to risk decisions for audit and approval hash context.

## Task Commits

1. **Task 1 RED: Pin risk disposition split in risk gate** - `2240af0` (test)
2. **Task 2 GREEN: Split risk severity disposition in risk gate** - `c584d80` (feat)

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/approvals/test_hash_binding.py -q --tb=short` -> `48 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py -q --tb=short` -> `38 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/risk_gate.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/approvals/test_hash_binding.py` -> `All checks passed!`

## Deviations From Plan

- The initial RED expectation for Phase 34 merchant-binding fail-closed was corrected during implementation: Phase 63 requires preserving legal existing severity, so a high-risk action that enters manual review remains `risk_level=high`, `risk_disposition=manual_review`.

## Remaining Scope

- `action_draft.py`, ToolPlatform write-tool boundary behavior, `intent_policy.py`, and routing taxonomy migration remain for 63-03 and 63-04.
- Drift guards and final architecture-debt closeout remain for 63-05.
