---
phase: 60
review_source: .planning/phases/60-v2-1-archive-evidence-closure/60-REVIEWS.md
decided_at: 2026-07-08T11:45:00Z
status: repaired
---

# Phase 60 Plan Review Decisions

## Summary

External Claude review agreed the five-plan structure is sound, but raised several execution guard risks. Codex adjudicated each item against the repository and Phase 60 context. Accepted items were repaired in `60-01-PLAN.md` through `60-05-PLAN.md`.

## Decisions

| Review Item | Decision | Evidence | Repair |
| --- | --- | --- | --- |
| Final archive gate may be unexecutable if audit tooling is unavailable. | Partially accepted. Tooling unavailability is a real risk, but it must be a hard stop, not an accepted passing status. | `audit-milestone.md` requires `gsd-integration-checker`; `gsd-sdk query init.phase-op 60` reports legacy `agents_installed: false`, while Codex has a callable `gsd-integration-checker` agent type. | `60-05` now states tooling unavailability is not accepted product debt and must not be represented as `complete`, `complete_with_accepted_debt`, `passed`, `archive_ready`, or `5/5 complete`. |
| Grep-only evidence checks cannot prove source-backed artifacts. | Accepted. | Phase 60 D-02/D-09 require real code/docs/tests evidence, not milestone-ledger restatement. | `60-01` and `60-02` now require `Evidence Anchors` with `path:line` citations and `rg` checks for `*.py/*.md/*.sql/*.toml:line` anchors. |
| No plan mechanically enforces planning/evidence-only changes. | Accepted. | D-14 says Phase 60 should update only planning/evidence artifacts unless validation proves a real defect. | Each plan's final scan now includes a `git status --short` guard that fails if any changed path is outside `.planning/`. |
| Most verification artifacts do not require fresh reruns. | Partially accepted. | Phase 56/CAGM-07 is safety-sensitive action/RAG/claim evidence; Phase 50 is SPEC-only and should remain docs/static. | `60-02` now mandates the focused Phase 56 CAGM-07 pytest rerun and requires recording its result in `56-VERIFICATION.md`. Other historical phases may still use source-backed no-rerun rationale where appropriate. |
| Language inconsistency across generated artifacts. | Not repaired. | MOCA docs default to Chinese, but existing verification/validation artifacts are mixed and technical artifact consistency matters more than language uniformity. | No plan change. Executors should follow existing target artifact style where practical. |
| `44-REVIEW-ADJUDICATION.md` may not exist. | False positive. | `test -f .planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-REVIEW-ADJUDICATION.md` returned success. | No repair needed. |
| `42-VALIDATION.md` regex `IDR-02.*not` is brittle. | Accepted. | Single-line negation may fail on a correct wrapped explanation. | `60-03` now checks for `IDR-02` separately from negation/out-of-scope terms. |
| `60-04` exact DB command substring verify is brittle. | Accepted. | Exact full-line command matching can fail if markdown wrapping changes while preserving the command components. | `60-04` now verifies required command components across artifacts and issue log instead of a single full string. |
| DB rerun should be serial. | Accepted as clarification. | `tests/conftest.py` DB fixture uses shared `moca_test`; research says DB-backed commands must be serial. | `60-04` now says to run the DB command as a single serial command and not add xdist/parallel flags. |
| `60-05` writes `5/5 complete` before Task 3 audit. | Accepted. | Task 2 previously described `5/5 complete` before Task 3 runs the archive gate. | `60-05` now keeps ROADMAP/STATE in pending-final-audit state during Task 2 and writes `5/5 complete` only after a real Task 3 audit result. |

## Repaired Files

- `.planning/phases/60-v2-1-archive-evidence-closure/60-01-PLAN.md`
- `.planning/phases/60-v2-1-archive-evidence-closure/60-02-PLAN.md`
- `.planning/phases/60-v2-1-archive-evidence-closure/60-03-PLAN.md`
- `.planning/phases/60-v2-1-archive-evidence-closure/60-04-PLAN.md`
- `.planning/phases/60-v2-1-archive-evidence-closure/60-05-PLAN.md`

## Follow-Up Gate

Rerun `gsd-plan-checker` after these repairs. If it passes, proceed to Codex independent plan review before execution.

## Codex Independent Plan Review

**Reviewed at:** 2026-07-08T11:44:55Z

### Checks

| Check | Result | Evidence |
| --- | --- | --- |
| Context / roadmap / requirements must-haves covered by concrete tasks or named deferral | Passed | `gsd-plan-checker` recheck passed with all seven requirement IDs covered by plans. |
| Task order and dependencies coherent | Passed | `60-01`/`60-02` wave 1, `60-03` wave 2, `60-04` wave 3, `60-05` wave 4; dependencies are acyclic. |
| Verification covers risky contracts and changed surfaces | Passed | Source anchors, `.planning/` diff guard, Phase 56 focused rerun, Phase 37 DB-note branch check, and final audit gate checks are present. |
| No out-of-scope implementation | Passed | All `files_modified` entries are `.planning/` artifacts; every plan has a final `.planning/` path guard. |
| Spec / implementation divergence not silent | Passed | Phase 49 accepted limitation, Phase 50 SPEC-only status, Phase 42 retroactive status, and audit-tooling hard stop are explicitly planned. |
| Accepted Claude findings resolved | Passed | All accepted repairs are reflected in `60-01` through `60-05` and plan-checker recheck passed. |
| Rejected/deferred Claude findings defensible | Passed | `44-REVIEW-ADJUDICATION.md` exists; tooling unavailable remains a hard stop rather than accepted product debt; language uniformity not required for archive correctness. |

