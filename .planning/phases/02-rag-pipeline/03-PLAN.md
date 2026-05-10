---
phase: 2
plan: "03"
plan_id: "03"
type: execute
title: "Repositories + Ingestion Service + CLI + Knowledge Documents"
wave: 2
depends_on: ["01", "02"]
files_modified:
  - src/repositories/policy_document_repo.py
  - src/repositories/policy_chunk_repo.py
  - src/rag/ingestion.py
  - scripts/ingest_policies.py
  - data/policies/refund_policy.md
  - data/policies/refund_sop.md
  - data/policies/compensation_rules.md
  - data/policies/merchant_faq.md
  - data/policies/return_shipping.md
  - data/policies/quality_issue_policy.md
  - data/policies/partial_refund_rules.md
  - data/policies/refund_time_limits.md
  - data/policies/high_value_refund.md
  - data/policies/cross_border_refund.md
  - data/policies/digital_goods_refund.md
  - data/policies/bulk_order_refund.md
  - data/policies/customer_escalation_sop.md
  - data/policies/compensation_approval_sop.md
  - data/policies/merchant_dispute_faq.md
autonomous: true
requirements: [RAG-01, RAG-02, RAG-03, RAG-04, INFR-06]
must_haves:
  truths:
    - "The policy corpus contains exactly the 15 manifest-backed Chinese Markdown documents."
    - "Repositories follow existing project patterns with AsyncSession constructor injection."
    - "Vector search joins PolicyDocument for doc_type and risk_level filtering."
    - "Vector search eager-loads the document relationship."
    - "Ingestion embeds content outside the database transaction."
    - "The ingestion CLI supports --dry-run without requiring an API key or database connection."
    - "The ingestion CLI supports --tenant-id."
    - "Failure of one document does not prevent other documents from ingesting."
  artifacts:
    - path: "src/repositories/policy_document_repo.py"
      provides: "Policy document persistence"
      contains: "class PolicyDocumentRepository"
    - path: "src/repositories/policy_chunk_repo.py"
      provides: "Policy chunk vector search"
      contains: "search_similar"
    - path: "src/rag/ingestion.py"
      provides: "Policy ingestion orchestration"
      contains: "class IngestionService"
    - path: "scripts/ingest_policies.py"
      provides: "Policy ingestion CLI"
      contains: "--dry-run"
    - path: "data/policies/refund_policy.md"
      provides: "Chinese refund policy corpus entry"
      contains: "##"
  key_links:
    - from: "scripts/ingest_policies.py"
      to: "src/rag/ingestion.py"
      via: "CLI delegates document processing to IngestionService"
      pattern: "IngestionService"
    - from: "src/rag/ingestion.py"
      to: "src/rag/chunker.py"
      via: "ingestion chunks Markdown before persistence"
      pattern: "chunk_markdown"
    - from: "src/rag/ingestion.py"
      to: "src/rag/embedder.py"
      via: "ingestion embeds chunks before database writes"
      pattern: "embed_documents"
---

# Plan 03: Repositories + Ingestion Service + CLI + Knowledge Documents

<objective>
Create PolicyDocument and PolicyChunk repositories following existing repo patterns, implement the ingestion service that embeds outside the DB transaction, build the CLI script with --dry-run and --tenant-id support, and create 15+ Chinese knowledge documents.
</objective>

<tasks>

<task id="03.1">
<title>Create PolicyDocument repository</title>
<read_first>
- src/repositories/order_repo.py (existing repository pattern)
- src/db/models.py (PolicyDocument model with doc_key)
- src/db/session.py (get_session pattern)
</read_first>
<action>
Create `src/repositories/policy_document_repo.py` following the pattern of order_repo.py:

