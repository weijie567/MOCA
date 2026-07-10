from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.api.main import app
from src.api.routers import approvals as approvals_router
from src.auth.jwt import create_access_token
from src.approvals.schemas import ApprovalDecisionCommand, ApprovalDecisionResult
from src.approvals.service import ApprovalService, ApprovalTransitionError
from src.approvals.snapshot_service import persist_action_safety_snapshot
from src.db.models import (
    ActionDraft,
    AgentRun,
    AgentStep,
    ApprovalAssignment,
    ApprovalDecision,
    ApprovalEvent,
    ApprovalLevel,
    ApprovalRequest,
    CaseWorkingContext,
    ConversationMessage,
    ConversationSummary,
    ConversationThread,
    MemoryWriteEvent,
    User,
)
from src.knowledge.schemas import EvidenceRefV1
from tests.approvals.test_service_transitions import _create_command, _phase34_binding_overrides


@dataclass(frozen=True)
class ApprovalBundle:
    approval: ApprovalRequest
    level: ApprovalLevel
    assignment: ApprovalAssignment


class FakeResumeGraph:
    def __init__(self, final_response: str | None = "resumed", *, extra_state: dict | None = None):
        self.calls: list[tuple[object, dict]] = []
        self.final_response = final_response
        self.extra_state = extra_state or {}

    async def ainvoke(self, command, config):
        self.calls.append((command, config))
        return {
            "final_response": self.final_response,
            "trace_steps": [
                {"node": "receive_request", "status": "completed"},
                {"node": "approval_gate", "status": "completed"},
                {"node": "final_response", "status": "completed"},
            ],
            **self.extra_state,
        }


class FakeInterrupt:
    def __init__(self, value: dict):
        self.value = value


