# Phase 16: Long-term / Case Memory - Research

**Researched:** 2026-06-17
**Status:** Ready for planning
**Scope:** reviewed long-term profile memory, reviewed case memory retrieval, tombstones, review/write events, and bounded prompt-context integration.

## Planning Summary

Phase 16 should add a new reviewed memory family instead of expanding `session_memories`. The current code already has same-thread session memory, a legacy session-derived `search_case_memory`, an empty `long_term_memory_retrieve` adapter, and a `ContextAssembler` with protected policy/business/current-message blocks. The phase should build durable reviewed memory tables and service boundaries first, then wire retrieval into the agent/prompt path only after predicates, tombstone checks, and prompt-safe projection are testable.

The implementation should keep memory as contextual assistance only:

- Long-term profile memory is predicate-only in Phase 16; no pgvector is needed for profile memory.
- Case memory is metadata-first + pgvector + light rerank; hard filters must run before semantic ranking.
- LLM/summary/semantic candidates enter `needs_review`; only deterministic durable sources or explicit remember requests may auto-approve.
- Memory must not create `EvidenceRefV1`, satisfy approval evidence, authorize actions, become current business truth, or change replay/audit truth.

## Live Code Findings

### Existing Memory Layer

- `src/db/models.py` defines `SessionMemory` with `tenant_id`, `user_id`, `thread_id`, JSONB slot fields, `version`, `expires_at`, and `deleted_at`. It has a partial unique active scope index on `(tenant_id, user_id, thread_id)` where `deleted_at is null`.
- `src/memory/repository.py` provides `SessionMemoryRepository` with active lookup, insert, text search over session fields, CAS update, and soft delete.
- `src/memory/service.py` implements same-thread session load/write, expiry handling, CAS merge, PII skip, and fallback behavior. This is a useful concurrency precedent, but it must not be stretched into long-term/case memory semantics.
- `src/memory/search.py` implements `SessionPrecedentSearchService`. The docstring explicitly says this is not the target reviewed case-memory store; it is a transitional read-only projection over `session_memories` for `search_case_memory`.

### Current Agent Integration

- `src/agent/nodes/long_term_memory_retrieve.py` is an empty adapter returning `long_term_memory=[]`, `case_memory=[]`, and `continuity_claimed=False`. Phase 16 can replace this only after reviewed retrieval predicates exist.
- `src/agent/state.py` already has `long_term_memory` / `case_memory` state fields, so the graph contract has a seam.
- `src/agent/context/assembler.py` currently assembles: system prompt, safety constraints, business IDs, working state, business context, thread summary, recent messages, tool summaries, policy refs, node hints, current user message. It has no memory-specific inputs yet.
- Policy refs are projected through `project_policy_refs_for_prompt` and inserted as a protected block. Memory blocks must stay below protected policy/business/current-user authority and must be prompt-safe summaries only.

### Existing Hash / Schema Patterns

- `src/common/canonical_hash.py` provides `CanonicalHashProfile v1` helpers with strict JSON normalization, schema-version binding, field allowlists, no bare floats, fixed UTC millisecond datetimes, and `sha256:<hex>` output. `memory_identity.v1` should reuse this style, but memory-specific normalization rules should live in the memory domain.
- `src/db/models.py` already uses `pgvector.sqlalchemy.Vector` for `PolicyChunk.embedding` with dimension 1024. Case memory should reuse this Postgres + pgvector stack instead of adding a new vector store.
- Migrations are under `src/db/migrations/versions/`; latest visible memory/conversation foundations are `011_memory_foundation_v2.py` and `012_thread_user_scope.py`. Phase 16 should add a new Alembic migration after `012`.

### Legacy Case Search

- `src/tools/catalog.py` still exposes `search_case_memory`.
- `src/tools/executors/memory.py` routes `search_case_memory` to the session-derived search service.
- Existing tests reference `search_case_memory` as a planner-visible retrieval tool. Phase 16 should either:
  - rename/quarantine the legacy surface, or
  - keep the external tool name but back it with reviewed case memory and clearly mark legacy session search unavailable/debug-only.

## Recommended Implementation Shape

### 1. `memory_identity.v1`

Add memory-specific identity helpers under `src/memory/identity.py` or equivalent:

- `memory_type`: `long_term_fact` | `case_memory`
- `scope_type`: `tenant` | `merchant` | `user` | `thread` | `case`
- `scope_id`: string
- `content_hash`: canonical content hash for normalized memory content
- `source_identity_hash`: canonical hash over allowed source refs only
- `candidate_hash`: stable write-event/candidate envelope hash over tenant, memory type, scope, `content_hash`, and nullable `source_identity_hash`
- allowed source refs: `source_type`, `run_id`, `event_id`, `conversation_message_id`, `tool_result_id`, `agent_run_id`, `business_object_type`, `business_object_id`, `policy_version`, `outcome_id`

