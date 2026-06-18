# Architecture Research

**Domain:** MOCA v1.4 RAG Production Ingestion + OCR
**Researched:** 2026-06-18
**Confidence:** HIGH

## Standard Architecture

### System Overview

Phase 21 should extend the existing RAG ingestion plane, not the agent runtime plane. The current online retrieval contract is already correct: `PolicyRetrievalEngine` reads `PolicyChunk`, builds internal hits, and `PolicyKnowledgeService` exposes canonical `EvidenceRefV1` refs to Agent, approval, snapshot, and replay consumers. Parser/OCR and source-block provenance belong before chunk storage.

Recommended architecture:

```text
Ingestion plane, offline or admin-triggered

Source file + manifest
  -> IngestionService
  -> ParserRegistry
  -> PDF/DOCX/Image/Markdown parser
  -> optional OCR adapter
  -> ParsedBlock DTOs
  -> cleaning/normalization
  -> block-aware chunker
  -> search_text + embedding text builders
  -> embedding
  -> single DB write transaction
  -> policy_documents + document_blocks + policy_chunks + rag_ingestion_jobs

Online retrieval plane, unchanged by default

Agent / search API
  -> UnifiedToolManager / KnowledgeToolExecutor
  -> PolicyKnowledgeService
  -> PolicyRetrievalEngine
  -> PolicyChunkRepository dense/sparse/fuzzy retrieval
  -> EvidenceRefV1

Optional provenance side path

EvidenceRefV1
  -> verify chunk content hash
  -> policy_chunks.source_block_ids_json
  -> document_blocks page/bbox/table/cell metadata
  -> UI/debug locator outside EvidenceRefV1
```

Storage layers:

```text
+-------------------------------------------------------------+
| Existing online contract                                    |
| PolicyKnowledgeService -> EvidenceRefV1                     |
| unchanged fields, unchanged canonical hash projection       |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
| Existing retrieval backend                                  |
| policy_chunks.content      citation text                    |
| policy_chunks.search_text  retrieval-only text              |
| policy_chunks.search_vector / embedding / filters           |
+------------------------------+------------------------------+
                               ^
                               |
+-------------------------------------------------------------+
| New Phase 21 ingestion provenance                           |
| document_blocks: parsed source blocks with page/bbox/table  |
| rag_ingestion_jobs: parser/OCR/indexing status and warnings |
| policy_chunks.source_block_ids_json + page/bbox summaries   |
+------------------------------+------------------------------+
                               ^
                               |
+-------------------------------------------------------------+
| New parser/OCR adapters                                     |
| Markdown fast path, PDF, DOCX, image/OCR                    |
| adapters are replaceable implementation, not agent contract |
+-------------------------------------------------------------+
```

The key decision is to make `DocumentBlock` durable but non-canonical for cross-layer evidence identity. It is authoritative for source location and parser/OCR quality, while `EvidenceRefV1` remains authoritative for citation identity.

### Component Responsibilities

