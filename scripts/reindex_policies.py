from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4

from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from sqlalchemy import select

from src.db.models import EvidenceIdentityRollout, PolicyCorpusVersion
from src.db.session import SessionLocal
from src.rag.activation_receipt import (
    ActivationArtifactPaths,
    ActivationReceiptStore,
    load_activation_authority,
)
from src.rag.embedding_tokenizer import load_embedding_tokenizer_config
from src.rag.embedder import EmbeddingService
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler
from src.rag.policy_reindex import (
    POLICY_REINDEX_OWNER_MARKER,
    PROVIDER_EXECUTION_ENVELOPE_CONTRACT_HASH,
    FreshProviderParityClaimV1,
    PolicyCorpusActivationReason,
    PolicyCorpusActivationRequest,
    PolicyReindexClaimRequest,
    PolicyReindexError,
    PolicyReindexFailureCode,
    PolicyReindexRunIdentity,
    PolicyReindexService,
    ReviewedPolicyCandidateBuildService,
)
from src.rag.policy_reindex_artifacts import (
    CandidateBuildResultCode,
    PolicyReindexArtifactError,
    PolicyReindexImmutableArtifactV1,
    build_policy_candidate_build_budget,
    build_policy_reindex_recovery_descriptor,
    load_candidate_build_attempt,
    load_policy_candidate_build_budget,
    load_policy_reindex_recovery_descriptor,
    load_policy_reindex_state,
    policy_candidate_build_attempt_path,
    policy_candidate_build_budget_path,
    policy_candidate_build_result_path,
    policy_reindex_descriptor_path,
    policy_reindex_state_path,
    record_candidate_build_result_create_only,
    reviewed_artifact_list_json,
    reviewed_artifact_path_exists,
    reviewed_artifact_read_bytes,
    reviewed_artifact_revalidate_namespace,
    require_candidate_build_budget_complete,
    secure_policy_reindex_artifact_namespace,
    write_policy_candidate_build_budget_create_only,
    write_policy_reindex_compat_identity_create_only,
    write_policy_reindex_recovery_descriptor_create_only,
    write_policy_reindex_state_create_only,
)
from src.rag.provider_execution_authority import (
    ProviderExecutionAuthorityRequestV1,
    ProviderExecutionAuthorityService,
)
from src.rag.tokenizer_parity import require_fresh_provider_parity
from src.repositories.policy_corpus_repo import PolicyCorpusRepository
from src.repositories.provider_execution_authority_repo import ProviderExecutionAuthorityRepository


DEFAULT_ACTIVATION_ROOT = Path("evaluation/reports/rag_token_chunk_ab/v1/activations")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REVIEWED_CANDIDATE_RELATIVE_ROOT = Path("evaluation/reports/rag_token_chunk_ab/v1/candidates")
LIVE_PROVIDER_EXECUTION_DISABLED = "live_provider_execution_disabled"
REVIEWED_AUTHORITY_PROJECTION_FILENAME = "provider-authority.v2.json"


