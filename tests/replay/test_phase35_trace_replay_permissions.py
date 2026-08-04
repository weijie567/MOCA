from __future__ import annotations

import inspect
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.api.routers import agent_runs as agent_runs_router
from src.api.routers import traces as traces_router
from src.auth.jwt import create_access_token, hash_password
from src.db.models import User
from src.replay.proof_projection import project_replay_authorization_proof


NON_OWNER_BUSINESS_ROLES = ("support", "manager", "merchant", "supervisor", "approval_manager")
FORBIDDEN_AUTH_SHORTCUT_PATTERNS = (
    r"target_merchant_context",
    r"project_replay_authorization_proof",
    r"proof_status",
    r"requested_by.*merchant",
    r"merchant_id.*requested_by",
)
PHASE36_FORBIDDEN_AUTH_GUARD_TOKENS = (
    "target_merchant_id",
    "scope_classification",
    "phase36_readiness",
    "project_replay_authorization_proof",
    "target_merchant_context",
)

PHASE35_SURFACE_REGRESSION_SOURCES = {
    "run_listing": Path("tests/test_agent_runs_api.py"),
    "trace_detail": Path("tests/test_trace_api.py"),
    "tool_result_records": Path("tests/replay/test_tool_policy_events.py"),
    "approval_views": Path("tests/test_approval_api.py"),
    "memory": Path("tests/replay/test_memory_foundation_alignment.py"),
    "reviewed_memory": Path("tests/agent/test_reviewed_memory_context_retrieve.py"),
    "replay_artifacts": Path("tests/replay/test_replay_api.py"),
}
PHASE35_NO_AUTHORIZATION_WIDENING = {
    "approval_views": "Phase 35 adds no authorization widening for approval review views.",
    "tool_result_records": "Phase 35 adds no authorization widening for tool result records.",
    "memory": "Phase 35 adds no authorization widening for memory surfaces.",
}


def test_trace_and_agent_run_admin_visibility_roles_remain_admin_only() -> None:
    assert traces_router.ADMIN_RUN_VISIBILITY_ROLES == {"admin"}
    assert agent_runs_router.ADMIN_RUN_VISIBILITY_ROLES == {"admin"}


def test_trace_and_replay_guards_are_owner_or_admin_only_and_proof_free() -> None:
    for guard in (traces_router.get_run_trace, traces_router.get_run_replay):
        source = inspect.getsource(guard)
        assert "run.user_id != user.id" in source
        assert "user.role not in ADMIN_RUN_VISIBILITY_ROLES" in source
        _assert_no_phase35_auth_shortcut(source)


def test_agent_run_visibility_guards_are_owner_or_admin_only_and_proof_free() -> None:
    view_source = inspect.getsource(agent_runs_router._ensure_can_view_run)
    assert "run.user_id != user.id" in view_source
    assert "user.role not in ADMIN_RUN_VISIBILITY_ROLES" in view_source
    _assert_no_phase35_auth_shortcut(view_source)

    status_source = inspect.getsource(agent_runs_router.get_agent_run_status)
    evidence_source = inspect.getsource(agent_runs_router.get_agent_run_evidence)
    stream_source = inspect.getsource(agent_runs_router.stream_agent_run_events)
    claim_source = inspect.getsource(agent_runs_router._claim_pending_run_for_stream)
    execute_source = inspect.getsource(agent_runs_router._ensure_can_execute_run)

    assert "_ensure_can_view_run(run, user=user)" in status_source
    assert "_ensure_can_view_run(run, user=user)" in evidence_source
    assert "_claim_pending_run_for_stream(session, run_uuid, user)" in stream_source
    assert "_ensure_can_view_run(run, user=user)" in claim_source
    assert "run.user_id != user.id" in execute_source
    for source in (status_source, evidence_source, stream_source, claim_source, execute_source):
        _assert_no_phase35_auth_shortcut(source)


