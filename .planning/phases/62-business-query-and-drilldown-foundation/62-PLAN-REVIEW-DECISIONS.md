---
phase: 62
review_loop: 1
review_source: 62-REVIEWS.md
adjudicated_at: 2026-07-09T12:18:27Z
status: repaired
---

# Phase 62 Plan Review Decisions

## Codex Adjudication

Claude's review returned `APPROVE WITH WARNINGS` and no blocker. Codex verified the warnings against the current Phase 62 plan set and accepted the items below as plan-hardening changes. None require re-splitting the seven-plan structure.

| ID | Claude finding | Outcome | Rationale | Plan repair |
|----|----------------|---------|-----------|-------------|
| C-62-01 | 62-04 runtime is the largest delivery risk; breakdown/compare must not be weak pass-throughs. | accepted | 62-04 intentionally owns runtime, but compare/breakdown and performance boundaries need explicit tests. | Hardened 62-04 acceptance for runtime-backed breakdown/compare, compare time edges, limit+1 pagination, and DB-side scope filtering. |
| C-62-02 | Runtime/projection result model boundary is underspecified. | accepted | 62-04 had `_business_query_result_to_fact_result`, but downstream shape needed a fixed handoff contract. | Hardened 62-04/62-06 around `fact_data["business_query"]` / `BusinessQueryResultV1` normalized handoff. |
| C-62-03 | Same-thread answer context invalidation is not specific enough. | accepted | 62-05 covered cross-thread stale context, but did not enumerate user/tenant/scope/role/permission-denial invalidation. | Added invalidation rules and tests to 62-05. |
| C-62-04 | New `business:query` scope could break existing `metrics:read` compatibility. | accepted | 62-03 preserved compatibility but needed explicit role/JWT/demo fixture migration coverage. | Added transition strategy and tests to 62-03. |
| C-62-05 | Registry could become a behavior/UI/layout owner. | accepted | 62-01 already says registry describes allowed shape only, but UI/projection/runtime exclusions should be explicit. | Hardened 62-01 registry boundary text. |
| C-62-06 | Generalized expected-slot flow could capture unrelated flows. | accepted | 62-05 had cross-thread coverage but not enough non-business negative coverage. | Added small-talk, unsupported, approval/action, and ordinary clarification negative tests to 62-05. |
| C-62-07 | Eval/golden could validate only fixture shape, not real graph/API behavior. | accepted | 62-06 had eval validator and API tests separately, but did not require graph/API cases to mirror golden categories. | Added graph/API behavior coverage and contract snapshot requirements to 62-06. |
| C-62-08 | Frontend E2E must actually run as a phase gate. | accepted | 62-07 placed E2E in the phase gate; acceptance should state the plan cannot be marked complete without it. | Hardened 62-07 acceptance/gate wording. |
| C-62-09 | Contract spec must avoid presenting target state as already implemented. | accepted | MOCA project rules require target/spec versus implementation fact separation. | Hardened 62-02 contract-spec action. |
| C-62-10 | List/detail/compare performance boundaries need attention. | accepted | 62-04 has limits/cursors, but DB-side filtering and compare time-window edge tests need explicit acceptance. | Hardened 62-04 acceptance. |

## Codex Independent Review

After applying the repairs, Codex rechecked the plan set for:

- context/roadmap coverage of `business_query`, compatibility, no-existence-leak, drilldown, projection/eval/UI, and Phase 63-67 deferrals;
- dependency order from registry/schema/policy/runtime/context/projection/UI;
- MOCA test entrypoint compliance;
- accepted Claude findings resolved in concrete plan text;
- no newly introduced source-code work outside Phase 62 scope.

Result: no additional accepted blockers. Phase 62 can proceed after the repaired plan diff passes markdown whitespace checks and the plan-review loop is recorded.

## Repair Validation

Recorded at 2026-07-09T12:25:35Z:

- `git diff --check -- .planning/phases/62-business-query-and-drilldown-foundation` passed.
- `gsd-sdk query verify plan-structure <plan>` returned `valid=true` for `62-01-PLAN.md` through `62-07-PLAN.md`.
- `gsd-sdk query frontmatter validate <plan> --schema plan --pick valid` returned `true` for `62-01-PLAN.md` through `62-07-PLAN.md`.

## Claude Re-Review Outcome

Claude re-reviewed the repaired plans at 2026-07-09T12:26:57Z and returned `APPROVE` with no blockers.

Two low-risk wording suggestions were accepted and repaired:

- 62-01 frontmatter now says projection consumes registry field allowlists but not projection formatting logic.
- 62-05 now sources answer context from the stable `BusinessFactResultV1.fact_data["business_query"]` / `BusinessQueryResultV1` handoff, not from a future projection layer or raw tool dict.
