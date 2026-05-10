---
phase: 2
plan_id: "02"
title: "Markdown Chunker + Embedding Service"
wave: 1
depends_on: []
files_modified:
  - src/rag/chunker.py
  - src/rag/embedder.py
  - tests/test_chunker.py
autonomous: true
requirements: [RAG-01, RAG-02, RAG-03, INFR-06]
---

# Plan 02: Markdown Chunker + Embedding Service

<objective>
Implement the heading-based Markdown chunker with stable chunk_id generation and the DashScope embedding service wrapper with lazy API key resolution, batch processing, and retry logic.
</objective>

<tasks>

<task id="02.1">
<title>Implement Markdown heading-based chunker</title>
<read_first>
- src/rag/schemas.py
- .planning/phases/02-rag-pipeline/02-CONTEXT.md (D-02 chunking strategy, D-07 stable IDs)
- .planning/phases/02-rag-pipeline/02-RESEARCH.md (Markdown Heading Chunker code example)
</read_first>
<action>
Create `src/rag/chunker.py` implementing:

1. `ChunkResult` dataclass:
```python
@dataclass
class ChunkResult:
    doc_key: str       # semantic stable ID (e.g., "refund_policy")
    chunk_id: str      # stable: f"{doc_key}_{idx:03d}" or f"{doc_key}_{idx:03d}_part_{part_idx}"
    section: str       # heading text
    content: str       # chunk body text
    chunk_index: int   # sequential index within document
    part_index: int | None = None  # sub-part index for oversized sections
```

2. `chunk_markdown(content: str, doc_key: str, max_chars: int = 1200, target_chars: int = 800, overlap_chars: int = 100) -> list[ChunkResult]`

Logic:
- Split content at `^#{2,3}\s` boundaries (re.MULTILINE)
- For each section: extract heading text as `section`
- If section body <= max_chars: single chunk with `chunk_id = f"{doc_key}_{idx:03d}"`
- If section body > max_chars: secondary split into parts of ~target_chars with overlap_chars overlap. Each part gets `chunk_id = f"{doc_key}_{idx:03d}_part_{part_idx}"`
- Content before first heading becomes section "intro" (if non-empty)
- Use `len(text)` for Chinese character counting (NOT token counting)
- Secondary split breaks at nearest sentence boundary: `。` `！` `？` `\n`
- If no sentence boundary found within range, break at nearest space or comma `，`

Constraints from CONTEXT.md D-02:
- Target chunk size: 400-800 Chinese characters
- Max chunk size: 1200-1500 Chinese characters
- Overlap: 80-150 characters (only within same section)
- Never mix unrelated rules in one chunk
</action>
<acceptance_criteria>
- src/rag/chunker.py exists
- File contains `def chunk_markdown(`
- File contains `@dataclass` and `class ChunkResult`
- ChunkResult has `doc_key: str` field (not doc_id)
- chunk_id format uses doc_key: grep for `f"{doc_key}_`
- Secondary split logic exists (grep for `_part_`)
- overlap_chars parameter with default 100 (within 80-150 range)
- max_chars parameter with default 1200
- target_chars parameter with default 800
- Sentence boundary splitting (grep for `。` or sentence boundary logic)
</acceptance_criteria>
</task>

<task id="02.2">
<title>Implement DashScope embedding service with lazy init</title>
<read_first>
- src/rag/schemas.py
- .planning/phases/02-rag-pipeline/02-CONTEXT.md (D-03, D-04 embedding config)
- .planning/phases/02-rag-pipeline/02-RESEARCH.md (Embedding Service Pattern)
</read_first>
<action>
Create `src/rag/embedder.py`:

```python
from __future__ import annotations

import asyncio
import os

from openai import AsyncOpenAI


class EmbeddingService:
    """DashScope text-embedding-v4 wrapper via OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        model: str = "text-embedding-v4",
        dimensions: int = 1024,
        batch_size: int = 10,
        max_retries: int = 3,
    ):
        # Lazy: store config but don't create client until first call
        self._api_key = api_key
        self._base_url = base_url
        self.model = model
        self.dimensions = dimensions
        self.batch_size = min(batch_size, 10)  # DashScope hard limit
        self.max_retries = max_retries
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            api_key = self._api_key or os.environ.get("DASHSCOPE_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "DASHSCOPE_API_KEY not set. Provide api_key parameter or set the environment variable."
                )
            self._client = AsyncOpenAI(api_key=api_key, base_url=self._base_url)
        return self._client

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batches. Raises on any failure (no silent skip)."""
        results: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            embeddings = await self._embed_with_retry(batch)
            results.extend(embeddings)
        return results

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        result = await self._embed_with_retry([text])
        return result[0]

    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        for attempt in range(self.max_retries):
            try:
                response = await client.embeddings.create(
                    model=self.model,
                    input=texts,
                    dimensions=self.dimensions,
                )
                return [item.embedding for item in response.data]
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError("unreachable")
```

Key design decisions addressing review feedback:
- Lazy client creation: `_get_client()` only called on first actual API call
- `os.environ.get()` (not `os.environ[]`) — won't crash on import/construction
- Clear error message when key is missing at call time
- `batch_size` clamped to max 10 regardless of input
</action>
<acceptance_criteria>
- src/rag/embedder.py exists
- File contains `class EmbeddingService`
- File contains `_get_client` method (lazy initialization)
- File uses `os.environ.get("DASHSCOPE_API_KEY")` (not `os.environ["DASHSCOPE_API_KEY"]`)
- File contains `min(batch_size, 10)` or equivalent clamping
- File contains `dimensions: int = 1024`
- File contains `"https://dashscope.aliyuncs.com/compatible-mode/v1"`
- File contains retry logic with `2 ** attempt`
- File contains `max_retries: int = 3`
- Construction without API key does NOT raise (lazy)
</acceptance_criteria>
</task>

<task id="02.3">
<title>Unit tests for chunker</title>
<read_first>
- src/rag/chunker.py
- tests/ (existing test patterns, conftest.py)
</read_first>
<action>
Create `tests/test_chunker.py` with tests:

1. `test_basic_heading_split` — Markdown with 3 ## sections produces 3 chunks with correct section titles
2. `test_stable_chunk_ids` — Same input always produces same chunk_ids; format is `{doc_key}_{idx:03d}`
3. `test_oversized_section_split` — Section with 2000 chars splits into multiple parts with `_part_` suffix
4. `test_overlap_within_section` — Parts from oversized section have overlapping content (80-150 chars)
5. `test_intro_section` — Content before first heading becomes "intro" section
6. `test_empty_sections_skipped` — Empty sections between headings don't produce chunks
7. `test_chinese_character_counting` — Chunk size limits work correctly with Chinese text
8. `test_sentence_boundary_split` — Secondary split breaks at 。！？ not mid-sentence
9. `test_max_chars_enforced` — No chunk exceeds max_chars (1200 default)
10. `test_long_no_punctuation` — Very long text without sentence boundaries still splits (fallback to comma/space)

Use pytest. Test data should be Chinese text matching the domain (退款规则 snippets).
</action>
<acceptance_criteria>
- tests/test_chunker.py exists
- File contains at least 8 test functions (grep -c "def test_" >= 8)
- File imports from src.rag.chunker
- Tests use Chinese text content
- `uv run pytest tests/test_chunker.py -q` exits 0
</acceptance_criteria>
</task>

</tasks>

<verification>
- `uv run pytest tests/test_chunker.py -q` passes all tests
- `uv run python -c "from src.rag.chunker import chunk_markdown, ChunkResult; print('OK')"` exits 0
- `uv run python -c "from src.rag.embedder import EmbeddingService; s = EmbeddingService(); print('OK')"` exits 0 (no crash without API key)
</verification>

<must_haves>
- Chunker splits by Markdown headings with stable deterministic chunk_ids using doc_key
- Oversized sections get secondary split at sentence boundaries with overlap
- Embedding service uses lazy client init (no crash without API key at construction)
- batch_size clamped to max 10
- Chinese character counting (not token counting) for size limits
</must_haves>
