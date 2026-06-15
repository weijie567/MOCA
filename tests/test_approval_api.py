from __future__ import annotations

from dataclasses import dataclass
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
from src.approvals.schemas import ApprovalDecisionCommand
from src.approvals.service import ApprovalService
from src.db.models import AgentRun, AgentStep, ApprovalAssignment, ApprovalLevel, ApprovalRequest, User
from tests.approvals.test_service_transitions import _create_command


@dataclass(frozen=True)
class ApprovalBundle:
    approval: ApprovalRequest
    level: ApprovalLevel
    assignment: ApprovalAssignment


class FakeResumeGraph:
    def __init__(self, final_response: str | None = "resumed"):
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


async def _create_run(session: AsyncSession, *, tenant_id: UUID, user_id: UUID, thread_id: str) -> UUID:
    run_id = uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=thread_id,
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
) -> ApprovalBundle:
    tenant = seeded_session[tenant_key]
    requester = requested_by or seeded_session["users"]["cs_zhang"]
    run_id = await _create_run(session, tenant_id=tenant.id, user_id=requester.id, thread_id=thread_id)
    created = await ApprovalService(session).create_request(
        _create_command(
            tenant_id=tenant.id,
            run_id=run_id,
            requested_by=requester.id,
            thread_id=thread_id,
            expires_at=expires_at or datetime.now(UTC) + timedelta(hours=1),
        )
    )
    approval = await session.get(ApprovalRequest, created.approval_id)
    assert approval is not None
    level = (
        await session.execute(select(ApprovalLevel).where(ApprovalLevel.approval_request_id == approval.id))
    ).scalar_one()
    assignment = (
        await session.execute(select(ApprovalAssignment).where(ApprovalAssignment.approval_level_id == level.id))
    ).scalar_one()
    if status != "pending":
        approval.status = status
    await session.commit()
    return ApprovalBundle(approval=approval, level=level, assignment=assignment)


def _decision_body(bundle: ApprovalBundle, decision_type: str = "approve", **overrides) -> dict:
    body = {
        "decision_type": decision_type,
        "expected_request_version": bundle.approval.version,
        "expected_level_version": bundle.level.version,
        "expected_assignment_version": bundle.assignment.version,
        "expected_revision": bundle.approval.revision,
        "action_payload_hash": bundle.approval.action_payload_hash,
        "safety_snapshot_hash": bundle.approval.safety_snapshot_hash,
        "reason": "valid",
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_decide_approve_builds_command_from_authenticated_actor_and_resumes_with_service_payload(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-approve")
    graph = FakeResumeGraph("approved response")
    manager = seeded_session["users"]["approval_manager"]
    captured: dict[str, ApprovalDecisionCommand] = {}
    original_decide = ApprovalService.decide

    async def spy_decide(self, command: ApprovalDecisionCommand):
        captured["command"] = command
        return await original_decide(self, command)

    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    monkeypatch.setattr(ApprovalService, "decide", spy_decide)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, "approve"),
        headers=await _manager_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["status"] == "approved"
    assert payload["data"]["request_version"] == 2
    assert captured["command"].actor_id == manager.id
    assert captured["command"].tenant_id == manager.tenant_id
    assert captured["command"].actor_role == "manager"
    assert len(graph.calls) == 1
    command, config = graph.calls[0]
    assert command.resume["schema_version"] == "approval_result.v1"
    assert command.resume["decision_type"] == "approve"
    assert command.resume["tenant_id"] == str(bundle.approval.tenant_id)
    assert command.resume["run_id"] == str(bundle.approval.run_id)
    assert command.resume["action_payload_hash"] == bundle.approval.action_payload_hash
    assert command.resume["safety_snapshot_ref"] == bundle.approval.safety_snapshot_ref
    assert command.resume["safety_snapshot_hash"] == bundle.approval.safety_snapshot_hash
    assert command.resume["decided_by"] == str(manager.id)
    assert config["configurable"]["thread_id"] == bundle.approval.thread_id


@pytest.mark.asyncio
async def test_decide_reject_resumes_graph_with_trusted_rejected_result(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-reject")
    graph = FakeResumeGraph("rejected response")
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, "reject", reason="not enough evidence"),
        headers=await _manager_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["data"]["status"] == "rejected"
    assert len(graph.calls) == 1
    command, config = graph.calls[0]
    assert command.resume["schema_version"] == "approval_result.v1"
    assert command.resume["decision_type"] == "reject"
    assert command.resume["status"] == "rejected"
    assert config["configurable"]["thread_id"] == bundle.approval.thread_id


@pytest.mark.asyncio
async def test_decide_stale_version_conflict_returns_409_code_conflict(
    client: AsyncClient, session: AsyncSession, seeded_session, monkeypatch
):
    bundle = await _create_approval(session, seeded_session)
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, expected_request_version=bundle.approval.version + 1),
        headers=await _manager_headers(client),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_decide_self_approval_returns_403_self_approval(
    client: AsyncClient, session: AsyncSession, seeded_session, monkeypatch
):
    manager = seeded_session["users"]["approval_manager"]
    bundle = await _create_approval(session, seeded_session, requested_by=manager)
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle),
        headers=await _manager_headers(client),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SELF_APPROVAL"


