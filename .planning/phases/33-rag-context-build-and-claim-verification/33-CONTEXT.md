# Phase 33: RAG Context Build and Claim Verification - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning
**Source:** `$gsd-discuss-phase 33`; interactive question UI was unavailable in Codex Default mode, so Codex selected conservative defaults after reading roadmap, requirements, prior phase context, current code, and the user-highlighted architecture target `docs/target-agent-platform-architecture-plan.md`.

<domain>
## Phase Boundary

Phase 33 turns the Phase 22 RAG reasoning kernel into the v1.9 platform boundary described by the target architecture: RAG must be split into candidate policy retrieval inside `investigate`, deterministic verified evidence package construction in `rag_context_build`, and post-generation material-claim verification in `claim_verify`.

This phase must satisfy APF-13 and APF-14. It owns `VerifiedEvidencePackageV1`, `rag_context_status`, `citation_map`, `evidence_map`, `route_after_rag_context`, `MaterialClaimV1` consumption, `ClaimVerificationBundleV1`, `blocked_claims`, `safe_support_refs`, and `route_after_claim_verify` enough for current graph execution, trace/eval projections, and downstream Phase 34 approval/action binding.

This phase should not implement broad retrieval-quality work, new search backends, real external action execution, Phase 34 action draft binding, Phase 35 broad replay/eval hardening, policy source UI, physical microservice extraction, or tenant-over-global policy fallback. `docs/contract-spec.md` remains normative; `docs/target-agent-platform-architecture-plan.md` is the migration target and design rationale that must shape the implementation unless it conflicts with the spec.

</domain>

<decisions>
## Implementation Decisions

### Architecture Target And Service Boundary

- **D-01:** Treat `docs/target-agent-platform-architecture-plan.md` as the primary architecture migration target for Phase 33, with `docs/contract-spec.md` as the normative contract source if the two differ.
- **D-02:** Converge RAG/claim behavior behind the target `KnowledgeService` public boundary: `search`, `build_verified_context`, and `verify_claims`. Current `src/agent/rag_context/` code can be reused, but graph nodes should not keep directly assembling one-off `ContextBuilder` / `MaterialClaimVerifier` flows if a service boundary can own that orchestration.
- **D-03:** Keep `KnowledgeService.search` as the candidate retrieval/read capability inside `investigate`. `rag_context_build` is outside the read loop and deterministic; it upgrades candidate refs into verified evidence. `claim_verify` runs after `recommendation_generation` because it needs generated `MaterialClaimV1` records and any proposed action claim.
- **D-04:** `RetrievalPolicyRegistry` and `KnowledgeQueryPlanner` may be introduced as minimal architecture-boundary seams only where needed to express evidence policy, query inputs, and future policy ownership. Do not use Phase 33 to add new retrieval algorithms, rerankers, external search backends, or quality tuning beyond preserving existing Phase 23 behavior.

### Registered Nodes, Routers, And Writer Ownership

- **D-05:** Phase 33 should make `rag_context_build` and `claim_verify` real runnable graph semantics, replacing the Phase 32 `deferred_non_runnable` target placeholders with tested runnable behavior or explicit fail-closed behavior.
- **D-06:** Prefer explicit registered nodes for `rag_context_build` and `claim_verify`, because both change routing, gate fail-closed behavior, and need trace/eval/replay surfaces. Legacy runtime/debug names may remain as aliases, but target canonical names must be visible in graph vocabulary and projections.
- **D-07:** `rag_context_build` is the only writer for `rag_context_status`, `verified_evidence_package`, `citation_map`, `evidence_map`, rejected/stale/conflict refs, and related build errors. `recommendation_generation` can consume those fields and write `material_claims`, but it cannot mark evidence or claims as verified.
- **D-08:** `claim_verify` is the only writer for `claim_verification_bundle`, `blocked_claims`, and `safe_support_refs`. LLM output, recommendation drafts, memory, and prompt summaries cannot override claim verification results.
- **D-09:** `route_after_rag_context` and `route_after_claim_verify` must be deterministic router functions. They must not call LLMs, tools, repositories, retrieval engines, or external services.

### VerifiedEvidencePackageV1

