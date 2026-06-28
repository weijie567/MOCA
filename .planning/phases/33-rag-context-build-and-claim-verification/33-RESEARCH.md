# Phase 33: RAG Context Build and Claim Verification - Research

**Researched:** 2026-06-29 [VERIFIED: environment_context.current_date]  
**Domain:** RAG evidence validation, KnowledgeService boundary, material-claim verification, LangGraph state/routing [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:10-14]  
**Confidence:** HIGH for current-code map and planning split; MEDIUM for exact final DTO module placement because the context leaves file split to planning [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:77-81]

<user_constraints>
## User Constraints (from CONTEXT.md)

Source copied from Phase 33 context. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:18-83]

### Locked Decisions

#### Architecture Target And Service Boundary

- **D-01:** Treat `docs/target-agent-platform-architecture-plan.md` as the primary architecture migration target for Phase 33, with `docs/contract-spec.md` as the normative contract source if the two differ.
- **D-02:** Converge RAG/claim behavior behind the target `KnowledgeService` public boundary: `search`, `build_verified_context`, and `verify_claims`. Current `src/agent/rag_context/` code can be reused, but graph nodes should not keep directly assembling one-off `ContextBuilder` / `MaterialClaimVerifier` flows if a service boundary can own that orchestration.
- **D-03:** Keep `KnowledgeService.search` as the candidate retrieval/read capability inside `investigate`. `rag_context_build` is outside the read loop and deterministic; it upgrades candidate refs into verified evidence. `claim_verify` runs after `recommendation_generation` because it needs generated `MaterialClaimV1` records and any proposed action claim.
- **D-04:** `RetrievalPolicyRegistry` and `KnowledgeQueryPlanner` may be introduced as minimal architecture-boundary seams only where needed to express evidence policy, query inputs, and future policy ownership. Do not use Phase 33 to add new retrieval algorithms, rerankers, external search backends, or quality tuning beyond preserving existing Phase 23 behavior.

#### Registered Nodes, Routers, And Writer Ownership

- **D-05:** Phase 33 should make `rag_context_build` and `claim_verify` real runnable graph semantics, replacing the Phase 32 `deferred_non_runnable` target placeholders with tested runnable behavior or explicit fail-closed behavior.
- **D-06:** Prefer explicit registered nodes for `rag_context_build` and `claim_verify`, because both change routing, gate fail-closed behavior, and need trace/eval/replay surfaces. Legacy runtime/debug names may remain as aliases, but target canonical names must be visible in graph vocabulary and projections.
- **D-07:** `rag_context_build` is the only writer for `rag_context_status`, `verified_evidence_package`, `citation_map`, `evidence_map`, rejected/stale/conflict refs, and related build errors. `recommendation_generation` can consume those fields and write `material_claims`, but it cannot mark evidence or claims as verified.
- **D-08:** `claim_verify` is the only writer for `claim_verification_bundle`, `blocked_claims`, and `safe_support_refs`. LLM output, recommendation drafts, memory, and prompt summaries cannot override claim verification results.
- **D-09:** `route_after_rag_context` and `route_after_claim_verify` must be deterministic router functions. They must not call LLMs, tools, repositories, retrieval engines, or external services.

#### VerifiedEvidencePackageV1

- **D-10:** Introduce or adapt to a stable `VerifiedEvidencePackageV1` target schema rather than treating current `RagContextBundle` as the whole contract. The existing bundle/projections can remain as compatibility internals or package projections.
- **D-11:** `VerifiedEvidencePackageV1` should include package identity/status, verified `EvidenceRefV1` items, citation map, evidence map, prompt/verifier/replay/debug projections, rejected candidate refs, stale/conflict refs, reason codes, policy/config versions, and replay snapshot refs or captured-at metadata where current storage supports it.
- **D-12:** Evidence validation must re-fetch canonical evidence through the Knowledge boundary and check tenant/scope/ACL, policy version/latest version, text hash/content hash, effective date/freshness, doc type, authority level, and source locator/provenance availability before evidence can enter prompt, verifier, replay, approval, or action surfaces.
- **D-13:** Candidate refs from `investigate` must never enter prompt/action/risk/approval directly. Invalid scope, invalid hash, unauthorized, stale, conflict, or missing canonical content must be represented as rejected/stale/conflict refs and must affect `rag_context_status`.
- **D-14:** Prompt/verifier/replay/debug projections remain separated. Prompt projection is bounded and prompt-safe; debug/replay can carry more diagnostic refs only through redacted/audit-safe channels. Raw source-block/OCR internals, raw retrieval debug, raw verifier prompts, private reasoning, and unbounded policy text remain forbidden in ordinary prompts, final responses, memory, action snapshots, and user-facing APIs.

#### RAG Context Status And Routing

- **D-15:** Adopt explicit `rag_context_status` values consistent with the target architecture: `not_required`, `verified`, `partial`, `no_evidence`, `unauthorized`, `stale`, `conflict`, `invalid_hash`, `invalid_scope`, and `build_error`, with exact enum spelling left to planning if tests pin the mapping.
- **D-16:** `route_after_rag_context` should allow `verified` and true `not_required` paths to reach `recommendation_generation`; allow `partial` only for conservative low-risk answer paths; route action-bound/high-risk `partial`, `stale`, `conflict`, invalid scope/hash, unauthorized, no evidence, or build errors to fail-closed final response, clarification, or manual-review-style safe response according to current graph capabilities.
- **D-17:** If missing slots or missing trusted business facts prevent evidence validation, route to `clarification_gate` or safe insufficient-evidence response rather than generating an action-bound recommendation.

#### Material Claims And ClaimVerificationBundleV1

- **D-18:** `recommendation_generation` must emit stable `MaterialClaimV1` records for user-visible policy claims, business fact claims, and action recommendation claims. Claim verification must not parse final natural language as its primary input.
- **D-19:** `ClaimVerificationBundleV1` should include overall status, route, claim-level results, blocked claims, safe support refs, reason codes, verifier policy/config version, rule check results, semantic review status, and booleans for whether each claim may be user-visible or action-supporting.
- **D-20:** A policy claim can be supported only by current verified evidence from the active package. Citation membership is necessary but not sufficient.
- **D-21:** A business fact claim can be supported only by current `BusinessFactRefV1` / `BusinessFactResultV1` authority from `BusinessFactService`. RAG, memory, model knowledge, prompt summaries, raw repository rows, and user text cannot prove current business facts.
- **D-22:** An action recommendation claim must depend on supported policy claim(s) and supported current business fact claim(s). Passing claim verification never bypasses risk, approval, action draft, payload hash, or action safety snapshot boundaries.

#### ClaimVerifier Hard Gates

- **D-23:** Claim verification is rules-first. Level 1 identity/scope/hash/effective-date/authority gates and business fact authority gates always run and cannot be overridden by semantic review.
- **D-24:** Add or expose a `DomainRuleVerifier` layer for the hard cases called out by the architecture target: negation, condition branches, amount thresholds, time windows, exceptions, and policy hierarchy conflicts. The exact implementation may start minimal, but tests must pin that these hard checks are not replaced by citation membership.
- **D-25:** Level 3 semantic verification remains selective: ambiguous, high-risk, action-bound, OCR/table, conflict, or manual-review-sensitive cases. It must be budgeted, deterministic under tests, and fail closed on timeout, provider error, malformed output, or budget overflow.
- **D-26:** Unsupported user-visible policy claims cannot be shown as supported answers. Unsupported action recommendation claims cannot reach `risk_gate`, approval, action draft, or action safety snapshot inputs.

#### Plan Granularity And Verification

- **D-27:** Do not plan Phase 33 as a single large `33-01-PLAN.md` despite the roadmap listing one placeholder plan. MOCA project rules treat this kind of service-boundary/platform-foundation phase as a planning blocker if it covers contracts, service boundary, graph nodes, routers, generation integration, risk/action gating, and final verification in one plan.
- **D-28:** Split planning into dependency-ordered units. Recommended shape:
  - contracts/state/service boundary for `VerifiedEvidencePackageV1`, `ClaimVerificationBundleV1`, `KnowledgeService.build_verified_context`, and `KnowledgeService.verify_claims`;
  - `rag_context_build` node, `route_after_rag_context`, projections, and candidate-ref hard gates;
  - `recommendation_generation` material-claim output plus `claim_verify` node and `route_after_claim_verify`;
  - risk/action/final-response integration gates and no-leak projections;
  - final static/focused verification and eval gate closure.
- **D-29:** Verification must use MOCA's valid local entrypoint: `uv run pytest ...` or `.venv/bin/pytest ...`; bare `pytest` and bare `python -m pytest` are invalid in this repository.
- **D-30:** Tests must include candidate refs not entering prompt/action, invalid scope/hash fail-closed, unsupported action claims blocked before risk/approval/action, business fact claims requiring `BusinessFactRefV1`, router totality, state reset/writer ownership, projection separation, and leakage negatives.

### Claude's Discretion

- Exact module/file split is left to planning. Likely targets include `src/knowledge/service.py`, `src/agent/rag_context/`, `src/agent/nodes/`, `src/agent/routing.py`, `src/agent/graph.py`, `src/agent/graph_vocabulary.py`, `src/agent/state.py`, trace/API projections, and focused tests.
- Exact enum names, package IDs, event payload shapes, and compatibility adapter names are planner discretion as long as spec semantics and tests are stable.
- Broad decision-event/replay completeness belongs to Phase 35, but Phase 33 should emit or preserve enough safe refs/status fields that Phase 35 can record RAG/claim decisions without reconstructing them from prompts.

### Deferred Ideas (OUT OF SCOPE)

Source copied from Phase 33 deferred section. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:203-214]

