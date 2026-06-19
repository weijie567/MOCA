# Phase 22: RAG Context Builder + Hallucination Control - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 22 builds the shared RAG reasoning kernel between retrieval and answer/action reasoning. It consumes already-retrieved `EvidenceRefV1` candidates, current Tool System business fact refs, trusted tenant/run/thread context, and risk/conflict hints; it then produces prompt-safe context, typed material claims, claim verification outcomes, deterministic safety routing, and hallucination-control acceptance gates.

This phase must not change Phase 20 dense/sparse/fuzzy/RRF ranking semantics, must not implement Phase 23 query rewrite/reranking, must not change `EvidenceRefV1` identity, must not turn source-block/OCR/provenance metadata into policy evidence, must not treat memory as authority, and must not implement Phase 17 external execution.

</domain>

<decisions>
## Implementation Decisions

### ContextBuilder boundary and outputs

- **D-01:** Add or extract a dedicated RAG reasoning context builder instead of expanding the existing generic `src/agent/context/ContextAssembler`. `ContextAssembler` remains the prompt-safe block assembler; the Phase 22 kernel owns evidence re-fetch, evidence validation, citation mapping, risk labels, exclusion reasons, and verifier-ready projections.
- **D-02:** The builder consumes candidate `EvidenceRefV1` values, current `BusinessFactRefV1` / safe `ToolResultV2` refs, trusted context (`tenant_id`, `run_id`, `thread_id`, `effective_at`, scope), and risk/conflict hints. It must not accept user- or model-authored authority refs as trusted input.
- **D-03:** The output should be a `RagContextBundle`, `ReasoningContext`, or equivalent stable DTO with separate prompt, verifier, debug/trace, and final-response projections. Prompt projections may include bounded snippets, citation IDs, display labels, and prompt-safe risk labels only.
- **D-04:** The bundle must include a stable citation map, included/truncated/excluded evidence trace, deterministic token/character budget trace, evidence risk labels, and exclusion reason codes. Protected citation metadata cannot be dropped by budget trimming.
- **D-05:** Evidence validation must re-fetch canonical content through `PolicyKnowledgeService`, reject tenant/scope/hash/freshness/latest-version invalid evidence, deduplicate duplicate keys, and record every exclusion. Latest/current policy version validity is a visible acceptance point, not just effective-date filtering.
- **D-06:** Source-block/OCR/provenance data may be used to derive prompt-safe labels such as `ocr_low_confidence`, `provenance_available`, or `source_locator_available`, but raw source-block IDs, bbox/table internals, raw OCR metadata, parser dumps, and provenance traces must stay out of ordinary prompts, final answers, memory, replay payloads, business facts, and action snapshots.

### MaterialClaim and authority binding

- **D-07:** MVP `MaterialClaim` supports exactly the three required authority classes: `policy_claim`, `business_fact_claim`, and `action_recommendation_claim`. Granular policy subtypes such as rule/exception/threshold/deadline remain Phase 22 stretch unless they are purely optional labels layered on top of the three authority classes.
- **D-08:** Every material claim must carry a stable `claim_id`, `claim_text`, `authority_class`, source node, risk level or risk hints, cited policy evidence IDs when applicable, business fact refs when applicable, dependency claim IDs when applicable, and verifier status once checked.
- **D-09:** A `policy_claim` is supportable only by current allowed evidence from the active context bundle. Citation membership is necessary but not sufficient; semantic or lexical support is tracked separately.
- **D-10:** A `business_fact_claim` is supportable only by current Tool System authority through `BusinessFactRefV1`, safe `ToolResultV2` refs, or equivalent existing business fact authority from the same trusted context. Policy evidence, memory, case memory, prior summaries, and model knowledge cannot satisfy it.
- **D-11:** An `action_recommendation_claim` must depend on supported policy claim(s) and supported current business fact claim(s). Passing claim verification never bypasses risk, approval, action draft, or action safety snapshot boundaries.
- **D-12:** Claim dependency mapping should extend the existing `claim_dependency_map` concept instead of inventing an unrelated dependency model. Permission-denied or missing-resource outcomes must block only dependent claims when dependencies can be verified; unverifiable dependencies fail closed.

### Verifier levels and deterministic routing

