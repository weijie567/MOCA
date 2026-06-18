from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from src.rag.ingestion import IngestionService
from src.rag.parsers.base import ParsedBlock, ParseResult, safe_failed_result
from tests.rag.phase21_xfail_inventory import xfail_for


PARSER_TIMEOUT_SECONDS = 30
OCR_TIMEOUT_SECONDS_PER_PAGE = 15
SAFE_JOB_STATUSES = {"pending", "success", "failed", "review_needed", "rejected"}
FORBIDDEN_REPORT_TERMS = (
    "/Users/ming/private/policy.pdf",
    "Traceback (most recent call last)",
    "raw_bytes",
    "parser_dump",
)


class _FakeSession:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.events.append("flush")

    async def commit(self) -> None:
        self.commits += 1
        self.events.append("commit")

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.events.append("rollback")


class _FakeEmbedder:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.texts: list[str] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.events.append("embed")
        self.texts = texts
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeDocumentRepo:
    def __init__(self, doc: object | None, events: list[str] | None = None) -> None:
        self.doc = doc
        self.events = events if events is not None else []
        self.locked = False

    async def get_by_doc_key(self, doc_key: str, tenant_id: UUID):
        return self.doc

    async def get_by_doc_key_for_update(self, doc_key: str, tenant_id: UUID):
        self.events.append("lock")
        self.locked = True
        return self.doc


class _FakeBlockRepo:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.inserted = []
        self.deleted = False

    async def delete_by_document_id(self, document_id, tenant_id) -> int:
        self.deleted = True
        return 1

    async def bulk_insert(self, blocks) -> None:
        self.events.append("insert_blocks")
        self.inserted = list(blocks)


class _FakeChunkRepo:
    def __init__(self, events: list[str] | None = None, *, fail_insert: bool = False) -> None:
        self.events = events if events is not None else []
        self.inserted = []
        self.fail_insert = fail_insert

    async def delete_by_document_id(self, document_id, tenant_id) -> int:
        return 1

    async def bulk_insert(self, chunks) -> None:
        self.events.append("insert_chunks")
        if self.fail_insert:
            raise RuntimeError("Traceback (most recent call last): /Users/ming/private/policy.pdf raw_bytes")
        self.inserted = list(chunks)


class _FakeJobRepo:
    def __init__(self, events: list[str] | None = None, *, fail_create: bool = False) -> None:
        self.events = events if events is not None else []
        self.created = []
        self.fail_create = fail_create

    async def create(self, job):
        self.events.append(f"job_create:{job.stage}:{job.status}")
        if self.fail_create:
            raise RuntimeError("database unavailable")
        self.created.append(job)
        return job


class _FakeParserRegistry:
    def __init__(self, result: ParseResult, events: list[str] | None = None) -> None:
        self.result = result
        self.events = events if events is not None else []

    def parse(self, path: Path, *, doc_key: str, source_type: str, metadata: dict) -> ParseResult:
        self.events.append("parse")
        return self.result


def _block(*, source_block_id: str = "block-001", text: str = "退款审核通过后两个工作日退回。") -> ParsedBlock:
    return ParsedBlock(
        source_block_id=source_block_id,
        block_index=0,
        block_type="paragraph",
        text=text,
        normalized_text=text,
        source_type="policy_markdown",
        parser_name="fake_parser",
        parser_version="1.0",
        page_number=2,
        box=None,
        table_metadata={},
        ocr_metadata={"confidence": 92.0},
    )


def _parse_result(*, blocks: tuple[ParsedBlock, ...] | None = None) -> ParseResult:
    return ParseResult(
        status="success",
        source_type="policy_markdown",
        parser_name="fake_parser",
        parser_version="1.0",
        blocks=blocks or (_block(),),
        warnings=(),
        failure_code=None,
        safe_message=None,
    )


def _write_policy(tmp_path: Path, content: str = "visible policy text") -> Path:
    path = tmp_path / "refund_policy.md"
    path.write_text(content, encoding="utf-8")
    return path


def _doc_meta(**overrides) -> dict:
    data = {
        "doc_key": "refund_policy",
        "title": "退款规则",
        "doc_type": "refund_rule",
        "risk_level": "high",
        "source_type": "policy_markdown",
    }
    data.update(overrides)
    return data


