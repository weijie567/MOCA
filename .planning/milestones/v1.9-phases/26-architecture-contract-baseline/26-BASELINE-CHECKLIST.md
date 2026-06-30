---
phase: 26
plan: 26-01
status: completed
created: 2026-06-22
normative: false
requirements:
  - APF-01
  - APF-02
---

# Phase 26 Baseline Checklist

This file is a non-normative Phase 26 verification artifact. It records audit results for APF-01 and APF-02, but it does not define executable contracts. `docs/contract-spec.md` remains MOCA's only normative contract source.

## Normative Authority

| Item | Status | Evidence |
| --- | --- | --- |
| Normative source | VERIFIED | `docs/contract-spec.md` opening NOTE says it is the only normative contract source. |
| Architecture plan role | VERIFIED | `docs/target-agent-platform-architecture-plan.md` describes target architecture and rationale; executable deltas must be synchronized to the spec. |
| Eval plan role | VERIFIED | `docs/eval-test-plan.md` defines contract tests and eval gates; it does not override spec semantics. |
| Phase 26 scope | VERIFIED | Phase 26 is docs/spec/eval baseline work only; no runtime implementation, physical microservice deployment, or full real external execution. |

## APF-01 Alignment Matrix

| Contract Area | Normative contract anchor | Architecture anchor | Eval anchor | Status | Phase 26 action |
| --- | --- | --- | --- | --- | --- |
| graph vocabulary and legacy aliases | `docs/contract-spec.md` §9.0, §9.4, §9.5 | `docs/target-agent-platform-architecture-plan.md` §6.1-§6.3 | `docs/eval-test-plan.md` §20.1 Node contract / Router contract | VERIFIED | Keep aliases in this checklist and validate no graph delta bypasses spec. |
| AgentState RAG/claim fields | `docs/contract-spec.md` §10 and §10.1 canonical field registry | `docs/target-agent-platform-architecture-plan.md` §6.3, §11.8-§11.10 | `docs/eval-test-plan.md` §20.1 State lifecycle / RAG context build / Claim verification | VERIFIED | Confirm `rag_context_status`, `verified_evidence_package`, `citation_map`, `evidence_map`, `claim_verification_bundle`, `blocked_claims`, and `safe_support_refs` remain registered in spec. |
| RAG context build | `docs/contract-spec.md` §8.3, §9.4 `rag_context_build`, §9.5 `route_after_rag_context` | `docs/target-agent-platform-architecture-plan.md` §6.3, §11.7-§11.9 | `docs/eval-test-plan.md` §20.1 RAG context build contract | VERIFIED | No Task 2 sync needed unless validation finds missing anchors. |
| claim verification | `docs/contract-spec.md` §8.3 `MaterialClaimV1` / `ClaimVerificationBundleV1`, §9.4 `claim_verify`, §9.5 `route_after_claim_verify` | `docs/target-agent-platform-architecture-plan.md` §11.10 | `docs/eval-test-plan.md` §20.1 Claim verification contract | VERIFIED | No Task 2 sync needed unless validation finds missing anchors. |
| ToolPolicyDecision and ToolView | `docs/contract-spec.md` §12.6 | `docs/target-agent-platform-architecture-plan.md` §10.6 | `docs/eval-test-plan.md` §20.1 Tool policy decision contract | VERIFIED | No Task 2 sync needed unless validation finds missing anchors. |
| BusinessFactResultV1 and BusinessFactRefV1 | `docs/contract-spec.md` §8.4 and §12.5 | `docs/target-agent-platform-architecture-plan.md` §12.1-§12.2 | `docs/eval-test-plan.md` §20.1 Business fact contract | VERIFIED | No Task 2 sync needed unless validation finds missing anchors. |
| DecisionEventEnvelopeV1 / minimal event envelope | `docs/contract-spec.md` §17.2 | `docs/target-agent-platform-architecture-plan.md` §14 and §14.1 | `docs/eval-test-plan.md` §20.1 Decision event / Replay contract | VERIFIED | No Task 2 sync needed unless validation finds missing anchors. |
| approval/action draft/no-real-execution boundary | `docs/contract-spec.md` §15 and §16 | `docs/target-agent-platform-architecture-plan.md` §13 | `docs/eval-test-plan.md` §20.1 Approval contract / Action contract | VERIFIED | Keep Phase 26 docs-only scope; do not add real execution, outbox dispatch, reconciliation, or compensation implementation work. |
| eval gate levels | `docs/contract-spec.md` §11.4 for normative Wilson/M6 formula; `docs/eval-test-plan.md` §20.0 for gate taxonomy | `docs/target-agent-platform-architecture-plan.md` §14.2 and §15 | `docs/eval-test-plan.md` §20.0 | VERIFIED | Preserve dev-contract / release / monitoring gate distinctions in implementation phases. |

