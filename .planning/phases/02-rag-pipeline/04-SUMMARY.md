---
phase: 02-rag-pipeline
plan: "04"
subsystem: rag-api
tags: [rag, retrieval, citation-validation, fastapi, oauth2-scopes, pytest]
requires:
  - phase: 02-rag-pipeline
    provides: policy document ingestion, chunk repository, embedding service, pgvector search
provides:
  - tenant-scoped retriever with confidence scoring
  - citation validator for retrieved chunk IDs
  - authenticated search API endpoint
  - mocked retriever and citation validator tests
affects: [phase-03-langgraph-core, phase-06-evaluation-polish]
tech-stack:
  added: []
  patterns: [repository-backed retrieval service, deterministic mocked embedding tests, ApiResponse router contract]
key-files:
  created:
    - src/rag/retriever.py
    - src/rag/citation_validator.py
    - src/api/routers/search.py
    - tests/test_retriever.py
  modified:
    - src/api/main.py
    - src/auth/jwt.py
    - src/auth/permissions.py
key-decisions:
  - "Retriever emits structured evidence and fallback state only; answer generation remains downstream."
  - "Citation validation is deterministic field matching against retrieved chunk IDs, with no LLM judge."
  - "knowledge:read is granted to existing roles so the protected search endpoint is reachable after login."
patterns-established:
  - "Retrieval services depend on repository and embedder objects for testability."
  - "Search APIs return ApiResponse with request trace_id and rely on Security-scoped current users."
requirements-completed: [RAG-04, RAG-06, RAG-07, EVAL-02]
duration: 4min
completed: 2026-05-10
---

# Phase 2 Plan 04: Retriever + Citation Validator + Search Endpoint Summary

**Tenant-scoped RAG retrieval with confidence fallback, deterministic citation validation, and an authenticated FastAPI search endpoint**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-10T10:53:26Z
- **Completed:** 2026-05-10T10:57:27Z
- **Tasks:** 4/4
- **Files modified:** 7

## Accomplishments

- Added `Retriever` with hard similarity filtering, strong/partial/no-evidence status, best-score propagation, and the required Chinese fallback message.
- Added `validate_citations` to reject missing citations and chunk IDs not present in retrieval evidence.
- Added `/api/v1/search` registration using `Security(get_current_user, scopes=["knowledge:read"])`, `get_session`, tenant scoping via `user.tenant_id`, and `ApiResponse` with `trace_id`.
- Added 9 mocked unit tests covering retrieval confidence states, doc_key evidence metadata, citation validation, and tenant isolation.

## Task Commits

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 04.1 | Implement retriever with confidence scoring | `0d3d030` | `src/rag/retriever.py` |
| 04.2 | Implement citation validator | `3756166` | `src/rag/citation_validator.py` |
| 04.3 | Create search API endpoint matching project conventions | `0fab647` | `src/api/routers/search.py`, `src/api/main.py`, `src/auth/jwt.py`, `src/auth/permissions.py` |
| 04.4 | Unit tests for retriever and citation validator | `5fc5aac` | `tests/test_retriever.py` |

## Files Created/Modified

- `src/rag/retriever.py` - Retrieval service that embeds a query, calls `PolicyChunkRepository.search_similar`, maps eager-loaded document metadata into evidence, and assigns retrieval confidence status.
- `src/rag/citation_validator.py` - Deterministic citation validator for retrieved chunk IDs.
- `src/api/routers/search.py` - Authenticated knowledge-base search endpoint.
- `src/api/main.py` - Search router registration under `settings.api_v1_prefix`.
- `src/auth/jwt.py` - Added `knowledge:read` to role-issued JWT scopes.
- `src/auth/permissions.py` - Advertised the `knowledge:read` OAuth2 scope.
- `tests/test_retriever.py` - Unit tests with mocked embedder and repository dependencies.

## Decisions Made

