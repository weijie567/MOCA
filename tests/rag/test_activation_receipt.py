from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    PolicyCorpusActivationHistory,
    PolicyCorpusManifestRevision,
    PolicyCorpusRollout,
    PolicyCorpusVersion,
    Tenant,
)
from src.rag.activation_receipt import (
    ACTIVATION_RECEIPT_GENESIS,
    ActivationArtifactPaths,
    ActivationReceiptError,
    ActivationReceiptFailureCode,
    ActivationReceiptStore,
    load_activation_authority,
    load_activation_receipt,
)
from tests.eval.test_rag_token_chunk_ab import (
    CANDIDATE_CORPUS_ID,
    GENERATED_AT,
    INCUMBENT_CORPUS_ID,
    TENANT_ID,
    _write_selected_recovery_lineage,
)


TOKEN_CONFIG_FINGERPRINT = "sha256:" + "c" * 64
CANDIDATE_RUN_TOKEN = UUID("64300000-0000-4000-8000-000000000014")
CANDIDATE_LEASE_OWNER = "phase64.4-plan13"
SOURCE_MANIFEST_HASH = "sha256:" + "4" * 64
ACTOR = "operator.phase64_4.live"


def _write_strict_artifacts(root: Path) -> ActivationArtifactPaths:
    lineage = _write_selected_recovery_lineage(root)
    return ActivationArtifactPaths(
        selection_path=lineage.selection.json_path,
        terminal_run_path=lineage.terminal.json_path,
        parity_report_path=lineage.parity_path,
        recovery_authorization_path=lineage.authorization.path,
        recovery_budget_manifest_path=lineage.budget_artifact.path,
        recovery_reservation_path=lineage.reservation_path,
        candidate_state_path=lineage.candidate_state_path,
    )


async def _seed_activation_authority(session: AsyncSession) -> PolicyCorpusRollout:
    session.add(Tenant(id=TENANT_ID, name="phase64-4-activation-receipt", status="active"))
    await session.flush()
    manifest = PolicyCorpusManifestRevision(
        id=UUID("64300000-0000-4000-8000-000000000020"),
        tenant_id=TENANT_ID,
        revision=1,
        manifest_schema_version="policy_corpus_source_manifest.v1",
        manifest_json={
            "schema_version": "policy_corpus_source_manifest.v1",
            "tenant_id": str(TENANT_ID),
            "documents": [],
        },
        manifest_hash=SOURCE_MANIFEST_HASH,
        document_count=0,
        block_count=0,
        chunk_count=0,
    )
    session.add(manifest)
    await session.flush()
    common = {
        "tenant_id": TENANT_ID,
        "source_manifest_revision_id": manifest.id,
        "source_manifest_hash": SOURCE_MANIFEST_HASH,
        "state": "complete",
        "state_version": 1,
        "next_document_index": 0,
        "bootstrap_counts_json": {
            "bound_document_count": 0,
            "bound_block_count": 0,
            "bound_chunk_count": 0,
        },
        "validation_proof_json": {},
        "terminal_at": GENERATED_AT,
    }
    incumbent = PolicyCorpusVersion(
        id=INCUMBENT_CORPUS_ID,
        generation_name="character.v1",
        owner_marker="moca.phase64_4.bootstrap",
        run_token=None,
        config_schema_version="character_compatibility.v1",
        config_json={"schema_version": "character_compatibility.v1"},
        config_fingerprint="sha256:" + "b" * 64,
        provider_parity_report_hash=None,
        source_active_corpus_version_id=None,
        source_rollout_epoch=None,
        expected_evidence_rollout_version=None,
        lease_owner=None,
        lease_expires_at=None,
        **common,
    )
    candidate = PolicyCorpusVersion(
        id=CANDIDATE_CORPUS_ID,
        generation_name="token.v1:selected",
        owner_marker="moca.policy_reindex.v1",
        run_token=CANDIDATE_RUN_TOKEN,
        config_schema_version="embedding_tokenizer.v1",
        config_json={"schema_version": "embedding_tokenizer.v1"},
        config_fingerprint=TOKEN_CONFIG_FINGERPRINT,
        provider_parity_report_hash=None,
        source_active_corpus_version_id=INCUMBENT_CORPUS_ID,
        source_rollout_epoch=7,
        expected_evidence_rollout_version=13,
        lease_owner=CANDIDATE_LEASE_OWNER,
        lease_expires_at=datetime(2026, 8, 12, tzinfo=UTC),
        **common,
    )
    session.add_all((incumbent, candidate))
    await session.flush()
    rollout = PolicyCorpusRollout(
        id=UUID("64300000-0000-4000-8000-000000000021"),
        tenant_id=TENANT_ID,
        active_corpus_version_id=INCUMBENT_CORPUS_ID,
        previous_corpus_version_id=None,
        rollout_epoch=7,
    )
    session.add(rollout)
    await session.commit()
    return rollout


