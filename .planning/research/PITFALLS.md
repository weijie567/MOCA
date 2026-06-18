# Pitfalls Research

**Domain:** MOCA v1.4 Phase 21 RAG Production Ingestion + OCR
**Researched:** 2026-06-18
**Confidence:** HIGH for MOCA contract/integration pitfalls; MEDIUM for parser/OCR engine-specific behavior until Phase 21 selects concrete libraries.

## Executive Scope

Phase 21 should add production parser/OCR ingestion and durable source-block provenance to the existing MOCA RAG system. It must not change the core evidence authority model: `EvidenceRefV1` remains canonical policy evidence, business facts remain Tool System outputs, memory remains contextual only, and v1.3 `search_text` remains retrieval-only enrichment.

The current implementation is intentionally simple: `src/rag/ingestion.py` reads UTF-8 Markdown, `src/rag/chunker.py` creates stable heading-based chunks, `PolicyChunk.content` is citation text, `PolicyChunk.search_text` is retrieval-only, and `EvidenceRefV1` hashes the supplied chunk text. Phase 21's main danger is not "can we parse PDFs?" but "can we parse real policy sources without breaking evidence identity, provenance, security, rollback, and the existing retrieval boundary?"

The pitfalls below are scoped to Phase 21 only. They explicitly exclude Phase 22 semantic verifier / `MaterialClaim`, Phase 23 reranker / query rewrite, and external search backend implementation.

## Critical Pitfalls

### Pitfall 1: Parser/OCR Text Replaces Canonical Citation Text

**What goes wrong:**
OCR-cleaned text, table-expanded text, parser normalization, or v1.3 `search_text` starts replacing `PolicyChunk.content`. `EvidenceRefV1.text_hash` then hashes text that is not the stable citation text users see, breaking replay, approval snapshots, citation validation, and existing tests that assume raw chunk content is the evidence body.

**Why it happens:**
Production ingestion wants better retrieval text, so developers collapse "citation text", "search text", and "parser-enriched text" into one field. This is tempting for tables and OCR because enriched text often retrieves better than the visible source text.

**How to avoid:**
Keep three separate surfaces:

| Surface | Purpose | May include enrichment? | May feed `EvidenceRefV1.text_hash`? |
|---------|---------|--------------------------|--------------------------------------|
| `PolicyChunk.content` | citation text shown/verified as policy evidence | No, except deterministic visible-source cleanup defined by Phase 21 | Yes |
| `PolicyChunk.search_text` | retrieval-only sparse/fuzzy text | Yes: title, section, table headers, OCR alternatives, domain tokens | No |
| `DocumentBlock` metadata | page/bbox/cell/parser/OCR provenance | Yes: parser trace, confidence, source-block refs | No |

If OCR changes visible source text, treat it as a policy content change and bump policy version. If only parser trace metadata changes, do not silently change evidence text.

**Warning signs:**
- Tests assert only retrieval quality, not `text_hash`.
- `EvidenceRefV1.build(..., text=chunk.search_text)` appears anywhere.
- Table headers or OCR alternatives appear in `PolicyChunk.content` only because they are useful for search.
- `search_text` or parser trace fields appear in API evidence projections.

**Phase to address:**
Phase 21.

---

### Pitfall 2: `DocumentBlock` Becomes a Second Evidence Schema

**What goes wrong:**
Source-block refs such as `page=2,bbox=...` become directly usable as policy evidence, or snapshots/replay/tools define reduced evidence variants because block metadata feels more precise than chunk identity. This weakens the existing contract that all policy evidence authority flows through canonical `EvidenceRefV1`.

**Why it happens:**
Page/bbox/cell provenance looks like a better citation object than `doc_key/chunk_id@policy_version`, especially for OCR highlights. Without a clear rule, implementers create `SourceRef`, `BlockEvidenceRef`, or `CitationRef` variants and let downstream code choose between them.

**How to avoid:**
Make `DocumentBlock` provenance subordinate to `PolicyChunk`:

- `EvidenceRefV1` remains the only policy evidence ref returned by `PolicyKnowledgeService`.
- `DocumentBlock` rows can be linked from chunks via `source_block_refs`, but they cannot authorize policy claims, actions, memory, or replay by themselves.
- API/debug projections may show page/bbox/cell data as citation display metadata, but snapshot/hash builders still consume canonical `EvidenceRefV1`.
- Add import/grep guards preventing new evidence schemas from snapshot, replay, action, memory, or tool contracts.

**Warning signs:**
- A new schema contains `tenant_id`, `doc_key`, `chunk_id`, `policy_version`, and `text_hash` but is not `EvidenceRefV1`.
- `DocumentBlock` IDs appear in action safety snapshots without the matching canonical evidence refs.
- `PolicyKnowledgeService.search()` returns block refs instead of evidence refs.

