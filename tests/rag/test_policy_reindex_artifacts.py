from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest

from src.rag import policy_reindex_artifacts
from src.rag.policy_reindex import PolicyReindexRunIdentity
from src.rag.policy_reindex_artifacts import (
    CandidateBuildResultCode,
    PolicyReindexArtifactError,
    build_policy_candidate_build_budget,
    load_candidate_build_attempt,
    policy_candidate_build_attempt_path,
    record_candidate_build_result_create_only,
    reviewed_artifact_read_bytes,
    reserve_candidate_build_attempt,
    secure_policy_reindex_artifact_namespace,
    build_policy_reindex_recovery_descriptor,
    load_policy_reindex_recovery_descriptor,
    load_policy_reindex_state,
    policy_reindex_descriptor_path,
    policy_reindex_state_path,
    write_policy_reindex_recovery_descriptor_create_only,
    write_policy_reindex_state_create_only,
    write_policy_candidate_build_budget_create_only,
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


def test_secure_namespace_rejects_run_substitution_after_open(tmp_path: Path) -> None:
    run_path = tmp_path / "tenants" / str(TENANT_ID) / "runs" / str(RUN_TOKEN)
    run_path.mkdir(parents=True)
    descriptor_path = run_path / "descriptor.json"
    descriptor_path.write_bytes(b"trusted")
    substituted_run = tmp_path / "substituted-run"
    substituted_run.mkdir()
    (substituted_run / "descriptor.json").write_bytes(b"substituted")

    with secure_policy_reindex_artifact_namespace(
        tmp_path,
        tenant_id=TENANT_ID,
        run_token=RUN_TOKEN,
    ):
        pinned_run = run_path.with_name(f"{run_path.name}.pinned")
        run_path.rename(pinned_run)
        run_path.symlink_to(substituted_run, target_is_directory=True)

        with pytest.raises(PolicyReindexArtifactError, match="artifact_namespace_invalid"):
            reviewed_artifact_read_bytes(descriptor_path)


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


def test_identical_state_replay_fsyncs_parent_before_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = _descriptor()
    write_policy_reindex_recovery_descriptor_create_only(descriptor, root=tmp_path)
    owner = _identity()
    state = write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=tmp_path)
    fsynced: list[Path] = []
    original_fsync = policy_reindex_artifacts._fsync_directory

    def record_fsync(path: Path) -> None:
        fsynced.append(path)
        original_fsync(path)

    monkeypatch.setattr(policy_reindex_artifacts, "_fsync_directory", record_fsync)

    replay = write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=tmp_path)

    assert replay == state
    assert state.path.parent in fsynced


def test_identical_state_file_exists_race_fsyncs_parent_before_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = _descriptor()
    write_policy_reindex_recovery_descriptor_create_only(descriptor, root=tmp_path)
    owner = _identity()
    state_path = policy_reindex_state_path(
        tmp_path,
        tenant_id=TENANT_ID,
        run_token=RUN_TOKEN,
        state_version=owner.state_version,
    )
    fsynced: list[Path] = []
    original_fsync = policy_reindex_artifacts._fsync_directory

    def record_fsync(path: Path) -> None:
        fsynced.append(path)
        original_fsync(path)

    def lose_link_race(source: Path, target: Path) -> None:
        Path(target).write_bytes(Path(source).read_bytes())
        raise FileExistsError

    monkeypatch.setattr(policy_reindex_artifacts, "_fsync_directory", record_fsync)
    monkeypatch.setattr(policy_reindex_artifacts.os, "link", lose_link_race)

    artifact = write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=tmp_path)

    assert artifact.path == state_path
    assert load_policy_reindex_state(state_path, descriptor=descriptor, root=tmp_path) == owner
    assert state_path.parent in fsynced


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


def _write_budget(tmp_path: Path, *, owner: PolicyReindexRunIdentity | None = None):
    descriptor = _descriptor()
    resolved_owner = owner or _identity()
    write_policy_reindex_recovery_descriptor_create_only(descriptor, root=tmp_path)
    state = write_policy_reindex_state_create_only(resolved_owner, descriptor=descriptor, root=tmp_path)
    budget = build_policy_candidate_build_budget(
        descriptor=descriptor,
        ordered_doc_keys=resolved_owner.ordered_doc_keys,
        created_at=NOW,
    )
    artifact = write_policy_candidate_build_budget_create_only(
        budget,
        descriptor=descriptor,
        root=tmp_path,
    )
    return descriptor, resolved_owner, state, budget, artifact


