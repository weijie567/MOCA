# MOCA — Merchant Operations Collaborative Agent

## What This Is

A production-grade AI agent for e-commerce/local-life platforms that helps merchants and support staff handle refund disputes, rule inquiries, and compensation decisions. It integrates with business systems (orders, refunds, tickets, coupons), retrieves evidence from a knowledge base, and enforces approval workflows for high-risk actions — all with full audit trails.

Built as an open-source portfolio project demonstrating enterprise Agent engineering and product thinking for AI/Agent engineer and product manager roles at top-tier internet companies.

## Core Value

When a merchant or support agent asks about a refund issue, the system must retrieve relevant business data and rules, provide an evidence-backed answer, and ensure any risky action goes through approval before execution — never silently executing something irreversible.

## Current State

**Last shipped milestone:** v2.1 Core Subsystem Hardening (shipped 2026-07-08)
**Current focus:** v2.2 follow-up architecture hardening is active. Phase 64.1 Runtime Safety And Approval Contract Repair is complete; Phase 64.2 Evidence Identity Immutable Replay And Memory Provenance is next.

MOCA now has hardened core subsystem boundaries across ToolPlatform, intent recognition, memory, RAG/claim routing, approval, canonical Agent Graph runtime, and the Phase 62 business-query/drilldown path. v2.1 closed all 24 tracked requirements and passed the milestone audit with no integration blockers.

## Current Milestone: v2.2 Product Experience Fixes

**Goal:** Fix concrete user-facing experience problems in the Agent Console while preserving the v2.1 safety, evidence, tool, memory, and approval boundaries.

**Target features:**
- Accurate direct-response and clarification behavior for greetings, unsupported requests, missing-slot prompts, and other user-visible edge cases.
- Scope-aware `business_metric_query` support for common operational metrics such as order count, refund count, pending ticket count, coupon issuance count, and merchant refund rate.
- Role- and merchant-scope enforcement for metric answers: support/manager see only authorized merchant scope, and admin sees only their management scope.
- Frontend timeline and final-response polish so users can understand what the agent did, why it needs more information, and what capability boundary was hit.
- A repeatable UX regression suite covering the specific prompts and flows that previously felt wrong in local demos.

## Last Shipped Milestone: v2.1 Core Subsystem Hardening

v2.1 shipped Phases 37-60 plus inserted Phase 48.1 on 2026-07-08. It cleaned up architecture debt across MOCA's core subsystems so tool contracts, intent routing, memory lifecycle behavior, and the canonical Agent Graph migration are explicit, tested, and aligned with `docs/contract-spec.md`.

**Delivered:**
- Consolidated ToolPlatform declaration/runtime/policy contracts: single-source tool registry, real output schemas, runtime output validation, shared failure handling, declarative policy gates, and removal of `UnifiedToolManager`.
- Decoupled intent recognition and preserved multi-intent utterances through bounded `TaskPlan` semantics without weakening the single-intent route contract.
- Rebuilt memory layering around Case Working Context, thread-case M:N linkage, session-context boundaries, reviewed case precedent generation, explicit preference-only long-term memory, and compatibility debt cleanup.
- Migrated `investigate` to a bounded read-only ReAct loop and completed the canonical 15-node Agent Graph cutover with legacy runtime route/name cleanup.
- Aligned recommendation/RAG claim fail-closed behavior, canonical `risk_gate`/`approval_gate` behavior, and approval-resume terminal memory finalization.
- Closed archive evidence gaps with formal verification, Nyquist validation, UAT, security signoff, and a passed v2.1 milestone audit.

**Guardrails carried forward:**
- `ToolCallContext` identity fields (`tenant_id/user_id/role/permissions/merchant_scope/session_id/thread_id/run_id/trace_id`) remain locked by spec §8.0 as `TrustedContext` projections.
- Domain-level ownership/scope enforcement remains owned by BusinessFactService.
- `docs/contract-spec.md` remains the primary accepted contract source, with explicit review/traceability required for spec deltas.
- Memory remains contextual-only unless a future phase explicitly designs a new authority boundary.
- Canonical Agent Graph node names remain the active runtime vocabulary; historical legacy graph names are allowed only as historical/test/documentation references.

**Archived:** `.planning/milestones/v2.1-ROADMAP.md`, `.planning/milestones/v2.1-REQUIREMENTS.md`, and `.planning/milestones/v2.1-MILESTONE-AUDIT.md`.

## Prior Shipped Milestone: v1.9 Agent Platform Foundation

v1.9 shipped Phases 26-35.1 on 2026-06-30. It converted MOCA from feature-by-feature agent code into a microservice-ready modular monolith foundation with stable platform/domain service contracts.

**Delivered:**
- Architecture/spec/eval baseline alignment and explicit module ownership boundaries.
- Canonical `TrustedContextFactory` plus prompt-safe and service-safe projections.
- Minimal `DecisionEventEnvelopeV1` and replay-owned decision event emission.
- Descriptor-driven `ToolView`, runtime `ToolPolicyDecision`, safe tool result projection, and ToolPlatform boundary.
- Merchant-bound role semantics for v1.9 runtime scope, with database hardening and same-merchant trace/replay authorization kept as Phase 36+ / future scope.
- `BusinessFactService`, `MemoryContextService`, target graph vocabulary, deterministic RAG context build, and post-generation claim verification.
- Approval/action draft binding hardening and replay/eval coverage for platform decisions.
- Formal milestone audit closure: all 19 APF/MER v1 requirements verified and v1.9 audit marked `ready_to_archive`.

