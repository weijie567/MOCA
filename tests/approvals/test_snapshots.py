from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.approvals.snapshots import (
    ActionSafetySnapshot,
    build_action_safety_snapshot,
    snapshot_hash_projection,
)
from src.common.canonical_hash import canonical_hash, canonical_json, hash_input_bytes
from src.knowledge.schemas import EvidenceRefV1


SNAPSHOT_SCHEMA_VERSION = "action_safety_snapshot.v1"
SNAPSHOT_ALLOWED_FIELDS = {
    "schema_version",
    "tenant_id",
    "run_id",
    "snapshot_id",
    "snapshot_ref",
    "policy_config_version",
    "risk_config_version",
    "retrieval_config_version",
    "evidence",
    "evidence_ids",
    "action_payload_hash",
    "target_merchant_id",
    "target_merchant_ref",
    "business_fact_refs",
    "created_at",
}
SNAPSHOT_NULLABLE_FIELDS = {
    "action_payload_hash",
    "target_merchant_id",
    "target_merchant_ref",
    "resource_version",
    "data_freshness_at",
}
PROPOSED_ACTION_HASH = "sha256:508e649e1b169a9520f7eb76403b0e00c90c1b1c52e17a499fd7bcdce2473094"
EXPECTED_SNAPSHOT_CANONICAL_JSON = (
    '{"action_payload_hash":"sha256:508e649e1b169a9520f7eb76403b0e00c90c1b1c52e17a499fd7bcdce2473094",'
    '"business_fact_refs":[{"data_freshness_at":null,"resource_id":"RF-001","resource_type":"refund_case",'
    '"resource_version":null,"retrieved_at":"2026-06-15T00:01:00.000Z",'
    '"schema_version":"business_fact_ref.v1","source_system":"moca_demo","tenant_id":"tenant-001"}],'
    '"created_at":"2026-06-15T00:00:00.000Z","evidence":[{'
    '"chunk_id":"chunk-001","doc_key":"refund-policy",'
    '"evidence_id":"refund-policy/chunk-001@v3","policy_version":"v3","rank":1,'
    '"retrieval_config_version":"retrieval.v1",'
    '"retrieved_at":"2026-06-15T00:00:00.000Z","schema_version":"evidence_ref.v1",'
    '"tenant_id":"tenant-001",'
    '"text_hash":"sha256:1111111111111111111111111111111111111111111111111111111111111111"}],'
    '"evidence_ids":["refund-policy/chunk-001@v3"],'
    '"policy_config_version":"approval-policy.v1",'
    '"retrieval_config_version":"retrieval.v1","risk_config_version":"risk-rules.v1",'
    '"run_id":"run-001","schema_version":"action_safety_snapshot.v1",'
    '"snapshot_id":"snap-001","snapshot_ref":"snapshot:snap-001","target_merchant_id":"merchant-001",'
    '"target_merchant_ref":{"business_fact_ref":{"data_freshness_at":null,"resource_id":"RF-001",'
    '"resource_type":"refund_case","resource_version":null,"retrieved_at":"2026-06-15T00:01:00.000Z",'
    '"schema_version":"business_fact_ref.v1","source_system":"moca_demo","tenant_id":"tenant-001"},'
    '"schema_version":"target_merchant_binding.v1","source":"business_fact_ref",'
    '"target_merchant_id":"merchant-001"},"tenant_id":"tenant-001"}'
)
EXPECTED_SNAPSHOT_DIGEST = "sha256:a102d45cc709ee2150da76e1999542182490f69ab5554032f0859dbaf010a07a"


def _evidence_ref(
    *,
    evidence_id: str = "refund-policy/chunk-001@v3",
    doc_key: str = "refund-policy",
    chunk_id: str = "chunk-001",
    text_hash: str = "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    retrieval_config_version: str = "retrieval.v1",
    score: float | None = 0.91,
    rank: int | None = 1,
) -> EvidenceRefV1:
    return EvidenceRefV1(
        tenant_id="tenant-001",
        evidence_id=evidence_id,
        doc_key=doc_key,
        chunk_id=chunk_id,
        policy_version="v3",
        text_hash=text_hash,
        retrieved_at="2026-06-15T00:00:00.000Z",
        retrieval_config_version=retrieval_config_version,
        score=score,
        rank=rank,
    )


def _business_fact_ref() -> dict:
    return {
        "schema_version": "business_fact_ref.v1",
        "tenant_id": "tenant-001",
        "source_system": "moca_demo",
        "resource_type": "refund_case",
        "resource_id": "RF-001",
        "resource_version": None,
        "data_freshness_at": None,
        "retrieved_at": "2026-06-15T00:01:00.000Z",
    }


def _target_merchant_ref() -> dict:
    return {
        "schema_version": "target_merchant_binding.v1",
        "target_merchant_id": "merchant-001",
        "source": "business_fact_ref",
        "business_fact_ref": _business_fact_ref(),
    }


