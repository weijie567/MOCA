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
- Post-review focused regression suite: `uv run pytest tests/memory/test_memory_identity.py tests/memory/test_long_term_memory_service.py tests/memory/test_memory_schema.py tests/memory/test_case_memory_retrieval.py tests/agent/test_tools/test_unified_tool_manager.py::test_search_case_memory_dispatches_to_reviewed_case_memory_service tests/agent/test_nodes/test_investigate.py::test_search_case_memory_tool_result_accumulates_contextual_case_memory -q` - passed, 33 tests, 1 warning.
- Post-review expanded memory/tool suite: `uv run pytest tests/memory tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_memory_evidence_boundary.py -q` - passed, 144 tests, 1 warning.
- Post-review lint: `uv run ruff check src/ tests/` - passed.
- Post-review schema drift: `gsd-sdk query verify.schema-drift 16` - passed, `valid: true`, `issues: []`.
- Post-review full suite: `uv run pytest -q` - passed, 980 tests, 6 warnings, 506.49s.
- Lifecycle follow-up regression suite: `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_memory_tombstones.py tests/memory/test_case_memory_retrieval.py -q` - passed, 31 tests, 1 warning.
- Lifecycle follow-up expanded memory/agent suite: `uv run pytest tests/memory tests/agent/test_memory_evidence_boundary.py tests/agent/test_policy_retrieval_ownership.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_unified_tool_manager.py -q` - passed, 152 tests, 1 warning.
- Lifecycle follow-up lint: `uv run ruff check src/memory tests/memory` - passed.
- Lifecycle follow-up full suite: `uv run pytest -q` - passed, 988 tests, 6 warnings, 564.26s.

## Full-Suite Deviation And Fix

The first full-suite run during Plan 16-09 failed with 2 failures:

- `tests/approvals/test_migration_contract.py::test_migration_report_names_read_switch_fallback_rollback_and_verification_commands` expected the Phase 13 migration report at the pre-archive `.planning/phases/...` path.
- `tests/replay/test_memory_foundation_alignment.py::test_phase_16_and_phase_17_artifacts_are_not_created` still asserted Phase 16 memory tables should not exist.

Both failures were stale cross-phase guard assumptions after v1.1 archive and intentional Phase 16 schema implementation. Commit `419b935` updated the tests to read the archived Phase 13 artifact and to preserve Phase 15.1/Phase 17 boundaries without contradicting Phase 16 tables. The full suite then passed.

## Code Review Fixes

Phase-level code review found 1 critical issue and 5 warnings in `.planning/phases/16-long-term-case-memory/16-REVIEW.md`. Commit `506c50d` resolved the findings:

- `supersede_memory()` now blocks prohibited PII before mutating the existing memory chain.
- Source identity hashes now require a durable discriminator beyond `source_type` or run metadata.
- Duplicate active long-term writes now return a skipped existing-memory result and event instead of the normal duplicate path hitting the active unique index.
- ORM metadata now matches the HNSW case-memory embedding index from migration 013.
- Planner-visible `search_case_memory` now accumulates prompt-safe case-memory snippets in investigate state.
- `search_case_memory` now preserves the required query argument and applies content-text filtering when no embedding is available.

The resolution is recorded in `.planning/phases/16-long-term-case-memory/16-REVIEW-FIX.md`.

Follow-up lifecycle review passes on 2026-06-18 found additional warning-class edge cases in long-term memory publication, supersede anchors, expired approvals, and expired tombstone identities. Commits `2312abe` and `f365f00` resolved those issues:

- Review-required supersede replacements now stay non-current until approval; approving them atomically supersedes the previous current row.
- Long-term review actions now require active `needs_review` rows and reject expired pending approval rows.
- Ordinary `needs_review` long-term candidates no longer occupy the current published slot or block later explicit/deterministic same-content writes.
- `supersede_memory()` now requires the previous row to be current, published, undeleted, and unexpired.
- Expired auto-approved replacement candidates are skipped without mutating the previous memory.
- Long-term and case tombstone creation now retires expired tombstones for the same content/source identity before creating a fresh tombstone.

## Coverage

Requirement coverage is recorded in `.planning/phases/16-long-term-case-memory/16-COVERAGE.md`. The manifest lists all 14 Phase 16 requirement IDs and is guarded by `tests/memory/test_phase16_requirement_coverage.py`.

The DB-backed pgvector recall fallback from `16-VALIDATION.md` was not needed because automated SQLAlchemy/pgvector-backed case-memory retrieval tests passed.

## Known Stubs

None recorded for Phase 16 closure. Safe empty/unavailable fallback paths remain intentional fail-closed behavior and do not claim continuity.