- **D-10:** Introduce or adapt to a stable `VerifiedEvidencePackageV1` target schema rather than treating current `RagContextBundle` as the whole contract. The existing bundle/projections can remain as compatibility internals or package projections.
- **D-11:** `VerifiedEvidencePackageV1` should include package identity/status, verified `EvidenceRefV1` items, citation map, evidence map, prompt/verifier/replay/debug projections, rejected candidate refs, stale/conflict refs, reason codes, policy/config versions, and replay snapshot refs or captured-at metadata where current storage supports it.
- **D-12:** Evidence validation must re-fetch canonical evidence through the Knowledge boundary and check tenant/scope/ACL, policy version/latest version, text hash/content hash, effective date/freshness, doc type, authority level, and source locator/provenance availability before evidence can enter prompt, verifier, replay, approval, or action surfaces.
- **D-13:** Candidate refs from `investigate` must never enter prompt/action/risk/approval directly. Invalid scope, invalid hash, unauthorized, stale, conflict, or missing canonical content must be represented as rejected/stale/conflict refs and must affect `rag_context_status`.
- **D-14:** Prompt/verifier/replay/debug projections remain separated. Prompt projection is bounded and prompt-safe; debug/replay can carry more diagnostic refs only through redacted/audit-safe channels. Raw source-block/OCR internals, raw retrieval debug, raw verifier prompts, private reasoning, and unbounded policy text remain forbidden in ordinary prompts, final responses, memory, action snapshots, and user-facing APIs.

### RAG Context Status And Routing

- **D-15:** Adopt explicit `rag_context_status` values consistent with the target architecture: `not_required`, `verified`, `partial`, `no_evidence`, `unauthorized`, `stale`, `conflict`, `invalid_hash`, `invalid_scope`, and `build_error`, with exact enum spelling left to planning if tests pin the mapping.
- **D-16:** `route_after_rag_context` should allow `verified` and true `not_required` paths to reach `recommendation_generation`; allow `partial` only for conservative low-risk answer paths; route action-bound/high-risk `partial`, `stale`, `conflict`, invalid scope/hash, unauthorized, no evidence, or build errors to fail-closed final response, clarification, or manual-review-style safe response according to current graph capabilities.
- **D-17:** If missing slots or missing trusted business facts prevent evidence validation, route to `clarification_gate` or safe insufficient-evidence response rather than generating an action-bound recommendation.

### Material Claims And ClaimVerificationBundleV1

- **D-18:** `recommendation_generation` must emit stable `MaterialClaimV1` records for user-visible policy claims, business fact claims, and action recommendation claims. Claim verification must not parse final natural language as its primary input.
- **D-19:** `ClaimVerificationBundleV1` should include overall status, route, claim-level results, blocked claims, safe support refs, reason codes, verifier policy/config version, rule check results, semantic review status, and booleans for whether each claim may be user-visible or action-supporting.
- **D-20:** A policy claim can be supported only by current verified evidence from the active package. Citation membership is necessary but not sufficient.
- **D-21:** A business fact claim can be supported only by current `BusinessFactRefV1` / `BusinessFactResultV1` authority from `BusinessFactService`. RAG, memory, model knowledge, prompt summaries, raw repository rows, and user text cannot prove current business facts.
- **D-22:** An action recommendation claim must depend on supported policy claim(s) and supported current business fact claim(s). Passing claim verification never bypasses risk, approval, action draft, payload hash, or action safety snapshot boundaries.

### ClaimVerifier Hard Gates

- **D-23:** Claim verification is rules-first. Level 1 identity/scope/hash/effective-date/authority gates and business fact authority gates always run and cannot be overridden by semantic review.
- **D-24:** Add or expose a `DomainRuleVerifier` layer for the hard cases called out by the architecture target: negation, condition branches, amount thresholds, time windows, exceptions, and policy hierarchy conflicts. The exact implementation may start minimal, but tests must pin that these hard checks are not replaced by citation membership.
- **D-25:** Level 3 semantic verification remains selective: ambiguous, high-risk, action-bound, OCR/table, conflict, or manual-review-sensitive cases. It must be budgeted, deterministic under tests, and fail closed on timeout, provider error, malformed output, or budget overflow.
- **D-26:** Unsupported user-visible policy claims cannot be shown as supported answers. Unsupported action recommendation claims cannot reach `risk_gate`, approval, action draft, or action safety snapshot inputs.

