from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.trace import write_agent_run
from src.conversation.repository import ConversationRepository
from src.conversation.schemas import FORBIDDEN_MESSAGE_KEYS
from src.conversation.service import ConversationService
from src.db.models import AgentTraceEvent, AuditLog, Base, ToolCallRecord, ToolResultRecord
from src.replay.service import ReplayService
from src.replay.validators import FORBIDDEN_REDACTED_PAYLOAD_KEYS, guard_redacted_payload
from src.repositories.audit_repo import AuditRepository
from src.tools.contracts import BusinessFactRefV1, ToolResultV2


async def _insert_run(
    session: AsyncSession,
    seeded_session: dict,
    *,
    thread_id: str,
    run_id: uuid.UUID | None = None,
    trace_id: str = "trace-memory-alignment",
) -> uuid.UUID:
    run_uuid = run_id or uuid.uuid4()
    await write_agent_run(
        session,
        run_id=str(run_uuid),
        thread_id=thread_id,
        tenant_id=str(seeded_session["tenant"].id),
        user_id=str(seeded_session["users"]["cs_zhang"].id),
        input_query="memory foundation alignment fixture",
        final_status="running",
        final_response=None,
        started_at=datetime.now(UTC),
        completed_at=None,
        total_latency_ms=None,
        trace_id=trace_id,
    )
    return run_uuid


def _tool_result(*, tenant_id: uuid.UUID, audit_ref: str) -> ToolResultV2:
    business_ref = BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="business_tool_service",
        resource_type="order",
        resource_id="ORD-ALIGN-001",
        resource_version=None,
        data_freshness_at=datetime.now(UTC),
        retrieved_at=datetime.now(UTC),
    )
    return ToolResultV2(
        status="success",
        data={"order_id": "ORD-ALIGN-001", "status": "delivered"},
        summary="Safe order status summary for ORD-ALIGN-001.",
        source_system="business_tool_service",
        data_freshness_at=datetime.now(UTC),
        policy_evidence_refs=[],
        business_fact_refs=[business_ref],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=11,
        audit_ref=audit_ref,
    )


@pytest.mark.asyncio
async def test_conversation_tool_replay_and_audit_refs_share_run_thread_trace_ids(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    tenant_id = seeded_session["tenant"].id
    user = seeded_session["users"]["cs_zhang"]
    user_id = user.id
    thread_id = "thread-memory-foundation-alignment"
    trace_id = "trace-memory-foundation-alignment"
    run_id = await _insert_run(session, seeded_session, thread_id=thread_id, trace_id=trace_id)
    operation_id = uuid.uuid4()
    tool_call_id = str(operation_id)
    tool_result_id = "tool-result-memory-foundation-alignment"

    conversation = ConversationService(ConversationRepository(session))
    user_message = await conversation.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id=trace_id,
        content="Please check order ORD-ALIGN-001.",
    )
    tool_message = await conversation.append_tool_summary_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id=trace_id,
        content="get_order will return a prompt-safe summary only.",
        metadata_json={"conversation_message_id": str(user_message.message_id)},
    )

    replay = ReplayService(session)
    await replay.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        trace_id=trace_id,
        event_type="tool_call_started",
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool": "get_order"},
        redacted_payload={"tool_name": "get_order", "status": "started"},
        operation_id=operation_id,
        attempt=1,
        tool_call_id=tool_call_id,
    )
    completed_replay_event = await replay.append_event(
        run_id=run_id,
        tenant_id=tenant_id,
        thread_id=thread_id,
        trace_id=trace_id,
        event_type="tool_call_completed",
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool": "get_order", "conversation_message_id": str(tool_message.message_id)},
        redacted_payload={
            "tool_name": "get_order",
            "status": "success",
            "tool_result_id": tool_result_id,
            "conversation_message_id": str(tool_message.message_id),
        },
        operation_id=operation_id,
        attempt=1,
        tool_call_id=tool_call_id,
    )
    audit_ref = await AuditRepository(session).record_conversation_reference(
        tenant_id=tenant_id,
        user=user,
        action="conversation.tool_result.correlated",
        resource_type="conversation",
        resource_id=tool_message.message_id,
        trace_id=trace_id,
        run_id=str(run_id),
        tool_call_id=tool_call_id,
        latency_ms=11,
        status="success",
        metadata_json={
            "conversation_message_id": str(tool_message.message_id),
            "tool_result_id": tool_result_id,
            "replay_event_id": str(completed_replay_event["event_id"]),
        },
    )
    tool_call = await conversation.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id=trace_id,
        tool_call_id=tool_call_id,
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"order_no": "ORD-ALIGN-001"},
        argument_summary_json={"order_no": "ORD-ALIGN-001"},
        redaction_policy_version="conversation_redaction.v1",
        conversation_message_id=tool_message.message_id,
    )
    prompt_summary = await conversation.append_tool_result(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id=trace_id,
        operation_id=operation_id,
        tool_call_id=tool_call_id,
        tool_call_record_id=tool_call.id,
        conversation_message_id=tool_message.message_id,
        tool_result_id=tool_result_id,
        tool_name="get_order",
        result=_tool_result(tenant_id=tenant_id, audit_ref=audit_ref),
        replay_event_id=completed_replay_event["event_id"],
    )
    assistant_message = await conversation.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id=trace_id,
        content="Order ORD-ALIGN-001 has been checked.",
        metadata_json={"conversation_message_id": str(tool_message.message_id)},
    )

    stored_call = (
        await session.execute(select(ToolCallRecord).where(ToolCallRecord.id == tool_call.id))
    ).scalar_one()
    stored_result = (
        await session.execute(select(ToolResultRecord).where(ToolResultRecord.tool_result_id == tool_result_id))
    ).scalar_one()
    replay_row = (
        await session.execute(
            select(AgentTraceEvent).where(AgentTraceEvent.event_id == completed_replay_event["event_id"])
        )
    ).scalar_one()
    audit_log_id = uuid.UUID(audit_ref.rsplit("/", 1)[-1])
    audit_row = (await session.execute(select(AuditLog).where(AuditLog.id == audit_log_id))).scalar_one()

    assert user_message.thread_id == tool_message.thread_id == assistant_message.thread_id == thread_id
    assert stored_call.tenant_id == stored_result.tenant_id == replay_row.tenant_id == audit_row.tenant_id == tenant_id
    assert stored_call.thread_id == stored_result.thread_id == replay_row.thread_id == thread_id
    assert stored_call.run_id == stored_result.run_id == replay_row.run_id == run_id
    assert stored_call.trace_id == stored_result.trace_id == replay_row.trace_id == audit_row.trace_id == trace_id
    assert stored_call.tool_call_id == stored_result.tool_call_id == replay_row.tool_call_id == tool_call_id
    assert stored_call.operation_id == stored_result.operation_id == replay_row.operation_id == operation_id
    assert stored_call.conversation_message_id == stored_result.conversation_message_id == tool_message.message_id
    assert stored_result.tool_result_id == prompt_summary.tool_result_id == tool_result_id
    assert stored_result.replay_event_id == completed_replay_event["event_id"]
    assert stored_result.audit_ref == audit_ref
    assert audit_row.metadata_json["conversation_message_id"] == str(tool_message.message_id)
    assert audit_row.metadata_json["tool_result_id"] == tool_result_id
    assert audit_row.metadata_json["replay_event_id"] == str(completed_replay_event["event_id"])


