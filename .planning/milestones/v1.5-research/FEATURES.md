# Feature Research

**Domain:** Phase 22 RAG Context Builder and hallucination control for MOCA's evidence-backed merchant operations agent
**Researched:** 2026-06-19
**Confidence:** HIGH for MOCA scope, contracts, current-code gaps, and roadmap boundaries; MEDIUM for exact semantic-verifier model quality because Phase 22 should budget and evaluate it before relying on it for release gates.

## Feature Landscape

Phase 22 should add a reusable Reasoning Kernel between retrieval and recommendation/final/action reasoning. v1.3 already shipped PostgreSQL hybrid retrieval and v1.4 already shipped parser/OCR/source-block provenance. Phase 22 should not revisit those layers. Its product job is to take already-retrieved policy evidence, current business facts, trusted context, and risk/conflict hints, then produce a prompt-safe reasoning bundle plus claim-level verification results that determine whether the system may answer, regenerate, refuse, or route to manual review.

The current implementation has important foundations: `generate_recommendation` re-fetches evidence content through `PolicyKnowledgeService`, keeps policy text out of persisted state, bounds prompt evidence text, and runs citation membership validation before promoting refs to `evidence_refs`. The current tests also prove the key gap: a semantically unsupported claim can pass if it cites a present `EvidenceRefV1`. Phase 22 should close that gap without changing `EvidenceRefV1`, without adding query rewrite/reranking, and without weakening business-tool, memory, approval, or action boundaries.

