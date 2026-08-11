from __future__ import annotations

from dataclasses import replace
from datetime import date
import inspect
from types import MappingProxyType, SimpleNamespace
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.db.models import PolicyChunk, PolicyChunkVersion, PolicyDocument, PolicyDocumentVersion, Tenant
from src.knowledge.text_hash import evidence_text_hash
from src.rag.ingestion import _policy_chunks_from_embedding_inputs
from src.rag.parsers.base import ParsedBlock
from src.rag.policy_embedding_input import PolicyEmbeddingInputV1
from src.rag.versioning import build_policy_version_fingerprint
from src.repositories.document_block_repo import (
    CANONICAL_DOCUMENT_CONTENT_SCHEMA_VERSION,
    build_canonical_document_content,
)
from src.repositories.evidence_version_repo import (
    EvidenceVersionRepository,
    canonical_chunk_version_matches_projection,
    canonical_document_version_matches_source,
)
from tests.migration_helpers import upgrade_to_head_with_evidence_cutover


DATABASE_URL = "postgresql+asyncpg://moca:moca_dev@localhost:5432/moca_test"


def _block(*, index: int, text: str, source_block_id: str | None = None) -> ParsedBlock:
    return ParsedBlock(
        source_block_id=source_block_id or f"policy:markdown:block:{index:04d}",
        block_index=index,
        block_type="paragraph",
        text=text,
        normalized_text=text.casefold(),
        source_type="policy_markdown",
        parser_name="markdown_parser",
        parser_version="21.02",
        page_number=index + 1,
        box=None,
        table_metadata={},
        ocr_metadata={},
        warnings=(),
    )


def _dto(*, config_marker: str, token_count: int = 17) -> PolicyEmbeddingInputV1:
    citation = "退款须在签收后七日内申请。"
    search_text = "退款 七日 policy"
    embedding_input = f"Policy / 退款规则: {citation}\nsource_block_id=policy:block:0000"
    return PolicyEmbeddingInputV1(
        doc_key="refund_policy",
        chunk_id="refund_policy_000",
        section="退款规则",
        citation_content=citation,
        primary_content=citation,
        overlap_content="",
        search_text=search_text,
        embedding_input=embedding_input,
        embedding_input_hash=evidence_text_hash(embedding_input),
        embedding_token_count=token_count,
        overlap_token_count=0,
        chunking_config_fingerprint=evidence_text_hash(config_marker),
        source_block_refs=(MappingProxyType({"source_block_id": "policy:block:0000", "page_number": 1}),),
        metadata=MappingProxyType({}),
        chunk_index=0,
        part_index=0,
    )


def test_canonical_document_v2_uses_ordered_authoritative_blocks_not_chunks() -> None:
    first = _block(index=0, text="第一段 authoritative source。")
    second = _block(index=1, text="第二段 authoritative source。")

    ordered = build_canonical_document_content((first, second))
    reordered_input = build_canonical_document_content((second, first))

    assert ordered == reordered_input
    assert ordered.schema_version == CANONICAL_DOCUMENT_CONTENT_SCHEMA_VERSION
    assert ordered.content == "第一段 authoritative source。\n第二段 authoritative source。"
    assert [item["source_block_id"] for item in ordered.blocks_json] == [
        first.source_block_id,
        second.source_block_id,
    ]
    assert ordered.content_hash == evidence_text_hash(ordered.content)
    assert ordered.blocks_hash.startswith("sha256:")


def test_canonical_document_v2_rejects_ambiguous_authoritative_order() -> None:
    duplicate_index = (_block(index=0, text="one"), _block(index=0, text="two"))

    try:
        build_canonical_document_content(duplicate_index)
    except ValueError as exc:
        assert str(exc) == "canonical_document_block_order_ambiguous"
    else:
        raise AssertionError("duplicate authoritative order must fail closed")