```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PolicyDocument


class PolicyDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_doc_key(self, doc_key: str, tenant_id: UUID) -> PolicyDocument | None:
        stmt = select(PolicyDocument).where(
            PolicyDocument.tenant_id == tenant_id,
            PolicyDocument.doc_key == doc_key,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, doc: PolicyDocument) -> PolicyDocument:
        """Merge (insert or update) a policy document."""
        merged = await self.session.merge(doc)
        await self.session.flush()
        return merged
```
</action>
<acceptance_criteria>
- src/repositories/policy_document_repo.py exists
- File contains `class PolicyDocumentRepository`
- File contains `async def get_by_doc_key(self, doc_key: str, tenant_id: UUID)`
- File uses `PolicyDocument.doc_key` for lookup (not title or UUID)
- Constructor takes `session: AsyncSession`
</acceptance_criteria>
</task>

<task id="03.2">
<title>Create PolicyChunk repository with vector search</title>
<read_first>
- src/repositories/order_repo.py (existing repository pattern)
- src/db/models.py (PolicyChunk, PolicyDocument models)
- .planning/phases/02-rag-pipeline/02-RESEARCH.md (Cosine Similarity Search example)
</read_first>
<action>
Create `src/repositories/policy_chunk_repo.py`:

```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import PolicyChunk, PolicyDocument


class PolicyChunkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def delete_by_document_id(self, document_id: UUID, tenant_id: UUID) -> int:
        stmt = delete(PolicyChunk).where(
            PolicyChunk.doc_id == document_id,
            PolicyChunk.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def bulk_insert(self, chunks: list[PolicyChunk]) -> None:
        self.session.add_all(chunks)
        await self.session.flush()

    async def search_similar(
        self,
        query_embedding: list[float],
        tenant_id: UUID,
        top_k: int = 5,
        min_similarity: float = 0.55,
        doc_type: str | None = None,
        risk_level: str | None = None,
    ) -> list[tuple[PolicyChunk, float]]:
        """
        Vector similarity search with metadata filters.
        Returns list of (chunk, similarity_score) tuples.
        Uses JOIN to PolicyDocument for doc_type filtering.
        Eager-loads document relationship to avoid async lazy-load issues.
        """
        similarity_expr = (1 - PolicyChunk.embedding.cosine_distance(query_embedding))

        stmt = (
            select(PolicyChunk, similarity_expr.label("score"))
            .join(PolicyDocument, PolicyChunk.doc_id == PolicyDocument.id)
            .options(selectinload(PolicyChunk.document))
            .where(
                and_(
                    PolicyChunk.tenant_id == tenant_id,
                    similarity_expr >= min_similarity,
                )
            )
            .order_by(PolicyChunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )

        # Metadata filters via JOIN to PolicyDocument
        if doc_type:
            stmt = stmt.where(PolicyDocument.doc_type == doc_type)
        if risk_level:
            stmt = stmt.where(PolicyChunk.risk_level == risk_level)

        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]
```

Key design decisions addressing review:
- JOIN to PolicyDocument for doc_type filtering (doc_type is on PolicyDocument, not PolicyChunk)
- `selectinload(PolicyChunk.document)` to eager-load and avoid async lazy-load issues
- Similarity = `1 - cosine_distance` (not raw distance)
</action>
<acceptance_criteria>
- src/repositories/policy_chunk_repo.py exists
- File contains `class PolicyChunkRepository`
- File contains `async def search_similar(` with parameters: query_embedding, tenant_id, top_k, min_similarity, doc_type, risk_level
- File contains `.join(PolicyDocument` for doc_type filtering
- File contains `selectinload(PolicyChunk.document)` for eager loading
- File contains `1 - PolicyChunk.embedding.cosine_distance(` for similarity calculation
- File contains `async def delete_by_document_id(` and `async def bulk_insert(`
</acceptance_criteria>
</task>

