from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun, ConversationMessage, ToolResultRecord


async def _insert_run(
    session: AsyncSession,
    seeded_session: dict,
    thread_id: str,
    *,
    user_key: str = "cs_zhang",
) -> uuid.UUID:
    run_id = uuid.uuid4()
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=seeded_session["tenant"].id,
            user_id=seeded_session["users"][user_key].id,
            thread_id=thread_id,
            input_query="test",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


@pytest.mark.asyncio
async def test_chat_turn_records_user_and_assistant_messages_without_raw_prompt(
    session: AsyncSession, seeded_session: dict
) -> None:
    from src.conversation.repository import ConversationRepository
    from src.conversation.service import ConversationService

    repository = ConversationRepository(session)
    service = ConversationService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-chat-turn"
    run_id = await _insert_run(session, seeded_session, thread_id)

    user_result = await service.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="我的退款为什么还没到账？",
        prompt_template_version="chat.request.v1",
        prompt_block_hashes_json=["sha256:user-block"],
        context_snapshot_ref="context_snapshot/thread-chat-turn/1",
    )
    assistant_result = await service.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="已查询到退款仍在审核中。",
    )

    messages = await repository.list_messages(tenant_id=tenant_id, user_id=user_id, thread_id=thread_id)

    assert [message.role for message in messages] == ["user", "assistant"]
    assert [message.message_index for message in messages] == [1, 2]
    assert user_result.message_id == messages[0].id
    assert assistant_result.message_id == messages[1].id
    for message in messages:
        assert "raw_prompt" not in message.metadata_json
        assert message.redacted_prompt_snapshot_ref is None


@pytest.mark.asyncio
async def test_append_tool_summary_message_rejects_authority_and_reasoning_payloads(
    session: AsyncSession, seeded_session: dict
) -> None:
    from src.conversation.repository import ConversationRepository
    from src.conversation.service import ConversationService

    repository = ConversationRepository(session)
    service = ConversationService(repository)

    with pytest.raises(ValueError, match="private_reasoning"):
        await service.append_tool_summary_message(
            tenant_id=seeded_session["tenant"].id,
            user_id=seeded_session["users"]["cs_zhang"].id,
            thread_id="thread-reject-private",
            run_id=uuid.uuid4(),
            content="safe summary",
            metadata_json={"private_reasoning": "hidden chain"},
        )
    with pytest.raises(ValueError, match="approval_authority_body"):
        await service.append_tool_summary_message(
            tenant_id=seeded_session["tenant"].id,
            user_id=seeded_session["users"]["cs_zhang"].id,
            thread_id="thread-reject-approval",
            run_id=uuid.uuid4(),
            content="safe summary",
            metadata_json={"approval_authority_body": {"approval": "raw"}},
        )


def test_reserved_case_id_does_not_create_case_memory_retrieval() -> None:
    migration_source = Path("src/db/migrations/versions/011_memory_foundation_v2.py").read_text(encoding="utf-8")
    conversation_sources = "\n".join(path.read_text(encoding="utf-8") for path in Path("src/conversation").glob("*.py"))

    assert "case_id" in migration_source
    assert "case_memories" not in migration_source
    assert "memory_tombstones" not in migration_source
    assert "embedding" not in migration_source
    assert "vector" not in migration_source
    assert "search_case_memory" not in conversation_sources


@pytest.mark.asyncio
async def test_load_prompt_context_first_turn_with_zero_summaries(session: AsyncSession, seeded_session: dict) -> None:
    from src.conversation.repository import ConversationRepository
    from src.conversation.service import ConversationService

    repository = ConversationRepository(session)
    service = ConversationService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-first-turn-zero-summaries"
    run_id = await _insert_run(session, seeded_session, thread_id)
    await service.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="first-turn zero summaries: 查询 ORD-FIRST-001。",
    )

    context = await service.load_prompt_context(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        max_recent_messages=4,
    )

    assert context.latest_thread_summary is None
    assert [message.content for message in context.recent_messages] == [
        "first-turn zero summaries: 查询 ORD-FIRST-001。"
    ]
    assert context.tool_prompt_summaries == []


