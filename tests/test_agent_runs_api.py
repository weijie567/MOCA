from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.api.main import app
from src.api.routers.agent_runs import _event_generator
from src.auth.jwt import create_access_token
from src.db.models import AgentRun, User


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
