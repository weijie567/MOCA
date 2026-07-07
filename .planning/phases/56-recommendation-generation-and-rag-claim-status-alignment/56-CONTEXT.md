# Phase 56: Recommendation Generation and RAG Claim Status Alignment - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 56 delivers CAGM-07: make `recommendation_generation` the active registered generation node and align `rag_context_build` / `claim_verify` fail-closed status semantics so unsafe evidence, missing evidence, stale/conflicting evidence, unsupported material claims, or unsupported action claims cannot enter approval/action paths.

This phase is not the final graph no-debt cleanup. It must close the active `generate_recommendation` graph-node debt, but it may keep explicitly documented import/test/historical trace compatibility surfaces until Phase 58. It must not rename `assess_risk_and_approval` to `risk_gate`; that belongs to Phase 57.

</domain>

<decisions>
## Implementation Decisions

### Active recommendation node cutover
- **D-56-01:** Active `StateGraph.add_node(...)` registration must use `recommendation_generation`, not `generate_recommendation`.
- **D-56-02:** Conditional edge path maps from `investigate` and `rag_context_build` must route the `recommendation_generation` route value to the active `recommendation_generation` node. The active route source for `route_after_recommendation` must also be `recommendation_generation`.
- **D-56-03:** Existing `src/agent/nodes/generate_recommendation.py` behavior may be reused only as an implementation compatibility layer if the plan records legacy surface, canonical owner, reason, trace projection, validation, and delete phase. It must not remain the active graph registration after Phase 56.
- **D-56-04:** `generate_recommendation` compatibility should be scoped narrowly to imports/tests/historical trace projection. Do not do a destructive repository-wide rename of every historical mention.

### RAG context fail-closed semantics
- **D-56-05:** `rag_context_build` status vocabulary must remain finite and machine-readable, aligned with `VerifiedEvidencePackageV1.status`: `not_required`, `verified`, `partial`, `no_evidence`, `unauthorized`, `stale`, `conflict`, `invalid_hash`, `invalid_scope`, and `build_error`.
- **D-56-06:** `route_after_rag_context` must fail closed to a safe terminal/clarification path for missing or unknown status and for unsafe evidence states. `partial` may proceed only for low-risk answer-only/policy-QA style generation, not action-bound or high-risk flows.
- **D-56-07:** Unauthorized, stale, conflict, invalid hash, invalid scope, no evidence, malformed package, and build error states must not be promotable to `evidence_refs`, approval snapshots, risk lowering, approval, or action draft authority.

### Claim verification hard gate
- **D-56-08:** Every material claim, user-visible policy/business/action claim, or proposed action from `recommendation_generation` must pass through `claim_verify`.
- **D-56-09:** `recommendation_generation` can write draft text, candidate `material_claims`, candidate `proposed_action`, `missing_info`, and citation-validated `evidence_refs`. It cannot mark evidence verified, write `claim_verification_bundle`, clear `blocked_claims`, or decide that a claim is safe.
- **D-56-10:** `route_after_claim_verify` may proceed toward the current Phase 57-owned risk node only when the canonical claim bundle allows it: `route == "continue"`, `overall_status in {"verified", "not_required"}`, no blocked claims, and action claims explicitly allow action recommendation when present.
- **D-56-11:** Existing legacy projection fields such as `verification_route`, `verifier_status`, and `verifier_reason_codes` can remain compatibility outputs, but they cannot override or bypass `claim_verification_bundle`.

### Final wording and safe termination
- **D-56-12:** Safe terminal wording must distinguish insufficient evidence, unsafe/invalid RAG context, unsupported claim, manual review, and verifier error where those states are available. User-visible final text must not imply verified policy/business/action authority when gates failed.
- **D-56-13:** `final_response` should consume only safe projections from `verified_evidence_package` and `claim_verification_bundle`; debug/verifier projections must not leak.

### Planning and validation shape
- **D-56-14:** Planning should be split into multiple ordered plans, not one large plan. Expected boundaries are: canonical node/wrapper contract; active graph/router/baseline cutover; RAG/claim status fail-closed alignment; vocabulary/API/docs/debt/validation closeout.
- **D-56-15:** Phase 56 must preserve Phase 55 memory authority boundaries and Phase 57 risk/approval scope. Tests should prove `assess_risk_and_approval` remains the Phase 57 active legacy row until Phase 57.
- **D-56-16:** All verification commands must use MOCA-approved entrypoints such as `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`; bare `pytest` and bare `python -m pytest` are invalid.

