---
phase: 03-langgraph-core
plan: "01"
subsystem: database
tags: [langgraph, langchain, postgres, alembic, sqlalchemy, pydantic-settings]

requires:
  - phase: 02-rag-pipeline
    provides: "Database, RAG retrieval baseline, and existing async SQLAlchemy/Alembic patterns"
provides:
  - "LangGraph, LangChain, and psycopg dependency declarations"
  - "LLM settings and derived psycopg checkpointer database URL"
  - "AgentRun and AgentStep ORM models for execution trace persistence"
  - "Alembic migration 003 for agent_runs and agent_steps tables"
affects: [03-langgraph-core, agent-runtime, trace-persistence, checkpointer]

tech-stack:
  added: [langgraph, langgraph-checkpoint-postgres, langchain-openai, langchain-core, psycopg]
  patterns:
    - "Derived checkpointer URL from Settings.database_url for psycopg compatibility"
    - "Agent trace tables use SQLAlchemy 2.0 mapped_column and TimestampMixin"

key-files:
  created:
    - src/db/migrations/versions/003_agent_tables.py
  modified:
    - pyproject.toml
    - uv.lock
    - src/config.py
    - src/db/models.py
    - .env.example

key-decisions:
  - "checkpointer_database_url is a derived Settings property, not an env-loaded pydantic field."
  - "Migration 003 uses down_revision 002_rag_pipeline to match the repository's actual Alembic chain."

patterns-established:
  - "LangGraph PostgresSaver should use postgresql:// psycopg URLs, while SQLAlchemy continues using postgresql+asyncpg://."
  - "Agent execution trace persistence is split into run-level AgentRun rows and node-level AgentStep rows."

requirements-completed: [AGNT-02, AGNT-05, AGNT-06, INFR-09, SAFE-06]

duration: 29m
completed: 2026-05-11
---

# Phase 03 Plan 01: Dependencies, Config, and Agent Trace Tables Summary

**LangGraph foundation with GLM/DashScope settings, psycopg checkpointer URL derivation, and durable agent run/step trace tables**

## Performance

- **Duration:** 29m
- **Started:** 2026-05-11T07:18:10Z
- **Completed:** 2026-05-11T07:47:16Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added LangGraph, checkpoint, LangChain OpenAI-compatible, and psycopg dependencies to `pyproject.toml` and refreshed `uv.lock`.
- Extended `Settings` with DashScope/GLM LLM options and a derived `checkpointer_database_url` that converts the async SQLAlchemy URL to a psycopg URL.
- Added `AgentRun` and `AgentStep` ORM models plus migration 003 to create `agent_runs` and `agent_steps`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add LangGraph dependencies and extend Settings** - `feb3047` (feat)
2. **Task 2: Add AgentRun and AgentStep models + Alembic migration** - `9f0a55e` (feat)

## Files Created/Modified

- `pyproject.toml` - Declares LangGraph, LangGraph checkpoint, LangChain, and psycopg dependencies.
- `uv.lock` - Locks the new dependency graph.
- `src/config.py` - Adds LLM settings and derived checkpointer database URL.
- `.env.example` - Documents placeholder DashScope and LLM env vars without real secrets.
- `src/db/models.py` - Adds `AgentRun` and `AgentStep` trace models.
- `src/db/migrations/versions/003_agent_tables.py` - Creates and drops agent trace tables.

## Decisions Made

- `checkpointer_database_url` remains a property so pydantic-settings does not require or load a separate env var.
- Migration 003 points to `002_rag_pipeline`, the actual current revision ID, instead of the plan snippet's shorter `002` value.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.config import settings; assert hasattr(settings, 'llm_model'); assert settings.checkpointer_database_url.startswith('postgresql://'); print('config OK')"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.config import settings; assert 'postgresql://' in settings.checkpointer_database_url; print('checkpointer URL OK')"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.db.models import AgentRun, AgentStep; print('models OK')"` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` - passed; applied `002_rag_pipeline -> 003` on first run and was clean on final verification.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/db/models.py src/db/migrations/versions/003_agent_tables.py` - passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - passed, 50 tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Corrected Alembic down_revision**
- **Found during:** Task 2 (AgentRun and AgentStep migration)
- **Issue:** The plan snippet used `down_revision = "002"`, but the repository's real prior revision is `002_rag_pipeline`; using `002` would break Alembic's revision chain.
- **Fix:** Set `down_revision: str | None = "002_rag_pipeline"` and updated the migration header to match.
- **Files modified:** `src/db/migrations/versions/003_agent_tables.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run alembic upgrade head` passed.
- **Committed in:** `9f0a55e`

---

**Total deviations:** 1 auto-fixed (Rule 3)
**Impact on plan:** Required for migration correctness; no scope expansion.

## Issues Encountered

- `uv run` initially hit sandboxed network access while resolving/building dependencies; rerun with approved network access passed.
- `alembic upgrade head` initially hit sandboxed localhost access; rerun with approved local Postgres access passed.

## Known Stubs

None. Stub scan found only the intentional empty `dashscope_api_key` default and standard Alembic `branch_labels`/`depends_on` metadata.

## Auth Gates

None.

## User Setup Required

No immediate setup is required for this plan's verified code path. Future live LLM runs must set `DASHSCOPE_API_KEY` in `.env`.

## Next Phase Readiness

Plan 03-02 can build AgentState schemas, prompts, and read-only tool wrappers on top of the installed LangGraph/LangChain dependencies and the committed trace table foundation.

## Self-Check: PASSED

- Found `.planning/phases/03-langgraph-core/03-01-SUMMARY.md`.
- Found `src/db/migrations/versions/003_agent_tables.py`.
- Found task commit `feb3047`.
- Found task commit `9f0a55e`.

---
*Phase: 03-langgraph-core*
*Completed: 2026-05-11*
