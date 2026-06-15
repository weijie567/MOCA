"""Action safety snapshot schema and immutable hash projection."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from src.approvals.schemas import ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION
from src.common.canonical_hash import canonical_hash
from src.knowledge.schemas import EvidenceRefV1, canonical_evidence_projection

SNAPSHOT_HASH_FIELDS = {
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
    "created_at",
}

LIFECYCLE_FIELDS = {"archived_at", "retention_until", "deleted_at"}
FORBIDDEN_SNAPSHOT_KEYS = {
    "raw_prompt",
    "raw_args",
    "raw_payload",
    "raw_tool_output",
    "secret",
    "secrets",
    "credential",
    "credentials",
    "pii",
}


class ActionSafetySnapshot(BaseModel):
    """Immutable approval/action safety material bound by CanonicalHashProfile v1."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["action_safety_snapshot.v1"] = (
        ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION
    )
    tenant_id: str
    run_id: str
    snapshot_id: str
    snapshot_ref: str
    policy_config_version: str
    risk_config_version: str
    retrieval_config_version: str
    evidence: list[EvidenceRefV1]
    evidence_ids: list[str]
    action_payload_hash: str
    created_at: str
    immutable_hash: str
    archived_at: str | None = None
    retention_until: str | None = None
    deleted_at: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_payload_keys(cls, data: Any) -> Any:
        _reject_forbidden_keys(data)
        return data


def snapshot_hash_projection(snapshot: ActionSafetySnapshot | Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact hash material for ``ActionSafetySnapshot.immutable_hash``."""

    data = _snapshot_mapping(snapshot)
    evidence_refs = [_as_evidence_ref(ref) for ref in data["evidence"]]
    projected_evidence = canonical_evidence_projection(evidence_refs)

    return {
        "schema_version": ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION,
        "tenant_id": data["tenant_id"],
        "run_id": data["run_id"],
        "snapshot_id": data["snapshot_id"],
        "snapshot_ref": data["snapshot_ref"],
        "policy_config_version": data["policy_config_version"],
        "risk_config_version": data["risk_config_version"],
        "retrieval_config_version": data["retrieval_config_version"],
        "evidence": projected_evidence,
        "evidence_ids": [item["evidence_id"] for item in projected_evidence],
        "action_payload_hash": data["action_payload_hash"],
        "created_at": _format_timestamp(data["created_at"]),
    }


def build_action_safety_snapshot(
    *,
    tenant_id: str,
    run_id: str,
    snapshot_id: str,
    snapshot_ref: str,
    policy_config_version: str,
    risk_config_version: str,
    retrieval_config_version: str,
    evidence: list[EvidenceRefV1 | Mapping[str, Any]],
    action_payload_hash: str,
    created_at: str | datetime,
    archived_at: str | None = None,
    retention_until: str | None = None,
    deleted_at: str | None = None,
    **extra: Any,
) -> ActionSafetySnapshot:
    """Build an ``ActionSafetySnapshot`` and compute its immutable hash."""

    if extra:
        _reject_forbidden_keys(extra)
        raise ValueError(f"unknown snapshot fields: {sorted(extra)}")

    evidence_refs = [_as_evidence_ref(ref) for ref in evidence]
    data = {
        "schema_version": ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "run_id": run_id,
        "snapshot_id": snapshot_id,
        "snapshot_ref": snapshot_ref,
        "policy_config_version": policy_config_version,
        "risk_config_version": risk_config_version,
        "retrieval_config_version": retrieval_config_version,
        "evidence": evidence_refs,
        "action_payload_hash": action_payload_hash,
        "created_at": _format_timestamp(created_at),
    }
    projection = snapshot_hash_projection(data)
    immutable_hash = canonical_hash(
        projection,
        schema_version=ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION,
        allowed_fields=SNAPSHOT_HASH_FIELDS,
    )

    return ActionSafetySnapshot(
        **data,
        evidence_ids=projection["evidence_ids"],
        immutable_hash=immutable_hash,
        archived_at=archived_at,
        retention_until=retention_until,
        deleted_at=deleted_at,
    )


def _snapshot_mapping(snapshot: ActionSafetySnapshot | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(snapshot, ActionSafetySnapshot):
        return snapshot.model_dump()
    _reject_forbidden_keys(snapshot)
    return snapshot


def _as_evidence_ref(ref: EvidenceRefV1 | Mapping[str, Any]) -> EvidenceRefV1:
    if isinstance(ref, EvidenceRefV1):
        return ref
    return EvidenceRefV1.model_validate(ref)


def _format_timestamp(value: str | datetime) -> str:
    if isinstance(value, str):
        return value
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("snapshot timestamp must be timezone-aware UTC")
    if value.microsecond % 1000 != 0:
        raise ValueError("snapshot timestamp must use fixed millisecond precision")
    normalized = value.astimezone(UTC)
    return normalized.strftime("%Y-%m-%dT%H:%M:%S.") + f"{normalized.microsecond // 1000:03d}Z"


def _reject_forbidden_keys(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, BaseModel):
        value = value.model_dump()

    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in FORBIDDEN_SNAPSHOT_KEYS:
                dotted = ".".join((*path, str(key)))
                raise ValueError(f"forbidden snapshot key: {dotted}")
            _reject_forbidden_keys(nested, (*path, str(key)))
        return

    if isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_keys(nested, (*path, str(index)))