<task id="03.3">
<title>Create ingestion service (embed outside transaction)</title>
<read_first>
- src/rag/chunker.py
- src/rag/embedder.py
- src/repositories/policy_chunk_repo.py
- src/repositories/policy_document_repo.py
- src/db/models.py
</read_first>
<action>
Create `src/rag/ingestion.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PolicyChunk, PolicyDocument
from src.rag.chunker import chunk_markdown
from src.rag.embedder import EmbeddingService
from src.repositories.policy_chunk_repo import PolicyChunkRepository
from src.repositories.policy_document_repo import PolicyDocumentRepository


@dataclass
class IngestionReport:
    doc_key: str
    title: str
    status: str  # "success" | "failed"
    chunks_created: int = 0
    error: str | None = None


class IngestionService:
    def __init__(self, session: AsyncSession, embedder: EmbeddingService, tenant_id: UUID):
        self.session = session
        self.embedder = embedder
        self.tenant_id = tenant_id
        self.chunk_repo = PolicyChunkRepository(session)
        self.doc_repo = PolicyDocumentRepository(session)

    async def ingest_document(self, file_path: Path, doc_meta: dict) -> IngestionReport:
        """
        Full pipeline for one document:
        1. Read markdown file
        2. Chunk by headings
        3. Generate embeddings (OUTSIDE transaction — network call)
        4. Open short transaction: delete old chunks + insert new ones
        """
        doc_key = doc_meta["doc_key"]
        title = doc_meta["title"]

        try:
            # Step 1: Read and chunk
            content = file_path.read_text(encoding="utf-8")
            chunks = chunk_markdown(content, doc_key=doc_key)

            if not chunks:
                return IngestionReport(doc_key=doc_key, title=title, status="failed", error="No chunks produced")

            # Step 2: Embed ALL chunks (outside transaction — network I/O)
            texts = [c.content for c in chunks]
            embeddings = await self.embedder.embed_documents(texts)

            # Step 3: Short DB transaction for delete + insert
            # Upsert document
            existing_doc = await self.doc_repo.get_by_doc_key(doc_key, self.tenant_id)
            if existing_doc:
                doc = existing_doc
                doc.title = title
                doc.doc_type = doc_meta["doc_type"]
                doc.risk_level = doc_meta["risk_level"]
                doc.content = content
            else:
                doc = PolicyDocument(
                    tenant_id=self.tenant_id,
                    doc_key=doc_key,
                    doc_type=doc_meta["doc_type"],
                    title=title,
                    effective_date=doc_meta.get("effective_date", date.today()),
                    risk_level=doc_meta["risk_level"],
                    content=content,
                )
                self.session.add(doc)
                await self.session.flush()

            # Delete existing chunks for this document
            await self.chunk_repo.delete_by_document_id(doc.id, self.tenant_id)

            # Insert new chunks with embeddings
            db_chunks = [
                PolicyChunk(
                    tenant_id=self.tenant_id,
                    doc_id=doc.id,
                    chunk_id=chunk.chunk_id,
                    section=chunk.section,
                    content=chunk.content,
                    risk_level=doc_meta["risk_level"],
                    effective_date=doc_meta.get("effective_date", date.today()),
                    embedding=embeddings[i],
                )
                for i, chunk in enumerate(chunks)
            ]
            await self.chunk_repo.bulk_insert(db_chunks)
            await self.session.commit()

            return IngestionReport(doc_key=doc_key, title=title, status="success", chunks_created=len(db_chunks))

        except Exception as e:
            await self.session.rollback()
            return IngestionReport(doc_key=doc_key, title=title, status="failed", error=str(e))

    async def ingest_directory(self, dir_path: Path, manifest: list[dict]) -> list[IngestionReport]:
        """Process all documents in manifest. Reports per-document status."""
        reports = []
        for doc_meta in manifest:
            file_path = dir_path / doc_meta["file"]
            report = await self.ingest_document(file_path, doc_meta)
            reports.append(report)
        return reports
```