- Full retrieval quality expansion, new query rewrite algorithms, reranker changes, external search backend, and retrieval ablation tuning remain outside Phase 33 unless needed only as no-op compatibility surfaces.
- Phase 34 owns approval/action draft binding to business fact refs, verified evidence refs, claim verification refs, risk decisions, payload hashes, and safety snapshots.
- Phase 35 owns broad replay/trace/eval hardening for all platform decisions.
- Phase 34 and Phase 35 must continue to treat `docs/target-agent-platform-architecture-plan.md` as a core architecture reference, with `docs/contract-spec.md` as the normative conflict resolver.
- Full policy source operations UI, source document viewer, and lifecycle management remain future scope.
- Tenant-over-global policy precedence and global/default fallback remain future policy-scope work.
- Real external execution, outbox, reconciliation, compensation dispatch, and external idempotency workers remain future execution-boundary work.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APF-13 | `rag_context_build` validates candidate policy evidence into `VerifiedEvidencePackageV1` with identity/scope/hash/version/effective-date checks, separated prompt/verifier/replay/debug projections, and deterministic `route_after_rag_context`. [VERIFIED: .planning/REQUIREMENTS.md:47-50] | Use `PolicyKnowledgeService.get_verified_evidence_details`, `ContextBuilder` projection patterns, new AgentState fields, and graph/router changes. [VERIFIED: src/knowledge/service.py:298-393; src/agent/rag_context/builder.py:66-120; src/agent/state.py:48-142; docs/contract-spec.md:641-643] |
| APF-14 | `claim_verify` consumes `MaterialClaimV1` outputs and produces `ClaimVerificationBundleV1` with rules-first support status, hard gates for unsupported user-visible/action claims, and fail-closed behavior for high-risk/action-bound verifier errors. [VERIFIED: .planning/REQUIREMENTS.md:47-50] | Reuse `MaterialClaimVerifier`, semantic verifier budget/fail-closed behavior, route mapping, and downstream risk/action blockers while moving aggregation into a `claim_verify` node/service method. [VERIFIED: src/agent/rag_context/verifier.py:262-335; src/agent/rag_context/verifier.py:398-520; src/agent/rag_context/verifier.py:916-930; src/agent/rag_context/routing.py:100-162; src/agent/nodes/action_draft.py:215-230] |
</phase_requirements>

## Summary

Phase 33 should platformize the existing Phase 22 RAG kernel instead of replacing it. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:165-180; src/agent/rag_context/builder.py:47-73; src/agent/rag_context/verifier.py:262-286] The current implementation already has strict RAG bundle DTOs, candidate evidence validation, separate prompt/verifier/debug/safe projections, material-claim verification, semantic verifier fail-closed behavior, backend route mapping, and downstream verifier blockers. [VERIFIED: src/agent/rag_context/schemas.py:30-159; src/agent/rag_context/builder.py:83-120; src/agent/rag_context/verifier.py:87-120; src/agent/rag_context/routing.py:100-162; src/agent/nodes/assess_risk_and_approval.py:442-454] The gap is ownership: `generate_recommendation` currently assembles context, calls the verifier, mutates drafts, writes verifier state, and merges evidence refs in one node. [VERIFIED: src/agent/nodes/generate_recommendation.py:182-280; src/agent/nodes/generate_recommendation.py:334-478; src/agent/nodes/generate_recommendation.py:804-860]

The normative target is a three-stage split: `investigate` performs candidate retrieval, `rag_context_build` deterministically upgrades candidates to a verified package, and `claim_verify` evaluates generated material claims after recommendation generation. [VERIFIED: docs/contract-spec.md:257-263; docs/contract-spec.md:641-643; docs/target-agent-platform-architecture-plan.md:403-448] `docs/contract-spec.md` is the conflict resolver, and the target architecture is migration rationale rather than proof that code already implements the target. [VERIFIED: docs/contract-spec.md:1-13; docs/target-agent-platform-architecture-plan.md:3-6; CLAUDE.md:65-73]

**Primary recommendation:** Split Phase 33 into five dependency-ordered plans: contracts/state/service boundary, `rag_context_build`, `recommendation_generation` + `claim_verify`, downstream risk/action/final/projection hardening, and final focused/static/eval closure. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:67-75; AGENTS.md:47-52]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Candidate policy retrieval | API / Backend service boundary | Database / Storage | `investigate` calls ToolPlatform read tools, and `search_policy` delegates to `PolicyKnowledgeService.search` and the retrieval engine. [VERIFIED: src/agent/nodes/investigate.py:34-61; src/tools/executors/knowledge.py:17-58; src/knowledge/service.py:102-171] |
| Verified evidence package construction | API / Backend service boundary | Database / Storage | `rag_context_build` must re-fetch canonical evidence through KnowledgeService and write verified package/status/map fields. [VERIFIED: docs/contract-spec.md:641-643; docs/contract-spec.md:904-906; src/knowledge/service.py:298-393] |
| Prompt/verifier/replay/debug projection separation | API / Backend service boundary | API projection layer | ContextBuilder already separates prompt, verifier, debug, final, memory, replay, business, and action snapshot surfaces; Phase 33 should preserve that separation in target package fields. [VERIFIED: src/agent/rag_context/schemas.py:90-159; tests/agent/rag_context/test_context_builder.py:108-139; docs/contract-spec.md:279-307] |
| Material-claim creation | API / Backend graph node | LLM provider for structured recommendation output | `recommendation_generation` currently builds material claims from the draft and should keep claim creation while losing verification ownership. [VERIFIED: src/agent/nodes/generate_recommendation.py:701-743; docs/contract-spec.md:642-643; docs/contract-spec.md:907-929] |
| Claim verification | API / Backend service boundary | Optional LLM semantic review only for selected cases | The contract says `claim_verify` consumes material claims and writes the claim bundle; semantic review cannot override hard gates. [VERIFIED: docs/contract-spec.md:330-347; docs/contract-spec.md:641-643; src/agent/rag_context/verifier.py:398-520] |
| Risk/action blocking | API / Backend graph/risk/action boundary | Database / Storage for snapshots/drafts | Risk and action draft already block non-allow verifier routes, but Phase 33 must switch them to bundle/safe refs and prevent candidate refs from binding actions. [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:152-175; src/agent/nodes/assess_risk_and_approval.py:264-314; src/agent/nodes/action_draft.py:99-111; docs/contract-spec.md:925-929] |
| Trace/API projection safety | API projection layer | Database / Storage | Trace APIs project target graph names and action drafts through safe allowlists; Phase 33 must add RAG/claim-safe projections without exposing raw/debug payloads. [VERIFIED: src/api/routers/traces.py:106-115; src/repositories/trace_repo.py:57-146; src/agent/trace.py:236-288; tests/test_trace_api.py:284-367] |

## Project Constraints (from CLAUDE.md)

- Local debugging or validation failures in RAG/agent/tool-call work must be recorded in `.planning/LOCAL-VALIDATION-ISSUES.md` after handling. [VERIFIED: CLAUDE.md:5-8]
- Phase-level planning and large changes use the dual-AI review workflow: GSD plan checker first, Codex independent cross-review second, and decisions must be checked against repository code/docs/tests. [VERIFIED: CLAUDE.md:9-37]
- Structural or multi-file plan changes should be handed to Codex execution rather than repaired inline by the planner when they exceed the small-change threshold. [VERIFIED: CLAUDE.md:39-58]
- `docs/contract-spec.md` is the only normative contract source, target text is not implementation proof, and spec/code deltas require either a spec fix or explicit MVP/deferral record. [VERIFIED: CLAUDE.md:65-73]

## Project Constraints (from AGENTS.md)

