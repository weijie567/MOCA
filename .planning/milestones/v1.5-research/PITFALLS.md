# Pitfalls Research

**Domain:** MOCA v1.5 / Phase 22 RAG Context Builder + Hallucination Control
**Researched:** 2026-06-19
**Confidence:** HIGH for MOCA contract and implementation pitfalls; MEDIUM for future semantic-verifier model behavior until Phase 22 selects concrete verifier implementation and eval thresholds.

## Executive Scope

Phase 22 adds a Reasoning Kernel between retrieval and answer/action reasoning. It should turn retrieved `EvidenceRefV1` values plus typed business facts into a prompt-safe context bundle, structured `MaterialClaim` records, deterministic verifier results, and refusal/manual-review/regeneration routes. This is not a retrieval-quality phase and not a backend phase.

The hard integration rule is authority separation. `EvidenceRefV1` remains canonical policy evidence. `BusinessFactRefV1` and `ToolResultV2` remain the authority for current business facts. Memory is contextual only. Source-block/OCR provenance is internal/debug lookup only. Approval, action, and replay remain authoritative in their own domains through `ActionSafetySnapshot`, action payload hashes, approval lifecycle records, and `ReplayEventV3`.

The current implementation already has useful foundations but also concrete fail-open seams: `generate_recommendation` can continue without grounded evidence text if content re-fetch fails; citation validation is membership-only; prompts receive allowed citation objects and bounded snippets but do not receive a reusable `ContextBuilder` output; risk/action snapshot logic consumes canonical evidence refs but does not yet know claim-level verifier outcomes. Phase 22 should close those seams without changing retrieval ranking semantics, adding query rewrite/reranking, introducing an external search backend, or changing `EvidenceRefV1` identity.

## Critical Pitfalls

### Pitfall 1: Collapsing Policy, Business, Memory, and Action Authority

**What goes wrong:**
`MaterialClaim` becomes a generic "thing the model said" object where policy claims, business facts, memory hints, and action recommendations are all validated with the same reference field. Business facts get cited as `EvidenceRefV1`, memory hints get treated as policy support, or action recommendations pass with policy evidence only and no current business fact refs.

**Why it happens:**
Claim-level validation is new, and a single `cited_refs` list is easier to implement than typed claim dependencies. The current prompt assembler already mixes policy snippets, business context, tool summaries, recent messages, long-term memory, and case memory into one prompt, so it is easy to blur support sources after assembly.

**How to avoid:**
Define `MaterialClaim` as a runtime Reasoning Kernel object with explicit claim types and typed support:

| Claim type | Required authority | Invalid support |
|------------|--------------------|-----------------|
| `policy_claim` | `EvidenceRefV1` from current ContextBuilder bundle | memory, business refs, source-block refs |
| `business_fact_claim` | `BusinessFactRefV1` / safe `ToolResultV2` ref from current run | policy evidence, memory |
| `action_recommendation_claim` | both policy support and current business fact support; then risk/approval/action boundaries still apply | policy-only, business-only, memory-only |
| `conflict_notice` / `missing_information` | verifier/context labels and safe missing-info codes | invented policy/business facts |

Add schema validation that rejects a claim whose type and support refs do not match. Add graph routing that treats claim support failures as regenerate/refuse/manual-review inputs, not as cosmetic warnings.

**Warning signs:**
- `MaterialClaim` has a single `refs: list[str]` or accepts arbitrary dictionaries.
- Business read tools populate `policy_evidence_refs`.
- Case memory `policy_refs` are copied into `evidence_refs`.
- An action recommendation can enter `risk_gate` with no `BusinessFactRefV1`.
- Tests assert citation presence but not typed authority separation.

**Phase to address:**
Phase 22. Verification should include claim-type schema tests and graph integration cases proving memory/case memory/business refs cannot satisfy policy evidence, and policy refs alone cannot authorize an action recommendation.

---

### Pitfall 2: Treating Citation Membership as Semantic Support

**What goes wrong:**
A policy claim cites a retrieved evidence ID, membership validation passes, and the system marks the claim as grounded even when the quoted chunk does not support the claim or even contradicts it.

**Why it happens:**
MOCA already has `validate_membership`, and it is correct for Phase 8: it only proves cited evidence IDs are in the allowed evidence set. It is tempting to reuse the existing `CitationValidationResult.is_valid` as a green light for hallucination control because it is deterministic and already integrated into `generate_recommendation`.

**How to avoid:**
Keep the gates separate and name them differently:

