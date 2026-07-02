"""Phase 29 Wave 0 RED tests for explicit tool policy decision events (APF-07).

Locks the ``tool_policy_visibility_recorded`` and ``tool_policy_runtime_auth_recorded``
event types, their retention classification, and the redaction/resource-ref guards
*before* Plan 29-02 registers them. Expected to fail RED until the event types are
registered in ``src/replay/validators.py`` and the ORM/Alembic constraints are aligned.
"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.replay.decision_events import emit_decision_event
from src.replay.validators import (
    EVENT_RETENTION_CLASSIFICATION,
    REPLAY_EVENT_TYPES,
    validate_event_type,
)
from src.tools.contracts import ToolCallContext


TOOL_POLICY_VISIBILITY_EVENT = "tool_policy_visibility_recorded"
TOOL_POLICY_RUNTIME_AUTH_EVENT = "tool_policy_runtime_auth_recorded"

_FORBIDDEN_PAYLOAD_KEYS = {
    "raw_args",
    "raw_payload",
    "raw_tool_output",
    "input_schema",
    "required_permission",
    "caller_allowlist",
    "arguments",
    "data",
    "secret",
    "pii",
}


async def _create_run(session: AsyncSession, *, thread_id: str = "tool-policy-thread") -> tuple[uuid.UUID, uuid.UUID]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=thread_id,
        tenant_id=str(tenant_id),
        user_id=str(uuid.uuid4()),
        input_query="tool policy decision",
        final_status="running",
        final_response=None,
        started_at=now,
        completed_at=None,
        total_latency_ms=None,
        trace_id="trace-tool-policy",
    )
    return run_id, tenant_id


def _has_forbidden_key(value: object) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in _FORBIDDEN_PAYLOAD_KEYS:
                return str(key)
            nested = _has_forbidden_key(child)
            if nested is not None:
                return nested
    if isinstance(value, list):
        for item in value:
            nested = _has_forbidden_key(item)
            if nested is not None:
                return nested
    return None


def _runtime_event_context() -> ToolCallContext:
    return ToolCallContext(
        tenant_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        role="support",
        permissions=[],
        merchant_scope={"merchant_ids": ["*"]},
        session_id=None,
        thread_id="tool-policy-thread",
        run_id=str(uuid.uuid4()),
        trace_id="trace-tool-policy",
        request_id=str(uuid.uuid4()),
        tool_call_id=str(uuid.uuid4()),
        caller_node="investigate",
        attempt=1,
        max_attempts=1,
        policy_snapshot_ref=None,
    )


def test_tool_policy_event_types_are_registered() -> None:
    # RED until Plan 29-02 adds both literals to REPLAY_EVENT_TYPES.
    assert TOOL_POLICY_VISIBILITY_EVENT in REPLAY_EVENT_TYPES
    assert TOOL_POLICY_RUNTIME_AUTH_EVENT in REPLAY_EVENT_TYPES
    validate_event_type(TOOL_POLICY_VISIBILITY_EVENT)
    validate_event_type(TOOL_POLICY_RUNTIME_AUTH_EVENT)


def test_tool_policy_event_types_have_retention_classification() -> None:
    assert EVENT_RETENTION_CLASSIFICATION[TOOL_POLICY_VISIBILITY_EVENT] == "tool_policy_event"
    assert EVENT_RETENTION_CLASSIFICATION[TOOL_POLICY_RUNTIME_AUTH_EVENT] == "tool_policy_event"


@pytest.mark.asyncio
async def test_tool_policy_visibility_recorded_emits_low_payload_batched_event(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)

    event = await emit_decision_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="tool-policy-thread",
        event_type=TOOL_POLICY_VISIBILITY_EVENT,
        actor={"type": "agent", "id": "moca"},
        resource_refs={"caller": "investigate"},
        redacted_payload={
            "decision_stage": "visibility",
            "tools": [
                {"tool_name": "get_order", "decision": "visible", "reason_codes": ["visible"]},
                {
                    "tool_name": "create_coupon_grant_draft",
                    "decision": "hidden",
                    "reason_codes": ["hidden_by_policy"],
                },
            ],
            "policy_version": "tool_policy.v1",
        },
    )

    assert event["event_type"] == TOOL_POLICY_VISIBILITY_EVENT
    payload = event["redacted_payload"]
    assert _has_forbidden_key(payload) is None
    tool_names = {entry["tool_name"] for entry in payload["tools"]}
    assert "get_order" in tool_names
    assert "create_coupon_grant_draft" in tool_names
    assert "input_schema" not in payload
    assert "required_permission" not in payload
    assert "caller_allowlist" not in payload


@pytest.mark.asyncio
async def test_tool_policy_runtime_auth_recorded_emits_per_invocation_event(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)

    event = await emit_decision_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="tool-policy-thread",
        event_type=TOOL_POLICY_RUNTIME_AUTH_EVENT,
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool_name": "get_order", "tool_call_id": "tc-1", "resource_type": "order"},
        redacted_payload={
            "decision_stage": "runtime_auth",
            "tool_name": "get_order",
            "decision": "denied",
            "reason_codes": ["missing_permission"],
            "policy_version": "tool_policy.v1",
            "data_classification": "internal",
            "runtime_available": True,
        },
    )

    assert event["event_type"] == TOOL_POLICY_RUNTIME_AUTH_EVENT
    payload = event["redacted_payload"]
    assert payload["decision_stage"] == "runtime_auth"
    assert payload["decision"] == "denied"
    assert _has_forbidden_key(payload) is None
    for forbidden in ("raw_args", "raw_payload", "raw_tool_output", "input_schema", "required_permission", "caller_allowlist"):
        assert forbidden not in payload


@pytest.mark.asyncio
async def test_tool_runtime_event_payload_source_omits_raw_descriptor_and_args(monkeypatch) -> None:
    from src.tools.platform import ToolPlatform

    captured: dict[str, object] = {}

    async def fake_emit_decision_event(session: object, **kwargs: object) -> dict[str, str]:
        del session
        captured["redacted_payload"] = kwargs["redacted_payload"]
        return {"event_id": "runtime-auth-event-1"}

    monkeypatch.setattr("src.replay.decision_events.emit_decision_event", fake_emit_decision_event)

    outcome = await ToolPlatform.with_defaults(None).invoke(
        "get_order",
        {"order_no": "ORD-1", "raw_args": {"secret": "RAW-RUNTIME-SENTINEL"}},
        _runtime_event_context(),
        session=object(),
    )

    payload = captured["redacted_payload"]
    assert isinstance(payload, dict)
    assert outcome.policy_event_id == "runtime-auth-event-1"
    assert payload["decision_stage"] == "runtime_auth"
    assert payload["data_classification"] == "internal"
    assert _has_forbidden_key(payload) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("forbidden_key", "forbidden_value"),
    [
        ("raw_args", {"order_no": "ORD-1"}),
        ("raw_payload", {"secret": "sk-xxx"}),
        ("raw_tool_output", "<upstream error text>"),
        ("input_schema", {"type": "object"}),
        ("required_permission", "tool:get_order"),
        ("caller_allowlist", ["investigate"]),
    ],
)
async def test_tool_policy_event_rejects_raw_descriptor_and_arg_payload(
    session: AsyncSession,
    forbidden_key: str,
    forbidden_value: object,
) -> None:
    run_id, tenant_id = await _create_run(session)

    with pytest.raises(Exception):
        await emit_decision_event(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id="tool-policy-thread",
            event_type=TOOL_POLICY_RUNTIME_AUTH_EVENT,
            actor={"type": "agent", "id": "moca"},
            resource_refs={"tool_name": "get_order"},
            redacted_payload={
                "decision_stage": "runtime_auth",
                "tool_name": "get_order",
                "decision": "denied",
                "reason_codes": ["missing_permission"],
                forbidden_key: forbidden_value,
            },
        )
