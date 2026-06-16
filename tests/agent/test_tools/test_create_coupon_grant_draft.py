from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.service import create_coupon_grant_draft
from src.agent.trace import write_agent_run
from src.approvals.service import ApprovalService
from src.db.models import ActionDraft, AgentTraceEvent, ApprovalAssignment, ApprovalLevel, ApprovalRequest
from src.tools.contracts import ToolCallContext
from src.tools.executors.action import ActionToolExecutor
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


def _tool_context(request: ApprovalRequest, *, user_id: str) -> ToolCallContext:
    return ToolCallContext(
        tenant_id=str(request.tenant_id),
        user_id=user_id,
        role="support",
        permissions=["tool:create_coupon_grant_draft"],
        merchant_scope={"merchant_ids": ["*"]},
        session_id=None,
        thread_id=f"draft-thread-{request.id}",
        run_id=str(request.run_id),
        trace_id=f"trace-{request.id}",
        request_id=f"request-{request.id}",
        tool_call_id=f"{request.run_id}:action_draft:create_coupon_grant_draft",
        caller_node="action_draft",
        deadline_at=datetime.now(UTC),
        attempt=1,
        max_attempts=1,
        idempotency_key="unsafe-caller-key",
        approval_ref=str(request.id),
        safety_snapshot_ref=request.safety_snapshot_ref,
        policy_snapshot_ref=None,
    )


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
async def test_create_coupon_grant_draft_cross_tenant_caller_key_is_ignored(
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
    other_created = await create_coupon_grant_draft(
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
    draft = await session.get(ActionDraft, UUID(created["data"]["draft_id"]))
    other_draft = await session.get(ActionDraft, UUID(other_created["data"]["draft_id"]))

    assert created["status"] == "success"
    assert other_created["status"] == "success"
    assert draft is not None
    assert other_draft is not None
    assert draft.idempotency_key != other_draft.idempotency_key
    assert "shared-draft-key" not in draft.idempotency_key
    assert "shared-draft-key" not in other_draft.idempotency_key


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
    assert result["data"]["draft_outcome"]["status"] == "not_executed_demo"
    assert result["data"]["draft_outcome"]["external_side_effect"] is False
    assert result["data"]["action_result"]["status"] != "success"


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


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_requires_target_id(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    request, _level, _assignment = await _approval_context(session, seeded_session)
    user_id = seeded_session["users"]["cs_zhang"].id

    result = await create_coupon_grant_draft(
        tenant_id=str(request.tenant_id),
        user_id=str(user_id),
        run_id=str(request.run_id),
        approval_request_id=None,
        idempotency_key="unsafe-caller-key",
        action_type="issue_coupon",
        payload={"amount": "25.00"},
        session=session,
        action_payload_hash=request.action_payload_hash,
        safety_snapshot_ref=request.safety_snapshot_ref,
        safety_snapshot_hash=request.safety_snapshot_hash,
    )

    assert result["status"] == "error"
    assert result["error"]["error_code"] == "TARGET_ID_REQUIRED"
    assert result["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_auto_allowed_key_is_service_owned(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    request, _level, _assignment = await _approval_context(session, seeded_session)
    user_id = seeded_session["users"]["cs_zhang"].id

    result = await create_coupon_grant_draft(
        tenant_id=str(request.tenant_id),
        user_id=str(user_id),
        run_id=str(request.run_id),
        approval_request_id=None,
        idempotency_key="unsafe-caller-key",
        action_type="issue_coupon",
        payload={"target_id": "RF-1001"},
        session=session,
        action_payload_hash=request.action_payload_hash,
        safety_snapshot_ref=request.safety_snapshot_ref,
        safety_snapshot_hash=request.safety_snapshot_hash,
    )
    draft = await session.get(ActionDraft, UUID(result["data"]["draft_id"]))

    assert result["status"] == "success"
    assert draft is not None
    assert draft.draft_outcome["status"] == "not_executed_demo"
    assert draft.draft_outcome["external_side_effect"] is False
    assert result["data"]["action_draft"]["target_id"] == "RF-1001"
    assert result["data"]["draft_outcome"]["draft_id"] == str(draft.id)
    assert result["data"]["action_result"]["status"] == "draft_created"
    assert draft.idempotency_key == (
        f"{request.tenant_id}:{request.run_id}:auto_allowed:issue_coupon:RF-1001:{request.action_payload_hash}"
    )
    assert "unsafe-caller-key" not in draft.idempotency_key


@pytest.mark.asyncio
async def test_create_coupon_grant_draft_approved_key_uses_trusted_revision(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    request, _level, _assignment = await _approval_context(session, seeded_session, status="approved")
    user_id = seeded_session["users"]["cs_zhang"].id

    result = await create_coupon_grant_draft(
        tenant_id=str(request.tenant_id),
        user_id=str(user_id),
        run_id=str(request.run_id),
        idempotency_key="unsafe-caller-key",
        action_type="issue_coupon",
        payload={"target_id": "RF-1001"},
        session=session,
        **_binding_kwargs(request),
    )
    draft = await session.get(ActionDraft, UUID(result["data"]["draft_id"]))

    assert result["status"] == "success"
    assert draft is not None
    assert draft.approval_revision_ref == f"approval_request/{request.id}@rev{request.revision}"
    assert result["data"]["action_draft"]["approval_revision_ref"] == draft.approval_revision_ref
    assert result["data"]["draft_outcome"]["status"] == "not_executed_demo"
    assert draft.idempotency_key == (
        f"{request.tenant_id}:{request.run_id}:approval_revision_{request.revision}:"
        f"issue_coupon:RF-1001:{request.action_payload_hash}"
    )
    assert "unsafe-caller-key" not in draft.idempotency_key


@pytest.mark.asyncio
async def test_action_executor_emits_safe_action_draft_created_event(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    request, _level, _assignment = await _approval_context(session, seeded_session, status="approved")
    user_id = str(seeded_session["users"]["cs_zhang"].id)
    ctx = _tool_context(request, user_id=user_id)

    result = await ActionToolExecutor(session).execute(
        "create_coupon_grant_draft",
        {
            "approval_request_id": str(request.id),
            "action_type": "issue_coupon",
            "payload": {"target_id": "RF-1001", "amount": "25.00"},
            "action_payload_hash": request.action_payload_hash,
            "safety_snapshot_ref": request.safety_snapshot_ref,
            "safety_snapshot_hash": request.safety_snapshot_hash,
        },
        ctx,
    )

    rows = (
        await session.execute(
            select(AgentTraceEvent).where(
                AgentTraceEvent.run_id == request.run_id,
                AgentTraceEvent.event_type == "action_draft_created",
            )
        )
    ).scalars().all()

    assert result.status == "success"
    assert len(rows) == 1
    event = rows[0]
    assert event.thread_id == ctx.thread_id
    assert event.trace_id == ctx.trace_id
    assert set(event.resource_refs) == {
        "draft_id",
        "target_id",
        "action_payload_hash",
        "safety_snapshot_hash",
    }
    assert event.resource_refs["draft_id"] == result.data["draft_id"]
    assert event.resource_refs["target_id"] == "RF-1001"
    assert event.resource_refs["action_payload_hash"] == request.action_payload_hash
    assert event.resource_refs["safety_snapshot_hash"] == request.safety_snapshot_hash
    assert event.redacted_payload == {
        "action_type": "issue_coupon",
        "execution_mode": "demo",
        "external_side_effect": False,
    }
    assert not any(row.event_type.startswith("action_execution_") for row in rows)
    assert "payload" not in event.resource_refs
    assert "payload" not in event.redacted_payload
    assert "arguments" not in event.redacted_payload