- Level 1 deterministic gate: membership, tenant/scope, hash, freshness, required metadata, allowed-evidence membership.
- Level 2 low-cost support gate: lexical/span/condition checks over ContextBuilder snippets for ordinary claims.
- Level 3 semantic verifier: risk-triggered support/refute/insufficient judgment for high-risk, conflict, stale, OCR-low-confidence, or ambiguous cases.

`citation_validation` should remain membership-only unless renamed and versioned. Phase 22 should create a separate claim verification result with fields such as `membership_valid`, `hash_valid`, `scope_valid`, `freshness_valid`, `lexical_support`, `semantic_support`, `support_status`, and deterministic `route_action`.

**Warning signs:**
- `validation.is_valid` is used as the only condition for answer/action allow.
- Verifier output does not preserve the difference between `cited_but_unsupported` and `missing_citation`.
- Tests include missing citation IDs but no supported-vs-unsupported evidence text cases.
- `MaterialClaim` is projected from only the final answer summary, not claim-level text.

**Phase to address:**
Phase 22. Verification should add an unsupported-but-cited fixture that passes membership but fails support, and assert the final route is regenerate/refuse/manual review rather than completed/action.

---

### Pitfall 3: ContextBuilder Fails Open on Re-fetch, Hash, Tenant, or Scope Failures

**What goes wrong:**
Evidence content cannot be re-fetched, hashes do not match, duplicate evidence keys are ambiguous, or tenant/scope mismatches occur, but generation still proceeds with citation IDs and no verified text. The model can then answer from memory, prior messages, pretraining, or business context while appearing evidence-backed.

**Why it happens:**
The current `generate_recommendation` logs content re-fetch failures and continues. That was acceptable as an incremental boundary because membership validation remained separate, but Phase 22's goal is hallucination control. Once ContextBuilder exists, missing verified content is not a soft warning for material policy claims.

**How to avoid:**
Make ContextBuilder produce explicit inclusion/exclusion records:

- `included_evidence`: only refs with tenant match, unique key, successful content re-fetch, matching `text_hash`, valid scope, and allowed freshness.
- `excluded_evidence`: reason-coded failures such as `tenant_mismatch`, `hash_mismatch`, `content_missing`, `duplicate_key`, `stale`, `unauthorized`, `ocr_low_confidence`.
- `bundle_status`: `ready`, `insufficient`, `conflicting`, `manual_review_required`, or `error`.

Any material policy claim requiring excluded evidence must fail closed. Generation may run only with the prompt-safe included bundle; if the bundle is insufficient for the requested intent, route to refusal/manual review before or after one bounded regeneration attempt.

**Warning signs:**
- Content re-fetch exceptions are logged but not surfaced in routing.
- Prompt includes allowed citation objects for refs whose text was not verified.
- Hash mismatch only removes text but still lets the model cite the ref.
- Exclusion reasons are stored in debug traces but not asserted in tests.

**Phase to address:**
Phase 22. Verification should add unit tests for every exclusion reason and integration tests where missing session/re-fetch/hash mismatch no longer produces a completed material recommendation.

---

### Pitfall 4: Freshness, Authority, and Conflict Become Labels Only

**What goes wrong:**
ContextBuilder adds labels like `stale`, `lower_authority`, or `conflict`, but the generator still sees all snippets and silently chooses one. The final answer may cite an old or lower-authority policy and appear valid because the evidence ID is real.

**Why it happens:**
Freshness and authority started as retrieval metadata. Phase 22 can be tempted to defer hard conflict behavior to a future reranker phase, especially because Phase 23 owns query rewrite/reranking. But conflict/freshness routing is explicitly in Phase 22's scope after retrieval has already returned candidates.

**How to avoid:**
Make conflict/freshness labels route-affecting:

- `stale` or superseded evidence cannot support a deterministic policy conclusion unless the claim is explicitly about historical policy.
- Same-topic contradictory evidence creates a `conflicting` verifier status unless authority/supersedes logic deterministically resolves it.
- Unresolved conflict in high-risk/action/troubleshooting routes to manual review.
- Low-risk FAQ may explain that evidence conflicts, but must not choose silently.

Do not implement new ranking or reranking in Phase 22. Use current candidate order plus document metadata and ContextBuilder labels to decide inclusion, exclusion, and manual review.

**Warning signs:**
- Conflict labels appear only in trace/debug JSON.
- Final answer has no conflict notice even when bundle contains conflict groups.
- Tests assert labels exist but not route changes.
- Old and new policy versions can both support the same claim without deterministic resolution.

