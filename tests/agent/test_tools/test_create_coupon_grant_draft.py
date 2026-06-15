from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.service import create_coupon_grant_draft
from src.agent.trace import write_agent_run
from src.approvals.service import ApprovalService
from src.db.models import ApprovalAssignment, ApprovalLevel, ApprovalRequest
from tests.approvals.test_service_transitions import _create_command, _decision_command


async def _create_run(session: AsyncSession, *, tenant_id: str, user_id: str) -> UUID:
    run_uuid = uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_uuid),
        thread_id=f"create-draft-test-{run_uuid}",
        tenant_id=tenant_id,
        user_id=user_id,
        input_query="create draft test",
        final_status="completed",
        final_response="ok",
        started_at=now,
        completed_at=now,
        total_latency_ms=1,
    )
    return run_uuid


async def _approval_context(
    session: AsyncSession,
    seeded_session: dict,
    *,
    tenant_key: str = "tenant",
    user_key: str = "cs_zhang",
    status: str = "pending",
) -> tuple[ApprovalRequest, ApprovalLevel, ApprovalAssignment]:
    tenant_id = seeded_session[tenant_key].id
    user_id = seeded_session["users"][user_key].id
    run_id = await _create_run(session, tenant_id=str(tenant_id), user_id=str(user_id))
    created = await ApprovalService(session).create_request(
        _create_command(tenant_id=tenant_id, run_id=run_id, requested_by=user_id)
    )
    request = await session.get(ApprovalRequest, created.approval_id)
    assert request is not None
    level = (
        await session.execute(select(ApprovalLevel).where(ApprovalLevel.approval_request_id == request.id))
    ).scalar_one()
    assignment = (
        await session.execute(select(ApprovalAssignment).where(ApprovalAssignment.approval_level_id == level.id))
    ).scalar_one()
    if status == "approved":
        await ApprovalService(session).decide(
            _decision_command(
                request,
                level,
                assignment,
                actor_id=seeded_session["users"]["approval_manager"].id,
            )
        )
        await session.refresh(request)
        await session.refresh(level)
        await session.refresh(assignment)
    elif status != "pending":
        request.status = status
        await session.flush()
    return request, level, assignment


def _binding_kwargs(request: ApprovalRequest, **overrides):
    payload = {
        "approval_request_id": str(request.id),
        "action_payload_hash": request.action_payload_hash,
        "safety_snapshot_ref": request.safety_snapshot_ref,
        "safety_snapshot_hash": request.safety_snapshot_hash,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_invalid_uuid_is_non_retryable(session: AsyncSession) -> None:
    result = await create_coupon_grant_draft(
        tenant_id="not-a-uuid",
        user_id=str(uuid4()),
        run_id=str(uuid4()),
        approval_request_id=None,
        idempotency_key="invalid-uuid",
        action_type="issue_coupon",
        payload={"target_id": "refund-1"},
        session=session,
        action_payload_hash="sha256:" + "1" * 64,
        safety_snapshot_ref="snapshot:test",
        safety_snapshot_hash="sha256:" + "2" * 64,
    )

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "INVALID_REQUEST"
    assert result["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_cross_tenant_idempotency_conflict_is_non_retryable(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    tenant_id = seeded_session["tenant"].id
    other_tenant_id = seeded_session["other_tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    other_user_id = seeded_session["users"]["other_support"].id
    request, _level, _assignment = await _approval_context(session, seeded_session)
    other_request, _other_level, _other_assignment = await _approval_context(
        session,
        seeded_session,
        tenant_key="other_tenant",
        user_key="other_support",
    )

    created = await create_coupon_grant_draft(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        run_id=str(request.run_id),
        approval_request_id=None,
        idempotency_key="shared-draft-key",
        action_type="issue_coupon",
        payload={"target_id": "refund-1"},
        session=session,
        action_payload_hash=request.action_payload_hash,
        safety_snapshot_ref=request.safety_snapshot_ref,
        safety_snapshot_hash=request.safety_snapshot_hash,
    )
    conflicted = await create_coupon_grant_draft(
        tenant_id=str(other_tenant_id),
        user_id=str(other_user_id),
        run_id=str(other_request.run_id),
        approval_request_id=None,
        idempotency_key="shared-draft-key",
        action_type="issue_coupon",
        payload={"target_id": "refund-2"},
        session=session,
        action_payload_hash=other_request.action_payload_hash,
        safety_snapshot_ref=other_request.safety_snapshot_ref,
        safety_snapshot_hash=other_request.safety_snapshot_hash,
    )

    assert created["status"] == "success"
    assert conflicted["status"] == "error"
    assert conflicted["error"]["error_code"] == "IDEMPOTENCY_CONFLICT"
    assert conflicted["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_requires_approved_request_binding(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    request, _level, _assignment = await _approval_context(session, seeded_session, status="approved")
    user_id = seeded_session["users"]["cs_zhang"].id

    result = await create_coupon_grant_draft(
        tenant_id=str(request.tenant_id),
        user_id=str(user_id),
        run_id=str(request.run_id),
        idempotency_key="approved-draft-key",
        action_type="issue_coupon",
        payload={"target_id": "refund-1"},
        session=session,
        **_binding_kwargs(request),
    )

    assert result["status"] == "success"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "needs_info", "superseded", "expired"])
async def test_create_coupon_grant_draft_rejects_unapproved_request_status(
    session: AsyncSession,
    seeded_session: dict,
    status: str,
) -> None:
    request, _level, _assignment = await _approval_context(session, seeded_session, status=status)
    user_id = seeded_session["users"]["cs_zhang"].id

    result = await create_coupon_grant_draft(
        tenant_id=str(request.tenant_id),
        user_id=str(user_id),
        run_id=str(request.run_id),
        idempotency_key=f"{status}-draft-key",
        action_type="issue_coupon",
        payload={"target_id": "refund-1"},
        session=session,
        **_binding_kwargs(request),
    )

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "APPROVAL_BINDING_MISMATCH"
    assert result["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_rejects_wrong_hash_binding(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    request, _level, _assignment = await _approval_context(session, seeded_session, status="approved")
    user_id = seeded_session["users"]["cs_zhang"].id

    result = await create_coupon_grant_draft(
        tenant_id=str(request.tenant_id),
        user_id=str(user_id),
        run_id=str(request.run_id),
        idempotency_key="wrong-hash-draft-key",
        action_type="issue_coupon",
        payload={"target_id": "refund-1"},
        session=session,
        **_binding_kwargs(request, action_payload_hash="sha256:" + "9" * 64),
    )

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "ACTION_BINDING_MISMATCH"
    assert result["error"]["retryable"] is False
