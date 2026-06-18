---
phase: "21-rag-production-ingestion-ocr"
plan: "01a"
title: "Source Block Schema Repositories And Boundary Guards"
type: "execute"
wave: 3
depends_on: ["21-01"]
files_modified:
  - "src/db/models.py"
  - "src/db/migrations/versions/015_rag_production_ingestion_ocr.py"
  - "src/repositories/document_block_repo.py"
  - "src/repositories/rag_ingestion_job_repo.py"
  - "tests/rag/phase21_xfail_inventory.py"
  - "tests/rag/test_document_block_schema.py"
  - "tests/test_rag_production_migration.py"
  - "tests/knowledge/test_phase21_boundaries.py"
  - "tests/knowledge/test_evidence_projection.py"
  - "tests/knowledge/test_hybrid_retrieval.py"
  - "tests/approvals/test_snapshots.py"
autonomous: true
requirements: [PROV-01, PROV-04, OCR-01, INGEST-01, INGEST-04, BOUNDARY-01, BOUNDARY-03, BOUNDARY-04]
requirements_addressed: [PROV-01, PROV-04, OCR-01, INGEST-01, INGEST-04, BOUNDARY-01, BOUNDARY-03, BOUNDARY-04]
must_haves:
  truths:
    - "Source blocks and ingestion jobs have tenant/document scoped durable schema."
    - "Ordered JSONB chunk source refs and chunk OCR metadata exist without changing canonical evidence fields."
    - "Strict Phase 22/23/RAG-5 exclusions are guarded on implementation surfaces while deferred docs and current v1.3 compatibility names remain allowed."
  artifacts:
    - path: "src/db/migrations/versions/015_rag_production_ingestion_ocr.py"
      provides: "DocumentBlock, RagIngestionJob, and chunk provenance migration"
    - path: "src/repositories/document_block_repo.py"
      provides: "Tenant-scoped source-block persistence"
    - path: "tests/knowledge/test_phase21_boundaries.py"
      provides: "Evidence and scope boundary regression tests"
  key_links:
    - from: "src/db/models.py"
      to: "src/repositories/document_block_repo.py"
      via: "DocumentBlock ORM"
    - from: "src/db/models.py"
      to: "PolicyChunk.source_block_refs_json"
      via: "ordered JSONB source-block refs"
---

<objective>
Create the durable Phase 21 schema, repositories, and boundary guards.

Purpose: block-aware ingestion needs source-block/job storage and chunk provenance columns before ingestion can persist parser output safely.
Output: Alembic migration, ORM models, repositories, and passing schema/migration/evidence/scope tests.
</objective>

<scope>
In scope: `DocumentBlock`, `RagIngestionJob`, additive policy document source metadata, a dedicated policy version fingerprint field, JSONB ordered chunk source refs, repositories, migration tests, and boundary guard tests.

Out of scope: PDF/DOCX/image/OCR adapters, block-aware ingestion refactor, provenance lookup exposure, UI, and deferred RAG reasoning/reranking systems.
</scope>

<context>
@/Users/ming/.codex/get-shit-done/workflows/execute-plan.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/21-rag-production-ingestion-ocr/21-RESEARCH.md
@.planning/phases/21-rag-production-ingestion-ocr/21-PATTERNS.md
@src/db/models.py
@src/db/migrations/versions/014_rag_hybrid_retrieval.py
@src/repositories/policy_chunk_repo.py
@src/repositories/policy_document_repo.py
@src/knowledge/schemas.py

<interfaces>
Current `PolicyChunk` citation/retrieval split:
```python
content: Mapped[str] = mapped_column(Text, nullable=False)
search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
```

Current verified evidence pattern:
```python
async def get_verified_evidence_contents(self, *, tenant_id: str, evidence_refs: list[EvidenceRefV1]) -> dict[str, str]:
    ...
    if ref.tenant_id == tenant_id and evidence_text_hash(content) == ref.text_hash:
        verified[ref.evidence_id] = content
```
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|---|---|
| parser DTO -> ORM | Parsed text and metadata become durable source-block and job rows. |
| source-block model -> authority surfaces | New block IDs must not become evidence, approval, action, memory, replay, or business fact authority. |
| migration -> existing retrieval schema | New Phase 21 structures must upgrade/downgrade without damaging Phase 20 hybrid retrieval columns. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan | Tests | Residual Risk |
|---|---|---|---|---|---|---|
| T21-02 | D | migration | mitigate | Create and drop new structures in dependency-safe order while preserving Phase 20 retrieval columns. | `uv run pytest tests/test_rag_production_migration.py -q` | Optional live DB round trip remains Plan 05-owned. |
| T21-05 | I | `DocumentBlock`, repositories | mitigate | Require `tenant_id` and `doc_id` in block/job rows and repository queries. | `uv run pytest tests/rag/test_document_block_schema.py -q` | Provenance lookup exposure lands in Plan 04. |
| T21-07 | E | `DocumentBlock`, tests | mitigate | Keep block IDs subordinate to chunks and add static tests that reject block authority in evidence, memory, approvals, actions, replay, or tools. | `uv run pytest tests/knowledge/test_phase21_boundaries.py -q` | Runtime side-path verification lands in Plan 04. |
| T21-08 | I | `RagIngestionJob` | mitigate | Persist bounded safe codes, counts, timings, checksums, parser versions, and warnings; reject raw paths/stacks/dumps. | `uv run pytest tests/rag/test_document_block_schema.py -q` | Report projection is finalized in Plan 04. |
</threat_model>