**Phase to address:**
Phase 21.

---

### Pitfall 3: Unstable Block and Chunk Identity Across Re-ingestion

**What goes wrong:**
Parser version changes, OCR nondeterminism, page ordering differences, or table extraction changes cause block IDs and chunk IDs to churn. Existing citations and eval cases become stale even when source content did not materially change. Worse, a failed parse can bump `PolicyDocument.version` or delete old chunks before replacement is complete.

**Why it happens:**
Current `chunk_markdown()` derives chunk IDs from section order. Parser/OCR ingestion introduces more moving parts: page boundaries, layout blocks, cells, confidence thresholds, and engine versions. If IDs are based on raw iteration order alone, small parser changes cascade into evidence identity changes.

**How to avoid:**
Define Phase 21 identity policy before coding:

- Stable block ID inputs: tenant, doc key/version, page number, block type, normalized visible text hash, and deterministic within-page order.
- Stable chunk ID inputs: existing doc key plus deterministic chunk index/part policy, with explicit version bump when citation text changes.
- Parser/OCR version and confidence belong in parser trace, not evidence identity unless they changed visible citation text.
- Re-ingestion remains all-or-nothing: parse, OCR, chunk, build search text, and embed before deleting old chunks/blocks; write blocks/chunks/doc update in one transaction.
- Keep the current row lock pattern from `IngestionService.get_by_doc_key_for_update()`.

**Warning signs:**
- Re-running ingestion on the same fixture changes chunk IDs or evidence IDs.
- Parser version upgrades rewrite chunks without a content-diff decision.
- `delete_by_document_id()` runs before parse/OCR/embed has fully succeeded.
- Rollback tests cover chunks but not blocks.

**Phase to address:**
Phase 21.

---

### Pitfall 4: Table Flattening Destroys Policy Semantics

**What goes wrong:**
Tables are converted into plain text rows that lose headers, merged cells, footnotes, row labels, or column relationships. Retrieval returns a chunk, but the citation no longer proves the rule because the condition/value/header context is missing.

**Why it happens:**
Generic PDF/DOCX extractors often emit text in visual order, not semantic table order. Developers then feed that text through the existing Markdown chunker, which was not designed to preserve cell provenance.

**How to avoid:**
Represent tables as first-class source blocks:

- Persist `block_type` values such as `paragraph`, `heading`, `table`, `table_row`, `table_cell`, `image_ocr`, and `footnote`.
- For cells, persist `table_id`, row/column indexes, row/column spans, header refs, and page/bbox where available.
- Build citation text that remains human-readable and faithful, for example `表1｜退款场景=仅退款｜处理时效=24小时内审核`.
- Put extra header synonyms and surrounding section labels into `search_text`, not into `PolicyChunk.content` unless they are part of the faithful table citation.
- Add table fixtures with merged cells, repeated headers, and footnotes.

**Warning signs:**
- Table chunks contain values like `24小时` with no column/header context.
- Cell bbox data exists but cannot map a chunk back to the source table.
- Eval passes keyword retrieval but manual citation inspection cannot verify the answer.

**Phase to address:**
Phase 21.

---

### Pitfall 5: OCR Confidence Is Treated as Policy Confidence

**What goes wrong:**
Low-confidence OCR text enters policy chunks as if it were reliable, or OCR confidence is mixed into `EvidenceRefV1.score` / `KnowledgeSearchResult.best_score`. The agent may cite misread policy text as strong evidence.

**Why it happens:**
OCR engines often expose confidence values, and it is tempting to reuse them as retrieval scores or hide them in parser metadata without deciding how low-confidence text affects policy trust.

**How to avoid:**
Define OCR confidence as ingestion quality metadata only:

- Store confidence at block/cell level with `ocr_engine`, `ocr_engine_version`, `language`, and preprocessing metadata.
- Set explicit thresholds: below a hard floor, exclude from policy chunks; in a gray zone, ingest with `needs_review` / `low_confidence` flags and do not allow strong-evidence behavior without reviewed text.
- Never map OCR confidence to `EvidenceRefV1.score`; retrieval score remains retrieval confidence.
- Emit ingestion reports that count low-confidence blocks and rejected pages.

**Warning signs:**
- `EvidenceRefV1.score` changes when OCR confidence changes but retrieval ranking does not.
- Low-confidence OCR output has no review or exclusion path.
- Golden fixtures with deliberately noisy scans still produce strong policy evidence.

**Phase to address:**
Phase 21.

---

### Pitfall 6: Raw Parser Payloads Leak Into Prompts, Logs, API, or Durable Tables

