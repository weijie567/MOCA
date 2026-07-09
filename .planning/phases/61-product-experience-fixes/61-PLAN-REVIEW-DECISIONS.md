---
phase: 61
review_source: claude
status: repaired
created: 2026-07-09
---

# Phase 61 Plan Review Decisions

Codex adjudication of `.planning/phases/61-product-experience-fixes/61-REVIEWS.md`.

## Summary

Claude's core architecture assessment is accepted: the five-plan structure is sound, but several pre-execution plan blockers needed repair. Codex verified the actionable findings against GSD workflow semantics, MOCA project rules, and current source files before editing plans.

## Decisions

| Finding | Decision | Evidence | Repair |
|---------|----------|----------|--------|
| Requirement frontmatter can mark requirements complete too early | accepted | `execute-plan.md` marks completed requirements from PLAN frontmatter `requirements:` via `requirements.mark-complete`; Plans 61-02 through 61-04 only deliver partial contract/runtime/graph layers. | Set `requirements: []` for 61-01 through 61-04 and documented why. Kept all 18 final requirements in 61-05 so completion happens after final regression validation. |
| Contract/spec delta missing for metric tool and permission changes | accepted | `AGENTS.md` requires spec deltas or MVP notes when implementation changes accepted contracts; 61-03 adds `metrics:read`, `tool:query_business_metric`, `query_business_metric`, and `business_metric` fact refs. | Added `docs/contract-spec.md` to 61-03 files and required spec updates/grep acceptance. |
| Refund-rate zero denominator missing | accepted | `merchant_refund_rate` uses numerator/denominator semantics; no existing plan defined denominator zero behavior. | Added typed non-computable result and final-response wording requirements in 61-03 and 61-04. |
| Playwright can degrade into mocked-only coverage | accepted | User chose full Playwright E2E; 61-05 allowed route-level mocking fallback. | Rewrote 61-05 to require live backend/API/SSE Playwright tier and `e2e:live` validation. |
| Merchant compatibility role has implicit metric permission expansion | accepted as warning | Current DB model and constraints include `merchant` role; Phase 61 user requirements name support/manager/admin only. | Changed 61-03 to allow merchant compatibility only if already first-class demo actor and own-bound-merchant-only tests are added. |
| Time-window semantics insufficiently tested | accepted | Context locks local time presets; plan lacked explicit boundary tests. | Added inclusive-start/exclusive-end, Monday week start, month/quarter/year, invalid/future range tests to 61-02/61-03. |
| `status_filter` not defined | accepted | MET-02 requires status filter slots; plan named but did not enumerate supported values. | Added metric-specific status/resource contract table in 61-02 and runtime tests in 61-03. |
| `resource_type` slot ambiguous | accepted | MET-02 names resource type; plan only named `metric_id`. | Added derived-or-explicit `resource_type` contract and acceptance coverage in 61-02. |
| Tool args can carry/widen merchant scope | accepted | Trusted scope must come from `ToolCallContext`; plan did not explicitly reject scope-like args. | Added malicious tool-arg tests and trusted-context-only scope rule to 61-03. |
| Coupon metric draft/record status under-specified | accepted | Context says MOCA demo records/drafts but plan did not say which lifecycle/status values count. | Defined Phase 61 MVP as all `ActionDraft.action_type == "issue_coupon"` records created in range regardless of lifecycle/status, with caveat. |
| `read_status` operation label may be poor for metrics | accepted as MVP compromise | `RequestedOperationLiteral` currently lists `read_status` but not metric read operation. Extending enum may have wider blast radius. | Updated 61-02 to require an explicit MVP compromise note/test if `read_status` is reused, or allow executor to add `read_metric` if lower-risk. |
| 61-01 temporary aggregate-order unsupported test may conflict with 61-02 | accepted as already mostly covered | 61-01 action already says temporary aggregate-order guard must be marked so 61-02 intentionally changes it. | No additional edit required beyond existing 61-01 action and source audit. |
| Validation strategy marked draft/pending | accepted | `61-VALIDATION.md` frontmatter and approval were still draft/pending. | Marked `61-VALIDATION.md` approved for execution while preserving final validation pending until execution proves commands pass. |

## Codex Independent Review

After repair, Codex rechecked:

- All Phase 61 requirement IDs remain represented in `requirements_addressed` and final 61-05 `requirements`.
- Plans remain dependency-ordered: 61-01 -> 61-02 -> 61-03 -> 61-04 -> 61-05.
- Contract/spec, scope/no-leak, metric edge cases, live Playwright, golden set, and local validation are now explicit execution requirements.
- No new phase or graph node was introduced; the user decision to keep this inside one Phase 61 remains intact.

## Claude Loop 2 Result

Claude re-reviewed the repaired plans and returned **READY for execution** with no remaining blockers. Two low-severity execution watchpoints remain:

- `npm run e2e` and `npm run e2e:live` must have non-empty, documented responsibilities; `e2e:live` must exercise real backend/API/SSE behavior if `e2e` includes any mocked-only coverage.
- The metric time-window implementation must lock a single authoritative local business/demo timezone source in code/tests.

These are covered by 61-05 final validation and 61-02/61-03 time-boundary requirements, so they do not block execution.

## Remaining Accepted Risk

The standard GSD `gsd-plan-checker` previously timed out for Phase 61. This artifact plus Claude review and Codex repair satisfy the autopilot plan-review loop for continuing to execution, but the timeout remains recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.