@pytest.mark.asyncio
async def test_decide_cross_tenant_approval_does_not_leak_request(
    client: AsyncClient, session: AsyncSession, seeded_session, monkeypatch
):
    bundle = await _create_approval(session, seeded_session)
    other_user = seeded_session["users"]["other_support"]
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle),
        headers=_auth_header(other_user, ["approvals:review"]),
    )

    assert response.status_code in {403, 404}
    assert response.json()["error"]["code"] in {"FORBIDDEN", "NOT_FOUND"}


@pytest.mark.asyncio
async def test_get_approval_returns_v2_details(client: AsyncClient, session: AsyncSession, seeded_session):
    bundle = await _create_approval(session, seeded_session)

    response = await client.get(f"/api/v1/approvals/{bundle.approval.id}", headers=await _manager_headers(client))
    payload = response.json()

    assert response.status_code == 200
    assert payload["data"]["id"] == str(bundle.approval.id)
    assert payload["data"]["risk_rule_ref"] == "risk:manual-review"
    assert payload["data"]["revision"] == 1
    assert payload["data"]["request_version"] == 1
    assert payload["data"]["action_payload_hash"] == bundle.approval.action_payload_hash
    assert payload["data"]["safety_snapshot_hash"] == bundle.approval.safety_snapshot_hash


@pytest.mark.asyncio
async def test_list_pending_approvals_returns_unexpired_pending_only(
    client: AsyncClient, session: AsyncSession, seeded_session
):
    pending = await _create_approval(session, seeded_session)
    expired = await _create_approval(session, seeded_session, expires_at=datetime.now(UTC) - timedelta(minutes=1))
    approved = await _create_approval(session, seeded_session, status="approved")

    response = await client.get("/api/v1/approvals", headers=await _manager_headers(client))
    payload = response.json()
    ids = {item["id"] for item in payload["data"]["approvals"]}

    assert response.status_code == 200
    assert str(pending.approval.id) in ids
    assert str(expired.approval.id) not in ids
    assert str(approved.approval.id) not in ids


@pytest.mark.asyncio
async def test_agent_run_status_updates_to_completed_after_service_resume(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session)
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph("approved final"), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle),
        headers=await _manager_headers(client),
    )

    run = await session.get(AgentRun, bundle.approval.run_id)
    assert response.status_code == 200
    assert run is not None
    assert run.final_status == "completed"
    assert run.final_response == "approved final"
    assert run.total_latency_ms >= 10


