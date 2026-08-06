"""Canonical, tenant-bound evidence identity contract.

This module is the only owner of ``evidence_identity.v1`` hashing and legacy
alias resolution. Callers must pass material loaded from the trusted immutable
repository boundary; request payloads never mint canonical identity directly.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.common.canonical_hash import canonical_hash

EVIDENCE_IDENTITY_SCHEMA_VERSION = "evidence_identity.v1"
ACCEPTED_POLICY_SCOPE_TYPE = "tenant_policy"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_LEGACY_ALIAS_RE = re.compile(r"^(?P<doc_key>[^/@]+)/(?P<chunk_id>[^/@]+)@v(?P<version>[1-9][0-9]*)$")


class EvidenceIdentityResolutionStatus(StrEnum):
    CANONICAL = "canonical"
    LEGACY_RESOLVED = "legacy_resolved"
    LEGACY_UNRESOLVED = "legacy_unresolved"
    INVALID = "invalid"


class EvidenceIdentityInternalReason(StrEnum):
    OK = "ok"
    LEGACY_ALIAS_RESOLVED = "legacy_alias_resolved"
    TENANT_MISMATCH = "tenant_mismatch"
    SCOPE_MISMATCH = "scope_mismatch"
    UNSUPPORTED_SCOPE = "unsupported_scope"
    HASH_MISMATCH = "hash_mismatch"
    VERSION_MISMATCH = "version_mismatch"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    MALFORMED = "malformed"
    INVALID_MATERIAL = "invalid_material"


class EvidenceIdentityExternalReason(StrEnum):
    """Public failure surface; deliberately hides existence and mismatch detail."""

    EVIDENCE_UNAVAILABLE = "evidence_unavailable"


class PersistedEvidenceIdentityMaterialV1(BaseModel):
    """Exact immutable material loaded from the trusted repository boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str
    scope_type: str
    scope_id: str
    document_version_id: str
    chunk_version_id: str
    doc_key: str = Field(min_length=1)
    document_version: int = Field(gt=0)
    chunk_id: str = Field(min_length=1)
    chunk_version: int = Field(gt=0)
    text_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def hash_material(self) -> dict[str, str | int]:
        return {
            "schema_version": EVIDENCE_IDENTITY_SCHEMA_VERSION,
            "tenant_id": self.tenant_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "document_version_id": self.document_version_id,
            "chunk_version_id": self.chunk_version_id,
            "doc_key": self.doc_key,
            "document_version": self.document_version,
            "chunk_id": self.chunk_id,
            "chunk_version": self.chunk_version,
            "text_hash": self.text_hash,
        }


_IDENTITY_HASH_FIELDS = {
    "schema_version",
    "tenant_id",
    "scope_type",
    "scope_id",
    "document_version_id",
    "chunk_version_id",
    "doc_key",
    "document_version",
    "chunk_id",
    "chunk_version",
    "text_hash",
}


class CanonicalEvidenceIdentityV1(BaseModel):
    """Frozen canonical identity produced from persisted immutable material."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["evidence_identity.v1"] = EVIDENCE_IDENTITY_SCHEMA_VERSION
    evidence_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    tenant_id: str
    scope_type: Literal["tenant_policy"]
    scope_id: str
    document_version_id: str
    chunk_version_id: str
    doc_key: str = Field(min_length=1)
    document_version: int = Field(gt=0)
    chunk_id: str = Field(min_length=1)
    chunk_version: int = Field(gt=0)
    text_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_canonical_binding(self) -> CanonicalEvidenceIdentityV1:
        if self.scope_id != self.tenant_id:
            raise ValueError("evidence_identity.v1 scope_id must equal the serialized tenant_id")
        expected = _hash_identity_material(self.hash_material())
        if self.evidence_id != expected:
            raise ValueError("evidence_id does not match canonical persisted material")
        return self

    def hash_material(self) -> dict[str, str | int]:
        return {
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "document_version_id": self.document_version_id,
            "chunk_version_id": self.chunk_version_id,
            "doc_key": self.doc_key,
            "document_version": self.document_version,
            "chunk_id": self.chunk_id,
            "chunk_version": self.chunk_version,
            "text_hash": self.text_hash,
        }


class CanonicalEvidenceResolutionV1(BaseModel):
    """Typed result that keeps detailed reasons internal and public failures generic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["evidence_identity_resolution.v1"] = "evidence_identity_resolution.v1"
    status: EvidenceIdentityResolutionStatus
    identity: CanonicalEvidenceIdentityV1 | None = None
    internal_reason: EvidenceIdentityInternalReason
    external_reason: EvidenceIdentityExternalReason | None = None

    @model_validator(mode="after")
    def _validate_result_shape(self) -> CanonicalEvidenceResolutionV1:
        is_success = self.status in {
            EvidenceIdentityResolutionStatus.CANONICAL,
            EvidenceIdentityResolutionStatus.LEGACY_RESOLVED,
        }
        if is_success and (self.identity is None or self.external_reason is not None):
            raise ValueError("resolved evidence identity must contain identity and no external failure")
        if not is_success and (
            self.identity is not None or self.external_reason is not EvidenceIdentityExternalReason.EVIDENCE_UNAVAILABLE
        ):
            raise ValueError("failed evidence identity must use the generic external failure")
        return self


