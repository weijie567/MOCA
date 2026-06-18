# Phase 21: RAG Production Ingestion + OCR - Pattern Map

**Mapped:** 2026-06-18  
**Files analyzed:** 33 new/modified files or module families  
**Analogs found:** 29 / 33 exact, role-match, or partial analogs  
**Scope note:** Work packages 21.1-21.5 are implementation slices inside Phase 21, not separate roadmap phases.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/rag/parsers/base.py` | model / utility | transform | `src/rag/chunker.py`; `src/knowledge/schemas.py` | role-match |
| `src/rag/parsers/registry.py` | service / utility | request-response / transform | `src/knowledge/service.py`; `scripts/ingest_policies.py` | partial |
| `src/rag/parsers/markdown.py`, `src/rag/parsers/plain_text.py` | service / adapter | file-I/O / transform | `src/rag/ingestion.py`; `src/rag/chunker.py` | role-match |
| `src/rag/parsers/pdf.py` | service / adapter | file-I/O / transform | `src/rag/parsers/base.py` pattern; no current PDF parser | partial |
| `src/rag/parsers/docx.py` | service / adapter | file-I/O / transform | `src/rag/parsers/base.py` pattern; no current DOCX parser | partial |
| `src/rag/parsers/image.py`, `src/rag/parsers/ocr.py` | service / adapter | file-I/O / transform | `src/rag/parsers/base.py` pattern; no current OCR parser | partial |
| `src/rag/chunker.py` | utility | transform | existing `src/rag/chunker.py` | exact |
| `src/rag/search_text.py` | utility | transform | existing `src/rag/search_text.py` | exact |
| `src/rag/ingestion.py` | service | file-I/O + CRUD | existing `src/rag/ingestion.py` | exact |
| `scripts/ingest_policies.py` | CLI / utility | file-I/O / batch | existing `scripts/ingest_policies.py` | exact |
| `src/db/models.py` | model | CRUD | `PolicyDocument`, `PolicyChunk`, `AgentTraceEvent` in `src/db/models.py` | exact |
| `src/db/migrations/versions/015_rag_production_ingestion_ocr.py` | migration | batch / schema | `014_rag_hybrid_retrieval.py`; `002_rag_pipeline.py` | exact |
| `src/repositories/document_block_repo.py` | repository | CRUD / request-response | `src/repositories/policy_chunk_repo.py` | role-match |
| `src/repositories/rag_ingestion_job_repo.py` | repository | CRUD / event trace | `src/repositories/policy_document_repo.py`; `src/db.models.AgentTraceEvent` | role-match |
| `src/repositories/policy_chunk_repo.py` | repository | CRUD + search | existing `src/repositories/policy_chunk_repo.py` | exact |
| `src/repositories/policy_document_repo.py` | repository | CRUD | existing `src/repositories/policy_document_repo.py` | exact |
| `src/knowledge/service.py` | service | request-response | existing `PolicyKnowledgeService.get_verified_evidence_contents` | exact |
| `src/knowledge/retrieval.py` | service | request-response / hybrid search | existing `PolicyRetrievalEngine` | exact |
| `src/knowledge/schemas.py` | schema | request-response | existing `EvidenceRefV1`, `KnowledgeSearchResult` | exact |
| `pyproject.toml`, `uv.lock`, `Dockerfile` | config | dependency / runtime setup | research standard stack and existing `uv run` workflow | role-match |
| `tests/rag/test_parser_contract.py` | test | transform | `tests/test_chunker.py`; `tests/rag/test_search_text.py` | role-match |
| `tests/rag/test_document_block_schema.py` | test | schema / CRUD | `tests/knowledge/test_hybrid_schema.py` | role-match |
| `tests/rag/test_block_chunker.py` | test | transform | `tests/test_chunker.py` | exact |
| `tests/rag/test_pdf_parser.py`, `test_docx_parser.py`, `test_ocr_parser.py` | test | file-I/O / transform | `tests/test_chunker.py`; safe-payload tests | partial |
| `tests/rag/test_ingestion_safety.py` | test | file-I/O / security | `tests/conversation/test_repository.py`; `src/conversation/schemas.py` | role-match |
| `tests/rag/test_ingestion_jobs.py` | test | event trace / CRUD | `tests/test_ingestion.py`; migration/schema tests | role-match |
| `tests/knowledge/test_provenance_lookup.py` | test | request-response | `tests/knowledge/test_service.py`; `tests/repositories/test_policy_chunk_repo.py` | exact |
| `tests/knowledge/test_phase21_boundaries.py` | test | boundary / static | `tests/knowledge/test_hybrid_schema.py`; prompt/raw-payload tests | role-match |
| `tests/test_rag_production_migration.py` | test | migration / batch | `tests/knowledge/test_hybrid_schema.py`; `tests/test_rag_migration.py` | exact |
| `tests/test_ingestion.py` | test | file-I/O + CRUD | existing `tests/test_ingestion.py` | exact |
| `tests/test_chunker.py` | test | transform | existing `tests/test_chunker.py` | exact |
| `tests/rag/test_search_text.py` | test | transform | existing `tests/rag/test_search_text.py` | exact |
| `tests/knowledge/test_hybrid_retrieval.py` | test | request-response / hybrid search | existing `tests/knowledge/test_hybrid_retrieval.py` | exact |
| `tests/knowledge/test_service.py`, `tests/knowledge/test_hybrid_schema.py` | test | request-response / boundary | existing service and schema tests | exact |

## Pattern Assignments

### `src/rag/parsers/base.py` (parser DTOs, transform)

**Analog:** `src/rag/chunker.py` for immutable internal DTOs; `src/knowledge/schemas.py` for public contract style.

**Imports and dataclass pattern** (`src/rag/chunker.py` lines 1-14):

```python
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkResult:
    doc_key: str
    chunk_id: str
    section: str
    content: str
    chunk_index: int
    part_index: int | None = None
