---
phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener
reviewed: 2026-07-03T15:08:43Z
depth: deep
files_reviewed: 15
files_reviewed_list:
  - docs/architecture-overview.md
  - docs/contract-spec.md
  - docs/current-implementation-map.md
  - src/memory/case_precedent.py
  - src/memory/policy.py
  - src/memory/schemas.py
  - src/repositories/refund_repo.py
  - tests/agent/test_reviewed_memory_context_retrieve.py
  - tests/memory/test_case_memory_retrieval.py
  - tests/memory/test_case_precedent_generation.py
  - tests/memory/test_memory_policy.py
  - tests/memory/test_phase47_case_precedent_alignment.py
  - tests/memory/test_reviewed_memory_context_boundary.py
  - tests/test_memory_review_api.py
  - tests/tools/test_catalog.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 47: Code Review Report

**Reviewed:** 2026-07-03T15:08:43Z
**Depth:** deep
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Reviewed the listed Phase 47 docs, implementation files, and tests at deep depth, including cross-file checks through `CaseMemoryService`, reviewed memory context retrieval, CWC projection, tool catalog boundaries, and review API behavior.

Two correctness issues need follow-up: generated closed-case candidates can dedupe distinct merchant precedents because their identity content is too generic, and the real reviewed-memory node can filter approved generated precedents out by using `primary_intent` as `case_type`. One documentation consistency issue was also found in the normative storage model.

No test suite was run during this review; findings are from static and cross-file analysis.

## Warnings

### WR-01: Generic closed-case summaries collapse distinct merchant precedents

**File:** `/Users/ming/projects/MOCA/src/memory/case_precedent.py:190`
**Issue:** Closed-case generated candidates use a generic summary of only `Closed refund case precedent: {case_type}.`, while `CaseMemoryService` derives `content_hash` only from `candidate.summary` in `/Users/ming/projects/MOCA/src/memory/case_memory.py:765-768`. Because duplicate detection checks `(tenant_id, scope_type, scope_id, content_hash)` before source identity, the second closed refund case for the same merchant and same `case_type` is skipped as `duplicate_active_identity` even when it has a different source case, CWC row, excerpt, facts, and outcome.
**Fix:**
```python
def _case_memory_identity_content(candidate: CaseMemoryWriteCandidate) -> str:
    return "\n".join(
        part
        for part in (
            candidate.summary,
            candidate.excerpt,
            candidate.applicability,
            candidate.outcome,
            candidate.caveats,
        )
        if part
    )

content_hash = canonical_memory_content_hash(
    memory_type=CASE_MEMORY_TYPE,
    content=_case_memory_identity_content(candidate),
)
```
Add a regression test that generates two different closed refund cases under the same merchant and same `issue_type`; both should create separate `needs_review` rows unless the full projected content is actually identical.

### WR-02: Reviewed-memory node filters generated precedents with the wrong case type

**File:** `/Users/ming/projects/MOCA/src/agent/nodes/reviewed_memory_context_retrieve.py:418`
**Issue:** The real node passes `case_type=_case_type(state)`, and `_case_type` returns `primary_intent` / `current_intent`. Generated closed-case precedents use CWC `issue_type` as `CaseMemory.case_type` in `/Users/ming/projects/MOCA/src/memory/case_precedent.py:189-202`. In normal refund flows, `primary_intent` is often `refund_troubleshooting`, while CWC issue types are values such as `refund_dispute` or `refund_status`; the exact filter in `CaseMemoryRepository._metadata_filters` then hides approved generated precedents from `reviewed_memory_context_retrieve`. Existing tests cover the service with explicit `case_type="refund_dispute"` and the node with fake services, but not the real node-service combination.
**Fix:**
```python
def _case_type(state: AgentState) -> str | None:
    for slot_source in (state.get("active_slots"), state.get("extracted_slots")):
        if isinstance(slot_source, Mapping):
            issue_type = slot_source.get("issue_type")
            if isinstance(issue_type, str) and issue_type.strip():
                return issue_type.strip()[:64]
    return None  # or use an explicit intent-to-case-type mapping shared with CWC projection
```
Add an integration test that inserts or generates an approved `closed_case_cwc_candidate` with `case_type="refund_dispute"`, runs `reviewed_memory_context_retrieve` with `primary_intent="refund_troubleshooting"` and matching merchant scope, and asserts the case item is returned.

## Info

### IN-01: Contract storage model is stale for case memory scope columns

**File:** `/Users/ming/projects/MOCA/docs/contract-spec.md:2456`
**Issue:** The `case_memories` storage model still lists fields and indexes such as `merchant_id`, `action_taken_json`, `approval_outcome_json`, `outcome_label`, `source_run_id`, and an index on `(tenant_id, merchant_id, case_type, created_at)`, but the current ORM model uses polymorphic `scope_type/scope_id` and does not define those columns (`/Users/ming/projects/MOCA/src/db/models.py:508-543`). This also conflicts with the Phase 47 text that says reusable retrieval scope lives in `CaseMemory.scope_type/scope_id`.
**Fix:** Update the storage model to match the implemented `case_memories` schema, or explicitly label the extra columns as future target fields and keep the Phase 47 MVP index guidance on `scope_type/scope_id` rather than `merchant_id`.

---

_Reviewed: 2026-07-03T15:08:43Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