def test_build_budget_is_descriptor_bound_fixed_at_two_and_reserves_before_execution(tmp_path: Path) -> None:
    descriptor, owner, state, budget, artifact = _write_budget(tmp_path)

    first = reserve_candidate_build_attempt(
        descriptor=descriptor,
        owner=owner,
        state_artifact=state,
        budget=budget,
        budget_artifact=artifact,
        root=tmp_path,
        reserved_at=NOW,
        expected_input_count=15,
        expected_batch_count=2,
    )

    assert budget.schema_version == "policy_candidate_build_budget.v1"
    assert budget.max_build_executions_per_document == 2
    assert first.ordinal == 1
    assert first.document_index == 0
    assert first.doc_key_sha256 == "sha256:" + "c1f7278b77bb9eb3977b9d5373b60680c8bf81ae32ab0aebd7c16b4b9884e4d8"
    assert first.state_version == owner.state_version
    assert first.expected_input_count == 15
    assert first.expected_batch_count == 2
    assert (
        load_candidate_build_attempt(
            policy_candidate_build_attempt_path(
                tmp_path,
                tenant_id=descriptor.tenant_id,
                run_token=descriptor.run_token,
                document_index=0,
                ordinal=1,
            ),
            descriptor=descriptor,
            budget=budget,
            budget_artifact=artifact,
            root=tmp_path,
        )
        == first
    )


def test_concurrent_first_reservation_has_one_winner_and_crash_consumes_ordinal(tmp_path: Path) -> None:
    descriptor, owner, state, budget, artifact = _write_budget(tmp_path)

    def reserve() -> object:
        try:
            return reserve_candidate_build_attempt(
                descriptor=descriptor,
                owner=owner,
                state_artifact=state,
                budget=budget,
                budget_artifact=artifact,
                root=tmp_path,
                reserved_at=NOW,
                expected_input_count=1,
                expected_batch_count=1,
            )
        except PolicyReindexArtifactError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: reserve(), range(2)))
    winners = [item for item in outcomes if not isinstance(item, str)]
    refusals = [item for item in outcomes if isinstance(item, str)]

    assert len(winners) == 1
    assert refusals == ["build_reservation_conflict"]
    with pytest.raises(PolicyReindexArtifactError, match="build_retry_evidence_missing"):
        reserve_candidate_build_attempt(
            descriptor=descriptor,
            owner=owner,
            state_artifact=state,
            budget=budget,
            budget_artifact=artifact,
            root=tmp_path,
            reserved_at=NOW + timedelta(seconds=1),
            expected_input_count=1,
            expected_batch_count=1,
        )


@pytest.mark.parametrize("boundary", ["stage_written", "stage_fsynced", "published", "parent_fsynced"])
def test_reservation_fault_boundaries_never_publish_partial_bytes(tmp_path: Path, boundary: str) -> None:
    descriptor, owner, state, budget, artifact = _write_budget(tmp_path)

    def fail_at(current: str) -> None:
        if current == boundary:
            raise RuntimeError("fault")

    with pytest.raises(RuntimeError, match="fault"):
        reserve_candidate_build_attempt(
            descriptor=descriptor,
            owner=owner,
            state_artifact=state,
            budget=budget,
            budget_artifact=artifact,
            root=tmp_path,
            reserved_at=NOW,
            expected_input_count=1,
            expected_batch_count=1,
            fault_injector=fail_at,
        )

    path = policy_candidate_build_attempt_path(
        tmp_path,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
        document_index=0,
        ordinal=1,
    )
    if path.exists():
        loaded = load_candidate_build_attempt(
            path,
            descriptor=descriptor,
            budget=budget,
            budget_artifact=artifact,
            root=tmp_path,
        )
        assert loaded.ordinal == 1
    else:
        recovered = reserve_candidate_build_attempt(
            descriptor=descriptor,
            owner=owner,
            state_artifact=state,
            budget=budget,
            budget_artifact=artifact,
            root=tmp_path,
            reserved_at=NOW,
            expected_input_count=1,
            expected_batch_count=1,
        )
        assert recovered.ordinal == 1