```

**Pydantic contract pattern** (`src/knowledge/schemas.py` lines 31-69):

```python
class EvidenceRefV1(BaseModel):
    schema_version: Literal["evidence_ref.v1"] = "evidence_ref.v1"
    tenant_id: str
    evidence_id: str
    doc_key: str
    chunk_id: str
    policy_version: str
    text_hash: str
    retrieved_at: str
    retrieval_config_version: str
    score: float | None = None
    rank: int | None = Field(default=None, ge=1)

    @classmethod
    def build(...):
        return cls(
            tenant_id=tenant_id,
            evidence_id=f"{doc_key}/{chunk_id}@{policy_version}",
            doc_key=doc_key,
            chunk_id=chunk_id,
            policy_version=policy_version,
            text_hash=evidence_text_hash(text),
            retrieved_at=retrieved_at,
            retrieval_config_version=retrieval_config_version,
            score=score,
            rank=rank,
        )
```

**Apply to Phase 21:** Define project-owned `SourceBox`, `ParserWarning`, `ParsedBlock`, `ParseResult` DTOs with explicit field names, deterministic ordering fields, parser/source metadata, safe failure codes, and no parser-library-native objects. Use `@dataclass(frozen=True)` for lightweight internal DTOs unless validation constraints require Pydantic.

---

### `src/rag/parsers/registry.py` and parser adapters (registry + file adapters)

**Analog:** `src/knowledge/service.py` protocol boundary; `scripts/ingest_policies.py` maintainer ingestion CLI.

**Protocol boundary pattern** (`src/knowledge/service.py` lines 25-42):

```python
class PolicyRetriever(Protocol):
    async def retrieve(
        self,
        *,
        query: str,
        context: KnowledgeContext,
        max_results: int,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> tuple[str, list[EvidenceRefV1], float]: ...

    async def get_contents_by_evidence_keys(
        self,
        *,
        tenant_id: UUID,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], str]: ...
```

**CLI routing and dry-run pattern** (`scripts/ingest_policies.py` lines 129-161):

```python
def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest policy documents into pgvector")
    parser.add_argument("--dir", default="data/policies/", help="Policy documents directory")
    parser.add_argument("--dry-run", action="store_true", help="Parse and chunk only, no embedding/DB")
    parser.add_argument("--tenant-id", help="Tenant UUID (default: first tenant from DB)")
    return parser

def _dry_run(dir_path: Path) -> list[IngestionReport]:
    reports: list[IngestionReport] = []
    for doc_meta in DOCUMENT_MANIFEST:
        ...
        try:
            content = (dir_path / doc_meta["file"]).read_text(encoding="utf-8")
            chunks = chunk_markdown(content, doc_key=doc_key)
            ...
        except Exception as exc:
            reports.append(IngestionReport(doc_key=doc_key, title=title, status="failed", error=str(exc)))
    return reports