**Phase to address:**
Phase 22. Verification should include stale-version and conflicting-policy golden cases with expected refusal/manual-review/conflict-notice outcomes.

---

### Pitfall 5: OCR and Source-Block Provenance Leaks Into Authority or Prompts

**What goes wrong:**
Source-block IDs, page/bbox data, parser metadata, OCR confidence, hidden OCR text, or raw provenance traces enter ordinary prompts, final answers, snapshots, replay payloads, memory, business facts, or `EvidenceRefV1`. Even worse, a `DocumentBlock` or `source_block_id` becomes a policy authority ref.

**Why it happens:**
Phase 21 made provenance valuable for debugging and future citation lookup. Phase 22 naturally wants OCR confidence and page/bbox labels for hallucination control. Without strict projection boundaries, internal provenance becomes prompt data or a second evidence identity.

**How to avoid:**
Use provenance only as an internal/debug side path:

- ContextBuilder may query verified provenance only after `EvidenceRefV1` tenant/hash checks pass.
- Prompt-safe bundles should expose coarse labels such as `ocr_confidence=low` or `provenance_available=true`, not raw parser/OCR payloads, hidden text, local paths, source-block IDs, or bbox unless a future UI/debug endpoint explicitly requires them.
- `EvidenceRefV1` fields remain unchanged.
- Action snapshots, replay events, memory, and business tool contracts must continue rejecting source-block/parser/OCR authority fields.

**Warning signs:**
- `source_block_id`, `parser_metadata_json`, `ocr_metadata_json`, `bbox`, or `DocumentBlock` appears in `EvidenceRefV1`, action snapshots, replay schemas, memory schemas, business tool results, or ordinary answer DTOs.
- Low OCR confidence text is copied into a final answer as if it were reviewed policy.
- Debug provenance enters `node_hints` or conversation prompt summaries.

**Phase to address:**
Phase 22. Verification should extend Phase 21 boundary tests to ContextBuilder, verifier traces, prompt snapshots, final response, replay redaction, and action snapshot projections.

---

### Pitfall 6: Scope Creep Into Query Rewrite, Reranking, or Search Backend Work

**What goes wrong:**
The ContextBuilder starts reordering evidence, rewriting queries, adding reranker interfaces, calling cross-encoder/external rerank APIs, defining a full `SearchBackend`, or changing Phase 20 hybrid retrieval semantics to improve verifier results.

**Why it happens:**
Unsupported claims often look like retrieval-quality failures. Teams naturally try to "fix hallucination" by fetching more or better evidence, especially when conflict/semantic support checks fail. But Phase 22's boundary is after retrieval and before reasoning; Phase 23 owns query rewrite/reranking, and RAG-5 owns external backend.

**How to avoid:**
Draw a hard Reasoning Kernel boundary:

- Inputs are candidate `EvidenceRefV1` values already produced by retrieval plus current trusted business refs/context.
- ContextBuilder may validate, filter, dedupe, merge adjacent chunks, budget, label, and map citations.
- It must not call new search backends, query rewrite, external rerank APIs, cross-encoders for relevance sorting, or mutate retrieval scores/ranks.
- If evidence is insufficient, route deterministically instead of widening retrieval inside the verifier.

**Warning signs:**
- New code names include `QueryRewriteService`, `CrossEncoderReranker`, `ExternalRerankClient`, `SearchBackend`, Vespa, or OpenSearch.
- Verifier has a `rerank_score` or writes back to retrieval rank.
- ContextBuilder fetches new candidates not present in the incoming evidence refs.
- Requirements say "try another search" without a Phase 23 owner.

**Phase to address:**
Phase 22 for guardrails; Phase 23 for any query rewrite/reranking work. Verification should include static scope guards and contract tests proving ContextBuilder output preserves incoming evidence identity/rank rather than redefining retrieval.

---

### Pitfall 7: Verifier Latency and Cost Explode

**What goes wrong:**
Every answer runs semantic verification for every sentence against every evidence snippet. Latency becomes unpredictable, provider cost spikes, and timeouts cause either user-visible failures or silent fail-open behavior.

**Why it happens:**
Semantic support is attractive but expensive. Without claim count, evidence count, token, concurrency, and timeout budgets, Level 3 becomes a mini RAG pipeline behind every request. The model-verifier path can also be accidentally invoked for low-risk FAQ or already-deterministic refusal cases.

**How to avoid:**
Budget the verifier before implementation:

- Level 1 always runs and is deterministic.
- Level 2 runs on ordinary material claims using bounded lexical/span checks over included snippets.
- Level 3 runs only for high-risk, action, conflict, stale, OCR-low-confidence, ambiguous, or policy-sensitive claims.
- Set hard limits: max material claims, max evidence refs per claim, max text chars/tokens, max Level 3 calls, deadline, retry count, and fallback route.
- Timeouts and provider errors fail closed to manual review/refusal for material claims, not completed answers.

**Warning signs:**
- The verifier receives the whole prompt or final answer blob instead of structured claims.
- There is no `verifier_latency_ms`, `level3_invoked`, `claim_count`, or timeout metric.
- Level 3 is invoked for small talk, fact-only order status, or no-evidence cases.
- Provider timeout falls back to `supported`.

**Phase to address:**
Phase 22. Verification should include latency-budget unit tests with fake slow verifiers, plus eval/report fields for Level 3 trigger rate, timeout rate, and fail-closed routing.

---

### Pitfall 8: Verifier Output Is Advisory Instead of Deterministic Routing

**What goes wrong:**
The verifier produces `unsupported`, `conflicting`, `stale`, or `manual_review_needed`, but the final response template still completes the recommendation, or risk assessment/action draft ignores the failure.

**Why it happens:**
It is easier to attach verifier details to trace output than to thread a route decision through `recommendation_generation`, `route_after_recommendation`, `risk_gate`, and `final_response`. The current graph already routes mainly on retrieval status, score, and draft `recommended_action`; Phase 22 must add claim verification status without making routers model-driven.

**How to avoid:**
Make verifier routing a first-class state contract:

- `verification_status`: `supported`, `unsupported`, `insufficient`, `conflicting`, `stale`, `unauthorized`, `hash_mismatch`, `manual_review_required`, `error`.
- `verification_route`: `allow`, `regenerate`, `refuse`, `manual_review`.
- Routers use deterministic enums only; they do not ask the model what to do.
- `risk_gate` and action snapshot creation require supported action-recommendation claims and exact canonical evidence refs.
- `final_response` has deterministic templates for unsupported/conflicting/stale/manual-review outcomes.

**Warning signs:**
- Verifier status is present only inside `llm_outputs` or `trace_steps`.
- `risk_gate` can build an `ActionSafetySnapshot` when verifier route is not `allow`.
- Unsupported claims remain in the final answer with a caveat instead of being removed/regenerated/refused.
- Manual-review wording is generated freely by the LLM.

**Phase to address:**
Phase 22. Verification should add graph-level tests for each route enum and prove fail states cannot create proposed actions, approval requests, or action drafts.

---

### Pitfall 9: Prompt-Safe Bundle and Debug Trace Boundaries Drift

**What goes wrong:**
The same object is used for prompts, verifier inputs, debug logs, trace replay, and API responses. It accumulates raw evidence text, exclusion reasons, model-verifier rationales, hidden OCR data, source locators, token traces, retrieval debug fields, and internal decision data. Sensitive or confusing internals leak into prompts or user-facing answers.

**Why it happens:**
ContextBuilder naturally produces rich debugging information. A single DTO is easier than separate projections. Existing code already uses prompt projectors and safe summaries, but Phase 22 will add more fields with different audiences.

**How to avoid:**
Define separate projections:

| Projection | Audience | Allowed contents |
|------------|----------|------------------|
| `RagContextBundle` / prompt projection | LLM generator | included evidence text, citation IDs, coarse labels, allowed refs, safe business summaries/refs |
| verifier input | deterministic/verifier code | material claims, included snippets, typed refs, labels needed for support checks |
| debug trace | developers/eval | exclusion reasons, budget trace, verifier timing, support statuses, no raw payloads |
| final/user response | user | answer/refusal/manual-review wording and display-safe citation summary only |

Protect citation metadata from token-budget trimming, but keep debug/budget/verifier trace out of ordinary prompts and final answers.

**Warning signs:**
- `model_dump()` of the ContextBuilder result is passed directly to the prompt.
- Token budget trace, verifier rationale, or excluded evidence appears in user text.
- Final response cites `E1` without a stable mapping to canonical `EvidenceRefV1`.
- Prompt snapshot contains raw debug fields or source-block/OCR internals.

**Phase to address:**
Phase 22. Verification should include projection tests for prompt, verifier, trace, final response, and replay redaction.

---