## Prior Shipped Milestone: v1.8 Intent Routing Safety Hardening

v1.8 shipped Phase 25 on 2026-06-21. It hardens the ordinary-chat intent/routing layer for production-style multi-turn safety.

**Delivered:**
- Raw LLM classification, deterministic pre-route decisions, policy overrides, effective classification, risk tier, final route, and reason codes are recorded in classification trace.
- Risk tier policy resolves read-only, draft-only, suggest-action, approval-required, and forbidden-in-chat outcomes from effective intent/operation/channel hints.
- Pending required-slot clarification can consume identifier replies before ordinary classification.
- Standalone ambiguous short approval/action replies fail closed in ordinary chat.
- Trusted inherited slots carry provenance and are invalidated on user negation or context switching.
- Focused regressions and GSD review/verification cover IRS-01 through IRS-12.

## Prior Shipped Milestone: v1.7 Short-term Memory Unification

v1.7 shipped Phase 24 on 2026-06-20. It completes the short-term memory chain for the current Agent Console `/api/v1/agent-runs + SSE` path.

**Delivered:**
- `/agent-runs` creates or resolves conversation threads, persists one user message per run, and passes trusted conversation identifiers into graph execution.
- Completed runs persist one assistant message and update thread rolling summaries from committed messages and eligible prompt-safe tool summaries.
- Same-thread follow-up turns can load trusted session slots, recent messages, tool prompt summaries, and rolling thread summaries into prompt context.
- Explicit current-turn slots override inherited session slots, while stale or scope-mismatched memory fails closed.
- Error, cancelled, approval-interrupted, retried, and re-opened stream states have deterministic idempotent memory persistence behavior.
- Memory remains contextual only and cannot satisfy policy evidence, current business fact, approval/action authority, or replay/audit truth.
- Focused regression coverage and a three-turn integration smoke prove slot continuity plus rolling-summary context.

## Prior Shipped Milestone: v1.6 RAG Reranker + Query Rewrite

v1.6 shipped Phase 23 on 2026-06-20. It improves policy retrieval quality after the v1.3 hybrid backend, v1.4 parser/OCR provenance, and v1.5 grounding kernel.

**Delivered:**
- Query rewrite for policy search that preserves the original user query, tenant/scope/effective-date filters, and failure fallback.
- Original-plus-rewrite retrieval fan-out with channel limits, merge/dedupe, and original-query fallback.
- Deterministic local reranking plus optional provider gates behind timeout, budget, validation, and fallback contracts.
- Safe ranking diagnostics and ablation reports for maintainers/evals without exposing raw prompts, provider payloads, source-block internals, or private reasoning to ordinary surfaces.
- Retrieval ablation evaluation for dense, sparse, fuzzy, RRF, rewrite, reranker, and rewrite-plus-reranker variants with latency/fallback metrics.
- Boundary regressions proving `EvidenceRefV1`, ContextBuilder, verifier, action snapshots, AgentState, and deferred Phase 17/RAG-5/Policy Source scopes remain intact.

## Shipped Milestones

- **v1.0 MVP** — shipped 2026-05-22.
- **v1.1 Agent Architecture Migration** — shipped 2026-06-17.
- **v1.2 Long-term / Case Memory** — shipped 2026-06-17.
- **v1.3 RAG Hybrid Retrieval** — shipped 2026-06-18.
- **v1.4 RAG Production Ingestion + OCR** — shipped 2026-06-19.
- **v1.5 RAG Context Builder + Hallucination Control** — shipped 2026-06-19.
- **v1.6 RAG Reranker + Query Rewrite** — shipped 2026-06-20.
- **v1.7 Short-term Memory Unification** — shipped 2026-06-20.
- **v1.8 Intent Routing Safety Hardening** — shipped 2026-06-21.
- **v1.9 Agent Platform Foundation** — shipped 2026-06-30.
- **v2.0 Merchant Scope Hardening** — shipped 2026-06-30.
- **v2.1 Core Subsystem Hardening** — shipped 2026-07-08.

Full archive records for archived milestones live in `.planning/milestones/`.

## Prior Shipped Milestone: v1.5 RAG Context Builder + Hallucination Control

v1.5 shipped Phase 22. It inserts a bounded reasoning kernel after retrieval and before answer/action reasoning, so RAG-backed policy conclusions and action recommendations use canonical verified evidence and current Tool System business facts.

**Delivered:** ContextBuilder, typed MaterialClaim verification, deterministic verifier route control, action-boundary blocking, safe final-response wording, leakage guards, and a deterministic hallucination-control eval gate.

**Shipped features:**
- Prompt-safe `RagContextBundle` construction with canonical evidence re-fetch, tenant/scope/hash/freshness/latest-version validation, citation maps, dedupe/merge traceability, risk labels, exclusion reasons, and budget traces.
- `MaterialClaim` authority contracts for policy claims, business fact claims, and action recommendation claims.
- Deterministic Level 1/2 verification plus risk-triggered, budgeted, fail-closed Level 3 semantic verification.
- Backend-owned route map for allow, regenerate-route, refusal/insufficient evidence, and manual review without model-selected safety routing.
- Action/risk/approval/final-response integration that blocks non-allow verifier outcomes from creating proposed actions, approval requests, action drafts, or safety snapshot evidence.
- Deterministic 24-case hallucination-control eval with 5 production-verifier cases, no live provider dependency, and no raw verifier/provenance/OCR/debug leakage.

