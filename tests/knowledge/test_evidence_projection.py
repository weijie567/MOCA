from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.knowledge.schemas import EvidenceRefV1, canonical_evidence_projection
from src.knowledge.text_hash import evidence_text_hash
from src.rag.embedding_tokenizer import load_embedding_tokenizer_config
from src.rag.ingestion import (
    CharacterCompatibilityAssembler,
    PolicyCorpusConfigError,
    assembler_for_active_policy_corpus,
)
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler
from src.repositories.evidence_version_repo import canonical_chunk_version_matches_projection
from src.db.models import CorpusBlockBinding, CorpusChunkBinding, CorpusDocumentBinding
from src.repositories.policy_corpus_scope import ActivePolicyCorpusScope, bind_active_policy_projection

from .conftest import FIXED_RETRIEVED_AT, make_evidence_ref


def test_build_derives_stable_evidence_identity():
    ref = make_evidence_ref()

    assert ref.evidence_id == "policy_refund_timeout/chunk_001@v3"


def test_canonical_projection_strips_score_and_sorts_by_rank():
    refs = [
        make_evidence_ref(doc_key="policy-c", chunk_id="chunk-c", rank=3),
        make_evidence_ref(doc_key="policy-a", chunk_id="chunk-a", rank=1),
        make_evidence_ref(doc_key="policy-b", chunk_id="chunk-b", rank=2),
    ]

    projected = canonical_evidence_projection(refs)

    assert all("score" not in item for item in projected)
    assert [item["rank"] for item in projected] == [1, 2, 3]


def test_canonical_projection_mixed_rank_falls_back_to_identity_sort():
    refs = [
        make_evidence_ref(doc_key="policy-z", chunk_id="chunk-z", rank=1),
        make_evidence_ref(doc_key="policy-a", chunk_id="chunk-a", rank=None),
        make_evidence_ref(doc_key="policy-m", chunk_id="chunk-m", rank=2),
    ]

    projected = canonical_evidence_projection(refs)

    assert [item["evidence_id"] for item in projected] == [
        "policy-a/chunk-a@v3",
        "policy-m/chunk-m@v3",
        "policy-z/chunk-z@v3",
    ]


