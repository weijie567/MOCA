from __future__ import annotations

from src.knowledge.schemas import EvidenceRefV1

FIXED_RETRIEVED_AT = "2026-06-05T00:00:00.000Z"


def make_evidence_ref(
    *,
    doc_key: str = "policy_refund_timeout",
    chunk_id: str = "chunk_001",
    policy_version: str = "v3",
    text: str = "退款超时",
    score: float | None = 0.82,
    rank: int | None = 1,
) -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id="tenant-001",
        doc_key=doc_key,
        chunk_id=chunk_id,
        policy_version=policy_version,
        text=text,
        retrieved_at=FIXED_RETRIEVED_AT,
        retrieval_config_version="retrieval.v3",
        score=score,
        rank=rank,
    )
