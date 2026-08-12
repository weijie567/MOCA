"""Tenant/run-scoped inactive policy corpus build lifecycle.

The rollout pointer is the only current authority. This service claims,
resumes, validates, or fails inactive candidates and exposes Plan 08's
fixture-authorized pointer CAS. It never reparses source files or produces a
real selection decision.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import math
import re
from typing import TYPE_CHECKING, Any, Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    CorpusBlockBinding,
    CorpusChunkBinding,
    CorpusDocumentBinding,
    PolicyChunk,
    PolicyChunkVersion,
    PolicyCorpusManifestRevision,
    PolicyCorpusVersion,
    PolicyDocument,
)
from src.rag.ingestion import _policy_chunks_from_embedding_inputs
from src.rag.policy_embedding_input import PolicyEmbeddingInputV1
from src.repositories.document_block_repo import (
    AuthoritativePolicyDocumentSnapshotV1,
    AuthoritativeSourceSnapshotError,
    DocumentBlockRepository,
)
from src.repositories.evidence_version_repo import (
    EvidenceRolloutError,
    EvidenceVersionRepository,
    canonical_chunk_version_matches_projection,
)
from src.repositories.policy_corpus_repo import (
    PolicyCorpusActivationView,
    PolicyCorpusRepository,
    PolicyCorpusUnavailable,
)

if TYPE_CHECKING:
    from src.rag.policy_reindex_artifacts import PolicyReindexRecoveryDescriptorV1


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
    SOURCE_SNAPSHOT_DRIFT = "source_snapshot_drift"
    CANDIDATE_PROJECTION_MISMATCH = "candidate_projection_mismatch"
    EMBEDDING_PROOF_FAILED = "embedding_proof_failed"
    SELECTION_PROOF_INVALID = "selection_proof_invalid"
    OBSOLETE_SOURCE = "obsolete_source"


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
    recovery_descriptor_payload_sha256: str | None = None
    parity_probe_fixture_sha256: str | None = None
    parity_submitted_content_sha256: str | None = None


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


@dataclass(frozen=True, slots=True)
class PolicyCandidateBuildPreparation:
    document_index: int
    doc_key: str
    state_version: int
    expected_input_count: int
    expected_batch_count: int


class PolicyCorpusActivationReason(StrEnum):
    SELECTED_CUTOVER = "selected_cutover"
    ROLLBACK_PRIOR = "rollback_prior"
    RESTORE_SELECTED = "restore_selected"


@dataclass(frozen=True, slots=True)
class ImmutableSelectionDecisionFixtureV1:
    """Plan08-only immutable contract fixture; Plan09 owns real artifacts."""

    schema_version: str
    selection_decision_sha256: str
    outcome: str
    tenant_id: UUID
    candidate_corpus_version_id: UUID
    run_token: UUID
    lease_owner: str
    config_fingerprint: str
    provider_parity_report_hash: str
    source_manifest_hash: str
    expected_evidence_rollout_version: int


@dataclass(frozen=True, slots=True)
class ImmutableSelectionDecisionV1:
    """Strict in-memory projection of a real Plan09 selection artifact."""

    schema_version: Literal["rag_token_chunk_selection.v1"]
    selection_decision_sha256: str
    outcome: Literal["selected_pass"]
    tenant_id: UUID
    candidate_corpus_version_id: UUID
    run_token: UUID
    lease_owner: str
    config_fingerprint: str
    provider_parity_report_hash: str
    source_manifest_hash: str
    expected_evidence_rollout_version: int
    recovery_authorization_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class PolicyCorpusActivationRequest:
    tenant_id: UUID
    target_corpus_version_id: UUID
    expected_active_corpus_version_id: UUID
    expected_rollout_epoch: int
    expected_evidence_rollout_version: int
    actor: str
    reason: PolicyCorpusActivationReason
    selection: ImmutableSelectionDecisionFixtureV1 | ImmutableSelectionDecisionV1 | None


class PolicyCandidateEmbedder(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class PolicyReindexService:
    """Claim and advance exactly one inactive candidate under tenant locks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.corpora = PolicyCorpusRepository(session)
        self.blocks = DocumentBlockRepository(session)
        self.evidence = EvidenceVersionRepository(session)

    async def activate_corpus(
        self,
        request: PolicyCorpusActivationRequest,
        *,
        now: datetime | None = None,
    ) -> PolicyCorpusActivationView:
        """CAS the sole pointer from a complete Plan08 fixture-authorized target."""

        _ = _as_utc(now or datetime.now(UTC))
        self._validate_activation_request(request)
        try:
            await self.evidence.lock_rollout(
                expected_rollout_version=request.expected_evidence_rollout_version,
                require_dual_write=True,
            )
            rollout = await self.corpora.acquire_tenant_rollout_lock(tenant_id=request.tenant_id)
            manifest = await self.corpora.lock_latest_manifest(tenant_id=request.tenant_id)
        except EvidenceRolloutError:
            _fail(PolicyReindexFailureCode.CAS_CONFLICT)
        except PolicyCorpusUnavailable:
            _fail(PolicyReindexFailureCode.AUTHORITY_UNAVAILABLE)
        if (
            rollout.active_corpus_version_id != request.expected_active_corpus_version_id
            or rollout.rollout_epoch != request.expected_rollout_epoch
        ):
            _fail(PolicyReindexFailureCode.CAS_CONFLICT)
        target = await self.corpora.get_corpus(
            tenant_id=request.tenant_id,
            corpus_version_id=request.target_corpus_version_id,
        )
        if target is None:
            _fail(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH)
        if target.state != "complete":
            _fail(PolicyReindexFailureCode.OBSOLETE_SOURCE)
        if target.source_manifest_revision_id != manifest.id or target.source_manifest_hash != manifest.manifest_hash:
            _fail(PolicyReindexFailureCode.OBSOLETE_SOURCE)

        selection_hash: str | None = None
        if request.reason is PolicyCorpusActivationReason.ROLLBACK_PRIOR:
            if request.selection is not None:
                _fail(PolicyReindexFailureCode.SELECTION_PROOF_INVALID)
            if rollout.previous_corpus_version_id != target.id:
                _fail(PolicyReindexFailureCode.CAS_CONFLICT)
        else:
            if request.reason is PolicyCorpusActivationReason.RESTORE_SELECTED:
                if rollout.previous_corpus_version_id != target.id:
                    _fail(PolicyReindexFailureCode.CAS_CONFLICT)
            self._validate_selection_proof(
                request,
                target=target,
                manifest=manifest,
                require_current_source_epoch=request.reason is PolicyCorpusActivationReason.SELECTED_CUTOVER,
            )
            await self._require_complete_candidate_projection(target)
            assert request.selection is not None
            selection_hash = request.selection.selection_decision_sha256

        activated = await self.corpora.activate_rollout_cas(
            rollout,
            expected_active_corpus_version_id=request.expected_active_corpus_version_id,
            expected_rollout_epoch=request.expected_rollout_epoch,
            target_corpus_version_id=request.target_corpus_version_id,
            reason_code=request.reason.value,
            actor=request.actor.strip(),
            selection_decision_hash=selection_hash,
        )
        if activated is None:
            _fail(PolicyReindexFailureCode.CAS_CONFLICT)
        return activated

    async def cleanup_candidate(
        self,
        owner: PolicyReindexRunIdentity,
        *,
        actor: str,
        now: datetime | None = None,
    ) -> PolicyReindexRunIdentity:
        """Logically terminate one exact candidate without deleting retained rows."""

        checked_at = _as_utc(now or datetime.now(UTC))
        if not actor.strip() or len(actor.strip()) > 128:
            _fail(PolicyReindexFailureCode.INVALID_CLAIM)
        row, manifest = await self._lock_validated(owner, now=checked_at, allow_terminal=False)
        if row.state not in {"claimed", "building", "built", "validating"}:
            _fail(PolicyReindexFailureCode.STATE_MISMATCH)
        proof = dict(row.validation_proof_json or {})
        proof["cleanup"] = {
            "schema_version": "policy_candidate_cleanup.v1",
            "actor": actor.strip(),
            "retention": "all_projection_and_immutable_rows_retained",
        }
        updated = await self.corpora.cas_candidate(
            row,
            expected_state_version=owner.state_version,
            expected_next_document_index=owner.next_document_index,
            values={
                "state": "failed",
                "validation_proof_json": proof,
                "failure_code": "operator_cleanup",
                "safe_message": "candidate logically cleaned with retained evidence",
                "terminal_at": checked_at,
            },
        )
        if updated is None:
            _fail(PolicyReindexFailureCode.CAS_CONFLICT)
        return self._identity_from_row(updated, manifest=manifest)

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
            self._assert_recovery_request_binding(existing, request)
            if owner.lease_expires_at <= checked_at:
                _fail(PolicyReindexFailureCode.LEASE_EXPIRED)
            return owner

        validation_proof: dict[str, Any] = {
            "claim": {
                "schema_version": POLICY_REINDEX_CLAIM_SCHEMA_VERSION,
                "ordered_doc_keys": list(ordered_doc_keys),
                "source_manifest_revision": manifest.revision,
                "parity_captured_at": _as_utc(request.parity.captured_at).isoformat(),
                "parity_expires_at": parity_expires_at.isoformat(),
            }
        }
        if request.recovery_descriptor_payload_sha256 is not None:
            validation_proof["recovery_descriptor"] = {
                "schema_version": "policy_reindex_recovery_descriptor_binding.v1",
                "descriptor_payload_sha256": request.recovery_descriptor_payload_sha256,
                "parity_probe_fixture_sha256": request.parity_probe_fixture_sha256,
                "parity_submitted_content_sha256": request.parity_submitted_content_sha256,
            }

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
            validation_proof_json=validation_proof,
            failure_code=None,
            safe_message=None,
            terminal_at=None,
        )
        self.session.add(candidate)
        await self.session.flush()
        return self._identity_from_row(candidate, manifest=manifest)

    async def claim_from_descriptor(
        self,
        descriptor: PolicyReindexRecoveryDescriptorV1,
        *,
        now: datetime | None = None,
    ) -> PolicyReindexRunIdentity:
        """Claim only the UUID, lease, parity, config, and source sealed pre-claim."""

        parity_maximum_age = descriptor.parity_expires_at - descriptor.parity_captured_at
        try:
            await self.evidence.lock_rollout(
                expected_rollout_version=descriptor.expected_evidence_rollout_version,
                require_dual_write=True,
            )
        except EvidenceRolloutError:
            _fail(PolicyReindexFailureCode.SOURCE_POINTER_DRIFT)
        owner = await self.claim(
            self._claim_request_from_descriptor(descriptor),
            now=now,
            parity_maximum_age=parity_maximum_age,
        )
        row = await self.corpora.lock_candidate(corpus_version_id=owner.corpus_version_id)
        if row is None or dict(row.config_json or {}) != descriptor.config_json:
            _fail(PolicyReindexFailureCode.CONFIG_DRIFT)
        return owner

    async def recover_identity(
        self,
        descriptor: PolicyReindexRecoveryDescriptorV1,
        *,
        now: datetime | None = None,
    ) -> PolicyReindexRunIdentity:
        """Recover one exact current row without renewal, transition, or creation."""

        checked_at = _as_utc(now or datetime.now(UTC))
        if checked_at >= _as_utc(descriptor.lease_expires_at):
            _fail(PolicyReindexFailureCode.LEASE_EXPIRED)
        if checked_at >= _as_utc(descriptor.parity_expires_at):
            _fail(PolicyReindexFailureCode.PARITY_STALE)
        try:
            await self.evidence.lock_rollout(
                expected_rollout_version=descriptor.expected_evidence_rollout_version,
                require_dual_write=True,
            )
            rollout = await self.corpora.acquire_tenant_rollout_lock(tenant_id=descriptor.tenant_id)
            manifest = await self.corpora.lock_latest_manifest(tenant_id=descriptor.tenant_id)
            row = await self.corpora.get_candidate_by_run(
                tenant_id=descriptor.tenant_id,
                run_token=descriptor.run_token,
            )
        except EvidenceRolloutError:
            _fail(PolicyReindexFailureCode.SOURCE_POINTER_DRIFT)
        except PolicyCorpusUnavailable:
            _fail(PolicyReindexFailureCode.AUTHORITY_UNAVAILABLE)
        if row is None:
            _fail(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH)
        request = self._claim_request_from_descriptor(descriptor)
        self._assert_requested_source_authority(request, manifest=manifest, rollout=rollout)
        owner = self._identity_from_row(row, manifest=manifest)
        self._assert_claim_matches(request, owner)
        self._assert_recovery_request_binding(row, request)
        if dict(row.config_json or {}) != descriptor.config_json:
            _fail(PolicyReindexFailureCode.CONFIG_DRIFT)
        return owner

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
        bootstrap_counts: dict[str, int] | None = None,
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
        values: dict[str, Any] = {
            "state": state,
            "next_document_index": next_index,
            "safe_message": "candidate document checkpoint committed",
        }
        if bootstrap_counts is not None:
            values["bootstrap_counts_json"] = dict(bootstrap_counts)
        updated = await self.corpora.cas_candidate(
            row,
            expected_state_version=owner.state_version,
            expected_next_document_index=owner.next_document_index,
            values=values,
        )
        if updated is None:
            _fail(PolicyReindexFailureCode.CAS_CONFLICT)
        return self._identity_from_row(updated, manifest=manifest)

    async def build_next_document(
        self,
        owner: PolicyReindexRunIdentity,
        *,
        assembler: Any,
        embedder: PolicyCandidateEmbedder,
        now: datetime | None = None,
    ) -> PolicyReindexRunIdentity:
        """Build and checkpoint one document without committing or changing current authority."""

        checked_at = _as_utc(now or datetime.now(UTC))
        row, manifest = await self._lock_validated(owner, now=checked_at)
        if row.state != "building" or owner.next_document_index >= len(owner.ordered_doc_keys):
            _fail(PolicyReindexFailureCode.STATE_MISMATCH)
        if _assembler_fingerprint(assembler) != owner.config_fingerprint:
            _fail(PolicyReindexFailureCode.CONFIG_DRIFT)
        doc_key = owner.ordered_doc_keys[owner.next_document_index]
        manifest_document = _manifest_document(manifest, doc_key=doc_key)
        snapshot = await self._load_snapshot(owner, manifest_document=manifest_document)
        await self._assert_candidate_document_absent(owner, snapshot=snapshot)
        assembled = assembler.assemble(
            blocks=snapshot.blocks,
            doc_key=snapshot.doc_key,
            title=snapshot.title,
            doc_type=snapshot.doc_type,
            risk_level=snapshot.risk_level,
        )
        if not assembled:
            _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)
        self._verify_assembled_inputs(owner, assembler=assembler, assembled=assembled)
        embeddings = await embedder.embed_documents([item.embedding_input for item in assembled])
        self._verify_embeddings(
            embeddings,
            expected_count=len(assembled),
            expected_dimensions=_assembler_dimensions(assembler),
        )

        document = await self.session.get(PolicyDocument, snapshot.policy_document_id)
        if document is None or document.tenant_id != owner.tenant_id:
            _fail(PolicyReindexFailureCode.SOURCE_SNAPSHOT_DRIFT)
        chunks = _policy_chunks_from_embedding_inputs(
            tenant_id=owner.tenant_id,
            doc_id=document.id,
            title=snapshot.title,
            doc_type=snapshot.doc_type,
            risk_level=snapshot.risk_level,
            effective_date=snapshot.effective_date,
            assembled_inputs=assembled,
            embeddings=embeddings,
        )
        self.session.add_all(chunks)
        await self.session.flush()
        immutable_document, immutable_chunks = await self.evidence.append_immutable_version(
            tenant_id=owner.tenant_id,
            document=document,
            chunks=chunks,
            write_sequence=0,
            canonical_source=snapshot.canonical_source,
            project_current_head=False,
        )
        if immutable_document.id != snapshot.policy_document_version_id:
            _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)
        self.session.add(
            CorpusDocumentBinding(
                tenant_id=owner.tenant_id,
                corpus_version_id=owner.corpus_version_id,
                policy_document_id=document.id,
                policy_document_version_id=immutable_document.id,
            )
        )
        self.session.add_all(
            [
                CorpusBlockBinding(
                    tenant_id=owner.tenant_id,
                    corpus_version_id=owner.corpus_version_id,
                    document_block_id=block_id,
                    policy_document_version_id=immutable_document.id,
                )
                for block_id in snapshot.block_ids
            ]
        )
        self.session.add_all(
            [
                CorpusChunkBinding(
                    tenant_id=owner.tenant_id,
                    corpus_version_id=owner.corpus_version_id,
                    policy_chunk_id=chunk.id,
                    policy_chunk_version_id=immutable.id,
                )
                for chunk, immutable in zip(chunks, immutable_chunks, strict=True)
            ]
        )
        await self.session.flush()
        try:
            await self.blocks.recheck_authoritative_snapshot(snapshot, manifest_document=manifest_document)
        except AuthoritativeSourceSnapshotError:
            _fail(PolicyReindexFailureCode.SOURCE_SNAPSHOT_DRIFT)
        self._verify_persisted_projection(
            owner,
            snapshot=snapshot,
            assembled=assembled,
            chunks=chunks,
            immutable_chunks=immutable_chunks,
        )
        counts = await self._candidate_counts(owner)
        return await self.checkpoint_document(
            owner,
            doc_key=doc_key,
            now=checked_at,
            bootstrap_counts=counts,
        )

    async def prepare_candidate_build(
        self,
        owner: PolicyReindexRunIdentity,
        *,
        assembler: Any,
        provider_batch_size: int,
        now: datetime | None = None,
    ) -> PolicyCandidateBuildPreparation:
        """Fix one document's input and provider-batch counts without provider access."""

        checked_at = _as_utc(now or datetime.now(UTC))
        row, manifest = await self._lock_validated(owner, now=checked_at)
        if row.state != "building" or owner.next_document_index >= len(owner.ordered_doc_keys):
            _fail(PolicyReindexFailureCode.STATE_MISMATCH)
        if _assembler_fingerprint(assembler) != owner.config_fingerprint:
            _fail(PolicyReindexFailureCode.CONFIG_DRIFT)
        runtime_config = _assembler_runtime_config(assembler)
        if (
            type(provider_batch_size) is not int
            or provider_batch_size <= 0
            or provider_batch_size > int(runtime_config.provider_max_batch_inputs)
        ):
            _fail(PolicyReindexFailureCode.CONFIG_DRIFT)
        document_index = owner.next_document_index
        doc_key = owner.ordered_doc_keys[document_index]
        manifest_document = _manifest_document(manifest, doc_key=doc_key)
        snapshot = await self._load_snapshot(owner, manifest_document=manifest_document)
        await self._assert_candidate_document_absent(owner, snapshot=snapshot)
        assembled = assembler.assemble(
            blocks=snapshot.blocks,
            doc_key=snapshot.doc_key,
            title=snapshot.title,
            doc_type=snapshot.doc_type,
            risk_level=snapshot.risk_level,
        )
        if not assembled:
            _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)
        self._verify_assembled_inputs(owner, assembler=assembler, assembled=assembled)
        return PolicyCandidateBuildPreparation(
            document_index=document_index,
            doc_key=doc_key,
            state_version=owner.state_version,
            expected_input_count=len(assembled),
            expected_batch_count=math.ceil(len(assembled) / provider_batch_size),
        )

    async def validate_candidate(
        self,
        owner: PolicyReindexRunIdentity,
        *,
        assembler: Any,
        now: datetime | None = None,
    ) -> PolicyReindexRunIdentity:
        """Rebuild audit material from source snapshots and seal completion proofs."""

        checked_at = _as_utc(now or datetime.now(UTC))
        if _assembler_fingerprint(assembler) != owner.config_fingerprint:
            _fail(PolicyReindexFailureCode.CONFIG_DRIFT)
        validating = await self.transition(owner, state="validating", now=checked_at)
        row, manifest = await self._lock_validated(validating, now=checked_at)
        replay_payload: list[dict[str, Any]] = []
        expected_block_count = 0
        expected_chunk_count = 0
        for doc_key in validating.ordered_doc_keys:
            manifest_document = _manifest_document(manifest, doc_key=doc_key)
            snapshot = await self._load_snapshot(validating, manifest_document=manifest_document)
            expected_block_count += len(snapshot.blocks)
            assembled = assembler.assemble(
                blocks=snapshot.blocks,
                doc_key=snapshot.doc_key,
                title=snapshot.title,
                doc_type=snapshot.doc_type,
                risk_level=snapshot.risk_level,
            )
            self._verify_assembled_inputs(validating, assembler=assembler, assembled=assembled)
            expected_chunk_count += len(assembled)
            projection_rows = list(
                (
                    await self.session.execute(
                        select(PolicyChunk, PolicyChunkVersion)
                        .join(
                            CorpusChunkBinding,
                            (CorpusChunkBinding.tenant_id == validating.tenant_id)
                            & (CorpusChunkBinding.corpus_version_id == validating.corpus_version_id)
                            & (CorpusChunkBinding.policy_chunk_id == PolicyChunk.id),
                        )
                        .join(
                            PolicyChunkVersion,
                            (PolicyChunkVersion.tenant_id == validating.tenant_id)
                            & (PolicyChunkVersion.id == CorpusChunkBinding.policy_chunk_version_id),
                        )
                        .where(
                            PolicyChunk.tenant_id == validating.tenant_id,
                            PolicyChunk.doc_id == snapshot.policy_document_id,
                        )
                        .order_by(PolicyChunk.chunk_id)
                    )
                ).all()
            )
            if len(projection_rows) != len(assembled):
                _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)
            for dto, (chunk, immutable_chunk) in zip(assembled, projection_rows, strict=True):
                if not _projection_matches_dto(chunk, dto) or not canonical_chunk_version_matches_projection(
                    immutable_chunk, chunk
                ):
                    _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)
                replay_payload.append(
                    {
                        "snapshot_hash": snapshot.snapshot_hash,
                        "chunk_id": chunk.chunk_id,
                        "embedding_input_hash": chunk.embedding_input_hash,
                        "embedding_token_count": chunk.embedding_token_count,
                    }
                )
        counts = await self._candidate_counts(validating)
        expected_counts = {
            "bound_document_count": len(validating.ordered_doc_keys),
            "bound_block_count": expected_block_count,
            "bound_chunk_count": expected_chunk_count,
        }
        if counts != expected_counts:
            _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)
        rebuild_hash = _sha256_json({"schema_version": "policy_candidate_rebuild.v1", "documents": replay_payload})
        proof = {
            "complete_document_coverage": True,
            "complete_block_coverage": True,
            "immutable_binding_replay": True,
            "all_embedding_inputs_within_512_tokens": True,
            "deterministic_rebuild_hash": rebuild_hash,
            "config_fingerprint": validating.config_fingerprint,
            "provider_parity_report_hash": validating.provider_parity_report_hash,
            "source_manifest_hash": validating.source_manifest_hash,
            "source_active_corpus_version_id": str(validating.source_active_corpus_version_id),
            "source_rollout_epoch": validating.source_rollout_epoch,
            "no_mixed_source": True,
        }
        merged_proof = dict(row.validation_proof_json or {})
        merged_proof["candidate_validation"] = proof
        updated = await self.corpora.cas_candidate(
            row,
            expected_state_version=validating.state_version,
            expected_next_document_index=validating.next_document_index,
            values={
                "state": "complete",
                "bootstrap_counts_json": counts,
                "validation_proof_json": merged_proof,
                "deterministic_rebuild_hash": rebuild_hash,
                "safe_message": "candidate validation complete",
                "terminal_at": checked_at,
            },
        )
        if updated is None:
            _fail(PolicyReindexFailureCode.CAS_CONFLICT)
        return self._identity_from_row(updated, manifest=manifest)

    async def _load_snapshot(
        self,
        owner: PolicyReindexRunIdentity,
        *,
        manifest_document: dict[str, Any],
    ) -> AuthoritativePolicyDocumentSnapshotV1:
        try:
            return await self.blocks.load_authoritative_snapshot(
                tenant_id=owner.tenant_id,
                source_corpus_version_id=owner.source_active_corpus_version_id,
                manifest_document=manifest_document,
            )
        except AuthoritativeSourceSnapshotError:
            _fail(PolicyReindexFailureCode.SOURCE_SNAPSHOT_DRIFT)

    async def _assert_candidate_document_absent(
        self,
        owner: PolicyReindexRunIdentity,
        *,
        snapshot: AuthoritativePolicyDocumentSnapshotV1,
    ) -> None:
        count = await self.session.scalar(
            select(func.count())
            .select_from(CorpusDocumentBinding)
            .where(
                CorpusDocumentBinding.tenant_id == owner.tenant_id,
                CorpusDocumentBinding.corpus_version_id == owner.corpus_version_id,
                CorpusDocumentBinding.policy_document_id == snapshot.policy_document_id,
            )
        )
        if count:
            _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)

    @staticmethod
    def _verify_assembled_inputs(
        owner: PolicyReindexRunIdentity,
        *,
        assembler: Any,
        assembled: tuple[PolicyEmbeddingInputV1, ...],
    ) -> None:
        for item in assembled:
            if (
                item.chunking_config_fingerprint != owner.config_fingerprint
                or item.embedding_input_hash != _sha256_text(item.embedding_input)
                or item.embedding_token_count != assembler.counter.count(item.embedding_input)
                or item.embedding_token_count > _assembler_max_embedding_tokens(assembler)
            ):
                _fail(PolicyReindexFailureCode.EMBEDDING_PROOF_FAILED)

    @staticmethod
    def _verify_embeddings(
        embeddings: list[list[float]],
        *,
        expected_count: int,
        expected_dimensions: int,
    ) -> None:
        if len(embeddings) != expected_count or any(
            len(vector) != expected_dimensions
            or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector)
            for vector in embeddings
        ):
            _fail(PolicyReindexFailureCode.EMBEDDING_PROOF_FAILED)

    @staticmethod
    def _verify_persisted_projection(
        owner: PolicyReindexRunIdentity,
        *,
        snapshot: AuthoritativePolicyDocumentSnapshotV1,
        assembled: tuple[PolicyEmbeddingInputV1, ...],
        chunks: list[PolicyChunk],
        immutable_chunks: list[PolicyChunkVersion],
    ) -> None:
        if len(chunks) != len(assembled) or len(immutable_chunks) != len(assembled):
            _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)
        for dto, chunk, immutable in zip(assembled, chunks, immutable_chunks, strict=True):
            if (
                chunk.tenant_id != owner.tenant_id
                or chunk.doc_id != snapshot.policy_document_id
                or not _projection_matches_dto(chunk, dto)
                or not canonical_chunk_version_matches_projection(immutable, chunk)
            ):
                _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)

    async def _candidate_counts(self, owner: PolicyReindexRunIdentity) -> dict[str, int]:
        document_count = await self.session.scalar(
            select(func.count())
            .select_from(CorpusDocumentBinding)
            .where(
                CorpusDocumentBinding.tenant_id == owner.tenant_id,
                CorpusDocumentBinding.corpus_version_id == owner.corpus_version_id,
            )
        )
        block_count = await self.session.scalar(
            select(func.count())
            .select_from(CorpusBlockBinding)
            .where(
                CorpusBlockBinding.tenant_id == owner.tenant_id,
                CorpusBlockBinding.corpus_version_id == owner.corpus_version_id,
            )
        )
        chunk_count = await self.session.scalar(
            select(func.count())
            .select_from(CorpusChunkBinding)
            .where(
                CorpusChunkBinding.tenant_id == owner.tenant_id,
                CorpusChunkBinding.corpus_version_id == owner.corpus_version_id,
            )
        )
        return {
            "bound_document_count": int(document_count or 0),
            "bound_block_count": int(block_count or 0),
            "bound_chunk_count": int(chunk_count or 0),
        }

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
    def _validate_activation_request(request: PolicyCorpusActivationRequest) -> None:
        actor = request.actor.strip()
        if (
            request.tenant_id.int == 0
            or request.target_corpus_version_id.int == 0
            or request.expected_active_corpus_version_id.int == 0
            or request.target_corpus_version_id == request.expected_active_corpus_version_id
            or request.expected_rollout_epoch <= 0
            or request.expected_evidence_rollout_version < 0
            or not actor
            or len(actor) > 128
            or not isinstance(request.reason, PolicyCorpusActivationReason)
        ):
            _fail(PolicyReindexFailureCode.INVALID_CLAIM)

    @staticmethod
    def _validate_selection_proof(
        request: PolicyCorpusActivationRequest,
        *,
        target: PolicyCorpusVersion,
        manifest: PolicyCorpusManifestRevision,
        require_current_source_epoch: bool,
    ) -> None:
        selection = request.selection
        if (
            selection is None
            or selection.schema_version not in {"rag_token_chunk_selection_fixture.v1", "rag_token_chunk_selection.v1"}
            or selection.outcome != "selected_pass"
            or not _valid_sha256(selection.selection_decision_sha256)
            or selection.tenant_id != request.tenant_id
            or selection.candidate_corpus_version_id != target.id
            or selection.run_token != target.run_token
            or selection.lease_owner != target.lease_owner
            or selection.config_fingerprint != target.config_fingerprint
            or selection.provider_parity_report_hash != target.provider_parity_report_hash
            or selection.source_manifest_hash != target.source_manifest_hash
            or selection.source_manifest_hash != manifest.manifest_hash
            or selection.expected_evidence_rollout_version != request.expected_evidence_rollout_version
            or selection.expected_evidence_rollout_version != target.expected_evidence_rollout_version
            or target.owner_marker != POLICY_REINDEX_OWNER_MARKER
            or target.run_token is None
            or target.lease_owner is None
        ):
            _fail(PolicyReindexFailureCode.SELECTION_PROOF_INVALID)
        if isinstance(selection, ImmutableSelectionDecisionV1) and not _valid_sha256(
            selection.recovery_authorization_sha256
        ):
            _fail(PolicyReindexFailureCode.SELECTION_PROOF_INVALID)
        if require_current_source_epoch and (
            target.source_active_corpus_version_id != request.expected_active_corpus_version_id
            or target.source_rollout_epoch != request.expected_rollout_epoch
        ):
            _fail(PolicyReindexFailureCode.SOURCE_POINTER_DRIFT)

    async def _require_complete_candidate_projection(self, target: PolicyCorpusVersion) -> None:
        proof = (
            target.validation_proof_json.get("candidate_validation")
            if isinstance(target.validation_proof_json, dict)
            else None
        )
        if not isinstance(proof, dict):
            _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)
        required_truths = (
            "complete_document_coverage",
            "complete_block_coverage",
            "immutable_binding_replay",
            "all_embedding_inputs_within_512_tokens",
            "no_mixed_source",
        )
        if (
            any(proof.get(key) is not True for key in required_truths)
            or proof.get("deterministic_rebuild_hash") != target.deterministic_rebuild_hash
            or proof.get("config_fingerprint") != target.config_fingerprint
            or proof.get("provider_parity_report_hash") != target.provider_parity_report_hash
            or proof.get("source_manifest_hash") != target.source_manifest_hash
            or proof.get("source_active_corpus_version_id") != str(target.source_active_corpus_version_id)
            or proof.get("source_rollout_epoch") != target.source_rollout_epoch
        ):
            _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)
        counts = await self.corpora.get_projection_counts(
            tenant_id=target.tenant_id,
            corpus_version_id=target.id,
        )
        expected = dict(target.bootstrap_counts_json or {})
        if (
            counts.documents != expected.get("bound_document_count")
            or counts.blocks != expected.get("bound_block_count")
            or counts.chunks != expected.get("bound_chunk_count")
        ):
            _fail(PolicyReindexFailureCode.CANDIDATE_PROJECTION_MISMATCH)

    @staticmethod
    def _claim_request_from_descriptor(
        descriptor: PolicyReindexRecoveryDescriptorV1,
    ) -> PolicyReindexClaimRequest:
        return PolicyReindexClaimRequest(
            tenant_id=descriptor.tenant_id,
            run_token=descriptor.run_token,
            generation_name=descriptor.generation_name,
            lease_owner=descriptor.lease_owner,
            lease_expires_at=descriptor.lease_expires_at,
            config_schema_version=descriptor.config_schema_version,
            config_json=dict(descriptor.config_json),
            config_fingerprint=descriptor.config_fingerprint,
            parity=FreshProviderParityClaimV1(
                report_hash=descriptor.parity_report_sha256,
                config_fingerprint=descriptor.parity_config_fingerprint,
                captured_at=descriptor.parity_captured_at,
                status="passed",
            ),
            source_manifest_revision_id=descriptor.source_manifest_revision_id,
            source_manifest_revision=descriptor.source_manifest_revision,
            source_manifest_hash=descriptor.source_manifest_hash,
            source_active_corpus_version_id=descriptor.source_active_corpus_version_id,
            source_rollout_epoch=descriptor.source_rollout_epoch,
            expected_evidence_rollout_version=descriptor.expected_evidence_rollout_version,
            recovery_descriptor_payload_sha256=descriptor.descriptor_payload_sha256,
            parity_probe_fixture_sha256=descriptor.parity_probe_fixture_sha256,
            parity_submitted_content_sha256=descriptor.parity_submitted_content_sha256,
        )

    @staticmethod
    def _assert_recovery_request_binding(
        row: PolicyCorpusVersion,
        request: PolicyReindexClaimRequest,
    ) -> None:
        expected_values = (
            request.recovery_descriptor_payload_sha256,
            request.parity_probe_fixture_sha256,
            request.parity_submitted_content_sha256,
        )
        if all(value is None for value in expected_values):
            return
        binding = (
            row.validation_proof_json.get("recovery_descriptor")
            if isinstance(row.validation_proof_json, dict)
            else None
        )
        if binding != {
            "schema_version": "policy_reindex_recovery_descriptor_binding.v1",
            "descriptor_payload_sha256": request.recovery_descriptor_payload_sha256,
            "parity_probe_fixture_sha256": request.parity_probe_fixture_sha256,
            "parity_submitted_content_sha256": request.parity_submitted_content_sha256,
        }:
            _fail(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH)

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
        recovery_values = (
            request.recovery_descriptor_payload_sha256,
            request.parity_probe_fixture_sha256,
            request.parity_submitted_content_sha256,
        )
        if any(value is not None for value in recovery_values) and (
            any(not _valid_sha256(value) for value in recovery_values) or request.config_json == {}
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


def _manifest_document(manifest: PolicyCorpusManifestRevision, *, doc_key: str) -> dict[str, Any]:
    documents = manifest.manifest_json.get("documents") if isinstance(manifest.manifest_json, dict) else None
    if not isinstance(documents, list):
        _fail(PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT)
    matches = [document for document in documents if isinstance(document, dict) and document.get("doc_key") == doc_key]
    if len(matches) != 1:
        _fail(PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT)
    return dict(matches[0])


def _projection_matches_dto(chunk: PolicyChunk, dto: PolicyEmbeddingInputV1) -> bool:
    return bool(
        chunk.chunk_id == dto.chunk_id
        and chunk.section == dto.section
        and chunk.content == dto.citation_content
        and chunk.search_text == dto.search_text
        and list(chunk.source_block_refs_json or []) == [dict(ref) for ref in dto.source_block_refs]
        and chunk.chunking_config_fingerprint == dto.chunking_config_fingerprint
        and chunk.embedding_input_hash == dto.embedding_input_hash
        and chunk.embedding_token_count == dto.embedding_token_count
    )


def _assembler_fingerprint(assembler: Any) -> str:
    direct = getattr(assembler, "config_fingerprint", None)
    if isinstance(direct, str):
        return direct
    config = getattr(assembler, "config", None)
    fingerprint = getattr(config, "config_fingerprint", None)
    if not isinstance(fingerprint, str):
        _fail(PolicyReindexFailureCode.CONFIG_DRIFT)
    return fingerprint


def _assembler_runtime_config(assembler: Any) -> Any:
    config = getattr(assembler, "config", None)
    if config is not None:
        return config
    counter = getattr(assembler, "counter", None)
    config = getattr(counter, "config", None)
    if config is None:
        _fail(PolicyReindexFailureCode.CONFIG_DRIFT)
    return config


def _assembler_dimensions(assembler: Any) -> int:
    return int(_assembler_runtime_config(assembler).dimensions)


def _assembler_max_embedding_tokens(assembler: Any) -> int:
    return int(_assembler_runtime_config(assembler).max_embedding_tokens)


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


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
