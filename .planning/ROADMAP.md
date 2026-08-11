# Roadmap: MOCA

## Milestones

- ✅ **v2.1 Core Subsystem Hardening** — Phases 37-60 plus inserted Phase 48.1 (shipped 2026-07-08). Archive: `.planning/milestones/v2.1-ROADMAP.md`
- ✅ **v2.0 Merchant Scope Hardening** — Phase 36 (shipped 2026-06-30). Archive: `.planning/milestones/v2.0-ROADMAP.md`
- ✅ **v1.9 Agent Platform Foundation** — Phases 26-35.1 (shipped 2026-06-30). Archive: `.planning/milestones/v1.9-ROADMAP.md`
- ✅ **v1.8 Intent Routing Safety Hardening** — Phase 25 (shipped 2026-06-21). Archive: `.planning/milestones/v1.8-phases/`
- ✅ Earlier milestones v1.0-v1.7 — archived under `.planning/milestones/`

## Current Planning State

**Active milestone:** v2.2 Product Experience Fixes
**Status:** Phase 64.3 complete with 5/5 plans, clean review, UAT, security, and Nyquist gates; inserted Phase 64.4 is next, followed by Phase 65
**Scope:** Complete the product-experience work and close source-audit gaps across runtime safety, evidence/replay/memory integrity, trace/SSE reliability, operation contracts, reproducible validation, lifecycle/data integrity, LLM runtime ownership, retrieval governance, and service boundaries without weakening accepted v2.1 contracts.

## Current Milestone: v2.2 Product Experience Fixes

**Goal:** Deliver trustworthy product behavior and a maintainable Agent platform by combining the original Console/response improvements with explicit, source-backed hardening phases for every confirmed P1/P2 audit finding.

**Requirements:** `.planning/REQUIREMENTS.md` — the 18 original Phase 61 requirements remain mapped; Phase 62-71 requirements are finalized during their phase planning and must trace to the roadmap criteria below.

### Phase 61: Product Experience Fixes

**Goal:** Fix the concrete Agent Console UX pain points currently known: misleading direct responses, unsupported/clarification wording, scoped business metric questions, timeline presentation, and regression coverage.
**Requirements**: UX-01, UX-02, UX-03, UX-04, MET-01, MET-02, MET-03, MET-04, SCOPE-01, SCOPE-02, SCOPE-03, SCOPE-04, CONSOLE-01, CONSOLE-02, CONSOLE-03, EVAL-01, EVAL-02, EVAL-03
**Depends on:** Phase 60
**Plans:** 5 plans

**Success criteria:**
1. Existing small-talk fix remains covered by regression tests and still never claims policy/RAG evidence or enters business investigation.
2. Unsupported and clarification responses explain the capability boundary, required input, and accepted filters without misleading the user.
3. `business_metric_query` is modeled as one generic metric intent with metric/resource/filter slots, not one intent per metric.
4. Supported MVP metrics include order count, refund count, pending ticket count, coupon issuance count, and merchant refund rate.
5. Metric tools are read-only ToolPlatform declarations backed by trusted tenant and merchant-scope filters, never LLM-generated SQL.
6. Support, manager, and admin metric visibility is enforced from trusted role and merchant scope only.
7. Metric final responses include the number/rate plus scope, filters, and freshness.
8. Agent Console timeline and response surfaces distinguish direct-response, clarification, unsupported, metric, RAG, and tool-call outcomes.
9. Known bad prompts and role/scope metric cases are captured in repeatable UX regression coverage and local validation docs.

Plans:
- [x] 61-01 Agent Response UX Baseline — deterministic small talk, unsupported/clarification wording, and no-false-evidence response baseline.
- [x] 61-02 Metric Contract, Intent, Slots, And Clarification — one generic `business_metric_query` contract with time/metric/scope slots.
- [x] 61-03 Scoped Metric Runtime — read-only `query_business_metric` ToolPlatform integration backed by BusinessFactService and trusted scope.
- [x] 61-04 Agent Graph Metric Integration — route complete metric queries through investigate/tool/final_response and project safe SSE metadata.
- [x] 61-05 Console UX And Regression Validation — timeline polish, Phase 61 golden set, Playwright E2E, and local validation records.

## Next

Phase 64.3 is complete. Next: plan Phase 64.4 Token-Aware Policy Chunking And Reindex Validation with `$gsd-phase-autopilot 64.4` or `$gsd-plan-phase 64.4`; Phase 65 follows Phase 64.4.

### Phase 62: Business Query And Drilldown Foundation

**Goal:** Build a safe, maintainable business-query foundation so scoped aggregate, list, detail, and follow-up drilldown questions can be added without multiplying hardcoded metric/time/status/tool/projection branches.
**Requirements**: TBD during Phase 62 planning.
**Depends on:** Phase 61
**Plans:** 7/7 plans complete

**Success criteria:**
1. Business query time, scope, operation, metric/resource, status, and parser definitions have a single source of truth for the agent/business-query path.
2. A safe `business_query` contract covers aggregate/list/detail/breakdown/compare operations with scoped filters, field allowlists, limits, cursors, sort, and no raw SQL exposure.
3. Runtime read queries are implemented behind `BusinessFactService` and trusted scope/policy gates, not by exposing generic repository list helpers.
4. Multi-turn drilldown uses structured answer context/query context instead of per-slot hardcoded follow-up branches.
5. Projection, final response, regression evals, and console UI safely handle metric/list/detail answers with bounded prompt payloads and no-existence-leak semantics.

