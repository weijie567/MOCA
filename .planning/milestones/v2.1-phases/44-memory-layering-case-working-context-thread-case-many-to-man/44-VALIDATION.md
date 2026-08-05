---
phase: 44
slug: memory-layering-case-working-context-thread-case-many-to-man
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-08
updated: 2026-07-08
---

# Phase 44 - Nyquist Validation

This artifact closes the missing Nyquist validation record for Phase 44 / MEM-01 / MEM-02.

Phase 44 delivered durable Case Working Context storage and additive thread-case many-to-many linkage. It intentionally deferred graph run-completion auto-update/read-active lifecycle wiring to Phase 45; that lifecycle defer is named in `44-VERIFICATION.md` and is not a Phase 44 validation gap.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio via `pyproject.toml` |
| **Config file** | `pyproject.toml` |
| **Phase 44 command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/db/test_phase44_schema.py tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py tests/memory/test_thread_case_links.py tests/memory/test_case_working_context_service.py tests/memory/test_phase44_contract_alignment.py -q` |
| **Alembic head command** | `UV_CACHE_DIR=/tmp/uv-cache uv run alembic heads` |
| **Lint command** | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check docs/contract-spec.md src/conversation/repository.py src/db/migrations/versions/021_thread_case_links.py src/db/migrations/versions/022_case_working_context.py src/db/models.py src/memory/case_identity.py src/memory/case_working_context.py src/memory/case_working_context_schemas.py src/memory/case_working_context_service.py src/memory/policy.py src/memory/thread_case_links.py tests/db/test_phase44_schema.py tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py tests/memory/test_case_working_context_service.py tests/memory/test_phase44_contract_alignment.py tests/memory/test_thread_case_links.py` |

## Requirement-To-Test Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 44-01-01 | 01 | 1 | MEM-01, MEM-02 | T-44-01 | Migrations 021/022 are linear and create `thread_case_links`, `case_working_contexts`, and `case_working_context_revisions`. | DB schema | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/db/test_phase44_schema.py -q` | yes | passed |
| 44-01-02 | 01 | 1 | MEM-01, MEM-02 | T-44-02 | Alembic has a single Phase 44 head after CWC migrations. | migration metadata | `UV_CACHE_DIR=/tmp/uv-cache uv run alembic heads` | yes | passed: `022_case_working_context (head)` |
| 44-02-01 | 02 | 2 | MEM-01 | T-44-03 | Case identity resolution and CWC repository read/write use canonical `refund_cases.id`, versioning, revisions, trusted provenance, and contextual-only authority. | repository / schema | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_identity.py tests/memory/test_case_working_context_repo.py -q` | yes | passed |
| 44-03-01 | 03 | 3 | MEM-02 | T-44-04 | `thread_case_links` supports explicit active dedup and many-to-many thread/case reads. | repository / lifecycle | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_thread_case_links.py -q` | yes | passed |
| 44-03-02 | 03 | 3 | MEM-01 | T-44-05 | Case Working Context service writes audit events, blocks sensitive/prohibited PII classifications, and preserves tenant/run provenance. | service / audit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_working_context_service.py -q` | yes | passed |
| 44-04-01 | 04 | 4 | MEM-01, MEM-02 | T-44-06 | Contract spec aligns with CWC and additive thread-case many-to-many red lines; `case_memories` / `long_term_memories` are not renamed. | contract / static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase44_contract_alignment.py -q` | yes | passed |
| 44-04-02 | 04 | 4 | MEM-01, MEM-02 | T-44-07 | Phase 45 owns active CWC lifecycle wiring; Phase 44 remains storage/service foundation only. | boundary / defer | `rg -n "Phase 45|lifecycle|defer|auto-update|read-active" .planning/phases/44-memory-layering-case-working-context-thread-case-many-to-man/44-VERIFICATION.md` | yes | passed |

## Closeout Evidence

- `44-VERIFICATION.md` records 15/15 must-haves verified.
- `44-VERIFICATION.md` records the Phase 44 DB-backed pytest result as `51 passed, 5 warnings`.
- `44-VERIFICATION.md` records `UV_CACHE_DIR=/tmp/uv-cache uv run alembic heads` -> `022_case_working_context (head)`.
- `44-REVIEW.md` records a clean deep review with 0 findings after review fixes.
- `44-REVIEW-ADJUDICATION.md` records the pre-implementation plan-review blocker and warning adjudication baseline.
- The named Phase 45 lifecycle defer is preserved and later addressed by Phase 45, not silently claimed by Phase 44.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | MEM-01, MEM-02 | Phase 44 behavior is backend schema/repository/service/contract behavior with automated DB-backed validation and clean review evidence. | N/A |

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Wave 0 covers CWC DDL, thread-case links, repository/service behavior, contract alignment, review evidence, and Alembic head.
- [x] Phase 45 lifecycle defer is explicit and not counted as a Phase 44 failure.
- [x] No watch-mode flags.
- [x] Newly recorded command evidence uses MOCA-approved entrypoints.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** complete.
