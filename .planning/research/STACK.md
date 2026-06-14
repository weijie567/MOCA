# Stack Research: MOCA

> **Note**: Versions below are based on knowledge as of May 2025. Run `pip index versions <package>` to confirm latest before pinning. Minor versions may have incremented since then.

## Recommended Stack

### LangGraph (Agent Orchestration)
- **Library**: `langgraph` 0.3.x (pin to latest 0.3.x at time of install)
- **Why**: First-class support for stateful, multi-step agent workflows with cycles. Built on LangChain primitives but designed for agent-level control flow (conditional edges, human-in-the-loop, persistence). The graph-based mental model maps cleanly to merchant operations workflows (order handling, customer inquiry routing, inventory checks).
- **Configuration notes**:
  - Use `langgraph` (not `langgraph-sdk` which is for LangGraph Platform/Cloud)
  - Pin `langchain-core` >= 0.3.0 alongside it for compatibility
  - Use `SqliteSaver` or `PostgresSaver` for checkpoint persistence (not in-memory for anything beyond dev)
  - Prefer `StateGraph` over legacy `MessageGraph`
  - Use `@tool` decorator from `langchain-core` for tool definitions
- **Key dependencies**: `langchain-core`, `langchain-openai` (or `langchain-anthropic`), `langgraph-checkpoint-postgres`
- **Confidence**: High (architecture choice); Medium (exact version — verify latest)

### FastAPI (API Layer)
- **Library**: `fastapi` 0.115.x
- **Why**: Async-native, automatic OpenAPI docs, Pydantic v2 integration, excellent for building the API layer that fronts the agent. Mature ecosystem, great DX for a solo developer.
- **Configuration notes**:
  - Use Pydantic v2 models (FastAPI 0.100+ requires Pydantic v2)
  - Use `lifespan` context manager (not deprecated `on_event`)
  - Use `fastapi[standard]` which bundles uvicorn
  - Structure: `app/main.py`, `app/routers/`, `app/models/`, `app/services/`
  - Enable CORS middleware for frontend dev
  - Use `BackgroundTasks` or integrate with LangGraph's async for long-running agent calls
  - Consider SSE (`sse-starlette`) for streaming agent responses to frontend
- **Key dependencies**: `uvicorn[standard]`, `pydantic` >= 2.5, `sse-starlette`
- **Confidence**: High

### PostgreSQL + pgvector (Data + Vector Store)
- **Library**: PostgreSQL 16, `pgvector` extension 0.7.x, Python driver `asyncpg` 0.30.x + `pgvector` Python package 0.3.x
- **Why**: Single database for both relational data (orders, products, merchants) and vector embeddings (product descriptions, FAQ, knowledge base). Eliminates need for a separate vector DB like Pinecone/Weaviate, reducing infra complexity for a solo project.
- **Configuration notes**:
  - Use `pgvector` with HNSW index (not IVFFlat) for better recall without tuning: `CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops)`
  - Set `m = 16`, `ef_construction = 64` for HNSW (good defaults for < 1M vectors)
  - Embedding dimension: 1536 (OpenAI text-embedding-3-small) or 1024 (if using Cohere)
  - Use `asyncpg` for async access from FastAPI, `psycopg[binary]` 3.x as fallback
  - Use SQLAlchemy 2.0 async with `asyncpg` dialect for ORM needs
  - Docker image: `pgvector/pgvector:pg16`
- **Key dependencies**: `sqlalchemy[asyncio]` >= 2.0.30, `asyncpg`, `pgvector`, `alembic` (migrations)
- **Confidence**: High

### Redis (Non-Authoritative Cache + Rate Limiting)
- **Library**: Redis 7.x (server), `redis` Python package >= 5.0 (async support built-in)
- **Why**: Caching repeated lookups, rate limiting API calls, short-TTL runtime hints, and potentially as a message broker for background tasks. Fast, simple, well-understood. Redis must not be the authoritative store for session memory, workflow checkpoint source-of-truth state, approval/action state, or replay/audit events.
- **Configuration notes**:
  - Use `redis.asyncio` client (built into `redis` >= 5.0, no separate `aioredis` needed)
  - Cache strategy: cache embedding lookups, repeated LLM calls, and optional session hot views with TTL
  - Use PostgreSQL for LangGraph checkpoint source-of-truth state; Redis may only cache active-run hot state that can fall back to PostgreSQL
  - Docker image: `redis:7-alpine`
  - Consider `redis-om` only if you need secondary indexing on cached objects (probably overkill here)