@pytest.mark.asyncio
async def test_replay_redaction_guard_is_not_weakened_by_conversation_refs(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    tenant_id = seeded_session["tenant"].id
    thread_id = "thread-memory-redaction-alignment"
    run_id = await _insert_run(session, seeded_session, thread_id=thread_id)
    service = ReplayService(session)

    for forbidden_key in ("raw_prompt", "raw_tool_output", "raw_payload", "raw", "data", "prompt"):
        with pytest.raises(ValueError, match=forbidden_key):
            guard_redacted_payload({"summary": [{"nested": {forbidden_key: "unsafe"}}]})
        with pytest.raises(ValueError, match=forbidden_key):
            await service.append_event(
                run_id=run_id,
                tenant_id=tenant_id,
                thread_id=thread_id,
                event_type="tool_call_started",
                actor={"type": "agent", "id": "moca"},
                resource_refs={"tool": "get_order", "conversation_message_id": str(uuid.uuid4())},
                redacted_payload={"summary": {forbidden_key: "unsafe"}},
                operation_id=uuid.uuid4(),
                attempt=1,
            )

    assert "approval_authority_body" not in FORBIDDEN_REDACTED_PAYLOAD_KEYS
    assert "action_authority_body" not in FORBIDDEN_REDACTED_PAYLOAD_KEYS
    guard_redacted_payload({"summary": {"conversation_message_id": str(uuid.uuid4())}})
    ConversationService(None).validate_safe_message_payload(
        content="safe summary",
        metadata_json={"conversation_message_id": str(uuid.uuid4())},
    )
    with pytest.raises(ValueError, match="approval_authority_body"):
        ConversationService(None).validate_safe_message_payload(
            content="safe summary",
            metadata_json={"approval_authority_body": {"raw": "authority"}},
        )


def test_memory_foundation_layers_do_not_overlap_authority() -> None:
    conversation_source = Path("src/conversation/service.py").read_text(encoding="utf-8")
    context_source = Path("src/agent/context/assembler.py").read_text(encoding="utf-8")
    session_memory_source = Path("src/db/migrations/versions/007_session_memories.py").read_text(encoding="utf-8")

    assert "session_memories" in session_memory_source
    assert "session_memories" not in conversation_source
    assert "ThreadRollingSummaryService" not in conversation_source
    assert "business_context" not in conversation_source
    assert {"approval_authority_body", "action_authority_body"} <= FORBIDDEN_MESSAGE_KEYS
    assert "authority objects" in context_source
    assert "approval_authority_body" not in FORBIDDEN_REDACTED_PAYLOAD_KEYS
    assert "action_authority_body" not in FORBIDDEN_REDACTED_PAYLOAD_KEYS
    assert "raw_payload" in FORBIDDEN_REDACTED_PAYLOAD_KEYS
    assert "raw_prompt" in FORBIDDEN_REDACTED_PAYLOAD_KEYS


def test_memory_foundation_and_phase_17_artifacts_remain_separate() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for root in ("src/conversation", "src/agent/context")
        for path in Path(root).glob("*.py")
    )
    memory_foundation_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            Path("src/db/migrations/versions/011_memory_foundation_v2.py"),
            Path("src/db/migrations/versions/012_thread_user_scope.py"),
        )
    )
    table_names = set(Base.metadata.tables)

    assert "embedding" not in source
    assert "vector search" not in source
    assert "external_execution" not in source
    assert "outbox" not in source
    assert "compensation workflow" not in source
    assert "case_memories" not in memory_foundation_source
    assert "memory_tombstones" not in memory_foundation_source
    assert "action_executions" not in memory_foundation_source
    assert "action_outbox_events" not in memory_foundation_source
    assert "long_term_memories" in table_names
    assert "case_memories" in table_names
    assert "memory_tombstones" in table_names
    assert "action_outbox_events" not in table_names