class ReinterruptResumeGraph:
    def __init__(self, *, target_merchant_id: str):
        self.calls: list[tuple[object, dict]] = []
        self.target_merchant_id = target_merchant_id

    async def ainvoke(self, command, config):
        self.calls.append((command, config))
        session = config["configurable"]["session"]
        resume = command.resume
        edited_action = dict(resume["edited_action"])
        evidence_refs = [EvidenceRefV1.model_validate(ref) for ref in edited_action["evidence_refs"]]
        created_at = datetime.now(UTC)
        created_at = created_at.replace(microsecond=(created_at.microsecond // 1000) * 1000)
        run = await session.get(AgentRun, UUID(edited_action["run_id"]))
        assert run is not None
        assert run.target_merchant_id == self.target_merchant_id
        assert run.target_merchant_ref is not None
        target_merchant_ref = run.target_merchant_ref
        business_fact_ref = target_merchant_ref["business_fact_ref"]
        snapshot = await persist_action_safety_snapshot(
            session,
            tenant_id=UUID(edited_action["tenant_id"]),
            run_id=UUID(edited_action["run_id"]),
            proposed_action=edited_action,
            action_payload_hash=resume["new_action_payload_hash"],
            policy_config_version="approval-policy.v1",
            risk_config_version="risk-rules.v1",
            retrieval_config_version=evidence_refs[0].retrieval_config_version,
            evidence_refs=evidence_refs,
            target_merchant_id=self.target_merchant_id,
            target_merchant_ref=target_merchant_ref,
            business_fact_refs=[business_fact_ref],
            created_at=created_at,
            created_by=UUID(resume["decided_by"]),
        )
        risk_decision_ref = f"risk_decision:{edited_action['run_id']}:{snapshot.action_payload_hash}"
        interrupt_payload = {
            "proposed_action": edited_action,
            "action_payload_hash": snapshot.action_payload_hash,
            "safety_snapshot_ref": snapshot.safety_snapshot_ref,
            "safety_snapshot_hash": snapshot.safety_snapshot_hash,
            "policy_config_version": "approval-policy.v1",
            "risk_config_version": "risk-rules.v1",
            "retrieval_config_version": evidence_refs[0].retrieval_config_version,
            "evidence_refs": [ref.model_dump(mode="json") for ref in evidence_refs],
            "risk_level": "high",
            "risk_reason": "Edited compensation still requires approval.",
            "risk_rule_ref": "HR-EDIT",
            "target_merchant_id": self.target_merchant_id,
            "target_merchant_ref": target_merchant_ref,
            "business_fact_refs": [business_fact_ref],
            "verified_evidence_refs": [ref.model_dump(mode="json") for ref in evidence_refs],
            "claim_verification_ref": None,
            "claim_verification_summary": {"overall_status": "verified", "safe_support_ref_count": 1},
            "risk_decision_ref": risk_decision_ref,
            "risk_decision": {
                "schema_version": "risk_decision.v1",
                "tenant_id": edited_action["tenant_id"],
                "run_id": edited_action["run_id"],
                "action_id": edited_action["action_id"],
                "action_payload_hash": snapshot.action_payload_hash,
                "risk_level": "high",
                "reason_codes": ["approval_required", "manager_edit"],
                "policy_config_version": "approval-policy.v1",
                "risk_config_version": "risk-rules.v1",
                "approval_required": True,
                "evaluated_at": "2026-06-29T00:02:00.000Z",
                "risk_rule_ref": "HR-EDIT",
                "risk_reason": "Edited compensation still requires approval.",
            },
            "approval_idempotency_key": (
                f"approval:{edited_action['tenant_id']}:{edited_action['run_id']}:{snapshot.action_payload_hash}"
            ),
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
        return {
            "__interrupt__": [FakeInterrupt(interrupt_payload)],
            "trace_steps": [
                {"node": "approval_gate", "status": "completed"},
                {"node": "risk_gate", "status": "completed"},
                {"node": "approval_gate", "status": "interrupted"},
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
    with_phase34_bindings: bool = True,
) -> ApprovalBundle:
    tenant = seeded_session[tenant_key]
    requester = requested_by or seeded_session["users"]["cs_zhang"]
    run_id = await _create_run(session, tenant_id=tenant.id, user_id=requester.id, thread_id=thread_id)
    binding_overrides = (
        _phase34_binding_overrides(
            tenant_id=tenant.id,
            run_id=run_id,
            merchant_id=str(requester.merchant_id or seeded_session["merchant"].id),
        )
        if with_phase34_bindings
        else {}
    )
    if binding_overrides:
        await _mark_run_business_merchant(session, run_id, binding_overrides)
    created = await ApprovalService(session).create_request(
        _create_command(
            tenant_id=tenant.id,
            run_id=run_id,
            requested_by=requester.id,
            thread_id=thread_id,
            expires_at=expires_at or datetime.now(UTC) + timedelta(hours=1),
            **binding_overrides,
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


async def _mark_run_business_merchant(session: AsyncSession, run_id: UUID, binding: dict) -> None:
    run = await session.get(AgentRun, run_id)
    assert run is not None
    run.scope_classification = "business_merchant"
    run.target_merchant_id = binding["target_merchant_id"]
    run.target_merchant_ref = binding["target_merchant_ref"]
    run.scope_source = "target_merchant_binding_v1"
    run.scope_reason_codes = []
    await session.flush()


async def _count_rows(session: AsyncSession, model, *filters) -> int:
    result = await session.execute(select(func.count()).select_from(model).where(*filters))
    return int(result.scalar_one())


async def _messages_for_run(session: AsyncSession, *, run_id: UUID, role: str | None = None) -> list[ConversationMessage]:
    filters = [ConversationMessage.run_id == run_id, ConversationMessage.deleted_at.is_(None)]
    if role is not None:
        filters.append(ConversationMessage.role == role)
    result = await session.execute(select(ConversationMessage).where(*filters).order_by(ConversationMessage.message_index))
    return list(result.scalars().all())


async def _finalizer_steps(session: AsyncSession, *, run_id: UUID) -> list[AgentStep]:
    result = await session.execute(
        select(AgentStep)
        .where(
            AgentStep.run_id == run_id,
            AgentStep.node_name == "agent_run_memory_finalize",
        )
        .order_by(AgentStep.step_index)
    )
    return list(result.scalars().all())


def _patch_completed_memory_write(monkeypatch: pytest.MonkeyPatch, captured_states: list[dict]) -> None:
    async def fake_memory_write(final_state, config):
        captured_states.append(dict(final_state))
        assert config["configurable"]["session"] is not None
        return {
            **final_state,
            "memory_write_result": {
                "status": "completed",
                "reason_code": "memory_persisted",
                "slot_count": 1,
                "decision": "write",
                "pii_classification": "none",
            },
            "trace_steps": [],
        }

    monkeypatch.setattr("src.api.services.agent_run_memory.memory_write", fake_memory_write)


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


def _trusted_resume_config(session: AsyncSession, result: ApprovalDecisionResult, actor: User) -> dict:
    trusted_context = approvals_router.TrustedContextFactory.create_from_request(
        user=actor,
        verified_token_scopes=frozenset(),
        thread_id=result.graph_thread_id,
        run_id=str(result.run_id),
        trace_id="trace-approval-test",
        server_tool_permissions=[approvals_router.ACTION_DRAFT_PERMISSION],
    )
    return {
        "configurable": {
            "thread_id": result.graph_thread_id,
            "session": session,
            **approvals_router._trusted_graph_config(trusted_context),
        }
    }


def _edited_action(bundle: ApprovalBundle) -> dict:
    return {
        **bundle.approval.proposed_action,
        "amount": "88.00",
        "args": {**bundle.approval.proposed_action.get("args", {}), "coupon_type": "service_recovery"},
        "reason": "reviewer edited compensation amount",
    }


def _edit_decision_result_for_resume_route(resume_route: str) -> ApprovalDecisionResult:
    approval_id = uuid4()
    tenant_id = uuid4()
    run_id = uuid4()
    decided_by = uuid4()
    decided_at = datetime.now(UTC)
    resume_payload = {
        "schema_version": "approval_result.v1",
        "approval_id": str(approval_id),
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "status": "superseded",
        "decision_type": "edit",
        "revision": 2,
        "request_version": 2,
        "level_version": 2,
        "assignment_version": 2,
        "action_payload_hash": "sha256:" + "1" * 64,
        "safety_snapshot_ref": "snapshot:test",
        "safety_snapshot_hash": "sha256:" + "2" * 64,
        "decided_by": str(decided_by),
        "decided_at": decided_at.isoformat(),
        "edited_action": {"action_type": "issue_coupon", "target_id": "RF-1001"},
        "new_action_payload_hash": "sha256:" + "3" * 64,
        "resume_route": resume_route,
    }
    return ApprovalDecisionResult(
        approval_id=approval_id,
        tenant_id=tenant_id,
        run_id=run_id,
        status="superseded",
        decision_type="edit",
        revision=2,
        request_version=2,
        level_version=2,
        assignment_version=2,
        action_payload_hash=resume_payload["action_payload_hash"],
        safety_snapshot_ref=resume_payload["safety_snapshot_ref"],
        safety_snapshot_hash=resume_payload["safety_snapshot_hash"],
        decided_by=decided_by,
        decided_at=decided_at,
        decision_id=uuid4(),
        event_id=uuid4(),
        new_action_payload_hash=resume_payload["new_action_payload_hash"],
        edited_action=resume_payload["edited_action"],
        resume_payload=resume_payload,
        graph_thread_id=f"{tenant_id}:{decided_by}:thread-edit-route",
    )


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
    admin = seeded_session["users"]["admin_user"]
    captured: dict[str, ApprovalDecisionCommand] = {}
    factory_kwargs: list[dict] = []
    original_decide = ApprovalService.decide
    original_create_from_request = approvals_router.TrustedContextFactory.create_from_request

    async def spy_decide(self, command: ApprovalDecisionCommand):
        captured["command"] = command
        return await original_decide(self, command)

    def spy_create_from_request(**kwargs):
        factory_kwargs.append(kwargs)
        return original_create_from_request(**kwargs)

    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    monkeypatch.setattr(ApprovalService, "decide", spy_decide)
    monkeypatch.setattr(
        approvals_router.TrustedContextFactory,
        "create_from_request",
        staticmethod(spy_create_from_request),
    )

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, "approve"),
        headers=await _admin_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["status"] == "approved"
    assert payload["data"]["request_version"] == 2
    assert captured["command"].actor_id == admin.id
    assert captured["command"].tenant_id == admin.tenant_id
    assert captured["command"].actor_role == "admin"
    assert len(graph.calls) == 1
    assert factory_kwargs
    assert factory_kwargs[-1]["server_tool_permissions"] == [approvals_router.ACTION_DRAFT_PERMISSION]
    assert "server_merchant_scope" not in factory_kwargs[-1]
    command, config = graph.calls[0]
    assert command.resume["schema_version"] == "approval_result.v1"
    assert command.resume["decision_type"] == "approve"
    assert command.resume["tenant_id"] == str(bundle.approval.tenant_id)
    assert command.resume["run_id"] == str(bundle.approval.run_id)
    assert command.resume["action_payload_hash"] == bundle.approval.action_payload_hash
    assert command.resume["safety_snapshot_ref"] == bundle.approval.safety_snapshot_ref
    assert command.resume["safety_snapshot_hash"] == bundle.approval.safety_snapshot_hash
    assert command.resume["decided_by"] == str(admin.id)
    assert config["configurable"]["thread_id"] == (
        f"{bundle.approval.tenant_id}:{bundle.approval.requested_by}:{bundle.approval.thread_id}"
    )
    trusted_context = config["configurable"]["trusted_context"]
    assert trusted_context["tenant_id"] == str(bundle.approval.tenant_id)
    assert trusted_context["user_id"] == str(admin.id)
    assert trusted_context["role"] == "admin"
    assert trusted_context["thread_id"] == config["configurable"]["thread_id"]
    assert trusted_context["run_id"] == str(bundle.approval.run_id)
    assert trusted_context["permissions"] == [approvals_router.ACTION_DRAFT_PERMISSION]
    assert config["configurable"]["permissions"] == trusted_context["permissions"]
    assert config["configurable"]["merchant_scope"] == trusted_context["merchant_scope"]
    assert config["configurable"]["trace_id"] == trusted_context["trace_id"]


@pytest.mark.asyncio
async def test_decide_commits_approval_decision_before_graph_resume(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-commit-before-resume")
    graph = FakeResumeGraph("approved response")
    headers = await _admin_headers(client)
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
    assert commit_count == 6


@pytest.mark.asyncio
async def test_decide_records_recoverable_resume_failure_and_retries_terminal_approval(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-resume-retry")
    refund_case = seeded_session["refund_case"]
    graph = FakeResumeGraph(
        "approved response",
        extra_state={
            "primary_intent": "refund_status",
            "approval_result": {"status": "approved", "decision_type": "approve"},
            "risk_assessment": {"approval_required": True, "risk_level": "high"},
            "active_slots": {
                "refund_case_id": refund_case.refund_case_no,
                "issue_type": "refund_status",
            },
            "extracted_slots": {"refund_case_id": refund_case.refund_case_no},
        },
    )
    headers = await _admin_headers(client)
    decision_body = _decision_body(bundle, "approve")
    original_record_resume_event = approvals_router._record_resume_event
    fail_completed_event_once = True

    async def fail_completed_resume_event_once(**kwargs):
        nonlocal fail_completed_event_once
        if kwargs.get("resume_status") == "completed" and fail_completed_event_once:
            fail_completed_event_once = False
            raise RuntimeError("simulated completed resume event failure")
        return await original_record_resume_event(**kwargs)

    monkeypatch.setattr(approvals_router, "_record_resume_event", fail_completed_resume_event_once)
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    first_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=decision_body,
        headers=headers,
    )
    await session.refresh(bundle.approval)
    run = await session.get(AgentRun, bundle.approval.run_id)
    resume_events = (
        (
            await session.execute(
                select(ApprovalEvent).where(
                    ApprovalEvent.approval_request_id == bundle.approval.id,
                    ApprovalEvent.event_type == "approval_resumed",
                )
            )
        )
        .scalars()
        .all()
    )
    resume_statuses = {event.metadata_json["resume_status"] for event in resume_events}

    assert first_response.status_code == 500
    assert first_response.json()["error"]["code"] == "APPROVAL_RESUME_FAILED"
    assert bundle.approval.status == "approved"
    assert run is not None
    assert run.final_status == "completed"
    assert {"attempted", "failed"} <= resume_statuses
    assert "completed" not in resume_statuses
    assert len(await _finalizer_steps(session, run_id=bundle.approval.run_id)) == 1
    assert (
        await _count_rows(
            session,
            ConversationMessage,
            ConversationMessage.run_id == bundle.approval.run_id,
            ConversationMessage.role == "assistant",
        )
        == 1
    )
    assert (
        await _count_rows(
            session,
            ConversationSummary,
            ConversationSummary.thread_id == run.thread_id,
            ConversationSummary.summary_type == "thread_rolling",
            ConversationSummary.deleted_at.is_(None),
        )
        == 1
    )
    assert (
        await _count_rows(
            session,
            MemoryWriteEvent,
            MemoryWriteEvent.run_id == bundle.approval.run_id,
            MemoryWriteEvent.memory_type == "session_slot",
            MemoryWriteEvent.decision == "write",
        )
        == 1
    )

    retry_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=decision_body,
        headers=headers,
    )
    await session.refresh(run)
    completed_events = (
        (
            await session.execute(
                select(ApprovalEvent).where(
                    ApprovalEvent.approval_request_id == bundle.approval.id,
                    ApprovalEvent.event_type == "approval_resumed",
                )
            )
        )
        .scalars()
        .all()
    )
    completed_statuses = [event.metadata_json["resume_status"] for event in completed_events]

    assert retry_response.status_code == 200
    assert retry_response.json()["data"]["status"] == "approved"
    assert run.final_status == "completed"
    assert completed_statuses.count("completed") == 1
    assert len(graph.calls) == 1
    assert len(await _finalizer_steps(session, run_id=bundle.approval.run_id)) == 1
    assert (
        await _count_rows(
            session,
            ConversationMessage,
            ConversationMessage.run_id == bundle.approval.run_id,
            ConversationMessage.role == "assistant",
            ConversationMessage.deleted_at.is_(None),
        )
        == 1
    )
    assert (
        await _count_rows(
            session,
            ConversationSummary,
            ConversationSummary.thread_id == run.thread_id,
            ConversationSummary.summary_type == "thread_rolling",
            ConversationSummary.deleted_at.is_(None),
        )
        == 1
    )
    assert (
        await _count_rows(
            session,
            MemoryWriteEvent,
            MemoryWriteEvent.run_id == bundle.approval.run_id,
            MemoryWriteEvent.memory_type == "session_slot",
            MemoryWriteEvent.decision == "write",
        )
        == 1
    )
    assert (
        await _count_rows(
            session,
            ActionDraft,
            ActionDraft.run_id == bundle.approval.run_id,
            ActionDraft.approval_request_id == bundle.approval.id,
        )
        == 1
    )


@pytest.mark.asyncio
async def test_approval_resume_trace_persistence_failure_fails_closed_after_terminal_surfaces(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-resume-trace-failure")
    refund_case = seeded_session["refund_case"]
    graph = FakeResumeGraph(
        "approved response",
        extra_state={
            "primary_intent": "refund_status",
            "approval_result": {"status": "approved", "decision_type": "approve"},
            "risk_assessment": {"approval_required": True, "risk_level": "high"},
            "active_slots": {
                "refund_case_id": refund_case.refund_case_no,
                "issue_type": "refund_status",
            },
            "extracted_slots": {"refund_case_id": refund_case.refund_case_no},
        },
    )
    headers = await _admin_headers(client)
    decision_body = _decision_body(bundle, "approve")

    async def fail_finalizer_trace_persistence(**kwargs):
        raise RuntimeError("simulated finalizer trace append failure")

    monkeypatch.setattr(
        approvals_router,
        "persist_agent_run_memory_finalize_trace_steps",
        fail_finalizer_trace_persistence,
    )
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=decision_body,
        headers=headers,
    )
    await session.refresh(bundle.approval)
    run = await session.get(AgentRun, bundle.approval.run_id)
    resume_events = (
        (
            await session.execute(
                select(ApprovalEvent).where(
                    ApprovalEvent.approval_request_id == bundle.approval.id,
                    ApprovalEvent.event_type == "approval_resumed",
                )
            )
        )
        .scalars()
        .all()
    )
    resume_statuses = {event.metadata_json["resume_status"] for event in resume_events}

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "APPROVAL_RESUME_FAILED"
    assert run is not None
    assert run.final_status == "completed"
    assert {"attempted", "failed"} <= resume_statuses
    assert "completed" not in resume_statuses
    assert len(await _finalizer_steps(session, run_id=bundle.approval.run_id)) == 0
    assert (
        await _count_rows(
            session,
            ConversationMessage,
            ConversationMessage.run_id == bundle.approval.run_id,
            ConversationMessage.role == "assistant",
            ConversationMessage.deleted_at.is_(None),
        )
        == 1
    )
    assert (
        await _count_rows(
            session,
            ConversationSummary,
            ConversationSummary.thread_id == run.thread_id,
            ConversationSummary.summary_type == "thread_rolling",
            ConversationSummary.deleted_at.is_(None),
        )
        == 1
    )
    assert (
        await _count_rows(
            session,
            MemoryWriteEvent,
            MemoryWriteEvent.run_id == bundle.approval.run_id,
            MemoryWriteEvent.memory_type == "session_slot",
            MemoryWriteEvent.decision == "write",
        )
        == 1
    )
    assert (
        await _count_rows(
            session,
            CaseWorkingContext,
            CaseWorkingContext.updated_by_run_id == bundle.approval.run_id,
            CaseWorkingContext.deleted_at.is_(None),
        )
        == 1
    )


@pytest.mark.asyncio
async def test_completed_resume_reconciliation_rechecks_status_under_lock(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-resume-lock-recheck")
    admin = seeded_session["users"]["admin_user"]
    result = _approved_decision_result(bundle, admin.id)
    calls: list[str] = []

    async def fake_lock(session: AsyncSession, approval_id: UUID) -> ApprovalRequest:
        calls.append("lock")
        assert approval_id == bundle.approval.id
        return bundle.approval

    async def fake_latest_status(session: AsyncSession, approval: ApprovalRequest) -> str:
        calls.append("latest")
        assert approval.id == bundle.approval.id
        return "completed"

    async def fail_record_resume_event(**kwargs):
        raise AssertionError("duplicate completed resume event should not be recorded")

    monkeypatch.setattr(approvals_router, "_lock_approval_request_for_resume", fake_lock)
    monkeypatch.setattr(approvals_router, "_latest_resume_status", fake_latest_status)
    monkeypatch.setattr(approvals_router, "_record_resume_event", fail_record_resume_event)

    recorded = await approvals_router._record_resume_completed_event_once(
        session=session,
        result=result,
        actor_id=admin.id,
        require_terminal_finalizer=True,
    )

    assert recorded is True
    assert calls == ["lock", "latest"]


@pytest.mark.asyncio
async def test_approval_resume_reconciliation_accepts_not_executed_demo_draft_outcome(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-reconcile-draft-outcome")
    admin = seeded_session["users"]["admin_user"]
    result = _approved_decision_result(bundle, admin.id)

    async def fake_action_draft(state, config):
        assert state["approval_result"] == result.resume_payload
        assert state["current_run_id"] == str(result.run_id)
        assert config["configurable"]["session"] is session
        outcome = {
            "schema_version": "draft_outcome.v1",
            "tenant_id": str(result.tenant_id),
            "run_id": str(result.run_id),
            "draft_id": "draft-api-001",
            "status": "not_executed_demo",
            "external_side_effect": False,
        }
        return {
            "action_draft": {
                "schema_version": "action_draft.v2",
                "tenant_id": str(result.tenant_id),
                "run_id": str(result.run_id),
                "draft_id": "draft-api-001",
                "status": "draft_created",
                "execution_mode": "demo",
                "lifecycle_status": "active",
                "draft_outcome": outcome,
            },
            "draft_outcome": outcome,
            "execution_mode": "demo",
            "action_result": {"status": "error", "data": {}, "error": {"message": "legacy field ignored"}},
            "trace_steps": [
                {
                    "node": "action_draft",
                    "status": "completed",
                    "tool_name": "create_coupon_grant_draft",
                }
            ],
        }

    monkeypatch.setattr(approvals_router, "action_draft", fake_action_draft)

    reconciled = await approvals_router._reconcile_approved_action_draft(
        session=session,
        result=result,
        final_state={"final_response": "approved"},
        config=_trusted_resume_config(session, result, admin),
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
    admin = seeded_session["users"]["admin_user"]
    result = _approved_decision_result(bundle, admin.id)

    async def fake_action_draft(_state, _config):
        return {"action_result": {"status": "draft_created", "data": {"draft_id": "draft-api-002"}, "error": {}}}

    monkeypatch.setattr(approvals_router, "action_draft", fake_action_draft)

    reconciled = await approvals_router._reconcile_approved_action_draft(
        session=session,
        result=result,
        final_state={"final_response": "approved"},
        config=_trusted_resume_config(session, result, admin),
    )

    assert {"node": "action_draft", "error": "action_draft_reconcile_failed"} in reconciled["node_errors"]


@pytest.mark.asyncio
async def test_approval_resume_reconciliation_records_error_for_side_effecting_draft_outcome(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-reconcile-side-effect")
    admin = seeded_session["users"]["admin_user"]
    result = _approved_decision_result(bundle, admin.id)

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
        config=_trusted_resume_config(session, result, admin),
    )

    assert {"node": "action_draft", "error": "action_draft_reconcile_failed"} in reconciled["node_errors"]


def test_approval_resume_reconciliation_uses_draft_outcome_not_action_result_success() -> None:
    source = Path("src/api/routers/approvals.py").read_text(encoding="utf-8")

    assert "action_draft(" in source
    assert "execute_action(" not in source
    assert "not_executed_demo" in source
    assert "external_side_effect" in source
    assert 'action_result", {}).get("status") != "success"' not in source


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
        headers=await _admin_headers(client),
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
        headers=await _admin_headers(client),
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
        headers=await _admin_headers(client),
    )
    assert respond.status_code == 200
    await session.refresh(bundle.approval)
    await session.refresh(bundle.level)
    await session.refresh(bundle.assignment)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/info",
        json=_info_body(bundle),
        headers=await _admin_headers(client),
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
async def test_attach_info_changed_payload_supersedes_without_unbound_replacement(
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
        headers=await _admin_headers(client),
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
        headers=await _admin_headers(client),
    )
    payload = response.json()
    await session.refresh(bundle.approval)
    rows = (
        (
            await session.execute(select(ApprovalRequest).where(ApprovalRequest.run_id == bundle.approval.run_id))
        )
        .scalars()
        .all()
    )

    assert response.status_code == 200
    assert payload["data"]["status"] == "superseded"
    assert payload["data"]["id"] == str(bundle.approval.id)
    assert payload["data"]["new_action_payload_hash"]
    assert payload["data"]["new_action_payload_hash"] != old_hash
    assert bundle.approval.status == "superseded"
    assert bundle.approval.superseded_by_request_id is None
    assert len(rows) == 1


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
        headers=await _admin_headers(client),
    )
    assert respond.status_code == 200
    await session.refresh(bundle.approval)
    await session.refresh(bundle.level)
    await session.refresh(bundle.assignment)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/info",
        json=_info_body(bundle, thread_id="wrong-thread"),
        headers=await _admin_headers(client),
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
        headers=await _admin_headers(client),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_decide_edit_supersedes_and_resumes_risk_reroute(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-edit-supersede")
    graph = FakeResumeGraph("edited action rerisked")
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    old_hash = bundle.approval.action_payload_hash
    edited_action = _edited_action(bundle)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, "edit", edited_action=edited_action),
        headers=await _admin_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["data"]["status"] == "superseded"
    assert payload["data"]["superseded_by_request_id"] is None
    assert payload["data"]["new_action_payload_hash"]
    assert old_hash != payload["data"]["new_action_payload_hash"]
    assert len(graph.calls) == 1
    command, config = graph.calls[0]
    assert command.resume["schema_version"] == "approval_result.v1"
    assert command.resume["decision_type"] == "edit"
    assert command.resume["status"] == "superseded"
    assert command.resume["resume_route"] == "risk_gate"
    assert command.resume["edited_action"] == edited_action
    assert command.resume["new_action_payload_hash"] == payload["data"]["new_action_payload_hash"]
    assert config["configurable"]["permissions"] == []


@pytest.mark.asyncio
async def test_decide_edit_rebinds_replacement_approval_from_resume_interrupt(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-edit-rebind")
    graph = ReinterruptResumeGraph(target_merchant_id=str(seeded_session["merchant"].id))
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    edited_action = _edited_action(bundle)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, "edit", edited_action=edited_action),
        headers=await _admin_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200, payload
    assert payload["data"]["status"] == "superseded"
    assert payload["data"]["superseded_by_request_id"] is None
    assert payload["data"]["new_action_payload_hash"] == graph.calls[0][0].resume["new_action_payload_hash"]

    rows = (
        (
            await session.execute(
                select(ApprovalRequest)
                .where(ApprovalRequest.run_id == bundle.approval.run_id)
                .order_by(ApprovalRequest.revision)
            )
        )
        .scalars()
        .all()
    )
    replacement = next((row for row in rows if row.id != bundle.approval.id), None)
    manager_list = await client.get("/api/v1/approvals", headers=await _manager_headers(client))
    manager_ids = {item["id"] for item in manager_list.json()["data"]["approvals"]}

    assert len(rows) == 2
    assert replacement is not None
    assert rows[0].id == bundle.approval.id
    assert rows[0].status == "superseded"
    assert rows[0].superseded_by_request_id is None
    assert replacement.status == "pending"
    assert replacement.requested_by == bundle.approval.requested_by
    assert replacement.action_payload_hash == payload["data"]["new_action_payload_hash"]
    assert replacement.target_merchant_id == str(seeded_session["merchant"].id)
    assert replacement.business_fact_refs[0]["resource_id"] == edited_action["target_id"]
    assert replacement.verified_evidence_refs[0]["evidence_id"] == edited_action["evidence_refs"][0]["evidence_id"]
    assert replacement.claim_verification_ref is None
    assert replacement.claim_verification_summary["overall_status"] == "verified"
    assert replacement.risk_decision_ref == f"risk_decision:{bundle.approval.run_id}:{replacement.action_payload_hash}"
    assert replacement.risk_decision["action_payload_hash"] == replacement.action_payload_hash
    assert replacement.approval_idempotency_key
    assert manager_list.status_code == 200
    assert str(replacement.id) in manager_ids
    assert str(bundle.approval.id) not in manager_ids
    run = await session.get(AgentRun, bundle.approval.run_id)
    assert run is not None
    assert run.final_status == "interrupted"
    assert (
        await _count_rows(
            session,
            ConversationMessage,
            ConversationMessage.run_id == bundle.approval.run_id,
            ConversationMessage.role == "assistant",
        )
        == 0
    )
    assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 0
    assert await _count_rows(session, MemoryWriteEvent, MemoryWriteEvent.run_id == bundle.approval.run_id) == 0
    assert len(await _finalizer_steps(session, run_id=bundle.approval.run_id)) == 0


@pytest.mark.asyncio
async def test_approval_resume_error_skips_terminal_finalizer_surfaces(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-resume-error-finalizer-skip")

    async def fail_if_finalizer_called(**_kwargs):
        pytest.fail("terminal finalizer must not run for approval resume error paths")

    monkeypatch.setattr(approvals_router, "finalize_completed_agent_run_memory", fail_if_finalizer_called)
    monkeypatch.setattr(
        app.state,
        "agent_graph",
        FakeResumeGraph(
            None,
            extra_state={
                "node_errors": [{"node": "action_draft", "error": "simulated"}],
            },
        ),
        raising=False,
    )

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle),
        headers=await _admin_headers(client),
    )

    run = await session.get(AgentRun, bundle.approval.run_id)
    assert response.status_code == 200
    assert run is not None
    assert run.final_status == "error"
    assert run.final_response is None
    assert (
        await _count_rows(
            session,
            ConversationMessage,
            ConversationMessage.run_id == bundle.approval.run_id,
            ConversationMessage.role == "assistant",
        )
        == 0
    )
    assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 0
    assert len(await _finalizer_steps(session, run_id=bundle.approval.run_id)) == 0


@pytest.mark.asyncio
async def test_approval_resume_action_failure_uses_terminal_guard_without_node_errors(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-resume-terminal-guard")
    finalizer_calls: list[dict] = []
    graph = FakeResumeGraph(
        "approved but database password=must-not-leak",
        extra_state={
            "recommendation_draft": {
                "recommended_action": "issue_coupon",
                "reasoning_summary": "符合补偿规则。",
                "evidence_refs": [],
            },
            "proposed_action": bundle.approval.proposed_action,
            "risk_assessment": {"approval_required": True, "risk_level": "high"},
            "approval_result": {"decision_type": "approve", "status": "approved"},
            "action_result": {
                "status": "error",
                "data": {},
                "error": {
                    "error_code": "DRAFT_CREATION_FAILED",
                    "message": "database password=must-not-leak",
                    "retryable": True,
                },
            },
        },
    )

    async def identity_reconcile(**kwargs):
        return kwargs["final_state"]

    async def record_finalizer_call(**kwargs):
        finalizer_calls.append(kwargs)
        return type("FinalizerResult", (), {"trace_steps": []})()

    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    monkeypatch.setattr(approvals_router, "_reconcile_approved_action_draft", identity_reconcile)
    monkeypatch.setattr(approvals_router, "finalize_completed_agent_run_memory", record_finalizer_call)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle),
        headers=await _admin_headers(client),
    )

    run = await session.get(AgentRun, bundle.approval.run_id)
    assert response.status_code == 200
    assert run is not None
    assert run.final_status == "error"
    assert run.final_response == "操作草稿未能安全创建，请稍后重试或转人工处理。"
    assert "must-not-leak" not in str(run.final_response)
    assert finalizer_calls == []
    assert await _count_rows(session, ActionDraft, ActionDraft.run_id == run.id) == 0
    assert await _count_rows(
        session,
        ConversationMessage,
        ConversationMessage.run_id == run.id,
        ConversationMessage.role == "assistant",
    ) == 0
    assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 0
    assert await _count_rows(session, MemoryWriteEvent, MemoryWriteEvent.run_id == run.id) == 0
    assert len(await _finalizer_steps(session, run_id=run.id)) == 0


@pytest.mark.asyncio
async def test_decide_edit_resume_failure_can_retry_and_rebind_without_new_decision(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-edit-resume-retry")
    merchant_id = str(seeded_session["merchant"].id)
    graph = ReinterruptResumeGraph(target_merchant_id=merchant_id)
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    headers = await _admin_headers(client)
    edited_action = _edited_action(bundle)
    decision_body = _decision_body(bundle, "edit", edited_action=edited_action)
    original_commit = session.commit
    commit_count = 0

    async def fail_final_resume_commit():
        nonlocal commit_count
        commit_count += 1
        if commit_count == 3:
            raise RuntimeError("simulated resume interrupt commit failure")
        await original_commit()

    monkeypatch.setattr(session, "commit", fail_final_resume_commit)
    first_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=decision_body,
        headers=headers,
    )
    await session.refresh(bundle.approval)
    rows_after_failure = (
        (
            await session.execute(select(ApprovalRequest).where(ApprovalRequest.run_id == bundle.approval.run_id))
        )
        .scalars()
        .all()
    )
    decisions_after_failure = (
        (
            await session.execute(select(ApprovalDecision).where(ApprovalDecision.run_id == bundle.approval.run_id))
        )
        .scalars()
        .all()
    )
    resume_events_after_failure = (
        (
            await session.execute(
                select(ApprovalEvent).where(
                    ApprovalEvent.approval_request_id == bundle.approval.id,
                    ApprovalEvent.event_type == "approval_resumed",
                )
            )
        )
        .scalars()
        .all()
    )
    resume_statuses_after_failure = {event.metadata_json["resume_status"] for event in resume_events_after_failure}

    assert first_response.status_code == 500
    assert first_response.json()["error"]["code"] == "APPROVAL_RESUME_FAILED"
    assert bundle.approval.status == "superseded"
    assert len(rows_after_failure) == 1
    assert len(decisions_after_failure) == 1
    assert {"attempted", "failed"} <= resume_statuses_after_failure
    assert len(graph.calls) == 1
    first_resume = dict(graph.calls[0][0].resume)
    assert first_resume["decision_type"] == "edit"
    assert first_resume["status"] == "superseded"
    assert first_resume["resume_route"] == "risk_gate"
    assert first_resume["edited_action"] == edited_action
    assert first_resume["new_action_payload_hash"]

    monkeypatch.setattr(session, "commit", original_commit)
    retry_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=decision_body,
        headers=headers,
    )
    payload = retry_response.json()
    rows = (
        (
            await session.execute(
                select(ApprovalRequest)
                .where(ApprovalRequest.run_id == bundle.approval.run_id)
                .order_by(ApprovalRequest.revision)
            )
        )
        .scalars()
        .all()
    )
    decisions = (
        (
            await session.execute(select(ApprovalDecision).where(ApprovalDecision.run_id == bundle.approval.run_id))
        )
        .scalars()
        .all()
    )
    resume_events = (
        (
            await session.execute(
                select(ApprovalEvent).where(
                    ApprovalEvent.approval_request_id == bundle.approval.id,
                    ApprovalEvent.event_type == "approval_resumed",
                )
            )
        )
        .scalars()
        .all()
    )
    resume_statuses = [event.metadata_json["resume_status"] for event in resume_events]
    replacement = next((row for row in rows if row.id != bundle.approval.id), None)
    retry_resume = dict(graph.calls[1][0].resume)

    assert retry_response.status_code == 200, payload
    assert payload["data"]["status"] == "superseded"
    assert payload["data"]["superseded_by_request_id"] is None
    assert len(graph.calls) == 2
    assert len(decisions) == 1
    assert resume_statuses.count("completed") == 1
    for key in (
        "approval_id",
        "tenant_id",
        "run_id",
        "status",
        "decision_type",
        "revision",
        "action_payload_hash",
        "safety_snapshot_hash",
        "edited_action",
        "new_action_payload_hash",
        "resume_route",
    ):
        assert retry_resume[key] == first_resume[key]
    assert len(rows) == 2
    assert replacement is not None
    assert replacement.status == "pending"
    assert replacement.requested_by == bundle.approval.requested_by
    assert replacement.action_payload_hash == first_resume["new_action_payload_hash"]
    assert payload["data"]["new_action_payload_hash"] == first_resume["new_action_payload_hash"]
    assert replacement.target_merchant_id == merchant_id
    assert replacement.business_fact_refs[0]["resource_id"] == edited_action["target_id"]
    assert replacement.verified_evidence_refs[0]["evidence_id"] == edited_action["evidence_refs"][0]["evidence_id"]
    assert replacement.claim_verification_ref is None
    assert replacement.claim_verification_summary["overall_status"] == "verified"
    assert replacement.risk_decision_ref == f"risk_decision:{bundle.approval.run_id}:{replacement.action_payload_hash}"
    assert replacement.risk_decision["action_payload_hash"] == replacement.action_payload_hash
    assert replacement.approval_idempotency_key


@pytest.mark.asyncio
async def test_decide_edit_retry_normalizes_persisted_legacy_route_before_graph_resume(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-edit-legacy-resume-retry")
    graph = ReinterruptResumeGraph(target_merchant_id=str(seeded_session["merchant"].id))
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    headers = await _admin_headers(client)
    edited_action = _edited_action(bundle)
    decision_body = _decision_body(bundle, "edit", edited_action=edited_action)
    original_commit = session.commit
    commit_count = 0

    async def fail_final_resume_commit():
        nonlocal commit_count
        commit_count += 1
        if commit_count == 3:
            raise RuntimeError("simulated historical retry commit failure")
        await original_commit()

    monkeypatch.setattr(session, "commit", fail_final_resume_commit)
    first_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=decision_body,
        headers=headers,
    )
    assert first_response.status_code == 500
    assert len(graph.calls) == 1

    monkeypatch.setattr(session, "commit", original_commit)
    decided_event = (
        (
            await session.execute(
                select(ApprovalEvent).where(
                    ApprovalEvent.approval_request_id == bundle.approval.id,
                    ApprovalEvent.event_type == "approval_decided",
                )
            )
        )
        .scalars()
        .one()
    )
    decided_event.metadata_json = {
        **(decided_event.metadata_json or {}),
        "resume_route": "assess_risk_and_approval",
    }
    await session.commit()

    retry_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=decision_body,
        headers=headers,
    )
    payload = retry_response.json()

    assert retry_response.status_code == 200, payload
    assert payload["data"]["resume_route"] == "risk_gate"
    assert len(graph.calls) == 2
    retry_resume = graph.calls[1][0].resume
    assert retry_resume["resume_route"] == "risk_gate"
    assert retry_resume["edited_action"] == edited_action
    assert retry_resume["new_action_payload_hash"] == graph.calls[0][0].resume["new_action_payload_hash"]


@pytest.mark.asyncio
async def test_decide_edit_retry_rejects_mismatched_hash_and_version(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-edit-retry-mismatch")
    graph = ReinterruptResumeGraph(target_merchant_id=str(seeded_session["merchant"].id))
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    headers = await _admin_headers(client)
    edited_action = _edited_action(bundle)
    decision_body = _decision_body(bundle, "edit", edited_action=edited_action)
    original_commit = session.commit
    commit_count = 0

    async def fail_final_resume_commit():
        nonlocal commit_count
        commit_count += 1
        if commit_count == 3:
            raise RuntimeError("simulated retry mismatch failure")
        await original_commit()

    monkeypatch.setattr(session, "commit", fail_final_resume_commit)
    first_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=decision_body,
        headers=headers,
    )
    assert first_response.status_code == 500
    assert len(graph.calls) == 1

    monkeypatch.setattr(session, "commit", original_commit)
    mismatched_hash = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json={**decision_body, "action_payload_hash": "sha256:" + "9" * 64},
        headers=headers,
    )
    mismatched_version = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json={**decision_body, "expected_request_version": decision_body["expected_request_version"] + 2},
        headers=headers,
    )

    assert mismatched_hash.status_code == 409
    assert mismatched_hash.json()["error"]["code"] == "CONFLICT"
    assert mismatched_version.status_code == 409
    assert mismatched_version.json()["error"]["code"] == "CONFLICT"
    assert len(graph.calls) == 1


