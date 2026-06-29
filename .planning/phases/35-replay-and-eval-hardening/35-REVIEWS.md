---
phase: 35-replay-and-eval-hardening
reviewed_at: "2026-06-29T14:11:29Z"
reviewers:
  - gsd-plan-checker
  - claude
failed_reviewers:
  - gemini
plans_reviewed:
  - 35-01-PLAN.md
  - 35-02-PLAN.md
  - 35-03-PLAN.md
  - 35-04-PLAN.md
  - 35-05-PLAN.md
  - 35-06-PLAN.md
status: passed
---

# Phase 35 Plan Reviews

## GSD Plan Checker

Result: passed.

The checker confirmed the required six-plan split, APF-17/APF-18 coverage intent, owner/admin-only scope, non-blocking release/monitoring artifacts, and MOCA-approved test command entrypoints.

## Gemini

Result: failed to run.

Command:

```bash
cat /tmp/gsd-review-prompt-35.md | gemini -p -
```

Observed failure:

```text
When using Gemini API, you must specify the GEMINI_API_KEY environment variable.
```

Adjudication: environment issue, not a Phase 35 plan finding. Continued with Claude review and recorded the local validation issue.

## Claude

Result: reviewed all six plans and rated overall risk as MEDIUM before repair.

Confirmed strengths:

- Phase 35 is split into six dependency-ordered plans instead of one broad `35-01-PLAN.md`.
- No new replay event envelope or real execution system is planned.
- Trace/replay visibility remains owner/admin-only.
- Proof fields are projection-only and fail closed.
- Dev-contract gates block Phase 35; release/monitoring artifacts do not block on missing samples or telemetry.
- Test commands use MOCA-approved `uv run` or `.venv` entrypoints.

Actionable findings accepted:

- `35-01` must not assert exact roadmap text `0/6 plans complete`; execution updates progress to `1/6` through `6/6`, so this would break later reruns and Phase 35 closure.
- The coverage matrix must require concrete decision assertion contracts for generic-event APF-17 boundaries, especially trusted context, intent, slot, memory load, business fact scope/freshness, and risk decision.
- Roadmap success criterion 4 surfaces must be explicitly audited: run listing, trace detail, tool result records, approval views, memory, and replay artifacts.
- `35-04` must not ambiguously validate files created by `35-05` while running in the same wave without dependency ordering.
- Final closure must verify matrix acceptance test paths and decision assertion test paths exist on disk.
- Redaction guarantees should record the residual limitation around arbitrary PII hidden in otherwise safe summary strings.

Findings accepted as clarification, not blockers:

- `project_replay_authorization_proof` intentionally remains non-authorizing and should not expand same-merchant visibility in Phase 35.
- Golden run lifecycle timelines should use `RunLifecycleService` shapes where applicable.

## Repair Decision

Accepted findings are repaired in the plan set before execution:

- `35-01` uses a denominator-six progress regex and requires `decision_assertions`.
- `35-02` records proof fields as non-authorizing and audits approval/tool-result/memory leakage surfaces.
- `35-04` now depends on `35-05` and moves after it.
- `35-06` moves to the final wave and records boundary assertions, criterion 4 scope audit, matrix path existence, and redaction limitation.

## Claude Re-Review

Source: `/tmp/gsd-review-claude-35-r2.md`.

Result: no actionable blockers remained after the first repair pass.

Accepted warnings from the re-review:

- `35-06` should verify assertion content, not only assertion file existence.
- `35-04` replay-by-rerun static checks should stay scoped to replay-owned code and trace/replay API code.
- `35-06` should record `replay_authorization_proof.v1` as projection-only Phase 35 MVP scope reserved for a named post-Phase 35 authorization-expansion phase.

These warnings are repaired in `35-04`, `35-06`, and `35-PLAN-REVIEW-DECISIONS.md`.

## GSD Plan-Checker Recheck

The next plan-checker pass found two blockers and one warning:

- `35-RESEARCH.md` still had unresolved open questions.
- `35-05` represented D-19 release smoke coverage as zero-sample metrics only.
- `35-02` mentioned modifying `tests/test_approval_api.py` without including it in task-level verification.

These findings are accepted and repaired:

- `35-RESEARCH.md` now marks all three planning questions `RESOLVED`.
- `35-05` now creates `eval/replay/release-smoke-cases.v1.json` with one limited smoke case each for `intent_hard_negatives`, `rag_claim_support`, and `approval_action_safety`.
- `35-02` now includes `tests/test_approval_api.py` in task files, pytest verification, and ruff verification.

Final plan-checker result: `## VERIFICATION PASSED`. APF-17 and APF-18 are covered across the six plans, no blockers or warnings remain, `35-05` precedes `35-04`, and `35-06` closes the phase.
