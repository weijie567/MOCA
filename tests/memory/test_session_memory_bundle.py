from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.db.models import AgentRun, ToolResultRecord
from src.memory.repository import SessionMemoryRepository
from src.memory.schemas import SessionMemoryView, SessionMemoryWriteCandidate, SessionSlotV1, SlotContinuityMemoryView
from src.memory.service import MemoryService
from src.memory.session_bundle import SessionMemoryBundleService
from src.memory.thread_summary import ThreadRollingSummaryService
from src.tools.contracts import BusinessFactRefV1, ToolResultV2


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


def _slot(value: str, run_id: uuid.UUID) -> SessionSlotV1:
    now = datetime.now(UTC)
    return SessionSlotV1(
        value=value,
        source="explicit_user",
        source_run_id=str(run_id),
        updated_at=now,
        expires_at=now + timedelta(minutes=30),
        compatible_intents=["refund_troubleshooting"],
    )


@pytest.mark.asyncio
async def test_session_memory_bundle_facade_loads_all_short_term_surfaces(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    conversation_repository = ConversationRepository(session)
    conversation_service = ConversationService(conversation_repository)
    memory_service = MemoryService(SessionMemoryRepository(session))
    bundle_service = SessionMemoryBundleService(
        conversation_service=conversation_service,
        memory_service=memory_service,
    )
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-session-memory-bundle"

    prior_run_id = await _insert_run(session, seeded_session, thread_id)
    await conversation_service.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
        content="prior turn: 查询 ORD-BUNDLE-PRIOR。",
    )
    await conversation_service.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
        content="关键决策：ORD-BUNDLE-PRIOR 已确认继续跟进。",
    )
    prior_summary = await ThreadRollingSummaryService(conversation_repository).persist_thread_summary(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
    )

    current_run_id = await _insert_run(session, seeded_session, thread_id)
    await conversation_service.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        content="follow-up: 继续查这个订单 ORD-BUNDLE-CURRENT。",
    )
    operation_id = uuid.uuid4()
    tool_call = await conversation_service.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        trace_id="trace-session-memory-bundle",
        tool_call_id=str(operation_id),
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"order_no": "ORD-BUNDLE-CURRENT", "raw_payload": "secret"},
        argument_summary_json={"order_no": "ORD-BUNDLE-CURRENT", "omitted": ["raw_payload"]},
        redaction_policy_version="conversation_redaction.v1",
    )
    await conversation_service.append_tool_result(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        trace_id="trace-session-memory-bundle",
        operation_id=operation_id,
        tool_call_id=str(operation_id),
        tool_call_record_id=tool_call.id,
        tool_result_id="tool-result-session-memory-bundle",
        tool_name="get_order",
        result=ToolResultV2(
            status="success",
            data={"order_id": "ORD-BUNDLE-CURRENT", "raw_payload": {"secret": "hidden"}},
            summary="Prompt-safe get_order summary for ORD-BUNDLE-CURRENT.",
            source_system="business_tool_service",
            data_freshness_at=datetime.now(UTC),
            policy_evidence_refs=[],
            business_fact_refs=[
                BusinessFactRefV1(
                    tenant_id=str(tenant_id),
                    source_system="business_tool_service",
                    resource_type="order",
                    resource_id="ORD-BUNDLE-CURRENT",
                    resource_version=None,
                    data_freshness_at=datetime.now(UTC),
                    retrieved_at=datetime.now(UTC),
                )
            ],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=6,
            audit_ref="audit/tool-result/ORD-BUNDLE-CURRENT",
        ),
        raw_result_ref="raw-result://raw_payload/private_reasoning/secret",
        raw_result_hash="sha256:sessionmemorybundle",
    )
    stored_tool_result = (
        await session.execute(select(ToolResultRecord).where(ToolResultRecord.tool_result_id == "tool-result-session-memory-bundle"))
    ).scalar_one()
    stored_tool_result.summary = "raw_payload private_reasoning approval_authority_body debug_trace secret"
    await memory_service.write_session_memory(
        SessionMemoryWriteCandidate(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            run_id=current_run_id,
            explicit_slots={"order_id": _slot("ORD-BUNDLE-CURRENT", current_run_id)},
            last_intent="refund_troubleshooting",
            session_summary="slot continuity summary",
        )
    )

    bundle = await bundle_service.load_session_memory_bundle(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=current_run_id,
        current_intent="refund_troubleshooting",
        max_recent_messages=4,
    )

    assert bundle.rolling_summary is not None
    assert prior_summary is not None
    assert bundle.rolling_summary.summary_id == str(prior_summary.id)
    assert "ORD-BUNDLE-PRIOR" in bundle.rolling_summary.summary_text
    assert [message.content for message in bundle.recent_messages][-1] == "follow-up: 继续查这个订单 ORD-BUNDLE-CURRENT。"
    assert bundle.tool_summaries[0].tool_call_id == str(operation_id)
    assert bundle.tool_summaries[0].tool_name == "get_order"
    assert "Prompt-safe get_order summary" in bundle.tool_summaries[0].prompt_summary
    assert bundle.slot_continuity.active_slots["order_id"] == "ORD-BUNDLE-CURRENT"
    assert bundle.slot_continuity.slot_metadata["order_id"]["source"] == "trusted_session_memory"

    serialized = json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False)
    assert "rolling_summary" in serialized
    assert "recent_messages" in serialized
    assert "tool_summaries" in serialized
    assert "slot_continuity" in serialized
    for forbidden in ("raw_payload", "private_reasoning", "approval_authority_body", "debug_trace", "secret"):
        assert forbidden not in serialized


def test_slot_continuity_view_alias_keeps_existing_session_memory_contract() -> None:
    assert SlotContinuityMemoryView is SessionMemoryView
