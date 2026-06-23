from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.db.models import AgentTraceEvent
from src.platform.context_projections import ReplayContext
from src.replay.decision_events import DecisionEventEnvelopeV1, emit_decision_event
from src.replay.service import ReplayService
from src.replay.validators import guard_resource_refs


MINIMAL_ENVELOPE_KEYS = {
    "schema_version",
    "event_id",
    "sequence",
    "operation_id",
    "run_id",
    "tenant_id",
    "thread_id",
    "trace_id",
    "event_type",
    "occurred_at",
    "actor",
    "resource_refs",
    "redaction_policy_version",
    "redacted_payload",
}


def test_replay_and_agent_event_modules_cold_import() -> None:
    import subprocess
    import sys

    subprocess.run([sys.executable, "-c", "import src.replay"], check=True)
    subprocess.run([sys.executable, "-c", "import src.agent.events"], check=True)


def _base_envelope(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "minimal_event_envelope.v1",
        "event_id": uuid.uuid4(),
        "sequence": 1,
        "operation_id": uuid.uuid4(),
        "run_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "thread_id": "decision-event-thread",
        "trace_id": "trace-decision-event",
        "event_type": "node_started",
        "occurred_at": datetime(2026, 6, 23, 1, 0, tzinfo=UTC),
        "actor": {"type": "agent", "id": "moca"},
        "resource_refs": {"node": "investigate"},
        "redaction_policy_version": "redaction.v1",
        "redacted_payload": {"status": "started"},
    }
    payload.update(overrides)
    return payload


async def _create_run(session: AsyncSession, *, thread_id: str = "decision-event-thread") -> tuple[uuid.UUID, uuid.UUID]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id=thread_id,
        tenant_id=str(tenant_id),
        user_id=str(uuid.uuid4()),
        input_query="需要记录决策事件",
        final_status="running",
        final_response=None,
        started_at=now,
        completed_at=None,
        total_latency_ms=None,
        trace_id="trace-decision-event",
    )
    return run_id, tenant_id


def test_decision_event_envelope_accepts_exact_minimal_fields() -> None:
    event = DecisionEventEnvelopeV1.model_validate(_base_envelope())

    assert set(event.model_dump(mode="python")) == MINIMAL_ENVELOPE_KEYS
    assert set(DecisionEventEnvelopeV1.model_fields) == MINIMAL_ENVELOPE_KEYS
    assert event.schema_version == "minimal_event_envelope.v1"


def test_decision_event_envelope_rejects_extra_top_level_service_metadata() -> None:
    for key in (
        "policy_version",
        "model_version",
        "tool_version",
        "reason_code",
        "reason_codes",
        "service_name",
        "operation_name",
        "decision_type",
        "latency_ms",
        "error_code",
    ):
        with pytest.raises(ValidationError, match=key):
            DecisionEventEnvelopeV1.model_validate(_base_envelope(**{key: "not-an-envelope-field"}))


@pytest.mark.parametrize(
    "field_name",
    [
        "run_id",
        "tenant_id",
        "thread_id",
        "actor",
        "resource_refs",
        "redaction_policy_version",
        "redacted_payload",
    ],
)
def test_decision_event_envelope_requires_foundation_fields(field_name: str) -> None:
    payload = _base_envelope()
    payload.pop(field_name)

    with pytest.raises(ValidationError, match=field_name):
        DecisionEventEnvelopeV1.model_validate(payload)


def test_decision_event_envelope_rejects_unregistered_event_type() -> None:
    with pytest.raises(ValidationError, match="not registered"):
        DecisionEventEnvelopeV1.model_validate(_base_envelope(event_type="action_execution_completed"))


@pytest.mark.parametrize(
    "event_type",
    [
        "node_started",
        "tool_call_started",
        "rag_retrieval_completed",
        "llm_call_failed",
        "memory_write_started",
    ],
)
def test_decision_event_envelope_requires_operation_id_for_operation_lifecycle(event_type: str) -> None:
    with pytest.raises(ValidationError, match="operation_id"):
        DecisionEventEnvelopeV1.model_validate(_base_envelope(event_type=event_type, operation_id=None))


@pytest.mark.parametrize(
    "event_type",
    [
        "run_status_changed",
        "approval_requested",
        "approval_decided",
        "approval_expired",
        "approval_resumed",
        "action_draft_created",
    ],
)
def test_decision_event_envelope_allows_selected_lifecycle_events_without_operation_id(event_type: str) -> None:
    event = DecisionEventEnvelopeV1.model_validate(
        _base_envelope(
            event_type=event_type,
            operation_id=None,
            resource_refs={},
            redacted_payload={"status": "recorded"},
        )
    )

    assert event.operation_id is None


