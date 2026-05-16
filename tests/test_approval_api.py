from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.api.main import app
from src.auth.jwt import create_access_token
from src.db.models import AgentRun, AgentStep, ApprovalRequest, ApprovalStep, User
from src.repositories.approval_repo import ApprovalRepository


class FakeResumeGraph:
    def __init__(self, final_response: str = "resumed"):
        self.calls: list[tuple[object, dict]] = []
        self.final_response = final_response

    async def ainvoke(self, command, config):
        self.calls.append((command, config))
        return {
            "final_response": self.final_response,
            "trace_steps": [
                {"node": "receive_request", "status": "completed"},
                {"node": "approval_gate", "status": "completed"},
                {"node": "final_response", "status": "completed"},
            ],
        }


class FakeInterruptGraph:
    def __init__(self, payload: dict, *, raises: bool = False):
        self.payload = payload
        self.raises = raises

    async def ainvoke(self, input_state, config):
        if self.raises:
            raise FakeGraphInterrupt([SimpleNamespace(value=self.payload)])
        return {"__interrupt__": [SimpleNamespace(value=self.payload)]}

    async def aget_state(self, config):
        return SimpleNamespace(
            values={
                "current_run_id": self.payload["run_id"],
                "trace_steps": [
                    {"node": "receive_request", "status": "completed"},
                    {"node": "approval_gate", "status": "interrupted"},
                ],
            }
        )


class FakeGraphInterrupt(Exception):
    pass


def _auth_header(user: User, scopes: list[str]) -> dict[str, str]:
    token = create_access_token(
        {
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "role": user.role,
            "scopes": scopes,
        }
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_run(session: AsyncSession, *, tenant_id: UUID, user_id: UUID) -> UUID:
    run_id = uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=f"approval-api-{run_id}",
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        input_query="审批接口测试",
        final_status="interrupted",
        final_response=None,
        started_at=now,
        completed_at=now,
        total_latency_ms=10,
    )
    return run_id


async def _create_approval(
    session: AsyncSession,
    seeded_session,
    *,
    requested_by: User | None = None,
    status: str = "pending",
    expires_at: datetime | None = None,
    tenant_key: str = "tenant",
    thread_id: str = "approval-thread-1",
) -> ApprovalRequest:
    tenant = seeded_session[tenant_key]
    requester = requested_by or seeded_session["users"]["cs_zhang"]
    run_id = await _create_run(session, tenant_id=tenant.id, user_id=requester.id)
    repo = ApprovalRepository(session)
    approval = await repo.create(
        run_id=run_id,
        tenant_id=tenant.id,
        requested_by=requester.id,
        proposed_action={"action_type": "issue_coupon", "target_id": "RF-TEST-001", "amount": "600"},
        risk_level="high",
        risk_rule_ref="HR-01",
        risk_reason="Compensation exceeds threshold",
        expires_at=expires_at or datetime.now(UTC) + timedelta(hours=1),
        thread_id=thread_id,
    )
    approval.status = status
    if status in {"approved", "rejected"}:
        approval.decision = "approve" if status == "approved" else "reject"
        approval.decided_by = seeded_session["users"]["admin_user"].id
        approval.decided_at = datetime.now(UTC)
    await session.commit()
    return approval


@pytest.mark.asyncio
async def test_decide_approve_returns_success_and_resumes_graph(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    approval = await _create_approval(session, seeded_session, thread_id="thread-approve")
    graph = FakeResumeGraph("approved response")
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "approve", "reason": "valid"},
        headers=await _admin_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["status"] == "approved"
    assert len(graph.calls) == 1
    command, config = graph.calls[0]
    assert command.resume["decision"] == "approve"
    assert config["configurable"]["thread_id"] == f"{approval.tenant_id}:{approval.requested_by}:thread-approve"


@pytest.mark.asyncio
async def test_decide_reject_returns_success_and_resumes_graph(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    approval = await _create_approval(session, seeded_session, thread_id="thread-reject")
    graph = FakeResumeGraph("rejected response")
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "reject", "reason": "not enough evidence"},
        headers=await _admin_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["data"]["status"] == "rejected"
    assert len(graph.calls) == 1
    command, config = graph.calls[0]
    assert command.resume["decision"] == "reject"
    assert config["configurable"]["thread_id"] == f"{approval.tenant_id}:{approval.requested_by}:thread-reject"


@pytest.mark.asyncio
async def test_decide_self_approval_returns_403(client: AsyncClient, session: AsyncSession, seeded_session, monkeypatch):
    admin = seeded_session["users"]["admin_user"]
    approval = await _create_approval(session, seeded_session, requested_by=admin)
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "approve"},
        headers=await _admin_headers(client),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SELF_APPROVAL"


@pytest.mark.asyncio
async def test_decide_insufficient_role_returns_403(client: AsyncClient, session: AsyncSession, seeded_session, monkeypatch):
    approval = await _create_approval(session, seeded_session)
    support = seeded_session["users"]["cs_zhang"]
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "approve"},
        headers=_auth_header(support, ["approvals:review"]),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_decide_expired_approval_returns_409(client: AsyncClient, session: AsyncSession, seeded_session, monkeypatch):
    approval = await _create_approval(session, seeded_session, expires_at=datetime.now(UTC) - timedelta(minutes=1))
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "approve"},
        headers=await _admin_headers(client),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EXPIRED"