### Plan Granularity And Verification

- **D-27:** Do not plan Phase 33 as a single large `33-01-PLAN.md` despite the roadmap listing one placeholder plan. MOCA project rules treat this kind of service-boundary/platform-foundation phase as a planning blocker if it covers contracts, service boundary, graph nodes, routers, generation integration, risk/action gating, and final verification in one plan.
- **D-28:** Split planning into dependency-ordered units. Recommended shape:
  - contracts/state/service boundary for `VerifiedEvidencePackageV1`, `ClaimVerificationBundleV1`, `KnowledgeService.build_verified_context`, and `KnowledgeService.verify_claims`;
  - `rag_context_build` node, `route_after_rag_context`, projections, and candidate-ref hard gates;
  - `recommendation_generation` material-claim output plus `claim_verify` node and `route_after_claim_verify`;
  - risk/action/final-response integration gates and no-leak projections;
  - final static/focused verification and eval gate closure.
- **D-29:** Verification must use MOCA's valid local entrypoint: `uv run pytest ...` or `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` are invalid in this repository.
- **D-30:** Tests must include candidate refs not entering prompt/action, invalid scope/hash fail-closed, unsupported action claims blocked before risk/approval/action, business fact claims requiring `BusinessFactRefV1`, router totality, state reset/writer ownership, projection separation, and leakage negatives.

### Agent Discretion

- Exact module/file split is left to planning. Likely targets include `src/knowledge/service.py`, `src/agent/rag_context/`, `src/agent/nodes/`, `src/agent/routing.py`, `src/agent/graph.py`, `src/agent/graph_vocabulary.py`, `src/agent/state.py`, trace/API projections, and focused tests.
- Exact enum names, package IDs, event payload shapes, and compatibility adapter names are planner discretion as long as spec semantics and tests are stable.
- Broad decision-event/replay completeness belongs to Phase 35, but Phase 33 should emit or preserve enough safe refs/status fields that Phase 35 can record RAG/claim decisions without reconstructing them from prompts.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope

- `.planning/ROADMAP.md` - Phase 33 goal, APF-13/APF-14 success criteria, dependency on Phase 32, and Phase 34/35 deferrals.
- `.planning/REQUIREMENTS.md` - APF-13/APF-14 requirement text and APF-15/APF-18 downstream traceability.
- `.planning/STATE.md` - Current milestone state, Phase 32 completion notes, and Phase 33 next-step context.

### Architecture Target And Normative Contracts

- `docs/target-agent-platform-architecture-plan.md` §3 - Modular monolith service-boundary principles.
- `docs/target-agent-platform-architecture-plan.md` §5 - Target `KnowledgeService` ownership and public method boundary.
- `docs/target-agent-platform-architecture-plan.md` §6 / §6.1 / §6.3 - Target graph shape, registered-node guidance, and `rag_context_build` / `route_after_rag_context` semantics.
- `docs/target-agent-platform-architecture-plan.md` §11 - RAG/Knowledge platform design, `VerifiedEvidencePackage`, three-stage RAG split, and ClaimVerifier hard gates.
- `docs/target-agent-platform-architecture-plan.md` §12 - BusinessFactService authority boundary consumed by claim verification.
- `docs/target-agent-platform-architecture-plan.md` §20 / Phase 33 implementation notes - RAG contract eval gates and target phase tasks.
- `docs/contract-spec.md` §0.2 - Module ownership registry, especially `KnowledgeService` and forbidden imports/access.
- `docs/contract-spec.md` §8.3 / §8.4 / §12.6 - Minimal contracts for `VerifiedEvidencePackageV1`, `MaterialClaimV1`, `ClaimVerificationBundleV1`, `BusinessFactResultV1`, `ToolPolicyDecision`, and authority refs.
- `docs/contract-spec.md` §9.4 / §9.5 - Node/router contracts for `rag_context_build`, `claim_verify`, `route_after_rag_context`, and `route_after_claim_verify`.
- `docs/contract-spec.md` §10 - AgentState RAG/claim fields, writer ownership, reset/merge rules, and audit handoff.
- `docs/eval-test-plan.md` §20.1 / §20.3 - RAG context build and claim verification contract test matrix and eval expectations.

