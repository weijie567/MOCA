from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.main import app
from src.approvals.service import ApprovalService
from src.db.models import ActionDraft, AgentRun, ApprovalAssignment, ApprovalLevel, ApprovalRequest
from tests.approvals.test_service_transitions import (
    _canonical_phase34_binding,
    _create_command,
    _create_run,
)


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

    thread_id = f"approve-{uuid4()}"
    chat_response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "请给ORD-TEST-001补偿600元", "thread_id": thread_id},
        headers=await auth_headers(agent_test_user.username),
    )
    chat_payload = chat_response.json()
    approval_id = UUID(chat_payload["data"]["approval_id"])
    run_id = UUID(chat_payload["data"]["run_id"])

    interrupted_run = await session.get(AgentRun, run_id)
    pending_approval = await session.get(ApprovalRequest, approval_id)

    assert chat_response.status_code == 200
    assert chat_payload["data"]["status"] == "interrupted"
    assert chat_payload["data"]["expected_request_version"] == 1
    assert chat_payload["data"]["expected_level_version"] == 1
    assert chat_payload["data"]["expected_assignment_version"] == 1
    assert chat_payload["data"]["expected_revision"] == 1
    assert chat_payload["data"]["action_payload_hash"] == pending_approval.action_payload_hash
    assert chat_payload["data"]["safety_snapshot_hash"] == pending_approval.safety_snapshot_hash
    assert interrupted_run is not None
    assert interrupted_run.final_status == "interrupted"
    assert pending_approval is not None
    assert pending_approval.status == "pending"

    decision_response = await client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json=_decision_body_from_wait_payload(chat_payload["data"]),
        headers=await auth_headers("admin_user"),
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
    assert draft.action_type == "issue_coupon"
    assert draft.draft_outcome["status"] == "not_executed_demo"
    assert draft.draft_outcome["external_side_effect"] is False
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
    chat_payload = chat_response.json()
    approval_id = UUID(chat_payload["data"]["approval_id"])
    run_id = UUID(chat_payload["data"]["run_id"])

    decision_response = await client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json=_decision_body_from_wait_payload(chat_payload["data"], decision_type="reject", reason="Too expensive"),
        headers=await auth_headers("admin_user"),
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


async def test_expired_approval_decision_returns_409_conflict(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    auth_headers,
    mock_graph,
    approval_test_user,
    monkeypatch,
):
    monkeypatch.setattr(app.state, "agent_graph", mock_graph, raising=False)
    bundle = await _create_manual_approval(
        session,
        tenant_id=seeded_session["tenant"].id,
        requested_by=seeded_session["users"]["cs_zhang"].id,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle),
        headers=await auth_headers("admin_user"),
    )
    await session.refresh(bundle.approval)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
    assert bundle.approval.status == "pending"


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
    wait_payload = chat_response.json()["data"]
    approval_id = UUID(wait_payload["approval_id"])
    run_id = UUID(wait_payload["run_id"])
    headers = await auth_headers("admin_user")

    first_response = await client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json=_decision_body_from_wait_payload(wait_payload),
        headers=headers,
    )
    second_response = await client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json=_decision_body_from_wait_payload(wait_payload),
        headers=headers,
    )
    draft_count = await _action_draft_count(session, run_id)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json()["error"]["code"] == "CONFLICT"
    assert draft_count == 1


async def _create_manual_approval(
    session: AsyncSession,
    *,
    tenant_id,
    requested_by,
    expires_at: datetime,
):
    run_id = await _create_run(
        session,
        tenant_id=tenant_id,
        user_id=requested_by,
        thread_id=f"manual-approval-{uuid4()}",
    )
    binding_overrides = await _canonical_phase34_binding(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
    )
    run = await session.get(AgentRun, run_id)
    assert run is not None
    run.scope_classification = "business_merchant"
    run.target_merchant_id = binding_overrides["target_merchant_id"]
    run.target_merchant_ref = binding_overrides["target_merchant_ref"]
    run.scope_source = "target_merchant_binding_v1"
    run.scope_reason_codes = []
    await session.flush()
    result = await ApprovalService(session).create_request(
        _create_command(
            tenant_id=tenant_id,
            run_id=run_id,
            requested_by=requested_by,
            thread_id=f"manual-approval-{run_id}",
            expires_at=expires_at,
            **binding_overrides,
        )
    )
    approval = await session.get(ApprovalRequest, result.approval_id)
    assert approval is not None
    level = (
        await session.execute(select(ApprovalLevel).where(ApprovalLevel.approval_request_id == approval.id))
    ).scalar_one()
    assignment = (
        await session.execute(select(ApprovalAssignment).where(ApprovalAssignment.approval_level_id == level.id))
    ).scalar_one()
    await session.commit()
    return type("ApprovalBundle", (), {"approval": approval, "level": level, "assignment": assignment})()


def _decision_body(bundle, decision_type: str = "approve") -> dict:
    return {
        "decision_type": decision_type,
        "expected_request_version": bundle.approval.version,
        "expected_level_version": bundle.level.version,
        "expected_assignment_version": bundle.assignment.version,
        "expected_revision": bundle.approval.revision,
        "action_payload_hash": bundle.approval.action_payload_hash,
        "safety_snapshot_hash": bundle.approval.safety_snapshot_hash,
        "reason": "Within policy",
    }


def _decision_body_from_wait_payload(
    wait_payload: dict,
    *,
    decision_type: str = "approve",
    reason: str = "Within policy",
) -> dict:
    return {
        "decision_type": decision_type,
        "expected_request_version": wait_payload["expected_request_version"],
        "expected_level_version": wait_payload["expected_level_version"],
        "expected_assignment_version": wait_payload["expected_assignment_version"],
        "expected_revision": wait_payload["expected_revision"],
        "action_payload_hash": wait_payload["action_payload_hash"],
        "safety_snapshot_hash": wait_payload["safety_snapshot_hash"],
        "reason": reason,
    }


async def _action_draft_count(session: AsyncSession, run_id: UUID) -> int:
    return (
        await session.execute(select(func.count()).select_from(ActionDraft).where(ActionDraft.run_id == run_id))
    ).scalar_one()
