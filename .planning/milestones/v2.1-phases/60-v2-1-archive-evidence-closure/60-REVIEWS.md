---
phase: 60
reviewers: [claude]
reviewed_at: 2026-07-08T11:35:42Z
plans_reviewed:
  - .planning/phases/60-v2-1-archive-evidence-closure/60-01-PLAN.md
  - .planning/phases/60-v2-1-archive-evidence-closure/60-02-PLAN.md
  - .planning/phases/60-v2-1-archive-evidence-closure/60-03-PLAN.md
  - .planning/phases/60-v2-1-archive-evidence-closure/60-04-PLAN.md
  - .planning/phases/60-v2-1-archive-evidence-closure/60-05-PLAN.md
---

# Cross-AI Plan Review - Phase 60

## Claude Review

# Cross-AI Plan Review - MOCA Phase 60 (v2.1 Archive Evidence Closure)

## Overall Assessment

The five-plan set is well-decomposed, dependency-ordered, and collectively covers all six Phase 60 success criteria with no orphaned requirements. Boundaries are clean (verification first, validation second, DB-note + graph/spec validation third, reconciliation + audit gate last), and the plans are commendably honest about retroactive evidence (Phase 42), accepted limitations (Phase 49), and spec-only status (Phase 50). The dominant risks are not scope or ordering - they are (1) an archive-gate task that depends on tooling the research already found missing, and (2) acceptance gates that verify keyword presence but cannot detect the exact failure mode the phase is meant to prevent (ledger restatement dressed up as source-backed verification).

---

## Cross-Cutting Concerns (apply to multiple plans)

- **[HIGH] The final archive gate (60-05 Task 3) may be unexecutable as written.** Research states `gsd-sdk query init.phase-op "60"` reports `agents_installed: false` with `gsd-integration-checker`, `gsd-nyquist-auditor`, etc. missing. Task 3 correctly forbids "silently substitute an unlabelled manual audit," but its acceptance criteria still *require* a terminal `workflow_status`/`status` in {passed, archive_ready, complete, complete_with_accepted_debt}. If the audit tool cannot run and the orchestrator does not sanction a labelled fallback, the executor is caught between "stop with Phase 60 incomplete" and an acceptance regex that demands a passing status. In full autopilot this is exactly where a model is tempted to write `complete_with_accepted_debt` to satisfy the grep without a real audit. Needs an explicit third branch: "audit tooling unavailable -> record `status: blocked_tooling_unavailable` + concrete repair/next-entry note, and treat Phase 60 as not-closed" - with that value accepted by the grep so the executor is never forced to choose between honesty and passing.

- **[MEDIUM] Acceptance gates are grep-only and cannot detect the primary quality risk.** D-02/D-09 demand each artifact be "based on real code/docs/tests, not a restatement of the milestone audit." Every acceptance criterion is `test -f` + `rg` keyword match - which a fabricated/restated artifact containing the right keywords passes trivially. The STRIDE entries (e.g. T-60-01-02 Repudiation) name this but the mitigation ("cite files") is unverifiable by grep. This is inherent to evidence-doc generation, but the gate is weakest precisely against the phase's central obligation. Consider requiring at least one `file:line` citation pattern per requirement row (e.g. `rg 'src/.*\.py:[0-9]+'`) so artifacts must anchor to real source loci, as the existing `44-VERIFICATION.md` does.

- **[MEDIUM] No plan enforces the "planning/evidence artifacts only" rule (D-14).** Several Task 3 scans only reject bare `pytest`/`python -m pytest` lines and the `git diff` check is described in prose ("shows only planning/evidence artifact changes") without an automated assertion. Add an automated guard, e.g. `git diff --name-only` must contain only `.planning/` paths, so accidental source edits fail the gate rather than relying on reviewer eyeballing.