@pytest.mark.asyncio
async def test_completed_chat_path_writes_thread_summary_after_user_tool_assistant_records(
    session: AsyncSession, seeded_session: dict
) -> None:
    from sqlalchemy import select

    from src.conversation.repository import ConversationRepository
    from src.conversation.service import ConversationService
    from src.db.models import ConversationSummary
    from src.memory.thread_summary import ThreadRollingSummaryService
    from src.tools.contracts import BusinessFactRefV1, ToolResultV2

    repository = ConversationRepository(session)
    service = ConversationService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-completed-chat-summary"
    run_id = await _insert_run(session, seeded_session, thread_id)
    operation_id = uuid.uuid4()
    await service.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="请查询 ORD-COMPLETE-001。",
    )
    tool_call = await service.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-completed-chat-summary",
        tool_call_id=str(operation_id),
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"order_no": "ORD-COMPLETE-001"},
        argument_summary_json={"order_no": "ORD-COMPLETE-001"},
        redaction_policy_version="conversation_redaction.v1",
    )
    business_ref = BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="business_tool_service",
        resource_type="order",
        resource_id="ORD-COMPLETE-001",
        resource_version=None,
        data_freshness_at=datetime.now(UTC),
        retrieved_at=datetime.now(UTC),
    )
    prompt_summary = await service.append_tool_result(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        trace_id="trace-completed-chat-summary",
        operation_id=operation_id,
        tool_call_id=str(operation_id),
        tool_call_record_id=tool_call.id,
        tool_result_id="tool-result-completed-chat",
        tool_name="get_order",
        result=ToolResultV2(
            status="success",
            data={"order_id": "ORD-COMPLETE-001"},
            summary="Safe completed chat tool summary for ORD-COMPLETE-001.",
            source_system="business_tool_service",
            data_freshness_at=datetime.now(UTC),
            policy_evidence_refs=[],
            business_fact_refs=[business_ref],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=9,
            audit_ref="audit/tool-result/ORD-COMPLETE-001",
        ),
    )
    tool_message = await service.append_tool_summary_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content=prompt_summary.prompt_summary,
    )
    assistant_message = await service.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="ORD-COMPLETE-001 已查询完成。",
    )

    summary = await ThreadRollingSummaryService(repository).persist_thread_summary(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
    )
    stored_summary = (
        await session.execute(
            select(ConversationSummary).where(
                ConversationSummary.id == summary.id,
                ConversationSummary.summary_type == "thread_rolling",
            )
        )
    ).scalar_one()

    assert stored_summary.source_start_message_id is not None
    assert stored_summary.source_end_message_id == assistant_message.message_id
    assert str(tool_message.message_id) in stored_summary.source_message_ids_json
    assert stored_summary.source_tool_result_ids_json
    assert "Safe completed chat tool summary" in (stored_summary.summary_text or "")
    assert "ORD-COMPLETE-001" in (stored_summary.summary_text or "")


@pytest.mark.asyncio
async def test_load_prompt_context_returns_latest_committed_prior_turn_and_bounded_recent_messages(
    session: AsyncSession, seeded_session: dict
) -> None:
    from src.conversation.repository import ConversationRepository
    from src.conversation.service import ConversationService
    from src.memory.thread_summary import ThreadRollingSummaryService
    from src.tools.contracts import BusinessFactRefV1, ToolResultV2

    repository = ConversationRepository(session)
    service = ConversationService(repository)
    summary_service = ThreadRollingSummaryService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-prior-turn-context-window"
    prior_run_id = await _insert_run(session, seeded_session, thread_id)
    await service.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
        content="prior-turn: 查询 ORD-PRIOR-001。",
    )
    await service.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
        content="prior-turn: ORD-PRIOR-001 已完成。",
    )
    prior_summary = await summary_service.persist_thread_summary(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
    )

    current_run_id = await _insert_run(session, seeded_session, thread_id)
    operation_id = uuid.uuid4()
    await service.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        content="current-turn recent conversation_messages: 第一条。",
    )
    await service.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        content="current-turn recent conversation_messages: 第二条。",
    )
    tool_call = await service.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        trace_id="trace-prior-turn-context-window",
        tool_call_id=str(operation_id),
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"order_no": "ORD-CURRENT-001"},
        argument_summary_json={"order_no": "ORD-CURRENT-001"},
        redaction_policy_version="conversation_redaction.v1",
    )
    business_ref = BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="business_tool_service",
        resource_type="order",
        resource_id="ORD-CURRENT-001",
        resource_version=None,
        data_freshness_at=datetime.now(UTC),
        retrieved_at=datetime.now(UTC),
    )
    await service.append_tool_result(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        trace_id="trace-prior-turn-context-window",
        operation_id=operation_id,
        tool_call_id=str(operation_id),
        tool_call_record_id=tool_call.id,
        tool_result_id="tool-result-current-context",
        tool_name="get_order",
        result=ToolResultV2(
            status="success",
            data={"order_id": "ORD-CURRENT-001"},
            summary="Current turn safe tool prompt_summary for ORD-CURRENT-001.",
            source_system="business_tool_service",
            data_freshness_at=datetime.now(UTC),
            policy_evidence_refs=[],
            business_fact_refs=[business_ref],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=7,
            audit_ref="audit/tool-result/ORD-CURRENT-001",
        ),
    )

    context = await service.load_prompt_context(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        max_recent_messages=2,
    )

    assert context.latest_thread_summary is not None
    assert context.latest_thread_summary.id == prior_summary.id
    assert "ORD-PRIOR-001" in (context.latest_thread_summary.summary_text or "")
    assert [message.content for message in context.recent_messages] == [
        "current-turn recent conversation_messages: 第一条。",
        "current-turn recent conversation_messages: 第二条。",
    ]
    assert len(context.recent_messages) == 2
    assert len(context.tool_prompt_summaries) == 1
    assert "ORD-CURRENT-001" in (context.tool_prompt_summaries[0].prompt_summary or "")


