from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.api.routers import traces as traces_router
from src.auth.jwt import create_access_token, hash_password
from src.db.models import ActionDraft, AgentRun, AgentStep, AgentTraceEvent, User


@pytest.mark.asyncio
async def test_get_run_replay_owner_success_reads_event_store_rows_first(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    support = seeded_session["users"]["cs_zhang"]
    run_id = await _create_replay_run(session, tenant_id=support.tenant_id, user_id=support.id)
    await _add_replay_rows_out_of_order(session, run_id=run_id, tenant_id=support.tenant_id)

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/replay",
        headers=await _support_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["schema_version"] == "replay_response.v3"
    assert payload["data"]["run_id"] == str(run_id)
    assert [event["sequence"] for event in payload["data"]["timeline"]] == [1, 2]
    assert {event["schema_version"] for event in payload["data"]["timeline"]} == {"replay_event.v3"}
    assert payload["data"]["timeline"][0]["provenance"]["source_schema_version"] == "minimal_event_envelope.v1"


@pytest.mark.asyncio
async def test_get_run_replay_admin_supervisor_can_view_same_tenant_run(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    support = seeded_session["users"]["cs_zhang"]
    run_id = await _create_replay_run(session, tenant_id=support.tenant_id, user_id=support.id)
    await _add_replay_rows_out_of_order(session, run_id=run_id, tenant_id=support.tenant_id)

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/replay",
        headers=await _admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["data"]["schema_version"] == "replay_response.v3"


@pytest.mark.asyncio
async def test_get_run_replay_cross_tenant_returns_404(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    support = seeded_session["users"]["cs_zhang"]
    other_support = seeded_session["users"]["other_support"]
    run_id = await _create_replay_run(session, tenant_id=support.tenant_id, user_id=support.id)

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/replay",
        headers=_auth_header(other_support, ["agent:chat"]),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_get_run_replay_same_tenant_non_owner_non_supervisor_gets_403(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    admin = seeded_session["users"]["admin_user"]
    run_id = await _create_replay_run(session, tenant_id=admin.tenant_id, user_id=admin.id)

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/replay",
        headers=await _support_headers(client),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_get_run_replay_supervisor_approval_manager_get_403(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    owner = seeded_session["users"]["cs_zhang"]
    run_id = await _create_replay_run(session, tenant_id=owner.tenant_id, user_id=owner.id)
    await _add_replay_rows_out_of_order(session, run_id=run_id, tenant_id=owner.tenant_id)
    supervisor = await _create_same_tenant_role_user(session, seeded_session, "supervisor")
    approval_manager = await _create_same_tenant_role_user(session, seeded_session, "approval_manager")
    await session.commit()

    for viewer in (supervisor, approval_manager):
        response = await client.get(
            f"/api/v1/agent-runs/{run_id}/replay",
            headers=_auth_header(viewer, ["agent:chat"]),
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"


def test_replay_visibility_guard_remains_admin_only_and_ignores_target_merchant_context():
    assert traces_router.ADMIN_RUN_VISIBILITY_ROLES == {"admin"}
    assert "target_merchant_context" not in inspect.getsource(traces_router.get_run_replay)


@pytest.mark.asyncio
async def test_get_run_replay_business_and_ghost_non_owner_roles_get_403(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    owner = seeded_session["users"]["admin_user"]
    run_id = await _create_replay_run(session, tenant_id=owner.tenant_id, user_id=owner.id)
    support = seeded_session["users"]["cs_zhang"]
    manager = await _create_same_tenant_role_user(session, seeded_session, "manager")
    merchant = await _create_same_tenant_role_user(session, seeded_session, "merchant")
    supervisor = await _create_same_tenant_role_user(session, seeded_session, "supervisor")
    approval_manager = await _create_same_tenant_role_user(session, seeded_session, "approval_manager")
    await session.commit()

    for viewer in (support, manager, merchant, supervisor, approval_manager):
        response = await client.get(
            f"/api/v1/agent-runs/{run_id}/replay",
            headers=_auth_header(viewer, ["agent:chat"]),
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_get_run_replay_invalid_uuid_returns_404(client: AsyncClient):
    response = await client.get(
        "/api/v1/agent-runs/not-a-uuid/replay",
        headers=await _support_headers(client),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_trace_remains_legacy_rollback_fallback(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    support = seeded_session["users"]["cs_zhang"]
    run_id = await _create_trace_fallback_run(session, tenant_id=support.tenant_id, user_id=support.id)

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/trace",
        headers=await _support_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["data"]["timeline"][0]["type"] == "agent_step"
    assert payload["data"]["timeline"][0]["detail"]["node_name"] == "receive_request"


@pytest.mark.asyncio
async def test_get_run_replay_action_draft_omits_raw_action_payload(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    support = seeded_session["users"]["cs_zhang"]
    run_id = await _create_replay_run(session, tenant_id=support.tenant_id, user_id=support.id)
    await _add_action_draft_replay_row(session, run_id=run_id, tenant_id=support.tenant_id)

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/replay",
        headers=await _support_headers(client),
    )
    payload = response.json()
    response_text = response.text

    assert response.status_code == 200
    event = payload["data"]["timeline"][0]
    assert event["event_type"] == "action_draft_created"
    assert event["redacted_payload"]["execution_mode"] == "demo"
    assert event["redacted_payload"]["external_side_effect"] is False
    assert event["redacted_payload"]["draft_outcome"]["status"] == "not_executed_demo"
    assert "raw_payload" not in response_text
    assert "secret-coupon-code" not in response_text
    assert "proposed_action" not in response_text
    assert "external_dispatched" not in response_text
    assert "action_execution_started" not in response_text
    assert "action_execution_completed" not in response_text
    assert "action_execution_failed" not in response_text


async def _create_replay_run(session: AsyncSession, *, tenant_id: UUID, user_id: UUID) -> UUID:
    run_id = uuid4()
    now = datetime.now(UTC)
    session.add(
        AgentRun(
            id=run_id,
            thread_id=f"replay-api-{run_id}",
            tenant_id=tenant_id,
            user_id=user_id,
            input_query="redacted replay API fixture",
            final_status="completed",
            final_response=None,
            started_at=now,
            completed_at=now + timedelta(seconds=1),
            total_latency_ms=1000,
        )
    )
    await session.flush()
    return run_id


async def _add_replay_rows_out_of_order(session: AsyncSession, *, run_id: UUID, tenant_id: UUID) -> None:
    now = datetime.now(UTC)
    session.add_all(
        [
            AgentTraceEvent(
                event_id=uuid4(),
                run_id=run_id,
                sequence=2,
                tenant_id=tenant_id,
                thread_id=f"replay-api-{run_id}",
                event_type="run_status_changed",
                schema_version="replay_event.v3",
                occurred_at=now + timedelta(seconds=1),
                actor={"type": "system", "id": "run_lifecycle"},
                resource_refs={"run_id": str(run_id)},
                redaction_policy_version="redaction.v1",
                redacted_payload={"from_status": "running", "to_status": "completed"},
            ),
            AgentTraceEvent(
                event_id=uuid4(),
                run_id=run_id,
                sequence=1,
                tenant_id=tenant_id,
                thread_id=f"replay-api-{run_id}",
                event_type="approval_requested",
                schema_version="minimal_event_envelope.v1",
                occurred_at=now,
                actor={"type": "approver", "id": "approval-service"},
                resource_refs={"approval_id": str(uuid4())},
                redaction_policy_version="redaction.v1",
                redacted_payload={"status": "pending"},
            ),
        ]
    )
    await session.flush()


async def _add_action_draft_replay_row(session: AsyncSession, *, run_id: UUID, tenant_id: UUID) -> None:
    now = datetime.now(UTC)
    draft_id = uuid4()
    draft_outcome = {
        "schema_version": "draft_outcome.v1",
        "status": "not_executed_demo",
        "external_side_effect": False,
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "draft_id": str(draft_id),
        "created_at": now.isoformat(),
    }
    session.add(
        ActionDraft(
            id=draft_id,
            run_id=run_id,
            tenant_id=tenant_id,
            idempotency_key=f"{run_id}:safe-replay-draft",
            action_type="issue_coupon",
            status="draft_created",
            payload={"raw_payload": "secret-coupon-code"},
            draft_outcome=draft_outcome,
            execution_mode="demo",
            created_by_agent_run=run_id,
            created_at=now,
        )
    )
    await session.flush()
    session.add(
        AgentTraceEvent(
            event_id=uuid4(),
            run_id=run_id,
            sequence=1,
            tenant_id=tenant_id,
            thread_id=f"replay-api-{run_id}",
            event_type="action_draft_created",
            schema_version="replay_event.v3",
            occurred_at=now,
            actor={"type": "agent", "id": "moca"},
            resource_refs={
                "draft_id": str(draft_id),
                "target_id": "RF-APPROVAL-1",
                "action_payload_hash": "sha256:" + "1" * 64,
                "safety_snapshot_hash": "sha256:" + "2" * 64,
            },
            draft_id=draft_id,
            redaction_policy_version="redaction.v1",
            redacted_payload={
                "action_type": "issue_coupon",
                "execution_mode": "demo",
                "external_side_effect": False,
                "draft_outcome": draft_outcome,
            },
        )
    )
    await session.flush()


async def _create_trace_fallback_run(session: AsyncSession, *, tenant_id: UUID, user_id: UUID) -> UUID:
    run_id = uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=f"trace-fallback-{run_id}",
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        input_query="secret raw user query",
        final_status="completed",
        final_response="secret model output",
        started_at=now,
        completed_at=now + timedelta(seconds=1),
        total_latency_ms=1000,
    )
    session.add(
        AgentStep(
            run_id=run_id,
            node_name="receive_request",
            step_index=0,
            status="completed",
            started_at=now,
            completed_at=now + timedelta(milliseconds=8),
            latency_ms=8,
        )
    )
    await session.commit()
    return run_id


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": "admin_user", "password": "moca2024"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


async def _support_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"username": "cs_zhang", "password": "moca2024"})
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


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


async def _create_same_tenant_role_user(session: AsyncSession, seeded_session: dict, role: str) -> User:
    user = User(
        id=uuid4(),
        tenant_id=seeded_session["tenant"].id,
        merchant_id=seeded_session["merchant"].id,
        username=f"{role}_{uuid4().hex[:8]}",
        password_hash=hash_password("moca2024"),
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user
