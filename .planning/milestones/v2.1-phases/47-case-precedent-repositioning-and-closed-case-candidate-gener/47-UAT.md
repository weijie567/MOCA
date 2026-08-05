---
status: complete
phase: 47-case-precedent-repositioning-and-closed-case-candidate-gener
source:
  - 47-01-SUMMARY.md
  - 47-02-SUMMARY.md
  - 47-03-SUMMARY.md
  - 47-04-SUMMARY.md
started: 2026-07-04T00:23:16+08:00
updated: 2026-07-04T00:23:16+08:00
mode: self-verified-backend-uat
---

## Current Test

[testing complete]

## Tests

### 1. Case Memory Boundary Is Reviewed Closed-Case Precedent
expected: `case_memories` remains reviewed closed-case precedent, not active case working state; active case state stays in `case_working_contexts`, and protected memory table names/`conversation_threads.case_id` remain intact.
result: pass
evidence: `docs/contract-spec.md`, `docs/current-implementation-map.md`, `docs/architecture-overview.md`, `tests/memory/test_phase47_case_precedent_alignment.py`, and `src/db/models.py`

### 2. Closed Case CWC Generates Governed Review Candidates
expected: A trusted terminal refund-case close with active CWC creates a `closed_case_cwc_candidate` only through `CaseMemoryService.submit_case_memory_candidate(...)`, defaults to `needs_review`, records allowed source identity, and preserves mapped policy refs.
result: pass
evidence: `src/memory/case_precedent.py`, `src/memory/case_memory.py`, `tests/memory/test_case_precedent_generation.py`, and `tests/test_memory_review_api.py`

### 3. Duplicate, Source Identity, And PII Controls Hold
expected: Repeated close/CWC identities dedupe through the existing case-memory service, distinct same-merchant closed cases do not collapse by generic summary, and sensitive/prohibited CWC rows emit `pii_blocked` without persisting raw sensitive content.
result: pass
evidence: `src/memory/case_memory.py`, `src/memory/case_precedent.py`, `tests/memory/test_case_precedent_generation.py`, and `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-REVIEW-FIX.md`

### 4. Reviewed Retrieval Publishes Only After Approval
expected: Generated candidates are visible to the existing pending-review surface but hidden from reviewed retrieval until approval; after approval, metadata/text retrieval with `query_embedding=None` works under merchant and exact case scopes.
result: pass
evidence: `tests/memory/test_case_precedent_generation.py`, `tests/memory/test_case_memory_retrieval.py`, `tests/memory/test_reviewed_memory_context_boundary.py`, and `tests/agent/test_reviewed_memory_context_retrieve.py`

### 5. Planner-Facing Contracts Stay Narrow
expected: `search_case_memory` uses reviewed case memory and builds scopes from tenant/user/thread/merchant context; `ToolCallContext` remains case-id-free, reviewed memory context stays separate from active CWC, and generated precedent filtering uses `issue_type` rather than `primary_intent`.
result: pass
evidence: `src/tools/executors/memory.py`, `src/tools/contracts.py`, `src/agent/nodes/reviewed_memory_context_retrieve.py`, `tests/tools/test_catalog.py`, and `tests/agent/test_reviewed_memory_context_retrieve.py`

### 6. Phase 48 Preference Memory Remains Deferred
expected: Phase 47 does not implement explicit durable long-term preference memory; DEFER-3 remains mapped to Phase 48/MEM-05 by name.
result: pass
evidence: `.planning/MEMORY-REDESIGN-DECISIONS.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `docs/architecture-overview.md`, and `tests/memory/test_phase47_case_precedent_alignment.py`

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Verification

`UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_memory_policy.py tests/test_memory_review_api.py tests/agent/test_reviewed_memory_context_retrieve.py tests/tools/test_catalog.py -q`

Result: `123 passed, 1 warning in 121.35s (0:02:01)`.

The warning is the existing LangGraph/LangChain pending deprecation warning from `.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py` and is not a Phase 47 UAT issue.

Security gate is complete: `.planning/phases/47-case-precedent-repositioning-and-closed-case-candidate-gener/47-SECURITY.md` has `status: verified` and `threats_open: 0`.

## Gaps

No UAT gaps.