def mint_canonical_evidence_identity(
    persisted_material: PersistedEvidenceIdentityMaterialV1 | Mapping[str, Any],
    *,
    expected_tenant_id: str,
    expected_scope_type: str,
    expected_scope_id: str,
) -> CanonicalEvidenceResolutionV1:
    """Mint only after exact tenant and accepted-scope comparison at a trusted boundary."""

    try:
        material = _coerce_material(persisted_material)
    except ValidationError:
        return _failure(EvidenceIdentityResolutionStatus.INVALID, EvidenceIdentityInternalReason.INVALID_MATERIAL)

    scope_failure = _scope_failure(
        material,
        expected_tenant_id=expected_tenant_id,
        expected_scope_type=expected_scope_type,
        expected_scope_id=expected_scope_id,
    )
    if scope_failure is not None:
        return _failure(EvidenceIdentityResolutionStatus.INVALID, scope_failure)

    material_dict = material.hash_material()
    identity = CanonicalEvidenceIdentityV1(
        evidence_id=_hash_identity_material(material_dict),
        **material_dict,
    )
    return CanonicalEvidenceResolutionV1(
        status=EvidenceIdentityResolutionStatus.CANONICAL,
        identity=identity,
        internal_reason=EvidenceIdentityInternalReason.OK,
    )


def validate_canonical_evidence_identity(
    candidate: CanonicalEvidenceIdentityV1 | Mapping[str, Any],
    persisted_material: PersistedEvidenceIdentityMaterialV1 | Mapping[str, Any],
    *,
    expected_tenant_id: str,
    expected_scope_type: str,
    expected_scope_id: str,
) -> CanonicalEvidenceResolutionV1:
    """Recompute and compare every identity field instead of trusting caller IDs."""

    trusted = mint_canonical_evidence_identity(
        persisted_material,
        expected_tenant_id=expected_tenant_id,
        expected_scope_type=expected_scope_type,
        expected_scope_id=expected_scope_id,
    )
    if trusted.identity is None:
        return trusted

    raw = candidate.model_dump() if isinstance(candidate, CanonicalEvidenceIdentityV1) else dict(candidate)
    reason = _candidate_mismatch_reason(raw, trusted.identity)
    if reason is not None:
        return _failure(EvidenceIdentityResolutionStatus.INVALID, reason)

    try:
        parsed = CanonicalEvidenceIdentityV1.model_validate(raw)
    except ValidationError:
        return _failure(EvidenceIdentityResolutionStatus.INVALID, EvidenceIdentityInternalReason.MALFORMED)
    return CanonicalEvidenceResolutionV1(
        status=EvidenceIdentityResolutionStatus.CANONICAL,
        identity=parsed,
        internal_reason=EvidenceIdentityInternalReason.OK,
    )


def resolve_evidence_identity(
    candidate: str | CanonicalEvidenceIdentityV1 | Mapping[str, Any],
    persisted_candidates: Sequence[PersistedEvidenceIdentityMaterialV1 | Mapping[str, Any]],
    *,
    expected_tenant_id: str,
    expected_scope_type: str,
    expected_scope_id: str,
) -> CanonicalEvidenceResolutionV1:
    """Resolve canonical IDs or legacy display aliases against persisted candidates."""

    if isinstance(candidate, (CanonicalEvidenceIdentityV1, Mapping)):
        if len(persisted_candidates) != 1:
            reason = (
                EvidenceIdentityInternalReason.AMBIGUOUS
                if persisted_candidates
                else EvidenceIdentityInternalReason.MISSING
            )
            return _failure(EvidenceIdentityResolutionStatus.INVALID, reason)
        return validate_canonical_evidence_identity(
            candidate,
            persisted_candidates[0],
            expected_tenant_id=expected_tenant_id,
            expected_scope_type=expected_scope_type,
            expected_scope_id=expected_scope_id,
        )

    if _SHA256_RE.fullmatch(candidate):
        matches: list[CanonicalEvidenceIdentityV1] = []
        for material in persisted_candidates:
            resolution = mint_canonical_evidence_identity(
                material,
                expected_tenant_id=expected_tenant_id,
                expected_scope_type=expected_scope_type,
                expected_scope_id=expected_scope_id,
            )
            if resolution.identity is not None and resolution.identity.evidence_id == candidate:
                matches.append(resolution.identity)
        if len(matches) == 1:
            return CanonicalEvidenceResolutionV1(
                status=EvidenceIdentityResolutionStatus.CANONICAL,
                identity=matches[0],
                internal_reason=EvidenceIdentityInternalReason.OK,
            )
        reason = (
            EvidenceIdentityInternalReason.AMBIGUOUS if len(matches) > 1 else EvidenceIdentityInternalReason.MISSING
        )
        return _failure(EvidenceIdentityResolutionStatus.INVALID, reason)

    alias = _LEGACY_ALIAS_RE.fullmatch(candidate)
    if alias is None:
        return _failure(EvidenceIdentityResolutionStatus.INVALID, EvidenceIdentityInternalReason.MALFORMED)

    try:
        materials = [_coerce_material(item) for item in persisted_candidates]
    except ValidationError:
        return _failure(
            EvidenceIdentityResolutionStatus.LEGACY_UNRESOLVED, EvidenceIdentityInternalReason.INVALID_MATERIAL
        )
    alias_matches = [
        material
        for material in materials
        if material.doc_key == alias["doc_key"]
        and material.chunk_id == alias["chunk_id"]
        and material.document_version == int(alias["version"])
    ]
    if not alias_matches:
        return _failure(EvidenceIdentityResolutionStatus.LEGACY_UNRESOLVED, EvidenceIdentityInternalReason.MISSING)

    resolved: list[CanonicalEvidenceIdentityV1] = []
    failures: list[EvidenceIdentityInternalReason] = []
    for material in alias_matches:
        resolution = mint_canonical_evidence_identity(
            material,
            expected_tenant_id=expected_tenant_id,
            expected_scope_type=expected_scope_type,
            expected_scope_id=expected_scope_id,
        )
        if resolution.identity is not None:
            resolved.append(resolution.identity)
        else:
            failures.append(resolution.internal_reason)

    if len(resolved) == 1:
        return CanonicalEvidenceResolutionV1(
            status=EvidenceIdentityResolutionStatus.LEGACY_RESOLVED,
            identity=resolved[0],
            internal_reason=EvidenceIdentityInternalReason.LEGACY_ALIAS_RESOLVED,
        )
    if len(resolved) > 1:
        return _failure(EvidenceIdentityResolutionStatus.LEGACY_UNRESOLVED, EvidenceIdentityInternalReason.AMBIGUOUS)
    return _failure(
        EvidenceIdentityResolutionStatus.LEGACY_UNRESOLVED,
        failures[0] if failures else EvidenceIdentityInternalReason.MISSING,
    )


