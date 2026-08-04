from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.actions.service import ActionService
from src.agent import routing as routing_module
from src.agent.graph import route_after_risk
from src.agent.nodes import risk_gate as risk_module
from src.agent.nodes.action_draft import action_draft
from src.agent.nodes.final_response import final_response
from src.agent.routing import route_after_recommendation
from src.agent.safety.taxonomy import resolve_action_text
from src.agent.schemas import RiskAssessment
from src.api.main import app
from src.api.routers.agent_runs import _event_generator
from src.approvals.schemas import ApprovalDecisionContextV1
from src.db.models import ActionDraft, AgentRun, AgentTraceEvent
from src.platform.trusted_context import MerchantScopeV1, TrustedContext
from tests.actions.test_auto_action_capabilities import _capability_context, _draft_kwargs
from tests.approvals.test_service_transitions import _create_run
from tests.test_agent_runs_api import DraftTerminalFailureGraph, _auth_header, _event_data, _stream_input
from tests.test_approval_integration import _create_manual_approval, _decision_body
from tests.test_graph_routing import (
    _FakeRiskLLM,
    _business_fact_ref_payload,
    _claim_bundle_payload,
)


ROOT = Path(__file__).resolve().parents[2]
DECISION_CONTEXT_FIXTURE = ROOT / "contracts" / "fixtures" / "approval_decision_context_v1.json"


class _FailingRiskLLM:
    def __init__(self, error_type: type[Exception]) -> None:
        self.error_type = error_type

    def with_structured_output(self, schema: type) -> _FailingRiskLLM:
        del schema
        return self

    async def ainvoke(self, messages: list[dict[str, str]]) -> RiskAssessment:
        del messages
        raise self.error_type("injected provider failure")


def _trusted_config(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    run_id: UUID,
    merchant_id: str,
    thread_id: str,
) -> dict[str, Any]:
    trusted_context = TrustedContext(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        role="support",
        permissions=[],
        merchant_scope=MerchantScopeV1(merchant_ids=[merchant_id]),
        thread_id=thread_id,
        run_id=str(run_id),
        trace_id=f"trace-{thread_id}",
    )
    return {
        "configurable": {
            "session": session,
            "trusted_context": trusted_context.model_dump(mode="json"),
        }
    }


def _verified_action_state(
    *,
    tenant_id: UUID,
    user_id: UUID,
    run_id: UUID,
    merchant_id: str,
    thread_id: str,
    action_text: str,
    amount: str,
) -> dict[str, Any]:
    resolution = resolve_action_text(action_text)
    fact_ref = _business_fact_ref_payload(str(tenant_id), resource_id="RF-TEST-001")
    claim_bundle = _claim_bundle_payload(str(tenant_id))
    claim_bundle["claim_results"][0]["business_fact_refs"] = [fact_ref]
    return {
        "user_query": action_text,
        "thread_id": thread_id,
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "role": "support",
        "current_run_id": str(run_id),
        "current_intent": "compensation_suggestion",
        "canonical_action": asdict(resolution),
        "recommendation_draft": {
            "recommended_action": action_text,
            "canonical_action": asdict(resolution),
            "reasoning_summary": f"Create a {amount} CNY service-recovery coupon draft.",
            "confidence": 0.9,
            "risk_level": "low",
            "missing_info": [],
        },
        "business_context": {
            "refund_case": {
                "id": "RF-TEST-001",
                "merchant_id": merchant_id,
                "requested_amount": amount,
            },
            "business_fact_refs": [fact_ref],
        },
        "claim_verification_bundle": claim_bundle,
        "trace_steps": [],
    }


async def _draft_count(session: AsyncSession, run_id: UUID | None = None) -> int:
    statement = select(func.count()).select_from(ActionDraft)
    if run_id is not None:
        statement = statement.where(ActionDraft.run_id == run_id)
    return int(await session.scalar(statement) or 0)


