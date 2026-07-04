---
phase: 48-narrow-long-term-explicit-preference-memory
plan: 03
subsystem: memory
tags: [long-term-memory, preferences, chat-capture, admin-api, auth]

requires:
  - phase: 48-narrow-long-term-explicit-preference-memory
    provides: 48-02 preference-only source policy and semantic candidate narrowing
provides:
  - deterministic explicit user preference capture from chat
  - admin-only long-term preference save API
  - memory:write admin auth scope
affects: [phase-48, memory-write, memory-api, auth, long-term-memory]

tech-stack:
  added: []
  patterns:
    - deterministic phrase gate instead of semantic/LLM preference inference
    - admin direct save still routes through LongTermMemoryService audit gates

key-files:
  created:
    - src/memory/preference_capture.py
  modified:
    - src/memory/write_service.py
    - src/agent/nodes/memory_write.py
    - src/api/routers/memory.py
    - src/api/schemas/memory.py
    - src/auth/jwt.py
    - src/auth/permissions.py
    - tests/memory/test_memory_write_service.py
    - tests/agent/test_memory_write_node.py
    - tests/test_memory_review_api.py
    - .planning/ARCHITECTURE-DEBT.md

key-decisions:
  - "Chat-captured user preferences require deterministic explicit phrases."
  - "Chat-captured preferences are merchant scoped from trusted context only."
  - "Tenant-scoped long-term preference is admin-only via memory:write."

patterns-established:
  - "memory_write passes trusted_context into MemoryWriteService for scope-constrained candidate construction."
  - "Admin memory writes use explicit_admin_preference and do not masquerade as pending review."

requirements-completed: [MEM-05]

duration: 12min
completed: 2026-07-04
---

# Phase 48 Plan 03 Summary

**Explicit user/admin preference write paths with deterministic chat gate and admin-only tenant scope**

## Performance

- **Duration:** about 12 min
- **Started:** 2026-07-04T08:16:59+08:00
- **Completed:** 2026-07-04T08:28:33+08:00
- **Tasks:** 2
- **Files modified:** 11 files, plus local validation issue record

## Accomplishments

- Added `src/memory/preference_capture.py` with deterministic explicit preference phrase detection, hard-rule rejection, PII classification, and trusted merchant scope resolution.
- Wired explicit user preference capture into `MemoryWriteService.propose_candidates(...)` and passed `configurable["trusted_context"]` from the `memory_write` node.
- Added admin-only `POST /api/v1/memory/long-term/preferences` with `memory:write` scope, merchant/tenant scope validation, and direct `explicit_admin_preference` writes through `LongTermMemoryService`.

## Task Commits

1. **Task 1: Add deterministic explicit user preference capture to memory_write** - `d1c0c88` (feat/test)
2. **Task 2: Add admin-only long-term preference save API** - `f836536` (feat/test)

## Files Created/Modified

- `src/memory/preference_capture.py` - Deterministic phrase gate and preference candidate builder.
- `src/memory/write_service.py` - Trusted-context-aware explicit user preference candidate proposal and state-candidate guard.
- `src/agent/nodes/memory_write.py` - Trusted context passed to memory write service.
- `src/api/routers/memory.py` - Admin preference save endpoint and scope validation.
- `src/api/schemas/memory.py` - Admin preference save request/response schemas.
- `src/auth/jwt.py` / `src/auth/permissions.py` - `memory:write` admin scope and OAuth scope description.
- `tests/memory/test_memory_write_service.py`, `tests/agent/test_memory_write_node.py`, `tests/test_memory_review_api.py` - Chat/admin write path coverage.

## Decisions Made

普通 chat 不进行语义推断写入长期偏好；只有明确短语进入 candidate builder。chat path 只使用 trusted merchant scope，tenant scope 只允许 admin API 通过 `explicit_admin_preference` 创建。

## Deviations from Plan

None. The implementation follows the planned split between deterministic chat capture and admin-only direct save.

## Issues Encountered

One node test initially asserted `scope_type` on every candidate projection, including session projections that do not carry scope fields. The assertion was narrowed to long-term projections and the issue was recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_write_service.py tests/agent/test_memory_write_node.py -x -q` -> 36 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_memory_review_api.py tests/memory/test_long_term_memory_service.py -x -q` -> 29 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_write_service.py tests/agent/test_memory_write_node.py tests/test_memory_review_api.py tests/memory/test_long_term_memory_service.py -q` -> 65 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/preference_capture.py src/memory/write_service.py src/agent/nodes/memory_write.py src/api/routers/memory.py src/api/schemas/memory.py src/auth/jwt.py src/auth/permissions.py tests/memory/test_memory_write_service.py tests/agent/test_memory_write_node.py tests/test_memory_review_api.py` -> pass.

## User Setup Required

None.

## Next Phase Readiness

48-04 can now close retrieval filtering, review approval publishing as `human_reviewed`, correction/tombstone lifecycle, and final validation on top of explicit write paths and source policy gates.

---
*Phase: 48-narrow-long-term-explicit-preference-memory*
*Completed: 2026-07-04*