```

**Apply to Phase 21:** Keep a narrow parser protocol/registry that maps allowlisted source type to adapter and returns `ParseResult`. Adapters for Markdown/plain/PDF/DOCX/image/OCR should normalize library outputs into DTOs and return safe failure reports instead of leaking exceptions or raw parser dumps.

---

### `src/db/models.py` (DocumentBlock, RagIngestionJob, PolicyChunk provenance)

**Analog:** `PolicyDocument`/`PolicyChunk` for tenant-scoped policy rows; `AuditLog`/`AgentTraceEvent` for safe trace JSON.

**Policy model pattern** (`src/db/models.py` lines 160-202):

```python
class PolicyDocument(TimestampMixin, Base):
    __tablename__ = "policy_documents"
    __table_args__ = (UniqueConstraint("tenant_id", "doc_key", name="uq_policy_documents_tenant_doc_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    doc_key: Mapped[str] = mapped_column(String(64), nullable=False)
    ...
    chunks: Mapped[list["PolicyChunk"]] = relationship(back_populates="document")

class PolicyChunk(TimestampMixin, Base):
    __tablename__ = "policy_chunks"
    ...
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policy_documents.id"), nullable=False, index=True
    )
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
```

**Safe JSON trace fields** (`src/db/models.py` lines 204-222):

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    ...
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

**Event trace pattern** (`src/db/models.py` lines 1110-1160):

```python
class AgentTraceEvent(TimestampMixin, Base):
    """Phase 10 minimal envelope expanded for Phase 15 ReplayEventV3 storage."""

    __tablename__ = "agent_trace_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_trace_events_run_seq"),
        CheckConstraint(..., name="ck_agent_trace_events_schema_version"),
        CheckConstraint(..., name="ck_agent_trace_events_event_type"),
        CheckConstraint("sequence > 0", name="ck_agent_trace_events_sequence_positive"),
    )
    ...
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    redacted_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
```

**Apply to Phase 21:** Add `DocumentBlock` and `RagIngestionJob` as tenant-scoped rows with stable IDs, bounded strings, JSONB metadata for parser/OCR/table fields, indexes on tenant/doc/block identity, and check constraints for finite statuses/block types. Add ordered chunk provenance to `PolicyChunk` as JSONB unless the plan chooses a join table.

---

### `src/db/migrations/versions/015_rag_production_ingestion_ocr.py` (migration, batch/schema)

**Analog:** `014_rag_hybrid_retrieval.py` and `002_rag_pipeline.py`.

**Revision and additive upgrade pattern** (`src/db/migrations/versions/014_rag_hybrid_retrieval.py` lines 16-50):

```python
revision: str = "014_rag_hybrid_retrieval"
down_revision: str | None = "013_long_term_case_memory"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column("policy_chunks", sa.Column("search_text", sa.Text(), nullable=True))
    op.execute("""
        UPDATE policy_chunks
        SET search_text = trim(concat_ws(' ', section, content))
        WHERE search_text IS NULL
    """)
    op.alter_column("policy_chunks", "search_text", nullable=False)
    ...
    op.create_index(
        "ix_policy_chunks_retrieval_scope",
        "policy_chunks",
        ["tenant_id", "effective_date", "risk_level"],
    )
```

**Dependency-safe downgrade pattern** (`src/db/migrations/versions/014_rag_hybrid_retrieval.py` lines 53-58):

```python
def downgrade() -> None:
    op.drop_index("ix_policy_chunks_retrieval_scope", table_name="policy_chunks")
    op.execute("DROP INDEX IF EXISTS ix_policy_chunks_search_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_policy_chunks_search_vector_gin")
    op.drop_column("policy_chunks", "search_vector")
    op.drop_column("policy_chunks", "search_text")
```

**Backfill-before-constraint pattern** (`src/db/migrations/versions/002_rag_pipeline.py` lines 20-30):

```python
def upgrade() -> None:
    # Add semantic document key column. Existing rows get unique legacy keys
    # before the tenant-scoped unique constraint is applied.
    op.add_column("policy_documents", sa.Column("doc_key", sa.String(64), nullable=True))
    op.execute("""
        UPDATE policy_documents
        SET doc_key = 'legacy_' || replace(id::text, '-', '')
        WHERE doc_key IS NULL
    """)
    op.alter_column("policy_documents", "doc_key", nullable=False)
    op.create_unique_constraint("uq_policy_documents_tenant_doc_key", "policy_documents", ["tenant_id", "doc_key"])
