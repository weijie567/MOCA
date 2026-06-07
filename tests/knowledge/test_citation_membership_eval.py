"""BLOCKING citation-membership eval gate.

Membership means a cited evidence_id is present in the retrieved evidence refs.
It is not semantic claim support, which requires a separate evaluation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.knowledge.citation import validate_membership
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1

DATASET_PATH = Path(__file__).parent / "datasets" / "citation_membership_v1.json"
DATASET_SHA256 = "sha256:3ac980b66024b2e4ebd404690aa22722a3818ff22c2f9015134f1eda57ac681b"


def _load_dataset() -> dict:
    return json.loads(DATASET_PATH.read_text())


def _evidence_ref(evidence_id: str) -> EvidenceRefV1:
    doc_key, versioned_chunk = evidence_id.split("/", maxsplit=1)
    chunk_id, policy_version = versioned_chunk.rsplit("@", maxsplit=1)
    return EvidenceRefV1.build(
        tenant_id="eval-tenant",
        doc_key=doc_key,
        chunk_id=chunk_id,
        policy_version=policy_version,
        text=f"Fixture text for {evidence_id}",
        retrieved_at="2026-06-07T00:00:00+00:00",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
    )


def test_dataset_hash_pinned():
    actual = f"sha256:{hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()}"

    assert actual == DATASET_SHA256


@pytest.mark.parametrize("case", _load_dataset()["cases"], ids=lambda case: case["id"])
def test_membership_eval_gate(case):
    refs = [_evidence_ref(evidence_id) for evidence_id in case["evidence_ids"]]

    result = validate_membership(case["claims"], refs)

    assert result.is_valid is case["expected_is_valid"]