| Component | Status | Responsibility | Implementation Guidance |
|-----------|--------|----------------|-------------------------|
| `src/rag/ingestion.py` `IngestionService` | Modify | Orchestrate parse, clean, chunk, embed, and DB write. Preserve current report style and transaction rollback behavior. | Keep one service. Add a block-based path beside the current Markdown path, then route Markdown through the same parser contract once stable. |
| `src/rag/parsers/base.py` | New | Define parser-neutral DTOs: `ParseResult`, `ParsedBlock`, parser metadata, warnings, OCR confidence. | Use small frozen dataclasses or Pydantic models. Do not leak backend-specific objects. |
| `src/rag/parsers/markdown.py` | New | Preserve current Markdown/plain-text fast path and produce structured blocks. | This should be the first adapter because existing ingestion fixtures can validate no evidence identity regression. |
| `src/rag/parsers/pdf.py`, `docx.py`, `image.py`, `ocr.py` | New | Convert source formats into `ParsedBlock` objects with page, bbox, table/cell, parser version, and OCR confidence where available. | Keep backend choice behind the adapter. Phase 21 should not bind MOCA contracts to a parser framework's internal model. |
| `src/rag/cleaning.py` | New | Normalize Unicode, whitespace, soft line breaks, repeated headers/footers, and low-confidence OCR markers before chunking. | Cleaning must be deterministic and fixture-tested. It must not hide low OCR confidence. |
| `src/rag/chunker.py` | Modify | Add block-aware chunking while preserving `chunk_markdown(...)` compatibility. | Introduce `chunk_blocks(...)` rather than replacing the current function in one step. Table chunks keep headers with row groups. |
| `PolicyDocument` model | Modify | Store source and parser-level metadata for a policy document. | Add only Phase 21-needed fields: source type/URI, checksums, content hash, parser/OCR metadata, ingestion status, last indexed time. |
| `DocumentBlock` model | New | Store parsed source blocks before chunking. | First-class DB table with tenant/doc scope, block index, page, bbox, type, text, normalized text, table metadata, parser version, OCR/layout confidence. |
| `PolicyChunk` model | Modify | Link chunks back to source blocks and expose source location summaries. | Add nullable provenance columns. Keep `content` and `search_text` semantics unchanged. |
| `rag_ingestion_jobs` model | New | Track parse/chunk/embed/index stages, warnings, errors, checksums, and parser versions. | Use a job log, not a full event stream, for Phase 21. Events can wait until async OCR is actually introduced. |
| `PolicyChunkRepository` | Modify narrowly | Existing retrieval queries stay the same. Add a separate provenance lookup method only if needed by tests/API. | Do not join `document_blocks` in default dense/sparse/fuzzy retrieval. |
| `PolicyRetrievalEngine` | Mostly unchanged | Continue to return `PolicyRetrievalHit` and build `EvidenceRefV1` from chunk content. | Optional internal hit fields may include locator metadata, but `EvidenceRefV1.model_dump()` must not change. |
| `PolicyKnowledgeService` | Interface unchanged | Preserve facade boundary and canonical evidence refs. | If provenance is exposed, add a separate verified lookup helper that first validates evidence text hash. |
| Agent nodes, `BusinessToolService`, approval, memory, replay | Unchanged | Consume policy evidence refs and business facts through existing boundaries. | No parser/OCR code should be imported by agent nodes or business tools. |

## Recommended Project Structure

Keep the structure close to the current `src/rag` and repository patterns:

```text
src/
├── rag/
│   ├── ingestion.py             # modified orchestration path
│   ├── chunker.py               # keep chunk_markdown, add chunk_blocks
│   ├── cleaning.py              # deterministic block/text normalization
│   ├── search_text.py           # existing retrieval-only text builder
│   └── parsers/
│       ├── __init__.py
│       ├── base.py              # ParsedBlock / ParseResult / parser protocol
│       ├── markdown.py          # existing markdown behavior as parser
│       ├── pdf.py               # PDF parser adapter
│       ├── docx.py              # DOCX parser adapter
│       ├── image.py             # image source adapter
│       └── ocr.py               # OCR backend wrapper
├── repositories/
│   ├── policy_document_repo.py  # existing, extend with source metadata if needed
│   ├── policy_chunk_repo.py     # existing retrieval, optional provenance lookup
│   ├── document_block_repo.py   # new block bulk insert/delete/query
│   └── rag_ingestion_job_repo.py# new job status writes
└── db/
    ├── models.py                # add DocumentBlock, RagIngestionJob, columns
    └── migrations/versions/
        └── 015_rag_source_blocks.py
```

### Structure Rationale

- **`src/rag/parsers/`:** parser/OCR backend churn stays inside ingestion. The rest of MOCA sees normalized `ParsedBlock` records, not PDF/DOCX/OCR library objects.
- **`src/rag/chunker.py`:** the current chunker is already the local home for chunk identity. Add block-aware behavior here to avoid a new parallel chunking subsystem.
- **Repository additions:** current code uses repository classes for policy documents/chunks. Add repositories only for new persistent tables; do not create a broad RAG service hierarchy.
- **No new search backend package:** Phase 21 is ingestion/provenance. PostgreSQL hybrid retrieval remains the backend.

## Architectural Patterns

### Pattern 1: Parser Contract Before Backend Choice

**What:** Every source parser returns the same project-owned DTOs.

