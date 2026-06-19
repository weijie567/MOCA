# Milestones

## v1.4 RAG Production Ingestion + OCR (Shipped: 2026-06-19)

**Delivered:** Production policy-source ingestion for PDF, DOCX, image/scanned-PDF, Markdown, and plain-text sources with parser/OCR traceability, durable source-block provenance, table-aware chunking, safe job traces, and v1.3 retrieval/evidence boundary preservation.

**Phases completed:** 21 (1 phase, 9 plans, 18 task markers)

**Key accomplishments:**

- Added project-owned parser DTOs, parser registry wiring, source safety guards, and deterministic Markdown/plain-text synthetic source blocks.
- Added tenant-scoped `DocumentBlock` and `RagIngestionJob` persistence with chunk provenance JSONB while keeping source blocks internal/debug-only.
- Added block-aware and table-aware chunking, retrieval-only `search_text` enrichment, and semantic policy version fingerprints without changing canonical citation text or `EvidenceRefV1.text_hash`.
- Added local PDF, DOCX, image, scanned-PDF, and OCR parser adapters with Tesseract `chi_sim+eng` preflight, OCR confidence thresholds, and fail-closed unsafe-source handling.
- Added tenant/hash-verified source-block provenance lookup plus allowlisted parser/OCR ingestion report projection.
- Locked parser/OCR/source-block boundaries across evidence, API, prompt, memory, action, replay, Tool System, and v1.3 hybrid retrieval surfaces.
- Verified migration downgrade/reupgrade, adversarial rollback, sanitized failure traces, scope guard, Ruff, secure-phase, and full regression gates.

**Stats:**

- 1 completed phase, 9 plans, 18 task markers
- Shipped on 2026-06-19
- Milestone audit passed: 26/26 requirements satisfied, 8/8 integration contracts verified, 5/5 end-to-end flows verified
- Full post-dependency regression gate passed: `1136 passed, 9 warnings`
- Post-dependency live migration + OCR gate passed: `28 passed, 4 warnings`
- Final acceptance: `ACCEPTED`; no dependency-only skips remained after local `chi_sim` traineddata and disposable pgvector PostgreSQL gates were available

**Known deferred items at close:**

- 1 pending todo acknowledged and deferred at close: `2026-06-17-constrain-agentstate-memory-expansion.md` (see `.planning/STATE.md` Deferred Items).
- Phase 17 owns external action execution storage, outbox dispatch, reconciliation, compensation, duplicate execution/key guards.
- Post-Phase 17 Policy Scope owns tenant-over-global global/default policy fallback.
- Phase 22 owns `MaterialClaim`, semantic support verifier, conflict/freshness routing, refusal/manual-review policy, and faithfulness/citation eval.
- Phase 23 owns query rewrite, reranker interface, optional cross-encoder/external rerank API, ranking explanations, retrieval ablation eval, and latency budget.
- Phase RAG-5 owns Vespa/OpenSearch shadow testing and full external `SearchBackend` if PostgreSQL hybrid no longer fits.
- Policy Source Operations owns document upload/review/lifecycle/retention and source-document viewer/highlight UI.

**Archived:**

- `.planning/milestones/v1.4-ROADMAP.md`
- `.planning/milestones/v1.4-REQUIREMENTS.md`
- `.planning/milestones/v1.4-MILESTONE-AUDIT.md`

**What's next:** Start the next milestone with fresh requirements via `$gsd-new-milestone`.

---

## v1.3 RAG Hybrid Retrieval (Shipped: 2026-06-18)

**Delivered:** Minimal production hybrid policy retrieval on PostgreSQL + pgvector + PostgreSQL full-text + pg_trgm, with RRF fusion and evidence-boundary preservation.

**Phases completed:** 20 (1 phase, 1 plan, 6 tasks)

**Key accomplishments:**

- Added deterministic Chinese/domain search text construction for policy chunks and queries.
- Added `PolicyChunk.search_text`, generated `search_vector`, pg_trgm/full-text indexes, and rollback-safe migration coverage.
- Persisted retrieval-only search text during ingestion while keeping `PolicyChunk.content` as citation text.
- Added sparse and fuzzy repository channels with the same trusted tenant/effective/doc/risk filters as dense retrieval.
- Added RRF fusion across dense/sparse/fuzzy results while keeping evidence confidence normalized to 0-1.
- Added internal retrieval trace fields and eval diagnostics without extending `EvidenceRefV1`.

**Stats:**

- 1 completed phase, 1 plan, 6 task markers
- 9 Phase 20 closeout commits from `e25a979` to `8b1d0c5`
- 26 files changed, 3,314 insertions, 148 deletions since the Phase 16 close baseline
- Shipped on 2026-06-18
- UAT passed 7/7; security verification closed 5/5 threats with `threats_open: 0`
- Full regression gate passed: `1002 passed, 6 warnings`

**Known deferred items at close:**