def _refuse_live_provider_execution() -> int:
    print(
        json.dumps(
            {
                "error": LIVE_PROVIDER_EXECUTION_DISABLED,
                "reason_code": LIVE_PROVIDER_EXECUTION_DISABLED,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 4


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claim or resume one inactive policy reindex candidate.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    claim = subcommands.add_parser("claim")
    claim.add_argument("--tenant-id", type=UUID, required=True)
    claim.add_argument("--run-token", type=UUID, default=None)
    claim.add_argument("--lease-owner", required=True)
    claim.add_argument("--lease-minutes", type=int, default=15)
    claim.add_argument("--parity-report", type=Path, required=True)
    claim.add_argument("--probe-fixture-hash", required=True)
    claim.add_argument("--submitted-content-hash", required=True)
    claim.add_argument("--state-path", type=Path, required=True)

    seal_descriptor = subcommands.add_parser("seal-descriptor")
    seal_descriptor.add_argument("--tenant-id", type=UUID, required=True)
    seal_descriptor.add_argument("--run-token", type=UUID, required=True)
    seal_descriptor.add_argument("--generation-name", required=True)
    seal_descriptor.add_argument("--lease-owner", required=True)
    seal_descriptor.add_argument("--lease-minutes", type=int, default=120)
    seal_descriptor.add_argument("--parity-report", type=Path, required=True)
    seal_descriptor.add_argument("--probe-fixture-hash", required=True)
    seal_descriptor.add_argument("--submitted-content-hash", required=True)
    seal_descriptor.add_argument("--artifact-root", type=Path, required=True)

    claim_reviewed = subcommands.add_parser("claim-reviewed")
    _add_reviewed_identity_args(claim_reviewed)
    recover_state = subcommands.add_parser("recover-state")
    _add_reviewed_identity_args(recover_state)
    issue_provider_authority = subcommands.add_parser("issue-provider-authority")
    _add_reviewed_identity_args(issue_provider_authority)
    issue_provider_authority.add_argument("--parity-report", type=Path, required=True)
    build_next_reviewed = subcommands.add_parser("build-next-reviewed")
    _add_reviewed_identity_args(build_next_reviewed)
    build_next_reviewed.add_argument("--authority-id", type=UUID, required=True)
    build_next_reviewed.add_argument("--ordinal", type=int, choices=(1, 2), required=True)
    validate_reviewed = subcommands.add_parser("validate-reviewed")
    _add_reviewed_identity_args(validate_reviewed)

    resume = subcommands.add_parser("resume")
    resume.add_argument("--state-path", type=Path, required=True)
    resume.add_argument("--output-state-path", type=Path, required=True)
    build = subcommands.add_parser("build-next")
    build.add_argument("--state-path", type=Path, required=True)
    build.add_argument("--output-state-path", type=Path, required=True)
    validate = subcommands.add_parser("validate")
    validate.add_argument("--state-path", type=Path, required=True)
    validate.add_argument("--output-state-path", type=Path, required=True)
    activate = subcommands.add_parser("activate")
    activate.add_argument("--tenant-id", type=UUID, required=True)
    activate.add_argument("--target-corpus-id", type=UUID, required=True)
    activate.add_argument("--expected-active-corpus-id", type=UUID, required=True)
    activate.add_argument("--expected-rollout-epoch", type=int, required=True)
    activate.add_argument("--expected-evidence-rollout-version", type=int, required=True)
    activate.add_argument("--actor", required=True)
    activate.add_argument(
        "--reason",
        choices=tuple(reason.value for reason in PolicyCorpusActivationReason),
        required=True,
    )
    _add_activation_artifact_args(activate)
    reconcile = subcommands.add_parser("reconcile-receipts")
    reconcile.add_argument("--tenant-id", type=UUID, required=True)
    _add_activation_artifact_args(reconcile)
    return parser.parse_args()


def _add_activation_artifact_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--terminal-run", type=Path, required=True)
    parser.add_argument("--parity-report", type=Path, required=True)
    parser.add_argument("--recovery-authorization", type=Path, required=True)
    parser.add_argument("--recovery-budget-manifest", type=Path, required=True)
    parser.add_argument("--recovery-reservation", type=Path, required=True)
    parser.add_argument("--candidate-state", type=Path, required=True)
    parser.add_argument("--activation-root", type=Path, default=DEFAULT_ACTIVATION_ROOT)


def _add_reviewed_identity_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--run-token", type=UUID, required=True)


def _require_canonical_reviewed_root(args: argparse.Namespace) -> Path:
    """Establish reviewed artifact authority without resolving production identity."""

    # Tests may inject a temporary canonical root through an attribute argparse
    # never creates. Production callers can only submit ``--artifact-root`` and
    # must match the repository-owned namespace exactly.
    injected = getattr(args, "_reviewed_root_for_testing", None)
    requested = Path(os.path.abspath(args.artifact_root))
    if injected is not None:
        injected_lexical = Path(os.path.abspath(injected))
        if requested != injected_lexical:
            raise RuntimeError("reviewed_artifact_root_invalid")
        try:
            canonical = Path(injected).resolve(strict=True)
        except OSError:
            raise RuntimeError("reviewed_artifact_root_invalid") from None
        _require_real_directory_ancestors(canonical)
        args.artifact_root = canonical
        return canonical

    canonical = Path(os.path.abspath(REPOSITORY_ROOT / REVIEWED_CANDIDATE_RELATIVE_ROOT))
    _require_real_directory_ancestors(canonical)
    if requested != canonical:
        raise RuntimeError("reviewed_artifact_root_invalid")
    args.artifact_root = canonical
    return canonical


def _require_real_directory_ancestors(path: Path) -> None:
    """Reject every lexical symlink/non-directory before secure namespace I/O."""

    current = path
    while True:
        try:
            metadata = os.lstat(current)
        except OSError:
            raise RuntimeError("reviewed_artifact_root_invalid") from None
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise RuntimeError("reviewed_artifact_root_invalid")
        if current == current.parent:
            break
        current = current.parent


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _secure_reviewed_artifact_command(
    *,
    create_run: bool = False,
) -> Callable[[Callable[[argparse.Namespace], Awaitable[Any]]], Callable[[argparse.Namespace], Awaitable[Any]]]:
    def decorate(
        function: Callable[[argparse.Namespace], Awaitable[Any]],
    ) -> Callable[[argparse.Namespace], Awaitable[Any]]:
        @wraps(function)
        async def secured(args: argparse.Namespace) -> Any:
            artifact_root = _require_canonical_reviewed_root(args)
            try:
                with secure_policy_reindex_artifact_namespace(
                    artifact_root,
                    tenant_id=args.tenant_id,
                    run_token=args.run_token,
                    create_run=create_run,
                ):
                    return await function(args)
            except PolicyReindexArtifactError as error:
                if str(error) == "artifact_namespace_invalid":
                    raise RuntimeError("reviewed_artifact_namespace_invalid") from None
                raise

        return secured

    return decorate


async def _claim(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    now = _utc_now()
    config = load_embedding_tokenizer_config()
    parity = require_fresh_provider_parity(
        args.parity_report,
        config=config,
        expected_probe_fixture_sha256=args.probe_fixture_hash,
        expected_submitted_content_sha256=args.submitted_content_hash,
        now=now,
    )
    parity_report_hash = "sha256:" + hashlib.sha256(args.parity_report.read_bytes()).hexdigest()
    run_token = args.run_token or uuid4()
    config_payload = asdict(config)
    config_payload.pop("config_fingerprint")
    config_payload.pop("_asset_root")
    async with SessionLocal() as session:
        async with session.begin():
            corpora = PolicyCorpusRepository(session)
            rollout = await corpora.acquire_tenant_rollout_lock(tenant_id=args.tenant_id)
            manifest = await corpora.lock_latest_manifest(tenant_id=args.tenant_id)
            evidence_rollout = (
                await session.execute(select(EvidenceIdentityRollout).where(EvidenceIdentityRollout.id == 1))
            ).scalar_one()
            request = PolicyReindexClaimRequest(
                tenant_id=args.tenant_id,
                run_token=run_token,
                generation_name=f"token.v1:{run_token.hex}",
                lease_owner=args.lease_owner,
                lease_expires_at=now + timedelta(minutes=args.lease_minutes),
                config_schema_version=config.schema_version,
                config_json=config_payload,
                config_fingerprint=config.config_fingerprint,
                parity=FreshProviderParityClaimV1(
                    report_hash=parity_report_hash,
                    config_fingerprint=parity.config_fingerprint,
                    captured_at=parity.captured_at,
                    status="passed",
                ),
                source_manifest_revision_id=manifest.id,
                source_manifest_revision=manifest.revision,
                source_manifest_hash=manifest.manifest_hash,
                source_active_corpus_version_id=rollout.active_corpus_version_id,
                source_rollout_epoch=rollout.rollout_epoch,
                expected_evidence_rollout_version=evidence_rollout.rollout_version,
            )
            return await PolicyReindexService(session).claim(request, now=now)


@_secure_reviewed_artifact_command(create_run=True)
async def _seal_descriptor(args: argparse.Namespace):
    artifact_root = _require_canonical_reviewed_root(args)
    now = datetime.now(UTC)
    if type(args.lease_minutes) is not int or not 0 < args.lease_minutes <= 120:
        raise RuntimeError("descriptor_lease_window_invalid")
    config = load_embedding_tokenizer_config()
    parity = require_fresh_provider_parity(
        args.parity_report,
        config=config,
        expected_probe_fixture_sha256=args.probe_fixture_hash,
        expected_submitted_content_sha256=args.submitted_content_hash,
        now=now,
    )
    config_payload = asdict(config)
    config_payload.pop("config_fingerprint")
    config_payload.pop("_asset_root")
    async with SessionLocal() as session:
        async with session.begin():
            corpora = PolicyCorpusRepository(session)
            rollout = await corpora.acquire_tenant_rollout_lock(tenant_id=args.tenant_id)
            manifest = await corpora.lock_latest_manifest(tenant_id=args.tenant_id)
            evidence_rollout = (
                await session.execute(select(EvidenceIdentityRollout).where(EvidenceIdentityRollout.id == 1))
            ).scalar_one()
    descriptor = build_policy_reindex_recovery_descriptor(
        sealed_at=now,
        tenant_id=args.tenant_id,
        run_token=args.run_token,
        generation_name=args.generation_name,
        lease_owner=args.lease_owner,
        lease_expires_at=now + timedelta(minutes=args.lease_minutes),
        config_schema_version=config.schema_version,
        config_json=config_payload,
        config_fingerprint=config.config_fingerprint,
        parity_report_sha256="sha256:" + hashlib.sha256(args.parity_report.read_bytes()).hexdigest(),
        parity_config_fingerprint=parity.config_fingerprint,
        parity_probe_fixture_sha256=parity.probe_fixture_sha256,
        parity_submitted_content_sha256=parity.submitted_content_sha256,
        parity_captured_at=parity.captured_at,
        parity_expires_at=parity.captured_at + timedelta(hours=24),
        source_manifest_revision_id=manifest.id,
        source_manifest_revision=manifest.revision,
        source_manifest_hash=manifest.manifest_hash,
        source_active_corpus_version_id=rollout.active_corpus_version_id,
        source_rollout_epoch=rollout.rollout_epoch,
        expected_evidence_rollout_version=evidence_rollout.rollout_version,
    )
    return write_policy_reindex_recovery_descriptor_create_only(descriptor, root=artifact_root)


def _reviewed_descriptor(args: argparse.Namespace):
    artifact_root = _require_canonical_reviewed_root(args)
    path = policy_reindex_descriptor_path(
        artifact_root,
        tenant_id=args.tenant_id,
        run_token=args.run_token,
    )
    return load_policy_reindex_recovery_descriptor(path, root=artifact_root)


def _provider_execution_authority_service() -> ProviderExecutionAuthorityService:
    repository = ProviderExecutionAuthorityRepository(SessionLocal, project_entry=REPOSITORY_ROOT)
    return ProviderExecutionAuthorityService(repository)


def _reviewed_authority_issued_projection_path(args: argparse.Namespace) -> Path:
    return (
        args.artifact_root
        / "tenants"
        / str(args.tenant_id)
        / "runs"
        / str(args.run_token)
        / REVIEWED_AUTHORITY_PROJECTION_FILENAME
    )


def _reviewed_authority_result_projection_path(
    args: argparse.Namespace,
    *,
    document_index: int,
    ordinal: int,
) -> Path:
    return (
        args.artifact_root
        / "tenants"
        / str(args.tenant_id)
        / "runs"
        / str(args.run_token)
        / f"provider-authority.document-{document_index:08d}.ordinal-{ordinal:02d}.v2.json"
    )


async def _derive_provider_authority_request(args: argparse.Namespace) -> ProviderExecutionAuthorityRequestV1:
    async with SessionLocal() as session:
        candidate = (
            await session.execute(
                select(PolicyCorpusVersion).where(
                    PolicyCorpusVersion.tenant_id == args.tenant_id,
                    PolicyCorpusVersion.run_token == args.run_token,
                )
            )
        ).scalar_one_or_none()
        if candidate is None:
            raise PolicyReindexError(PolicyReindexFailureCode.AUTHORITY_UNAVAILABLE)
        proof = candidate.validation_proof_json if isinstance(candidate.validation_proof_json, dict) else None
        claim = proof.get("claim") if proof is not None else None
        descriptor_binding = proof.get("recovery_descriptor") if proof is not None else None
        if not isinstance(claim, dict) or not isinstance(descriptor_binding, dict):
            raise PolicyReindexError(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH)
        try:
            parity_captured_at = datetime.fromisoformat(str(claim["parity_captured_at"]))
            parity_expires_at = datetime.fromisoformat(str(claim["parity_expires_at"]))
            probe_fixture_sha256 = str(descriptor_binding["parity_probe_fixture_sha256"])
            submitted_content_sha256 = str(descriptor_binding["parity_submitted_content_sha256"])
        except (KeyError, TypeError, ValueError):
            raise PolicyReindexError(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH) from None
        if parity_captured_at.tzinfo is None or parity_expires_at.tzinfo is None:
            raise PolicyReindexError(PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH)
        candidate_values = {
            "candidate_id": candidate.id,
            "owner_marker": candidate.owner_marker,
            "config_schema_version": candidate.config_schema_version,
            "config_json": dict(candidate.config_json or {}),
            "config_fingerprint": candidate.config_fingerprint,
            "provider_parity_report_hash": candidate.provider_parity_report_hash,
            "source_manifest_revision_id": candidate.source_manifest_revision_id,
            "source_manifest_hash": candidate.source_manifest_hash,
            "source_active_corpus_version_id": candidate.source_active_corpus_version_id,
            "source_rollout_epoch": candidate.source_rollout_epoch,
            "evidence_rollout_version": candidate.expected_evidence_rollout_version,
            "candidate_lease_expires_at": candidate.lease_expires_at,
        }

    config = load_embedding_tokenizer_config()
    config_payload = asdict(config)
    config_payload.pop("config_fingerprint")
    config_payload.pop("_asset_root")
    if (
        candidate_values["owner_marker"] != POLICY_REINDEX_OWNER_MARKER
        or candidate_values["config_schema_version"] != config.schema_version
        or candidate_values["config_json"] != config_payload
        or candidate_values["config_fingerprint"] != config.config_fingerprint
    ):
        raise PolicyReindexError(PolicyReindexFailureCode.CONFIG_DRIFT)
    report = require_fresh_provider_parity(
        args.parity_report,
        config=config,
        expected_probe_fixture_sha256=probe_fixture_sha256,
        expected_submitted_content_sha256=submitted_content_sha256,
    )
    try:
        parity_report_hash = "sha256:" + hashlib.sha256(args.parity_report.read_bytes()).hexdigest()
    except OSError:
        raise PolicyReindexError(PolicyReindexFailureCode.PARITY_DRIFT) from None
    if parity_report_hash != candidate_values["provider_parity_report_hash"] or report.captured_at.astimezone(
        UTC
    ) != parity_captured_at.astimezone(UTC):
        raise PolicyReindexError(PolicyReindexFailureCode.PARITY_DRIFT)
    required_values = (
        candidate_values["source_manifest_revision_id"],
        candidate_values["source_manifest_hash"],
        candidate_values["source_active_corpus_version_id"],
        candidate_values["source_rollout_epoch"],
        candidate_values["evidence_rollout_version"],
        candidate_values["candidate_lease_expires_at"],
    )
    if any(value is None for value in required_values):
        raise PolicyReindexError(PolicyReindexFailureCode.SOURCE_POINTER_DRIFT)
    candidate_lease_expires_at = candidate_values["candidate_lease_expires_at"]
    assert isinstance(candidate_lease_expires_at, datetime)
    return ProviderExecutionAuthorityRequestV1(
        tenant_id=args.tenant_id,
        run_token=args.run_token,
        candidate_id=candidate_values["candidate_id"],
        owner_marker=POLICY_REINDEX_OWNER_MARKER,
        config_schema_version=config.schema_version,
        config_json=config_payload,
        config_fingerprint=config.config_fingerprint,
        provider_parity_run_id=report.run_id,
        provider_parity_report_hash=parity_report_hash,
        provider_parity_probe_fixture_sha256=report.probe_fixture_sha256,
        provider_parity_submitted_content_sha256=report.submitted_content_sha256,
        parity_captured_at=parity_captured_at,
        parity_expires_at=parity_expires_at,
        source_manifest_revision_id=candidate_values["source_manifest_revision_id"],
        source_manifest_hash=candidate_values["source_manifest_hash"],
        source_active_corpus_version_id=candidate_values["source_active_corpus_version_id"],
        source_rollout_epoch=candidate_values["source_rollout_epoch"],
        evidence_rollout_version=candidate_values["evidence_rollout_version"],
        candidate_lease_expires_at=candidate_lease_expires_at,
        expires_at=min(parity_expires_at, candidate_lease_expires_at),
        provider_name=config.provider,
        model_name=config.model,
        dimensions=config.dimensions,
        envelope_contract_hash=PROVIDER_EXECUTION_ENVELOPE_CONTRACT_HASH,
    )


@_secure_reviewed_artifact_command()
async def _issue_provider_authority(args: argparse.Namespace):
    request = await _derive_provider_authority_request(args)
    authority_service = _provider_execution_authority_service()
    authority = await authority_service.issue_authority_root(request)
    reviewed_artifact_revalidate_namespace()
    projection = await authority_service.reconcile_projection(
        authority_id=authority.authority_id,
        projection_path=_reviewed_authority_issued_projection_path(args),
    )
    reviewed_artifact_revalidate_namespace()
    return authority, projection


def _ensure_reviewed_budget(args: argparse.Namespace, *, descriptor, owner):
    budget = build_policy_candidate_build_budget(
        descriptor=descriptor,
        ordered_doc_keys=owner.ordered_doc_keys,
        created_at=descriptor.sealed_at,
    )
    artifact = write_policy_candidate_build_budget_create_only(
        budget,
        descriptor=descriptor,
        root=args.artifact_root,
    )
    return budget, artifact


def _load_reviewed_budget(args: argparse.Namespace, *, descriptor):
    path = policy_candidate_build_budget_path(
        args.artifact_root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
    )
    budget = load_policy_candidate_build_budget(
        path,
        descriptor=descriptor,
        root=args.artifact_root,
    )
    return budget, PolicyReindexImmutableArtifactV1(path=path, sha256=budget.budget_payload_sha256)


@_secure_reviewed_artifact_command()
async def _claim_reviewed(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    descriptor = _reviewed_descriptor(args)
    checked_at = _utc_now()
    if checked_at >= descriptor.lease_expires_at or checked_at >= descriptor.parity_expires_at:
        raise RuntimeError("reindex_claim_authority_expired")
    async with SessionLocal() as session:
        async with session.begin():
            service = PolicyReindexService(session)
            claimed = await service.claim_from_descriptor(descriptor, now=checked_at)
    v1_path = policy_reindex_state_path(
        args.artifact_root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
        state_version=1,
    )
    if claimed.state == "claimed" and claimed.state_version == 1 and claimed.next_document_index == 0:
        write_policy_reindex_state_create_only(claimed, descriptor=descriptor, root=args.artifact_root)
    elif not reviewed_artifact_path_exists(v1_path):
        raise RuntimeError("reindex_state_predecessor_missing")

    checked_at = _utc_now()
    if checked_at >= descriptor.lease_expires_at or checked_at >= descriptor.parity_expires_at:
        raise RuntimeError("reindex_claim_authority_expired")
    async with SessionLocal() as session:
        async with session.begin():
            service = PolicyReindexService(session)
            current = await service.recover_identity(descriptor, now=checked_at)
            owner = await service.resume(current, now=checked_at)
    write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=args.artifact_root)
    _ensure_reviewed_budget(args, descriptor=descriptor, owner=owner)
    return owner


def _derive_exact_initial_claim_predecessor(
    current: PolicyReindexRunIdentity,
    *,
    canonical_v2: PolicyReindexRunIdentity,
    descriptor,
) -> PolicyReindexRunIdentity:
    if (
        current != canonical_v2
        or current.tenant_id != descriptor.tenant_id
        or current.run_token != descriptor.run_token
        or current.state != "building"
        or current.state_version != 2
        or current.next_document_index != 0
    ):
        raise RuntimeError("reindex_initial_predecessor_invalid")
    return replace(current, state="claimed", state_version=1)


@_secure_reviewed_artifact_command()
async def _recover_state(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    descriptor = _reviewed_descriptor(args)
    checked_at = datetime.now(UTC)
    if checked_at >= descriptor.lease_expires_at or checked_at >= descriptor.parity_expires_at:
        raise RuntimeError("reindex_recovery_authority_expired")
    async with SessionLocal() as session:
        async with session.begin():
            owner = await PolicyReindexService(session).recover_identity(descriptor, now=checked_at)
    v1_path = policy_reindex_state_path(
        args.artifact_root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
        state_version=1,
    )
    v2_path = policy_reindex_state_path(
        args.artifact_root,
        tenant_id=descriptor.tenant_id,
        run_token=descriptor.run_token,
        state_version=2,
    )
    if not reviewed_artifact_path_exists(v1_path):
        if reviewed_artifact_path_exists(v2_path):
            canonical_v2 = load_policy_reindex_state(
                v2_path,
                descriptor=descriptor,
                root=args.artifact_root,
            )
            predecessor = _derive_exact_initial_claim_predecessor(
                owner,
                canonical_v2=canonical_v2,
                descriptor=descriptor,
            )
            write_policy_reindex_state_create_only(
                predecessor,
                descriptor=descriptor,
                root=args.artifact_root,
            )
        elif owner.state_version != 1:
            raise RuntimeError("reindex_state_invalid")
    elif owner.state_version > 1:
        current_path = policy_reindex_state_path(
            args.artifact_root,
            tenant_id=descriptor.tenant_id,
            run_token=descriptor.run_token,
            state_version=owner.state_version,
        )
        last_existing_version = (
            owner.state_version if reviewed_artifact_path_exists(current_path) else owner.state_version - 1
        )
        expected = [f"{version:08d}.json" for version in range(1, last_existing_version + 1)]
        if [path.name for path in reviewed_artifact_list_json(v1_path.parent)] != expected:
            raise RuntimeError("reindex_state_invalid")
    state_artifact = write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=args.artifact_root)
    budget, budget_artifact = _ensure_reviewed_budget(args, descriptor=descriptor, owner=owner)
    _reconcile_committed_build(
        args,
        descriptor=descriptor,
        owner=owner,
        state_artifact=state_artifact,
        budget=budget,
        budget_artifact=budget_artifact,
    )
    return owner


def _latest_reviewed_state_artifact(args: argparse.Namespace, *, descriptor):
    state_root = (
        args.artifact_root / "tenants" / str(descriptor.tenant_id) / "runs" / str(descriptor.run_token) / "states"
    )
    paths = reviewed_artifact_list_json(state_root)
    expected_names = [f"{ordinal:08d}.json" for ordinal in range(1, len(paths) + 1)]
    if [path.name for path in paths] != expected_names or not paths:
        raise RuntimeError("reindex_state_invalid")
    path = paths[-1]
    owner = load_policy_reindex_state(path, descriptor=descriptor, root=args.artifact_root)
    artifact = PolicyReindexImmutableArtifactV1(
        path=path,
        sha256="sha256:" + hashlib.sha256(reviewed_artifact_read_bytes(path)).hexdigest(),
    )
    return owner, artifact


def _load_latest_reviewed_state(args: argparse.Namespace, *, descriptor):
    return _latest_reviewed_state_artifact(args, descriptor=descriptor)[0]


def _reconcile_committed_build(
    args: argparse.Namespace,
    *,
    descriptor,
    owner: PolicyReindexRunIdentity,
    state_artifact: PolicyReindexImmutableArtifactV1,
    budget,
    budget_artifact: PolicyReindexImmutableArtifactV1,
) -> None:
    if owner.next_document_index == 0:
        return
    document_index = owner.next_document_index - 1
    for ordinal in range(budget.max_build_executions_per_document, 0, -1):
        attempt_path = policy_candidate_build_attempt_path(
            args.artifact_root,
            tenant_id=descriptor.tenant_id,
            run_token=descriptor.run_token,
            document_index=document_index,
            ordinal=ordinal,
        )
        if not reviewed_artifact_path_exists(attempt_path):
            continue
        result_path = policy_candidate_build_result_path(
            args.artifact_root,
            tenant_id=descriptor.tenant_id,
            run_token=descriptor.run_token,
            document_index=document_index,
            ordinal=ordinal,
        )
        if reviewed_artifact_path_exists(result_path):
            return
        reservation = load_candidate_build_attempt(
            attempt_path,
            descriptor=descriptor,
            budget=budget,
            budget_artifact=budget_artifact,
            root=args.artifact_root,
        )
        if (
            reservation.document_index != document_index
            or reservation.state_version + 1 != owner.state_version
            or reservation.next_document_index + 1 != owner.next_document_index
        ):
            raise RuntimeError("build_recovery_state_mismatch")
        record_candidate_build_result_create_only(
            descriptor=descriptor,
            owner=owner,
            budget=budget,
            budget_artifact=budget_artifact,
            reservation=reservation,
            root=args.artifact_root,
            recorded_at=datetime.now(UTC),
            result_code=CandidateBuildResultCode.SUCCESS,
            provider_request_count=reservation.expected_batch_count,
            post_state_artifact=state_artifact,
        )
        return


def _safe_build_result_code(error: Exception) -> CandidateBuildResultCode:
    if isinstance(error, (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)):
        return CandidateBuildResultCode.PROVIDER_TRANSIENT
    if isinstance(error, PolicyReindexError):
        if error.code is PolicyReindexFailureCode.CONFIG_DRIFT:
            return CandidateBuildResultCode.CONFIG_ERROR
        if error.code in {PolicyReindexFailureCode.PARITY_DRIFT, PolicyReindexFailureCode.PARITY_STALE}:
            return CandidateBuildResultCode.PARITY_ERROR
        if error.code in {
            PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT,
            PolicyReindexFailureCode.SOURCE_POINTER_DRIFT,
            PolicyReindexFailureCode.SOURCE_SNAPSHOT_DRIFT,
            PolicyReindexFailureCode.OBSOLETE_SOURCE,
        }:
            return CandidateBuildResultCode.SOURCE_ERROR
        if error.code is PolicyReindexFailureCode.EMBEDDING_PROOF_FAILED:
            return CandidateBuildResultCode.RESPONSE_ERROR
        return CandidateBuildResultCode.PROJECTION_ERROR
    if isinstance(error, RuntimeError) and str(error) == "embedding_response_invalid":
        return CandidateBuildResultCode.RESPONSE_ERROR
    if isinstance(error, RuntimeError) and str(error).startswith("DASHSCOPE_API_KEY not set"):
        return CandidateBuildResultCode.PROVIDER_UNAVAILABLE
    return CandidateBuildResultCode.PROJECTION_ERROR


@_secure_reviewed_artifact_command()
async def _build_next_reviewed(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    descriptor = _reviewed_descriptor(args)
    state_owner, _ = _latest_reviewed_state_artifact(args, descriptor=descriptor)
    assembler = PolicyEmbeddingInputAssembler()
    authority_service = _provider_execution_authority_service()
    reviewed_service = ReviewedPolicyCandidateBuildService(
        SessionLocal,
        authority_service=authority_service,
        provider_factory=EmbeddingService,
    )
    outcome = await reviewed_service.build_next_document(
        state_owner,
        authority_id=args.authority_id,
        assembler=assembler,
        ordinal=args.ordinal,
        projection_path=_reviewed_authority_result_projection_path(
            args,
            document_index=state_owner.next_document_index,
            ordinal=args.ordinal,
        ),
    )
    reviewed_artifact_revalidate_namespace()
    write_policy_reindex_state_create_only(
        outcome.owner,
        descriptor=descriptor,
        root=args.artifact_root,
    )
    return outcome.owner


@_secure_reviewed_artifact_command()
async def _validate_reviewed(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    descriptor = _reviewed_descriptor(args)
    state_owner = _load_latest_reviewed_state(args, descriptor=descriptor)
    budget, budget_artifact = _load_reviewed_budget(args, descriptor=descriptor)
    require_candidate_build_budget_complete(
        descriptor=descriptor,
        owner=state_owner,
        budget=budget,
        budget_artifact=budget_artifact,
        root=args.artifact_root,
    )
    async with SessionLocal() as session:
        async with session.begin():
            service = PolicyReindexService(session)
            current = await service.recover_identity(descriptor)
            if current != state_owner:
                raise RuntimeError("reindex_state_db_mismatch")
            owner = await service.validate_candidate(
                current,
                assembler=PolicyEmbeddingInputAssembler(),
            )
    write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=args.artifact_root)
    return owner


async def _resume(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    owner = _load_identity(args.state_path)
    async with SessionLocal() as session:
        async with session.begin():
            return await PolicyReindexService(session).resume(owner)


async def _build_next(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    owner = _load_identity(args.state_path)
    async with SessionLocal() as session:
        async with session.begin():
            return await PolicyReindexService(session).build_next_document(
                owner,
                assembler=PolicyEmbeddingInputAssembler(),
                embedder=EmbeddingService(),
            )


async def _validate(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    owner = _load_identity(args.state_path)
    async with SessionLocal() as session:
        async with session.begin():
            return await PolicyReindexService(session).validate_candidate(
                owner,
                assembler=PolicyEmbeddingInputAssembler(),
            )


def _activation_authority(args: argparse.Namespace):
    return load_activation_authority(
        ActivationArtifactPaths(
            selection_path=args.selection,
            terminal_run_path=args.terminal_run,
            parity_report_path=args.parity_report,
            recovery_authorization_path=args.recovery_authorization,
            recovery_budget_manifest_path=args.recovery_budget_manifest,
            recovery_reservation_path=args.recovery_reservation,
            candidate_state_path=args.candidate_state,
        ),
        repository_root=REPOSITORY_ROOT,
    )


async def _activate(args: argparse.Namespace) -> dict[str, Any]:
    """Commit the DB event first, then verify live state and create its receipt."""

    authority = _activation_authority(args)
    reason = PolicyCorpusActivationReason(args.reason)
    selection = (
        None
        if reason is PolicyCorpusActivationReason.ROLLBACK_PRIOR
        else authority.to_selection_proof(
            expected_evidence_rollout_version=args.expected_evidence_rollout_version,
        )
    )
    request = PolicyCorpusActivationRequest(
        tenant_id=args.tenant_id,
        target_corpus_version_id=args.target_corpus_id,
        expected_active_corpus_version_id=args.expected_active_corpus_id,
        expected_rollout_epoch=args.expected_rollout_epoch,
        expected_evidence_rollout_version=args.expected_evidence_rollout_version,
        actor=args.actor,
        reason=reason,
        selection=selection,
    )
    async with SessionLocal() as session:
        async with session.begin():
            activated = await PolicyReindexService(session).activate_corpus(request)
    async with SessionLocal() as receipt_session:
        artifact = await ActivationReceiptStore(args.activation_root).write_committed(
            receipt_session,
            tenant_id=args.tenant_id,
            history_sequence=activated.rollout_epoch,
            authority=authority,
        )
        await receipt_session.rollback()
    return {
        "schema_version": "rag_token_chunk_activation_result.v1",
        "tenant_id": str(activated.tenant_id),
        "active_corpus_version_id": str(activated.active_corpus_version_id),
        "previous_corpus_version_id": (
            str(activated.previous_corpus_version_id) if activated.previous_corpus_version_id else None
        ),
        "rollout_epoch": activated.rollout_epoch,
        "receipt_sha256": artifact.file_sha256,
    }


async def _reconcile_receipts(args: argparse.Namespace) -> dict[str, Any]:
    authority = _activation_authority(args)
    async with SessionLocal() as session:
        artifacts = await ActivationReceiptStore(args.activation_root).reconcile_missing(
            session,
            tenant_id=args.tenant_id,
            authority=authority,
        )
        await session.rollback()
    return {
        "schema_version": "rag_token_chunk_activation_reconciliation.v1",
        "tenant_id": str(args.tenant_id),
        "history_sequences": [item.receipt.history_sequence for item in artifacts],
        "receipt_sha256": [item.file_sha256 for item in artifacts],
    }


def _identity_payload(owner: PolicyReindexRunIdentity) -> dict[str, Any]:
    payload = asdict(owner)
    for key, value in tuple(payload.items()):
        if isinstance(value, UUID):
            payload[key] = str(value)
        elif isinstance(value, datetime):
            payload[key] = value.astimezone(UTC).isoformat()
        elif isinstance(value, tuple):
            payload[key] = list(value)
    return {"schema_version": "policy_reindex_run_identity.v1", "identity": payload}


def _write_identity_create_only(path: Path, owner: PolicyReindexRunIdentity) -> None:
    write_policy_reindex_compat_identity_create_only(path, owner)


def _load_identity(path: Path) -> PolicyReindexRunIdentity:
    payload = json.loads(path.read_bytes())
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "identity"}:
        raise RuntimeError("reindex_state_invalid")
    if payload["schema_version"] != "policy_reindex_run_identity.v1" or not isinstance(payload["identity"], dict):
        raise RuntimeError("reindex_state_invalid")
    identity = dict(payload["identity"])
    expected = set(PolicyReindexRunIdentity.__dataclass_fields__)
    if set(identity) != expected:
        raise RuntimeError("reindex_state_invalid")
    for key in (
        "corpus_version_id",
        "tenant_id",
        "run_token",
        "source_manifest_revision_id",
        "source_active_corpus_version_id",
    ):
        identity[key] = UUID(identity[key])
    for key in ("lease_expires_at", "parity_captured_at", "parity_expires_at"):
        identity[key] = datetime.fromisoformat(identity[key]).astimezone(UTC)
    identity["ordered_doc_keys"] = tuple(identity["ordered_doc_keys"])
    return PolicyReindexRunIdentity(**identity)


async def _main() -> int:
    args = _parse_args()
    if args.command == "build-next":
        return _refuse_live_provider_execution()
    if args.command == "claim":
        owner = await _claim(args)
        _write_identity_create_only(args.state_path, owner)
    elif args.command == "seal-descriptor":
        artifact = await _seal_descriptor(args)
        print(json.dumps({"descriptor": str(artifact.path), "sha256": artifact.sha256}, sort_keys=True))
        return 0
    elif args.command == "claim-reviewed":
        owner = await _claim_reviewed(args)
    elif args.command == "recover-state":
        owner = await _recover_state(args)
    elif args.command == "issue-provider-authority":
        authority, projection = await _issue_provider_authority(args)
        print(
            json.dumps(
                {
                    "authority_id": str(authority.authority_id),
                    "projection": str(projection.projection_path),
                    "projection_sha256": projection.projection_sha256,
                },
                sort_keys=True,
            )
        )
        return 0
    elif args.command == "build-next-reviewed":
        owner = await _build_next_reviewed(args)
    elif args.command == "validate-reviewed":
        owner = await _validate_reviewed(args)
    elif args.command == "resume":
        owner = await _resume(args)
        _write_identity_create_only(args.output_state_path, owner)
    elif args.command == "build-next":
        owner = await _build_next(args)
        _write_identity_create_only(args.output_state_path, owner)
    elif args.command == "validate":
        owner = await _validate(args)
        _write_identity_create_only(args.output_state_path, owner)
    elif args.command == "activate":
        print(json.dumps(await _activate(args), sort_keys=True))
        return 0
    else:
        print(json.dumps(await _reconcile_receipts(args), sort_keys=True))
        return 0
    print(json.dumps({"state": owner.state, "state_version": owner.state_version}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