- **[MEDIUM] Verification artifacts are paper-only for most phases; only Phase 37 mandates a fresh rerun.** 60-04 Task 2 genuinely reruns the Phase 37 current-equivalent suite (good). But 43/48/48.1/56/49 verification permits "command evidence *or* explicit no-rerun rationale." For an archive gate, phases whose code could have drifted since completion (weeks ago) deserve at least a focused spot rerun - the research already supplies exact commands for each. Recommend mandating one focused rerun per verification artifact where a MOCA-approved command exists, reserving "no-rerun rationale" for genuinely doc/spec-only cases (Phase 50).

- **[LOW] Language inconsistency.** AGENTS.md defaults planning docs to Chinese; existing `42-VERIFICATION.md` is Chinese while `44-`/`59-VERIFICATION.md` are English. Plans don't specify a language, so the seven new artifacts will drift stylistically. Not blocking; a one-line "match the target phase's existing artifact language" instruction would keep the archive coherent.

---

## 60-01 - Formal Verification Batch A (37, 43, 48, 48.1)

**Summary:** Cleanly creates four phase-specific verification artifacts with correct separation of TPH-03 vs TPH-04 and honest preservation of the Phase 37 DB-note handoff and Phase 48.1 compatibility debt. The strongest-scoped plan in the set.

**Strengths**
- Correctly forces TPH-03 and TPH-04 into *separate* evidence rows and explicitly forbids erasing the DB-note (`status: passed_with_followup`).
- Phase 48.1 framed as `passed_with_accepted_compatibility_debt`, matching MEM-COMPAT-01 reality rather than overclaiming.
- No source files in `files_modified`; disjoint from 60-02 so wave-1 parallelism is safe.

**Concerns**
- **[MEDIUM]** Acceptance for Phase 37 requires `passed_with_followup` and a DB-note line but does not require any `file:line` source anchor - restatement risk (see cross-cutting).
- **[LOW]** Phase 48 verification duplicates work already fully covered by `48-VALIDATION/SECURITY/UAT/REVIEW`; risk of a thin "wrapper" artifact. Requiring it to cite the specific security threat IDs (T-48-xx) closed would give it independent value.

**Suggestions**
- Add one `rg 'src/.*:[0-9]+'` acceptance per artifact to force source anchoring.
- Specify artifact language per target phase.

**Risk:** LOW

---

## 60-02 - Formal Verification Batch B (49, 50, 56)

**Summary:** Handles the three trickiest phases well - implemented-with-limitation (49), spec-only (50), and RAG/claim fail-closed (56) - with correct status semantics for each.

**Strengths**
- Phase 49 mandates a dedicated `Accepted Limitation` section for the replay parent-operation gap and forbids "fixing" it in Phase 60 (D-12 honored).
- Phase 50 correctly typed `passed_spec_only` with an explicit "no runtime rewiring; Phases 51-58 own implementation" note.
- 56 verification maps to the real fail-closed/action-claim authority boundary, not just a rename.

**Concerns**
- **[MEDIUM]** Phase 56 is the highest-stakes safety requirement (unsafe evidence / unsupported action claims must not reach action paths), yet its verification is permitted to rest on existing validation without a mandated rerun. Given the action-boundary blast radius, a focused rerun of the CAGM-07 suite should be required, not optional.
- **[LOW]** 50-VERIFICATION acceptance regex includes `runtime source` as a required token - brittle phrasing dependency; a semantic "no runtime code change" assertion would be more robust than a literal string match.

**Suggestions**
- Mandate the Phase 56 focused rerun (research supplies the command).
- Loosen literal-token acceptance to `rg -i` where phrasing is incidental.

**Risk:** LOW-MEDIUM

---

## 60-03 - Nyquist Validation Batch A (37, 38, 40, 41, 42, 44)

**Summary:** Refreshes/creates six validation artifacts and handles the 40/42 metadata caveats honestly. Correctly keeps 37 at `nyquist_compliant: false` pending 60-04.

**Strengths**
- Keeps Phase 42 explicitly `complete_retroactive` and blocks conflating IDR-01 with IDR-02 - matches the retroactive registration reality.
- Phase 37 validation deliberately deferred to `false` until 60-04 resolves the DB note; no premature green.
- Offers a genuine choice (normalize frontmatter vs. preserve + caveat) for the nonstandard 40/42 artifacts rather than forcing a rewrite.