@pytest.mark.asyncio
async def test_emit_decision_event_uses_replay_context_identity(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)
    context = ReplayContext(
        tenant_id=str(tenant_id),
        user_id=str(uuid.uuid4()),
        role="support",
        thread_id="trusted-thread",
        run_id=str(run_id),
        trace_id="trusted-trace",
        policy_version="policy.v1",
        model_version="gpt-test.v1",
        tool_version="tool.v2",
    )

    event = await emit_decision_event(
        session,
        replay_context=context,
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        thread_id="caller-thread-must-not-win",
        trace_id="caller-trace-must-not-win",
        event_type="run_status_changed",
        actor={"type": "system", "id": "decision-test"},
        resource_refs={},
        redacted_payload={"status": "running"},
    )

    assert event["schema_version"] == "minimal_event_envelope.v1"
    assert event["run_id"] == run_id
    assert event["tenant_id"] == tenant_id
    assert event["thread_id"] == "trusted-thread"
    assert event["trace_id"] == "trusted-trace"
    assert event["redacted_payload"]["versions"] == {
        "policy_version": "policy.v1",
        "model_version": "gpt-test.v1",
        "tool_version": "tool.v2",
    }


@pytest.mark.asyncio
async def test_emit_decision_event_missing_required_identity_fails_closed(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)
    before_count = await session.scalar(select(func.count()).select_from(AgentTraceEvent))

    with pytest.raises(ValueError, match="tenant_id"):
        await emit_decision_event(
            session,
            run_id=run_id,
            tenant_id=None,
            thread_id="decision-event-thread",
            event_type="run_status_changed",
            actor={"type": "system", "id": "decision-test"},
            resource_refs={},
            redacted_payload={"status": "running"},
        )

    after_count = await session.scalar(select(func.count()).select_from(AgentTraceEvent))
    assert tenant_id
    assert after_count == before_count


@pytest.mark.asyncio
async def test_append_minimal_event_validates_before_flush_on_operation_id_failure(
    session: AsyncSession,
) -> None:
    run_id, tenant_id = await _create_run(session)
    before_count = await session.scalar(
        select(func.count()).select_from(AgentTraceEvent).where(AgentTraceEvent.run_id == run_id)
    )

    with pytest.raises(ValueError, match="operation_id"):
        await ReplayService(session).append_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id="decision-event-thread",
            event_type="node_started",
            actor={"type": "agent", "id": "moca"},
            resource_refs={"node": "investigate"},
            redacted_payload={"status": "started"},
            schema_version="minimal_event_envelope.v1",
        )

    await session.commit()
    row_count = await session.scalar(
        select(func.count()).select_from(AgentTraceEvent).where(AgentTraceEvent.run_id == run_id)
    )
    assert row_count == before_count


@pytest.mark.asyncio
async def test_reason_code_compatibility_normalizes_first_seen_reason_codes(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)

    event = await emit_decision_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="decision-event-thread",
        event_type="run_status_changed",
        actor={"type": "system", "id": "decision-test"},
        resource_refs={},
        redacted_payload={"decision": "deny"},
        reason_code="scope_denied",
        reason_codes=["missing_permission", "scope_denied"],
    )

    assert event["redacted_payload"]["reason_codes"] == ["scope_denied", "missing_permission"]
    assert "reason_code" not in event
    assert "reason_codes" not in event


@pytest.mark.asyncio
async def test_reason_code_validation_accepts_unknown_snake_case_without_allowlist(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)

    event = await emit_decision_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="decision-event-thread",
        event_type="run_status_changed",
        actor={"type": "system", "id": "decision-test"},
        resource_refs={},
        redacted_payload={"decision": "defer"},
        reason_codes=["phase_29_future_reason"],
    )

    assert event["redacted_payload"]["reason_codes"] == ["phase_29_future_reason"]


@pytest.mark.asyncio
async def test_redacted_payload_reason_codes_are_normalized(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)

    event = await emit_decision_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="decision-event-thread",
        event_type="run_status_changed",
        actor={"type": "system", "id": "decision-test"},
        resource_refs={},
        redacted_payload={"reason_codes": ["scope_denied", "missing_permission", "scope_denied"]},
    )

    assert event["redacted_payload"]["reason_codes"] == ["scope_denied", "missing_permission"]