@pytest.mark.asyncio
async def test_agent_runs_prompt_context_loads_prior_summary_recent_messages_and_tool_summaries(
    session: AsyncSession, seeded_session: dict
) -> None:
    from src.conversation.repository import ConversationRepository
    from src.conversation.service import ConversationService
    from src.memory.thread_summary import ThreadRollingSummaryService
    from src.tools.contracts import BusinessFactRefV1, ToolResultV2

    repository = ConversationRepository(session)
    service = ConversationService(repository)
    summary_service = ThreadRollingSummaryService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-agent-runs-prompt-context"
    prior_run_id = await _insert_run(session, seeded_session, thread_id)

    await service.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
        content="prior agent-runs turn: 查询 ORD-AGENT-PRIOR。",
    )
    await service.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
        content="关键决策：ORD-AGENT-PRIOR 已核实，后续只需继续同一 thread。",
    )
    prior_summary = await summary_service.persist_thread_summary(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
    )

    current_run_id = await _insert_run(session, seeded_session, thread_id)
    await service.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        content="agent-runs follow-up: 继续查这个订单 ORD-AGENT-CURRENT。",
    )
    operation_id = uuid.uuid4()
    tool_call = await service.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        trace_id="trace-agent-runs-prompt-context",
        tool_call_id=str(operation_id),
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"order_no": "ORD-AGENT-CURRENT", "raw_payload": "secret"},
        argument_summary_json={"order_no": "ORD-AGENT-CURRENT", "omitted": ["raw_payload"]},
        redaction_policy_version="conversation_redaction.v1",
    )
    business_ref = BusinessFactRefV1(
        tenant_id=str(tenant_id),
        source_system="business_tool_service",
        resource_type="order",
        resource_id="ORD-AGENT-CURRENT",
        resource_version=None,
        data_freshness_at=datetime.now(UTC),
        retrieved_at=datetime.now(UTC),
    )
    await service.append_tool_result(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        trace_id="trace-agent-runs-prompt-context",
        operation_id=operation_id,
        tool_call_id=str(operation_id),
        tool_call_record_id=tool_call.id,
        tool_result_id="tool-result-agent-runs-prompt-context",
        tool_name="get_order",
        result=ToolResultV2(
            status="success",
            data={
                "order_id": "ORD-AGENT-CURRENT",
                "raw_payload": {"secret": "must-not-enter-prompt-context"},
                "private_reasoning": "hidden",
                "approval_authority_body": {"decision": "approve"},
                "debug_trace": "debug-only",
            },
            summary="Prompt-safe get_order summary for ORD-AGENT-CURRENT.",
            source_system="business_tool_service",
            data_freshness_at=datetime.now(UTC),
            policy_evidence_refs=[],
            business_fact_refs=[business_ref],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=6,
            audit_ref="audit/tool-result/ORD-AGENT-CURRENT",
        ),
        raw_result_ref="raw-result://raw_payload/private_reasoning/secret",
        raw_result_hash="sha256:agentrunpromptcontext",
    )
    stored_tool_result = (
        await session.execute(
            select(ToolResultRecord).where(
                ToolResultRecord.tool_result_id == "tool-result-agent-runs-prompt-context"
            )
        )
    ).scalar_one()
    stored_tool_result.summary = "raw_payload private_reasoning approval_authority_body debug_trace secret"
    await session.flush()

    context = await service.load_prompt_context(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        max_recent_messages=4,
    )
    thread = await repository.get_thread(tenant_id=tenant_id, user_id=user_id, thread_id=thread_id)

    assert context.latest_thread_summary is not None
    assert context.latest_thread_summary.id == prior_summary.id
    assert context.latest_thread_summary.tenant_id == tenant_id
    assert context.latest_thread_summary.conversation_thread_id == thread.id
    assert context.recent_messages
    assert context.tool_prompt_summaries
    assert all(message.tenant_id == tenant_id for message in context.recent_messages)
    assert all(message.thread_id == thread_id for message in context.recent_messages)
    assert all(result.tenant_id == tenant_id for result in context.tool_prompt_summaries)
    assert all(result.thread_id == thread_id for result in context.tool_prompt_summaries)

    prompt_safe_surface = "\n".join(
        [
            context.latest_thread_summary.summary_text or "",
            *[message.content for message in context.recent_messages],
            *[result.prompt_summary or "" for result in context.tool_prompt_summaries],
        ]
    )
    assert "ORD-AGENT-PRIOR" in prompt_safe_surface
    assert "ORD-AGENT-CURRENT" in prompt_safe_surface
    assert "Prompt-safe get_order summary" in prompt_safe_surface
    for forbidden in ("raw_payload", "private_reasoning", "approval_authority_body", "debug_trace", "secret"):
        assert forbidden not in prompt_safe_surface


