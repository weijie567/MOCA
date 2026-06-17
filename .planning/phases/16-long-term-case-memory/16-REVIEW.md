---
phase: 16-long-term-case-memory
reviewed: 2026-06-18T00:00:00Z
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
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 16: Code Review Report

**Reviewed:** 2026-06-18T00:00:00Z
**Depth:** deep
**Files Reviewed:** 39
**Status:** issues_found

## Summary

Deep review covered the listed context assembly, graph nodes, memory services/repositories/schemas, migration/model declarations, tool catalog/manager, and related tests. The prompt-safe projection and reviewed-memory-vs-policy-evidence boundaries are generally well covered. The main concerns are long-term memory lifecycle edge cases that can hide approved memories or allow invalid lifecycle transitions.

## Warnings

### WR-01: Superseding With A Review-Required Replacement Hides The Current Approved Memory

**File:** `src/memory/long_term.py:400`
**Issue:** `supersede_memory()` marks the previous memory as `is_current=False` and `review_status='superseded'` before inserting the replacement, regardless of the replacement's review status. If the replacement source is `llm_candidate`, `semantic_episode_candidate`, or another review-required source, the new row is inserted with `review_status='needs_review'` but `is_current=True`. Retrieval only publishes `auto_approved`/`approved` rows, so the previously approved memory disappears until manual approval, creating a continuity/data-contract regression.
**Fix:** Keep the previous memory current when the replacement requires review, or insert review-required replacements as non-current pending candidates and only supersede the previous row during approval.

```python
review_status = _review_status_for_source(replacement_candidate.source_type)
replacement_is_current = review_status == "auto_approved"
if replacement_is_current:
    previous.is_current = False
    previous.review_status = "superseded"
    previous.superseded_at = now
```

### WR-02: Long-Term Review Actions Can Mutate Invalid Lifecycle States

**File:** `src/memory/long_term.py:197`
**Issue:** `approve_memory()` and `reject_memory()` call `update_review_status()` without checking the current lifecycle state. Unlike `CaseMemoryRepository.approve_case_memory()`/`reject_case_memory()`, long-term memory can be approved or rejected after it is already approved, rejected, deleted, tombstoned, or superseded. In particular, approval sets `is_current=True` while leaving fields such as `deleted_at`, `superseded_by`, or `superseded_at` untouched, which can create inconsistent rows and future retrieval/unique-index surprises.
**Fix:** Require `review_status == 'needs_review'` before approval/rejection, and refuse deleted/tombstoned/superseded rows. Prefer repository-level guards so all service entry points share the same lifecycle contract.

```python
memory = await self.repository.get_memory(tenant_id=tenant_id, memory_id=memory_id)
if memory is None:
    raise ValueError("long-term memory not found")
if memory.review_status != "needs_review" or memory.deleted_at is not None:
    raise ValueError("long-term memory review requires needs_review status")
```

### WR-03: Expired Current Memories Block Fresh Writes With The Same Content

**File:** `src/memory/repository.py:185`
**Issue:** `get_active_by_content_hash()` treats any non-deleted `is_current=True` row as a duplicate, but it does not exclude expired rows. `write_memory()` uses this method to skip duplicate writes, while retrieval excludes expired rows. A same-content refresh after expiry can therefore be skipped as `duplicate_active_identity`, leaving no retrievable memory even though the existing row is expired.
**Fix:** Pass `now` from `write_memory()` into `get_active_by_content_hash()` and filter out expired rows with `expires_at IS NULL OR expires_at > now`.

```python
.where(
    LongTermMemory.deleted_at.is_(None),
    LongTermMemory.is_current.is_(True),
    or_(LongTermMemory.expires_at.is_(None), LongTermMemory.expires_at > now),
)
```

---

_Reviewed: 2026-06-18T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
