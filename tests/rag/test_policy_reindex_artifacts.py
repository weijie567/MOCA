from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from src.rag.policy_reindex import PolicyReindexRunIdentity
from src.rag.policy_reindex_artifacts import (
    PolicyReindexArtifactError,
    build_policy_reindex_recovery_descriptor,
    load_policy_reindex_recovery_descriptor,
    load_policy_reindex_state,
    policy_reindex_descriptor_path,
    policy_reindex_state_path,
    write_policy_reindex_recovery_descriptor_create_only,
    write_policy_reindex_state_create_only,
)


NOW = datetime(2026, 8, 12, 1, 0, tzinfo=UTC)
TENANT_ID = UUID("64300000-0000-4000-8000-000000000001")
RUN_TOKEN = UUID("64340000-0000-4000-8000-000000000013")
CORPUS_ID = UUID("64340000-0000-4000-8000-000000000113")
MANIFEST_ID = UUID("64340000-0000-4000-8000-000000000213")
SOURCE_CORPUS_ID = UUID("64340000-0000-4000-8000-000000000313")
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64
SHA_E = "sha256:" + "e" * 64


def _descriptor():
    return build_policy_reindex_recovery_descriptor(
        sealed_at=NOW,
        tenant_id=TENANT_ID,
        run_token=RUN_TOKEN,
        generation_name=f"token.v1:{RUN_TOKEN.hex}",
        lease_owner="phase64.4-plan13",
        lease_expires_at=NOW + timedelta(hours=2),
        config_schema_version="embedding_tokenizer.v1",
        config_json={
            "dimensions": 1024,
            "max_embedding_tokens": 512,
            "overlap_tokens": 48,
            "target_embedding_tokens": 384,
        },
        config_fingerprint=SHA_A,
        parity_report_sha256=SHA_B,
        parity_config_fingerprint=SHA_A,
        parity_probe_fixture_sha256=SHA_C,
        parity_submitted_content_sha256=SHA_D,
        parity_captured_at=NOW - timedelta(minutes=5),
        parity_expires_at=NOW + timedelta(hours=23, minutes=55),
        source_manifest_revision_id=MANIFEST_ID,
        source_manifest_revision=7,
        source_manifest_hash=SHA_E,
        source_active_corpus_version_id=SOURCE_CORPUS_ID,
        source_rollout_epoch=11,
        expected_evidence_rollout_version=13,
    )


def _identity() -> PolicyReindexRunIdentity:
    descriptor = _descriptor()
    return PolicyReindexRunIdentity(
        corpus_version_id=CORPUS_ID,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
        generation_name=descriptor.generation_name,
        lease_owner=descriptor.lease_owner,
        lease_expires_at=descriptor.lease_expires_at,
        state="building",
        state_version=2,
        next_document_index=0,
        ordered_doc_keys=("policy-a", "policy-b"),
        config_schema_version=descriptor.config_schema_version,
        config_fingerprint=descriptor.config_fingerprint,
        provider_parity_report_hash=descriptor.parity_report_sha256,
        source_manifest_revision_id=descriptor.source_manifest_revision_id,
        source_manifest_revision=descriptor.source_manifest_revision,
        source_manifest_hash=descriptor.source_manifest_hash,
        source_active_corpus_version_id=descriptor.source_active_corpus_version_id,
        source_rollout_epoch=descriptor.source_rollout_epoch,
        expected_evidence_rollout_version=descriptor.expected_evidence_rollout_version,
        parity_captured_at=descriptor.parity_captured_at,
        parity_expires_at=descriptor.parity_expires_at,
    )


def test_recovery_descriptor_is_hashed_canonical_bounded_and_create_only(tmp_path: Path) -> None:
    descriptor = _descriptor()
    artifact = write_policy_reindex_recovery_descriptor_create_only(descriptor, root=tmp_path)

    assert artifact.path == policy_reindex_descriptor_path(
        tmp_path,
        tenant_id=TENANT_ID,
        run_token=RUN_TOKEN,
    )
    assert artifact.sha256 == descriptor.descriptor_payload_sha256
    assert load_policy_reindex_recovery_descriptor(artifact.path, root=tmp_path) == descriptor
    assert not tuple(artifact.path.parent.glob("*.tmp"))
    assert not tuple(artifact.path.parent.glob(".staging/*"))

    with pytest.raises(PolicyReindexArtifactError, match="descriptor_create_conflict"):
        write_policy_reindex_recovery_descriptor_create_only(descriptor, root=tmp_path)
    with pytest.raises(PolicyReindexArtifactError, match="descriptor_lease_window_invalid"):
        build_policy_reindex_recovery_descriptor(
            **{
                field: getattr(descriptor, field)
                for field in descriptor.__dataclass_fields__
                if field not in {"schema_version", "descriptor_payload_sha256", "lease_expires_at"}
            },
            lease_expires_at=NOW + timedelta(hours=2, microseconds=1),
        )


def test_state_publication_is_atomic_idempotent_and_conflict_closed(tmp_path: Path) -> None:
    descriptor = _descriptor()
    write_policy_reindex_recovery_descriptor_create_only(descriptor, root=tmp_path)
    owner = _identity()

    first = write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=tmp_path)
    replay = write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=tmp_path)

    assert replay == first
    assert first.path == policy_reindex_state_path(
        tmp_path,
        tenant_id=TENANT_ID,
        run_token=RUN_TOKEN,
        state_version=2,
    )
    assert load_policy_reindex_state(first.path, descriptor=descriptor, root=tmp_path) == owner

    first.path.write_bytes(first.path.read_bytes()[:-1])
    with pytest.raises(PolicyReindexArtifactError, match="state_create_conflict"):
        write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=tmp_path)
    with pytest.raises(PolicyReindexArtifactError, match="state_invalid"):
        load_policy_reindex_state(first.path, descriptor=descriptor, root=tmp_path)


@pytest.mark.parametrize("boundary", ["stage_written", "stage_fsynced", "published", "parent_fsynced"])
def test_state_fault_boundaries_never_publish_partial_bytes(tmp_path: Path, boundary: str) -> None:
    descriptor = _descriptor()
    write_policy_reindex_recovery_descriptor_create_only(descriptor, root=tmp_path)
    owner = _identity()

    def fail_at(current: str) -> None:
        if current == boundary:
            raise RuntimeError("fault")

    with pytest.raises(RuntimeError, match="fault"):
        write_policy_reindex_state_create_only(
            owner,
            descriptor=descriptor,
            root=tmp_path,
            fault_injector=fail_at,
        )

    path = policy_reindex_state_path(
        tmp_path,
        tenant_id=TENANT_ID,
        run_token=RUN_TOKEN,
        state_version=2,
    )
    if path.exists():
        assert load_policy_reindex_state(path, descriptor=descriptor, root=tmp_path) == owner
    else:
        recovered = write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=tmp_path)
        assert load_policy_reindex_state(recovered.path, descriptor=descriptor, root=tmp_path) == owner


def test_state_refuses_descriptor_or_identity_drift_before_publication(tmp_path: Path) -> None:
    descriptor = _descriptor()
    write_policy_reindex_recovery_descriptor_create_only(descriptor, root=tmp_path)

    with pytest.raises(PolicyReindexArtifactError, match="state_descriptor_mismatch"):
        write_policy_reindex_state_create_only(
            replace(_identity(), run_token=UUID("64340000-0000-4000-8000-000000000099")),
            descriptor=descriptor,
            root=tmp_path,
        )
    assert not policy_reindex_state_path(
        tmp_path,
        tenant_id=TENANT_ID,
        run_token=RUN_TOKEN,
        state_version=2,
    ).exists()
