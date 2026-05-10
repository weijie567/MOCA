---
phase: 02-rag-pipeline
plan: "01"
subsystem: database
tags: [rag, pgvector, alembic, pydantic, openai]

requires:
  - phase: 01-foundation
    provides: PostgreSQL schema, SQLAlchemy models, Alembic baseline, API schema conventions
provides:
  - RAG schema foundation with 1024-dimension policy chunk embeddings
  - Tenant-scoped policy document semantic keys
  - Citation and vector search indexes for retrieval
  - Pydantic schemas for retrieval evidence, citation validation, and search requests
affects: [rag-pipeline, policy-documents, policy-chunks, retrieval-api]

tech-stack:
  added: [openai]
  patterns: [tenant-scoped semantic document keys, pgvector HNSW cosine index, ApiResponse-wrapped RAG results]

key-files:
  created:
    - src/db/migrations/versions/002_rag_pipeline.py
    - src/rag/__init__.py
    - src/rag/schemas.py
  modified:
    - pyproject.toml
    - uv.lock
    - src/db/models.py

key-decisions:
  - "Use doc_key as the policy document semantic identifier instead of exposing doc_id in RAG schemas."
  - "Standardize policy chunk embeddings on vector(1024) to match the planned embedding model."
  - "Use ApiResponse[RetrievalResult] composition rather than a custom SearchResponse wrapper."

patterns-established:
  - "RAG API schemas live under src/rag and use Pydantic Field validation for bounded user inputs."
  - "Policy document uniqueness is tenant-scoped by tenant_id plus doc_key."

requirements-completed: [RAG-02, RAG-03]

duration: 6 min
completed: 2026-05-10
---

# Phase 2 Plan 01: Schema Migration + Dependencies + Pydantic Schemas Summary

**RAG database and schema foundation with OpenAI SDK dependency, tenant-scoped doc keys, 1024-dimension pgvector embeddings, and validated retrieval schemas**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-10T10:32:07Z
- **Completed:** 2026-05-10T10:38:00Z
- **Tasks:** 4/4
- **Files created/modified:** 9

## Accomplishments

- Added `openai>=1.30` and refreshed `uv.lock` with the resolved OpenAI SDK package set.
- Added `PolicyDocument.doc_key`, tenant-scoped uniqueness, `PolicyChunk.chunk_id` indexing, and `Vector(1024)` embeddings.
- Created Alembic revision `002_rag_pipeline` with doc_key, citation index, vector dimension, and HNSW cosine index changes plus downgrade coverage.
- Added RAG Pydantic schemas for evidence, retrieval results, citation validation, and search requests without a custom `SearchResponse`.

## Task Commits

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 01.1 | Add openai dependency | `d1755d9` | `pyproject.toml`, `uv.lock` |
| 01.2 | Add doc_key column to PolicyDocument model | `f3e6d8a` | `src/db/models.py` |
| 01.3 | Create Alembic migration for schema changes | `7e67b32` | `src/db/migrations/versions/002_rag_pipeline.py` |
| 01.4 | Create RAG Pydantic schemas | `6854f58` | `src/rag/__init__.py`, `src/rag/schemas.py` |
| Fix | Keep migration lint clean | `47d87ba` | `src/db/migrations/versions/002_rag_pipeline.py` |

## Files Created/Modified

- `pyproject.toml` - Adds `openai>=1.30`.
- `uv.lock` - Locks OpenAI SDK and transitive dependencies.
- `src/db/models.py` - Adds doc_key uniqueness, chunk citation index, and 1024-dimensional embeddings.
- `src/db/migrations/versions/002_rag_pipeline.py` - Applies and downgrades the RAG schema changes.
- `src/rag/__init__.py` - Creates the RAG package.
- `src/rag/schemas.py` - Defines RAG request and result schemas.
- `.planning/phases/02-rag-pipeline/01-SUMMARY.md` - Documents Plan 01 execution.
- `.planning/STATE.md` - Updates plan progress based on completed summaries.
- `.planning/REQUIREMENTS.md` - Marks `RAG-02` and `RAG-03` complete.

## Decisions Made