Production behavior should be conservative: every material claim must be tied to the correct authority source, every failure must have deterministic routing, and every prompt should receive only a sanitized `RagContextBundle` / `ReasoningContext`, not raw retrieval debug data, OCR provenance blobs, source-block internals, or raw tool payloads.

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = Phase 22 does not satisfy "production evidence-backed agent."

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Reusable `ContextBuilder` contract | Evidence-backed answers need one shared assembly path rather than duplicated prompt snippets in `recommendation_generation`, `final_response`, and verifier code. | HIGH | Input candidate `EvidenceRefV1[]`, `BusinessFactRefV1[]` / safe `ToolResultV2` summaries, trusted tenant/run/thread context, risk/conflict hints, and token budget. Output a prompt-safe `RagContextBundle` or `ReasoningContext`. Test with direct service/unit coverage and node integration. |
| Canonical evidence content re-fetch | Retrieval refs alone are not enough for grounding; the generator/verifier must check current canonical chunk text. | MEDIUM | Move current `generate_recommendation` re-fetch behavior into `ContextBuilder`. Use `PolicyKnowledgeService`, not direct repository access from agent nodes. Missing session/content should produce exclusions or failure routing, not silent ungrounded answer generation. |
| Level 1 deterministic evidence gates | A production agent must never cite stale, unauthorized, wrong-tenant, wrong-scope, or hash-mismatched evidence. | HIGH | Always validate membership, tenant, scope/ACL where available, `text_hash`, freshness/effective-at, and required evidence type before any prompt or claim support check. Fail closed with typed reasons. |
| Prompt-safe citation map | The model needs stable citation handles, but protected metadata cannot be dropped by token pruning or mixed with debug internals. | MEDIUM | Emit `citation_id -> EvidenceRefV1 + safe snippet + display metadata` mapping. Keep full `EvidenceRefV1` fields needed for audit/action snapshot, but ordinary prompts should see only safe citation IDs, bounded text, title/section/page labels, and required policy version/hash hints. |
| Token budget trace with protected metadata | Context pruning must be testable and must not delete citation identity. | MEDIUM | Record included/excluded refs, char/token estimates, truncation reasons, protected metadata preservation, and final budget. Tests should assert metadata survives even when evidence text is truncated. |
| Deduplication and adjacent-chunk merge | Retrieval can return overlapping chunks; duplicated evidence wastes context and can overweight a single policy. | MEDIUM | Deduplicate by `evidence_id` and merge adjacent same-doc/same-version chunks only when hash-verified and citation metadata remains traceable. Do not change `EvidenceRefV1` identity. |
| Freshness, authority, conflict, and OCR-risk labels | v1.4 provenance and policy metadata only help if the reasoning layer exposes them as safety signals. | MEDIUM | Label current/stale, high/low authority, superseded/conflicting, OCR-low-confidence/degraded, and manual-review-needed evidence. If reliable source metadata is absent, label unknown rather than guessing. |
| `MaterialClaim` taxonomy | Claim support cannot be validated from one free-text answer. | HIGH | Use Phase 22 target types: `policy_claim`, `business_fact_claim`, and `action_recommendation_claim`. Optional subtypes may map to policy rule/exception, risk assessment, missing information, or conflict notice, but authority rules must remain simple. |
| Policy-claim authority binding | Policy conclusions must be backed by policy evidence, not tool facts, memory, or general model knowledge. | MEDIUM | Every `policy_claim` requires one or more allowed `EvidenceRefV1` citations that pass Level 1 and support checks. Missing or invalid refs route to regenerate/refuse/manual review. |
| Business-fact authority binding | Order/refund/ticket/account facts are Tool System facts, not RAG evidence. | MEDIUM | Every `business_fact_claim` requires typed `BusinessFactRefV1` / safe `ToolResultV2` provenance. Policy refs cannot satisfy business facts, and memory cannot satisfy current facts. |
| Action-recommendation support chain | A recommendation to refund, compensate, escalate, or draft an action needs both policy support and current business facts. | HIGH | Every `action_recommendation_claim` must bind to supporting policy claims and business fact claims. Passing support does not authorize execution; it only allows the deterministic risk/approval/action path to continue. |
| Level 2 lexical/span support checks | Ordinary claims need a low-cost guard stronger than membership validation. | MEDIUM | Add deterministic or rule-based lexical/span checks against cited snippets for normal-risk claims. This is support validation, not reranking. Expected outputs: supported, unsupported, insufficient, or needs Level 3. |
| Level 3 semantic support verifier | High-risk, conflicting, stale, OCR-low-confidence, or ambiguous claims need deeper support judgment. | HIGH | Trigger only on configured risk signals. Use explicit claim/evidence/token/latency budgets, deterministic preconditions, structured outputs, and fail-closed behavior. Do not make it an always-on reranker or retrieval scorer. |
| Deterministic failure routing | The model must not decide what to do when evidence fails. | HIGH | Route `unsupported`, `insufficient`, `conflicting`, `stale`, `unauthorized`, `hash_mismatched`, `scope_invalid`, and `manual_review_needed` through code-owned actions: regenerate with constraints, refuse/insufficient-evidence response, or manual review. |
| Safe final-response behavior | Final answers should expose supported conclusions and safe citations, not internal verifier/debug details. | MEDIUM | `final_response` should render refusal/manual-review/insufficient-evidence states deterministically. User text may mention evidence gaps/conflicts at product level, but not dump verifier traces or raw source metadata. |
| Integration with risk and approval gates | Hallucination control must block unsafe action drafts before `ActionSafetySnapshot` and approval logic. | HIGH | Unsupported or partially supported action recommendations must not produce `proposed_action`. Verified `evidence_refs` remain the only policy evidence input to snapshot building. |
| Hallucination-control eval suite | A production reasoning kernel needs regression coverage beyond Hit@5. | HIGH | Add golden cases for faithfulness, citation accuracy, refusal/manual-review routing, stale/conflicting evidence, OCR-low-confidence traps, business-data hallucination, memory/evidence/action authority separation, and action recommendations missing required support. |
| Prompt/debug boundary tests | Existing tests already guard raw payload leakage; Phase 22 must extend that to reasoning bundles and verifier traces. | MEDIUM | Assert ordinary prompts exclude raw tool data, source-block/OCR raw metadata, retrieval debug fields, verifier chain-of-thought, and full policy text outside bounded snippets. |

### Differentiators (Competitive Advantage)

