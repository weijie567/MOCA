from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.schemas import ApprovalRequestCreateCommand
from src.approvals.service import ApprovalService, ApprovalTransitionError
from src.approvals.snapshot_service import compute_action_payload_hash, persist_action_safety_snapshot
from src.db.models import (
    ActionSafetySnapshot,
    ApprovalAssignment,
    ApprovalEvent,
    ApprovalLevel,
    ApprovalRequest,
    PolicyChunkVersion,
    PolicyDocument,
    PolicyDocumentVersion,
)
from src.knowledge.schemas import EvidenceRefV1, canonical_evidence_projection
from src.knowledge.text_hash import evidence_text_hash
from src.repositories.evidence_version_repo import EvidenceVersionRepository
from tests.approvals.test_service_transitions import (
    _business_fact_ref,
    _create_command,
    _create_run,
    _mark_run_business_scope,
    _proposed_action,
    _risk_decision_payload,
    _target_merchant_ref,
)


APPROVAL_OWNED_TABLES = (
    ActionSafetySnapshot,
    ApprovalRequest,
    ApprovalLevel,
    ApprovalAssignment,
    ApprovalEvent,
)


async def _approval_counts(session: AsyncSession) -> dict[str, int]:
    return {
        table.__tablename__: int(await session.scalar(select(func.count()).select_from(table)) or 0)
        for table in APPROVAL_OWNED_TABLES
    }


async def _seed_canonical_evidence(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    suffix: str,
    rank: int = 1,
    retrieval_config_version: str = "retrieval.v1",
) -> EvidenceRefV1:
    doc_key = f"approval-policy-{suffix}"
    chunk_id = f"chunk-{suffix}"
    content = f"Canonical approval evidence {suffix}."
    document = PolicyDocument(
        tenant_id=tenant_id,
        doc_key=doc_key,
        doc_type="refund_rule",
        title=f"Approval policy {suffix}",
        effective_date=date(2026, 1, 1),
        risk_level="high",
        version=1,
        content=content,
        source_type="phase64_2_test",
    )
    session.add(document)
    await session.flush()

    document_version = PolicyDocumentVersion(
        tenant_id=tenant_id,
        policy_document_id=document.id,
        scope_type="tenant_policy",
        scope_id=str(tenant_id),
        doc_key=doc_key,
        document_version=1,
        content=content,
        content_hash=evidence_text_hash(content),
        source_locator_json={"source_type": "phase64_2_test"},
        lifecycle_status="active",
        retention_until=datetime.now(UTC) + timedelta(days=365),
    )
    session.add(document_version)
    await session.flush()

    chunk_version = PolicyChunkVersion(
        tenant_id=tenant_id,
        policy_document_version_id=document_version.id,
        scope_type="tenant_policy",
        scope_id=str(tenant_id),
        doc_key=doc_key,
        document_version=1,
        chunk_id=chunk_id,
        chunk_version=1,
        content=content,
        text_hash=evidence_text_hash(content),
        source_locator_json={"source_type": "phase64_2_test"},
        lifecycle_status="active",
        retention_until=datetime.now(UTC) + timedelta(days=365),
    )
    session.add(chunk_version)
    await session.flush()

    repository = EvidenceVersionRepository(session)
    resolution = await repository.mint_for_chunk_version(
        chunk_version,
        expected_tenant_id=tenant_id,
        expected_scope_type="tenant_policy",
        expected_scope_id=str(tenant_id),
    )
    assert resolution.identity is not None
    return repository.evidence_ref_from_identity(
        resolution.identity,
        retrieved_at="2026-06-15T00:00:00.000Z",
        retrieval_config_version=retrieval_config_version,
        rank=rank,
    )


def _ref_json(ref: EvidenceRefV1) -> dict[str, Any]:
    return ref.model_dump(mode="json")


def _forged_ref(ref: EvidenceRefV1, **updates: Any) -> EvidenceRefV1:
    return ref.model_copy(update=updates)


def _legacy_ref(ref: EvidenceRefV1) -> EvidenceRefV1:
    return EvidenceRefV1(
        tenant_id=ref.tenant_id,
        evidence_id=f"{ref.doc_key}/{ref.chunk_id}@{ref.policy_version}",
        doc_key=ref.doc_key,
        chunk_id=ref.chunk_id,
        policy_version=ref.policy_version,
        text_hash=ref.text_hash,
        retrieved_at=ref.retrieved_at,
        retrieval_config_version=ref.retrieval_config_version,
        rank=ref.rank,
    )