- Used `doc_key` as the semantic policy document identifier in schemas and model constraints, matching the plan and avoiding UUID leakage in evidence items.
- Kept search responses as `ApiResponse(success=True, data=RetrievalResult(...))`; no `SearchResponse` wrapper was introduced.
- Removed an unused migration import after lint verification while preserving the planned migration behavior.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused migration import**
- **Found during:** Plan-level verification
- **Issue:** `src/db/migrations/versions/002_rag_pipeline.py` imported `Vector` but never used it, causing targeted ruff verification to fail with `F401`.
- **Fix:** Removed the unused import.
- **Files modified:** `src/db/migrations/versions/002_rag_pipeline.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev ruff check src/db/models.py src/db/migrations/versions/002_rag_pipeline.py src/rag/schemas.py`
- **Committed in:** `47d87ba`

**2. [Rule 1 - Bug] Corrected SDK metadata formatting**
- **Found during:** Plan metadata updates
- **Issue:** `gsd-sdk query requirements.mark-complete` marked `RAG-02` and `RAG-03` complete but split the bold requirement IDs across lines. `state.update-progress` also changed `STATE.md` status to `unknown`.
- **Fix:** Restored single-line requirement checkbox formatting, marked the traceability rows complete, and restored `status: in_progress`.
- **Files modified:** `.planning/REQUIREMENTS.md`, `.planning/STATE.md`
- **Verification:** `rg -n 'RAG-02|RAG-03|status:|completed_plans|percent' .planning/REQUIREMENTS.md .planning/STATE.md`
- **Committed in:** final metadata commit

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** No behavioral scope change. The fixes keep the migration lint-clean and planning metadata well-formed while preserving the required doc_key, vector dimension, citation index, and HNSW index operations.

## Issues Encountered

- Initial `uv lock` could not write to the default home cache under sandbox restrictions. Reran with `UV_CACHE_DIR=/tmp/uv-cache`.
- Dependency resolution required network access under the restricted sandbox. The escalated `UV_CACHE_DIR=/tmp/uv-cache uv lock` run succeeded and updated `uv.lock`.
- `gsd-sdk query state.advance-plan` could not parse a current-plan counter from this project's `STATE.md`, so no manual plan-counter field was invented.

## Verification

| Check | Result |
| ----- | ------ |
| `UV_CACHE_DIR=/tmp/uv-cache uv lock` | PASS - resolved 49 packages |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.rag.schemas import EvidenceItem, RetrievalResult, CitationValidation, SearchRequest; print('OK')"` | PASS - `OK` |
| `grep -c "Vector(1024)" src/db/models.py` | PASS - `1` |
| `grep -c "Vector(1536)" src/db/models.py` | PASS - `0` |
| `grep "doc_key" src/db/models.py` | PASS - column and tenant-scoped unique constraint present |
| Migration down revision check | PASS - `down_revision: str \| None = "001_initial_schema"` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev ruff check src/db/models.py src/db/migrations/versions/002_rag_pipeline.py src/rag/schemas.py` | PASS |
| `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest -q --tb=short` | PASS - 22 passed |

## Known Stubs

None. The `server_default=""` in the migration is a compatibility default for adding a non-null column, not a runtime stub or UI placeholder.

## Threat Flags

None. This plan changes database schema and local Pydantic validation only; it introduces no new network endpoints, auth paths, file access paths, or trust-boundary behavior beyond the planned RAG schema surface.

## User Setup Required

None - no manual setup required for this plan.

## Next Phase Readiness

Ready for downstream RAG pipeline plans to chunk documents, generate 1024-dimensional embeddings, persist policy chunks, and return `ApiResponse`-wrapped `RetrievalResult` payloads using `doc_key` citations.

## Self-Check: PASSED

- Verified all created/modified Plan 01 files exist.
- Verified commits `d1755d9`, `f3e6d8a`, `7e67b32`, `6854f58`, and `47d87ba` are present in git history.
- Verified no missing file or missing commit entries were reported by the self-check commands.

---
*Phase: 02-rag-pipeline*
*Completed: 2026-05-10*
