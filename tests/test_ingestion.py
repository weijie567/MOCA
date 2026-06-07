from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.db.models import PolicyDocument
from src.knowledge.schemas import EvidenceRefV1
from src.rag.ingestion import IngestionService


class _FakeEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.texts = texts
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeSession:
    def __init__(self, tracked_doc: object | None = None) -> None:
        self.committed = False
        self.rolled_back = False
        self.added: list[object] = []
        self.tracked_doc = tracked_doc
        self._original_version = getattr(tracked_doc, "version", None)
        self._original_content = getattr(tracked_doc, "content", None)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if isinstance(obj, PolicyDocument) and obj.version is None:
                obj.version = 1

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
        if self.tracked_doc is not None:
            self.tracked_doc.version = self._original_version
            self.tracked_doc.content = self._original_content


class _FakeDocumentRepo:
    def __init__(self, doc: object) -> None:
        self.doc = doc
        self.locked = False

    async def get_by_doc_key_for_update(self, doc_key: str, tenant_id):
        self.locked = True
        return self.doc


class _FakeChunkRepo:
    def __init__(self, *, fail_insert: bool = False) -> None:
        self.inserted = []
        self.fail_insert = fail_insert

    async def delete_by_document_id(self, document_id, tenant_id) -> int:
        return 0

    async def bulk_insert(self, chunks) -> None:
        if self.fail_insert:
            raise RuntimeError("chunk insert failed")
        self.inserted = chunks


def _write_policy(tmp_path: Path, content: str) -> Path:
    policy_file = tmp_path / "refund_policy.md"
    policy_file.write_text(content, encoding="utf-8")
    return policy_file


def _doc_meta() -> dict:
    return {
        "doc_key": "refund_policy",
        "title": "退款规则",
        "doc_type": "refund_rule",
        "risk_level": "high",
    }


def _existing_doc(content: str, version: int = 1):
    return SimpleNamespace(
        id=uuid4(),
        content=content,
        version=version,
        title="退款规则",
        doc_type="refund_rule",
        risk_level="high",
        effective_date=None,
    )


@pytest.mark.asyncio
async def test_ingestion_embeds_title_and_section_but_persists_raw_content(tmp_path: Path):
    policy_file = _write_policy(
        tmp_path,
        """# 退款规则

## 七天无理由
商品不影响二次销售时，支持七天无理由退货退款。
""",
    )
    tenant_id = uuid4()
    doc = _existing_doc(policy_file.read_text(encoding="utf-8"))
    session = _FakeSession()
    embedder = _FakeEmbedder()
    chunk_repo = _FakeChunkRepo()

    service = IngestionService(session=session, embedder=embedder, tenant_id=tenant_id)
    service.doc_repo = _FakeDocumentRepo(doc)
    service.chunk_repo = chunk_repo

    report = await service.ingest_document(
        policy_file,
        _doc_meta(),
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


@pytest.mark.asyncio
async def test_first_import_starts_at_version_one(tmp_path: Path):
    policy_file = _write_policy(tmp_path, "# 退款规则\n\n首次内容")
    session = _FakeSession()
    service = IngestionService(session=session, embedder=_FakeEmbedder(), tenant_id=uuid4())
    service.doc_repo = _FakeDocumentRepo(None)
    service.chunk_repo = _FakeChunkRepo()

    report = await service.ingest_document(policy_file, _doc_meta())

    assert report.status == "success"
    assert len(session.added) == 1
    assert session.added[0].version == 1


@pytest.mark.asyncio
async def test_same_content_reimport_keeps_version_one_and_locks_row(tmp_path: Path):
    content = "# 退款规则\n\n相同内容"
    policy_file = _write_policy(tmp_path, content)
    doc = _existing_doc(content)
    session = _FakeSession(doc)
    doc_repo = _FakeDocumentRepo(doc)
    service = IngestionService(session=session, embedder=_FakeEmbedder(), tenant_id=uuid4())
    service.doc_repo = doc_repo
    service.chunk_repo = _FakeChunkRepo()

    report = await service.ingest_document(policy_file, _doc_meta())

    assert report.status == "success"
    assert doc.version == 1
    assert doc_repo.locked is True


@pytest.mark.asyncio
async def test_changed_content_reimport_bumps_version_and_evidence_identity(tmp_path: Path):
    policy_file = _write_policy(tmp_path, "# 退款规则\n\n变更后内容")
    doc = _existing_doc("# 退款规则\n\n变更前内容")
    session = _FakeSession(doc)
    service = IngestionService(session=session, embedder=_FakeEmbedder(), tenant_id=uuid4())
    service.doc_repo = _FakeDocumentRepo(doc)
    service.chunk_repo = _FakeChunkRepo()

    old_ref = EvidenceRefV1.build(
        tenant_id="tenant-001",
        doc_key="refund_policy",
        chunk_id="chunk_001",
        policy_version=f"v{doc.version}",
        text="变更前内容",
        retrieved_at="2026-06-05T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
    )
    report = await service.ingest_document(policy_file, _doc_meta())
    new_ref = EvidenceRefV1.build(
        tenant_id="tenant-001",
        doc_key="refund_policy",
        chunk_id="chunk_001",
        policy_version=f"v{doc.version}",
        text="变更后内容",
        retrieved_at="2026-06-05T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
    )

    assert report.status == "success"
    assert doc.version == 2
    assert old_ref.evidence_id.endswith("@v1")
    assert new_ref.evidence_id.endswith("@v2")


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