**What goes wrong:**
Raw PDF bytes, DOCX XML, image bytes, full parser JSON, file paths, or OCR debug dumps are stored in prompt-visible state, trace events, API responses, or broad JSONB columns. This can leak sensitive source material, hidden content, filesystem paths, parser internals, or prompt-injection payloads.

**Why it happens:**
Parser debugging is painful, so developers persist "raw_payload" to make failures inspectable. This repeats a problem MOCA already guarded against in memory and trace work: raw payloads are convenient but become authority, privacy, and security debt.

**How to avoid:**
Persist only bounded, typed, sanitized metadata:

- `DocumentBlock` stores visible text and necessary provenance fields, not raw file bytes or full parser output.
- Ingestion trace stores parser decision summaries, page counts, error codes, timings, confidence histograms, and sanitized failure reasons.
- Store source files outside prompt/API surfaces if retained at all; use generated storage names, access control, retention, and content hashes.
- Reuse redaction guard patterns: forbid keys such as `raw`, `raw_payload`, `prompt`, `arguments`, `bytes`, `xml`, and full `parser_output` in trace/API schemas.

**Warning signs:**
- New JSONB columns are named `raw_payload`, `parser_output`, `ocr_json`, or `debug_dump`.
- Tests assert parsing succeeds but do not assert absence of raw payloads.
- API response snapshots include parser trace internals.

**Phase to address:**
Phase 21.

---

### Pitfall 7: Uploaded Source Files Are Treated as Benign Inputs

**What goes wrong:**
PDF/DOCX/image files exploit parser libraries, exhaust CPU/memory/storage, overwrite paths, or carry active content/macros. Even if Phase 21 ingestion is CLI-only at first, the parser boundary still consumes untrusted source files.

**Why it happens:**
Ingestion feels like an offline admin workflow, so validation and sandboxing get deferred. File type checks rely on extension or `Content-Type` alone, and parser libraries run with broad filesystem/network privileges.

**How to avoid:**
Implement defense in depth around parser inputs:

- Allowlist exact file types needed for Phase 21: PDF, DOCX, and selected image formats.
- Validate extension, decoded filename, MIME sniffing, and file signature; do not trust `Content-Type` alone.
- Generate storage filenames; never use uploaded filename as a path.
- Enforce file size, page count, image dimensions, decompression ratio, parse timeout, and memory limits.
- Disable network access and active content where the parser supports it; run risky parsing in a restricted process/container if feasible.
- Record safe failure codes instead of raw exceptions.

**Warning signs:**
- Parser accepts any path under a directory without extension/signature validation.
- Tests only cover well-formed small fixtures.
- Malformed PDF/DOCX/image files crash the process instead of returning failed ingestion reports.

**Phase to address:**
Phase 21.

---

### Pitfall 8: Indirect Prompt Injection From OCR/Parser Text

**What goes wrong:**
Policy source files contain visible or hidden instructions such as "ignore previous instructions", white-on-white PDF text, comments, alt text, or image text. Once ingested, this content can influence generation, memory, or tool behavior when cited as evidence.

**Why it happens:**
Retrieved policy chunks are treated as trusted because they came from the knowledge base. In reality, parser/OCR text is external content and must remain data, not instructions. OCR also makes hidden or incidental text easier to ingest accidentally.

**How to avoid:**
Treat all parsed/OCR text as untrusted policy data:

- Delimit evidence text in prompts and keep system/developer instructions separate from source content.
- Do not allow source text or parser trace to set tool arguments, permissions, approval state, memory authority, or routing.
- Add ingestion fixtures with injection phrases in visible text, hidden PDF text, DOCX comments, and image OCR output.
- Verify the generated prompt includes only verified evidence text and existing guardrails, and that action/memory/business fact paths ignore source instructions.
- Consider filtering or flagging hidden text/comments as parser metadata requiring review rather than direct policy evidence.

**Warning signs:**
- Source text appears outside evidence delimiters in prompts.
- Parser trace or OCR text is summarized into memory.
- Prompt-injection fixtures change route decisions or tool calls.

**Phase to address:**
Phase 21.

---

### Pitfall 9: Source-Block Provenance Is Not Tenant-Scoped

**What goes wrong:**
`DocumentBlock` or source-block refs are globally addressable, so a chunk from one tenant can point to block metadata or source file coordinates from another tenant. This causes citation leakage even if retrieval itself remains tenant-scoped.

**Why it happens:**
Current retrieval filters are enforced on `PolicyChunk`; new block tables may be added as "metadata" and not receive the same tenant/doc scope constraints.

**How to avoid:**
Make source-block scope explicit:

- Every source document, block, table, and chunk-block mapping carries `tenant_id` and `doc_id`.
- Use composite uniqueness that includes tenant/doc/version where applicable.
- All block lookup repository methods require trusted `tenant_id`.
- API citation expansion must fetch blocks through `(tenant_id, doc_key, chunk_id/source_block_id)` scoped joins, never by bare block ID.