**Concerns**
- **[MEDIUM] `read_first` references files that may not exist.** Task 2 lists `44-REVIEW-ADJUDICATION.md`; the research inventory only confirms `44-REVIEW.md` and `44-VERIFICATION.md`. The mandatory read_first gate can hard-fail on a nonexistent file. Verify the filename against disk or mark it conditional.
- **[MEDIUM]** `42-VALIDATION.md` acceptance pattern `IDR-02.*not` requires the negation and the token on one line - brittle; an executor writing "IDR-02 (multi-intent) was out of scope for Phase 42" on a wrapped line fails the grep despite being correct.
- **[LOW]** Three plans (60-03, 60-04, 60-05) sequentially rewrite `37-VALIDATION.md`; heavy churn on one file, though ordering is sound.

**Suggestions**
- Confirm/adjust the `44-REVIEW-ADJUDICATION.md` reference before execution.
- Replace fragile one-line regexes (`IDR-02.*not`) with token-presence checks plus a prose instruction.

**Risk:** MEDIUM (mainly the read_first file-existence risk)

---

## 60-04 - Graph/Spec Validation + Phase 37 DB-Note (49, 50, 37)

**Summary:** The only plan doing real fresh execution (the Phase 37 DB-backed rerun) with a well-designed resolve/carry-forward branch and a proper named-debt token. Strong.

**Strengths**
- Explicit three-way branch on the DB command: pass -> resolve; environment failure -> named debt `TPH-04-DB-EVIDENCE-POST-V2.1` with owner + target phase + `LOCAL-VALIDATION-ISSUES.md` entry; real defect -> stop (no source changes). This is exactly the right handling.
- Uses the *current-equivalent* command that excludes the deleted `test_unified_tool_manager.py` - the research flagged this trap and the plan avoids it.
- 49/50 validation semantics (`complete_with_accepted_limitation`, `complete_spec_only`) are consistent with 60-02.

**Concerns**
- **[MEDIUM]** The automated verify requires the exact command string appear verbatim in both `37-VALIDATION.md` and `37-VERIFICATION.md` (`cmd in val and cmd in ver`). If the executor renders the command inside a fenced block, wrapped, or with any spacing variance, the substring check fails despite correct content. Recommend normalizing to a stable single-line form or relaxing to a component-token check.
- **[LOW]** DB rerun mutates the shared `moca_test` schema and must run serially - the plan says so in prose but nothing enforces serial execution if the executor batches. Given it's the only DB task in its wave, low likelihood, but worth an explicit "-p no:xdist"/serial note.

**Suggestions**
- Pin the exact command string once (a fenced canonical form) and have both artifacts and the verify block reference that identical string.

**Risk:** MEDIUM

---

## 60-05 - Reconciliation + Archive Gate

**Summary:** Correctly gates ledger reconciliation behind full artifact inventory and refuses to claim archive-ready before the audit runs. But it inherits the fragile dependency on missing audit tooling, making it the riskiest plan.

**Strengths**
- Task 1 hard-stops reconciliation until all 15 target artifacts exist - prevents ledgers claiming closure ahead of evidence.
- Preserves the implementation-completion vs. archive-evidence-closure distinction (D-06) rather than flattening statuses.
- Named-debt branch for TPH-04 is threaded through to REQUIREMENTS/audit consistently.

**Concerns**
- **[HIGH]** Archive-gate tooling dependency (see cross-cutting): acceptance demands a terminal status while the tool may be unrunnable, with no accepted "blocked" value. This is the single most likely point where autopilot either stalls or fabricates a status.
- **[MEDIUM]** `$gsd-audit-milestone` in a plan `execution_context` (`@.../gsd-audit-milestone/SKILL.md`) assumes the skill loads; if it doesn't, the executor has no defined evidence standard for a "manual equivalent" and the plan explicitly disallows an unlabelled one - an under-specified dead-end.
- **[LOW]** Task 2 sets `5/5 complete` "only after this plan records the final audit result," but Task 2 runs *before* Task 3's audit - the ordering note is correct in prose but the two tasks touch overlapping ledger claims; ensure `5/5 complete` is written in Task 3, not Task 2, to avoid a transient inconsistent state.

