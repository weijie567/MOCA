from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.api.main import app
from src.api.routers.agent_runs import _dedupe_evidence_refs, _event_generator, _extract_step_payload
from src.auth.jwt import create_access_token
from src.db.models import AgentRun, ApprovalRequest, User


class NeverCalledGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict]] = []

    async def astream(self, input_state, config, stream_mode):
        self.calls.append((input_state, config))
        raise AssertionError("graph.astream must not be called")
        yield


class CaptureConfigGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict]] = []

    async def astream(self, input_state, config, stream_mode):
        self.calls.append((input_state, config))
        yield ("final_response", {"final_response": "done", "trace_steps": []})


class CaptureInvokeConfigGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[object, dict]] = []

    async def ainvoke(self, input_state, config):
        self.calls.append((input_state, config))
        return {"final_response": "done", "trace_steps": []}


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


def test_extract_step_payload_counts_v2_evidence_refs():
    payload = _extract_step_payload(
        "investigate",
        {
            "retrieved_evidence": {
                "schema_version": "knowledge_search_result.v2",
                "evidence_refs": [
                    {"evidence_id": "refund_policy/refund_policy_001@v1"},
                    {"evidence_id": "refund_policy/refund_policy_001@v2"},
                ],
            }
        },
    )

    assert payload["evidence_count"] == 2


def test_dedupe_evidence_refs_preserves_policy_versions():
    refs = _dedupe_evidence_refs(
        [
            [
                {
                    "evidence_id": "refund_policy/refund_policy_001@v1",
                    "chunk_id": "refund_policy_001",
                },
                {
                    "evidence_id": "refund_policy/refund_policy_001@v2",
                    "chunk_id": "refund_policy_001",
                },
            ]
        ]
    )

    assert [ref["evidence_id"] for ref in refs] == [
        "refund_policy/refund_policy_001@v1",
        "refund_policy/refund_policy_001@v2",
    ]
    assert all("text" not in ref for ref in refs)


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


def test_agent_chat_only_support_token_receives_no_tool_permissions():
    """A support-role token with only agent:chat gets permissions=[] in trusted config."""
    from unittest.mock import MagicMock
    from src.api.routers.agent_runs import _trusted_tool_config

    user = MagicMock()
    user.role = "support"

    # The intersection of token_scopes={"agent:chat"} and ROLE_SCOPES["support"]
    # should yield no tool permissions since agent:chat has no tool mapping
    config = _trusted_tool_config(user, token_scopes=["agent:chat"], trace_id="test-trace")
    assert config["permissions"] == []


@pytest.mark.asyncio
async def test_agent_chat_only_token_streams_with_no_tool_permissions(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id)
    await session.commit()
    graph = CaptureConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.get(
        f"/api/v1/agent-runs/{run.id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 200
    assert len(graph.calls) == 1
    _, config = graph.calls[0]
    assert config["configurable"]["permissions"] == []


@pytest.mark.asyncio
async def test_agent_chat_only_token_invokes_legacy_chat_with_no_tool_permissions(
    client: AsyncClient,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureInvokeConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "退款政策是什么？", "thread_id": f"restricted-chat-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 200
    assert len(graph.calls) == 1
    _, config = graph.calls[0]
    assert config["configurable"]["permissions"] == []


@pytest.mark.asyncio
async def test_chat_memory_write_background_returns_final_response_before_slow_hook(
    client: AsyncClient,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureInvokeConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    started = asyncio.Event()
    finished = asyncio.Event()
    captured: dict[str, object] = {}

    def fake_schedule_memory_write(final_state, *, session_factory, trace_id=None):
        captured["session_factory"] = session_factory

        async def slow_hook():
            started.set()
            await asyncio.sleep(0.2)
            finished.set()

        return asyncio.create_task(slow_hook())

    monkeypatch.setattr("src.api.routers.agent._schedule_memory_write_after_response", fake_schedule_memory_write)
    t0 = time.perf_counter()

    response = await client.post(
        "/api/v1/agent/chat",
        json={"query": "退款政策是什么？", "thread_id": f"memory-write-chat-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 200
    assert response.json()["data"]["response"] == "done"
    assert time.perf_counter() - t0 < 0.15
    assert captured["session_factory"] is not None
    assert started.is_set()
    assert not finished.is_set()


@pytest.mark.asyncio
async def test_sse_final_response_before_memory_write_schedule(session: AsyncSession, seeded_session, monkeypatch):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()
    scheduled: list[dict] = []

    def fake_schedule_memory_write(final_state, *, session_factory, trace_id=None):
        scheduled.append(final_state)

    monkeypatch.setattr("src.api.routers.agent_runs._schedule_memory_write_after_response", fake_schedule_memory_write)
    generator = _event_generator(
        CaptureConfigGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    final_event = None
    try:
        async for event in generator:
            if "data" in event and '"event_type": "final_response"' in event["data"]:
                final_event = event
                assert scheduled == []
                break
        assert final_event is not None
        with pytest.raises(StopAsyncIteration):
            await anext(generator)
        assert scheduled
    finally:
        await generator.aclose()


@pytest.mark.asyncio
async def test_sse_interrupted_path_skips_memory_write(session: AsyncSession, seeded_session, monkeypatch):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()
    scheduled: list[dict] = []

    def fake_schedule_memory_write(final_state, *, session_factory, trace_id=None):
        scheduled.append(final_state)

    monkeypatch.setattr("src.api.routers.agent_runs._schedule_memory_write_after_response", fake_schedule_memory_write)
    generator = _event_generator(
        StreamInterruptGraph(),
        {"user_query": run.input_query},
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    events = [event async for event in generator]

    assert any("approval_required" in event.get("data", "") for event in events)
    assert scheduled == []


def test_support_token_with_orders_read_gets_only_get_order():
    """A support token with agent:chat+orders:read gets exactly ['tool:get_order']."""
    from unittest.mock import MagicMock
    from src.api.routers.agent_runs import _trusted_tool_config

    user = MagicMock()
    user.role = "support"

    config = _trusted_tool_config(user, token_scopes=["agent:chat", "orders:read"], trace_id="test-trace")
    assert config["permissions"] == ["tool:get_order"]


def test_merchant_with_merchant_id_none_gets_empty_merchant_ids():
    """A merchant with merchant_id=None receives explicit deny-all scope."""
    from unittest.mock import MagicMock
    from src.api.routers.agent_runs import _trusted_tool_config

    user = MagicMock()
    user.role = "merchant"
    user.merchant_id = None

    config = _trusted_tool_config(user, token_scopes=["agent:chat"], trace_id="test-trace")

    assert config["merchant_scope"]["merchant_ids"] == []


def test_role_scopes_alone_widen_permissions():
    """Without token scope intersection, a support user would get all role permissions."""
    from unittest.mock import MagicMock
    from src.api.routers.agent_runs import _trusted_tool_config

    user = MagicMock()
    user.role = "support"
    user.merchant_id = "test-merchant"

    # Full role scopes should give all mapped permissions
    config = _trusted_tool_config(
        user,
        token_scopes=["orders:read", "refunds:read", "tickets:read", "knowledge:read", "agent:chat"],
        trace_id="test-trace",
    )
    assert set(config["permissions"]) == {
        "tool:get_order",
        "tool:get_refund_case",
        "tool:get_ticket",
        "tool:search_policy",
    }