## Earlier Shipped Milestone: v1.4 RAG Production Ingestion + OCR

v1.4 shipped Phase 21. It turns the v1.3 hybrid retrieval base into a production ingestion foundation for real policy source files: Markdown/plain text, PDF, DOCX, image inputs, and scanned PDFs with parser/OCR metadata.

**Delivered:** Parser/OCR ingestion and source-block citation metadata so policy chunks can be traced back to pages, bounding boxes, table cells, parser versions, OCR confidence, and source blocks without weakening `EvidenceRefV1` or mixing business facts into policy evidence.

**Shipped features:**
- Parser/OCR abstraction for PDF, DOCX, and image inputs.
- Durable `DocumentBlock` or equivalent source-block model with page, bbox, block type, table/cell metadata, parser version, OCR confidence, and source block references.
- Table-aware chunking that can preserve cell/header context for retrieval search text.
- Ingestion trace that records parser/OCR decisions and failure modes without storing unsafe raw payloads in prompts.
- Compatibility with v1.3 hybrid retrieval: `PolicyChunk.content` remains citation text, `search_text` remains retrieval-only enrichment, and `EvidenceRefV1` identity remains stable.
- Focused tests for parser fixtures, OCR confidence boundaries, block-to-chunk provenance, downgrade/rollback behavior, and no cross-contamination with business facts.

## Earlier Shipped Milestone: v1.3 RAG Hybrid Retrieval

v1.3 shipped Phase 20. It upgraded MOCA's policy retrieval from pgvector-only search plus lightweight lexical rerank into a minimal production hybrid retrieval backend on PostgreSQL.

**Delivered:** Combined pgvector semantic retrieval, PostgreSQL full-text sparse retrieval, and pg_trgm fuzzy retrieval with RRF, while preserving `PolicyKnowledgeService`, canonical `EvidenceRefV1`, citation identity, and the Tool System boundary for business facts.

**Shipped features:**
- `PolicyChunk.search_text` / `search_vector` storage and indexes for full-text and pg_trgm search.
- Application-level Chinese tokenizer with refund/support domain dictionary.
- Dense + sparse + fuzzy retrieval merged by Reciprocal Rank Fusion.
- Retrieval pre-filters for tenant, effective date, doc type, risk level, and existing knowledge scope.
- Minimal retrieval trace for eval/debug without entering prompts or replacing `EvidenceRefV1`.
- Focused tests and eval coverage for tokenizer, hybrid ranking, RRF ordering, permission/effective-date filtering, Hit@5, fallback accuracy, UAT, and security threats.

## Earlier Shipped Milestone: v1.1 Agent Architecture Migration

**Goal:** Migrate the existing deterministic agent toward explicit, testable contracts for knowledge, business tools, state/routing, intent/clarification, memory, approvals, actions, replay, schema rollout, and evaluation without weakening the shipped v1.0 safety boundary.

**Target features:**
- KnowledgeService and BusinessToolService facades with canonical evidence/tool contracts.
- Enforced AgentState lifecycle, trusted fields, router totality, and safe invalid-state fallback.
- Versioned approval lifecycle and immutable ActionSafetySnapshot binding.
- Strict demo draft boundary followed by separately owned future external execution.
- PostgreSQL-authoritative session memory CAS, with optional Redis hot cache and long-term/case memory independently deferred.
- ReplayEventV3, lifecycle finalizer, redaction/retention, migration rollout, contract tests, golden flows, and blocking eval gates.

## Requirements

### Validated