Plans:
- [x] 62-01 Query Foundation And Single Source Cleanup — shared time/scope resolvers, operation taxonomy, metric/resource/status/time-preset definitions, and parser consolidation.
- [x] 62-02 Safe Business Query Contract And Schema — accepted `business_query` contract, strict `BusinessQuerySpec`, result/context/cursor models, and metric compatibility mapping.
- [x] 62-03 ToolPlatform Policy And Trusted Scope Boundary — trusted permission mapping, read-only ToolCatalog descriptor, ToolPolicy denial checks, and safe executor boundary.
- [x] 62-04 Business Query Runtime Implementation — controlled aggregate/list/detail/breakdown/compare execution in `BusinessFactService` with scoped repositories and bounded pagination.
- [x] 62-05 Answer Context And Drilldown Flow — `last_query_spec`, `last_answer_context`, result cursor, expected-slot-type parser flow, and aggregate-to-list follow-up revalidation.
- [x] 62-06 Projection, Final Response, API, And Eval — safe backend projection, `business_query_answer` payload, golden/eval coverage, and raw payload stripping.
- [x] 62-07 Agent Console Business Query UI — typed Timeline/Details rendering, operation-specific result display, frontend unit/build checks, and E2E phase gate.

### Phase 63: Safety Taxonomy And Risk Vocabulary

**Goal:** Unify action classification and risk vocabulary across `risk_gate`, `action_draft`, and `intent_policy` so safety routing and execution-side action handling cannot drift.
**Requirements**: TBD during Phase 63 planning.
**Depends on:** Phase 62
**Plans:** 5/5 plans complete

**Success criteria:**
1. `canonical_action_type` and action keyword taxonomy have one owner shared by risk, action draft, and intent policy code.
2. Risk severity and risk disposition are modeled separately instead of overloading one string field.
3. Safety-critical route checks and action execution checks use the same taxonomy and are covered by parity tests.

Plans:
- [x] 63-01-PLAN.md — Taxonomy registry foundation and RED/parity tests.
- [x] 63-02-PLAN.md — Risk gate risk vocabulary and action proposal migration.
- [x] 63-03-PLAN.md — Action draft and ToolPlatform boundary migration.
- [x] 63-04-PLAN.md — Intent policy and routing taxonomy/registry migration.
- [x] 63-05-PLAN.md — Drift guards, architecture-debt updates, and closeout verification.

**Closeout:** code review clean after one fixed warning, UAT 5/5 passed, `threats_open: 0`, and `nyquist_compliant: true`.

### Phase 64: RAG Risk Label Unification

**Goal:** Unify RAG risk labels across context builder, metrics, verifier, semantic routing, and tests so labels such as `manual_review_sensitive`, `conflict`, and `stale_evidence` keep the same meaning across the RAG pipeline.
**Requirements**: TBD during Phase 64 planning.
**Depends on:** Phase 63
**Plans:** 4/4 plans complete

**Success criteria:**
1. RAG risk labels have a single source of truth consumed by builder, metrics, verifier, and routing.
2. Existing labels keep compatible semantics or receive an explicit migration note.
3. Parity tests prevent future label-set drift.

Plans:
- [x] 64-01-PLAN.md — RAG risk label registry foundation.
- [x] 64-02-PLAN.md — ContextBuilder and recommendation-generation migration.
- [x] 64-03-PLAN.md — Verifier, routing, and metrics migration.
- [x] 64-04-PLAN.md — Drift guards, architecture-debt updates, and focused validation.

**Closeout:** code review clean, UAT 4/4 passed, `threats_open: 0`, and `nyquist_compliant: true`.

### Phase 64.1: Runtime Safety And Approval Contract Repair (INSERTED)

**Goal:** Repair the confirmed cross-layer safety breaks between recommendation generation, deterministic risk evaluation, approval APIs, frontend approval handling, and auto-allowed action drafting so every actionable recommendation is normalized, risk-classified, authorized, and auditable before it can reach an action draft or a successful final response.
**Requirements**: SC-64.1-1, SC-64.1-2, SC-64.1-3, SC-64.1-4, SC-64.1-5
**Depends on:** Phase 64
**Plans:** 6/6 plans complete

**Audit findings owned:** Chinese/English actionable recommendations can bypass action claims and `risk_gate`; medium-risk rules disappear in fallback and can become low/auto-allowed; the frontend approval payload cannot satisfy the backend decision schema; normal auto-allowed runs lack a narrowly authorized draft capability; action-draft failures can be hidden by a successful final response.

**Scope boundaries:** This phase owns actionable-recommendation canonicalization, deterministic risk-rule parity and fail-closed fallback, the versioned approval decision contract across backend/API/SSE/frontend, narrowly bound auto-action capability issuance, and end-to-end safety-route verification. It does not redesign the general operation/tool gateway assigned to Phase 66, centralize provider/model policy assigned to Phase 69, change evidence/memory semantics assigned to Phase 64.2, or add a production external side-effect executor.

**Success criteria:**
1. Every actionable recommendation, including Chinese and English variants, resolves through the canonical action taxonomy before material-claim generation and routing; node-local keyword sets no longer decide whether risk or approval handling runs.
2. One deterministic backend rule model evaluates configured high-, medium-, and low-risk rules; invalid, timed-out, unavailable, or schema-invalid LLM risk output cannot downgrade risk and falls closed to manual review or required approval.
3. Approval list/get/SSE/decide flows share one versioned decision-context contract containing the required decision type, lifecycle versions, revision, and integrity hashes; the frontend can construct a valid request from returned data and stale or mismatched decisions fail closed.
4. Auto-allowed draft creation uses only a server-minted capability bound to trusted tenant, actor, run, canonical action, payload hash, risk decision, merchant scope, and permitted draft handler; it cannot broaden general tool permissions.
5. End-to-end safety-matrix tests prove canonicalization -> claim verification -> deterministic risk -> approval or trusted auto-allow -> action draft behavior, and prove denied, stale, malformed, unsupported, or draft-failure paths cannot report successful completion or create a draft.