- **Key dependencies**: `redis` >= 5.0
- **Confidence**: High

### LlamaIndex (RAG Ingestion Pipeline)
- **Library**: `llama-index` 0.12.x (or latest 0.11.x — verify)
- **Why**: Best-in-class for document ingestion, chunking, and index building. Use it specifically for the offline/batch RAG pipeline (ingesting product catalogs, merchant docs, FAQ), not for runtime query orchestration (that's LangGraph's job).
- **Configuration notes**:
  - Use modular install: `llama-index-core`, `llama-index-vector-stores-postgres`, `llama-index-embeddings-openai`
  - Do NOT install monolithic `llama-index` in production — use individual packages
  - Use `PGVectorStore` from `llama-index-vector-stores-postgres` to write directly to your pgvector tables
  - Chunking: `SentenceSplitter` with `chunk_size=512`, `chunk_overlap=50` as starting point
  - Use `IngestionPipeline` for reproducible ETL
  - Keep LlamaIndex isolated to ingestion scripts — do NOT use it at query time (use raw pgvector queries via SQLAlchemy instead, for lower latency and fewer dependencies in the hot path)
- **Key dependencies**: `llama-index-core`, `llama-index-vector-stores-postgres`, `llama-index-readers-file`, `llama-index-embeddings-openai`
- **Confidence**: Medium (version number — LlamaIndex releases frequently and has had major API changes)

### Docker Compose (Local Infrastructure)
- **Library**: Docker Compose v2 (built into Docker Desktop)
- **Why**: Single `docker compose up` to run Postgres, Redis, and optionally the app itself. Essential for reproducible local dev and demo-ability in interviews.
- **Configuration notes**:
  - Services: `postgres` (pgvector/pgvector:pg16), `redis` (redis:7-alpine), `app` (your FastAPI app)
  - Use named volumes for Postgres data persistence
  - Use healthchecks so app waits for DB readiness
  - Use `.env` file for secrets (add to .gitignore)
  - Expose Postgres on 5432, Redis on 6379, App on 8000
  - Add `pgadmin` service for DB inspection during dev (optional)
- **Confidence**: High

### Frontend (React/Next.js)
- **Library**: Next.js 14.x (App Router), React 18.x, TypeScript
- **Why**: App Router gives you server components and API routes. For a portfolio project, it provides a polished UI with minimal effort. Vercel deployment is free for demos.
- **Configuration notes**:
  - Use App Router (`app/` directory), not Pages Router
  - Keep it simple: 3-5 pages max (dashboard, chat interface, order list, settings)
  - Use `shadcn/ui` for components (copy-paste, no heavy dependency)
  - Use `swr` or `tanstack-query` for data fetching
  - Use Server-Sent Events for streaming agent responses (not WebSocket — simpler)
  - Tailwind CSS for styling
  - Do NOT over-invest here — the backend/agent is the star of the show
- **Key dependencies**: `next` 14.x, `react` 18.x, `tailwindcss`, `shadcn/ui`, `swr`
- **Confidence**: High (architecture); Medium (Next.js 15 may be stable by now — check)

### LLM Provider
- **Library**: OpenAI API via `langchain-openai` or `openai` >= 1.40
- **Why**: GPT-4o for agent reasoning, text-embedding-3-small for embeddings. Best balance of capability, speed, and cost for a demo project. Chinese companies are familiar with OpenAI API patterns.
- **Configuration notes**:
  - Use `gpt-4o-mini` for most agent steps (fast, cheap), `gpt-4o` for complex reasoning steps
  - Use `text-embedding-3-small` (1536 dim) for embeddings — good quality/cost ratio
  - Set temperature=0 for tool-calling steps, 0.3-0.7 for generation
  - Implement retry with exponential backoff
  - Consider adding `zhipuai` (GLM-4) or `dashscope` (Qwen) as alternative for China-based demos