```python
@dataclass(frozen=True)
class ParsedBlock:
    block_index: int
    block_type: str
    text: str
    normalized_text: str
    page_number: int | None = None
    bbox_json: dict | None = None
    ocr_confidence: float | None = None
    layout_confidence: float | None = None
    parent_heading_path: tuple[str, ...] = ()
    table_json: dict | None = None
    metadata_json: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ParseResult:
    source_type: str
    parser_name: str
    parser_version: str
    ocr_required: bool
    ocr_engine: str | None
    blocks: list[ParsedBlock]
    warnings: list[dict]
```

**When to use:** For Markdown, PDF, DOCX, image, and OCR paths.

**Trade-offs:** This adds a small adapter layer, but it prevents parser lock-in and lets tests pin MOCA's real contract: page/bbox stability, table preservation, low-confidence markers, and source-block traceability.

### Pattern 2: Source Blocks Are Durable, Not Prompt Payload

**What:** Persist `DocumentBlock` rows as provenance and quality-control records. Do not push raw parser payloads or full OCR debug blobs into prompts.

Recommended `DocumentBlock` columns:

```text
id
tenant_id
doc_id
block_index
page_number
block_type
text
normalized_text
bbox_json
ocr_confidence
layout_confidence
parent_heading_path_json
table_json
metadata_json
parser_name
parser_version
created_at
updated_at
```

Recommended indexes:

```text
unique: tenant_id, doc_id, block_index
index:  tenant_id, doc_id, page_number
index:  tenant_id, doc_id, block_type
```

**When to use:** Always for Phase 21 source ingestion, including Markdown. Markdown blocks may have null page/bbox/OCR fields, but the path should still prove block-to-chunk provenance.

**Trade-offs:** Storing block text duplicates some content already represented in chunks. That is acceptable because blocks answer a different question: "where did this chunk come from?"

### Pattern 3: Provenance Sidecar, Not EvidenceRef Extension

**What:** Store locator metadata beside chunks and blocks, but leave `EvidenceRefV1` unchanged.

Recommended `PolicyChunk` additions:

```text
source_block_ids_json   JSONB array of DocumentBlock ids in chunk order
page_start              nullable int
page_end                nullable int
bbox_json               nullable JSONB summary, page keyed if multi-page
content_hash            hash of PolicyChunk.content
token_count             nullable int
metadata_json           JSONB, including low_ocr_confidence flags/table summary
```

`PolicyChunk.content` remains the citation text used for `EvidenceRefV1.text_hash`. `PolicyChunk.search_text` remains retrieval-only enrichment. `embedding_text` can be built in memory during ingestion; storing it is not required for Phase 21 and should not be treated as citation text.

**When to use:** Whenever UI/debug needs page/bbox/cell provenance or tests need to prove chunk-to-source traceability.

**Trade-offs:** A JSONB block-id array has weaker DB-level referential integrity than a join table. It is the right v1.4 default because ingestion recreates all blocks/chunks per document and online retrieval does not need reverse block-to-chunk joins. Add a join table later only if visual review workflows need block-centric queries.

### Pattern 4: Atomic Reindex With Parse/Embed Outside The Write Transaction

**What:** Continue the existing pattern where expensive work happens before the short DB mutation window.

Recommended flow:

```text
1. Compute source checksum.
2. Parse/OCR source file to ParsedBlock DTOs.
3. Clean and normalize blocks.
4. Chunk blocks and build content/search_text/embedding_text.
5. Generate embeddings.
6. Open DB transaction and lock policy_documents row by tenant/doc_key.
7. Decide whether canonical content changed and whether PolicyDocument.version bumps.
8. Delete old chunks and blocks for the document.
9. Insert DocumentBlock rows.
10. Insert PolicyChunk rows with source_block_ids_json mapped from block_index -> id.
11. Update document metadata and job status.
12. Commit.
```

If parse, OCR, chunking, or embedding fails before step 6, no existing indexed document is touched. If DB mutation fails after step 6, rollback restores the previous indexed document because delete/insert happened inside one transaction. After rollback, mark the job failed in a separate best-effort status update so failures are observable without partial index state.

**When to use:** Every reimport, including same-content reimports and parser-version-only reindexes.

