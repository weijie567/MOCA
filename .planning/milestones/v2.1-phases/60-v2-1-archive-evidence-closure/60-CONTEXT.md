# Phase 60: v2.1 Archive Evidence Closure - Context

**Gathered:** 2026-07-08T10:55:24Z
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 60 closes the remaining v2.1 archive evidence gaps after Phase 59 fixed the approval-resume terminal memory lifecycle gap. This phase creates or refreshes formal verification and Nyquist validation artifacts, reconciles milestone-tracking documents, and reruns the milestone audit until v2.1 is archive-ready or any remaining issue is deliberately recorded as accepted post-v2.1 debt.

This is an evidence-closure and archive-gate phase. It must not introduce new runtime product behavior, graph nodes, tool contracts, memory semantics, approval behavior, or frontend UX. If validating a requirement exposes a real implementation defect, record the defect and stop or plan a named follow-up instead of silently widening Phase 60.

</domain>

<decisions>
## Implementation Decisions

### Evidence Closure Scope
- **D-01:** Treat `.planning/v2.1-MILESTONE-AUDIT.md` as the primary gap ledger for Phase 60. The phase must close the listed formal verification and Nyquist validation gaps, while recognizing that Phase 59 already closed the approval-resume runtime integration gap.
- **D-02:** Generate missing formal `*-VERIFICATION.md` artifacts for Phases 37, 43, 48, 48.1, 49, 50, and 56. Each artifact must be based on real phase summaries, source files, tests, and current repo evidence, not a restatement of the milestone audit.
- **D-03:** Refresh, create, or explicitly exempt Nyquist validation artifacts for Phases 37, 38, 40, 41, 42, 44, 49, and 50. Existing compliant validation artifacts outside this list should not be churned.
- **D-04:** Normalize nonstandard verification metadata for Phases 40 and 42 when practical. If preserving retroactive/non-frontmatter evidence is more honest, document the accepted metadata caveat explicitly in Phase 60 summary and milestone audit closure.
- **D-05:** Resolve the Phase 37 / TPH-04 DB-backed pytest note by rerunning an approved `UV_CACHE_DIR=/tmp/uv-cache uv run ...` command when the local DB is available; if not available or not required for strict archive proof, carry it forward as named debt with evidence and a concrete next entry point.
- **D-06:** After evidence artifacts are updated, reconcile `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, and `.planning/v2.1-MILESTONE-AUDIT.md` so they distinguish implementation completion from strict archive evidence closure.
- **D-07:** The phase is complete only after a follow-up `$gsd-audit-milestone` reaches archive-ready status, or every remaining issue is recorded as accepted post-v2.1 debt with owner/target phase.

### Planning Granularity
- **D-08:** Do not plan Phase 60 as one large artifact-writing plan. Split into dependency-ordered plans with narrow ownership: formal verification artifacts first, validation/Nyquist artifacts second, final archive audit and state reconciliation last.
- **D-09:** Verification artifacts may be generated in grouped batches, but each target phase must have its own evidence trail and requirement mapping. Avoid a single generic “all phases verified” document.
- **D-10:** Validation artifact work should prefer focused existing test commands and evidence already recorded in phase summaries. Add tests only if a real requirement lacks automated evidence and the missing check is safe to add without implementation changes.

### Evidence Standards
- **D-11:** All test commands recorded in Phase 60 artifacts must use MOCA-approved entrypoints: `UV_CACHE_DIR=/tmp/uv-cache uv run ...` or repository `.venv/bin/...`. Bare `pytest` and bare `python -m pytest` are invalid as verification evidence.
- **D-12:** Archive evidence must separate source-verified facts, accepted limitations, and unresolved debt. The Phase 49 parent-operation replay limitation is accepted Phase 49 scope, not an archive blocker by itself.
- **D-13:** Phase 50 is a SPEC-only phase; its validation may be a document/spec/guardrail validation artifact rather than runtime implementation tests, but the rationale must be explicit.
- **D-14:** Phase 60 should update only planning/evidence artifacts unless a validation gap proves a real test or source guard is missing. Any source-code change triggers normal GSD code review, security, validation, and MOCA architecture-debt rules.

### the agent's Discretion
- Choose the exact grouping of target phases into plans, provided the plan boundaries remain reviewable and dependency-ordered.
- Choose the specific focused verification commands per target phase after reading that phase's summaries, plans, and existing tests.
- Decide whether a missing validation artifact should be filled with new automated tests, existing command evidence, or an explicit manual/exemption rationale, based on the underlying phase type and current codebase evidence.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 60 scope and archive gaps
- `.planning/ROADMAP.md` — Phase 60 goal, requirements, success criteria, and v2.1 phase sequencing.
- `.planning/STATE.md` — Current milestone state, Phase 60 position, and accumulated context for affected phases.
- `.planning/REQUIREMENTS.md` — Requirement IDs and current Phase 60 pending evidence mapping for TPH-03, TPH-04, IDR-02, MEM-COMPAT-01, GAD-01-IMPL, CAGM-01, and CAGM-07.
- `.planning/v2.1-MILESTONE-AUDIT.md` — Primary gap ledger: missing formal verification artifacts, partial/missing Nyquist validation, metadata caveats, and accepted debt.

### Contract and target architecture references
- `docs/contract-spec.md` — Normative contract source for tool, memory, graph, ReAct, and evidence boundaries.
- `docs/target-agent-platform-architecture-plan.md` — Readable target architecture reference for canonical Agent Graph migration context.
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` — Binding Phase 50 migration charter for CAGM-01 and downstream canonical graph phases.