Features that set Phase 22 apart from a basic "cite retrieved chunks" chatbot.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Reasoning Kernel as a first-class product boundary | Makes MOCA explainable as `Evidence -> MaterialClaim -> Answer/Refusal/ManualReview`, not as prompt engineering. | HIGH | Aligns with `docs/rag-architecture-spec.md` kernel split while keeping `EvidenceRefV1` canonical. |
| Claim-level authority graph | Shows which conclusion depends on which policy refs, business fact refs, and risk/action constraints. | HIGH | Useful for audit, UI highlighting, eval, and approval review. It also supports partial permission-denial behavior because denied refs can invalidate only dependent claims. |
| Risk-triggered semantic verification | Controls cost and latency while applying stronger verification where wrong answers have business impact. | HIGH | Level 3 should be mandatory for compensation, refund responsibility, appeals/unbans, compliance/risk policy, conflicts, stale evidence, and low-confidence OCR. |
| Deterministic regenerate/refuse/manual-review policy | Turns hallucination control into product behavior rather than best-effort scoring. | MEDIUM | Verifier outputs should select one of a small set of code-owned actions. This is stronger than returning a confidence score to the LLM. |
| Conflict-aware answer degradation | When current evidence conflicts, MOCA can explain the conflict or route to human review instead of silently choosing a side. | MEDIUM | This is especially valuable for policy changeovers and authority/supersedes ambiguity. |
| Action recommendation proof chain | Demonstrates enterprise agent maturity: supported recommendation is still separate from approval/action authorization. | HIGH | Prevents "verified answer" from being confused with "approved action." |
| Budget trace as a regression artifact | Makes prompt construction auditable and testable under tight context budgets. | MEDIUM | Enables tests for protected metadata, exclusion reasons, and deterministic context pruning. |
| Evaluation categories mapped to failure routes | Lets roadmap/release gates measure whether the system refused or escalated correctly, not just whether the answer was fluent. | MEDIUM | Add metrics for unsupported-claim catch rate, citation support accuracy, unsafe answer rate, manual-review precision, and partial-evidence overclaim rate. |
| Maintainer-facing verifier trace | Gives developers enough information to debug failures without leaking raw traces to user answers. | MEDIUM | Store low-sensitive summaries and refs. Keep chain-of-thought and raw model judge output out of ordinary API responses unless a later debug/admin contract approves it. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem useful but would make Phase 22 too broad or unsafe.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Query rewrite in `ContextBuilder` | It seems like a natural way to improve recall when context is weak. | It belongs to Phase 23 and changes retrieval behavior rather than reasoning over retrieved evidence. | Phase 22 may route insufficient evidence to refusal/regeneration/re-retrieval hooks, but must not implement query rewrite. |
| Model reranking, cross-encoder reranking, or external rerank API | It can improve evidence relevance. | It is Phase 23 scope and risks mixing support verification with relevance ranking. | Keep Level 2/3 as claim-support verification after retrieval; do not mutate RRF ranking semantics. |
| New search backend or `SearchBackend` abstraction | It can look more scalable. | It belongs to Phase RAG-5 and would distract from the Reasoning Kernel. | Continue consuming `PolicyKnowledgeService` outputs from the existing PostgreSQL hybrid backend. |
| Changing `EvidenceRefV1` identity | Richer provenance and support data can tempt schema changes. | It would break canonical policy evidence identity, action snapshots, replay, and shipped tests. | Keep `EvidenceRefV1` unchanged; attach runtime context, citation map, labels, and verification results outside identity. |
| Treating business facts as policy evidence | It simplifies citation logic. | It violates `ToolResultV2` / `BusinessFactRefV1` boundaries and can let policy retrieval hallucinate order/refund state. | Use separate claim types and require business fact refs for business claims. |
| Treating memory as evidence or action authority | Memory can contain helpful context. | MOCA memory is contextual assistance only; it cannot satisfy policy evidence, current business fact, approval, action, or replay truth. | Memory may inform wording or slot continuity only after current facts/evidence are fetched and verified. |
| Prompt-only hallucination guardrails | They are fast to add. | Prompts cannot enforce tenant/hash/freshness/support/routing rules. | Use code-owned Level 1 gates, structured `MaterialClaim`, verifier results, and deterministic routing. |
| Always-on heavy semantic verifier | It appears safer. | It adds cost/latency, can become opaque, and may mask deterministic failures that should fail closed first. | Run Level 3 only after Level 1 passes and risk/conflict/ambiguity triggers justify it. |
| Letting verifier scores authorize actions | A high support score can look like permission. | Support is not approval; approval/action boundaries remain authoritative. | Verified action recommendations must still pass risk gate, approval policy, `ActionSafetySnapshot`, and draft/execution guards. |
| Raw OCR/source-block/retrieval/debug data in prompts or user answers | It may help the model or reviewer. | It can leak internal data, bloat context, and weaken prompt safety. | Provide bounded snippets and safe citation labels; expose debug details only through a separate maintainer/debug path if later approved. |
| User-facing source upload/review UI | It feels useful after v1.4 provenance work. | It belongs to Policy Source Operations and is outside Phase 22. | Persist/consume labels and provenance needed for reasoning; defer UI workflow. |
| Real external execution or outbox/reconciliation | Strong recommendations invite direct action. | Phase 17 owns external execution; Phase 22 must not add side effects. | Continue durable draft / approval boundaries only. |

