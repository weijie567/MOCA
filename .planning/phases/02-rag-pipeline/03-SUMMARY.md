---
phase: 02-rag-pipeline
plan: "03"
subsystem: rag
tags: [rag, pgvector, ingestion, repositories, markdown, chinese-policy-docs]

requires:
  - phase: 02-rag-pipeline
    provides: Plan 01 policy document/chunk schema and Plan 02 chunker/embedding service
provides:
  - Tenant-scoped policy document and policy chunk repositories
  - Vector similarity search with PolicyDocument metadata joins and eager document loading
  - Policy ingestion service that embeds before DB chunk replacement
  - CLI ingestion script with dry-run chunking and tenant selection
  - Fifteen Chinese Markdown policy knowledge documents
affects: [rag-pipeline, ingestion, retrieval, eval]

tech-stack:
  added: []
  patterns:
    - Repository methods keep tenant_id scoping on policy documents and chunks
    - Ingestion performs network embedding before delete/insert DB mutations
    - Dry-run CLI validates local policy corpus without requiring API keys or DB access

key-files:
  created:
    - src/repositories/policy_document_repo.py
    - src/repositories/policy_chunk_repo.py
    - src/rag/ingestion.py
    - scripts/ingest_policies.py
    - data/policies/*.md
  modified: []

key-decisions:
  - "Use doc_key for idempotent PolicyDocument lookup while using doc.id as the PolicyChunk foreign key."
  - "Keep --dry-run independent from EmbeddingService construction and SessionLocal usage."
  - "Fail one ingestion report if embedding count differs from chunk count instead of partially writing chunks."

patterns-established:
  - "PolicyChunkRepository.search_similar computes similarity as 1 - cosine distance and filters by tenant_id plus optional doc_type/risk_level."
  - "IngestionService commits or rolls back per document so one failed document does not prevent later manifest entries."

requirements-completed: [RAG-01, RAG-02, RAG-03, RAG-04, INFR-06]

duration: 7 min
completed: 2026-05-10
---

# Phase 2 Plan 03: Repositories + Ingestion Service + CLI + Knowledge Documents Summary

**Tenant-scoped RAG repositories, idempotent policy ingestion, dry-run CLI validation, and a 15-document Chinese refund knowledge corpus**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-10T10:42:32Z
- **Completed:** 2026-05-10T10:49:46Z
- **Tasks:** 5/5
- **Files created/modified:** 20

## Accomplishments

- Added `PolicyDocumentRepository` with tenant-scoped `doc_key` lookup and merge-based upsert.
- Added `PolicyChunkRepository` with chunk replacement helpers and pgvector cosine similarity search that joins `PolicyDocument` for `doc_type` filtering.
- Added `IngestionService` with per-document reports, embedding before DB mutation, chunk replacement, commit, and rollback behavior.
- Added `scripts/ingest_policies.py` with an exact 15-document manifest, `--dry-run`, `--dir`, and `--tenant-id`.
- Added 15 Chinese Markdown policy documents covering refund rules, SOPs, compensation, merchant disputes, logistics, high-value, cross-border, digital goods, and escalation flows.

## Task Commits

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 03.1 | Create PolicyDocument repository | `90fc4a6` | `src/repositories/policy_document_repo.py` |
| 03.2 | Create PolicyChunk repository with vector search | `c97277a` | `src/repositories/policy_chunk_repo.py` |
| 03.3 | Create ingestion service | `e240de9` | `src/rag/ingestion.py` |
| 03.4 | Create CLI ingestion script | `1adce5d` | `scripts/ingest_policies.py` |
| 03.5 | Create 15 Chinese knowledge documents | `efa764f` | `data/policies/*.md` |

## Files Created/Modified

- `src/repositories/policy_document_repo.py` - Tenant-scoped lookup and upsert for policy documents.
- `src/repositories/policy_chunk_repo.py` - Tenant-scoped chunk deletion, bulk insert, and vector similarity search.
- `src/rag/ingestion.py` - Document ingestion service with chunking, embedding, DB replacement, and per-document reports.
- `scripts/ingest_policies.py` - CLI for dry-run chunk validation and real pgvector ingestion.
- `data/policies/*.md` - Fifteen manifest-matched Chinese Markdown source documents.
- `.planning/phases/02-rag-pipeline/03-SUMMARY.md` - Plan execution summary.

## Decisions Made

- Used `doc_key` as the stable document lookup key and `doc.id` as the persisted foreign key for chunks, matching Plan 01 schema decisions.
- Kept dry-run local-only: it reads Markdown and calls `chunk_markdown()` but does not instantiate `EmbeddingService` or open a DB session.
- Added an embedding count check before DB writes so a malformed embedding response fails the document report rather than inserting mismatched chunks.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added embedding count mismatch protection**
- **Found during:** Task 03.3
- **Issue:** The plan assumed the embedding service returns one vector per chunk. A short or malformed response would otherwise misalign chunks and vectors during insertion.
- **Fix:** `IngestionService.ingest_document()` now fails the document report before DB mutation when `len(embeddings) != len(chunks)`.
- **Files modified:** `src/rag/ingestion.py`
- **Verification:** `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.rag.ingestion import IngestionService, IngestionReport; print('OK')"`
- **Committed in:** `e240de9`

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** No scope expansion. The fix preserves all-or-nothing per-document ingestion correctness.

## Issues Encountered

- Plain `uv run ...` attempted to use `/Users/ming/.cache/uv`, which is not writable in the sandbox. Verification was rerun with `UV_CACHE_DIR=/tmp/uv-cache`, matching the established project pattern.

## Verification

| Check | Result |
| ----- | ------ |
| `ls data/policies/*.md \| wc -l` | PASS - `15` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --dry-run` | PASS - all 15 documents succeeded with chunk counts |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.rag.ingestion import IngestionService, IngestionReport; print('OK')"` | PASS - `OK` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.repositories.policy_chunk_repo import PolicyChunkRepository; print('OK')"` | PASS - `OK` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/ingest_policies.py --help` | PASS |
| `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/repositories/policy_document_repo.py src/repositories/policy_chunk_repo.py src/rag/ingestion.py scripts/ingest_policies.py` | PASS |
| `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest -q --tb=short` | PASS - 22 passed |

## Acceptance Criteria

- `src/repositories/policy_document_repo.py` exists with `PolicyDocumentRepository`, `get_by_doc_key()`, `PolicyDocument.doc_key`, and `AsyncSession`.
- `src/repositories/policy_chunk_repo.py` exists with `PolicyChunkRepository`, `delete_by_document_id()`, `bulk_insert()`, `search_similar()`, `.join(PolicyDocument...)`, `selectinload(PolicyChunk.document)`, and `1 - PolicyChunk.embedding.cosine_distance(...)`.
- `src/rag/ingestion.py` exists with `IngestionReport`, `IngestionService`, embed-before-delete line order, commit, rollback, `doc_key` lookup, and `doc.id` chunk FK usage.
- `scripts/ingest_policies.py` exists with exactly 15 manifest entries and `--dir`, `--dry-run`, `--tenant-id`, and `asyncio.run(main())`.
- `data/policies/` contains exactly 15 Markdown files matching the manifest; each has at least 3 `##` or `###` headings and Chinese refund-domain terms; `refund_policy.md` has 2801 characters.

## Known Stubs

None.

## Threat Flags

None. The plan intentionally introduces local file reads, DB writes, and embedding calls through the ingestion path; no unplanned network endpoint, auth path, schema change, or trust-boundary surface was added.

## User Setup Required

Set `DASHSCOPE_API_KEY` before running real ingestion without `--dry-run`. Dry-run requires no API key or database connection.

## Next Phase Readiness

Ready for Plan 04 retrieval work. The corpus can be chunked deterministically, the ingestion path can populate `policy_documents` and `policy_chunks`, and vector search already returns eager-loaded policy document metadata for citation construction.

## Self-Check: PASSED

- Verified all created Plan 03 files exist: repositories, ingestion service, CLI, summary, and 15 policy Markdown files.
- Verified task commits `90fc4a6`, `c97277a`, `e240de9`, `1adce5d`, and `efa764f` are present in git history.
- Verified no missing file or missing commit entries were reported by the self-check commands.

---
*Phase: 02-rag-pipeline*
*Completed: 2026-05-10*
