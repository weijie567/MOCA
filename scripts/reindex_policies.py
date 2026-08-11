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
from src.rag.embedding_tokenizer import load_embedding_tokenizer_config
from src.rag.embedder import EmbeddingService
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler
from src.rag.policy_reindex import (
    FreshProviderParityClaimV1,
    PolicyReindexClaimRequest,
    PolicyReindexRunIdentity,
    PolicyReindexService,
)
from src.rag.tokenizer_parity import require_fresh_provider_parity
from src.repositories.policy_corpus_repo import PolicyCorpusRepository


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

    resume = subcommands.add_parser("resume")
    resume.add_argument("--state-path", type=Path, required=True)
    resume.add_argument("--output-state-path", type=Path, required=True)
    build = subcommands.add_parser("build-next")
    build.add_argument("--state-path", type=Path, required=True)
    build.add_argument("--output-state-path", type=Path, required=True)
    validate = subcommands.add_parser("validate")
    validate.add_argument("--state-path", type=Path, required=True)
    validate.add_argument("--output-state-path", type=Path, required=True)
    return parser.parse_args()


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
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(_identity_payload(owner), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with path.open("x", encoding="utf-8") as handle:
        handle.write(encoded)
        handle.write("\n")


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
    elif args.command == "resume":
        owner = await _resume(args)
        _write_identity_create_only(args.output_state_path, owner)
    elif args.command == "build-next":
        owner = await _build_next(args)
        _write_identity_create_only(args.output_state_path, owner)
    else:
        owner = await _validate(args)
        _write_identity_create_only(args.output_state_path, owner)
    print(json.dumps({"state": owner.state, "state_version": owner.state_version}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
