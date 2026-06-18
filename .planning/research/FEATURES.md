# Feature Research

**Domain:** Production policy-source ingestion and OCR for MOCA RAG
**Researched:** 2026-06-18
**Confidence:** HIGH for project scope and dependencies; MEDIUM for exact parser/OCR implementation details because this file intentionally does not select third-party libraries.

## Feature Landscape

Phase 21 should turn MOCA's existing Markdown-oriented policy ingestion into a production ingestion foundation for real policy source files. The milestone should stop at parser/OCR normalization, durable source-block provenance, table-aware chunking, and traceability into the existing `PolicyChunk` and `EvidenceRefV1` retrieval contract.

The key product behavior is: a policy source file can be ingested, parsed into auditable source blocks, chunked without losing page/table/cell provenance, embedded through the existing v1.3 retrieval path, and cited later with source-location metadata. It must not introduce business-fact ingestion or change the existing policy evidence identity.

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = Phase 21 does not satisfy "production ingestion/OCR."

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| PDF, DOCX, and image policy source intake | Real policy sources rarely arrive only as Markdown; Phase 21 is explicitly scoped to these formats. | MEDIUM | Keep current Markdown path working, but route new file types through a parser registry rather than branching inside `IngestionService`. |
| Parser abstraction with normalized output | The rest of MOCA should not care whether text came from PDF text extraction, DOCX structure, image OCR, or a scanned PDF fallback. | MEDIUM | Define a small adapter contract that returns source metadata, blocks, warnings, parser version, and fatal/nonfatal errors. |
| Durable `DocumentBlock` source-block model | Page, bbox, block type, table/cell metadata, parser version, and OCR confidence cannot be reconstructed reliably from chunk text later. | HIGH | Persist blocks separately from `PolicyChunk`; include stable block IDs, source order, text hash, parser/OCR metadata, and tenant/doc ownership. |
| Block-to-chunk provenance | A retrieved chunk must be traceable back to the exact source blocks that produced it. | HIGH | Add a chunk provenance mapping or JSON sidecar that records block IDs and ranges. Do not replace `EvidenceRefV1.evidence_id`. |
| Page and bounding-box citation metadata | Human reviewers need to verify policy answers against the original source location, especially for scanned or paginated rules. | MEDIUM | Store page number and bbox where available. Missing bbox should be explicit, not silently represented as zero or full page. |
| Table-aware block and chunk handling | Platform policies often encode thresholds, categories, and exceptions in tables; naive line chunking loses row/header meaning. | HIGH | Preserve table ID, row/column indexes, header cells, merged-cell context, and row-level text. Add header context to retrieval `search_text` without mutating canonical citation text. |
| Cell-level citation support where available | For table-derived answers, citing only a broad page is often too weak; reviewers need the exact row/cell that supplied the rule. | HIGH | Cell citation is metadata/provenance. It should enrich source verification, not become a new evidence identity. |
| OCR confidence capture and gating | OCR output can be wrong; low-confidence text should not silently become authoritative policy evidence. | MEDIUM | Store per-block or per-token/page confidence when available. Define thresholds for accepted, degraded, and failed OCR blocks. |
| Parser trace and ingest report | Production ingestion needs debuggability: which parser ran, which fallback triggered, what failed, and how many blocks/chunks were produced. | MEDIUM | Persist trace metadata safe for logs/eval. Exclude raw file blobs, full OCR images, and unsafe raw payloads from prompts. |
| Existing v1.3 retrieval compatibility | Phase 20 established `PolicyChunk.content` as citation text and `search_text` as retrieval-only enrichment. Phase 21 must preserve that contract. | HIGH | `PolicyChunk.content`, `PolicyChunk.search_text`, embeddings, tenant/effective filters, hybrid retrieval, and `EvidenceRefV1` identity must remain compatible. |
| Rollback-safe migration and downgrade behavior | New block/provenance tables are foundational; failed migrations or disabled ingestion should not corrupt existing policy retrieval. | HIGH | Expand schema first, keep read paths tolerant of absent provenance, and include downgrade/preflight tests. |
| Fixture-based parser tests | Parser output must be deterministic enough for regression tests, not manually inspected only. | MEDIUM | Use small synthetic PDF/DOCX/image fixtures with expected block order, page, bbox/cell metadata, confidence buckets, and chunk provenance. |

