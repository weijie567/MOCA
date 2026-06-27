from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.approvals.schemas import ApprovalDecisionCommand
from src.approvals.service import ApprovalService, ApprovalTransitionError
from src.db.models import ApprovalRequest
from src.repositories.action_draft_repo import ActionDraftRepository
from tests.approvals.test_service_transitions import (
    _approval_bundle,
    _create_run,
    _decision_command,
)


async def _create_action_draft(
    store: ActionDraftRepository,
    *,
    run_id: UUID,
    tenant_id: UUID,
    idempotency_key: str,
    action_type: str = "refund_override",
    target_id: str = "refund-100",
    action_payload_hash: str = "sha256:" + "a" * 64,
    safety_snapshot_ref: str = "action_safety_snapshot/test-snapshot",
    safety_snapshot_hash: str = "sha256:" + "b" * 64,
    payload: dict[str, object] | None = None,
):
    return await store.create_or_get(
        run_id=run_id,
        tenant_id=tenant_id,
        approval_request_id=None,
        idempotency_key=idempotency_key,
        action_type=action_type,
        target_id=target_id,
        approval_revision_ref="auto_allowed",
        action_payload_hash=action_payload_hash,
        safety_snapshot_ref=safety_snapshot_ref,
        safety_snapshot_hash=safety_snapshot_hash,
        payload=payload or {"amount": 100},
        draft_outcome={
            "schema_version": "draft_outcome.v1",
            "status": "not_executed_demo",
            "external_side_effect": False,
            "tenant_id": str(tenant_id),
            "run_id": str(run_id),
            "draft_id": None,
            "created_at": "2026-06-16T00:00:00.000Z",
        },
        execution_mode="demo",
        draft_version=1,
        lifecycle_status="active",
        retention_policy="phase14_demo_draft",
    )


@pytest.mark.asyncio
async def test_approval_service_accept_uses_exact_version_revision_and_hash_bindings(
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="approval-model-exact-binding",
    )
    actor_id = seeded_session["users"]["admin_user"].id
    command: ApprovalDecisionCommand = _decision_command(
        request,
        level,
        assignment,
        actor_id=actor_id,
        decision_type="approve",
    )

    result = await ApprovalService(session).decide(command)

    assert result.status == "approved"
    assert result.decision_type == "approve"
    assert result.revision == command.expected_revision == 1
    assert result.request_version == command.expected_request_version + 1
    assert result.level_version == command.expected_level_version + 1
    assert result.assignment_version == command.expected_assignment_version + 1
    assert result.action_payload_hash == command.action_payload_hash == request.action_payload_hash
    assert result.safety_snapshot_hash == command.safety_snapshot_hash == request.safety_snapshot_hash
    assert result.safety_snapshot_ref == request.safety_snapshot_ref
    assert result.resume_payload is not None
    assert result.resume_payload["schema_version"] == "approval_result.v1"
    assert result.resume_payload["revision"] == result.revision
    assert result.resume_payload["request_version"] == result.request_version


@pytest.mark.asyncio
async def test_duplicate_same_decision_after_terminal_conflicts(
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="approval-model-duplicate-terminal",
    )
    actor_id = seeded_session["users"]["admin_user"].id
    command = _decision_command(request, level, assignment, actor_id=actor_id, decision_type="approve")

    await ApprovalService(session).decide(command)

    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).decide(command)

    assert exc.value.code == "approval_conflict"


@pytest.mark.asyncio
async def test_changed_decision_after_terminal_status_conflicts(
    session: AsyncSession,
    seeded_session,
):
    request, level, assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="approval-model-terminal-conflict",
    )
    actor_id = seeded_session["users"]["admin_user"].id

    await ApprovalService(session).decide(
        _decision_command(request, level, assignment, actor_id=actor_id, decision_type="approve")
    )

    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).decide(
            _decision_command(
                request,
                level,
                assignment,
                actor_id=actor_id,
                decision_type="reject",
                expected_request_version=2,
                expected_level_version=2,
                expected_assignment_version=2,
            )
        )

    assert exc.value.code == "approval_conflict"


@pytest.mark.asyncio
async def test_legacy_v1_approval_row_cannot_authorize_service_decision(
    session: AsyncSession,
    seeded_session,
):
    tenant_id = seeded_session["tenant"].id
    requested_by = seeded_session["users"]["cs_zhang"].id
    actor_id = seeded_session["users"]["admin_user"].id
    run_id = await _create_run(
        session,
        tenant_id=tenant_id,
        user_id=requested_by,
        thread_id="legacy-v1-model-thread",
    )
    legacy = ApprovalRequest(
        run_id=run_id,
        tenant_id=tenant_id,
        schema_version="approval_request.v1",
        status="pending",
        revision=1,
        version=1,
        legacy_non_executable=True,
        requested_by=requested_by,
        proposed_action={"legacy_v1": True},
        risk_level="high",
        risk_rule_ref="legacy",
        risk_reason="legacy row",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        thread_id="legacy-v1-model-thread",
    )
    session.add(legacy)
    await session.flush()

    command = ApprovalDecisionCommand(
        approval_id=legacy.id,
        tenant_id=tenant_id,
        run_id=run_id,
        thread_id=legacy.thread_id,
        level_id=uuid4(),
        assignment_id=uuid4(),
        actor_id=actor_id,
        actor_role="admin",
        decision_type="approve",
        expected_request_version=1,
        expected_level_version=1,
        expected_assignment_version=1,
        expected_revision=1,
        action_payload_hash="sha256:" + "7" * 64,
        safety_snapshot_hash="sha256:" + "6" * 64,
        reason="legacy_v1 rows must fail closed",
    )

    with pytest.raises(ApprovalTransitionError) as exc:
        await ApprovalService(session).decide(command)

    assert exc.value.code == "approval_not_executable"