**Warning signs:**
- `source_block_id` is a UUID lookup without tenant criteria.
- Tests cover retrieval tenant filters but not citation metadata expansion.
- Block tables lack tenant indexes or foreign-key path to tenant-owned `PolicyDocument`.

**Phase to address:**
Phase 21.

---

### Pitfall 10: Page/Bbox Coordinates Are Stored Without a Canonical Coordinate System

**What goes wrong:**
Citation highlights point to the wrong place because parsers disagree on coordinate origin, units, page rotation, crop boxes, DPI, or image preprocessing. Users see a citation but cannot visually verify the policy.

**Why it happens:**
Page/bbox data looks simple until multiple source formats are supported. PDF coordinates, image pixels, OCR bounding boxes, and DOCX layout projections are not automatically comparable.

**How to avoid:**
Define a canonical `SourceBox` contract:

- `page_number` is 1-based and source-visible.
- `bbox` uses one coordinate convention, with documented origin, unit, and normalization.
- Store page width/height, rotation, coordinate space, and parser-provided confidence.
- Reject or omit bbox when the parser cannot guarantee the coordinate convention.
- Keep text provenance usable even when bbox is absent.

**Warning signs:**
- Bbox is stored as a raw list with no unit/origin fields.
- Rotated pages or cropped PDFs have no fixture.
- UI/API consumers need parser-specific logic to interpret boxes.

**Phase to address:**
Phase 21.

---

### Pitfall 11: Parser Trace Becomes User-Facing Authority

**What goes wrong:**
Parser decisions such as selected engine, fallback OCR path, confidence, or failure modes appear in prompts/API as if they were evidence. The agent may cite "OCR confidence 0.91" or "parser chose table mode" as policy support.

**Why it happens:**
Trace metadata is useful for debugging and eval. Without strict serialization rules, it leaks into the same surfaces as evidence and business facts.

**How to avoid:**
Keep ingestion trace internal:

- Define a typed ingestion trace schema with `exclude=True` or internal-only API projections.
- Include trace in admin/debug/eval outputs only after redaction.
- Never serialize parser trace into `EvidenceRefV1`, `KnowledgeSearchResult.summary`, memory, action safety snapshots, or business tool results.
- Add tests matching Phase 20's hybrid trace exclusion pattern.

**Warning signs:**
- Parser/OCR trace fields appear in `EvidenceRefV1.model_dump()`.
- Agent prompt snapshots contain parser version, raw error messages, or OCR engine debug text.
- A downstream node branches on parser trace instead of retrieval status/evidence refs.

**Phase to address:**
Phase 21.

---

### Pitfall 12: Phase 21 Accidentally Absorbs Phase 22/23/RAG-5 Scope

**What goes wrong:**
Parser/OCR work expands into semantic claim verification, `MaterialClaim`, query rewrite, reranking, external search backend abstractions, or large-scale indexing decisions. The phase becomes too broad and muddles ownership.

**Why it happens:**
Once richer source-block provenance exists, it is natural to want verifier, reranker, and backend upgrades immediately. But v1.3 intentionally deferred those with named owners.

**How to avoid:**
Keep Phase 21 acceptance narrow:

- Build parser/OCR abstraction, `DocumentBlock`/source-block provenance, table-aware chunking, ingestion trace, rollback, and security tests.
- Do not implement `MaterialClaim`, semantic support verifier, reranker/query rewrite, Vespa/OpenSearch, or full external `SearchBackend`.
- If a future-facing field is needed, add a documented deferral note and owner phase rather than partial behavior.
- Add negative migration/source checks similar to Phase 20's "no DocumentBlock/OCR/MaterialClaim/Vespa/OpenSearch" guard, but updated for Phase 21: DocumentBlock/OCR allowed; MaterialClaim/verifier/reranker/external backend forbidden.

**Warning signs:**
- Requirements mention "faithfulness", "claim support", "rerank", "query rewrite", "cross-encoder", "OpenSearch", or "SearchBackend" as Phase 21 deliverables.
- Parser tasks depend on verifier/reranker tasks.
- Tests validate answer faithfulness rather than ingestion/provenance integrity.

**Phase to address:**
Phase 21, with explicit deferrals to Phase 22, Phase 23, and Phase RAG-5.

---

### Pitfall 13: Reusing Markdown Chunker Assumptions for Real Documents

**What goes wrong:**
PDF/DOCX/image extraction is forced through `chunk_markdown()` without preserving headings, reading order, pages, footnotes, tables, or image OCR boundaries. Chunks look valid but provenance cannot be reconstructed.

**Why it happens:**
The current chunker is small and reliable for Markdown; extending it feels cheaper than adding a source-block layer. But Phase 21's requirement is block-to-chunk provenance, not only text splitting.

