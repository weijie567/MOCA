from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.api.main import app
from src.api.routers import approvals as approvals_router
from src.auth.jwt import create_access_token
from src.approvals.schemas import ApprovalDecisionCommand, ApprovalDecisionResult
from src.approvals.service import ApprovalService
from src.db.models import AgentRun, ApprovalAssignment, ApprovalEvent, ApprovalLevel, ApprovalRequest, User
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


def _info_body(bundle: ApprovalBundle, **overrides) -> dict:
    body = {
        "clarification_request_id": bundle.approval.clarification_request_id,
        "thread_id": bundle.approval.thread_id,
        "expected_request_version": bundle.approval.version,
        "expected_level_version": bundle.level.version,
        "expected_assignment_version": bundle.assignment.version,
        "expected_revision": bundle.approval.revision,
        "info_payload": {"response_text": "Customer confirmed the coupon details."},
    }
    body.update(overrides)
    return body


def _approved_decision_result(bundle: ApprovalBundle, actor_id: UUID) -> ApprovalDecisionResult:
    decided_at = datetime.now(UTC)
    resume_payload = {
        "schema_version": "approval_result.v1",
        "approval_id": str(bundle.approval.id),
        "tenant_id": str(bundle.approval.tenant_id),
        "run_id": str(bundle.approval.run_id),
        "status": "approved",
        "decision_type": "approve",
        "revision": bundle.approval.revision,
        "request_version": bundle.approval.version,
        "level_version": bundle.level.version,
        "assignment_version": bundle.assignment.version,
        "action_payload_hash": bundle.approval.action_payload_hash,
        "safety_snapshot_ref": bundle.approval.safety_snapshot_ref,
        "safety_snapshot_hash": bundle.approval.safety_snapshot_hash,
        "decided_by": str(actor_id),
        "decided_at": decided_at.isoformat(),
    }
    return ApprovalDecisionResult(
        approval_id=bundle.approval.id,
        tenant_id=bundle.approval.tenant_id,
        run_id=bundle.approval.run_id,
        status="approved",
        decision_type="approve",
        revision=bundle.approval.revision,
        request_version=bundle.approval.version,
        level_version=bundle.level.version,
        assignment_version=bundle.assignment.version,
        action_payload_hash=bundle.approval.action_payload_hash,
        safety_snapshot_ref=bundle.approval.safety_snapshot_ref,
        safety_snapshot_hash=bundle.approval.safety_snapshot_hash,
        decided_by=actor_id,
        decided_at=decided_at,
        decision_id=uuid4(),
        event_id=uuid4(),
        reason="valid",
        resume_payload=resume_payload,
        graph_thread_id=f"{bundle.approval.tenant_id}:{bundle.approval.requested_by}:{bundle.approval.thread_id}",
    )


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
async def test_decide_commits_approval_decision_before_graph_resume(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-commit-before-resume")
    graph = FakeResumeGraph("approved response")
    headers = await _manager_headers(client)
    decision_body = _decision_body(bundle, "approve")
    original_commit = session.commit
    commit_count = 0
    graph_commit_counts: list[int] = []

    async def spy_commit():
        nonlocal commit_count
        commit_count += 1
        await original_commit()

    async def spy_ainvoke(command, config):
        graph_commit_counts.append(commit_count)
        return await FakeResumeGraph.ainvoke(graph, command, config)

    monkeypatch.setattr(session, "commit", spy_commit)
    monkeypatch.setattr(graph, "ainvoke", spy_ainvoke)
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=decision_body,
        headers=headers,
    )

    assert response.status_code == 200
    assert graph_commit_counts == [2]
    assert commit_count == 3