- MOCA tests must use `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, `.venv/bin/pytest ...`, or `.venv/bin/python -m pytest ...`; bare `pytest` and bare `python -m pytest` are invalid validation. [VERIFIED: AGENTS.md:16-21]
- Service-boundary/platform-foundation phases must be split into multiple dependency-ordered plans when they cover multiple ownership domains, waves, and verification gates. [VERIFIED: AGENTS.md:47-52]
- The same contract-spec conflict rule applies in AGENTS: implementation/spec mismatch must be recorded and not silently chosen. [VERIFIED: AGENTS.md:86-94]
- No project skill files were found under `.claude/skills` or `.agents/skills`; `.claude` exists and `.agents/skills` did not produce any `SKILL.md` paths. [VERIFIED: command `ls -ld .claude .agents 2>/dev/null; find .claude/skills .agents/skills -maxdepth 2 -name SKILL.md -print 2>/dev/null || true`]

## Graph Context

- `.planning/graphs/graph.json` is absent, so no graphify semantic relationship context was available for this research. [VERIFIED: command `ls .planning/graphs/graph.json 2>/dev/null` exited 1]
- The planner should rely on the source/document map below instead of graphify-derived relationships for Phase 33. [VERIFIED: command `ls .planning/graphs/graph.json 2>/dev/null` exited 1; INFERRED]

## Current Code Map

| Area | Exact code | What matters for planning |
|------|------------|---------------------------|
| Current RAG DTOs | `src/agent/rag_context/schemas.py` defines `MaterialClaim`, `RagContextBuildInput`, `RagContextBundle`, prompt/verifier/debug/safe contexts, and citation map entries. [VERIFIED: src/agent/rag_context/schemas.py:30-159] | Current DTOs are strict but do not equal the target `VerifiedEvidencePackageV1` or `ClaimVerificationBundleV1`; planner must adapt or wrap them instead of renaming them blindly. [VERIFIED: docs/contract-spec.md:279-339; src/agent/rag_context/schemas.py:144-159] |
| Candidate validation and projections | `ContextBuilder.build` dedupes candidate refs, validates tenant/content, sorts by rank, budgets evidence items, and emits prompt/verifier/debug/final-safe projections. [VERIFIED: src/agent/rag_context/builder.py:66-120; tests/agent/rag_context/test_context_builder.py:108-139] | This is the best reusable implementation for `build_verified_context`, but it needs package identity/status, evidence items, maps, rejected/stale/conflict classification, and writer ownership. [VERIFIED: docs/contract-spec.md:279-307; docs/contract-spec.md:904-906] |
| Canonical row validation | `ContextBuilder` can use `get_verified_evidence_details`, falls back to canonical rows, and checks text hash, latest version, effective date, merchant scope, doc type, and risk level. [VERIFIED: src/agent/rag_context/builder.py:244-330; src/agent/rag_context/builder.py:465-507] | APF-13 should preserve these checks behind KnowledgeService rather than duplicating them in graph nodes. [VERIFIED: .planning/REQUIREMENTS.md:47-50; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:23-40] |
| KnowledgeService boundary | `PolicyKnowledgeService` currently exposes `search`, `get_verified_evidence_contents`, `get_verified_evidence_provenance`, `get_canonical_evidence_rows`, and `get_verified_evidence_details`. [VERIFIED: src/knowledge/service.py:102-180; src/knowledge/service.py:210-393] | Target public boundary adds `build_verified_context` and `verify_claims`; current service has enough internals to start without new retrieval backends. [VERIFIED: docs/contract-spec.md:16-31; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:23-26] |
| Candidate retrieval | `investigate` includes `search_policy` in its deterministic fallback plan and stores policy candidate refs in `policy_evidence` and `retrieved_evidence.evidence_refs`. [VERIFIED: src/agent/nodes/investigate.py:34-61; src/agent/nodes/investigate.py:226-244; src/agent/nodes/investigate.py:540-590] | `investigate` should remain candidate retrieval owner and must not write target verified package fields. [VERIFIED: docs/contract-spec.md:639-660; docs/contract-spec.md:925-929] |
| Knowledge tool executor | `KnowledgeToolExecutor` exposes only `search_policy` and returns `policy_evidence_refs` from `PolicyKnowledgeService.search`. [VERIFIED: src/tools/executors/knowledge.py:17-91] | No new ToolPlatform tool is needed for `rag_context_build`; the deterministic node should call KnowledgeService directly via trusted config/session. [VERIFIED: docs/contract-spec.md:1203-1214; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:30-34; INFERRED] |
| Citation membership | `validate_membership` checks only cited `evidence_id` presence and explicitly does not infer semantic support. [VERIFIED: src/knowledge/citation.py:1-6; src/knowledge/citation.py:15-51] | `claim_verify` must not reuse membership as support; membership remains a necessary input gate. [VERIFIED: docs/contract-spec.md:247-255; docs/contract-spec.md:341-347] |
| Current material claims | `MaterialClaim` currently uses `authority_class` values `policy_claim`, `business_fact_claim`, and `action_recommendation_claim`. [VERIFIED: src/agent/rag_context/schemas.py:14-45; tests/agent/rag_context/test_material_claims.py:66-93] | Contract `MaterialClaimV1` uses `claim_type` values `policy`, `business_fact`, and `action_recommendation`; planner must decide compatibility adapter or schema migration. [VERIFIED: docs/contract-spec.md:308-317; src/agent/rag_context/schemas.py:30-45] |
| Claim verifier | `MaterialClaimVerifier.verify_claim` runs Level 1 gates, business-fact branch, action branch, policy support branch, and dependency checks. [VERIFIED: src/agent/rag_context/verifier.py:262-335; src/agent/rag_context/verifier.py:398-520; src/agent/rag_context/verifier.py:826-865] | Reuse this for per-claim checks, but add bundle aggregation and route fields matching `ClaimVerificationBundleV1`. [VERIFIED: docs/contract-spec.md:330-347; src/agent/nodes/generate_recommendation.py:381-478] |
| Semantic verifier | `SemanticSupportVerifier` has explicit budgets and fail-closed behavior for timeout, provider error, malformed output, and budget overflow. [VERIFIED: src/agent/rag_context/verifier.py:87-120; tests/agent/rag_context/test_semantic_verifier.py:105-170] | Tests should mock provider behavior; no phase `AI-SPEC.md` exists, so live AI/provider evaluation should remain out of the implementation plan unless a separate AI spec is added. [VERIFIED: command `test -f .planning/phases/33-rag-context-build-and-claim-verification/AI-SPEC.md && echo present || echo absent`; tests/agent/rag_context/test_semantic_verifier.py:128-170; INFERRED] |
| Existing route map | `src/agent/rag_context/routing.py` maps verifier outcomes/reason codes to backend-owned routes and blocks recommendation/action/approval/draft/snapshot on non-allow. [VERIFIED: src/agent/rag_context/routing.py:12-40; src/agent/rag_context/routing.py:100-162; tests/agent/rag_context/test_routing.py:121-180] | It is reusable but route values differ from the target `ClaimVerificationBundleV1.route` values `continue`, `final_response`, and `manual_review`. [VERIFIED: docs/contract-spec.md:330-339; src/agent/rag_context/routing.py:12-18] |
| Current oversized generation node | `generate_recommendation` currently builds a RAG bundle, validates membership, emits material claims, verifies them, mutates the draft, writes verifier fields, and writes `evidence_refs`. [VERIFIED: src/agent/nodes/generate_recommendation.py:182-280; src/agent/nodes/generate_recommendation.py:381-478; src/agent/nodes/generate_recommendation.py:804-860] | Phase 33 must split this node so generation consumes verified prompt projection and emits `material_claims` only. [VERIFIED: docs/contract-spec.md:642-643; docs/contract-spec.md:907-929] |
| AgentState | Current state has `rag_context_bundle`, `rag_verification`, `verifier_status`, `verification_route`, `verifier_reason_codes`, `verifier_safe_citation_refs`, and `verifier_metrics`. [VERIFIED: src/agent/state.py:83-99] | Missing target fields include `rag_context_status`, `verified_evidence_package`, `citation_map`, `evidence_map`, `material_claims`, `claim_verification_bundle`, `blocked_claims`, `safe_support_refs`, and likely `risk_signals`. [VERIFIED: docs/contract-spec.md:904-910; src/agent/state.py:83-99] |
| State reset | `receive_request` resets current RAG/verifier compatibility fields each turn. [VERIFIED: src/agent/nodes/receive_request.py:61-138] | Any new Phase 33 fields must be reset here and covered by reset tests. [VERIFIED: docs/contract-spec.md:851-870; docs/contract-spec.md:904-908; src/agent/nodes/receive_request.py:61-138; INFERRED] |
| Graph vocabulary | `rag_context_build` and `claim_verify` are currently `deferred_non_runnable` entries with Phase 33 reason codes. [VERIFIED: src/agent/graph_vocabulary.py:76-91; tests/agent/test_graph_vocabulary.py:91-106] | Phase 33 must promote or explicitly fail-close these entries and update Phase 32 static guards. [VERIFIED: tests/architecture/test_phase32_static_contract.py:37-47; .planning/phases/32-intent-graph-migration/32-MVP-TARGET-MAPPING.md:23-24] |
| Graph registration | `build_graph` currently registers `generate_recommendation` and routes it directly to risk/final, with no `rag_context_build` or `claim_verify` nodes. [VERIFIED: src/agent/graph.py:131-211; tests/agent/test_graph.py:728-737] | Planner should add explicit nodes and update conditional edges: `investigate -> rag_context_build -> generation -> claim_verify -> risk/final`. [VERIFIED: docs/contract-spec.md:663-675; docs/target-agent-platform-architecture-plan.md:214-249; INFERRED] |
| Router code | `_INVESTIGATE_ROUTES` lacks `rag_context_build`, `_RECOMMENDATION_ROUTES` lacks `claim_verify`, and `route_after_recommendation` currently sends allow/none directly to risk. [VERIFIED: src/agent/routing.py:17-23; src/agent/routing.py:271-349] | Add deterministic `route_after_rag_context` and `route_after_claim_verify`, then update finite route-key guards and graph tests. [VERIFIED: docs/contract-spec.md:663-675; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:32-34; INFERRED] |
| Risk gate | `assess_risk_and_approval` blocks non-allow current verifier routes but builds snapshots from `state.evidence_refs`, draft refs, or `retrieved_evidence.evidence_refs`. [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:152-175; src/agent/nodes/assess_risk_and_approval.py:264-314; src/agent/nodes/assess_risk_and_approval.py:442-454] | Phase 33 must prevent candidate `retrieved_evidence.evidence_refs` fallback from binding action snapshots. [VERIFIED: docs/contract-spec.md:925-929; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:41-42; INFERRED] |
| Action draft | `action_draft` blocks current non-allow verifier routes before durable draft creation. [VERIFIED: src/agent/nodes/action_draft.py:99-111; src/agent/nodes/action_draft.py:215-230] | Keep this fail-closed behavior but read `claim_verification_bundle` or a compatibility route adapter. [VERIFIED: docs/contract-spec.md:675-678; docs/contract-spec.md:908-929; INFERRED] |
| Final response | `final_response` renders current verifier route failures and a narrow policy-QA partial-overlap path. [VERIFIED: src/agent/nodes/final_response.py:272-320; src/agent/nodes/final_response.py:407-425; src/agent/nodes/final_response.py:512-630] | Update final responses to consume `ClaimVerificationBundleV1` and safe support refs without leaking debug/verifier internals. [VERIFIED: docs/contract-spec.md:341-347; tests/agent/rag_context/test_leakage.py:264-361; INFERRED] |
| Working state projection | `project_working_state` currently can expose `evidence_refs`, `policy_evidence`, or `retrieved_evidence.evidence_refs` as `retrieved_evidence_refs`. [VERIFIED: src/agent/working_state.py:133-216] | APF-13 requires prompt/action surfaces to prefer verified package projection/safe refs and treat candidate refs as prompt-unsafe. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:41-42; docs/contract-spec.md:925-929; INFERRED] |
| Trace/API projections | `build_trace_summary` counts evidence from `retrieved_evidence.evidence_refs`, and trace APIs project safe target node names but not RAG/claim bundle fields. [VERIFIED: src/agent/trace.py:236-288; src/api/routers/traces.py:106-115; src/api/schemas/agent_runs.py:24-33] | Phase 33 should add safe status/count/ref projections, not raw package/debug payloads, and should consider evidence_count semantics. [VERIFIED: docs/eval-test-plan.md:33-39; tests/agent/rag_context/test_leakage.py:264-361; INFERRED] |
| DB persistence | `AgentStep` has JSONB `input_summary`, `output_summary`, `metrics_json`, and `evidence_refs`; `AgentTraceEvent` has JSONB `evidence_refs_json` and `redacted_payload`. [VERIFIED: src/db/models.py:964-990; src/db/models.py:1228-1279] | A schema migration is not required for state-only package/bundle fields unless a plan adds new columns or new trace event types. [VERIFIED: src/db/models.py:964-990; src/db/models.py:1228-1279; INFERRED] |

## Standard Stack

### Core

| Library / Component | Version | Purpose | Why Standard |
|---------------------|---------|---------|--------------|
| Python | `>=3.12`; `.venv` is Python 3.12.13 | Runtime language for backend graph/services/tests. [VERIFIED: pyproject.toml:5; command `.venv/bin/python --version`] | Project code uses Python 3.12 constructs and AGENTS warns bare commands can hit older Python. [VERIFIED: AGENTS.md:16-21] |
| `uv` | 0.11.2 | Project command runner and dependency environment entrypoint. [VERIFIED: command `uv --version`] | MOCA validation rules require `uv run pytest ...` or venv pytest. [VERIFIED: AGENTS.md:16-21] |
| Pydantic | 2.13.4 | Strict DTO schemas for state, evidence refs, material claims, business refs, and route/bundle payloads. [VERIFIED: command `uv run python -c ...`; src/agent/rag_context/schemas.py:8-45; src/knowledge/schemas.py:13-69] | Existing project pattern uses `ConfigDict(extra="forbid")` and typed `BaseModel` boundaries. [VERIFIED: src/agent/rag_context/schemas.py:20-45; src/business/schemas.py:20-56] |
| LangGraph | 1.1.10 | StateGraph orchestration and graph node/routing runtime. [VERIFIED: command `uv run python -c ...`; src/agent/graph.py:16-18] | Current agent graph is built with `StateGraph(AgentState)` and named nodes/conditional edges. [VERIFIED: src/agent/graph.py:131-211] |
| SQLAlchemy | 2.0.49 | DB ORM for policy chunks, agent traces, approvals, action snapshots, and JSONB persistence. [VERIFIED: command `uv run python -c ...`; src/db/models.py:24-25] | Existing repositories/services use SQLAlchemy async sessions and JSONB fields for flexible trace/evidence payloads. [VERIFIED: src/repositories/policy_chunk_repo.py:1-16; src/db/models.py:964-990] |
| `PolicyKnowledgeService` + `PolicyRetrievalEngine` | Local source | Knowledge boundary for search and canonical evidence validation. [VERIFIED: src/knowledge/service.py:102-180; src/knowledge/retrieval.py:234-340] | Target contract says KnowledgeService owns EvidenceRef, VerifiedEvidencePackage, MaterialClaim, and ClaimVerificationBundle behavior. [VERIFIED: docs/contract-spec.md:16-31] |
| `src.agent.rag_context` kernel | Local source | ContextBuilder, claim verifier, route mapping, semantic verifier, and material claim helpers. [VERIFIED: src/agent/rag_context/builder.py:47-73; src/agent/rag_context/verifier.py:262-286; src/agent/rag_context/routing.py:100-162; src/agent/rag_context/claims.py:15-95] | Phase 33 should reuse this kernel and move orchestration behind service/node boundaries. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:23-26; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:165-180] |

### Supporting

| Library / Component | Version | Purpose | When to Use |
|---------------------|---------|---------|-------------|
| `pytest` | 9.0.3 | Unit/integration/architecture validation. [VERIFIED: command `uv run python -c ...`; pyproject.toml:36-37] | Use for every Phase 33 plan gate through `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`. [VERIFIED: AGENTS.md:16-21] |
| `pytest-asyncio` | 1.3.0 | Async service/node tests. [VERIFIED: command `uv run python -c ...`; pyproject.toml:36-37] | Existing async RAG/graph tests use `@pytest.mark.asyncio`. [VERIFIED: tests/agent/rag_context/test_context_builder.py:142-180; tests/agent/rag_context/test_verifier.py:113-138] |
| `ruff` | 0.15.12 | Static style/lint validation. [VERIFIED: command `uv run python -c ...`; pyproject.toml:39-55] | Use final plan-level focused lint on touched files through `uv run ruff check ...`. [VERIFIED: AGENTS.md:16-21; .planning/phases/32-intent-graph-migration/32-05-SUMMARY.md:104-108] |
| `langchain-openai` | 1.2.1 | Existing dependency for LLM integrations. [VERIFIED: command `uv run python -c ...`; pyproject.toml:21] | Do not introduce live semantic-provider dependency for deterministic dev tests; mock semantic provider behavior. [VERIFIED: tests/agent/rag_context/test_semantic_verifier.py:128-170; command `test -f .../AI-SPEC.md && echo present || echo absent`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `PolicyKnowledgeService.build_verified_context` orchestration | Continue constructing `ContextBuilder` directly inside graph nodes | Direct node orchestration repeats the current Phase 22 ownership problem and conflicts with the target KnowledgeService public boundary. [VERIFIED: src/agent/nodes/generate_recommendation.py:334-358; docs/contract-spec.md:16-31] |
| `MaterialClaimV1` input to `claim_verify` | Parse final natural language response after generation | CONTEXT locks that claim verification must not parse final natural language as primary input. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:52-56] |
| Existing retrieval/reranker tuning | Add new query planners, rerankers, or search backends | Phase 33 explicitly excludes new retrieval algorithms/backends/tuning beyond preserving existing behavior. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:26; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:206-212] |
| New DB tables for package/bundle | Store package/bundle in existing AgentStep JSONB / trace redacted payload | No ORM schema change is required for state-only DTOs and JSONB trace summaries; new columns/events would require migration. [VERIFIED: src/db/models.py:964-990; src/db/models.py:1228-1279; INFERRED] |

**Installation:**

No new packages are recommended for Phase 33 MVP. [VERIFIED: pyproject.toml:1-55; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:26]

```bash
uv sync --extra dev
```

**Version verification:** Python dependency versions were verified with `uv run python -c "import importlib.metadata as m; ..."` because this is a Python project, not an npm project. [VERIFIED: command `uv run python -c "import importlib.metadata as m; ..."`]

## Architecture Patterns

### System Architecture Diagram

Primary data flow for APF-13/APF-14: [VERIFIED: docs/contract-spec.md:641-675; docs/target-agent-platform-architecture-plan.md:403-488]

```text
API / trusted graph config
  -> LangGraph AgentState
    -> investigate
       -> ToolPlatform.invoke("search_policy")
          -> PolicyKnowledgeService.search
             -> PolicyRetrievalEngine / PolicyChunkRepository
       -> candidate policy refs in policy_evidence / retrieved_evidence
    -> route_after_investigate
       -> rag_context_build when policy evidence is required
    -> rag_context_build
       -> PolicyKnowledgeService.build_verified_context
          -> canonical evidence re-fetch + scope/hash/version/effective-date/provenance checks
       -> AgentState: rag_context_status, verified_evidence_package, citation_map, evidence_map
    -> route_after_rag_context
       -> fail closed / clarify / recommendation_generation
    -> recommendation_generation
       -> consumes verified prompt projection
       -> writes recommendation/proposed_action/material_claims only
    -> route_after_recommendation
       -> claim_verify when material claims or action claim exist
    -> claim_verify
       -> PolicyKnowledgeService.verify_claims
          -> MaterialClaimVerifier + DomainRuleVerifier + selective semantic verifier
       -> AgentState: claim_verification_bundle, blocked_claims, safe_support_refs
    -> route_after_claim_verify
       -> final_response on blocked/manual/error
       -> risk_gate path only when verified and action-safe