**How to avoid:**
Introduce a parser-neutral block pipeline:

```text
source file -> ParsedDocument -> DocumentBlock[] -> ChunkPlan[] -> PolicyChunk[] + chunk_block_links
```

Keep `chunk_markdown()` as one parser path or compatibility fallback, not the central abstraction for all formats. Chunking should consume structured blocks and emit traceable chunk-to-block mappings.

**Warning signs:**
- `DocumentBlock` is generated after chunks instead of before them.
- Source page/bbox/cell refs cannot explain how a chunk was formed.
- Chunking tests assert content only, not source-block mappings.

**Phase to address:**
Phase 21.

---

### Pitfall 14: Business Facts Leak Into Policy Ingestion

**What goes wrong:**
Parser/OCR ingestion starts accepting merchant tickets, order screenshots, refund case exports, or operational spreadsheets as "documents" and turns them into policy chunks. This contaminates policy evidence with current business facts.

**Why it happens:**
Real document ingestion often starts from mixed folders. OCR makes screenshots and exports easy to parse, and "more searchable text" feels useful.

**How to avoid:**
Enforce policy-source classification:

- Phase 21 ingestion accepts policy source files only.
- Manifest metadata must require `doc_type`, `risk_level`, `effective_date`, and policy source ownership; reject business objects and case artifacts.
- `DocumentBlock` belongs to policy documents, not Tool System resources.
- Business facts continue to be fetched through `BusinessToolService` and `ToolResultV2`.

**Warning signs:**
- Ingestion manifests include `order_no`, `refund_case_no`, `ticket_id`, merchant screenshots, or live system exports.
- `DocumentBlock` has `resource_type` values like `order` or `refund_case`.
- Search results can cite a business record as `EvidenceRefV1`.

**Phase to address:**
Phase 21.

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store full parser JSON in a JSONB column | Easy debugging | Raw payload leakage, schema drift, impossible redaction, prompt-injection persistence | Never for default Phase 21 path; sanitized trace summaries only |
| Use parser output order as block/chunk identity | Fast implementation | Evidence churn after parser upgrades or minor layout changes | Only in throwaway tests, not persisted identity |
| Flatten tables to newline-separated text | Quick retrieval | Lost header/cell semantics and unverifiable citations | Only for non-policy decorative tables explicitly excluded from evidence |
| Treat OCR text as normal policy text regardless of confidence | More chunks, fewer rejects | Misread rules become citable policy evidence | Never without threshold/review policy |
| Add page/bbox as loose dict metadata on chunks | Minimal migration | No validation, no coordinate contract, no cross-tenant safeguards | Only for experimental local branch, not roadmap acceptance |
| Put parser trace in API response for convenience | Easier frontend debugging | Debug metadata becomes public contract and possible authority | Internal admin/debug endpoints only, redacted |
| Extend `EvidenceRefV1` with block fields directly | One object to pass around | Breaks canonical evidence compatibility with snapshots/replay/action code | Avoid; use subordinate display/provenance metadata |
| Let Phase 21 implement claim verifier/reranker while touching retrieval | Feels coherent | Scope creep and owner confusion with Phase 22/23 | Never in Phase 21 |

## Integration Gotchas

Common mistakes when connecting parser/OCR ingestion to existing MOCA surfaces.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `IngestionService` | Delete old chunks before parser/OCR/embed succeeds | Parse/OCR/chunk/embed first; lock doc row; commit doc/blocks/chunks atomically |
| `PolicyDocument.version` | Bump version for parser metadata-only changes, or fail to bump when OCR text changes | Version changes track citation text/content changes; parser trace changes remain metadata unless citation text changes |
| `PolicyChunk.content` | Store table-expanded or OCR-enriched search text | Store faithful citation text; put retrieval enrichment in `search_text` |
| `PolicyChunk.search_text` | Treat as prompt/citation text because it retrieves better | Keep retrieval-only; tests assert it is excluded from `EvidenceRefV1` and prompt evidence content |
| `DocumentBlock` table | Use bare `source_block_id` lookups | Scope every lookup by trusted tenant/doc/version and join through `PolicyDocument` |
| Chunk-to-block mapping | Store only first block ref | Store ordered source refs with offsets/spans where practical, especially for chunks spanning multiple blocks |
| Parser abstraction | Return raw library objects | Return typed `ParsedDocument` / `DocumentBlock` models with bounded fields |
| OCR engine | Ignore language, preprocessing, confidence, and rotation metadata | Persist engine/version/language/confidence/preprocessing trace separately from evidence |
| API citation display | Fetch page/bbox metadata without tenant check | Expand citation display through scoped repository methods only |
| Agent prompt assembly | Include parser trace or hidden source comments | Include only verified evidence content through existing KnowledgeService path |
| Eval scripts | Measure only Hit@5 | Add fixture-level provenance checks: block refs, table headers, bbox validity, low-confidence behavior, rollback |
| Migrations | Add non-null columns without backfill/downgrade | Create reversible migration with backfill or nullable rollout; downgrade drops indexes/links before tables |