- [x] Docker Compose one-command startup for local infrastructure and FastAPI baseline (validated in Phase 1)
- [x] Role-based access control for support/reviewer/manager style API scopes (validated in Phase 1)
- [x] Demo data seed script populates realistic synthetic Chinese business data (validated in Phase 1)
- [x] Knowledge base ingestion, pgvector retrieval, top-5 evidence, citation validation, and DB-backed RAG Hit@5 baseline (validated in Phase 2)
- [x] Agent accepts refund/order questions, retrieves business context and policy evidence, and returns evidence-cited answers (validated in Phase 3)
- [x] Structured read tools retrieve order, refund, and ticket data for agent reasoning (validated in Phase 3)
- [x] Agent runs produce trace records for nodes, tool calls, evidence, and same-thread memory (validated in Phase 3)
- [x] High-risk actions trigger approval workflow interruption instead of direct execution (validated in Phase 4)
- [x] Approval decisions resume or halt graph execution through LangGraph interrupt/resume (validated in Phase 4)
- [x] Approval workflow creates auditable action drafts and exposes run-level trace replay (validated in Phase 4)
- [x] Simple frontend allows submitting questions, viewing streamed agent responses, inspecting evidence/trace details, and handling approvals (validated in Phase 5)
- [x] Final evaluation and polish expands the golden set, validates end-to-end metrics, and prepares demo/README materials (validated in Phase 6)
- [x] v1.1 contract baseline inventories current evidence, target contracts, phase owners, follow-up gates, and downstream readiness (validated in Phase 7)
- [x] v1.1 KnowledgeService and BusinessToolService boundaries are explicit and verified (validated in Phases 8-9)
- [x] v1.1 state/router and intent/clarification contracts are deterministic and tested (validated in Phases 10-11)
- [x] v1.1 PostgreSQL-authoritative session memory uses CAS, safe same-thread slot continuity, evidence/action authority separation, and explicit Redis deferral (validated in Phase 12)
- [x] v1.1 approval lifecycle and ActionSafetySnapshot binding are versioned, immutable, and verified (validated in Phase 13)
- [x] v1.1 demo action boundary creates durable drafts only, binds exact payload/hash/snapshot data, and fails closed without trusted approval permission (validated in Phase 14)
- [x] v1.1 replay contract stores and reads ReplayEventV3 facts with lifecycle finalization, shared sequence allocation, operation pairing, redaction/retention, `/replay` read-switch, and `/trace` fallback (validated in Phase 15)
- [x] v1.3 policy retrieval stores retrieval-only search text, generated search vectors, full-text and pg_trgm indexes, and rollback-safe migration coverage (validated in Phase 20)
- [x] v1.3 policy retrieval combines dense, sparse, and fuzzy channels with RRF while preserving normalized evidence confidence and `EvidenceRefV1` citation identity (validated in Phase 20)
- [x] v1.3 retrieval applies tenant, effective-date, doc type, risk level, and knowledge-scope filters before every channel contributes candidates (validated in Phase 20)
- [x] v1.3 hybrid retrieval exposes internal eval/debug trace without entering prompts, API serialization, business facts, or policy evidence refs (validated in Phase 20)
- [x] v1.4 policy source ingestion routes Markdown/plain text, PDF, DOCX, image, and scanned-PDF sources through project-owned parser/OCR DTOs (validated in Phase 21)
- [x] v1.4 source-block provenance persists page/bbox/table/OCR metadata and exposes it only through verified tenant/hash-checked lookup (validated in Phase 21)
- [x] v1.4 block-aware chunking preserves canonical citation text and keeps search enrichment retrieval-only (validated in Phase 21)
- [x] v1.4 ingestion traces, rollback behavior, parser/OCR safety, migration downgrade/reupgrade, and v1.3 contract preservation are verified (validated in Phase 21)
- [x] Phase 22 RAG reasoning kernel builds a bounded ContextBuilder between retrieval and answer/action reasoning (validated in Phase 22)
- [x] Phase 22 ContextBuilder emits prompt-safe evidence context with citation maps, risk labels, exclusion reasons, and token budget trace (validated in Phase 22)
- [x] Phase 22 MaterialClaim outputs separate policy claims, business fact claims, and action recommendation claims with the correct authority refs (validated in Phase 22)
- [x] Phase 22 verifier applies deterministic Level 1 gates, low-cost Level 2 lexical/span support checks, and risk-triggered Level 3 semantic support (validated in Phase 22)
- [x] Phase 22 routes unsupported, stale, conflicting, unauthorized, hash-mismatched, and insufficient claims deterministically to regenerate, refuse, or manual review (validated in Phase 22)
- [x] Phase 22 evals cover faithfulness, citation accuracy, refusal/manual-review routing, business-data hallucination, OCR/conflict traps, and authority-boundary regressions (validated in Phase 22)
- [x] Phase 23 query rewrite improves recall for ambiguous, underspecified, or domain-synonym policy questions without losing the original query or trusted filters (validated in Phase 23)
- [x] Phase 23 reranker interface reorders candidate evidence with bounded deterministic/default behavior and optional provider adapters behind timeout/fallback controls (validated in Phase 23)
- [x] Phase 23 ranking explanations expose safe, bounded diagnostics for maintainers and evals without changing `EvidenceRefV1` identity or leaking internal payloads (validated in Phase 23)
- [x] Phase 23 evals compare retrieval variants, report recall/precision/Hit@K/citation-support impacts, and enforce latency budgets (validated in Phase 23)
- [x] Phase 23 preserves Phase 20 retrieval filters, Phase 21 provenance boundaries, and Phase 22 grounding/verifier/action boundaries (validated in Phase 23)
- [x] Current Agent Console `/agent-runs + SSE` runs persist user/assistant conversation messages and rolling summaries consistently with the legacy `/agent/chat` path (validated in Phase 24)
- [x] Short-term prompt context combines trusted session slots, recent messages, tool prompt summaries, and thread rolling summary for same-thread follow-ups (validated in Phase 24)
- [x] Memory context is prompt-safe and cannot act as policy evidence, current business fact authority, approval/action authority, or replay/audit truth (validated in Phase 24)
- [x] Completed, error, cancelled, interrupted, and stream-retry states have deterministic, idempotent memory persistence semantics (validated in Phase 24)
- [x] v1.8 intent routing safety hardening records traceable raw/effective classification, deterministic risk tiering, workflow-state-first clarification handling, and trusted slot invalidation (validated in Phase 25)
- [x] v1.9 architecture/spec/eval baseline and module ownership boundaries are aligned across contract, roadmap, and eval artifacts (validated in Phase 26 and Phase 35.1)
- [x] v1.9 trusted context and service-safe projection contracts are canonical and cannot be widened by LLM/user payloads (validated in Phase 27)
- [x] v1.9 decision event envelope and emitter foundation records stable reason/version/redaction/run identity for later platform services (validated in Phase 28)
- [x] v1.9 ToolPlatform exposes prompt-safe `ToolView` projections and rechecks runtime `ToolPolicyDecision` authorization before invocation (validated in Phase 29)
- [x] v1.9 merchant-bound role semantics are complete for runtime scope, with database hardening and same-merchant trace/replay authorization expansion explicitly future-scoped (validated in Phase 29.5 and Phase 35.1)
- [x] v1.9 `BusinessFactService` exposes current business facts only through `BusinessFactResultV1` / `BusinessFactRefV1` authority contracts (validated in Phase 30)
- [x] v1.9 memory platform APIs separate session, long-term, case, conversation, workflow, working-state, and write-candidate memory while keeping memory contextual-only (validated in Phase 31)
- [x] v1.9 graph vocabulary, intent policy registry, and slot policy registry own deterministic target route/slot decisions (validated in Phase 32)
- [x] v1.9 RAG context build and claim verification produce `VerifiedEvidencePackageV1`, `MaterialClaimV1`, and `ClaimVerificationBundleV1` with fail-closed authority gates (validated in Phase 33)
- [x] v1.9 approval/action draft boundary binds payloads to business facts, verified evidence, claim verification, risk decisions, hashes, and safety snapshots without real external execution (validated in Phase 34)
- [x] v1.9 replay/eval hardening records platform decision coverage and dev/release/monitoring gate artifacts for trusted context, intent/slot, memory, tool, RAG, claim, risk, approval, and action draft boundaries (validated in Phase 35)
- [x] v2.0 merchant-scope database and role semantics are hardened without opening new run/trace/replay visibility (validated in Phase 36)
- [x] Phase 36 emits `ready_with_agent_run_binding` as the trace/replay authorization readiness conclusion for later same-merchant manager visibility expansion (validated in Phase 36)
- [x] v2.1 tool declarations resolve from a single-source registry, and runtime/policy internals use shared/declarative structures without external contract shape changes (validated in Phase 37)
- [x] v2.1 real output schemas are declared for the eight scoped tools and enforced by runtime output validation as safe `invalid_response` failures, with DB-backed full relevant pytest passing (validated in Phase 38)
- [x] v2.1 contract spec §12.5/§12.6 matches the implemented tool contract fields while preserving §8.0 TrustedContext identity ownership (validated in Phase 39)
- [x] v2.1 session memory is repositioned after Case Working Context as thread-scoped, short-lived conversational context only, with contract/static/behavioral tests preventing cross-case state, reviewed precedent, long-term sedimentation, and authority use (validated in Phase 46)
- [x] v2.1 case memory is repositioned as reviewed closed-case precedent with governed closed-case CWC candidate generation and approval-gated publication (validated in Phase 47)
- [x] v2.1 long-term memory is narrowed to explicit preference memory only, with chat/admin/reviewed write paths, published preference-only retrieval, and no generic automatic run summarization (validated in Phase 48)

