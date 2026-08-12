"""Crash-safe immutable authority for reviewed policy candidate rebuilds.

The filesystem contracts in this module are deterministic only.  They never
construct a provider, query a database, or mutate the active corpus pointer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from enum import StrEnum
from typing import Any, Callable
from uuid import UUID


POLICY_REINDEX_RECOVERY_DESCRIPTOR_SCHEMA_VERSION = "policy_reindex_recovery_descriptor.v1"
POLICY_REINDEX_STATE_SCHEMA_VERSION = "policy_reindex_run_state.v1"
POLICY_CANDIDATE_BUILD_BUDGET_SCHEMA_VERSION = "policy_candidate_build_budget.v1"
POLICY_CANDIDATE_BUILD_ATTEMPT_SCHEMA_VERSION = "policy_candidate_build_attempt.v1"
POLICY_CANDIDATE_BUILD_RESULT_SCHEMA_VERSION = "policy_candidate_build_result.v1"
MAXIMUM_REVIEWED_LEASE = timedelta(hours=2)
MAX_BUILD_EXECUTIONS_PER_DOCUMENT = 2
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")

ArtifactFaultInjector = Callable[[str], None]


class PolicyReindexArtifactError(RuntimeError):
    """Closed safe-code error for descriptor, state, and budget artifacts."""


class CandidateBuildResultCode(StrEnum):
    SUCCESS = "success"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_TRANSIENT = "provider_transient"
    CONFIG_ERROR = "config_error"
    PARITY_ERROR = "parity_error"
    SOURCE_ERROR = "source_error"
    RESPONSE_ERROR = "response_error"
    PROJECTION_ERROR = "projection_error"


@dataclass(frozen=True, slots=True)
class PolicyReindexRecoveryDescriptorV1:
    schema_version: str
    descriptor_payload_sha256: str
    sealed_at: datetime
    tenant_id: UUID
    run_token: UUID
    generation_name: str
    lease_owner: str
    lease_expires_at: datetime
    config_schema_version: str
    config_json: dict[str, Any]
    config_fingerprint: str
    parity_report_sha256: str
    parity_config_fingerprint: str
    parity_probe_fixture_sha256: str
    parity_submitted_content_sha256: str
    parity_captured_at: datetime
    parity_expires_at: datetime
    source_manifest_revision_id: UUID
    source_manifest_revision: int
    source_manifest_hash: str
    source_active_corpus_version_id: UUID
    source_rollout_epoch: int
    expected_evidence_rollout_version: int

    def __post_init__(self) -> None:
        _validate_descriptor(self)


@dataclass(frozen=True, slots=True)
class PolicyReindexImmutableArtifactV1:
    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class PolicyCandidateBuildBudgetV1:
    schema_version: str
    budget_payload_sha256: str
    descriptor_payload_sha256: str
    created_at: datetime
    tenant_id: UUID
    run_token: UUID
    max_build_executions_per_document: int
    ordered_document_sha256: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_build_budget(self)


@dataclass(frozen=True, slots=True)
class PolicyCandidateBuildAttemptV1:
    schema_version: str
    attempt_payload_sha256: str
    descriptor_payload_sha256: str
    budget_payload_sha256: str
    state_artifact_sha256: str
    document_index: int
    doc_key_sha256: str
    state_version: int
    next_document_index: int
    ordinal: int
    reserved_at: datetime
    expected_input_count: int
    expected_batch_count: int

    def __post_init__(self) -> None:
        _validate_build_attempt(self)


@dataclass(frozen=True, slots=True)
class PolicyCandidateBuildResultV1:
    schema_version: str
    result_payload_sha256: str
    descriptor_payload_sha256: str
    budget_payload_sha256: str
    attempt_payload_sha256: str
    document_index: int
    ordinal: int
    state_version: int
    recorded_at: datetime
    result_code: CandidateBuildResultCode
    provider_request_count: int
    post_state_version: int | None
    post_next_document_index: int | None
    post_state_artifact_sha256: str | None

    def __post_init__(self) -> None:
        _validate_build_result(self)


def build_policy_reindex_recovery_descriptor(
    *,
    sealed_at: datetime,
    tenant_id: UUID,
    run_token: UUID,
    generation_name: str,
    lease_owner: str,
    lease_expires_at: datetime,
    config_schema_version: str,
    config_json: dict[str, Any],
    config_fingerprint: str,
    parity_report_sha256: str,
    parity_config_fingerprint: str,
    parity_probe_fixture_sha256: str,
    parity_submitted_content_sha256: str,
    parity_captured_at: datetime,
    parity_expires_at: datetime,
    source_manifest_revision_id: UUID,
    source_manifest_revision: int,
    source_manifest_hash: str,
    source_active_corpus_version_id: UUID,
    source_rollout_epoch: int,
    expected_evidence_rollout_version: int,
) -> PolicyReindexRecoveryDescriptorV1:
    base: dict[str, Any] = {
        "schema_version": POLICY_REINDEX_RECOVERY_DESCRIPTOR_SCHEMA_VERSION,
        "sealed_at": _as_utc(sealed_at),
        "tenant_id": tenant_id,
        "run_token": run_token,
        "generation_name": generation_name,
        "lease_owner": lease_owner,
        "lease_expires_at": _as_utc(lease_expires_at),
        "config_schema_version": config_schema_version,
        "config_json": dict(config_json),
        "config_fingerprint": config_fingerprint,
        "parity_report_sha256": parity_report_sha256,
        "parity_config_fingerprint": parity_config_fingerprint,
        "parity_probe_fixture_sha256": parity_probe_fixture_sha256,
        "parity_submitted_content_sha256": parity_submitted_content_sha256,
        "parity_captured_at": _as_utc(parity_captured_at),
        "parity_expires_at": _as_utc(parity_expires_at),
        "source_manifest_revision_id": source_manifest_revision_id,
        "source_manifest_revision": source_manifest_revision,
        "source_manifest_hash": source_manifest_hash,
        "source_active_corpus_version_id": source_active_corpus_version_id,
        "source_rollout_epoch": source_rollout_epoch,
        "expected_evidence_rollout_version": expected_evidence_rollout_version,
    }
    return PolicyReindexRecoveryDescriptorV1(
        **base,
        descriptor_payload_sha256=_sha256_payload(base),
    )


def policy_reindex_descriptor_path(root: Path, *, tenant_id: UUID, run_token: UUID) -> Path:
    return root / "tenants" / str(tenant_id) / "runs" / str(run_token) / "descriptor.json"


def policy_reindex_state_path(
    root: Path,
    *,
    tenant_id: UUID,
    run_token: UUID,
    state_version: int,
) -> Path:
    return root / "tenants" / str(tenant_id) / "runs" / str(run_token) / "states" / f"{state_version:08d}.json"


def policy_candidate_build_budget_path(root: Path, *, tenant_id: UUID, run_token: UUID) -> Path:
    return root / "tenants" / str(tenant_id) / "runs" / str(run_token) / "build-budget" / "manifest.json"


def policy_candidate_build_attempt_path(
    root: Path,
    *,
    tenant_id: UUID,
    run_token: UUID,
    document_index: int,
    ordinal: int,
) -> Path:
    return (
        policy_candidate_build_budget_path(root, tenant_id=tenant_id, run_token=run_token).parent
        / "documents"
        / f"{document_index:08d}"
        / "attempts"
        / f"{ordinal:02d}.json"
    )


def policy_candidate_build_result_path(
    root: Path,
    *,
    tenant_id: UUID,
    run_token: UUID,
    document_index: int,
    ordinal: int,
) -> Path:
    return (
        policy_candidate_build_budget_path(root, tenant_id=tenant_id, run_token=run_token).parent
        / "documents"
        / f"{document_index:08d}"
        / "results"
        / f"{ordinal:02d}.json"
    )


def build_policy_candidate_build_budget(
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    ordered_doc_keys: tuple[str, ...],
    created_at: datetime,
) -> PolicyCandidateBuildBudgetV1:
    _validate_descriptor(descriptor)
    if not ordered_doc_keys or any(not isinstance(key, str) or not key for key in ordered_doc_keys):
        raise PolicyReindexArtifactError("build_budget_documents_invalid")
    base: dict[str, Any] = {
        "schema_version": POLICY_CANDIDATE_BUILD_BUDGET_SCHEMA_VERSION,
        "descriptor_payload_sha256": descriptor.descriptor_payload_sha256,
        "created_at": _as_utc(created_at),
        "tenant_id": descriptor.tenant_id,
        "run_token": descriptor.run_token,
        "max_build_executions_per_document": MAX_BUILD_EXECUTIONS_PER_DOCUMENT,
        "ordered_document_sha256": tuple(_sha256_text(key) for key in ordered_doc_keys),
    }
    return PolicyCandidateBuildBudgetV1(
        **base,
        budget_payload_sha256=_sha256_payload(base),
    )


def write_policy_candidate_build_budget_create_only(
    budget: PolicyCandidateBuildBudgetV1,
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    root: Path,
    fault_injector: ArtifactFaultInjector | None = None,
) -> PolicyReindexImmutableArtifactV1:
    _validate_build_budget_binding(budget, descriptor=descriptor)
    path = policy_candidate_build_budget_path(
        root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
    )
    payload = _canonical_json_bytes(asdict(budget))
    _publish_canonical_bytes(
        path,
        payload,
        conflict_code="build_budget_create_conflict",
        identical_replay=True,
        fault_injector=fault_injector,
    )
    return PolicyReindexImmutableArtifactV1(path=path, sha256=budget.budget_payload_sha256)


def load_policy_candidate_build_budget(
    path: Path,
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    root: Path,
) -> PolicyCandidateBuildBudgetV1:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
            field.name for field in fields(PolicyCandidateBuildBudgetV1)
        }:
            raise ValueError
        converted = dict(payload)
        converted["created_at"] = _parse_datetime(payload["created_at"])
        converted["tenant_id"] = UUID(payload["tenant_id"])
        converted["run_token"] = UUID(payload["run_token"])
        converted["ordered_document_sha256"] = tuple(payload["ordered_document_sha256"])
        budget = PolicyCandidateBuildBudgetV1(**converted)
        _validate_build_budget_binding(budget, descriptor=descriptor)
        expected = policy_candidate_build_budget_path(
            root,
            tenant_id=descriptor.tenant_id,
            run_token=descriptor.run_token,
        )
        if path.absolute() != expected.absolute() or _canonical_json_bytes(asdict(budget)) != raw:
            raise ValueError
    except (OSError, TypeError, ValueError, PolicyReindexArtifactError):
        raise PolicyReindexArtifactError("build_budget_invalid") from None
    return budget


def reserve_candidate_build_attempt(
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    owner: Any,
    state_artifact: PolicyReindexImmutableArtifactV1,
    budget: PolicyCandidateBuildBudgetV1,
    budget_artifact: PolicyReindexImmutableArtifactV1,
    root: Path,
    reserved_at: datetime,
    expected_input_count: int,
    expected_batch_count: int,
    fault_injector: ArtifactFaultInjector | None = None,
) -> PolicyCandidateBuildAttemptV1:
    checked_at = _as_utc(reserved_at)
    _validate_identity_binding(owner, descriptor=descriptor)
    _validate_build_budget_binding(budget, descriptor=descriptor)
    _validate_build_artifact_authority(
        descriptor=descriptor,
        owner=owner,
        state_artifact=state_artifact,
        budget=budget,
        budget_artifact=budget_artifact,
        root=root,
    )
    if checked_at >= min(descriptor.lease_expires_at, descriptor.parity_expires_at):
        raise PolicyReindexArtifactError("build_authority_expired")
    if (
        owner.state != "building"
        or owner.next_document_index >= len(owner.ordered_doc_keys)
        or budget.ordered_document_sha256 != tuple(_sha256_text(key) for key in owner.ordered_doc_keys)
    ):
        raise PolicyReindexArtifactError("build_state_descriptor_mismatch")
    if (
        type(expected_input_count) is not int
        or type(expected_batch_count) is not int
        or expected_input_count <= 0
        or not 0 < expected_batch_count <= expected_input_count
    ):
        raise PolicyReindexArtifactError("build_expected_counts_invalid")

    document_index = owner.next_document_index
    attempts_root = policy_candidate_build_attempt_path(
        root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
        document_index=document_index,
        ordinal=1,
    ).parent
    paths = sorted(attempts_root.glob("*.json")) if attempts_root.is_dir() else []
    if [path.name for path in paths] != [f"{ordinal:02d}.json" for ordinal in range(1, len(paths) + 1)]:
        raise PolicyReindexArtifactError("build_reservation_invalid")
    attempts = [
        load_candidate_build_attempt(
            path,
            descriptor=descriptor,
            budget=budget,
            budget_artifact=budget_artifact,
            root=root,
        )
        for path in paths
    ]
    if len(attempts) >= budget.max_build_executions_per_document:
        raise PolicyReindexArtifactError("build_budget_exhausted")
    if attempts:
        previous = attempts[-1]
        result_path = policy_candidate_build_result_path(
            root,
            tenant_id=descriptor.tenant_id,
            run_token=descriptor.run_token,
            document_index=document_index,
            ordinal=previous.ordinal,
        )
        if not result_path.is_file():
            raise PolicyReindexArtifactError("build_retry_evidence_missing")
        result = load_candidate_build_result(
            result_path,
            descriptor=descriptor,
            budget=budget,
            budget_artifact=budget_artifact,
            reservation=previous,
            root=root,
        )
        if result.result_code not in {
            CandidateBuildResultCode.PROVIDER_UNAVAILABLE,
            CandidateBuildResultCode.PROVIDER_TRANSIENT,
        }:
            raise PolicyReindexArtifactError("build_retry_not_allowed")
        if (
            previous.state_version != owner.state_version
            or previous.next_document_index != owner.next_document_index
            or previous.state_artifact_sha256 != state_artifact.sha256
            or previous.expected_input_count != expected_input_count
            or previous.expected_batch_count != expected_batch_count
        ):
            raise PolicyReindexArtifactError("build_retry_state_mismatch")

    ordinal = len(attempts) + 1
    base: dict[str, Any] = {
        "schema_version": POLICY_CANDIDATE_BUILD_ATTEMPT_SCHEMA_VERSION,
        "descriptor_payload_sha256": descriptor.descriptor_payload_sha256,
        "budget_payload_sha256": budget.budget_payload_sha256,
        "state_artifact_sha256": state_artifact.sha256,
        "document_index": document_index,
        "doc_key_sha256": budget.ordered_document_sha256[document_index],
        "state_version": owner.state_version,
        "next_document_index": owner.next_document_index,
        "ordinal": ordinal,
        "reserved_at": checked_at,
        "expected_input_count": expected_input_count,
        "expected_batch_count": expected_batch_count,
    }
    attempt = PolicyCandidateBuildAttemptV1(
        **base,
        attempt_payload_sha256=_sha256_payload(base),
    )
    path = policy_candidate_build_attempt_path(
        root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
        document_index=document_index,
        ordinal=ordinal,
    )
    _publish_canonical_bytes(
        path,
        _canonical_json_bytes(asdict(attempt)),
        conflict_code="build_reservation_conflict",
        identical_replay=False,
        fault_injector=fault_injector,
    )
    return attempt


def load_candidate_build_attempt(
    path: Path,
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    budget: PolicyCandidateBuildBudgetV1,
    budget_artifact: PolicyReindexImmutableArtifactV1,
    root: Path,
) -> PolicyCandidateBuildAttemptV1:
    try:
        _validate_budget_artifact(
            budget=budget,
            budget_artifact=budget_artifact,
            descriptor=descriptor,
            root=root,
        )
        raw = path.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
            field.name for field in fields(PolicyCandidateBuildAttemptV1)
        }:
            raise ValueError
        converted = dict(payload)
        converted["reserved_at"] = _parse_datetime(payload["reserved_at"])
        attempt = PolicyCandidateBuildAttemptV1(**converted)
        _validate_build_attempt_binding(attempt, descriptor=descriptor, budget=budget)
        expected = policy_candidate_build_attempt_path(
            root,
            tenant_id=descriptor.tenant_id,
            run_token=descriptor.run_token,
            document_index=attempt.document_index,
            ordinal=attempt.ordinal,
        )
        if path.absolute() != expected.absolute() or _canonical_json_bytes(asdict(attempt)) != raw:
            raise ValueError
    except (OSError, TypeError, ValueError, PolicyReindexArtifactError):
        raise PolicyReindexArtifactError("build_reservation_invalid") from None
    return attempt


def record_candidate_build_result_create_only(
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    owner: Any,
    budget: PolicyCandidateBuildBudgetV1,
    budget_artifact: PolicyReindexImmutableArtifactV1,
    reservation: PolicyCandidateBuildAttemptV1,
    root: Path,
    recorded_at: datetime,
    result_code: CandidateBuildResultCode,
    provider_request_count: int,
    post_state_artifact: PolicyReindexImmutableArtifactV1 | None = None,
    fault_injector: ArtifactFaultInjector | None = None,
) -> PolicyCandidateBuildResultV1:
    _validate_identity_binding(owner, descriptor=descriptor)
    _validate_budget_artifact(
        budget=budget,
        budget_artifact=budget_artifact,
        descriptor=descriptor,
        root=root,
    )
    _validate_build_attempt_binding(reservation, descriptor=descriptor, budget=budget)
    reservation_path = policy_candidate_build_attempt_path(
        root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
        document_index=reservation.document_index,
        ordinal=reservation.ordinal,
    )
    if (
        load_candidate_build_attempt(
            reservation_path,
            descriptor=descriptor,
            budget=budget,
            budget_artifact=budget_artifact,
            root=root,
        )
        != reservation
    ):
        raise PolicyReindexArtifactError("build_reservation_invalid")
    if not isinstance(result_code, CandidateBuildResultCode):
        raise PolicyReindexArtifactError("build_result_code_invalid")
    if type(provider_request_count) is not int or provider_request_count < 0:
        raise PolicyReindexArtifactError("build_provider_count_invalid")

    post_state_version: int | None = None
    post_next_document_index: int | None = None
    post_state_artifact_sha256: str | None = None
    if result_code is CandidateBuildResultCode.SUCCESS:
        if (
            owner.state_version != reservation.state_version + 1
            or owner.next_document_index != reservation.document_index + 1
            or provider_request_count != reservation.expected_batch_count
            or post_state_artifact is None
        ):
            raise PolicyReindexArtifactError("build_success_advance_invalid")
        _validate_state_artifact(
            owner=owner,
            state_artifact=post_state_artifact,
            descriptor=descriptor,
            root=root,
        )
        post_state_version = owner.state_version
        post_next_document_index = owner.next_document_index
        post_state_artifact_sha256 = post_state_artifact.sha256
    elif (
        owner.state_version != reservation.state_version
        or owner.next_document_index != reservation.next_document_index
        or post_state_artifact is not None
    ):
        raise PolicyReindexArtifactError("build_failure_state_invalid")

    base: dict[str, Any] = {
        "schema_version": POLICY_CANDIDATE_BUILD_RESULT_SCHEMA_VERSION,
        "descriptor_payload_sha256": descriptor.descriptor_payload_sha256,
        "budget_payload_sha256": budget.budget_payload_sha256,
        "attempt_payload_sha256": reservation.attempt_payload_sha256,
        "document_index": reservation.document_index,
        "ordinal": reservation.ordinal,
        "state_version": reservation.state_version,
        "recorded_at": _as_utc(recorded_at),
        "result_code": result_code,
        "provider_request_count": provider_request_count,
        "post_state_version": post_state_version,
        "post_next_document_index": post_next_document_index,
        "post_state_artifact_sha256": post_state_artifact_sha256,
    }
    result = PolicyCandidateBuildResultV1(
        **base,
        result_payload_sha256=_sha256_payload(base),
    )
    path = policy_candidate_build_result_path(
        root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
        document_index=reservation.document_index,
        ordinal=reservation.ordinal,
    )
    _publish_canonical_bytes(
        path,
        _canonical_json_bytes(asdict(result)),
        conflict_code="build_result_create_conflict",
        identical_replay=True,
        fault_injector=fault_injector,
    )
    return result


def load_candidate_build_result(
    path: Path,
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    budget: PolicyCandidateBuildBudgetV1,
    budget_artifact: PolicyReindexImmutableArtifactV1,
    reservation: PolicyCandidateBuildAttemptV1,
    root: Path,
) -> PolicyCandidateBuildResultV1:
    try:
        _validate_budget_artifact(
            budget=budget,
            budget_artifact=budget_artifact,
            descriptor=descriptor,
            root=root,
        )
        _validate_build_attempt_binding(reservation, descriptor=descriptor, budget=budget)
        raw = path.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
            field.name for field in fields(PolicyCandidateBuildResultV1)
        }:
            raise ValueError
        converted = dict(payload)
        converted["recorded_at"] = _parse_datetime(payload["recorded_at"])
        converted["result_code"] = CandidateBuildResultCode(payload["result_code"])
        result = PolicyCandidateBuildResultV1(**converted)
        _validate_build_result_binding(
            result,
            descriptor=descriptor,
            budget=budget,
            reservation=reservation,
        )
        expected = policy_candidate_build_result_path(
            root,
            tenant_id=descriptor.tenant_id,
            run_token=descriptor.run_token,
            document_index=result.document_index,
            ordinal=result.ordinal,
        )
        if path.absolute() != expected.absolute() or _canonical_json_bytes(asdict(result)) != raw:
            raise ValueError
    except (OSError, TypeError, ValueError, PolicyReindexArtifactError):
        raise PolicyReindexArtifactError("build_result_invalid") from None
    return result


def require_candidate_build_budget_complete(
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    owner: Any,
    budget: PolicyCandidateBuildBudgetV1,
    budget_artifact: PolicyReindexImmutableArtifactV1,
    root: Path,
) -> None:
    _validate_identity_binding(owner, descriptor=descriptor)
    _validate_budget_artifact(
        budget=budget,
        budget_artifact=budget_artifact,
        descriptor=descriptor,
        root=root,
    )
    if budget.ordered_document_sha256 != tuple(_sha256_text(key) for key in owner.ordered_doc_keys):
        raise PolicyReindexArtifactError("build_state_descriptor_mismatch")
    for document_index in range(len(budget.ordered_document_sha256)):
        successes = 0
        for ordinal in range(1, budget.max_build_executions_per_document + 1):
            attempt_path = policy_candidate_build_attempt_path(
                root,
                tenant_id=descriptor.tenant_id,
                run_token=descriptor.run_token,
                document_index=document_index,
                ordinal=ordinal,
            )
            if not attempt_path.exists():
                continue
            attempt = load_candidate_build_attempt(
                attempt_path,
                descriptor=descriptor,
                budget=budget,
                budget_artifact=budget_artifact,
                root=root,
            )
            result_path = policy_candidate_build_result_path(
                root,
                tenant_id=descriptor.tenant_id,
                run_token=descriptor.run_token,
                document_index=document_index,
                ordinal=ordinal,
            )
            if not result_path.exists():
                raise PolicyReindexArtifactError("build_result_missing")
            result = load_candidate_build_result(
                result_path,
                descriptor=descriptor,
                budget=budget,
                budget_artifact=budget_artifact,
                reservation=attempt,
                root=root,
            )
            if result.result_code is CandidateBuildResultCode.SUCCESS:
                successes += 1
                if result.post_next_document_index != document_index + 1:
                    raise PolicyReindexArtifactError("build_success_advance_invalid")
        if successes != 1:
            raise PolicyReindexArtifactError("build_document_incomplete")


def write_policy_reindex_recovery_descriptor_create_only(
    descriptor: PolicyReindexRecoveryDescriptorV1,
    *,
    root: Path,
    fault_injector: ArtifactFaultInjector | None = None,
) -> PolicyReindexImmutableArtifactV1:
    _validate_descriptor(descriptor)
    path = policy_reindex_descriptor_path(
        root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
    )
    payload = _canonical_json_bytes(asdict(descriptor))
    _publish_canonical_bytes(
        path,
        payload,
        conflict_code="descriptor_create_conflict",
        identical_replay=False,
        fault_injector=fault_injector,
    )
    return PolicyReindexImmutableArtifactV1(
        path=path,
        sha256=descriptor.descriptor_payload_sha256,
    )


def load_policy_reindex_recovery_descriptor(
    path: Path,
    *,
    root: Path | None = None,
) -> PolicyReindexRecoveryDescriptorV1:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
            field.name for field in fields(PolicyReindexRecoveryDescriptorV1)
        }:
            raise ValueError
        converted = dict(payload)
        converted["sealed_at"] = _parse_datetime(payload["sealed_at"])
        converted["tenant_id"] = UUID(payload["tenant_id"])
        converted["run_token"] = UUID(payload["run_token"])
        converted["lease_expires_at"] = _parse_datetime(payload["lease_expires_at"])
        converted["parity_captured_at"] = _parse_datetime(payload["parity_captured_at"])
        converted["parity_expires_at"] = _parse_datetime(payload["parity_expires_at"])
        converted["source_manifest_revision_id"] = UUID(payload["source_manifest_revision_id"])
        converted["source_active_corpus_version_id"] = UUID(payload["source_active_corpus_version_id"])
        descriptor = PolicyReindexRecoveryDescriptorV1(**converted)
        if _canonical_json_bytes(asdict(descriptor)) != raw:
            raise ValueError
    except (OSError, TypeError, ValueError, PolicyReindexArtifactError):
        raise PolicyReindexArtifactError("descriptor_invalid") from None
    if root is not None:
        expected = policy_reindex_descriptor_path(
            root,
            tenant_id=descriptor.tenant_id,
            run_token=descriptor.run_token,
        )
        if path.absolute() != expected.absolute():
            raise PolicyReindexArtifactError("descriptor_root_mismatch")
    return descriptor


def write_policy_reindex_state_create_only(
    identity: Any,
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    root: Path,
    fault_injector: ArtifactFaultInjector | None = None,
) -> PolicyReindexImmutableArtifactV1:
    _validate_identity_binding(identity, descriptor=descriptor)
    path = policy_reindex_state_path(
        root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
        state_version=identity.state_version,
    )
    payload = _canonical_json_bytes(
        {
            "schema_version": POLICY_REINDEX_STATE_SCHEMA_VERSION,
            "descriptor_payload_sha256": descriptor.descriptor_payload_sha256,
            "identity": asdict(identity),
        }
    )
    _publish_canonical_bytes(
        path,
        payload,
        conflict_code="state_create_conflict",
        identical_replay=True,
        fault_injector=fault_injector,
    )
    return PolicyReindexImmutableArtifactV1(path=path, sha256=_sha256_bytes(payload))


def write_policy_reindex_compat_identity_create_only(path: Path, identity: Any) -> None:
    """Keep legacy CLI paths compatible while giving them the atomic writer."""

    payload = _canonical_json_bytes(
        {
            "schema_version": "policy_reindex_run_identity.v1",
            "identity": asdict(identity),
        }
    )
    _publish_canonical_bytes(
        path,
        payload,
        conflict_code="state_create_conflict",
        identical_replay=True,
        fault_injector=None,
    )


def load_policy_reindex_state(
    path: Path,
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    root: Path,
) -> Any:
    from src.rag.policy_reindex import PolicyReindexRunIdentity

    try:
        payload = json.loads(path.read_bytes())
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version",
            "descriptor_payload_sha256",
            "identity",
        }:
            raise ValueError
        if (
            payload["schema_version"] != POLICY_REINDEX_STATE_SCHEMA_VERSION
            or payload["descriptor_payload_sha256"] != descriptor.descriptor_payload_sha256
            or not isinstance(payload["identity"], dict)
            or set(payload["identity"]) != set(PolicyReindexRunIdentity.__dataclass_fields__)
        ):
            raise ValueError
        identity_payload = dict(payload["identity"])
        for key in (
            "corpus_version_id",
            "tenant_id",
            "run_token",
            "source_manifest_revision_id",
            "source_active_corpus_version_id",
        ):
            identity_payload[key] = UUID(identity_payload[key])
        for key in ("lease_expires_at", "parity_captured_at", "parity_expires_at"):
            identity_payload[key] = _parse_datetime(identity_payload[key])
        identity_payload["ordered_doc_keys"] = tuple(identity_payload["ordered_doc_keys"])
        identity = PolicyReindexRunIdentity(**identity_payload)
        _validate_identity_binding(identity, descriptor=descriptor)
        expected = policy_reindex_state_path(
            root,
            tenant_id=descriptor.tenant_id,
            run_token=descriptor.run_token,
            state_version=identity.state_version,
        )
        if path.absolute() != expected.absolute():
            raise ValueError
        if _canonical_json_bytes(payload) != path.read_bytes():
            raise ValueError
    except (OSError, TypeError, ValueError, PolicyReindexArtifactError):
        raise PolicyReindexArtifactError("state_invalid") from None
    return identity


def _validate_descriptor(descriptor: PolicyReindexRecoveryDescriptorV1) -> None:
    try:
        sealed_at = _as_utc(descriptor.sealed_at)
        lease_expires_at = _as_utc(descriptor.lease_expires_at)
        parity_captured_at = _as_utc(descriptor.parity_captured_at)
        parity_expires_at = _as_utc(descriptor.parity_expires_at)
    except (TypeError, ValueError):
        raise PolicyReindexArtifactError("descriptor_time_invalid") from None
    if descriptor.schema_version != POLICY_REINDEX_RECOVERY_DESCRIPTOR_SCHEMA_VERSION:
        raise PolicyReindexArtifactError("descriptor_schema_invalid")
    if (
        descriptor.tenant_id.int == 0
        or descriptor.run_token.int == 0
        or descriptor.source_manifest_revision_id.int == 0
        or descriptor.source_active_corpus_version_id.int == 0
        or not descriptor.generation_name.strip()
        or len(descriptor.generation_name) > 128
        or not descriptor.lease_owner.strip()
        or len(descriptor.lease_owner) > 128
        or not descriptor.config_schema_version.strip()
        or not isinstance(descriptor.config_json, dict)
        or descriptor.source_manifest_revision <= 0
        or descriptor.source_rollout_epoch <= 0
        or descriptor.expected_evidence_rollout_version < 0
    ):
        raise PolicyReindexArtifactError("descriptor_identity_invalid")
    if any(
        not _valid_sha256(value)
        for value in (
            descriptor.descriptor_payload_sha256,
            descriptor.config_fingerprint,
            descriptor.parity_report_sha256,
            descriptor.parity_config_fingerprint,
            descriptor.parity_probe_fixture_sha256,
            descriptor.parity_submitted_content_sha256,
            descriptor.source_manifest_hash,
        )
    ):
        raise PolicyReindexArtifactError("descriptor_hash_invalid")
    if descriptor.parity_config_fingerprint != descriptor.config_fingerprint:
        raise PolicyReindexArtifactError("descriptor_parity_config_mismatch")
    if not sealed_at < lease_expires_at <= sealed_at + MAXIMUM_REVIEWED_LEASE:
        raise PolicyReindexArtifactError("descriptor_lease_window_invalid")
    if parity_captured_at > sealed_at or parity_expires_at <= sealed_at:
        raise PolicyReindexArtifactError("descriptor_parity_window_invalid")
    base = asdict(descriptor)
    base.pop("descriptor_payload_sha256")
    if descriptor.descriptor_payload_sha256 != _sha256_payload(base):
        raise PolicyReindexArtifactError("descriptor_payload_hash_mismatch")


def _validate_identity_binding(identity: Any, *, descriptor: PolicyReindexRecoveryDescriptorV1) -> None:
    required = {
        "tenant_id": descriptor.tenant_id,
        "run_token": descriptor.run_token,
        "generation_name": descriptor.generation_name,
        "lease_owner": descriptor.lease_owner,
        "lease_expires_at": descriptor.lease_expires_at,
        "config_schema_version": descriptor.config_schema_version,
        "config_fingerprint": descriptor.config_fingerprint,
        "provider_parity_report_hash": descriptor.parity_report_sha256,
        "source_manifest_revision_id": descriptor.source_manifest_revision_id,
        "source_manifest_revision": descriptor.source_manifest_revision,
        "source_manifest_hash": descriptor.source_manifest_hash,
        "source_active_corpus_version_id": descriptor.source_active_corpus_version_id,
        "source_rollout_epoch": descriptor.source_rollout_epoch,
        "expected_evidence_rollout_version": descriptor.expected_evidence_rollout_version,
        "parity_captured_at": descriptor.parity_captured_at,
        "parity_expires_at": descriptor.parity_expires_at,
    }
    if not is_dataclass(identity) or any(getattr(identity, key, None) != value for key, value in required.items()):
        raise PolicyReindexArtifactError("state_descriptor_mismatch")
    if (
        type(getattr(identity, "state_version", None)) is not int
        or identity.state_version <= 0
        or type(getattr(identity, "next_document_index", None)) is not int
        or identity.next_document_index < 0
        or not isinstance(getattr(identity, "ordered_doc_keys", None), tuple)
    ):
        raise PolicyReindexArtifactError("state_invalid")


def _validate_build_budget(budget: PolicyCandidateBuildBudgetV1) -> None:
    try:
        _as_utc(budget.created_at)
    except (TypeError, ValueError):
        raise PolicyReindexArtifactError("build_budget_time_invalid") from None
    if (
        budget.schema_version != POLICY_CANDIDATE_BUILD_BUDGET_SCHEMA_VERSION
        or budget.tenant_id.int == 0
        or budget.run_token.int == 0
        or budget.max_build_executions_per_document != MAX_BUILD_EXECUTIONS_PER_DOCUMENT
        or not budget.ordered_document_sha256
        or any(not _valid_sha256(item) for item in budget.ordered_document_sha256)
        or not _valid_sha256(budget.descriptor_payload_sha256)
        or not _valid_sha256(budget.budget_payload_sha256)
    ):
        raise PolicyReindexArtifactError("build_budget_invalid")
    base = asdict(budget)
    base.pop("budget_payload_sha256")
    if budget.budget_payload_sha256 != _sha256_payload(base):
        raise PolicyReindexArtifactError("build_budget_hash_mismatch")


def _validate_build_budget_binding(
    budget: PolicyCandidateBuildBudgetV1,
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
) -> None:
    _validate_descriptor(descriptor)
    _validate_build_budget(budget)
    if (
        budget.descriptor_payload_sha256 != descriptor.descriptor_payload_sha256
        or budget.tenant_id != descriptor.tenant_id
        or budget.run_token != descriptor.run_token
        or budget.created_at != descriptor.sealed_at
    ):
        raise PolicyReindexArtifactError("build_budget_descriptor_mismatch")


def _validate_build_attempt(attempt: PolicyCandidateBuildAttemptV1) -> None:
    try:
        _as_utc(attempt.reserved_at)
    except (TypeError, ValueError):
        raise PolicyReindexArtifactError("build_reservation_time_invalid") from None
    if (
        attempt.schema_version != POLICY_CANDIDATE_BUILD_ATTEMPT_SCHEMA_VERSION
        or any(
            not _valid_sha256(item)
            for item in (
                attempt.attempt_payload_sha256,
                attempt.descriptor_payload_sha256,
                attempt.budget_payload_sha256,
                attempt.state_artifact_sha256,
                attempt.doc_key_sha256,
            )
        )
        or type(attempt.document_index) is not int
        or attempt.document_index < 0
        or type(attempt.state_version) is not int
        or attempt.state_version <= 0
        or type(attempt.next_document_index) is not int
        or attempt.next_document_index != attempt.document_index
        or type(attempt.ordinal) is not int
        or not 1 <= attempt.ordinal <= MAX_BUILD_EXECUTIONS_PER_DOCUMENT
        or type(attempt.expected_input_count) is not int
        or type(attempt.expected_batch_count) is not int
        or attempt.expected_input_count <= 0
        or not 0 < attempt.expected_batch_count <= attempt.expected_input_count
    ):
        raise PolicyReindexArtifactError("build_reservation_invalid")
    base = asdict(attempt)
    base.pop("attempt_payload_sha256")
    if attempt.attempt_payload_sha256 != _sha256_payload(base):
        raise PolicyReindexArtifactError("build_reservation_hash_mismatch")


def _validate_build_attempt_binding(
    attempt: PolicyCandidateBuildAttemptV1,
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    budget: PolicyCandidateBuildBudgetV1,
) -> None:
    _validate_build_attempt(attempt)
    _validate_build_budget_binding(budget, descriptor=descriptor)
    if (
        attempt.descriptor_payload_sha256 != descriptor.descriptor_payload_sha256
        or attempt.budget_payload_sha256 != budget.budget_payload_sha256
        or attempt.document_index >= len(budget.ordered_document_sha256)
        or attempt.doc_key_sha256 != budget.ordered_document_sha256[attempt.document_index]
    ):
        raise PolicyReindexArtifactError("build_reservation_binding_mismatch")


def _validate_build_result(result: PolicyCandidateBuildResultV1) -> None:
    try:
        _as_utc(result.recorded_at)
    except (TypeError, ValueError):
        raise PolicyReindexArtifactError("build_result_time_invalid") from None
    if (
        result.schema_version != POLICY_CANDIDATE_BUILD_RESULT_SCHEMA_VERSION
        or not isinstance(result.result_code, CandidateBuildResultCode)
        or any(
            not _valid_sha256(item)
            for item in (
                result.result_payload_sha256,
                result.descriptor_payload_sha256,
                result.budget_payload_sha256,
                result.attempt_payload_sha256,
            )
        )
        or type(result.document_index) is not int
        or result.document_index < 0
        or type(result.ordinal) is not int
        or not 1 <= result.ordinal <= MAX_BUILD_EXECUTIONS_PER_DOCUMENT
        or type(result.state_version) is not int
        or result.state_version <= 0
        or type(result.provider_request_count) is not int
        or result.provider_request_count < 0
    ):
        raise PolicyReindexArtifactError("build_result_invalid")
    if result.result_code is CandidateBuildResultCode.SUCCESS:
        if (
            type(result.post_state_version) is not int
            or result.post_state_version != result.state_version + 1
            or type(result.post_next_document_index) is not int
            or result.post_next_document_index != result.document_index + 1
            or not _valid_sha256(result.post_state_artifact_sha256)
        ):
            raise PolicyReindexArtifactError("build_success_advance_invalid")
    elif any(
        item is not None
        for item in (
            result.post_state_version,
            result.post_next_document_index,
            result.post_state_artifact_sha256,
        )
    ):
        raise PolicyReindexArtifactError("build_failure_state_invalid")
    base = asdict(result)
    base.pop("result_payload_sha256")
    if result.result_payload_sha256 != _sha256_payload(base):
        raise PolicyReindexArtifactError("build_result_hash_mismatch")


def _validate_build_result_binding(
    result: PolicyCandidateBuildResultV1,
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    budget: PolicyCandidateBuildBudgetV1,
    reservation: PolicyCandidateBuildAttemptV1,
) -> None:
    _validate_build_result(result)
    _validate_build_attempt_binding(reservation, descriptor=descriptor, budget=budget)
    if (
        result.descriptor_payload_sha256 != descriptor.descriptor_payload_sha256
        or result.budget_payload_sha256 != budget.budget_payload_sha256
        or result.attempt_payload_sha256 != reservation.attempt_payload_sha256
        or result.document_index != reservation.document_index
        or result.ordinal != reservation.ordinal
        or result.state_version != reservation.state_version
    ):
        raise PolicyReindexArtifactError("build_result_binding_mismatch")


def _validate_state_artifact(
    *,
    owner: Any,
    state_artifact: PolicyReindexImmutableArtifactV1,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    root: Path,
) -> None:
    try:
        loaded = load_policy_reindex_state(
            state_artifact.path,
            descriptor=descriptor,
            root=root,
        )
        if state_artifact.sha256 != _sha256_bytes(state_artifact.path.read_bytes()) or loaded != owner:
            raise PolicyReindexArtifactError("build_state_descriptor_mismatch")
    except PolicyReindexArtifactError as error:
        if str(error) == "build_state_descriptor_mismatch":
            raise
        raise PolicyReindexArtifactError("build_state_artifact_invalid") from None
    except (OSError, ValueError):
        raise PolicyReindexArtifactError("build_state_artifact_invalid") from None


def _validate_budget_artifact(
    *,
    budget: PolicyCandidateBuildBudgetV1,
    budget_artifact: PolicyReindexImmutableArtifactV1,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    root: Path,
) -> None:
    expected = policy_candidate_build_budget_path(
        root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
    )
    if budget_artifact.path.absolute() != expected.absolute():
        raise PolicyReindexArtifactError("build_artifact_root_mismatch")
    try:
        if (
            budget_artifact.sha256 != budget.budget_payload_sha256
            or load_policy_candidate_build_budget(expected, descriptor=descriptor, root=root) != budget
        ):
            raise ValueError
    except (OSError, ValueError, PolicyReindexArtifactError):
        raise PolicyReindexArtifactError("build_budget_artifact_invalid") from None


def _validate_build_artifact_authority(
    *,
    descriptor: PolicyReindexRecoveryDescriptorV1,
    owner: Any,
    state_artifact: PolicyReindexImmutableArtifactV1,
    budget: PolicyCandidateBuildBudgetV1,
    budget_artifact: PolicyReindexImmutableArtifactV1,
    root: Path,
) -> None:
    run_root = root / "tenants" / str(descriptor.tenant_id) / "runs" / str(descriptor.run_token)
    if not state_artifact.path.absolute().is_relative_to(run_root.absolute()):
        raise PolicyReindexArtifactError("build_artifact_root_mismatch")
    _validate_state_artifact(
        owner=owner,
        state_artifact=state_artifact,
        descriptor=descriptor,
        root=root,
    )
    _validate_budget_artifact(
        budget=budget,
        budget_artifact=budget_artifact,
        descriptor=descriptor,
        root=root,
    )


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _publish_canonical_bytes(
    path: Path,
    payload: bytes,
    *,
    conflict_code: str,
    identical_replay: bool,
    fault_injector: ArtifactFaultInjector | None,
) -> None:
    staging_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        staging_root = path.parent / ".staging"
        staging_root.mkdir(exist_ok=True)
        if path.exists():
            if identical_replay and path.read_bytes() == payload:
                return
            raise PolicyReindexArtifactError(conflict_code)
        descriptor, staging_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=staging_root)
        staging_path = Path(staging_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            _inject_fault(fault_injector, "stage_written")
            os.fsync(stream.fileno())
        _inject_fault(fault_injector, "stage_fsynced")
        _fsync_directory(staging_root)
        os.link(staging_path, path)
        _inject_fault(fault_injector, "published")
        _fsync_directory(path.parent)
        _inject_fault(fault_injector, "parent_fsynced")
    except FileExistsError:
        if identical_replay:
            try:
                if path.read_bytes() == payload:
                    return
            except OSError:
                pass
        raise PolicyReindexArtifactError(conflict_code) from None
    except PolicyReindexArtifactError:
        raise
    except OSError:
        raise PolicyReindexArtifactError("artifact_write_failed") from None
    finally:
        if staging_path is not None:
            try:
                staging_path.unlink(missing_ok=True)
                _fsync_directory(staging_path.parent)
            except (OSError, PolicyReindexArtifactError):
                pass


def _inject_fault(fault_injector: ArtifactFaultInjector | None, boundary: str) -> None:
    if fault_injector is not None:
        fault_injector(boundary)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        raise PolicyReindexArtifactError("artifact_write_failed") from None


def _canonical_json_bytes(payload: object) -> bytes:
    return (json.dumps(_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _jsonable(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return _as_utc(value).isoformat()
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _sha256_payload(payload: object) -> str:
    return _sha256_bytes(_canonical_json_bytes(payload))


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _as_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(UTC)


def _parse_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError
    return _as_utc(datetime.fromisoformat(value))