### Pitfall 10: Token Budgeting Drops the Metadata Needed to Verify Claims

**What goes wrong:**
Evidence text is clipped or merged without preserving `evidence_id`, `doc_key`, `chunk_id`, `policy_version`, `text_hash`, claim-to-citation mapping, conflict/freshness/OCR labels, or exclusion reasons. The model may see text but cannot cite it correctly, or the verifier cannot map generated claims back to support.

**Why it happens:**
The existing `ContextAssembler` has protected prompt blocks, but Phase 22 needs RAG-specific invariants. Context budgeting that is safe for general prompt assembly is not enough for citation-bearing evidence.

**How to avoid:**
Make ContextBuilder token budgeting structured:

- Citation metadata is protected and never truncated independently of text.
- Text truncation records exact truncation and does not claim semantic support for omitted conditions.
- Adjacent/duplicate chunk merge preserves every source `EvidenceRefV1`.
- Every prompt citation ID maps back to exactly one canonical evidence ref or an explicit merged evidence group.
- If budget removes required support for a material claim, route to insufficient/manual review rather than let the model infer.

**Warning signs:**
- The prompt has snippet text but no allowed citation object for it.
- `E1` maps to multiple unrelated chunks without a deterministic merge record.
- Verifier checks only the truncated prompt text while final citation points to a larger chunk.
- Tests use short snippets only.

**Phase to address:**
Phase 22. Verification should include long evidence, adjacent-merge, duplicate-ref, and protected-metadata budget cases.

---

### Pitfall 11: Business Data Hallucination Survives Through Natural-Language Summaries

**What goes wrong:**
The model states order status, refund outcome, logistics status, merchant risk, or compensation amount from policy text, prior messages, memory, or a tool summary that lacks a current `BusinessFactRefV1`. Troubleshooting answers look plausible but are not grounded in current tool results.

**Why it happens:**
Prompt summaries are natural-language and often contain business IDs. Existing projectors intentionally keep safe summaries visible, but a summary is not the same as current fact authority. Phase 22 claim verification must validate business-fact support, not just policy support.

**How to avoid:**
Require `business_fact_claim` and `action_recommendation_claim` support checks:

- Business facts must reference current-run `BusinessFactRefV1` or safe `ToolResultV2` provenance.
- Prompt summaries may help wording but cannot satisfy support.
- Same-thread memory may carry slots, not current status/facts.
- Case memory may suggest precedent, not current outcome or amount.
- If current business facts are missing, route to clarification/missing-info/manual review before recommendation/action.

**Warning signs:**
- A final answer contains an order/refund status not present in current `business_context.facts` or tool refs.
- `reasoning_summary` includes a compensation amount that only appears in policy text or memory.
- Tests inspect policy citations but not business fact refs.
- Tool `partial_success` still supports a complete business fact claim.

**Phase to address:**
Phase 22. Verification should add business-data hallucination cases and action recommendations missing either policy support or business fact support.

---

### Pitfall 12: Evaluation Covers Happy-Path Grounding but Misses Refusal and Boundary Regressions

**What goes wrong:**
Phase 22 passes faithfulness examples where the correct evidence is present, but fails in real failure modes: no evidence, unsupported-but-cited claims, stale/conflicting policies, OCR-low-confidence traps, cross-tenant evidence, business-fact hallucination, memory-as-evidence, prompt/debug leaks, and action recommendations missing required support.

**Why it happens:**
Existing RAG evals emphasize Hit@5 and fallback accuracy. Hallucination control requires negative and adversarial evals, plus graph-level outcome checks. It is easy to measure retrieval quality while missing whether the final product refused or escalated correctly.

**How to avoid:**
Build a Phase 22 eval gate around outcomes, not just answer text:

- Faithfulness and citation accuracy at claim level.
- Membership vs semantic support split.
- Refusal/manual-review routing accuracy.
- Conflict/freshness correctness.
- OCR low-confidence behavior.
- Business data grounding.
- Memory/evidence/action authority separation.
- Prompt/debug/provenance leak checks.
- Action recommendation support completeness.

Each golden case should specify expected `MaterialClaim` types, required support refs, verifier status, and final route.

**Warning signs:**
- Eval has no expected route.
- Eval accepts "answer mentions uncertainty" when the route should be manual review/refusal.
- No cases assert absence of leaked debug/provenance fields.
- No metrics for unsafe answer rate, partial-evidence overclaim rate, or Level 3 timeout fail-closed behavior.