### Active

_No active v2.2 requirements remain after Phase 61 completion._

### Validated In Phase 61

- [x] v2.2 fixes misleading agent responses for known direct-response and unsupported-capability prompts.
- [x] v2.2 adds safe, scoped business metric query support for common operational count/rate questions.
- [x] v2.2 improves Agent Console timeline, clarification, unsupported, and metric-result presentation.
- [x] v2.2 adds repeatable UX regression coverage for the concrete local-demo pain points discovered during validation.

### Validated In Phase 64.1

- [x] Actionable Chinese/English recommendations resolve through one canonical taxonomy before claim and safety routing; unknown, ambiguous, and invalid candidates fail closed.
- [x] One deterministic high/medium/low evaluator owns risk precedence, and LLM/config failures cannot downgrade an action into auto-allow.
- [x] Approval list/get/SSE/decide and the Console share one exact versioned decision context; stale, cross-scope, ambiguous, and concurrent recovery paths fail closed without automatic replay.
- [x] Low-risk demo draft creation requires a durable server-minted, fully bound capability and cannot widen general permissions or execute an external effect.
- [x] Shared terminal projection prevents authorization, draft, audit, claim, or evidence failures from becoming completed API/SSE/final/memory state.

### Out of Scope

- Real external action execution, outbox, reconciliation, and compensation — future External Action Execution milestone.
- Tenant-over-global global/default policy fallback — future post-Phase 17 Policy Scope milestone.
- Memory as policy evidence, approval/action authority, current business fact, or replay/audit truth — violates the contract boundary.
- Full user-facing memory management UI — defer until storage/review/tombstone/retrieval foundations are safe.
- Full external `SearchBackend` interface — deferred to Phase RAG-5: Optional External Search Backend; current code has one Postgres backend and `PolicyKnowledgeService` already hides retriever details from Agent nodes.
- New vector database service — PostgreSQL/pgvector remains the default unless Phase RAG-5 backend planning proves a stronger need.
- Source-block/OCR/provenance fields in `EvidenceRefV1` or ordinary business facts — provenance remains internal/debug/maintainer lookup data.
- Policy source upload/review/lifecycle UI — future Policy Source Operations milestone.
- Vespa/OpenSearch or another search backend — future Phase RAG-5 only if PostgreSQL hybrid no longer fits.
- Second scenario (creator appeals) — defer to polish phase
- MCP protocol layer — adds complexity without MVP value
- Kubernetes / production deployment — Docker Compose sufficient for demo
- Celery / async workers — LangGraph handles the flow; no separate queue needed for MVP
- LangSmith integration — OTel traces sufficient; LangSmith is optional enhancement
- Mobile app or native clients — web only
- Real payment/refund execution — all tools are simulated
- Multi-tenant SaaS deployment — single-tenant demo with role separation
- Same-merchant manager run/trace/replay visibility expansion — future Phase 37 after Phase 36 readiness is proven.
- PostgreSQL RLS enforcement — future hardening phase; v2.0 prepares schema constraints and migration gates only.
- General-purpose analytics dashboarding — v2.2 only supports bounded agent-answered operational metrics needed for demo UX.
- Arbitrary SQL, natural-language database exploration, or cross-tenant analytics — violates ToolPlatform and trusted-scope boundaries.
- Production-grade BI exports, chart builders, or scheduled reporting — outside this UX-focused milestone.