Plans:
- [x] 64.1-01-PLAN.md — Canonical action candidate and fail-closed routing
- [x] 64.1-02-PLAN.md — Deterministic risk rule parity and fallback
- [x] 64.1-03-PLAN.md — Versioned approval decision contract across backend/API/SSE/frontend
- [x] 64.1-04-PLAN.md — Durable bounded auto-action capability
- [x] 64.1-05-PLAN.md — Conditional post-draft terminal integrity
- [x] 64.1-06-PLAN.md — End-to-end matrix, architecture guards, and closeout gates

**Closeout:** 6/6 plans complete; phase verification 20/20, automated UAT 7/7, code-review findings 3/3 fixed, `threats_open: 0`, and `nyquist_compliant: true` on 2026-08-04.

### Phase 64.2: Evidence Identity Immutable Replay And Memory Provenance (INSERTED)

**Goal:** Make evidence, replay, Case Working Context, and memory identity trustworthy across ingestion, retrieval, agent projection, persistence, review, and replay so failed observations cannot become verified facts and historical decisions can be reconstructed from immutable, canonically identified source material.
**Requirements**: SC-64.2-1, SC-64.2-2, SC-64.2-3, SC-64.2-4, SC-64.2-5
**Depends on:** Phase 64.1
**Plans:** 11/11 plans complete

**Audit findings owned:** Failed or denied tool summaries can enter CWC `verified_facts`; evidence IDs are not recomputed at trust boundaries; re-ingestion replaces old evidence rows while replay stores only mutable refs; session-memory candidate hashes have multiple algorithms; reviewed case-memory refs lose real scope/status/provenance; duplicate and expired pending memory lifecycle behavior lacks enforceable invariants.

**Scope boundaries:** This phase owns verified-fact promotion rules, canonical evidence identity validation, immutable evidence/document/chunk version references required for replay, one shared memory-candidate identity algorithm, reviewed-memory scope/status/provenance preservation, and correctness-critical duplicate/pending-review lifecycle handling. It does not optimize embedding recall or reranking, redesign PII vocabulary governance assigned to Phase 70, redesign operation dispatch assigned to Phase 66, or perform the broad AgentState/service decomposition assigned to Phase 71.

**Success criteria:**
1. Only successful authoritative tool or retrieval results with validated canonical references can enter CWC `verified_facts`; unavailable, denied, stale, malformed, partial, and error observations remain typed observations/errors and cannot enter reviewed case memory.
2. Evidence identity has one canonical computation and validation path shared by ingestion, retrieval, agent state, APIs, memory, and replay; forged or mismatched aliases are rejected without existence leakage.
3. Replay references resolve the exact immutable document, chunk, evidence content, version, scope, and integrity hash used by the original run after re-ingestion, correction, supersession, or tombstoning, with migration/backfill and compatibility reads covered.
4. Memory candidate hashing has one owner consumed by nodes, services, events, stores, deduplication, and review flows; reviewed records preserve real tenant/merchant scope, source status, review decision, source/run provenance, and correction lineage.
5. Database constraints, idempotent writes, and lifecycle tests prevent concurrent duplicate candidates or reviews and define deterministic expiry, rejection, correction, and tombstone behavior for stale pending records without silently merging distinct identities.

Plans:
- [x] 64.2-01-PLAN.md — Canonical Evidence Identity Owner And Additive Immutable Schema (`depends_on: []`).
- [x] 64.2-02-PLAN.md — Dual-Write Evidence Cutover Watermarked Backfill And Canonical Retrieval (`depends_on: [64.2-01]`).
- [x] 64.2-03-PLAN.md — Shared Memory Candidate Identity Owner (`depends_on: []`).
- [x] 64.2-04-PLAN.md — Approval Snapshot Canonical Evidence Validation (`depends_on: [64.2-02]`).
- [x] 64.2-05-PLAN.md — Typed CWC Authoritative Fact Promotion (`depends_on: [64.2-02]`).
- [x] 64.2-06-PLAN.md — Production Evidence Event Binding And Exact Replay Resolution (`depends_on: [64.2-02]`).
- [x] 64.2-07-PLAN.md — Reviewed Case-Memory Canonical Provenance (`depends_on: [64.2-03, 64.2-05]`).
- [x] 64.2-08-PLAN.md — Exact-Identity Memory Lifecycle And Concurrency (`depends_on: [64.2-03, 64.2-07]`).
- [x] 64.2-09-PLAN.md — Cross-System Integrity Guards And Initial Closeout (`depends_on: [64.2-04, 64.2-05, 64.2-06, 64.2-08]`).
- [x] 64.2-10-PLAN.md — Canonical RAG Combined-Status Fixture Repair (`depends_on: [64.2-09]`).
- [x] 64.2-11-PLAN.md — Approval Fixture Rollout State And Final Regression Gate (`depends_on: [64.2-10]`).

**Closeout:** 11/11 plans and 26/26 executable tasks complete; final 82-file code review clean after four accepted warnings were fixed; automated backend UAT has 0 issues/0 blocked; `4462 passed, 4 skipped`; `threats_open: 0`; `nyquist_compliant: true` on 2026-08-06.

### Phase 64.3: RAG Format Parity And Document Quality Evaluation (INSERTED)

**Goal:** Use three canonical policies and their Markdown, digital-PDF, and scanned-PDF variants to establish a reproducible parser and retrieval format-parity baseline through the existing production parser, ingestion, and retrieval paths without changing production RAG behavior.
**Requirements**: ROADMAP-SC-1, ROADMAP-SC-2, ROADMAP-SC-3, ROADMAP-SC-4, ROADMAP-SC-5
**Depends on:** Phase 64.2
**Plans:** 5/5 plans complete

**Confirmed gaps owned:** The existing RAG evaluator and golden cases do not measure equivalent content across formats; parser quality, retrieval quality, and evidence-location quality are not independently scored; repeated retrieval-parity rounds do not yet have an explicit reset contract; and there is no reproducible baseline report that attributes failures to parsing, chunking, retrieval, or provenance.