@pytest.mark.parametrize("invalid_reason_codes", ["scope_denied", ("scope_denied",)])
@pytest.mark.asyncio
async def test_reason_codes_argument_must_be_list(
    session: AsyncSession,
    invalid_reason_codes: object,
) -> None:
    run_id, tenant_id = await _create_run(session)

    with pytest.raises(ValueError, match="reason_codes must be a list"):
        await emit_decision_event(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id="decision-event-thread",
            event_type="run_status_changed",
            actor={"type": "system", "id": "decision-test"},
            resource_refs={},
            redacted_payload={"decision": "deny"},
            reason_codes=invalid_reason_codes,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_redacted_payload_reason_codes_must_be_list(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)

    with pytest.raises(ValueError, match="reason_codes must be a list"):
        await emit_decision_event(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id="decision-event-thread",
            event_type="run_status_changed",
            actor={"type": "system", "id": "decision-test"},
            resource_refs={},
            redacted_payload={"reason_codes": "ScopeDenied"},
        )


@pytest.mark.parametrize("reason_code", ["", "ScopeDenied", "scope-denied", "scope denied"])
@pytest.mark.asyncio
async def test_invalid_reason_codes_raise_value_error(session: AsyncSession, reason_code: str) -> None:
    run_id, tenant_id = await _create_run(session)

    with pytest.raises(ValueError, match="reason_code"):
        await emit_decision_event(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id="decision-event-thread",
            event_type="run_status_changed",
            actor={"type": "system", "id": "decision-test"},
            resource_refs={},
            redacted_payload={"decision": "deny"},
            reason_code=reason_code,
        )


@pytest.mark.asyncio
async def test_versions_land_under_redacted_payload_versions(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)
    context = ReplayContext(
        tenant_id=str(tenant_id),
        user_id=str(uuid.uuid4()),
        role="support",
        thread_id="decision-event-thread",
        run_id=str(run_id),
        trace_id="trace-decision-event",
        policy_version="tool_policy.v1",
        model_version="gpt-test.v1",
    )

    event = await emit_decision_event(
        session,
        replay_context=context,
        event_type="run_status_changed",
        actor={"type": "system", "id": "decision-test"},
        resource_refs={},
        redacted_payload={"decision": "allow"},
        versions={"tool_version": "refund_lookup.v2", "redaction_policy_version": "redaction.v1"},
    )

    assert event["redacted_payload"]["versions"] == {
        "policy_version": "tool_policy.v1",
        "model_version": "gpt-test.v1",
        "tool_version": "refund_lookup.v2",
    }
    assert "policy_version" not in event
    assert "model_version" not in event
    assert "tool_version" not in event


@pytest.mark.parametrize(
    "key",
    ["raw_prompt", "raw_args", "raw_payload", "raw_tool_output", "secret", "credentials", "pii"],
)
def test_resource_refs_redaction_guard_rejects_unsafe_keys(key: str) -> None:
    with pytest.raises(ValueError, match=key):
        guard_resource_refs({"typed_ref": {"nested": {key: "unsafe"}}})


@pytest.mark.parametrize(
    "key",
    ["raw_prompt", "raw_args", "raw_payload", "raw_tool_output", "secret", "credentials", "pii"],
)
@pytest.mark.asyncio
async def test_emit_decision_event_rejects_payload_and_resource_ref_leakage(
    session: AsyncSession,
    key: str,
) -> None:
    run_id, tenant_id = await _create_run(session)

    with pytest.raises(ValueError, match=key):
        await emit_decision_event(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id="decision-event-thread",
            event_type="run_status_changed",
            actor={"type": "system", "id": "decision-test"},
            resource_refs={},
            redacted_payload={"summary": {key: "unsafe"}},
        )

    with pytest.raises(ValueError, match=key):
        await emit_decision_event(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id="decision-event-thread",
            event_type="run_status_changed",
            actor={"type": "system", "id": "decision-test"},
            resource_refs={"typed_ref": {key: "unsafe"}},
            redacted_payload={"summary": "safe"},
        )


@pytest.mark.asyncio
async def test_emit_decision_event_allows_service_metadata_inside_redacted_payload(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)

    event = await emit_decision_event(
        session,
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="decision-event-thread",
        event_type="run_status_changed",
        actor={"type": "system", "id": "decision-test"},
        resource_refs={"policy_ref": "policy:refund:v1"},
        redacted_payload={
            "service_name": "tool_policy",
            "operation_name": "authorize_tool",
            "decision_type": "deny",
            "latency_ms": 12,
            "error_code": "SCOPE_DENIED",
        },
    )

    assert event["redacted_payload"]["service_name"] == "tool_policy"
    assert "service_name" not in event
    assert set(event) == MINIMAL_ENVELOPE_KEYS


@pytest.mark.asyncio
async def test_project_minimal_event_matches_decision_event_envelope(session: AsyncSession) -> None:
    run_id, tenant_id = await _create_run(session)

    event = await ReplayService(session).append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id="decision-event-thread",
        trace_id="trace-decision-event",
        event_type="run_status_changed",
        actor={"type": "system", "id": "replay-service"},
        resource_refs={},
        redacted_payload={"from_status": "pending", "to_status": "running"},
        schema_version="minimal_event_envelope.v1",
    )

    validated = DecisionEventEnvelopeV1.model_validate(event).model_dump(mode="python")
    assert set(validated) == MINIMAL_ENVELOPE_KEYS
    assert validated["schema_version"] == "minimal_event_envelope.v1"
