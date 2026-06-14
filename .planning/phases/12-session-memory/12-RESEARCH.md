# Phase 12: Session Memory - Local Research

**Date:** 2026-06-14
**Scope:** Local-only code search. Keywords constrained to `conversation`, `session`, `memory`, `Redis`, `cache`, and `thread`.
**Sources:** MOCA plus three newly cloned customer-support reference repositories:
- `/Users/ming/projects/reference-repos/Multi-Agent-Customer-Support`
- `/Users/ming/projects/reference-repos/agent-desk`
- `/Users/ming/projects/reference-repos/basjoo`

## Research Conclusion

Phase 12 should keep PostgreSQL as the authoritative session-memory store. Redis may be introduced only as a non-authoritative hot cache with tenant/user/thread-scoped keys, mandatory TTL, PostgreSQL fallback, and no correctness dependency.

The strongest local pattern across MOCA and the customer-support references is a separation between:
- per-run/checkpoint state,
- durable conversation/session records,
- short-lived caches/rate limits,
- message/history context used for prompting.

For MOCA, `session_memories` must be its own durable service/repository boundary with version CAS. LangGraph checkpointer state and recent chat history are useful context mechanisms, but neither is an authoritative memory contract.

## Standard Stack

- **PostgreSQL + SQLAlchemy/Alembic** for `session_memories`, matching MOCA's existing ORM/migration style in `src/db/models.py` and `src/db/migrations/versions/`.
- **Repository + service facade** under `src/memory/`, matching the KnowledgeService and BusinessToolService ownership style from prior phases.
- **LangGraph node integration** by replacing the current empty `session_memory_load` adapter in `src/agent/nodes/session_memory_load.py`.
- **Existing deterministic router** in `src/agent/routing.py` remains the slot-inheritance gate. It already requires `continuity_claimed=True`, trusted slot metadata, matching tenant/user/thread, freshness, and intent compatibility.
- **Redis is optional and non-authoritative for Phase 12.** The simplest implementation can stay PostgreSQL-only. If Redis is added, it is a short-TTL hot cache for active session reads/writes and must fall back to PostgreSQL on miss or failure.

## Architecture Patterns

### 1. Authoritative Store Separate From Checkpointer

MOCA already uses a PostgreSQL LangGraph checkpointer, scoped through `_checkpoint_thread_id(user, thread_id)` as `tenant_id:user_id:thread_id` in `src/api/routers/agent.py` and `src/api/routers/agent_runs.py`.

Phase 12 should not treat that checkpoint as authoritative session memory. The contract requires `session_memories` keyed by `(tenant_id, user_id, thread_id)` with `version` CAS and `deleted_at` active uniqueness.

Reference confirmation:
- `Multi-Agent-Customer-Support` uses `MemorySaver` and `InMemoryStore`, and its docs explicitly call them in-memory teaching components.
- `agent-desk` stores runtime checkpoint bytes in `ConversationInterrupt`, while business conversation/message/read state are separate durable tables.
- `basjoo` uses SQLAlchemy `ChatSession`/`ChatMessage` for authoritative chat history; Redis is only cache/rate-limit/queue infrastructure.

### 2. Typed Session Slot Envelope, Flattened Loaded View

The DB column should store the contract-owned envelope:

```json
{
  "schema_version": "session_slots.v1",
  "slots": {
    "order_id": {
      "value": "ORD-1001",
      "source": "explicit_user",
      "source_run_id": "uuid",
      "updated_at": "2026-06-14T00:00:00Z",
      "expires_at": "2026-06-14T00:30:00Z",
      "compatible_intents": ["order_status_inquiry", "refund_troubleshooting"]
    }
  }
}
```

The graph-loaded `session_memory` view should stay compatible with the current router shape:

```python
{
    "source": "postgres_session_memory",
    "continuity_claimed": True,
    "active_slots": {"order_id": "ORD-1001"},
    "slot_metadata": {
        "order_id": {
            "source": "trusted_session_memory",
            "tenant_id": "...",
            "user_id": "...",
            "thread_id": "...",
            "fresh": True,
            "compatible_intents": ["refund_troubleshooting"],
        }
    },
}
```

This avoids changing `route_after_slots()` in Phase 12 and keeps inheritance enforcement deterministic.

### 3. Optional Redis Hot Cache

Redis can improve the hot path for active thread continuity, but it must be a derived view, not the memory contract.

Allowed shape:

```text
session:{tenant_id}:{user_id}:{thread_id}
```

