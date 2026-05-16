from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.repositories.action_draft_repo import ActionDraftRepository
from src.repositories.approval_repo import ApprovalRepository


async def _create_run(session: AsyncSession, *, tenant_id: str, user_id: str) -> UUID:
    run_uuid = uuid4()
    run_id = str(run_uuid)
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=run_id,
        thread_id=f"approval-test-{run_id}",
        tenant_id=tenant_id,
        user_id=user_id,
        input_query="审批测试",
        final_status="interrupted",
        final_response=None,
        started_at=now,
        completed_at=now,
        total_latency_ms=10,
    )
    return run_uuid


async def _create_approval(
    session: AsyncSession,
    seeded_session,
    *,
    status: str = "pending",
    expires_at: datetime | None = None,
):
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=str(tenant_id), user_id=str(user_id))
    repo = ApprovalRepository(session)
    approval = await repo.create(
        run_id=run_id,
        tenant_id=tenant_id,
        requested_by=user_id,
        proposed_action={"type": "refund_override", "amount": 100},
        risk_level="high",
        risk_rule_ref="HR-02",
        risk_reason="manual approval required",
        expires_at=expires_at or datetime.now(UTC) + timedelta(hours=1),
        thread_id="approval-thread-1",
    )
    approval.status = status
    await session.flush()
    return approval


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("initial_status", "decision", "expected_status", "expected_error"),
    [
        ("pending", "approve", "approved", None),
        ("pending", "reject", "rejected", None),
        ("approved", "approve", "approved", None),
        ("approved", "reject", None, "conflict"),
        ("rejected", "reject", "rejected", None),
        ("rejected", "approve", None, "conflict"),
        ("expired", "approve", None, "expired"),
        ("expired", "reject", None, "expired"),
    ],
)
async def test_approval_decide_idempotency_matrix(
    session: AsyncSession,
    seeded_session,
    initial_status: str,
    decision: str,
    expected_status: str | None,
    expected_error: str | None,
):
    approval = await _create_approval(session, seeded_session, status=initial_status)
    repo = ApprovalRepository(session)
    tenant_id = seeded_session["tenant"].id
    reviewer_id = seeded_session["users"]["admin_user"].id

    if expected_error:
        with pytest.raises(ValueError, match=expected_error):
            await repo.decide(approval.id, tenant_id, decision=decision, reason="reviewed", decided_by=reviewer_id)
        return

    decided, transitioned = await repo.decide(
        approval.id,
        tenant_id,
        decision=decision,
        reason="reviewed",
        decided_by=reviewer_id,
    )

    assert decided.id == approval.id
    assert decided.status == expected_status
    if initial_status == "pending":
        assert transitioned is True
        assert decided.decision == decision
        assert decided.decided_by == reviewer_id
        assert decided.decided_at is not None
    else:
        assert transitioned is False


@pytest.mark.asyncio
async def test_action_draft_create_or_get_is_idempotent(session: AsyncSession, seeded_session):
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    run_id = await _create_run(session, tenant_id=str(tenant_id), user_id=str(user_id))
    repo = ActionDraftRepository(session)

    created_draft, created = await repo.create_or_get(
        run_id=run_id,
        tenant_id=tenant_id,
        approval_request_id=None,
        idempotency_key="refund-override-1",
        action_type="refund_override",
        payload={"amount": 100},
    )
    existing_draft, reused = await repo.create_or_get(
        run_id=run_id,
        tenant_id=tenant_id,
        approval_request_id=None,
        idempotency_key="refund-override-1",
        action_type="refund_override",
        payload={"amount": 200},
    )

    assert created is True
    assert reused is False
    assert existing_draft.id == created_draft.id
    assert existing_draft.payload == {"amount": 100}


@pytest.mark.asyncio
async def test_action_draft_rejects_cross_tenant_idempotency_reuse(session: AsyncSession, seeded_session):
    tenant_id = seeded_session["tenant"].id
    other_tenant_id = seeded_session["other_tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    other_user_id = seeded_session["users"]["other_support"].id
    run_id = await _create_run(session, tenant_id=str(tenant_id), user_id=str(user_id))
    other_run_id = await _create_run(session, tenant_id=str(other_tenant_id), user_id=str(other_user_id))
    repo = ActionDraftRepository(session)

    await repo.create_or_get(
        run_id=run_id,
        tenant_id=tenant_id,
        approval_request_id=None,
        idempotency_key="shared-key",
        action_type="refund_override",
        payload={"amount": 100},
    )

    with pytest.raises(ValueError, match="idempotency_key_conflict"):
        await repo.create_or_get(
            run_id=other_run_id,
            tenant_id=other_tenant_id,
            approval_request_id=None,
            idempotency_key="shared-key",
            action_type="refund_override",
            payload={"amount": 100},
        )


@pytest.mark.asyncio
async def test_approval_request_thread_id_is_stored_and_retrievable(session: AsyncSession, seeded_session):
    approval = await _create_approval(session, seeded_session)
    repo = ApprovalRepository(session)

    found = await repo.get_by_id(approval.id, seeded_session["tenant"].id)

    assert found is not None
    assert found.thread_id == "approval-thread-1"


@pytest.mark.asyncio
async def test_approval_get_by_id_is_tenant_scoped(session: AsyncSession, seeded_session):
    approval = await _create_approval(session, seeded_session)
    repo = ApprovalRepository(session)

    assert await repo.get_by_id(approval.id, seeded_session["other_tenant"].id) is None


@pytest.mark.asyncio
async def test_get_pending_by_tenant_excludes_expired_approvals(session: AsyncSession, seeded_session):
    future = await _create_approval(
        session,
        seeded_session,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    expired = await _create_approval(
        session,
        seeded_session,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    approved = await _create_approval(
        session,
        seeded_session,
        status="approved",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    repo = ApprovalRepository(session)

    pending = await repo.get_pending_by_tenant(seeded_session["tenant"].id)
    pending_ids = {row.id for row in pending}

    assert future.id in pending_ids
    assert expired.id not in pending_ids
    assert approved.id not in pending_ids