def _decision_body_from_context(context: dict[str, Any], decision_type: str = "approve") -> dict[str, Any]:
    return {
        "decision_type": decision_type,
        "expected_request_version": context["request_version"],
        "expected_level_version": context["level_version"],
        "expected_assignment_version": context["assignment_version"],
        "expected_revision": context["revision"],
        "action_payload_hash": context["action_payload_hash"],
        "safety_snapshot_hash": context["safety_snapshot_hash"],
        "reason": "Phase 64.1 safety matrix",
    }


def test_shared_decision_context_fixture_is_backend_valid_and_language_neutral() -> None:
    fixture = json.loads(DECISION_CONTEXT_FIXTURE.read_text(encoding="utf-8"))

    context = ApprovalDecisionContextV1.model_validate(fixture)

    assert context.schema_version == "approval_decision_context.v1"
    assert context.approval_id == UUID(fixture["approval_id"])
    assert context.request_version == fixture["request_version"]
    assert context.action_payload_hash == fixture["action_payload_hash"]
    assert DECISION_CONTEXT_FIXTURE.suffix == ".json"
    assert not list(DECISION_CONTEXT_FIXTURE.parent.glob("approval_decision_context_v1.*.json"))


@pytest.mark.asyncio
@pytest.mark.parametrize("action_text", ["issue coupon", "补偿"])
async def test_canonical_low_action_reaches_one_audited_demo_draft(
    session: AsyncSession,
    seeded_session: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    action_text: str,
) -> None:
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    merchant_id = str(seeded_session["merchant"].id)
    thread_id = f"phase64-1-low-{uuid4()}"
    run_id = await _create_run(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
    )
    state = _verified_action_state(
        tenant_id=tenant_id,
        user_id=user_id,
        run_id=run_id,
        merchant_id=merchant_id,
        thread_id=thread_id,
        action_text=action_text,
        amount="50.00",
    )
    config = _trusted_config(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        run_id=run_id,
        merchant_id=merchant_id,
        thread_id=thread_id,
    )
    monkeypatch.setattr(
        risk_module,
        "_get_llm",
        lambda: _FakeRiskLLM(
            RiskAssessment(
                risk_level="low",
                risk_reason="Low-value compensation is auto allowed.",
                approval_required=False,
                rule_ref="LR-01",
            )
        ),
    )

    risk_update = await risk_module.risk_gate(state, config)
    post_risk = {**state, **risk_update}
    assert post_risk["canonical_action"]["executable_action_type"] == "issue_coupon"
    assert post_risk["claim_verification_bundle"]["overall_status"] == "verified"
    assert post_risk["risk_assessment"]["risk_disposition"] == "allow"
    assert route_after_risk(post_risk) == "action_draft"
    assert post_risk["auto_action_capability"]["capability_ref"].startswith("aac_")

    draft_update = await action_draft(post_risk, config)
    terminal_state = {**post_risk, **draft_update}
    terminal = routing_module.project_action_draft_terminal(terminal_state)

    assert terminal.final_status == "completed"
    assert terminal.route_key == "final_response"
    assert await _draft_count(session, run_id) == 1
    draft = (await session.execute(select(ActionDraft).where(ActionDraft.run_id == run_id))).scalar_one()
    assert draft.draft_outcome["status"] == "not_executed_demo"
    assert draft.draft_outcome["external_side_effect"] is False
    events = (
        (
            await session.execute(
                select(AgentTraceEvent).where(
                    AgentTraceEvent.run_id == run_id,
                    AgentTraceEvent.event_type == "action_draft_created",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].redacted_payload["authorization_source"] == "auto_allow_capability"


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [TimeoutError, ConnectionError, ValueError])
async def test_unproven_medium_action_stays_closed_when_llm_fails(
    session: AsyncSession,
    seeded_session: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
) -> None:
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    merchant_id = str(seeded_session["merchant"].id)
    thread_id = f"phase64-1-provider-failure-{uuid4()}"
    run_id = await _create_run(session, tenant_id=tenant_id, user_id=user_id, thread_id=thread_id)
    state = _verified_action_state(
        tenant_id=tenant_id,
        user_id=user_id,
        run_id=run_id,
        merchant_id=merchant_id,
        thread_id=thread_id,
        action_text="issue_coupon",
        amount="200.00",
    )
    config = _trusted_config(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        run_id=run_id,
        merchant_id=merchant_id,
        thread_id=thread_id,
    )
    monkeypatch.setattr(risk_module, "_get_llm", lambda: _FailingRiskLLM(error_type))

    result = await risk_module.risk_gate(state, config)

    assert result["risk_assessment"]["risk_severity"] == "medium"
    assert result["risk_assessment"]["risk_disposition"] == "manual_review"
    assert result["auto_action_capability"] is None
    assert result["auto_allowed"] is False
    post_risk = {**state, **result}
    assert route_after_risk(post_risk) == "final_response"
    terminal = routing_module.project_run_terminal(post_risk)
    rendered = await final_response(post_risk)
    assert terminal.status == "manual_review"
    assert terminal.reason_code == "risk_manual_review"
    assert rendered["llm_outputs"]["final_response"]["final_status"] == "manual_review"
    assert await _draft_count(session, run_id) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("candidate", "match_kind"),
    [
        ("launch rocket", "unknown"),
        ("issue coupon and full refund", "ambiguous"),
        ({"action_type": "issue_coupon", "extra": True}, "schema_invalid"),
    ],
)
async def test_unknown_ambiguous_and_schema_invalid_actions_never_reach_draft(
    session: AsyncSession,
    candidate: Any,
    match_kind: str,
) -> None:
    resolution = resolve_action_text(candidate)
    state = {
        "canonical_action": asdict(resolution),
        "risk_signals": ["manual_review_required"],
        "recommendation_draft": {
            "recommended_action": str(candidate),
            "reasoning_summary": "unproven action",
            "evidence_refs": [],
        },
        "proposed_action": None,
        "auto_action_capability": None,
    }

    assert resolution.match_kind == match_kind
    assert resolution.executable_action_type is None
    assert resolution.disposition == "manual_review"
    assert route_after_recommendation(state) == "claim_verify"
    terminal = routing_module.project_run_terminal(state)
    rendered = await final_response(state)
    assert terminal.status == "manual_review"
    assert terminal.reason_code == "unresolved_action"
    assert rendered["llm_outputs"]["final_response"]["final_status"] == "manual_review"
    assert await _draft_count(session) == 0


def test_blocked_action_and_risk_keep_distinct_non_success_reasons() -> None:
    blocked_action = routing_module.project_run_terminal(
        {"canonical_action": {"executable_action_type": None, "disposition": "blocked"}}
    )
    blocked_risk = routing_module.project_run_terminal(
        {
            "canonical_action": {"executable_action_type": "issue_coupon", "disposition": "allow"},
            "risk_assessment": {"risk_disposition": "blocked"},
        }
    )

    assert blocked_action.final_status == "manual_review"
    assert blocked_action.reason_code == "canonical_action_blocked"
    assert blocked_risk.final_status == "manual_review"
    assert blocked_risk.reason_code == "risk_blocked"


@pytest.mark.asyncio
async def test_high_action_uses_latest_decision_context_before_one_approved_draft(
    client: AsyncClient,
    session: AsyncSession,
    auth_headers,
    mock_graph,
    agent_test_user,
    approval_test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del approval_test_user
    monkeypatch.setattr(app.state, "agent_graph", mock_graph, raising=False)
    chat = await client.post(
        "/api/v1/agent/chat",
        json={"query": "请给ORD-TEST-001补偿600元", "thread_id": f"phase64-1-high-{uuid4()}"},
        headers=await auth_headers(agent_test_user.username),
    )
    wait_payload = chat.json()["data"]
    approval_id = UUID(wait_payload["approval_id"])
    run_id = UUID(wait_payload["run_id"])

    assert chat.status_code == 200
    assert wait_payload["status"] == "interrupted"
    assert await _draft_count(session, run_id) == 0
    run = await session.get(AgentRun, run_id)
    assert run is not None and run.final_status == "interrupted"

    headers = await auth_headers("admin_user")
    pending = await client.get("/api/v1/approvals", headers=headers)
    detail = await client.get(f"/api/v1/approvals/{approval_id}", headers=headers)
    list_context = next(
        item["decision_context"] for item in pending.json()["data"]["approvals"] if item["id"] == str(approval_id)
    )
    detail_context = detail.json()["data"]["decision_context"]
    assert list_context == detail_context
    ApprovalDecisionContextV1.model_validate(detail_context)

    decided = await client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json=_decision_body_from_context(detail_context),
        headers=headers,
    )
    await session.refresh(run)

    assert decided.status_code == 200
    assert run.final_status == "completed"
    assert await _draft_count(session, run_id) == 1
    draft = (await session.execute(select(ActionDraft).where(ActionDraft.run_id == run_id))).scalar_one()
    assert draft.draft_outcome["status"] == "not_executed_demo"
    assert draft.draft_outcome["external_side_effect"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_status"),
    [
        ("stale_revision", 409),
        ("stale_request_version", 409),
        ("hash_mismatch", 409),
        ("malformed", 422),
        ("unsupported", 422),
        ("cross_tenant", 403),
    ],
)
async def test_denied_stale_malformed_and_unsupported_decisions_cannot_resume_or_draft(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict[str, Any],
    auth_headers,
    case: str,
    expected_status: int,
) -> None:
    bundle = await _create_manual_approval(
        session,
        tenant_id=seeded_session["tenant"].id,
        requested_by=seeded_session["users"]["cs_zhang"].id,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    body = _decision_body(bundle)
    username = "admin_user"
    if case == "stale_revision":
        body["expected_revision"] += 1
    elif case == "stale_request_version":
        body["expected_request_version"] += 1
    elif case == "hash_mismatch":
        body["action_payload_hash"] = "sha256:" + "0" * 64
    elif case == "malformed":
        body.pop("expected_revision")
    elif case == "unsupported":
        body["decision_type"] = "execute"
    elif case == "cross_tenant":
        username = "other_support"

    response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=body,
        headers=await auth_headers(username),
    )
    run = await session.get(AgentRun, bundle.approval.run_id)

    assert response.status_code == expected_status
    assert await _draft_count(session, bundle.approval.run_id) == 0
    assert run is not None and run.final_status != "completed"
    await session.refresh(bundle.approval)
    assert bundle.approval.status == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("override", "value_factory"),
    [
        ("tenant_id", lambda _ctx: str(uuid4())),
        ("user_id", lambda _ctx: str(uuid4())),
        ("run_id", lambda _ctx: str(uuid4())),
        ("merchant_scope", lambda _ctx: {"merchant_ids": ["merchant-out-of-scope"]}),
        ("target_merchant_id", lambda _ctx: "merchant-other"),
        ("action_type", lambda _ctx: "approve_refund"),
    ],
)
async def test_cross_binding_capability_misuse_creates_zero_drafts(
    session: AsyncSession,
    seeded_session: dict[str, Any],
    override: str,
    value_factory,
) -> None:
    context = await _capability_context(session, seeded_session)
    result = await ActionService(session).create_coupon_grant_draft(
        **_draft_kwargs(context, **{override: value_factory(context)})
    )

    assert result["status"] == "error"
    assert await _draft_count(session, context["run_id"]) == 0