```

### Recommended Project Structure

Use the existing package layout and add narrow modules only where ownership becomes clearer. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:77-81; src/knowledge/service.py:102-180; src/agent/rag_context/claims.py:15-95]

```text
src/
├── knowledge/
│   ├── schemas.py          # EvidenceRefV1 plus public KnowledgeService-owned DTOs
│   └── service.py          # search, build_verified_context, verify_claims orchestration
├── agent/
│   ├── rag_context/        # reusable ContextBuilder, verifier, routes, claim adapters
│   ├── nodes/
│   │   ├── rag_context_build.py
│   │   └── claim_verify.py
│   ├── routing.py          # route_after_rag_context, route_after_claim_verify
│   ├── graph.py            # registered nodes and conditional edges
│   ├── graph_vocabulary.py # Phase 33 runtime vocabulary promotion
│   ├── state.py            # target AgentState fields
│   └── working_state.py    # prompt-safe verified refs only
└── api/
    └── routers/            # safe status/count projections only, no raw package/debug payload
```

### Pattern 1: Service-Owned Evidence Package Builder

**What:** Add `PolicyKnowledgeService.build_verified_context(...)` as the public orchestration boundary and delegate reusable projection work to `ContextBuilder`. [VERIFIED: docs/contract-spec.md:16-31; src/agent/rag_context/builder.py:47-73]  
**When to use:** Use from `rag_context_build` only; do not call it from routers or LLM prompt assembly. [VERIFIED: docs/contract-spec.md:641-643; docs/contract-spec.md:663-675]  
**Example:**

```python
# Source: docs/contract-spec.md:641-643 and src/agent/rag_context/builder.py:66-73
package = await knowledge_service.build_verified_context(
    candidate_evidence_refs=state_candidate_refs,
    business_fact_refs=business_refs,
    knowledge_context=knowledge_context,
    evidence_policy=evidence_policy,
)
return {
    "rag_context_status": package.status,
    "verified_evidence_package": package.model_dump(mode="json"),
    "citation_map": package.citation_map,
    "evidence_map": package.evidence_map,
}
```

### Pattern 2: Router Totality by Finite Route Keys

**What:** Keep route functions deterministic, side-effect-free, exception-safe, and guarded by finite allowed route sets. [VERIFIED: src/agent/routing.py:260-279; docs/contract-spec.md:663-675]  
**When to use:** Use for `route_after_rag_context`, `route_after_recommendation`, and `route_after_claim_verify`. [VERIFIED: docs/contract-spec.md:672-675]  
**Example:**

```python
# Source: docs/contract-spec.md:672-675 and src/agent/routing.py:260-279
def route_after_rag_context(state: AgentState) -> str:
    try:
        route = _route_after_rag_context(state)
    except Exception:
        return "final_response"
    if route in {"recommendation_generation", "clarification_gate", "final_response"}:
        return route
    return "final_response"
