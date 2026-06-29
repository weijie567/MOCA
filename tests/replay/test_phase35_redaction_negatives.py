from __future__ import annotations

from datetime import UTC, datetime
import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, AgentTraceEvent
from src.replay.service import ReplayService
from src.replay.validators import FORBIDDEN_REDACTED_PAYLOAD_KEYS, guard_redacted_payload


UNSAFE_REPLAY_KEYS = (
    "raw_prompt",
    "raw_tool_payload",
    "ticket_pii",
    "order_pii",
    "refund_pii",
    "raw_action_payload",
    "secret",
    "credential",
    "unsafe_debug_payload",
    "buyer_name",
    "api_key",
)


async def _create_run(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID, str]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    thread_id = f"phase35-redaction-{run_id}"
    now = datetime.now(UTC)
    session.add(
        AgentRun(
            id=run_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            user_id=uuid.uuid4(),
            input_query="phase35 redaction negatives",
            final_status="completed",
            final_response="safe final response",
            started_at=now,
            completed_at=now,
            total_latency_ms=10,
        )
    )
    await session.flush()
    return run_id, tenant_id, thread_id


def _unsafe_marker(key: str) -> str:
    return f"SHOULD_NOT_LEAK_{key.upper()}"


def test_phase35_forbidden_key_aliases_are_registered() -> None:
    assert set(UNSAFE_REPLAY_KEYS) <= FORBIDDEN_REDACTED_PAYLOAD_KEYS


@pytest.mark.parametrize("unsafe_key", UNSAFE_REPLAY_KEYS)
def test_redaction_guard_rejects_phase35_raw_pii_secret_and_debug_aliases(unsafe_key: str) -> None:
    with pytest.raises(ValueError, match=unsafe_key):
        guard_redacted_payload({"safe_summary": {unsafe_key: _unsafe_marker(unsafe_key)}})


@pytest.mark.asyncio
@pytest.mark.parametrize("unsafe_key", UNSAFE_REPLAY_KEYS)
async def test_append_event_rejects_phase35_raw_pii_secret_and_debug_aliases(
    session: AsyncSession,
    unsafe_key: str,
) -> None:
    run_id, tenant_id, thread_id = await _create_run(session)
    service = ReplayService(session)

    with pytest.raises(ValueError, match=unsafe_key):
        await service.append_event(
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=thread_id,
            event_type="action_draft_created",
            actor={"type": "agent", "id": "moca"},
            resource_refs={"draft_id": str(uuid.uuid4())},
            redacted_payload={"safe_summary": {unsafe_key: _unsafe_marker(unsafe_key)}},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("unsafe_key", UNSAFE_REPLAY_KEYS)
async def test_get_replay_rejects_or_omits_stored_phase35_unsafe_payload_aliases(
    session: AsyncSession,
    unsafe_key: str,
) -> None:
    run_id, tenant_id, thread_id = await _create_run(session)
    marker = _unsafe_marker(unsafe_key)
    session.add(
        AgentTraceEvent(
            event_id=uuid.uuid4(),
            run_id=run_id,
            sequence=1,
            tenant_id=tenant_id,
            thread_id=thread_id,
            event_type="action_draft_created",
            schema_version="replay_event.v3",
            occurred_at=datetime.now(UTC),
            actor={"type": "agent", "id": "moca"},
            resource_refs={"draft_id": str(uuid.uuid4())},
            redaction_policy_version="redaction.v1",
            redacted_payload={"safe_summary": {unsafe_key: marker}},
        )
    )
    await session.flush()

    try:
        replay = await ReplayService(session).get_replay(run_id)
    except ValueError as exc:
        assert unsafe_key in str(exc)
    else:
        serialized = json.dumps(replay, default=str, sort_keys=True)
        assert marker not in serialized
        assert unsafe_key not in serialized
        pytest.fail(f"{unsafe_key} reached replay projection")