@pytest.mark.asyncio
async def test_decide_idempotent_approve_returns_success_without_resume(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    approval = await _create_approval(session, seeded_session, status="approved")
    graph = FakeResumeGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "approve"},
        headers=await _admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"
    assert graph.calls == []


@pytest.mark.asyncio
async def test_decide_approved_then_reject_returns_409(client: AsyncClient, session: AsyncSession, seeded_session):
    approval = await _create_approval(session, seeded_session, status="approved")

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "reject"},
        headers=await _admin_headers(client),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_decide_rejected_then_approve_returns_409(client: AsyncClient, session: AsyncSession, seeded_session):
    approval = await _create_approval(session, seeded_session, status="rejected")

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "approve"},
        headers=await _admin_headers(client),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_get_approval_returns_details(client: AsyncClient, session: AsyncSession, seeded_session):
    approval = await _create_approval(session, seeded_session)

    response = await client.get(f"/api/v1/approvals/{approval.id}", headers=await _admin_headers(client))
    payload = response.json()

    assert response.status_code == 200
    assert payload["data"]["id"] == str(approval.id)
    assert payload["data"]["risk_rule_ref"] == "HR-01"


@pytest.mark.asyncio
async def test_list_pending_approvals_returns_unexpired_pending_only(client: AsyncClient, session: AsyncSession, seeded_session):
    pending = await _create_approval(session, seeded_session)
    expired = await _create_approval(session, seeded_session, expires_at=datetime.now(UTC) - timedelta(minutes=1))
    approved = await _create_approval(session, seeded_session, status="approved")

    response = await client.get("/api/v1/approvals", headers=await _admin_headers(client))
    payload = response.json()
    ids = {item["id"] for item in payload["data"]["approvals"]}

    assert response.status_code == 200
    assert str(pending.id) in ids
    assert str(expired.id) not in ids
    assert str(approved.id) not in ids


@pytest.mark.asyncio
async def test_cross_tenant_get_returns_404(client: AsyncClient, session: AsyncSession, seeded_session):
    approval = await _create_approval(session, seeded_session)
    other_user = seeded_session["users"]["other_support"]

    response = await client.get(
        f"/api/v1/approvals/{approval.id}",
        headers=_auth_header(other_user, ["approvals:review"]),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_agent_run_status_updates_to_completed_after_approve(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    approval = await _create_approval(session, seeded_session)
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph("approved final"), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "approve"},
        headers=await _admin_headers(client),
    )

    run = await session.get(AgentRun, approval.run_id)
    assert response.status_code == 200
    assert run is not None
    assert run.final_status == "completed"
    assert run.final_response == "approved final"


@pytest.mark.asyncio
async def test_agent_run_status_updates_to_completed_after_reject(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    approval = await _create_approval(session, seeded_session)
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph("rejected final"), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "reject"},
        headers=await _admin_headers(client),
    )

    run = await session.get(AgentRun, approval.run_id)
    assert response.status_code == 200
    assert run is not None
    assert run.final_status == "completed"
    assert run.final_response == "rejected final"


@pytest.mark.asyncio
async def test_agent_chat_interrupt_result_creates_approval_and_interrupted_run(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    support = seeded_session["users"]["cs_zhang"]
    run_id = uuid4()
    payload = _interrupt_payload(run_id)
    monkeypatch.setattr(app.state, "agent_graph", FakeInterruptGraph(payload), raising=False)

    response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "给这个订单补偿600元", "thread_id": "chat-interrupt-result"},
        headers=await _support_headers(client),
    )
    body = response.json()

    approval = await session.get(ApprovalRequest, UUID(body["data"]["approval_id"]))
    run = await session.get(AgentRun, run_id)
    steps = (await session.execute(select(AgentStep).where(AgentStep.run_id == run_id))).scalars().all()

    assert response.status_code == 200
    assert body["data"]["status"] == "interrupted"
    assert approval is not None
    assert approval.thread_id == "chat-interrupt-result"
    assert approval.requested_by == support.id
    assert run is not None
    assert run.final_status == "interrupted"
    assert [step.node_name for step in steps] == ["receive_request", "approval_gate"]


@pytest.mark.asyncio
async def test_agent_chat_interrupt_exception_creates_approval_step(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch,
):
    run_id = uuid4()
    payload = _interrupt_payload(run_id)
    monkeypatch.setattr(app.state, "agent_graph", FakeInterruptGraph(payload, raises=True), raising=False)

    response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "给这个订单补偿600元", "thread_id": "chat-interrupt-exception"},
        headers=await _support_headers(client),
    )
    body = response.json()

    steps = (
        await session.execute(
            select(ApprovalStep).where(ApprovalStep.approval_request_id == UUID(body["data"]["approval_id"]))
        )
    ).scalars().all()

    assert response.status_code == 200
    assert body["data"]["status"] == "interrupted"
    assert [step.event_type for step in steps] == ["created"]


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": "admin_user", "password": "moca2024"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def _support_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": "cs_zhang", "password": "moca2024"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _interrupt_payload(run_id: UUID) -> dict:
    return {
        "run_id": str(run_id),
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "proposed_action": {"action_type": "issue_coupon", "amount": "600"},
        "risk_level": "high",
        "risk_rule_ref": "HR-01",
        "risk_reason": "Compensation exceeds threshold",
        "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
    }