## APF-02 Module Ownership Matrix

| Module | Owned schemas/tables/events | Public methods | Allowed downstream dependencies | Forbidden imports/access | Decision events | Normative source |
| --- | --- | --- | --- | --- | --- | --- |
| `RunOrchestrator` | run entry/lifecycle orchestration refs, graph invocation refs, finalize/schedule refs | `start_run`, `invoke_graph`, `finalize_run`, `schedule_post_response_jobs` | `TrustedContextFactory`, Agent Graph, `RunLifecycleService`, Observability | Direct business/memory/RAG repository access; business rules | run lifecycle / orchestration events | SYNCED_TO_SPEC_BY_TASK_2: `docs/contract-spec.md` §0.2 |
| `TrustedContextFactory` | canonical `TrustedContext`, projection schemas | `create_from_request`, `project_to_tool_context`, `project_to_knowledge_context`, `project_to_memory_context`, `project_to_approval_context`, `project_to_replay_context` | trusted auth/session/run metadata sources | LLM/user payload identity or scope overrides; projection-local fields widened into canonical context | trusted context projection decisions | SYNCED_TO_SPEC_BY_TASK_2: `docs/contract-spec.md` §0.2 |
| `IntentService` | `IntentCandidate`, `ResolvedIntent`, intent policy decision, slot policy decision | `resolve_contextual_intent`, `resolve_required_slots`, `route_after_contextual_intent` adapter | `SessionContextMemory`, `IntentPolicyRegistry`, `SlotPolicyRegistry` | tool/repository calls; model confidence as authorization | intent policy and slot policy decisions | SYNCED_TO_SPEC_BY_TASK_2: `docs/contract-spec.md` §0.2 |
| `MemoryContextService` | session/long-term/case memory projections, write candidates, review queue refs | `load_session_context_for_intent`, `load_memory_bundle_after_slot_resolution`, `propose_memory_writes` | memory repositories, redaction policy, review queue | satisfying policy evidence/current business fact/approval/action/replay truth | memory load/write policy decisions | SYNCED_TO_SPEC_BY_TASK_2: `docs/contract-spec.md` §0.2 |
| `ToolPlatform` | `ToolDescriptor`, `ToolView`, `ToolPolicyDecision`, runtime auth, tool result projection, tool decision events | `visible_tools`, `invoke` | `ToolPolicyEngine`, domain service public methods, artifact store | graph/investigate custom allowlists; raw adapter payloads in prompts | tool visibility/runtime auth/result projection decisions | SYNCED_TO_SPEC_BY_TASK_2: `docs/contract-spec.md` §0.2 |
| `KnowledgeService` | `EvidenceRefV1`, `VerifiedEvidencePackageV1`, `MaterialClaimV1`, `ClaimVerificationBundleV1`, evidence validation, claim verification decisions | `search`, `build_verified_context`, `verify_claims` | policy/chunk repositories, retrieval engine, domain rule verifier plugins | judging current business facts; citation membership as semantic support | retrieval/evidence validation/claim verification decisions | SYNCED_TO_SPEC_BY_TASK_2: `docs/contract-spec.md` §0.2 |
| `BusinessFactService` | `BusinessFactResultV1`, `BusinessFactRefV1`, `BusinessContextV1`, resource freshness/scope checks | `fetch_context`, `get_order`, `get_refund_case`, `get_ticket` | owned business repositories/adapters | graph/tool direct repository access; memory/RAG/LLM-substituted facts | business fact read/scope/freshness decisions | SYNCED_TO_SPEC_BY_TASK_2: `docs/contract-spec.md` §0.2 |
| `ApprovalService` | approval request/revision/interrupt/resume state machine, approval records/events | `create_request`, `record_decision`, `resume_with_trusted_decision`, `request_more_info` | risk/approval policy, snapshot refs, trusted resume adapter | risk auto/block ownership; ordinary chat as approval truth | approval request/decision/resume lifecycle events | SYNCED_TO_SPEC_BY_TASK_2: `docs/contract-spec.md` §0.2 |
| `ActionDraftService / ExecutionBoundary` | action proposal/draft records, payload hashes, draft safety binding | `create_draft`, `bind_safety_snapshot`, `prepare_execution_boundary` | trusted approval result, risk policy output, snapshot store | real external side effects in v1.9; approval/snapshot/action policy bypass | action draft/safety binding decisions | SYNCED_TO_SPEC_BY_TASK_2: `docs/contract-spec.md` §0.2 |
| `Observability / Replay` | `DecisionEventEnvelopeV1`, minimal event envelope, replay artifacts, redaction policy, eval artifact refs | `emit_decision_event`, `append_trace_event`, `build_replay_view`, `record_eval_artifact_ref` | service decision events, artifact stores, sequence allocator | replay by rerunning LLMs; raw prompt/tool/PII/action payload persistence | decision event envelope and replay lifecycle events | SYNCED_TO_SPEC_BY_TASK_2: `docs/contract-spec.md` §0.2 |