- **D-13:** Level 1 deterministic gates always run before a claim can be treated as supported. They include bundle membership, tenant/scope, duplicate-key, `text_hash`, freshness/effective-at, latest/current policy version, authority-source compatibility, and required business fact authority checks.
- **D-14:** Level 2 is the ordinary low-cost support check for material claims. It should be deterministic or near-deterministic lexical/span support, with typed outcomes such as `supported`, `unsupported`, `insufficient`, `ambiguous`, and `needs_semantic_review`.
- **D-15:** Level 3 semantic support runs only for high-risk, action recommendation, conflict, stale, OCR-low-confidence, Level 2 ambiguous, or manual-review-sensitive cases. It is not always-on for low-risk FAQ/policy QA.
- **D-16:** Initial Level 3 budget defaults for planning: max 6 claims per run, max 3 evidence snippets per claim, max 12,000 verifier input characters per run, 15 second timeout, 0 semantic-provider retries after a provider/malformed-output failure, and explicit verifier config versioning. Planner may tune these only if tests or code constraints justify a different value.
- **D-17:** Non-allow outcomes route deterministically. `unsupported`, missing citation, or cited-but-unsupported policy claims produce a `regenerate_route` outcome if a bounded regeneration attempt is separately accepted; otherwise they render insufficient/refusal. `conflicting`, stale high-risk, OCR-low-confidence high-risk, semantic ambiguous, Level 3 timeout, provider error, or malformed verifier output route to manual review for action/high-risk paths. Unauthorized, scope-invalid, hash-mismatched, or latest-version-invalid evidence is excluded and cannot support claims. `business_fact_missing` routes to clarification/insufficient evidence and blocks action recommendations.
- **D-18:** Any non-allow verification outcome must prevent proposed actions, approval requests, action drafts, and `ActionSafetySnapshot` evidence. The model never chooses the safety route.

### Acceptance gate and metrics

- **D-19:** Blocking acceptance requires 100% pass on named safety golden cases for unsupported claims, cited-but-unsupported claims, missing citations, stale/conflicting evidence, unauthorized/hash-mismatched evidence, OCR-low-confidence traps, business-fact hallucination, memory/evidence/action authority separation, and action recommendations missing required support.
- **D-20:** Leakage tolerance is zero. Raw tool payloads, retrieval debug fields, verifier prompts/traces, source-block/OCR raw metadata, raw provenance, private reasoning, and unbounded policy text must not enter ordinary prompts, final responses, memory, replay, action snapshots, or user-facing answers.
- **D-21:** Reported metrics must include claim support accuracy, citation support accuracy, refusal/manual-review routing accuracy, unsafe answer rate, business-data hallucination rate, leakage count, Level 3 trigger rate, timeout rate, and fail-closed rate. Blocking defaults: unsafe answer rate 0, business-data hallucination rate 0, leakage count 0, fail-closed behavior 100% for verifier timeout/provider/malformed failures, and at least 95% claim/citation support accuracy on non-safety aggregate evals.
- **D-22:** Default automated tests should not require live external model calls. Semantic verifier behavior must be covered by deterministic fakes/mocks in unit and integration tests, with any live provider evaluation treated as optional or separately gated.

### the agent's Discretion

- Exact module/package names, DTO class names, enum literal spelling, and file split are left to planner/executor as long as the boundaries above hold.
- Exact Level 2 lexical/span support algorithm is planner discretion, but it must produce typed outcomes and must not be confused with retrieval ranking.
- Exact prompt wording and final-response templates are planner discretion, but must preserve the routing semantics and leakage boundaries.
- Exact eval fixture filenames and command grouping are planner discretion, as long as the blocking coverage in D-19 through D-22 is present.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements

- `.planning/ROADMAP.md` - Phase 22 goal, success criteria, suggested plan slices, acceptance notes, and hard boundaries.
- `.planning/REQUIREMENTS.md` - v1.5 CTX/CLM/VER/RTE/BND/EVAL requirements and named stretch/future-owner exclusions.
- `.planning/PROJECT.md` - Current milestone value, active constraints, shipped milestone boundaries, and key decisions.
- `.planning/STATE.md` - Current Phase 22 readiness notes and blockers/concerns.

### Normative contracts

- `docs/contract-spec.md` section 8.3 - Canonical `EvidenceRefV1`, text hash, effective/freshness rules, citation membership vs semantic support.
- `docs/contract-spec.md` section 8.4 and section 12.5 - Business Tool / `ToolResultV2` / `BusinessFactRefV1` authority boundaries.
- `docs/contract-spec.md` section 9.4, section 9.5, and section 10.1 - Agent node/router/state contracts for `investigate`, `recommendation_generation`, `risk_gate`, `retrieved_evidence`, `evidence_refs`, and `claim_dependency_map`.
- `docs/contract-spec.md` section 13 - Memory is contextual assistance only and cannot produce policy evidence, current business fact authority, approval/action authority, replay truth, or audit truth.

### RAG target architecture

- `docs/rag-architecture-spec.md` section 12 - Hallucination-control model, context layer, generation layer, verifier principles, and business-data hallucination boundary.
- `docs/rag-architecture-spec.md` section 15-section 17 - RAG-3 target scope, target-state acceptance criteria, and key decisions.