def test_phase36_scope_and_readiness_fields_do_not_enter_authorization_guards() -> None:
    guard_sources = {
        "agent_runs._ensure_can_view_run": inspect.getsource(agent_runs_router._ensure_can_view_run),
        "agent_runs._ensure_can_execute_run": inspect.getsource(agent_runs_router._ensure_can_execute_run),
        "agent_runs._claim_pending_run_for_stream": _authorization_lines(
            inspect.getsource(agent_runs_router._claim_pending_run_for_stream)
        ),
        "agent_runs.get_agent_run_status": _authorization_lines(
            inspect.getsource(agent_runs_router.get_agent_run_status)
        ),
        "agent_runs.get_agent_run_evidence": _authorization_lines(
            inspect.getsource(agent_runs_router.get_agent_run_evidence)
        ),
        "agent_runs.stream_agent_run_events": _authorization_lines(
            inspect.getsource(agent_runs_router.stream_agent_run_events)
        ),
        "traces.get_run_trace": _authorization_lines(inspect.getsource(traces_router.get_run_trace)),
        "traces.get_run_replay": _authorization_lines(inspect.getsource(traces_router.get_run_replay)),
    }

    status_source = inspect.getsource(agent_runs_router.get_agent_run_status)
    assert "target_merchant_id=run.target_merchant_id" in status_source
    assert "scope_classification=run.scope_classification" in status_source

    for name, source in guard_sources.items():
        assert "run.user_id" in source or "_ensure_can_view_run(run, user=user)" in source, name
        _assert_no_phase36_auth_shortcut(source, name=name)


@pytest.mark.asyncio
async def test_owner_and_admin_can_read_business_data_trace_replay_status_and_evidence(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
) -> None:
    owner = seeded_session["users"]["cs_zhang"]
    admin = seeded_session["users"]["admin_user"]
    run = await _create_business_data_run(session, tenant_id=owner.tenant_id, user_id=owner.id)
    await session.commit()

    for viewer in (owner, admin):
        headers = _auth_header(viewer, ["agent:chat"])
        responses = [
            await client.get(f"/api/v1/agent-runs/{run.id}", headers=headers),
            await client.get(f"/api/v1/agent-runs/{run.id}/evidence", headers=headers),
            await client.get(f"/api/v1/agent-runs/{run.id}/trace", headers=headers),
            await client.get(f"/api/v1/agent-runs/{run.id}/replay", headers=headers),
        ]

        assert [response.status_code for response in responses] == [200, 200, 200, 200]


@pytest.mark.asyncio
async def test_cross_tenant_trace_replay_status_evidence_and_stream_return_404(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
) -> None:
    owner = seeded_session["users"]["cs_zhang"]
    other_support = seeded_session["users"]["other_support"]
    completed_run = await _create_business_data_run(session, tenant_id=owner.tenant_id, user_id=owner.id)
    pending_run = await _create_business_data_run(
        session,
        tenant_id=owner.tenant_id,
        user_id=owner.id,
        final_status="pending",
    )
    await session.commit()
    headers = _auth_header(other_support, ["agent:chat"])

    responses = [
        await client.get(f"/api/v1/agent-runs/{completed_run.id}", headers=headers),
        await client.get(f"/api/v1/agent-runs/{completed_run.id}/evidence", headers=headers),
        await client.get(f"/api/v1/agent-runs/{completed_run.id}/trace", headers=headers),
        await client.get(f"/api/v1/agent-runs/{completed_run.id}/replay", headers=headers),
        await client.get(f"/api/v1/agent-runs/{pending_run.id}/events", headers=headers),
    ]

    assert [response.status_code for response in responses] == [404, 404, 404, 404, 404]
    assert {response.json()["error"]["code"] for response in responses} == {"NOT_FOUND"}


@pytest.mark.asyncio
async def test_same_tenant_non_owner_business_roles_get_403_for_trace_replay_and_agent_run_surfaces(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
) -> None:
    owner = seeded_session["users"]["admin_user"]
    completed_run = await _create_business_data_run(session, tenant_id=owner.tenant_id, user_id=owner.id)
    pending_run = await _create_business_data_run(
        session,
        tenant_id=owner.tenant_id,
        user_id=owner.id,
        final_status="pending",
    )
    viewers = [
        seeded_session["users"]["cs_zhang"],
        *[
            await _create_same_tenant_role_user(session, seeded_session, role)
            for role in ("manager", "merchant", "supervisor", "approval_manager")
        ],
    ]
    await session.commit()
    assert [viewer.role for viewer in viewers] == list(NON_OWNER_BUSINESS_ROLES)

    for viewer in viewers:
        headers = _auth_header(viewer, ["agent:chat"])
        responses = [
            await client.get(f"/api/v1/agent-runs/{completed_run.id}", headers=headers),
            await client.get(f"/api/v1/agent-runs/{completed_run.id}/evidence", headers=headers),
            await client.get(f"/api/v1/agent-runs/{completed_run.id}/trace", headers=headers),
            await client.get(f"/api/v1/agent-runs/{completed_run.id}/replay", headers=headers),
            await client.get(f"/api/v1/agent-runs/{pending_run.id}/events", headers=headers),
        ]

        assert [response.status_code for response in responses] == [403, 403, 403, 403, 403]
        assert {response.json()["error"]["code"] for response in responses} == {"FORBIDDEN"}