## Feature Dependencies

```
Existing v1.3 hybrid retrieval + v1.4 source-block provenance
    -> produces -> candidate EvidenceRefV1 values and metadata
        -> requires -> ContextBuilder input validation
            -> requires -> canonical content re-fetch + Level 1 gates
                -> produces -> prompt-safe RagContextBundle / ReasoningContext
                    -> feeds -> recommendation_generation structured MaterialClaim output
                        -> requires -> claim authority binding
                            -> feeds -> Level 2 lexical/span verifier
                                -> conditionally feeds -> Level 3 semantic verifier
                                    -> produces -> verification action
                                        -> routes -> allow / regenerate / refuse / manual_review

BusinessToolService ToolResultV2
    -> produces -> BusinessFactRefV1 and safe prompt summaries
        -> supports -> business_fact_claim
            -> required by -> action_recommendation_claim

Verified policy_claim + verified business_fact_claim
    -> required by -> action_recommendation_claim
        -> if supported -> risk_gate / approval_gate / action_draft boundary
        -> if unsupported -> no proposed_action

Memory context
    -> may assist -> wording / slot continuity
    -> must not satisfy -> policy_claim / business_fact_claim / action_recommendation_claim

Verifier failure reasons
    -> drive -> deterministic final_response / regenerate / manual_review behavior
    -> feed -> hallucination-control eval
```

### Dependency Notes

- **`ContextBuilder` depends on existing retrieval, not vice versa:** It consumes `EvidenceRefV1` candidates produced by `PolicyKnowledgeService`; it must not rewrite queries, change ranking, or call a new backend.
- **Level 1 gates precede prompts and semantic checks:** Scope/hash/freshness failures are deterministic safety failures. They should not be handed to a model judge.
- **`MaterialClaim` depends on a prompt-safe context bundle:** The generator should cite only allowed citation IDs from the bundle and should not invent refs from raw retrieval payloads.
- **Level 2 depends on bounded evidence text:** Lexical/span checks need the canonical snippets selected by `ContextBuilder`, not arbitrary policy text or retrieval debug fields.
- **Level 3 depends on risk/conflict/ambiguity triggers:** Semantic verification should run only when deterministic policy marks it necessary.
- **Action recommendations depend on both policy and business support:** A policy claim without current business facts cannot justify compensation/refund/escalation. A business fact without policy support cannot justify a policy conclusion.
- **Risk/approval depends on verified `evidence_refs`:** Snapshot building should only see refs that survived citation/support validation. Business fact refs may be audited separately but do not replace policy evidence in `ActionSafetySnapshot.evidence`.
- **Refusal/manual-review behavior depends on typed failure reasons:** `unsupported` should not be treated the same as `unauthorized`, `stale`, or `conflicting`; each needs a deterministic route and a safe user-facing response.
- **Eval depends on stable artifacts:** Golden cases should record expected claims, refs, support status, route, refusal/manual-review outcome, and forbidden refs/debug leaks.