**Trade-offs:** Parser/OCR output is held in memory for the current document. That is acceptable for Phase 21 fixtures and admin imports; async streaming/worker ingestion can be a later phase if file sizes demand it.

### Pattern 5: Version Bump Based On Canonical Citation Text

**What:** Keep evidence identity stable unless the policy text seen by citations changes.

Rules:

- Bump `PolicyDocument.version` when canonical document/chunk citation text changes, or when policy semantics metadata changes in a way that should invalidate old evidence, such as effective date, doc type, or risk level.
- Do not bump version for parser-version-only changes when `PolicyChunk.content` and `EvidenceRefV1.text_hash` remain unchanged.
- Do not hash `search_text`, parser warnings, bbox, or OCR debug metadata into `EvidenceRefV1`.
- If OCR output changes chunk citation text, the content hash changes and version should bump.

This preserves approval/replay expectations: old evidence refs remain meaningful when citation text is unchanged, and changed text forces a new evidence identity or fails text-hash verification.

## Data Flow

### Ingestion Flow

```text
Manifest row
  doc_key, title, doc_type, risk_level, source_type, file/source URI
    |
    v
IngestionService.ingest_document(...)
    |
    +-> create rag_ingestion_jobs row: stage=received, status=running
    |
    +-> ParserRegistry selects adapter by source_type or file extension
    |
    +-> parser returns ParseResult(blocks, warnings, parser metadata)
    |
    +-> cleaning normalizes block text and marks low-confidence OCR
    |
    +-> chunk_blocks produces ChunkResult records:
    |      content             citation text
    |      search_text input   retrieval-only enrichment source
    |      embedding_text      title/heading/context-enriched embedding input
    |      source_block_indexes
    |      page_start/page_end/bbox/table metadata
    |
    +-> embedder.embed_documents(embedding_texts)
    |
    v
DB transaction
    |
    +-> lock PolicyDocument by tenant/doc_key
    +-> upsert PolicyDocument source/parser/checksum/content metadata
    +-> delete old PolicyChunk rows for doc
    +-> delete old DocumentBlock rows for doc
    +-> bulk insert DocumentBlock rows
    +-> bulk insert PolicyChunk rows with source_block_ids_json
    +-> set rag_ingestion_jobs stage=indexed, status=success
    |
    v
commit
```

`rag_ingestion_jobs` minimum columns:

```text
id
tenant_id
doc_id
doc_key
source_type
source_uri
source_checksum
stage
status
parser_name
parser_version
ocr_engine
retrieval_config_version
warnings_json
error_code
error_message
started_at
completed_at
created_at
updated_at
```

Use stage values that match actual implementation gates:

```text
received -> parsed -> cleaned -> chunked -> embedded -> indexed -> ready
parse_failed | clean_failed | chunk_failed | embedding_failed | index_failed
```

### Chunking Flow

Current `chunk_markdown(content, doc_key=...)` should remain as a compatibility helper. Phase 21 adds `chunk_blocks(parse_result, doc_key=...)` with these rules:

1. Heading/list/paragraph blocks inherit `parent_heading_path`.
2. Table blocks remain atomic by default.
3. Oversized tables split by row groups and repeat header context in `content` and `search_text` input.
4. Chunk overlap is allowed for paragraphs but must not create false page/bbox ranges.
5. Each chunk records source block indexes before DB insert and source block ids after block rows exist.
6. Low OCR confidence propagates into chunk metadata and should be available for future ranking/verification, but Phase 21 must not implement Phase 22 semantic verifier logic.

### Retrieval Flow

Default online retrieval stays as v1.3:

```text
query
  -> build_policy_chunk_search_text(query)
  -> embed query
  -> PolicyChunkRepository.search_similar/search_sparse/search_fuzzy
  -> RRF merge in PolicyRetrievalEngine
  -> PolicyRetrievalHit(text=PolicyChunk.content)
  -> EvidenceRefV1.build(text=hit.text)
  -> KnowledgeSearchResult.evidence_refs
```

No default retrieval query needs to join `document_blocks`. The extra provenance fields are read only when explicitly requested for display/debug. This avoids latency and keeps `PolicyKnowledgeService.search(...)` stable.

### Provenance Lookup Flow

If Phase 21 exposes source locators, use a verified side path:

```text
EvidenceRefV1
  -> PolicyKnowledgeService.get_verified_evidence_contents(...)
  -> content hash matches ref.text_hash
  -> PolicyChunkRepository.get_provenance_by_evidence_keys(...)
  -> source_block_ids_json
  -> DocumentBlockRepository.get_by_ids(...)
  -> locator payload: page, bbox, block type, table/cell metadata, OCR confidence
```

Do not include this locator payload in `EvidenceRefV1`, `canonical_evidence_projection`, or `ActionSafetySnapshot.immutable_hash` in Phase 21. The locator is useful context, not canonical citation identity.

## Integration Points

### Internal Boundaries

| Boundary | Communication | Recommendation |
|----------|---------------|----------------|
| Source manifest -> `IngestionService` | Existing dict-style `doc_meta`, extended | Add `source_type`, optional `source_uri`, optional parser hints. Keep existing Markdown manifest working. |
| `IngestionService` -> parser adapters | `ParseResult` DTO | Parser adapters never receive DB models and never write DB rows. |
| Parser adapters -> OCR backend | Adapter-local implementation | OCR backend is replaceable. Store backend name/version/confidence, not backend-native objects. |
| Parser/cleaner -> chunker | `ParsedBlock` list | Chunker owns chunk ids, content text, source block span, and table-aware splitting. |
| Chunker -> search text builder | Plain strings and metadata | Reuse `build_policy_chunk_search_text`; extend inputs only if needed for heading/table context. |
| Ingestion -> DB repositories | SQLAlchemy models/repositories | Preserve bulk insert style and short write transactions. |
| Retrieval -> Knowledge facade | Existing `EvidenceRefV1` | Do not widen `KnowledgeSearchResult` for provenance in Phase 21. |
| Provenance display/debug -> repository | Separate lookup helper | Verify evidence content hash before returning locator metadata. |
| Business tools -> RAG ingestion | No communication | Business facts must never become policy source files, document blocks, chunks, or evidence refs. |

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| PDF parser | Wrapped behind `src/rag/parsers/pdf.py` | Must output page numbers, text blocks, table hints, and parser warnings. Backend can change without schema changes. |
| DOCX parser | Wrapped behind `src/rag/parsers/docx.py` | Must preserve headings, paragraphs, tables, and image OCR requirements. |
| OCR engine | Wrapped behind `src/rag/parsers/ocr.py` | Must expose confidence and bbox. Low confidence is metadata, not silent normal text. |
| Embedding provider | Existing `EmbeddingService` | Continue embedding before DB mutation. Store only needed metadata; do not make embedding text citation text. |
| PostgreSQL/pgvector | Existing canonical store | Add provenance tables/columns. Do not add Vespa/OpenSearch or external `SearchBackend` in Phase 21. |

## Build Order

1. **Schema and model foundation**
   - Add migration `015_rag_source_blocks.py` after `014_rag_hybrid_retrieval`.
   - Add `DocumentBlock`, `RagIngestionJob`, `PolicyDocument` source metadata, and nullable `PolicyChunk` provenance columns.
   - Add model/migration tests for columns, indexes, check constraints, downgrade order, and unchanged `EvidenceRefV1`.

2. **Parser contract and Markdown adapter**
   - Add `ParsedBlock`/`ParseResult` DTOs and parser protocol.
   - Implement Markdown/plain-text parser by adapting current behavior.
   - Fixtures should prove current Markdown ingestion still produces the same `PolicyChunk.content`, `search_text`, and evidence text hashes.

3. **Cleaning and block-aware chunking**
   - Add deterministic cleaning.
   - Add `chunk_blocks(...)` with source block indexes, page range, bbox summary, table handling, and OCR confidence propagation.
   - Keep `chunk_markdown(...)` tests passing.

4. **Ingestion transaction integration**
   - Modify `IngestionService` to parse, clean, chunk, and embed before DB writes.
   - Inside one transaction, lock doc, version if needed, delete old chunks/blocks, insert blocks/chunks, update job status.
   - Add rollback tests proving a failed insert leaves previous doc version/content/chunks/blocks intact.