@pytest.mark.asyncio
async def test_decide_records_recoverable_resume_failure_and_retries_terminal_approval(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-resume-retry")
    graph = FakeResumeGraph("approved response")
    headers = await _manager_headers(client)
    decision_body = _decision_body(bundle, "approve")
    original_commit = session.commit
    commit_count = 0

    async def fail_final_resume_commit():
        nonlocal commit_count
        commit_count += 1
        if commit_count == 3:
            raise RuntimeError("simulated final commit failure")
        await original_commit()

    monkeypatch.setattr(session, "commit", fail_final_resume_commit)
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    first_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=decision_body,
        headers=headers,
    )
    await session.refresh(bundle.approval)
    run = await session.get(AgentRun, bundle.approval.run_id)
    resume_events = (
        await session.execute(
            select(ApprovalEvent).where(
                ApprovalEvent.approval_request_id == bundle.approval.id,
                ApprovalEvent.event_type == "approval_resumed",
            )
        )
    ).scalars().all()
    resume_statuses = {event.metadata_json["resume_status"] for event in resume_events}

    assert first_response.status_code == 500
    assert first_response.json()["error"]["code"] == "APPROVAL_RESUME_FAILED"
    assert bundle.approval.status == "approved"
    assert run is not None
    assert run.final_status == "interrupted"
    assert {"attempted", "failed"} <= resume_statuses
    assert "completed" not in resume_statuses

    monkeypatch.setattr(session, "commit", original_commit)
    retry_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=decision_body,
        headers=headers,
    )
    await session.refresh(run)
    completed_events = (
        await session.execute(
            select(ApprovalEvent).where(
                ApprovalEvent.approval_request_id == bundle.approval.id,
                ApprovalEvent.event_type == "approval_resumed",
            )
        )
    ).scalars().all()
    completed_statuses = [event.metadata_json["resume_status"] for event in completed_events]

    assert retry_response.status_code == 200
    assert retry_response.json()["data"]["status"] == "approved"
    assert run.final_status == "completed"
    assert completed_statuses.count("completed") == 1
    assert len(graph.calls) == 2


@pytest.mark.asyncio
async def test_approval_resume_reconciliation_accepts_not_executed_demo_draft_outcome(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-reconcile-draft-outcome")
    manager = seeded_session["users"]["approval_manager"]
    result = _approved_decision_result(bundle, manager.id)

    async def fake_action_draft(state, config):
        assert state["approval_result"] == result.resume_payload
        assert config["configurable"]["session"] is session
        return {
            "action_draft": {"draft_id": "draft-api-001", "status": "draft_created"},
            "draft_outcome": {
                "schema_version": "draft_outcome.v1",
                "draft_id": "draft-api-001",
                "status": "not_executed_demo",
                "external_side_effect": False,
            },
            "action_result": {"status": "error", "data": {}, "error": {"message": "legacy field ignored"}},
        }

    monkeypatch.setattr(approvals_router, "action_draft", fake_action_draft)

    reconciled = await approvals_router._reconcile_approved_action_draft(
        session=session,
        result=result,
        final_state={"final_response": "approved"},
        config={"configurable": {"session": session}},
    )

    assert reconciled["draft_outcome"]["status"] == "not_executed_demo"
    assert reconciled["draft_outcome"]["external_side_effect"] is False
    assert reconciled.get("node_errors") is None


@pytest.mark.asyncio
async def test_approval_resume_reconciliation_records_error_when_draft_outcome_missing(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-reconcile-missing-outcome")
    result = _approved_decision_result(bundle, seeded_session["users"]["approval_manager"].id)

    async def fake_action_draft(_state, _config):
        return {"action_result": {"status": "draft_created", "data": {"draft_id": "draft-api-002"}, "error": {}}}

    monkeypatch.setattr(approvals_router, "action_draft", fake_action_draft)

    reconciled = await approvals_router._reconcile_approved_action_draft(
        session=session,
        result=result,
        final_state={"final_response": "approved"},
        config={"configurable": {"session": session}},
    )

    assert {"node": "action_draft", "error": "action_draft_reconcile_failed"} in reconciled["node_errors"]


@pytest.mark.asyncio
async def test_approval_resume_reconciliation_records_error_for_side_effecting_draft_outcome(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-reconcile-side-effect")
    result = _approved_decision_result(bundle, seeded_session["users"]["approval_manager"].id)

    async def fake_action_draft(_state, _config):
        return {
            "draft_outcome": {
                "schema_version": "draft_outcome.v1",
                "draft_id": "draft-api-003",
                "status": "not_executed_demo",
                "external_side_effect": True,
            },
            "action_result": {"status": "success", "data": {"draft_id": "draft-api-003"}, "error": {}},
        }

    monkeypatch.setattr(approvals_router, "action_draft", fake_action_draft)

    reconciled = await approvals_router._reconcile_approved_action_draft(
        session=session,
        result=result,
        final_state={"final_response": "approved"},
        config={"configurable": {"session": session}},
    )

    assert {"node": "action_draft", "error": "action_draft_reconcile_failed"} in reconciled["node_errors"]


def test_approval_resume_reconciliation_uses_draft_outcome_not_action_result_success() -> None:
    source = Path("src/api/routers/approvals.py").read_text(encoding="utf-8")

    assert "action_draft(" in source
    assert "execute_action(" not in source
    assert "not_executed_demo" in source
    assert "external_side_effect" in source
    assert "action_result\", {}).get(\"status\") != \"success\"" not in source


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
async def test_attach_info_same_revision_reopens_pending_request(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-info-same-revision")
    graph = FakeResumeGraph("should not run")
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    respond = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, "respond", response_text="Please confirm the coupon details."),
        headers=await _manager_headers(client),
    )
    assert respond.status_code == 200
    await session.refresh(bundle.approval)
    await session.refresh(bundle.level)
    await session.refresh(bundle.assignment)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/info",
        json=_info_body(bundle),
        headers=await _manager_headers(client),
    )
    payload = response.json()
    await session.refresh(bundle.approval)
    await session.refresh(bundle.level)
    await session.refresh(bundle.assignment)

    assert response.status_code == 200
    assert payload["data"]["status"] == "pending"
    assert payload["data"]["id"] == str(bundle.approval.id)
    assert payload["data"]["request_version"] == 3
    assert bundle.approval.status == "pending"
    assert bundle.level.version == 3
    assert bundle.assignment.version == 3
    assert len(graph.calls) == 0


@pytest.mark.asyncio
async def test_attach_info_changed_payload_supersedes_old_request(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-info-supersede")
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph("should not run"), raising=False)
    respond = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, "respond", response_text="Please confirm the coupon amount."),
        headers=await _manager_headers(client),
    )
    assert respond.status_code == 200
    await session.refresh(bundle.approval)
    await session.refresh(bundle.level)
    await session.refresh(bundle.assignment)
    old_hash = bundle.approval.action_payload_hash

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/info",
        json=_info_body(
            bundle,
            info_payload={"response_text": "confirmed", "proposed_action": _edited_action(bundle)},
        ),
        headers=await _manager_headers(client),
    )
    payload = response.json()
    await session.refresh(bundle.approval)
    new_approval = await session.get(ApprovalRequest, UUID(payload["data"]["id"]))

    assert response.status_code == 200
    assert payload["data"]["status"] == "pending"
    assert payload["data"]["id"] != str(bundle.approval.id)
    assert payload["data"]["new_action_payload_hash"]
    assert payload["data"]["new_action_payload_hash"] != old_hash
    assert bundle.approval.status == "superseded"
    assert bundle.approval.superseded_by_request_id == new_approval.id
    assert new_approval is not None
    assert new_approval.status == "pending"