**Phase to address:**
Phase 22. Verification should be blocking for claim-level faithfulness, citation accuracy, refusal/manual-review routing, and boundary regressions.

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use existing `validate_membership` as the verifier | Fast integration | Unsupported-but-cited claims pass as grounded | Never for Phase 22 material claims; membership remains Level 1 only |
| Let generation continue when ContextBuilder cannot verify content | Preserves current happy path | Fail-open hallucinations with real-looking citations | Only for non-material direct response paths that do not make policy/business/action claims |
| Single `MaterialClaim.refs` field | Simple schema | Authority collapse across policy, business, memory, action | Never; refs must be typed by claim type |
| Store verifier/debug trace in the prompt bundle | Easier debugging | Prompt/debug leaks and model overfitting to verifier internals | Never for ordinary prompts; use separate debug projection |
| Run Level 3 on every answer | Simpler mental model | Cost/latency blowup and timeout failures | Never by default; use risk-triggered policy |
| Add query rewrite/rerank to fix unsupported claims | Better retrieval in some examples | Phase 22 becomes Phase 23 and changes retrieval semantics | Never in Phase 22; defer to Phase 23 |
| Use source-block IDs as claim support refs | Precise page/bbox lookup | Second policy evidence authority shape | Never; source-block lookup is subordinate to verified `EvidenceRefV1` |
| Only test final answer text | Easy golden files | Misses route, authority, and leakage regressions | Never as the only gate |

## Integration Gotchas

Common mistakes when connecting Phase 22 to existing MOCA components.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `generate_recommendation` | Keep local re-fetch/hash checks and add ContextBuilder beside them | Move evidence re-fetch/hash/budget/citation-map work into reusable ContextBuilder and make generation consume only prompt-safe bundle output |
| `src/knowledge/citation.py` | Expand membership validator into semantic verifier in place | Keep membership-only validator stable; create separate claim verifier contract/version |
| `ContextAssembler` | Treat it as the new ContextBuilder | Keep it as generic prompt assembly; Phase 22 ContextBuilder is RAG-specific and feeds safe blocks into assembler |
| `assess_risk_and_approval` | Let risk gate infer action safety from draft evidence refs only | Require supported action recommendation claims plus canonical evidence refs before snapshot creation |
| `final_response` | Surface verifier/debug details directly to users | Use deterministic refusal/manual-review/conflict templates with display-safe citation summaries |
| `PolicyKnowledgeService` | Ask it to rewrite queries or fetch more candidates when verifier fails | Use it only for verified content/provenance lookup of incoming refs; route insufficient evidence instead |
| Conversation/tool prompt summaries | Treat safe summaries as current fact authority | Require current `BusinessFactRefV1`/`ToolResultV2` support for business fact claims |
| Replay/events | Store full verifier prompts, raw evidence text, or source provenance in replay payloads | Store low-sensitive status/timing/reason codes and canonical refs; keep raw text/provenance out |

## Performance Traps