## MVP Definition

### Launch With (Phase 22)

Minimum viable Phase 22 behavior needed for v1.5.

- [ ] `ContextBuilder` service/module with a typed input contract and prompt-safe `RagContextBundle` / `ReasoningContext` output.
- [ ] Canonical evidence content re-fetch moved out of `generate_recommendation` into `ContextBuilder`, preserving current hash/tenant safety behavior.
- [ ] Level 1 verifier that always checks citation membership, tenant/scope/ACL where available, hash validity, freshness/effective-at, and authority/source-type compatibility.
- [ ] Evidence deduplication, adjacent same-doc merge where safe, bounded evidence snippets, protected citation metadata, exclusion reasons, and token budget trace.
- [ ] Freshness, authority, conflict, and OCR-confidence labels surfaced in the context bundle and verifier inputs.
- [ ] `MaterialClaim` runtime schema with `policy_claim`, `business_fact_claim`, and `action_recommendation_claim`.
- [ ] Authority binding rules: policy claims require `EvidenceRefV1`; business fact claims require `BusinessFactRefV1` / safe `ToolResultV2`; action recommendation claims require both and cannot authorize actions.
- [ ] Level 2 lexical/span support checks for ordinary claims, with deterministic `supported | unsupported | insufficient | needs_semantic` outputs.
- [ ] Level 3 semantic support verifier for high-risk/conflict/stale/OCR-low-confidence/ambiguous cases, with explicit claim/evidence/token/latency budgets and fail-closed timeout behavior.
- [ ] Deterministic failure routing to allow, regenerate, refuse/insufficient-evidence response, or manual review.
- [ ] `generate_recommendation`, `final_response`, and `assess_risk_and_approval` integration so unsupported claims do not produce `proposed_action` or action snapshots.
- [ ] Prompt/debug boundary tests proving raw tool payloads, retrieval debug fields, source-block/OCR raw metadata, verifier traces, and full unbounded policy text do not enter ordinary prompts or final responses.
- [ ] Hallucination-control eval cases for faithfulness, citation support accuracy, refusal/manual-review routing, stale/conflicting evidence, OCR traps, business-data hallucination, memory/evidence/action authority separation, and action recommendations missing required support.

### Add After Validation (Phase 22 Stretch Only)

Add only if the launch set is stable and tests are passing.

- [ ] Regeneration loop with verifier-provided constraints - useful after first-pass failure routing works; cap attempts and preserve original failure trace.
- [ ] Claim dependency map persisted into replay/eval summaries - useful for partial permission denial and audit, but not required for the first support checks if integration cost is high.
- [ ] Maintainer-facing verifier trace view or CLI report - useful for debugging only if it does not become source upload/review UI.
- [ ] More granular policy-claim subtypes, such as rule, exception, threshold, deadline, eligibility, and conflict notice - add after the three authority categories are proven.
- [ ] Semantic verifier calibration thresholds by intent/risk family - add after golden-set data is large enough to justify thresholds.

### Future Consideration (Owner Must Be Named Before Build)

These are not Phase 22 requirements.