```

### Pattern 3: Material Claim Verification as Bundle Aggregation

**What:** Keep `MaterialClaimVerifier.verify_claim(...)` for claim-level logic and add a bundle aggregation function that emits `ClaimVerificationBundleV1`. [VERIFIED: src/agent/rag_context/verifier.py:280-335; docs/contract-spec.md:330-347]  
**When to use:** Use in `claim_verify` after `recommendation_generation` writes `material_claims`. [VERIFIED: docs/contract-spec.md:642-643; docs/contract-spec.md:674-675]  
**Example:**

```python
# Source: docs/contract-spec.md:330-347 and src/agent/nodes/generate_recommendation.py:424-477
bundle = await knowledge_service.verify_claims(
    material_claims=state["material_claims"],
    verified_evidence_package=state.get("verified_evidence_package"),
    business_context=state.get("business_context") or {},
    proposed_action=state.get("proposed_action"),
)
return {
    "claim_verification_bundle": bundle.model_dump(mode="json"),
    "blocked_claims": bundle.blocked_claims,
    "safe_support_refs": [ref.model_dump(mode="json") for ref in bundle.safe_support_refs],
}
```

### Anti-Patterns to Avoid

- **One giant `33-01-PLAN.md`:** This phase crosses contracts, service boundary, graph routing, generation, downstream gates, trace/API projection, and validation; project rules mark that as a planning blocker. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:67-75; AGENTS.md:47-52]
- **Candidate refs promoted to prompt/action:** Candidate refs in `policy_evidence` / `retrieved_evidence` are retrieval outputs, not verified package refs or claim support. [VERIFIED: docs/contract-spec.md:257-263; docs/contract-spec.md:925-929]
- **Verifier ownership in generation:** `recommendation_generation` must write material claims but cannot mark claims verified. [VERIFIED: docs/contract-spec.md:907-929]
- **Router service calls:** Routers must not call LLMs, tools, repositories, external APIs, or services. [VERIFIED: docs/contract-spec.md:663-665]
- **Business fact substitution:** Policy evidence, memory, model knowledge, prompt summaries, raw rows, and user text cannot prove current business facts. [VERIFIED: docs/contract-spec.md:341-347; tests/agent/rag_context/test_authority_boundaries.py:147-180; tests/agent/rag_context/test_authority_boundaries.py:254-276]

## Recommended Plan Split

| Plan | Ownership Boundary | Depends On | Main Files | Required Tests |
|------|--------------------|------------|------------|----------------|
| 33-01 Contracts, state, and service boundary | KnowledgeService public contract + AgentState lifecycle | Phase 32 completed | `src/knowledge/schemas.py`, `src/knowledge/service.py`, `src/agent/rag_context/schemas.py`, `src/agent/state.py`, `src/agent/nodes/receive_request.py` [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:68-75; src/agent/state.py:48-142] | New schema/service/reset tests plus `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_material_claims.py tests/agent/test_nodes/test_receive_request.py -q --tb=short`. [VERIFIED: tests/agent/rag_context/test_material_claims.py:66-100; src/agent/nodes/receive_request.py:61-138] |
| 33-02 `rag_context_build` node and route | Candidate-to-verified evidence boundary | 33-01 | `src/agent/nodes/rag_context_build.py`, `src/agent/routing.py`, `src/agent/graph.py`, `src/agent/graph_vocabulary.py`, `src/agent/working_state.py` [VERIFIED: docs/contract-spec.md:641-643; src/agent/graph.py:131-211] | New node/router tests plus existing context/budget/leakage tests. [VERIFIED: tests/agent/rag_context/test_context_builder.py:108-294; tests/agent/rag_context/test_budgeting.py:80-180; tests/agent/rag_context/test_leakage.py:264-361] |
| 33-03 Material claims and `claim_verify` | Recommendation output + claim verification bundle | 33-01, 33-02 | `src/agent/nodes/generate_recommendation.py`, `src/agent/nodes/claim_verify.py`, `src/agent/rag_context/verifier.py`, `src/agent/rag_context/routing.py`, `src/agent/routing.py`, `src/agent/graph.py` [VERIFIED: src/agent/nodes/generate_recommendation.py:701-860; docs/contract-spec.md:642-675] | Claim verifier, authority, semantic fail-closed, and graph route tests. [VERIFIED: tests/agent/rag_context/test_verifier.py:113-312; tests/agent/rag_context/test_authority_boundaries.py:121-530; tests/agent/rag_context/test_semantic_verifier.py:93-170] |
| 33-04 Downstream gates and no-leak projections | Risk/action/final/working-state/API safety | 33-02, 33-03 | `src/agent/nodes/assess_risk_and_approval.py`, `src/agent/nodes/action_draft.py`, `src/agent/nodes/final_response.py`, `src/agent/trace.py`, `src/api/routers/agent_runs.py`, `src/api/routers/traces.py`, `src/repositories/trace_repo.py` [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:264-314; src/agent/nodes/final_response.py:512-630; src/api/routers/traces.py:23-71] | Negative tests for unsupported action before risk/approval/action, candidate refs not in snapshots, final/API no-leak. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:75; tests/agent/rag_context/test_routing.py:150-162; tests/test_trace_api.py:284-367] |
| 33-05 Final static/focused/eval closure | Cross-plan verification and Phase 32 guard migration | 33-01..33-04 | `tests/architecture/test_phase32_static_contract.py` or new `test_phase33_*`, Phase docs, focused validation matrix [VERIFIED: tests/architecture/test_phase32_static_contract.py:37-47; .planning/phases/32-intent-graph-migration/32-VALIDATION.md:40-45] | Full Phase 33 focused suite, static guards, `uv run ruff check ...`, `git diff --check`. [VERIFIED: AGENTS.md:16-21; .planning/phases/32-intent-graph-migration/32-05-SUMMARY.md:104-108] |

Each plan has one primary ownership boundary, which keeps contract/schema work, graph evidence gates, claim verification, downstream safety projection, and final regression closure independently reviewable. [VERIFIED: AGENTS.md:47-52; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:67-75; INFERRED]

## Contract Deltas And Migration Risks

| Contract / Field | Current Code | Target | Migration Risk |
|------------------|--------------|--------|----------------|
| `VerifiedEvidencePackageV1` | Current `RagContextBundle` has projections and citation map but lacks package ID/status/evidence item map/rejected stale conflict refs/config versions. [VERIFIED: src/agent/rag_context/schemas.py:144-159] | Target package includes package identity, status, evidence items, citation/evidence maps, projections, rejected/stale/conflict refs, reason codes, policy/retrieval versions. [VERIFIED: docs/contract-spec.md:279-307] | Treating `RagContextBundle` as the whole target would miss APF-13 status/router and audit requirements. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:38-42; INFERRED] |
| `rag_context_status` | Current state has no `rag_context_status`. [VERIFIED: src/agent/state.py:83-99] | Target status enum is `not_required`, `verified`, `partial`, `no_evidence`, `unauthorized`, `stale`, `conflict`, `invalid_hash`, `invalid_scope`, `build_error`. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:46-48; docs/contract-spec.md:279-293] | Router totality depends on exact mapping from reason codes to status; tests must pin invalid hash/scope/stale/conflict fail-closed paths. [VERIFIED: docs/eval-test-plan.md:33-34; INFERRED] |
| `MaterialClaimV1` | Current claim schema uses `authority_class` values ending in `_claim` and `source_node`. [VERIFIED: src/agent/rag_context/schemas.py:30-45] | Contract uses `claim_type` values `policy`, `business_fact`, `action_recommendation` and `generated_from_step`. [VERIFIED: docs/contract-spec.md:308-317] | Existing tests and helpers may need compatibility adapters or phased field aliases to avoid breaking current verifier tests. [VERIFIED: tests/agent/rag_context/test_material_claims.py:66-100; INFERRED] |
| `ClaimVerificationBundleV1` | Current `generate_recommendation` returns a normalized dict with `overall_outcome`, `route`, `material_claims`, `reason_codes`, `safe_citation_refs`, and metrics. [VERIFIED: src/agent/nodes/generate_recommendation.py:769-783] | Target bundle has `overall_status`, `route`, claim-level results, blocked claims, safe support refs, reason codes, and verifier policy version. [VERIFIED: docs/contract-spec.md:330-339] | Downstream route and final response logic will keep reading old fields unless compatibility adapters are explicit. [VERIFIED: src/agent/nodes/final_response.py:272-320; src/agent/nodes/action_draft.py:99-111; INFERRED] |
| `BusinessFactRefV1` support | Business fact refs are typed in `src/tools/contracts.py` and consumed by business schemas/service. [VERIFIED: src/tools/contracts.py:58-69; src/business/schemas.py:20-56; src/business/service.py:90-150] | Business fact claims must cite current `BusinessFactRefV1` / `BusinessFactResultV1` authority. [VERIFIED: docs/contract-spec.md:341-347] | If `claim_verify` reads prompt summaries or memory for business support, it violates APF-14. [VERIFIED: tests/agent/rag_context/test_authority_boundaries.py:147-180; tests/agent/rag_context/test_authority_boundaries.py:254-276; INFERRED] |
| Writer ownership | Current generation node writes context bundle, verification, route, safe refs, metrics, and evidence refs. [VERIFIED: src/agent/nodes/generate_recommendation.py:268-280] | `rag_context_build` is only writer for package/status/maps; `claim_verify` is only writer for bundle/blocked/safe refs; generation writes only material claims. [VERIFIED: docs/contract-spec.md:904-929] | Missing writer tests can allow LLM/generation to override hard-gate results. [VERIFIED: docs/eval-test-plan.md:21-39; INFERRED] |
| Reset / merge rules | `receive_request` resets current compatibility RAG/verifier fields. [VERIFIED: src/agent/nodes/receive_request.py:61-138] | Target fields reset each turn and replace by package/bundle, while blocked claims cannot be merged away by LLM. [VERIFIED: docs/contract-spec.md:851-870; docs/contract-spec.md:904-908] | Stale package/bundle fields could leak across turns without explicit reset tests. [VERIFIED: tests/agent/test_graph.py:610-658; INFERRED] |
| Projection separation | Current builder separates prompt/verifier/debug/final/memory/replay/business/action snapshot contexts. [VERIFIED: src/agent/rag_context/schemas.py:90-159; tests/agent/rag_context/test_context_builder.py:108-139] | Target package separates prompt/verifier/replay/debug projections and forbids raw internals in ordinary surfaces. [VERIFIED: docs/contract-spec.md:279-307; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:38-42] | `working_state` currently can expose candidate refs from `policy_evidence` or `retrieved_evidence`; this is a prompt-leak risk. [VERIFIED: src/agent/working_state.py:206-216; INFERRED] |
| Fail-closed routes | Current route map blocks non-allow verifier routes but uses Phase 22 route values. [VERIFIED: src/agent/rag_context/routing.py:12-40; tests/agent/rag_context/test_routing.py:150-162] | Target routes require `route_after_rag_context` and `route_after_claim_verify` with valid graph node keys. [VERIFIED: docs/contract-spec.md:663-675] | If old `allow` route semantics remain attached to generation, unsupported actions may enter risk before `claim_verify`. [VERIFIED: src/agent/routing.py:282-286; docs/contract-spec.md:674-675; INFERRED] |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Evidence text hashing | Custom hash normalization inside nodes | `evidence_text_hash` / `EvidenceRefV1.build` [VERIFIED: src/knowledge/text_hash.py:9-19; src/knowledge/schemas.py:31-69] | Contract requires one canonical hash rule and snapshot builders must strip score only in canonical projection. [VERIFIED: docs/contract-spec.md:226-245] |
| Candidate evidence re-fetch | Direct repository queries inside graph nodes | `PolicyKnowledgeService.get_verified_evidence_details` and future `build_verified_context` [VERIFIED: src/knowledge/service.py:298-393] | KnowledgeService owns evidence validation and graph nodes should not import repositories for this boundary. [VERIFIED: docs/contract-spec.md:16-31] |
| Citation support semantics | Treat citation membership as claim support | `validate_membership` plus `MaterialClaimVerifier` support checks [VERIFIED: src/knowledge/citation.py:1-6; src/agent/rag_context/verifier.py:311-334] | Membership is necessary but not semantic support. [VERIFIED: docs/contract-spec.md:247-255; tests/agent/rag_context/test_verifier.py:113-135] |
| Business fact support | Infer current facts from policy, memory, prompts, user text, or raw rows | `BusinessFactService` / `BusinessFactRefV1` / `BusinessFactResultV1` [VERIFIED: src/business/service.py:90-150; src/tools/contracts.py:58-69] | Business facts require current business authority and scope. [VERIFIED: docs/contract-spec.md:122-139; tests/agent/rag_context/test_authority_boundaries.py:147-180] |
| Router decisions | Router calls LLM/tools/services to decide next node | Pure deterministic route functions with finite route-key guards [VERIFIED: src/agent/routing.py:260-279] | Contract forbids routers from calling LLMs, tools, repositories, external APIs, or services. [VERIFIED: docs/contract-spec.md:663-665] |
| Claim extraction | Parse final response prose for claims | Stable `MaterialClaimV1` emitted by generation [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:52-56] | Claim verification must not parse final natural language as the primary input. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:52-56] |
| Prompt/API redaction | Ad hoc string filtering after raw bundle exposure | Existing projection/no-leak helpers and tests, plus target package projections [VERIFIED: tests/agent/rag_context/test_leakage.py:264-361; src/agent/rag_context/schemas.py:90-159] | Raw source/OCR/verifier/private reasoning/unbounded text is forbidden in ordinary surfaces. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:41-42] |

**Key insight:** The hard part is not retrieval; it is preserving authority boundaries as data moves from candidate refs to verified package to material claims to action/risk gates. [VERIFIED: docs/contract-spec.md:257-263; docs/contract-spec.md:925-929; docs/eval-test-plan.md:33-34; INFERRED]

## Common Pitfalls

### Pitfall 1: Candidate Ref Leakage
**What goes wrong:** `policy_evidence` or `retrieved_evidence.evidence_refs` enters prompts, action snapshots, risk, final response citations, working-state prompt context, or APIs before `rag_context_build`. [VERIFIED: src/agent/working_state.py:206-216; src/agent/nodes/assess_risk_and_approval.py:264-314]  
**Why it happens:** Existing compatibility code used retrieved evidence as a fallback before target package fields existed. [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:264-314; src/agent/trace.py:263-269]  
**How to avoid:** Make verified package prompt/safe refs the only downstream source and add negative tests for candidate-only refs. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:41-42; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:75]  
**Warning signs:** Tests pass while `retrieved_evidence.evidence_refs` still appears in snapshot or prompt projection code paths. [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:264-314; INFERRED]

### Pitfall 2: Generation Still Owns Verification
**What goes wrong:** `generate_recommendation` continues to call `ContextBuilder` or `MaterialClaimVerifier` directly and writes verifier status. [VERIFIED: src/agent/nodes/generate_recommendation.py:182-280; src/agent/nodes/generate_recommendation.py:381-478]  
**Why it happens:** Current Phase 22 behavior colocates context build, claim construction, verification, and draft mutation. [VERIFIED: src/agent/nodes/generate_recommendation.py:182-280]  
**How to avoid:** Move verification orchestration to `claim_verify` and leave generation with prompt consumption plus material-claim output. [VERIFIED: docs/contract-spec.md:642-643; docs/contract-spec.md:907-929]  
**Warning signs:** `generate_recommendation` writes `rag_verification`, `verification_route`, or `verifier_safe_citation_refs` after Phase 33. [VERIFIED: src/agent/nodes/generate_recommendation.py:268-280; INFERRED]

### Pitfall 3: Route Values Drift from Graph Keys
**What goes wrong:** `ClaimVerificationBundleV1.route` values or old Phase 22 routes do not map to LangGraph edge keys. [VERIFIED: docs/contract-spec.md:330-339; src/agent/rag_context/routing.py:12-18]  
**Why it happens:** Contract route values are semantic, while graph routers return node keys. [VERIFIED: docs/contract-spec.md:330-339; docs/contract-spec.md:663-675]  
**How to avoid:** Keep bundle route semantic and adapter route functions returning finite graph keys; test all router returns are registered edges. [VERIFIED: tests/agent/test_graph.py:748-798]  
**Warning signs:** A bundle route value like `continue` is returned directly to LangGraph. [VERIFIED: docs/contract-spec.md:330-339; docs/contract-spec.md:663-675; INFERRED]

### Pitfall 4: Phase 32 Static Guards Left Unchanged
**What goes wrong:** Phase 32 tests still assert `rag_context_build` and `claim_verify` are non-runnable after Phase 33 promotes them. [VERIFIED: tests/architecture/test_phase32_static_contract.py:37-47; tests/agent/test_graph.py:728-737]  
**Why it happens:** Phase 32 intentionally froze Phase 33 target names as deferred placeholders. [VERIFIED: .planning/phases/32-intent-graph-migration/32-MVP-TARGET-MAPPING.md:23-24; .planning/phases/32-intent-graph-migration/32-05-SUMMARY.md:55-63]  
**How to avoid:** Move the guard to Phase 33 semantics: nodes are runnable/fail-closed and have explicit tests, not absent. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:30-31; INFERRED]  
**Warning signs:** `test_phase_33_target_nodes_are_not_registered_as_runnable_graph_nodes` still exists unchanged. [VERIFIED: tests/agent/test_graph.py:728-737]

### Pitfall 5: Semantic Review Overrides Hard Gates
**What goes wrong:** LLM semantic support marks claims supported despite invalid scope/hash/business authority. [VERIFIED: docs/contract-spec.md:341-347]  
**Why it happens:** Semantic review can look like a higher-order support check unless Level 1/DomainRule gates are enforced first. [VERIFIED: src/agent/rag_context/verifier.py:398-445; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:60-63]  
**How to avoid:** Run hard gates first, keep semantic verifier selective and fail-closed, and pin hard-case tests for negation/conditions/thresholds/time windows/exceptions/conflicts. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:60-63; tests/agent/rag_context/test_semantic_verifier.py:128-170]  
**Warning signs:** Semantic provider result is checked before tenant/scope/hash/business authority. [VERIFIED: src/agent/rag_context/verifier.py:280-335; INFERRED]

## Code Examples

### Verified Evidence Package Status Mapping

```python
# Source: docs/contract-spec.md:279-307 and src/knowledge/service.py:298-393
def package_status(included_count: int, excluded_reason_codes: set[str], evidence_required: bool) -> str:
    if not evidence_required:
        return "not_required"
    if included_count and not excluded_reason_codes:
        return "verified"
    if "text_hash_mismatch" in excluded_reason_codes:
        return "invalid_hash"
    if {"scope_invalid", "merchant_scope_invalid", "doc_type_invalid"} & excluded_reason_codes:
        return "invalid_scope"
    if {"freshness_invalid", "effective_date_invalid", "latest_version_invalid"} & excluded_reason_codes:
        return "stale"
    if included_count:
        return "partial"
    return "no_evidence"