### Differentiators (Competitive Advantage)

Features that set Phase 21 apart from a basic "upload document and chunk text" pipeline.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Evidence identity plus source-location sidecar | Preserves MOCA's stable `EvidenceRefV1` contract while adding richer source verification. | HIGH | This is the core design advantage: retrieval identity stays stable, provenance becomes inspectable metadata. |
| Table row reconstruction for search and citation | Enables accurate retrieval for threshold-heavy policy tables without claiming table parsing is a later hallucination-control feature. | HIGH | Row text should include relevant headers; source metadata should retain cell coordinates and original cell text. |
| Confidence-aware OCR status | Makes scanned policy ingestion honest: accepted text, degraded text, and failed regions are distinguishable. | MEDIUM | Low confidence should affect ingestion status and tests before it affects answer generation. |
| Parser trace designed for replay/debug, not prompting | Helps diagnose ingestion errors without leaking full raw payloads or parser internals into the LLM context. | MEDIUM | Mirrors v1.3's internal retrieval trace pattern: useful for eval/debug, excluded from prompts and public evidence refs by default. |
| Stable block hashes across re-ingestion | Lets MOCA detect unchanged source regions and reason about provenance when source files are re-imported. | MEDIUM | Hash normalized block text plus source coordinates/structure, not volatile parser timestamps. |
| Partial-ingestion status model | A real source file may parse mostly correctly while some pages/tables fail; treating all failures as binary hides useful progress. | MEDIUM | Per-document status should distinguish success, degraded, failed, and skipped; per-block warnings should be queryable. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem useful but would make Phase 21 too broad or unsafe.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Use an LLM to parse or rewrite policy source text | It looks flexible for messy PDFs and scanned images. | It can change policy wording, erase layout evidence, and make OCR errors non-reproducible. | Use deterministic parser/OCR adapters; keep extracted text, confidence, warnings, and trace. |
| Store raw files, page images, or full extracted payloads in prompts | It seems convenient for later answer generation. | It violates the existing prompt-safety boundary and bloats context with unaudited data. | Store durable source refs, hashes, block text, bbox/cell metadata, and safe trace summaries. |
| Replace `EvidenceRefV1` with page/bbox/cell identity | It makes citations look more precise. | It breaks v1.1/v1.3 evidence identity, approval snapshots, replay assumptions, and existing tests. | Keep `EvidenceRefV1` unchanged; attach source-block provenance as metadata resolved by `doc_key/chunk_id/version`. |
| Treat low-confidence OCR as normal policy text | It maximizes recall and makes ingestion appear successful. | It turns OCR noise into authoritative policy evidence. | Gate OCR by confidence; mark degraded blocks; exclude or quarantine blocks below threshold. |
| Chunk directly from parser text without storing blocks | It is faster to implement. | Page, bbox, table, parser, and OCR metadata are lost permanently, forcing a rewrite for citations. | Persist `DocumentBlock` first, then derive chunks from blocks. |
| Flatten tables into plain paragraphs only | It makes chunks easy to embed. | Header and row/cell semantics are lost, especially for fee, threshold, and exception tables. | Build row-aware text for retrieval while preserving structured table/cell metadata. |
| Ingest business attachments into the policy KB | It reuses the parser for more files. | It mixes business facts with policy evidence and violates the Tool System boundary. | Restrict Phase 21 ingestion to policy source documents only. |
| Build a full document-management CMS | It looks production-like. | It shifts the milestone from ingestion infrastructure to admin product scope. | Provide ingestion CLI/service behavior, persisted reports, and tests; UI can be selected by a separately named future milestone. |

## Feature Dependencies

