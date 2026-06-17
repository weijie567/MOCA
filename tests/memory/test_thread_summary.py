from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.db.models import AgentRun, ConversationSummary, ToolResultRecord
from src.memory.repository import SessionMemoryRepository
from src.memory.thread_summary import ThreadRollingSummaryService
from src.tools.contracts import BusinessFactRefV1, ToolResultV2


RAW_TOOL_PAYLOAD_SHOULD_NOT_APPEAR = "RAW_TOOL_PAYLOAD_SHOULD_NOT_APPEAR"
RAW_POLICY_TEXT_SHOULD_NOT_APPEAR = "RAW_POLICY_TEXT_SHOULD_NOT_APPEAR"
STORED_TOOL_SUMMARY_SHOULD_NOT_APPEAR = "STORED_TOOL_SUMMARY_SHOULD_NOT_APPEAR"


async def _insert_run(session: AsyncSession, seeded_session: dict, thread_id: str) -> uuid.UUID:
    run_id = uuid.uuid4()
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=seeded_session["tenant"].id,
            user_id=seeded_session["users"]["cs_zhang"].id,
            thread_id=thread_id,
            input_query="test",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


def _tool_result_with_raw_payload(tenant_id: uuid.UUID) -> ToolResultV2:
    business_ref = BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="business_tool_service",
        resource_type="order",
        resource_id="ORD-TOOL-001",
        resource_version=None,
        data_freshness_at=datetime.now(UTC),
        retrieved_at=datetime.now(UTC),
    )
    return ToolResultV2(
        status="success",
        data={
            "order_id": "ORD-TOOL-001",
            "raw_payload": {
                "marker": RAW_TOOL_PAYLOAD_SHOULD_NOT_APPEAR,
                "raw_policy_text": RAW_POLICY_TEXT_SHOULD_NOT_APPEAR,
            },
        },
        summary="Safe tool summary: order ORD-TOOL-001 refund status is reviewing.",
        source_system="business_tool_service",
        data_freshness_at=datetime.now(UTC),
        policy_evidence_refs=[],
        business_fact_refs=[business_ref],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=11,
        audit_ref="audit/tool-result/ORD-TOOL-001",
    )


async def _summary_row(session: AsyncSession, *, thread_id: str) -> ConversationSummary:
    return (
        await session.execute(
            select(ConversationSummary)
            .where(
                ConversationSummary.thread_id == thread_id,
                ConversationSummary.summary_type == "thread_rolling",
            )
            .order_by(ConversationSummary.created_at.desc())
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_thread_rolling_summary_records_source_message_range(
    session: AsyncSession, seeded_session: dict
) -> None:
    repository = ConversationRepository(session)
    conversation = ConversationService(repository)
    summary_service = ThreadRollingSummaryService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-summary-source-range"
    run_id = await _insert_run(session, seeded_session, thread_id)

    user_message = await conversation.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="请确认订单 ORD-TEST-001 的退款 RF-TEST-001 进度。",
    )
    assistant_message = await conversation.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="已确认 ORD-TEST-001 / RF-TEST-001 仍在审核中。",
    )

    persisted = await summary_service.persist_thread_summary(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
    )

    assert persisted.summary_type == "thread_rolling"
    assert persisted.source_start_message_id == user_message.message_id
    assert persisted.source_end_message_id == assistant_message.message_id
    assert persisted.source_message_ids_json == [str(user_message.message_id), str(assistant_message.message_id)]
    assert persisted.source_tool_result_ids_json == []
    assert "ORD-TEST-001" in (persisted.summary_text or "")
    assert "RF-TEST-001" in (persisted.summary_text or "")


