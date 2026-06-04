from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.api.main import app
from src.api.routers.agent_runs import _event_generator
from src.auth.jwt import create_access_token
from src.db.models import AgentRun, ApprovalRequest, User


class NeverCalledGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict]] = []

    async def astream(self, input_state, config, stream_mode):
        self.calls.append((input_state, config))
        raise AssertionError("graph.astream must not be called")
        yield


class CancelledGraph:
    async def astream(self, input_state, config, stream_mode):
        raise asyncio.CancelledError("client disconnected")
        yield


class SlowGraph:
    async def astream(self, input_state, config, stream_mode):
        await asyncio.sleep(0.05)
        yield ("receive_request", {"trace_steps": []})


class MissingFinalResponseGraph:
    async def astream(self, input_state, config, stream_mode):
        yield (
            "assess_risk_and_approval",
            {
                "current_intent": "refund_troubleshooting",
                "recommendation_draft": {
                    "recommended_action": "manual_review",
                    "reasoning_summary": "退款链路需要人工核实。",
                    "evidence_refs": [
                        {
                            "doc_key": "refund_policy",
                            "chunk_id": "refund_policy_001",
                            "title": "退款规则",
                            "section": "超时处理",
                            "confidence": 0.9,
                        }
                    ],
                    "confidence": 0.8,
                },
                "risk_assessment": {
                    "risk_level": "low",
                    "risk_reason": "No customer compensation proposed.",
                    "approval_required": False,
                },
                "trace_steps": [
                    {
                        "node": "assess_risk_and_approval",
                        "status": "completed",
                        "started_at": datetime.now(UTC).isoformat(),
                        "completed_at": datetime.now(UTC).isoformat(),
                    }
                ],
            },
        )


class FakeInterrupt:
    def __init__(self, value: dict):
        self.value = value


class StreamInterruptGraph:
    async def astream(self, input_state, config, stream_mode):
        yield (
            "assess_risk_and_approval",
            {
                "risk_assessment": {
                    "risk_level": "high",
                    "risk_reason": "Compensation amount exceeds threshold.",
                    "approval_required": True,
                    "rule_ref": "RISK-COMP-001",
                },
                "proposed_action": {
                    "action_type": "issue_coupon",
                    "target_id": "ORD-2024-001",
                    "amount": 600,
                },
                "trace_steps": [
                    {
                        "node": "assess_risk_and_approval",
                        "status": "completed",
                        "started_at": datetime.now(UTC).isoformat(),
                        "completed_at": datetime.now(UTC).isoformat(),
                    }
                ],
            },
        )
        yield (
            "__interrupt__",
            (
                FakeInterrupt(
                    {
                        "proposed_action": {
                            "action_type": "issue_coupon",
                            "target_id": "ORD-2024-001",
                            "amount": 600,
                        },
                        "risk_level": "high",
                        "risk_reason": "Compensation amount exceeds threshold.",
                        "risk_rule_ref": "RISK-COMP-001",
                        "expires_at": datetime.now(UTC).isoformat(),
                    }
                ),
            ),
        )


INVESTIGATION_RESPONSE_FIELDS = {
    "investigation_result",
    "investigation_steps",
    "investigation_trigger_reason",
    "investigation_path",
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


async def _create_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    final_status: str = "pending",
) -> AgentRun:
    run_id = uuid4()
    now = datetime.now(UTC)
    return await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=f"sse-{run_id}",
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        input_query="SSE duplicate guard test",
        final_status=final_status,
        final_response=None,
        started_at=now,
        completed_at=None,
        total_latency_ms=None,
    )


def _event_data(event: dict) -> dict:
    return json.loads(event["data"])


def _assert_no_investigation_fields(payload: dict) -> None:
    assert INVESTIGATION_RESPONSE_FIELDS.isdisjoint(payload)
    serialized = json.dumps(payload, ensure_ascii=False)
    for field in INVESTIGATION_RESPONSE_FIELDS:
        assert field not in serialized