async def _commit_event(
    session: AsyncSession,
    *,
    sequence: int,
    from_corpus: UUID,
    to_corpus: UUID,
    reason: str,
    selection_sha256: str | None,
) -> None:
    await session.execute(
        update(PolicyCorpusRollout)
        .where(PolicyCorpusRollout.tenant_id == TENANT_ID)
        .values(
            active_corpus_version_id=to_corpus,
            previous_corpus_version_id=from_corpus,
            rollout_epoch=sequence,
        )
    )
    session.add(
        PolicyCorpusActivationHistory(
            id=UUID(f"64300000-0000-4000-8000-{sequence:012d}"),
            tenant_id=TENANT_ID,
            from_corpus_version_id=from_corpus,
            to_corpus_version_id=to_corpus,
            prior_rollout_epoch=sequence - 1,
            rollout_epoch=sequence,
            reason_code=reason,
            actor=ACTOR,
            selection_decision_hash=selection_sha256,
            receipt_hash=None,
            created_at=GENERATED_AT.replace(second=sequence),
        )
    )
    await session.commit()


def test_activation_authority_requires_complete_recovery_lineage(tmp_path: Path) -> None:
    paths = _write_strict_artifacts(tmp_path / "valid")
    authority = load_activation_authority(paths)
    assert authority.recovery_authorization_sha256.startswith("sha256:")

    missing = tmp_path / "missing-authorization.json"
    with pytest.raises(ActivationReceiptError) as missing_authority:
        load_activation_authority(replace(paths, recovery_authorization_path=missing))
    assert missing_authority.value.code is ActivationReceiptFailureCode.ARTIFACT_MISMATCH

    copied_manifest = tmp_path / "copied" / "manifest.json"
    copied_manifest.parent.mkdir(parents=True)
    copied_manifest.write_bytes(paths.recovery_budget_manifest_path.read_bytes())
    with pytest.raises(ActivationReceiptError) as alternate_manifest:
        load_activation_authority(replace(paths, recovery_budget_manifest_path=copied_manifest))
    assert alternate_manifest.value.code is ActivationReceiptFailureCode.ARTIFACT_MISMATCH

    wrong_state = tmp_path / "copied" / "state.json"
    wrong_state.write_bytes(paths.candidate_state_path.read_bytes())
    with pytest.raises(ActivationReceiptError) as candidate_mismatch:
        load_activation_authority(replace(paths, candidate_state_path=wrong_state))
    assert candidate_mismatch.value.code is ActivationReceiptFailureCode.ARTIFACT_MISMATCH

    tampered_paths = _write_strict_artifacts(tmp_path / "tampered")
    payload = tampered_paths.recovery_authorization_path.read_bytes()
    tampered_paths.recovery_authorization_path.write_bytes(
        payload.replace(b'"reservation_ordinal":1', b'"reservation_ordinal":2')
    )
    with pytest.raises(ActivationReceiptError) as fabricated:
        load_activation_authority(tampered_paths)
    assert fabricated.value.code is ActivationReceiptFailureCode.ARTIFACT_MISMATCH


