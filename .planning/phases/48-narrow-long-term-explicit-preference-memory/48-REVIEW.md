---
phase: 48-narrow-long-term-explicit-preference-memory
reviewed: 2026-07-04T01:58:56Z
depth: deep
files_reviewed: 25
files_reviewed_list:
  - docs/architecture-overview.md
  - docs/contract-spec.md
  - docs/memory-contract-delta.md
  - src/agent/nodes/memory_write.py
  - src/api/routers/memory.py
  - src/api/schemas/memory.py
  - src/auth/jwt.py
  - src/auth/permissions.py
  - src/memory/long_term.py
  - src/memory/policy.py
  - src/memory/preference_capture.py
  - src/memory/repository.py
  - src/memory/schemas.py
  - src/memory/semantic_episode.py
  - src/memory/write_service.py
  - tests/agent/test_memory_write_node.py
  - tests/architecture/test_memory_contract_delta.py
  - tests/memory/test_long_term_memory_repository.py
  - tests/memory/test_long_term_memory_service.py
  - tests/memory/test_memory_policy.py
  - tests/memory/test_memory_write_service.py
  - tests/memory/test_phase48_long_term_preference_alignment.py
  - tests/memory/test_reviewed_memory_context_boundary.py
  - tests/memory/test_semantic_episode_projection.py
  - tests/test_memory_review_api.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 48: Code Review Report

**Reviewed:** 2026-07-04T01:58:56Z
**Depth:** deep
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Deep re-review covered the Phase 48 memory contract docs, long-term preference write/retrieval path, memory write facade, review API, auth scope changes, semantic episode projection, and tests. The prior long-term preference boundary fixes are present, but two current issues remain around review authorization and state-origin case-memory provenance.

## Critical Issues

### CR-01: Merchant-bound managers can review all tenant memory

**File:** `/Users/ming/projects/MOCA/src/api/routers/memory.py:30`
**Issue:** `MEMORY_REVIEW_ROLES` allows `manager`, and `manager` receives the `approvals:review` scope in `/Users/ming/projects/MOCA/src/auth/jwt.py:15`. The review API then lists and mutates pending long-term/case memory by `tenant_id` only (`src/api/routers/memory.py:45`, `src/api/routers/memory.py:52`, `src/api/routers/memory.py:284`, `src/api/routers/memory.py:335`). Because MOCA's trusted context model treats `manager` as merchant-bound, a manager for one merchant can list, approve, reject, delete, or forget another merchant's memory within the same tenant.
**Fix:** Fail closed to admin-only until merchant-scoped review is implemented, or load each memory row before action and enforce `user.merchant_id` against `scope_type="merchant"` / resolved case merchant. Add cross-merchant API tests with `manager_other_merchant`.

```python
MEMORY_REVIEW_ROLES = {"admin"}

def _assert_memory_reviewer(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Insufficient role for memory review"},
        )
```

## Warnings

### WR-01: State-origin case candidates can self-claim reviewed/admin provenance

**File:** `/Users/ming/projects/MOCA/src/memory/write_service.py:291`
**Issue:** `_state_candidate_identity_allowed` applies trusted scope/source restrictions only to `LongTermMemoryWriteCandidate`. A `CaseMemoryWriteCandidate` from `state["memory_write_candidates"]` only needs matching tenant/run/source_ref, so it can use `source_type="human_reviewed"` or `source_type="explicit_admin_preference"`. `case_memory_policy_decision` auto-approves those sources, which lets state-provided candidates bypass the intended review-required case-memory path.
**Fix:** Add a case-specific state gate. State-origin case candidates should be limited to review-required generator sources such as `closed_case_cwc_candidate` / `semantic_episode_candidate`, and merchant/case scope must be checked against trusted context or resolved case identity. Keep `human_reviewed` and `explicit_admin_preference` for explicit review/admin service paths only.

```python
from src.memory.policy import REVIEW_REQUIRED_CASE_SOURCE_TYPES

def _state_candidate_identity_allowed(...):
    ...
    if isinstance(candidate, LongTermMemoryWriteCandidate):
        return _state_long_term_candidate_allowed(candidate, trusted_context=trusted_context)
    if isinstance(candidate, CaseMemoryWriteCandidate):
        return _state_case_candidate_allowed(candidate, trusted_context=trusted_context)
    return True

def _state_case_candidate_allowed(
    candidate: CaseMemoryWriteCandidate,
    *,
    trusted_context: Any | None,
) -> bool:
    if candidate.source_type not in REVIEW_REQUIRED_CASE_SOURCE_TYPES:
        return False
    if candidate.scope_type == "merchant":
        return _trusted_merchant_scope_allows(candidate.scope_id, trusted_context=trusted_context)
    return candidate.scope_type == "case" and candidate.source_type == "closed_case_cwc_candidate"
```

---

_Reviewed: 2026-07-04T01:58:56Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