**Scope boundaries:** This phase owns format-parity manifests and Gold evidence anchors, direct parser evaluation, isolated round-based retrieval evaluation, evaluation-only reset safety, and reproducible baseline/report gates. It does not redesign or tune the production parser, chunker, embeddings, hybrid retrieval, reranker, `ContextBuilder`, or claim verifier; add parent-child chunking or complex-table enhancements; build a 20-30-document mixed corpus; add DOCX/XLSX/PPTX parity; or introduce domain-specific terminology.

**Success criteria:**
1. One validated manifest/Gold contract describes exactly three canonical policy groups and nine Markdown/digital-PDF/scanned-PDF variants, with format-independent fact and evidence anchors rather than generated chunk IDs.
2. A direct parser-parity evaluator runs all nine fixtures without tenant, database, embedding, or retrieval dependencies and reports content fidelity, structural preservation, provenance/location coverage, OCR diagnostics, and actionable per-case failures.
3. A provider-backed retrieval-parity evaluator uses a fixed evaluation tenant and logical `doc_key`, ingests one equivalent format per round, fully resets evaluation-owned state between rounds, reuses identical questions, and reports Hit@1/3/5, MRR, anchor coverage, fallback coverage, and locator coverage.
4. A versioned baseline report records manifest/Gold hashes plus parser, OCR, embedding, retrieval, and reranker configuration; reports results by format and case; and separates parser failures from chunking, retrieval, and provenance failures. A truthful reproducible failing baseline is an acceptable phase result and drives later targeted work.
5. Existing production RAG contracts and behavior remain unchanged, evaluation cleanup cannot affect non-evaluation tenants or data, and focused plus existing RAG regression gates pass.

Plans:
- [x] 64.3-01-PLAN.md — Contract And Semantic Gold (`depends_on: []`).
- [x] 64.3-02-PLAN.md — Direct Parser Parity Evaluator (`depends_on: [64.3-01]`).
- [x] 64.3-03-PLAN.md — Retrieval Round Isolation And Provider Runtime (`depends_on: [64.3-01]`).
- [x] 64.3-04-PLAN.md — Canonical Reporting And Provider Baseline (`depends_on: [64.3-02, 64.3-03]`).
- [x] 64.3-05-PLAN.md — Final Regression Documentation And Ledgers (`depends_on: [64.3-04]`).

**Closeout:** 5/5 plans and 12/12 executable tasks complete; final deep code review clean after 11 accepted findings were fixed across two repair iterations; automated UAT 5/5 passed; `threats_open: 0`; `nyquist_compliant: true`; focused 143 tests and expanded 442 tests passed on 2026-08-10. The canonical provider baseline is intentionally `completed_quality_fail` and remains the truthful input to Phase 64.4 and owner-named parser/ingestion and retrieval follow-ups.

### Phase 64.4: Token-Aware Policy Chunking And Reindex Validation (INSERTED)

**Goal:** Replace character-count policy chunk sizing with a versioned tokenizer-aware assembly path that measures the final `text-embedding-v4` input while preserving parser structure, provenance, evidence identity, deterministic rebuilds, and safe rollback, then prove the change against the Phase 64.3 format-parity baseline.
**Requirements**: SC-64.4-1, SC-64.4-2, SC-64.4-3, SC-64.4-4, SC-64.4-5, SC-64.4-6
**Depends on:** Phase 64.3
**Plans:** 14 plans

**Confirmed gaps owned:** Production `chunk_blocks` and legacy `chunk_markdown` enforce character budgets rather than embedding-model token budgets; final embedding text adds title, section, and source context only after chunking; dry-run/golden validation and production ingestion do not share one authoritative chunk path; chunker/tokenizer configuration and per-chunk token counts are not persisted; and a rechunk/re-embedding rollout must preserve the immutable evidence/replay contract established by Phase 64.2.

**Scope boundaries:** This phase owns the embedding-tokenizer/counting contract and parity check, token-aware block/table/oversized/overlap assembly over the final embedding input, convergence of production/dry-run/golden chunk behavior, chunker/tokenizer configuration provenance, evidence/version compatibility, isolated reindex/cutover/rollback, and A/B evaluation against Phase 64.3. It does not add an LLM policy-clause classifier or parent-child chunking; redesign production parsers, hybrid retrieval, RRF, reranking, `ContextBuilder`, or claim verification; replace the embedding model; or migrate Agent prompt budgets to the generation-model tokenizer owned by Phase 69.

**Success criteria:**
1. One versioned model-to-tokenizer contract provides deterministic offline counts for the configured embedding model and has a provider-backed parity check against reported usage without exposing credentials or production text.
2. Every final embedding input, including title, section, table headers, overlap, and allowed source context, stays within the configured token maximum; existing structural/provenance boundaries remain intact and identical source plus configuration produces identical chunks.
3. Production ingestion, dry-run, and golden validation consume one authoritative chunk assembly contract, with regression coverage for Chinese, English, mixed text, long unpunctuated text, tables, OCR content, URLs, numbers, and tokenizer failure behavior.
4. Chunker/tokenizer/model versions and actual token counts are auditable, and rechunking cannot silently reuse incompatible policy/chunk/evidence identity or break historical replay semantics established by Phase 64.2.
5. Reindexing is isolated, resumable, and rollback-safe so failures preserve the prior usable index and no tenant observes a partially mixed old/new corpus.
6. A versioned A/B report compares character- and token-aware candidates on Phase 64.3 Hit@1/3/5, MRR, anchor/locator coverage, format parity, duplicate rate, chunk count, latency, and embedding token cost; the selected configuration satisfies explicit non-regression gates and existing RAG tests pass.