def _existing_doc(content: str = "old visible policy text"):
    return SimpleNamespace(
        id=uuid4(),
        content=content,
        version=1,
        title="退款规则",
        doc_type="refund_rule",
        risk_level="high",
        effective_date=None,
        source_type="policy_markdown",
        source_checksum=None,
        parser_metadata_json=None,
    )


def test_parser_trace_only_metadata_does_not_bump_document_version() -> None:
    from datetime import date

    from src.rag.versioning import build_policy_version_fingerprint

    first = build_policy_version_fingerprint(
        citation_text="七天无理由正文",
        title="退款规则",
        doc_type="refund_rule",
        risk_level="high",
        effective_date=date(2026, 1, 1),
    )
    second = build_policy_version_fingerprint(
        citation_text=" 七天无理由正文 ",
        title="退款规则",
        doc_type="refund_rule",
        risk_level="high",
        effective_date=date(2026, 1, 1),
    )
    changed_semantics = build_policy_version_fingerprint(
        citation_text="七天无理由正文",
        title="退款规则",
        doc_type="refund_rule",
        risk_level="medium",
        effective_date=date(2026, 1, 1),
    )

    assert first == second
    assert first != changed_semantics


@pytest.mark.asyncio
async def test_parse_ocr_chunk_and_embed_complete_before_document_write_transaction(tmp_path: Path) -> None:
    events: list[str] = []
    doc = _existing_doc()
    session = _FakeSession(events)
    embedder = _FakeEmbedder(events)
    service = IngestionService(session=session, embedder=embedder, tenant_id=uuid4())
    service.parser_registry = _FakeParserRegistry(_parse_result(), events)
    service.doc_repo = _FakeDocumentRepo(doc, events)
    service.block_repo = _FakeBlockRepo(events)
    service.chunk_repo = _FakeChunkRepo(events)
    service.job_repo = _FakeJobRepo(events)

    report = await service.ingest_document(_write_policy(tmp_path), _doc_meta())

    assert report.status == "success"
    assert events.index("parse") < events.index("embed") < events.index("lock")
    assert events.index("lock") < events.index("insert_blocks") < events.index("insert_chunks")
    assert service.doc_repo.locked is True
    assert service.block_repo.inserted[0].source_block_id == "block-001"
    assert service.chunk_repo.inserted[0].source_block_refs_json[0]["source_block_id"] == "block-001"
    assert service.chunk_repo.inserted[0].content == "退款审核通过后两个工作日退回。"
    assert "source_block_id=block-001" in embedder.texts[0]


@pytest.mark.asyncio
async def test_pre_transaction_failures_persist_sanitized_failed_job_without_document_lock(tmp_path: Path) -> None:
    events: list[str] = []
    failure = safe_failed_result(
        source_type="policy_image",
        parser_name="fake_ocr",
        parser_version="1.0",
        failure_code="ocr_timeout",
        safe_message="Traceback (most recent call last): /Users/ming/private/policy.pdf raw_bytes",
    )
    session = _FakeSession(events)
    service = IngestionService(session=session, embedder=_FakeEmbedder(events), tenant_id=uuid4())
    service.parser_registry = _FakeParserRegistry(failure, events)
    service.doc_repo = _FakeDocumentRepo(_existing_doc(), events)
    service.job_repo = _FakeJobRepo(events)

    report = await service.ingest_document(_write_policy(tmp_path), _doc_meta(source_type="policy_image"))

    assert report.status == "failed"
    assert report.error_code == "ocr_timeout"
    assert report.job_id is not None
    assert service.doc_repo.locked is False
    failed_job = service.job_repo.created[-1]
    assert failed_job.status == "failed"
    assert failed_job.stage == "parsing"
    assert failed_job.error_code == "ocr_timeout"
    serialized = f"{report.safe_message} {failed_job.safe_message}"
    for term in FORBIDDEN_REPORT_TERMS:
        assert term not in serialized


@pytest.mark.asyncio
async def test_business_artifact_rejection_persists_failed_job_without_document_lock(tmp_path: Path) -> None:
    events: list[str] = []
    session = _FakeSession(events)
    service = IngestionService(session=session, embedder=_FakeEmbedder(events), tenant_id=uuid4())
    service.doc_repo = _FakeDocumentRepo(_existing_doc(), events)
    service.job_repo = _FakeJobRepo(events)

    report = await service.ingest_document(_write_policy(tmp_path), _doc_meta(source_type="order_export"))

    assert report.status == "failed"
    assert report.error_code == "business_artifact_rejected"
    assert service.doc_repo.locked is False
    assert service.job_repo.created[-1].status == "failed"