- **Confidence**: High

### Python Environment & Tooling
- **Library**: Python 3.11 (not 3.12/3.13 — better library compatibility), `uv` for package management
- **Why**: 3.11 has the best balance of performance improvements and library compatibility. `uv` is dramatically faster than pip/poetry for installs and resolves.
- **Configuration notes**:
  - Use `uv` (by Astral) instead of pip/poetry — 10-100x faster, better resolver
  - Use `pyproject.toml` for project metadata
  - Use `uv.lock` for reproducible installs
  - Linting: `ruff` (replaces flake8, isort, black in one tool)
  - Type checking: `pyright` or `mypy` (optional for 4-week timeline)
- **Confidence**: High

## What NOT to Use

- **LangChain (full framework)** — Too much abstraction, too many breaking changes, hard to debug. Use `langchain-core` for primitives (tools, messages) but avoid `langchain` the framework. LangGraph is the right layer for orchestration.
- **Pinecone / Weaviate / Qdrant / Milvus** — Adding a separate vector DB when pgvector handles your scale (< 1M vectors) adds unnecessary infra complexity. pgvector in Postgres is sufficient and keeps your stack simpler.
- **Celery** — Overkill for a solo project. Use FastAPI BackgroundTasks or LangGraph's built-in async. If you need a task queue later, consider `arq` (Redis-based, async-native, much simpler).
- **LangServe** — Deprecated in favor of LangGraph Platform. Don't use it.
- **AutoGen / CrewAI** — Multi-agent frameworks that add complexity without proportional benefit for a single-developer project. LangGraph gives you multi-agent patterns without the framework lock-in.
- **MongoDB** — No good reason to add a document DB when Postgres handles JSON (jsonb) and vectors. Adds operational complexity.
- **Kubernetes / Helm** — Way overkill for local dev and demo. Docker Compose is the right level.
- **GraphQL** — REST + SSE is simpler and sufficient. GraphQL adds schema complexity without clear benefit for this use case.
- **aioredis** — Deprecated. Use `redis` >= 5.0 which has built-in async support.
- **Pydantic v1** — FastAPI 0.100+ requires v2. Don't use v1 compatibility mode.
- **SQLAlchemy 1.x** — Use 2.0 style with async support. The 1.x query API is legacy.
- **LlamaIndex at query time** — Use it for ingestion only. At query time, use raw SQL/pgvector queries for lower latency and fewer moving parts.
- **Chroma** — In-memory vector DB, not suitable for production patterns. Use pgvector.

## Integration Patterns

### 1. FastAPI ↔ LangGraph (Agent Invocation)
```python
# app/services/agent.py
from langgraph.graph import StateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async def get_agent():
    checkpointer = AsyncPostgresSaver.from_conn_string(DATABASE_URL)
    graph = create_graph()  # your StateGraph
    return graph.compile(checkpointer=checkpointer)

# app/routers/chat.py
@router.post("/chat")
async def chat(request: ChatRequest):
    agent = await get_agent()
    config = {"configurable": {"thread_id": request.session_id}}
    result = await agent.ainvoke({"messages": [request.message]}, config)
    return result
```

### 2. LangGraph ↔ pgvector (RAG Retrieval as Tool)
```python
# Agent tool that queries pgvector directly
@tool
async def search_knowledge_base(query: str) -> str:
    """Search merchant knowledge base for relevant information."""
    embedding = await get_embedding(query)
    async with get_db_session() as session:
        results = await session.execute(
            text("""
                SELECT content, 1 - (embedding <=> :query_vec) as similarity
                FROM knowledge_chunks
                WHERE 1 - (embedding <=> :query_vec) > 0.7
                ORDER BY embedding <=> :query_vec
                LIMIT 5
            """),
            {"query_vec": str(embedding)}
        )
        return "\n".join(row.content for row in results)
```