- Kept retrieval answer-free: the retriever returns evidence, scores, status, and fallback text only.
- Used stable `chunk.document.doc_key` in evidence items rather than the UUID foreign key.
- Added `knowledge:read` to existing roles as a correctness requirement because the endpoint uses that required scope.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added usable `knowledge:read` scope**
- **Found during:** Task 04.3 (Create search API endpoint matching project conventions)
- **Issue:** The plan required `Security(get_current_user, scopes=["knowledge:read"])`, but existing login tokens never issued `knowledge:read` and OAuth2 scopes did not advertise it. The endpoint would return 403 for normal authenticated users.
- **Fix:** Added `knowledge:read` to role scopes in `src/auth/jwt.py` and OAuth2 scope metadata in `src/auth/permissions.py`.
- **Files modified:** `src/auth/jwt.py`, `src/auth/permissions.py`
- **Verification:** Full pytest suite passed; search router import passed.
- **Committed in:** `0fab647`

---

**Total deviations:** 1 auto-fixed (1 missing critical functionality)
**Impact on plan:** Required for the planned secured endpoint to be usable. No architectural changes.

## Verification

| Check | Result |
| ----- | ------ |
| `uv run pytest tests/test_retriever.py -q` | Initial sandbox cache failure at `/Users/ming/.cache/uv`; rerun with writable cache passed |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_retriever.py -q` | PASS - 9 passed |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.rag.retriever import Retriever; print('OK')"` | PASS - OK |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.rag.citation_validator import validate_citations; print('OK')"` | PASS - OK |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.api.routers.search import router; print('OK')"` | PASS - OK |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` | PASS - 31 passed |
| `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/rag/retriever.py src/rag/citation_validator.py src/api/routers/search.py src/api/main.py src/auth/jwt.py src/auth/permissions.py tests/test_retriever.py` | PASS - All checks passed |

## Acceptance Criteria

- Retriever file exists and contains `class Retriever`, `STRONG_EVIDENCE_THRESHOLD = 0.70`, `MIN_SIMILARITY_THRESHOLD = 0.55`, `chunk.document.doc_key`, the required fallback text, and all three retrieval states.
- Citation validator file exists, checks empty citation lists, checks citations against retrieval evidence, returns `CitationValidation`, and contains no LLM judge logic.
- Search router exists, imports `ApiResponse`, `get_current_user`, and `get_session`, uses `Security(get_current_user, scopes=["knowledge:read"])`, scopes retrieval to `user.tenant_id`, returns `ApiResponse(... trace_id=request.state.trace_id)`, and is registered at `settings.api_v1_prefix/search`.
- Retriever tests exist, contain 9 tests, use `AsyncMock`, cover all retrieval states, cover citation valid/invalid/empty cases, and pass.

## Known Stubs

None. Stub scan found only intentional empty invalid-citation lists and test assertions; no UI-facing placeholder or unwired mock data was introduced.

## Threat Flags

| Flag | File | Description |
| ---- | ---- | ----------- |
| threat_flag: network_endpoint | `src/api/routers/search.py` | New authenticated POST search endpoint accepts user query text and returns policy evidence scoped to `user.tenant_id`. |
| threat_flag: auth_scope | `src/auth/jwt.py`, `src/auth/permissions.py` | Added `knowledge:read` to role-issued JWT scopes and OAuth2 scope metadata. |

## Issues Encountered

- The first exact `uv run pytest tests/test_retriever.py -q` attempt failed because `uv` could not write to `/Users/ming/.cache/uv` under the sandbox. All verification commands were rerun successfully with `UV_CACHE_DIR=/tmp/uv-cache`.

## User Setup Required

None - no new external service configuration required. Unit tests use mocked embeddings and do not call DashScope.

## Next Phase Readiness

Plan 04 exposes retrieval, citation validation, and a secured API surface for downstream LangGraph work. Plan 05 can build the RAG eval baseline against this retriever and search contract.

## Self-Check: PASSED

- Created files exist: `src/rag/retriever.py`, `src/rag/citation_validator.py`, `src/api/routers/search.py`, `tests/test_retriever.py`, `.planning/phases/02-rag-pipeline/04-SUMMARY.md`.
- Task commits exist: `0d3d030`, `3756166`, `0fab647`, `5fc5aac`.
- Verification commands passed with writable uv cache.

---
*Phase: 02-rag-pipeline*
*Completed: 2026-05-10*