<tasks>

<task type="auto" id="21-01a-01">
  <name>Add source-block, ingestion-job, and chunk provenance schema</name>
  <files>src/db/models.py, src/db/migrations/versions/015_rag_production_ingestion_ocr.py, src/repositories/document_block_repo.py, src/repositories/rag_ingestion_job_repo.py, tests/rag/phase21_xfail_inventory.py, tests/rag/test_document_block_schema.py, tests/test_rag_production_migration.py</files>
  <read_first>
    src/db/models.py
    src/db/migrations/versions/014_rag_hybrid_retrieval.py
    src/repositories/policy_chunk_repo.py
    src/repositories/policy_document_repo.py
    tests/rag/phase21_xfail_inventory.py
    tests/rag/test_document_block_schema.py
    tests/test_rag_production_migration.py
  </read_first>
  <action>
    Add ORM models to `src/db/models.py`: `DocumentBlock(TimestampMixin, Base)` with table name `document_blocks`, and `RagIngestionJob(TimestampMixin, Base)` with table name `rag_ingestion_jobs`.
    `DocumentBlock` must include: `id`, `tenant_id`, `doc_id`, `source_block_id`, `block_index`, `block_type`, `text`, `normalized_text`, `text_hash`, `page_number`, `bbox_json`, `table_metadata_json`, `parser_metadata_json`, `ocr_metadata_json`, `source_uri`, and relationships to `PolicyDocument` when practical.
    `DocumentBlock.text` means bounded faithful visible block text only. It must not contain hidden PDF text, DOCX comments, raw parser dumps, debug OCR payloads, or control-character instructions. `DocumentBlock.normalized_text` is a bounded retrieval/chunking-internal normalization and must not be used as public evidence text, prompt authority text, or API evidence text.
    Enforce or test a deterministic max persisted block text length: overlong visible text must be split before persistence or rejected with a safe warning code; raw hidden/comment/parser dump data must be represented only by safe warning codes in metadata.
    `RagIngestionJob` must include: `id`, `tenant_id`, `doc_id`, `doc_key`, `source_type`, `source_checksum`, `parser_name`, `parser_version`, `ocr_engine`, `stage`, `status`, `error_code`, `safe_message`, `warnings_json`, `counts_json`, `timings_json`, `started_at`, and `completed_at`.
    Add `PolicyDocument.source_type`, `PolicyDocument.source_checksum`, `PolicyDocument.parser_metadata_json`, and `PolicyDocument.policy_version_fingerprint` as nullable/additive fields. `parser_metadata_json` is trace/debug-only metadata and must not store the policy version fingerprint.
    Add `PolicyChunk.source_block_refs_json` as non-null JSONB default list for ordered block refs, and `PolicyChunk.ocr_metadata_json` as non-null JSONB default dict for chunk-level OCR summary. Do not change `PolicyChunk.content`, `PolicyChunk.search_text`, `EvidenceRefV1`, or `evidence_text_hash`.
    Create migration `src/db/migrations/versions/015_rag_production_ingestion_ocr.py` with revision `015_rag_production_ingestion_ocr`, down revision `014_rag_hybrid_retrieval`, additive upgrade, and reverse dependency-safe downgrade: drop indexes/constraints, drop chunk provenance columns, then drop `rag_ingestion_jobs`, then drop `document_blocks`, then remove additive `policy_documents` columns.
    Create `src/repositories/document_block_repo.py` and `src/repositories/rag_ingestion_job_repo.py` with `AsyncSession` constructors, tenant-scoped bulk insert/delete/query methods, and no independent commits.
    Remove Wave 0 strict xfail markers for schema/migration tests this task satisfies and remove their entries from `tests/rag/phase21_xfail_inventory.py`.
  </action>
  <verify>
    <automated>uv run pytest tests/rag/test_document_block_schema.py tests/test_rag_production_migration.py -q</automated>
  </verify>
  <acceptance_criteria>
    `Base.metadata.tables` contains `document_blocks` and `rag_ingestion_jobs`.
    Static migration tests verify revision chain, tenant/doc indexes, JSONB fields, `policy_documents.policy_version_fingerprint`, no fake server defaults for semantic data, and downgrade ordering.
    Repository tests or schema tests prove every block/job query includes `tenant_id`.
    Schema tests assert `parser_metadata_json` is trace/debug-only, `policy_version_fingerprint` is a separate `PolicyDocument` field, `DocumentBlock.text` excludes hidden/comment/raw parser dump text, and overlong/control-character block text is split, stripped, or rejected before persistence.
  </acceptance_criteria>
  <done>DocumentBlock, RagIngestionJob, policy document source metadata, chunk provenance columns, repositories, and migration coverage exist.</done>
