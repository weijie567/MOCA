---
phase: 48-narrow-long-term-explicit-preference-memory
reviewed: 2026-07-04T02:41:19Z
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
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 48: Code Review Report

**Reviewed:** 2026-07-04T02:41:19Z
**Depth:** deep
**Files Reviewed:** 25
**Status:** clean

## Summary

Deep re-review covered the Phase 48 memory contract docs, long-term explicit preference write/retrieval path, memory write facade, memory review API, auth scope/role guards, semantic episode projection, and the listed regression tests.

The prior merchant-scoped closed-case provenance finding is resolved. `MemoryWriteService` now requires `closed_case_cwc_candidate` state candidates to pass the shared closed-case source-ref gate before either merchant or case scope acceptance, and the regression tests cover trusted merchant scope, missing `source_ref`, missing `event_id`, missing `business_object_id`, and wrong `business_object_type`.

All reviewed files meet the current quality, security, and contract boundaries. No current issues found.

## Verification

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_write_node.py tests/architecture/test_memory_contract_delta.py tests/memory/test_long_term_memory_repository.py tests/memory/test_long_term_memory_service.py tests/memory/test_memory_policy.py tests/memory/test_memory_write_service.py tests/memory/test_phase48_long_term_preference_alignment.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_semantic_episode_projection.py tests/test_memory_review_api.py
```

Result: 130 passed, 1 existing LangGraph deprecation warning.

---

_Reviewed: 2026-07-04T02:41:19Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
