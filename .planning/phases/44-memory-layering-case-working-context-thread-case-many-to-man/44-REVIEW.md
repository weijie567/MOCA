---
phase: 44-memory-layering-case-working-context-thread-case-many-to-man
reviewed: 2026-07-03T00:24:43Z
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
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 44: Code Review Report

**Reviewed:** 2026-07-03T00:24:43Z
**Depth:** deep
**Files Reviewed:** 17
**Status:** clean

## Summary

Deep re-review covered the Phase 44 Case Working Context layer, thread-to-case many-to-many links, ORM models, Alembic migrations, contract appendix updates, and the scoped tests after commit `94da915 fix(44): close CWC review findings`.

All reviewed files meet quality standards. No bugs, security vulnerabilities, tenant/provenance boundary issues, migration regressions, concurrency/versioning defects, or actionable code quality findings remain in the reviewed scope.

## Prior Findings Verification

- WR-01 is closed. `src/memory/case_working_context.py` now returns `conflict` when `expected_version` is supplied and no active CWC row exists, before any row or revision is inserted. `tests/memory/test_case_working_context_repo.py` covers the no-active-row conflict path.
- WR-02 is closed. Direct CWC repository writes now normalize row and nested content source refs to the target refund case, validate any present `run_id` / `agent_run_id` values against same-tenant `agent_runs`, and reject cross-tenant provenance. Repository and service tests cover the negative cases.
- IN-01 is closed. `docs/contract-spec.md` Section 18.1 now documents `thread_case_links`, `case_working_contexts`, and `case_working_context_revisions`, including tenant composite FKs, active unique indexes, authority/version checks, and CWC source provenance requirements. `tests/memory/test_phase44_contract_alignment.py` covers the appendix terms.

## Deep Review Notes

- Tenant boundaries: `thread_case_links` and CWC rows use tenant-scoped validation plus composite tenant FKs in models and migrations.
- Provenance boundaries: CWC service and repository paths normalize trusted run/case source refs and validate run ownership; thread-case links validate thread, case, and optional run ownership.
- Versioning/concurrency: CWC writes serialize by tenant/case advisory lock, lock active rows with `FOR UPDATE`, preserve prior active versions in append-only revisions, and return conflict on stale `expected_version`. Thread-case links serialize by tenant/thread/case advisory lock and dedupe active links.
- Migration correctness: the Alembic chain is linear through revisions 021 and 022; upgrade/downgrade behavior and the downgrade guard for CWC audit rows are covered by PostgreSQL-backed tests.

## Residual Risks / Test Gaps

- Phase 44 introduces storage/service surfaces but does not wire automatic CWC update hooks into production graph flow yet; that integration is deferred and should be reviewed when Phase 45 or equivalent lifecycle wiring lands.
- Repository-level tests exercise direct CWC persistence for schema, versioning, and provenance. PII blocking is covered at the `CaseWorkingContextService` policy/audit entrypoint, which is the intended write boundary for CWC memory-write events.

## Tests Run

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/db/test_phase44_schema.py tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py tests/memory/test_case_working_context_service.py tests/memory/test_phase44_contract_alignment.py tests/memory/test_thread_case_links.py
```

Result: `51 passed, 5 warnings in 33.61s`.

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check docs/contract-spec.md src/conversation/repository.py src/db/migrations/versions/021_thread_case_links.py src/db/migrations/versions/022_case_working_context.py src/db/models.py src/memory/case_identity.py src/memory/case_working_context.py src/memory/case_working_context_schemas.py src/memory/case_working_context_service.py src/memory/policy.py src/memory/thread_case_links.py tests/db/test_phase44_schema.py tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py tests/memory/test_case_working_context_service.py tests/memory/test_phase44_contract_alignment.py tests/memory/test_thread_case_links.py
```

Result: `All checks passed!`

---

_Reviewed: 2026-07-03T00:24:43Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
