# Testing Patterns

**Analysis Date:** 2026-06-05

## Test Framework

**Backend runner:**
- pytest
- pytest-asyncio
- httpx AsyncClient for API tests

**Frontend runner:**
- Frontend has at least hook-level tests under `frontend/src/hooks/`.
- Use the frontend package scripts from `frontend/package.json` for exact commands.

**Run Commands:**
```bash
uv run pytest -q
uv run pytest tests/agent/test_tools -q
uv run pytest tests/agent/test_nodes -q
uv run pytest tests/integration -q
uv run ruff check .
```

Frontend commands should be run from `frontend/`:
```bash
npm test
npm run lint
npm run build
```

## Test File Organization

**Backend root tests:**
- API and domain tests live directly under `tests/`, such as `test_agent_runs_api.py`, `test_approval_api.py`, `test_search_integration.py`, and `test_trace_api.py`.

**Integration tests:**
- `tests/integration/` covers auth, tenant isolation, health, error format, and business-domain routes.

**Agent tests:**
- `tests/agent/test_graph.py`
- `tests/agent/test_trace.py`
- `tests/agent/test_nodes/`
- `tests/agent/test_tools/`

**RAG tests:**
- `tests/test_chunker.py`
- `tests/test_embedder.py`
- `tests/test_retriever.py`
- `tests/test_ingestion.py`
- `tests/test_rag_eval.py`
- `tests/test_rag_migration.py`

**Evaluation fixtures:**
- `evaluation/golden/`
- `eval/golden_rag_queries.jsonl`
- `evals/golden_set_phase3.json`

## Test Structure

**Common backend patterns:**
- Async tests use pytest-asyncio.
- API tests exercise the FastAPI app with seeded database state.
- Agent tests use focused state fixtures and fake graph/model behavior where needed.
- Approval tests verify both API behavior and persisted state transitions.

**Phase 7 specific coverage:**
- Tool contracts: `tests/agent/test_tools/test_tool_contracts.py`
- Tool adapters: `tests/agent/test_tools/test_tool_adapters.py`
- Registry behavior: `tests/agent/test_tools/test_registry.py`
- Read/retrieval tools: get order, refund case, ticket, and search policy tests

## Mocking

**Observed strategy:**
- Mock or fake graph/model behavior for API and approval resume tests when live LangGraph execution is not the subject.
- Keep repository/API integration tests close to real database behavior through fixtures.
- Avoid live external model calls in default test runs.

## Fixtures and Factories

**Implemented assets:**
- `tests/conftest.py` for shared backend app/session/client/seed fixtures
- `tests/agent/conftest.py` for agent-specific fixtures
- `scripts/seed_demo.py` for realistic local demo data
- `data/policies/` for synthetic policy documents

## Coverage

**Covered surfaces:**
- Health and error envelopes
- Auth and tenant isolation
- Business read APIs
- RAG ingestion/search/evaluation basics
- Agent graph routing and nodes
- Approval API and integration lifecycle
- Trace API and latency instrumentation
- Tool registry contracts, adapters, and authorization constraints

**Known gaps:**
- Full live model integration is not part of default automated tests.
- Frontend coverage is lighter than backend coverage.
- End-to-end browser-level demo validation is not represented as a standard CI command yet.
- OTel/Prometheus-style observability is not implemented or tested.

## Test Types

**Unit Tests:**
- Node behavior, tool registry, tool adapters, chunker/embedder/retriever helpers

**Integration Tests:**
- API route behavior, auth/tenant isolation, approval lifecycle, RAG search, trace timeline

**Evaluation Tests:**
- RAG and agent golden-set scripts and fixtures exist; exact scoring scripts should be run when changing retrieval, prompts, graph nodes, or tool behavior

**E2E / Demo Validation:**
- Smoke/demo scripts exist under `scripts/`, including live smoke and Phase 6 demo support
- Frontend-to-backend browser automation is not yet a standard committed test workflow

## Immediate Testing Priorities

1. Keep Phase 7 tool contract tests required for any future tool changes.
2. Add or standardize frontend test/build commands in top-level documentation.
3. Add a small end-to-end smoke path that runs seed, API, agent query, approval decision, and trace retrieval.
4. Keep golden RAG/agent evaluation tied to changes in `src/rag/`, `src/agent/`, `data/policies/`, and evaluation fixtures.

---
*Testing analysis: 2026-06-05*
*Refresh when test commands, fixtures, or coverage surfaces change*
