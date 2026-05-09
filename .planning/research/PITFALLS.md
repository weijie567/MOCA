# Pitfalls Research: MOCA

## Critical Pitfalls

### 1. LangGraph State Explosion

- **What goes wrong**: The graph state object accumulates every message, tool result, and intermediate value. Within a few turns the state becomes massive, causing serialization slowdowns, checkpoint bloat, and hitting LLM context limits. Developers add fields to state "just in case" and never prune.
- **Warning signs**: Checkpoint sizes growing beyond 100KB; graph resumption taking >2s; LLM calls failing with token limit errors on longer conversations.
- **Prevention**: Define a minimal TypedDict state up front. Only store what downstream nodes actually read. Summarize or truncate message history before it hits the LLM. Use `add_messages` reducer with a max-length window.
- **Recovery**: Refactor state to separate "hot" (current turn) from "cold" (audit log) data. Move audit data to DB writes inside nodes rather than carrying it in state.
- **Phase relevance**: Phase 1 (graph skeleton) — get the state schema right before building nodes.

### 2. LangGraph Interrupt/Resume Serialization Bugs

- **What goes wrong**: When a graph hits an interrupt (for human approval), the entire state must be serialized to a checkpoint store and later deserialized to resume. Non-serializable objects (DB connections, httpx clients, datetime objects without serializers, Pydantic models with custom validators) silently corrupt or crash on resume.
- **Warning signs**: Graph works fine without interrupts but fails on resume; "pickle" or JSON serialization errors in logs; state values are None or wrong type after resume.
- **Prevention**: Keep state values as plain dicts, strings, numbers, and lists. Test the interrupt→resume cycle from day one with a trivial approval node. Never put connection objects or callables in state.
- **Recovery**: Add a `test_interrupt_resume` integration test that serializes and deserializes state at every interrupt point. Fix by extracting non-serializable values into node-local variables fetched fresh on resume.
- **Phase relevance**: Phase 1-2 — must be validated before building the real approval workflow.

### 3. LangGraph Graph Complexity Spiral

- **What goes wrong**: Developer starts with a clean linear graph, then adds conditional edges, retry loops, parallel branches, and sub-graphs. The graph becomes impossible to visualize, debug, or explain in an interview. Edge conditions have subtle ordering bugs.
- **Warning signs**: More than 8-10 nodes in a single graph; conditional edges with >3 branches; you can't draw the graph on a whiteboard in 30 seconds.
- **Prevention**: Keep the main graph to 5-7 nodes max. Use a single conditional router node rather than complex edge logic. If a sub-flow is complex, extract it to a tested utility function called within a node — not a sub-graph.
- **Recovery**: Flatten. Merge nodes that always run sequentially. Replace sub-graphs with function calls inside nodes.
- **Phase relevance**: Phase 1 (architecture) — lock the graph shape early, resist adding nodes later.

### 4. RAG Chunking Destroys Context

- **What goes wrong**: Naive fixed-size chunking splits documents mid-sentence, mid-table, or mid-rule. A refund policy that says "if order > 500 yuan AND within 7 days, then..." gets split so the retriever returns only half the condition. The agent then gives wrong answers confidently.
- **Warning signs**: Retrieved chunks that start or end mid-sentence; agent answers that contradict the source document; citation points to a chunk but the chunk is incomplete.
- **Prevention**: Use semantic/structural chunking — split on headers, numbered rules, or paragraph boundaries. For structured policy docs, chunk by rule/section. Keep chunk sizes 300-800 tokens with 50-100 token overlap. Test retrieval quality manually on 10 representative queries before building further.
- **Recovery**: Re-chunk with better boundaries. Add a "parent document" retrieval strategy — retrieve the chunk but return the full parent section for context.
- **Phase relevance**: Phase 2 (RAG pipeline) — chunking strategy must be validated before ingesting all documents.

### 5. RAG Citation Hallucination

- **What goes wrong**: The LLM generates an answer and attributes it to a retrieved document, but the document doesn't actually say that. Or worse, the citation format is inconsistent so the frontend can't link back to the source. Interviewers will check citations — if they're wrong, the entire "evidence-first" claim collapses.
- **Warning signs**: Citations that reference document IDs not in the retrieval results; answers that go beyond what the retrieved chunks actually state; citation format varying between responses.
- **Prevention**: Use a strict prompt template: "Answer ONLY based on the following evidence. If the evidence doesn't contain the answer, say so. Cite using [DOC-ID] format." Include the document ID in the chunk metadata. Post-process: verify every cited ID exists in the retrieval results. Build an eval set of 20 Q&A pairs with known correct citations.
- **Recovery**: Add a citation validation step after LLM response — strip any citation that doesn't match a retrieved chunk ID. Log citation accuracy as a metric.
- **Phase relevance**: Phase 2-3 — must be solid before demo.