5. **PDF, DOCX, image/OCR adapters**
   - Add fixture-backed adapters with predictable output.
   - Prioritize contract behavior over parser sophistication: page/bbox presence, table header preservation, low-confidence flags, warnings.
   - Avoid making OCR async unless a local blocking fixture path is impossible.

6. **Provenance read path**
   - Add repository lookup for block locators if Phase 21 needs display/debug output.
   - Gate it behind evidence hash verification.
   - Tests must assert provenance fields do not appear in `EvidenceRefV1.model_dump()`.

7. **Boundary and regression tests**
   - Run focused ingestion/retrieval tests plus schema tests.
   - Add tests proving business tool outputs are not accepted as policy ingestion sources and no business fact refs are serialized as `EvidenceRefV1`.
   - Keep v1.3 hybrid retrieval behavior intact: dense/sparse/fuzzy filters, RRF ordering, and `search_text` semantics.

8. **Rollback verification**
   - Migration downgrade drops provenance indexes/tables and then columns in reverse dependency order.
   - Runtime feature rollback can disable parser/OCR ingestion and keep Markdown ingestion working.
   - Failed ingestion must leave the last committed indexed document retrievable.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Local demo / current MOCA | Synchronous admin/CLI ingestion is enough. Parser/OCR work can run in process, with a job log for observability. |
| Larger policy corpus | Add batching, per-document job retries, and separate parser/OCR timeouts. Keep PostgreSQL as source of truth. |
| Slow OCR or large scanned PDFs | Introduce a background worker only after job durations make synchronous ingestion painful. The job log already gives the handoff point. |
| Retrieval scale pressure | Do not solve in Phase 21. PostgreSQL hybrid remains the backend until Phase RAG-5 explicitly evaluates external search. |

### Scaling Priorities

1. **First bottleneck: OCR latency.** Add parser/OCR timeout, job status, and retry before adding queues.
2. **Second bottleneck: large source blocks/tables.** Cap block/table metadata sizes and store summaries in chunks; keep full details in `DocumentBlock.table_json`.
3. **Third bottleneck: retrieval query latency.** Avoid default joins to `document_blocks`; keep provenance lookup separate and on-demand.

## Anti-Patterns

### Anti-Pattern 1: Extending `EvidenceRefV1` With Page/Bbox Fields

**What people do:** Add `page_number`, `bbox`, `source_block_ids`, or parser metadata directly to `EvidenceRefV1`.

**Why it is wrong:** `EvidenceRefV1` is already consumed by AgentState, approval snapshots, replay, citation validation, and canonical hash projection. Adding mutable locator metadata risks invalidating snapshots and widening a stable contract for UI/debug needs.

**Do this instead:** Store locators on `PolicyChunk` and `DocumentBlock`; expose them through a separate verified provenance lookup.

### Anti-Pattern 2: Treating `search_text` Or `embedding_text` As Citation Text

**What people do:** Put heading expansions, synonyms, table headers, OCR hints, or retrieval tokens into `PolicyChunk.content`.

**Why it is wrong:** `PolicyChunk.content` is hashed into `EvidenceRefV1.text_hash` and shown as evidence. Retrieval enrichment would become fake citation text.

**Do this instead:** Keep three surfaces separate: `content` for citation, `search_text` for sparse/fuzzy retrieval, and in-memory `embedding_text` for embeddings.

### Anti-Pattern 3: Parser/OCR Output Goes Straight To Chunks

**What people do:** Parse a PDF into a long string and feed it directly to the existing markdown chunker.

**Why it is wrong:** Page numbers, bbox, table cells, OCR confidence, and parser warnings are lost before chunks are created.

**Do this instead:** Persist `DocumentBlock` first conceptually, even if DB insert happens in the final transaction. Chunks must carry source block ids.

### Anti-Pattern 4: Low-Confidence OCR Becomes Normal Evidence

**What people do:** OCR text with confidence 0.42 is indexed and retrieved the same as clean text.

**Why it is wrong:** Misread amounts, dates, and policy exceptions can produce high-risk wrong answers.

**Do this instead:** Propagate confidence to `DocumentBlock` and chunk metadata. Phase 21 should flag and test it; future Phase 22 can use it for verifier/manual-review policy.

### Anti-Pattern 5: Business Facts Enter The RAG Corpus