### Result

Codex independent plan review found no additional accepted issues.

Because accepted Claude findings caused material changes to verification strategy and acceptance criteria, the autopilot loop must rerun Claude plan review once more before execution.

## Claude Review Loop 2 Decisions

**Reviewed at:** 2026-07-08T11:48:05Z

| Review Item | Decision | Evidence | Repair |
| --- | --- | --- | --- |
| `60-05` still cannot express honest audit-tooling unavailability in acceptance/verify checks. | Accepted with guardrails. `blocked_tooling_unavailable` is allowed only as an explicitly incomplete status with next entry point; it must not mark Phase 60 complete. | `60-05` already says tooling unavailability is a hard stop; acceptance regex previously only accepted terminal completion/debt statuses. | `60-05` now allows `blocked_tooling_unavailable` in status checks and requires incomplete/next-entry markers in audit, validation, and summary artifacts if that branch occurs. |
| `60-02` Phase 56 focused rerun lacks an environment-failure branch. | Accepted. | The fresh CAGM-07 rerun command includes DB-backed/API suites, unlike the original paper-only evidence path. | `60-02` now supports pass / environment-failure named debt `CAGM-07-RERUN-EVIDENCE-POST-V2.1` / real-defect stop handling, with `.planning/LOCAL-VALIDATION-ISSUES.md` evidence for environment failures. |
| `git status --short` guard is fragile on renames. | Disagree for Phase 60. | Phase 60 plans only create/edit `.planning/` files and do not plan renames. | No repair. |
| `60-04` prose mentions scanning `LOCAL-VALIDATION-ISSUES.md`, automation omits it. | Disagree. | Omitting historical local issue log from bare-command scan avoids false positives; Task 2 already requires exact named-debt markers there if environment branch occurs. | No repair. |
| Evidence-anchor grep is one-anchor-satisfiable. | Accepted as residual risk, not further repaired. | Stronger per-row parsing would be disproportionate for planning artifacts; executor still must produce source-backed evidence under D-02/D-09. | Existing `Evidence Anchors` checks remain the mitigation. |

## Loop 2 Repair Gate

Rerun `gsd-plan-checker` after these loop-2 repairs. If it passes and Codex independent plan review finds no new issue, proceed to execution.

## Loop 2 Plan-Checker Decisions

**Checked at:** 2026-07-08T11:57:09Z

| Checker Item | Decision | Evidence | Repair |
| --- | --- | --- | --- |
| Unrelated `.planning/` changes can still pass silently. | Accepted. The prior guard only rejected non-`.planning/` paths and did not enforce each plan's declared write surface. | Plan-checker cited `60-01`/`60-02`/`60-03`/`60-04`/`60-05` final `git status --short` guards. | Replaced broad `.planning/` prefix guards with per-plan allowlists derived from `files_modified` plus the plan summary artifact. `60-05` now allowlists only the full Phase 60 evidence/tracking artifact set. |
| `60-02` Phase 56 environment-debt verify can be fooled by `status: passed` substring matching. | Accepted. `status: passed_with_rerun_environment_debt` contains the substring `status: passed`. | `60-02` automated branch check used substring matching. | Replaced substring status checks with exact `^status:` line regexes and expanded command-component checks to the full focused rerun command. |

These repairs are guard-only changes to the execution plans. They do not change Phase 60 deliverables or requirement coverage.

## Codex Independent Re-Review After Checker Repairs

**Reviewed at:** 2026-07-08T11:59:49Z

### Checks

| Check | Result | Evidence |
| --- | --- | --- |
| Previous broad `.planning/` dirty-path guard removed | Passed | `rg` found no remaining `not line[3:].startswith(".planning/")` checks in Phase 60 plans. |
| Per-plan dirty-path allowlists present | Passed | `60-01` through `60-04` allow only their declared evidence files plus summary; `60-05` allowlists the complete Phase 60 evidence/tracking artifact set. |
| Phase 56 status branch cannot substring-pass | Passed | Synthetic regex test confirmed `status: passed_with_rerun_environment_debt` does not satisfy the exact `status: passed` branch. |
| `blocked_tooling_unavailable` remains incomplete | Passed | `60-05` requires `Phase 60 incomplete` and `next entry point` markers and forbids `5/5 complete` on that branch. |
| Plan-checker recheck | Passed | Recheck returned `## VERIFICATION PASSED`, with plan granularity and requirement coverage still valid. |

### Result

Codex independent re-review found no additional accepted issues. No third Claude plan-review loop is required because the final repairs are mechanical guard hardening only: they do not change plan scope, wave order, requirement coverage, audit semantics, or deliverables. Proceed to execution.