```

### Claim Verification Bundle Aggregation

```python
# Source: docs/contract-spec.md:330-347 and src/agent/nodes/generate_recommendation.py:424-477
blocked = [
    result.claim_id
    for result in claim_results
    if not result.allows_user_visible_claim or not result.allows_action_recommendation
]
overall_status = "verified" if not blocked else "blocked"
route = "continue" if overall_status == "verified" else "final_response"
```

### Candidate Ref Negative Test Shape

```python
# Source: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:75
final_state = await graph.ainvoke(state_with_candidate_only_policy_ref, config)
serialized = json.dumps(final_state, ensure_ascii=False)
assert candidate_evidence_id not in json.dumps(final_state.get("proposed_action") or {})
assert final_state.get("verification_route") != "allow"
assert final_state.get("safety_snapshot_verified") is not True
```

## State Of The Art

| Old / Current Approach | Current Target Approach | When Changed | Impact |
|------------------------|-------------------------|--------------|--------|
| Phase 22 generation node owns RAG context build and claim verification. [VERIFIED: src/agent/nodes/generate_recommendation.py:182-280] | Phase 33 splits retrieval, verified package build, and post-generation claim verification. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:10-14] | Target accepted in Phase 33 context on 2026-06-29. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:3-5] | Planner must avoid a single implementation plan and move ownership behind service/node boundaries. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:67-75; AGENTS.md:47-52] |
| Phase 32 records `rag_context_build` and `claim_verify` as `deferred_non_runnable`. [VERIFIED: src/agent/graph_vocabulary.py:76-91] | Phase 33 makes them runnable semantics or explicit fail-closed behavior. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:30-31] | Phase 32 completed 2026-06-28. [VERIFIED: .planning/STATE.md:200-210] | Static tests must be updated from "not registered" to "registered/fail-closed and correctly routed." [VERIFIED: tests/architecture/test_phase32_static_contract.py:37-47; INFERRED] |
| Citation membership is used inside generation flow before verifier aggregation. [VERIFIED: src/agent/nodes/generate_recommendation.py:216-253] | Membership remains necessary but is not support; support is claim verification bundle output. [VERIFIED: docs/contract-spec.md:247-263; docs/contract-spec.md:341-347] | Contract already states membership/support separation. [VERIFIED: docs/contract-spec.md:247-263] | Tests must prove membership/reranker diagnostics cannot support claims. [VERIFIED: tests/agent/rag_context/test_verifier.py:113-135; tests/agent/rag_context/test_verifier.py:284-312] |

**Deprecated/outdated for Phase 33:**

- `tests/architecture/test_phase32_static_contract.py::test_phase33_rag_and_claim_targets_are_deferred_non_runnable_and_not_graph_registered` becomes obsolete once Phase 33 promotes nodes. [VERIFIED: tests/architecture/test_phase32_static_contract.py:37-47; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:30-31; INFERRED]
- `generate_recommendation` writing `rag_verification` and `verification_route` becomes a compatibility path only after `claim_verify` owns bundle output. [VERIFIED: docs/contract-spec.md:907-929; src/agent/nodes/generate_recommendation.py:268-280; INFERRED]

## Schema Push Requirement Assessment

No ORM schema push is expected for the Phase 33 MVP if the plan keeps `VerifiedEvidencePackageV1` and `ClaimVerificationBundleV1` as Pydantic/state/AgentStep JSONB payloads. [VERIFIED: src/db/models.py:964-990; docs/contract-spec.md:904-908; INFERRED] The current persistence model already has JSONB `AgentStep.evidence_refs`, JSONB summaries/metrics, and `AgentTraceEvent.redacted_payload` / `evidence_refs_json`. [VERIFIED: src/db/models.py:964-990; src/db/models.py:1228-1279] A DB migration becomes required only if the plan adds dedicated package/bundle columns, new tables, or new `AgentTraceEvent.event_type` values because event types are enforced by a CHECK constraint. [VERIFIED: src/db/models.py:1231-1247; INFERRED]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|

No `[ASSUMED]` claims are used in this research; implementation recommendations are either verified from source/docs or explicitly marked as source-backed inference. [VERIFIED: RESEARCH.md self-audit]

## Open Questions

1. **DTO module placement**
   - What we know: Context leaves exact module/file split to planning and likely targets include `src/knowledge/service.py`, `src/agent/rag_context/`, and `src/knowledge/schemas.py`. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:77-81]
   - What's unclear: Whether public target DTOs should live in `src/knowledge/schemas.py` or remain in `src/agent/rag_context/schemas.py` with re-exports. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:77-81; INFERRED]
   - Recommendation: Put canonical KnowledgeService-owned DTOs in `src/knowledge/schemas.py` or re-export them from there to match the ownership registry. [VERIFIED: docs/contract-spec.md:16-31; INFERRED]
2. **Decision event expansion**
   - What we know: Phase 35 owns broad replay/trace/eval hardening, while Phase 33 should preserve enough safe refs/status fields. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:77-81; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:206-212]
   - What's unclear: Whether Phase 33 should add new event types for evidence validation and claim verification. [VERIFIED: src/db/models.py:1231-1247; INFERRED]
   - Recommendation: Avoid new event types in Phase 33 unless necessary; if added, include an Alembic migration because `AgentTraceEvent.event_type` is CHECK-constrained. [VERIFIED: src/db/models.py:1231-1247; INFERRED]
3. **Manual review node absence**
   - What we know: Current graph has `final_response` and approval paths but no dedicated manual-review graph node. [VERIFIED: src/agent/graph.py:131-211]
   - What's unclear: Whether Phase 33 should model `manual_review` as final-response safe handoff or introduce a node. [VERIFIED: docs/contract-spec.md:673-675; src/agent/graph.py:131-211; INFERRED]
   - Recommendation: Use existing final-response/manual-review-style safe response for Phase 33 and defer dedicated review workflow unless user locks a new node. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:47; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:198-199; INFERRED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | All validation commands | Yes [VERIFIED: command `command -v uv && uv --version`] | 0.11.2 [VERIFIED: command `uv --version`] | `.venv/bin/pytest` for tests only [VERIFIED: AGENTS.md:16-21] |
| `.venv/bin/python` | Project Python runtime | Yes [VERIFIED: command `test -x .venv/bin/python && .venv/bin/python --version`] | Python 3.12.13 [VERIFIED: command `.venv/bin/python --version`] | `uv run ...` [VERIFIED: AGENTS.md:16-21] |
| `.venv/bin/pytest` | Direct venv test fallback | Yes [VERIFIED: command `test -x .venv/bin/pytest && .venv/bin/pytest --version`] | pytest 9.0.3 [VERIFIED: command `.venv/bin/pytest --version`] | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` [VERIFIED: AGENTS.md:16-21] |
| `rg` | Source/test audit | Yes [VERIFIED: command `command -v rg && rg --version | head -1`] | ripgrep 14.1.1 [VERIFIED: command `rg --version | head -1`] | POSIX `grep`, but `rg` is available. [VERIFIED: command `command -v rg`] |
| Python dependencies | Phase tests/runtime | Yes [VERIFIED: command `uv run python -c "import importlib.metadata as m; ..."`] | Pydantic 2.13.4, LangGraph 1.1.10, SQLAlchemy 2.0.49, pytest 9.0.3, ruff 0.15.12 [VERIFIED: command `uv run python -c "import importlib.metadata as m; ..."`] | None needed. [VERIFIED: command output] |

