# Phase 12 Redis Evaluation

Decision: SKIP_FOR_PHASE_12

## Reason

The Phase 12 PostgreSQL-only path passes the focused safety matrix from 12-04:

- Same-thread continuity and cross-thread/user/tenant isolation pass.
- PostgreSQL CAS merge/conflict behavior is covered without silent last-write-wins.
- Disabled and unavailable session memory fall back to ordinary routing.
- Session memory cannot satisfy policy evidence, approval, action authority, replay, or audit truth.
- PII/prohibited/raw payload write candidates are blocked or excluded before persistence.

There is no measured read-latency or database-load issue yet. Adding Redis now would increase correctness surface without a demonstrated need.

## Non-Authoritative Cache Contract

Redis may be reconsidered only as a derived hot cache. The contract is:

- Scoped key: `session:{tenant_id}:{user_id}:{thread_id}` or a stricter authorized scope.
- mandatory TTL: every Redis key must expire, and the cache TTL must not exceed the session memory TTL.
- PostgreSQL fallback: cache miss, Redis unavailable, timeout, stale version, invalid JSON, or schema/scope mismatch must fall back to PostgreSQL.
- Post-CAS refresh only: session memory writes commit through PostgreSQL CAS before any cache refresh is trusted.
- no correctness dependency: Redis values must be reconstructable from PostgreSQL-backed `session_memories` and durable events.
- No authority storage: Redis must not be the only copy of inherited slots, unresolved questions, summaries, approval waits, side-effect boundaries, replay/audit facts, action authorization, policy evidence, tombstones, long-term memory, or case memory.

## Revisit Triggers

Reopen the Redis decision only if one or more of these are observed in production-like tests:

- Session memory read latency exceeds the agreed p95/p99 service threshold.
- Database load from same-thread session memory reads materially affects API or graph latency.
- Profiling shows session-memory reads are a top contributor after query/index tuning.
- A later architecture phase needs a non-authoritative active-session hot layer and can preserve all Phase 12 safety boundaries.

## Required Future Tests If Accepted

If a future decision changes this to `IMPLEMENT_OPTIONAL_HOT_CACHE`, the implementation must add blocking tests for:

- Cache miss falls back to PostgreSQL.
- Redis unavailable or timeout falls back to PostgreSQL.
- Stale cached version falls back to PostgreSQL.
- Invalid JSON or schema/scope mismatch falls back to PostgreSQL.
- Disabled cache bypasses Redis completely.
- PostgreSQL CAS succeeds before cache refresh is attempted.
- Cache refresh failure does not change a successful PostgreSQL write result.
- No Redis-only correctness: deleting Redis data does not change routing correctness.
- No approval/action/replay truth in Redis.
- No policy evidence, action authorization, tombstones, long-term memory, or case memory in Redis.

## Default Path Checks

- `test ! -f src/memory/redis_cache.py`
- `rg -n "redis|Redis" src/memory src/agent/nodes/session_memory_load.py src/agent/nodes/memory_write.py` returns no matches for Phase 12-owned code paths.

## Decision Owner

Owner: Phase 12 session memory.

Future owner if reopened: the phase introducing Redis, with Phase 12 safety regression coverage retained.
