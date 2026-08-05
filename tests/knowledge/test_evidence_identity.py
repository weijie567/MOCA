from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from src.knowledge.evidence_identity import (
    CanonicalEvidenceIdentityV1,
    EvidenceIdentityExternalReason,
    EvidenceIdentityInternalReason,
    EvidenceIdentityResolutionStatus,
    PersistedEvidenceIdentityMaterialV1,
    mint_canonical_evidence_identity,
    resolve_evidence_identity,
    validate_canonical_evidence_identity,
)
from src.knowledge.schemas import EvidenceRefV1

TENANT_ID = "11111111-1111-1111-1111-111111111111"
OTHER_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DOCUMENT_VERSION_ID = "22222222-2222-2222-2222-222222222222"
CHUNK_VERSION_ID = "33333333-3333-3333-3333-333333333333"
TEXT_HASH = "sha256:14da429414366e3cf6996d34022943fe381b4901065dc785fdc66107402a1427"
CANONICAL_EVIDENCE_ID = "sha256:0c1b1ceffc3982d9df4e1248242ecc670b0d1f4be718dfe291051eebcff1d764"


def _material(**updates: Any) -> PersistedEvidenceIdentityMaterialV1:
    values: dict[str, Any] = {
        "tenant_id": TENANT_ID,
        "scope_type": "tenant_policy",
        "scope_id": TENANT_ID,
        "document_version_id": DOCUMENT_VERSION_ID,
        "chunk_version_id": CHUNK_VERSION_ID,
        "doc_key": "refund_policy",
        "document_version": 3,
        "chunk_id": "refund_001",
        "chunk_version": 2,
        "text_hash": TEXT_HASH,
    }
    values.update(updates)
    return PersistedEvidenceIdentityMaterialV1.model_validate(values)


def _mint(material: PersistedEvidenceIdentityMaterialV1 | None = None):
    return mint_canonical_evidence_identity(
        material or _material(),
        expected_tenant_id=TENANT_ID,
        expected_scope_type="tenant_policy",
        expected_scope_id=TENANT_ID,
    )


def test_canonical_identity_has_frozen_scope_bound_hash_golden():
    result = _mint()

    assert result.status is EvidenceIdentityResolutionStatus.CANONICAL
    assert result.internal_reason is EvidenceIdentityInternalReason.OK
    assert result.external_reason is None
    assert result.identity is not None
    assert result.identity.evidence_id == CANONICAL_EVIDENCE_ID
    assert result.identity.hash_material() == {
        "schema_version": "evidence_identity.v1",
        "tenant_id": TENANT_ID,
        "scope_type": "tenant_policy",
        "scope_id": TENANT_ID,
        "document_version_id": DOCUMENT_VERSION_ID,
        "chunk_version_id": CHUNK_VERSION_ID,
        "doc_key": "refund_policy",
        "document_version": 3,
        "chunk_id": "refund_001",
        "chunk_version": 2,
        "text_hash": TEXT_HASH,
    }

    with pytest.raises(ValidationError):
        result.identity.scope_id = OTHER_TENANT_ID


def test_evidence_ref_serializes_owner_produced_immutable_binding_as_exact_strings():
    identity = _mint().identity
    assert identity is not None

    ref = EvidenceRefV1.from_canonical_identity(
        identity,
        retrieved_at="2026-06-05T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
        score=0.82,
        rank=1,
    )
    serialized = ref.model_dump(mode="json")

    assert serialized["scope_type"] == "tenant_policy"
    assert serialized["scope_id"] == TENANT_ID
    assert serialized["document_version_id"] == DOCUMENT_VERSION_ID
    assert serialized["chunk_version_id"] == CHUNK_VERSION_ID
    assert serialized["document_version"] == 3
    assert serialized["chunk_version"] == 2
    assert serialized["evidence_id"] == CANONICAL_EVIDENCE_ID
    assert set(CanonicalEvidenceIdentityV1.model_fields) <= set(EvidenceRefV1.model_fields) | {"schema_version"}


def test_score_rank_and_retrieval_metadata_do_not_change_identity():
    identity = _mint().identity
    assert identity is not None

    first = EvidenceRefV1.from_canonical_identity(
        identity,
        retrieved_at="2026-06-05T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
        score=0.82,
        rank=1,
    )
    second = EvidenceRefV1.from_canonical_identity(
        identity,
        retrieved_at="2026-07-01T00:00:00.000Z",
        retrieval_config_version="retrieval.v4",
        score=0.21,
        rank=9,
    )

    assert first.evidence_id == second.evidence_id == CANONICAL_EVIDENCE_ID
    assert first.to_canonical_identity() == second.to_canonical_identity() == identity