## Context

**Target audience for the project itself:** Hiring managers and technical interviewers at internet companies (Alibaba, ByteDance, Meituan, JD, etc.) evaluating candidates for AI/Agent engineer and AI product manager roles.

**What this proves:**
- Agent engineering: LangGraph state machines, human-in-the-loop, tool orchestration, RAG with citations
- Product thinking: scenario analysis, user journeys, permission models, success metrics, risk mitigation
- Engineering maturity: Docker Compose reproducibility, structured APIs, audit trails, evaluation framework

**Tech stack (simplified from research report):**
- Orchestration: LangGraph (state machine, interrupt/resume, memory)
- API layer: FastAPI (OAuth2 scopes, dependency injection, OpenAPI docs)
- Database: PostgreSQL + pgvector (business data + vector search + RLS in one system)
- Cache: Redis (optional non-authoritative session hot cache, rate limiting)
- Model: OpenAI-compatible API (cloud or local vLLM)
- RAG: LlamaIndex for offline ingestion; custom retrieval chain online
- Frontend: Simple React + Vite interface
- Infra: Docker Compose for local; no K8s in MVP
- Observability: Basic OTel tracing (polish phase: Prometheus + Grafana)

**Key differentiation from typical chatbot projects:**
- Not a chatbot — it's a business process agent that reads systems, enforces approvals, executes actions, and audits everything
- Evidence-first: every answer cites specific documents or data records
- Interrupt/resume: approval workflow is a first-class graph node, not an if/else hack
- Auditable: every run is replayable from audit logs

## Historical State Ledger