def test_plan04_dto_audit_values_are_persisted_exactly_on_current_chunks() -> None:
    dto = _dto(config_marker="token-config-a", token_count=23)
    [chunk] = _policy_chunks_from_embedding_inputs(
        tenant_id=uuid4(),
        doc_id=uuid4(),
        title="Policy",
        doc_type="refund_rule",
        risk_level="medium",
        effective_date=date(2026, 8, 11),
        assembled_inputs=(dto,),
        embeddings=[[0.0] * 1024],
    )

    assert chunk.content == dto.citation_content
    assert chunk.search_text == dto.search_text
    assert chunk.embedding_input_hash == dto.embedding_input_hash
    assert chunk.embedding_token_count == dto.embedding_token_count
    assert chunk.chunking_config_fingerprint == dto.chunking_config_fingerprint


def test_document_compatibility_ignores_chunk_config_but_requires_v2_source_snapshot() -> None:
    canonical = build_canonical_document_content((_block(index=0, text="same source"),))
    document_version = SimpleNamespace(
        source_checksum="sha256:" + "a" * 64,
        canonical_content_schema_version=canonical.schema_version,
        canonical_blocks_json=[dict(item) for item in canonical.blocks_json],
        canonical_blocks_hash=canonical.blocks_hash,
        content=canonical.content,
        content_hash=canonical.content_hash,
    )

    assert canonical_document_version_matches_source(
        document_version,
        source_checksum="sha256:" + "a" * 64,
        canonical_source=canonical,
    )
    assert not canonical_document_version_matches_source(
        document_version,
        source_checksum="sha256:" + "b" * 64,
        canonical_source=canonical,
    )

    legacy = SimpleNamespace(
        source_checksum=None,
        canonical_content_schema_version=None,
        canonical_blocks_json=None,
        canonical_blocks_hash=None,
        content=canonical.content,
        content_hash=canonical.content_hash,
    )
    assert canonical_document_version_matches_source(
        legacy,
        source_checksum="sha256:" + "a" * 64,
        canonical_source=None,
    )
    assert legacy.canonical_content_schema_version is None


def test_chunk_compatibility_is_config_aware_and_corpus_agnostic() -> None:
    dto_a = _dto(config_marker="token-config-a")
    current = SimpleNamespace(
        chunk_id=dto_a.chunk_id,
        content=dto_a.citation_content,
        search_text=dto_a.search_text,
        source_block_refs_json=[dict(ref) for ref in dto_a.source_block_refs],
        chunking_config_fingerprint=dto_a.chunking_config_fingerprint,
        embedding_input_hash=dto_a.embedding_input_hash,
        embedding_token_count=dto_a.embedding_token_count,
    )
    immutable = SimpleNamespace(
        chunk_id=current.chunk_id,
        content=current.content,
        text_hash=evidence_text_hash(current.content),
        search_text=current.search_text,
        source_locator_json={"source_type": "policy_markdown", "source_block_refs": current.source_block_refs_json},
        chunking_config_fingerprint=current.chunking_config_fingerprint,
        embedding_input_hash=current.embedding_input_hash,
        embedding_token_count=current.embedding_token_count,
    )

    assert canonical_chunk_version_matches_projection(immutable, current)
    incompatible = SimpleNamespace(**{**vars(current), "chunking_config_fingerprint": evidence_text_hash("config-b")})
    assert not canonical_chunk_version_matches_projection(immutable, incompatible)

    for callable_object in (
        canonical_document_version_matches_source,
        canonical_chunk_version_matches_projection,
        EvidenceVersionRepository.find_exact_binding,
        EvidenceVersionRepository.append_immutable_version,
    ):
        assert "corpus" not in inspect.signature(callable_object).parameters


def test_same_source_snapshot_is_unchanged_by_character_or_token_chunk_boundaries() -> None:
    blocks = (_block(index=0, text="A long authoritative source block that remains stable."),)
    canonical_before = build_canonical_document_content(blocks)
    character_dto = _dto(config_marker="character")
    token_dto = replace(character_dto, chunking_config_fingerprint=evidence_text_hash("token"))

    assert character_dto.chunking_config_fingerprint != token_dto.chunking_config_fingerprint
    assert build_canonical_document_content(blocks) == canonical_before


