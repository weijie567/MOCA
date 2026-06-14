from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.service import create_coupon_grant_draft
from src.agent.trace import write_agent_run


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
    run_id = await _create_run(session, tenant_id=str(tenant_id), user_id=str(user_id))
    other_run_id = await _create_run(session, tenant_id=str(other_tenant_id), user_id=str(other_user_id))

    created = await create_coupon_grant_draft(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        run_id=str(run_id),
        approval_request_id=None,
        idempotency_key="shared-draft-key",
        action_type="issue_coupon",
        payload={"target_id": "refund-1"},
        session=session,
    )
    conflicted = await create_coupon_grant_draft(
        tenant_id=str(other_tenant_id),
        user_id=str(other_user_id),
        run_id=str(other_run_id),
        approval_request_id=None,
        idempotency_key="shared-draft-key",
        action_type="issue_coupon",
        payload={"target_id": "refund-2"},
        session=session,
    )

    assert created["status"] == "success"
    assert conflicted["status"] == "error"
    assert conflicted["error"]["error_code"] == "IDEMPOTENCY_CONFLICT"
    assert conflicted["error"]["retryable"] is False