### Target phase evidence directories
- `.planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/` — TPH-03/TPH-04 summaries and draft validation evidence.
- `.planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/` — Existing partial/draft validation and DB-backed evidence context.
- `.planning/phases/40-tool-contract-validation-hardening/` — Nonstandard verification metadata and missing validation target.
- `.planning/phases/41-tool-platform-legacy-manager-cleanup/` — Existing verification and missing validation target.
- `.planning/phases/42-intent-recognition-three-layer-decoupling/` — Retroactive verification metadata and missing validation target.
- `.planning/phases/43-intent-recognition-multi-intent-tier-a/` — IDR-02 summaries/validation and missing formal verification target.
- `.planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/` — Existing verification and missing validation target.
- `.planning/phases/48-narrow-long-term-explicit-preference-memory/` — MEM-05 summaries/validation and missing formal verification target.
- `.planning/phases/48.1-memory-context-compatibility-debt-cleanup/` — MEM-COMPAT-01 summaries/validation and missing formal verification target.
- `.planning/phases/49-investigate-bounded-react-loop-migration/` — GAD-01-IMPL summaries, accepted limitation, and missing formal verification/validation targets.
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/` — CAGM-01 spec/summary and missing formal verification/validation targets.
- `.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/` — CAGM-07 summaries/validation and missing formal verification target.
- `.planning/phases/59-approval-resume-terminal-memory-finalization/` — Phase 59 evidence that the previous integration gap is fixed before archive closure.

### Project rules
- `AGENTS.md` — MOCA-specific language, local-validation issue ledger, architecture-debt ledger, and test command entrypoint rules.
- `.planning/codebase/CONVENTIONS.md` — Planning artifact naming and code/test conventions.
- `.planning/codebase/TESTING.md` — Test organization and broad test patterns; MOCA-specific entrypoint override in `AGENTS.md` is authoritative.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing phase summaries, validation files, verification files, review reports, security reports, and UAT files under `.planning/phases/` are the primary source material for Phase 60.
- `gsd-sdk query init.phase-op`, `gsd-sdk query commit`, and milestone audit commands can be used to locate phase directories and persist planning artifact changes.
- Existing pytest/ruff commands recorded in phase artifacts should be reused where they are still meaningful and MOCA-approved.

### Established Patterns
- Phase artifacts use phase-prefixed filenames such as `37-VERIFICATION.md` and `37-VALIDATION.md`.
- Validation artifacts use frontmatter with `status`, `nyquist_compliant`, and evidence sections where possible.
- Verification artifacts should include concrete observable truths, artifacts checked, requirement coverage, command evidence, gaps, and residual risks.
- MOCA forbids bare `pytest` / bare `python -m pytest` as valid verification evidence.

### Integration Points
- Phase 60 will mainly touch `.planning/phases/*` evidence artifacts plus `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, and `.planning/v2.1-MILESTONE-AUDIT.md`.
- Source-code and test files should only be touched if a real validation gap cannot be closed with current test evidence.
- Final closeout must rerun the milestone audit and update the audit artifact/status based on actual results.

</code_context>

<specifics>
## Specific Ideas

- Use a strict archive-gate standard: every requirement should have implementation evidence, formal verification evidence, and validation evidence or an explicit accepted debt/exemption.
- Keep Phase 60 artifact language precise about retroactive evidence. Do not pretend older phases followed a workflow they did not follow.
- Preserve existing accepted limitations, especially Phase 49's parent-operation replay limitation, as named limitations instead of trying to “fix” them in Phase 60.
- The user asked for full autopilot, so planning should minimize future interactive questions and make conservative decisions from repository evidence.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 60 archive evidence closure scope.

</deferred>

---

*Phase: 60-v2-1-archive-evidence-closure*
*Context gathered: 2026-07-08T10:55:24Z*