@pytest.mark.asyncio
async def test_action_draft_create_or_get_is_idempotent(session: AsyncSession, seeded_session):
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=user_id)
    store = ActionDraftRepository(session)

    created_draft, created = await _create_action_draft(
        store,
        run_id=run_id,
        tenant_id=tenant_id,
        idempotency_key="refund-override-1",
        payload={"amount": 100},
    )
    existing_draft, reused = await _create_action_draft(
        store,
        run_id=run_id,
        tenant_id=tenant_id,
        idempotency_key="refund-override-1",
        payload={"amount": 200},
    )

    assert created is True
    assert reused is False
    assert existing_draft.id == created_draft.id
    assert existing_draft.payload == {"amount": 100}


@pytest.mark.asyncio
async def test_action_draft_idempotency_key_is_tenant_scoped(session: AsyncSession, seeded_session):
    tenant_id = seeded_session["tenant"].id
    other_tenant_id = seeded_session["other_tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    other_user_id = seeded_session["users"]["other_support"].id
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=user_id)
    other_run_id = await _create_run(session, tenant_id=other_tenant_id, user_id=other_user_id)
    store = ActionDraftRepository(session)

    draft, created = await _create_action_draft(
        store,
        run_id=run_id,
        tenant_id=tenant_id,
        idempotency_key="shared-key",
        payload={"amount": 100},
    )
    other_draft, other_created = await _create_action_draft(
        store,
        run_id=other_run_id,
        tenant_id=other_tenant_id,
        idempotency_key="shared-key",
        payload={"amount": 100},
    )

    assert created is True
    assert other_created is True
    assert other_draft.id != draft.id
    assert other_draft.tenant_id == other_tenant_id


@pytest.mark.asyncio
async def test_approval_request_thread_id_is_stored_and_retrievable(session: AsyncSession, seeded_session):
    request, _level, _assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="approval-thread-1",
    )

    found = await ApprovalService(session).get_request(request.id, seeded_session["tenant"].id)

    assert found is not None
    assert found.thread_id == "approval-thread-1"


@pytest.mark.asyncio
async def test_approval_get_by_id_is_tenant_scoped(session: AsyncSession, seeded_session):
    request, _level, _assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="approval-tenant-scope",
    )

    assert await ApprovalService(session).get_request(request.id, seeded_session["other_tenant"].id) is None


@pytest.mark.asyncio
async def test_list_pending_requests_excludes_expired_and_terminal_approvals(
    session: AsyncSession,
    seeded_session,
):
    future, _future_level, _future_assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="approval-pending-future",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    expired, _expired_level, _expired_assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="approval-pending-expired",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    approved, approved_level, approved_assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="approval-pending-approved",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    await ApprovalService(session).decide(
        _decision_command(
            approved,
            approved_level,
            approved_assignment,
            actor_id=seeded_session["users"]["admin_user"].id,
            decision_type="approve",
        )
    )
    legacy_run_id = await _create_run(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id="approval-pending-legacy",
    )
    legacy = ApprovalRequest(
        tenant_id=seeded_session["tenant"].id,
        run_id=legacy_run_id,
        thread_id="approval-pending-legacy",
        schema_version="approval_request.v1",
        status="pending",
        revision=1,
        version=1,
        legacy_non_executable=True,
        requested_by=seeded_session["users"]["cs_zhang"].id,
        proposed_action=future.proposed_action,
        risk_level="high",
        risk_rule_ref="legacy:manual-review",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(legacy)
    await session.flush()

    pending = await ApprovalService(session).list_pending_requests(seeded_session["tenant"].id)
    pending_ids = {row.id for row in pending}

    assert future.id in pending_ids
    assert expired.id not in pending_ids
    assert approved.id not in pending_ids
    assert legacy.id not in pending_ids


@pytest.mark.asyncio
async def test_service_read_model_returns_v2_revision_hash_fields(session: AsyncSession, seeded_session):
    request, _level, _assignment = await _approval_bundle(
        session,
        seeded_session,
        thread_id="approval-model-read-v2",
    )

    found = await ApprovalService(session).get_request(request.id, request.tenant_id)

    assert found is not None
    assert found.schema_version == "approval_request.v2"
    assert found.revision == 1
    assert found.version == 1
    assert found.action_payload_hash == request.action_payload_hash
    assert found.safety_snapshot_ref == request.safety_snapshot_ref
    assert found.safety_snapshot_hash == request.safety_snapshot_hash
    assert found.legacy_non_executable is False
    assert (
        await session.execute(select(ApprovalRequest).where(ApprovalRequest.id == found.id))
    ).scalar_one().id == found.id
