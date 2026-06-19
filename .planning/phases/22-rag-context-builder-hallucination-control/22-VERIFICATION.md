---
phase: 22-rag-context-builder-hallucination-control
verified: 2026-06-19T15:49:26Z
status: passed
score: "5/5 roadmap must-haves verified; 19/19 plan truths covered"
overrides_applied: 0
---

# Phase 22: RAG Context Builder + Hallucination Control Verification Report

**Phase Goal:** Users and downstream agent nodes can rely on answers and action recommendations being grounded only in current, authorized, hash-valid, semantically supported policy evidence and current Tool System business facts, with unsupported or unsafe outcomes routed to regenerate-route, refusal/insufficient-evidence, or manual review before any action boundary can proceed.
**Verified:** 2026-06-19T15:49:26Z
**Status:** passed
**Re-verification:** Yes - post-final-deep-review re-verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | System builds a prompt-safe `RagContextBundle` from candidate evidence refs and business refs, preserving citation maps, dedupe/merge traceability, risk labels, exclusion reasons, and budget traces while rejecting invalid evidence. | VERIFIED | `ContextBuilder.build()` validates tenant/scope/content, calls canonical evidence validation, dedupes, applies item and cumulative prompt budgets, builds citation maps, and emits safe prompt/final/memory/replay/action surfaces in `src/agent/rag_context/builder.py:66`; service-level latest/hash/freshness/scope checks are in `src/knowledge/service.py:281`. |
| 2 | System represents policy, business fact, and action recommendation conclusions as typed `MaterialClaim` records and verifies each claim against the correct authority source. | VERIFIED | `MaterialClaimAuthorityClass` and strict `MaterialClaim` DTOs are in `src/agent/rag_context/schemas.py:14`; `MaterialClaimVerifier.verify_claim()` separates policy, business fact, and action recommendation authority in `src/agent/rag_context/verifier.py:262`; tests cover membership-vs-support and authority separation. |
| 3 | System deterministically maps unsupported, insufficient, conflicting, stale, unauthorized, scope-invalid, hash-mismatched, OCR-low-confidence, business-fact-missing, and manual-review-needed outcomes to backend routes. | VERIFIED | Backend-only route enum/decision map is in `src/agent/rag_context/routing.py:12` and `src/agent/rag_context/routing.py:92`; decisions set `selected_by=backend` and `model_selected=false`; route tests and eval cover all expected route classes. |
| 4 | System prevents non-allow verification outcomes from creating proposed actions, approval requests, action drafts, or `ActionSafetySnapshot` evidence while preserving existing approval/action boundaries when support passes. | VERIFIED | `generate_recommendation` clears validated refs and rewrites drafts for non-allow routes at `src/agent/nodes/generate_recommendation.py:245`; graph routing exits non-allow recommendations to final response in `src/agent/routing.py:157`; `assess_risk_and_approval` clears proposed action/approval/action draft/snapshot state at `src/agent/nodes/assess_risk_and_approval.py:444`; `action_draft` rejects non-allow state with `VERIFIER_NOT_ALLOW` at `src/agent/nodes/action_draft.py:200`. |
| 5 | System passes blocking hallucination-control acceptance gates for claim support, citation support, routing, business-data hallucination, leakage, Level 3 trigger/timeout behavior, and fail-closed outcomes. | VERIFIED | `scripts/eval_phase22_hallucination.py --fail-thresholds` passed with 24 cases, no failed cases, all blocking thresholds met. Metrics include claim/citation/routing accuracy 1.0, unsafe answer rate 0.0, business hallucination rate 0.0, leakage count 0, fail-closed rate 1.0. |