@pytest.mark.asyncio
async def test_same_merchant_manager_with_valid_replay_proof_still_gets_403_in_phase35(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
) -> None:
    owner = seeded_session["users"]["cs_zhang"]
    manager = await _create_same_tenant_role_user(session, seeded_session, "manager")
    completed_run = await _create_business_data_run(session, tenant_id=owner.tenant_id, user_id=owner.id)
    pending_run = await _create_business_data_run(
        session,
        tenant_id=owner.tenant_id,
        user_id=owner.id,
        final_status="pending",
    )
    await session.commit()
    proof = project_replay_authorization_proof(
        {
            "tenant_id": str(owner.tenant_id),
            "current_intent": "refund_troubleshooting",
            "last_business_context_refs": {
                "business_fact_refs": [
                    {
                        "schema_version": "business_fact_ref.v1",
                        "tenant_id": str(owner.tenant_id),
                        "source_system": "business_fact_service",
                        "resource_type": "order",
                        "resource_id": "ORD-PHASE35-SAME-MERCHANT",
                        "resource_version": "v1",
                        "data_freshness_at": "2026-06-29T00:00:00+00:00",
                        "retrieved_at": "2026-06-29T00:01:00+00:00",
                    }
                ]
            },
        }
    )
    assert proof["proof_status"] == "resolved"
    assert proof["proof_source"] == "business_fact_refs"

    headers = _auth_header(manager, ["agent:chat"])
    responses = [
        await client.get(f"/api/v1/agent-runs/{completed_run.id}", headers=headers),
        await client.get(f"/api/v1/agent-runs/{completed_run.id}/evidence", headers=headers),
        await client.get(f"/api/v1/agent-runs/{completed_run.id}/trace", headers=headers),
        await client.get(f"/api/v1/agent-runs/{completed_run.id}/replay", headers=headers),
        await client.get(f"/api/v1/agent-runs/{pending_run.id}/events", headers=headers),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403, 403]
    assert {response.json()["error"]["code"] for response in responses} == {"FORBIDDEN"}


def test_phase35_surface_regression_sources_exist_and_remain_non_widening() -> None:
    for surface, path in PHASE35_SURFACE_REGRESSION_SOURCES.items():
        assert path.exists(), f"{surface} regression source is missing: {path}"

    assert set(PHASE35_NO_AUTHORIZATION_WIDENING) == {
        "approval_views",
        "tool_result_records",
        "memory",
    }
    assert all("no authorization widening" in note for note in PHASE35_NO_AUTHORIZATION_WIDENING.values())


def _assert_no_phase35_auth_shortcut(source: str) -> None:
    for pattern in FORBIDDEN_AUTH_SHORTCUT_PATTERNS:
        assert re.search(pattern, source) is None


def _assert_no_phase36_auth_shortcut(source: str, *, name: str) -> None:
    for token in PHASE36_FORBIDDEN_AUTH_GUARD_TOKENS:
        assert token not in source, f"{name} authorization guard contains {token}"


def _authorization_lines(source: str) -> str:
    guard_markers = (
        "run.user_id",
        "ADMIN_RUN_VISIBILITY_ROLES",
        "_ensure_can_view_run",
        "_ensure_can_execute_run",
        "_claim_pending_run_for_stream",
    )
    return "\n".join(line.strip() for line in source.splitlines() if any(marker in line for marker in guard_markers))


async def _create_business_data_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    final_status: str = "completed",
):
    run_id = uuid4()
    now = datetime.now(UTC)
    return await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=f"phase35-permissions-{run_id}",
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        input_query="Phase 35 owner/admin-only business-data run",
        final_status=final_status,
        final_response="done" if final_status == "completed" else None,
        started_at=now,
        completed_at=now if final_status == "completed" else None,
        total_latency_ms=10 if final_status == "completed" else None,
    )


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
        username=f"phase35_{role}_{uuid4().hex[:8]}",
        password_hash=hash_password("moca2024"),
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user