@pytest.mark.asyncio
async def test_append_or_get_run_role_messages_are_idempotent(session: AsyncSession, seeded_session: dict) -> None:
    from src.conversation.repository import ConversationRepository
    from src.conversation.service import ConversationService

    repository = ConversationRepository(session)
    service = ConversationService(repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-agent-runs-run-role-idempotent"
    run_id = await _insert_run(session, seeded_session, thread_id)

    first_user = await service.append_or_get_user_message_for_run(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="agent-runs user message should be inserted once",
        prompt_template_version="agent_runs.request.v1",
        prompt_block_hashes_json=["sha256:user-message"],
        context_snapshot_ref="context_snapshot/agent-runs/idempotent",
    )
    second_user = await service.append_or_get_user_message_for_run(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="retry should return the existing user message",
        prompt_template_version="agent_runs.request.v1",
        prompt_block_hashes_json=["sha256:user-message-retry"],
        context_snapshot_ref="context_snapshot/agent-runs/idempotent-retry",
    )
    first_assistant = await service.append_or_get_assistant_message_for_run(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="assistant final response should be inserted once",
    )
    second_assistant = await service.append_or_get_assistant_message_for_run(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        content="retry should return the existing assistant message",
    )

    assert second_user.message_id == first_user.message_id
    assert second_assistant.message_id == first_assistant.message_id
    user_count = await session.scalar(
        select(func.count())
        .select_from(ConversationMessage)
        .where(
            ConversationMessage.tenant_id == tenant_id,
            ConversationMessage.run_id == run_id,
            ConversationMessage.role == "user",
            ConversationMessage.deleted_at.is_(None),
        )
    )
    assistant_count = await session.scalar(
        select(func.count())
        .select_from(ConversationMessage)
        .where(
            ConversationMessage.tenant_id == tenant_id,
            ConversationMessage.run_id == run_id,
            ConversationMessage.role == "assistant",
            ConversationMessage.deleted_at.is_(None),
        )
    )
    assert user_count == 1
    assert assistant_count == 1


@pytest.mark.asyncio
async def test_load_prompt_context_is_user_scoped_within_tenant(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    from src.conversation.repository import ConversationRepository
    from src.conversation.service import ConversationService
    from src.memory.thread_summary import ThreadRollingSummaryService

    repository = ConversationRepository(session)
    service = ConversationService(repository)
    summary_service = ThreadRollingSummaryService(repository)
    tenant_id = seeded_session["tenant"].id
    support_user_id = seeded_session["users"]["cs_zhang"].id
    merchant_user_id = seeded_session["users"]["merchant_wang"].id
    thread_id = "shared-thread-id-user-scope"

    support_run_id = await _insert_run(session, seeded_session, thread_id, user_key="cs_zhang")
    await service.append_user_message(
        tenant_id=tenant_id,
        user_id=support_user_id,
        thread_id=thread_id,
        run_id=support_run_id,
        content="support user secret ORD-SUPPORT-ONLY.",
    )
    await service.append_assistant_message(
        tenant_id=tenant_id,
        user_id=support_user_id,
        thread_id=thread_id,
        run_id=support_run_id,
        content="support-only answer.",
    )
    await summary_service.persist_thread_summary(
        tenant_id=tenant_id,
        user_id=support_user_id,
        thread_id=thread_id,
        run_id=support_run_id,
    )

    merchant_run_id = await _insert_run(session, seeded_session, thread_id, user_key="merchant_wang")
    await service.append_user_message(
        tenant_id=tenant_id,
        user_id=merchant_user_id,
        thread_id=thread_id,
        run_id=merchant_run_id,
        content="merchant user message ORD-MERCHANT-ONLY.",
    )

    merchant_context = await service.load_prompt_context(
        tenant_id=tenant_id,
        user_id=merchant_user_id,
        thread_id=thread_id,
        run_id=merchant_run_id,
        max_recent_messages=4,
    )

    assert merchant_context.latest_thread_summary is None
    assert [message.content for message in merchant_context.recent_messages] == [
        "merchant user message ORD-MERCHANT-ONLY."
    ]
    serialized = "\n".join(message.content for message in merchant_context.recent_messages)
    assert "ORD-SUPPORT-ONLY" not in serialized