Do not allow arbitrary JSON keys to participate in source identity. Do not include raw payload, raw tool output, policy text, approval/action authority bodies, or replay/debug blobs in `candidate_hash`. Tombstone fallback must compare canonical identity first, then normalized source identity, never semantic similarity.

### 2. Schema And Migration

Add separate tables/models:

- `long_term_memories`
- `case_memories`
- `memory_tombstones`
- `memory_write_events`

Key constraints:

- `review_status` check: `auto_approved`, `needs_review`, `approved`, `rejected`, `superseded`, `tombstoned`, `deleted`
- `pii_classification` check: `none`, `low`, `sensitive`, `prohibited`
- `scope_type` check: `tenant`, `merchant`, `user`, `thread`, `case`; no `global` in MVP
- long-term current unique identity on `(tenant_id, scope_type, scope_id, content_hash)` where active/current
- active tombstone lookup by `(tenant_id, memory_type, scope_type, scope_id, content_hash)` where `content_hash is not null and deleted_at is null`
- case memory metadata indexes on tenant, merchant/scope, case type, policy family/version, review status, expiry/deletion, and embedding

Prefer a single Phase 16 migration that creates nullable/expand-first tables and indexes. If migration becomes too large, split into schema and index/backfill migrations, but keep rollback/read-switch tasks explicit.

### 3. Services And Repositories

Keep new boundaries under `src/memory/`:

- `identity.py` for canonical normalization and hashes
- `models` additions in `src/db/models.py`
- `long_term_repository.py` / `case_memory_repository.py` or a combined reviewed-memory repository if local style favors fewer files
- `long_term_service.py` for write/review/retrieve/correction/supersede
- `case_memory_service.py` for reviewed precedent insert/review/retrieve
- `events.py` or service methods for `memory_write_events`
- prompt-safe projection helpers, either under `src/memory/projections.py` or `src/agent/context/projectors.py`

Service transactions should own tenant/scope validation, tombstone checks, source-identity fallback, supersede state changes, and write-event emission. Do not rely on JSONB foreign-key semantics for source refs.

### 4. Retrieval Predicates

Long-term profile retrieval:

- tenant + allowed scope
- `review_status in ('auto_approved', 'approved')`
- not deleted, not tombstoned, not superseded
- not expired
- PII not prohibited
- version/policy compatibility where applicable
- bounded top 3 profile snippets, 150-200 chars each

Case memory retrieval:

- apply hard filters first: tenant, reviewed status, tombstone/deletion, case type, merchant/scope, policy family/version compatibility, expiry
- then run pgvector semantic top-k
- then light rerank, for example semantic similarity + policy match + recency
- return top 3 fixed-shape snippets: `excerpt`, `applicability`, `outcome`, `caveats`

### 5. ContextAssembler Integration

Add explicit memory inputs and prompt-safe projection:

- profile memory block after policy/business/tool facts and before recent messages
- case precedent block after profile constraints and before recent messages
- memory block total hard cap: 1600 chars
- profile max 3 items
- case max 3 items
- no raw memory rows, raw JSON payloads, hashes, approval/action authority bodies, replay/debug blobs, or implicit dict/list stringification

Keep policy refs, business IDs/state, safety constraints, and current user message protected and higher authority. Tests should prove recent/current user text and current business facts override memory.

### 6. Legacy `search_case_memory`

Plan should force an explicit transition:

- Rename current session-derived search internally to `legacy_session_precedent_search` or mark it debug/unavailable in planner-visible paths.
- Add reviewed case memory retrieval service.
- Either wire `search_case_memory` to reviewed case memory or update the catalog description to state legacy/unavailable until reviewed store exists.
- Keep event family compatibility only if tests still require `search_case_memory` as a RAG/retrieval tool; do not let it imply reviewed precedents unless backed by reviewed rows.

## Suggested Plan Decomposition

1. Identity and schema contract tests first: golden `memory_identity.v1`, allowed source refs, no arbitrary JSON keys, hash stability.
2. Migration/model plan: create long-term/case/tombstone/write-event tables, indexes, constraints, rollback/downgrade preflight.
3. Repository/service write lifecycle: deterministic auto-approve, `needs_review`, approve/reject, write events, prohibited skip.
4. Tombstone and supersede transactions: delete/forget creates tombstone, same-transaction no-rewrite, correction leaves one current long-term row.
5. Retrieval predicates: long-term predicate retrieval and reviewed case metadata-first + pgvector retrieval.
6. Prompt/context integration: `long_term_memory_retrieve` and `ContextAssembler` prompt-safe bounded blocks.
7. Legacy search quarantine/wiring: `search_case_memory` no longer claims reviewed case memory unless backed by reviewed case store.
8. Eval and negative boundary tests: authority boundaries, prompt leakage, concurrency, transition behavior.

