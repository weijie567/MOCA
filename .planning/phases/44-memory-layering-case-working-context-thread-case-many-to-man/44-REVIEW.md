---
phase: 44-memory-layering-case-working-context-thread-case-many-to-man
reviewed: 2026-07-02T18:59:34Z
depth: deep
files_reviewed: 16
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
  - src/memory/thread_case_links.py
  - tests/db/test_phase44_schema.py
  - tests/memory/test_case_identity.py
  - tests/memory/test_case_working_context_repo.py
  - tests/memory/test_thread_case_links.py
  - tests/memory/test_case_working_context_service.py
  - tests/memory/test_phase44_contract_alignment.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 44: Final Post-Fix Re-Review

**Reviewed:** 2026-07-02T18:59:34Z
**Depth:** deep
**Files Reviewed:** 16
**Status:** clean

## Findings

No findings.

## Verified Prior Fixes

- CWC writes now enforce tenant-owned cases through service and repository validation before persistence (`src/memory/case_working_context_service.py:59`, `src/memory/case_working_context.py:67`) and composite case/tenant constraints (`src/db/models.py:586`, `src/db/migrations/versions/022_case_working_context.py:128`).
- Thread-case links now validate tenant-owned thread, case, and run ids (`src/memory/thread_case_links.py:37`, `src/memory/thread_case_links.py:123`, `src/memory/thread_case_links.py:143`) with tenant composite FKs in schema (`src/db/models.py:1261`, `src/db/migrations/versions/021_thread_case_links.py:70`).
- `updated_by_run_id` spoofing through the CWC service is rejected before the isolated write opens, and the trusted run id is applied to the write candidate (`src/memory/case_working_context_service.py:55`, `src/memory/case_working_context_service.py:162`, `src/memory/case_working_context_service.py:171`).
- CWC evidence refs are typed contextual pointers rather than policy `EvidenceRefV1` payloads (`src/memory/case_working_context_schemas.py:51`, `tests/memory/test_case_working_context_repo.py:228`).
- Concurrent first thread-case writes are idempotent via advisory locking plus active-link recheck (`src/memory/thread_case_links.py:32`, `src/memory/thread_case_links.py:43`, `tests/memory/test_thread_case_links.py:295`).
- Contract storage/audit constraints include `case_working_context` and CWC tables (`docs/contract-spec.md:1595`, `docs/contract-spec.md:2517`, `src/db/models.py:778`, `src/db/migrations/versions/022_case_working_context.py:199`).
- Unknown UUID case refs report `input_form="uuid"` (`src/memory/case_identity.py:33`, `src/memory/case_identity.py:44`, `tests/memory/test_case_identity.py:66`).
- Caller-controlled CWC run/case source-ref discriminators are normalized to trusted run/case before hashing, audit, and persistence (`src/memory/case_working_context_schemas.py:104`, `src/memory/case_working_context_service.py:69`, `src/memory/case_working_context_service.py:71`, `tests/memory/test_case_working_context_service.py:304`).
- Direct CWC repository writes reject cross-tenant `updated_by_run_id` (`src/memory/case_working_context.py:68`, `src/memory/case_working_context.py:167`, `tests/memory/test_case_working_context_repo.py:375`).
- Staff-manual CWC revisions preserve `edit_source="staff_manual"` from stored source provenance instead of inferring `run_auto` from a non-null run id (`src/memory/case_working_context.py:116`, `src/memory/case_working_context.py:205`, `tests/memory/test_case_working_context_service.py:365`).

## Residual Risks / Test Gaps

- Phase 44 still relies on upstream producer discipline and `pii_classification` for free-text CWC fields. The schema blocks policy-evidence-shaped CWC evidence refs and the service blocks sensitive/prohibited classifications, but there is no semantic scanner for raw policy body text or sensitive PII in arbitrary strings.
- `source_type="staff_manual"` is preserved when supplied with a tenant-valid run id. This review verifies provenance preservation, not caller authorization for manual edits.
- Raw SQL writes can bypass repository/service tenant checks for run ownership because `updated_by_run_id` remains a simple FK to `agent_runs.id`; covered application paths reject cross-tenant runs.

## Tests Run

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/db/test_phase44_schema.py tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py tests/memory/test_phase44_contract_alignment.py
```

Result: `48 passed, 5 warnings in 30.83s`.

---

_Reviewed: 2026-07-02T18:59:34Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
