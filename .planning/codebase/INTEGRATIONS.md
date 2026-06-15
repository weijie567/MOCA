# External Integrations

**Analysis Date:** 2026-06-05

## APIs & External Services

**Implemented internal APIs:**
- Auth: `src/api/routers/auth.py`
- Orders: `src/api/routers/orders.py`
- Refund cases: `src/api/routers/refund_cases.py`
- Tickets: `src/api/routers/tickets.py`
- Search: `src/api/routers/search.py`
- Agent chat/runs: `src/api/routers/agent.py`, `src/api/routers/agent_runs.py`
- Approvals: `src/api/routers/approvals.py`
- Trace timeline: `src/api/routers/traces.py`

**Model integration surface:**
- OpenAI-compatible dependencies are installed through `openai`, `langchain-openai`, and `langchain-core`.
- Current architecture supports cloud or compatible local model endpoints through settings and LangChain/OpenAI-compatible interfaces.

**Business tool integration surface:**
- Tool registry and adapters live under `src/agent/tools/`.
- Implemented read/retrieval tools include order lookup, refund-case lookup, ticket lookup, and policy search.
- Write/approval-related behavior includes coupon/action draft creation after approval.

## Data Storage

**Implemented:**
- PostgreSQL through SQLAlchemy async ORM
- pgvector support for policy chunk embeddings
- Alembic migrations:
  - `001_initial_schema.py`
  - `002_rag_pipeline.py`
  - `003_agent_tables.py`
  - `004_latency_metrics.py`
  - `005_approval_tables.py`
  - `006_agent_trace_events.py`
  - `007_session_memories.py`
  - `008_approval_state_machine.py`
- Repository layer under `src/repositories/`

**Persisted domains:**
- Tenants, roles, users, merchants
- Orders, refund cases, tickets
- Policy documents and policy chunks
- Audit logs
- Agent runs and agent steps
- Approval requests, approval steps, approval levels, assignments, decisions, events, action safety snapshots, and action drafts
- Action drafts

**Local service orchestration:**
- `docker-compose.yml` starts local Postgres, Redis, and API dependencies.

## Authentication & Identity

**Implemented:**
- JWT helpers in `src/auth/jwt.py`
- Permission/scope checks in `src/auth/permissions.py`
- FastAPI dependencies in `src/api/deps.py`
- Auth schemas in `src/api/schemas/auth.py`

**Covered roles/scopes:**
- Merchant/support/manager/admin style roles with scopes for business read access, agent chat, and approval review.
- Tests cover auth, tenant isolation, and approval reviewer constraints.

## Monitoring & Observability

**Implemented:**
- Request trace ID middleware in `src/api/main.py`
- Agent run and step persistence in `src/agent/trace.py`
- Trace timeline repository in `src/repositories/trace_repo.py`
- Trace API coverage in `tests/test_trace_api.py`
- Latency instrumentation coverage in `tests/test_latency_instrumentation.py`

**Not yet implemented as external integrations:**
- OpenTelemetry exporter
- Prometheus/Grafana deployment
- Centralized log collector

## CI/CD & Deployment

**Implemented local deployment assets:**
- `Dockerfile`
- `docker-compose.yml`
- `docker-entrypoint.sh`
- `Makefile`

**Repository CI:**
- `.github/` exists, but current map does not treat CI as a fully verified deployment system.
- Backend and frontend commands should be kept explicit in README/Makefile and rerun after each major phase.

## Environment Configuration

**Implemented:**
- `.env.example` defines application configuration contract.
- `.env` exists locally and should not be treated as a committed source of truth.
- `src/config.py` centralizes backend environment parsing.

**Expected handling:**
- Keep secrets out of tracked docs and test fixtures.
- Document new environment keys in `.env.example` before code starts depending on them.

## Webhooks & Callbacks

**Current state:**
- Approval resume is implemented through API decision endpoints and LangGraph resume semantics, not external webhook delivery.
- No external webhook receiver/retry queue is implemented yet.

## Integration Risk Summary

- External model/provider configuration exists as an integration surface, but production-grade provider failover, cost controls, and rate limiting remain future hardening work.
- Approval and tool execution have local persistence and tests; external notification/webhook delivery remains out of scope.
- Observability is strong at application trace level, but not yet connected to OTel/Prometheus/Grafana.

---
*Integration audit: 2026-06-05*
*Refresh when external providers, service manifests, migrations, or auth contracts change*