The planner should include a blocking schema migration/push task after model/migration edits and before verification.

## Migration Rollback And Downgrade Preflight

Planning should require:

- `upgrade()` creates new tables/indexes without mutating `session_memories`.
- `downgrade()` drops Phase 16 objects in reverse dependency order.
- rollback/read-switch strategy: feature/service can return empty safe retrieval when tables are absent or disabled.
- preflight check before enabling reads: tables exist, indexes exist, review-status constraints exist, tombstone indexes exist, vector extension compatibility is present for case memory embeddings.
- no destructive migration of existing session memory data.
- tests or migration-contract checks for upgrade/downgrade ordering and table/index names.

## Risk Notes

- Cross-tenant/scope mistakes are the highest-impact class; DB checks cannot validate polymorphic `scope_id`, so service tests must.
- Tombstone no-rewrite must be transactional; an async candidate writer that checks tombstones outside the write transaction can resurrect deleted content.
- Case memory pgvector filters can produce poor recall if filtering happens after approximate scan; MVP should preserve hard filters and accept simple rerank rather than overbuilding hybrid/RRF.
- `search_case_memory` naming is already misleading; leaving it unchanged without reviewed backing will violate Phase 16 success criteria.
- `ContextAssembler` block ordering currently puts recent messages before tool summaries/policy refs in code order but budget priority reorders by `TokenBudgetPolicy`; tests should assert final assembled block names/order/priority rather than assume source order only.

## Test And Verification Strategy

Required automated coverage:

- `tests/memory/test_memory_identity.py`: golden normalization/hash cases, allowed fields, nullable handling, source identity fallback, unknown source refs rejected.
- `tests/memory/test_long_term_memory_repository.py`: review status, scope filters, freshness/expiry, deleted/tombstoned/superseded/prohibited exclusion.
- `tests/memory/test_long_term_memory_service.py`: deterministic writes, explicit preference auto-approve, LLM candidate `needs_review`, correction/supersede one-current invariant.
- `tests/memory/test_memory_tombstones.py`: forget/delete creates tombstone, immediate retrieval exclusion, same-transaction candidate write emits `memory_write_event(reason_code='tombstone_match')`.
- `tests/memory/test_case_memory_retrieval.py`: metadata-first filters, approved-only, policy version compatibility, pgvector ranking/rerank, separation from session memory and policy evidence.
- `tests/agent/context/test_assembler.py`: memory block counts, total chars, no raw payload/hash/authority leakage, protected policy/business/current-user precedence.
- `tests/agent/test_memory_evidence_boundary.py`: memory cannot become `EvidenceRefV1`, approval evidence, action authorization, current business truth, or replay truth.
- `tests/agent/test_graph.py`: `long_term_memory_retrieve` safe empty behavior when no reviewed memory exists and real retrieval behavior when reviewed records exist.
- `tests/tools/test_catalog.py` and `tests/agent/test_policy_retrieval_ownership.py`: `search_case_memory` transition semantics are explicit.
- Migration tests for new Alembic revision upgrade/downgrade and schema object presence.

Concurrency coverage:

- separate sessions attempting candidate write while tombstone is created
- CAS/supersede conflict where only one current long-term memory remains
- delayed/asynchronous candidate write blocked by active tombstone in the same transaction

## Validation Architecture

| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pyproject.toml` / existing pytest configuration |
| Quick run command | `pytest tests/memory tests/agent/context -q` |
| Full suite command | `pytest -q` |
| Estimated runtime | repo-dependent; quick memory/context subset should remain the per-task feedback loop |

Sampling guidance:

- After identity/schema/service tasks: run `pytest tests/memory -q`.
- After prompt/context tasks: run `pytest tests/agent/context tests/agent/test_memory_evidence_boundary.py -q`.
- After tool/catalog transition tasks: run `pytest tests/tools tests/agent/test_policy_retrieval_ownership.py -q`.
- After migration tasks: run the migration-specific tests plus any existing migration contract tests.
- Before phase verification: run `pytest -q`.

Nyquist expectations:

- No three consecutive implementation tasks should lack an automated verify command.
- Every Phase 16 requirement should map to at least one automated test file or migration-contract check.
- Manual verification should be unnecessary for core behavior; if DB/pgvector integration is not available in CI, planner must include a local DB-backed eval/manual command and a pure unit fallback.

## Open Questions (RESOLVED)

None blocking for planning. Exact file naming, pgvector index parameters, and whether case embeddings live on `case_memories` or a separate embedding table can be decided during implementation as long as the plan preserves metadata-first retrieval, tombstone semantics, and prompt authority boundaries.