Rules:
- TTL is mandatory.
- Values must be reconstructable from `session_memories`.
- Cache miss, stale version, or Redis unavailability falls back to PostgreSQL.
- Writes must still commit through PostgreSQL CAS before any cache update is trusted.
- Redis loss must not affect correctness, auditability, replay, approval/action safety, or future deterministic merge.

This cache is optional for Phase 12 and should be skipped if it complicates the first implementation.

### 4. CAS Update With Deterministic Merge

Implement write as a MemoryService transaction:

1. Load active row for `(tenant_id, user_id, thread_id)` where `deleted_at is null`.
2. If no row exists, insert a new row with `version=1`.
3. If row exists, compute merged memory from latest row plus current run candidates.
4. Update with `WHERE id = :id AND version = :expected_version`.
5. On zero rows affected, reload latest and retry deterministic merge once or return explicit conflict/fallback.

Merge precedence:
- current-turn explicit validated slots,
- compatible non-expired existing session slots,
- no inherited value.

Silent last-write-wins is forbidden.

### 5. Memory Write Placement

The contract has a `memory_write` node, but MOCA's current graph ends at `final_response`.

Recommended Phase 12 plan:
- Add a bounded post-response `memory_write` finalizer/hook that runs only after the API/SSE path has built and emitted or persisted the user-visible final response.
- Ensure slow writes, CAS waits, DB failures, or write failures append observable fallback/result state but do not suppress, delay, or replace the already-built final response.
- Do not run normal `memory_write` for interrupted approval paths; the approval path currently completes the run as `interrupted` outside the normal completed final-response path.
- Treat the graph-level `trace_close`/canonical finalizer as Phase 15 scope. Phase 12 plugs memory write into the existing API terminal persistence path and registers memory write event additions on the Phase 10 envelope.

### 6. Read/Disable Fallback

`session_memory_load` should continue returning the Phase 10 empty adapter shape when:
- feature/read switch is disabled,
- Redis misses, is stale, or is unavailable,
- AsyncSession is missing from config,
- memory row is missing,
- row is expired/deleted,
- service read errors.

Fallback must be observable:
- `source`: `disabled`, `missing_session`, `unavailable`, or `empty_adapter`,
- `continuity_claimed=False`,
- no inherited slots,
- trace step metrics or node error entry.

## Reference Repository Findings

### Multi-Agent-Customer-Support

Relevant files:
- `src/agents/graph.py`
- `src/agents/nodes.py`
- `src/state.py`
- `docs/architecture.md`

Findings:
- Uses `MemorySaver` for per-thread checkpointing and `InMemoryStore` for per-customer preferences.
- `load_memory` reads `("memory_profile", customer_id)` from store.
- `create_memory` extracts recent preference memory from the last 10 messages and writes set-union preferences.
- This is useful as a simple load-before-agent / write-after-agent graph shape.
- It is not suitable as a Phase 12 persistence model because storage is in-memory, preference-oriented, and not CAS/versioned.

### agent-desk

Relevant files:
- `internal/models/models.go`
- `internal/services/conversation_service.go`
- `internal/services/message_service.go`
- `internal/services/conversation_read_state_service.go`
- `internal/ai/runtime/internal/impl/store/checkpoint_store.go`
- `internal/ai/runtime/internal/impl/adapter/message_adapter.go`

Findings:
- Has durable `Conversation`, `Message`, `ConversationReadState`, `ConversationEventLog`, and `ConversationInterrupt` models.
- Checkpoint bytes are stored in `ConversationInterrupt.CheckPointData`, separate from business conversation state.
- Message writes update message row, conversation last-message fields, unread counts, and event log in one transaction.
- Read cursors are monotonic (`LastReadSeqNo` never moves backward).
- AI prompt history uses the latest 12 messages via `BuildHistoryMessages`; this is context-window history, not structured session memory.
- Main reusable pattern for MOCA: keep checkpoint/runtime state separate from durable conversation/session contracts, and make per-session updates transactional and monotonic.

### basjoo

Relevant files:
- `backend/models.py`
- `backend/api/v1/endpoints.py`
- `backend/services/redis_service.py`
- `backend/middleware/rate_limit.py`
- `backend/services/scheduler.py`