def _snapshot_kwargs(**overrides):
    kwargs = {
        "tenant_id": "tenant-001",
        "run_id": "run-001",
        "snapshot_id": "snap-001",
        "snapshot_ref": "snapshot:snap-001",
        "policy_config_version": "approval-policy.v1",
        "risk_config_version": "risk-rules.v1",
        "retrieval_config_version": "retrieval.v1",
        "evidence": [_evidence_ref()],
        "action_payload_hash": PROPOSED_ACTION_HASH,
        "target_merchant_id": "merchant-001",
        "target_merchant_ref": _target_merchant_ref(),
        "business_fact_refs": [_business_fact_ref()],
        "created_at": "2026-06-15T00:00:00.000Z",
    }
    kwargs.update(overrides)
    return kwargs


def test_snapshot_hash_projection_contains_hash_material_and_sorted_evidence():
    snapshot = build_action_safety_snapshot(
        **_snapshot_kwargs(
            evidence=[
                _evidence_ref(
                    evidence_id="refund-policy/chunk-002@v3",
                    chunk_id="chunk-002",
                    text_hash=("sha256:2222222222222222222222222222222222222222222222222222222222222222"),
                    score=0.77,
                    rank=2,
                ),
                _evidence_ref(score=0.91, rank=1),
            ]
        )
    )

    projection = snapshot_hash_projection(snapshot)

    assert projection["schema_version"] == SNAPSHOT_SCHEMA_VERSION
    assert projection["tenant_id"] == "tenant-001"
    assert projection["run_id"] == "run-001"
    assert projection["snapshot_id"] == "snap-001"
    assert projection["snapshot_ref"] == "snapshot:snap-001"
    assert projection["policy_config_version"] == "approval-policy.v1"
    assert projection["risk_config_version"] == "risk-rules.v1"
    assert projection["retrieval_config_version"] == "retrieval.v1"
    assert projection["evidence_ids"] == [
        "refund-policy/chunk-001@v3",
        "refund-policy/chunk-002@v3",
    ]
    assert projection["action_payload_hash"] == PROPOSED_ACTION_HASH
    assert projection["created_at"] == "2026-06-15T00:00:00.000Z"
    assert [item["rank"] for item in projection["evidence"]] == [1, 2]
    assert all("score" not in item for item in projection["evidence"])
    assert all("rank" in item for item in projection["evidence"])


def test_action_safety_snapshot_v1_has_frozen_canonical_json_hash_input_and_digest():
    snapshot = build_action_safety_snapshot(**_snapshot_kwargs())
    projection = snapshot_hash_projection(snapshot)

    canonical = canonical_json(
        projection,
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        allowed_fields=SNAPSHOT_ALLOWED_FIELDS,
        nullable_fields=SNAPSHOT_NULLABLE_FIELDS,
    )
    expected_snapshot_hash_input = (
        b"hash_profile.v1\naction_safety_snapshot.v1\n" + EXPECTED_SNAPSHOT_CANONICAL_JSON.encode("utf-8")
    )

    assert canonical == EXPECTED_SNAPSHOT_CANONICAL_JSON
    assert hash_input_bytes(SNAPSHOT_SCHEMA_VERSION, canonical) == expected_snapshot_hash_input
    assert (
        canonical_hash(
            projection,
            schema_version=SNAPSHOT_SCHEMA_VERSION,
            allowed_fields=SNAPSHOT_ALLOWED_FIELDS,
            nullable_fields=SNAPSHOT_NULLABLE_FIELDS,
        )
        == EXPECTED_SNAPSHOT_DIGEST
    )
    assert snapshot.immutable_hash == EXPECTED_SNAPSHOT_DIGEST


@pytest.mark.parametrize(
    "field, overrides",
    [
        (
            "evidence text_hash",
            {
                "evidence": [
                    _evidence_ref(text_hash=("sha256:3333333333333333333333333333333333333333333333333333333333333333"))
                ]
            },
        ),
        ("evidence rank", {"evidence": [_evidence_ref(rank=2)]}),
        (
            "evidence retrieval_config_version",
            {"evidence": [_evidence_ref(retrieval_config_version="retrieval.v2")]},
        ),
        ("policy_config_version", {"policy_config_version": "approval-policy.v2"}),
        ("risk_config_version", {"risk_config_version": "risk-rules.v2"}),
        (
            "action_payload_hash",
            {"action_payload_hash": ("sha256:9999999999999999999999999999999999999999999999999999999999999999")},
        ),
    ],
)
def test_hash_material_changes_change_immutable_hash(field, overrides):
    baseline = build_action_safety_snapshot(**_snapshot_kwargs())
    changed = build_action_safety_snapshot(**_snapshot_kwargs(**overrides))

    assert changed.immutable_hash != baseline.immutable_hash, field


@pytest.mark.parametrize(
    "forbidden_key",
    ["raw_prompt", "raw_args", "raw_payload", "raw_tool_output", "secret", "pii"],
)
def test_snapshot_construction_rejects_raw_payload_keys(forbidden_key):
    snapshot = build_action_safety_snapshot(**_snapshot_kwargs())
    payload = {
        **snapshot.model_dump(),
        forbidden_key: "must not enter action_safety_snapshot.v1",
    }

    with pytest.raises(ValidationError, match=forbidden_key):
        ActionSafetySnapshot.model_validate(payload)