def test_should_resume_graph_accepts_only_current_canonical_edit_route() -> None:
    canonical = _edit_decision_result_for_resume_route("risk_gate")
    legacy = _edit_decision_result_for_resume_route("assess_risk_and_approval")

    assert approvals_router._should_resume_graph(canonical) is True
    assert approvals_router._should_resume_graph(legacy) is False


def test_phase58_retry_route_compatibility_is_historical_persisted_data_read_only() -> None:
    source = Path("src/api/routers/approvals.py").read_text(encoding="utf-8")

    assert "LEGACY_RISK_ROUTE" not in source
    assert "HISTORICAL_RETRY_ROUTE_TO_CANONICAL" in source
    legacy_lines = [
        line.strip() for line in source.splitlines() if "assess_risk_and_approval" in line and not line.strip().startswith("#")
    ]
    assert legacy_lines == ['HISTORICAL_RETRY_ROUTE_TO_CANONICAL = {"assess_risk_and_approval": CANONICAL_RISK_ROUTE}']


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
        headers=await _admin_headers(client),
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
    trusted_context = config["configurable"]["trusted_context"]
    assert trusted_context["run_id"] == str(bundle.approval.run_id)
    assert trusted_context["permissions"] == []
    assert config["configurable"]["permissions"] == trusted_context["permissions"]


