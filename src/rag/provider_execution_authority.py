"""Typed, fail-closed provider execution authority boundary.

PostgreSQL rows are authoritative.  The models in this module are immutable
request/value objects; file projections produced by reconciliation are audit
copies and never grant permission to construct or call a provider.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, ClassVar, Final, Literal, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


PROMOTION_SCOPE = "phase64.5.reviewed-provider-execution"
PROMOTION_SCHEMA_VERSION = "provider_execution_promotion.v1"
AUTHORITY_SCHEMA_VERSION = "provider_execution_authority.v1"
RESERVATION_SCHEMA_VERSION = "provider_execution_reservation.v1"
RESULT_SCHEMA_VERSION = "provider_execution_result.v1"
PROJECTION_SCHEMA_VERSION = "provider_execution_projection.v1"
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
GIT_OBJECT_PATTERN = r"^[0-9a-f]{40}$"

# This is the sole review/promotion identity for provider-capable production
# code. ``src`` is deliberately a broad Git pathspec: every loadable application
# module and migration is security-relevant to provider dispatch, so a narrow
# hand-maintained import list is not a safe boundary. The exact script paths are
# the two provider CLIs, their imported parity helper, and the checker which
# seals/promotes this graph. Tests and review artifacts are intentionally not
# execution identity inputs.
PROTECTED_PROVIDER_EXECUTION_GRAPH: Final[tuple[str, ...]] = (
    "src",
    "scripts/__init__.py",
    "scripts/reindex_policies.py",
    "scripts/eval_rag_token_chunk_ab.py",
    "scripts/eval_rag_format_parity.py",
    "scripts/check_phase64_5_gate.py",
)


class ProviderExecutionPurpose(StrEnum):
    REVIEWED_BUILD = "reviewed_build"
    CANONICAL_AB = "canonical_ab"


class ProviderExecutionResultCode(StrEnum):
    SUCCESS = "success"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TRANSIENT_EXECUTION_ERROR = "transient_execution_error"
    QUALITY_FAIL = "quality_fail"
    SAFETY_FAIL = "safety_fail"
    CONFIGURATION_ERROR = "configuration_error"
    PARITY_ERROR = "parity_error"
    SOURCE_DRIFT = "source_drift"
    RESPONSE_ERROR = "response_error"
    PROJECTION_ERROR = "projection_error"
    UNKNOWN_ERROR = "unknown_error"


RETRYABLE_RESULT_CODES = frozenset(
    {
        ProviderExecutionResultCode.PROVIDER_UNAVAILABLE,
        ProviderExecutionResultCode.TRANSIENT_EXECUTION_ERROR,
    }
)


class ProviderExecutionAuthorityFailureCode(StrEnum):
    PROMOTION_MISSING = "promotion_missing"
    PROMOTION_STALE = "promotion_stale"
    PROMOTION_MISMATCH = "promotion_mismatch"
    AUTHORITY_MISSING = "authority_missing"
    AUTHORITY_STALE = "authority_stale"
    AUTHORITY_MISMATCH = "authority_mismatch"
    RESERVATION_CONFLICT = "reservation_conflict"
    RESERVATION_MISSING = "reservation_missing"
    RESERVATION_MISMATCH = "reservation_mismatch"
    RESERVATION_EXHAUSTED = "reservation_exhausted"
    RETRY_NOT_ALLOWED = "retry_not_allowed"
    RESULT_MISMATCH = "result_mismatch"
    PROJECTION_MISMATCH = "projection_mismatch"


class ProviderExecutionAuthorityError(RuntimeError):
    """Safe typed refusal; details never include source/provider payload bytes."""

    def __init__(self, reason_code: ProviderExecutionAuthorityFailureCode | str) -> None:
        self.reason_code = str(reason_code)
        super().__init__(self.reason_code)


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CurrentProtectedCodeIdentityV1(_FrozenModel):
    commit: str = Field(pattern=GIT_OBJECT_PATTERN)
    tree_hash: str = Field(pattern=GIT_OBJECT_PATTERN)
    protected_paths: tuple[str, ...] = Field(min_length=1)


class ExecutionPromotionRequestV1(_FrozenModel):
    """Checker-validated bytes allowed into the singleton promotion row."""

    schema_version: Literal["provider_execution_promotion.v1"] = PROMOTION_SCHEMA_VERSION
    protected_code_c0_commit: str = Field(pattern=GIT_OBJECT_PATTERN)
    protected_code_c0_tree_hash: str = Field(pattern=GIT_OBJECT_PATTERN)
    protected_code_c1_commit: str = Field(pattern=GIT_OBJECT_PATTERN)
    protected_code_c1_tree_hash: str = Field(pattern=GIT_OBJECT_PATTERN)
    c0_to_c1_diff_hash: str = Field(pattern=SHA256_PATTERN)
    c0_code_review_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    c0_security_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    c1_code_review_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    c1_security_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    c0_code_review_attestation_sha256: str = Field(pattern=SHA256_PATTERN)
    c0_security_attestation_sha256: str = Field(pattern=SHA256_PATTERN)
    c1_code_review_attestation_sha256: str = Field(pattern=SHA256_PATTERN)
    c1_security_attestation_sha256: str = Field(pattern=SHA256_PATTERN)
    c0_gate_report_sha256: str = Field(pattern=SHA256_PATTERN)
    c1_gate_report_sha256: str = Field(pattern=SHA256_PATTERN)
    promotion_request_hash: str = Field(pattern=SHA256_PATTERN)

    _HASH_FIELDS: ClassVar[tuple[str, ...]] = (
        "schema_version",
        "protected_code_c0_commit",
        "protected_code_c0_tree_hash",
        "protected_code_c1_commit",
        "protected_code_c1_tree_hash",
        "c0_to_c1_diff_hash",
        "c0_code_review_artifact_sha256",
        "c0_security_artifact_sha256",
        "c1_code_review_artifact_sha256",
        "c1_security_artifact_sha256",
        "c0_code_review_attestation_sha256",
        "c0_security_attestation_sha256",
        "c1_code_review_attestation_sha256",
        "c1_security_attestation_sha256",
        "c0_gate_report_sha256",
        "c1_gate_report_sha256",
    )

    @classmethod
    def seal(cls, **values: Any) -> Self:
        payload = {"schema_version": PROMOTION_SCHEMA_VERSION, **values}
        return cls(**payload, promotion_request_hash=canonical_sha256(payload))

    @model_validator(mode="after")
    def validate_canonical_hash(self) -> Self:
        payload = {field: getattr(self, field) for field in self._HASH_FIELDS}
        if canonical_sha256(payload) != self.promotion_request_hash:
            raise ValueError("promotion_request_hash_mismatch")
        if self.protected_code_c0_commit == self.protected_code_c1_commit:
            raise ValueError("promotion_transition_missing")
        return self


class ExecutionPromotionViewV1(ExecutionPromotionRequestV1):
    promotion_id: UUID
    scope: Literal["phase64.5.reviewed-provider-execution"] = PROMOTION_SCOPE
    promoted_at: datetime


class ProviderExecutionAuthorityRequestV1(_FrozenModel):
    """Shared root bindings; purpose and request envelopes live on reservations."""

    schema_version: Literal["provider_execution_authority.v1"] = AUTHORITY_SCHEMA_VERSION
    tenant_id: UUID
    run_token: UUID
    candidate_id: UUID
    owner_marker: str = Field(min_length=1, max_length=128)
    config_schema_version: str = Field(min_length=1, max_length=64)
    config_json: dict[str, JsonValue]
    config_fingerprint: str = Field(pattern=SHA256_PATTERN)
    provider_parity_run_id: UUID
    provider_parity_report_hash: str = Field(pattern=SHA256_PATTERN)
    provider_parity_probe_fixture_sha256: str = Field(pattern=SHA256_PATTERN)
    provider_parity_submitted_content_sha256: str = Field(pattern=SHA256_PATTERN)
    parity_captured_at: datetime
    parity_expires_at: datetime
    source_manifest_revision_id: UUID
    source_manifest_hash: str = Field(pattern=SHA256_PATTERN)
    source_active_corpus_version_id: UUID
    source_rollout_epoch: int = Field(gt=0)
    evidence_rollout_version: int = Field(ge=0)
    candidate_lease_expires_at: datetime
    expires_at: datetime
    provider_name: str = Field(min_length=1, max_length=64)
    model_name: str = Field(min_length=1, max_length=128)
    dimensions: int = Field(gt=0)
    envelope_contract_hash: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_expiry_intersection(self) -> Self:
        captured = as_utc(self.parity_captured_at)
        parity_expiry = as_utc(self.parity_expires_at)
        lease_expiry = as_utc(self.candidate_lease_expires_at)
        expiry = as_utc(self.expires_at)
        if captured >= parity_expiry or expiry != min(parity_expiry, lease_expiry):
            raise ValueError("authority_expiry_intersection_invalid")
        return self


class ProviderExecutionAuthorityViewV1(ProviderExecutionAuthorityRequestV1):
    authority_id: UUID
    promotion_id: UUID
    issued_at: datetime


class ProviderRequestEnvelopeV1(_FrozenModel):
    schema_version: str = Field(min_length=1, max_length=64)
    contract_hash: str = Field(pattern=SHA256_PATTERN)
    ordered_call_sites: tuple[str, ...] = Field(min_length=1)
    maximum_attempts_per_site: tuple[int, ...] = Field(min_length=1)
    maximum_request_count: int = Field(gt=0)
    provider_name: str = Field(min_length=1, max_length=64)
    model_name: str = Field(min_length=1, max_length=128)
    dimensions: int = Field(gt=0)
    canonical_hash: str = Field(pattern=SHA256_PATTERN)

    @classmethod
    def seal(cls, **values: Any) -> Self:
        payload = dict(values)
        return cls(**payload, canonical_hash=canonical_sha256(payload))

    @model_validator(mode="after")
    def validate_bounded_calls(self) -> Self:
        if (
            len(self.ordered_call_sites) != len(self.maximum_attempts_per_site)
            or len(set(self.ordered_call_sites)) != len(self.ordered_call_sites)
            or any(not site.strip() or len(site) > 256 for site in self.ordered_call_sites)
            or any(attempts <= 0 for attempts in self.maximum_attempts_per_site)
            or sum(self.maximum_attempts_per_site) != self.maximum_request_count
        ):
            raise ValueError("request_envelope_cardinality_invalid")
        payload = self.model_dump(mode="json", exclude={"canonical_hash"})
        if canonical_sha256(payload) != self.canonical_hash:
            raise ValueError("request_envelope_hash_mismatch")
        return self


class ProviderExecutionReservationRequestV1(_FrozenModel):
    authority_id: UUID
    purpose: ProviderExecutionPurpose
    subject_kind: Literal["candidate_document", "canonical_ab_run"]
    subject_index: int = Field(ge=0)
    subject_hash: str = Field(pattern=SHA256_PATTERN)
    ordinal: int = Field(ge=1)
    request_envelope: ProviderRequestEnvelopeV1
    explicit_retry: bool = False

    @model_validator(mode="after")
    def validate_purpose_and_retry(self) -> Self:
        expected_kind = {
            ProviderExecutionPurpose.REVIEWED_BUILD: "candidate_document",
            ProviderExecutionPurpose.CANONICAL_AB: "canonical_ab_run",
        }[self.purpose]
        if self.subject_kind != expected_kind:
            raise ValueError("reservation_subject_kind_mismatch")
        if self.purpose is ProviderExecutionPurpose.CANONICAL_AB and self.subject_index != 0:
            raise ValueError("canonical_ab_subject_index_invalid")
        if self.explicit_retry != (self.ordinal == 2):
            raise ValueError("reservation_retry_intent_mismatch")
        return self


class ProviderExecutionReservationViewV1(ProviderExecutionReservationRequestV1):
    schema_version: Literal["provider_execution_reservation.v1"] = RESERVATION_SCHEMA_VERSION
    reservation_id: UUID
    tenant_id: UUID
    predecessor_result_id: UUID | None = None
    reserved_at: datetime


class ProviderExecutionResultRequestV1(_FrozenModel):
    reservation_id: UUID
    result_id: UUID
    result_code: ProviderExecutionResultCode
    actual_request_count: int = Field(ge=0)
    result_json: dict[str, JsonValue]
    output_candidate_id: UUID | None = None
    terminal_run_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    terminal_report_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    selection_id: UUID | None = None
    selection_decision_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    activation_authorization_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    result_hash: str = Field(pattern=SHA256_PATTERN)

    _HASH_FIELDS: ClassVar[tuple[str, ...]] = (
        "reservation_id",
        "result_id",
        "result_code",
        "actual_request_count",
        "result_json",
        "output_candidate_id",
        "terminal_run_hash",
        "terminal_report_hash",
        "selection_id",
        "selection_decision_hash",
        "activation_authorization_hash",
    )

    @classmethod
    def seal(cls, **values: Any) -> Self:
        payload = {
            "result_id": values.pop("result_id", uuid4()),
            "output_candidate_id": None,
            "terminal_run_hash": None,
            "terminal_report_hash": None,
            "selection_id": None,
            "selection_decision_hash": None,
            "activation_authorization_hash": None,
            **values,
        }
        return cls(**payload, result_hash=canonical_sha256(payload))

    @model_validator(mode="after")
    def validate_canonical_hash(self) -> Self:
        payload = {field: getattr(self, field) for field in self._HASH_FIELDS}
        if canonical_sha256(payload) != self.result_hash:
            raise ValueError("result_hash_mismatch")
        if self.result_code is ProviderExecutionResultCode.TRANSIENT_EXECUTION_ERROR and self.actual_request_count == 0:
            raise ValueError("transient_result_requires_actual_request")
        return self


class ProviderExecutionResultViewV1(ProviderExecutionResultRequestV1):
    schema_version: Literal["provider_execution_result.v1"] = RESULT_SCHEMA_VERSION
    tenant_id: UUID
    request_limit: int = Field(gt=0)
    completed_at: datetime


class ProviderExecutionProjectionV1(_FrozenModel):
    """Non-authoritative, deterministic snapshot of one committed DB graph."""

    schema_version: Literal["provider_execution_projection.v1"] = PROJECTION_SCHEMA_VERSION
    promotion: ExecutionPromotionViewV1
    authority: ProviderExecutionAuthorityViewV1
    reservations: tuple[ProviderExecutionReservationViewV1, ...]
    results: tuple[ProviderExecutionResultViewV1, ...]


class ProjectionReconciliationViewV1(_FrozenModel):
    projection_path: Path
    projection_sha256: str = Field(pattern=SHA256_PATTERN)
    created: bool
    projection: ProviderExecutionProjectionV1


class ProviderExecutionAuthorityService:
    """Orchestrates only typed calls; each repository mutation commits independently."""

    def __init__(self, repository: Any) -> None:
        self._repository = repository

    async def inspect_current_code_identity(self) -> CurrentProtectedCodeIdentityV1:
        return await self._repository.inspect_current_code_identity()

    async def promote_reviewed_execution(
        self,
        request: ExecutionPromotionRequestV1,
    ) -> ExecutionPromotionViewV1:
        return await self._repository.promote_reviewed_execution(request)

    async def require_current_promotion(self) -> ExecutionPromotionViewV1:
        return await self._repository.require_current_promotion()

    async def issue_authority_root(
        self,
        request: ProviderExecutionAuthorityRequestV1,
    ) -> ProviderExecutionAuthorityViewV1:
        await self.require_current_promotion()
        return await self._repository.issue_authority_root(request)

    async def reserve_and_commit(
        self,
        request: ProviderExecutionReservationRequestV1,
    ) -> ProviderExecutionReservationViewV1:
        await self.require_current_promotion()
        return await self._repository.reserve_and_commit(request)

    async def recheck_dispatch(
        self,
        reservation: ProviderExecutionReservationViewV1,
    ) -> ProviderExecutionReservationViewV1:
        await self.require_current_promotion()
        return await self._repository.recheck_dispatch(reservation)

    async def record_result(
        self,
        request: ProviderExecutionResultRequestV1,
    ) -> ProviderExecutionResultViewV1:
        return await self._repository.record_result(request)

    async def get_result(
        self,
        *,
        reservation_id: UUID,
    ) -> ProviderExecutionResultViewV1 | None:
        return await self._repository.get_result(reservation_id=reservation_id)

    async def reconcile_projection(
        self,
        *,
        authority_id: UUID,
        projection_path: Path,
    ) -> ProjectionReconciliationViewV1:
        """Create one immutable audit projection from committed DB rows only."""

        projection = await self._repository.read_projection(authority_id=authority_id)
        payload = canonical_json_bytes(projection.model_dump(mode="json")) + b"\n"
        path = projection_path.absolute()
        path.parent.mkdir(parents=True, exist_ok=True)
        created = _create_projection_once(path, payload)
        return ProjectionReconciliationViewV1(
            projection_path=path,
            projection_sha256=canonical_sha256(payload),
            created=created,
            projection=projection,
        )


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_canonical_json_default,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    payload = bytes(value) if isinstance(value, (bytes, bytearray, memoryview)) else canonical_json_bytes(value)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _canonical_json_default(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def _create_projection_once(path: Path, payload: bytes) -> bool:
    """Atomically create without replacing any pre-existing projection bytes."""

    try:
        existing_stat = path.lstat()
    except FileNotFoundError:
        existing_stat = None
    if existing_stat is not None:
        if not stat.S_ISREG(existing_stat.st_mode) or path.read_bytes() != payload:
            _fail(ProviderExecutionAuthorityFailureCode.PROJECTION_MISMATCH)
        return False

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_path, path)
            created = True
        except FileExistsError:
            created = False
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    try:
        final_stat = path.lstat()
    except FileNotFoundError:
        _fail(ProviderExecutionAuthorityFailureCode.PROJECTION_MISMATCH)
    if not stat.S_ISREG(final_stat.st_mode) or path.read_bytes() != payload:
        _fail(ProviderExecutionAuthorityFailureCode.PROJECTION_MISMATCH)
    return created


def _fail(code: ProviderExecutionAuthorityFailureCode) -> None:
    raise ProviderExecutionAuthorityError(code)
