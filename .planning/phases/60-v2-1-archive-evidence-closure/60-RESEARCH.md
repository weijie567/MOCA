# Phase 60: v2.1 Archive Evidence Closure - Research

**Researched:** 2026-07-08 [VERIFIED: local date/context]
**Domain:** planning/evidence archive closure, formal verification artifacts, Nyquist validation artifacts, milestone audit reconciliation [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:9-36]
**Confidence:** HIGH for repository inventory and planning boundaries; MEDIUM for final audit outcome because it depends on execution-time reruns and `$gsd-audit-milestone`. [VERIFIED: local artifact inventory] [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:62-72]

<user_constraints>
## User Constraints (from CONTEXT.md)

Source: copied from `.planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md`. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md]

### Locked Decisions

#### Evidence Closure Scope
- **D-01:** Treat `.planning/v2.1-MILESTONE-AUDIT.md` as the primary gap ledger for Phase 60. The phase must close the listed formal verification and Nyquist validation gaps, while recognizing that Phase 59 already closed the approval-resume runtime integration gap.
- **D-02:** Generate missing formal `*-VERIFICATION.md` artifacts for Phases 37, 43, 48, 48.1, 49, 50, and 56. Each artifact must be based on real phase summaries, source files, tests, and current repo evidence, not a restatement of the milestone audit.
- **D-03:** Refresh, create, or explicitly exempt Nyquist validation artifacts for Phases 37, 38, 40, 41, 42, 44, 49, and 50. Existing compliant validation artifacts outside this list should not be churned.
- **D-04:** Normalize nonstandard verification metadata for Phases 40 and 42 when practical. If preserving retroactive/non-frontmatter evidence is more honest, document the accepted metadata caveat explicitly in Phase 60 summary and milestone audit closure.
- **D-05:** Resolve the Phase 37 / TPH-04 DB-backed pytest note by rerunning an approved `UV_CACHE_DIR=/tmp/uv-cache uv run ...` command when the local DB is available; if not available or not required for strict archive proof, carry it forward as named debt with evidence and a concrete next entry point.
- **D-06:** After evidence artifacts are updated, reconcile `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, and `.planning/v2.1-MILESTONE-AUDIT.md` so they distinguish implementation completion from strict archive evidence closure.
- **D-07:** The phase is complete only after a follow-up `$gsd-audit-milestone` reaches archive-ready status, or every remaining issue is recorded as accepted post-v2.1 debt with owner/target phase.

#### Planning Granularity
- **D-08:** Do not plan Phase 60 as one large artifact-writing plan. Split into dependency-ordered plans with narrow ownership: formal verification artifacts first, validation/Nyquist artifacts second, final archive audit and state reconciliation last.
- **D-09:** Verification artifacts may be generated in grouped batches, but each target phase must have its own evidence trail and requirement mapping. Avoid a single generic “all phases verified” document.
- **D-10:** Validation artifact work should prefer focused existing test commands and evidence already recorded in phase summaries. Add tests only if a real requirement lacks automated evidence and the missing check is safe to add without implementation changes.

#### Evidence Standards
- **D-11:** All test commands recorded in Phase 60 artifacts must use MOCA-approved entrypoints: `UV_CACHE_DIR=/tmp/uv-cache uv run ...` or repository `.venv/bin/...`. Bare `pytest` and bare `python -m pytest` are invalid as verification evidence.
- **D-12:** Archive evidence must separate source-verified facts, accepted limitations, and unresolved debt. The Phase 49 parent-operation replay limitation is accepted Phase 49 scope, not an archive blocker by itself.
- **D-13:** Phase 50 is a SPEC-only phase; its validation may be a document/spec/guardrail validation artifact rather than runtime implementation tests, but the rationale must be explicit.
- **D-14:** Phase 60 should update only planning/evidence artifacts unless a validation gap proves a real test or source guard is missing. Any source-code change triggers normal GSD code review, security, validation, and MOCA architecture-debt rules.

### Claude's Discretion
- Choose the exact grouping of target phases into plans, provided the plan boundaries remain reviewable and dependency-ordered.
- Choose the specific focused verification commands per target phase after reading that phase's summaries, plans, and existing tests.
- Decide whether a missing validation artifact should be filled with new automated tests, existing command evidence, or an explicit manual/exemption rationale, based on the underlying phase type and current codebase evidence.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within Phase 60 archive evidence closure scope.
</user_constraints>

## Project Constraints (from CLAUDE.md / AGENTS.md)

- Planning/evidence docs should use Chinese by default where practical; technical names, commands, paths, APIs, and identifiers may remain English. [VERIFIED: AGENTS.md:5-11]
- Any MOCA local validation/debug/verification failure should be recorded in `.planning/LOCAL-VALIDATION-ISSUES.md` with symptom, repro, evidence, root-cause judgment, handling, remaining issue, and next entry point. [VERIFIED: AGENTS.md:13-15] [VERIFIED: CLAUDE.md:7-9]
- Changes touching tool calling, RAG, memory, or intent recognition architecture debt should update `.planning/ARCHITECTURE-DEBT.md`; Phase 60 should avoid source changes unless evidence proves a real implementation defect. [VERIFIED: AGENTS.md:17-23] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:36]
- MOCA test evidence must not use bare `pytest` or bare `python -m pytest`; Phase 60 should record only `UV_CACHE_DIR=/tmp/uv-cache uv run ...` or repository `.venv/bin/...` commands. [VERIFIED: AGENTS.md:25-29] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:33]
- Phase-level planning must split work when a phase spans multiple ownership domains, waves, or gates; a single large Phase 60 plan would violate MOCA planning rules. [VERIFIED: AGENTS.md:60-64] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:28-30]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
| --- | --- | --- |
| TPH-03 | Tool declarations resolve from a single-source registry and duplicate hardcoded lists are derived or consistency-checked. [VERIFIED: .planning/REQUIREMENTS.md:19] | Phase 37 needs `37-VERIFICATION.md`, refreshed validation, and a current-equivalent command because the historical manager test file was later deleted by Phase 41. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:14,108,137] [VERIFIED: tests/agent/test_tools/test_unified_tool_manager.py missing in local inventory] |
| TPH-04 | Runtime failures use one shared helper and runtime auth uses a declarative gate sequence without external contract shape changes. [VERIFIED: .planning/REQUIREMENTS.md:23] | Phase 37 needs formal verification plus either a serial DB-backed rerun or named accepted debt for the DB-backed pytest note. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:15,28,219] [VERIFIED: .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-03-SUMMARY.md:87-106] |
| IDR-02 | Multi-intent utterances are preserved as bounded Tier-A `TaskPlan`, with only s1 effective and later steps visible as deferred. [VERIFIED: .planning/REQUIREMENTS.md:30] | Phase 43 has complete validation but lacks `43-VERIFICATION.md`. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:16,113,138] [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-VALIDATION.md] |
| MEM-COMPAT-01 | Active memory-context readers use canonical surfaces without destructive renames. [VERIFIED: .planning/REQUIREMENTS.md:41] | Phase 48.1 has complete validation but lacks `48.1-VERIFICATION.md`. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:17,119,140] [VERIFIED: .planning/phases/48.1-memory-context-compatibility-debt-cleanup/48.1-VALIDATION.md] |
| GAD-01-IMPL | `investigate` is migrated to bounded read-only ReAct with ToolPlatform dispatch, projection boundary, fallback, and loop-local slots; it closed with replay parent-operation limitation. [VERIFIED: .planning/REQUIREMENTS.md:47] | Phase 49 lacks both `49-VERIFICATION.md` and `49-VALIDATION.md`, and its accepted limitation must remain explicit rather than fixed inside Phase 60. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:18,120,141,174-180] [VERIFIED: .planning/DEFERRED-DECISIONS.md:21-28] |
| CAGM-01 | Phase 50 locks the canonical Agent Graph migration charter, 15-node target, exclusions, source hierarchy, validation matrix, phase order, and final no-debt gate. [VERIFIED: .planning/REQUIREMENTS.md:53] | Phase 50 is SPEC-only and lacks both formal verification and validation; validation can be document/spec/static-guardrail based. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:19,121,142,197] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:35] |
| CAGM-07 | `recommendation_generation` replaces active `generate_recommendation`, and RAG/claim fail-closed states prevent unsafe evidence or unsupported claims from entering action paths. [VERIFIED: .planning/REQUIREMENTS.md:59] | Phase 56 has complete validation/security/UAT/review evidence but lacks `56-VERIFICATION.md`. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:20,127,143] [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-VALIDATION.md] |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
| --- | --- | --- | --- |
| Formal verification artifact creation | Planning / Evidence | Source/tests/docs | The output is `*-VERIFICATION.md` under `.planning/phases/*`, but each artifact must cite current source, tests, summaries, reviews, and accepted debt. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:20,87-99] |
| Nyquist validation artifact refresh | Planning / Validation | Test infrastructure | The output is `*-VALIDATION.md`, and the artifact must map requirements to runnable commands or explicit exemptions. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:180-208] [VERIFIED: .planning/config.json] |
| Phase 37 DB-backed evidence closure | Test infrastructure | Planning / Evidence | The proof is a serial pytest rerun against the local PostgreSQL-backed `moca_test` fixture or named debt with exact environment evidence. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:23] [VERIFIED: tests/conftest.py:30-81] |
| Milestone audit closeout | GSD workflow / Planning | Requirements and roadmap docs | The final gate is a follow-up `$gsd-audit-milestone` and reconciliation of `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, and `.planning/v2.1-MILESTONE-AUDIT.md`. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:24-25] |

## Scope and Non-Scope

- Scope is evidence/archive closure for Phase 60: create missing verification artifacts, refresh or create validation artifacts, normalize metadata caveats, resolve or carry forward the Phase 37 DB-backed note, reconcile tracking docs, and rerun the milestone audit. [VERIFIED: .planning/ROADMAP.md:535-548] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:9-36]
- In-scope formal verification targets are Phases 37, 43, 48, 48.1, 49, 50, and 56. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:135-143]
- In-scope Nyquist validation cleanup targets are Phases 37, 38, 40, 41, 42, 44, 49, and 50. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:180-208]
- In-scope metadata caveats are Phase 40 non-frontmatter verification and Phase 42 retroactive non-frontmatter verification. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:28-35] [VERIFIED: .planning/phases/40-tool-contract-validation-hardening/40-VERIFICATION.md] [VERIFIED: .planning/phases/42-intent-recognition-three-layer-decoupling/42-VERIFICATION.md]
- Phase 59 is not a Phase 60 artifact target, but its `59-VERIFICATION.md` is required closeout evidence that the prior approval-resume terminal memory integration gap is fixed. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:74] [VERIFIED: .planning/phases/59-approval-resume-terminal-memory-finalization/59-VERIFICATION.md]
- Non-scope: new runtime behavior, graph nodes, tool contracts, memory semantics, approval behavior, frontend UX, or broad refactors. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:11,36]
- Non-scope: fixing Phase 49 parent-operation replay limitation inside Phase 60; it is accepted Phase 49 scope unless a later named hardening phase is created. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:34] [VERIFIED: .planning/DEFERRED-DECISIONS.md:21-28]

## Gap Inventory by Target Phase

| Phase | Current Artifacts | Gap Status | Planning Implication |
| --- | --- | --- | --- |
| 37 | `37-01/02/03-SUMMARY.md`, `37-REVIEW.md`, and draft `37-VALIDATION.md` exist; `37-VERIFICATION.md` is missing. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-VALIDATION.md] | Formal verification missing; validation is draft/noncompliant; DB-backed pytest note remains open. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:14-15,184,219] | Plan must write `37-VERIFICATION.md`, refresh `37-VALIDATION.md`, and handle DB-backed evidence with current-equivalent tests because `tests/agent/test_tools/test_unified_tool_manager.py` is gone after Phase 41. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/41-tool-platform-legacy-manager-cleanup/41-VERIFICATION.md] |
| 38 | `38-VERIFICATION.md` exists and passed; `38-VALIDATION.md` exists but remains draft/noncompliant. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-VERIFICATION.md] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-VALIDATION.md] | Nyquist cleanup only; formal verification is not missing. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:184-185] | Plan should refresh metadata/status from existing verification/UAT evidence rather than rerun a full Phase 38 implementation gate unless the planner wants fresh confidence. [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-HUMAN-UAT.md] |
| 40 | `40-VERIFICATION.md` exists and records PASS but lacks YAML frontmatter; no `40-VALIDATION.md` exists. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/40-tool-contract-validation-hardening/40-VERIFICATION.md] | Metadata caveat plus missing Nyquist validation. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:28-31,186-187] | Plan should either add standard metadata to verification or explicitly preserve the human-valid retroactive artifact, and should create `40-VALIDATION.md` from the existing summaries/verification. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:22] |
| 41 | `41-VERIFICATION.md`, `41-REVIEW.md`, and `41-CLOSURE-REVIEW.md` exist; no `41-VALIDATION.md` exists. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/41-tool-platform-legacy-manager-cleanup/41-VERIFICATION.md] | Missing Nyquist validation. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:187] | Plan should create `41-VALIDATION.md` using existing no-legacy grep, ToolPlatform tests, architecture tests, and review evidence. [VERIFIED: .planning/phases/41-tool-platform-legacy-manager-cleanup/41-VERIFICATION.md] |
| 42 | `42-VERIFICATION.md` exists as retroactive non-frontmatter evidence; no `42-VALIDATION.md` exists. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/42-intent-recognition-three-layer-decoupling/42-VERIFICATION.md] | Metadata caveat plus missing Nyquist validation. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:32-35,188] | Plan should not pretend Phase 42 ran normal plan-then-execute; create validation or exemption that states retroactive nature and maps IDR-01 evidence honestly. [VERIFIED: .planning/ROADMAP.md:160-178] |
| 43 | `43-VALIDATION.md` is complete/nyquist-compliant; no `43-VERIFICATION.md` exists. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-VALIDATION.md] | Formal verification missing. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:16,113,138] | Plan should write `43-VERIFICATION.md` from summaries, validation, review, UAT, and current intent tests. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/] |
| 44 | `44-VERIFICATION.md` exists and passed; no `44-VALIDATION.md` exists. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-VERIFICATION.md] | Missing Nyquist validation. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:188-189] | Plan should create `44-VALIDATION.md` from existing verification commands and the Phase 45 lifecycle defer; no new implementation should be planned. [VERIFIED: .planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-VERIFICATION.md] |
| 48 | `48-VALIDATION.md`, review, security, UAT, and four summaries exist; no `48-VERIFICATION.md` exists. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/48-narrow-long-term-explicit-preference-memory/48-VALIDATION.md] | Formal verification missing. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:118-140] | Plan should write `48-VERIFICATION.md` as a phase-level MEM-05 evidence closeout using summaries/validation/security/UAT/review. [VERIFIED: .planning/phases/48-narrow-long-term-explicit-preference-memory/] |
| 48.1 | `48.1-VALIDATION.md`, review, and four summaries exist; no `48.1-VERIFICATION.md` exists. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/48.1-memory-context-compatibility-debt-cleanup/48.1-VALIDATION.md] | Formal verification missing. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:17,119,140] | Plan should write `48.1-VERIFICATION.md` for MEM-COMPAT-01 and explicitly record remaining legacy names as deferred compatibility debt, not missing implementation. [VERIFIED: .planning/phases/48.1-memory-context-compatibility-debt-cleanup/48.1-04-SUMMARY.md] |
| 49 | Four summaries and plan review exist; no `49-VERIFICATION.md` or `49-VALIDATION.md` exists. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/49-investigate-bounded-react-loop-migration/49-04-SUMMARY.md] | Formal verification and Nyquist validation missing; accepted replay parent-operation limitation must be preserved. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:18,120,141,197] [VERIFIED: .planning/DEFERRED-DECISIONS.md:21-28] | Plan should create both artifacts and close as implemented-with-limitations evidence, not fully remove the limitation. [VERIFIED: .planning/phases/49-investigate-bounded-react-loop-migration/49-04-SUMMARY.md] |
| 50 | `50-SPEC.md` and `50-SUMMARY.md` exist; no `50-VERIFICATION.md` or `50-VALIDATION.md` exists. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md] | Formal verification and validation missing; phase is SPEC-only. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:19,121,142,197] | Plan should create spec/static validation and formal verification that confirms charter presence, boundaries, downstream order, and no runtime code change. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:1-280] |
| 56 | `56-VALIDATION.md`, review, review-fix, security, UAT, and four summaries exist; no `56-VERIFICATION.md` exists. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-VALIDATION.md] | Formal verification missing only. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:20,127,143] | Plan should write `56-VERIFICATION.md` using validation/security/UAT/review-fix evidence and CAGM-07 requirement mapping. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/] |

## Evidence Sources to Read

| Target | Primary Evidence | Current Source/Test Evidence |
| --- | --- | --- |
| Phase 37 / TPH-03, TPH-04 | `37-01-SUMMARY.md`, `37-02-SUMMARY.md`, `37-03-SUMMARY.md`, `37-REVIEW.md`, `37-VALIDATION.md`, `.planning/ARCHITECTURE-DEBT.md`, `.planning/LOCAL-VALIDATION-ISSUES.md`. [VERIFIED: local `find` inventory] [VERIFIED: .planning/ARCHITECTURE-DEBT.md:115-131] [VERIFIED: .planning/LOCAL-VALIDATION-ISSUES.md:9930-10105] | `src/tools/catalog.py`, `src/tools/runtime.py`, `src/tools/policy.py`, `tests/tools/test_catalog.py`, `tests/tools/test_tool_platform.py`, `tests/replay/test_tool_policy_events.py`, `tests/architecture/test_trusted_context_boundaries.py`, `tests/architecture/test_tool_boundaries.py`. [VERIFIED: local `rg` source/test scan] |
| Phase 38 / validation cleanup | `38-VERIFICATION.md`, `38-HUMAN-UAT.md`, `38-VALIDATION.md`, `38-01/02/03-SUMMARY.md`. [VERIFIED: local `find` inventory] | `tests/tools/test_catalog.py`, `tests/tools/test_tool_platform.py`, high-blast consumer tests named in `38-VERIFICATION.md`. [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-VERIFICATION.md] |
| Phase 40 / TPH-05 metadata and validation | `40-01/02/03-SUMMARY.md`, `40-VERIFICATION.md`, `40-CONTEXT.md`. [VERIFIED: local `find` inventory] | `tests/tools/test_catalog.py`, `tests/tools/test_tool_platform.py`, `tests/architecture/test_tool_contract_backstops.py`, `tests/architecture/test_tool_boundaries.py`. [VERIFIED: local `rg` test scan] |
| Phase 41 / TPH-06 validation | `41-01/02/03/04-SUMMARY.md`, `41-REVIEW.md`, `41-VERIFICATION.md`, `41-CLOSURE-REVIEW.md`. [VERIFIED: local `find` inventory] | `tests/tools/test_tool_platform.py`, `tests/architecture/test_tool_boundaries.py`, and no-legacy `rg` scans. [VERIFIED: .planning/phases/41-tool-platform-legacy-manager-cleanup/41-VERIFICATION.md] |
| Phase 42 / retroactive validation | `42-VERIFICATION.md`, `42-01-SUMMARY.md`, `.planning/ARCHITECTURE-DEBT.md` intent section. [VERIFIED: local `find` inventory] [VERIFIED: .planning/ARCHITECTURE-DEBT.md:194-252] | `src/agent/intent_policy.py`, `src/agent/nodes/classify_intent.py`, `tests/agent/test_intent_routing.py`, `tests/agent/test_graph.py`, `tests/architecture/test_phase32_static_contract.py`. [VERIFIED: .planning/ARCHITECTURE-DEBT.md:202-218] |
| Phase 43 / IDR-02 | `43-01/02/03-SUMMARY.md`, `43-VALIDATION.md`, `43-REVIEW.md`, `43-UAT.md`. [VERIFIED: local `find` inventory] | `tests/agent/test_intent_task_plan.py`, `tests/agent/test_nodes/test_classify_intent.py`, `tests/agent/test_nodes/test_receive_request.py`, `tests/agent/test_nodes/test_final_response.py`, `tests/agent/test_graph.py`. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-VALIDATION.md] |
| Phase 44 / MEM-01, MEM-02 validation | `44-01/02/03/04-SUMMARY.md`, `44-VERIFICATION.md`, `44-REVIEW.md`, `.planning/MEMORY-REDESIGN-DECISIONS.md`. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-VERIFICATION.md] | `tests/db/test_phase44_schema.py`, `tests/memory/test_case_identity.py`, `tests/memory/test_case_working_context_repo.py`, `tests/memory/test_thread_case_links.py`, `tests/memory/test_case_working_context_service.py`, `tests/memory/test_phase44_contract_alignment.py`. [VERIFIED: .planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-VERIFICATION.md] |
| Phase 48 / MEM-05 | `48-01/02/03/04-SUMMARY.md`, `48-VALIDATION.md`, `48-REVIEW.md`, `48-SECURITY.md`, `48-UAT.md`. [VERIFIED: local `find` inventory] | Memory preference, policy, review, and retrieval tests listed in `48-VALIDATION.md`. [VERIFIED: .planning/phases/48-narrow-long-term-explicit-preference-memory/48-VALIDATION.md] |
| Phase 48.1 / MEM-COMPAT-01 | `48.1-01/02/03/04-SUMMARY.md`, `48.1-VALIDATION.md`, `48.1-REVIEW.md`. [VERIFIED: local `find` inventory] | `tests/memory/test_phase48_1_memory_compat_alignment.py`, `tests/memory/test_thread_case_links.py`, `tests/conversation/test_repository.py`, and canonical session/reviewed-memory tests listed in `48.1-VALIDATION.md`. [VERIFIED: .planning/phases/48.1-memory-context-compatibility-debt-cleanup/48.1-VALIDATION.md] |
| Phase 49 / GAD-01-IMPL | `49-01/02/03/04-SUMMARY.md`, `49-PLAN-REVIEW.md`, `.planning/DEFERRED-DECISIONS.md`, `.planning/ARCHITECTURE-DEBT.md`. [VERIFIED: local `find` inventory] [VERIFIED: .planning/DEFERRED-DECISIONS.md:21-28] | `src/agent/nodes/investigate.py`, `tests/agent/test_nodes/test_investigate.py`, `tests/agent/test_graph.py`, `tests/tools/test_tool_platform.py`, `tests/replay/test_operation_pairing.py`, `tests/replay/test_replay_service.py`. [VERIFIED: local `rg` source/test scan] |
| Phase 50 / CAGM-01 | `50-SPEC.md`, `50-SUMMARY.md`, Phase 51-58 artifacts showing downstream use, `tests/architecture/test_canonical_graph_baseline.py`. [VERIFIED: local `find` inventory] [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md] | Static spec/doc checks plus graph baseline/no-debt tests are sufficient because Phase 50 has no runtime source changes. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:103-113,229-250] |
| Phase 56 / CAGM-07 | `56-01/02/03/04-SUMMARY.md`, `56-VALIDATION.md`, `56-REVIEW.md`, `56-REVIEW-FIX.md`, `56-SECURITY.md`, `56-UAT.md`, `.planning/ARCHITECTURE-DEBT.md` RAG section. [VERIFIED: local `find` inventory] [VERIFIED: .planning/ARCHITECTURE-DEBT.md:300-345] | `tests/agent/test_graph_vocabulary.py`, `tests/agent/test_trace.py`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`, `tests/agent/test_nodes/test_recommendation_generation.py`, `tests/agent/test_rag_context_routing.py`, `tests/agent/rag_context/test_routing.py`, `tests/knowledge/test_verified_evidence_package.py`, `tests/knowledge/test_claim_verification_bundle.py`. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-VALIDATION.md] |
| Phase 59 / prior audit gap closure | `59-VALIDATION.md`, `59-VERIFICATION.md`, `59-REVIEW.md`, `59-SECURITY.md`, `59-UAT.md`. [VERIFIED: local `find` inventory] | `src/api/services/agent_run_memory.py`, `src/api/routers/approvals.py`, `src/api/routers/agent_runs.py`, `tests/test_approval_api.py`, `tests/test_agent_runs_api.py`, `tests/agent/test_memory_write_node.py`. [VERIFIED: .planning/phases/59-approval-resume-terminal-memory-finalization/59-VERIFICATION.md] |

## Plan Granularity Recommendation

Recommended shape: five dependency-ordered plans, not one umbrella plan. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:28-30] [VERIFIED: AGENTS.md:60-64]

| Plan | Ownership | Artifacts | Why This Boundary |
| --- | --- | --- | --- |
| `60-01` | Formal verification, tool + intent + memory evidence batch A. [ASSUMED: plan numbering recommendation] | Create `37-VERIFICATION.md`, `43-VERIFICATION.md`, `48-VERIFICATION.md`, `48.1-VERIFICATION.md`. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:135-140] | These phases already have summaries/validation evidence; this plan can focus on phase-level truth mapping and current-source spot checks. [VERIFIED: local artifact inventory] |
| `60-02` | Formal verification, graph/ReAct/spec/RAG evidence batch B. [ASSUMED: plan numbering recommendation] | Create `49-VERIFICATION.md`, `50-VERIFICATION.md`, `56-VERIFICATION.md`; preserve Phase 49 accepted limitation and Phase 50 spec-only rationale. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:141-143] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:34-35] | These targets share graph/RAG/canonical migration context and need careful distinction between implemented facts, spec-only charter, and accepted limitation. [VERIFIED: .planning/DEFERRED-DECISIONS.md:21-28] [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md] |
| `60-03` | Nyquist validation cleanup for historical/tool/memory phases. [ASSUMED: plan numbering recommendation] | Refresh/create `37-VALIDATION.md`, `38-VALIDATION.md`, `40-VALIDATION.md`, `41-VALIDATION.md`, `42-VALIDATION.md`, `44-VALIDATION.md`; normalize or caveat `40-VERIFICATION.md` and `42-VERIFICATION.md`. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:180-208] [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:28-35] | This plan owns validation metadata and can keep retroactive/nonstandard evidence honest without mixing in final audit reconciliation. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:22] |
| `60-04` | Nyquist validation for graph/spec closure plus Phase 37 DB-note decision. [ASSUMED: plan numbering recommendation] | Create `49-VALIDATION.md`, `50-VALIDATION.md`; serially rerun Phase 37 current-equivalent DB-backed command if possible or record named debt. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:197] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:23] | Phase 49 and 50 need different validation semantics than standard implementation phases, and the DB-backed rerun can mutate the local shared test DB, so it should be isolated. [VERIFIED: .planning/DEFERRED-DECISIONS.md:21-28] [VERIFIED: tests/conftest.py:30-81] |
| `60-05` | Tracking reconciliation and archive gate. [ASSUMED: plan numbering recommendation] | Update `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/v2.1-MILESTONE-AUDIT.md`, Phase 60 summary/validation, then run `$gsd-audit-milestone`. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:24-25] | This plan should only run after artifacts exist so milestone status reflects actual evidence, not planned evidence. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:53,62-72] |

## Verification Strategy

### Environment

- `uv`, Python 3.12.13, pytest 9.0.3, and ruff 0.15.12 are available through `UV_CACHE_DIR=/tmp/uv-cache uv run ...`. [VERIFIED: local probe `uv --version`; local probe `UV_CACHE_DIR=/tmp/uv-cache uv run python --version`; local probe `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --version`; local probe `UV_CACHE_DIR=/tmp/uv-cache uv run ruff --version`]
- `pg_isready` is not available on the host PATH, but `localhost:5432` is reachable and Docker shows `moca-postgres-1` running and healthy with `5432->5432`. [VERIFIED: local probe `pg_isready`] [VERIFIED: local probe `nc -z localhost 5432`] [VERIFIED: local probe `docker ps`]
- The test fixture uses fixed `postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test` and drops/creates metadata in `test_engine`; DB-backed pytest commands must be serial, not parallel. [VERIFIED: tests/conftest.py:30-81] [VERIFIED: .planning/LOCAL-VALIDATION-ISSUES.md:19130-19212]
- `gsd-sdk query init.phase-op "60"` reports `agents_installed: false` and missing `gsd-integration-checker`, `gsd-nyquist-auditor`, `gsd-ui-auditor`, and `gsd-doc-verifier`; final audit planning should be ready to handle tool fallback or manual evidence review if the audit workflow cannot spawn expected agents. [VERIFIED: local `gsd-sdk query init.phase-op "60"`]

### Artifact Checks

Use artifact existence checks before and after each plan. [VERIFIED: local `find` inventory]

```bash
test -f .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-VERIFICATION.md
test -f .planning/phases/43-intent-recognition-multi-intent-tier-a/43-VERIFICATION.md
test -f .planning/phases/48-narrow-long-term-explicit-preference-memory/48-VERIFICATION.md
test -f .planning/phases/48.1-memory-context-compatibility-debt-cleanup/48.1-VERIFICATION.md
test -f .planning/phases/49-investigate-bounded-react-loop-migration/49-VERIFICATION.md
test -f .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-VERIFICATION.md
test -f .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-VERIFICATION.md
test -f .planning/phases/40-tool-contract-validation-hardening/40-VALIDATION.md
test -f .planning/phases/41-tool-platform-legacy-manager-cleanup/41-VALIDATION.md
test -f .planning/phases/42-intent-recognition-three-layer-decoupling/42-VALIDATION.md
test -f .planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-VALIDATION.md
test -f .planning/phases/49-investigate-bounded-react-loop-migration/49-VALIDATION.md
test -f .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-VALIDATION.md
```

Scan Phase 60-created/updated artifacts for invalid command entrypoints. [VERIFIED: AGENTS.md:25-29]

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'from pathlib import Path; bad=[]; roots=[Path(".planning/phases/60-v2-1-archive-evidence-closure"), Path(".planning/phases")]; phase_files=[]; phase_files += list(Path(".planning/phases/60-v2-1-archive-evidence-closure").glob("60-*.md")); phase_files += [p for p in Path(".planning/phases").glob("*/*-VALIDATION.md") if p.name.split("-")[0] in {"37","38","40","41","42","44","49","50"}]; phase_files += [p for p in Path(".planning/phases").glob("*/*-VERIFICATION.md") if p.name.split("-")[0] in {"37","43","48","48.1","49","50","56"}]; [bad.append(f"{p}:{i}:{line.strip()}") for p in phase_files for i,line in enumerate(p.read_text(encoding="utf-8").splitlines(),1) if line.strip().startswith(("pytest ", "python -m pytest"))]; assert not bad, "\\n".join(bad)'
```

### Recommended Current-Equivalent Test Commands

- Phase 37 current-equivalent DB-backed gate should not include deleted `tests/agent/test_tools/test_unified_tool_manager.py`; use current catalog/platform/replay/architecture tests and run serially. [VERIFIED: local inventory showing deleted file] [VERIFIED: tests/tools/test_catalog.py] [VERIFIED: tests/tools/test_tool_platform.py]

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/replay/test_tool_policy_events.py tests/architecture/test_trusted_context_boundaries.py tests/architecture/test_tool_boundaries.py -q
```

- Phase 40 validation can use the focused tool contract hardening suite. [VERIFIED: .planning/phases/40-tool-contract-validation-hardening/40-VERIFICATION.md] [VERIFIED: local test scan]

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py tests/tools/test_tool_platform.py tests/architecture/test_tool_contract_backstops.py -q
```

- Phase 41 validation can use ToolPlatform/no-legacy coverage plus an explicit no-legacy grep. [VERIFIED: .planning/phases/41-tool-platform-legacy-manager-cleanup/41-VERIFICATION.md]

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_tool_platform.py tests/architecture/test_tool_boundaries.py -q
rg -n "UnifiedToolManager|from src\\.tools\\.manager(\\s|$)|import src\\.tools\\.manager(\\s|$)|tool_manager|action_tool_manager|\\._platform" src tests docs/contract-spec.md --glob '!**/.planning/**'
```

- Phase 42/43 intent validation can reuse existing intent suites with the approved cache prefix. [VERIFIED: .planning/phases/42-intent-recognition-three-layer-decoupling/42-VERIFICATION.md] [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-VALIDATION.md]

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/architecture/test_phase32_static_contract.py -q
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_final_response.py tests/agent/test_nodes/test_receive_request.py -q
```

- Phase 44 validation can map directly to the passing verification suite and Alembic head check. [VERIFIED: .planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-VERIFICATION.md]

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/db/test_phase44_schema.py tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py tests/memory/test_phase44_contract_alignment.py -q
UV_CACHE_DIR=/tmp/uv-cache uv run alembic heads
```

- Phase 48 and 48.1 verification can cite existing complete validation evidence; reruns should use the full gates already defined in their validation artifacts with the approved prefix. [VERIFIED: .planning/phases/48-narrow-long-term-explicit-preference-memory/48-VALIDATION.md] [VERIFIED: .planning/phases/48.1-memory-context-compatibility-debt-cleanup/48.1-VALIDATION.md]

- Phase 49 validation should include investigate, graph, replay, tool-platform, intent, memory, and approval/action no-regression slices. [VERIFIED: .planning/phases/49-investigate-bounded-react-loop-migration/49-01-SUMMARY.md] [VERIFIED: .planning/phases/49-investigate-bounded-react-loop-migration/49-04-SUMMARY.md]

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py tests/agent/test_graph.py tests/tools/test_tool_platform.py tests/replay/test_operation_pairing.py tests/replay/test_replay_service.py -q
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_classify_intent.py tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_memory_evidence_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_phase48_1_memory_compat_alignment.py tests/memory/test_phase48_long_term_preference_alignment.py tests/test_approval_gate.py tests/agent/test_phase22_action_boundary.py tests/test_interception_rate.py -q
```

- Phase 50 validation should be static/doc/spec-only unless the planner intentionally adds an artifact consistency script. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:103-113] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:35]

```bash
test -f .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md
rg -n "receive_request|safety_pre_route|session_context_load|contextual_intent_resolve|slot_resolution_gate|memory_context_load|recommendation_generation|risk_gate|Final No-Debt Gate|Temporary Compatibility Policy" .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py -q
```

- Phase 56 verification can cite existing final validation/review-fix evidence; a fresh confidence rerun can use the post-review focused suite. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-VALIDATION.md]

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_routing.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_nodes/test_recommendation_generation.py tests/agent/test_phase22_action_boundary.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_rag_context_routing.py tests/agent/test_trace.py tests/architecture/test_canonical_graph_baseline.py tests/test_agent_runs_api.py tests/test_execute_action.py tests/test_graph_routing.py tests/test_trace_api.py -q --tb=short
```

- Phase 59 closeout evidence can be spot-checked to prove the original integration gap is closed before rerunning milestone audit. [VERIFIED: .planning/phases/59-approval-resume-terminal-memory-finalization/59-VERIFICATION.md]

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_approval_resume_completed_runs_terminal_memory_finalizer tests/test_approval_api.py::test_approval_resume_trace_persistence_failure_fails_closed_after_terminal_surfaces tests/test_approval_api.py::test_completed_resume_reconciliation_rechecks_status_under_lock tests/agent/test_memory_write_node.py::test_memory_write_node_skips_approval_marked_states -q
```

### Final Archive Gate

- After artifact and tracking-doc reconciliation, rerun `$gsd-audit-milestone`; Phase 60 is done only if the audit reaches archive-ready/passed or every remaining gap is named accepted post-v2.1 debt with owner and target phase. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:25] [VERIFIED: .planning/ROADMAP.md:548]
- If audit tooling cannot run because required GSD agents are missing, record the exact blocker and either install/repair the tooling or perform a manual equivalent only if the orchestrator accepts that substitution. [VERIFIED: local `gsd-sdk query init.phase-op "60"`]

## Risks / Known Debt

- Phase 37 historical test commands include the deleted legacy manager test file; blindly copying those commands into Phase 60 would create false failures. [VERIFIED: .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-01-SUMMARY.md:98-105] [VERIFIED: local file inventory] [VERIFIED: .planning/phases/41-tool-platform-legacy-manager-cleanup/41-VERIFICATION.md]
- Phase 37 DB-backed pytest debt can likely be retried now because PostgreSQL is reachable, but DB-backed commands must run serially due shared `moca_test` schema setup. [VERIFIED: local probe `nc -z localhost 5432`] [VERIFIED: tests/conftest.py:30-81] [VERIFIED: .planning/LOCAL-VALIDATION-ISSUES.md:19130-19212]
- Phase 40 verification is human-valid but nonstandard because it lacks YAML frontmatter; normalizing it is safe if content remains truthful, but preserving it with an explicit caveat is also allowed by Phase 60 context. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:28-31] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:22]
- Phase 42 is retroactive evidence; rewriting it into a standard-looking plan-then-execute artifact would be misleading. [VERIFIED: .planning/ROADMAP.md:160-178] [VERIFIED: .planning/phases/42-intent-recognition-three-layer-decoupling/42-VERIFICATION.md]
- Phase 49 must remain `IMPLEMENTED_WITH_LIMITATIONS` for replay parent-operation semantics; Phase 60 should document, not erase, that limitation. [VERIFIED: .planning/DEFERRED-DECISIONS.md:21-28] [VERIFIED: .planning/phases/49-investigate-bounded-react-loop-migration/49-04-SUMMARY.md]
- Phase 50 validation is intentionally spec/static because the phase changed planning/architecture artifacts rather than runtime code. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SUMMARY.md] [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:103-113]
- `REQUIREMENTS.md` currently marks the seven Phase 60-linked requirements as pending evidence closure even though base implementation is recorded in original phase artifacts; final reconciliation should update this distinction only after artifacts exist. [VERIFIED: .planning/REQUIREMENTS.md:81-106]
- `.planning/LOCAL-VALIDATION-ISSUES.md` and `.planning/STATE.md` are already modified in the worktree before this research write; Phase 60 planning/execution should not revert unrelated existing changes. [VERIFIED: local `git status --short`]

## Planner Inputs

- Required deliverables: `37-VERIFICATION.md`, `43-VERIFICATION.md`, `48-VERIFICATION.md`, `48.1-VERIFICATION.md`, `49-VERIFICATION.md`, `50-VERIFICATION.md`, `56-VERIFICATION.md`, refreshed `37-VALIDATION.md`, refreshed `38-VALIDATION.md`, new `40-VALIDATION.md`, new `41-VALIDATION.md`, new `42-VALIDATION.md`, new `44-VALIDATION.md`, new `49-VALIDATION.md`, new `50-VALIDATION.md`, and reconciled milestone tracking docs. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:135-143,180-208] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:24]
- Each `*-VERIFICATION.md` should include goal, observable truths, artifacts checked, source/test/doc evidence, requirement coverage, command evidence or reason for not rerunning, accepted limitations, residual risk, and final status. [ASSUMED: recommended verification artifact pattern from existing `59-VERIFICATION.md` and `44-VERIFICATION.md`]
- Each `*-VALIDATION.md` should include frontmatter with `status: complete`, `nyquist_compliant: true` or explicit exemption, `wave_0_complete`, test infrastructure, requirement-to-test map, closeout evidence, manual-only rationale if any, and sign-off. [VERIFIED: existing compliant validation artifacts `43-VALIDATION.md`, `48.1-VALIDATION.md`, `56-VALIDATION.md`]
- Phase 60 should avoid changing source/tests unless a current requirement lacks any safe automated evidence; if source/test changes are required, that must trigger normal code review/security/validation and architecture-debt rules. [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:31-36] [VERIFIED: AGENTS.md:17-23]
- `REQUIREMENTS.md` should not mark TPH-03, TPH-04, IDR-02, MEM-COMPAT-01, GAD-01-IMPL, CAGM-01, and CAGM-07 fully archive-closed until their formal verification and validation gaps are actually closed or accepted as named debt. [VERIFIED: .planning/REQUIREMENTS.md:81-106] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:24-25]
- `ROADMAP.md`, `STATE.md`, and `.planning/v2.1-MILESTONE-AUDIT.md` should distinguish base implementation completion from strict archive evidence closure until the follow-up audit passes. [VERIFIED: .planning/v2.1-MILESTONE-AUDIT.md:53,62-72] [VERIFIED: .planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md:24]
- The planner should include an artifact-command scan and `git diff --check` in the final plan because prior Phase 56/59 local issue logs show shell quoting, artifact glob, and whitespace problems can create false failures. [VERIFIED: .planning/LOCAL-VALIDATION-ISSUES.md:16922-17025] [VERIFIED: .planning/LOCAL-VALIDATION-ISSUES.md:19130-19212]

## Sources

- `.planning/phases/60-v2-1-archive-evidence-closure/60-CONTEXT.md` - locked scope, decisions, evidence standards, canonical refs. [VERIFIED: local read]
- `.planning/v2.1-MILESTONE-AUDIT.md` - primary gap ledger for formal verification, Nyquist, metadata caveats, and prior integration gap. [VERIFIED: local read]
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` - requirement IDs, phase goals, current milestone state, traceability. [VERIFIED: local read]
- Target phase directories under `.planning/phases/{37,38,40,41,42,43,44,48,48.1,49,50,56,59}-*` - current artifacts and source evidence. [VERIFIED: local `find` inventory]
- `AGENTS.md` and `CLAUDE.md` - MOCA command, workflow, validation, and ledger rules. [VERIFIED: local read]
- `pyproject.toml`, `uv.lock`, `tests/conftest.py`, `docker-compose.yml` - tool/test/DB environment facts. [VERIFIED: local read/probe]
- `.planning/ARCHITECTURE-DEBT.md`, `.planning/DEFERRED-DECISIONS.md`, `.planning/LOCAL-VALIDATION-ISSUES.md` - accepted debt, limitation, and local-validation context. [VERIFIED: local read]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
| --- | --- | --- | --- |
| A1 | Five-plan decomposition is the recommended structure. | Plan Granularity Recommendation | Planner could choose four or six plans; must still preserve formal verification first, validation second, audit/reconciliation last. |
| A2 | Existing Phase 59/44 verification artifact shape is a good template for Phase 60-generated verification files. | Planner Inputs | Planner may prefer a different template, but artifacts still need source-backed truths, requirement mapping, commands, gaps, and residual risk. |

## RESEARCH COMPLETE