@pytest.mark.asyncio
async def test_agent_chat_interrupt_result_creates_service_approval_and_interrupted_run(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    run_id = uuid4()
    payload = _interrupt_payload(run_id, seeded_session)
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
    assert body["data"]["expected_request_version"] == 1
    assert body["data"]["expected_level_version"] == 1
    assert body["data"]["expected_assignment_version"] == 1
    assert body["data"]["expected_revision"] == 1
    assert body["data"]["action_payload_hash"] == approval.action_payload_hash
    assert body["data"]["safety_snapshot_hash"] == approval.safety_snapshot_hash
    assert body["data"]["allowed_decision_types"] == ["accept", "approve", "reject", "ignore"]
    assert approval is not None
    assert approval.schema_version == "approval_request.v2"
    assert approval.thread_id == "chat-interrupt-result"
    assert approval.safety_snapshot_ref
    assert run is not None
    assert run.final_status == "interrupted"
    assert [step.node_name for step in steps] == ["receive_request", "approval_gate"]
    assert steps[1].status == "interrupted"


@pytest.mark.asyncio
async def test_agent_chat_interrupt_missing_hashes_fails_closed_without_approval(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    run_id = uuid4()
    payload = _interrupt_payload(run_id, seeded_session)
    payload.pop("action_payload_hash")
    monkeypatch.setattr(app.state, "agent_graph", FakeInterruptGraph(payload), raising=False)

    response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "给这个订单补偿600元", "thread_id": "chat-missing-hashes"},
        headers=await _support_headers(client),
    )
    body = response.json()

    approvals = (await session.execute(select(ApprovalRequest).where(ApprovalRequest.run_id == run_id))).scalars().all()
    assert response.status_code == 200
    assert body["data"]["status"] == "interrupted"
    assert body["data"]["approval_id"] is None
    assert body["data"]["error"]["code"] == "MISSING_ACTION_PAYLOAD_HASH"
    assert approvals == []


async def _manager_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": "approval_manager", "password": "moca2024"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def _support_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": "cs_zhang", "password": "moca2024"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def _interrupt_payload(run_id: UUID, seeded_session) -> dict:
    tenant_id = seeded_session["tenant"].id
    evidence_ref = {
        "schema_version": "evidence_ref.v1",
        "tenant_id": str(tenant_id),
        "evidence_id": "refund-policy/chunk-001@v3",
        "doc_key": "refund-policy",
        "chunk_id": "chunk-001",
        "policy_version": "v3",
        "text_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
        "retrieved_at": "2026-06-15T00:00:00.000Z",
        "retrieval_config_version": "retrieval.v1",
        "rank": 1,
    }
    proposed_action = {
        "schema_version": "proposed_action.v1",
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "action_id": "act-chat-interrupt",
        "action_type": "issue_coupon",
        "target_type": "refund_case",
        "target_id": "RF-TEST-001",
        "amount": "100.00",
        "currency": "CNY",
        "args": {"coupon_type": "cash"},
        "reason": "refund delay compensation",
        "evidence_refs": [evidence_ref],
    }
    return {
        "run_id": str(run_id),
        "tenant_id": str(tenant_id),
        "user_id": str(seeded_session["users"]["cs_zhang"].id),
        "proposed_action": proposed_action,
        "risk_level": "high",
        "risk_rule_ref": "HR-01",
        "risk_reason": "Compensation exceeds threshold",
        "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
        "action_payload_hash": "sha256:508e649e1b169a9520f7eb76403b0e00c90c1b1c52e17a499fd7bcdce2473094",
        "safety_snapshot_ref": "snapshot:display-only",
        "safety_snapshot_hash": "sha256:aafef5b8874e80241fce531bc6d3f73a7e713b6066586c50330ec9ee5e0ad144",
        "policy_config_version": "approval-policy.v1",
        "risk_config_version": "risk-rules.v1",
        "retrieval_config_version": "retrieval.v1",
        "evidence_refs": [evidence_ref],
    }