- [ ] Query rewrite, model reranking, cross-encoder reranking, external rerank APIs, ranking ablation, and latency tuning - owner: Phase 23 RAG Reranker + Query Rewrite.
- [ ] External action execution, outbox, reconciliation, external idempotency, and compensation dispatch - owner: Phase 17 External Action Execution.
- [ ] External `SearchBackend`, Vespa/OpenSearch, or a new vector database service - owner: Phase RAG-5 Optional External Search Backend.
- [ ] Policy source upload/review/lifecycle UI, source document viewer, and admin review workflow - owner: Policy Source Operations.
- [ ] Tenant-over-global/default policy fallback and global policy precedence merge - owner: post-Phase 17 Policy Scope.
- [ ] Business-fact hash contract for action snapshots - owner: a separately planned approval/action contract phase if needed; Phase 22 should audit business fact refs but not add them to `EvidenceRefV1`.
- [ ] Always-on semantic verification for all low-risk FAQ and policy QA - owner: future eval/performance hardening only if latency/cost data proves it is needed.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `ContextBuilder` contract and bundle output | HIGH | HIGH | P1 |
| Evidence re-fetch and Level 1 deterministic gates | HIGH | HIGH | P1 |
| Prompt-safe citation map and protected metadata | HIGH | MEDIUM | P1 |
| Token budget trace and exclusion reasons | HIGH | MEDIUM | P1 |
| Deduplication / safe adjacent merge | MEDIUM | MEDIUM | P1 |
| Freshness/authority/conflict/OCR labels | HIGH | MEDIUM | P1 |
| `MaterialClaim` taxonomy | HIGH | HIGH | P1 |
| Policy/business/action authority binding | HIGH | HIGH | P1 |
| Level 2 lexical/span support verifier | HIGH | MEDIUM | P1 |
| Risk-triggered Level 3 semantic verifier | HIGH | HIGH | P1 |
| Deterministic failure routing | HIGH | HIGH | P1 |
| Node integration with recommendation/final/risk gates | HIGH | HIGH | P1 |
| Hallucination-control eval suite | HIGH | HIGH | P1 |
| Maintainer verifier trace | MEDIUM | MEDIUM | P2 |
| Regeneration with verifier constraints | MEDIUM | MEDIUM | P2 |
| Persisted claim dependency map for replay/eval | MEDIUM | MEDIUM | P2 |
| Granular claim subtypes | MEDIUM | LOW | P2 |
| Semantic verifier calibration by intent/risk | MEDIUM | HIGH | P2 |
| User-facing source review UI | LOW for Phase 22 | HIGH | P3 |
| Query rewrite/reranking | HIGH but out of scope | HIGH | P3 / Phase 23 |
| External search backend | LOW for Phase 22 | HIGH | P3 / RAG-5 |

**Priority key:**
- P1: Must have for Phase 22 launch
- P2: Should have if it fits without weakening the core contract
- P3: Nice to have or deferred to a named owner phase

## Competitor Feature Analysis

This file is scoped to MOCA feature behavior, not vendor selection. The useful comparison is current MOCA vs production RAG practice vs the Phase 22 target.

| Feature | Current MOCA v1.4 Baseline | Production RAG Practice | Phase 22 Approach |
|---------|----------------------------|-------------------------|-------------------|
| Context assembly | `generate_recommendation` performs local evidence re-fetch and prompt snippet construction. | Grounded generation systems separate context assembly from generation so prompts, verifiers, and responses consume the same checked context. | Introduce reusable `ContextBuilder` after retrieval and before answer/action reasoning. |
| Citation validation | Membership validation proves cited IDs are in retrieved evidence. | RAGTruth and newer verification work show retrieved/cited context can still be unsupported or contradictory. | Keep membership as Level 1, then add Level 2 lexical/span and Level 3 semantic support checks. |
| Claim representation | `RecommendationDraft` has a reasoning summary and evidence refs; tests project it into one pseudo-claim for membership. | Faithfulness metrics decompose responses into claims and check whether each claim is supported by retrieved context. | Add explicit `MaterialClaim` records with authority-specific refs and support status. |
| Business facts | Tool results and prompt summaries are separate from policy refs. | Tool-using agents need provenance separation between structured facts and document evidence. | Require `BusinessFactRefV1` / `ToolResultV2` for business claims; forbid business facts as `EvidenceRefV1`. |
| Action support | Risk node can build action snapshots from available evidence refs. | Enterprise agents separate evidence support from approval/action authorization. | Verified support is required before action recommendation, but risk/approval/action gates remain authoritative. |
| Failure handling | `citation_invalid` and `insufficient_evidence` paths exist. | Selective RAG systems abstain or route when support is insufficient. | Expand deterministic routing for unsupported, stale, conflicting, unauthorized, hash-mismatched, insufficient, and manual-review-needed outcomes. |
| Evaluation | Retrieval Hit@5/fallback and node tests cover current RAG safety basics. | Modern RAG evaluation measures faithfulness, context precision/recall, citation support, conflict handling, and refusal quality. | Add Phase 22 hallucination-control eval with claim-level expected support and expected route. |