@pytest.mark.asyncio
async def test_events_rejects_already_started_run_with_409(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()
    graph = NeverCalledGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.get(
        f"/api/v1/agent-runs/{run.id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUN_ALREADY_STARTED"
    assert graph.calls == []


@pytest.mark.asyncio
async def test_events_rejects_terminal_run_with_409(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="completed")
    await session.commit()
    graph = NeverCalledGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.get(
        f"/api/v1/agent-runs/{run.id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUN_ALREADY_STARTED"
    assert graph.calls == []


@pytest.mark.asyncio
async def test_events_rejects_cross_tenant_run_before_claim(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    other_user = seeded_session["users"]["other_support"]
    run = await _create_run(session, tenant_id=other_user.tenant_id, user_id=other_user.id)
    await session.commit()
    graph = NeverCalledGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.get(
        f"/api/v1/agent-runs/{run.id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 404
    assert graph.calls == []
    await session.refresh(run)
    assert run.final_status == "pending"


@pytest.mark.asyncio
async def test_event_generator_marks_run_error_when_stream_is_cancelled(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    generator = _event_generator(
        CancelledGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    first_event = await anext(generator)
    assert '"event_type": "run_started"' in first_event["data"]
    with pytest.raises(asyncio.CancelledError):
        await anext(generator)

    await session.refresh(run)
    assert run.final_status == "error"
    assert run.completed_at is not None
    assert run.error_summary == "client disconnected"


@pytest.mark.asyncio
async def test_event_generator_sends_keepalive_while_graph_node_is_running(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    monkeypatch.setattr("src.api.routers.agent_runs.SSE_HEARTBEAT_SECONDS", 0.01)
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    generator = _event_generator(
        SlowGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    try:
        first_event = await anext(generator)
        keepalive = await anext(generator)
        next_event = await anext(generator)
        while "data" not in next_event:
            next_event = await anext(generator)
    finally:
        await generator.aclose()

    assert '"event_type": "run_started"' in first_event["data"]
    assert keepalive == {"comment": "keepalive"}
    assert '"event_type": "step_started"' in next_event["data"]


@pytest.mark.asyncio
async def test_event_generator_synthesizes_final_response_when_stream_ends_without_one(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    generator = _event_generator(
        MissingFinalResponseGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    final_event = None
    async for event in generator:
        if "data" in event and '"event_type": "final_response"' in event["data"]:
            final_event = event

    await session.refresh(run)
    assert final_event is not None
    final_data = _event_data(final_event)
    assert set(final_data["payload"]) == {"final_response"}
    _assert_no_investigation_fields(final_data)
    assert run.final_status == "completed"
    assert run.final_response is not None
    assert "退款链路需要人工核实" in run.final_response


@pytest.mark.asyncio
async def test_event_generator_reports_completion_persistence_failure(
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    async def fail_write_agent_steps(*args, **kwargs):
        raise RuntimeError("step write failed")

    monkeypatch.setattr("src.api.routers.agent_runs.write_agent_steps", fail_write_agent_steps)
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    generator = _event_generator(
        MissingFinalResponseGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    events = [event async for event in generator]

    await session.refresh(run)
    assert any("step write failed" in event.get("data", "") for event in events)
    assert any('"event_type": "error"' in event.get("data", "") for event in events)
    assert not any('"event_type": "final_response"' in event.get("data", "") for event in events)
    assert run.final_status == "error"
    assert run.final_response is None
    assert run.error_summary == "step write failed"


@pytest.mark.asyncio
async def test_event_generator_treats_stream_interrupt_node_as_approval_required(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    generator = _event_generator(
        StreamInterruptGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    approval_event = None
    async for event in generator:
        if "data" in event and '"event_type": "approval_required"' in event["data"]:
            approval_event = event

    await session.refresh(run)
    approval = (await session.execute(select(ApprovalRequest).where(ApprovalRequest.run_id == run.id))).scalar_one()
    assert approval_event is not None
    approval_data = _event_data(approval_event)
    assert set(approval_data["payload"]) == {"approval_id", "proposed_action", "risk_level"}
    _assert_no_investigation_fields(approval_data)
    assert '"status": "waiting_approval"' in approval_event["data"]
    assert run.final_status == "interrupted"
    assert run.final_response is None
    assert approval.status == "pending"
    assert approval.risk_level == "high"
    assert approval.proposed_action["amount"] == 600
