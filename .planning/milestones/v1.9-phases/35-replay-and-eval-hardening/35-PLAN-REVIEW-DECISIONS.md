---
phase: 35-replay-and-eval-hardening
created_at: "2026-06-29T14:11:29Z"
review_source: 35-REVIEWS.md
status: repaired
---

# Phase 35 Plan Review Decisions

## Decision Summary

All accepted Claude findings were repaired before execution. Gemini did not produce a review because the local CLI lacks `GEMINI_API_KEY`; that failure is recorded as an environment issue, not a plan finding.

## Findings

### C-01: Roadmap progress assertion locked to `0/6`

Disposition: accepted.

Evidence: `35-01-PLAN.md` previously required `.planning/ROADMAP.md` to contain exact text `**Plans:** 0/6 plans complete`, while GSD execution updates progress after each completed plan.

Repair:

- `35-01` now requires a denominator-six progress regex instead of exact current count.
- `35-01` acceptance checks look for `PLAN_PROGRESS_RE`, not the literal initial progress value.

### C-02: APF-17 generic-event boundaries could be paper-only

Disposition: accepted.

Evidence: existing replay event registry does not have dedicated event types for several APF-17 left-half boundaries, so the matrix must prove payload/projection assertions rather than only list generic events.

Repair:

- `35-01` now requires `decision_assertions` on every matrix row.
- Required left-half assertion ids are explicit: `trusted_context_projection_replay_context`, `intent_policy_effective_route_trace`, `slot_policy_inheritance_trace`, `memory_load_scope_trace`, `business_fact_scope_freshness_proof`, and `risk_decision_action_path_trace`.
- `35-06` now records a boundary-level assertion audit.

### C-03: Roadmap criterion 4 surfaces were not explicit

Disposition: accepted.

Evidence: Phase 35 context narrows active authorization work to run/trace/replay, but roadmap criterion 4 names run listing, trace detail, tool result records, approval views, memory, and replay artifacts.

Repair:

- `35-02` now requires a static/source audit over all criterion 4 surfaces and references existing regression files for unchanged tool-result and memory surfaces.
- `35-06` now records a dedicated roadmap criterion 4 scope audit.

### C-04: `35-04` referenced manifests created by `35-05`

Disposition: accepted.

Evidence: `35-04` dev-contract validator references release/monitoring manifest files created by `35-05`; both were previously in the same wave with no ordering guarantee.

Repair:

- `35-04` now depends on `35-05` and moves to wave 4.
- `35-06` moves to wave 5.

### C-05: Matrix acceptance paths were not checked for existence at closure

Disposition: accepted.

Evidence: `35-01` cannot require future test files to exist before later plans create them, and the original `35-06` closure did not add the final existence check.

Repair:

- `35-06` now requires a matrix path existence audit for `acceptance_tests` and `decision_assertions[].test_path`.

### C-06: Redaction guarantee could overstate value-level PII coverage

Disposition: accepted as residual-risk note.

Evidence: current redaction guards are deterministic and key/path/fixture focused; arbitrary PII embedded in otherwise safe summary text is a broader semantic data-quality problem.

Repair:

- `35-06` now requires a Redaction Limitation section that records this residual release/monitoring follow-up while keeping Phase 35 dev-contract blockers deterministic.

### C-07: Proof projection remains non-authorizing and may be unconnected

Disposition: accepted as clarification.

Evidence: Phase 35 explicitly keeps manager same-merchant visibility closed; proof fields are for future authorization readiness and must not be consumed by guards.

Repair:

- `35-02` now states `project_replay_authorization_proof` must not be wired into authorization guards or broaden API output except for safe trace-summary projections covered by tests.

### C-08: Run lifecycle payload shape consistency

Disposition: already covered; no new repair required.

Evidence: `35-03` already instructs terminal golden timelines to use `RunLifecycleService` for lifecycle event creation.

### C-09: `tests/eval/` collection risk

Disposition: accepted as verification concern.

Evidence: Phase 35 creates new `tests/eval/` files.

Repair:

- `35-04`, `35-05`, and `35-06` include focused pytest commands over `tests/eval/...` using MOCA-approved entrypoints.

## Codex Independent Review

After repair, the plan set is coherent:

- The user hard constraint is satisfied: Phase 35 has six small dependency-ordered plans, not one broad `35-01`.
- Material dependency order is explicit: `35-05` precedes `35-04`, and `35-06` closes last.
- Dev-contract blockers remain deterministic; release and monitoring stay artifactized and non-blocking for sample/telemetry gaps.
- Proof fields remain non-authorizing and owner/admin-only visibility remains closed.
- No plan introduces real external execution, replay-by-rerun, new physical service deployment, or ad hoc replay event types.

## Second Claude Re-Review

Source: `/tmp/gsd-review-claude-35-r2.md`.

Verdict: no actionable blockers remain.

Warnings accepted as small refinements:

- W1: `35-06` now requires boundary-specific content checks for every `decision_assertions[].test_path`; file existence alone is not enough.
- W2: `35-04` now explicitly scopes replay-by-rerun forbidden-string checks to replay-owned code and the trace/replay API path.
- W3: `35-06` now records `replay_authorization_proof.v1` as projection-only Phase 35 MVP scope reserved for a named post-Phase 35 authorization-expansion phase.

## Second GSD Plan-Checker

Source: `gsd-plan-checker` agent `019f13bc-6796-7eb0-af28-f64c14c8b846`.

Initial verdict: two blockers and one warning.

Accepted repairs:

- Research open questions are resolved directly in `35-RESEARCH.md` with the decisions already encoded by the repaired plans.
- `35-05` now creates `eval/replay/release-smoke-cases.v1.json` with one limited smoke case each for `intent_hard_negatives`, `rag_claim_support`, and `approval_action_safety`; release metrics keep `statistical_gate_not_demonstrated` with `smoke_n=1` and `statistical_n=0`.
- `35-02` now includes `tests/test_approval_api.py` in the task file list, pytest verification, and ruff verification.