@pytest.mark.asyncio
async def test_wrong_handler_expiry_and_replay_never_create_an_unauthorized_new_draft(
    session: AsyncSession,
    seeded_session: dict[str, Any],
) -> None:
    context = await _capability_context(session, seeded_session)
    api = context["api"]
    with pytest.raises(api["verification_error"]):
        async with session.begin_nested():
            await api["service"](session).lock_and_verify_for_draft(
                capability_ref=context["grant"].capability_ref,
                tenant_id=context["tenant_id"],
                actor_id=context["actor_id"],
                run_id=context["run_id"],
                merchant_scope=context["merchant_scope"],
                target_merchant_id=context["target_merchant_id"],
                canonical_action="issue_coupon",
                action_payload_hash=context["action_payload_hash"],
                safety_snapshot_ref=context["snapshot_ref"],
                safety_snapshot_hash=context["snapshot_hash"],
                risk_decision_ref=context["risk_decision_ref"],
                risk_decision=context["risk_decision"],
                handler="production_executor",
            )
    assert await _draft_count(session, context["run_id"]) == 0

    row = await session.scalar(select(api["model"]).where(api["model"].run_id == context["run_id"]))
    assert row is not None
    row.issued_at = datetime.now(UTC) - timedelta(seconds=10)
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.flush()
    expired = await ActionService(session).create_coupon_grant_draft(**_draft_kwargs(context))
    assert expired["status"] == "error"
    assert expired["error"]["error_code"] == "AUTO_ACTION_CAPABILITY_EXPIRED"
    assert await _draft_count(session, context["run_id"]) == 0

    replay_context = await _capability_context(session, seeded_session)
    service = ActionService(session)
    first = await service.create_coupon_grant_draft(**_draft_kwargs(replay_context))
    exact_retry = await service.create_coupon_grant_draft(**_draft_kwargs(replay_context))
    tampered_risk = {**replay_context["risk_decision"], "risk_reason": "tampered replay"}
    replay = await service.create_coupon_grant_draft(**_draft_kwargs(replay_context, risk_decision=tampered_risk))
    assert first["status"] == exact_retry["status"] == "success"
    assert first["data"]["draft_id"] == exact_retry["data"]["draft_id"]
    assert exact_retry["data"]["idempotent_reused"] is True
    assert replay["status"] == "error"
    assert await _draft_count(session, replay_context["run_id"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["store", "audit"])
async def test_store_and_audit_failure_roll_back_draft_capability_and_critical_event(
    session: AsyncSession,
    seeded_session: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    context = await _capability_context(session, seeded_session)
    service = ActionService(session)
    if failure_point == "store":
        original = service.draft_store.create_or_get

        async def fail_after_store(**kwargs: Any):
            await original(**kwargs)
            raise RuntimeError("injected store failure")

        monkeypatch.setattr(service.draft_store, "create_or_get", fail_after_store)
    else:
        original = service._emit_action_draft_created

        async def fail_after_audit(**kwargs: Any):
            await original(**kwargs)
            raise RuntimeError("injected audit failure")

        monkeypatch.setattr(service, "_emit_action_draft_created", fail_after_audit)

    result = await service.create_coupon_grant_draft(**_draft_kwargs(context))
    session.expire_all()

    assert result["status"] == "error"
    assert await _draft_count(session, context["run_id"]) == 0
    event_count = await session.scalar(
        select(func.count())
        .select_from(AgentTraceEvent)
        .where(
            AgentTraceEvent.run_id == context["run_id"],
            AgentTraceEvent.event_type == "action_draft_created",
        )
    )
    assert event_count == 0
    capability = await session.scalar(
        select(context["api"]["model"]).where(context["api"]["model"].run_id == context["run_id"])
    )
    assert capability is not None and capability.status == "issued"


@pytest.mark.asyncio
async def test_tool_failure_has_no_completed_db_api_sse_or_final_projection(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session: dict[str, Any],
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    run_id = await _create_run(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id=f"phase64-1-terminal-failure-{uuid4()}",
    )
    run = await session.get(AgentRun, run_id)
    assert run is not None
    run.final_status = "running"
    run.completed_at = None
    await session.commit()

    events = [
        _event_data(event)
        async for event in _event_generator(
            DraftTerminalFailureGraph(),
            _stream_input(run, user),
            {"configurable": {"thread_id": run.thread_id, "session": session}},
            run=run,
            session=session,
            user=user,
        )
        if "data" in event
    ]
    await session.refresh(run)

    terminal_events = [event for event in events if event["event_type"] in {"final_response", "error"}]
    assert [event["event_type"] for event in terminal_events] == ["error"]
    assert terminal_events[0]["payload"]["error_code"] == "ACTION_DRAFT_TERMINAL_FAILED"
    assert not any(event["status"] == "completed" for event in terminal_events)
    assert "must-not-leak" not in json.dumps(events, ensure_ascii=False)
    assert run.final_status == "error"
    assert await _draft_count(session, run_id) == 0

    poll = await client.get(
        f"/api/v1/agent-runs/{run_id}",
        headers=_auth_header(user, ["agent:chat"]),
    )
    assert poll.status_code == 200
    assert poll.json()["data"]["final_status"] == "error"
    assert poll.json()["data"]["final_response"] == run.final_response