### Prior Phase Context

- `.planning/milestones/v1.5-phases/22-rag-context-builder-hallucination-control/22-CONTEXT.md` - Existing Phase 22 RAG kernel decisions and boundaries that Phase 33 should platformize.
- `.planning/milestones/v1.5-research/SUMMARY.md` - Phase 22 research summary for reasoning kernel risks, module candidates, and verifier levels.
- `.planning/phases/27-trustedcontextfactory-and-projections/27-CONTEXT.md` - Trusted context and KnowledgeContext projection rules.
- `.planning/phases/28-decision-event-foundation/28-CONTEXT.md` - Decision event envelope and reason-code conventions.
- `.planning/phases/29-tool-platform-boundary/29-CONTEXT.md` - ToolPlatform read capability and runtime policy boundary.
- `.planning/phases/29.5-merchant-scope-role-model-alignment/29.5-CONTEXT.md` - Merchant-bound role semantics and tenant public policy separation.
- `.planning/phases/30-businessfactservice-boundary/30-CONTEXT.md` - Current business fact authority and no-leak business scope semantics.
- `.planning/phases/31-memory-platform-boundary/31-CONTEXT.md` - Memory contextual-only authority boundary and non-substitution rules.
- `.planning/phases/32-intent-graph-migration/32-CONTEXT.md` - Target graph vocabulary, Phase 33 deferred non-runnable placeholders, and graph projection rules.

### Current Code Sites

- `src/agent/rag_context/schemas.py` - Current `RagContextBundle`, material claim authority class, prompt/verifier/debug/safe projections, and build input schemas.
- `src/agent/rag_context/builder.py` - Current `ContextBuilder` validation/projection implementation.
- `src/agent/rag_context/verifier.py` - Current `MaterialClaimVerifier`, semantic verifier budgets, authority checks, and support result schemas.
- `src/agent/rag_context/routing.py` - Current backend-owned verification route mapping.
- `src/agent/rag_context/claims.py` - Current material claim normalization/validation.
- `src/agent/nodes/generate_recommendation.py` - Current recommendation generation, RAG context build call, claim construction, and verifier integration.
- `src/agent/nodes/assess_risk_and_approval.py` - Current verifier route blocking before risk/approval.
- `src/agent/nodes/action_draft.py` - Current verifier route blocking before action draft.
- `src/agent/graph.py` - Current graph registration and verification route handling.
- `src/agent/graph_vocabulary.py` - Phase 32 target vocabulary entries for `rag_context_build` and `claim_verify`.
- `src/agent/state.py` - Current AgentState RAG/verifier fields and reset expectations.
- `src/knowledge/service.py` - Current `PolicyKnowledgeService`; target `KnowledgeService` boundary integration point.
- `src/knowledge/schemas.py` - Canonical `EvidenceRefV1` and knowledge result schemas.
- `src/business/service.py` and `src/business/schemas.py` - Current business fact service and `BusinessFactResultV1` / `BusinessContextV1` authority boundary.
- `src/tools/contracts.py` - `BusinessFactRefV1`, `ToolResultV2`, and tool authority refs.

### Tests To Inspect