Key design decisions addressing review:
- Embedding happens BEFORE any DB transaction (no long-held transaction during network calls)
- Each document gets its own commit (failure of one doesn't roll back others)
- Uses doc_key for lookup, doc.id (UUID) for FK relationships
- Explicit rollback on failure
</action>
<acceptance_criteria>
- src/rag/ingestion.py exists
- File contains `class IngestionService`
- File contains `class IngestionReport` (or @dataclass)
- Embedding call (`embed_documents`) happens BEFORE `delete_by_document_id` (embed outside transaction)
- File contains `await self.session.commit()` after insert
- File contains `await self.session.rollback()` in except block
- File uses `doc_key` for document lookup
- File uses `doc.id` (UUID) for PolicyChunk.doc_id FK
</acceptance_criteria>
</task>

<task id="03.4">
<title>Create CLI ingestion script with --dry-run and --tenant-id</title>
<read_first>
- scripts/seed_demo.py (existing CLI script pattern)
- src/rag/ingestion.py
- src/db/session.py
</read_first>
<action>
Create `scripts/ingest_policies.py`:

```python
"""CLI script to ingest policy documents into pgvector.

Usage:
    uv run python scripts/ingest_policies.py
    uv run python scripts/ingest_policies.py --dir data/policies/
    uv run python scripts/ingest_policies.py --dry-run
    uv run python scripts/ingest_policies.py --tenant-id <uuid>
"""
import asyncio
import argparse
from pathlib import Path

DOCUMENT_MANIFEST = [
    {"file": "refund_policy.md", "doc_key": "refund_policy", "doc_type": "refund_rule", "risk_level": "high", "title": "退款规则"},
    {"file": "refund_sop.md", "doc_key": "refund_sop", "doc_type": "sop", "risk_level": "medium", "title": "退款处理SOP"},
    {"file": "compensation_rules.md", "doc_key": "compensation_rules", "doc_type": "refund_rule", "risk_level": "high", "title": "补偿规则"},
    {"file": "merchant_faq.md", "doc_key": "merchant_faq", "doc_type": "faq", "risk_level": "low", "title": "商家FAQ"},
    {"file": "return_shipping.md", "doc_key": "return_shipping", "doc_type": "refund_rule", "risk_level": "medium", "title": "退货物流规则"},
    {"file": "quality_issue_policy.md", "doc_key": "quality_issue_policy", "doc_type": "refund_rule", "risk_level": "high", "title": "质量问题退款细则"},
    {"file": "partial_refund_rules.md", "doc_key": "partial_refund_rules", "doc_type": "refund_rule", "risk_level": "medium", "title": "部分退款规则"},
    {"file": "refund_time_limits.md", "doc_key": "refund_time_limits", "doc_type": "refund_rule", "risk_level": "medium", "title": "退款时效规则"},
    {"file": "high_value_refund.md", "doc_key": "high_value_refund", "doc_type": "refund_rule", "risk_level": "high", "title": "高价值订单退款规则"},
    {"file": "cross_border_refund.md", "doc_key": "cross_border_refund", "doc_type": "refund_rule", "risk_level": "medium", "title": "跨境订单退款规则"},
    {"file": "digital_goods_refund.md", "doc_key": "digital_goods_refund", "doc_type": "refund_rule", "risk_level": "low", "title": "虚拟商品退款规则"},
    {"file": "bulk_order_refund.md", "doc_key": "bulk_order_refund", "doc_type": "refund_rule", "risk_level": "medium", "title": "批量订单退款规则"},
    {"file": "customer_escalation_sop.md", "doc_key": "customer_escalation_sop", "doc_type": "sop", "risk_level": "medium", "title": "客户投诉升级SOP"},
    {"file": "compensation_approval_sop.md", "doc_key": "compensation_approval_sop", "doc_type": "sop", "risk_level": "high", "title": "补偿审批SOP"},
    {"file": "merchant_dispute_faq.md", "doc_key": "merchant_dispute_faq", "doc_type": "faq", "risk_level": "low", "title": "商家争议FAQ"},
]

async def main():
    parser = argparse.ArgumentParser(description="Ingest policy documents into pgvector")
    parser.add_argument("--dir", default="data/policies/", help="Policy documents directory")
    parser.add_argument("--dry-run", action="store_true", help="Parse and chunk only, no embedding/DB")
    parser.add_argument("--tenant-id", help="Tenant UUID (default: first tenant from DB)")
    args = parser.parse_args()

    # ... setup: resolve tenant_id, create session, create EmbeddingService
    # In dry-run mode: only chunk, print stats, do NOT create EmbeddingService or connect to DB
    # Print summary table: doc_key | status | chunks | error
    # Exit non-zero if any document failed

if __name__ == "__main__":
    asyncio.run(main())
```

Key: --dry-run does NOT instantiate EmbeddingService or require DB (addresses review concern).
</action>
<acceptance_criteria>
- scripts/ingest_policies.py exists
- DOCUMENT_MANIFEST has exactly 15 entries
- File contains `--dir`, `--dry-run`, and `--tenant-id` arguments
- File contains `asyncio.run(main())`
- `uv run python scripts/ingest_policies.py --help` exits 0
</acceptance_criteria>
</task>

<task id="03.5">
<title>Create 15 Chinese knowledge documents</title>
<read_first>
- .planning/phases/02-rag-pipeline/02-CONTEXT.md (D-01 document types, specifics section)
</read_first>
<action>
Create `data/policies/` directory with 15 Chinese Markdown documents matching the manifest. Each document:
- Uses ## and ### headings for structure (at least 3 headings per doc)
- Contains 800-3000 Chinese characters total
- Has specific rules with conditions, amounts, time limits
- Uses realistic e-commerce terminology (退款、退货、补偿、商家、订单、客服)
- Includes edge cases and exceptions in sub-sections

Files to create (matching DOCUMENT_MANIFEST exactly):
1. refund_policy.md — 退款规则（8+ sections: 七天无理由、质量问题、已发货仅退款、超时自动退款等）
2. refund_sop.md — 退款处理SOP（6+ sections）
3. compensation_rules.md — 补偿规则（5+ sections）
4. merchant_faq.md — 商家FAQ（8+ sections）
5. return_shipping.md — 退货物流规则（5+ sections）
6. quality_issue_policy.md — 质量问题退款细则（5+ sections）
7. partial_refund_rules.md — 部分退款规则（4+ sections）
8. refund_time_limits.md — 退款时效规则（5+ sections）
9. high_value_refund.md — 高价值订单退款规则（4+ sections）
10. cross_border_refund.md — 跨境订单退款规则（4+ sections）
11. digital_goods_refund.md — 虚拟商品退款规则（4+ sections）
12. bulk_order_refund.md — 批量订单退款规则（4+ sections）
13. customer_escalation_sop.md — 客户投诉升级SOP（5+ sections）
14. compensation_approval_sop.md — 补偿审批SOP（4+ sections）
15. merchant_dispute_faq.md — 商家争议FAQ（5+ sections）
</action>
<acceptance_criteria>
- data/policies/ directory exists
- Exactly 15 .md files in data/policies/ (ls data/policies/*.md | wc -l == 15)
- Each file has at least 3 ## or ### headings
- Files contain Chinese text (grep -l "退款\|退货\|补偿\|商家\|订单" data/policies/*.md | wc -l >= 12)
- refund_policy.md has >= 800 characters (wc -m)
- File names match DOCUMENT_MANIFEST entries exactly
</acceptance_criteria>
</task>

</tasks>

<verification>
- `ls data/policies/*.md | wc -l` == 15
- `uv run python scripts/ingest_policies.py --dry-run` exits 0 and shows chunk counts per document
- `uv run python -c "from src.rag.ingestion import IngestionService, IngestionReport; print('OK')"` exits 0
- `uv run python -c "from src.repositories.policy_chunk_repo import PolicyChunkRepository; print('OK')"` exits 0
</verification>

<must_haves>
- 15 Chinese knowledge documents with heading structure (exact match to manifest)
- Repositories follow existing project patterns (constructor takes AsyncSession)
- search_similar JOINs to PolicyDocument for doc_type filtering
- Eager-loads document relationship (selectinload)
- Ingestion embeds OUTSIDE DB transaction
- CLI supports --dry-run without requiring API key or DB
- CLI supports --tenant-id
- Failure of one document doesn't prevent others from ingesting
</must_haves>
