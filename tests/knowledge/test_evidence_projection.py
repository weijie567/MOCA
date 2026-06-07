from __future__ import annotations

import json

from src.knowledge.schemas import EvidenceRefV1, canonical_evidence_projection

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
