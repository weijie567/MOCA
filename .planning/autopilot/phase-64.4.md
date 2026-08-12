---
phase: "64.4"
status: running
current_step: execute
current_plan: "17"
plan_review_loop: 6
quota_waits: 0
updated_at: "2026-08-12T11:52:00+08:00"
next_command: "execute Plan17 deterministic manifest issuance and lease gate"
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
- Stage 5 execution Plan 10 reached the planned bounded stop: activation receipt mechanics, fresh parity, a complete inactive token candidate and three immutable nonpassing provider attempts were retained; no selection or pointer mutation occurred. After the third execution error exposed missing role-level provenance, the user approved a reviewed recovery replan on 2026-08-12.
- Fresh recovery review found five real blockers: crash-partial diagnostic publication, ambiguous unavailable retry evidence, unbounded unknown-defect repair, missing immediate ledgers and a forbidden Plan10 summary rewrite. Claude additionally identified procedural attempt caps and false-closeout risk.
- The repaired recovery expands the phase from 11 plans/22 tasks to 14 plans/28 tasks: Plan11 uses a single commit manifest as the diagnostic bundle visibility point without provider calls; Plan12 machine-enforces a two-slot selection budget and never repairs unknown defects; Plan13 owns the reversible activation drill plus live closeout guard; Plan14 owns final docs/regression closeout. Plan10 failure evidence remains untouched.
- Clean recovery re-review passed: fresh GSD checker closed all five blockers/two warnings with no new finding; external Claude returned PASS with no actionable blocker or warning; Codex final coverage/order/scope adjudication is clean.
- Stage 5 recovery Plan 11 complete: crash-consistent manifest-committed execution diagnostics, strict redaction, typed role/round/stage/rollback provenance and fault-injection coverage committed in five atomic commits; format/lint and 166 focused tests passed with no live provider, selection or pointer mutation.
- Stage 5 recovery Plan 12 complete under its fail-closed checkpoint revision: cap=2 reserve-before-provider ledger and closed retry matrix passed 183 tests; fresh parity passed but the old complete candidate bound the previous report SHA, so exact readiness refused before budget creation with slots still 0/2 and pointer/history unchanged.
- Fresh review rejected the first rebuild draft on three repository-backed blockers: DB-commit-before-state-publish could lose the candidate identity, build provider retries lacked a machine cap, and cap=2 A-B attempts could be reset through an alternate output root while activation lacked pre-CAS budget lineage.
- Current superseding recovery authority is 20 plans/40 tasks: Plan15 is the blocked checkpoint; Plan16 repairs exact claim-state publication/recovery; Plan17 implements and proves the manifest-issuance/current-lease gate; Plan18 resumes the same candidate and runs canonical A-B; Plan19 activates and guards closeout; Plan20 owns docs/full regression.
- Clean authority repair re-review passed: fresh GSD checker and external Claude both returned no blocker or warning; Codex independently accepted the repository-backed results and authorized execution from Plan13.
- Stage 5 recovery Plan 13 complete: fixed descriptor/recover-state, atomic state publication, descriptor-bound per-document cap=2 provider budget and single MOCA retry authority committed in five atomic commits; full lint and 45 focused tests passed with no live provider, candidate, DB, pointer/history or A-B side effect.
- Stage 5 recovery Plan 14 complete: canonical production recovery root, actual candidate-state/parity rehash, separate create-only recovery authorization and real pre-CAS enforcement committed in five atomic commits; full lint and 202 scoped tests passed with no live provider, DB, A-B slot/evidence or pointer/history side effect.
- Stage 5 recovery Plan 15 stopped truthfully before its first build reservation/provider construction: the sole retained descriptor/run/candidate reached DB `building`, state version 2, document index 0, but only `states/00000002.json` was published while the canonical reader requires contiguous v1 first. Candidate attempts/results remain 0/0; canonical A-B manifest remains absent at 0/2; selection, authorization, activation, pointer/history and requirement completion remain zero.
- A bounded 20-plan / 40-task recovery draft preserves Plan15 as the checked blocked checkpoint, keeps Plan16 only for deterministic future v1->v2 claim publication plus exact same-candidate v1 predecessor recovery, adds Plan17 for deterministic manifest issuance/current lease gating and a zero-side-effect refusal on the still-building candidate, moves same-candidate build/issuance/A-B to Plan18, activation/guard to Plan19 and docs/full regression to Plan20.
- Stage 5 recovery Plan16 complete: future claim publication is ordered v1 then v2 across separate transactions, exact predecessor recovery is building/v2/index0-only, identical replay fsyncs parent, and the retained candidate gained only canonical v1 with all budgets and DB authority unchanged.
- Plans16-20 passed the fresh GSD checker and repository-backed Codex adjudication; external clean-review retries were unavailable because both providers returned quota errors and are recorded as unavailable, not as PASS. The reviewed plans are execution authority, while every absolute lease and zero-side-effect stop gate remains binding.
- User execution boundary after Plan16: freeze the phase at 20 plans, run Plans17-20 strictly serially, stop each RED as soon as it proves the gap, read only the current plan's necessary delta, and stop truthfully on live lease expiry without renewal, a second candidate, or another recovery-chain expansion.

## Evidence

- Phase goal: replace character-count policy chunk sizing with a versioned tokenizer-aware final-embedding-input assembly contract and validate safe reindex A/B behavior against the sealed Phase 64.3 baseline.
- Phase boundaries exclude parser, retrieval/reranker, ContextBuilder/claim-verifier redesign, embedding-model replacement, parent-child chunking, and generation-model prompt budgets.
- ROADMAP requires six success criteria covering tokenizer parity, hard final-input token bounds, authoritative chunk assembly, identity/replay compatibility, isolated rollback-safe reindexing, and a versioned A/B report.
- Production must fail closed on unknown tokenizer/count failures and may keep character sizing only as an explicit A/B baseline, never a silent fallback.
- Phase completion requires a token-aware candidate that passes hard safety and fixed same-run non-regression gates; a truthful red candidate report alone is not completion.
- Planning must split tokenizer/parity, assembly/path convergence, persistence/reindex, and A/B/cutover into separate dependency-ordered plans.
- Original granularity was 11 plans/22 tasks; after the Plan15 claim-state blocker the reviewed and now frozen authority is 20 plans/40 tasks, still 2 tasks and at most 12 files per plan. Plan16 is complete; Plans17-20 execute strictly serially under R-28.
- `evidence_identity.v1` remains corpus-free; canonical document source content comes from ordered blocks, chunk compatibility is config-aware, and corpus projections control visibility only.
- Provider parity, all-outcome terminal A/B reports, passing-only selection decisions, and hash-chained activation receipts are separate immutable stages.
- External review's highest-priority inference is that Plan 04 must keep token-aware production activation default-off until active-corpus routing exists in Plan 06; no external finding has been accepted before repository-backed adjudication.
- Plans11-14 executed. Plan15 is a truthful blocked checkpoint with no completed requirement; Plan16 completed exact state recovery, and Plans17-20 remain dependency-ordered execution work.

## Last Failure

No provider request, candidate build reservation or A-B slot was consumed by the Plan15 failure or Plan16 recovery. Plan16 restored only the exact immutable v1 predecessor and preserved the descriptor `f8e190f1-ad0e-4476-9f77-704735e3dc46`, candidate `64932871-4488-4b8b-b438-a02791a1151f`, v2 state and unused build manifest. Plan17 is current; expiry or drift is a truthful stop, never authority to bypass review, renew the lease, create another candidate or extend the recovery chain.