**Suggestions**
- Add an explicit `status: blocked_tooling_unavailable` terminal branch, accepted by the grep, that marks Phase 60 not-closed with a concrete repair entry point - so honesty and gate-passing don't conflict.
- Move the actual `5/5 complete` write into Task 3 post-audit.

**Risk:** MEDIUM-HIGH

---

## Overall Risk: MEDIUM

Justification: Scope, sequencing, requirement coverage, and honesty conventions are all sound - the plans will produce the required artifacts in the right order. Risk concentrates in two places: the archive-gate's dependency on audit tooling the research already found missing (60-05, could stall or induce a fabricated status under autopilot), and grep-only acceptance that cannot enforce the "source-backed, not restated" obligation that is the phase's whole point. Both are addressable with small, targeted edits - an accepted `blocked_tooling_unavailable` status, mandated focused reruns on the safety-critical phases (37 already done, add 56), a `file:line` anchor requirement, an automated "only `.planning/` paths changed" guard, and fixing the `44-REVIEW-ADJUDICATION.md` read_first reference. None require restructuring the five-plan decomposition.

---

## Consensus Summary

Only the external Claude reviewer was requested and run for this autopilot stage, so this is a single-reviewer synthesis rather than a multi-reviewer consensus.

### Agreed Strengths

- Five-plan decomposition and wave ordering are sound.
- Requirement coverage is complete.
- Phase 42 retroactive evidence, Phase 49 accepted limitation, and Phase 50 spec-only semantics are handled honestly.
- The Phase 37 DB-note branch in `60-04` is directionally correct.

### Agreed Concerns

- `60-05` needs an honest blocked-tooling branch if `$gsd-audit-milestone` cannot run due missing audit agents.
- Evidence artifacts need stronger source-backed safeguards than keyword-only greps.
- Plans should mechanically enforce that Phase 60 touches only `.planning/` evidence artifacts unless a real defect stops execution.
- `60-03` may reference a nonexistent `44-REVIEW-ADJUDICATION.md`.
- Phase 56 should likely get a focused rerun because it is safety-sensitive CAGM-07 evidence.

### Divergent Views

No divergent reviewer views; only one external reviewer was run.

---

## Claude Review - Loop 2

### Summary

The revised five-plan set is materially improved. Source-anchor requirements, `.planning/`-only diff guards, Phase 56 mandated rerun, Phase 42 regex hardening, Phase 37 DB-note component matching, and deferred `5/5 complete` write are present and correct. The decomposition, wave ordering, and honesty conventions remain sound.

### Remaining Concerns

- **HIGH-if-tooling-absent / MEDIUM-if-present:** `60-05` prose says audit-tooling unavailability is a hard stop, but the acceptance regex still required a passing terminal status. Suggested fix: allow `blocked_tooling_unavailable` as an explicitly incomplete status with a concrete next entry point.
- **MEDIUM:** `60-02` Phase 56 focused rerun lacks an environment-failure branch. Suggested fix: mirror `60-04` with pass / environment-failure named debt / real-defect stop handling.
- **LOW:** `git status --short` guard is fragile on renames, but Phase 60 does not plan renames.
- **LOW:** `60-04` prose says `.planning/LOCAL-VALIDATION-ISSUES.md` scan handles newly appended invalid commands, but automation intentionally omits that file to avoid historical false positives.
- **LOW:** evidence-anchor grep raises the floor but remains one-anchor-satisfiable.

### Already Resolved

- Source-backed `path:line` anchors.
- `.planning/`-only change guard.
- Phase 56 focused rerun mandate.
- Phase 42 negation check hardening.
- Phase 37 DB-note component-token matching.
- DB rerun serial note.
- `5/5 complete` moved post-audit.
- `44-REVIEW-ADJUDICATION.md` verified as present.

### Risk Assessment

Medium. Residual risk is concentrated in the audit-tooling unavailable branch and Phase 56 rerun environment handling. Both are small targeted repairs.
