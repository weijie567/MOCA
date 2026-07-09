---
phase: 63
review_source: claude
review_artifact: .planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-REVIEWS.md
status: repaired
updated_at: "2026-07-10T02:36:00+08:00"
---

# Phase 63 Plan Review Decisions

## Scope

This file records Codex adjudication of the external Claude plan review before Phase 63 execution.
Every accepted finding is repaired in the plan files before execution.

## Decisions

### C63-PR-01 — Taxonomy helper surface too narrow

- Outcome: accepted.
- Evidence: `63-02-PLAN.md` needs full-refund alias matching in `risk_gate`; `63-04-PLAN.md` needs compensation/coupon alias data and pre-route action alias matching. Original `63-01-PLAN.md` exposed only generic resolution helpers.
- Repair: `63-01-PLAN.md` now requires `action_aliases_for`, `pre_route_action_aliases`, `matches_full_refund_alias`, `matches_compensation_alias`, and stable `ActionResolution` fields.

### C63-PR-02 — Manual-review disposition could downgrade severity

- Outcome: accepted.
- Evidence: original `63-02-PLAN.md` hard-coded manual review to `medium` and blocked/refuse to `high`. This conflated routing disposition with severity when a legal high severity already exists.
- Repair: `63-02-PLAN.md` now requires preserving existing legal severity for manual-review paths, falling back to `medium` only for absent/legacy disposition severity.

### C63-PR-03 — Risk compatibility contract was under-specified

- Outcome: accepted.
- Evidence: Phase 63 must preserve legacy `RiskDecisionV1.risk_level` acceptance while preventing new runtime routing from reading `manual_review` / `blocked` as severity.
- Repair: `63-02-PLAN.md` now states new `risk_assessment["risk_level"]` and new `RiskDecisionV1.risk_level` are severity-only, while legacy model validation remains compatible. It also requires stable `risk_severity:<value>` and `risk_disposition:<value>` reason-code tokens or a documented equivalent.

### C63-PR-04 — New action-draft error codes need a safe contract

- Outcome: accepted.
- Evidence: `NON_EXECUTABLE_ACTION_DISPOSITION` and `NON_EXECUTABLE_ACTION_TYPE` become test/debug contract values and must not leak taxonomy internals.
- Repair: `63-03-PLAN.md` now requires safe error shape parity with existing action-boundary errors, no raw taxonomy internals in messages, stable trace step fields, and no ToolPlatform invocation.

### C63-PR-05 — Intent alias migration needs stronger hard negatives

- Outcome: accepted.
- Evidence: `63-04-PLAN.md` moved compensation/coupon/action terms into taxonomy aliases, which can over-match policy questions without explicit hard-negative tests.
- Repair: `63-04-PLAN.md` now adds Chinese/English compensation-policy hard negatives and direct action positive controls.

### C63-PR-06 — Registry exception fallback was too abstract

- Outcome: accepted.
- Evidence: blindly returning action-bound/evidence-required on every registry exception can route direct-response or unsupported intents incorrectly.
- Repair: `63-04-PLAN.md` now requires layered fail-closed behavior, preserving direct-response route policy before evidence fallback and adding fake-registry-raises tests proving no action execution occurs.

### C63-PR-07 — RED test "committed" wording conflicts with execution semantics

- Outcome: accepted.
- Evidence: original `63-01-PLAN.md` said RED tests are committed before implementation. Executors should write and observe RED failure without implying an extra commit boundary outside the GSD executor's atomic commit flow.
- Repair: wording changed to "written and observed failing".

### C63-PR-08 — Local validation log should be conditional

- Outcome: accepted.
- Evidence: `AGENTS.md` requires `.planning/LOCAL-VALIDATION-ISSUES.md` only when a real local validation/debug issue is found. Original `63-05-PLAN.md` listed it as a required modified file.
- Repair: `63-05-PLAN.md` now moves the file to `conditional_files_modified` and requires leaving it untouched unless a real incident occurs.

### C63-PR-09 — Drift guard must avoid broad `manual_review` / `blocked` grep

- Outcome: accepted.
- Evidence: `manual_review` and `blocked` are valid compatibility strings, reason-code values, and test fixtures. Broad scans would create false positives.
- Repair: `63-05-PLAN.md` now scopes the architecture guard to assignment names, local canonicalizers, and action payload construction that can recreate executable-action drift.

## Codex Independent Plan Review

After repairs, Codex rechecked the plan set for:

- D-63-01 through D-63-16 coverage.
- Plan grain and dependency order.
- Phase 64/65/66/67 scope exclusion.
- MOCA test command entrypoint compliance.
- Security boundaries for executable actions, disposition, routing, and compatibility fields.

Status: no additional accepted issues before rerunning GSD plan-checker and external review.