## Legacy Alias and Delta Register

| Legacy name | Target canonical name | Status | Target phase / disposition |
| --- | --- | --- | --- |
| `intent_classification` | `contextual_intent_resolve` | VERIFIED | Phase 32 Intent Graph Migration keeps alias mapping until migration completes. |
| `session_memory_load` | `session_context_load` | VERIFIED | Phase 32 Intent Graph Migration keeps alias mapping until migration completes. |
| `long_term_memory_retrieve` | `memory_context_load` | VERIFIED | Phase 32 Intent Graph Migration keeps alias mapping until migration completes. |
| `route_after_intent` | `route_after_contextual_intent` | VERIFIED | Phase 32 Intent Graph Migration keeps alias mapping until migration completes. |
| `route_after_slots` | `route_after_slot_resolution` | VERIFIED | Phase 32 Intent Graph Migration keeps alias mapping until migration completes. |
| APF-02 normative ownership registry | `docs/contract-spec.md` §0.2 | SYNCED_TO_SPEC_BY_TASK_2 | Added in Phase 26 Task 2. |
| Architecture ownership matrix columns | mirror of `docs/contract-spec.md` §0.2 | SYNCED_TO_SPEC_BY_TASK_2 | Updated `docs/target-agent-platform-architecture-plan.md` §5.2 in Phase 26 Task 2. |
| Eval APF-02 module ownership row | `Module ownership boundary contract` in §20.1 | SYNCED_TO_SPEC_BY_TASK_2 | Added to `docs/eval-test-plan.md` §20.1 in Phase 26 Task 2. |

## Eval Gate Coverage

| Gate | Status | Evidence |
| --- | --- | --- |
| Dev-contract gate | VERIFIED | `docs/eval-test-plan.md` §20.0 defines phase merge contract checks for schema, router totality, state writer, forbidden behavior, and scope/permission negatives. |
| Release gate | VERIFIED | `docs/eval-test-plan.md` §20.0 and `docs/contract-spec.md` §11.4 distinguish production/statistical gates from MVP dev gates. |
| Monitoring gate | VERIFIED | `docs/eval-test-plan.md` §20.0 defines drift, false negative, deny reason, no-evidence, memory quality, and replay completeness monitoring. |
| APF-02 module ownership | SYNCED_TO_SPEC_BY_TASK_2 | `docs/eval-test-plan.md` §20.1 now includes `Module ownership boundary contract`, and `docs/contract-spec.md` §0.2 owns the registry. |

## GSD Metadata Caveat

`gsd-sdk query validate.health` may remain `status: degraded` only for documented metadata caveats: old STATE phase references, old completed Phase 24/24.x/25 directories or summary/archive state, and missing future Phase 27-35 directories. `phases.clear --confirm` is forbidden because it deletes instead of archiving.

Phase 26 execution also records known `state.planned-phase` and `state.begin-phase` writer issues in `.planning/LOCAL-VALIDATION-ISSUES.md`; these tooling issues do not change the architecture contract baseline.

## Scope Containment

Old Phase 24/24.x/25 directory archival is a separate pending cleanup todo and is not a Phase 26 prerequisite or task. Phase 26 must not implement runtime code, physical microservice deployment, outbox dispatch, reconciliation, compensation, or full real external execution.

## Validation Log

