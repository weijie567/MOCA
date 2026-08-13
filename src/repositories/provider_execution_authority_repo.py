"""PostgreSQL authority repository for bounded provider execution.

Every durable transition owns a short transaction.  Locking order is:
promotion singleton -> tenant advisory lock -> rollout -> manifest -> evidence
rollout -> source/candidate -> authority -> reservations -> results.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import (
    EvidenceIdentityRollout,
    PolicyCorpusManifestRevision,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    ProviderExecutionAuthority,
    ProviderExecutionPromotion,
    ProviderExecutionReservation,
    ProviderExecutionResult,
)
from src.rag.provider_execution_authority import (
    PROMOTION_SCOPE,
    PROTECTED_PROVIDER_EXECUTION_GRAPH,
    RETRYABLE_RESULT_CODES,
    CurrentProtectedCodeIdentityV1,
    ExecutionPromotionRequestV1,
    ExecutionPromotionViewV1,
    ProviderExecutionAuthorityFailureCode,
    ProviderExecutionProjectionV1,
    ProviderExecutionAuthorityRequestV1,
    ProviderExecutionAuthorityViewV1,
    ProviderExecutionReservationRequestV1,
    ProviderExecutionReservationViewV1,
    ProviderExecutionResultCode,
    ProviderExecutionResultRequestV1,
    ProviderExecutionResultViewV1,
    ProviderRequestEnvelopeV1,
    as_utc,
    canonical_sha256,
)


_ACTIVE_CANDIDATE_STATES = frozenset({"claimed", "building", "built", "validating", "complete"})


class ProviderExecutionAuthorityRepository:
    """Owns all DB reads, locks, inserts, DB time, and exact-match checks."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        project_entry: Path | None = None,
    ) -> None:
        self._sessions = session_factory
        self._project_root = _find_project_root(project_entry or Path(__file__))

    async def inspect_current_code_identity(self) -> CurrentProtectedCodeIdentityV1:
        """Derive identity from the repository checkout, never from request data."""

        dirty = _git_bytes(
            self._project_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *PROTECTED_PROVIDER_EXECUTION_GRAPH,
        )
        if dirty:
            _fail(ProviderExecutionAuthorityFailureCode.PROMOTION_STALE)
        return CurrentProtectedCodeIdentityV1(
            commit=_git_text(self._project_root, "rev-parse", "HEAD"),
            tree_hash=_git_text(self._project_root, "rev-parse", "HEAD^{tree}"),
            protected_paths=PROTECTED_PROVIDER_EXECUTION_GRAPH,
        )

    async def promote_reviewed_execution(
        self,
        request: ExecutionPromotionRequestV1,
    ) -> ExecutionPromotionViewV1:
        await self._validate_promotion_transition(request)
        async with self._sessions.begin() as session:
            await _lock_promotion_scope(session)
            existing = (
                await session.execute(
                    select(ProviderExecutionPromotion)
                    .where(ProviderExecutionPromotion.scope == PROMOTION_SCOPE)
                    .execution_options(populate_existing=True)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if existing is not None:
                view = _promotion_view(existing)
                if not _promotion_request_matches(view, request):
                    _fail(ProviderExecutionAuthorityFailureCode.PROMOTION_MISMATCH)
                return view

            row = ProviderExecutionPromotion(
                id=uuid4(),
                scope=PROMOTION_SCOPE,
                protected_code_c0_commit=request.protected_code_c0_commit,
                protected_code_c0_tree_hash=request.protected_code_c0_tree_hash,
                protected_code_c1_commit=request.protected_code_c1_commit,
                protected_code_c1_tree_hash=request.protected_code_c1_tree_hash,
                c0_to_c1_diff_hash=request.c0_to_c1_diff_hash,
                c0_code_review_artifact_sha256=request.c0_code_review_artifact_sha256,
                c0_security_artifact_sha256=request.c0_security_artifact_sha256,
                c1_code_review_artifact_sha256=request.c1_code_review_artifact_sha256,
                c1_security_artifact_sha256=request.c1_security_artifact_sha256,
                c0_code_review_attestation_sha256=request.c0_code_review_attestation_sha256,
                c0_security_attestation_sha256=request.c0_security_attestation_sha256,
                c1_code_review_attestation_sha256=request.c1_code_review_attestation_sha256,
                c1_security_attestation_sha256=request.c1_security_attestation_sha256,
                c0_gate_report_sha256=request.c0_gate_report_sha256,
                c1_gate_report_sha256=request.c1_gate_report_sha256,
                promotion_request_hash=request.promotion_request_hash,
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return _promotion_view(row)

    async def require_current_promotion(self) -> ExecutionPromotionViewV1:
        async with self._sessions.begin() as session:
            return await self._require_current_promotion_in_session(session)

    async def issue_authority_root(
        self,
        request: ProviderExecutionAuthorityRequestV1,
    ) -> ProviderExecutionAuthorityViewV1:
        await self.require_current_promotion()
        async with self._sessions.begin() as session:
            promotion = await self._require_current_promotion_in_session(session)
            await _lock_tenant_scope(session, request.tenant_id)
            inputs = await self._lock_current_inputs(
                session,
                request=request,
                require_unexpired=True,
            )
            existing = list(
                (
                    await session.execute(
                        select(ProviderExecutionAuthority)
                        .where(
                            ProviderExecutionAuthority.tenant_id == request.tenant_id,
                            or_(
                                ProviderExecutionAuthority.run_token == request.run_token,
                                ProviderExecutionAuthority.candidate_id == request.candidate_id,
                            ),
                        )
                        .order_by(ProviderExecutionAuthority.issued_at, ProviderExecutionAuthority.id)
                        .execution_options(populate_existing=True)
                        .with_for_update()
                    )
                ).scalars()
            )
            if existing:
                if len(existing) != 1:
                    _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISMATCH)
                view = _authority_view(existing[0])
                if view.promotion_id != promotion.promotion_id or not _authority_request_matches(view, request):
                    _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISMATCH)
                return view

            row = ProviderExecutionAuthority(
                id=uuid4(),
                tenant_id=request.tenant_id,
                promotion_id=promotion.promotion_id,
                run_token=request.run_token,
                candidate_id=request.candidate_id,
                owner_marker=request.owner_marker,
                config_schema_version=request.config_schema_version,
                config_json=dict(request.config_json),
                config_fingerprint=request.config_fingerprint,
                provider_parity_run_id=request.provider_parity_run_id,
                provider_parity_report_hash=request.provider_parity_report_hash,
                provider_parity_probe_fixture_sha256=request.provider_parity_probe_fixture_sha256,
                provider_parity_submitted_content_sha256=request.provider_parity_submitted_content_sha256,
                parity_captured_at=as_utc(request.parity_captured_at),
                parity_expires_at=as_utc(request.parity_expires_at),
                source_manifest_revision_id=request.source_manifest_revision_id,
                source_manifest_hash=request.source_manifest_hash,
                source_active_corpus_version_id=request.source_active_corpus_version_id,
                source_rollout_epoch=request.source_rollout_epoch,
                evidence_rollout_version=request.evidence_rollout_version,
                candidate_lease_expires_at=as_utc(request.candidate_lease_expires_at),
                expires_at=as_utc(request.expires_at),
                provider_name=request.provider_name,
                model_name=request.model_name,
                dimensions=request.dimensions,
                envelope_contract_hash=request.envelope_contract_hash,
                issued_at=inputs.now,
            )
            session.add(row)
            await session.flush()
            return _authority_view(row)

    async def reserve_and_commit(
        self,
        request: ProviderExecutionReservationRequestV1,
    ) -> ProviderExecutionReservationViewV1:
        await self.require_current_promotion()
        if request.ordinal > 2:
            _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_EXHAUSTED)
        async with self._sessions.begin() as session:
            promotion = await self._require_current_promotion_in_session(session)
            peek = await session.get(ProviderExecutionAuthority, request.authority_id)
            if peek is None:
                _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISSING)
            await _lock_tenant_scope(session, peek.tenant_id)
            authority = await self._lock_and_validate_authority(
                session,
                authority_id=request.authority_id,
                expected_promotion_id=promotion.promotion_id,
            )
            _validate_envelope(authority, request.request_envelope)
            reservations = list(
                (
                    await session.execute(
                        select(ProviderExecutionReservation)
                        .where(
                            ProviderExecutionReservation.authority_id == authority.id,
                            ProviderExecutionReservation.purpose == request.purpose.value,
                            ProviderExecutionReservation.subject_hash == request.subject_hash,
                        )
                        .order_by(ProviderExecutionReservation.ordinal, ProviderExecutionReservation.id)
                        .execution_options(populate_existing=True)
                        .with_for_update()
                    )
                ).scalars()
            )
            if any(row.ordinal == request.ordinal for row in reservations):
                _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_CONFLICT)

            predecessor_result_id: UUID | None = None
            if request.ordinal == 1:
                if reservations:
                    _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_CONFLICT)
            else:
                ordinal_one = [row for row in reservations if row.ordinal == 1]
                if len(ordinal_one) != 1 or len(reservations) != 1:
                    _fail(ProviderExecutionAuthorityFailureCode.RETRY_NOT_ALLOWED)
                first = ordinal_one[0]
                predecessor = (
                    await session.execute(
                        select(ProviderExecutionResult)
                        .where(ProviderExecutionResult.reservation_id == first.id)
                        .execution_options(populate_existing=True)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                predecessor_code = (
                    ProviderExecutionResultCode(predecessor.result_code) if predecessor is not None else None
                )
                if (
                    predecessor is None
                    or predecessor_code not in RETRYABLE_RESULT_CODES
                    or (
                        predecessor_code is ProviderExecutionResultCode.TRANSIENT_EXECUTION_ERROR
                        and predecessor.actual_request_count <= 0
                    )
                    or not _retry_request_matches_first(first, request)
                ):
                    _fail(ProviderExecutionAuthorityFailureCode.RETRY_NOT_ALLOWED)
                predecessor_result_id = predecessor.id

            row = ProviderExecutionReservation(
                id=uuid4(),
                tenant_id=authority.tenant_id,
                authority_id=authority.id,
                purpose=request.purpose.value,
                subject_kind=request.subject_kind,
                subject_index=request.subject_index,
                subject_hash=request.subject_hash,
                ordinal=request.ordinal,
                envelope_schema_version=request.request_envelope.schema_version,
                request_envelope_json=_envelope_json(request.request_envelope),
                request_envelope_hash=request.request_envelope.canonical_hash,
                max_request_count=request.request_envelope.maximum_request_count,
                predecessor_result_id=predecessor_result_id,
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return _reservation_view(row)

    async def recheck_dispatch(
        self,
        expected: ProviderExecutionReservationViewV1,
    ) -> ProviderExecutionReservationViewV1:
        await self.require_current_promotion()
        async with self._sessions.begin() as session:
            promotion = await self._require_current_promotion_in_session(session)
            peek = await session.get(ProviderExecutionReservation, expected.reservation_id)
            if peek is None:
                _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_MISSING)
            if peek.authority_id != expected.authority_id or peek.tenant_id != expected.tenant_id:
                _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_MISMATCH)
            await _lock_tenant_scope(session, peek.tenant_id)
            await self._lock_and_validate_authority(
                session,
                authority_id=peek.authority_id,
                expected_promotion_id=promotion.promotion_id,
            )
            row = (
                await session.execute(
                    select(ProviderExecutionReservation)
                    .where(ProviderExecutionReservation.id == expected.reservation_id)
                    .execution_options(populate_existing=True)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None:
                _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_MISSING)
            actual = _reservation_view(row)
            if actual != expected:
                _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_MISMATCH)
            result = (
                await session.execute(
                    select(ProviderExecutionResult.id)
                    .where(ProviderExecutionResult.reservation_id == row.id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if result is not None:
                _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_MISMATCH)
            return actual

    async def record_result(
        self,
        request: ProviderExecutionResultRequestV1,
    ) -> ProviderExecutionResultViewV1:
        """Append or exactly replay the sole committed result for a reservation."""

        if (
            request.result_code == ProviderExecutionResultCode.TRANSIENT_EXECUTION_ERROR
            and request.actual_request_count <= 0
        ):
            _fail(ProviderExecutionAuthorityFailureCode.RESULT_MISMATCH)
        async with self._sessions.begin() as session:
            peek = await session.get(ProviderExecutionReservation, request.reservation_id)
            if peek is None:
                _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_MISSING)
            await _lock_tenant_scope(session, peek.tenant_id)
            reservation = (
                await session.execute(
                    select(ProviderExecutionReservation)
                    .where(ProviderExecutionReservation.id == request.reservation_id)
                    .execution_options(populate_existing=True)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if reservation is None:
                _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_MISSING)
            try:
                _reservation_view(reservation)
            except ValueError:
                _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_MISMATCH)
            if request.actual_request_count > reservation.max_request_count:
                _fail(ProviderExecutionAuthorityFailureCode.RESULT_MISMATCH)

            existing = list(
                (
                    await session.execute(
                        select(ProviderExecutionResult)
                        .where(
                            or_(
                                ProviderExecutionResult.id == request.result_id,
                                ProviderExecutionResult.reservation_id == request.reservation_id,
                            )
                        )
                        .order_by(ProviderExecutionResult.completed_at, ProviderExecutionResult.id)
                        .execution_options(populate_existing=True)
                        .with_for_update()
                    )
                ).scalars()
            )
            if existing:
                if len(existing) != 1:
                    _fail(ProviderExecutionAuthorityFailureCode.RESULT_MISMATCH)
                view = _result_view(existing[0])
                if not _result_request_matches(view, request):
                    _fail(ProviderExecutionAuthorityFailureCode.RESULT_MISMATCH)
                return view

            if request.output_candidate_id is not None:
                output_candidate = (
                    await session.execute(
                        select(PolicyCorpusVersion)
                        .where(
                            PolicyCorpusVersion.id == request.output_candidate_id,
                            PolicyCorpusVersion.tenant_id == reservation.tenant_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if output_candidate is None:
                    _fail(ProviderExecutionAuthorityFailureCode.RESULT_MISMATCH)

            row = ProviderExecutionResult(
                id=request.result_id,
                tenant_id=reservation.tenant_id,
                reservation_id=reservation.id,
                request_limit=reservation.max_request_count,
                result_code=request.result_code.value,
                actual_request_count=request.actual_request_count,
                result_schema_version="provider_execution_result.v1",
                result_json=dict(request.result_json),
                result_hash=request.result_hash,
                output_candidate_id=request.output_candidate_id,
                terminal_run_hash=request.terminal_run_hash,
                terminal_report_hash=request.terminal_report_hash,
                selection_id=request.selection_id,
                selection_decision_hash=request.selection_decision_hash,
                activation_authorization_hash=request.activation_authorization_hash,
            )
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return _result_view(row)

    async def get_result(
        self,
        *,
        reservation_id: UUID,
    ) -> ProviderExecutionResultViewV1 | None:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(ProviderExecutionResult).where(ProviderExecutionResult.reservation_id == reservation_id)
                )
            ).scalar_one_or_none()
            return _result_view(row) if row is not None else None

    async def read_projection(
        self,
        *,
        authority_id: UUID,
    ) -> ProviderExecutionProjectionV1:
        """Read and lock a committed graph; never infer or create missing DB rows."""

        async with self._sessions.begin() as session:
            await _lock_promotion_scope(session)
            peek = await session.get(ProviderExecutionAuthority, authority_id)
            if peek is None:
                _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISSING)
            await _lock_tenant_scope(session, peek.tenant_id)
            authority = (
                await session.execute(
                    select(ProviderExecutionAuthority)
                    .where(ProviderExecutionAuthority.id == authority_id)
                    .execution_options(populate_existing=True)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if authority is None:
                _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISSING)
            promotion = (
                await session.execute(
                    select(ProviderExecutionPromotion)
                    .where(ProviderExecutionPromotion.id == authority.promotion_id)
                    .execution_options(populate_existing=True)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if promotion is None:
                _fail(ProviderExecutionAuthorityFailureCode.PROMOTION_MISSING)
            reservations = list(
                (
                    await session.execute(
                        select(ProviderExecutionReservation)
                        .where(ProviderExecutionReservation.authority_id == authority.id)
                        .order_by(
                            ProviderExecutionReservation.purpose,
                            ProviderExecutionReservation.subject_hash,
                            ProviderExecutionReservation.ordinal,
                            ProviderExecutionReservation.id,
                        )
                        .execution_options(populate_existing=True)
                        .with_for_update()
                    )
                ).scalars()
            )
            reservation_ids = [row.id for row in reservations]
            results = (
                list(
                    (
                        await session.execute(
                            select(ProviderExecutionResult)
                            .where(ProviderExecutionResult.reservation_id.in_(reservation_ids))
                            .order_by(
                                ProviderExecutionResult.reservation_id,
                                ProviderExecutionResult.id,
                            )
                            .execution_options(populate_existing=True)
                            .with_for_update()
                        )
                    ).scalars()
                )
                if reservation_ids
                else []
            )
            try:
                return ProviderExecutionProjectionV1(
                    promotion=_promotion_view(promotion),
                    authority=_authority_view(authority),
                    reservations=tuple(_reservation_view(row) for row in reservations),
                    results=tuple(_result_view(row) for row in results),
                )
            except ValueError:
                _fail(ProviderExecutionAuthorityFailureCode.PROJECTION_MISMATCH)

    async def _validate_promotion_transition(self, request: ExecutionPromotionRequestV1) -> None:
        try:
            c0_tree = _git_text(self._project_root, "rev-parse", f"{request.protected_code_c0_commit}^{{tree}}")
            c1_tree = _git_text(self._project_root, "rev-parse", f"{request.protected_code_c1_commit}^{{tree}}")
            _git_bytes(
                self._project_root,
                "merge-base",
                "--is-ancestor",
                request.protected_code_c0_commit,
                request.protected_code_c1_commit,
            )
        except (OSError, subprocess.CalledProcessError):
            _fail(ProviderExecutionAuthorityFailureCode.PROMOTION_MISMATCH)
        if c0_tree != request.protected_code_c0_tree_hash or c1_tree != request.protected_code_c1_tree_hash:
            _fail(ProviderExecutionAuthorityFailureCode.PROMOTION_MISMATCH)
        current = await self.inspect_current_code_identity()
        if (
            current.commit != request.protected_code_c1_commit
            or current.tree_hash != request.protected_code_c1_tree_hash
        ):
            _fail(ProviderExecutionAuthorityFailureCode.PROMOTION_MISMATCH)
        diff = _git_bytes(
            self._project_root,
            "diff",
            "--binary",
            "--full-index",
            request.protected_code_c0_commit,
            request.protected_code_c1_commit,
            "--",
            *PROTECTED_PROVIDER_EXECUTION_GRAPH,
        )
        if canonical_sha256(diff) != request.c0_to_c1_diff_hash:
            _fail(ProviderExecutionAuthorityFailureCode.PROMOTION_MISMATCH)

    async def _require_current_promotion_in_session(
        self,
        session: AsyncSession,
    ) -> ExecutionPromotionViewV1:
        await _lock_promotion_scope(session)
        row = (
            await session.execute(
                select(ProviderExecutionPromotion)
                .where(ProviderExecutionPromotion.scope == PROMOTION_SCOPE)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            _fail(ProviderExecutionAuthorityFailureCode.PROMOTION_MISSING)
        try:
            current = await self.inspect_current_code_identity()
        except Exception as exc:
            if getattr(exc, "reason_code", None) == ProviderExecutionAuthorityFailureCode.PROMOTION_STALE.value:
                raise
            _fail(ProviderExecutionAuthorityFailureCode.PROMOTION_STALE)
        if current.commit != row.protected_code_c1_commit or current.tree_hash != row.protected_code_c1_tree_hash:
            _fail(ProviderExecutionAuthorityFailureCode.PROMOTION_STALE)
        try:
            return _promotion_view(row)
        except ValueError:
            _fail(ProviderExecutionAuthorityFailureCode.PROMOTION_MISMATCH)

    async def _lock_current_inputs(
        self,
        session: AsyncSession,
        *,
        request: ProviderExecutionAuthorityRequestV1,
        require_unexpired: bool,
    ) -> _LockedInputs:
        rollout = (
            await session.execute(
                select(PolicyCorpusRollout)
                .where(PolicyCorpusRollout.tenant_id == request.tenant_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        ).scalar_one_or_none()
        manifest = (
            await session.execute(
                select(PolicyCorpusManifestRevision)
                .where(PolicyCorpusManifestRevision.tenant_id == request.tenant_id)
                .order_by(PolicyCorpusManifestRevision.revision.desc(), PolicyCorpusManifestRevision.id.desc())
                .limit(1)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        ).scalar_one_or_none()
        evidence = (
            await session.execute(
                select(EvidenceIdentityRollout)
                .where(EvidenceIdentityRollout.id == 1)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        ).scalar_one_or_none()
        source = (
            await session.execute(
                select(PolicyCorpusVersion)
                .where(
                    PolicyCorpusVersion.id == request.source_active_corpus_version_id,
                    PolicyCorpusVersion.tenant_id == request.tenant_id,
                )
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        ).scalar_one_or_none()
        candidate = (
            await session.execute(
                select(PolicyCorpusVersion)
                .where(
                    PolicyCorpusVersion.id == request.candidate_id,
                    PolicyCorpusVersion.tenant_id == request.tenant_id,
                )
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        ).scalar_one_or_none()
        now = _require_db_time(await session.scalar(text("SELECT clock_timestamp()")))
        if (
            rollout is None
            or manifest is None
            or evidence is None
            or source is None
            or candidate is None
            or rollout.active_corpus_version_id != request.source_active_corpus_version_id
            or rollout.rollout_epoch != request.source_rollout_epoch
            or manifest.id != request.source_manifest_revision_id
            or manifest.manifest_hash != request.source_manifest_hash
            or source.id != rollout.active_corpus_version_id
            or source.state != "complete"
            or source.source_manifest_revision_id != manifest.id
            or source.source_manifest_hash != manifest.manifest_hash
            or evidence.rollout_version != request.evidence_rollout_version
            or candidate.run_token != request.run_token
            or candidate.owner_marker != request.owner_marker
            or candidate.config_schema_version != request.config_schema_version
            or dict(candidate.config_json or {}) != request.config_json
            or candidate.config_fingerprint != request.config_fingerprint
            or candidate.provider_parity_report_hash != request.provider_parity_report_hash
            or candidate.source_manifest_revision_id != request.source_manifest_revision_id
            or candidate.source_manifest_hash != request.source_manifest_hash
            or candidate.source_active_corpus_version_id != request.source_active_corpus_version_id
            or candidate.source_rollout_epoch != request.source_rollout_epoch
            or candidate.expected_evidence_rollout_version != request.evidence_rollout_version
            or candidate.lease_expires_at is None
            or as_utc(candidate.lease_expires_at) != as_utc(request.candidate_lease_expires_at)
            or candidate.state not in _ACTIVE_CANDIDATE_STATES
            or as_utc(request.expires_at)
            != min(as_utc(request.parity_expires_at), as_utc(request.candidate_lease_expires_at))
        ):
            _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISMATCH)
        claim = (
            candidate.validation_proof_json.get("claim") if isinstance(candidate.validation_proof_json, dict) else None
        )
        if not isinstance(claim, dict):
            _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISMATCH)
        try:
            captured = as_utc(datetime.fromisoformat(str(claim["parity_captured_at"])))
            parity_expiry = as_utc(datetime.fromisoformat(str(claim["parity_expires_at"])))
            source_manifest_revision = int(claim["source_manifest_revision"])
        except (KeyError, TypeError, ValueError):
            _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISMATCH)
        if (
            captured != as_utc(request.parity_captured_at)
            or parity_expiry != as_utc(request.parity_expires_at)
            or source_manifest_revision != manifest.revision
            or captured > now
        ):
            _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISMATCH)
        if require_unexpired and (
            now >= as_utc(request.expires_at)
            or now >= as_utc(request.parity_expires_at)
            or now >= as_utc(request.candidate_lease_expires_at)
        ):
            _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_STALE)
        return _LockedInputs(now=now)

    async def _lock_and_validate_authority(
        self,
        session: AsyncSession,
        *,
        authority_id: UUID,
        expected_promotion_id: UUID,
    ) -> ProviderExecutionAuthority:
        peek = await session.get(ProviderExecutionAuthority, authority_id)
        if peek is None:
            _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISSING)
        try:
            request = _authority_request_from_row(peek)
        except ValueError:
            _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISMATCH)
        await self._lock_current_inputs(session, request=request, require_unexpired=True)
        row = (
            await session.execute(
                select(ProviderExecutionAuthority)
                .where(ProviderExecutionAuthority.id == authority_id)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISSING)
        if row.promotion_id != expected_promotion_id or _authority_view(row) != _authority_view(peek):
            _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISMATCH)
        return row


class _LockedInputs:
    def __init__(self, *, now: datetime) -> None:
        self.now = now


async def _lock_promotion_scope(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
        {"scope": PROMOTION_SCOPE},
    )


async def _lock_tenant_scope(session: AsyncSession, tenant_id: UUID) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:tenant_id AS text), 0))"),
        {"tenant_id": str(tenant_id)},
    )


def _promotion_view(row: ProviderExecutionPromotion) -> ExecutionPromotionViewV1:
    return ExecutionPromotionViewV1(
        promotion_id=row.id,
        scope=row.scope,
        protected_code_c0_commit=row.protected_code_c0_commit,
        protected_code_c0_tree_hash=row.protected_code_c0_tree_hash,
        protected_code_c1_commit=row.protected_code_c1_commit,
        protected_code_c1_tree_hash=row.protected_code_c1_tree_hash,
        c0_to_c1_diff_hash=row.c0_to_c1_diff_hash,
        c0_code_review_artifact_sha256=row.c0_code_review_artifact_sha256,
        c0_security_artifact_sha256=row.c0_security_artifact_sha256,
        c1_code_review_artifact_sha256=row.c1_code_review_artifact_sha256,
        c1_security_artifact_sha256=row.c1_security_artifact_sha256,
        c0_code_review_attestation_sha256=row.c0_code_review_attestation_sha256,
        c0_security_attestation_sha256=row.c0_security_attestation_sha256,
        c1_code_review_attestation_sha256=row.c1_code_review_attestation_sha256,
        c1_security_attestation_sha256=row.c1_security_attestation_sha256,
        c0_gate_report_sha256=row.c0_gate_report_sha256,
        c1_gate_report_sha256=row.c1_gate_report_sha256,
        promotion_request_hash=row.promotion_request_hash,
        promoted_at=row.promoted_at,
    )


def _authority_request_from_row(row: ProviderExecutionAuthority) -> ProviderExecutionAuthorityRequestV1:
    return ProviderExecutionAuthorityRequestV1(
        tenant_id=row.tenant_id,
        run_token=row.run_token,
        candidate_id=row.candidate_id,
        owner_marker=row.owner_marker,
        config_schema_version=row.config_schema_version,
        config_json=dict(row.config_json or {}),
        config_fingerprint=row.config_fingerprint,
        provider_parity_run_id=row.provider_parity_run_id,
        provider_parity_report_hash=row.provider_parity_report_hash,
        provider_parity_probe_fixture_sha256=row.provider_parity_probe_fixture_sha256,
        provider_parity_submitted_content_sha256=row.provider_parity_submitted_content_sha256,
        parity_captured_at=row.parity_captured_at,
        parity_expires_at=row.parity_expires_at,
        source_manifest_revision_id=row.source_manifest_revision_id,
        source_manifest_hash=row.source_manifest_hash,
        source_active_corpus_version_id=row.source_active_corpus_version_id,
        source_rollout_epoch=row.source_rollout_epoch,
        evidence_rollout_version=row.evidence_rollout_version,
        candidate_lease_expires_at=row.candidate_lease_expires_at,
        expires_at=row.expires_at,
        provider_name=row.provider_name,
        model_name=row.model_name,
        dimensions=row.dimensions,
        envelope_contract_hash=row.envelope_contract_hash,
    )


def _authority_view(row: ProviderExecutionAuthority) -> ProviderExecutionAuthorityViewV1:
    return ProviderExecutionAuthorityViewV1(
        **_authority_request_from_row(row).model_dump(),
        authority_id=row.id,
        promotion_id=row.promotion_id,
        issued_at=row.issued_at,
    )


def _reservation_view(row: ProviderExecutionReservation) -> ProviderExecutionReservationViewV1:
    envelope = ProviderRequestEnvelopeV1.model_validate(dict(row.request_envelope_json or {}))
    if (
        row.envelope_schema_version != envelope.schema_version
        or row.request_envelope_hash != envelope.canonical_hash
        or row.max_request_count != envelope.maximum_request_count
    ):
        _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_MISMATCH)
    return ProviderExecutionReservationViewV1(
        reservation_id=row.id,
        tenant_id=row.tenant_id,
        authority_id=row.authority_id,
        purpose=row.purpose,
        subject_kind=row.subject_kind,
        subject_index=row.subject_index,
        subject_hash=row.subject_hash,
        ordinal=row.ordinal,
        request_envelope=envelope,
        explicit_retry=row.ordinal == 2,
        predecessor_result_id=row.predecessor_result_id,
        reserved_at=row.reserved_at,
    )


def _result_view(row: ProviderExecutionResult) -> ProviderExecutionResultViewV1:
    if (
        row.actual_request_count < 0
        or row.actual_request_count > row.request_limit
        or (
            row.result_code == ProviderExecutionResultCode.TRANSIENT_EXECUTION_ERROR.value
            and row.actual_request_count == 0
        )
    ):
        _fail(ProviderExecutionAuthorityFailureCode.RESULT_MISMATCH)
    try:
        return ProviderExecutionResultViewV1(
            schema_version=row.result_schema_version,
            reservation_id=row.reservation_id,
            result_id=row.id,
            tenant_id=row.tenant_id,
            request_limit=row.request_limit,
            result_code=row.result_code,
            actual_request_count=row.actual_request_count,
            result_json=dict(row.result_json or {}),
            result_hash=row.result_hash,
            output_candidate_id=row.output_candidate_id,
            terminal_run_hash=row.terminal_run_hash,
            terminal_report_hash=row.terminal_report_hash,
            selection_id=row.selection_id,
            selection_decision_hash=row.selection_decision_hash,
            activation_authorization_hash=row.activation_authorization_hash,
            completed_at=row.completed_at,
        )
    except ValueError:
        _fail(ProviderExecutionAuthorityFailureCode.RESULT_MISMATCH)


def _result_request_matches(
    view: ProviderExecutionResultViewV1,
    request: ProviderExecutionResultRequestV1,
) -> bool:
    return (
        ProviderExecutionResultRequestV1.model_validate(
            view.model_dump(exclude={"schema_version", "tenant_id", "request_limit", "completed_at"})
        )
        == request
    )


def _promotion_request_matches(view: ExecutionPromotionViewV1, request: ExecutionPromotionRequestV1) -> bool:
    return all(
        getattr(view, field) == getattr(request, field) for field in ExecutionPromotionRequestV1._HASH_FIELDS
    ) and (view.promotion_request_hash == request.promotion_request_hash)


def _authority_request_matches(
    view: ProviderExecutionAuthorityViewV1,
    request: ProviderExecutionAuthorityRequestV1,
) -> bool:
    return (
        ProviderExecutionAuthorityRequestV1.model_validate(
            view.model_dump(exclude={"authority_id", "promotion_id", "issued_at"})
        )
        == request
    )


def _validate_envelope(authority: ProviderExecutionAuthority, envelope: ProviderRequestEnvelopeV1) -> None:
    if (
        envelope.contract_hash != authority.envelope_contract_hash
        or envelope.provider_name != authority.provider_name
        or envelope.model_name != authority.model_name
        or envelope.dimensions != authority.dimensions
    ):
        _fail(ProviderExecutionAuthorityFailureCode.RESERVATION_MISMATCH)


def _retry_request_matches_first(
    first: ProviderExecutionReservation,
    request: ProviderExecutionReservationRequestV1,
) -> bool:
    return (
        first.purpose == request.purpose.value
        and first.subject_kind == request.subject_kind
        and first.subject_index == request.subject_index
        and first.subject_hash == request.subject_hash
        and first.envelope_schema_version == request.request_envelope.schema_version
        and dict(first.request_envelope_json or {}) == _envelope_json(request.request_envelope)
        and first.request_envelope_hash == request.request_envelope.canonical_hash
        and first.max_request_count == request.request_envelope.maximum_request_count
    )


def _envelope_json(envelope: ProviderRequestEnvelopeV1) -> dict[str, Any]:
    return envelope.model_dump(mode="json")


def _find_project_root(entry: Path) -> Path:
    resolved = entry.absolute()
    candidate = resolved if resolved.is_dir() else resolved.parent
    for directory in (candidate, *candidate.parents):
        if (directory / ".git").exists():
            return directory
    raise RuntimeError("provider authority project checkout is unavailable")


def _git_text(project_root: Path, *args: str) -> str:
    return _git_bytes(project_root, *args).decode("utf-8").strip()


def _git_bytes(project_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *args],
        check=True,
        capture_output=True,
    )
    return completed.stdout


def _require_db_time(value: object) -> datetime:
    if not isinstance(value, datetime):
        _fail(ProviderExecutionAuthorityFailureCode.AUTHORITY_MISMATCH)
    return as_utc(value)


def _fail(code: ProviderExecutionAuthorityFailureCode) -> None:
    from src.rag.provider_execution_authority import ProviderExecutionAuthorityError

    raise ProviderExecutionAuthorityError(code)