@pytest.mark.parametrize(
    ("result_code", "retry_allowed"),
    [
        (CandidateBuildResultCode.PROVIDER_UNAVAILABLE, True),
        (CandidateBuildResultCode.PROVIDER_TRANSIENT, True),
        (CandidateBuildResultCode.CONFIG_ERROR, False),
        (CandidateBuildResultCode.PARITY_ERROR, False),
        (CandidateBuildResultCode.SOURCE_ERROR, False),
        (CandidateBuildResultCode.RESPONSE_ERROR, False),
        (CandidateBuildResultCode.PROJECTION_ERROR, False),
    ],
)
def test_second_ordinal_has_closed_safe_result_matrix(
    tmp_path: Path,
    result_code: CandidateBuildResultCode,
    retry_allowed: bool,
) -> None:
    descriptor, owner, state, budget, artifact = _write_budget(tmp_path)
    first = reserve_candidate_build_attempt(
        descriptor=descriptor,
        owner=owner,
        state_artifact=state,
        budget=budget,
        budget_artifact=artifact,
        root=tmp_path,
        reserved_at=NOW,
        expected_input_count=1,
        expected_batch_count=1,
    )
    record_candidate_build_result_create_only(
        descriptor=descriptor,
        owner=owner,
        budget=budget,
        budget_artifact=artifact,
        reservation=first,
        root=tmp_path,
        recorded_at=NOW + timedelta(seconds=1),
        result_code=result_code,
        provider_request_count=1 if "provider" in result_code.value else 0,
    )

    if retry_allowed:
        second = reserve_candidate_build_attempt(
            descriptor=descriptor,
            owner=owner,
            state_artifact=state,
            budget=budget,
            budget_artifact=artifact,
            root=tmp_path,
            reserved_at=NOW + timedelta(seconds=2),
            expected_input_count=1,
            expected_batch_count=1,
        )
        assert second.ordinal == 2
        with pytest.raises(PolicyReindexArtifactError, match="build_budget_exhausted"):
            reserve_candidate_build_attempt(
                descriptor=descriptor,
                owner=owner,
                state_artifact=state,
                budget=budget,
                budget_artifact=artifact,
                root=tmp_path,
                reserved_at=NOW + timedelta(seconds=3),
                expected_input_count=1,
                expected_batch_count=1,
            )
    else:
        with pytest.raises(PolicyReindexArtifactError, match="build_retry_not_allowed"):
            reserve_candidate_build_attempt(
                descriptor=descriptor,
                owner=owner,
                state_artifact=state,
                budget=budget,
                budget_artifact=artifact,
                root=tmp_path,
                reserved_at=NOW + timedelta(seconds=2),
                expected_input_count=1,
                expected_batch_count=1,
            )


def test_advanced_state_and_alternate_root_or_expiry_refuse_before_reservation(tmp_path: Path) -> None:
    descriptor, owner, state, budget, artifact = _write_budget(tmp_path)
    advanced = replace(owner, state_version=3, next_document_index=1)

    refusals = (
        (
            {"owner": advanced},
            "build_state_descriptor_mismatch",
        ),
        (
            {"root": tmp_path / "alternate"},
            "build_artifact_root_mismatch",
        ),
        (
            {"reserved_at": descriptor.lease_expires_at},
            "build_authority_expired",
        ),
        (
            {"reserved_at": descriptor.parity_expires_at},
            "build_authority_expired",
        ),
    )
    for changes, code in refusals:
        arguments = {
            "descriptor": descriptor,
            "owner": owner,
            "state_artifact": state,
            "budget": budget,
            "budget_artifact": artifact,
            "root": tmp_path,
            "reserved_at": NOW,
            "expected_input_count": 1,
            "expected_batch_count": 1,
        }
        arguments.update(changes)
        with pytest.raises(PolicyReindexArtifactError, match=code):
            reserve_candidate_build_attempt(**arguments)