```

**Apply to Phase 21:** Use `revision="015_rag_production_ingestion_ocr"` and `down_revision="014_rag_hybrid_retrieval"`. Create tables and indexes additively, backfill nullable columns before making any new field non-null, and downgrade in reverse dependency order: dependent indexes/constraints, chunk provenance columns, job/block tables.

---

### Repository Files (document blocks, ingestion jobs, policy chunks/documents)

**Analog:** `src/repositories/policy_chunk_repo.py` and `src/repositories/policy_document_repo.py`.

**Delete/bulk insert pattern** (`src/repositories/policy_chunk_repo.py` lines 14-28):

```python
class PolicyChunkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def delete_by_document_id(self, document_id: UUID, tenant_id: UUID) -> int:
        stmt = delete(PolicyChunk).where(
            PolicyChunk.doc_id == document_id,
            PolicyChunk.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def bulk_insert(self, chunks: list[PolicyChunk]) -> None:
        self.session.add_all(chunks)
        await self.session.flush()
```

**Tenant-scoped evidence content lookup** (`src/repositories/policy_chunk_repo.py` lines 30-58):

```python
async def get_contents_by_evidence_keys(
    self,
    tenant_id: UUID,
    keys: list[tuple[str, str]],
) -> dict[tuple[str, str], str]:
    if not keys:
        return {}

    stmt = (
        select(PolicyDocument.doc_key, PolicyChunk.chunk_id, PolicyChunk.content)
        .join(
            PolicyDocument,
            and_(
                PolicyChunk.doc_id == PolicyDocument.id,
                PolicyDocument.tenant_id == tenant_id,
            ),
        )
        .where(
            PolicyChunk.tenant_id == tenant_id,
            tuple_(PolicyDocument.doc_key, PolicyChunk.chunk_id).in_(keys),
        )
    )
    rows = (await self.session.execute(stmt)).all()
    counts = Counter((row[0], row[1]) for row in rows)
    return {
        (doc_key, chunk_id): content
        for doc_key, chunk_id, content in rows
        if counts[(doc_key, chunk_id)] == 1
    }
```

**Row lock pattern** (`src/repositories/policy_document_repo.py` lines 23-34):

```python
async def get_by_doc_key_for_update(self, doc_key: str, tenant_id: UUID) -> PolicyDocument | None:
    """Fetch and lock a document so concurrent content-version bumps serialize."""
    stmt = (
        select(PolicyDocument)
        .where(
            PolicyDocument.tenant_id == tenant_id,
            PolicyDocument.doc_key == doc_key,
        )
        .with_for_update()
    )
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none()
```

**Apply to Phase 21:** New block/job repositories should take `AsyncSession`, require `tenant_id` in every query, return empty results on empty keys, de-duplicate ambiguous provenance rows, and be used inside the ingestion transaction rather than committing independently.

---

### `src/rag/ingestion.py` (atomic ingestion transaction)

**Analog:** Existing `IngestionService.ingest_document`.

**Preflight before DB mutation** (`src/rag/ingestion.py` lines 35-61):

```python
async def ingest_document(self, file_path: Path, doc_meta: dict) -> IngestionReport:
    """
    Ingest one policy document.

    Embeddings are generated before delete/insert DB mutations, so network
    I/O does not hold the short write transaction open.
    """
    doc_key = doc_meta["doc_key"]
    title = doc_meta["title"]

    try:
        content = file_path.read_text(encoding="utf-8")
        chunks = chunk_markdown(content, doc_key=doc_key)
        if not chunks:
            return IngestionReport(doc_key=doc_key, title=title, status="failed", error="No chunks produced")
        ...
        embeddings = await self.embedder.embed_documents(texts)
        if len(embeddings) != len(chunks):
            msg = f"Embedding count mismatch: expected {len(chunks)}, got {len(embeddings)}"
            return IngestionReport(doc_key=doc_key, title=title, status="failed", error=msg)
```

**Locked write + rollback pattern** (`src/rag/ingestion.py` lines 62-117):

```python
effective_date = doc_meta.get("effective_date", date.today())
existing_doc = await self.doc_repo.get_by_doc_key_for_update(doc_key, self.tenant_id)
if existing_doc:
    doc = existing_doc
    content_changed = doc.content != content
    if content_changed:
        doc.version = (doc.version or 1) + 1
    ...
else:
    doc = PolicyDocument(...)
    self.session.add(doc)
    await self.session.flush()

await self.chunk_repo.delete_by_document_id(doc.id, self.tenant_id)
...
await self.chunk_repo.bulk_insert(db_chunks)
await self.session.commit()

return IngestionReport(doc_key=doc_key, title=title, status="success", chunks_created=len(db_chunks))
except Exception as exc:
    await self.session.rollback()
    return IngestionReport(doc_key=doc_key, title=title, status="failed", error=str(exc))
```

**Apply to Phase 21:** Parse/OCR/clean/chunk/embed must finish before the short locked write. The transaction should update document metadata/version, delete/insert blocks, delete/insert chunks, persist ordered chunk provenance, and update the safe job status atomically. Parser trace-only metadata must not bump `PolicyDocument.version`.

---

### `src/rag/chunker.py` and `tests/rag/test_block_chunker.py` (block-aware chunking)

**Analog:** Existing Markdown chunker and tests.

**Stable chunk ID pattern** (`src/rag/chunker.py` lines 22-70):

```python
def chunk_markdown(
    content: str,
    doc_key: str,
    max_chars: int = 1200,
    target_chars: int = 800,
    overlap_chars: int = 100,
) -> list[ChunkResult]:
    """Split Markdown policy text into stable heading-based chunks."""
    if not doc_key:
        raise ValueError("doc_key must not be empty")
    ...
    chunks: list[ChunkResult] = []
    chunk_index = 0

    for section, body in _iter_sections(content):
        if not body:
            continue
        ...
        chunks.append(
            ChunkResult(
                doc_key=doc_key,
                chunk_id=f"{doc_key}_{chunk_index:03d}",
                section=section,
                content=body,
                chunk_index=chunk_index,
            )
        )
        ...
        chunk_index += 1

    return chunks
```

**Boundary-aware split pattern** (`src/rag/chunker.py` lines 95-140):

```python
def _split_oversized(text: str, max_chars: int, target_chars: int, overlap_chars: int) -> list[str]:
    parts: list[str] = []
    start = 0
    text_len = len(text)
    ...
    end = _find_split_position(text, start, preferred_end)
    ...
    next_start = max(end - overlap_chars, start + 1)
    start = _trim_leading_boundary(text, next_start)
    return parts
```

**Current test shape** (`tests/test_chunker.py` lines 24-37):

```python
def test_stable_chunk_ids():
    markdown = """
## 退款时效
退款审核通过后，系统应在两个工作日内原路退回。
## 商家举证
商家拒绝退款时，需要上传物流签收或商品完好凭证。
"""

    first = chunk_markdown(markdown, "refund_policy")
    second = chunk_markdown(markdown, "refund_policy")

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.chunk_id for chunk in first] == ["refund_policy_000", "refund_policy_001"]
    assert all(chunk.doc_key == "refund_policy" for chunk in first)
