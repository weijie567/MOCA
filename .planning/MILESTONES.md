# Milestones

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