| Check | Command / evidence | Result | Notes |
| --- | --- | --- | --- |
| Phase metadata | `gsd-sdk query init.plan-phase 26 && gsd-sdk query roadmap.get-phase 26` | PASS | Phase 26 resolves with APF-01 and APF-02. |
| APF-01 contract anchors | `rg -n "VerifiedEvidencePackageV1|ClaimVerificationBundleV1|ToolPolicyDecision|BusinessFactResultV1|DecisionEventEnvelopeV1|route_after_rag_context|route_after_claim_verify" docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md` | PASS | Required graph/RAG/tool/business/event names are present across the baseline docs. |
| APF-02 ownership anchors | `rg -n "Module ownership boundary registry|Module ownership boundary contract|forbidden imports|Decision events|BusinessFactService|ToolPlatform|KnowledgeService|Observability / Replay" docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md .planning/phases/26-architecture-contract-baseline/26-BASELINE-CHECKLIST.md` | PASS | `contract-spec.md` §0.2 is the normative registry, architecture §5.2 mirrors it, and eval §20.1 covers ownership boundary tests. |
| Markdown / whitespace | `git diff --check -- docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md .planning/phases/26-architecture-contract-baseline .planning/ROADMAP.md .planning/STATE.md .planning/REQUIREMENTS.md` | PASS | No whitespace diff errors. |
| GSD state / roadmap | `gsd-sdk query state.load && gsd-sdk query roadmap.analyze --pick next_phase` | PASS WITH CAVEAT | SDK reports v1.9 and next phase 27. `state.load` still reports `total_plans: 1` due known GSD state parser/writer behavior recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`. |
| Code fence parity | target file fence loop from `26-VALIDATION.md` | PASS | All target Markdown files have balanced fenced code blocks. |
| GSD health | `gsd-sdk query validate.health` | PASS WITH CAVEAT | Status is `degraded` with no errors. W002/W006/I001 warnings match known old STATE references, future Phase 27-35 directories, and old phase summary/archive state. No destructive cleanup was run. |
| Scope containment | `git status --short --untracked-files=all -- . ':(exclude)docs/**' ':(exclude).planning/**'` and `git diff --name-only -- . ':(exclude)docs/**' ':(exclude).planning/**'` | PASS | No runtime-code paths were reported. |
| Scope wording diagnostic | `rg -n "Phase 26.*(physical microservice|microservice deployment|full real external execution|outbox dispatch|reconciliation|compensation)|implements? (...)" ... || true` | PASS WITH CAVEAT | Matches are prohibition/diagnostic text in plan/checklist/pattern docs, not implementation claims. |
| GSD-native checker | `gsd-plan-checker` on Phase 26 execution artifacts | PASS | Returned `## VERIFICATION PASSED`. |
| Plan structure | `frontmatter.validate` and `verify.plan-structure` for `26-01-PLAN.md` | PASS | Frontmatter and all three tasks are structurally valid. |

## Cross-Review Sign-off

| Finding | Evidence | Disposition | Follow-up |
| --- | --- | --- | --- |
| APF-01 coverage is present across spec, architecture, and eval docs. | `docs/contract-spec.md` §9/§10/§8.3/§8.4/§12.6/§17.2; architecture §6/§10-§14; eval §20.1. | PASS | Later implementation phases must keep writing spec deltas before new executable contracts. |
| APF-02 ownership was missing as a normative registry before Task 2. | This checklist initially marked APF-02 rows as needing Task 2 sync; Task 2 added `docs/contract-spec.md` §0.2 and mirrored it in architecture §5.2. | PASS | Phase 27-35 should use §0.2 as the dependency/import boundary. |
| `contract-spec.md` remains normative source. | Checklist Normative Authority; architecture §5.2 says spec wins on conflict; eval row points to `docs/contract-spec.md` §0.2. | PASS | Do not treat this checklist as a normative source. |
| No runtime implementation scope was introduced. | Scope containment commands reported no paths outside docs/planning. | PASS | Runtime code starts only in Phase 27-35 implementation phases. |
| Physical microservice deployment and full real execution remain out of scope. | Prohibition text appears in plan/checklist/context; no implementation claims or runtime changes were added. | PASS | Physical microservice extraction and full real external execution remain future/out-of-v1.9 scope. |
| Old phase archive cleanup was not folded into Phase 26. | Pending cleanup todo exists separately; checklist Scope Containment keeps archive cleanup out of Phase 26. | PASS | Handle old phase directory archive as a separate cleanup task. |
| `validate.health` degraded status is understood and bounded. | Health output has no errors; warnings match documented GSD metadata caveats. Phase 26 no longer appears as a missing-summary info item after summary creation. | PASS | Do not run `phases.clear --confirm`; old phase archive cleanup remains a separate todo. |
| Broad grep found non-blocking wording outside the checklist. | `docs/target-agent-platform-architecture-plan.md` has existing idempotency TODO wording; spec/eval contain named-phase deferred contexts. | NOT A BLOCKER | Plan's hard gate is checklist-only. Optional wording cleanup can be handled if it affects a named phase contract. |
| External Claude review returned `PASS_WITH_WARNINGS`. | Warnings were limited to architecture mirror drift and `.planning` status consistency; no Phase 27 blocker was identified. | PASS | Fixed §6 canonical graph labels, §14 envelope mirror, checklist status, requirements traceability, summary readiness, roadmap/state progress before closing Phase 26. |