</task>

<task type="auto" id="21-01a-02">
  <name>Lock evidence compatibility and strict scope guards</name>
  <files>tests/rag/phase21_xfail_inventory.py, tests/knowledge/test_phase21_boundaries.py, tests/knowledge/test_evidence_projection.py, tests/knowledge/test_hybrid_retrieval.py, tests/approvals/test_snapshots.py</files>
  <read_first>
    docs/contract-spec.md
    docs/rag-architecture-spec.md
    src/knowledge/schemas.py
    src/knowledge/retrieval.py
    src/approvals/snapshots.py
    src/replay/schemas.py
    tests/knowledge/test_phase21_boundaries.py
    tests/knowledge/test_evidence_projection.py
    tests/knowledge/test_hybrid_retrieval.py
    tests/approvals/test_snapshots.py
  </read_first>
  <action>
    Complete `tests/knowledge/test_phase21_boundaries.py` so forbidden-name scans target implementation surfaces: `src/`, `tests/`, and migration files. Allow explicit deferred target-state documentation strings in `docs/` and `.planning/` files so existing roadmap/spec deferrals do not fail the guard.
    The guard must be precise and delta-aware enough not to fail on current v1.3 compatibility names. It must allow pre-existing `KnowledgeSearchResult.query_rewrite`, `RERANK_CONFIG_VERSION`, `rerank_config_version`, `rerank_candidates(...)`, and existing Phase 20 hybrid retrieval tests.
    The guard must forbid strict out-of-scope implementation deliverables: `MaterialClaim`, `semantic_verifier`, `SemanticVerifier`, `QueryRewriteService`, `query_rewriter`, `rewrite_query(`, `CrossEncoderReranker`, `ExternalRerankClient`, cross-encoder code, Vespa, OpenSearch, full external `SearchBackend`, external action execution, and business data ingestion into RAG.
    Add assertions that `DocumentBlock`, `source_block_id`, parser metadata, OCR metadata, and ingestion job IDs are absent from `EvidenceRefV1.model_fields`, `canonical_evidence_projection`, approval snapshot hash projection, replay event payload authority, memory modules, and business tool contracts.
    Remove strict xfail markers from Wave 0 scope/evidence tests that this task satisfies and remove their entries from `tests/rag/phase21_xfail_inventory.py`.
  </action>
  <verify>
    <automated>uv run pytest tests/knowledge/test_phase21_boundaries.py tests/knowledge/test_evidence_projection.py tests/knowledge/test_hybrid_retrieval.py tests/approvals/test_snapshots.py -q</automated>
  </verify>
  <acceptance_criteria>
    `EvidenceRefV1` field set remains exactly schema_version, tenant_id, evidence_id, doc_key, chunk_id, policy_version, text_hash, retrieved_at, retrieval_config_version, score, rank.
    Scope guard tests fail if forbidden Phase 22/23/RAG-5 deliverable identifiers are introduced in implementation surfaces, while deferred target-state docs/planning strings and current v1.3 `query_rewrite`/rerank compatibility names are explicitly allowed.
    Approval snapshot tests still import canonical `EvidenceRefV1` from `src.knowledge.schemas`.
  </acceptance_criteria>
  <done>Evidence compatibility and strict Phase 22/23/RAG-5 exclusion tests pass without changing canonical evidence schemas.</done>
</task>

</tasks>

<verification>
`uv run pytest tests/rag/test_document_block_schema.py tests/test_rag_production_migration.py tests/knowledge/test_phase21_boundaries.py tests/knowledge/test_evidence_projection.py tests/knowledge/test_hybrid_retrieval.py tests/approvals/test_snapshots.py -q`
</verification>

<must_haves>
- `DocumentBlock`, `RagIngestionJob`, dedicated `PolicyDocument.policy_version_fingerprint`, and JSONB ordered `PolicyChunk.source_block_refs_json` exist with migration coverage.
- Evidence compatibility tests remain green without changing canonical evidence schemas.
- Scope guards scan implementation surfaces and allow explicit deferred target-state documentation strings plus current v1.3 compatibility names.
</must_haves>

<out_of_scope>
No PDF/DOCX/image/OCR adapter implementation, no block-aware ingestion refactor, no provenance lookup method, no runtime hallucination verifier, no query rewrite service, no reranker service/interface, no external search backend, no CMS/viewer UI, and no business artifact ingestion.
</out_of_scope>

<output>
After completion, create `.planning/phases/21-rag-production-ingestion-ocr/21-01a-SUMMARY.md`.
</output>