@pytest.mark.parametrize(
    ("material_updates", "request_updates", "reason"),
    [
        ({"tenant_id": OTHER_TENANT_ID, "scope_id": OTHER_TENANT_ID}, {}, "tenant_mismatch"),
        ({"scope_id": OTHER_TENANT_ID}, {}, "scope_mismatch"),
        ({}, {"expected_scope_id": OTHER_TENANT_ID}, "scope_mismatch"),
        ({}, {"expected_scope_type": "merchant_policy"}, "unsupported_scope"),
    ],
)
def test_tenant_request_scope_and_same_tenant_cross_scope_fail_generically(
    material_updates: dict[str, Any],
    request_updates: dict[str, str],
    reason: str,
):
    expected = {
        "expected_tenant_id": TENANT_ID,
        "expected_scope_type": "tenant_policy",
        "expected_scope_id": TENANT_ID,
    }
    expected.update(request_updates)

    result = mint_canonical_evidence_identity(_material(**material_updates), **expected)

    assert result.status is EvidenceIdentityResolutionStatus.INVALID
    assert result.internal_reason.value == reason
    assert result.external_reason is EvidenceIdentityExternalReason.EVIDENCE_UNAVAILABLE
    assert result.identity is None


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("text_hash", "sha256:" + "f" * 64, EvidenceIdentityInternalReason.HASH_MISMATCH),
        ("document_version", 4, EvidenceIdentityInternalReason.VERSION_MISMATCH),
        ("chunk_version", 3, EvidenceIdentityInternalReason.VERSION_MISMATCH),
        (
            "document_version_id",
            "44444444-4444-4444-4444-444444444444",
            EvidenceIdentityInternalReason.VERSION_MISMATCH,
        ),
    ],
)
def test_validation_recomputes_persisted_hash_and_versions(
    field: str, value: Any, reason: EvidenceIdentityInternalReason
):
    identity = _mint().identity
    assert identity is not None
    untrusted = identity.model_dump()
    untrusted[field] = value

    result = validate_canonical_evidence_identity(
        untrusted,
        _material(),
        expected_tenant_id=TENANT_ID,
        expected_scope_type="tenant_policy",
        expected_scope_id=TENANT_ID,
    )

    assert result.status is EvidenceIdentityResolutionStatus.INVALID
    assert result.internal_reason is reason
    assert result.external_reason is EvidenceIdentityExternalReason.EVIDENCE_UNAVAILABLE


def test_legacy_alias_is_only_canonical_after_unique_persisted_resolution():
    resolved = resolve_evidence_identity(
        "refund_policy/refund_001@v3",
        [_material()],
        expected_tenant_id=TENANT_ID,
        expected_scope_type="tenant_policy",
        expected_scope_id=TENANT_ID,
    )
    unresolved = resolve_evidence_identity(
        "refund_policy/refund_001@v3",
        [],
        expected_tenant_id=TENANT_ID,
        expected_scope_type="tenant_policy",
        expected_scope_id=TENANT_ID,
    )

    assert resolved.status is EvidenceIdentityResolutionStatus.LEGACY_RESOLVED
    assert resolved.identity is not None
    assert resolved.identity.evidence_id == CANONICAL_EVIDENCE_ID
    assert unresolved.status is EvidenceIdentityResolutionStatus.LEGACY_UNRESOLVED
    assert unresolved.identity is None
    assert unresolved.external_reason is EvidenceIdentityExternalReason.EVIDENCE_UNAVAILABLE


def test_ambiguous_and_malformed_legacy_aliases_never_become_canonical():
    ambiguous = resolve_evidence_identity(
        "refund_policy/refund_001@v3",
        [_material(), _material(chunk_version_id="44444444-4444-4444-4444-444444444444")],
        expected_tenant_id=TENANT_ID,
        expected_scope_type="tenant_policy",
        expected_scope_id=TENANT_ID,
    )
    malformed = resolve_evidence_identity(
        "refund_policy/refund_001@latest",
        [_material()],
        expected_tenant_id=TENANT_ID,
        expected_scope_type="tenant_policy",
        expected_scope_id=TENANT_ID,
    )

    assert ambiguous.status is EvidenceIdentityResolutionStatus.LEGACY_UNRESOLVED
    assert ambiguous.internal_reason is EvidenceIdentityInternalReason.AMBIGUOUS
    assert malformed.status is EvidenceIdentityResolutionStatus.INVALID
    assert malformed.internal_reason is EvidenceIdentityInternalReason.MALFORMED


def test_all_resolution_failures_share_one_external_reason():
    failures = [
        resolve_evidence_identity(
            "refund_policy/refund_001@v3",
            [_material(tenant_id=OTHER_TENANT_ID, scope_id=OTHER_TENANT_ID)],
            expected_tenant_id=TENANT_ID,
            expected_scope_type="tenant_policy",
            expected_scope_id=TENANT_ID,
        ),
        resolve_evidence_identity(
            CANONICAL_EVIDENCE_ID,
            [_material(text_hash="sha256:" + "f" * 64)],
            expected_tenant_id=TENANT_ID,
            expected_scope_type="tenant_policy",
            expected_scope_id=TENANT_ID,
        ),
        resolve_evidence_identity(
            "missing/chunk@v1",
            [],
            expected_tenant_id=TENANT_ID,
            expected_scope_type="tenant_policy",
            expected_scope_id=TENANT_ID,
        ),
    ]

    assert {result.external_reason for result in failures} == {EvidenceIdentityExternalReason.EVIDENCE_UNAVAILABLE}


def test_legacy_builder_does_not_infer_merchant_policy_scope_from_context():
    ref = EvidenceRefV1.build(
        tenant_id=TENANT_ID,
        doc_key="refund_policy",
        chunk_id="refund_001",
        policy_version="v3",
        text="退款超时",
        retrieved_at="2026-06-05T00:00:00.000Z",
        retrieval_config_version="retrieval.v3",
    )

    assert ref.scope_type is None
    assert ref.scope_id is None
    assert ref.document_version_id is None
    assert ref.chunk_version_id is None