async def test_postgresql_reuses_document_version_and_versions_incompatible_chunk_config() -> None:
    await _reset_schema()
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    cfg.attributes["database_url"] = DATABASE_URL
    await upgrade_to_head_with_evidence_cutover(cfg, database_url=DATABASE_URL)

    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            tenant_id = uuid4()
            session.add(Tenant(id=tenant_id, name="source-identity", status="active"))
            await session.flush()
            canonical = build_canonical_document_content((_block(index=0, text="stable source"),))
            document = PolicyDocument(
                tenant_id=tenant_id,
                doc_key="stable_policy",
                doc_type="refund_rule",
                title="Stable policy",
                effective_date=date(2026, 8, 11),
                risk_level="medium",
                version=1,
                content=canonical.content,
                source_type="policy_markdown",
                source_checksum="sha256:" + "a" * 64,
                parser_metadata_json={},
                policy_version_fingerprint=build_policy_version_fingerprint(
                    citation_text=canonical.content,
                    title="Stable policy",
                    doc_type="refund_rule",
                    risk_level="medium",
                    effective_date=date(2026, 8, 11),
                ),
            )
            session.add(document)
            await session.flush()
            chunk = PolicyChunk(
                tenant_id=tenant_id,
                doc_id=document.id,
                chunk_id="stable_policy_000",
                section="intro",
                content="stable source",
                search_text="stable source search",
                source_block_refs_json=[{"source_block_id": "policy:markdown:block:0000"}],
                ocr_metadata_json={},
                risk_level="medium",
                effective_date=date(2026, 8, 11),
                embedding=None,
                chunking_config_fingerprint=evidence_text_hash("character-config"),
                embedding_input_hash=evidence_text_hash("character-input"),
                embedding_token_count=11,
            )
            session.add(chunk)
            await session.flush()

            repository = EvidenceVersionRepository(session)
            first_document, [first_chunk] = await repository.append_immutable_version(
                tenant_id=tenant_id,
                document=document,
                chunks=[chunk],
                write_sequence=1,
                canonical_source=canonical,
            )

            chunk.chunking_config_fingerprint = evidence_text_hash("token-config")
            chunk.embedding_input_hash = evidence_text_hash("token-input")
            chunk.embedding_token_count = 13
            second_document, [second_chunk] = await repository.append_immutable_version(
                tenant_id=tenant_id,
                document=document,
                chunks=[chunk],
                write_sequence=2,
                canonical_source=canonical,
            )
            third_document, [third_chunk] = await repository.append_immutable_version(
                tenant_id=tenant_id,
                document=document,
                chunks=[chunk],
                write_sequence=3,
                canonical_source=canonical,
            )

            assert first_document.id == second_document.id == third_document.id
            assert first_chunk.id != second_chunk.id
            assert second_chunk.id == third_chunk.id
            assert second_chunk.chunk_version == 2
            assert second_chunk.search_text == chunk.search_text
            assert second_chunk.chunking_config_fingerprint == chunk.chunking_config_fingerprint
            assert second_chunk.embedding_input_hash == chunk.embedding_input_hash
            assert second_chunk.embedding_token_count == chunk.embedding_token_count
            assert second_document.canonical_content_schema_version == canonical.schema_version
            assert second_document.canonical_blocks_hash == canonical.blocks_hash
            assert await session.scalar(select(func.count()).select_from(PolicyDocumentVersion)) == 1
            assert await session.scalar(select(func.count()).select_from(PolicyChunkVersion)) == 2
    finally:
        await engine.dispose()


async def _reset_schema() -> None:
    engine = create_async_engine(DATABASE_URL, future=True, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    finally:
        await engine.dispose()
