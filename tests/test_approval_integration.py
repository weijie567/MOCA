from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.api.main import app
from src.db.models import ActionDraft, AgentRun, ApprovalRequest
from src.repositories.approval_repo import ApprovalRepository


pytestmark = pytest.mark.asyncio


async def test_high_risk_approve_flow_interrupts_resumes_executes_action(
    client: AsyncClient,
    session: AsyncSession,
    auth_headers,
    mock_graph,
    agent_test_user,
    approval_test_user,
    monkeypatch,
):
    monkeypatch.setattr(app.state, "agent_graph", mock_graph, raising=False)

    chat_response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "请给ORD-TEST-001补偿600元", "thread_id": f"approve-{uuid4()}"},
        headers=await auth_headers(agent_test_user.username),
    )
    chat_payload = chat_response.json()
    approval_id = UUID(chat_payload["data"]["approval_id"])
    run_id = UUID(chat_payload["data"]["run_id"])

    interrupted_run = await session.get(AgentRun, run_id)
    pending_approval = await session.get(ApprovalRequest, approval_id)

    assert chat_response.status_code == 200
    assert chat_payload["data"]["status"] == "interrupted"
    assert interrupted_run is not None
    assert interrupted_run.final_status == "interrupted"
    assert pending_approval is not None
    assert pending_approval.status == "pending"

    decision_response = await client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json={"decision": "approve", "reason": "Within policy"},
        headers=await auth_headers(approval_test_user.username),
    )
    decision_payload = decision_response.json()
    await session.refresh(interrupted_run)
    await session.refresh(pending_approval)
    draft = (
        await session.execute(
            select(ActionDraft).where(
                ActionDraft.run_id == run_id,
                ActionDraft.approval_request_id == approval_id,
            )
        )
    ).scalar_one()

    assert decision_response.status_code == 200
    assert decision_payload["data"]["status"] == "approved"
    assert pending_approval.status == "approved"
    assert interrupted_run.final_status == "completed"
    assert draft.idempotency_key == f"{run_id}_{approval_id}_issue_coupon_"
    assert draft.action_type == "issue_coupon"
    assert interrupted_run.final_response is not None
    assert "补偿草稿已创建" in interrupted_run.final_response


async def test_high_risk_reject_flow_completes_without_action(
    client: AsyncClient,
    session: AsyncSession,
    auth_headers,
    mock_graph,
    agent_test_user,
    approval_test_user,
    monkeypatch,
):
    monkeypatch.setattr(app.state, "agent_graph", mock_graph, raising=False)

    chat_response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "请给ORD-TEST-001补偿600元", "thread_id": f"reject-{uuid4()}"},
        headers=await auth_headers(agent_test_user.username),
    )
    approval_id = UUID(chat_response.json()["data"]["approval_id"])
    run_id = UUID(chat_response.json()["data"]["run_id"])

    decision_response = await client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json={"decision": "reject", "reason": "Too expensive"},
        headers=await auth_headers(approval_test_user.username),
    )
    approval = await session.get(ApprovalRequest, approval_id)
    run = await session.get(AgentRun, run_id)
    draft_count = await _action_draft_count(session, run_id)

    assert decision_response.status_code == 200
    assert approval is not None
    assert approval.status == "rejected"
    assert draft_count == 0
    assert run is not None
    assert run.final_status == "completed"
    assert run.final_response is not None
    assert "Too expensive" in run.final_response


async def test_low_risk_policy_query_bypasses_approval(
    client: AsyncClient,
    session: AsyncSession,
    auth_headers,
    mock_graph,
    agent_test_user,
    monkeypatch,
):
    monkeypatch.setattr(app.state, "agent_graph", mock_graph, raising=False)

    response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "七天无理由退款政策规则是什么？", "thread_id": f"low-risk-{uuid4()}"},
        headers=await auth_headers(agent_test_user.username),
    )
    payload = response.json()
    run_id = UUID(payload["data"]["trace_summary"]["run_id"])
    approval_count = (
        await session.execute(select(func.count()).select_from(ApprovalRequest).where(ApprovalRequest.run_id == run_id))
    ).scalar_one()
    run = await session.get(AgentRun, run_id)

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["trace_summary"]["final_status"] == "completed"
    assert "approval_id" not in payload["data"]
    assert approval_count == 0
    assert run is not None
    assert run.final_status == "completed"


async def test_expired_approval_decision_returns_409(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    auth_headers,
    mock_graph,
    approval_test_user,
    monkeypatch,
):
    monkeypatch.setattr(app.state, "agent_graph", mock_graph, raising=False)
    approval = await _create_manual_approval(
        session,
        tenant_id=seeded_session["tenant"].id,
        requested_by=seeded_session["users"]["cs_zhang"].id,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "approve", "reason": "Expired"},
        headers=await auth_headers(approval_test_user.username),
    )
    await session.refresh(approval)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EXPIRED"
    assert approval.status == "expired"


async def test_idempotent_approve_does_not_duplicate_action_draft(
    client: AsyncClient,
    session: AsyncSession,
    auth_headers,
    mock_graph,
    agent_test_user,
    approval_test_user,
    monkeypatch,
):
    monkeypatch.setattr(app.state, "agent_graph", mock_graph, raising=False)

    chat_response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "请给ORD-TEST-001补偿600元", "thread_id": f"idempotent-{uuid4()}"},
        headers=await auth_headers(agent_test_user.username),
    )
    approval_id = UUID(chat_response.json()["data"]["approval_id"])
    run_id = UUID(chat_response.json()["data"]["run_id"])
    headers = await auth_headers(approval_test_user.username)

    first_response = await client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json={"decision": "approve", "reason": "Within policy"},
        headers=headers,
    )
    second_response = await client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json={"decision": "approve", "reason": "Within policy"},
        headers=headers,
    )
    draft_count = await _action_draft_count(session, run_id)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["data"]["status"] == "approved"
    assert draft_count == 1


async def _create_manual_approval(
    session: AsyncSession,
    *,
    tenant_id,
    requested_by,
    expires_at: datetime,
) -> ApprovalRequest:
    run_id = uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=f"manual-approval-{run_id}",
        tenant_id=str(tenant_id),
        user_id=str(requested_by),
        input_query="manual expired approval",
        final_status="interrupted",
        final_response=None,
        started_at=now,
        completed_at=now,
        total_latency_ms=1,
    )
    repo = ApprovalRepository(session)
    approval = await repo.create(
        run_id=run_id,
        tenant_id=tenant_id,
        requested_by=requested_by,
        proposed_action={"action_type": "issue_coupon", "amount": "600"},
        risk_level="high",
        risk_rule_ref="HR-01",
        risk_reason="Compensation amount exceeds threshold",
        expires_at=expires_at,
        thread_id=f"manual-approval-{run_id}",
    )
    await session.commit()
    return approval


async def _action_draft_count(session: AsyncSession, run_id: UUID) -> int:
    return (
        await session.execute(select(func.count()).select_from(ActionDraft).where(ActionDraft.run_id == run_id))
    ).scalar_one()
