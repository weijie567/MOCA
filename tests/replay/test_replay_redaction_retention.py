from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.replay.service import ReplayService
from src.replay.validators import (
    EVENT_RETENTION_CLASSIFICATION,
    FORBIDDEN_REDACTED_PAYLOAD_KEYS,
    guard_redacted_payload,
    retention_for_event_type,
)


async def _create_run(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)
    await write_agent_run(
        session,
        run_id=str(run_id),
        thread_id="thread-redaction-retention",
        tenant_id=str(tenant_id),
        user_id=str(uuid.uuid4()),
        input_query="退款异常怎么处理？",
        final_status="running",
        final_response=None,
        started_at=now,
        completed_at=None,
        total_latency_ms=None,
    )
    return run_id, tenant_id


def test_every_replay_event_type_has_explicit_retention_classification():
    expected_events = {
        "approval_requested",
        "approval_decided",
        "approval_expired",
        "approval_resumed",
        "action_draft_created",
    }

    assert expected_events <= EVENT_RETENTION_CLASSIFICATION.keys()
    for event_type, retention_class in EVENT_RETENTION_CLASSIFICATION.items():
        assert retention_class
        assert retention_for_event_type(event_type) == retention_class


def test_redaction_guard_rejects_recursive_unsafe_keys():
    expected_forbidden = {
        "raw",
        "data",
        "arguments",
        "prompt",
        "raw_prompt",
        "raw_args",
        "raw_payload",
        "raw_tool_output",
        "secret",
        "secrets",
        "credential",
        "credentials",
        "pii",
    }
    assert expected_forbidden <= FORBIDDEN_REDACTED_PAYLOAD_KEYS

    for key in sorted(expected_forbidden):
        with pytest.raises(ValueError, match=key):
            guard_redacted_payload({"safe": [{"nested": {key: "unsafe"}}]})


@pytest.mark.asyncio
async def test_replay_service_rejects_unsafe_payload_before_persistence(session: AsyncSession):
    run_id, tenant_id = await _create_run(session)
    service = ReplayService(session)

    for key in ("raw_prompt", "raw_args", "raw_payload", "raw_tool_output", "secret", "credential", "pii"):
        with pytest.raises(ValueError, match=key):
            await service.append_event(
                run_id=run_id,
                tenant_id=tenant_id,
                thread_id="thread-redaction-retention",
                event_type="action_draft_created",
                actor={"type": "agent", "id": "moca"},
                resource_refs={"draft_id": str(uuid.uuid4())},
                redacted_payload={"summary": {key: "unsafe"}},
                schema_version="replay_event.v3",
            )