Plans:
- [x] 64.4-01-PLAN.md — Pinned Tokenizer Contract And Assets (`depends_on: []`).
- [x] 64.4-02-PLAN.md — Exact Final Input Token Chunker (`depends_on: [64.4-01]`).
- [x] 64.4-03-PLAN.md — Provider Usage And Immutable Parity Protocol (`depends_on: [64.4-02]`).
- [x] 64.4-04-PLAN.md — Production Dry Run Golden And A-B Convergence (`depends_on: [64.4-03]`).
- [x] 64.4-05-PLAN.md — Corpus Schema Bootstrap And Source Identity (`depends_on: [64.4-04]`).
- [x] 64.4-06-PLAN.md — Active Corpus Paths And Immutable Bindings (`depends_on: [64.4-05]`).
- [x] 64.4-07-PLAN.md — Authoritative Snapshot Reindex Build And Resume (`depends_on: [64.4-06]`).
- [x] 64.4-08-PLAN.md — Atomic Pointer Activation And Ingestion Continuity (`depends_on: [64.4-07]`).
- [x] 64.4-09-PLAN.md — Exact A-B Runtime And Immutable Selection (`depends_on: [64.4-08]`).
- [x] 64.4-10-PLAN.md — Activation Receipts And Bounded Initial Live Evidence (`depends_on: [64.4-09]`).
- [ ] 64.4-11-PLAN.md — Role Failure Provenance And Safe Diagnostic Artifacts (`depends_on: [64.4-10]`).
- [ ] 64.4-12-PLAN.md — Guarded Live Selection Recovery (`depends_on: [64.4-11]`).
- [ ] 64.4-13-PLAN.md — Reversible Activation Drill And Closeout Guard (`depends_on: [64.4-12]`).
- [ ] 64.4-14-PLAN.md — Final Documentation Ledgers And Regression Closeout (`depends_on: [64.4-13]`).

### Phase 65: Trace Event And Console Label Consistency

**Goal:** Make runtime observability trustworthy end to end: canonical trace/event vocabulary must match what production nodes actually emit, persist, replay, project through SSE/API, and render in the Console, while failures are redacted and database/event lifecycles remain bounded.
**Requirements**: TBD during Phase 65 planning.
**Depends on:** Phase 64.4
**Plans:** 0 plans

**Audit findings owned:** LLM event types are registered but production calls do not emit them; two SSE paths expose raw exceptions; long streams retain request-scoped DB sessions; audit/event persistence failures can be silently discarded; backend/replay/DB/frontend labels remain separate facts.

**Scope boundaries:** This phase owns trace/SSE/runtime audit reliability and label parity. It may instrument current LLM call sites, but it does not redesign operation dispatch (Phase 66), CI/config profiles (Phase 67), lifecycle/relational constraints (Phase 68), or provider/model/retry policy in the central LLM gateway (Phase 69).

**Success criteria:**
1. Trace event types, node/tool/safe-reason/response-kind labels, DB constraints, replay validators, API projections, and frontend labels have one canonical ownership model plus parity or migration tests.
2. Every production LLM call path emits correlated `llm_call_started`, `llm_call_completed`, or `llm_call_failed` events with redacted metadata and available timing, model, and usage fields; registry-only placeholders are insufficient.
3. SSE and streaming error envelopes expose stable safe reason codes and request IDs, never raw exceptions, provider/SQL details, credentials, secrets, or internal object representations.
4. Long-running LLM/SSE work does not hold a request-scoped DB transaction or connection for the entire stream; persistence uses explicit short lifecycle boundaries covered by interruption/error tests.
5. Tool, action, approval, and lifecycle event-persistence failures have explicit reliability semantics; safety/audit-critical events cannot be silently discarded, and intentional best-effort diagnostics are named, bounded, and observable.
6. Console Timeline/Details renders canonical and unknown future labels safely, preserves historical-event readability, and never infers security meaning from display text.
7. Backend integration, replay, SSE-contract, and frontend tests prove emitted -> persisted -> projected -> rendered parity for success, denial, interruption, timeout, and failure paths.

Plans:
- [ ] TBD (run /gsd-plan-phase 65; expected slices: event/label ownership, production LLM emission, safe SSE/session lifecycle, audit reliability, and backend/frontend parity gates)

### Phase 66: Unified Operation Contract And Tool Gateway

**Goal:** Replace planner-visible concrete-tool coupling with versioned, typed operation contracts whose backend-owned registry dispatches only supported business, knowledge, and action capabilities through existing permission, scope, safety, projection, audit, and replay boundaries.
**Requirements**: TBD during Phase 66 planning.
**Depends on:** Phase 65
**Plans:** 0 plans

**Audit findings owned:** The planner returns concrete tool strings; planner/catalog/event/policy/frontend names have multiple owners; BusinessQuery advertises schema-valid runtime-impossible operation/resource pairs; KnowledgeSearch exposes filters the runtime ignores or narrows; refund actions can be persisted through a coupon-named capability; legacy metric calculation remains as a second business-rule truth.

**Scope boundaries:** This phase owns operation/capability truth and compatibility migration. It does not add production external side effects, expand the product surface merely to satisfy a registry, centralize LLM provider/runtime policy (Phase 69), or perform broad state/service decomposition (Phase 71).