### Shipped milestone boundaries

- `.planning/milestones/v1.3-ROADMAP.md` - Phase 20 PostgreSQL hybrid retrieval boundaries, RRF semantics, and Phase 22 deferrals.
- `.planning/milestones/v1.4-ROADMAP.md` - Phase 21 parser/OCR/source-block provenance boundaries and Phase 22 deferrals.

### Executable boundary references

- `tests/knowledge/test_phase21_boundaries.py` - Current static and behavioral guards proving Phase 21 did not introduce MaterialClaim/semantic verifier/reranker scope and that provenance fields do not enter evidence identity or ordinary prompt/snapshot surfaces.
- `tests/agent/context/test_assembler.py` and `tests/agent/context/test_budget.py` - Current prompt-safe context assembly and budget behavior that Phase 22 must reuse or preserve.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `src/knowledge/schemas.py` owns canonical `EvidenceRefV1`, `KnowledgeSearchRequest`, `KnowledgeSearchResult`, and membership validation result schemas.
- `src/knowledge/service.py` already exposes `get_verified_evidence_contents` and `get_verified_evidence_provenance`, which are the natural re-fetch/hash/provenance lookup base for ContextBuilder.
- `src/repositories/policy_chunk_repo.py` supports content lookup and provenance lookup by `(doc_key, chunk_id)` under tenant scope.
- `src/knowledge/provenance.py` provides safe internal provenance DTOs and allowlisted OCR/parser/source locator projection.
- `src/tools/contracts.py` owns `ToolCallContext`, `ToolResultV2`, `BusinessFactRefV1`, and prompt-safe tool result summaries.
- `src/agent/context/` already has prompt-safe projectors and token/character budget behavior; reuse this as the final prompt assembly layer, not as the evidence verifier.
- `src/knowledge/citation.py` currently provides membership-only citation validation.

### Established Patterns

- Pydantic models define cross-layer contracts; adapter-local shapes must be validated before leaving their boundary.
- Routers are deterministic and side-effect free; safety routing should be code-owned, not model-owned.
- Existing code favors fail-closed behavior when approval/action snapshot binding cannot be verified.
- Prompt-safe projectors strip raw payloads, parser/OCR internals, hashes, authority bodies, and debug traces.
- Retrieval debug/ranking fields can exist for eval/debug, but must not mutate `EvidenceRefV1` or ordinary prompt/final response identity.

### Integration Points

- Current flow is `investigate -> generate_recommendation -> assess_risk_and_approval -> approval_gate/action_draft -> final_response`.
- `investigate` accumulates `business_context`, `policy_evidence`, `retrieved_evidence`, `tool_results`, and `claim_dependency_map`.
- `generate_recommendation` currently re-fetches evidence content, builds snippets, asks the LLM for a structured recommendation, and runs membership validation. Phase 22 should centralize this behavior in the shared kernel.
- `assess_risk_and_approval` builds proposed actions and action safety snapshots from validated evidence refs; Phase 22 verification must gate this path before actions or approvals are created.
- `final_response` already has deterministic branches for insufficient evidence, retrieval error, citation invalid, and completed recommendations; Phase 22 should add safe language for verifier/routing outcomes without leaking debug details.

</code_context>

<specifics>
## Specific Ideas

- The discussion UI was unavailable in the current Codex Default mode, so all four recommended gray areas were selected via the workflow fallback and decisions above were recorded as agent recommended defaults.
- Treat `regenerate_route` as a route enum/action in scope. Do not implement an automatic regeneration attempt unless Phase 22 stretch is separately accepted.
- Keep semantic verifier coverage deterministic in default tests by using fake verifier providers; live provider evaluation can be optional.

</specifics>

<deferred>
## Deferred Ideas

- Bounded automatic regeneration attempt after support failure - Phase 22 stretch only.
- Persisted claim dependency map for replay/eval summaries beyond existing state-level dependencies - Phase 22 stretch only if low cost and redaction boundaries remain clear.
- Maintainer-facing verifier trace report or CLI - Phase 22 stretch only.
- Granular policy claim subtypes beyond the three required authority classes - Phase 22 stretch only.
- Query rewrite, reranking, cross-encoder/external rerank APIs, retrieval ablation, and retrieval latency tuning - Phase 23.
- Real external action execution, outbox, reconciliation, compensation dispatch, and external idempotency workers - Phase 17.
- External `SearchBackend`, Vespa/OpenSearch, or new vector database service - Phase RAG-5.
- Policy source upload/review/lifecycle UI and source document viewer - Policy Source Operations.

</deferred>

---

*Phase: 22-rag-context-builder-hallucination-control*
*Context gathered: 2026-06-19*