## Performance Traps

Patterns that work with small fixtures but fail for real policy source files.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous OCR inside request/agent path | Chat/search latency spikes; timeouts | Keep Phase 21 ingestion offline/admin path; retrieval uses persisted chunks only | Any multi-page scan or image-heavy PDF |
| Embedding every block instead of final chunks | High token/cost usage; duplicate vectors | Embed selected citation chunks; keep block text for provenance/search construction | Documents with dense tables or scanned pages |
| Loading whole PDFs/images into memory repeatedly | Worker OOM, slow ingest | Stream where possible; enforce size/page/dimension limits; isolate parser process | Large PDFs, high-DPI scans, image batches |
| No page/image limits | Parser jobs hang or exhaust disk | Max pages, max pixels, max extracted characters, timeout per file/page | Malformed or intentionally oversized files |
| Re-OCR unchanged documents | Slow reimports and unnecessary churn | Use source file hash + parser config version to skip or classify unchanged work | Re-running ingestion on full corpus |
| Storing duplicate text in document, blocks, chunks, trace, and logs | DB bloat; backup size growth | Store canonical text once where possible; trace stores summaries; use hashes/refs | Corpus grows beyond demo fixtures |
| Missing indexes on block refs | Citation expansion is slow | Index `(tenant_id, doc_id, source_block_id)` and chunk-block mapping keys | More than hundreds of chunks/blocks |
| Table cell explosion without chunk planning | Too many tiny chunks; poor retrieval | Chunk rows/groups with header context; store cell provenance separately | Large policy matrices |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Trusting file extension or `Content-Type` | Spoofed files reach parser; parser exploit or DoS | Extension allowlist plus MIME/signature validation, size/page limits, parser sandbox |
| Using original filenames as storage paths | Path traversal, overwrite, sensitive path leakage | Generate storage names; keep original filename as sanitized display metadata only |
| Persisting raw parser/OCR payloads | Sensitive data, hidden prompts, filesystem paths, or malware indicators leak | Store bounded typed metadata and hashes; forbid raw/debug payload keys in schemas |
| Running parsers with broad privileges | Parser CVE can read files or reach network | Restricted process/container, no network, least filesystem access, time/memory limits |
| Ingesting hidden PDF/DOCX text/comments as trusted policy | Indirect prompt injection or invisible malicious instruction becomes evidence | Detect/flag hidden/comment/alt text; treat as untrusted metadata requiring review |
| Letting OCR/parser text influence tools or memory | Source document can manipulate action, approval, or future sessions | Parsed text only enters policy evidence path; no tool authority, memory authority, or business fact refs |
| Cross-tenant block lookup | Citation metadata leaks another tenant's document page/bbox/text | Tenant-scoped block tables and repository methods; negative tests |
| Exposing parser errors verbatim | Internal paths/library versions/source snippets leak | Safe error codes and sanitized messages in ingestion reports |
| Accepting archives or embedded objects implicitly | Zip bombs, macro/content execution, nested active content | Phase 21 accepts direct PDF/DOCX/image only; inspect DOCX zip safely; reject unexpected embedded active content |
| Treating parser/OCR confidence as authorization confidence | Misread source text supports risky recommendations | OCR confidence gates ingestion quality only; `EvidenceRefV1.score` remains retrieval confidence |

## UX Pitfalls

Phase 21 is mostly backend, but citation/provenance quality affects operator trust.

| Pitfall | User/Operator Impact | Better Approach |
|---------|----------------------|-----------------|
| Citation says only `chunk_003` after adding page/bbox | User cannot inspect real source | Show stable evidence ref plus page/table/cell display metadata where available |
| Low-confidence OCR silently appears as normal text | Operator trusts misread policy | Surface ingestion warnings and block counts; require review/exclusion policy |
| Parser failures are all "failed" | Maintainer cannot fix source issues | Use safe structured error codes: unsupported_type, parse_timeout, low_confidence, no_blocks, malformed_file |
| Bbox highlights are wrong or absent without explanation | Citation UI feels unreliable | Omit bbox when uncertain; still show page/source text; test coordinate fixtures |
| Reimport changes many chunk IDs without report | Eval/replay/citation drift surprises maintainers | Ingestion report shows content version change, chunk churn count, block churn count, skipped unchanged docs |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical Phase 21 verification.