**Success criteria:**
1. A canonical versioned operation registry owns every operation ID, family, typed input/output schema, runtime-enabled status, handler, permission/scope policy, risk/approval policy, projection, and event/replay identity.
2. LLM/planner-facing choices use typed operation specs rather than ad hoc concrete tool names wherever an operation family exists; any remaining visible compatibility tool is individually justified and parity-tested.
3. Every advertised operation/resource/filter combination has a registered runtime compiler or handler, and every handler is either advertised or explicitly backend-only; schema-valid/runtime-impossible requests fail the parity gate.
4. BusinessQuery and KnowledgeSearch expose only filters, sorts, fields, and operation/resource pairs the backend enforces; schema-only capability claims are implemented or removed.
5. Canonical action types map to semantically correct capabilities and permissions; refund actions no longer masquerade as coupon-grant operations, while drafting and external execution remain separate safety boundaries.
6. Dispatch remains fail-closed through trusted scope, permissions, schema validation, side-effect/approval/snapshot/idempotency gates, safe projection, audit, and replay; no raw-SQL, generic repository, or arbitrary-call executor is exposed to the LLM.
7. Legacy tool names and duplicate metric paths receive explicit compatibility/deprecation or removal treatment that preserves historical audit/replay readability and prevents a second business-rule source of truth.

Plans:
- [ ] TBD (run /gsd-plan-phase 66; expected slices: operation registry, business/knowledge capability parity, action capability mapping, compatibility migration, and end-to-end policy/projection/replay gates)

### Phase 67: Dev Test And Config Hygiene

**Goal:** Make the repository reproducibly verifiable in CI and local development, with explicit environment profiles and safe production startup guards instead of hidden localhost, demo, credential, fixture, or frontend assumptions.
**Requirements**: TBD during Phase 67 planning.
**Depends on:** Phase 66
**Plans:** 0 plans

**Audit findings owned:** CI has no PostgreSQL/pgvector service and no frontend gate; DB-dependent tests assume a local privileged database; an architecture guard rejects legal current dependencies; Docker/install inputs are not fully pinned; demo authentication and default secrets are unsafe outside the declared local-demo profile.

**Scope boundaries:** This phase owns reproducible validation and environment/config hygiene. It does not choose a production hosting platform, provision a cloud secret manager, rewrite business behavior, redesign schemas unrelated to validation, or absorb operation/state/service-boundary work owned by Phases 66, 68, and 71.

**Success criteria:**
1. CI provisions the required PostgreSQL extensions/database, runs migrations, and executes backend tests only through `uv run ...` or a verified repository `.venv`, never bare system Python/pytest.
2. CI includes deterministic frontend install plus lint, type/build, unit, and bounded API/Console contract or E2E smoke gates; frontend regressions cannot ship behind backend-only green checks.
3. Architecture tests describe current intended boundaries precisely and fail on real forbidden dependencies, not legal broad-prefix imports; obsolete guards are migrated with source-backed rationale.
4. Dev/test/demo/production profiles have explicit ownership, and non-demo startup rejects default JWT secrets, passwordless demo-token access, unsafe credentials, or other demo-only security defaults.
5. Database URLs, ports, frontend API URLs, origins, model/investigate limits, retention values, and similar settings have documented override paths and no conflicting duplicate owners.
6. Repeated magic dates, tenant/business identifiers, and demo fixtures use shared deterministic factories/constants where this reduces brittleness without hiding test intent.
7. Docker/local onboarding and CI use compatible pinned setup and validation commands, with a clean-environment artifact proving the documented workflow works from scratch.

Plans:
- [ ] TBD (run /gsd-plan-phase 67; expected slices: self-contained backend CI, frontend/contract gates, architecture-test repair, environment security profiles, and reproducible local/Docker validation)

### Phase 68: State Machine Registry And DB Constraint Hardening

**Goal:** Give lifecycle states and tenant-owned relationships enforceable canonical contracts across service, database, API, replay, and frontend surfaces, with safe migrations for state, foreign-key, uniqueness, and soft-delete lifecycle drift.
**Requirements**: TBD during Phase 68 planning.
**Depends on:** Phase 67
**Plans:** 0 plans

**Audit findings owned:** Lifecycle values are distributed strings; state parity is not enforced across service/DB/API/replay/frontend; tenant-parent consistency relies on repository convention; tenant-owned business identifiers are globally unique; soft-delete and sequence/index uniqueness can conflict with future records.

**Scope boundaries:** This phase owns lifecycle-state and relational-integrity hardening. It does not redesign immutable evidence/replay or memory provenance already owned by Phase 64.2, implement memory retrieval quality (Phase 70), decompose AgentState/services (Phase 71), or introduce new product lifecycle states without separate requirements.

**Success criteria:**
1. AgentRun, ActionDraft, Approval, memory, replay, and other in-scope lifecycle values and allowed transitions have canonical registry/schema owners consumed by every service writer.
2. Service transitions, API schemas, frontend types/rendering, replay validators, and tests remain in parity; adding a state or transition without every required consumer fails a guard.
3. Safe DB CHECK constraints and migration-backed transition/invariant tests enforce high-risk state fields with explicit compatibility treatment for historical/demo-only values.
4. Audited tenant-parent relationships, including order/refund/ticket and knowledge/memory children, use tenant-consistent composite keys/FKs or an equivalently enforceable DB invariant rather than repository convention alone.
5. Tenant-owned external/business identifiers use tenant-scoped uniqueness where reuse is valid, with migration preflight scans/backfills that fail safely on contaminated or ambiguous rows.
6. Soft-delete/tombstone rows and sequence/index uniqueness have an explicit lifecycle so deleted history remains auditable without blocking legitimate future records or silently reusing conflicting identities.
7. Migration, rollback/compatibility, DB-backed repository, cross-tenant negative, API, replay, and frontend tests prove invalid states and cross-tenant relationships are rejected without breaking historical reads.

Plans:
- [ ] TBD (run /gsd-plan-phase 68; expected slices: lifecycle registry, cross-surface parity, DB state constraints, tenant relational integrity, uniqueness/soft-delete migrations, and DB/API/replay/frontend gates)

### Phase 69: LLM Runtime Gateway And Observability

**Goal:** Replace node-local LLM client construction with one backend-owned runtime gateway so model selection, structured-output invocation, timeout, retry, fallback, usage accounting, safe failure handling, and trace emission follow one testable contract across all Agent nodes.
**Requirements**: TBD during Phase 69 planning.
**Depends on:** Phase 68
**Plans:** 0 plans