async def _create_command_with_canonical_evidence(
    session: AsyncSession,
    seeded_session,
    refs: Sequence[EvidenceRefV1],
    *,
    verified_refs: Sequence[EvidenceRefV1] = (),
    thread_id: str = "phase64-2-approval-create",
) -> ApprovalRequestCreateCommand:
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(
        session,
        tenant_id=tenant_id,
        user_id=requested_by,
        thread_id=thread_id,
    )
    merchant_id = str(seeded_session["merchant"].id)
    target_ref = _target_merchant_ref(tenant_id=tenant_id, merchant_id=merchant_id)
    binding = {"target_merchant_id": merchant_id, "target_merchant_ref": target_ref}
    await _mark_run_business_scope(session, run_id, binding)
    ref_payloads = canonical_evidence_projection(list(refs))
    action = _proposed_action(tenant_id=tenant_id, run_id=run_id, evidence_refs=ref_payloads)
    action_hash = compute_action_payload_hash(action)
    return _create_command(
        tenant_id=tenant_id,
        run_id=run_id,
        requested_by=requested_by,
        thread_id=thread_id,
        evidence_refs=ref_payloads,
        proposed_action=action,
        action_payload_hash=action_hash,
        target_merchant_id=merchant_id,
        target_merchant_ref=target_ref,
        business_fact_refs=[_business_fact_ref(tenant_id=tenant_id)],
        verified_evidence_refs=canonical_evidence_projection(list(verified_refs)),
        risk_decision_ref=f"risk_decision:{run_id}:{action_hash}",
        risk_decision=_risk_decision_payload(
            tenant_id=tenant_id,
            run_id=run_id,
            action_payload_hash=action_hash,
        ),
    )


