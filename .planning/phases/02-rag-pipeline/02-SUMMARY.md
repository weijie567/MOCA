---
phase: 02-rag-pipeline
plan: "02"
subsystem: rag
tags: [rag, markdown, chunking, embeddings, dashscope, openai]

requires:
  - phase: 01-foundation
    provides: Python project structure, uv/pytest tooling, and base package layout
provides:
  - Heading-based Markdown policy chunker with stable doc_key chunk IDs
  - DashScope text-embedding-v4 service wrapper with lazy API key resolution
  - Focused chunker unit tests covering Chinese policy text and oversized sections
affects: [rag-pipeline, ingestion, retrieval, eval]

tech-stack:
  added: []
  patterns:
    - Dataclass chunk results for deterministic ingestion handoff
    - Async OpenAI-compatible DashScope embedding wrapper

key-files:
  created:
    - src/rag/chunker.py
    - src/rag/embedder.py
    - tests/test_chunker.py
  modified: []

key-decisions:
  - "Used doc_key-based sequential chunk IDs exactly as planned to keep eval expected_chunk_ids stable."
  - "Kept DashScope client construction lazy so imports and service construction do not require DASHSCOPE_API_KEY."
  - "Did not create src/rag/schemas.py because Plan 02 does not consume schema types and Plan 01 owns that dependency."

patterns-established:
  - "Oversized sections split within their original heading only, with overlap applied only between same-section parts."
  - "Embedding batches are capped with min(batch_size, 10) to respect DashScope's request limit."

requirements-completed: [RAG-01, RAG-02, RAG-03, INFR-06]

duration: 5 min
completed: 2026-05-10
---

# Phase 2 Plan 02: Markdown Chunker + Embedding Service Summary

**Heading-aware Chinese policy chunking with deterministic doc_key IDs and a lazy DashScope text-embedding-v4 wrapper**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-10T10:32:10Z
- **Completed:** 2026-05-10T10:37:31Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `chunk_markdown()` and `ChunkResult` for `##` / `###` Markdown policy sections.
- Implemented oversized section splitting with Chinese sentence-boundary preference, fallback boundaries, max length enforcement, and same-section overlap.
- Added `EmbeddingService` using `openai.AsyncOpenAI` against DashScope's OpenAI-compatible endpoint with lazy key lookup, batch clamping, and exponential retry backoff.
- Added 10 pytest cases covering stable IDs, intro sections, empty sections, Chinese character limits, sentence-boundary splitting, overlap, and no-punctuation fallback.

## Task Commits

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 02.1 | Implement Markdown heading-based chunker | `df8423d` | `src/rag/chunker.py` |
| 02.2 | Implement DashScope embedding service with lazy init | `44c83f9` | `src/rag/embedder.py` |
| 02.3 | Unit tests for chunker | `4327364` | `tests/test_chunker.py` |

## Files Created/Modified

- `src/rag/chunker.py` - Heading-based Markdown chunker and `ChunkResult` dataclass.
- `src/rag/embedder.py` - DashScope embedding service wrapper using the OpenAI-compatible async client.
- `tests/test_chunker.py` - Focused unit tests for Plan 02 chunking behavior.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_chunker.py -q` - PASS, 10 passed.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.rag.chunker import chunk_markdown, ChunkResult; print('OK')"` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from src.rag.embedder import EmbeddingService; s = EmbeddingService(); print('OK')"` - PASS.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/rag/chunker.py src/rag/embedder.py tests/test_chunker.py` - PASS.

## Acceptance Criteria

- `src/rag/chunker.py` exists with `@dataclass`, `ChunkResult`, `doc_key: str`, and `def chunk_markdown(`.
- Chunk IDs use `f"{doc_key}_..."`, oversized sections use `_part_`, and default limits are `max_chars=1200`, `target_chars=800`, `overlap_chars=100`.
- Sentence-boundary splitting includes Chinese punctuation handling.
- `src/rag/embedder.py` exists with `EmbeddingService`, `_get_client()`, `os.environ.get("DASHSCOPE_API_KEY")`, `min(batch_size, 10)`, `dimensions=1024`, DashScope base URL, retry backoff, and `max_retries=3`.
- `EmbeddingService()` construction succeeds without `DASHSCOPE_API_KEY`.
- `tests/test_chunker.py` has 10 tests importing from `src.rag.chunker` and using Chinese refund-domain text.

## Decisions Made

- Followed the plan's hand-rolled regex chunker approach rather than adding a Markdown parsing dependency.
- Preserved Plan 01 ownership of `src/rag/schemas.py`; when it was initially missing, no local stub was needed because Plan 02 files do not import it.
- Treated shared planning state and roadmap files as orchestrator-owned because Plan 01 may be executing in parallel.

## Deviations from Plan

### Auto-fixed Issues

None.

### Coordination Deviations

**1. Missing Plan 01 schema dependency at task start**
- **Found during:** Task 02.1 and Task 02.2 read-first checks
- **Issue:** `src/rag/schemas.py` was not present when Plan 02 started.
- **Resolution:** No stub was created because Plan 02 does not require schema imports. Later checks showed `src/rag/schemas.py` had appeared from parallel Plan 01 work.
- **Files modified:** None.
- **Impact:** No runtime or API impact for Plan 02.

**Total deviations:** 0 auto-fixed; 1 coordination note.
**Impact on plan:** Plan goal was achieved without broadening Plan 02 ownership.

## Issues Encountered

- Initial `uv run` failed inside the sandbox because the default uv cache under `/Users/ming/.cache/uv` was not writable. Resolved by using `UV_CACHE_DIR=/tmp/uv-cache`.
- Downloading the newly required OpenAI dependency needed approved network access. After approval, dependency resolution and tests completed successfully.

## Known Stubs

None.

## Threat Flags

None. The only external network surface is the planned DashScope embedding client, and client construction is lazy with explicit API key resolution at call time.

## User Setup Required

Set `DASHSCOPE_API_KEY` before calling `EmbeddingService.embed_documents()` or `EmbeddingService.embed_query()` against the real DashScope API.

## Next Phase Readiness

Plan 03 can build ingestion on top of `chunk_markdown()` and `EmbeddingService`. The chunker returns deterministic IDs and stable section metadata suitable for idempotent document ingestion and RAG eval references.

## Self-Check: PASSED

- Created files verified on disk: `src/rag/chunker.py`, `src/rag/embedder.py`, `tests/test_chunker.py`, `.planning/phases/02-rag-pipeline/02-SUMMARY.md`.
- Task commits verified in git history: `df8423d`, `44c83f9`, `4327364`.
- Final working tree check before metadata commit showed only `02-SUMMARY.md` pending.

---
*Phase: 02-rag-pipeline*
*Completed: 2026-05-10*