### 6. RAG Retrieval Returns Irrelevant Results

- **What goes wrong**: Vector similarity search returns semantically similar but factually irrelevant documents. "How do I get a refund for a damaged item?" retrieves "How do I return an undamaged item?" because the embeddings are close. With only 20-50 policy documents, this is especially painful — every miss is obvious.
- **Warning signs**: Top-3 results don't contain the answer for known test queries; retrieval works for simple keyword-match queries but fails for nuanced ones.
- **Prevention**: Hybrid search (vector + keyword/BM25). For a small corpus, metadata filtering is powerful — tag documents by category (refund, shipping, compensation) and filter before vector search. Test retrieval in isolation before connecting to the agent. Consider a reranker (cross-encoder) for the top-10 → top-3 step.
- **Recovery**: Add metadata filters. If corpus is small (<100 docs), consider a simple keyword fallback. Tune the similarity threshold — don't return results below 0.7 cosine similarity.
- **Phase relevance**: Phase 2 (RAG) — validate retrieval quality before integrating with agent.

### 7. FastAPI Async + Sync Database Mixing

- **What goes wrong**: FastAPI runs on asyncio, but SQLAlchemy's default session is synchronous. Calling sync DB operations inside async endpoints blocks the event loop, causing all concurrent requests to stall. Alternatively, using `run_in_executor` everywhere adds complexity and subtle bugs.
- **Warning signs**: Response times spike under concurrent load; endpoints that work fine alone become slow when called together; "RuntimeWarning: coroutine was never awaited" in logs.
- **Prevention**: Use SQLAlchemy 2.0 async engine (`create_async_engine`) with `AsyncSession` from the start. All DB access through async sessions. Use `asyncpg` as the driver, not `psycopg2`. Define the pattern in Phase 1 and never deviate.
- **Recovery**: Migrate to async engine. It's painful if done late — affects every repository/service function. Better to start right.
- **Phase relevance**: Phase 1 (foundation) — async DB pattern must be established in the first endpoint.

### 8. FastAPI Dependency Injection Lifecycle Leaks

- **What goes wrong**: Database sessions or Redis connections created in `Depends()` aren't properly closed on exceptions. Connection pool exhaustion follows — the app works for 50 requests then hangs.
- **Warning signs**: "too many connections" errors after running for a while; connections in `idle in transaction` state in pg_stat_activity; app works after restart but degrades over time.
- **Prevention**: Always use `async with` or try/finally in dependency generators. Use `yield`-based dependencies with proper cleanup. Set connection pool limits explicitly (`pool_size=5, max_overflow=10`). Add a health check endpoint that reports pool status.
- **Recovery**: Add connection pool monitoring. Wrap all DB dependencies in proper context managers. Set `pool_pre_ping=True` to detect stale connections.
- **Phase relevance**: Phase 1 (foundation) — get the dependency pattern right in the first endpoint.

### 9. pgvector Index Missing or Misconfigured