@pytest.mark.asyncio
async def test_thread_rolling_summary_includes_safe_tool_summaries_only(
    session: AsyncSession, seeded_session: dict
) -> None:
    repository = ConversationRepository(session)
    conversation = ConversationService(repository)
    summary_service = ThreadRollingSummaryService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-summary-safe-tool"
    run_id = await _insert_run(session, seeded_session, thread_id)
    operation_id = uuid.uuid4()

    await conversation.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="查一下 ORD-TOOL-001。",
    )
    tool_call = await conversation.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-summary-safe-tool",
        tool_call_id=str(operation_id),
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"order_no": "ORD-TOOL-001", "raw_payload": RAW_TOOL_PAYLOAD_SHOULD_NOT_APPEAR},
        argument_summary_json={"order_no": "ORD-TOOL-001", "omitted": ["raw_payload"]},
        redaction_policy_version="conversation_redaction.v1",
    )
    prompt_summary = await conversation.append_tool_result(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-summary-safe-tool",
        operation_id=operation_id,
        tool_call_id=str(operation_id),
        tool_call_record_id=tool_call.id,
        tool_result_id="tool-result-thread-summary-1",
        tool_name="get_order",
        result=_tool_result_with_raw_payload(tenant_id),
        raw_result_ref="raw-result://orders/ORD-TOOL-001",
        raw_result_hash="sha256:rawresultfixture",
    )
    stored_tool_result = (
        await session.execute(
            select(ToolResultRecord).where(ToolResultRecord.tool_result_id == "tool-result-thread-summary-1")
        )
    ).scalar_one()
    stored_tool_result.summary = STORED_TOOL_SUMMARY_SHOULD_NOT_APPEAR
    stored_tool_result.prompt_summary = "Prompt-safe tool summary for ORD-TOOL-001."
    await session.flush()

    persisted = await summary_service.persist_thread_summary(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
    )

    summary_text = persisted.summary_text or ""
    assert prompt_summary.prompt_summary
    assert "ORD-TOOL-001" in summary_text
    assert "Prompt-safe tool summary" in summary_text
    assert STORED_TOOL_SUMMARY_SHOULD_NOT_APPEAR not in summary_text
    assert str(stored_tool_result.id) in persisted.source_tool_result_ids_json
    assert RAW_TOOL_PAYLOAD_SHOULD_NOT_APPEAR not in summary_text
    assert RAW_POLICY_TEXT_SHOULD_NOT_APPEAR not in summary_text
    assert "raw_payload" not in summary_text
    assert "raw_policy_text" not in summary_text


@pytest.mark.asyncio
async def test_thread_rolling_summary_preserves_open_questions_and_constraints(
    session: AsyncSession, seeded_session: dict
) -> None:
    repository = ConversationRepository(session)
    conversation = ConversationService(repository)
    summary_service = ThreadRollingSummaryService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-summary-open-questions"
    run_id = await _insert_run(session, seeded_session, thread_id)

    await conversation.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="订单 ORD-OPEN-001 是否还缺少物流签收证明？",
    )
    await conversation.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="关键决策：先核实 ORD-OPEN-001。开放问题：需要确认物流签收时间。约束：不能承诺自动退款。",
    )

    persisted = await summary_service.persist_thread_summary(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
    )

    summary_text = persisted.summary_text or ""
    assert "ORD-OPEN-001" in summary_text
    assert "开放问题" in summary_text
    assert "需要确认物流签收时间" in summary_text
    assert "不能承诺自动退款" in summary_text


@pytest.mark.asyncio
async def test_thread_summary_is_not_session_memory_or_case_memory(
    session: AsyncSession, seeded_session: dict
) -> None:
    repository = ConversationRepository(session)
    conversation = ConversationService(repository)
    session_memory_repository = SessionMemoryRepository(session)
    summary_service = ThreadRollingSummaryService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-summary-not-session"
    run_id = await _insert_run(session, seeded_session, thread_id)
    await session_memory_repository.insert_active(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        active_slots_json={
            "schema_version": "session_slots.v1",
            "slots": {},
        },
        session_summary="existing Phase 12 session summary",
        unresolved_questions_json=["existing Phase 12 question"],
        last_intent="refund_troubleshooting",
    )
    await conversation.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="继续看 ORD-SEPARATE-001。",
    )
    await conversation.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="ORD-SEPARATE-001 当前只写入 thread_rolling summary。",
    )

    persisted = await summary_service.persist_thread_summary(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
    )
    active_session_memory = await session_memory_repository.get_active(tenant_id, user_id, thread_id)
    stored_summary = await _summary_row(session, thread_id=thread_id)

    assert active_session_memory is not None
    assert active_session_memory.session_summary == "existing Phase 12 session summary"
    assert active_session_memory.unresolved_questions_json == ["existing Phase 12 question"]
    assert active_session_memory.last_intent == "refund_troubleshooting"
    assert stored_summary.id == persisted.id
    assert stored_summary.summary_type == "thread_rolling"
    assert stored_summary.case_id is None
    assert "case_memory" not in (stored_summary.summary_text or "")
    assert "embedding" not in (stored_summary.summary_text or "")
    assert "tombstone" not in (stored_summary.summary_text or "")