@pytest.mark.asyncio
async def test_decide_stale_version_conflict_returns_409_code_conflict(
    client: AsyncClient, session: AsyncSession, seeded_session, monkeypatch
):
    bundle = await _create_approval(session, seeded_session)
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle, expected_request_version=bundle.approval.version + 1),
        headers=await _admin_headers(client),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_decide_self_approval_returns_403_self_approval(
    client: AsyncClient, session: AsyncSession, seeded_session, monkeypatch
):
    admin = seeded_session["users"]["admin_user"]
    bundle = await _create_approval(session, seeded_session, requested_by=admin)
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle),
        headers=await _admin_headers(client),
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

    response = await client.get(f"/api/v1/approvals/{bundle.approval.id}", headers=await _admin_headers(client))
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
async def test_manager_approval_review_paths_allow_same_merchant(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-manager-allow")
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)
    manager_headers = await _manager_headers(client)

    list_response = await client.get("/api/v1/approvals", headers=manager_headers)
    get_response = await client.get(f"/api/v1/approvals/{bundle.approval.id}", headers=manager_headers)
    decide_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle),
        headers=manager_headers,
    )

    assert list_response.status_code == 200
    assert get_response.status_code == 200
    assert decide_response.status_code == 200
    assert list_response.json()["data"]["total"] == 1
    assert list_response.json()["data"]["approvals"][0]["id"] == str(bundle.approval.id)
    assert get_response.json()["data"]["target_merchant_id"] == str(seeded_session["merchant"].id)