- 1 pending todo acknowledged and deferred at close: `2026-06-17-constrain-agentstate-memory-expansion.md` (see `.planning/STATE.md` Deferred Items).
- Phase 21 owns OCR/parser, `DocumentBlock`, page/bbox/cell citation, table-aware chunking, OCR confidence, and parser trace.
- Phase 22 owns `MaterialClaim`, semantic support verifier, conflict/freshness routing, refusal/manual-review policy, and faithfulness/citation eval.
- Phase 23 owns query rewrite, reranker interface, optional cross-encoder/external rerank API, full ranking explanation, retrieval ablation eval, and latency budget.
- Phase RAG-5 owns Vespa/OpenSearch shadow testing and full external `SearchBackend` if PostgreSQL hybrid no longer fits.
- No standalone `.planning/v1.3-MILESTONE-AUDIT.md` existed at close; closure used Phase 20 validation, review, UAT, security verification, and full pytest gates.

**Archived:**

- `.planning/milestones/v1.3-ROADMAP.md`
- `.planning/milestones/v1.3-REQUIREMENTS.md`

**What's next:** Start the next milestone with fresh requirements via `$gsd-new-milestone`.

---

## v1.1 Agent Architecture Migration (Shipped: 2026-06-17)

**Delivered:** A contract-hardened agent architecture with explicit service facades, deterministic state/routing, approval/action safety contracts, replay events, and pre-Phase 16 memory foundation.

**Phases completed:** 7-15.2 (11 phases, 62 plans, 362 task markers)

**Key accomplishments:**

- Established a contract baseline with owner phases, acceptance gates, and no unresolved baseline `MISSING` rows.
- Migrated policy and business reads behind KnowledgeService and BusinessToolService facades with canonical evidence/tool contracts.
- Hardened AgentState lifecycle, deterministic routers, intent/clarification boundaries, and PostgreSQL-authoritative session memory.
- Rebuilt approval, demo action, and replay surfaces around versioned state transitions, immutable safety snapshots, draft-only demo behavior, ReplayEventV3, and redaction/retention checks.
- Added Memory Foundation V2: user-scoped conversation log, layered tool call/result storage, prompt-safe WorkingStateV1, thread summaries, ContextAssembler, token budgeting, and replay/audit/conversation ID alignment.
- Closed readiness gaps with Phase 15.2 formal verification for Phases 7 and 10 plus `KNOW-02` owner disposition.

**Stats:**

- 11 completed phases, 62 plans
- 500 commits since v1.0 archive
- 675 files changed, 95,913 insertions, 30,352 deletions since v1.0 archive baseline
- Shipped over 21 calendar days (2026-05-28 to 2026-06-17)
- Milestone audit passed: 32/32 current-scope requirements satisfied, 0 orphaned, 0 ownerless partials

**Known deferred items at close:**

- Phase 16 Long-term / Case Memory remains deferred beyond the v1.1 gate.
- Phase 17 External Action Execution remains deferred beyond the v1.1 gate.
- Tenant-over-global global/default policy fallback is target-state `DEFERRED_WITH_OWNER` to post-Phase 17 `Policy Scope`.

**Archived:**

- `.planning/milestones/v1.1-ROADMAP.md`
- `.planning/milestones/v1.1-REQUIREMENTS.md`
- `.planning/milestones/v1.1-MILESTONE-AUDIT.md`

**What's next:** Start the next milestone with fresh requirements; likely first candidate is Phase 16 Long-term / Case Memory.

---

## v1.0 MVP (Shipped: 2026-05-22)

**Delivered:** A complete merchant operations agent demo for refund disputes, rule Q&A, compensation decisions, approval workflows, evidence-backed responses, frontend review, and evaluation reporting.

**Phases completed:** 1-6 (6 phases, 36 plans, 94 tasks)

**Key accomplishments:**

- Built the FastAPI/Postgres/pgvector/Redis foundation with deterministic Chinese demo data, tenant-scoped repositories, JWT scopes, and audit-ready schemas.
- Implemented the RAG pipeline with policy ingestion, DashScope embeddings, hybrid reranking, citation validation, and DB-backed Hit@5 at 83.3%.
- Delivered the LangGraph agent happy path with business-data tools, policy evidence retrieval, same-thread memory, structured fallbacks, and persisted execution traces.
- Added human-in-the-loop approval with LangGraph interrupt/resume, approval APIs, action drafts, trace replay, and 100% high-risk interception.
- Shipped a React/Vite support console with SSE progress, evidence/trace panels, role switching, pending approvals, and Docker Compose demo routing.
- Finished evaluation and polish with 14 RAG cases, 35 agent cases, unified JSON/Markdown reports, CI lint/unit gates, demo script, README, and technical docs.

**Stats:**

- 6 phases, 36 plans, 94 tasks
- 251 commits through archive preparation
- Shipped over 14 calendar days (2026-05-09 to 2026-05-22)
- Known deferred/open artifact records at close: 4 historical audit entries, documented in `.planning/STATE.md`

**Archived:**

- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`

**What's next:** v1.1 Agent Architecture Migration is registered in `.planning/ROADMAP.md` as Phases 7-17.

---
