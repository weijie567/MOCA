from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from types import SimpleNamespace
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


@pytest.mark.asyncio
async def test_session_memory_bundle_derives_policy_hints_from_tool_summaries() -> None:
    class FakeConversationService:
        async def load_prompt_context(self, **kwargs):
            return SimpleNamespace(
                latest_thread_summary=None,
                recent_messages=[],
                tool_prompt_summaries=[
                    SimpleNamespace(
                        id="tool-record-1",
                        tool_result_id="tool-result-1",
                        tool_call_id="tool-call-1",
                        status="success",
                        prompt_summary="Prompt-safe policy lookup summary.",
                        policy_evidence_refs_json=[
                            {
                                "schema_version": "evidence_ref.v1",
                                "tenant_id": "tenant-should-not-copy",
                                "evidence_id": "evidence-should-not-copy",
                                "doc_key": "refund_policy",
                                "chunk_id": "chunk-1",
                                "policy_version": "v1",
                                "text_hash": "hash-should-not-copy",
                                "retrieved_at": "2026-01-01T00:00:00Z",
                            }
                        ],
                    )
                ],
            )

    class FakeMemoryService:
        async def load_session_memory(self, *args, **kwargs):
            return SessionMemoryView(
                source="postgres_session_memory",
                continuity_claimed=False,
                active_slots={},
                slot_metadata={},
            )

    bundle = await SessionMemoryBundleService(
        conversation_service=FakeConversationService(),  # type: ignore[arg-type]
        memory_service=FakeMemoryService(),  # type: ignore[arg-type]
    ).load_session_memory_bundle(
        tenant_id="tenant-1",
        user_id="user-1",
        thread_id="thread-1",
        run_id="run-1",
        current_intent="policy_qa",
    )

    assert bundle.policy_topic_hints == ["refund_policy@v1"]
    assert bundle.prior_policy_mention_refs == [
        {
            "doc_key": "refund_policy",
            "chunk_id": "chunk-1",
            "policy_version": "v1",
            "tool_result_id": "tool-result-1",
        }
    ]
    serialized_refs = json.dumps(bundle.prior_policy_mention_refs, ensure_ascii=False)
    for forbidden in ("schema_version", "evidence_id", "tenant_id", "text_hash", "retrieved_at"):
        assert forbidden not in serialized_refs


@pytest.mark.asyncio
async def test_session_memory_bundle_serializes_policy_refs_as_hints_only() -> None:
    class FakeConversationService:
        async def load_prompt_context(self, **kwargs):
            return SimpleNamespace(
                latest_thread_summary=None,
                recent_messages=[],
                tool_prompt_summaries=[
                    SimpleNamespace(
                        id="tool-record-policy-hint",
                        tool_result_id="tool-result-policy-hint",
                        tool_call_id="tool-call-policy-hint",
                        status="success",
                        prompt_summary="Prompt-safe policy lookup summary.",
                        policy_evidence_refs_json=[
                            {
                                "schema_version": "evidence_ref.v1",
                                "tenant_id": "tenant-must-not-copy",
                                "evidence_id": "policy/refund_policy/chunk-1@v1",
                                "doc_key": "refund_policy",
                                "chunk_id": "chunk-1",
                                "policy_version": "v1",
                                "text_hash": "hash-must-not-copy",
                                "retrieved_at": "2026-01-01T00:00:00Z",
                                "body_text": "raw policy body must not enter session memory",
                            }
                        ],
                    )
                ],
            )

    class FakeMemoryService:
        async def load_session_memory(self, *args, **kwargs):
            return SessionMemoryView(
                source="postgres_session_memory",
                continuity_claimed=False,
                active_slots={},
                slot_metadata={},
            )

    bundle = await SessionMemoryBundleService(
        conversation_service=FakeConversationService(),  # type: ignore[arg-type]
        memory_service=FakeMemoryService(),  # type: ignore[arg-type]
    ).load_session_memory_bundle(
        tenant_id="tenant-1",
        user_id="user-1",
        thread_id="thread-1",
        run_id="run-1",
        current_intent="policy_qa",
    )

    assert bundle.policy_topic_hints == ["refund_policy@v1"]
    assert bundle.prior_policy_mention_refs == [
        {
            "doc_key": "refund_policy",
            "chunk_id": "chunk-1",
            "policy_version": "v1",
            "tool_result_id": "tool-result-policy-hint",
        }
    ]
    serialized = json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False)
    assert "policy_topic_hints" in serialized
    assert "prior_policy_mention_refs" in serialized
    for forbidden in (
        "evidence_id",
        "tenant-must-not-copy",
        "text_hash",
        "retrieved_at",
        "approval_authority_body",
        "action_authorization",
        "replay_event",
        "raw policy body must not enter session memory",
    ):
        assert forbidden not in serialized


def test_session_context_memory_projection_wraps_session_memory_bundle() -> None:
    from src.memory.schemas import SessionContextBundle, SessionContextMemory

    run_id = uuid.uuid4()
    slot_continuity = SessionMemoryView(
        source="postgres_session_memory",
        continuity_claimed=True,
        active_slots={"order_id": "ORD-CONTEXT-PROJECTION"},
        slot_metadata={"order_id": {"source": "trusted_session_memory"}},
        version=7,
    )
    legacy_bundle = {
        "schema_version": "session_memory_bundle.v1",
        "source": "session_memory_bundle",
        "tenant_id": "tenant-memory-boundary",
        "user_id": "user-memory-boundary",
        "thread_id": "thread-memory-boundary",
        "run_id": str(run_id),
        "rolling_summary": {
            "summary_id": "summary-context-projection",
            "summary_text": "rolling summary keeps ORD-CONTEXT-PROJECTION continuity",
        },
        "recent_messages": [
            {
                "message_id": "message-context-projection",
                "run_id": str(run_id),
                "message_index": 1,
                "role": "user",
                "content": "继续刚才那笔 ORD-CONTEXT-PROJECTION。",
            }
        ],
        "tool_summaries": [
            {
                "tool_result_record_id": "tool-summary-context-projection",
                "tool_result_id": "tool-result-context-projection",
                "run_id": str(run_id),
                "tool_call_id": "tool-call-context-projection",
                "tool_name": "get_order",
                "status": "success",
                "prompt_summary": "Prompt-safe order summary for ORD-CONTEXT-PROJECTION.",
            }
        ],
        "slot_continuity": slot_continuity.model_dump(mode="json"),
        "fallback_reasons": {},
    }

    context_memory = SessionContextMemory.model_validate(legacy_bundle)
    context_bundle = SessionContextBundle.model_validate(
        {"schema_version": "session_context_bundle.v1", "session_context": context_memory}
    )
    serialized = json.dumps(context_bundle.model_dump(mode="json"), ensure_ascii=False)

    assert context_bundle.schema_version == "session_context_bundle.v1"
    assert context_bundle.session_context.rolling_summary.summary_text.startswith("rolling summary")
    assert context_bundle.session_context.recent_messages[0].content == "继续刚才那笔 ORD-CONTEXT-PROJECTION。"
    assert context_bundle.session_context.tool_summaries[0].tool_name == "get_order"
    assert context_bundle.session_context.slot_continuity.active_slots["order_id"] == "ORD-CONTEXT-PROJECTION"
    assert "SessionContinuityStore" not in serialized
