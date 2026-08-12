"""Create-only activation receipts bound to committed PostgreSQL history.

The database activation row is committed first and remains append-only.  This
module then re-reads the live row and pointer, revalidates the immutable
selection/terminal/parity files, and creates a deterministic receipt.  Missing
receipt files can be reconstructed from committed history; existing bytes are
never rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    PolicyCorpusActivationHistory,
    PolicyCorpusRollout,
)
from src.rag.evaluation.token_chunk_ab import (
    ABRecoveryAuthorizationV1,
    ABSelectionDecisionV1,
    TerminalABRunV1,
    load_recovery_authorization,
    load_selection_decision,
    load_terminal_ab_run,
    require_canonical_recovery_root,
)
from src.rag.tokenizer_parity import (
    EmbeddingTokenizerParityReportV1,
    TokenizerParityError,
    load_parity_report,
)

if TYPE_CHECKING:
    from src.rag.policy_reindex import ImmutableSelectionDecisionV1


ACTIVATION_RECEIPT_SCHEMA_VERSION = "rag_token_chunk_activation.v1"
ACTIVATION_RECEIPT_GENESIS = "genesis"
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_RECEIPT_REASONS = ("selected_cutover", "rollback_prior", "restore_selected")


class ActivationReceiptFailureCode(StrEnum):
    ARTIFACT_MISMATCH = "artifact_mismatch"
    HISTORY_UNAVAILABLE = "history_unavailable"
    HISTORY_MISMATCH = "history_mismatch"
    LIVE_POINTER_MISMATCH = "live_pointer_mismatch"
    PREVIOUS_RECEIPT_MISSING = "previous_receipt_missing"
    CREATE_CONFLICT = "create_conflict"
    RECEIPT_INVALID = "receipt_invalid"
    WRITE_FAILED = "write_failed"


class ActivationReceiptError(RuntimeError):
    """Safe activation evidence failure with an allowlisted reason code."""

    def __init__(self, code: ActivationReceiptFailureCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class ActivationArtifactPaths:
    selection_path: Path
    terminal_run_path: Path
    parity_report_path: Path
    recovery_authorization_path: Path
    recovery_budget_manifest_path: Path
    recovery_reservation_path: Path
    candidate_state_path: Path


@dataclass(frozen=True, slots=True)
class ActivationAuthorityV1:
    paths: ActivationArtifactPaths
    selection: ABSelectionDecisionV1
    terminal_run: TerminalABRunV1
    parity_report: EmbeddingTokenizerParityReportV1
    recovery_authorization: ABRecoveryAuthorizationV1
    selection_decision_sha256: str
    terminal_run_sha256: str
    provider_parity_report_sha256: str
    recovery_authorization_sha256: str
    config_fingerprint: str

    def to_selection_proof(
        self,
        *,
        expected_evidence_rollout_version: int,
    ) -> ImmutableSelectionDecisionV1:
        """Project verified immutable files into the cutover service contract."""

        from src.rag.policy_reindex import ImmutableSelectionDecisionV1

        return ImmutableSelectionDecisionV1(
            schema_version="rag_token_chunk_selection.v1",
            selection_decision_sha256=self.selection_decision_sha256,
            outcome="selected_pass",
            tenant_id=self.selection.tenant_id,
            candidate_corpus_version_id=self.selection.candidate_corpus_version_id,
            run_token=self.selection.candidate_run_token,
            lease_owner=self.selection.candidate_lease_owner,
            config_fingerprint=self.config_fingerprint,
            provider_parity_report_hash=self.provider_parity_report_sha256,
            source_manifest_hash=self.selection.source_manifest_hash,
            expected_evidence_rollout_version=expected_evidence_rollout_version,
            recovery_authorization_sha256=self.recovery_authorization_sha256,
        )


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ActivationReceiptV1(_FrozenModel):
    schema_version: Literal["rag_token_chunk_activation.v1"] = ACTIVATION_RECEIPT_SCHEMA_VERSION
    tenant_id: UUID
    history_id: UUID
    history_sequence: int = Field(gt=0)
    event_reason: Literal["selected_cutover", "rollback_prior", "restore_selected"]
    from_corpus_version_id: UUID
    to_corpus_version_id: UUID
    before_rollout_epoch: int = Field(ge=0)
    after_rollout_epoch: int = Field(gt=0)
    db_history_sha256: str = Field(pattern=_SHA256_PATTERN)
    actor: str = Field(min_length=1, max_length=128)
    committed_at: datetime
    selection_decision_sha256: str = Field(pattern=_SHA256_PATTERN)
    selection_payload_sha256: str = Field(pattern=_SHA256_PATTERN)
    terminal_run_sha256: str = Field(pattern=_SHA256_PATTERN)
    provider_parity_report_sha256: str = Field(pattern=_SHA256_PATTERN)
    recovery_authorization_sha256: str = Field(pattern=_SHA256_PATTERN)
    candidate_run_token: UUID
    candidate_lease_owner: str = Field(min_length=1, max_length=128)
    source_manifest_hash: str = Field(pattern=_SHA256_PATTERN)
    config_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    previous_receipt_sha256: str
    receipt_payload_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_receipt(self) -> ActivationReceiptV1:
        if self.committed_at.tzinfo is None:
            raise ValueError("committed_time_invalid")
        if self.after_rollout_epoch != self.history_sequence:
            raise ValueError("history_sequence_mismatch")
        if self.before_rollout_epoch + 1 != self.after_rollout_epoch:
            raise ValueError("history_epoch_mismatch")
        if self.from_corpus_version_id == self.to_corpus_version_id:
            raise ValueError("history_pointer_mismatch")
        if self.previous_receipt_sha256 != ACTIVATION_RECEIPT_GENESIS and not _valid_sha256(
            self.previous_receipt_sha256
        ):
            raise ValueError("previous_receipt_invalid")
        expected = _sha256_json(self.model_dump(mode="json", exclude={"receipt_payload_sha256"}))
        if self.receipt_payload_sha256 != expected:
            raise ValueError("receipt_payload_hash_mismatch")
        return self


@dataclass(frozen=True, slots=True)
class ActivationReceiptArtifactV1:
    path: Path
    file_sha256: str
    receipt: ActivationReceiptV1


def load_activation_authority(
    paths: ActivationArtifactPaths,
    *,
    repository_root: Path | None = None,
) -> ActivationAuthorityV1:
    """Strictly load and cross-check selection plus its recovery lineage."""

    try:
        recovery_root = paths.recovery_budget_manifest_path.parents[2]
        if repository_root is not None:
            require_canonical_recovery_root(
                output_root=recovery_root,
                repository_root=repository_root,
            )
        selection_bytes = paths.selection_path.read_bytes()
        terminal_bytes = paths.terminal_run_path.read_bytes()
        parity_bytes = paths.parity_report_path.read_bytes()
        authorization_bytes = paths.recovery_authorization_path.read_bytes()
        selection = load_selection_decision(paths.selection_path)
        terminal = load_terminal_ab_run(paths.terminal_run_path)
        parity = load_parity_report(paths.parity_report_path)
        recovery_authorization = load_recovery_authorization(paths.recovery_authorization_path)
        load_recovery_authorization(
            paths.recovery_authorization_path,
            root=recovery_root,
            manifest_path=paths.recovery_budget_manifest_path,
            reservation_path=paths.recovery_reservation_path,
            candidate_state_path=paths.candidate_state_path,
            provider_parity_report_path=paths.parity_report_path,
            terminal_run_path=paths.terminal_run_path,
            selection_path=paths.selection_path,
            checked_at=recovery_authorization.authorized_at,
        )
        selection_sha256 = _sha256_bytes(selection_bytes)
        terminal_sha256 = _sha256_bytes(terminal_bytes)
        parity_sha256 = _sha256_bytes(parity_bytes)
        authorization_sha256 = _sha256_bytes(authorization_bytes)
        candidate = terminal.candidate
        if (
            terminal.outcome != "selected_pass"
            or candidate is None
            or selection.outcome != "selected_pass"
            or selection.terminal_run_id != terminal.run_id
            or selection.terminal_run_sha256 != terminal_sha256
            or selection.provider_parity_report_sha256 != parity_sha256
            or selection.tenant_id != terminal.runtime.tenant_id
            or selection.candidate_corpus_version_id != candidate.corpus_version_id
            or selection.manifest_hash != terminal.inputs.manifest_hash
            or selection.gold_hash != terminal.inputs.gold_hash
            or selection.dataset_baseline_identity != terminal.inputs.dataset_baseline_identity
            or selection.runtime_config_sha256 != _sha256_json(terminal.runtime.model_dump(mode="json"))
            or selection.candidate_observation_sha256 != _sha256_json(candidate.model_dump(mode="json"))
            or selection.exact_gate_profile_sha256
            != _sha256_json([gate.model_dump(mode="json") for gate in terminal.gates])
            or terminal.parity.report_sha256 != parity_sha256
            or terminal.parity.run_id != parity.run_id
            or terminal.parity.captured_at.astimezone(UTC) != parity.captured_at.astimezone(UTC)
            or terminal.parity.status != "passed"
            or parity.provider_parity_status.value != "passed"
            or terminal.parity.config_fingerprint != parity.config_fingerprint
            or candidate.config_fingerprint != parity.config_fingerprint
            or terminal.parity.probe_fixture_sha256 != parity.probe_fixture_sha256
            or terminal.parity.submitted_content_sha256 != parity.submitted_content_sha256
            or recovery_authorization.selection_sha256 != selection_sha256
            or recovery_authorization.terminal_run_sha256 != terminal_sha256
            or recovery_authorization.provider_parity_report_sha256 != parity_sha256
            or recovery_authorization.candidate_config_fingerprint != parity.config_fingerprint
        ):
            _fail(ActivationReceiptFailureCode.ARTIFACT_MISMATCH)
    except ActivationReceiptError:
        raise
    except (IndexError, OSError, TokenizerParityError, ValidationError, TypeError, ValueError):
        _fail(ActivationReceiptFailureCode.ARTIFACT_MISMATCH)
    return ActivationAuthorityV1(
        paths=paths,
        selection=selection,
        terminal_run=terminal,
        parity_report=parity,
        recovery_authorization=recovery_authorization,
        selection_decision_sha256=selection_sha256,
        terminal_run_sha256=terminal_sha256,
        provider_parity_report_sha256=parity_sha256,
        recovery_authorization_sha256=authorization_sha256,
        config_fingerprint=parity.config_fingerprint,
    )


def load_activation_receipt(path: Path) -> ActivationReceiptV1:
    try:
        payload = json.loads(path.read_bytes())
        return ActivationReceiptV1.model_validate(payload)
    except (OSError, TypeError, ValueError, ValidationError):
        _fail(ActivationReceiptFailureCode.RECEIPT_INVALID)


class ActivationReceiptStore:
    """Create and reconcile deterministic receipt files from committed history."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, *, tenant_id: UUID, history_sequence: int) -> Path:
        if tenant_id.int == 0 or history_sequence <= 0:
            _fail(ActivationReceiptFailureCode.HISTORY_MISMATCH)
        return self.root / str(tenant_id) / f"{history_sequence:020d}.json"

    async def write_committed(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        history_sequence: int,
        authority: ActivationAuthorityV1,
    ) -> ActivationReceiptArtifactV1:
        """Write only the latest committed pointer event after a live recheck."""

        checked = self._revalidate_authority(authority)
        history = await self._load_history(
            session,
            tenant_id=tenant_id,
            history_sequence=history_sequence,
        )
        self._validate_history(history, authority=checked)
        await self._require_live_pointer(session, history=history)
        previous = await self._previous_receipt(
            session,
            tenant_id=tenant_id,
            history_sequence=history_sequence,
            authority=checked,
        )
        receipt = _build_receipt(history, authority=checked, previous_receipt_sha256=previous)
        return self._persist_expected(receipt)

    async def reconcile_missing(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        authority: ActivationAuthorityV1,
    ) -> tuple[ActivationReceiptArtifactV1, ...]:
        """Rebuild missing files in history order without mutating existing bytes."""

        checked = self._revalidate_authority(authority)
        histories = list(
            (
                await session.execute(
                    select(PolicyCorpusActivationHistory)
                    .where(
                        PolicyCorpusActivationHistory.tenant_id == tenant_id,
                        PolicyCorpusActivationHistory.reason_code.in_(_RECEIPT_REASONS),
                    )
                    .order_by(PolicyCorpusActivationHistory.rollout_epoch)
                )
            ).scalars()
        )
        if not histories:
            return ()
        artifacts: list[ActivationReceiptArtifactV1] = []
        previous_sha256 = ACTIVATION_RECEIPT_GENESIS
        for history in histories:
            self._validate_history(history, authority=checked)
            receipt = _build_receipt(
                history,
                authority=checked,
                previous_receipt_sha256=previous_sha256,
            )
            artifact = self._persist_expected(receipt)
            artifacts.append(artifact)
            previous_sha256 = artifact.file_sha256
        await self._require_live_pointer(session, history=histories[-1])
        return tuple(artifacts)

    def _revalidate_authority(self, authority: ActivationAuthorityV1) -> ActivationAuthorityV1:
        checked = load_activation_authority(authority.paths)
        if checked != authority:
            _fail(ActivationReceiptFailureCode.ARTIFACT_MISMATCH)
        return checked

    @staticmethod
    async def _load_history(
        session: AsyncSession,
        *,
        tenant_id: UUID,
        history_sequence: int,
    ) -> PolicyCorpusActivationHistory:
        rows = list(
            (
                await session.execute(
                    select(PolicyCorpusActivationHistory).where(
                        PolicyCorpusActivationHistory.tenant_id == tenant_id,
                        PolicyCorpusActivationHistory.rollout_epoch == history_sequence,
                    )
                )
            ).scalars()
        )
        if len(rows) != 1:
            _fail(ActivationReceiptFailureCode.HISTORY_UNAVAILABLE)
        return rows[0]

    @staticmethod
    def _validate_history(
        history: PolicyCorpusActivationHistory,
        *,
        authority: ActivationAuthorityV1,
    ) -> None:
        selection = authority.selection
        if (
            history.tenant_id != selection.tenant_id
            or history.from_corpus_version_id is None
            or history.from_corpus_version_id == history.to_corpus_version_id
            or history.rollout_epoch <= 0
            or history.prior_rollout_epoch + 1 != history.rollout_epoch
            or history.reason_code not in _RECEIPT_REASONS
            or not history.actor.strip()
            or history.created_at.tzinfo is None
        ):
            _fail(ActivationReceiptFailureCode.HISTORY_MISMATCH)
        selected_id = selection.candidate_corpus_version_id
        if history.reason_code in {"selected_cutover", "restore_selected"}:
            if (
                history.to_corpus_version_id != selected_id
                or history.selection_decision_hash != authority.selection_decision_sha256
            ):
                _fail(ActivationReceiptFailureCode.HISTORY_MISMATCH)
        elif (
            history.from_corpus_version_id != selected_id
            or history.to_corpus_version_id == selected_id
            or history.selection_decision_hash is not None
        ):
            _fail(ActivationReceiptFailureCode.HISTORY_MISMATCH)

    @staticmethod
    async def _require_live_pointer(
        session: AsyncSession,
        *,
        history: PolicyCorpusActivationHistory,
    ) -> None:
        rollout = (
            await session.execute(select(PolicyCorpusRollout).where(PolicyCorpusRollout.tenant_id == history.tenant_id))
        ).scalar_one_or_none()
        if (
            rollout is None
            or rollout.active_corpus_version_id != history.to_corpus_version_id
            or rollout.previous_corpus_version_id != history.from_corpus_version_id
            or rollout.rollout_epoch != history.rollout_epoch
        ):
            _fail(ActivationReceiptFailureCode.LIVE_POINTER_MISMATCH)

    async def _previous_receipt(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        history_sequence: int,
        authority: ActivationAuthorityV1,
    ) -> str:
        previous = (
            await session.execute(
                select(PolicyCorpusActivationHistory)
                .where(
                    PolicyCorpusActivationHistory.tenant_id == tenant_id,
                    PolicyCorpusActivationHistory.reason_code.in_(_RECEIPT_REASONS),
                    PolicyCorpusActivationHistory.rollout_epoch < history_sequence,
                )
                .order_by(PolicyCorpusActivationHistory.rollout_epoch.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if previous is None:
            return ACTIVATION_RECEIPT_GENESIS
        self._validate_history(previous, authority=authority)
        path = self.path_for(tenant_id=tenant_id, history_sequence=previous.rollout_epoch)
        if not path.is_file():
            _fail(ActivationReceiptFailureCode.PREVIOUS_RECEIPT_MISSING)
        try:
            receipt = load_activation_receipt(path)
        except ActivationReceiptError:
            _fail(ActivationReceiptFailureCode.PREVIOUS_RECEIPT_MISSING)
        expected = _build_receipt(
            previous,
            authority=authority,
            previous_receipt_sha256=receipt.previous_receipt_sha256,
        )
        if receipt != expected:
            _fail(ActivationReceiptFailureCode.PREVIOUS_RECEIPT_MISSING)
        return _sha256_bytes(path.read_bytes())

    def _persist_expected(self, receipt: ActivationReceiptV1) -> ActivationReceiptArtifactV1:
        path = self.path_for(
            tenant_id=receipt.tenant_id,
            history_sequence=receipt.history_sequence,
        )
        payload = _canonical_receipt_bytes(receipt)
        if path.exists():
            try:
                loaded = load_activation_receipt(path)
                if loaded != receipt or path.read_bytes() != payload:
                    _fail(ActivationReceiptFailureCode.CREATE_CONFLICT)
            except ActivationReceiptError:
                _fail(ActivationReceiptFailureCode.CREATE_CONFLICT)
            return ActivationReceiptArtifactV1(
                path=path,
                file_sha256=_sha256_bytes(payload),
                receipt=receipt,
            )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(prefix=".activation-", suffix=".tmp", dir=path.parent)
            try:
                with os.fdopen(descriptor, "wb") as temporary:
                    temporary.write(payload)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                os.link(temporary_name, path)
            finally:
                Path(temporary_name).unlink(missing_ok=True)
        except FileExistsError:
            return self._persist_expected(receipt)
        except OSError:
            _fail(ActivationReceiptFailureCode.WRITE_FAILED)
        return ActivationReceiptArtifactV1(
            path=path,
            file_sha256=_sha256_bytes(payload),
            receipt=receipt,
        )


def _build_receipt(
    history: PolicyCorpusActivationHistory,
    *,
    authority: ActivationAuthorityV1,
    previous_receipt_sha256: str,
) -> ActivationReceiptV1:
    assert history.from_corpus_version_id is not None
    base: dict[str, Any] = {
        "schema_version": ACTIVATION_RECEIPT_SCHEMA_VERSION,
        "tenant_id": history.tenant_id,
        "history_id": history.id,
        "history_sequence": history.rollout_epoch,
        "event_reason": history.reason_code,
        "from_corpus_version_id": history.from_corpus_version_id,
        "to_corpus_version_id": history.to_corpus_version_id,
        "before_rollout_epoch": history.prior_rollout_epoch,
        "after_rollout_epoch": history.rollout_epoch,
        "db_history_sha256": _db_history_sha256(history),
        "actor": history.actor,
        "committed_at": history.created_at.astimezone(UTC),
        "selection_decision_sha256": authority.selection_decision_sha256,
        "selection_payload_sha256": authority.selection.decision_payload_sha256,
        "terminal_run_sha256": authority.terminal_run_sha256,
        "provider_parity_report_sha256": authority.provider_parity_report_sha256,
        "recovery_authorization_sha256": authority.recovery_authorization_sha256,
        "candidate_run_token": authority.selection.candidate_run_token,
        "candidate_lease_owner": authority.selection.candidate_lease_owner,
        "source_manifest_hash": authority.selection.source_manifest_hash,
        "config_fingerprint": authority.config_fingerprint,
        "previous_receipt_sha256": previous_receipt_sha256,
    }
    return ActivationReceiptV1(
        **base,
        receipt_payload_sha256=_sha256_json(_jsonable(base)),
    )


def _db_history_sha256(history: PolicyCorpusActivationHistory) -> str:
    return _sha256_json(
        {
            "schema_version": "policy_corpus_activation_history.v1",
            "id": str(history.id),
            "tenant_id": str(history.tenant_id),
            "from_corpus_version_id": (
                str(history.from_corpus_version_id) if history.from_corpus_version_id is not None else None
            ),
            "to_corpus_version_id": str(history.to_corpus_version_id),
            "prior_rollout_epoch": history.prior_rollout_epoch,
            "rollout_epoch": history.rollout_epoch,
            "reason_code": history.reason_code,
            "actor": history.actor,
            "selection_decision_hash": history.selection_decision_hash,
            "receipt_hash": history.receipt_hash,
            "created_at": history.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        }
    )


def _canonical_receipt_bytes(receipt: ActivationReceiptV1) -> bytes:
    return (
        json.dumps(
            receipt.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=_json_default, ensure_ascii=False))


def _json_default(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    raise TypeError


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return _sha256_bytes(encoded)


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _valid_sha256(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _fail(code: ActivationReceiptFailureCode) -> None:
    raise ActivationReceiptError(code)