- Phase 1 Foundation is complete: local infrastructure, schema, seed data, auth/scopes, repository layer, and CRUD/tool-call foundations are in place.
- Phase 2 RAG Pipeline is complete: 15 Chinese policy documents are chunked and embedded, `/api/v1/search/` returns tenant-filtered evidence with citation metadata, and live DB-backed EVAL-02 passes at Hit@5 83.3% with fallback accuracy 100.0%.
- Phase 3 LangGraph Core is complete: read tools, RAG evidence, trace logging, same-thread memory, and the read-only agent happy path are validated.
- Phase 4 Approval Workflow & Audit is complete: high-risk actions interrupt for approval, approve/reject resumes are validated, action drafts are idempotent, trace replay is queryable by run_id, and high-risk interception is 100%.
- Phase 5 Frontend & SSE is complete: the React/Vite demo supports chat submission, progressive SSE timeline updates, evidence/trace inspection, pending approval handling, role switching, and Docker Compose frontend-to-API routing.
- Phase 6 Evaluation & Polish is complete: the golden set now covers 14 RAG cases and 35 deterministic agent cases, evaluation scripts generate reports, CI runs lint/unit checks, and README/demo/security/evaluation docs are polished for the v1.0 demo.
- v1.0 MVP is shipped and archived on 2026-05-22. Full milestone history lives in `.planning/milestones/v1.0-ROADMAP.md` and `.planning/milestones/v1.0-REQUIREMENTS.md`.
- Phase 7 Contract Baseline is complete: the contract inventory, current-vs-target evidence checklist, initial coverage matrix, follow-up register disposition, and readiness verdict are persisted.
- Phase 8 Knowledge Facade is complete: policy evidence retrieval uses the KnowledgeService facade with canonical EvidenceRefV1/citation contracts and verified checkpoint red-line behavior.
- Phase 9 Business Tool Facade is complete: read business tools route through BusinessToolService with trusted ToolCallContext and typed ToolResultV2.
- Phase 10 State Lifecycle + Routing Migration is complete: AgentState lifecycle, trusted-field reset/merge behavior, deterministic routers, empty session-memory adapter, and bounded investigate graph wiring are verified.
- Phase 11 Intent / Clarification is complete: strict intent schema, deterministic pre-router/slot routing, ordinary clarification, and hash-owned golden/manifest gates are verified.
- Phase 12 Session Memory is complete: PostgreSQL-authoritative session memory, CAS merge/conflict behavior, same-thread slot continuity, evidence/action authority separation, post-response bounded writes, and Redis skip decision are verified.
- Phase 13 Approval State Machine is complete: versioned lifecycle, immutable ActionSafetySnapshot binding, trusted API/graph transitions, approval events, SLA scanning, and legacy quarantine are verified.
- Phase 14 Demo Action Executor Boundary is complete: durable draft-only behavior, exact payload/hash/snapshot binding, no-approval fail-closed behavior, trusted write-tool permission ownership, and draft-only final/API wording are verified.
- Phase 15 Replay Event Contract is complete: ReplayEventV3 storage/projection, lifecycle finalization, shared sequence allocation, operation pairing, replay redaction/retention, `/replay` read-switch, `/trace` rollback fallback, and owner-named Phase 17 deferrals are verified.
- Phase 15.1 Memory Foundation V2 is complete: user-scoped conversation log, layered tool call/result storage, prompt-safe WorkingStateV1, source-range thread summaries, ContextAssembler/token budgeting, and replay/audit/conversation ID alignment are verified without implementing Phase 16/17 scope.
- Phase 15.2 v1.1 Readiness Closure is complete: formal Phase 7/10 verification exists, `KNOW-02` tenant-over-global target semantics have a post-Phase 17 `Policy Scope` owner, and the milestone readiness audit passes.
- v1.1 is shipped and archived on 2026-06-17. Full milestone history lives in `.planning/milestones/v1.1-ROADMAP.md`, `.planning/milestones/v1.1-REQUIREMENTS.md`, and `.planning/milestones/v1.1-MILESTONE-AUDIT.md`.
- v1.2 Long-term / Case Memory is complete. Phase 16 owns `memory_identity.v1`, reviewed long-term memory, reviewed case memory, memory tombstones, memory write events, and prompt-context integration.
- v1.3 RAG Hybrid Retrieval is shipped and archived. Phase 20 owns the minimal PostgreSQL hybrid retrieval upgrade and explicitly excludes OCR, `DocumentBlock`, `MaterialClaim`, semantic verifier, reranker/query rewrite, Vespa/OpenSearch, and full external `SearchBackend`. OCR/parser/`DocumentBlock` is Phase 21-owned; `MaterialClaim`/semantic verifier is Phase 22-owned; reranker/query rewrite is Phase 23-owned; Vespa/OpenSearch/full external `SearchBackend` is Phase RAG-5-owned.
- v1.4 RAG Production Ingestion + OCR is shipped and archived. Phase 21 preserved v1.3 retrieval/evidence contracts while adding parser/OCR and source-block provenance.
- v1.5 RAG Context Builder + Hallucination Control is shipped and archived. Phase 22 owns ContextBuilder, canonical evidence validation, MaterialClaim authority verification, deterministic route control, action-boundary blocking, safe final-response wording, and hallucination-control evals while preserving v1.3/v1.4 evidence and provenance boundaries.
- v1.6 RAG Reranker + Query Rewrite is shipped and archived on 2026-06-20. Full milestone history lives in `.planning/milestones/v1.6-ROADMAP.md`, `.planning/milestones/v1.6-REQUIREMENTS.md`, and `.planning/milestones/v1.6-phases/`.
- v1.7 Short-term Memory Unification is complete on 2026-06-20. Phase 24 owns Agent Console `/agent-runs + SSE` conversation persistence, rolling summaries, prompt-safe tool summaries, PostgreSQL-backed session slot continuity, failure/idempotency safeguards, authority-boundary regressions, and three-turn smoke verification.
- v1.9 Agent Platform Foundation is shipped and archived on 2026-06-30. It completes Phases 26-35.1: architecture contract baseline, TrustedContextFactory/projections, decision events, tool platform, merchant scope alignment, BusinessFactService, memory platform, intent graph migration, deterministic RAG context build, claim verification, approval/action draft hardening, replay/eval hardening, and audit readiness closure. Full milestone history lives in `.planning/milestones/v1.9-ROADMAP.md`, `.planning/milestones/v1.9-REQUIREMENTS.md`, and `.planning/milestones/v1.9-MILESTONE-AUDIT.md`.
- v2.1 Core Subsystem Hardening is shipped and archived on 2026-07-08. It completes Phases 37-60 plus inserted Phase 48.1: ToolPlatform contract hardening, intent decoupling, memory layering, bounded investigate ReAct migration, canonical Agent Graph cutover, approval-resume memory finalization, and archive evidence closure. Full milestone history lives in `.planning/milestones/v2.1-ROADMAP.md`, `.planning/milestones/v2.1-REQUIREMENTS.md`, and `.planning/milestones/v2.1-MILESTONE-AUDIT.md`.
- v2.2 Product Experience Fixes starts on 2026-07-09. Its scope is not another broad subsystem rewrite; it is a user-facing correction milestone focused on concrete bad experiences found during local demo and Agent Console validation.

## Next Milestone Setup

- v2.2 is the active milestone.
- Phase numbering continues after Phase 60; do not restart at Phase 1 or use old v1.x phase numbers.
- Preserve v2.1 subsystem contracts from `docs/contract-spec.md` unless a future phase explicitly records a spec delta.
- Keep owner-named deferrals explicit: Phase 49 replay parent-operation identity limitation, legacy `/api/v1/agent/chat` background memory-write compatibility, same-merchant trace/replay authorization expansion, Phase 17 External Action Execution, post-Phase 17 Policy Scope, Phase RAG-5 external backend, and Policy Source Operations.
- Preserve safety boundaries: policy evidence remains `EvidenceRefV1`; current business facts remain `BusinessFactResultV1` / `BusinessFactRefV1`; memory remains contextual assistance only; parser/OCR provenance remains internal unless verified through maintainer lookup; verifier failures and timeouts fail closed; replay/eval artifacts do not authorize new access by themselves.

## Constraints

