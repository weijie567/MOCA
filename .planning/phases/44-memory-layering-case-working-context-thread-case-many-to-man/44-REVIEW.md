---
phase: 44-memory-layering-case-working-context-thread-case-many-to-man
reviewed: 2026-07-03T00:07:30Z
depth: deep
files_reviewed: 17
files_reviewed_list:
  - docs/contract-spec.md
  - src/conversation/repository.py
  - src/db/migrations/versions/021_thread_case_links.py
  - src/db/migrations/versions/022_case_working_context.py
  - src/db/models.py
  - src/memory/case_identity.py
  - src/memory/case_working_context.py
  - src/memory/case_working_context_schemas.py
  - src/memory/case_working_context_service.py
  - src/memory/policy.py
  - src/memory/thread_case_links.py
  - tests/db/test_phase44_schema.py
  - tests/memory/test_case_identity.py
  - tests/memory/test_case_working_context_repo.py
  - tests/memory/test_case_working_context_service.py
  - tests/memory/test_phase44_contract_alignment.py
  - tests/memory/test_thread_case_links.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 44: Code Review Report

**Reviewed:** 2026-07-03T00:07:30Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Deep review covered the Phase 44 CWC repositories/service, thread-case link repository, ORM/migrations, contract updates, and tests. The main service path has the expected tenant checks, source-ref normalization, isolated write behavior, audit rows, and PostgreSQL migration coverage. Remaining issues are in lower-level repository edge cases and a contract appendix gap.

## Warnings

### WR-01: Expected Version Is Ignored When No Active CWC Row Exists

**File:** `src/memory/case_working_context.py:82`

**Issue:** `write_working_context()` creates version 1 whenever no active row exists, before honoring `candidate.expected_version`. A caller that supplies `expected_version=1` or `99` after the active row was deleted, or for a scope that never existed, gets a successful create instead of a conflict. That weakens the version/CAS contract and can let stale writers resurrect an absent case working context.

**Fix:**

```python
if row is None:
    if candidate.expected_version is not None:
        return CaseWorkingContextWriteResult(
            status="conflict",
            case_working_context_id=None,
            version=None,
        )
    row = CaseWorkingContext(...)
```

Add a repository test for `expected_version` with no active row.

### WR-02: Direct Repository Writes Can Persist Unvalidated Run Provenance

**File:** `src/memory/case_working_context.py:68`

**Issue:** The repository validates `candidate.updated_by_run_id` only when that field is non-null. If a direct repository caller omits `updated_by_run_id`, `_source_ref_json()` and `normalize_case_working_context_content_sources()` preserve caller-supplied `source_ref.run_id` / `agent_run_id` values. The service path overwrites them with the trusted run, but the repository path can still persist spoofed or cross-tenant run provenance in row and nested content source refs.

**Fix:**

```python
source_ref_json = _source_ref_json(candidate)
await self._assert_source_ref_runs_belong_to_tenant(
    tenant_id=candidate.tenant_id,
    source_ref_json=source_ref_json,
)
```

Implement the helper to validate any present `run_id` / `agent_run_id` as tenant-owned `AgentRun` UUIDs, or strip those fields unless `updated_by_run_id` supplies the trusted run. Add a negative repository test with `updated_by_run_id=None` and a cross-tenant `agent_run_id`.

## Info

### IN-01: Contract Appendix Omits The New Phase 44 Table Schemas

**File:** `docs/contract-spec.md:2390`

**Issue:** Section 13 now declares `thread_case_links`, `case_working_contexts`, and `case_working_context_revisions`, but the detailed schema appendix in Section 18.1 still jumps from existing memory tables to `memory_write_events`. Future schema work can follow the appendix and miss the Phase 44 columns/constraints even though the migrations are correct.

**Fix:** Add appendix entries for `thread_case_links`, `case_working_contexts`, and `case_working_context_revisions`, including tenant composite FKs, active partial unique indexes, version checks, `authority_class = contextual_only`, and `memory_write_events.memory_type = 'case_working_context'`.

## Tests Run

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/db/test_phase44_schema.py tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py tests/memory/test_case_working_context_service.py tests/memory/test_phase44_contract_alignment.py tests/memory/test_thread_case_links.py
```

Result: `48 passed, 5 warnings in 32.70s`.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check docs/contract-spec.md src/conversation/repository.py src/db/migrations/versions/021_thread_case_links.py src/db/migrations/versions/022_case_working_context.py src/db/models.py src/memory/case_identity.py src/memory/case_working_context.py src/memory/case_working_context_schemas.py src/memory/case_working_context_service.py src/memory/policy.py src/memory/thread_case_links.py tests/db/test_phase44_schema.py tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py tests/memory/test_case_working_context_service.py tests/memory/test_phase44_contract_alignment.py tests/memory/test_thread_case_links.py
```

Result: `All checks passed!`

---

_Reviewed: 2026-07-03T00:07:30Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