def test_canonical_projection_has_frozen_golden_bytes():
    refs = [
        EvidenceRefV1(
            tenant_id="tenant-001",
            evidence_id="policy-b/chunk-b@v2",
            doc_key="policy-b",
            chunk_id="chunk-b",
            policy_version="v2",
            text_hash="sha256:bbbb",
            retrieved_at=FIXED_RETRIEVED_AT,
            retrieval_config_version="retrieval.v3",
            score=0.91,
            rank=2,
        ),
        EvidenceRefV1(
            tenant_id="tenant-001",
            evidence_id="policy-a/chunk-a@v1",
            doc_key="policy-a",
            chunk_id="chunk-a",
            policy_version="v1",
            text_hash="sha256:aaaa",
            retrieved_at=FIXED_RETRIEVED_AT,
            retrieval_config_version="retrieval.v3",
            score=0.82,
            rank=1,
        ),
    ]

    golden_bytes = json.dumps(
        canonical_evidence_projection(refs),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()

    assert golden_bytes == (
        b'[{"chunk_id":"chunk-a","doc_key":"policy-a","evidence_id":"policy-a/chunk-a@v1",'
        b'"policy_version":"v1","rank":1,"retrieval_config_version":"retrieval.v3",'
        b'"retrieved_at":"2026-06-05T00:00:00.000Z","schema_version":"evidence_ref.v1",'
        b'"tenant_id":"tenant-001","text_hash":"sha256:aaaa"},'
        b'{"chunk_id":"chunk-b","doc_key":"policy-b","evidence_id":"policy-b/chunk-b@v2",'
        b'"policy_version":"v2","rank":2,"retrieval_config_version":"retrieval.v3",'
        b'"retrieved_at":"2026-06-05T00:00:00.000Z","schema_version":"evidence_ref.v1",'
        b'"tenant_id":"tenant-001","text_hash":"sha256:bbbb"}]'
    )


def test_same_logical_chunk_keeps_identity_and_hash_across_retrievals():
    first = make_evidence_ref(score=0.82, rank=1)
    second = make_evidence_ref(score=0.75, rank=3)

    assert first.evidence_id == second.evidence_id
    assert first.text_hash == second.text_hash


def test_immutable_chunk_compatibility_is_corpus_free():
    current = SimpleNamespace(
        chunk_id="refund_policy_001",
        content="退款必须原路返回。",
        search_text="退款 原路返回",
        source_block_refs_json=[{"source_block_id": "refund:block:0001"}],
        chunking_config_fingerprint=evidence_text_hash("token-config"),
        embedding_input_hash=evidence_text_hash("provider-input"),
        embedding_token_count=19,
    )
    immutable = SimpleNamespace(
        chunk_id=current.chunk_id,
        content=current.content,
        text_hash=evidence_text_hash(current.content),
        search_text=current.search_text,
        source_locator_json={"source_block_refs": current.source_block_refs_json},
        chunking_config_fingerprint=current.chunking_config_fingerprint,
        embedding_input_hash=current.embedding_input_hash,
        embedding_token_count=current.embedding_token_count,
    )

    assert canonical_chunk_version_matches_projection(immutable, current)
    current.corpus_version_id = "corpus-b"
    immutable.corpus_version_id = "corpus-a"
    assert canonical_chunk_version_matches_projection(immutable, current)


def _active_scope(**overrides: object) -> ActivePolicyCorpusScope:
    data: dict[str, object] = {
        "tenant_id": uuid4(),
        "corpus_version_id": uuid4(),
        "generation_name": "character.v1",
        "config_schema_version": "character_compatibility.v1",
        "config_fingerprint": CharacterCompatibilityAssembler().config_fingerprint,
        "rollout_epoch": 1,
    }
    data.update(overrides)
    return ActivePolicyCorpusScope(**data)  # type: ignore[arg-type]


def test_active_character_corpus_selects_only_character_compatibility_assembler() -> None:
    assembler = assembler_for_active_policy_corpus(_active_scope())

    assert isinstance(assembler, CharacterCompatibilityAssembler)


def test_active_token_corpus_selects_only_pinned_token_assembler() -> None:
    token_config = load_embedding_tokenizer_config()
    assembler = assembler_for_active_policy_corpus(
        _active_scope(
            generation_name="token.selected.v1",
            config_schema_version=token_config.schema_version,
            config_fingerprint=token_config.config_fingerprint,
        )
    )

    assert isinstance(assembler, PolicyEmbeddingInputAssembler)
    assert assembler.config.config_fingerprint == token_config.config_fingerprint


@pytest.mark.parametrize(
    "overrides",
    [
        {"generation_name": "unknown.v1"},
        {"config_schema_version": "unknown.v1"},
        {"config_fingerprint": evidence_text_hash("drifted-config")},
        {
            "generation_name": "character.v1",
            "config_schema_version": "embedding_tokenizer.v1",
            "config_fingerprint": load_embedding_tokenizer_config().config_fingerprint,
        },
    ],
)
def test_active_unknown_mixed_or_drifted_config_fails_closed(overrides: dict[str, object]) -> None:
    with pytest.raises(PolicyCorpusConfigError, match="active_policy_corpus_config_unavailable"):
        assembler_for_active_policy_corpus(_active_scope(**overrides))


class _BindingResult:
    def __init__(self, *, row=None, scalar=None, values=()) -> None:
        self.row = row
        self.scalar = scalar
        self.values = values

    def one_or_none(self):
        return self.row

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def all(self):
        return self.values

    def __iter__(self):
        return iter(self.values)


class _BindingSession:
    def __init__(self, results: list[_BindingResult]) -> None:
        self.results = results
        self.added: list[object] = []
        self.flushed = False

    async def execute(self, statement):
        return self.results.pop(0)

    def add(self, row: object) -> None:
        self.added.append(row)

    def add_all(self, rows: list[object]) -> None:
        self.added.extend(rows)

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.asyncio
async def test_active_projection_binding_resolves_pointer_and_binds_exact_immutable_rows() -> None:
    scope = _active_scope()
    document_id = uuid4()
    document_version_id = uuid4()
    block_id = uuid4()
    chunk_id = uuid4()
    chunk_version_id = uuid4()
    source_refs = [{"source_block_id": "refund:block:0001"}]
    document = SimpleNamespace(id=document_id, tenant_id=scope.tenant_id)
    document_version = SimpleNamespace(
        id=document_version_id,
        tenant_id=scope.tenant_id,
        policy_document_id=document_id,
    )
    block = SimpleNamespace(id=block_id, tenant_id=scope.tenant_id, doc_id=document_id)
    chunk = SimpleNamespace(
        id=chunk_id,
        tenant_id=scope.tenant_id,
        doc_id=document_id,
        chunk_id="refund_001",
        content="退款必须原路返回。",
        search_text="退款 原路返回",
        source_block_refs_json=source_refs,
        chunking_config_fingerprint=scope.config_fingerprint,
        embedding_input_hash=evidence_text_hash("provider-input"),
        embedding_token_count=19,
    )
    chunk_version = SimpleNamespace(
        id=chunk_version_id,
        tenant_id=scope.tenant_id,
        policy_document_version_id=document_version_id,
        chunk_id=chunk.chunk_id,
        content=chunk.content,
        text_hash=evidence_text_hash(chunk.content),
        search_text=chunk.search_text,
        source_locator_json={"source_block_refs": source_refs},
        chunking_config_fingerprint=chunk.chunking_config_fingerprint,
        embedding_input_hash=chunk.embedding_input_hash,
        embedding_token_count=chunk.embedding_token_count,
    )
    rollout = SimpleNamespace(
        tenant_id=scope.tenant_id,
        active_corpus_version_id=scope.corpus_version_id,
        rollout_epoch=scope.rollout_epoch,
    )
    corpus = SimpleNamespace(
        id=scope.corpus_version_id,
        generation_name=scope.generation_name,
        config_schema_version=scope.config_schema_version,
        config_fingerprint=scope.config_fingerprint,
    )
    session = _BindingSession(
        [
            _BindingResult(row=(rollout, corpus)),
            _BindingResult(scalar=None),
            _BindingResult(values=()),
            _BindingResult(values=()),
        ]
    )

    resolved = await bind_active_policy_projection(
        session,  # type: ignore[arg-type]
        tenant_id=scope.tenant_id,
        document=document,  # type: ignore[arg-type]
        blocks=[block],  # type: ignore[list-item]
        chunks=[chunk],  # type: ignore[list-item]
        document_version=document_version,  # type: ignore[arg-type]
        chunk_versions=[chunk_version],  # type: ignore[list-item]
    )

    assert resolved == scope
    assert {type(row) for row in session.added} == {
        CorpusDocumentBinding,
        CorpusBlockBinding,
        CorpusChunkBinding,
    }
    assert {row.corpus_version_id for row in session.added} == {scope.corpus_version_id}
    assert session.flushed is True