- [ ] **Parser abstraction:** It returns text for PDF/DOCX/image fixtures, but not typed `DocumentBlock` rows with parser version, page, block type, and trace metadata. Verify typed model/schema tests.
- [ ] **OCR support:** It extracts text, but low-confidence blocks are not gated. Verify noisy OCR fixture produces rejected or review-flagged blocks.
- [ ] **DocumentBlock persistence:** Blocks exist, but source refs are not tenant-scoped. Verify cross-tenant block expansion returns no data.
- [ ] **Chunk provenance:** Chunks link to source blocks, but only the first block is stored. Verify multi-block chunk maps to ordered block refs/spans.
- [ ] **Table-aware chunking:** Tables retrieve, but headers/cell context are missing from citation text. Verify merged-cell/header fixture preserves context.
- [ ] **Citation identity:** Page/bbox works, but `EvidenceRefV1` changed shape or hash source. Verify existing EvidenceRefV1 contract tests still pass unchanged.
- [ ] **Search quality:** `search_text` includes parser enrichment, but citation content also changed. Verify `PolicyChunk.content != search_text` when enrichment is present and hash uses content.
- [ ] **Rollback:** Failed parser/OCR insert leaves partial blocks or bumped doc version. Verify transaction rollback restores old doc/chunks/blocks.
- [ ] **Raw payload controls:** Parser debug fields help tests, but raw payload keys are persisted. Verify schema/trace/API forbidden-key tests.
- [ ] **Security fixtures:** Happy path fixtures pass, but malformed/oversized/hidden-prompt files are untested. Verify rejection and safe error reports.
- [ ] **Scope discipline:** Phase 21 mentions verifier/reranker because provenance is ready. Verify roadmap requirements defer `MaterialClaim`, verifier, reranker/query rewrite, and external backend to named phases.
- [ ] **Downgrade path:** Migration upgrades locally, but downgrade leaves block indexes/tables or breaks existing chunks. Verify migration upgrade/downgrade/reupgrade in disposable DB.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Citation text/hash polluted by search/parser enrichment | HIGH | Freeze writes, identify affected versions, restore `PolicyChunk.content` from source or backup, rebuild `search_text`, re-embed if needed, regenerate evidence/hash golden tests |
| Block IDs/chunk IDs unstable after parser change | MEDIUM/HIGH | Introduce deterministic identity policy, write migration or reimport report, bump policy versions only for changed citation text, update eval fixtures intentionally |
| Raw parser payload persisted | HIGH | Stop exposing affected endpoints, add redaction migration, purge raw columns/logs if feasible, replace with sanitized trace summaries and forbidden-key tests |
| Low-confidence OCR already indexed | MEDIUM | Add confidence thresholds, mark/reject affected blocks, re-chunk/re-embed reviewed text, add noisy scan regression fixtures |
| Table semantics lost in chunks | MEDIUM | Add table block model/header extraction, reprocess table documents, update chunk text/search text generation, add manual citation review fixtures |
| Cross-tenant provenance leak | HIGH | Patch repository/API scoping immediately, audit access logs, add tenant_id/index constraints, backfill tenant scope if missing |
| Parser failure leaves partial state | MEDIUM | Repair affected docs by reimporting last known good version, wrap doc/block/chunk writes in one transaction, add rollback tests |
| Phase 21 scope creep into verifier/reranker | LOW/MEDIUM | Split requirements, delete partial future-scope code or mark behind no-op deferral, update roadmap owner notes |

## Pitfall-to-Phase Mapping

How Phase 21 should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Parser/OCR text replaces canonical citation text | Phase 21 | Unit tests assert `PolicyChunk.content` is citation text, `search_text` is retrieval-only, and `EvidenceRefV1.text_hash` hashes content |
| `DocumentBlock` becomes second evidence schema | Phase 21 | Contract/import/serialization tests assert `PolicyKnowledgeService` returns only `EvidenceRefV1`; block metadata is subordinate |
| Unstable block/chunk identity | Phase 21 | Same-fixture reingestion produces stable block/chunk refs; parser-only trace changes do not silently mutate evidence |
| Table flattening destroys semantics | Phase 21 | Table fixtures with merged cells/header rows produce chunks with header context and cell provenance |
| OCR confidence treated as policy confidence | Phase 21 | Low-confidence OCR fixture is rejected or review-flagged; `EvidenceRefV1.score` unaffected by OCR confidence |
| Raw parser payload leakage | Phase 21 | Schema/API/trace forbidden-key tests for raw payloads, bytes, full parser output, prompts, and unsafe paths |
| Unsafe source files | Phase 21 | Malformed/oversized/spoofed file fixtures return safe failed ingestion reports without process crash |
| Indirect prompt injection from parsed text | Phase 21 | Hidden/visible prompt-injection fixtures do not alter routing, tool calls, memory writes, or action authority |
| Tenant scope leak in provenance | Phase 21 | Cross-tenant block/chunk citation expansion tests fail closed |
| Non-canonical bbox coordinates | Phase 21 | Golden page/bbox fixtures validate coordinate origin/unit/page rotation handling; unsupported bbox omitted safely |
| Parser trace becomes authority | Phase 21 | Prompt/API/EvidenceRefV1 serialization tests exclude parser trace by default |
| Phase 22/23/RAG-5 scope creep | Phase 21 planning gate | Grep/migration/requirement checks forbid `MaterialClaim`, verifier, reranker/query rewrite, external backend deliverables |
| Markdown chunker assumptions reused | Phase 21 | Parser-neutral block pipeline tests prove blocks precede chunks and chunk-block mappings are persisted |
| Business facts leak into policy ingestion | Phase 21 | Manifest validation rejects order/refund/ticket artifacts; no `business_fact_refs` in policy evidence or blocks |