- `tests/agent/rag_context/test_context_builder.py`
- `tests/agent/rag_context/test_budgeting.py`
- `tests/agent/rag_context/test_material_claims.py`
- `tests/agent/rag_context/test_authority_boundaries.py`
- `tests/agent/rag_context/test_verifier.py`
- `tests/agent/rag_context/test_routing.py`
- `tests/agent/test_phase22_recommendation_integration.py`
- `tests/agent/test_phase22_final_response.py`
- `tests/agent/test_nodes/test_generate_recommendation.py`
- `tests/agent/test_nodes/test_assess_risk_and_approval.py`
- `tests/agent/test_nodes/test_receive_request.py`
- `tests/agent/test_graph.py`
- `tests/agent/test_graph_vocabulary.py`
- `tests/architecture/test_phase32_static_contract.py`
- `tests/business/test_schemas.py`
- `tests/agent/test_memory_evidence_boundary.py`
- `tests/agent/test_policy_retrieval_ownership.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src/agent/rag_context/` already contains a Phase 22 kernel: `ContextBuilder`, strict projection DTOs, `MaterialClaimVerifier`, semantic verifier budget controls, routing helpers, material claim normalization, and metrics helpers.
- `generate_recommendation` already builds a RAG context bundle, emits material claims, runs verifier logic, and stores `rag_context_bundle`, `rag_verification`, `verifier_status`, `verification_route`, `verifier_reason_codes`, `verifier_safe_citation_refs`, and `verifier_metrics`.
- `assess_risk_and_approval` and `action_draft` already consult verifier route state and block non-allow verification paths.
- `AgentState` already has compatibility RAG/verifier fields, but target spec expects additional canonical fields such as `rag_context_status`, `verified_evidence_package`, `citation_map`, `evidence_map`, `claim_verification_bundle`, `blocked_claims`, and `safe_support_refs`.
- Phase 32 graph vocabulary already records `rag_context_build` and `claim_verify`, but marks them `deferred_non_runnable`; Phase 33 must update this safely.
- Existing tests already cover many Phase 22 boundaries and should be reused rather than replaced.

### Established Patterns

- Cross-layer contracts use strict Pydantic schemas or typed state fields.
- Routers are deterministic and side-effect-free.
- Prompt/debug/replay/action projections must be separated and prompt-safe.
- Authority boundaries are defense-in-depth: memory and model knowledge are contextual only; business facts require `BusinessFactRefV1`; policy claims require verified policy evidence.
- Safety and boundary tests include negative cases, static guards, no-leak assertions, and focused graph/node behavior.

### Integration Points

- `investigate` produces policy candidate refs and business context; Phase 33 should make the candidate-to-verified handoff explicit.
- `rag_context_build` should consume candidate policy evidence and KnowledgeContext/trusted context, write package/status/projection fields, and route through `route_after_rag_context`.
- `recommendation_generation` should consume only verified package prompt projection for policy-backed claims and emit `MaterialClaimV1` records.
- `claim_verify` should consume material claims, verified evidence package, business context, and proposed action, then write `ClaimVerificationBundleV1` and route through `route_after_claim_verify`.
- `risk_gate`, approval, action draft, final response, trace/eval/API projections must consume verifier/package outputs without letting invalid candidate refs or unsupported claims pass through.

</code_context>

<specifics>
## Specific Ideas

- User explicitly pointed to `docs/target-agent-platform-architecture-plan.md` as the prior architecture migration target; Phase 33 planning must read it, not only `contract-spec.md`.
- Treat Phase 22 as historical implementation proof, not final platform shape. The goal is platformizing and making writer/router/service boundaries explicit.
- If implementation discovers mismatch between architecture plan and `contract-spec.md`, stop and document a spec/architecture delta rather than silently choosing one in code.
- Keep default tests deterministic; semantic-provider behavior should be faked/mocked unless an optional release eval explicitly requires live provider coverage.
- Keep manual-review behavior compatible with the current graph: if there is no dedicated manual-review node, use a safe final response or existing review handoff semantics while preserving route/status refs.

</specifics>

<deferred>
## Deferred Ideas

- Full retrieval quality expansion, new query rewrite algorithms, reranker changes, external search backend, and retrieval ablation tuning remain outside Phase 33 unless needed only as no-op compatibility surfaces.
- Phase 34 owns approval/action draft binding to business fact refs, verified evidence refs, claim verification refs, risk decisions, payload hashes, and safety snapshots.
- Phase 35 owns broad replay/trace/eval hardening for all platform decisions.
- Phase 34 and Phase 35 must continue to treat `docs/target-agent-platform-architecture-plan.md` as a core architecture reference, with `docs/contract-spec.md` as the normative conflict resolver.
- Full policy source operations UI, source document viewer, and lifecycle management remain future scope.
- Tenant-over-global policy precedence and global/default fallback remain future policy-scope work.
- Real external execution, outbox, reconciliation, compensation dispatch, and external idempotency workers remain future execution-boundary work.

</deferred>

---

*Phase: 33-rag-context-build-and-claim-verification*
*Context gathered: 2026-06-29*