```
Source file metadata
    -> requires -> Parser registry and adapter selection
        -> requires -> Format-specific parser/OCR adapters
            -> produces -> DocumentBlock records
                -> requires -> Block validation, hashes, parser trace
                    -> feeds -> Table-aware chunker
                        -> produces -> PolicyChunk.content and search_text
                            -> links -> Chunk-to-block provenance
                                -> supports -> page/bbox/cell citation metadata

Existing v1.3 retrieval
    -> requires -> PolicyChunk.content/search_text/embedding compatibility
        -> preserves -> EvidenceRefV1 identity and PolicyKnowledgeService behavior

OCR confidence
    -> gates -> DocumentBlock accepted/degraded/failed status
        -> gates -> whether block text can contribute to chunks

Parser trace
    -> records -> parser version, OCR version, fallback path, warnings, failure modes
        -> must not enter -> prompts or EvidenceRefV1
```

### Dependency Notes

- **Parser registry requires source metadata:** Format, MIME type, file extension, source hash, tenant, `doc_key`, and policy metadata must be known before selecting an adapter.
- **`DocumentBlock` requires parser/OCR adapters:** Blocks are the normalized boundary. Adapters may differ internally, but downstream chunking should consume one block contract.
- **Table-aware chunking requires structured blocks:** Cell and header context cannot be recovered reliably after tables are flattened.
- **Page/bbox/cell citation requires block-to-chunk provenance:** Citation metadata should be resolved from chunk provenance, not guessed from chunk text.
- **OCR confidence gates chunk eligibility:** A low-confidence block should not contribute to `PolicyChunk.content` unless Phase 21 explicitly marks it as degraded and tests that behavior.
- **`PolicyChunk.search_text` depends on v1.3 search-text builder:** Phase 21 may enrich search text with table headers and source-section context, but must keep it retrieval-only.
- **`EvidenceRefV1` depends on stable `PolicyChunk.content`:** Re-ingestion should only bump policy version when canonical content changes, not when parser trace timestamps or non-content metadata change.
- **Rollback safety depends on read-path tolerance:** Retrieval should still work with existing chunks if source-block tables are absent, disabled, or empty during rollout.

## MVP Definition

### Launch With (Phase 21)

Minimum viable Phase 21 behavior needed for v1.4.

- [ ] Parser registry and adapter contract for PDF, DOCX, and image policy sources.
- [ ] Durable `DocumentBlock` or equivalent source-block schema with tenant/doc ownership, source order, block type, page, bbox, table/cell metadata, parser/OCR versions, confidence, and text hash.
- [ ] Ingestion flow that parses sources into blocks before deriving chunks.
- [ ] Table-aware chunking that preserves row/header context and keeps retrieval-only enrichment in `search_text`.
- [ ] Chunk-to-block provenance so each `PolicyChunk` can resolve source page/bbox/cell metadata.
- [ ] OCR confidence thresholds with accepted/degraded/failed outcomes.
- [ ] Parser trace and per-document ingest report with warnings and failure modes.
- [ ] Compatibility tests proving `EvidenceRefV1`, `PolicyChunk.content`, hybrid retrieval filters, and business-tool boundaries remain unchanged.
- [ ] Migration, downgrade, and failed-ingestion rollback coverage.
- [ ] Synthetic parser fixtures for PDF, DOCX, image OCR, scanned/low-confidence OCR, and table extraction.

### Add After Validation (Phase 21 Stretch Only)

Add only if the launch set is stable and tests are passing.

- [ ] Duplicate source-file detection by source hash - useful if repeated imports become noisy.
- [ ] More table-layout fixtures - add complex merged-header and multi-page table cases after the basic row/cell contract is proven.
- [ ] Internal provenance inspection endpoint or CLI report - useful for debugging if it does not become a user-facing CMS.

### Future Consideration (Owner Must Be Named Before Build)

These are not Phase 21 requirements.