**Audit findings owned:** Multiple nodes construct provider clients locally; model/timeout/retry/fallback policy is scattered; production LLM events lack a central emitter; usage/cost and cancellation are not consistently observable; provider failures can interact differently with safety-critical callers.

**Scope boundaries:** This phase owns production LLM invocation policy and observability for Agent nodes. It does not redesign prompts/business policy, tool/operation dispatch (Phase 66), memory ranking (Phase 70), or grant models authority over permissions, risk disposition, approval, or execution.

**Success criteria:**
1. Production Agent nodes no longer construct provider clients locally; one composition/runtime boundary creates clients and injects an explicit interface.
2. Each LLM call purpose has a typed policy for provider/model, structured-output schema, temperature, timeout, bounded retry, fallback eligibility, and token/cost budget.
3. Every production invocation emits correlated started/completed/failed events with run/node/call identity, model, latency, usage, and safe reason fields compatible with replay and Console projections.
4. Safety-critical calls fail closed when providers time out, structured output is invalid, or allowed fallbacks fail; retry/fallback cannot turn unknown decisions into allow/low-risk outcomes.
5. Raw prompts, credentials, provider payloads, sensitive data, and unrestricted outputs are excluded from logs/events by default, with explicit bounded diagnostics where needed.
6. Development/demo/production runtime configuration is validated; unsupported provider/model combinations and insecure production defaults fail at startup.
7. Provider-independent tests cover success, timeout, malformed structured output, bounded retry, allowed/forbidden fallback, usage accounting, redaction, cancellation, and event parity without live network access.

Plans:
- [ ] TBD (run /gsd-plan-phase 69; expected slices: runtime interface/composition, call-purpose policies, event/usage observability, fail-closed fallback, config/redaction, and provider-independent tests)

### Phase 70: Memory Retrieval Quality And Governance

**Goal:** Make reviewed memory retrieval accurate, explainable, and lifecycle-safe by unifying retrieval contracts, metadata/text/vector behavior, filters, ranking, diagnostics, PII vocabulary, and tombstone enforcement without widening memory into policy, business-fact, approval, action, or replay authority.
**Requirements**: TBD during Phase 70 planning.
**Depends on:** Phase 69
**Plans:** 0 plans

**Audit findings owned:** Production case-memory retrieval does not use the available vector path; advertised filters can be ignored or narrowed; lexical fallbacks lack corresponding indexing; PII markers, terminology, and tombstone lifecycle rules have multiple owners; retrieval quality and false positives lack a deterministic evaluation owner.

**Scope boundaries:** This phase owns long-term preference and reviewed case-memory retrieval, query embedding, hybrid ranking, filter parity, prompt-safe projection, diagnostics/evals, PII vocabulary, and tombstone exclusion. It does not redo evidence/replay identity or candidate-hash fixes from Phase 64.2, auto-approve memories, create new authority classes, or substitute memory for canonical policy/business facts.

**Success criteria:**
1. Long-term and case-memory retrieval use typed request/result contracts whose advertised filters are enforced by runtime queries, with parity tests preventing schema-only or ignored filters.
2. Query embeddings are generated and used when vector retrieval is enabled; deterministic metadata/text fallback remains available, and similarity never replaces tenant/scope/review/expiry/tombstone gates.
3. Hybrid candidate generation and reranking have bounded top-k, thresholds, tie-breaking, prompt limits, and diagnostics explaining which path and filters produced each memory.
4. Retrieval enforces trusted tenant/scope, memory kind/source, approved review status, non-expired state, PII policy, and active tombstone/deletion rules across text, vector, cached, and fallback paths.
5. Prompt-facing projections preserve canonical identity and provenance while keeping memory contextual-only and unable to become verified evidence, policy authority, approval authority, or executable action input.
6. PII patterns, memory terminology, tombstone vocabulary, and retrieval exclusion reasons have canonical owners or generated parity guards rather than divergent service/API/test copies.
7. A deterministic evaluation suite measures relevant-hit coverage, false positives, no-result behavior, scope isolation, tombstone exclusion, vector-unavailable fallback, and bounded latency/query cost.

Plans:
- [ ] TBD (run /gsd-plan-phase 70; expected slices: contract/filter parity, embedding/hybrid retrieval, ranking/diagnostics, lifecycle/PII/tombstone governance, prompt-safe projection, and deterministic evaluation)

### Phase 71: Agent State And Service Boundary Decomposition

**Goal:** Decompose the oversized Agent state and orchestration modules into typed lifecycle-owned state slices and explicit application/domain boundaries so graph behavior, reset/merge rules, dependency direction, persistence, and API/SSE responsibilities remain understandable and independently testable.
**Requirements**: TBD during Phase 71 planning.
**Depends on:** Phase 70
**Plans:** 0 plans

**Audit findings owned:** `AgentState` mixes durable and ephemeral state with many opaque dictionaries; `investigate` mixes planning, tool dispatch, business-query drilldown, result normalization, and conversation concerns; agent-run routes mix HTTP/SSE/graph/persistence/finalization; route-bearing modules across `src/api/routers/` can directly construct repositories, retrieval engines, adapters, or domain services and therefore blur transport, transaction, persistence, and business ownership; knowledge, memory, and actions domains import Agent implementation concerns, including Agent-owned event and run-scope helpers from the actions service; several services have unclear ownership boundaries.

**Scope boundaries:** This phase owns state lifecycle ownership, typed substate/view contracts, node adapters, graph merge/reset rules, investigate decomposition, agent-run lifecycle separation, a complete ownership audit and boundary decision for every route-bearing module under `src/api/routers/`, repair of Actions-to-Agent reverse dependencies, dependency direction, and characterization/architecture tests. Router work is limited to moving domain, persistence, retrieval, lifecycle, and composition responsibilities behind explicit application/domain services or documenting a source-backed transport-only exception; it does not redesign endpoint behavior. This phase does not add product features, new intents/tools, change safety semantics, replace LangGraph, or silently change public/checkpoint/replay contracts without explicit migration.

