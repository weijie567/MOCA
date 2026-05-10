from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.rag.ingestion import IngestionService


class _FakeEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.texts = texts
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def add(self, obj: object) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _FakeDocumentRepo:
    def __init__(self, doc: object) -> None:
        self.doc = doc

    async def get_by_doc_key(self, doc_key: str, tenant_id):
        return self.doc


class _FakeChunkRepo:
    def __init__(self) -> None:
        self.inserted = []

    async def delete_by_document_id(self, document_id, tenant_id) -> int:
        return 0

    async def bulk_insert(self, chunks) -> None:
        self.inserted = chunks


@pytest.mark.asyncio
async def test_ingestion_embeds_title_and_section_but_persists_raw_content(tmp_path: Path):
    policy_file = tmp_path / "refund_policy.md"
    policy_file.write_text(
        """# 退款规则

## 七天无理由
商品不影响二次销售时，支持七天无理由退货退款。
""",
        encoding="utf-8",
    )
    tenant_id = uuid4()
    doc = SimpleNamespace(id=uuid4())
    session = _FakeSession()
    embedder = _FakeEmbedder()
    chunk_repo = _FakeChunkRepo()

    service = IngestionService(session=session, embedder=embedder, tenant_id=tenant_id)
    service.doc_repo = _FakeDocumentRepo(doc)
    service.chunk_repo = chunk_repo

    report = await service.ingest_document(
        policy_file,
        {
            "doc_key": "refund_policy",
            "title": "退款规则",
            "doc_type": "refund_rule",
            "risk_level": "high",
        },
    )

    assert report.status == "success"
    assert embedder.texts == [
        "退款规则: # 退款规则",
        "退款规则 / 七天无理由: 商品不影响二次销售时，支持七天无理由退货退款。",
    ]
    assert [chunk.content for chunk in chunk_repo.inserted] == [
        "# 退款规则",
        "商品不影响二次销售时，支持七天无理由退货退款。",
    ]
    assert session.committed is True
