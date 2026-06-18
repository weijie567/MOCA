from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PolicyChunk, PolicyDocument
from src.rag.chunker import chunk_markdown
from src.rag.embedder import EmbeddingService
from src.rag.search_text import build_policy_chunk_search_text
from src.repositories.policy_chunk_repo import PolicyChunkRepository
from src.repositories.policy_document_repo import PolicyDocumentRepository


@dataclass
class IngestionReport:
    doc_key: str
    title: str
    status: str
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

            texts = [
                f"{title}: {chunk.content}"
                if chunk.section == "intro"
                else f"{title} / {chunk.section}: {chunk.content}"
                for chunk in chunks
            ]
            embeddings = await self.embedder.embed_documents(texts)
            if len(embeddings) != len(chunks):
                msg = f"Embedding count mismatch: expected {len(chunks)}, got {len(embeddings)}"
                return IngestionReport(doc_key=doc_key, title=title, status="failed", error=msg)

            effective_date = doc_meta.get("effective_date", date.today())
            # Lock the existing row through the final commit so concurrent
            # re-imports cannot write the same next content version.
            existing_doc = await self.doc_repo.get_by_doc_key_for_update(doc_key, self.tenant_id)
            if existing_doc:
                doc = existing_doc
                content_changed = doc.content != content
                if content_changed:
                    doc.version = (doc.version or 1) + 1
                doc.title = title
                doc.doc_type = doc_meta["doc_type"]
                doc.risk_level = doc_meta["risk_level"]
                doc.effective_date = effective_date
                doc.content = content
            else:
                doc = PolicyDocument(
                    tenant_id=self.tenant_id,
                    doc_key=doc_key,
                    doc_type=doc_meta["doc_type"],
                    title=title,
                    effective_date=effective_date,
                    risk_level=doc_meta["risk_level"],
                    content=content,
                )
                self.session.add(doc)
                await self.session.flush()

            await self.chunk_repo.delete_by_document_id(doc.id, self.tenant_id)

            db_chunks = [
                PolicyChunk(
                    tenant_id=self.tenant_id,
                    doc_id=doc.id,
                    chunk_id=chunk.chunk_id,
                    section=chunk.section,
                    content=chunk.content,
                    search_text=build_policy_chunk_search_text(
                        title=title,
                        section=chunk.section,
                        content=chunk.content,
                        doc_type=doc_meta["doc_type"],
                        risk_level=doc_meta["risk_level"],
                    ),
                    risk_level=doc_meta["risk_level"],
                    effective_date=effective_date,
                    embedding=embeddings[index],
                )
                for index, chunk in enumerate(chunks)
            ]
            await self.chunk_repo.bulk_insert(db_chunks)
            await self.session.commit()

            return IngestionReport(doc_key=doc_key, title=title, status="success", chunks_created=len(db_chunks))
        except Exception as exc:
            await self.session.rollback()
            return IngestionReport(doc_key=doc_key, title=title, status="failed", error=str(exc))

    async def ingest_directory(self, dir_path: Path, manifest: list[dict]) -> list[IngestionReport]:
        """Process all documents in manifest and report per-document status."""
        reports = []
        for doc_meta in manifest:
            file_path = dir_path / doc_meta["file"]
            report = await self.ingest_document(file_path, doc_meta)
            reports.append(report)
        return reports