```

**Apply to Phase 21:** Add `chunk_blocks(...)` next to `chunk_markdown(...)`, not replacing it. Preserve stable `doc_key_000` style IDs, faithful visible `content`, deterministic source-block refs, max length enforcement, and table header/row context tests.

---

### `src/rag/search_text.py` (retrieval-only enrichment)

**Analog:** Existing search-text builder.

**Search text builder pattern** (`src/rag/search_text.py` lines 71-90):

```python
def build_policy_chunk_search_text(
    *,
    title: str,
    section: str,
    content: str,
    doc_type: str | None = None,
    risk_level: str | None = None,
) -> str:
    context_parts = [title, section, doc_type or "", risk_level or "", content]
    normalized_context = normalize_search_text(" ".join(part for part in context_parts if part))
    tokens = tokenize_search_text(normalized_context)
    parts = [normalized_context, *tokens]

    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if part and part not in seen:
            seen.add(part)
            deduped.append(part)
    return " ".join(deduped)
```

**Isolation test pattern** (`tests/rag/test_search_text.py` lines 34-50):

```python
def test_build_policy_chunk_search_text_includes_context_without_mutating_content() -> None:
    content = "商品不影响二次销售时，客服可支持七天无理由退货退款。"

    search_text = build_policy_chunk_search_text(
        title="退款规则",
        section="七天无理由",
        content=content,
        doc_type="refund_rule",
        risk_level="high",
    )

    assert "退款规则" in search_text
    assert "七天无理由" in search_text
    assert "二次销售" in search_text
    assert "refund_rule" in search_text
    assert "high" in search_text
    assert content == "商品不影响二次销售时，客服可支持七天无理由退货退款。"
```

**Apply to Phase 21:** Add optional heading/table/source context enrichment to `search_text` only. Tests must assert `PolicyChunk.content` and `EvidenceRefV1.text_hash` remain unchanged.

---

### `src/knowledge/service.py` (verified provenance lookup)

**Analog:** `get_verified_evidence_contents`.

**Tenant/hash verification pattern** (`src/knowledge/service.py` lines 105-140):

```python
async def get_verified_evidence_contents(
    self,
    *,
    tenant_id: str,
    evidence_refs: list[EvidenceRefV1],
) -> dict[str, str]:
    try:
        tenant_uuid = UUID(tenant_id)
    except ValueError:
        return {}

    key_counts = Counter((ref.doc_key, ref.chunk_id) for ref in evidence_refs)
    keys = [key for key, count in key_counts.items() if count == 1 and all(key)]
    if not keys:
        return {}

    try:
        contents = await self.retriever.get_contents_by_evidence_keys(
            tenant_id=tenant_uuid,
            keys=keys,
        )
    except Exception:
        return {}

    verified: dict[str, str] = {}
    for ref in evidence_refs:
        key = (ref.doc_key, ref.chunk_id)
        content = contents.get(key)
        if (
            key_counts.get(key) == 1
            and ref.tenant_id == tenant_id
            and content is not None
            and evidence_text_hash(content) == ref.text_hash
        ):
            verified[ref.evidence_id] = content
    return verified
```

**Service error pattern** (`src/knowledge/service.py` lines 75-82):

```python
except asyncio.TimeoutError:
    return self._error_result("DB_TIMEOUT", "Policy search timeout", retryable=True)
except Exception:
    return self._error_result(
        "SEARCH_ERROR",
        "Failed to search policy evidence",
        retryable=False,
    )
```

**Apply to Phase 21:** Implement provenance lookup as a side path that first validates tenant ID, unique `(doc_key, chunk_id)` keys, canonical chunk content, and `evidence_text_hash(content)`. Return source locators only for verified evidence IDs; return empty on malformed tenant, duplicate keys, missing rows, hash mismatch, or repository errors.

---

### `src/knowledge/retrieval.py` (hybrid retrieval boundary)

**Analog:** Current retrieval hit vs public evidence ref separation.

**Internal trace dataclass** (`src/knowledge/retrieval.py` lines 106-122):

```python
@dataclass(frozen=True)
class PolicyRetrievalHit:
    doc_key: str
    chunk_id: str
    title: str
    section: str
    policy_version: str
    text: str
    score: float
    rank: int
    selected_by: tuple[str, ...] = ()
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fuzzy_rank: int | None = None
    rrf_score: float | None = None
    filter_status: str = "passed"
