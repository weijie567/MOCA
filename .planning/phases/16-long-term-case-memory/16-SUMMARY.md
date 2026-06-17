---
phase: 16
slug: long-term-case-memory
status: complete
plans_total: 9
plans_completed: 9
completed: 2026-06-18
coverage: .planning/phases/16-long-term-case-memory/16-COVERAGE.md
---

# Phase 16: Long-term / Case Memory Execution Summary

Phase 16 implemented reviewed long-term profile memory and reviewed case memory retrieval on top of the v1.1 conversation/context foundation. Memory remains contextual assistance only: it is not policy evidence, current business fact truth, approval/action authority, or replay/audit truth.

## Completed Plans

| Plan | Summary |
|------|---------|
| 16-01 | Added `memory_identity.v1` canonical content/source/candidate hashing and prompt-safe identity schemas. |
| 16-02 | Added SQLAlchemy models and Alembic migration 013 for long-term memories, case memories, memory tombstones, and memory write events. |
| 16-03 | Added reviewed long-term memory write/review/retrieval service and repository behavior. |
| 16-04 | Added candidate-only semantic episode projection feeding review-gated long-term candidates. |
| 16-05 | Added tombstone no-rewrite, delete, delayed-write blocking, and supersede event chains. |
| 16-06 | Added reviewed case memory storage/retrieval with metadata filtering and tombstone blocking. |
| 16-07 | Added bounded prompt-safe memory blocks to `ContextAssembler`. |
| 16-08 | Wired reviewed memory retrieval into graph state and prompt call sites. |
| 16-09 | Backed planner-visible `search_case_memory` with reviewed case memory and added final coverage/eval closure. |

## Verification Results

- MEMSCHEMA exact command: `uv run pytest tests/memory/test_memory_schema.py tests/conversation/test_models.py -q` - passed, 17 tests, 6 warnings.
- Focused Phase 16 suite: `uv run pytest tests/memory tests/agent/context tests/agent/test_memory_evidence_boundary.py tests/tools/test_catalog.py tests/agent/test_policy_retrieval_ownership.py tests/memory/test_phase16_requirement_coverage.py -q` - passed, 114 tests, 1 warning.
- Legacy search transition command: `uv run pytest tests/tools/test_catalog.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_tools/test_unified_tool_manager.py tests/memory/test_session_precedent_search.py -q` - passed, 55 tests, 1 warning.
- Full suite: `uv run pytest -q` - passed, 974 tests, 6 warnings, 511.65s.

## Full-Suite Deviation And Fix

The first full-suite run during Plan 16-09 failed with 2 failures:

- `tests/approvals/test_migration_contract.py::test_migration_report_names_read_switch_fallback_rollback_and_verification_commands` expected the Phase 13 migration report at the pre-archive `.planning/phases/...` path.
- `tests/replay/test_memory_foundation_alignment.py::test_phase_16_and_phase_17_artifacts_are_not_created` still asserted Phase 16 memory tables should not exist.

Both failures were stale cross-phase guard assumptions after v1.1 archive and intentional Phase 16 schema implementation. Commit `419b935` updated the tests to read the archived Phase 13 artifact and to preserve Phase 15.1/Phase 17 boundaries without contradicting Phase 16 tables. The full suite then passed.

## Coverage

Requirement coverage is recorded in `.planning/phases/16-long-term-case-memory/16-COVERAGE.md`. The manifest lists all 14 Phase 16 requirement IDs and is guarded by `tests/memory/test_phase16_requirement_coverage.py`.

The DB-backed pgvector recall fallback from `16-VALIDATION.md` was not needed because automated SQLAlchemy/pgvector-backed case-memory retrieval tests passed.

## Known Stubs

None recorded for Phase 16 closure. Safe empty/unavailable fallback paths remain intentional fail-closed behavior and do not claim continuity.

