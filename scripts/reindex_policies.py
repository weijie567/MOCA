from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from src.db.models import EvidenceIdentityRollout
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
    FreshProviderParityClaimV1,
    PolicyCorpusActivationReason,
    PolicyCorpusActivationRequest,
    PolicyReindexClaimRequest,
    PolicyReindexRunIdentity,
    PolicyReindexService,
)
from src.rag.policy_reindex_artifacts import (
    build_policy_reindex_recovery_descriptor,
    load_policy_reindex_recovery_descriptor,
    load_policy_reindex_state,
    policy_reindex_descriptor_path,
    write_policy_reindex_compat_identity_create_only,
    write_policy_reindex_recovery_descriptor_create_only,
    write_policy_reindex_state_create_only,
)
from src.rag.tokenizer_parity import require_fresh_provider_parity
from src.repositories.policy_corpus_repo import PolicyCorpusRepository


DEFAULT_ACTIVATION_ROOT = Path("evaluation/reports/rag_token_chunk_ab/v1/activations")


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
    parser.add_argument("--activation-root", type=Path, default=DEFAULT_ACTIVATION_ROOT)


def _add_reviewed_identity_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--run-token", type=UUID, required=True)


async def _claim(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    now = datetime.now(UTC)
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


async def _seal_descriptor(args: argparse.Namespace):
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
    return write_policy_reindex_recovery_descriptor_create_only(descriptor, root=args.artifact_root)


def _reviewed_descriptor(args: argparse.Namespace):
    path = policy_reindex_descriptor_path(
        args.artifact_root,
        tenant_id=args.tenant_id,
        run_token=args.run_token,
    )
    return load_policy_reindex_recovery_descriptor(path, root=args.artifact_root)


async def _claim_reviewed(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    descriptor = _reviewed_descriptor(args)
    async with SessionLocal() as session:
        async with session.begin():
            owner = await PolicyReindexService(session).claim_from_descriptor(descriptor)
    write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=args.artifact_root)
    return owner


async def _recover_state(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    descriptor = _reviewed_descriptor(args)
    async with SessionLocal() as session:
        async with session.begin():
            owner = await PolicyReindexService(session).recover_identity(descriptor)
    write_policy_reindex_state_create_only(owner, descriptor=descriptor, root=args.artifact_root)
    return owner


def _load_latest_reviewed_state(args: argparse.Namespace, *, descriptor):
    state_root = (
        args.artifact_root / "tenants" / str(descriptor.tenant_id) / "runs" / str(descriptor.run_token) / "states"
    )
    paths = sorted(state_root.glob("*.json")) if state_root.is_dir() else []
    expected_names = [f"{ordinal:08d}.json" for ordinal in range(1, len(paths) + 1)]
    if [path.name for path in paths] != expected_names or not paths:
        raise RuntimeError("reindex_state_invalid")
    return load_policy_reindex_state(paths[-1], descriptor=descriptor, root=args.artifact_root)


async def _validate_reviewed(args: argparse.Namespace) -> PolicyReindexRunIdentity:
    descriptor = _reviewed_descriptor(args)
    state_owner = _load_latest_reviewed_state(args, descriptor=descriptor)
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
        )
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
