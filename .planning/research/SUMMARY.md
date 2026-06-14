# Research Summary: MOCA

## Stack Decision

Use LangGraph 0.3.x for agent orchestration (with `langchain-core` primitives, NOT full LangChain), FastAPI 0.115.x as the async API layer, PostgreSQL 16 + pgvector 0.7.x as the unified data + vector store, Redis 7.x for caching, and LlamaIndex (modular packages) for offline RAG ingestion only. Python 3.11 with `uv` for package management, `ruff` for linting. Frontend is Next.js 14.x + shadcn/ui but is last priority. Avoid: full LangChain framework, separate vector DBs (Pinecone/Weaviate), Celery, LangServe, multi-agent frameworks (AutoGen/CrewAI), MongoDB, Kubernetes, GraphQL, Pydantic v1, SQLAlchemy 1.x. Pin all versions at project start and do not upgrade mid-project.

## Feature Priorities

**Table Stakes** (must ship or project looks like a toy):
- Structured tool calls grounded in real DB records (get_order, get_refund, get_ticket)
- Evidence-cited RAG answers with source attribution ([DOC-ID] format)
- Human-in-the-loop approval workflow with interrupt/resume (the core differentiator)
- Queryable audit trail logging every agent step
- Docker Compose one-command startup with realistic Chinese seed data

**Differentiators** (make it stand out in interviews):
- Graph visualization of actual agent execution paths
- Evaluation framework with automated test scenarios and scoring
- Structured execution trace (decision/evidence/action as structured data)
- Configurable business rules engine (thresholds in config, not code)
- Streaming responses with progressive disclosure (SSE)

## Architecture Blueprint

Single-graph, 8-node LangGraph system: router -> retriever -> tool_caller -> reasoner -> risk_check -> approval (interrupt) -> executor -> response. FastAPI is a thin API gateway handling auth and routing to the graph. One Postgres instance serves business data, vector embeddings (pgvector HNSW), state checkpointing (PostgresSaver), authoritative session memory, and audit logs. Redis handles non-authoritative hot cache and rate limiting. Tools are thin wrappers that never raise exceptions — they return structured error objects. Audit logging is implemented as LangGraph callbacks, not inline. The approval node uses `interrupt()` to pause execution; resume happens via API endpoint calling `Command(resume=...)`. Auth is layered: JWT at API level, permission checks inside tools.

**Build order**: Foundation (Docker + DB + API + seed) -> RAG pipeline (ingest + retrieve + eval) -> LangGraph core (graph + tools + endpoint) -> Approval workflow + polish.

## Critical Risks

1. **State explosion** — Define minimal TypedDict state upfront; separate hot (current turn) from cold (audit) data; use `add_messages` with max-length window.
2. **Interrupt/resume serialization bugs** — Keep state as plain dicts/strings/numbers only; test interrupt-resume cycle from day one with a trivial approval node.
3. **RAG chunking destroys context** — Use structural chunking (split on headers/rules, not fixed-size); validate retrieval on 10 test queries before building further.
4. **Async/sync DB mixing** — Use SQLAlchemy 2.0 async engine + `asyncpg` from the first endpoint; never mix sync calls in async handlers.
5. **Docker startup race conditions** — Use `depends_on` with `condition: service_healthy` and proper healthchecks; add retry logic in app startup.

## Key Insights

1. **Checkpoint and session memory are separate contracts** — the checkpointer enables approval interrupt/resume and workflow recovery; same-thread conversation memory should be an explicit PostgreSQL/CAS service, with Redis only as an optional non-authoritative hot cache.

2. **LlamaIndex is ingestion-only** — use it offline for chunking and embedding, but at query time use raw pgvector SQL via SQLAlchemy. This cuts latency and reduces hot-path dependencies.

3. **Audit trail must be designed INTO the graph from Phase 1** — bolting it on later requires touching every node. Implement the callback pattern early even if you don't persist until later.

4. **One polished scenario beats three half-working ones** — perfect the refund dispute flow end-to-end. Resist adding shipping disputes, seller penalties, or other scenarios. Mention them as "planned extensions" in docs.

5. **Citation validation is non-negotiable** — post-process every LLM response to verify cited IDs exist in retrieval results. Interviewers at Chinese internet companies will check citations because their internal systems already do this.

## Build Order Recommendation

> **Note:** This was the original 4-week research recommendation. The converged 6-week timeline is in ROADMAP.md (the current source of truth).

| Phase | Duration | Focus | Verification |
|-------|----------|-------|--------------|
| 1. Foundation | Week 1 | Docker Compose, Postgres+pgvector, FastAPI skeleton, DB schema, seed data, JWT auth, async DB pattern | `docker compose up` works; Swagger shows CRUD endpoints |
| 2. RAG Pipeline | Week 2 | Knowledge base docs (Chinese), LlamaIndex ingestion, pgvector HNSW index, retrieval function, retrieval eval (10 queries) | Search endpoint returns relevant rule chunks |
| 3. LangGraph Core | Week 3 | AgentState, tool wrappers, all nodes (minus approval), graph compilation, agent endpoint, PostgresSaver, basic audit | Submit question -> get evidence-cited answer with tool traces |
| 4. Approval + Polish | Week 4 | risk_check node, approval interrupt/resume, executor node, resume API, end-to-end test, audit enrichment | Compensation request pauses -> approve -> executes -> full audit chain |