def _coerce_material(
    value: PersistedEvidenceIdentityMaterialV1 | Mapping[str, Any],
) -> PersistedEvidenceIdentityMaterialV1:
    if isinstance(value, PersistedEvidenceIdentityMaterialV1):
        return value
    return PersistedEvidenceIdentityMaterialV1.model_validate(value)


def _scope_failure(
    material: PersistedEvidenceIdentityMaterialV1,
    *,
    expected_tenant_id: str,
    expected_scope_type: str,
    expected_scope_id: str,
) -> EvidenceIdentityInternalReason | None:
    expected_tenant = str(expected_tenant_id)
    expected_scope = str(expected_scope_id)
    if expected_scope_type != ACCEPTED_POLICY_SCOPE_TYPE:
        return EvidenceIdentityInternalReason.UNSUPPORTED_SCOPE
    if expected_scope != expected_tenant:
        return EvidenceIdentityInternalReason.SCOPE_MISMATCH
    if material.tenant_id != expected_tenant:
        return EvidenceIdentityInternalReason.TENANT_MISMATCH
    if material.scope_type != ACCEPTED_POLICY_SCOPE_TYPE or material.scope_id != expected_scope:
        return EvidenceIdentityInternalReason.SCOPE_MISMATCH
    return None


def _candidate_mismatch_reason(
    candidate: Mapping[str, Any],
    trusted: CanonicalEvidenceIdentityV1,
) -> EvidenceIdentityInternalReason | None:
    if candidate.get("tenant_id") != trusted.tenant_id:
        return EvidenceIdentityInternalReason.TENANT_MISMATCH
    if candidate.get("scope_type") != trusted.scope_type or candidate.get("scope_id") != trusted.scope_id:
        return EvidenceIdentityInternalReason.SCOPE_MISMATCH
    version_fields = ("document_version_id", "chunk_version_id", "document_version", "chunk_version")
    if any(candidate.get(field) != getattr(trusted, field) for field in version_fields):
        return EvidenceIdentityInternalReason.VERSION_MISMATCH
    if candidate.get("text_hash") != trusted.text_hash:
        return EvidenceIdentityInternalReason.HASH_MISMATCH
    identity_fields = ("schema_version", "doc_key", "chunk_id")
    if any(candidate.get(field) != getattr(trusted, field) for field in identity_fields):
        return EvidenceIdentityInternalReason.MISSING
    if candidate.get("evidence_id") != trusted.evidence_id:
        return EvidenceIdentityInternalReason.HASH_MISMATCH
    return None


def _hash_identity_material(material: Mapping[str, Any]) -> str:
    return canonical_hash(
        material,
        schema_version=EVIDENCE_IDENTITY_SCHEMA_VERSION,
        allowed_fields=_IDENTITY_HASH_FIELDS,
    )


def _failure(
    status: EvidenceIdentityResolutionStatus,
    reason: EvidenceIdentityInternalReason,
) -> CanonicalEvidenceResolutionV1:
    return CanonicalEvidenceResolutionV1(
        status=status,
        internal_reason=reason,
        external_reason=EvidenceIdentityExternalReason.EVIDENCE_UNAVAILABLE,
    )
