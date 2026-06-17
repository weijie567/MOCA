# Milestones

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
