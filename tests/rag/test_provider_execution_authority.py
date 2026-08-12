from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import (
    EvidenceIdentityRollout,
    PolicyCorpusManifestRevision,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    ProviderExecutionReservation,
    ProviderExecutionPromotion,
    Tenant,
)
from src.rag.provider_execution_authority import (
    ExecutionPromotionRequestV1,
    ProviderExecutionAuthorityError,
    ProviderExecutionAuthorityRequestV1,
    ProviderExecutionAuthorityService,
    ProviderExecutionPurpose,
    ProviderExecutionReservationRequestV1,
    ProviderRequestEnvelopeV1,
    canonical_sha256,
)
from src.repositories.provider_execution_authority_repo import (
    ProviderExecutionAuthorityRepository,
)


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
SHA_D = "sha256:" + "d" * 64
SHA_E = "sha256:" + "e" * 64
SHA_F = "sha256:" + "f" * 64


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _reviewed_git_root(tmp_path: Path) -> tuple[Path, str, str, str, str, str]:
    root = tmp_path / "reviewed"
    protected = (
        "src/db/models.py",
        "src/db/migrations/versions/032_phase64_5_provider_execution_authority.py",
        "src/rag/provider_execution_authority.py",
        "src/repositories/provider_execution_authority_repo.py",
    )
    for relative in protected:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("c0\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "authority@example.invalid")
    _git(root, "config", "user.name", "Authority Test")
    _git(root, "add", *protected)
    _git(root, "commit", "-qm", "c0")
    c0_commit = _git(root, "rev-parse", "HEAD")
    c0_tree = _git(root, "rev-parse", "HEAD^{tree}")
    (root / protected[2]).write_text("c1\n", encoding="utf-8")
    _git(root, "add", protected[2])
    _git(root, "commit", "-qm", "c1")
    c1_commit = _git(root, "rev-parse", "HEAD")
    c1_tree = _git(root, "rev-parse", "HEAD^{tree}")
    diff = subprocess.run(
        ["git", "-C", str(root), "diff", "--binary", "--full-index", c0_commit, c1_commit, "--", *protected],
        check=True,
        capture_output=True,
    ).stdout
    return root, c0_commit, c0_tree, c1_commit, c1_tree, canonical_sha256(diff)


async def _seed_authority_inputs(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    now = datetime.now(UTC)
    ids = {
        "tenant_id": uuid4(),
        "manifest_id": uuid4(),
        "active_corpus_id": uuid4(),
        "candidate_id": uuid4(),
        "run_token": uuid4(),
        "parity_run_id": uuid4(),
    }
    config_json = {"schema_version": "token.v1", "max_tokens": 8192}
    config_hash = canonical_sha256(config_json)
    parity_captured_at = now - timedelta(minutes=1)
    parity_expires_at = now + timedelta(hours=1)
    lease_expires_at = now + timedelta(hours=2)
    async with session_factory.begin() as session:
        session.add(Tenant(id=ids["tenant_id"], name=f"authority-{ids['tenant_id']}", status="active"))
        await session.flush()
        session.add(
            PolicyCorpusManifestRevision(
                id=ids["manifest_id"],
                tenant_id=ids["tenant_id"],
                revision=1,
                manifest_schema_version="policy_corpus_source_manifest.v1",
                manifest_json={"schema_version": "policy_corpus_source_manifest.v1", "documents": []},
                manifest_hash=SHA_A,
                document_count=0,
                block_count=0,
                chunk_count=0,
            )
        )
        await session.flush()
        session.add(
            PolicyCorpusVersion(
                id=ids["active_corpus_id"],
                tenant_id=ids["tenant_id"],
                generation_name="character.v1",
                owner_marker="fixture.active",
                run_token=None,
                config_schema_version="character.v1",
                config_json={},
                config_fingerprint=SHA_A,
                provider_parity_report_hash=None,
                source_manifest_revision_id=ids["manifest_id"],
                source_manifest_hash=SHA_A,
                source_active_corpus_version_id=None,
                source_rollout_epoch=None,
                expected_evidence_rollout_version=None,
                state="complete",
                state_version=1,
                lease_owner=None,
                lease_expires_at=None,
                next_document_index=0,
                bootstrap_counts_json={},
                validation_proof_json={},
            )
        )
        await session.flush()
        session.add(
            PolicyCorpusRollout(
                tenant_id=ids["tenant_id"],
                active_corpus_version_id=ids["active_corpus_id"],
                previous_corpus_version_id=None,
                rollout_epoch=1,
            )
        )
        session.add(
            EvidenceIdentityRollout(
                id=1,
                rollout_version=1,
                dual_write_enabled_at=now - timedelta(days=1),
                canonical_reads_enabled=True,
                canonical_reads_enabled_at=now - timedelta(days=1),
            )
        )
        session.add(
            PolicyCorpusVersion(
                id=ids["candidate_id"],
                tenant_id=ids["tenant_id"],
                generation_name="token.v1.fixture",
                owner_marker="moca.policy_reindex.v1",
                run_token=ids["run_token"],
                config_schema_version="token.v1",
                config_json=config_json,
                config_fingerprint=config_hash,
                provider_parity_report_hash=SHA_B,
                source_manifest_revision_id=ids["manifest_id"],
                source_manifest_hash=SHA_A,
                source_active_corpus_version_id=ids["active_corpus_id"],
                source_rollout_epoch=1,
                expected_evidence_rollout_version=1,
                state="claimed",
                state_version=1,
                lease_owner="fixture-owner",
                lease_expires_at=lease_expires_at,
                next_document_index=0,
                bootstrap_counts_json={},
                validation_proof_json={
                    "claim": {
                        "schema_version": "policy_reindex_claim.v1",
                        "ordered_doc_keys": [],
                        "source_manifest_revision": 1,
                        "parity_captured_at": parity_captured_at.isoformat(),
                        "parity_expires_at": parity_expires_at.isoformat(),
                    }
                },
            )
        )
    return {
        **ids,
        "config_json": config_json,
        "config_hash": config_hash,
        "parity_captured_at": parity_captured_at,
        "parity_expires_at": parity_expires_at,
        "lease_expires_at": lease_expires_at,
    }


async def _build_service_and_authority(
    test_engine,
    tmp_path: Path,
) -> tuple[
    async_sessionmaker[AsyncSession],
    ProviderExecutionAuthorityService,
    object,
    dict[str, object],
]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    seeded = await _seed_authority_inputs(session_factory)
    git_root, c0_commit, c0_tree, c1_commit, c1_tree, diff_hash = _reviewed_git_root(tmp_path)
    service = ProviderExecutionAuthorityService(
        ProviderExecutionAuthorityRepository(
            session_factory,
            project_entry=git_root / "src/rag/provider_execution_authority.py",
        )
    )
    promotion = await service.promote_reviewed_execution(
        ExecutionPromotionRequestV1.seal(
            protected_code_c0_commit=c0_commit,
            protected_code_c0_tree_hash=c0_tree,
            protected_code_c1_commit=c1_commit,
            protected_code_c1_tree_hash=c1_tree,
            c0_to_c1_diff_hash=diff_hash,
            c0_code_review_artifact_sha256=SHA_A,
            c0_security_artifact_sha256=SHA_B,
            c1_code_review_artifact_sha256=SHA_C,
            c1_security_artifact_sha256=SHA_D,
            c0_code_review_attestation_sha256=SHA_E,
            c0_security_attestation_sha256=SHA_F,
            c1_code_review_attestation_sha256=SHA_A,
            c1_security_attestation_sha256=SHA_B,
            c0_gate_report_sha256=SHA_C,
            c1_gate_report_sha256=SHA_D,
        )
    )
    authority = await service.issue_authority_root(
        ProviderExecutionAuthorityRequestV1(
            tenant_id=seeded["tenant_id"],
            run_token=seeded["run_token"],
            candidate_id=seeded["candidate_id"],
            owner_marker="moca.policy_reindex.v1",
            config_schema_version="token.v1",
            config_json=seeded["config_json"],
            config_fingerprint=seeded["config_hash"],
            provider_parity_run_id=seeded["parity_run_id"],
            provider_parity_report_hash=SHA_B,
            provider_parity_probe_fixture_sha256=SHA_C,
            provider_parity_submitted_content_sha256=SHA_D,
            parity_captured_at=seeded["parity_captured_at"],
            parity_expires_at=seeded["parity_expires_at"],
            source_manifest_revision_id=seeded["manifest_id"],
            source_manifest_hash=SHA_A,
            source_active_corpus_version_id=seeded["active_corpus_id"],
            source_rollout_epoch=1,
            evidence_rollout_version=1,
            candidate_lease_expires_at=seeded["lease_expires_at"],
            expires_at=seeded["parity_expires_at"],
            provider_name="openai",
            model_name="text-embedding-v4",
            dimensions=1536,
            envelope_contract_hash=SHA_E,
        )
    )
    assert authority.promotion_id == promotion.promotion_id
    seeded["git_root"] = git_root
    seeded["promotion"] = promotion
    return session_factory, service, authority, seeded


def _envelope(*, call_site: str = "document:0:batch:0") -> ProviderRequestEnvelopeV1:
    return ProviderRequestEnvelopeV1.seal(
        schema_version="provider_request_envelope.v1",
        contract_hash=SHA_E,
        ordered_call_sites=(call_site,),
        maximum_attempts_per_site=(1,),
        maximum_request_count=1,
        provider_name="openai",
        model_name="text-embedding-v4",
        dimensions=1536,
    )


def _reservation_request(
    authority_id,
    *,
    purpose: ProviderExecutionPurpose = ProviderExecutionPurpose.REVIEWED_BUILD,
    subject_hash: str = SHA_F,
    ordinal: int = 1,
    explicit_retry: bool = False,
) -> ProviderExecutionReservationRequestV1:
    subject_kind = "candidate_document" if purpose is ProviderExecutionPurpose.REVIEWED_BUILD else "canonical_ab_run"
    return ProviderExecutionReservationRequestV1(
        authority_id=authority_id,
        purpose=purpose,
        subject_kind=subject_kind,
        subject_index=0,
        subject_hash=subject_hash,
        ordinal=ordinal,
        request_envelope=_envelope(call_site=f"{purpose.value}:0"),
        explicit_retry=explicit_retry,
    )


@pytest.mark.asyncio
async def test_concurrent_same_subject_reservation_has_exactly_one_winner(test_engine, tmp_path: Path) -> None:
    session_factory, service, authority, _ = await _build_service_and_authority(test_engine, tmp_path)
    envelope = _envelope()
    request = _reservation_request(authority.authority_id).model_copy(update={"request_envelope": envelope})

    async def reserve() -> object:
        try:
            return await service.reserve_and_commit(request)
        except ProviderExecutionAuthorityError as exc:
            return exc

    outcomes = await asyncio.gather(reserve(), reserve())
    winners = [item for item in outcomes if not isinstance(item, ProviderExecutionAuthorityError)]
    losers = [item for item in outcomes if isinstance(item, ProviderExecutionAuthorityError)]
    assert len(winners) == 1
    assert len(losers) == 1
    assert losers[0].reason_code == "reservation_conflict"
    async with session_factory() as session:
        reservation_count = await session.scalar(
            select(func.count())
            .select_from(ProviderExecutionReservation)
            .where(ProviderExecutionReservation.authority_id == authority.authority_id)
        )
    assert reservation_count == 1


@pytest.mark.asyncio
async def test_one_shared_root_supports_both_purpose_envelopes_and_dispatch_recheck(
    test_engine,
    tmp_path: Path,
) -> None:
    session_factory, service, authority, _ = await _build_service_and_authority(test_engine, tmp_path)
    same_root = await service.issue_authority_root(
        ProviderExecutionAuthorityRequestV1.model_validate(
            authority.model_dump(exclude={"authority_id", "promotion_id", "issued_at"})
        )
    )
    assert same_root.authority_id == authority.authority_id

    build = await service.reserve_and_commit(_reservation_request(authority.authority_id))
    ab = await service.reserve_and_commit(
        _reservation_request(
            authority.authority_id,
            purpose=ProviderExecutionPurpose.CANONICAL_AB,
            subject_hash=SHA_A,
        )
    )
    assert {build.purpose, ab.purpose} == {
        ProviderExecutionPurpose.REVIEWED_BUILD,
        ProviderExecutionPurpose.CANONICAL_AB,
    }
    assert build.request_envelope != ab.request_envelope
    assert await service.recheck_dispatch(build) == build

    async with session_factory() as independent_session:
        committed = list(
            (
                await independent_session.execute(
                    select(ProviderExecutionReservation).where(
                        ProviderExecutionReservation.authority_id == authority.authority_id
                    )
                )
            ).scalars()
        )
    assert {row.purpose for row in committed} == {"reviewed_build", "canonical_ab"}


@pytest.mark.asyncio
async def test_missing_promotion_refuses_before_authority(test_engine, tmp_path: Path) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    await _seed_authority_inputs(session_factory)
    git_root, *_ = _reviewed_git_root(tmp_path)
    service = ProviderExecutionAuthorityService(
        ProviderExecutionAuthorityRepository(
            session_factory,
            project_entry=git_root / "src/rag/provider_execution_authority.py",
        )
    )
    with pytest.raises(ProviderExecutionAuthorityError, match="promotion_missing") as missing:
        await service.require_current_promotion()
    assert missing.value.reason_code == "promotion_missing"


@pytest.mark.asyncio
async def test_dirty_promotion_refuses_before_reservation(test_engine, tmp_path: Path) -> None:
    session_factory, service, authority, seeded = await _build_service_and_authority(test_engine, tmp_path)
    protected_file = Path(seeded["git_root"]) / "src/rag/provider_execution_authority.py"
    protected_file.write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ProviderExecutionAuthorityError, match="promotion_stale") as dirty:
        await service.reserve_and_commit(_reservation_request(authority.authority_id))
    assert dirty.value.reason_code == "promotion_stale"
    async with session_factory() as independent_session:
        count = await independent_session.scalar(select(func.count()).select_from(ProviderExecutionReservation))
    assert count == 0


@pytest.mark.asyncio
async def test_promotion_is_singleton_and_different_review_bytes_are_refused(test_engine, tmp_path: Path) -> None:
    session_factory, service, _, seeded = await _build_service_and_authority(test_engine, tmp_path)
    promotion = seeded["promotion"]
    exact = ExecutionPromotionRequestV1.model_validate(
        promotion.model_dump(exclude={"promotion_id", "scope", "promoted_at"})
    )
    assert (await service.promote_reviewed_execution(exact)).promotion_id == promotion.promotion_id

    changed = ExecutionPromotionRequestV1.seal(
        **exact.model_dump(exclude={"promotion_request_hash", "c1_gate_report_sha256"}),
        c1_gate_report_sha256=SHA_E,
    )
    with pytest.raises(ProviderExecutionAuthorityError, match="promotion_mismatch"):
        await service.promote_reviewed_execution(changed)
    async with session_factory() as independent_session:
        count = await independent_session.scalar(select(func.count()).select_from(ProviderExecutionPromotion))
    assert count == 1


@pytest.mark.asyncio
async def test_db_time_expiry_and_source_drift_refuse_before_new_reservation(test_engine, tmp_path: Path) -> None:
    session_factory, service, authority, _ = await _build_service_and_authority(test_engine, tmp_path)
    await service.reserve_and_commit(_reservation_request(authority.authority_id))
    async with session_factory.begin() as drift_session:
        rollout = (
            await drift_session.execute(
                select(PolicyCorpusRollout)
                .where(PolicyCorpusRollout.tenant_id == authority.tenant_id)
                .with_for_update()
            )
        ).scalar_one()
        rollout.rollout_epoch += 1
    with pytest.raises(ProviderExecutionAuthorityError, match="authority_mismatch"):
        await service.reserve_and_commit(_reservation_request(authority.authority_id, subject_hash=SHA_B))
    async with session_factory() as independent_session:
        count = await independent_session.scalar(
            select(func.count())
            .select_from(ProviderExecutionReservation)
            .where(ProviderExecutionReservation.authority_id == authority.authority_id)
        )
    assert count == 1

    source = Path("src/repositories/provider_execution_authority_repo.py").read_text(encoding="utf-8")
    assert 'text("SELECT clock_timestamp()")' in source
    assert "now >= as_utc(request.expires_at)" in source
