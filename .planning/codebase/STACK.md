# Technology Stack

**Analysis Date:** 2026-06-05

## Languages

**Primary:**
- Python 3.12 - Backend API, agent graph, RAG pipeline, repositories, migrations, scripts, and tests
- TypeScript - Frontend Vite/React client in `frontend/`

**Secondary:**
- Markdown - Planning, architecture, evaluation, demo, and security documentation
- YAML - Risk rules in `rules/risk_rules.yaml`
- JSON / JSONL - Golden evaluation datasets and API fixtures

## Runtime

**Backend:**
- FastAPI application entry point: `src/api/main.py`
- Uvicorn runtime via `uvicorn src.api.main:app`
- Async SQLAlchemy session layer in `src/db/session.py`
- Alembic migrations under `src/db/migrations/`
- LangGraph graph construction in `src/agent/graph.py`

**Frontend:**
- Vite + React + TypeScript application under `frontend/`
- Main entry point: `frontend/src/main.tsx`
- App shell: `frontend/src/App.tsx`

**Package Managers:**
- Python: `uv` with `pyproject.toml` and `uv.lock`
- Frontend: npm with `frontend/package.json` and `frontend/package-lock.json`

## Frameworks

**Implemented:**
- FastAPI - API layer, middleware, auth dependencies, REST endpoints, and SSE agent-run streaming
- Pydantic / Pydantic Settings - API schemas, settings, tool contracts, and RAG schemas
- SQLAlchemy 2.0 async - ORM models and repositories
- Alembic - Database migration management
- LangGraph - Agent orchestration, checkpointing, interrupt/resume approval flow
- langgraph-checkpoint-postgres - Postgres-backed graph checkpoint persistence
- pgvector - Vector storage support for policy chunks
- OpenAI / LangChain OpenAI packages - Model-compatible integration surface
- Redis - Local service dependency for cache/rate-limit style infrastructure
- React + Vite - Frontend UI
- Tailwind CSS / shadcn-style UI components - Frontend styling and component primitives

**Workflow and Quality:**
- pytest / pytest-asyncio - Backend test runner
- httpx - Async API tests
- Ruff - Python linting
- Docker Compose - Local Postgres, Redis, and API orchestration

## Key Dependencies

**Backend from `pyproject.toml`:**
- `fastapi`, `uvicorn[standard]`
- `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
- `pydantic-settings`
- `pyjwt`, `bcrypt`, `python-multipart`
- `redis`, `pgvector`
- `openai`, `langgraph`, `langgraph-checkpoint-postgres`, `langchain-openai`, `langchain-core`
- `psycopg[binary,pool]`
- `sse-starlette`

**Frontend from `frontend/package.json`:**
- React/Vite TypeScript toolchain
- Tailwind and component utilities
- Local tests for frontend hooks

## Configuration

**Environment:**
- `.env.example` documents backend configuration
- `.env` exists locally and must remain treated as non-source secret material
- `src/config.py` centralizes settings through Pydantic Settings

**Build and Tooling:**
- `Dockerfile`, `docker-compose.yml`, and `docker-entrypoint.sh` define local runtime packaging
- `Makefile` provides project commands
- `pyproject.toml` defines Ruff and pytest settings
- `frontend/vite.config.ts`, `frontend/tsconfig*.json`, `frontend/eslint.config.js`, and `frontend/tailwind.config.ts` define frontend tooling

## Platform Requirements

**Development:**
- Python 3.12
- `uv`
- Docker and Docker Compose
- Node.js/npm for frontend work

**Local Services:**
- PostgreSQL with pgvector
- Redis

**Production Posture:**
- Not production-deployed yet
- Architecture is currently optimized for local demo, testability, and interview-grade end-to-end proof

---
*Stack analysis: 2026-06-05*
*Refresh after major phase execution, dependency changes, or frontend/backend scaffold changes*