Patterns that work in unit tests but fail under realistic agent runs.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Level 3 semantic verifier for all claims | Slow ordinary FAQ, high provider bill, timeouts | Trigger Level 3 only for high-risk/conflict/stale/OCR-low-confidence/ambiguous/action claims | As soon as answers have multiple claims and 5+ snippets |
| Cross-product claim x evidence checking | O(n*m) verifier work | Pre-map citations, cap refs per claim, run Level 2 only on cited snippets first | 5 claims x 5 snippets already creates 25 checks per turn |
| Whole-prompt verifier input | Excess tokens and unstable judgments | Verify structured claims against bounded included evidence snippets | Long conversation history or large business context |
| No fail-closed timeout path | Timeouts become completed answers or generic errors | Deadline-aware verifier with deterministic `manual_review`/`refuse` fallback | Provider latency spike or local model slowdown |
| Debug trace stored with raw text | Large traces, privacy/security exposure | Store hashes, refs, reason codes, lengths, timings, statuses | Long snippets, OCR documents, repeated retries |
| Token budgeting by raw character slicing | Lost conditions/citation metadata | Structured budget policy with protected refs and truncation metadata | Long policy tables or adjacent chunk merge |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Let source text or OCR content instruct the agent | Indirect prompt injection can affect tools/actions/memory | Treat all evidence text as data, delimit it, and ignore source instructions for routing/tool/action decisions |
| Include source-block/OCR/debug fields in ordinary prompts | Hidden text, local paths, parser internals, or prompt attacks leak | Prompt projection allows only verified evidence text, canonical refs, and coarse labels |
| Allow model/user-supplied refs in ContextBuilder | Cross-tenant or forged evidence support | Build from trusted retrieval output only and re-check tenant/hash/scope |
| Put verifier rationales in final response | Reveals internal policy and encourages prompt gaming | Final responses use deterministic public wording; traces store low-sensitive codes |
| Persist raw verifier prompts or evidence text in replay | Replay privacy and retention breach | Store canonical refs, hashes, route/status, latency, and redacted snippets only if explicitly allowed |
| Treat memory/case memory as authority | Stale or poisoned memory can support actions | Memory remains contextual; tests must block memory-as-evidence/action authority |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Refusal wording says only "insufficient evidence" | User does not know what to provide next | Include safe missing-info reason: missing policy evidence, stale/conflict, missing business fact, or manual review needed |
| Conflict handling is hidden in trace | Support staff receives a confident but unsafe answer | Use deterministic conflict/manual-review response when unresolved policy conflict exists |
| Low OCR confidence is exposed as raw technical metadata | User sees confusing parser details | Present a simple manual-review reason; keep OCR details in debug lookup |
| Citation IDs change after budget/merge | User cannot map answer to evidence panel/replay | Stable citation map from prompt IDs to canonical refs |
| Manual-review routes look like system errors | Users retry instead of escalating | Make manual review a normal safety outcome with concise explanation |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **ContextBuilder contract:** Often missing explicit excluded evidence reasons - verify every rejected ref has a reason and route impact.
- [ ] **Prompt-safe bundle:** Often missing separate prompt/debug/verifier projections - verify raw debug/provenance fields cannot enter prompts or final responses.
- [ ] **MaterialClaim taxonomy:** Often missing typed authority refs - verify policy, business, and action claims reject wrong support types.
- [ ] **Level 1 gate:** Often checks membership only - verify tenant, scope, hash, freshness, duplicate-key, and allowed-ref checks always run.
- [ ] **Level 2 support:** Often becomes vague keyword matching - verify span/condition checks can fail unsupported-but-cited claims.
- [ ] **Level 3 verifier:** Often runs everywhere or nowhere - verify risk-trigger policy, budgets, timeout fail-closed behavior, and metrics.
- [ ] **Conflict/freshness routing:** Often only labels evidence - verify stale/conflicting claims alter route.
- [ ] **Business fact grounding:** Often trusts natural-language summaries - verify current `BusinessFactRefV1`/`ToolResultV2` refs support business claims.
- [ ] **Action recommendations:** Often require only policy citations - verify both policy and business support plus existing approval/action snapshot boundaries.
- [ ] **Scope guard:** Often accidentally adds reranking/query rewrite - grep for Phase 23/RAG-5 surfaces and ensure no retrieval rank semantics changed.
- [ ] **Eval:** Often measures only answer quality - verify route, claim support, citation accuracy, boundary leaks, and fail-closed outcomes.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Authority collapse in `MaterialClaim` | HIGH | Freeze schema, split typed refs, migrate tests/golden cases, reject old generic refs, audit action paths |
| Membership used as support | MEDIUM | Rename outputs, add separate verifier result, update routers, add unsupported-but-cited regression tests |
| ContextBuilder fail-open | MEDIUM/HIGH | Add exclusion reasons, route failures, change generation preconditions, replay affected eval cases |
| Provenance/debug leak | HIGH | Remove leaked fields from projections, add redaction/static guards, rotate unsafe trace snapshots if persisted |
| Reranker/query rewrite scope creep | MEDIUM | Delete/defer code to Phase 23, restore retrieval semantics, add static guard and roadmap owner note |
| Verifier cost blowup | MEDIUM | Add trigger policy, caps, timeout, metrics, and skip Level 3 for low-risk/no-evidence paths |
| Missing eval negatives | MEDIUM | Add blocking golden categories and fail CI until unsafe routes are covered |
| Action path ignores verifier | HIGH | Block snapshot/action creation on non-allow verifier routes and audit existing graph tests |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Authority collapse across policy/business/memory/action | Phase 22 | Claim schema tests; graph tests proving wrong ref types fail; memory boundary regressions remain green |
| Membership mistaken for semantic support | Phase 22 | Unsupported-but-cited fixture passes membership but fails support and routes safely |
| ContextBuilder fail-open | Phase 22 | Re-fetch failure, hash mismatch, tenant mismatch, stale/unauthorized refs route to refuse/manual review/regenerate |
| Conflict/freshness labels do not route | Phase 22 | Stale and conflicting policy golden cases assert deterministic route changes |
| OCR/provenance leaks or authority drift | Phase 22 | Static/projection tests forbid source-block/OCR/debug fields in prompts, answers, memory, replay, business tools, snapshots |
| Reranker/query rewrite/backend creep | Phase 22 guard; Phase 23/RAG-5 owners | Static grep guard; no new cross-encoder/external rerank/backend interfaces; input refs preserved |
| Verifier latency/cost blowup | Phase 22 | Fake slow verifier tests; metrics for Level 3 triggers/timeouts; fail-closed timeout route |
| Verifier advisory only | Phase 22 | Router tests for `allow/regenerate/refuse/manual_review`; non-allow cannot create proposed action/action draft |
| Prompt/debug boundary drift | Phase 22 | Separate projection snapshots for prompt, verifier, trace, final response |
| Token budget drops citation metadata | Phase 22 | Long-snippet and merge tests preserve citation map/protected metadata |
| Business data hallucination | Phase 22 | Golden cases require `BusinessFactRefV1`/`ToolResultV2`; policy-only business claims fail |
| Eval blind spots | Phase 22 | Blocking eval categories for faithfulness, citation accuracy, refusal/manual review, OCR/conflict traps, boundary regressions |

