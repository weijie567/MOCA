---
phase: 16-long-term-case-memory
reviewed: 2026-06-17T18:08:26Z
depth: deep
files_reviewed: 39
files_reviewed_list:
  - src/agent/context/__init__.py
  - src/agent/context/assembler.py
  - src/agent/context/budget.py
  - src/agent/context/projectors.py
  - src/agent/events.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/extract_slots.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/investigate.py
  - src/agent/nodes/long_term_memory_retrieve.py
  - src/db/migrations/versions/013_long_term_case_memory.py
  - src/db/models.py
  - src/memory/case_memory.py
  - src/memory/identity.py
  - src/memory/long_term.py
  - src/memory/repository.py
  - src/memory/schemas.py
  - src/memory/semantic_episode.py
  - src/memory/tombstones.py
  - src/tools/catalog.py
  - src/tools/executors/memory.py
  - src/tools/manager.py
  - tests/agent/context/test_assembler.py
  - tests/agent/test_graph.py
  - tests/agent/test_memory_evidence_boundary.py
  - tests/agent/test_policy_retrieval_ownership.py
  - tests/agent/test_tools/test_unified_tool_manager.py
  - tests/approvals/test_migration_contract.py
  - tests/memory/test_case_memory_retrieval.py
  - tests/memory/test_long_term_memory_repository.py
  - tests/memory/test_long_term_memory_service.py
  - tests/memory/test_memory_identity.py
  - tests/memory/test_memory_schema.py
  - tests/memory/test_memory_tombstones.py
  - tests/memory/test_phase16_requirement_coverage.py
  - tests/memory/test_semantic_episode_projection.py
  - tests/memory/test_session_precedent_search.py
  - tests/replay/test_memory_foundation_alignment.py
  - tests/tools/test_catalog.py
findings:
  critical: 1
  warning: 5
  info: 0
  total: 6
status: issues_found
---

# Phase 16: Code Review Report

**Reviewed:** 2026-06-17T18:08:26Z
**Depth:** deep
**Files Reviewed:** 39
**Status:** issues_found

## Summary

Deep review covered the Phase 16 long-term/case memory stack: identity hashing, schema/migration/ORM mapping, review lifecycle, tombstone semantics, prompt projection, graph retrieval integration, and planner-visible tool dispatch. The authority boundary is mostly well protected: reviewed memory does not become `EvidenceRefV1`, policy evidence, approval authority, action authority, or raw prompt state in the main projection paths.

The main defects are in edge paths around memory writes and integration: `supersede_memory` can persist prohibited PII, source-only tombstones can over-block unrelated future writes, duplicate long-term writes can crash on the active-identity unique index, the ORM vector index does not match the migration's HNSW index, and the planner-visible `search_case_memory` path both drops returned snippets and ignores its required query.

## Critical Issues

### CR-01: Supersede Path Can Persist Prohibited PII

**File:** `src/memory/long_term.py:309`

**Issue:** `write_memory()` blocks `candidate.pii_classification == "prohibited"` before insert at `src/memory/long_term.py:106`, but `supersede_memory()` computes identity, checks tombstones, marks the previous row superseded, and inserts `replacement_candidate` without the same PII guard. A caller can therefore persist a prohibited-PII replacement through the correction/supersede path, bypassing the normal memory write safety policy.

**Fix:**
```python
if replacement_candidate.pii_classification == "prohibited":
    event = await self.repository.emit_write_event(
        tenant_id=replacement_candidate.tenant_id,
        run_id=run_id,
        memory_type=LONG_TERM_MEMORY_TYPE,
        memory_id=None,
        decision="skip",
        reason_code="pii_blocked",
        pii_classification=replacement_candidate.pii_classification,
        candidate_hash=identity["candidate_hash"],
        source_ref_json=identity["source_ref_json"],
    )
    return LongTermMemoryWriteResult(
        status="skipped",
        memory_id=None,
        review_status=None,
        decision="skip",
        reason_code="pii_blocked",
        pii_classification=replacement_candidate.pii_classification,
        candidate_hash=identity["candidate_hash"],
        content_hash=identity["content_hash"],
        source_identity_hash=identity["source_identity_hash"],
        event_id=event.id,
    )
```

Add a regression test that calls `supersede_memory()` with `replacement_candidate.pii_classification="prohibited"` and asserts no replacement row is inserted and the write event uses `reason_code == "pii_blocked"`.

## Warnings

### WR-01: Source-Only Tombstones Can Over-Block Future Writes

**File:** `src/memory/identity.py:120`

**Issue:** `canonical_source_identity_hash()` returns a hash when the source ref contains only `source_type`. Both `src/memory/long_term.py:416` and `src/memory/case_memory.py:644` create `{"source_type": candidate.source_type}` when `source_ref` is omitted. Because tombstone checks match either `content_hash` or `source_identity_hash`, deleting one memory with a source-type-only identity can block unrelated future memories in the same tenant/scope/source category even when the content is different.

**Fix:**
```python
_SOURCE_IDENTITY_REQUIRED_DISCRIMINATORS = {
    "event_id",
    "conversation_message_id",
    "tool_result_id",
    "agent_run_id",
    "business_object_id",
    "outcome_id",
}

if not any(source_ref.get(key) for key in _SOURCE_IDENTITY_REQUIRED_DISCRIMINATORS):
    return None
```