@pytest.mark.asyncio
async def test_committed_event_writes_create_only_receipt_bound_to_live_pointer_and_artifacts(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    paths = _write_strict_artifacts(tmp_path / "evidence")
    authority = load_activation_authority(paths)
    proof = authority.to_selection_proof(expected_evidence_rollout_version=13)
    assert proof.schema_version == "rag_token_chunk_selection.v1"
    assert proof.selection_decision_sha256 == authority.selection_decision_sha256
    assert proof.provider_parity_report_hash == authority.provider_parity_report_sha256
    assert proof.recovery_authorization_sha256 == authority.recovery_authorization_sha256
    await _seed_activation_authority(session)
    await _commit_event(
        session,
        sequence=8,
        from_corpus=INCUMBENT_CORPUS_ID,
        to_corpus=CANDIDATE_CORPUS_ID,
        reason="selected_cutover",
        selection_sha256=authority.selection_decision_sha256,
    )

    store = ActivationReceiptStore(tmp_path / "activations")
    first = await store.write_committed(
        session,
        tenant_id=TENANT_ID,
        history_sequence=8,
        authority=authority,
    )
    before = first.path.read_bytes()
    replayed = await store.write_committed(
        session,
        tenant_id=TENANT_ID,
        history_sequence=8,
        authority=authority,
    )
    receipt = load_activation_receipt(first.path)

    assert replayed == first
    assert first.path.read_bytes() == before
    assert receipt.schema_version == "rag_token_chunk_activation.v1"
    assert receipt.history_sequence == 8
    assert receipt.event_reason == "selected_cutover"
    assert receipt.before_rollout_epoch == 7
    assert receipt.after_rollout_epoch == 8
    assert receipt.from_corpus_version_id == INCUMBENT_CORPUS_ID
    assert receipt.to_corpus_version_id == CANDIDATE_CORPUS_ID
    assert receipt.selection_decision_sha256 == authority.selection_decision_sha256
    assert receipt.terminal_run_sha256 == authority.terminal_run_sha256
    assert receipt.provider_parity_report_sha256 == authority.provider_parity_report_sha256
    assert receipt.recovery_authorization_sha256 == authority.recovery_authorization_sha256
    assert receipt.db_history_sha256.startswith("sha256:")
    assert receipt.actor == ACTOR
    assert receipt.previous_receipt_sha256 == ACTIVATION_RECEIPT_GENESIS


@pytest.mark.asyncio
async def test_three_receipts_form_hash_chain_and_missing_receipt_reconciles_idempotently(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    authority = load_activation_authority(_write_strict_artifacts(tmp_path / "evidence"))
    await _seed_activation_authority(session)
    events = (
        (8, INCUMBENT_CORPUS_ID, CANDIDATE_CORPUS_ID, "selected_cutover", authority.selection_decision_sha256),
        (9, CANDIDATE_CORPUS_ID, INCUMBENT_CORPUS_ID, "rollback_prior", None),
        (10, INCUMBENT_CORPUS_ID, CANDIDATE_CORPUS_ID, "restore_selected", authority.selection_decision_sha256),
    )
    for sequence, from_corpus, to_corpus, reason, selection_hash in events:
        await _commit_event(
            session,
            sequence=sequence,
            from_corpus=from_corpus,
            to_corpus=to_corpus,
            reason=reason,
            selection_sha256=selection_hash,
        )

    store = ActivationReceiptStore(tmp_path / "activations")
    receipts = await store.reconcile_missing(session, tenant_id=TENANT_ID, authority=authority)
    assert [item.receipt.history_sequence for item in receipts] == [8, 9, 10]
    assert receipts[0].receipt.previous_receipt_sha256 == ACTIVATION_RECEIPT_GENESIS
    assert receipts[1].receipt.previous_receipt_sha256 == receipts[0].file_sha256
    assert receipts[2].receipt.previous_receipt_sha256 == receipts[1].file_sha256

    missing_path = receipts[1].path
    expected_bytes = missing_path.read_bytes()
    missing_path.unlink()
    reconciled = await store.reconcile_missing(session, tenant_id=TENANT_ID, authority=authority)
    assert reconciled[1].path.read_bytes() == expected_bytes
    assert reconciled[2].receipt.previous_receipt_sha256 == reconciled[1].file_sha256
    assert [item.file_sha256 for item in reconciled] == [item.file_sha256 for item in receipts]


@pytest.mark.asyncio
async def test_existing_receipt_or_artifact_mismatch_fails_without_rewrite(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    paths = _write_strict_artifacts(tmp_path / "evidence")
    authority = load_activation_authority(paths)
    await _seed_activation_authority(session)
    await _commit_event(
        session,
        sequence=8,
        from_corpus=INCUMBENT_CORPUS_ID,
        to_corpus=CANDIDATE_CORPUS_ID,
        reason="selected_cutover",
        selection_sha256=authority.selection_decision_sha256,
    )
    store = ActivationReceiptStore(tmp_path / "activations")
    written = await store.write_committed(
        session,
        tenant_id=TENANT_ID,
        history_sequence=8,
        authority=authority,
    )
    written.path.write_bytes(b'{"schema_version":"rag_token_chunk_activation.v1","tampered":true}\n')
    tampered = written.path.read_bytes()

    with pytest.raises(ActivationReceiptError) as conflict:
        await store.write_committed(
            session,
            tenant_id=TENANT_ID,
            history_sequence=8,
            authority=authority,
        )
    assert conflict.value.code is ActivationReceiptFailureCode.CREATE_CONFLICT
    assert written.path.read_bytes() == tampered

    paths.parity_report_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ActivationReceiptError) as artifact_mismatch:
        load_activation_authority(paths)
    assert artifact_mismatch.value.code is ActivationReceiptFailureCode.ARTIFACT_MISMATCH


@pytest.mark.asyncio
async def test_uncommitted_or_stale_pointer_event_cannot_write_latest_receipt(
    session: AsyncSession,
    tmp_path: Path,
) -> None:
    authority = load_activation_authority(_write_strict_artifacts(tmp_path / "evidence"))
    await _seed_activation_authority(session)
    await _commit_event(
        session,
        sequence=8,
        from_corpus=INCUMBENT_CORPUS_ID,
        to_corpus=CANDIDATE_CORPUS_ID,
        reason="selected_cutover",
        selection_sha256=authority.selection_decision_sha256,
    )
    await session.execute(
        update(PolicyCorpusRollout)
        .where(PolicyCorpusRollout.tenant_id == TENANT_ID)
        .values(active_corpus_version_id=INCUMBENT_CORPUS_ID, rollout_epoch=9)
    )
    await session.commit()

    with pytest.raises(ActivationReceiptError) as stale:
        await ActivationReceiptStore(tmp_path / "activations").write_committed(
            session,
            tenant_id=TENANT_ID,
            history_sequence=8,
            authority=authority,
        )
    assert stale.value.code is ActivationReceiptFailureCode.LIVE_POINTER_MISMATCH
    assert list((tmp_path / "activations").rglob("*.json")) == []

    rows = list(
        (
            await session.execute(
                select(PolicyCorpusActivationHistory).where(PolicyCorpusActivationHistory.tenant_id == TENANT_ID)
            )
        ).scalars()
    )
    assert len(rows) == 1
    assert rows[0].receipt_hash is None