**Score:** 5/5 roadmap truths verified. All 19 plan-frontmatter truths were also covered through the required artifacts, key links, tests, and spot-checks below.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/agent/rag_context/schemas.py` | Strict DTOs for bundle, claim, citation, budget, and route-safe projections | VERIFIED | DTOs are substantive and imported by builder/verifier/claims. `EvidenceRefV1` identity remains separate. |
| `src/agent/rag_context/builder.py` | ContextBuilder with canonical re-fetch, validation, dedupe/merge, budgeting, safe projections | VERIFIED | Builds `RagContextBundle`; rejects tenant/hash/latest/freshness/scope invalid evidence; enforces cumulative prompt budget. |
| `src/knowledge/service.py` and `src/repositories/policy_chunk_repo.py` | Canonical current evidence validation and tenant-scoped row lookup | VERIFIED | `get_verified_evidence_details()` checks tenant, duplicate key, content, hash, latest version, freshness, merchant/doc/risk scope; repository fetches current doc/chunk metadata. |
| `src/agent/rag_context/claims.py` and `src/agent/rag_context/verifier.py` | MaterialClaim normalization, dependency map, Level 1/2/3 verification contracts | VERIFIED | Business facts require `BusinessFactRefV1`/safe tool refs; policy claims require active bundle evidence; action claims require policy and business dependencies. |
| `src/agent/rag_context/routing.py` | Deterministic route map | VERIFIED | Covers allow, regenerate-route, insufficient evidence, refuse, and manual review; route permissions are false unless route is allow. |
| `src/agent/nodes/generate_recommendation.py` | Shared ContextBuilder/verifier integration before recommendation advances | VERIFIED | Builds bundle from retrieved evidence/business refs, verifies draft-derived material claims, aggregates non-allow claim dependencies fail-closed, and applies backend route to state/draft. Review fixes confirmed draft claim text no longer self-verifies evidence text and missing-session compatibility no longer returns `allow`. |
| `src/agent/graph.py`, `src/agent/routing.py`, `src/agent/nodes/assess_risk_and_approval.py`, `src/agent/nodes/action_draft.py`, `src/agent/nodes/final_response.py` | Graph/action/final-response hardening | VERIFIED | Non-allow routes skip risk/action path, explicitly clear stale action/snapshot bindings, reject action drafts, and render safe user-facing final responses. |
| `src/agent/rag_context/metrics.py`, `scripts/eval_phase22_hallucination.py`, `evaluation/golden/phase22_hallucination_cases.jsonl` | Blocking hallucination eval and metrics | VERIFIED | 24 golden cases; five marked `production_verifier` cases exercise ContextBuilder + MaterialClaimVerifier + route map, including unsupported claim text, hash/latest/freshness invalid evidence, and OCR low-confidence routing; thresholds are enforced. |
| `tests/agent/rag_context/*`, `tests/agent/test_phase22_*`, `tests/knowledge/test_phase22_evidence_validation.py`, `tests/knowledge/test_phase21_boundaries.py` | Unit/integration/boundary/leakage coverage | VERIFIED | Tests cover ContextBuilder, budgeting, claim authority, verifier tiers, semantic fail-closed behavior, routing, recommendation integration, action boundaries, final response, evidence validation, and static boundaries. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `src/agent/rag_context/builder.py` | `src/knowledge/service.py` | `get_verified_evidence_details()` canonical validation | WIRED | Builder uses service-level current row validation when available. |
| `src/knowledge/service.py` | `src/repositories/policy_chunk_repo.py` | `get_canonical_evidence_rows_by_keys()` | WIRED | Service fetches tenant-scoped current policy document/chunk metadata. |
| `src/agent/rag_context/verifier.py` | `src/agent/rag_context/schemas.py` / `src/tools/contracts.py` | `MaterialClaim`, `BusinessFactRefV1`, `ToolResultV2` | WIRED | Authority verification consumes typed policy and business fact contracts. |
| `src/agent/nodes/generate_recommendation.py` | `ContextBuilder` / `MaterialClaimVerifier` / `determine_verification_route` | Shared RAG reasoning kernel | WIRED | Recommendation generation builds the shared bundle, verifies material claims, and stores route/status/metrics on state. |
| `src/agent/graph.py` | `src/agent/routing.py` | `route_after_recommendation` conditional edge | WIRED | Non-allow verifier routes go to final response instead of action assessment. |
| `scripts/eval_phase22_hallucination.py` | `src/agent/rag_context/metrics.py` and golden JSONL | Dataset loader and threshold checks | WIRED | Eval loads the golden set, delegates per-case evaluation, computes metrics, and exits nonzero on threshold failure. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `ContextBuilder` | `citation_map`, `prompt_context`, `verifier_context`, `budget_trace` | `PolicyKnowledgeService.get_verified_evidence_details()` or canonical rows/content lookup | Yes | FLOWING - canonical DB/service rows are validated and projected; invalid rows become typed exclusions. |
| `MaterialClaimVerifier` | `MaterialClaimVerificationResult` | Active `RagContextBundle.citation_map` / `verifier_context.business_fact_refs` / tool results | Yes | FLOWING - policy support is checked against active evidence snippets; business support is checked against current business refs. |
| `generate_recommendation` | `rag_verification`, `verification_route`, `material_claims` | LLM draft + shared ContextBuilder/verifier output | Yes | FLOWING - draft text is converted to typed claims, verified, routed, and applied to the recommendation draft/state. |
| Action/final boundary nodes | `proposed_action`, `approval_result`, `action_draft`, `final_response` | `rag_verification.route` and `verification_route` | Yes | FLOWING - non-allow route state is consumed by graph, risk, action draft, and final response nodes. |
| Hallucination eval | `metrics`, `failed_cases`, `threshold_failures` | Golden JSONL + metrics evaluator | Yes | FLOWING - eval uses 24 JSONL cases and includes production-verifier path cases for unsupported claims, canonical invalid-evidence filtering, and OCR low-confidence routing. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Blocking hallucination eval passes thresholds | `uv run python scripts/eval_phase22_hallucination.py --dataset evaluation/golden/phase22_hallucination_cases.jsonl --fail-thresholds` | `status: pass`, `case_count: 24`, `failed_cases: []`, `threshold_failures: {}` | PASS |
| Review-fix regressions pass | `uv run pytest tests/agent/test_phase22_recommendation_integration.py::test_valid_citation_membership_does_not_allow_unsupported_action_recommendation tests/agent/rag_context/test_budgeting.py::test_prompt_budget_caps_cumulative_citation_snippet_text -q --tb=short` | `2 passed, 1 warning` | PASS |
| Second deep-review regressions pass | `uv run pytest tests/agent/test_phase22_recommendation_integration.py::test_supported_policy_claim_does_not_mask_failed_action_dependency tests/agent/test_phase22_recommendation_integration.py::test_missing_session_context_builder_fails_closed_instead_of_allowing_membership_only tests/agent/rag_context/test_context_builder.py::test_wrong_tenant_duplicate_cannot_discard_valid_tenant_evidence -q --tb=short` | `3 passed, 1 warning` | PASS |
| Action/final non-allow boundaries pass | `uv run pytest tests/agent/test_phase22_action_boundary.py::test_action_draft_node_refuses_even_trusted_approval_when_verifier_route_is_non_allow tests/agent/test_phase22_final_response.py::test_final_response_does_not_turn_manual_review_verification_into_action_success -q --tb=short` | `2 passed, 1 warning` | PASS |
| Golden dataset includes production verifier path and all route classes | Local JSONL inspection | `24`, `production_verifier=True`, routes: allow, insufficient_evidence, manual_review, refuse, regenerate_route | PASS |
| `EvidenceRefV1` identity has no Phase 22 authority/debug fields | Local model field inspection | `MaterialClaim`, source block, OCR, provenance, business fact, verifier fields all absent | PASS |

Final gates after final Claude deep-review fixes passed: full non-integration pytest (`1228 passed, 1 skipped`), `ruff check .`, `ruff format --check .`, and Phase 22 eval (`24` cases, no failed cases). Focused gates also passed: Phase 22 related suite (`119 passed`) and recommendation/action regressions within that suite.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| CTX-01 | 22-01/03/06 | Build prompt-safe shared context after retrieval and before reasoning | SATISFIED | `ContextBuilder.build()` produces `RagContextBundle`; recommendation generation consumes it before verifier/routing. |
| CTX-02 | 22-02/03/06 | Canonical re-fetch and invalid evidence exclusion | SATISFIED | Service and builder reject tenant, scope, duplicate-key, content, hash, freshness, and latest-version failures. |
| CTX-03 | 22-01/03/06 | Stable prompt-safe citation map | SATISFIED | `CitationMapEntry` preserves `EvidenceRefV1`; prompt citations expose bounded snippets, labels, and safe metadata. |
| CTX-04 | 22-01/03/06 | Dedupe repeated evidence and merge adjacent same-doc evidence | SATISFIED | `_dedupe_candidates()` and `_merge_adjacent()` retain traceability through exclusions and merged IDs. |
| CTX-05 | 22-01/03/06 | Deterministic evidence budget with included/truncated/excluded reasons | SATISFIED | `RagContextBudgetTrace` records included/truncated/excluded; cumulative prompt budget regression test passes. |
| CTX-06 | 22-02/03/06 | Risk/freshness/OCR/provenance labels without identity leakage | SATISFIED | Safe risk labels are projected; raw source-block/OCR/provenance data stays out of ordinary surfaces. |
| CLM-01 | 22-01/04/06 | Typed material claim records | SATISFIED | `MaterialClaimAuthorityClass` defines policy, business fact, and action recommendation claims. |
| CLM-02 | 22-01/04/06 | Policy claims require active bundle evidence support | SATISFIED | Level 1 membership plus Level 2 semantic support required; membership-only unsupported claim test passes. |
| CLM-03 | 22-01/04/06 | Business claims require current Tool System support | SATISFIED | Verifier requires `BusinessFactRefV1` from context/tool results. |
| CLM-04 | 22-01/04/05/06 | Action recommendation claims require policy and business support and cannot bypass boundaries | SATISFIED | Action claims require dependency results and business refs; non-allow graph/action boundaries pass targeted tests. |
| CLM-05 | 22-01/04/06 | Memory/provenance/model knowledge cannot satisfy authority | SATISFIED | Authority tests prove memory/model/provenance reason codes and non-supported outcomes. |
| VER-01 | 22-01/03/04/06 | Level 1 gates for membership, tenant/scope, duplicate/hash/freshness/latest/authority | SATISFIED | Builder/service evidence gates and claim Level 1 gates are implemented and tested. |
| VER-02 | 22-01/04/06 | Citation membership distinct from semantic support | SATISFIED | `check_level2_support()` can return unsupported despite membership; production-verifier golden case covers this. |
| VER-03 | 22-01/04/06 | Low-cost Level 2 lexical/span support outcomes | SATISFIED | Level 2 returns supported, unsupported, insufficient, ambiguous, and needs-semantic-review. |
| VER-04 | 22-01/04/06 | Level 3 only for configured high-risk/action/conflict/stale/OCR/ambiguous cases | SATISFIED | `should_run_level3_semantic_verification()` and eval trigger metrics cover configured triggers. |
| VER-05 | 22-01/04/06 | Level 3 budgets and fail-closed timeout/error/malformed behavior | SATISFIED | `SemanticSupportVerifier` enforces claim/evidence/input/timeout/config budgets and fail-closed outcomes; targeted tests pass. |
| VER-06 | 22-02/04/05/06 | Redacted verifier status/metrics only; no prompt/debug/private leakage | SATISFIED | Leakage tests and final response tests keep raw verifier/provenance/private data out of user-facing surfaces. |
| RTE-01 | 22-01/05/06 | Backend deterministic route selection | SATISFIED | `determine_verification_route()` owns routing; route payload marks backend-selected and not model-selected. |
| RTE-02 | 22-01/05/06 | Explicit behavior for unsupported/insufficient/conflict/stale/unauthorized/scope/hash/OCR/business/manual states | SATISFIED | Route map and 24-case eval cover all required route classes. |
| RTE-03 | 22-02/05/06 | Recommendation generation uses shared ContextBuilder/verifier kernel | SATISFIED | Integration tests spy on `ContextBuilder`/`MaterialClaimVerifier`; node-local refetch is guarded. |
| RTE-04 | 22-02/05/06 | Non-allow outcomes block proposed actions/approvals/drafts/snapshot evidence | SATISFIED | Graph, risk, and action draft nodes all consume non-allow route state and targeted tests pass. |
| RTE-05 | 22-02/05/06 | Safe final responses for refusal/insufficient/conflict/stale/unauthorized/manual states | SATISFIED | Final response template returns safe Chinese wording and excludes internal codes/traces. |
| BND-01 | 22-02/03/06 | Preserve `EvidenceRefV1` identity | SATISFIED | `EvidenceRefV1` fields remain canonical; static field inspection and boundary tests pass. |
| BND-02 | 22-02/03/06 | Preserve existing retrieval/ranking; no query rewrite/rerank/backend scope expansion | SATISFIED | Phase boundary tests guard forbidden Phase 23/RAG-5 symbols; current v1.3 compatibility names remain at known sites. |
| BND-03 | 22-02/04/06 | Preserve Tool System authority for business facts | SATISFIED | `BusinessFactRefV1` cannot validate as `EvidenceRefV1`; verifier uses business refs separately. |
| BND-04 | 22-02/04/06 | Preserve memory as contextual assistance only | SATISFIED | Authority tests reject memory/model-supported policy/business/action dependencies. |
| BND-05 | 22-02/03/05/06 | Keep source-block/OCR/parser metadata internal except prompt-safe labels | SATISFIED | Leakage and boundary tests verify only safe labels are projected. |
| EVAL-01 | 22-02/06 | Golden cases for policy support/citation/stale/conflict/unauthorized/hash/OCR/insufficient | SATISFIED | Golden JSONL includes required categories and passes eval. |
| EVAL-02 | 22-02/06 | Golden cases for business/policy/memory/action authority separation | SATISFIED | Cases cover business-from-policy, policy-from-business, policy-from-memory, and action dependency failures. |
| EVAL-03 | 22-02/06 | Golden routing cases for unsupported/conflict/stale/unauthorized/hash/OCR/business missing | SATISFIED | Eval route accuracy is 1.0 for non-allow routing cases. |
| EVAL-04 | 22-02/06 | Leakage tests for prompts/final/memory/replay/action/eval reports | SATISFIED | Leakage tests and eval report redaction tests are present; eval leakage count is 0. |
| EVAL-05 | 22-02/06 | Blocking metrics and thresholds | SATISFIED | `DEFAULT_HALLUCINATION_THRESHOLDS` and eval output enforce claim/citation/routing/unsafe/business/leakage/fail-closed gates. |

No orphaned Phase 22 requirements were found in `.planning/REQUIREMENTS.md`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/eval_phase22_hallucination.py` | 8 | Header still describes a "future" adapter / Wave 0 missing implementation | Info | Documentation drift only. The implementation now imports `evaluate_hallucination_case`, the eval passes, and production-verifier cases `P22-HC-020` through `P22-HC-024` exercise the real verifier path. |

No blocker TODO/FIXME/placeholder implementations, orphaned core artifacts, or UI-flowing hardcoded empty data were found. Many empty-list/default matches are DTO defaults, test fixtures, or fail-closed initialization and were not classified as stubs.

### Human Verification Required

None. Phase 22 is backend/eval logic with deterministic local tests; no visual flow or external-service behavior is required for this phase verification.

### Gaps Summary

No blocking gaps found. Review findings from `22-REVIEW.md` and the Claude follow-up review were re-checked against code: draft-derived claim verification is present, cumulative prompt budgeting is enforced, failed action dependencies cannot aggregate to `allow`, missing-session recommendation verification fails closed, tenant-aware dedupe preserves valid tenant evidence, non-allow risk assessment clears stale snapshot bindings, builder exclusion reasons and OCR risk labels for cited evidence flow into recommendation routing, and the eval includes production-verifier golden paths for unsupported claims plus hash/latest/freshness invalid evidence and OCR low-confidence evidence.

Residual risks/test gaps:

- Most golden cases still use deterministic status inference; five cases (`P22-HC-020` through `P22-HC-024`) exercise ContextBuilder + MaterialClaimVerifier + route map. Future coverage can move more authority and action-dependency categories onto the production-verifier path if the eval is intended to become a stronger end-to-end oracle.
- Level 3 semantic provider behavior is verified with deterministic fake providers and local fail-closed tests, not a live provider. That matches the no-live-model Phase 22 gate, but live provider integration should be verified separately if enabled later.

---

_Verified: 2026-06-19T15:49:26Z_
_Verifier: Codex (gsd-verifier)_
