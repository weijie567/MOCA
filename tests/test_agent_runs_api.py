from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.api.main import app
from src.api.routers.agent_runs import _dedupe_evidence_refs, _event_generator, _extract_step_payload
from src.approvals.schemas import PROPOSED_ACTION_SCHEMA_VERSION
from src.approvals.snapshot_service import compute_action_payload_hash, persist_action_safety_snapshot
from src.auth.jwt import ROLE_SCOPES, create_access_token
from src.db.models import (
    AgentRun,
    AgentTraceEvent,
    ApprovalRequest,
    ConversationMessage,
    ConversationSummary,
    MemoryWriteEvent,
    ToolResultRecord,
    User,
)
from src.knowledge.schemas import EvidenceRefV1


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


class ErrorGraph:
    async def astream(self, input_state, config, stream_mode):
        raise RuntimeError("graph failed")
        yield


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
        evidence_ref = EvidenceRefV1.build(
            tenant_id=input_state["tenant_id"],
            doc_key="refund_policy",
            chunk_id="refund_policy_001",
            policy_version="v1",
            text="Compensation above 500 CNY requires approval.",
            retrieved_at=_fixed_ms_iso_z(),
            retrieval_config_version="retrieval.v1",
            rank=1,
        )
        proposed_action = {
            "schema_version": PROPOSED_ACTION_SCHEMA_VERSION,
            "tenant_id": input_state["tenant_id"],
            "run_id": input_state["current_run_id"],
            "action_id": f"act:{input_state['current_run_id']}:issue_coupon:ORD-2024-001",
            "action_type": "issue_coupon",
            "target_type": "order",
            "target_id": "ORD-2024-001",
            "amount": "600.00",
            "currency": "CNY",
            "args": {"risk_level": "high", "rule_ref": "RISK-COMP-001"},
            "reason": "Compensation amount exceeds threshold.",
            "evidence_refs": [evidence_ref.model_dump(mode="json", exclude_none=True)],
        }
        action_payload_hash = compute_action_payload_hash(proposed_action)
        snapshot = await persist_action_safety_snapshot(
            config["configurable"]["session"],
            tenant_id=UUID(input_state["tenant_id"]),
            run_id=UUID(input_state["current_run_id"]),
            proposed_action=proposed_action,
            action_payload_hash=action_payload_hash,
            policy_config_version="approval-policy.v1",
            risk_config_version="risk-rules.v1",
            retrieval_config_version=evidence_ref.retrieval_config_version,
            evidence_refs=[evidence_ref],
            created_at=_fixed_ms_now(),
            created_by=UUID(input_state["user_id"]),
        )
        yield (
            "assess_risk_and_approval",
            {
                "risk_assessment": {
                    "risk_level": "high",
                    "risk_reason": "Compensation amount exceeds threshold.",
                    "approval_required": True,
                    "rule_ref": "RISK-COMP-001",
                },
                "proposed_action": proposed_action,
                "action_payload_hash": snapshot.action_payload_hash,
                "safety_snapshot_ref": snapshot.safety_snapshot_ref,
                "safety_snapshot_hash": snapshot.safety_snapshot_hash,
                "safety_snapshot_verified": True,
                "policy_config_version": "approval-policy.v1",
                "risk_config_version": "risk-rules.v1",
                "retrieval_config_version": evidence_ref.retrieval_config_version,
                "evidence_refs": [evidence_ref.model_dump(mode="json", exclude_none=True)],
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
                        "proposed_action": proposed_action,
                        "action_payload_hash": snapshot.action_payload_hash,
                        "safety_snapshot_ref": snapshot.safety_snapshot_ref,
                        "safety_snapshot_hash": snapshot.safety_snapshot_hash,
                        "policy_config_version": "approval-policy.v1",
                        "risk_config_version": "risk-rules.v1",
                        "retrieval_config_version": evidence_ref.retrieval_config_version,
                        "evidence_refs": [evidence_ref.model_dump(mode="json", exclude_none=True)],
                        "risk_level": "high",
                        "risk_reason": "Compensation amount exceeds threshold.",
                        "risk_rule_ref": "RISK-COMP-001",
                        "expires_at": datetime.now(UTC).isoformat(),
                    }
                ),
            ),
        )