### 3. LlamaIndex → pgvector (Offline Ingestion)
```python
# scripts/ingest.py — run offline, not in the API server
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter

vector_store = PGVectorStore.from_params(
    database="moca", host="localhost", port="5432",
    table_name="knowledge_chunks", embed_dim=1536
)
pipeline = IngestionPipeline(
    transformations=[SentenceSplitter(chunk_size=512, chunk_overlap=50)],
    vector_store=vector_store,
)
pipeline.run(documents=documents)
```

### 4. Redis Caching Pattern
```python
# app/services/cache.py
import redis.asyncio as redis
import json, hashlib

cache = redis.from_url("redis://localhost:6379")

async def cached_embedding(text: str) -> list[float]:
    key = f"emb:{hashlib.md5(text.encode()).hexdigest()}"
    cached = await cache.get(key)
    if cached:
        return json.loads(cached)
    embedding = await openai_client.embeddings.create(input=text, model="text-embedding-3-small")
    result = embedding.data[0].embedding
    await cache.setex(key, 3600, json.dumps(result))  # 1hr TTL
    return result
```

### 5. SSE Streaming (FastAPI → Frontend)
```python
# app/routers/chat.py
from sse_starlette.sse import EventSourceResponse

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        agent = await get_agent()
        config = {"configurable": {"thread_id": request.session_id}}
        async for event in agent.astream_events(
            {"messages": [request.message]}, config, version="v2"
        ):
            if event["event"] == "on_chat_model_stream":
                yield {"data": json.dumps({"token": event["data"]["chunk"].content})}
        yield {"data": json.dumps({"done": True})}
    return EventSourceResponse(event_generator())
```

### 6. Project Structure
```
MOCA/
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── alembic/                  # DB migrations
├── app/
│   ├── main.py              # FastAPI app + lifespan
│   ├── config.py            # Settings via pydantic-settings
│   ├── routers/
│   │   ├── chat.py          # Agent interaction endpoints
│   │   ├── orders.py        # Order management CRUD
│   │   └── products.py      # Product catalog
│   ├── models/              # SQLAlchemy + Pydantic models
│   ├── services/
│   │   ├── agent.py         # LangGraph agent definition
│   │   ├── cache.py         # Redis caching
│   │   └── embeddings.py    # Embedding utilities
│   └── tools/               # LangGraph tools
│       ├── order_tools.py
│       ├── product_tools.py
│       └── knowledge_tools.py
├── scripts/
│   └── ingest.py            # LlamaIndex ingestion pipeline
├── frontend/                # Next.js app
└── tests/
```

## Open Questions

- **LlamaIndex version stability**: LlamaIndex has had multiple major API rewrites (0.9 → 0.10 → 0.11 → 0.12). Verify the current stable API before committing. If the API has changed significantly, consider using `langchain-community` document loaders + manual chunking as a simpler alternative.
- **LangGraph version**: LangGraph is pre-1.0 and evolving rapidly. Pin to a specific version and don't upgrade mid-project. Check if `langgraph-checkpoint-postgres` is still the correct package name.
- **Next.js 14 vs 15**: Next.js 15 may be fully stable by now. Check if App Router patterns have changed. If 15 is stable, prefer it.
- **Python 3.12 compatibility**: By mid-2026, most libraries should support 3.12 well. If all your dependencies support it, 3.12 is fine (better error messages, performance). Test before committing.
- **Chinese LLM fallback**: If demoing in China where OpenAI access is unreliable, have a `zhipuai` (GLM-4) or `dashscope` (Qwen-Max) integration ready. Both have OpenAI-compatible APIs, making the switch easy via `langchain-community`.
- **Embedding model choice**: `text-embedding-3-small` (1536d) vs `text-embedding-3-large` (3072d) — small is sufficient for a demo. If using Chinese content heavily, consider `BAAI/bge-m3` via a local embedding service.
- **Authentication**: For a portfolio project, simple JWT auth is sufficient. Don't over-engineer with OAuth2 flows unless the interview specifically values it.

## Version Verification Checklist

Before starting development, run these to pin exact versions:

```bash
uv pip install --dry-run langgraph fastapi "sqlalchemy[asyncio]" asyncpg pgvector redis llama-index-core uvicorn pydantic-settings alembic sse-starlette
```

This will show you the resolved versions. Pin those exact versions in `pyproject.toml`.
