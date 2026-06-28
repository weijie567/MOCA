from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.auth.jwt import create_access_token, hash_password
from src.db.models import ActionDraft, AgentStep, ApprovalRequest, ApprovalStep, User
from src.repositories.trace_repo import TraceRepository


@pytest.mark.asyncio
async def test_get_run_trace_returns_full_timeline_with_agent_steps_approvals_and_action_drafts(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    support = seeded_session["users"]["cs_zhang"]
    run_id = await _create_trace_run(session, tenant_id=support.tenant_id, user_id=support.id)
    await _add_full_trace_events(session, run_id=run_id, tenant_id=support.tenant_id, user_id=support.id)

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/trace",
        headers=await _support_headers(client),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["run_id"] == str(run_id)
    assert [item["type"] for item in payload["data"]["timeline"]] == [
        "agent_step",
        "approval_request",
        "approval_decision",
        "agent_step",
        "action_draft",
    ]
    assert payload["data"]["steps"][0] == {
        "node": "receive_request",
        "implementation_node": "receive_request",
        "target_node": "request_entry",
        "status": "completed",
        "latency_ms": 12,
        "tool_name": None,
    }
    assert payload["data"]["approvals"][0]["risk_rule_ref"] == "HR-01"
    assert payload["data"]["action_drafts"][0]["action_type"] == "issue_coupon"
    assert payload["data"]["action_drafts"][0]["draft_outcome"]["status"] == "not_executed_demo"
    assert payload["data"]["action_drafts"][0]["draft_outcome"]["external_side_effect"] is False
    assert "payload" not in payload["data"]["action_drafts"][0]
    action_draft_item = next(item for item in payload["data"]["timeline"] if item["type"] == "action_draft")
    first_step_item = payload["data"]["timeline"][0]
    assert first_step_item["detail"]["node_name"] == "receive_request"
    assert first_step_item["detail"]["target_node"] == "request_entry"
    assert action_draft_item["detail"]["draft_outcome"]["status"] == "not_executed_demo"
    assert action_draft_item["detail"]["draft_outcome"]["external_side_effect"] is False
    assert "payload" not in action_draft_item["detail"]
    assert "input_query" not in payload["data"]
    assert "final_response" not in payload["data"]
    assert "secret" not in str(payload["data"])


@pytest.mark.asyncio
async def test_get_run_trace_timeline_is_sorted_by_time(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    support = seeded_session["users"]["cs_zhang"]
    run_id = await _create_trace_run(session, tenant_id=support.tenant_id, user_id=support.id)
    await _add_full_trace_events(session, run_id=run_id, tenant_id=support.tenant_id, user_id=support.id)

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/trace",
        headers=await _support_headers(client),
    )
    times = [item["time"] for item in response.json()["data"]["timeline"]]

    assert response.status_code == 200
    assert times == sorted(times)


@pytest.mark.asyncio
async def test_get_run_trace_non_owner_non_supervisor_gets_403(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    admin = seeded_session["users"]["admin_user"]
    run_id = await _create_trace_run(session, tenant_id=admin.tenant_id, user_id=admin.id)

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/trace",
        headers=await _support_headers(client),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_get_run_trace_supervisor_approval_manager_get_403(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    owner = seeded_session["users"]["cs_zhang"]
    run_id = await _create_trace_run(session, tenant_id=owner.tenant_id, user_id=owner.id)
    supervisor = await _create_same_tenant_role_user(session, seeded_session, "supervisor")
    approval_manager = await _create_same_tenant_role_user(session, seeded_session, "approval_manager")
    await session.commit()

    for viewer in (supervisor, approval_manager):
        response = await client.get(
            f"/api/v1/agent-runs/{run_id}/trace",
            headers=_auth_header(viewer, ["agent:chat"]),
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_get_run_trace_admin_can_view_any_run_in_same_tenant(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    support = seeded_session["users"]["cs_zhang"]
    run_id = await _create_trace_run(session, tenant_id=support.tenant_id, user_id=support.id)

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/trace",
        headers=await _admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["data"]["run_id"] == str(run_id)


@pytest.mark.asyncio
async def test_get_run_trace_cross_tenant_returns_404(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    support = seeded_session["users"]["cs_zhang"]
    other_support = seeded_session["users"]["other_support"]
    run_id = await _create_trace_run(session, tenant_id=support.tenant_id, user_id=support.id)

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/trace",
        headers=_auth_header(other_support, ["agent:chat"]),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_build_timeline_merges_all_event_types_correctly():
    now = datetime.now(UTC)
    approval_id = uuid4()
    draft_outcome = _draft_outcome(draft_id=uuid4(), run_id=uuid4(), tenant_id=uuid4())
    repo = TraceRepository(SimpleNamespace())

    timeline = repo.build_timeline(
        steps=[
            SimpleNamespace(
                started_at=now + timedelta(seconds=1),
                node_name="investigate",
                status="completed",
                tool_name="search_policy",
                latency_ms=22,
                provider_latency_ms=18,
            )
        ],
        approvals=[
            SimpleNamespace(
                id=approval_id,
                created_at=now,
                risk_rule_ref="HR-01",
                status="pending",
                risk_level="high",
                proposed_action={"action_type": "issue_coupon"},
            )
        ],
        approval_steps=[
            SimpleNamespace(
                created_at=now + timedelta(seconds=2),
                event_type="approved",
                actor_id=uuid4(),
                metadata_json={"reason": "valid"},
            )
        ],
        drafts=[
            SimpleNamespace(
                id=uuid4(),
                created_at=now + timedelta(seconds=3),
                action_type="issue_coupon",
                status="draft_created",
                idempotency_key="idem-1",
                draft_outcome=draft_outcome,
                payload={"secret": "do not expose"},
            )
        ],
    )

    assert [item["type"] for item in timeline] == [
        "approval_request",
        "agent_step",
        "approval_decision",
        "action_draft",
    ]
    assert all({"type", "time", "title", "status", "detail"} <= set(item) for item in timeline)
    assert timeline[1]["detail"]["tool_name"] == "search_policy"
    assert timeline[1]["detail"]["node_name"] == "investigate"
    assert timeline[1]["detail"]["target_node"] == "business_investigation"
    assert timeline[3]["detail"]["draft_outcome"] == draft_outcome
    assert "payload" not in timeline[3]["detail"]


def test_trace_action_draft_projection_excludes_raw_payload_even_when_present():
    idempotency_key = "tenant:run:approval_revision_1:issue_coupon:RF-SECRET:sha256-" + "a" * 64
    draft = SimpleNamespace(
        id=uuid4(),
        created_at=datetime.now(UTC),
        action_type="issue_coupon",
        status="draft_created",
        idempotency_key=idempotency_key,
        draft_outcome=_draft_outcome(draft_id=uuid4(), run_id=uuid4(), tenant_id=uuid4()),
        payload={
            "target_id": "RF-SECRET",
            "raw_payload": {"customer_phone": "13900000000"},
            "secret": "do not expose",
        },
    )
    repo = TraceRepository(SimpleNamespace())

    timeline = repo.build_timeline(steps=[], approvals=[], approval_steps=[], drafts=[draft])

    assert "idempotency_key" not in timeline[0]["detail"]
    assert idempotency_key not in str(timeline[0])
    assert "payload" not in timeline[0]["detail"]
    assert "raw_payload" not in str(timeline[0])
    assert "RF-SECRET" not in str(timeline[0])
    assert "13900000000" not in str(timeline[0])
    assert "do not expose" not in str(timeline[0])


def test_trace_action_draft_projection_allowlists_draft_outcome_keys():
    draft_id = uuid4()
    run_id = uuid4()
    tenant_id = uuid4()
    draft = SimpleNamespace(
        id=draft_id,
        created_at=datetime.now(UTC),
        action_type="issue_coupon",
        status="draft_created",
        idempotency_key="idem",
        draft_outcome={
            **_draft_outcome(draft_id=draft_id, run_id=run_id, tenant_id=tenant_id),
            "raw_payload": {"target_id": "RF-SECRET"},
            "secret": "do not expose",
            "customer_phone": "13900000000",
        },
        payload={"target_id": "RF-SECRET"},
    )
    repo = TraceRepository(SimpleNamespace())

    timeline = repo.build_timeline(steps=[], approvals=[], approval_steps=[], drafts=[draft])
    outcome = timeline[0]["detail"]["draft_outcome"]

    assert outcome["status"] == "not_executed_demo"
    assert outcome["external_side_effect"] is False
    assert set(outcome) == {
        "schema_version",
        "status",
        "external_side_effect",
        "tenant_id",
        "run_id",
        "draft_id",
        "created_at",
    }
    assert "raw_payload" not in str(timeline[0])
    assert "RF-SECRET" not in str(timeline[0])
    assert "13900000000" not in str(timeline[0])
    assert "do not expose" not in str(timeline[0])


def test_trace_action_draft_projection_marks_invalid_draft_outcome():
    draft = SimpleNamespace(
        id=uuid4(),
        created_at=datetime.now(UTC),
        action_type="issue_coupon",
        status="draft_created",
        idempotency_key="idem",
        draft_outcome={
            "schema_version": "draft_outcome.v1",
            "status": "executed",
            "external_side_effect": True,
            "raw_payload": {"target_id": "RF-SECRET"},
        },
        payload={"target_id": "RF-SECRET"},
    )
    repo = TraceRepository(SimpleNamespace())

    timeline = repo.build_timeline(steps=[], approvals=[], approval_steps=[], drafts=[draft])
    outcome = timeline[0]["detail"]["draft_outcome"]

    assert outcome == {"status": "invalid_draft_outcome", "external_side_effect": False}
    assert outcome["status"] != "not_executed_demo"


@pytest.mark.asyncio
async def test_get_run_trace_empty_run_returns_only_agent_steps(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
):
    support = seeded_session["users"]["cs_zhang"]
    run_id = await _create_trace_run(session, tenant_id=support.tenant_id, user_id=support.id)
    now = datetime.now(UTC)
    session.add(
        AgentStep(
            run_id=run_id,
            node_name="final_response",
            step_index=0,
            status="completed",
            started_at=now,
            completed_at=now + timedelta(milliseconds=7),
            latency_ms=7,
        )
    )
    await session.commit()

    response = await client.get(
        f"/api/v1/agent-runs/{run_id}/trace",
        headers=await _support_headers(client),
    )
    payload = response.json()["data"]

    assert response.status_code == 200
    assert payload["approvals"] == []
    assert payload["action_drafts"] == []
    assert [item["type"] for item in payload["timeline"]] == ["agent_step"]


async def _create_trace_run(session: AsyncSession, *, tenant_id: UUID, user_id: UUID) -> UUID:
    run_id = uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=f"trace-api-{run_id}",
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        input_query="secret raw user query",
        final_status="completed",
        final_response="secret model output",
        started_at=now,
        completed_at=now + timedelta(seconds=5),
        total_latency_ms=5000,
    )
    await session.commit()
    return run_id


async def _add_full_trace_events(session: AsyncSession, *, run_id: UUID, tenant_id: UUID, user_id: UUID) -> None:
    now = datetime.now(UTC)
    approval_id = uuid4()
    draft_id = uuid4()
    approval = ApprovalRequest(
        id=approval_id,
        run_id=run_id,
        tenant_id=tenant_id,
        status="approved",
        requested_by=user_id,
        proposed_action={
            "action_type": "issue_coupon",
            "target_id": "RF-TEST-001",
            "amount": "600",
            "currency": "CNY",
            "reasoning_summary": "secret reasoning",
        },
        risk_level="high",
        risk_rule_ref="HR-01",
        risk_reason="Compensation exceeds threshold",
        decision="approve",
        decided_by=user_id,
        decided_at=now + timedelta(seconds=2),
        expires_at=now + timedelta(hours=1),
        thread_id="trace-thread",
        created_at=now + timedelta(seconds=1),
    )
    session.add_all(
        [
            AgentStep(
                run_id=run_id,
                node_name="receive_request",
                step_index=0,
                status="completed",
                started_at=now,
                completed_at=now + timedelta(milliseconds=12),
                latency_ms=12,
            ),
            AgentStep(
                run_id=run_id,
                node_name="execute_action",
                step_index=1,
                status="completed",
                tool_name="create_coupon_grant_draft",
                started_at=now + timedelta(seconds=3),
                completed_at=now + timedelta(seconds=3, milliseconds=31),
                latency_ms=31,
            ),
            approval,
        ]
    )
    await session.flush()
    session.add_all(
        [
            ApprovalStep(
                approval_request_id=approval_id,
                event_type="approved",
                actor_id=user_id,
                metadata_json={"reason": "valid"},
                created_at=now + timedelta(seconds=2),
            ),
            ActionDraft(
                id=draft_id,
                run_id=run_id,
                approval_request_id=approval_id,
                tenant_id=tenant_id,
                idempotency_key=f"{run_id}_{approval_id}_issue_coupon_RF-TEST-001",
                action_type="issue_coupon",
                status="draft_created",
                payload={"secret": "do not expose"},
                draft_outcome=_draft_outcome(draft_id=draft_id, run_id=run_id, tenant_id=tenant_id),
                created_by_agent_run=run_id,
                created_at=now + timedelta(seconds=4),
            ),
        ]
    )
    await session.commit()


def _draft_outcome(*, draft_id: UUID, run_id: UUID, tenant_id: UUID) -> dict[str, str | bool]:
    return {
        "schema_version": "draft_outcome.v1",
        "status": "not_executed_demo",
        "tenant_id": str(tenant_id),
        "run_id": str(run_id),
        "draft_id": str(draft_id),
        "external_side_effect": False,
        "created_at": datetime.now(UTC).isoformat(),
    }


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
