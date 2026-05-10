# Phase 2: RAG Pipeline — Research

**Researched:** 2026-05-10
**Mode:** ecosystem
**Confidence:** High (API docs verified, patterns confirmed against existing codebase)

---

## Standard Stack

| Component | Library | Why |
|-----------|---------|-----|
| Embedding client | `openai` (Python SDK) | DashScope is OpenAI-compatible; just change base_url. No DashScope-specific SDK needed. Lightweight, well-maintained, async support via `AsyncOpenAI`. |
| Markdown parsing | Hand-rolled regex splitter | Documents are simple structured Markdown (##/### headings). No need for langchain-text-splitters or markdown-it — a ~60-line function handles heading-based splitting with size limits. Avoids heavy dependency. |
| Vector storage | `pgvector` (already installed) | Already in pyproject.toml. SQLAlchemy integration via `pgvector.sqlalchemy.Vector`. |
| Vector search | Raw SQLAlchemy + pgvector operators | `<=>`  (cosine distance) operator directly in SQLAlchemy queries. No ORM abstraction needed for similarity search. |
| Async HTTP | `httpx` (already in dev deps) | For embedding API calls if openai SDK async isn't sufficient. But prefer `openai.AsyncOpenAI`. |

**New dependencies to add:**
- `openai>=1.30` — embedding client (OpenAI-compatible API for DashScope)

**Do NOT add:**
- `langchain` / `langchain-text-splitters` — overkill for heading-based Markdown splitting
- `llama-index` — architecture diagram mentions it but project doesn't use it; direct pgvector is simpler
- `tiktoken` — not needed; DashScope counts tokens server-side; chunk size measured in Chinese characters
- `sentence-transformers` — not using local models

---

## Architecture Patterns

### Embedding Service Pattern

```python
from openai import AsyncOpenAI

class EmbeddingService:
    def __init__(self, api_key: str, base_url: str, model: str = "text-embedding-v4"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def embed_documents(self, texts: list[str], dimensions: int = 1024) -> list[list[float]]:
        # DashScope max 10 items per request
        results = []
        for batch in _chunked(texts, 10):
            resp = await self.client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=dimensions,
            )
            results.extend([item.embedding for item in resp.data])
        return results

    async def embed_query(self, text: str, dimensions: int = 1024) -> list[float]:
        resp = await self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=dimensions,
        )
        return resp.data[0].embedding
```

### Chunking Pattern

```python
import re

def chunk_markdown_by_headings(
    content: str,
    doc_id: str,
    max_chunk_chars: int = 1200,
    target_chunk_chars: int = 800,
    overlap_chars: int = 100,
) -> list[dict]:
    """Split markdown by ## and ### headings. Returns list of chunk dicts."""
    heading_pattern = re.compile(r'^(#{2,3})\s+(.+)$', re.MULTILINE)
    # Split at headings, preserve hierarchy, generate stable chunk_ids
    ...
```

### Retrieval Pattern (pgvector cosine search)

```python
from pgvector.sqlalchemy import Vector
from sqlalchemy import text

async def search_chunks(
    session: AsyncSession,
    query_embedding: list[float],
    tenant_id: UUID,
    top_k: int = 5,
    min_similarity: float = 0.55,
    filters: dict | None = None,
) -> list[dict]:
    # Use cosine distance operator <=>
    # 1 - (a <=> b) = cosine similarity
    stmt = (
        select(
            PolicyChunk,
            (1 - PolicyChunk.embedding.cosine_distance(query_embedding)).label("similarity")
        )
        .where(PolicyChunk.tenant_id == tenant_id)
        .where((1 - PolicyChunk.embedding.cosine_distance(query_embedding)) >= min_similarity)
        .order_by(PolicyChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    # Apply metadata filters (doc_type, risk_level)
    ...
```

### Repository Pattern (follows existing BaseRepository)

```python
class PolicyChunkRepository(BaseRepository[PolicyChunk]):
    model = PolicyChunk

    async def search_similar(self, query_embedding, tenant_id, top_k=5, min_similarity=0.55, **filters):
        ...

    async def delete_by_doc_id(self, doc_id: UUID, tenant_id: UUID) -> int:
        """Delete all chunks for a document (idempotent re-ingestion)."""
        ...

    async def bulk_insert(self, chunks: list[PolicyChunk]) -> None:
        """Insert chunks in batch."""
        ...
```

---

## Don't Hand-Roll

| Problem | Use Instead | Why |
|---------|-------------|-----|
| Embedding API calls | `openai.AsyncOpenAI` with base_url | Handles retries, streaming, error parsing. Battle-tested. |
| Vector similarity SQL | pgvector `<=>` operator via SQLAlchemy | Correct cosine distance implementation, uses HNSW index automatically. |
| UUID generation | `uuid.uuid4()` (existing pattern) | Already established in all models. |
| Batch retry logic | `tenacity` or manual loop with exponential backoff | Don't write custom retry from scratch; but for MVP a simple 3-retry loop is fine without adding tenacity. |
| HNSW index | Alembic migration with raw SQL | `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 128)` |

---

## Common Pitfalls

### 1. Vector Dimension Mismatch (CRITICAL)
**Current state:** `PolicyChunk.embedding` is `Vector(1536)` in models.py.
**Required:** `Vector(1024)` per D-03b (DashScope text-embedding-v4 default).
**Fix:** Alembic migration to ALTER COLUMN type. Must happen before any embedding is stored.

### 2. DashScope Batch Limit is 10, Not 16
**D-04a says 16 chunks/request.** DashScope API docs confirm max 10 items per request.
**Fix:** Use batch size of 10 (or configurable `EMBEDDING_BATCH_SIZE` defaulting to 10).

### 3. Cosine Distance vs Cosine Similarity
pgvector `<=>` returns **distance** (0 = identical, 2 = opposite). Similarity = 1 - distance.
Thresholds in D-05 are **similarity** values (0.55, 0.70). Query must compute `1 - distance >= threshold`.

### 4. Chinese Character Counting
`len(text)` in Python counts Unicode code points, which is correct for Chinese characters.
Do NOT use token counting for chunk size — DashScope tokens ≠ characters. The 400-800 char target is character-based.

### 5. text_type Parameter for Asymmetric Retrieval
DashScope supports `text_type: "query"` vs `"document"` for asymmetric embedding.
- Ingestion: use `text_type: "document"` (or omit, it's default)
- Query-time: use `text_type: "query"`
- **Caveat:** This parameter is in DashScope's native API (`parameters.text_type`), NOT in the OpenAI-compatible endpoint. If using OpenAI SDK, this may not be passable. Verify at implementation time. If not available, omit — v4 model still works well without it.

### 6. HNSW Index Must Be Created AFTER Data Load
For small datasets (<1000 rows), building HNSW index on empty table is fine. But for best practice:
- Create index in migration (it works on empty tables)
- For large re-ingestion: consider dropping and recreating index

### 7. Stable chunk_id Generation
chunk_id must be deterministic: `f"{doc_id}_{section_index:03d}"` or `f"{doc_id}_{section_index:03d}_part_{part_index}"`.
Do NOT use content hashing — content changes should update the same chunk_id, not create a new one.

### 8. Idempotent Ingestion Race Condition
Delete-and-reinsert per document is simple but not atomic. Wrap in a transaction:
```python
async with session.begin():
    await repo.delete_by_doc_id(doc_id, tenant_id)
    await repo.bulk_insert(new_chunks)
```

### 9. Empty Embedding on API Failure
If embedding API fails mid-batch, some chunks have embeddings and some don't. The ingestion script must be all-or-nothing per document — fail the entire document if any chunk embedding fails.

---

## Code Examples

### DashScope Embedding Call (OpenAI-compatible)

```python
import os
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# Single query embedding
response = await client.embeddings.create(
    model="text-embedding-v4",
    input="用户申请仅退款但商家已经发货",
    dimensions=1024,
)
embedding = response.data[0].embedding  # list[float], len=1024

# Batch document embedding (max 10 per request)
response = await client.embeddings.create(
    model="text-embedding-v4",
    input=["chunk text 1", "chunk text 2", ..., "chunk text 10"],
    dimensions=1024,
)
embeddings = [item.embedding for item in response.data]
```

### HNSW Index Migration (Alembic)

```python
def upgrade():
    # Fix dimension: 1536 -> 1024
    op.alter_column('policy_chunks', 'embedding',
                    type_=sa.Column(Vector(1024)),
                    postgresql_using='embedding::vector(1024)')

    # Create HNSW index for cosine similarity search
    op.execute("""
        CREATE INDEX ix_policy_chunks_embedding_hnsw
        ON policy_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 128)
    """)
```

### Cosine Similarity Search with Metadata Filter

```python
from sqlalchemy import select, and_
from pgvector.sqlalchemy import Vector

stmt = (
    select(
        PolicyChunk.id,
        PolicyChunk.doc_id,
        PolicyChunk.chunk_id,
        PolicyChunk.section,
        PolicyChunk.content,
        PolicyChunk.risk_level,
        (1 - PolicyChunk.embedding.cosine_distance(query_embedding)).label("score"),
    )
    .where(
        and_(
            PolicyChunk.tenant_id == tenant_id,
            (1 - PolicyChunk.embedding.cosine_distance(query_embedding)) >= 0.55,
        )
    )
    .order_by(PolicyChunk.embedding.cosine_distance(query_embedding))
    .limit(5)
)

# Add optional filters
if doc_type:
    stmt = stmt.join(PolicyDocument).where(PolicyDocument.doc_type == doc_type)
if risk_level:
    stmt = stmt.where(PolicyChunk.risk_level == risk_level)
```

### Markdown Heading Chunker (Core Logic)

```python
import re
from dataclasses import dataclass

@dataclass
class ChunkResult:
    doc_id: str
    chunk_id: str
    section: str
    content: str
    chunk_index: int
    part_index: int | None = None

def chunk_markdown(content: str, doc_id: str, max_chars: int = 1200, target_chars: int = 800) -> list[ChunkResult]:
    sections = re.split(r'(?=^#{2,3}\s)', content, flags=re.MULTILINE)
    chunks = []
    idx = 0

    for section in sections:
        if not section.strip():
            continue
        heading_match = re.match(r'^(#{2,3})\s+(.+?)$', section, re.MULTILINE)
        section_title = heading_match.group(2).strip() if heading_match else "intro"
        section_body = section[heading_match.end():].strip() if heading_match else section.strip()

        if len(section_body) <= max_chars:
            chunks.append(ChunkResult(
                doc_id=doc_id, chunk_id=f"{doc_id}_{idx:03d}",
                section=section_title, content=section_body, chunk_index=idx
            ))
            idx += 1
        else:
            # Secondary split for oversized sections
            parts = _split_oversized(section_body, target_chars, overlap=100)
            for part_idx, part in enumerate(parts):
                chunks.append(ChunkResult(
                    doc_id=doc_id, chunk_id=f"{doc_id}_{idx:03d}_part_{part_idx}",
                    section=section_title, content=part,
                    chunk_index=idx, part_index=part_idx
                ))
            idx += 1

    return chunks
```

### Citation Validator

```python
@dataclass
class CitationValidationResult:
    valid: bool
    invalid_citations: list[str]

def validate_citations(cited_chunk_ids: list[str], retrieved_chunk_ids: set[str]) -> CitationValidationResult:
    invalid = [cid for cid in cited_chunk_ids if cid not in retrieved_chunk_ids]
    return CitationValidationResult(valid=len(invalid) == 0, invalid_citations=invalid)
```

### Golden Set Eval Script Pattern

```python
import json
from dataclasses import dataclass

@dataclass
class EvalResult:
    total: int
    hit_at_5: float
    fallback_accuracy: float
    per_category: dict[str, float]
    failed_cases: list[dict]

async def evaluate_rag(golden_path: str, retriever) -> EvalResult:
    with open(golden_path) as f:
        cases = [json.loads(line) for line in f]

    hits = 0
    fallback_correct = 0
    fallback_total = 0
    failed = []

    for case in cases:
        results = await retriever.search(case["query"])
        retrieved_ids = {r.chunk_id for r in results}

        if case.get("should_fallback"):
            fallback_total += 1
            if results.retrieval_status == "no_evidence":
                fallback_correct += 1
            else:
                failed.append({"case": case, "reason": "should_fallback_but_got_results"})
        else:
            expected = set(case["expected_chunk_ids"])
            if expected & retrieved_ids:
                hits += 1
            else:
                failed.append({"case": case, "reason": "expected_chunk_not_in_top5"})

    non_fallback = len(cases) - fallback_total
    return EvalResult(
        total=len(cases),
        hit_at_5=hits / non_fallback if non_fallback else 0,
        fallback_accuracy=fallback_correct / fallback_total if fallback_total else 0,
        per_category=_compute_per_category(cases, ...),
        failed_cases=failed,
    )
```

---

## HNSW Index Parameters

For this project's scale (~200-500 chunks from 15-30 documents):

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `m` | 16 | Good recall for small datasets; default is fine |
| `ef_construction` | 128 | 2x default (64) for better index quality; build time negligible at this scale |
| Distance operator | `vector_cosine_ops` | Cosine similarity is standard for text embeddings; DashScope embeddings are normalized |
| `ef_search` | 40 (default) | Sufficient for top-5 retrieval on small dataset |

At <1000 vectors, sequential scan would actually be fast enough. HNSW is added for correctness and to establish the pattern for production scale.

---

## Decision Corrections

| Original Decision | Issue | Correction |
|-------------------|-------|------------|
| D-04a: batch size 16 | DashScope API limit is 10 items/request | Use batch size 10 (configurable, max 10) |
| Model Vector(1536) | DashScope v4 default is 1024 dim | Migration to Vector(1024) required |

---

## Open Questions (Low Risk)

1. **text_type parameter via OpenAI SDK:** May not be passable through OpenAI-compatible endpoint. If not, embeddings still work — asymmetric optimization is a minor quality boost, not a requirement. Verify during implementation.
2. **DashScope rate limits:** Not documented explicitly. At our scale (15-30 docs, ~200-500 chunks), unlikely to hit limits. Add retry with backoff as safety net.

---

## RESEARCH COMPLETE

**Summary:** Phase 2 is straightforward with well-understood patterns. The main risks are the dimension mismatch (easy fix via migration) and the batch size correction. No exotic libraries needed — `openai` SDK + raw SQLAlchemy pgvector queries + hand-rolled Markdown splitter covers everything.

**Recommended next step:** `/gsd-plan-phase 2`