**Missing dependencies with no fallback:**
- None found for research/planning. [VERIFIED: environment commands listed above]

**Missing dependencies with fallback:**
- Phase `AI-SPEC.md` is absent; this is non-blocking because Phase 33 can keep semantic provider tests mocked and deterministic. [VERIFIED: command `test -f .planning/phases/33-rag-context-build-and-claim-verification/AI-SPEC.md && echo present || echo absent`; tests/agent/rag_context/test_semantic_verifier.py:128-170; INFERRED]

## Validation Architecture

Validation is enabled because `.planning/config.json` sets `workflow.nyquist_validation` to true. [VERIFIED: .planning/config.json:15-20]

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 [VERIFIED: command `uv run python -c "import importlib.metadata as m; ..."`] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"` [VERIFIED: pyproject.toml:50-55] |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_routing.py -q --tb=short` [VERIFIED: tests/agent/rag_context/test_context_builder.py:108-294; tests/agent/rag_context/test_verifier.py:113-312; tests/agent/rag_context/test_routing.py:121-180] |
| Full focused suite command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/agent/rag_context/test_budgeting.py tests/agent/rag_context/test_material_claims.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_semantic_verifier.py tests/agent/rag_context/test_routing.py tests/agent/rag_context/test_leakage.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_final_response.py tests/agent/test_phase22_action_boundary.py tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_agent_runs_api.py tests/test_trace_api.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_action_draft_boundaries.py tests/business/test_schemas.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_provenance_lookup.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_text_hash.py tests/platform/test_context_projections.py tests/replay/test_replay_api.py -q --tb=short` [VERIFIED: tests discovered with `find tests -maxdepth 3 -type f ...`] |

### Phase Requirements To Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| APF-13 | Candidate refs become `VerifiedEvidencePackageV1` only after scope/hash/version/effective-date validation. [VERIFIED: .planning/REQUIREMENTS.md:47-50] | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_context_builder.py tests/knowledge/test_phase22_evidence_validation.py tests/knowledge/test_provenance_lookup.py -q --tb=short` [VERIFIED: tests/agent/rag_context/test_context_builder.py:242-294; tests/knowledge/test_phase22_evidence_validation.py exists from file audit] | Existing plus W0 updates needed. [VERIFIED: tests/agent/rag_context/test_context_builder.py:242-294; INFERRED] |
| APF-13 | `route_after_rag_context` is deterministic and total over status enum. [VERIFIED: docs/contract-spec.md:672-673] | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_graph_vocabulary.py -q --tb=short` [VERIFIED: tests/agent/test_graph.py:748-798; tests/agent/test_graph_vocabulary.py:91-106] | W0 new route cases required. [VERIFIED: src/agent/routing.py:17-23; INFERRED] |
| APF-13 | Candidate refs do not enter prompt/action/risk/approval directly. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:41-42; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:75] | negative/security | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_leakage.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` [VERIFIED: tests/agent/rag_context/test_leakage.py:264-361; tests/architecture/test_action_draft_boundaries.py:163-205] | Existing plus Phase 33 candidate-only negatives required. [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:264-314; INFERRED] |
| APF-14 | `recommendation_generation` emits `MaterialClaimV1` and does not verify claims. [VERIFIED: docs/contract-spec.md:642-643; docs/contract-spec.md:907-929] | unit/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_generate_recommendation.py tests/agent/rag_context/test_material_claims.py -q --tb=short` [VERIFIED: tests/agent/rag_context/test_material_claims.py:66-100; src/agent/nodes/generate_recommendation.py:701-743] | Existing plus W0 ownership/static tests needed. [VERIFIED: src/agent/nodes/generate_recommendation.py:268-280; INFERRED] |
| APF-14 | `claim_verify` emits `ClaimVerificationBundleV1`, blocked claims, and safe support refs. [VERIFIED: docs/contract-spec.md:330-347; docs/contract-spec.md:641-643] | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_verifier.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_semantic_verifier.py -q --tb=short` [VERIFIED: tests/agent/rag_context/test_verifier.py:113-312; tests/agent/rag_context/test_authority_boundaries.py:121-530; tests/agent/rag_context/test_semantic_verifier.py:93-170] | New `tests/agent/test_nodes/test_claim_verify.py` required. [VERIFIED: src/agent/graph.py:131-211; INFERRED] |
| APF-14 | Unsupported action claims cannot reach risk/approval/action. [VERIFIED: docs/contract-spec.md:341-347; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:63] | negative/security/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_routing.py tests/agent/test_phase22_action_boundary.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_nodes/test_generate_recommendation.py -q --tb=short` [VERIFIED: tests/agent/rag_context/test_routing.py:150-162; src/agent/nodes/action_draft.py:215-230] | Existing plus Phase 33 bundle-based negatives required. [VERIFIED: docs/contract-spec.md:675-678; INFERRED] |

### Sampling Rate

- **Per task commit:** Run the plan-local quick command for touched boundary plus `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_receive_request.py -q --tb=short` when state fields or reset behavior changes. [VERIFIED: AGENTS.md:16-21; src/agent/nodes/receive_request.py:61-138]
- **Per wave merge:** Run the full focused suite listed above. [VERIFIED: .planning/phases/32-intent-graph-migration/32-VALIDATION.md:40-45; INFERRED]
- **Phase gate:** Focused suite green, `uv run ruff check` on touched files, `git diff --check`, and no invalid bare pytest commands in phase artifacts. [VERIFIED: AGENTS.md:16-21; .planning/phases/32-intent-graph-migration/32-05-SUMMARY.md:104-108]

### Wave 0 Gaps

- [ ] `tests/knowledge/test_verified_evidence_package.py` - covers APF-13 package schema/status/map/rejected/stale/conflict semantics. [VERIFIED: docs/contract-spec.md:279-307; INFERRED]
- [ ] `tests/agent/test_nodes/test_rag_context_build.py` - covers node writer ownership, candidate-to-package output, fail-closed errors, and trace step. [VERIFIED: docs/contract-spec.md:641-643; src/agent/graph.py:131-211; INFERRED]
- [ ] `tests/agent/test_rag_context_routing.py` or update `tests/agent/test_graph.py` - covers `route_after_rag_context` totality and graph edge registration. [VERIFIED: docs/contract-spec.md:672-673; tests/agent/test_graph.py:748-798; INFERRED]
- [ ] `tests/knowledge/test_claim_verification_bundle.py` - covers `ClaimVerificationBundleV1`, blocked claims, safe support refs, and verifier policy/config version. [VERIFIED: docs/contract-spec.md:330-347; INFERRED]
- [ ] `tests/agent/test_nodes/test_claim_verify.py` - covers node writer ownership, malformed bundle fail-closed, business fact refs, and action claim blocking. [VERIFIED: docs/contract-spec.md:643-675; INFERRED]
- [ ] `tests/architecture/test_phase33_rag_claim_boundaries.py` - replaces Phase 32 "not runnable" guard with Phase 33 service/node/writer/static ownership checks. [VERIFIED: tests/architecture/test_phase32_static_contract.py:37-47; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:30-31; INFERRED]
- [ ] Update trace/API projection tests so status/count/safe refs are visible without raw package/debug payload. [VERIFIED: src/api/routers/traces.py:106-115; tests/test_trace_api.py:284-367; INFERRED]

## Security Domain

Security enforcement is enabled by default because `.planning/config.json` has no explicit `security_enforcement: false` key and validation workflow is enabled. [VERIFIED: .planning/config.json:1-43; GSD role instruction]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | Indirect | Use existing API auth and `TrustedContextFactory`; do not trust LLM/user/checkpoint fields for tenant/user/run identity. [VERIFIED: src/api/routers/agent_runs.py:196-219; docs/contract-spec.md:122-156] |
| V3 Session Management | Indirect | Reset per-turn state in `receive_request` and preserve only trusted interrupted-run fields. [VERIFIED: src/agent/nodes/receive_request.py:61-138; docs/contract-spec.md:851-870] |
| V4 Access Control | Yes | Scope/hash/version/effective-date validation via KnowledgeService and BusinessFactService authority refs. [VERIFIED: src/knowledge/service.py:298-393; src/business/service.py:90-150; docs/contract-spec.md:122-139] |
| V5 Input Validation | Yes | Strict Pydantic DTOs with `extra="forbid"` for claims, bundles, business facts, and route payloads. [VERIFIED: src/agent/rag_context/schemas.py:20-45; src/business/schemas.py:20-56; src/agent/rag_context/routing.py:20-40] |
| V6 Cryptography | Yes for hashing only | Use existing `evidence_text_hash`; do not invent hash rules. [VERIFIED: src/knowledge/text_hash.py:9-19; docs/contract-spec.md:226-245] |
| V8 Data Protection | Yes | Keep prompt/verifier/replay/debug projections separated and block raw source/OCR/verifier/private reasoning leakage. [VERIFIED: tests/agent/rag_context/test_leakage.py:264-361; .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:41-42] |

### Known Threat Patterns for Phase 33

| Plan | Pattern | STRIDE | Standard Mitigation |
|------|---------|--------|---------------------|
| 33-01 | LLM or stale checkpoint overwrites package/bundle fields. [VERIFIED: docs/contract-spec.md:851-870; docs/contract-spec.md:904-929] | Tampering / Elevation of privilege | State writer ownership tests, reset tests, and `receive_request` reset entries for all new fields. [VERIFIED: src/agent/nodes/receive_request.py:61-138; INFERRED] |
| 33-02 | Invalid hash/scope/unauthorized candidate is promoted to prompt/action. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:41-42] | Tampering / Information disclosure / Elevation of privilege | Canonical re-fetch through KnowledgeService, status enum, rejected refs, and fail-closed `route_after_rag_context`. [VERIFIED: src/knowledge/service.py:298-393; docs/contract-spec.md:672-673] |
| 33-02 | Raw source-block/OCR/provenance/debug payload leaks into prompt/final/API. [VERIFIED: tests/agent/rag_context/test_leakage.py:264-361] | Information disclosure | Projection separation and no-leak tests across prompt/final/memory/replay/action/API. [VERIFIED: src/agent/rag_context/schemas.py:90-159; tests/agent/rag_context/test_leakage.py:264-361] |
| 33-03 | Unsupported policy claim becomes user-visible as supported. [VERIFIED: docs/contract-spec.md:341-347] | Tampering / Repudiation | Rules-first verifier, membership-not-support tests, and bundle `allows_user_visible_claim`. [VERIFIED: tests/agent/rag_context/test_verifier.py:113-135; docs/contract-spec.md:318-339] |
| 33-03 | Business fact claim is proven by RAG/memory/model/prompt/user text. [VERIFIED: docs/contract-spec.md:341-347] | Spoofing / Elevation of privilege | Require `BusinessFactRefV1`/`BusinessFactResultV1` authority and negative tests for all substitutes. [VERIFIED: tests/agent/rag_context/test_authority_boundaries.py:147-180; tests/agent/rag_context/test_authority_boundaries.py:254-276] |
| 33-04 | Unsupported action reaches risk, approval, action draft, or safety snapshot. [VERIFIED: docs/contract-spec.md:341-347] | Elevation of privilege | `route_after_claim_verify` fail-closed, risk/action guards, and snapshot source restricted to verified safe refs. [VERIFIED: src/agent/nodes/action_draft.py:215-230; docs/contract-spec.md:675-678; INFERRED] |
| 33-05 | Trace/API projection exposes raw verifier/package internals or widens run visibility. [VERIFIED: src/api/routers/traces.py:23-71; tests/test_trace_api.py:130-180] | Information disclosure / Elevation of privilege | Safe allowlisted projections and owner/admin visibility unchanged. [VERIFIED: src/api/routers/traces.py:37-44; tests/test_trace_api.py:130-180] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md` - locked decisions, scope, deferred items, code sites, and plan split. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:1-218]
- `.planning/REQUIREMENTS.md` - APF-13/APF-14 requirement text. [VERIFIED: .planning/REQUIREMENTS.md:47-50]
- `.planning/ROADMAP.md` - Phase 33 scope, dependency, success criteria, and Phase 34 downstream dependency. [VERIFIED: .planning/ROADMAP.md:348-390]
- `.planning/STATE.md` - current focus and Phase 32 completion/deferred context. [VERIFIED: .planning/STATE.md:23-31; .planning/STATE.md:125-135; .planning/STATE.md:200-210]
- `docs/contract-spec.md` - normative service ownership, evidence/claim contracts, node/router contracts, state lifecycle, writer boundaries, tool allowlist. [VERIFIED: docs/contract-spec.md:1-31; docs/contract-spec.md:257-347; docs/contract-spec.md:625-680; docs/contract-spec.md:872-930; docs/contract-spec.md:1203-1214]
- `docs/target-agent-platform-architecture-plan.md` - target architecture and RAG/claim migration rationale. [VERIFIED: docs/target-agent-platform-architecture-plan.md:403-488; docs/target-agent-platform-architecture-plan.md:1368-1497]
- Current source modules listed in Current Code Map. [VERIFIED: src/agent/rag_context/schemas.py:30-159; src/agent/rag_context/builder.py:47-120; src/agent/rag_context/verifier.py:262-520; src/knowledge/service.py:102-393; src/agent/graph.py:131-211]
- Existing tests listed in Validation Architecture. [VERIFIED: tests/agent/rag_context/test_context_builder.py:108-294; tests/agent/rag_context/test_verifier.py:113-312; tests/agent/rag_context/test_authority_boundaries.py:121-530; tests/agent/rag_context/test_leakage.py:264-361]

