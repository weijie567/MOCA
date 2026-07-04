---
phase: 48-narrow-long-term-explicit-preference-memory
reviewed: 2026-07-04T01:48:37Z
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
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 48: Code Review Report

**Reviewed:** 2026-07-04T01:48:37Z
**Depth:** deep
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Deep re-review covered the Phase 48 memory contract docs, memory write facade, long-term preference service and repository, admin/review API, auth scope additions, semantic episode projection, memory write node, and related tests.

The prior CR-01, WR-01, and IN-01 are resolved: state-origin long-term candidates now fail closed on tenant/run/source/scope boundaries, long-term preference publication rejects hard-rule content at write and approval boundaries, and the architecture overview now documents the implemented narrow explicit preference path.

Verification with `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_write_service.py tests/memory/test_long_term_memory_service.py tests/test_memory_review_api.py tests/agent/test_memory_write_node.py tests/memory/test_phase48_long_term_preference_alignment.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_semantic_episode_projection.py tests/memory/test_long_term_memory_repository.py tests/memory/test_memory_policy.py tests/architecture/test_memory_contract_delta.py` reported 119 passed and 1 failed. The remaining issue is a stale test expectation in the memory write node suite.

## Warnings

### WR-01: Memory write node test omits trusted context for a trusted long-term candidate

**File:** `tests/agent/test_memory_write_node.py:194`
**Issue:** `test_memory_write_node_applies_explicit_long_term_and_case_candidates_through_facade` expects the state-provided long-term merchant candidate to pass through the facade, but the test invokes `memory_write` with only a session object. After the Phase 48 boundary fix, `MemoryWriteService` correctly rejects state-origin long-term merchant candidates unless `trusted_context.merchant_scope` permits the candidate scope. The targeted approved test run fails because the long-term candidate is filtered out and only `["session", "case"]` remains.
**Fix:** Provide a trusted merchant scope in this test when asserting the long-term candidate is applied, or change the expected projection to omit long-term if the test is meant to cover the untrusted path.

```python
result = await memory_write(
    state,
    {
        "configurable": {
            "session": object(),
            "trusted_context": {"merchant_scope": {"merchant_ids": ["merchant-1"]}},
        }
    },
)
```

---

_Reviewed: 2026-07-04T01:48:37Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
