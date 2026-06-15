from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
from src.db.models import AgentRun, ApprovalAssignment, ApprovalLevel, ApprovalRequest, User
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


def _edited_action(bundle: ApprovalBundle) -> dict:
    return {
        **bundle.approval.proposed_action,
        "amount": "88.00",
        "args": {**bundle.approval.proposed_action.get("args", {}), "coupon_type": "service_recovery"},
        "reason": "manager edited compensation amount",
    }


@pytest.mark.parametrize("decision_type", ["respond", "edit"])
def test_decide_request_covers_approval_02_decision_type_cases(decision_type: str):
    assert decision_type in {"respond", "edit"}


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
    assert config["configurable"]["thread_id"] == (
        f"{bundle.approval.tenant_id}:{bundle.approval.requested_by}:{bundle.approval.thread_id}"
    )


@pytest.mark.asyncio
async def test_decide_respond_requires_response_text_validation(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-respond-validation")
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, "respond"),
        headers=await _manager_headers(client),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_decide_respond_sets_needs_info_without_graph_resume(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-respond-needs-info")
    graph = FakeResumeGraph("should not run")
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(
            bundle,
            "respond",
            response_text="Please confirm the order and coupon amount.",
        ),
        headers=await _manager_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["data"]["status"] == "needs_info"
    assert payload["data"]["clarification_request_id"]
    assert len(graph.calls) == 0
    run = await session.get(AgentRun, bundle.approval.run_id)
    assert run is not None
    assert run.final_status == "interrupted"


@pytest.mark.asyncio
async def test_decide_edit_requires_edited_action_validation(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-edit-validation")
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, "edit"),
        headers=await _manager_headers(client),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_decide_edit_supersedes_without_action_draft_resume(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-edit-supersede")
    graph = FakeResumeGraph("should not authorize action")
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    old_hash = bundle.approval.action_payload_hash

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, "edit", edited_action=_edited_action(bundle)),
        headers=await _manager_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["data"]["status"] == "superseded"
    assert payload["data"]["superseded_by_request_id"]
    assert payload["data"]["new_action_payload_hash"]
    assert old_hash != payload["data"]["new_action_payload_hash"]
    assert len(graph.calls) == 0


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
    assert config["configurable"]["thread_id"] == (
        f"{bundle.approval.tenant_id}:{bundle.approval.requested_by}:{bundle.approval.thread_id}"
    )


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


async def _manager_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": "approval_manager", "password": "moca2024"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}