## Sources

- `.planning/PROJECT.md` - v1.5 scope, Phase 22 requirements, hard boundaries, shipped v1.3/v1.4 evidence/provenance constraints. Confidence: HIGH.
- `docs/rag-architecture-spec.md` sections 4.1, 4.2, 9.5, 11, 12, 13, 15 - Reasoning Kernel, ContextBuilder, freshness/authority/conflict handling, hallucination-control levels, eval categories, and Phase RAG-3 scope. Confidence: HIGH for target architecture; note Phase 22 milestone wording should override any older Level 2 wording that implies reranking work.
- `docs/rag_spec_suggestion.md` - recommendation to separate citation membership from semantic support, preserve freshness/authority as routing inputs, and keep PostgreSQL/retrieval work separate from reasoning verification. Confidence: MEDIUM/HIGH.
- `docs/contract-spec.md` sections 8.0, 8.3, 8.4, 12.5, 13.3, 13.4, 14, 17 - normative `TrustedContext`, `EvidenceRefV1`, `BusinessFactRefV1`, `ToolResultV2`, memory, action snapshot, and replay boundaries. Confidence: HIGH.
- `src/agent/nodes/generate_recommendation.py` - current generation prompt assembly, evidence content re-fetch, membership validation, and fail-open re-fetch behavior. Confidence: HIGH.
- `src/knowledge/citation.py` - explicit membership-only validator. Confidence: HIGH.
- `src/agent/context/assembler.py` and `src/agent/context/projectors.py` - current prompt-safe projection and budget behavior that Phase 22 should reuse but not confuse with RAG ContextBuilder. Confidence: HIGH.
- `src/agent/nodes/assess_risk_and_approval.py` - action snapshot creation and canonical evidence projection dependency. Confidence: HIGH.
- `src/agent/nodes/investigate.py`, `src/agent/routing.py`, `src/agent/nodes/final_response.py` - current retrieval-status routing, business/tool result accumulation, and deterministic final response templates. Confidence: HIGH.
- `src/knowledge/service.py` and `src/knowledge/provenance.py` - verified content/provenance lookup patterns and internal/debug provenance sanitization. Confidence: HIGH.
- `tests/agent/test_memory_evidence_boundary.py` - verified memory cannot satisfy policy evidence/action authority and raw authority payloads are excluded. Confidence: HIGH.
- `tests/knowledge/test_phase21_boundaries.py` - verified Phase 21 provenance is not evidence/action/replay/memory/business authority and Phase 22/23/RAG-5 surfaces were previously excluded. Confidence: HIGH.

## Orchestrator Summary

Phase 22 should be planned as a bounded Reasoning Kernel phase: ContextBuilder validates and budgets current evidence refs, `MaterialClaim` separates policy/business/action support, the verifier fails closed through deterministic routes, and evals prove unsafe answers are refused or escalated. The main roadmap risks are authority collapse, membership-as-support, fail-open verifier behavior, provenance/debug leakage, reranker/query-rewrite scope creep, unbounded Level 3 cost, and evals that miss negative boundary cases.

---
*Pitfalls research for: MOCA v1.5 Phase 22 RAG Context Builder + Hallucination Control*
*Researched: 2026-06-19*
