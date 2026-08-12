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
from typing import Any, Callable
from uuid import UUID


POLICY_REINDEX_RECOVERY_DESCRIPTOR_SCHEMA_VERSION = "policy_reindex_recovery_descriptor.v1"
POLICY_REINDEX_STATE_SCHEMA_VERSION = "policy_reindex_run_state.v1"
MAXIMUM_REVIEWED_LEASE = timedelta(hours=2)
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")

ArtifactFaultInjector = Callable[[str], None]


class PolicyReindexArtifactError(RuntimeError):
    """Closed safe-code error for descriptor, state, and budget artifacts."""


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