```

**Public evidence projection pattern** (`src/knowledge/retrieval.py` lines 232-246):

```python
evidence_refs = [
    EvidenceRefV1.build(
        tenant_id=context.tenant_id,
        doc_key=hit.doc_key,
        chunk_id=hit.chunk_id,
        policy_version=hit.policy_version,
        text=hit.text,
        retrieved_at=context.effective_at,
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=hit.score,
        rank=hit.rank,
    )
    for hit in hits
]
return status, evidence_refs, best_score
```

**Apply to Phase 21:** Parser/OCR/provenance metadata may be internal hit/debug/eval data, but must not be added to `EvidenceRefV1`. OCR confidence must not replace `hit.score` or `KnowledgeSearchResult.best_score`.

---

### Test Patterns

#### Ingestion rollback and version tests

**Analog:** `tests/test_ingestion.py`.

**Content/search_text separation** (`tests/test_ingestion.py` lines 101-139):

```python
@pytest.mark.asyncio
async def test_ingestion_embeds_title_and_section_but_persists_raw_content(tmp_path: Path):
    ...
    report = await service.ingest_document(policy_file, _doc_meta())

    assert report.status == "success"
    assert embedder.texts == [
        "退款规则: # 退款规则",
        "退款规则 / 七天无理由: 商品不影响二次销售时，支持七天无理由退货退款。",
    ]
    assert [chunk.content for chunk in chunk_repo.inserted] == [
        "# 退款规则",
        "商品不影响二次销售时，支持七天无理由退货退款。",
    ]
    assert "退款规则" in chunk_repo.inserted[0].search_text
    assert session.committed is True
```

**Rollback on failed reimport** (`tests/test_ingestion.py` lines 209-224):

```python
@pytest.mark.asyncio
async def test_failed_changed_content_reimport_rolls_back_version(tmp_path: Path):
    original_content = "# 退款规则\n\n变更前内容"
    policy_file = _write_policy(tmp_path, "# 退款规则\n\n变更后内容")
    doc = _existing_doc(original_content)
    session = _FakeSession(doc)
    service = IngestionService(session=session, embedder=_FakeEmbedder(), tenant_id=uuid4())
    service.doc_repo = _FakeDocumentRepo(doc)
    service.chunk_repo = _FakeChunkRepo(fail_insert=True)

    report = await service.ingest_document(policy_file, _doc_meta())

    assert report.status == "failed"
    assert session.rolled_back is True
    assert doc.version == 1
    assert doc.content == original_content
```

#### Provenance lookup tests

**Analog:** `tests/knowledge/test_service.py`.

**Hash/tenant/duplicate/error tests** (`tests/knowledge/test_service.py` lines 94-146):

```python
@pytest.mark.asyncio
async def test_verified_evidence_contents_rechecks_hash_and_tenant():
    tenant_id = str(uuid4())
    valid = _evidence(tenant_id=tenant_id, text="真实政策正文")
    wrong_hash = _evidence(tenant_id=tenant_id, chunk_id="chunk-2", text="旧正文")
    wrong_tenant = _evidence(tenant_id=str(uuid4()), chunk_id="chunk-3", text="跨租户正文")
    get_contents = AsyncMock(
        return_value={
            (valid.doc_key, valid.chunk_id): "真实政策正文",
            (wrong_hash.doc_key, wrong_hash.chunk_id): "被修改的正文",
            (wrong_tenant.doc_key, wrong_tenant.chunk_id): "跨租户正文",
        }
    )
    service = PolicyKnowledgeService(SimpleNamespace(get_contents_by_evidence_keys=get_contents))

    result = await service.get_verified_evidence_contents(
        tenant_id=tenant_id,
        evidence_refs=[valid, wrong_hash, wrong_tenant],
    )

    assert result == {valid.evidence_id: "真实政策正文"}
```

#### Hybrid retrieval boundary tests

**Analog:** `tests/knowledge/test_hybrid_retrieval.py`.

**Internal trace exclusion** (`tests/knowledge/test_hybrid_retrieval.py` lines 121-132):

```python
@pytest.mark.asyncio
async def test_retrieval_trace_stays_internal_to_hits() -> None:
    target = _chunk("refund_policy_001")
    engine, _ = _engine(dense=[(target, 0.82)], sparse=[(target, 0.12)])
    context = _context()

    _, hits, _ = await engine.retrieve_hits(query="仅退款怎么处理？", context=context, max_results=5)
    _, refs, _ = await engine.retrieve(query="仅退款怎么处理？", context=context, max_results=5)

    assert hits[0].selected_by == ("dense", "sparse")
    assert hits[0].rrf_score is not None
    assert "selected_by" not in refs[0].model_dump()
    assert "rrf_score" not in refs[0].model_dump()