async def _assert_create_rejected_atomically(
    session: AsyncSession,
    command: ApprovalRequestCreateCommand,
) -> None:
    before = await _approval_counts(session)
    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).create_request(command)
    assert exc.value.code == "approval_not_executable"
    assert await _approval_counts(session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("verified_mode", ["empty", "exact_reversed"])
async def test_create_persists_one_repository_canonical_evidence_list(
    session: AsyncSession,
    seeded_session,
    verified_mode: str,
) -> None:
    tenant_id = seeded_session["tenant"].id
    first = await _seed_canonical_evidence(session, tenant_id=tenant_id, suffix="one", rank=2)
    second = await _seed_canonical_evidence(session, tenant_id=tenant_id, suffix="two", rank=1)
    verified_refs = [] if verified_mode == "empty" else [first, second]
    command = await _create_command_with_canonical_evidence(
        session,
        seeded_session,
        [first, second],
        verified_refs=verified_refs,
        thread_id=f"phase64-2-create-{verified_mode}",
    )

    result = await ApprovalService(session).create_request(command)
    request = await session.get(ApprovalRequest, result.approval_id)
    snapshot = (
        await session.execute(
            select(ActionSafetySnapshot).where(
                ActionSafetySnapshot.snapshot_ref == result.safety_snapshot_ref,
                ActionSafetySnapshot.immutable_hash == result.safety_snapshot_hash,
            )
        )
    ).scalar_one()
    expected_projection = canonical_evidence_projection([first, second])
    expected_stored = [EvidenceRefV1.model_validate(item).model_dump(mode="json") for item in expected_projection]

    assert request is not None
    assert request.proposed_action["evidence_refs"] == expected_projection
    assert snapshot.snapshot_json["evidence"] == expected_stored
    assert request.verified_evidence_refs == expected_stored
    assert [ref.model_dump(mode="json") for ref in result.verified_evidence_refs] == expected_stored
    assert {item["scope_type"] for item in expected_projection} == {"tenant_policy"}
    assert {item["scope_id"] for item in expected_projection} == {str(tenant_id)}
    assert [item["rank"] for item in expected_projection] == [1, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_name", "mutation"),
    [
        ("forged_id", lambda ref, _other, _tenant: _forged_ref(ref, evidence_id="sha256:" + "f" * 64)),
        ("changed_hash", lambda ref, _other, _tenant: _forged_ref(ref, text_hash="sha256:" + "f" * 64)),
        ("wrong_document_version", lambda ref, _other, _tenant: _forged_ref(ref, document_version=2, policy_version="v2")),
        ("wrong_chunk_version", lambda ref, _other, _tenant: _forged_ref(ref, chunk_version=2)),
        ("request_scope_substitution", lambda ref, _other, _tenant: _forged_ref(ref, scope_id="merchant-request-scope")),
        ("same_tenant_cross_scope", lambda ref, _other, _tenant: _forged_ref(ref, scope_type="merchant_policy")),
        ("cross_tenant", lambda _ref, other, _tenant: other),
        ("legacy_ambiguous", lambda ref, _other, _tenant: _legacy_ref(ref)),
    ],
)
async def test_create_rejects_untrusted_evidence_without_new_rows(
    session: AsyncSession,
    seeded_session,
    case_name: str,
    mutation,
) -> None:
    tenant_id = seeded_session["tenant"].id
    valid = await _seed_canonical_evidence(session, tenant_id=tenant_id, suffix=f"valid-{case_name}")
    await _seed_canonical_evidence(session, tenant_id=tenant_id, suffix=f"ambiguity-{case_name}")
    cross_tenant = await _seed_canonical_evidence(
        session,
        tenant_id=seeded_session["other_tenant"].id,
        suffix=f"cross-{case_name}",
    )
    command = await _create_command_with_canonical_evidence(
        session,
        seeded_session,
        [valid],
        thread_id=f"phase64-2-invalid-{case_name}",
    )
    candidate = mutation(valid, cross_tenant, tenant_id)
    command = command.model_copy(update={"evidence_refs": [candidate]})

    await _assert_create_rejected_atomically(session, command)


@pytest.mark.asyncio
async def test_create_rejects_mixed_valid_and_forged_evidence_without_new_rows(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant_id = seeded_session["tenant"].id
    valid = await _seed_canonical_evidence(session, tenant_id=tenant_id, suffix="mixed-valid")
    second = await _seed_canonical_evidence(session, tenant_id=tenant_id, suffix="mixed-forged", rank=2)
    forged = _forged_ref(second, text_hash="sha256:" + "f" * 64)
    command = await _create_command_with_canonical_evidence(session, seeded_session, [valid, second])
    command = command.model_copy(update={"evidence_refs": [valid, forged]})

    await _assert_create_rejected_atomically(session, command)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_name",
    ["missing", "extra", "forged", "mixed", "cross_tenant", "same_tenant_cross_scope"],
)
async def test_create_rejects_divergent_verified_evidence_without_new_rows(
    session: AsyncSession,
    seeded_session,
    case_name: str,
) -> None:
    tenant_id = seeded_session["tenant"].id
    first = await _seed_canonical_evidence(session, tenant_id=tenant_id, suffix=f"verified-first-{case_name}")
    second = await _seed_canonical_evidence(
        session,
        tenant_id=tenant_id,
        suffix=f"verified-second-{case_name}",
        rank=2,
    )
    extra = await _seed_canonical_evidence(session, tenant_id=tenant_id, suffix=f"verified-extra-{case_name}", rank=3)
    cross_tenant = await _seed_canonical_evidence(
        session,
        tenant_id=seeded_session["other_tenant"].id,
        suffix=f"verified-cross-{case_name}",
    )
    command = await _create_command_with_canonical_evidence(session, seeded_session, [first, second])
    cases = {
        "missing": [first],
        "extra": [first, second, extra],
        "forged": [_forged_ref(first, evidence_id="sha256:" + "f" * 64), second],
        "mixed": [first, _forged_ref(second, text_hash="sha256:" + "f" * 64)],
        "cross_tenant": [first, cross_tenant],
        "same_tenant_cross_scope": [first, _forged_ref(second, scope_id="merchant-request-scope")],
    }
    command = command.model_copy(update={"verified_evidence_refs": cases[case_name]})

    await _assert_create_rejected_atomically(session, command)


@pytest.mark.asyncio
async def test_create_rejects_existing_snapshot_with_divergent_evidence_without_new_rows(
    session: AsyncSession,
    seeded_session,
) -> None:
    tenant_id = seeded_session["tenant"].id
    command_ref = await _seed_canonical_evidence(session, tenant_id=tenant_id, suffix="command")
    snapshot_ref = await _seed_canonical_evidence(session, tenant_id=tenant_id, suffix="snapshot")
    command = await _create_command_with_canonical_evidence(
        session,
        seeded_session,
        [command_ref],
        verified_refs=[command_ref],
        thread_id="phase64-2-existing-snapshot-divergence",
    )
    snapshot_action = {
        **command.proposed_action,
        "evidence_refs": canonical_evidence_projection([snapshot_ref]),
    }
    snapshot_action_hash = compute_action_payload_hash(snapshot_action)
    persisted = await persist_action_safety_snapshot(
        session,
        tenant_id=command.tenant_id,
        run_id=command.run_id,
        proposed_action=snapshot_action,
        action_payload_hash=snapshot_action_hash,
        policy_config_version=command.policy_config_version,
        risk_config_version=command.risk_config_version,
        retrieval_config_version=command.retrieval_config_version,
        evidence_refs=[snapshot_ref],
        target_merchant_id=command.target_merchant_id,
        target_merchant_ref=command.target_merchant_ref.model_dump(mode="json") if command.target_merchant_ref else None,
        business_fact_refs=[ref.model_dump(mode="json") for ref in command.business_fact_refs],
        created_at=command.created_at,
        created_by=command.requested_by,
    )
    command = command.model_copy(
        update={
            "proposed_action": snapshot_action,
            "action_payload_hash": snapshot_action_hash,
            "safety_snapshot_ref": persisted.safety_snapshot_ref,
            "safety_snapshot_hash": persisted.safety_snapshot_hash,
        }
    )
    before = await _approval_counts(session)
    assert before[ActionSafetySnapshot.__tablename__] == 1

    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).create_request(command)

    assert exc.value.code == "approval_not_executable"
    assert await _approval_counts(session) == before