Findings:
- `ChatSession`/`ChatMessage` are SQLAlchemy authoritative records.
- Active uniqueness is modeled as unique `(agent_id, session_id)` where status is not `closed`.
- `get_or_create_chat_session()` catches `IntegrityError`, reloads, and returns the active row.
- Chat history injection reads the last 10 messages only when `agent.enable_context` is true.
- Redis wraps cache, rate limiting, queues, and pub/sub. `cache_session()` exists but is not used by the main chat path.
- Redis failures fall back to memory rate limiting at startup/middleware.
- Reusable pattern for MOCA: active-scope uniqueness plus inactive/closed state releasing active uniqueness. Redis can cache hot session views, but must not be authoritative session state.

## Don't Hand-Roll

- Do not hand-roll Redis-backed session-memory correctness. Redis is allowed only as a derived hot cache; PostgreSQL CAS remains the write correctness boundary.
- Do not use LangGraph checkpoint state as the authoritative memory table.
- Do not use raw dicts without typed slot metadata for inherited slots.
- Do not let LLM candidate slots write directly to session memory.
- Do not make session summary a source of policy/risk/approval/action evidence.
- Do not widen Phase 12 into long-term memory, case memory, embeddings, tombstones, async extraction, or review workflow.

## Common Pitfalls

- **Router shape mismatch:** `active_slots_json` is envelope-shaped in DB, but `route_after_slots()` expects flattened `active_slots` and `slot_metadata` in `state["session_memory"]`.
- **False continuity:** `continuity_claimed=True` without metadata currently fails closed. Preserve that behavior.
- **CAS tests that do not exercise real concurrency:** Need repository/service tests proving concurrent updates do not lose slots, summary, unresolved questions, last intent, or business refs.
- **Current explicit vs inherited confusion:** `extract_slots.py` currently merges `state.active_slots` with new slots. Phase 12 must ensure inherited values stay distinguishable in session metadata and current-turn explicit slots override.
- **Memory write after interruptions:** Approval interruption does not produce the normal completed final-response path. Do not run normal memory write for interrupted approval flows.
- **Policy evidence pollution:** Memory refs must not be assignable to `EvidenceRefV1`; negative tests should assert memory cannot satisfy policy evidence/citation/action requirements.

## MOCA Implementation Touchpoints

- `src/db/models.py`: add `SessionMemory` ORM model.
- `src/db/migrations/versions/`: add migration for `session_memories`.
- `src/memory/schemas.py`: define `SessionSlot`, `SessionSlotsEnvelope`, loaded view, write candidates/result.
- `src/memory/repository.py`: scoped load/create/update with active row filter and CAS.
- `src/memory/service.py`: read fallback, slot filtering, deterministic merge, write policy.
- Optional Redis adapter/cache module: only if needed after the PostgreSQL service is correct; must be non-authoritative, TTL-bound, and fallback-safe.
- `src/agent/nodes/session_memory_load.py`: replace empty adapter with MemoryService read path, preserving fallback shape.
- `src/api/routers/agent.py` and `src/api/routers/agent_runs.py`: invoke/schedule a bounded post-response memory write hook after final response delivery/persistence.
- `src/agent/nodes/memory_write.py`: provide the reusable finalizer callable used by API/SSE completion paths.
- `src/agent/state.py`: add `memory_write_result` and candidate fields if needed.
- `tests/agent/test_required_slots.py`: extend trusted metadata cases for stale, wrong tenant/user/thread, incompatible intent, explicit override.
- New `tests/memory/` and migration tests: CAS, isolation, active unique scope, expiration, disable fallback, memory-is-not-evidence.

## Recommended Planning Slices

1. **Schema and service foundation:** ORM, migration, schemas, repository, basic read/write.
2. **Trusted read integration:** wire `session_memory_load` to MemoryService with feature switch/fallback and slot metadata flattening.
3. **Safe write path:** add post-response `memory_write` finalizer hook, write candidates, deterministic merge, timeout, PII/prohibited-content blocking, and summary restrictions.
4. **CAS/isolation hardening:** concurrent update tests, cross-thread/user/tenant isolation, stale/incompatible exclusion.
5. **Optional hot-cache hardening:** if Redis is introduced, add cache miss/stale/unavailable fallback tests and prove PostgreSQL CAS remains the correctness boundary.
6. **Evidence-boundary and eval gates:** negative tests proving memory is not policy evidence, approval/action evidence, or citation source.

## Verification Commands

Suggested focused checks after implementation:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory tests/agent/test_required_slots.py tests/agent/test_empty_session_adapter.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py tests/agent/test_graph.py -q --tb=short
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent src/memory tests/memory tests/agent
```
