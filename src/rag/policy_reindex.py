"""Tenant/run-scoped inactive policy corpus build lifecycle.

The rollout pointer is the only current authority.  This service may claim,
resume, checkpoint, validate, or fail a candidate, but it never flips that
pointer and never reparses source files.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import re
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PolicyCorpusManifestRevision, PolicyCorpusVersion
from src.repositories.policy_corpus_repo import PolicyCorpusRepository, PolicyCorpusUnavailable


POLICY_REINDEX_OWNER_MARKER = "moca.policy_reindex.v1"
POLICY_REINDEX_CLAIM_SCHEMA_VERSION = "policy_reindex_claim.v1"
POLICY_REINDEX_STATES = frozenset({"claimed", "building", "built", "validating", "complete", "failed", "source_stale"})
POLICY_REINDEX_TERMINAL_STATES = frozenset({"complete", "failed", "source_stale"})
DEFAULT_PARITY_MAXIMUM_AGE = timedelta(hours=24)
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class PolicyReindexFailureCode(StrEnum):
    INVALID_CLAIM = "invalid_claim"
    AUTHORITY_UNAVAILABLE = "authority_unavailable"
    RUN_IDENTITY_MISMATCH = "run_identity_mismatch"
    CONFIG_DRIFT = "config_drift"
    PARITY_DRIFT = "parity_drift"
    PARITY_STALE = "parity_stale"
    SOURCE_MANIFEST_DRIFT = "source_manifest_drift"
    SOURCE_POINTER_DRIFT = "source_pointer_drift"
    LEASE_OWNER_MISMATCH = "lease_owner_mismatch"
    LEASE_EXPIRED = "lease_expired"
    STATE_MISMATCH = "state_mismatch"
    CAS_CONFLICT = "cas_conflict"
    DOCUMENT_ORDER_MISMATCH = "document_order_mismatch"


class PolicyReindexError(RuntimeError):
    """Safe lifecycle refusal with no source, credential, or payload text."""

    def __init__(self, code: PolicyReindexFailureCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class FreshProviderParityClaimV1:
    report_hash: str
    config_fingerprint: str
    captured_at: datetime
    status: Literal["passed", "quarantined", "unavailable"]


@dataclass(frozen=True, slots=True)
class PolicyReindexClaimRequest:
    tenant_id: UUID
    run_token: UUID
    generation_name: str
    lease_owner: str
    lease_expires_at: datetime
    config_schema_version: str
    config_json: dict[str, Any]
    config_fingerprint: str
    parity: FreshProviderParityClaimV1
    source_manifest_revision_id: UUID
    source_manifest_revision: int
    source_manifest_hash: str
    source_active_corpus_version_id: UUID
    source_rollout_epoch: int
    expected_evidence_rollout_version: int


@dataclass(frozen=True, slots=True)
class PolicyReindexRunIdentity:
    corpus_version_id: UUID
    tenant_id: UUID
    run_token: UUID
    generation_name: str
    lease_owner: str
    lease_expires_at: datetime
    state: str
    state_version: int
    next_document_index: int
    ordered_doc_keys: tuple[str, ...]
    config_schema_version: str
    config_fingerprint: str
    provider_parity_report_hash: str
    source_manifest_revision_id: UUID
    source_manifest_revision: int
    source_manifest_hash: str
    source_active_corpus_version_id: UUID
    source_rollout_epoch: int
    expected_evidence_rollout_version: int
    parity_captured_at: datetime
    parity_expires_at: datetime


class PolicyReindexService:
    """Claim and advance exactly one inactive candidate under tenant locks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.corpora = PolicyCorpusRepository(session)

    async def claim(
        self,
        request: PolicyReindexClaimRequest,
        *,
        now: datetime | None = None,
        parity_maximum_age: timedelta = DEFAULT_PARITY_MAXIMUM_AGE,
    ) -> PolicyReindexRunIdentity:
        checked_at = _as_utc(now or datetime.now(UTC))
        parity_expires_at = self._validate_claim(
            request,
            now=checked_at,
            parity_maximum_age=parity_maximum_age,
        )
        try:
            rollout = await self.corpora.acquire_tenant_rollout_lock(tenant_id=request.tenant_id)
            manifest = await self.corpora.lock_latest_manifest(tenant_id=request.tenant_id)
        except PolicyCorpusUnavailable:
            _fail(PolicyReindexFailureCode.AUTHORITY_UNAVAILABLE)
        self._assert_requested_source_authority(request, manifest=manifest, rollout=rollout)
        source = await self.corpora.get_corpus(
            tenant_id=request.tenant_id,
            corpus_version_id=request.source_active_corpus_version_id,
        )
        if source is None or source.state != "complete":
            _fail(PolicyReindexFailureCode.SOURCE_POINTER_DRIFT)
        ordered_doc_keys = _ordered_doc_keys(manifest)

        existing = await self.corpora.get_candidate_by_run(
            tenant_id=request.tenant_id,
            run_token=request.run_token,
        )
        if existing is not None:
            owner = self._identity_from_row(existing, manifest=manifest)
            self._assert_claim_matches(request, owner)
            if owner.lease_expires_at <= checked_at:
                _fail(PolicyReindexFailureCode.LEASE_EXPIRED)
            return owner

        candidate = PolicyCorpusVersion(
            id=uuid4(),
            tenant_id=request.tenant_id,
            generation_name=request.generation_name,
            owner_marker=POLICY_REINDEX_OWNER_MARKER,
            run_token=request.run_token,
            config_schema_version=request.config_schema_version,
            config_json=dict(request.config_json),
            config_fingerprint=request.config_fingerprint,
            provider_parity_report_hash=request.parity.report_hash,
            source_manifest_revision_id=request.source_manifest_revision_id,
            source_manifest_hash=request.source_manifest_hash,
            source_active_corpus_version_id=request.source_active_corpus_version_id,
            source_rollout_epoch=request.source_rollout_epoch,
            expected_evidence_rollout_version=request.expected_evidence_rollout_version,
            state="claimed",
            state_version=1,
            lease_owner=request.lease_owner,
            lease_expires_at=_as_utc(request.lease_expires_at),
            next_document_index=0,
            bootstrap_counts_json={
                "source_document_count": manifest.document_count,
                "source_block_count": manifest.block_count,
                "source_chunk_count": manifest.chunk_count,
                "candidate_document_count": 0,
                "candidate_block_count": 0,
                "candidate_chunk_count": 0,
            },
            validation_proof_json={
                "claim": {
                    "schema_version": POLICY_REINDEX_CLAIM_SCHEMA_VERSION,
                    "ordered_doc_keys": list(ordered_doc_keys),
                    "source_manifest_revision": manifest.revision,
                    "parity_captured_at": _as_utc(request.parity.captured_at).isoformat(),
                    "parity_expires_at": parity_expires_at.isoformat(),
                }
            },
            failure_code=None,
            safe_message=None,
            terminal_at=None,
        )
        self.session.add(candidate)
        await self.session.flush()
        return self._identity_from_row(candidate, manifest=manifest)

    async def resume(
        self,
        owner: PolicyReindexRunIdentity,
        *,
        now: datetime | None = None,
    ) -> PolicyReindexRunIdentity:
        checked_at = _as_utc(now or datetime.now(UTC))
        row, manifest = await self._lock_validated(owner, now=checked_at)
        if row.state == "claimed":
            updated = await self.corpora.cas_candidate(
                row,
                expected_state_version=owner.state_version,
                expected_next_document_index=owner.next_document_index,
                values={"state": "building", "safe_message": "candidate build started"},
            )
            if updated is None:
                _fail(PolicyReindexFailureCode.CAS_CONFLICT)
            return self._identity_from_row(updated, manifest=manifest)
        if row.state in {"building", "built", "validating"}:
            return self._identity_from_row(row, manifest=manifest)
        _fail(PolicyReindexFailureCode.STATE_MISMATCH)

    async def checkpoint_document(
        self,
        owner: PolicyReindexRunIdentity,
        *,
        doc_key: str,
        now: datetime | None = None,
    ) -> PolicyReindexRunIdentity:
        """Advance only after the caller's document projection writes are flushed.

        The method never commits.  Projection writes and this cursor CAS therefore
        share the caller's per-document transaction and roll back together.
        """

        checked_at = _as_utc(now or datetime.now(UTC))
        row, manifest = await self._lock_validated(owner, now=checked_at)
        if row.state != "building":
            _fail(PolicyReindexFailureCode.STATE_MISMATCH)
        expected = (
            owner.ordered_doc_keys[owner.next_document_index]
            if owner.next_document_index < len(owner.ordered_doc_keys)
            else None
        )
        if expected is None or doc_key != expected:
            _fail(PolicyReindexFailureCode.DOCUMENT_ORDER_MISMATCH)
        next_index = owner.next_document_index + 1
        state = "built" if next_index == len(owner.ordered_doc_keys) else "building"
        updated = await self.corpora.cas_candidate(
            row,
            expected_state_version=owner.state_version,
            expected_next_document_index=owner.next_document_index,
            values={
                "state": state,
                "next_document_index": next_index,
                "safe_message": "candidate document checkpoint committed",
            },
        )
        if updated is None:
            _fail(PolicyReindexFailureCode.CAS_CONFLICT)
        return self._identity_from_row(updated, manifest=manifest)

    async def transition(
        self,
        owner: PolicyReindexRunIdentity,
        *,
        state: Literal["validating", "complete", "failed", "source_stale"],
        now: datetime | None = None,
        validation_proof: dict[str, Any] | None = None,
        failure_code: str | None = None,
    ) -> PolicyReindexRunIdentity:
        """CAS the remaining candidate-only states; never make a state active."""

        checked_at = _as_utc(now or datetime.now(UTC))
        row, manifest = await self._lock_validated(owner, now=checked_at, allow_terminal=False)
        allowed = {
            "built": {"validating", "failed", "source_stale"},
            "validating": {"complete", "failed", "source_stale"},
            "claimed": {"failed", "source_stale"},
            "building": {"failed", "source_stale"},
        }
        if state not in allowed.get(row.state, set()):
            _fail(PolicyReindexFailureCode.STATE_MISMATCH)
        if state in {"validating", "complete"} and row.next_document_index != len(owner.ordered_doc_keys):
            _fail(PolicyReindexFailureCode.STATE_MISMATCH)
        proof = dict(row.validation_proof_json or {})
        if validation_proof is not None:
            proof["candidate_validation"] = dict(validation_proof)
        updated = await self.corpora.cas_candidate(
            row,
            expected_state_version=owner.state_version,
            expected_next_document_index=owner.next_document_index,
            values={
                "state": state,
                "validation_proof_json": proof,
                "failure_code": failure_code,
                "safe_message": "candidate lifecycle advanced",
                "terminal_at": checked_at if state in POLICY_REINDEX_TERMINAL_STATES else None,
            },
        )
        if updated is None:
            _fail(PolicyReindexFailureCode.CAS_CONFLICT)
        return self._identity_from_row(updated, manifest=manifest)

    async def _lock_validated(
        self,
        owner: PolicyReindexRunIdentity,
        *,
        now: datetime,
        allow_terminal: bool = False,
    ) -> tuple[PolicyCorpusVersion, PolicyCorpusManifestRevision]:
        try:
            rollout = await self.corpora.acquire_tenant_rollout_lock(tenant_id=owner.tenant_id)
            row = await self.corpora.lock_candidate(corpus_version_id=owner.corpus_version_id)
            manifest = await self.corpora.lock_latest_manifest(tenant_id=owner.tenant_id)
        except PolicyCorpusUnavailable:
            _fail(PolicyReindexFailureCode.AUTHORITY_UNAVAILABLE)
        if row is None:
            _fail(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH)
        if (
            row.tenant_id != owner.tenant_id
            or row.run_token != owner.run_token
            or row.owner_marker != POLICY_REINDEX_OWNER_MARKER
            or row.generation_name != owner.generation_name
        ):
            _fail(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH)
        if (
            row.config_schema_version != owner.config_schema_version
            or row.config_fingerprint != owner.config_fingerprint
        ):
            _fail(PolicyReindexFailureCode.CONFIG_DRIFT)
        if row.provider_parity_report_hash != owner.provider_parity_report_hash:
            _fail(PolicyReindexFailureCode.PARITY_DRIFT)
        if row.lease_owner != owner.lease_owner:
            _fail(PolicyReindexFailureCode.LEASE_OWNER_MISMATCH)
        if row.lease_expires_at is None or _as_utc(row.lease_expires_at) <= now:
            _fail(PolicyReindexFailureCode.LEASE_EXPIRED)
        if now > owner.parity_expires_at:
            _fail(PolicyReindexFailureCode.PARITY_STALE)
        if (
            row.state != owner.state
            or row.state_version != owner.state_version
            or row.next_document_index != owner.next_document_index
        ):
            _fail(PolicyReindexFailureCode.CAS_CONFLICT)
        if not allow_terminal and row.state in POLICY_REINDEX_TERMINAL_STATES:
            _fail(PolicyReindexFailureCode.STATE_MISMATCH)
        if (
            row.source_manifest_revision_id != owner.source_manifest_revision_id
            or row.source_manifest_hash != owner.source_manifest_hash
        ):
            _fail(PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT)
        if (
            row.source_active_corpus_version_id != owner.source_active_corpus_version_id
            or row.source_rollout_epoch != owner.source_rollout_epoch
            or row.expected_evidence_rollout_version != owner.expected_evidence_rollout_version
        ):
            _fail(PolicyReindexFailureCode.SOURCE_POINTER_DRIFT)
        if (
            manifest.id != owner.source_manifest_revision_id
            or manifest.revision != owner.source_manifest_revision
            or manifest.manifest_hash != owner.source_manifest_hash
        ):
            await self._mark_source_stale(row, owner=owner, now=now, code="source_manifest_drift")
            _fail(PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT)
        if (
            rollout.active_corpus_version_id != owner.source_active_corpus_version_id
            or rollout.rollout_epoch != owner.source_rollout_epoch
        ):
            await self._mark_source_stale(row, owner=owner, now=now, code="source_pointer_drift")
            _fail(PolicyReindexFailureCode.SOURCE_POINTER_DRIFT)
        if _ordered_doc_keys(manifest) != owner.ordered_doc_keys:
            await self._mark_source_stale(row, owner=owner, now=now, code="source_manifest_drift")
            _fail(PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT)
        return row, manifest

    async def _mark_source_stale(
        self,
        row: PolicyCorpusVersion,
        *,
        owner: PolicyReindexRunIdentity,
        now: datetime,
        code: str,
    ) -> None:
        updated = await self.corpora.cas_candidate(
            row,
            expected_state_version=owner.state_version,
            expected_next_document_index=owner.next_document_index,
            values={
                "state": "source_stale",
                "failure_code": code,
                "safe_message": "candidate source authority changed",
                "terminal_at": now,
            },
        )
        if updated is None:
            _fail(PolicyReindexFailureCode.CAS_CONFLICT)

    @staticmethod
    def _validate_claim(
        request: PolicyReindexClaimRequest,
        *,
        now: datetime,
        parity_maximum_age: timedelta,
    ) -> datetime:
        try:
            captured_at = _as_utc(request.parity.captured_at)
            lease_expires_at = _as_utc(request.lease_expires_at)
        except (TypeError, ValueError):
            _fail(PolicyReindexFailureCode.INVALID_CLAIM)
        if (
            request.tenant_id.int == 0
            or request.run_token.int == 0
            or request.source_manifest_revision_id.int == 0
            or request.source_active_corpus_version_id.int == 0
            or not request.generation_name.strip()
            or len(request.generation_name) > 128
            or not request.lease_owner.strip()
            or len(request.lease_owner) > 128
            or not request.config_schema_version.strip()
            or request.source_manifest_revision <= 0
            or request.source_rollout_epoch <= 0
            or request.expected_evidence_rollout_version < 0
            or not _valid_sha256(request.config_fingerprint)
            or not _valid_sha256(request.source_manifest_hash)
            or not _valid_sha256(request.parity.report_hash)
            or request.parity.config_fingerprint != request.config_fingerprint
            or request.parity.status != "passed"
            or parity_maximum_age <= timedelta(0)
            or captured_at > now
            or now - captured_at > parity_maximum_age
            or lease_expires_at <= now
        ):
            _fail(PolicyReindexFailureCode.INVALID_CLAIM)
        return captured_at + parity_maximum_age

    @staticmethod
    def _assert_requested_source_authority(
        request: PolicyReindexClaimRequest,
        *,
        manifest: PolicyCorpusManifestRevision,
        rollout: Any,
    ) -> None:
        if (
            manifest.id != request.source_manifest_revision_id
            or manifest.revision != request.source_manifest_revision
            or manifest.manifest_hash != request.source_manifest_hash
        ):
            _fail(PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT)
        if (
            rollout.active_corpus_version_id != request.source_active_corpus_version_id
            or rollout.rollout_epoch != request.source_rollout_epoch
        ):
            _fail(PolicyReindexFailureCode.SOURCE_POINTER_DRIFT)

    @staticmethod
    def _assert_claim_matches(
        request: PolicyReindexClaimRequest,
        owner: PolicyReindexRunIdentity,
    ) -> None:
        if (
            request.generation_name != owner.generation_name
            or request.lease_owner != owner.lease_owner
            or _as_utc(request.lease_expires_at) != owner.lease_expires_at
            or request.source_manifest_revision_id != owner.source_manifest_revision_id
            or request.source_manifest_revision != owner.source_manifest_revision
            or request.source_manifest_hash != owner.source_manifest_hash
            or request.source_active_corpus_version_id != owner.source_active_corpus_version_id
            or request.source_rollout_epoch != owner.source_rollout_epoch
            or request.expected_evidence_rollout_version != owner.expected_evidence_rollout_version
        ):
            _fail(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH)
        if (
            request.config_schema_version != owner.config_schema_version
            or request.config_fingerprint != owner.config_fingerprint
        ):
            _fail(PolicyReindexFailureCode.CONFIG_DRIFT)
        if request.parity.report_hash != owner.provider_parity_report_hash:
            _fail(PolicyReindexFailureCode.PARITY_DRIFT)

    @staticmethod
    def _identity_from_row(
        row: PolicyCorpusVersion,
        *,
        manifest: PolicyCorpusManifestRevision,
    ) -> PolicyReindexRunIdentity:
        claim = row.validation_proof_json.get("claim") if isinstance(row.validation_proof_json, dict) else None
        if not isinstance(claim, dict):
            _fail(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH)
        ordered_doc_keys = claim.get("ordered_doc_keys")
        try:
            identity = PolicyReindexRunIdentity(
                corpus_version_id=row.id,
                tenant_id=row.tenant_id,
                run_token=_required_uuid(row.run_token),
                generation_name=row.generation_name,
                lease_owner=_required_string(row.lease_owner),
                lease_expires_at=_as_utc(_required_datetime(row.lease_expires_at)),
                state=row.state,
                state_version=row.state_version,
                next_document_index=row.next_document_index,
                ordered_doc_keys=tuple(_required_string(item) for item in ordered_doc_keys),
                config_schema_version=row.config_schema_version,
                config_fingerprint=row.config_fingerprint,
                provider_parity_report_hash=_required_string(row.provider_parity_report_hash),
                source_manifest_revision_id=row.source_manifest_revision_id,
                source_manifest_revision=int(claim["source_manifest_revision"]),
                source_manifest_hash=row.source_manifest_hash,
                source_active_corpus_version_id=_required_uuid(row.source_active_corpus_version_id),
                source_rollout_epoch=int(row.source_rollout_epoch),
                expected_evidence_rollout_version=int(row.expected_evidence_rollout_version),
                parity_captured_at=_as_utc(datetime.fromisoformat(_required_string(claim["parity_captured_at"]))),
                parity_expires_at=_as_utc(datetime.fromisoformat(_required_string(claim["parity_expires_at"]))),
            )
        except (KeyError, TypeError, ValueError):
            _fail(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH)
        if (
            row.owner_marker != POLICY_REINDEX_OWNER_MARKER
            or row.state not in POLICY_REINDEX_STATES
            or identity.source_manifest_revision_id != manifest.id
            or identity.source_manifest_revision != manifest.revision
            or identity.ordered_doc_keys != _ordered_doc_keys(manifest)
            or not 0 <= identity.next_document_index <= len(identity.ordered_doc_keys)
        ):
            _fail(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH)
        return identity


def _ordered_doc_keys(manifest: PolicyCorpusManifestRevision) -> tuple[str, ...]:
    payload = manifest.manifest_json
    documents = payload.get("documents") if isinstance(payload, dict) else None
    if not isinstance(documents, list) or len(documents) != manifest.document_count:
        _fail(PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT)
    doc_keys: list[str] = []
    for document in documents:
        if not isinstance(document, dict):
            _fail(PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT)
        doc_key = document.get("doc_key")
        if not isinstance(doc_key, str) or not doc_key.strip():
            _fail(PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT)
        doc_keys.append(doc_key)
    if len(doc_keys) != len(set(doc_keys)):
        _fail(PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT)
    return tuple(doc_keys)


def _as_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timezone-aware datetime required")
    return value.astimezone(UTC)


def _required_datetime(value: datetime | None) -> datetime:
    if value is None:
        raise ValueError("datetime required")
    return value


def _required_string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("string required")
    return value


def _required_uuid(value: UUID | None) -> UUID:
    if value is None:
        raise ValueError("uuid required")
    return value


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _fail(code: PolicyReindexFailureCode) -> None:
    raise PolicyReindexError(code)