- **What goes wrong**: Developer inserts vectors and queries work... slowly. Without an IVFFlat or HNSW index, pgvector does sequential scan. With 10K+ vectors this means 200ms+ per query. Or the index is created with wrong parameters (too few lists for IVFFlat, wrong distance metric).
- **Warning signs**: Vector search queries taking >50ms on small datasets; EXPLAIN shows sequential scan on the vector column; search results change after adding an index (wrong distance metric).
- **Prevention**: Create HNSW index (preferred for <1M vectors, no training needed): `CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`. Use cosine distance consistently (match embedding model's training). Create index AFTER bulk insert, not before.
- **Recovery**: Drop and recreate index with correct parameters. Verify with `EXPLAIN ANALYZE` that the index is being used.
- **Phase relevance**: Phase 2 (RAG/vector setup) — create index as part of the seed script.

### 10. pgvector Dimension Mismatch

- **What goes wrong**: The vector column is defined as `vector(1536)` (OpenAI ada-002) but the actual embedding model produces 768 or 3072 dimensions. Insert fails silently or with a cryptic error. Switching embedding models later requires re-creating the column and re-embedding everything.
- **Warning signs**: Insert errors mentioning dimension mismatch; deciding to switch embedding models mid-project.
- **Prevention**: Define the embedding dimension as a config constant. Validate dimension at ingestion time. Document which model produces which dimension. If using OpenAI text-embedding-3-small (1536) or text-embedding-3-large (3072), lock it in early.
- **Recovery**: Alter column dimension, re-embed all documents. This is why you want a small corpus — re-embedding 50 docs takes seconds, 50K docs takes hours.
- **Phase relevance**: Phase 2 — lock embedding model choice before ingesting documents.

### 11. Docker Compose Startup Order Race Conditions

- **What goes wrong**: App container starts before Postgres is ready to accept connections. `depends_on` only waits for container start, not service readiness. The app crashes on first request, or the seed script fails because the DB isn't ready.
- **Warning signs**: Intermittent startup failures; "connection refused" on first run; works on second `docker compose up` but not first.
- **Prevention**: Use `depends_on` with `condition: service_healthy` and proper healthchecks for Postgres and Redis. Add retry logic in app startup (3 retries with 2s backoff). Use a wait-for-it script or built-in healthcheck.
- **Recovery**: Add healthchecks to docker-compose.yml. Add startup retry logic to the app's DB initialization.
- **Phase relevance**: Phase 1 (infrastructure) — must work reliably from day one for "one-command startup" claim.

### 12. LLM API Failures Without Graceful Degradation

- **What goes wrong**: The LLM API (OpenAI, or local vLLM) returns a 429, 500, or timeout. The entire agent crashes with an unhandled exception. During a demo, this means a blank screen or error page.
- **Warning signs**: No try/except around LLM calls; no retry logic; no timeout configuration; demo works 9/10 times but fails unpredictably.
- **Prevention**: Wrap all LLM calls with retry (3 attempts, exponential backoff). Set explicit timeouts (30s). Return a graceful error message to the user: "I'm having trouble processing this right now." For demos, have a local model fallback or pre-cached responses for key demo scenarios.
- **Recovery**: Add retry middleware. For critical demo paths, consider caching known-good responses that can be replayed if the API is down.
- **Phase relevance**: Phase 3 (integration) — add resilience before demo preparation.

---

## "Looks Like a Toy" Signals

Things that make interviewers dismiss the project:

- **Single happy path only**: Agent works for the one demo query but fails on any variation → Build 5-10 test scenarios covering edge cases (missing order, expired refund window, insufficient permissions).

- **No error states in UI**: Errors show as raw JSON or blank screen → Design error states: loading spinners, error messages, retry buttons, timeout notices.

- **Hardcoded responses or prompts visible in output**: LLM clearly following a rigid template with no real reasoning → Use dynamic prompts that incorporate actual retrieved data; show the agent "thinking" with intermediate steps visible.

- **No data variety**: All demo orders have the same structure and amounts → Seed 50+ orders with varied statuses, amounts, dates, product categories, and dispute reasons.

- **Instant responses (obviously fake)**: Agent responds in <100ms, clearly not calling an LLM → Show realistic latency with streaming responses. Display "retrieving evidence..." and "analyzing..." steps.

- **No permission model visible**: Everyone can do everything → Show different views for merchant vs. support vs. manager. Demonstrate that a merchant CANNOT approve their own compensation.

- **No audit trail accessible**: Claims "full audit" but no way to view it → Add an audit log page showing the chain: query → retrieval → reasoning → decision → approval.

- **README has no architecture diagram**: Just a wall of text → Include a clear system architecture diagram and a graph flow diagram. Interviewers scan READMEs in 30 seconds.

- **No metrics or evaluation**: No way to measure if the system actually works → Include a simple eval script that runs test queries and reports retrieval accuracy + answer correctness.

- **Docker Compose doesn't actually work on first try**: "Works on my machine" → Test on a clean machine (or CI). Pin all image versions. Include `.env.example`.

---

## Demo Killers

Things that break during live demonstrations:

- **LLM API rate limit or outage**: Prevention — use a local model (Ollama) as fallback; pre-warm the API with a health check before demo; have 2-3 pre-recorded demo videos as backup.

- **Docker Compose fails on interviewer's machine**: Prevention — pin ALL versions (Python packages, Node modules, Docker images). Test `docker compose up` from a clean clone weekly. Include a "Quick Start" that's actually quick (<3 minutes to running).

- **Database not seeded / empty state**: Prevention — make seeding part of the startup script (run migrations + seed on first boot). Add a "reset demo data" button or command.

- **Slow cold start (>60s)**: Prevention — pre-build images, use multi-stage Docker builds, lazy-load heavy dependencies. First response should come within 10s of asking a question.

- **WebSocket/SSE disconnection during streaming**: Prevention — implement reconnection logic in frontend. Use polling fallback. Test with network throttling.

- **CORS errors when frontend calls backend**: Prevention — configure CORS in FastAPI from day one with explicit origins. Test cross-origin in Docker (frontend on :3000, backend on :8000).

- **Environment variable missing**: Prevention — validate ALL required env vars at startup with clear error messages. Provide `.env.example` with every variable documented. Fail fast with "Missing OPENAI_API_KEY" not a cryptic traceback.

- **Approval workflow gets stuck**: Prevention — add a timeout on approval waits (auto-expire after 5 minutes in demo mode). Add a "force resume" admin endpoint for emergencies.

- **Chinese characters display as garbled text**: Prevention — ensure UTF-8 everywhere: database encoding, API responses with proper Content-Type, frontend meta charset. Test with actual Chinese demo data from day one.

- **Browser caching shows stale state**: Prevention — add cache-busting headers to API responses. Use React Query or SWR with proper invalidation. Add a visible "last updated" timestamp.

---

## Scope Creep Traps

Features that seem small but explode in complexity:

- **"Let's add multi-turn conversation memory"**: Why it's a trap — requires conversation storage, context window management, memory summarization, and changes the entire state management approach. A single-turn Q&A with context from retrieved docs is 10x simpler and still impressive. → Do single-turn first. Add conversation memory only in polish phase, and only for the current session (not persistent cross-session memory).

- **"Let's support multiple LLM providers"**: Why it's a trap — each provider has different API shapes, token counting, streaming formats, and error codes. Abstraction layers add complexity without demo value. → Pick one provider (OpenAI-compatible API). Use it everywhere. Add a provider abstraction only if you actually need to switch.

- **"Let's add real-time notifications for approvals"**: Why it's a trap — requires WebSocket infrastructure, connection management, reconnection logic, and frontend state sync. → Use polling (every 3s) for approval status. It's simpler, more reliable, and visually identical in a demo.

- **"Let's build a proper admin dashboard"**: Why it's a trap — dashboards need charts, filters, pagination, date ranges, export. Each "simple" feature is a full frontend component. → Build ONE admin page: the audit log list with basic filtering. That's enough to prove the concept.

- **"Let's add document upload for the knowledge base"**: Why it's a trap — file upload needs validation, parsing (PDF/DOCX/HTML), chunking pipeline, progress tracking, error handling for malformed files. → Pre-ingest documents via a CLI script. The knowledge base is static for the demo. Show the ingestion script in the README as "how to add new documents."

- **"Let's implement proper RBAC with dynamic roles"**: Why it's a trap — dynamic role management needs a role editor UI, permission inheritance, role-to-scope mapping, and testing every endpoint with every role combination. → Hardcode 4 roles (merchant, support, reviewer, manager) with fixed permission sets. Define them as enums. No role editor needed.

- **"Let's add comprehensive logging and monitoring"**: Why it's a trap — proper observability means structured logging, log aggregation, metrics collection, dashboards, alerting rules. → Add structured JSON logs to stdout. Add one OTel trace per agent run. Add a `/health` endpoint. That's production-grade enough for a portfolio project.

- **"Let's make the agent handle multiple scenarios"**: Why it's a trap — each new scenario (returns, shipping disputes, seller penalties) needs its own tools, test data, evaluation set, and prompt tuning. → Perfect ONE scenario (refund disputes) end-to-end. Mention others in the README as "planned extensions." One polished scenario beats three half-working ones.

- **"Let's add caching for LLM responses"**: Why it's a trap — cache invalidation for LLM responses is genuinely hard. When do you invalidate? What's the cache key when context changes? Stale cached answers during demo are worse than slow fresh answers. → Cache embeddings and retrieval results (deterministic). Don't cache LLM responses unless you have a very clear invalidation strategy.

- **"Let's add user authentication with OAuth/SSO"**: Why it's a trap — OAuth flows need redirect handling, token refresh, session management, CSRF protection, and testing with real providers. → Use simple JWT with hardcoded demo users (login as "merchant_zhang" or "manager_li"). No registration flow. No password reset. Authentication is not what this project demonstrates.