### the agent's Discretion
- Exact wrapper/module naming is left to the planner as long as active graph registration and trace projection are canonical.
- Exact low-risk `partial` status predicate may be refined from current code, but it must stay deterministic and action-bound flows must fail closed.
- Exact safe final-response copy is implementation discretion as long as it truthfully reflects gate outcomes.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and migration charter
- `.planning/ROADMAP.md` — Phase 56 goal, dependencies, and CAGM-07 success criteria.
- `.planning/REQUIREMENTS.md` — CAGM-07 requirement text and pending status.
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` — source hierarchy, target 15-node graph, temporary compatibility policy, authority matrix, validation matrix, and required phase order.

### Target graph and RAG/claim contract
- `docs/contract-spec.md` §9.1, §9.4, §9.5 — target graph node list, node authority table, and router contract table for `rag_context_build`, `recommendation_generation`, and `claim_verify`.
- `docs/contract-spec.md` §13 state registry around `rag_context_status`, `verified_evidence_package`, `material_claims`, `claim_verification_bundle`, `blocked_claims`, and `safe_support_refs`.
- `docs/current-langgraph-architecture.md` — current source snapshot and Phase 56 compatibility row for active `generate_recommendation`.

### Prior phase handoff
- `.planning/phases/55-memory-context-load-cutover/55-VERIFICATION.md` — Phase 55 verified that Phase 56/57 active legacy rows remain intentionally open.
- `.planning/phases/55-memory-context-load-cutover/55-VALIDATION.md` — approved command style and final focused suite shape after Phase 55.
- `.planning/ARCHITECTURE-DEBT.md` — Phase 55 Plan 03 remaining risk: Phase 56 owns `generate_recommendation -> recommendation_generation`; Phase 57 owns `assess_risk_and_approval -> risk_gate`; Phase 58 owns final no-debt cleanup.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/agent/nodes/generate_recommendation.py` — existing generation implementation with verified package gating, citation membership validation, material claim creation, draft output, and legacy trace/llm output naming.
- `src/agent/nodes/rag_context_build.py` — existing deterministic verified evidence package builder that writes `rag_context_status`, `verified_evidence_package`, `citation_map`, and `evidence_map`.
- `src/agent/nodes/claim_verify.py` — existing ClaimVerifier node that writes `claim_verification_bundle`, `blocked_claims`, `safe_support_refs`, and compatibility verifier fields.
- `src/knowledge/schemas.py` and `src/knowledge/service.py` — strict DTOs and service methods backing `VerifiedEvidencePackageV1`, `MaterialClaimV1`, and `ClaimVerificationBundleV1`.

### Established Patterns
- Recent migration phases use canonical active nodes plus compatibility wrappers/trace projection with explicit reason codes and `DELETE_BY_PHASE_58` metadata.
- `src/agent/graph_vocabulary.py` is the current projection point for runtime vs compatibility alias semantics.
- `tests/architecture/graph_baseline.py` and `tests/architecture/test_canonical_graph_baseline.py` are the static source-of-truth tests for active graph node names, route maps, and remaining migration rows.
- `route_after_*` functions are deterministic, side-effect-free routers with allowlists and safe fallback behavior.

### Integration Points
- `src/agent/graph.py` currently registers `generate_recommendation` and maps `recommendation_generation` route values to that legacy destination.
- `src/agent/routing.py` already returns `recommendation_generation` from investigation/RAG routers and routes material claims/actions to `claim_verify`.
- `tests/agent/test_graph.py`, `tests/test_graph_routing.py`, `tests/agent/rag_context/test_routing.py`, `tests/knowledge/test_verified_evidence_package.py`, and `tests/knowledge/test_claim_verification_bundle.py` already cover major RAG/claim behavior and should be updated/extended rather than replaced.
- `src/agent/nodes/final_response.py`, `tests/test_trace_api.py`, and `tests/test_agent_runs_api.py` project gate outputs to user/API surfaces and need regression coverage for truthful fail-closed wording/projection.

</code_context>

<specifics>
## Specific Ideas

- Auto discussion selected conservative defaults: canonical active graph identity first, fail-closed evidence/claim semantics second, compatibility ledger/docs third.
- No new product capability was added. This is a backend architecture/routing/safety alignment phase.

</specifics>

<deferred>
## Deferred Ideas

- `assess_risk_and_approval -> risk_gate` active graph rename and approval/risk responsibility split remain Phase 57 scope.
- Final deletion of compatibility aliases/wrappers/historical display rows remains Phase 58 scope.

</deferred>

---

*Phase: 56-recommendation-generation-and-rag-claim-status-alignment*
*Context gathered: 2026-07-07*