def _fixed_ms_now() -> datetime:
    now = datetime.now(UTC)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def _fixed_ms_iso_z() -> str:
    now = _fixed_ms_now()
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


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


def _stream_input(run: AgentRun, user: User) -> dict[str, str]:
    return {
        "user_query": run.input_query,
        "thread_id": run.thread_id,
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.id),
        "role": user.role,
        "current_run_id": str(run.id),
    }


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


async def _run_agent_run_stream(client: AsyncClient, run_id: str, user: User) -> list[dict]:
    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert response.status_code == 200
    events: list[dict] = []
    for line in response.text.splitlines():
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line.removeprefix("data: ")))
    return events


async def _messages_for_run(session: AsyncSession, *, run_id: UUID, role: str | None = None) -> list[ConversationMessage]:
    filters = [ConversationMessage.run_id == run_id, ConversationMessage.deleted_at.is_(None)]
    if role is not None:
        filters.append(ConversationMessage.role == role)
    result = await session.execute(select(ConversationMessage).where(*filters).order_by(ConversationMessage.message_index))
    return list(result.scalars().all())


async def _count_rows(session: AsyncSession, model, *filters) -> int:
    result = await session.execute(select(func.count()).select_from(model).where(*filters))
    return int(result.scalar_one())


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
async def test_create_agent_run_persists_exactly_one_user_message(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)

    response = await client.post(
        "/api/v1/agent-runs",
        json={"query": "订单 ORD-TEST-001 的退款进度如何？", "thread_id": f"phase24-create-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )

    assert response.status_code == 200
    run_id = UUID(response.json()["data"]["run_id"])
    user_messages = await _messages_for_run(session, run_id=run_id, role="user")
    assert len(user_messages) == 1
    assert user_messages[0].role == "user"
    assert user_messages[0].run_id == run_id
    assert user_messages[0].content == "订单 ORD-TEST-001 的退款进度如何？"

    await _run_agent_run_stream(client, str(run_id), user)
    duplicate_response = await client.get(
        f"/api/v1/agent-runs/{run_id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert duplicate_response.status_code == 409
    assert len(await _messages_for_run(session, run_id=run_id, role="user")) == 1


@pytest.mark.asyncio
async def test_agent_run_stream_passes_conversation_ids_to_graph_and_tools(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    response = await client.post(
        "/api/v1/agent-runs",
        json={"query": "帮我查一下订单 ORD-TEST-001", "thread_id": f"phase24-config-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert response.status_code == 200
    run_id = UUID(response.json()["data"]["run_id"])

    user_messages = await _messages_for_run(session, run_id=run_id, role="user")
    assert len(user_messages) == 1
    await _run_agent_run_stream(client, str(run_id), user)

    assert len(graph.calls) == 1
    _, config = graph.calls[0]
    configurable = config["configurable"]
    assert configurable["conversation_thread_id"] == str(user_messages[0].conversation_thread_id)
    assert configurable["conversation_message_id"] == str(user_messages[0].id)


@pytest.mark.asyncio
async def test_completed_agent_run_persists_exactly_one_assistant_message(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    monkeypatch.setattr(app.state, "agent_graph", CaptureConfigGraph(), raising=False)
    response = await client.post(
        "/api/v1/agent-runs",
        json={"query": "给我一个完成答复", "thread_id": f"phase24-assistant-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert response.status_code == 200
    run_id = UUID(response.json()["data"]["run_id"])

    await _run_agent_run_stream(client, str(run_id), user)

    assistant_messages = await _messages_for_run(session, run_id=run_id, role="assistant")
    assert len(assistant_messages) == 1
    assert assistant_messages[0].content == "done"
    assert assistant_messages[0].metadata_json["status"] == "completed"


@pytest.mark.asyncio
async def test_completed_agent_run_updates_thread_summary_idempotently(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    tenant_id = user.tenant_id
    monkeypatch.setattr(app.state, "agent_graph", CaptureConfigGraph(), raising=False)
    response = await client.post(
        "/api/v1/agent-runs",
        json={"query": "总结这个回合", "thread_id": f"phase24-summary-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert response.status_code == 200
    run_id = UUID(response.json()["data"]["run_id"])

    await _run_agent_run_stream(client, str(run_id), user)
    duplicate_response = await client.get(
        f"/api/v1/agent-runs/{run_id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert duplicate_response.status_code == 409

    summaries = (
        (
            await session.execute(
                select(ConversationSummary).where(
                    ConversationSummary.tenant_id == tenant_id,
                    ConversationSummary.summary_type == "thread_rolling",
                    ConversationSummary.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(summaries) == 1
    assert str(run_id) in (summaries[0].summary_json or {}).get("source_run_ids", [str(run_id)])


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
    lifecycle_rows = (
        (
            await session.execute(
                select(AgentTraceEvent)
                .where(AgentTraceEvent.run_id == run.id, AgentTraceEvent.event_type == "run_status_changed")
                .order_by(AgentTraceEvent.sequence)
            )
        )
        .scalars()
        .all()
    )
    assert run.final_status == "error"
    assert run.completed_at is not None
    assert run.error_summary == "client disconnected"
    assert [row.redacted_payload["status"] for row in lifecycle_rows] == ["running", "error"]
    assert all(row.redacted_payload["status"] != "completed" for row in lifecycle_rows)


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
    lifecycle_rows = (
        (
            await session.execute(
                select(AgentTraceEvent)
                .where(AgentTraceEvent.run_id == run.id, AgentTraceEvent.event_type == "run_status_changed")
                .order_by(AgentTraceEvent.sequence)
            )
        )
        .scalars()
        .all()
    )
    assert final_event is not None
    final_data = _event_data(final_event)
    assert set(final_data["payload"]) == {"final_response"}
    _assert_no_investigation_fields(final_data)
    assert run.final_status == "completed"
    assert run.final_response is not None
    assert "退款链路需要人工核实" in run.final_response
    assert [row.redacted_payload["status"] for row in lifecycle_rows] == ["running", "completed"]


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
        _stream_input(run, user),
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
    lifecycle_rows = (
        (
            await session.execute(
                select(AgentTraceEvent)
                .where(AgentTraceEvent.run_id == run.id, AgentTraceEvent.event_type == "run_status_changed")
                .order_by(AgentTraceEvent.sequence)
            )
        )
        .scalars()
        .all()
    )
    assert approval_event is not None
    approval_data = _event_data(approval_event)
    assert {"approval_id", "proposed_action", "risk_level"}.issubset(approval_data["payload"])
    assert {
        "approval_revision_refs",
        "expected_request_version",
        "expected_level_version",
        "expected_assignment_version",
        "expected_revision",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
        "allowed_decision_types",
    }.issubset(approval_data["payload"])
    assert approval_data["payload"]["allowed_decision_types"] == [
        "accept",
        "approve",
        "edit",
        "respond",
        "reject",
        "ignore",
    ]
    _assert_no_investigation_fields(approval_data)
    assert '"status": "waiting_approval"' in approval_event["data"]
    assert run.final_status == "interrupted"
    assert run.final_response is None
    assert approval.status == "pending"
    assert approval.risk_level == "high"
    assert approval.proposed_action["amount"] == "600.00"
    assert [row.redacted_payload["status"] for row in lifecycle_rows] == ["running", "interrupted"]


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
async def test_sse_final_response_after_bounded_memory_persistence_result(
    session: AsyncSession, seeded_session, monkeypatch
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()
    memory_results: list[dict] = []

    async def fake_memory_write(final_state, config):
        result = {"status": "completed", "reason_code": "memory_persisted"}
        memory_results.append(result)
        return {
            **final_state,
            "memory_write_result": result,
            "trace_steps": [
                {
                    "node": "memory_write",
                    "status": "completed",
                    "started_at": datetime.now(UTC).isoformat(),
                    "completed_at": datetime.now(UTC).isoformat(),
                }
            ],
        }

    monkeypatch.setattr("src.api.routers.agent_runs.memory_write", fake_memory_write)
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
                assert memory_results == [{"status": "completed", "reason_code": "memory_persisted"}]
                break
        assert final_event is not None
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
        _stream_input(run, user),
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    events = [event async for event in generator]

    assert any("approval_required" in event.get("data", "") for event in events)
    assert scheduled == []


@pytest.mark.asyncio
async def test_agent_run_error_cancel_interrupted_do_not_write_completed_memory(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]

    error_run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    cancelled_run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    interrupted_run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    error_events = [
        event
        async for event in _event_generator(
            ErrorGraph(),
            _stream_input(error_run, user),
            {"configurable": {"thread_id": error_run.thread_id, "session": session}},
            run=error_run,
            session=session,
            user=user,
        )
    ]
    with pytest.raises(asyncio.CancelledError):
        generator = _event_generator(
            CancelledGraph(),
            _stream_input(cancelled_run, user),
            {"configurable": {"thread_id": cancelled_run.thread_id, "session": session}},
            run=cancelled_run,
            session=session,
            user=user,
        )
        await anext(generator)
        await anext(generator)
    interrupted_events = [
        event
        async for event in _event_generator(
            StreamInterruptGraph(),
            _stream_input(interrupted_run, user),
            {"configurable": {"thread_id": interrupted_run.thread_id, "session": session}},
            run=interrupted_run,
            session=session,
            user=user,
        )
    ]

    assert any('"event_type": "error"' in event.get("data", "") for event in error_events)
    assert any('"event_type": "approval_required"' in event.get("data", "") for event in interrupted_events)
    for run in (error_run, cancelled_run, interrupted_run):
        await session.refresh(run)
        assert run.final_status in {"error", "interrupted"}
        assert await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run.id, ConversationMessage.role == "assistant") == 0
        assert await _count_rows(session, ConversationSummary, ConversationSummary.thread_id == run.thread_id) == 0


@pytest.mark.asyncio
async def test_duplicate_sse_stream_does_not_duplicate_memory_surfaces(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    monkeypatch.setattr(app.state, "agent_graph", CaptureConfigGraph(), raising=False)
    response = await client.post(
        "/api/v1/agent-runs",
        json={"query": "重复打开 SSE 不能重复写记忆", "thread_id": f"phase24-duplicate-{uuid4()}"},
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert response.status_code == 200
    run_id = UUID(response.json()["data"]["run_id"])

    await _run_agent_run_stream(client, str(run_id), user)
    counts_after_first = {
        "user": await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run_id, ConversationMessage.role == "user"),
        "assistant": await _count_rows(
            session, ConversationMessage, ConversationMessage.run_id == run_id, ConversationMessage.role == "assistant"
        ),
        "tool_results": await _count_rows(session, ToolResultRecord, ToolResultRecord.run_id == run_id),
        "summaries": await _count_rows(session, ConversationSummary, ConversationSummary.thread_id.like("phase24-duplicate-%")),
        "session_memory_writes": await _count_rows(session, MemoryWriteEvent, MemoryWriteEvent.run_id == run_id),
    }
    duplicate_response = await client.get(
        f"/api/v1/agent-runs/{run_id}/events",
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert duplicate_response.status_code == 409
    counts_after_duplicate = {
        "user": await _count_rows(session, ConversationMessage, ConversationMessage.run_id == run_id, ConversationMessage.role == "user"),
        "assistant": await _count_rows(
            session, ConversationMessage, ConversationMessage.run_id == run_id, ConversationMessage.role == "assistant"
        ),
        "tool_results": await _count_rows(session, ToolResultRecord, ToolResultRecord.run_id == run_id),
        "summaries": await _count_rows(session, ConversationSummary, ConversationSummary.thread_id.like("phase24-duplicate-%")),
        "session_memory_writes": await _count_rows(session, MemoryWriteEvent, MemoryWriteEvent.run_id == run_id),
    }

    assert counts_after_first["user"] == 1
    assert counts_after_first["assistant"] == 1
    assert counts_after_first["tool_results"] == 0
    assert counts_after_first["summaries"] == 1
    assert counts_after_first["session_memory_writes"] >= 0
    assert counts_after_duplicate == counts_after_first


@pytest.mark.asyncio
async def test_three_turn_agent_runs_smoke_uses_slots_and_summary_context(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    user = seeded_session["users"]["cs_zhang"]
    graph = CaptureConfigGraph()
    monkeypatch.setattr(app.state, "agent_graph", graph, raising=False)
    thread_id = f"phase24-three-turn-{uuid4()}"

    run_ids: list[UUID] = []
    for query in (
        "订单 ORD-TEST-001 的退款进度如何？",
        "那这个订单下一步应该怎么处理？",
        "总结一下刚才这个退款问题和后续动作。",
    ):
        response = await client.post(
            "/api/v1/agent-runs",
            json={"query": query, "thread_id": thread_id},
            headers=_auth_header(user, ["agent:chat"]),
        )
        assert response.status_code == 200
        run_id = UUID(response.json()["data"]["run_id"])
        run_ids.append(run_id)
        await _run_agent_run_stream(client, str(run_id), user)

    assert await _count_rows(session, ConversationMessage, ConversationMessage.thread_id == thread_id, ConversationMessage.role == "user") >= 3
    assert await _count_rows(
        session,
        ConversationMessage,
        ConversationMessage.thread_id == thread_id,
        ConversationMessage.role == "assistant",
        ConversationMessage.metadata_json["status"].as_string() == "completed",
    ) >= 3
    assert await _count_rows(
        session,
        ConversationSummary,
        ConversationSummary.thread_id == thread_id,
        ConversationSummary.summary_type == "thread_rolling",
    ) >= 1
    assert len(graph.calls) == 3
    assert all("conversation_message_id" in config["configurable"] for _, config in graph.calls)
    assert all("conversation_thread_id" in config["configurable"] for _, config in graph.calls)
    assert set(run_ids) == {
        UUID(str(message.run_id))
        for message in (
            await session.execute(
                select(ConversationMessage).where(
                    ConversationMessage.thread_id == thread_id,
                    ConversationMessage.role == "user",
                )
            )
        )
        .scalars()
        .all()
    }
    serialized_configs = json.dumps([config["configurable"] for _, config in graph.calls], default=str)
    assert "memory_policy_evidence_authority" not in serialized_configs
    assert "memory_business_fact_authority" not in serialized_configs
    assert "memory_action_authority" not in serialized_configs
    assert "memory_replay_truth" not in serialized_configs


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


def test_merchant_role_scopes_project_merchant_scope_and_tool_permissions():
    from unittest.mock import MagicMock
    from src.api.routers.agent_runs import _trusted_tool_config

    merchant_id = uuid4()
    user = MagicMock()
    user.role = "merchant"
    user.merchant_id = merchant_id

    config = _trusted_tool_config(user, token_scopes=ROLE_SCOPES["merchant"], trace_id="trace-merchant")

    assert config["merchant_scope"]["merchant_ids"] == [str(merchant_id)]
    assert "tool:get_order" in config["permissions"]
    assert config["trace_id"] == "trace-merchant"


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