Apply this rule before hashing source identity, or avoid emitting `source_identity_hash` for source refs that lack a stable discriminator beyond `source_type`. Keep content-hash tombstones active for exact content no-rewrite.

### WR-02: Duplicate Active Long-Term Memory Writes Crash Instead Of Returning An Idempotent Result

**File:** `src/memory/long_term.py:134`

**Issue:** The migration defines `uq_long_term_memories_active_identity` over `(tenant_id, scope_type, scope_id, content_hash)` for current, undeleted rows at `src/db/migrations/versions/013_long_term_case_memory.py:90`, but `write_memory()` always calls `insert_memory()` after tombstone/PII checks. Re-submitting the same active memory content for the same scope will raise an `IntegrityError` at flush time instead of returning a stable `skipped`/existing-memory result and an observable `memory_write_events` row.

**Fix:**
```python
existing = await self.repository.get_active_by_content_hash(
    tenant_id=candidate.tenant_id,
    scope_type=candidate.scope_type,
    scope_id=candidate.scope_id,
    content_hash=identity["content_hash"],
)
if existing is not None:
    event = await self.repository.emit_write_event(
        tenant_id=candidate.tenant_id,
        run_id=candidate.run_id,
        memory_type=LONG_TERM_MEMORY_TYPE,
        memory_id=existing.id,
        decision="skip",
        reason_code="duplicate_active_identity",
        pii_classification=candidate.pii_classification,
        candidate_hash=identity["candidate_hash"],
        source_ref_json=identity["source_ref_json"],
    )
    return LongTermMemoryWriteResult(
        status="skipped",
        memory_id=existing.id,
        review_status=existing.review_status,
        decision="skip",
        reason_code="duplicate_active_identity",
        pii_classification=candidate.pii_classification,
        candidate_hash=identity["candidate_hash"],
        content_hash=identity["content_hash"],
        source_identity_hash=identity["source_identity_hash"],
        event_id=event.id,
    )
```

Also catch `IntegrityError` around the insert as a race fallback so concurrent duplicate writers do not leave the session in a failed state without a controlled result.

### WR-03: ORM Declares A Different Case-Memory Vector Index Than The Migration

**File:** `src/db/models.py:424`

**Issue:** The migration creates `ix_case_memories_embedding_hnsw` with `USING hnsw` at `src/db/migrations/versions/013_long_term_case_memory.py:180`, but the ORM metadata declares `ix_case_memories_embedding_vector` with `postgresql_using="ivfflat"` at `src/db/models.py:424`. This schema drift means metadata-created databases and future Alembic autogeneration will not match the applied migration, and Phase 16's MEMSCHEMA/HNSW contract is not represented in `Base.metadata`.

**Fix:**
```python
Index(
    "ix_case_memories_embedding_hnsw",
    CaseMemory.embedding,
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
    postgresql_with={"m": 16, "ef_construction": 128},
)
```

Alternatively, remove the ORM index declaration and document that the HNSW index is migration-managed only, then add a metadata/migration contract test so the names do not drift again.

### WR-04: Planner-Visible Case Memory Search Drops The Retrieved Snippets

**File:** `src/agent/nodes/investigate.py:201`

**Issue:** `MemoryToolExecutor` returns reviewed case-memory items in `ToolResultV2.data["items"]` at `src/tools/executors/memory.py:92`, but `investigate()` only carries forward `state.get("case_memory")` and never accumulates those retrieved items into `case_memory`. `_project_tool_result()` also summarizes only tool status/count, so a planner-visible `search_case_memory` call provides little usable precedent context to later prompt assembly even though it reports success.

**Fix:**
```python
context: dict[str, Any] = {
    # ...
    "case_memory": list(state.get("case_memory") or []),
}

def _accumulate_tool_result(...):
    # existing accumulation
    if tool_name == "search_case_memory" and result.status == "success":
        items = (result.data or {}).get("items") if isinstance(result.data, dict) else None
        if isinstance(items, list):
            context["case_memory"].extend(item for item in items if isinstance(item, dict))

# return
"case_memory": context["case_memory"],
```

Keep the current boundary intact: do not copy those items into `policy_evidence`, `evidence_refs`, `business_context.facts`, approval state, or action authority.

### WR-05: `search_case_memory` Ignores Its Required Query Argument

**File:** `src/tools/executors/memory.py:62`

**Issue:** The catalog requires `{"query": string}` for `search_case_memory`, but `_case_memory_request()` immediately deletes the query and builds only broad scope filters. With no `query_embedding`, `case_type`, or other query-derived constraint, the tool can return the latest reviewed memories in broad tenant/user/thread/merchant scope even when they are unrelated to the user's current question.

**Fix:**
```python
def _case_memory_request(*, query: str, context: ToolCallContext) -> CaseMemorySearchRequest | None:
    query_embedding = context.metadata.get("case_memory_query_embedding") if hasattr(context, "metadata") else None
    # or inject an embedding service into MemoryToolExecutor and compute it here
    return CaseMemorySearchRequest(
        tenant_id=tenant_id,
        scopes=scopes,
        query_embedding=query_embedding,
        limit=5,
    )
```

If Phase 16 intentionally defers query embedding for this planner-visible tool, fail closed instead of returning unrelated rows: make the executor return `unavailable` or keep the tool internal until it can honor the query.

---

_Reviewed: 2026-06-17T18:08:26Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