**Mandatory module responsibility matrix:** Before implementation, Phase 71 must inventory `src/agent/state.py`, `src/agent/nodes/investigate.py`, `src/api/routers/agent_runs.py`, `src/business/service.py`, `src/agent/nodes/risk_gate.py`, `src/agent/nodes/final_response.py`, `src/knowledge/service.py`, `src/memory/case_memory.py`, `src/actions/service.py`, and `src/db/models.py`. For each module, the matrix must record current responsibilities, canonical owners, allowed dependency direction, and a source-backed `KEEP`, `SPLIT`, `MOVE`, `DELETE`, or named-phase `DEFER` decision. In addition, a mandatory API-router ownership ledger must cover every module under `src/api/routers/` that registers routes, including routers added while the phase is in progress; for each endpoint it must record transport-only responsibilities, direct session/repository/retrieval-engine/adapter/service construction, domain or lifecycle decisions, transaction ownership, the target application/domain service or port, and a source-backed `KEEP_AS_TRANSPORT`, `THIN`, `MOVE_TO_SERVICE`, or named-phase `DEFER` decision. File length alone is not a split criterion; confirmed multi-owner authority or unreviewed direct infrastructure access without an explicit retained-boundary rationale is not acceptable.

**Success criteria:**
1. Every AgentState field has one documented lifecycle, writer, reader/router set, reset/merge rule, persistence target, and canonical type; guards fail on unregistered keys or undocumented aliases.
2. High-churn state domains use typed substate/view contracts and explicit adapters instead of arbitrary whole-state dictionaries while trusted identity/permissions remain sourced from run configuration.
3. Each node declares and tests its required input view and bounded output patch; turn/run reset, checkpoint restoration, parallel merge, and terminal persistence behavior are covered.
4. `investigate` is separated into bounded planner/orchestrator, business-query/drilldown, tool-result normalization, and terminal-decision components without changing the approved read-only loop or ToolPlatform policy gates.
5. Agent-run HTTP handling, SSE projection, graph coordination, lifecycle persistence, and terminal finalization have explicit ownership so streaming does not control domain transactions or duplicate completion logic.
6. Every route-bearing module under `src/api/routers/` is covered by the API-router ownership ledger; domain rules, lifecycle transitions, repository/retrieval/adapter construction, and transaction ownership move behind explicit application/domain service methods unless a source-backed transport-only exception is recorded, and architecture guards fail when a new or changed router introduces unreviewed direct infrastructure access.
7. Dependency rules prevent business, knowledge, memory, actions, safety, and tool domains from importing Agent node/router/event/run-scope implementation details. In particular, `src/actions/service.py` consumes neutral owned contracts or injected event/scope ports instead of `src.agent.events` or `src.agent.run_scope`; a composition root wires application ports to adapters and architecture tests enforce the direction.
8. Characterization/compatibility tests prove unchanged graph topology/routing, approval resume, action safety bindings, SSE/API payloads, replay/checkpoint identity, and user-visible responses before legacy paths or state aliases are removed.
9. The mandatory module responsibility matrix and API-router ownership ledger cover every audit-named high-complexity module and every route-bearing API module, leaving no confirmed multi-owner module or router-owned domain/infrastructure responsibility without an implemented boundary decision or an explicit named-phase deferral with evidence, remaining risk, and a verification entry point.

Plans:
- [ ] TBD (run /gsd-plan-phase 71; expected slices: mandatory module responsibility matrix and all-router ownership ledger, state inventory/contracts, typed views/node patches, investigate and service decomposition, API/SSE lifecycle separation and router thinning, Actions reverse-dependency repair, dependency-direction enforcement, and compatibility/characterization gates)

---

## Last Completed Milestone: v2.1 Core Subsystem Hardening

**Status:** shipped 2026-07-08
**Scope:** Phases 37-60 plus inserted Phase 48.1
**Plans:** 87/87 complete
**Requirements:** 24/24 complete
**Audit:** `.planning/milestones/v2.1-MILESTONE-AUDIT.md` — `passed` / `archive_ready`

**Delivered:**

- Consolidated ToolPlatform declarations, runtime output-schema validation, failure handling, policy gates, and legacy manager cleanup.
- Decoupled intent recognition and preserved multi-intent utterances through bounded `TaskPlan` semantics without weakening the single-intent route contract.
- Rebuilt memory layering around Case Working Context, thread-case M:N linkage, session-context boundaries, reviewed case precedent generation, explicit preference-only long-term memory, and memory compatibility cleanup.
- Migrated `investigate` to a bounded read-only ReAct loop and completed the canonical 15-node Agent Graph cutover with legacy runtime route/name cleanup.
- Aligned recommendation/RAG claim fail-closed behavior, canonical `risk_gate`/`approval_gate` behavior, and approval-resume terminal memory finalization.
- Closed archive evidence gaps with formal verification, Nyquist validation, UAT, security signoff, and a passed v2.1 milestone audit.

**Accepted follow-ups:**

- Phase 49 bounded ReAct replay parent-operation identity remains an accepted limitation for a future replay/event hardening milestone if needed.
- Historical legacy graph-name references remain accepted only as historical/test/documentation refs after Phase 58 cleanup.
- Legacy `/api/v1/agent/chat` background `memory_write` compatibility remains outside the current `agent-runs` frontend lifecycle.
- GSD tooling/reporting debt: `gsd-sdk query init.milestone-op` can report missing legacy audit agents even when the main orchestrator can run `gsd-integration-checker`.