## Sources

- `.planning/PROJECT.md` - v1.5 goal, Phase 22 target features, shipped v1.3/v1.4 dependencies, and explicit out-of-scope boundaries. Confidence: HIGH.
- `docs/rag-architecture-spec.md` - Reasoning Kernel, `ContextBuilder`, freshness/authority/conflict labels, hallucination-control layers, verifier levels, eval categories, and RAG phase boundaries. Confidence: HIGH for project target architecture; `docs/contract-spec.md` remains normative where they differ.
- `docs/rag_spec_suggestion.md` - Prior RAG ecosystem synthesis supporting claim-level verification, context assembly, and the separation of citation membership from semantic support. Confidence: MEDIUM because it is advisory, not normative.
- `docs/contract-spec.md` - canonical `TrustedContext`, `EvidenceRefV1`, KnowledgeService, `ToolResultV2`, `BusinessFactRefV1`, router/node contracts, memory boundaries, approval/action snapshot boundaries, and final response safety rules. Confidence: HIGH.
- `src/agent/nodes/generate_recommendation.py` - current evidence re-fetch, prompt snippet assembly, membership validation, and `evidence_refs` promotion behavior. Confidence: HIGH.
- `src/agent/nodes/final_response.py` - current deterministic insufficient-evidence, citation-invalid, retrieval-error, approval, and demo-draft response behavior. Confidence: HIGH.
- `src/agent/nodes/assess_risk_and_approval.py` - current action recommendation to risk/snapshot binding path and no-action behavior for insufficient/citation-invalid/retrieval-error drafts. Confidence: HIGH.
- `tests/knowledge/test_facade_integration.py` - integration proof that membership passes can still allow semantically unsupported reasoning today, plus no-evidence and citation-invalid safety paths. Confidence: HIGH.
- `tests/agent/test_nodes/test_generate_recommendation.py` - prompt-safety, hash mismatch, cross-tenant grounding, bounded policy text, and raw-payload exclusion coverage. Confidence: HIGH.
- RAGTruth, ACL 2024 (`https://aclanthology.org/2024.acl-long.585/`) - external evidence that RAG systems can still emit unsupported or contradictory claims and need hallucination-specific evaluation. Confidence: HIGH for the general research finding.
- SURE-RAG, arXiv 2026 (`https://arxiv.org/abs/2605.03534`) - external evidence that retrieval is not verification and that evidence sufficiency should produce support/refute/insufficient style decisions. Confidence: MEDIUM because it is recent preprint evidence, not a MOCA contract.
- RT4CHART, arXiv 2026 (`https://arxiv.org/html/2603.27752v1`) - external support for decomposing answers into independently verifiable claims with localized evidence and claim-level verdicts. Confidence: MEDIUM because it is recent preprint evidence, not a MOCA contract.
- Ragas faithfulness and context precision docs (`https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/`, `https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/`) - evaluation vocabulary for claim support and retrieved-context quality. Confidence: MEDIUM; useful for metric framing, not required technology.

## Orchestrator Summary

Phase 22 should launch as a Reasoning Kernel: reusable `ContextBuilder`, prompt-safe context bundle, `MaterialClaim` taxonomy, Level 1/2/3 verification, deterministic failure routing, and hallucination-control eval. It should explicitly avoid Phase 23 retrieval improvements, Phase 17 external execution, RAG-5 backend work, Policy Source Operations UI, and any `EvidenceRefV1` identity change.

---
*Feature research for: MOCA v1.5 Phase 22 RAG Context Builder + Hallucination Control*
*Researched: 2026-06-19*