- **Timeline**: 4 weeks to MVP core (full-time), 2 weeks polish (frontend + eval) — 6 weeks total
- **Learning curve**: LangGraph, FastAPI, pgvector are new — architecture must stay simple enough to learn while building
- **Solo developer**: no team; must avoid over-engineering
- **Demo-first**: everything must be runnable with `docker compose up` and demonstrable in 10 minutes
- **Open source**: all data must be synthetic/anonymized; no real PII; compliant with Chinese data protection laws

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Single graph, multi-node over multi-agent | Simpler to build, debug, and explain; multi-agent adds complexity without MVP value | Adopted through Phase 6 |
| pgvector over Milvus/Weaviate | One-command reproducibility; business data + vectors + RLS in same DB | Adopted in Phase 2 |
| No Celery/queue system | LangGraph's durable execution handles the async flow; separate queue is premature | Adopted for Phase 2 ingestion/eval CLI; revisit only if Phase 3/4 needs background work |
| Chinese demo data, English README | Targets Chinese internet companies but accessible to global open-source community | Adopted in Phase 6 |
| Approval as graph node, not external middleware | Demonstrates LangGraph's core strength; more impressive in interviews | Adopted in Phase 4 |
| Simple frontend over pure API | 10-minute demo needs visual impact; keeps PM angle visible | Adopted in Phase 5 |
| Keep v1.1 scope fresh | v1.0 requirements are complete and archived; continuing in the same requirements file would mix shipped and future obligations | Adopted after v1.0 archive |
| Replace the previous v1.1 investigation roadmap with Agent Architecture Migration | The architecture spec now defines the authoritative capability sequence and standard Phase 7-17 identities are required for SDK planning | Adopted 2026-06-06 |
| Phase 13-17 architecture-first planning standard | Approval, action, replay, memory, and external execution are tightly coupled; plans must read `docs/phase-13-17-architecture-plan.md`, define owners/contracts first, and delete or quarantine old paths instead of preserving minimum-diff compatibility | Adopted 2026-06-15 |
| Archive v1.1 before Phase 16 | Readiness closure showed v1.1 could be archived cleanly before entering long-term memory, avoiding carry-over evidence debt | Adopted 2026-06-17 |
| Scope v1.2 to Phase 16 only | Preserves the existing architecture-owner meaning of Phase 16 while avoiding renumbering or absorbing Phase 17 External Action Execution | Adopted 2026-06-17 |
| Treat long-term/case memory as contextual assistance only | Prevents memory from weakening the policy evidence, approval/action authority, current business fact, and replay/audit contracts established in v1.1 | Adopted 2026-06-17 |
| Keep v1.3 hybrid retrieval inside PostgreSQL and PolicyKnowledgeService | PostgreSQL hybrid search is enough for the current scale, and the service facade already hides retriever details from Agent nodes | Adopted 2026-06-18 |
| Separate retrieval search text from citation content | Preserves `PolicyChunk.content`, `EvidenceRefV1.text_hash`, approval snapshots, and replay/citation identity while improving retrieval quality | Adopted 2026-06-18 |
| Name RAG deferral owners explicitly | Prevents OCR, `DocumentBlock`, `MaterialClaim`, reranking, and external backend work from being treated as vague future scope | Adopted 2026-06-18 |
| Scope v1.4 to Phase 21 ingestion/OCR | Keeps source parsing and provenance separate from later hallucination-control, reranking, and backend-scale work | Adopted 2026-06-18 |
| Ship v1.4 only after dependency gates pass | Local `chi_sim+eng` OCR preflight and live pgvector migration round trip remove the earlier dependency-only acceptance caveat | Adopted 2026-06-19 |
| Scope v1.5 to Phase 22 hallucination control | Keeps reasoning-context validation, MaterialClaim support checks, and deterministic failure routing separate from Phase 23 reranking/query rewrite and Phase 17 external execution | Adopted 2026-06-19 |
| Scope v1.6 to Phase 23 retrieval quality | Starts the owner-named RAG reranker/query rewrite phase while keeping 17-prep as a later Phase 17 prerequisite | Adopted 2026-06-20 |
| Scope v1.7 to Agent Console short-term memory unification | The current frontend path uses `/agent-runs + SSE`; it needs parity with the existing conversation log and rolling summary infrastructure while preserving memory authority boundaries | Adopted 2026-06-20 |
| Scope v1.9 to Agent Platform Foundation | The next architecture milestone should land modular-monolith service boundaries and platform contracts before graph/RAG/tool/memory rewrites, without restarting phase numbering or implementing full real execution | Adopted 2026-06-22 |
| Keep Phase 36+ for future hardening, not audit closure | Phase 35.1 closed v1.9 readiness gaps while preserving Phase 36+ as database hardening / role cleanup / same-merchant trace-replay expansion scope | Adopted 2026-06-30 |
| Close MER-01 as v1.9 runtime scope only | Runtime merchant boundaries are verified, but database/RLS/role cleanup and trace/replay authorization expansion remain named future scope | Adopted 2026-06-30 |
| Archive v1.9 after formal audit closure | Phase 35.1 added missing formal verification artifacts, refreshed validation metadata, and produced a ready-to-archive milestone audit | Adopted 2026-06-30 |
| Scope v2.2 to concrete Product Experience Fixes | v2.1 hardened internals but local demo validation exposed user-facing confusion: misleading direct responses, unsupported capability wording, missing metric answers, and timeline clarity gaps | Adopted 2026-07-09 |
| Repair runtime safety as one cross-layer contract in Phase 64.1 | Canonical action, deterministic risk, exact approval context, bounded capability, and terminal integrity fail together when owned as isolated patches | Adopted and verified 2026-08-04 |
| Keep Phase 64.1 draft-only and name downstream owners | Evidence/replay/memory identity, the general operation gateway, the LLM gateway, and production external effects require separate trust boundaries and threat models | Deferred explicitly to Phase 64.2, Phase 66, Phase 69, and a separately authorized external-effects phase |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-04 — completed Phase 64.1 Runtime Safety And Approval Contract Repair*
