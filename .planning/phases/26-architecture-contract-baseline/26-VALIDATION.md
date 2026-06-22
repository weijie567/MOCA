---
phase: 26
slug: architecture-contract-baseline
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-22
---

# Phase 26 - Validation Strategy

Per-phase validation contract for the architecture/spec/eval baseline.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | Markdown, `rg`, `gsd-sdk`, shell format checks |
| Config file | `.planning/config.json` |
| Quick run command | `gsd-sdk query init.plan-phase 26 && gsd-sdk query roadmap.get-phase 26` |
| Full suite command | Run `git diff --check -- docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md .planning/phases/26-architecture-contract-baseline .planning/ROADMAP.md .planning/STATE.md .planning/REQUIREMENTS.md`, the target file fence check below, `gsd-sdk query state.load`, and `gsd-sdk query roadmap.analyze --pick next_phase`. |
| Estimated runtime | ~15 seconds |

## Sampling Rate

- After every task commit: run the quick command.
- After every plan wave: run the full suite command.
- Before `$gsd-verify-work`: full suite must be green, except known non-blocking `validate.health` warnings for old completed phase directories and future phase directories.
- Max feedback latency: 30 seconds for command-based checks.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 26-01-01 | 01 | 1 | APF-01 | T26-01 | Normative contract names remain synchronized across spec, architecture plan, and eval plan | docs-contract | `rg -n "VerifiedEvidencePackageV1|ClaimVerificationBundleV1|ToolPolicyDecision|BusinessFactResultV1|DecisionEventEnvelopeV1|route_after_rag_context|route_after_claim_verify" docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md` | yes | pending |
| 26-01-02 | 01 | 1 | APF-02 | T26-02 | Module ownership identifies owners, dependencies, forbidden imports, and decision events without enabling direct repository access | docs-contract | `rg -n "Module Ownership|Owns|forbidden imports|Decision Event|BusinessFactService|ToolPlatform|KnowledgeService|Observability" docs/target-agent-platform-architecture-plan.md docs/contract-spec.md` | yes | pending |
| 26-01-03 | 01 | 1 | APF-01, APF-02 | T26-03 | GSD metadata still resolves v1.9 Phase 26 and does not require destructive phase cleanup | tooling | `gsd-sdk query init.plan-phase 26 && gsd-sdk query state.load && gsd-sdk query roadmap.analyze --pick next_phase` | yes | pending |
| 26-01-04 | 01 | 1 | APF-01, APF-02 | T26-04 | Markdown/docs edits are parseable and no runtime code files are modified without explicit plan justification | docs-format | `git diff --check -- docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md .planning/phases/26-architecture-contract-baseline .planning/ROADMAP.md .planning/STATE.md .planning/REQUIREMENTS.md` plus the target file fence check below | yes | pending |

## Target File Fence Check

```bash
for f in docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md .planning/phases/26-architecture-contract-baseline/*.md; do
  c=$(rg -n '^```' "$f" | wc -l | tr -d ' ')
  test $((c % 2)) -eq 0
done
```

## Wave 0 Requirements

- [x] `.planning/phases/26-architecture-contract-baseline/26-CONTEXT.md` - locked user decisions for Phase 26.
- [x] `.planning/phases/26-architecture-contract-baseline/26-RESEARCH.md` - phase research with validation architecture.
- [x] `.planning/phases/26-architecture-contract-baseline/26-VALIDATION.md` - this validation strategy.

Existing infrastructure covers all Phase 26 requirements.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cross-document semantic agreement | APF-01 | `rg` proves names exist but cannot prove the three docs assign the same authority semantics | Read the touched sections in `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, and `docs/eval-test-plan.md`; verify graph vocabulary, AgentState fields, RAG/claim contracts, tool policy, business facts, decision events, approval/action boundary, and eval gates agree. |
| Module ownership quality | APF-02 | Ownership matrices require architectural judgment beyond string presence | Verify each platform/domain module lists owned schemas/tables/events, public methods, allowed downstream calls, forbidden imports/access patterns, and decision events. |
| Scope containment | APF-01, APF-02 | Preventing runtime implementation scope creep requires diff review | Run `git status --short` and inspect changed files. Phase 26 should touch docs/planning artifacts unless PLAN.md explicitly justifies a code-level helper or test. |

## Validation Sign-Off

- [x] All tasks have command-based or manual verification.
- [x] Sampling continuity: no three consecutive tasks should proceed without a command-based check.
- [x] Wave 0 covers all missing validation references.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 30 seconds for command-based checks.
- [x] `nyquist_compliant: true` set in frontmatter.

Approval: pending Phase 26 plan execution.
