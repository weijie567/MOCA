"""Action safety snapshot schema and immutable hash projection."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.approvals.schemas import ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION, TargetMerchantBindingV1
from src.common.canonical_hash import canonical_hash
from src.knowledge.schemas import EvidenceRefV1, canonical_evidence_projection
from src.tools.contracts import BusinessFactRefV1

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
    "target_merchant_id",
    "target_merchant_ref",
    "business_fact_refs",
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

    schema_version: Literal["action_safety_snapshot.v1"] = ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION
    tenant_id: str
    run_id: str
    snapshot_id: str
    snapshot_ref: str
    policy_config_version: str
    risk_config_version: str
    retrieval_config_version: str
    evidence: list[EvidenceRefV1]
    evidence_ids: list[str]
    action_payload_hash: str | None = None
    target_merchant_id: str | None = None
    target_merchant_ref: TargetMerchantBindingV1 | None = None
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
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
    target_merchant_ref = _as_target_merchant_ref(data.get("target_merchant_ref"))
    business_fact_refs = [_as_business_fact_ref(ref) for ref in data.get("business_fact_refs") or []]

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
        "action_payload_hash": data.get("action_payload_hash"),
        "target_merchant_id": data.get("target_merchant_id"),
        "target_merchant_ref": _hashable_json(target_merchant_ref.model_dump(mode="json"))
        if target_merchant_ref
        else None,
        "business_fact_refs": [_hashable_json(ref.model_dump(mode="json")) for ref in business_fact_refs],
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
    action_payload_hash: str | None,
    target_merchant_id: str | None = None,
    target_merchant_ref: TargetMerchantBindingV1 | Mapping[str, Any] | None = None,
    business_fact_refs: list[BusinessFactRefV1 | Mapping[str, Any]] | None = None,
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

    if action_payload_hash is not None and (not target_merchant_id or target_merchant_ref is None):
        raise ValueError("action-bound snapshot requires target merchant binding")

    evidence_refs = [_as_evidence_ref(ref) for ref in evidence]
    canonical_target_ref = _as_target_merchant_ref(target_merchant_ref)
    if target_merchant_id and canonical_target_ref and canonical_target_ref.target_merchant_id != target_merchant_id:
        raise ValueError("snapshot target merchant binding mismatch")
    canonical_business_fact_refs = [_as_business_fact_ref(ref) for ref in business_fact_refs or []]
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
        "target_merchant_id": target_merchant_id,
        "target_merchant_ref": canonical_target_ref,
        "business_fact_refs": canonical_business_fact_refs,
        "created_at": _format_timestamp(created_at),
    }
    projection = snapshot_hash_projection(data)
    immutable_hash = canonical_hash(
        projection,
        schema_version=ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION,
        allowed_fields=SNAPSHOT_HASH_FIELDS,
        nullable_fields={
            "action_payload_hash",
            "target_merchant_id",
            "target_merchant_ref",
            "resource_version",
            "data_freshness_at",
        },
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


def _as_target_merchant_ref(ref: TargetMerchantBindingV1 | Mapping[str, Any] | None) -> TargetMerchantBindingV1 | None:
    if ref is None:
        return None
    if isinstance(ref, TargetMerchantBindingV1):
        return ref
    return TargetMerchantBindingV1.model_validate(ref)


def _as_business_fact_ref(ref: BusinessFactRefV1 | Mapping[str, Any]) -> BusinessFactRefV1:
    if isinstance(ref, BusinessFactRefV1):
        return ref
    return BusinessFactRefV1.model_validate(ref)


def _hashable_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _hashable_json_timestamp(str(key), nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_hashable_json(item) for item in value]
    return value


def _hashable_json_timestamp(key: str, value: Any) -> Any:
    if key.endswith("_at") and isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        return _format_timestamp(parsed)
    return _hashable_json(value)


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