```

**Scope filter propagation** (`tests/knowledge/test_hybrid_retrieval.py` lines 136-156):

```python
@pytest.mark.asyncio
async def test_each_hybrid_channel_receives_scope_filters() -> None:
    tenant_id = uuid4()
    engine, repo = _engine(dense=[(_chunk("refund_policy_001"), 0.82)])

    await engine.retrieve_hits(
        query="仅退款怎么处理？",
        context=_context(tenant_id),
        max_results=5,
        doc_type="refund_rule",
        risk_level="high",
    )

    for method_name in ("search_similar", "search_sparse", "search_fuzzy"):
        kwargs = getattr(repo, method_name).await_args.kwargs
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["doc_type"] == "refund_rule"
        assert kwargs["risk_level"] == "high"
        assert kwargs["effective_date"] == date(2026, 6, 14)
```

#### Migration and downgrade tests

**Analog:** `tests/knowledge/test_hybrid_schema.py`; `tests/test_rag_migration.py`.

**Static migration source helper** (`tests/knowledge/test_hybrid_schema.py` lines 8-13):

```python
MIGRATION_PATH = Path("src/db/migrations/versions/014_rag_hybrid_retrieval.py")

def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), "Phase 20 RAG hybrid migration must exist"
    return MIGRATION_PATH.read_text(encoding="utf-8")
```

**Revision, forbidden scope, downgrade ordering** (`tests/knowledge/test_hybrid_schema.py` lines 23-52):

```python
def test_phase20_migration_declares_full_text_and_trgm_indexes() -> None:
    source = _migration_source()

    assert 'revision: str = "014_rag_hybrid_retrieval"' in source
    assert 'down_revision: str | None = "013_long_term_case_memory"' in source
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in source
    assert "ix_policy_chunks_search_vector_gin" in source
    assert "ix_policy_chunks_search_text_trgm" in source

def test_phase20_migration_does_not_create_deferred_ingestion_or_verifier_tables() -> None:
    source = _migration_source().lower()

    for forbidden in ("documentblock", "ocr", "material_claim", "vespa", "opensearch"):
        assert forbidden not in source

def test_phase20_migration_downgrade_drops_search_columns_after_indexes() -> None:
    source = _migration_source()
    ...
    assert vector_index_pos < search_vector_pos
    assert trgm_index_pos < search_text_pos
    assert search_vector_pos < search_text_pos
```

**Backfill-before-constraint assertion** (`tests/test_rag_migration.py` lines 6-13):

```python
def test_rag_migration_backfills_unique_doc_keys_before_constraint():
    migration = Path("src/db/migrations/versions/002_rag_pipeline.py").read_text()

    assert 'server_default=""' not in migration
    assert "nullable=True" in migration
    assert "UPDATE policy_documents" in migration
    assert "'legacy_' || replace(id::text, '-', '')" in migration
    assert migration.index("UPDATE policy_documents") < migration.index("create_unique_constraint")
```

**Apply to Phase 21:** `tests/test_rag_production_migration.py` should statically assert revision chain, table/column/index creation, no server-default fake values, dependency-safe downgrade order, no Phase 22/23/RAG-5 names, and optional disposable DB upgrade/downgrade/reupgrade when configured.

#### Raw payload / prompt-boundary tests

**Analog:** `src/conversation/schemas.py`; `tests/conversation/test_repository.py`.

**Recursive forbidden-key guard** (`src/conversation/schemas.py` lines 10-20 and 86-98):

```python
FORBIDDEN_MESSAGE_KEYS: set[str] = {
    "raw",
    "raw_prompt",
    "raw_args",
    "raw_payload",
    "raw_tool_output",
    "private_reasoning",
    "chain_of_thought",
    "approval_authority_body",
    "action_authority_body",
}

def guard_forbidden_message_keys(payload: Any) -> None:
    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in FORBIDDEN_MESSAGE_KEYS:
                    raise ValueError(f"{path} must not carry {key}")
                walk(child, f"{path}.{key}")
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(payload, "conversation_message")
```

**Safe test pattern** (`tests/conversation/test_repository.py` lines 130-149):

```python
def test_tool_message_rejects_raw_payload_keys() -> None:
    from src.conversation.schemas import ConversationMessageCreate
    from src.conversation.service import ConversationService

    service = ConversationService(repository=None)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ConversationMessageCreate(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            thread_id="thread-raw-tool",
            run_id=uuid.uuid4(),
            role="tool",
            content="safe summary",
            metadata_json={"raw_payload": {"secret": "do-not-store"}},
        )
    with pytest.raises(ValueError, match="raw_tool_output"):
        service.validate_safe_message_payload(
            content="safe",
            metadata_json={"raw_tool_output": {"full": "payload"}},
        )