- [ ] User-facing document viewer/highlight UI - owner if selected: `Policy Source Review UI` milestone; Phase 21 should only persist the metadata needed for it.
- [ ] Broad document-management workflow for uploads, approvals, lifecycle, and retention - owner if selected: `Policy Source Operations` milestone.
- [ ] Async large-batch ingestion workers - owner if selected: `Ingestion Scale` milestone; require file-volume or latency evidence before planning.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Parser adapter contract | HIGH | MEDIUM | P1 |
| PDF/DOCX/image intake | HIGH | MEDIUM | P1 |
| Durable `DocumentBlock` schema | HIGH | HIGH | P1 |
| Chunk-to-block provenance | HIGH | HIGH | P1 |
| Page/bbox citation metadata | HIGH | MEDIUM | P1 |
| Table-aware chunking | HIGH | HIGH | P1 |
| OCR confidence capture and gating | HIGH | MEDIUM | P1 |
| Parser trace and ingest report | HIGH | MEDIUM | P1 |
| v1.3 retrieval/evidence compatibility tests | HIGH | MEDIUM | P1 |
| Migration/downgrade/rollback coverage | HIGH | HIGH | P1 |
| Cell-level citation support | MEDIUM | HIGH | P2 |
| Stable block hashes across re-ingestion | MEDIUM | MEDIUM | P2 |
| Partial-ingestion status model | MEDIUM | MEDIUM | P2 |
| Duplicate source-file detection | MEDIUM | LOW | P3 |
| Internal provenance inspection report | MEDIUM | LOW | P3 |
| User-facing source document viewer | LOW for Phase 21 | HIGH | P3 |

**Priority key:**
- P1: Must have for Phase 21 launch
- P2: Should have if it fits without weakening the core contract
- P3: Nice to have; defer unless core scope is already stable

## Baseline Feature Analysis

External competitor research was not performed because the request scoped this file to MOCA v1.4 expected behavior and asked to use project context first. The relevant comparison is MOCA's current v1.3 baseline versus the Phase 21 target.

| Feature | Current MOCA v1.3 | Phase 21 Approach |
|---------|-------------------|-------------------|
| Source formats | Markdown text ingestion path. | Add PDF, DOCX, and image policy source parsing through adapters. |
| Source structure | Heading-aware Markdown chunks. | Normalize source files into `DocumentBlock` records before chunking. |
| Citation text | `PolicyChunk.content` is canonical citation text. | Preserve `PolicyChunk.content`; add provenance metadata outside evidence identity. |
| Retrieval enrichment | `PolicyChunk.search_text` is retrieval-only and feeds PostgreSQL full-text/pg_trgm. | Add table/header/source context to `search_text` only where it improves retrieval without changing citation text. |
| Evidence identity | `EvidenceRefV1` uses `doc_key/chunk_id@policy_version` plus text hash. | Keep unchanged; resolve page/bbox/cell metadata through chunk provenance. |
| Trace | Internal hybrid retrieval diagnostics excluded from prompts/API serialization. | Add parser/OCR trace with the same internal/debug-only posture. |
| Boundary protection | Business facts stay in Tool System outputs, not policy chunks. | Keep parser/OCR ingestion restricted to policy sources only. |

## Sources

- `.planning/PROJECT.md` - v1.4 goal, target features, active requirements, and out-of-scope boundaries. Confidence: HIGH.
- `.planning/MILESTONES.md` - v1.3 shipped context and Phase 21 owner scope. Confidence: HIGH.
- `.planning/milestones/v1.3-ROADMAP.md` - Phase 20 decisions and explicit Phase 21 deferrals. Confidence: HIGH.
- `.planning/phases/20-rag-hybrid-retrieval/20-CONTEXT.md` - v1.3 retrieval boundary, deferred OCR/parser/DocumentBlock ownership, and current-code references. Confidence: HIGH.
- `.planning/phases/20-rag-hybrid-retrieval/20-01-postgres-hybrid-retrieval-SUMMARY.md` - shipped search-text, retrieval trace, and `EvidenceRefV1` preservation decisions. Confidence: HIGH.
- `src/rag/ingestion.py`, `src/rag/chunker.py`, `src/db/models.py`, `src/knowledge/schemas.py`, `tests/test_ingestion.py` - current ingestion, chunking, model, and evidence identity behavior. Confidence: HIGH.

No external library or vendor documentation was used. This research recommends feature behavior and dependencies, not a parser/OCR technology stack.

---
*Feature research for: MOCA v1.4 Phase 21 RAG Production Ingestion + OCR*
*Researched: 2026-06-18*