### Secondary (MEDIUM confidence)

- Source-backed implementation inferences about file placement, schema push, graph edge rewiring, and adapter shape. [VERIFIED: each inference tagged inline]

### Tertiary (LOW confidence)

- None. [VERIFIED: research source list]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions and tooling were verified through `uv run python`, `uv --version`, pyproject, and venv commands. [VERIFIED: command outputs; pyproject.toml:1-55]
- Architecture: HIGH - target split is locked in CONTEXT and repeated in contract/architecture docs. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:10-14; docs/contract-spec.md:641-675; docs/target-agent-platform-architecture-plan.md:403-488]
- Current code map: HIGH - source modules and tests were read directly. [VERIFIED: source tags throughout Current Code Map]
- Plan split: HIGH - CONTEXT and AGENTS both require splitting this service-boundary/platform phase. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:67-75; AGENTS.md:47-52]
- Exact DTO module placement: MEDIUM - context leaves file split to planning; recommendation follows KnowledgeService ownership. [VERIFIED: .planning/phases/33-rag-context-build-and-claim-verification/33-CONTEXT.md:77-81; docs/contract-spec.md:16-31; INFERRED]

**Research date:** 2026-06-29 [VERIFIED: environment_context.current_date]  
**Valid until:** 2026-07-29 for local architecture/code findings unless Phase 33 implementation or contract-spec changes first. [VERIFIED: .planning/STATE.md:23-31; INFERRED]