@pytest.mark.asyncio
async def test_db_write_failure_rolls_back_document_blocks_chunks_and_records_safe_job(tmp_path: Path) -> None:
    events: list[str] = []
    doc = _existing_doc("old content")
    session = _FakeSession(events)
    service = IngestionService(session=session, embedder=_FakeEmbedder(events), tenant_id=uuid4())
    service.parser_registry = _FakeParserRegistry(_parse_result(), events)
    service.doc_repo = _FakeDocumentRepo(doc, events)
    service.block_repo = _FakeBlockRepo(events)
    service.chunk_repo = _FakeChunkRepo(events, fail_insert=True)
    service.job_repo = _FakeJobRepo(events)

    report = await service.ingest_document(_write_policy(tmp_path), _doc_meta())

    assert report.status == "failed"
    assert report.error_code == "db_write_failed"
    assert session.rollbacks >= 1
    assert doc.version == 1
    assert doc.content == "old content"
    failed_job = service.job_repo.created[-1]
    assert failed_job.status == "failed"
    assert failed_job.stage == "persisting"
    assert failed_job.counts_json["chunks_created"] == 0
    serialized = f"{report.safe_message} {failed_job.safe_message}"
    for term in FORBIDDEN_REPORT_TERMS:
        assert term not in serialized


@pytest.mark.asyncio
async def test_db_unavailable_early_failure_returns_safe_report_without_persisted_job_id(tmp_path: Path) -> None:
    events: list[str] = []
    failure = safe_failed_result(
        source_type="policy_markdown",
        parser_name="fake_parser",
        parser_version="1.0",
        failure_code="malformed_source",
        safe_message="Policy source could not be parsed.",
    )
    session = _FakeSession(events)
    service = IngestionService(session=session, embedder=_FakeEmbedder(events), tenant_id=uuid4())
    service.parser_registry = _FakeParserRegistry(failure, events)
    service.doc_repo = _FakeDocumentRepo(_existing_doc(), events)
    service.job_repo = _FakeJobRepo(events, fail_create=True)

    report = await service.ingest_document(_write_policy(tmp_path), _doc_meta())

    assert report.status == "failed"
    assert report.job_id is None
    assert report.error_code == "job_trace_unavailable"
    assert "database unavailable" not in (report.safe_message or "")
    assert service.doc_repo.locked is False


@xfail_for("21-04-02/safe-job-report")
def test_safe_job_report_includes_status_warnings_counts_timings_and_timeout_limits() -> None:
    from src.rag.ingestion_reports import build_safe_ingestion_report

    report = build_safe_ingestion_report(
        {
            "status": "review_needed",
            "warnings": [{"code": "ocr_confidence_review_needed"}],
            "counts": {"pages": 12, "blocks": 42, "chunks": 7},
            "timings": {"parse_ms": 1200, "ocr_ms": OCR_TIMEOUT_SECONDS_PER_PAGE * 1000},
            "limits": {"parser_timeout_seconds": PARSER_TIMEOUT_SECONDS},
        }
    )

    assert report["status"] in SAFE_JOB_STATUSES
    assert report["warnings"][0]["code"] == "ocr_confidence_review_needed"
    assert report["counts"] == {"pages": 12, "blocks": 42, "chunks": 7}
    assert report["timings"]["parse_ms"] == 1200


@xfail_for("21-04-02/raw-payload-report-boundary")
def test_sanitized_failure_reasons_forbid_raw_paths_stack_traces_bytes_and_parser_dumps() -> None:
    from src.rag.ingestion_reports import sanitize_failure_reason

    unsafe_reason = {
        "path": "/Users/ming/private/policy.pdf",
        "stack": "Traceback (most recent call last)",
        "raw_bytes": b"secret-pdf-bytes",
        "parser_dump": {"object": "raw library node"},
    }

    safe_reason = sanitize_failure_reason(unsafe_reason)
    serialized = repr(safe_reason)

    assert safe_reason["failure_code"] == "parser_failed"
    for term in FORBIDDEN_REPORT_TERMS:
        assert term not in serialized