## Recommended Phase 21 Verification Gates

Use these gates as acceptance criteria inputs for the Phase 21 plan.

1. **Contract preservation gate:** Existing `EvidenceRefV1`, `PolicyKnowledgeService`, ingestion content/search text, and hybrid retrieval tests continue to pass unchanged.
2. **Parser fixture gate:** PDF, DOCX, image, table, multi-page, rotated page, and malformed file fixtures produce deterministic `DocumentBlock` output or safe failures.
3. **OCR quality gate:** OCR confidence thresholds are tested with high-confidence, low-confidence, mixed-language, and noisy-image fixtures.
4. **Provenance gate:** Every persisted `PolicyChunk` from parser/OCR ingestion has ordered source-block refs; page/bbox/cell refs are validated when present and safely absent when unsupported.
5. **Rollback gate:** Parser failure, OCR timeout, embedding mismatch, and DB insert failure roll back document version, blocks, chunks, and chunk-block links.
6. **Security gate:** Spoofed extension, oversized file, decompression/zip-style hazard, hidden prompt text, raw payload, and cross-tenant provenance tests fail closed.
7. **Scope gate:** Phase 21 migration/source scan allows parser/OCR/DocumentBlock but forbids `MaterialClaim`, semantic verifier, reranker/query rewrite, Vespa/OpenSearch, and full external `SearchBackend`.

## Sources

- `.planning/PROJECT.md` — v1.4 active scope, current/validated requirements, and safety boundaries. Confidence: HIGH.
- `.planning/MILESTONES.md` — v1.3 shipped status and explicit Phase 21/22/23/RAG-5 deferral owners. Confidence: HIGH.
- `.planning/milestones/v1.3-ROADMAP.md` — Phase 20 decisions and deferred ingestion/OCR scope. Confidence: HIGH.
- `.planning/phases/20-rag-hybrid-retrieval/20-SECURITY.md` — existing security controls for retrieval scope, citation identity, search text, and trace exclusion. Confidence: HIGH.
- `src/rag/ingestion.py` — current Markdown ingestion, row locking, version bump, chunk persistence, search text separation, rollback behavior. Confidence: HIGH.
- `src/rag/chunker.py` — current heading-based Markdown chunking and chunk ID behavior. Confidence: HIGH.
- `src/knowledge/schemas.py` and `docs/contract-spec.md` — canonical `EvidenceRefV1` and evidence boundary. Confidence: HIGH.
- `src/db/models.py` — current `PolicyDocument` / `PolicyChunk` schema. Confidence: HIGH.
- `tests/test_ingestion.py`, `tests/knowledge/test_facade_status.py`, `src/knowledge/retrieval.py`, `src/knowledge/service.py` — existing verification pattern for content hashing, versioning, retrieval evidence refs, and verified evidence contents. Confidence: HIGH.
- OWASP File Upload Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html — defense-in-depth controls for upload validation, storage, size limits, AV/CDR, parser library updates. Confidence: HIGH.
- OWASP Unrestricted File Upload: https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload — examples of parser exploits, file overwrite/path, DoS, sensitive file disclosure, and malicious uploaded content. Confidence: HIGH.
- OWASP LLM Prompt Injection Prevention Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html — direct/indirect prompt injection through documents and hidden content. Confidence: HIGH.
- OWASP AI Agent Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html — agent risks from untrusted external data, tool abuse, data exfiltration, memory poisoning, and excessive agency. Confidence: HIGH.
- OWASP Top 10 for Large Language Model Applications: https://owasp.org/www-project-top-10-for-large-language-model-applications/ — LLM prompt injection, insecure output handling, model DoS, sensitive information disclosure, excessive agency. Confidence: HIGH.

---
*Pitfalls research for: MOCA v1.4 Phase 21 RAG Production Ingestion + OCR*
*Researched: 2026-06-18*
