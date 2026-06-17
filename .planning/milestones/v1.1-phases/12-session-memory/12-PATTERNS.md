# Phase 12: Session Memory - Pattern Map

**Generated:** 2026-06-14
**Scope:** Planning-only map for Phase 12 implementation.

## Target Files and Local Analogs

| Target | Role | Closest Analog | Pattern to Reuse |
| --- | --- | --- | --- |
| `src/db/models.py` | Add `SessionMemory` ORM model | `AgentRun`, `AgentTraceEvent`, `PolicyDocument` | UUID primary keys, tenant/user/thread scoped indexes, JSONB columns, `TimestampMixin`, explicit `Index(...)` definitions. |
| `src/db/migrations/versions/007_session_memories.py` | Add PostgreSQL table/indexes | `006_agent_trace_events.py` | Alembic `revision`, `down_revision`, `op.create_table`, explicit indexes, reversible downgrade. |
| `src/memory/schemas.py` | Typed memory contracts | `src/knowledge/schemas.py`, `src/business_tools/schemas.py`, `src/agent/schemas.py` | Pydantic models with literal `schema_version`, JSON-serializable outputs, no raw dict contract as the service boundary. |
| `src/memory/repository.py` | Scoped persistence and CAS | `src/knowledge/adapters.py`, `src/business_tools/service.py`, `src/agent/events.py` | Async SQLAlchemy session injected at service boundary; repository handles DB statements, service owns policy decisions. |
| `src/memory/service.py` | Authoritative session memory facade | `PolicyKnowledgeService`, `BusinessToolService` | Service facade catches failures and returns typed safe fallback results instead of leaking persistence errors into graph nodes. |
| `src/agent/nodes/session_memory_load.py` | Read path graph node | current empty adapter | Preserve empty fallback shape: `active_slots={}`, `continuity_claimed=False`, trace step appended. |
| `src/agent/nodes/memory_write.py` | Post-response write finalizer callable | `src/agent/nodes/final_response.py`, `src/agent/events.py`, `src/api/routers/agent.py`, `src/api/routers/agent_runs.py` | Deterministic finalizer writes `memory_write_result` and trace/event telemetry after user-visible final response delivery/persistence; timeout/failure is observable and does not delay or clear `final_response`. |
| `src/agent/routing.py` | Inherited-slot gate | `resolve_slots_for_completeness` | Current explicit `extracted_slots` win; session slots require trusted metadata and fail closed. |
| `src/api/routers/agent.py`, `src/api/routers/agent_runs.py` | Add post-response memory write hook | current API/SSE terminal persistence | Keep graph final-response path non-blocking; invoke/schedule bounded best-effort memory write after `/chat` response payload is fixed or after SSE `final_response` is yielded. |
| `tests/memory/` | Service/repository contract tests | `tests/knowledge`, `tests/business_tools`, `tests/agent/test_events.py` | Focused service tests plus integration tests with existing async SQLAlchemy fixtures. |
| `tests/agent/test_required_slots.py` | Router inheritance safety | existing Phase 11 slot tests | Extend stale/wrong-scope/incompatible/explicit-override cases; keep router tests DB-free. |
| `tests/agent/test_graph.py` | Full graph continuity | current graph tests with `MemorySaver` and fake LLM/tool manager | Patch graph dependencies at node seams; assert node sequence and final state, not private LangGraph internals. |

## Existing Contracts to Preserve

- Router tests stay pure and must not require DB, Redis, LLM, network, or service calls.
- `session_memory_load` must keep an observable empty fallback that matches the Phase 10 adapter when disabled, missing session, unavailable, or errored.
- `resolve_slots_for_completeness` must never read top-level stale `active_slots` for required-slot completeness.
- `candidate_slots` remain hints only and cannot write or override `extracted_slots` or `active_slots`.
- Memory references/results must not be assignable to `EvidenceRefV1`; KnowledgeService remains the sole policy evidence producer.
- PostgreSQL is authoritative for Phase 12. Redis is only a later decision gate and must not enter correctness tests unless an optional derived cache is deliberately added.

## Planning Slices

1. `12-01`: PostgreSQL schema, typed memory contracts, repository, MemoryService foundation.
2. `12-02`: `session_memory_load` integration and safe inherited-slot read path.
3. `12-03`: post-response `memory_write` finalizer, write candidates, memory events, timeout, and normal completed-path API/SSE hook.
4. `12-04`: CAS/isolation/evidence-boundary hardening and graph/API regression matrix.
5. `12-05`: Redis hot-cache decision gate only; no Redis code unless the PostgreSQL path is already stable and the decision doc explicitly keeps it non-authoritative.