**What people do:** Ingest order, refund, ticket, or tool result summaries as policy chunks to improve answers.

**Why it is wrong:** MOCA's contract separates policy evidence from current business facts. Business facts belong to the Tool System and typed business fact refs, not `EvidenceRefV1`.

**Do this instead:** Keep RAG ingestion limited to policy/FAQ source documents. Troubleshooting answers must combine business tool refs with policy evidence refs at reasoning time.

### Anti-Pattern 6: Building Phase 22/23 Early

**What people do:** Add `MaterialClaim`, semantic verifier, reranker/query rewrite, or external search backend while implementing OCR provenance.

**Why it is wrong:** It expands too many contracts at once and makes it hard to tell whether regressions come from ingestion, retrieval ranking, or generation control.

**Do this instead:** Phase 21 ends when source files can become block-provenanced chunks without changing current evidence identity. Later phases consume that foundation.

## Phase-Specific Test Strategy

| Test Area | Required Coverage |
|-----------|-------------------|
| Schema/migration | `DocumentBlock` and job tables exist; chunk provenance columns exist; downgrade drops indexes/tables/columns in reverse order; `EvidenceRefV1` schema unchanged. |
| Parser fixtures | Markdown, PDF, DOCX, image/OCR fixture outputs produce stable `ParsedBlock` objects with parser metadata and warnings. |
| OCR confidence | Low-confidence blocks remain flagged through chunk metadata; no test should expect them to become high-confidence evidence. |
| Table chunking | Table headers/cells survive chunking; oversized tables split by row group with header context retained. |
| Provenance mapping | Every chunk from block ingestion has source block references, page range, and retrievable block rows. |
| Citation identity | `EvidenceRefV1.text_hash` is still based on `PolicyChunk.content`; provenance fields do not appear in `EvidenceRefV1`. |
| Transaction rollback | Failed parse/chunk/embed/insert does not delete the previous document's committed chunks/blocks or bump version. |
| Business boundary | Tool results/business fact refs cannot be ingested into `policy_chunks`, `document_blocks`, or `EvidenceRefV1`. |
| v1.3 regression | Hybrid retrieval tests still pass; sparse/fuzzy search still use `search_text`; tenant/effective/risk filters still apply before candidates. |

## Sources

- `.planning/PROJECT.md` - v1.4 scope, Phase 21 active requirements, and evidence/business boundaries. Confidence: HIGH.
- `.planning/MILESTONES.md` - v1.3 shipped state and explicit Phase 21/22/23/RAG-5 deferrals. Confidence: HIGH.
- `.planning/milestones/v1.3-ROADMAP.md` - Phase 20 delivered architecture and deferred ingestion/OCR ownership. Confidence: HIGH.
- `src/rag/ingestion.py` - current Markdown ingestion transaction, version bump, search text, embedding, and rollback pattern. Confidence: HIGH.
- `src/rag/chunker.py` - current heading-based chunk identity and split behavior. Confidence: HIGH.
- `src/db/models.py` - current `PolicyDocument`, `PolicyChunk`, and JSONB/model conventions. Confidence: HIGH.
- `src/db/migrations/versions/002_rag_pipeline.py` and `014_rag_hybrid_retrieval.py` - current migration chain, pgvector, full-text, trigram, and rollback patterns. Confidence: HIGH.
- `src/knowledge/schemas.py`, `src/knowledge/service.py`, `src/knowledge/retrieval.py` - canonical `EvidenceRefV1`, facade behavior, retrieval hit projection, and verified content lookup. Confidence: HIGH.
- `docs/contract-spec.md` - normative EvidenceRefV1 and business-tool boundary contracts. Confidence: HIGH.
- `docs/rag-architecture-spec.md` - project RAG target architecture, DocumentBlock/OCR rationale, and Phase RAG-2 goals. Confidence: MEDIUM because it is target-state design, not all implemented code.
- `.planning/phases/20-rag-hybrid-retrieval/20-RESEARCH.md` and `20-CONTEXT.md` - v1.3 decisions about `search_text`, internal retrieval trace, and no business fact pollution. Confidence: HIGH.

---
*Architecture research for: MOCA v1.4 Phase 21 parser/OCR ingestion and source-block provenance*
*Researched: 2026-06-18*
