from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    PolicyCorpusManifestRevision,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    Tenant,
)
from src.rag.policy_reindex import (
    POLICY_REINDEX_STATES,
    FreshProviderParityClaimV1,
    PolicyReindexClaimRequest,
    PolicyReindexError,
    PolicyReindexFailureCode,
    PolicyReindexService,
)


NOW = datetime(2026, 8, 11, 8, 30, tzinfo=UTC)
TOKEN_CONFIG_FINGERPRINT = "sha256:" + "1" * 64
PARITY_REPORT_HASH = "sha256:" + "2" * 64


def _sha256(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


async def _seed_source_authority(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    doc_keys: tuple[str, ...] = ("policy-a", "policy-b"),
) -> tuple[UUID, PolicyCorpusManifestRevision, PolicyCorpusVersion, PolicyCorpusRollout]:
    resolved_tenant_id = tenant_id or uuid4()
    session.add(Tenant(id=resolved_tenant_id, name=f"tenant-{resolved_tenant_id}", status="active"))
    await session.flush()
    manifest_payload = {
        "schema_version": "policy_corpus_source_manifest.v1",
        "tenant_id": str(resolved_tenant_id),
        "documents": [
            {
                "policy_document_id": str(uuid4()),
                "policy_document_version_id": str(uuid4()),
                "doc_key": doc_key,
                "document_version": 1,
                "source_type": "markdown",
                "source_checksum": _sha256({"doc_key": doc_key}),
                "source_block_ids": [f"{doc_key}:0"],
                "chunk_ids": [f"{doc_key}_0"],
            }
            for doc_key in doc_keys
        ],
    }
    manifest = PolicyCorpusManifestRevision(
        id=uuid4(),
        tenant_id=resolved_tenant_id,
        revision=1,
        manifest_schema_version="policy_corpus_source_manifest.v1",
        manifest_json=manifest_payload,
        manifest_hash=_sha256(manifest_payload),
        document_count=len(doc_keys),
        block_count=len(doc_keys),
        chunk_count=len(doc_keys),
    )
    source = PolicyCorpusVersion(
        id=uuid4(),
        tenant_id=resolved_tenant_id,
        generation_name="character.v1",
        owner_marker="moca.phase64_4.bootstrap",
        run_token=None,
        config_schema_version="character_compatibility.v1",
        config_json={"schema_version": "character_compatibility.v1"},
        config_fingerprint="sha256:" + "0" * 64,
        provider_parity_report_hash=None,
        source_manifest_revision_id=manifest.id,
        source_manifest_hash=manifest.manifest_hash,
        source_active_corpus_version_id=None,
        source_rollout_epoch=None,
        expected_evidence_rollout_version=None,
        state="complete",
        state_version=1,
        lease_owner=None,
        lease_expires_at=None,
        next_document_index=len(doc_keys),
        bootstrap_counts_json={
            "bound_document_count": 0,
            "bound_block_count": 0,
            "bound_chunk_count": 0,
        },
        validation_proof_json={},
        terminal_at=NOW,
    )
    rollout = PolicyCorpusRollout(
        id=uuid4(),
        tenant_id=resolved_tenant_id,
        active_corpus_version_id=source.id,
        previous_corpus_version_id=None,
        rollout_epoch=7,
    )
    session.add(manifest)
    await session.flush()
    session.add(source)
    await session.flush()
    session.add(rollout)
    await session.flush()
    return resolved_tenant_id, manifest, source, rollout


def _claim_request(
    *,
    tenant_id: UUID,
    manifest: PolicyCorpusManifestRevision,
    source: PolicyCorpusVersion,
    rollout: PolicyCorpusRollout,
    run_token: UUID | None = None,
    lease_owner: str = "worker-a",
    lease_expires_at: datetime = NOW + timedelta(minutes=15),
) -> PolicyReindexClaimRequest:
    return PolicyReindexClaimRequest(
        tenant_id=tenant_id,
        run_token=run_token or uuid4(),
        generation_name=f"token.v1:{run_token or uuid4()}",
        lease_owner=lease_owner,
        lease_expires_at=lease_expires_at,
        config_schema_version="embedding_tokenizer.v1",
        config_json={
            "schema_version": "embedding_tokenizer.v1",
            "max_embedding_tokens": 512,
            "target_embedding_tokens": 384,
            "overlap_tokens": 48,
        },
        config_fingerprint=TOKEN_CONFIG_FINGERPRINT,
        parity=FreshProviderParityClaimV1(
            report_hash=PARITY_REPORT_HASH,
            config_fingerprint=TOKEN_CONFIG_FINGERPRINT,
            captured_at=NOW - timedelta(minutes=5),
            status="passed",
        ),
        source_manifest_revision_id=manifest.id,
        source_manifest_revision=manifest.revision,
        source_manifest_hash=manifest.manifest_hash,
        source_active_corpus_version_id=source.id,
        source_rollout_epoch=rollout.rollout_epoch,
        expected_evidence_rollout_version=11,
    )


@pytest.mark.asyncio
async def test_claim_seals_fixed_identity_and_keeps_active_authority_pointer_only(session: AsyncSession) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    request = _claim_request(tenant_id=tenant_id, manifest=manifest, source=source, rollout=rollout)
    service = PolicyReindexService(session)

    owner = await service.claim(request, now=NOW)
    duplicate = await service.claim(request, now=NOW)

    assert owner == duplicate
    assert owner.state == "claimed"
    assert owner.state_version == 1
    assert owner.next_document_index == 0
    assert owner.ordered_doc_keys == ("policy-a", "policy-b")
    assert owner.config_fingerprint == TOKEN_CONFIG_FINGERPRINT
    assert owner.provider_parity_report_hash == PARITY_REPORT_HASH
    assert owner.source_manifest_revision_id == manifest.id
    assert owner.source_manifest_revision == 1
    assert owner.source_manifest_hash == manifest.manifest_hash
    assert owner.source_active_corpus_version_id == source.id
    assert owner.source_rollout_epoch == 7
    assert owner.lease_owner == "worker-a"
    assert owner.lease_expires_at == NOW + timedelta(minutes=15)
    assert POLICY_REINDEX_STATES == frozenset(
        {"claimed", "building", "built", "validating", "complete", "failed", "source_stale"}
    )
    assert "active" not in POLICY_REINDEX_STATES
    await session.refresh(rollout)
    assert rollout.active_corpus_version_id == source.id
    assert rollout.rollout_epoch == 7
    assert await session.scalar(select(func.count()).select_from(PolicyCorpusVersion)) == 2


@pytest.mark.asyncio
async def test_resume_and_ordered_checkpoint_use_cas_and_transaction_rollback(session: AsyncSession) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    service = PolicyReindexService(session)
    owner = await service.claim(
        _claim_request(tenant_id=tenant_id, manifest=manifest, source=source, rollout=rollout),
        now=NOW,
    )
    building = await service.resume(owner, now=NOW)
    assert building.state == "building"
    assert building.state_version == 2

    with pytest.raises(PolicyReindexError) as out_of_order:
        await service.checkpoint_document(building, doc_key="policy-b", now=NOW)
    assert out_of_order.value.code is PolicyReindexFailureCode.DOCUMENT_ORDER_MISMATCH

    first = await service.checkpoint_document(building, doc_key="policy-a", now=NOW)
    assert first.next_document_index == 1
    assert first.state == "building"
    with pytest.raises(PolicyReindexError) as stale:
        await service.checkpoint_document(building, doc_key="policy-a", now=NOW)
    assert stale.value.code is PolicyReindexFailureCode.CAS_CONFLICT

    await session.commit()
    try:
        async with session.begin():
            rolled_back = await service.checkpoint_document(first, doc_key="policy-b", now=NOW)
            assert rolled_back.state == "built"
            raise RuntimeError("interrupt after projection write but before transaction commit")
    except RuntimeError:
        pass
    await session.rollback()
    resumed = await service.resume(first, now=NOW)
    assert resumed.next_document_index == 1
    assert resumed.state == "building"


@pytest.mark.asyncio
async def test_resume_refuses_config_parity_owner_expiry_and_foreign_run(session: AsyncSession) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    other_tenant_id, other_manifest, other_source, other_rollout = await _seed_source_authority(session)
    service = PolicyReindexService(session)
    owner = await service.claim(
        _claim_request(tenant_id=tenant_id, manifest=manifest, source=source, rollout=rollout),
        now=NOW,
    )
    other_owner = await service.claim(
        _claim_request(
            tenant_id=other_tenant_id,
            manifest=other_manifest,
            source=other_source,
            rollout=other_rollout,
            lease_owner="worker-b",
        ),
        now=NOW,
    )

    refusals = (
        (replace(owner, config_fingerprint="sha256:" + "a" * 64), PolicyReindexFailureCode.CONFIG_DRIFT),
        (
            replace(owner, provider_parity_report_hash="sha256:" + "b" * 64),
            PolicyReindexFailureCode.PARITY_DRIFT,
        ),
        (replace(owner, lease_owner="worker-b"), PolicyReindexFailureCode.LEASE_OWNER_MISMATCH),
        (replace(owner, run_token=other_owner.run_token), PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH),
        (replace(owner, tenant_id=other_tenant_id), PolicyReindexFailureCode.RUN_IDENTITY_MISMATCH),
    )
    for drifted, expected_code in refusals:
        with pytest.raises(PolicyReindexError) as denied:
            await service.resume(drifted, now=NOW)
        assert denied.value.code is expected_code

    with pytest.raises(PolicyReindexError) as expired:
        await service.resume(owner, now=owner.lease_expires_at + timedelta(microseconds=1))
    assert expired.value.code is PolicyReindexFailureCode.LEASE_EXPIRED
    await session.refresh(source)
    await session.refresh(other_source)
    assert source.state == "complete"
    assert other_source.state == "complete"


@pytest.mark.asyncio
async def test_resume_marks_source_stale_on_manifest_or_active_pointer_epoch_drift(session: AsyncSession) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    service = PolicyReindexService(session)
    owner = await service.claim(
        _claim_request(tenant_id=tenant_id, manifest=manifest, source=source, rollout=rollout),
        now=NOW,
    )
    next_manifest_payload = {
        **manifest.manifest_json,
        "documents": [*manifest.manifest_json["documents"], {"doc_key": "policy-c"}],
    }
    session.add(
        PolicyCorpusManifestRevision(
            id=uuid4(),
            tenant_id=tenant_id,
            revision=2,
            manifest_schema_version="policy_corpus_source_manifest.v1",
            manifest_json=next_manifest_payload,
            manifest_hash=_sha256(next_manifest_payload),
            document_count=3,
            block_count=3,
            chunk_count=3,
        )
    )
    await session.flush()

    with pytest.raises(PolicyReindexError) as stale_manifest:
        await service.resume(owner, now=NOW)
    assert stale_manifest.value.code is PolicyReindexFailureCode.SOURCE_MANIFEST_DRIFT
    candidate = await session.get(PolicyCorpusVersion, owner.corpus_version_id)
    assert candidate is not None
    assert candidate.state == "source_stale"

    tenant2, manifest2, source2, rollout2 = await _seed_source_authority(session)
    owner2 = await service.claim(
        _claim_request(tenant_id=tenant2, manifest=manifest2, source=source2, rollout=rollout2),
        now=NOW,
    )
    replacement = PolicyCorpusVersion(
        id=uuid4(),
        tenant_id=tenant2,
        generation_name="character.v1.replacement",
        owner_marker="test",
        run_token=None,
        config_schema_version=source2.config_schema_version,
        config_json=source2.config_json,
        config_fingerprint=source2.config_fingerprint,
        provider_parity_report_hash=None,
        source_manifest_revision_id=manifest2.id,
        source_manifest_hash=manifest2.manifest_hash,
        source_active_corpus_version_id=None,
        source_rollout_epoch=None,
        expected_evidence_rollout_version=None,
        state="complete",
        state_version=1,
        lease_owner=None,
        lease_expires_at=None,
        next_document_index=2,
        bootstrap_counts_json={},
        validation_proof_json={},
        terminal_at=NOW,
    )
    session.add(replacement)
    await session.flush()
    rollout2.active_corpus_version_id = replacement.id
    rollout2.rollout_epoch += 1
    await session.flush()

    with pytest.raises(PolicyReindexError) as stale_pointer:
        await service.resume(owner2, now=NOW)
    assert stale_pointer.value.code is PolicyReindexFailureCode.SOURCE_POINTER_DRIFT
    candidate2 = await session.get(PolicyCorpusVersion, owner2.corpus_version_id)
    assert candidate2 is not None
    assert candidate2.state == "source_stale"


@pytest.mark.asyncio
async def test_resume_rejects_taken_lease_without_touching_other_tenant_or_run(session: AsyncSession) -> None:
    tenant_id, manifest, source, rollout = await _seed_source_authority(session)
    other_tenant_id, other_manifest, other_source, other_rollout = await _seed_source_authority(session)
    service = PolicyReindexService(session)
    owner = await service.claim(
        _claim_request(tenant_id=tenant_id, manifest=manifest, source=source, rollout=rollout),
        now=NOW,
    )
    other = await service.claim(
        _claim_request(
            tenant_id=other_tenant_id,
            manifest=other_manifest,
            source=other_source,
            rollout=other_rollout,
            lease_owner="worker-b",
        ),
        now=NOW,
    )
    candidate = await session.get(PolicyCorpusVersion, owner.corpus_version_id)
    assert candidate is not None
    candidate.lease_owner = "worker-takeover"
    candidate.state_version += 1
    await session.flush()

    with pytest.raises(PolicyReindexError) as denied:
        await service.resume(owner, now=NOW)
    assert denied.value.code is PolicyReindexFailureCode.LEASE_OWNER_MISMATCH
    other_candidate = await session.get(PolicyCorpusVersion, other.corpus_version_id)
    assert other_candidate is not None
    assert other_candidate.state == "claimed"
    assert other_candidate.next_document_index == 0
