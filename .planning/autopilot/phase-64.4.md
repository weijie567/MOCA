---
phase: "64.4"
status: running
current_step: execute
plan_review_loop: 2
quota_waits: 0
updated_at: "2026-08-11T19:23:56+08:00"
next_command: "$gsd-execute-phase 64.4 (resume at 64.4-10)"
---

# Phase 64.4 Autopilot Checkpoint

## Completed

- Stage 0 preflight: PR #5 is merged at `b47bbaa0`; GitHub Actions lint/test are green.
- Created isolated worktree `/tmp/moca-phase-64-4.OO8Tz2/worktree` on `codex/phase-64-4` directly from latest `origin/main`.
- Confirmed the original MOCA main worktree is not used or modified.
- `gsd-sdk query init.phase-op 64.4` found the registered roadmap phase with no context, research, plans, verification, or reviews.
- Stage 1 discuss: auto-selected conservative decisions for the tokenizer contract, exact final-input assembly, path convergence, immutable reindex/cutover, and A/B selection; committed `64.4-CONTEXT.md` and the audit-only discussion log.
- Reproduced the known GSD decimal-phase `state.record-session` metadata bug, restored the 7/15 (47%) milestone state, and recorded the incident in the local validation ledger.
- Stage 2 research pinned the official Qwen tokenizer asset/revision, established exact 10/10 DashScope single-input parity plus aggregate-batch accounting boundaries, and documented that the mapping is empirical rather than vendor-guaranteed.
- Stage 2 validation created a 22-task Nyquist strategy with mandatory live provider/PostgreSQL gates and MOCA `make format` / `make lint` / `uv run pytest` entries.
- Stage 2 planning split Phase 64.4 into 11 strictly sequential plans and 22 bounded tasks. GSD plan-checker converged from 9 issues to 2 and then clean after the accepted repairs were applied.
- Stage 3 external review: invoked a separate Claude CLI session through `$gsd-review 64.4 --claude` and wrote `64.4-REVIEWS.md`. Claude verified the core repository facts and raised one HIGH, three MEDIUM, and three LOW concerns for Codex adjudication.
- Stage 4 Codex adjudication checked all seven concerns and three suggestions against live repository/planning evidence, accepted eight items, classified one as already covered and disagreed with one boundary-mixing suggestion, and recorded every outcome in `64.4-PLAN-REVIEW-DECISIONS.md`.
- Accepted repairs keep Plan04 token mode default-off until Plan06 active routing, define the canonical threat registry, make production/current versus explicit evaluation/history scopes exact, cap provider attempts without post-observation tuning, register unique SC-64.4 requirements, lock tokenizer platform/license evidence, and align Phase64.3 hash field names.
- Fresh GSD plan-checker returned `## VERIFICATION PASSED`; Claude review loop 2 returned no actionable blocker or warning; Codex's independent coverage/order/scope review is clean. Two optional traceability clarifications were applied without changing tasks, files, dependencies, values, thresholds, or scope.
- Stage 5 execution Plan 01 complete: exact official tokenizer asset/runtime/config and fail-closed offline counter committed in three atomic commits; `make lint`, 21 focused tests, lock check, asset size/SHA and summary self-check passed.
- Stage 5 execution Plan 02 complete: sole exact-final-input assembler, structural/table/token-window splitting, overlap/Unicode/rebuild invariants and fail-closed bounds committed in three atomic commits; `make lint`, 38 focused tests and summary self-check passed.
- Stage 5 execution Plan 03 complete: request-level provider usage and immutable fresh parity protocol/assembler-only CLI committed in three atomic commits; `make lint`, 14 focused tests, truthful no-credential unavailable smoke and summary self-check passed without fabricating live success.
- Stage 5 execution Plan 04 complete: default-off typed ingestion, dry-run/golden/Phase64.3 seam convergence and static single-assembler guards committed in three atomic commits; `make lint`, 151 combined tests, golden validation and summary self-check passed. A minimal Rule2 typed retrieval-round injection seam closed a hidden character-default path without entering Plan09 scope.
- Stage 5 execution Plan 05 complete: migration030 corpus projections/bootstrap, canonical ordered-block document identity, config-aware chunk compatibility and post-schema DTO audit persistence committed in three atomic commits; `make lint`, real PostgreSQL/pgvector migration, replay/source-identity and ingestion audit gates passed.
- Stage 5 execution Plan 06 complete: repository-internal active current scope, exact evaluation/reindex scope, active-config ordinary writes and exhaustive current-path guards committed in three atomic commits; `make lint`, 65 task tests, 41 scope regression tests and summary self-check passed.
- Stage 5 execution Plan 07 complete: fixed candidate claim/lease/CAS resume, authoritative database-only source snapshots, inactive token-corpus build and deterministic completion proofs committed in four atomic commits; `make lint` and 89 PostgreSQL/pgvector-focused regressions passed. Candidate immutable append explicitly suppresses shared current-head projection while ordinary ingestion retains the compatible default.
- Stage 5 execution Plan 08 complete: reversible fixture-authorized pointer CAS, append-only activation history, source-stale refusal and ordinary-ingestion same-config COW committed in five atomic commits; `make lint` and a 94-test PostgreSQL/pgvector combined gate passed. A user-approved Rule 4 migration 031 removed the incompatible block-source uniqueness constraint and added prior epoch/actor audit fields without entering Plan 09/10 selection or receipt scope.
- Stage 5 execution Plan 09 complete: exact raw Fraction/Decimal A/B gates, create-only all-outcome run artifacts, passing-only immutable selection and a production-capable rollback-only full-provider CLI committed in five atomic commits; `make lint` and 118 focused tests passed. Connection-owned outer transactions now prove production ingestion commits cannot leak evaluation pointer/history changes; no live selected pass was fabricated.

## Evidence

- Phase goal: replace character-count policy chunk sizing with a versioned tokenizer-aware final-embedding-input assembly contract and validate safe reindex A/B behavior against the sealed Phase 64.3 baseline.
- Phase boundaries exclude parser, retrieval/reranker, ContextBuilder/claim-verifier redesign, embedding-model replacement, parent-child chunking, and generation-model prompt budgets.
- ROADMAP requires six success criteria covering tokenizer parity, hard final-input token bounds, authoritative chunk assembly, identity/replay compatibility, isolated rollback-safe reindexing, and a versioned A/B report.
- Production must fail closed on unknown tokenizer/count failures and may keep character sizing only as an explicit A/B baseline, never a silent fallback.
- Phase completion requires a token-aware candidate that passes hard safety and fixed same-run non-regression gates; a truthful red candidate report alone is not completion.
- Planning must split tokenizer/parity, assembly/path convergence, persistence/reindex, and A/B/cutover into separate dependency-ordered plans.
- Final granularity is 11 plans, 2 tasks each, with at most 12 files per plan and a 22/22 validation map.
- `evidence_identity.v1` remains corpus-free; canonical document source content comes from ordered blocks, chunk compatibility is config-aware, and corpus projections control visibility only.
- Provider parity, all-outcome terminal A/B reports, passing-only selection decisions, and hash-chained activation receipts are separate immutable stages.
- External review's highest-priority inference is that Plan 04 must keep token-aware production activation default-off until active-corpus routing exists in Plan 06; no external finding has been accepted before repository-backed adjudication.
- Plan review is closed after two loops: 11 plans/22 tasks, all SC-64.4-1..6 and D-01..D-24 mapped, canonical T64.4 IDs, structural/YAML/XML checks green, external verdict clean, and independent GSD/Codex verdicts clean.

## Last Failure

None.