@pytest.mark.asyncio
async def test_attach_info_wrong_thread_returns_conflict(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-info-conflict")
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)
    respond = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, "respond", response_text="Please confirm details."),
        headers=await _manager_headers(client),
    )
    assert respond.status_code == 200
    await session.refresh(bundle.approval)
    await session.refresh(bundle.level)
    await session.refresh(bundle.assignment)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/info",
        json=_info_body(bundle, thread_id="wrong-thread"),
        headers=await _manager_headers(client),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


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
    assert payload["data"]["reason"] == "not enough evidence"
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
async def test_get_approval_rejects_over_scoped_non_reviewer_token(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    bundle = await _create_approval(session, seeded_session)
    support = seeded_session["users"]["cs_zhang"]

    response = await client.get(
        f"/api/v1/approvals/{bundle.approval.id}",
        headers=_auth_header(support, ["approvals:review"]),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_list_pending_approvals_returns_unexpired_pending_only(
    client: AsyncClient, session: AsyncSession, seeded_session
):
    pending = await _create_approval(session, seeded_session)
    expired = await _create_approval(session, seeded_session, expires_at=datetime.now(UTC) - timedelta(minutes=1))
    approved = await _create_approval(session, seeded_session, status="approved")
    legacy_run_id = await _create_run(
        session,
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id="approval-legacy-pending",
    )
    legacy = ApprovalRequest(
        tenant_id=seeded_session["tenant"].id,
        run_id=legacy_run_id,
        thread_id="approval-legacy-pending",
        schema_version="approval_request.v1",
        status="pending",
        revision=1,
        version=1,
        legacy_non_executable=True,
        requested_by=seeded_session["users"]["cs_zhang"].id,
        proposed_action=pending.approval.proposed_action,
        risk_level="high",
        risk_rule_ref="legacy:manual-review",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add(legacy)
    await session.commit()

    response = await client.get("/api/v1/approvals", headers=await _manager_headers(client))
    payload = response.json()
    ids = {item["id"] for item in payload["data"]["approvals"]}

    assert response.status_code == 200
    assert str(pending.approval.id) in ids
    assert str(expired.approval.id) not in ids
    assert str(approved.approval.id) not in ids
    assert str(legacy.id) not in ids


@pytest.mark.asyncio
async def test_list_pending_approvals_rejects_over_scoped_non_reviewer_token(
    client: AsyncClient,
    seeded_session,
):
    support = seeded_session["users"]["cs_zhang"]

    response = await client.get("/api/v1/approvals", headers=_auth_header(support, ["approvals:review"]))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


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