```

**Apply to Phase 21:** Parser/OCR raw bytes, parser dumps, hidden instructions, stack traces, unsafe file paths, and business artifacts should be rejected or sanitized before persistence and must not appear in prompts, memory, action snapshots, replay, or public evidence serialization.

## Shared Patterns

### Tenant Scope

**Source:** `src/repositories/policy_chunk_repo.py` lines 38-50; `src/knowledge/service.py` lines 111-139  
**Apply to:** DocumentBlock repo, ingestion job repo, provenance lookup, parser job trace queries.

Every repository query that returns policy/provenance data must include `tenant_id`. Provenance lookup must validate the caller tenant string parses to UUID, the ref tenant matches the caller tenant, and the fetched content hash matches the evidence ref.

### Transaction Boundary

**Source:** `src/rag/ingestion.py` lines 35-117  
**Apply to:** `IngestionService`, block/chunk/job writes.

Do parser/OCR/chunk/embed before DB mutation. Lock the document row with `get_by_doc_key_for_update`, then write document, blocks, chunks, provenance, and job status in one transaction. On any exception, rollback and return a safe failed report.

### Evidence Surface Separation

**Source:** `src/knowledge/retrieval.py` lines 106-122 and 232-246; `tests/knowledge/test_hybrid_retrieval.py` lines 121-132  
**Apply to:** Retrieval, provenance, OCR confidence, parser metadata.

Internal trace fields can exist on internal hit/provenance DTOs, but public `EvidenceRefV1` remains unchanged. `PolicyChunk.content` remains citation text; `PolicyChunk.search_text` remains retrieval-only.

### Migration Downgrade Order

**Source:** `src/db/migrations/versions/014_rag_hybrid_retrieval.py` lines 53-58; `tests/knowledge/test_hybrid_schema.py` lines 42-52  
**Apply to:** `015_rag_production_ingestion_ocr.py`, `tests/test_rag_production_migration.py`.

Drop dependent indexes before columns/tables. Drop chunk provenance references before source-block tables. Add static tests using `source.index(...)` to lock ordering.

### Scope Guards

**Source:** `tests/knowledge/test_hybrid_schema.py` lines 35-39; `.planning/REQUIREMENTS.md` lines 78-88  
**Apply to:** `tests/knowledge/test_phase21_boundaries.py`, migration tests, architecture scans.

Phase 21 may introduce parser/OCR/source-block provenance, but must not introduce `MaterialClaim`, semantic verifier, query rewrite, reranker/cross-encoder API, Vespa/OpenSearch, or full external `SearchBackend`.

### Parser/OCR Stack Decisions

**Source:** `21-RESEARCH.md` lines 146-152 and 166-176  
**Apply to:** parser adapters, dependency config, OCR preflight tests.

Use `pdfplumber==0.11.10`, `pypdfium2==5.10.1`, `python-docx==1.2.0`, `pytesseract==0.3.13`, `Pillow==12.2.0`, and `filetype==1.2.0` if the implementation adopts the research recommendation. Local Tesseract exists, but `chi_sim` is missing; tests need an explicit preflight/skip/fail message for Chinese OCR acceptance.

## No Exact Analog Found

| File / Family | Role | Data Flow | Reason | Fallback Pattern |
|---|---|---|---|---|
| `src/rag/parsers/pdf.py` | adapter | file-I/O / transform | No PDF parser exists in current repo. | Use parser DTO contract + safe failure pattern; test with fixtures. |
| `src/rag/parsers/docx.py` | adapter | file-I/O / transform | No DOCX parser exists in current repo. | Use parser DTO contract; explicitly null page/bbox. |
| `src/rag/parsers/image.py`, `src/rag/parsers/ocr.py` | adapter | file-I/O / transform | No OCR wrapper exists in current repo. | Use safe parser reports, confidence metadata, timeout tests. |
| `src/rag/parsers/registry.py` | registry | request-response / transform | Existing services use protocols but no parser registry. | Copy `PolicyRetriever` protocol style and manifest routing shape. |
| File signature/decompression safety utility | utility | file-I/O / security | Current ingestion only reads Markdown text. | Copy recursive forbidden-key and safe-report test style; use research stack for file limits. |
| Disposable DB migration round-trip test | test | migration / batch | Existing migration tests are static; no live upgrade/downgrade test analog found. | Add optional DB-gated test plus static assertions. |

## Metadata

**Analog search scope:** `src/rag`, `src/knowledge`, `src/repositories`, `src/db/models.py`, `src/db/migrations/versions`, `scripts`, `tests`  
**Files scanned:** 200  
**Pattern extraction date:** 2026-06-18  
**Dirty work preserved:** repository had unrelated modified/untracked files before this map; only this `21-PATTERNS.md` file was written.