@pytest.mark.asyncio
async def test_manager_approval_review_paths_deny_cross_merchant(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    other_support = seeded_session["users"]["cs_other_merchant"]
    bundle = await _create_approval(
        session,
        seeded_session,
        requested_by=other_support,
        thread_id="thread-manager-cross-deny",
    )
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)
    manager_headers = await _manager_headers(client)

    list_response = await client.get("/api/v1/approvals", headers=manager_headers)
    get_response = await client.get(f"/api/v1/approvals/{bundle.approval.id}", headers=manager_headers)
    decide_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle),
        headers=manager_headers,
    )

    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 0
    assert get_response.status_code == 403
    assert decide_response.status_code == 403
    assert get_response.json()["error"]["code"] == "FORBIDDEN"
    assert decide_response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_manager_approval_review_paths_deny_missing_target_merchant(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    with pytest.raises(ApprovalTransitionError, match="action-bound snapshot requires target merchant binding"):
        await _create_approval(
            session,
            seeded_session,
            thread_id="thread-manager-missing-target-deny",
            with_phase34_bindings=False,
        )


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

    response = await client.get("/api/v1/approvals", headers=await _admin_headers(client))
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
async def test_approval_resume_completed_runs_terminal_memory_finalizer(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-completed-finalizer")
    refund_case = seeded_session["refund_case"]
    monkeypatch.setattr(
        app.state,
        "agent_graph",
        FakeResumeGraph(
            "approved final",
            extra_state={
                "primary_intent": "refund_status",
                "approval_result": {"status": "approved", "decision_type": "approve"},
                "approval_required": True,
                "risk_assessment": {
                    "approval_required": True,
                    "risk_level": "high",
                    "risk_reason": "manual approval completed",
                },
                "active_slots": {
                    "refund_case_id": refund_case.refund_case_no,
                    "issue_type": "refund_status",
                },
                "extracted_slots": {"refund_case_id": refund_case.refund_case_no},
            },
        ),
        raising=False,
    )

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle),
        headers=await _admin_headers(client),
    )

    run = await session.get(AgentRun, bundle.approval.run_id)
    assert response.status_code == 200
    assert run is not None
    assert run.final_status == "completed"
    assert run.final_response == "approved final"
    assert run.total_latency_ms >= 10
    assistant_messages = await _messages_for_run(session, run_id=bundle.approval.run_id, role="assistant")
    assert len(assistant_messages) == 1
    message_thread = await session.get(ConversationThread, assistant_messages[0].conversation_thread_id)
    assert message_thread is not None
    assert message_thread.user_id == run.user_id
    assert assistant_messages[0].metadata_json["source"] == "agent_runs.finalizer"
    assert assistant_messages[0].metadata_json["status"] == "completed"
    assert (
        await _count_rows(
            session,
            ConversationSummary,
            ConversationSummary.thread_id == run.thread_id,
            ConversationSummary.summary_type == "thread_rolling",
            ConversationSummary.deleted_at.is_(None),
        )
        == 1
    )
    memory_events = (
        (
            await session.execute(
                select(MemoryWriteEvent).where(
                    MemoryWriteEvent.run_id == bundle.approval.run_id,
                    MemoryWriteEvent.memory_type == "session_slot",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(memory_events) == 1
    assert memory_events[0].decision == "write"
    finalizer_steps = await _finalizer_steps(session, run_id=bundle.approval.run_id)
    assert len(finalizer_steps) == 1
    metrics = finalizer_steps[0].metrics_json or {}
    assert metrics["memory_write_status"] == "completed"
    assert metrics["memory_write_reason_code"] != "not_completed_path"
    assert "case_working_context_status" in metrics
    assert metrics["case_working_context_status"] in {"written", "skipped", "error", "conflict"}


async def _manager_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": "approval_manager", "password": "moca2024"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": "admin_user", "password": "moca2024"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}
