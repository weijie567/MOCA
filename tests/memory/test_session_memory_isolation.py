from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import uuid
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.db.models import AgentRun, ToolResultRecord
from src.memory.repository import SessionMemoryRepository
from src.memory.schemas import SessionMemoryWriteCandidate, SessionSlotV1
from src.memory.service import MemoryService
from src.memory.thread_summary import ThreadRollingSummaryService
from src.platform.trusted_context import MerchantScopeV1, TrustedContext
from src.tools.contracts import BusinessFactRefV1, ToolResultV2


def _slot(
    value: str,
    *,
    expires_at: datetime | None = None,
    intents: list[str] | None = None,
) -> SessionSlotV1:
    now = datetime.now(UTC)
    return SessionSlotV1(
        value=value,
        source="explicit_user",
        source_run_id=str(uuid4()),
        updated_at=now,
        expires_at=expires_at or now + timedelta(minutes=30),
        compatible_intents=intents or ["refund_troubleshooting"],
    )


def _envelope(slots: dict[str, SessionSlotV1]) -> dict:
    return {
        "schema_version": "session_slots.v1",
        "slots": {key: slot.model_dump(mode="json") for key, slot in slots.items()},
    }


async def _insert_run(session: AsyncSession, seeded_session: dict, *, thread_id: str) -> uuid.UUID:
    run_id = uuid.uuid4()
    user = seeded_session["users"]["cs_zhang"]
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=thread_id,
            input_query="session context merchant isolation",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


def _trusted_context(seeded_session: dict, *, merchant_id: str, thread_id: str, run_id: uuid.UUID) -> TrustedContext:
    user = seeded_session["users"]["cs_zhang"]
    return TrustedContext(
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        role=user.role,
        permissions=["tool:get_order", "tool:get_refund_case"],
        merchant_scope=MerchantScopeV1(merchant_ids=[merchant_id]),
        thread_id=thread_id,
        run_id=str(run_id),
        trace_id="trace-session-context-merchant-isolation",
    )


def _session_context_load():
    from src.agent.nodes.session_context_load import session_context_load

    return session_context_load


async def _seed_merchant_a_prompt_context(
    session: AsyncSession,
    seeded_session: dict,
    *,
    thread_id: str,
    merchant_a: str,
) -> uuid.UUID:
    conversation_repository = ConversationRepository(session)
    conversation_service = ConversationService(conversation_repository)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    prior_run_id = await _insert_run(session, seeded_session, thread_id=thread_id)
    await conversation_service.append_user_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
        content=f"merchant-a recent message contains {merchant_a} and ORD-MERCHANT-A-SESSION.",
    )
    await conversation_service.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
        content="merchant-a assistant recent message contains RF-MERCHANT-A-SESSION.",
    )
    await ThreadRollingSummaryService(conversation_repository).persist_thread_summary(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
    )
    operation_id = uuid.uuid4()
    tool_call = await conversation_service.append_tool_call(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
        trace_id="trace-merchant-a-tool-summary",
        tool_call_id=str(operation_id),
        tool_name="get_order",
        caller_node="investigate",
        operation_id=operation_id,
        attempt=1,
        arguments={"order_no": "ORD-MERCHANT-A-SESSION"},
        argument_summary_json={"order_no": "ORD-MERCHANT-A-SESSION"},
        redaction_policy_version="conversation_redaction.v1",
    )
    await conversation_service.append_tool_result(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        run_id=prior_run_id,
        trace_id="trace-merchant-a-tool-summary",
        operation_id=operation_id,
        tool_call_id=str(operation_id),
        tool_call_record_id=tool_call.id,
        tool_result_id="tool-result-merchant-a-session",
        tool_name="get_order",
        result=ToolResultV2(
            status="success",
            data={"order_id": "ORD-MERCHANT-A-SESSION", "merchant_id": merchant_a},
            summary="Merchant A tool summary must be filtered for ORD-MERCHANT-A-SESSION.",
            source_system="business_tool_service",
            data_freshness_at=datetime.now(UTC),
            policy_evidence_refs=[],
            business_fact_refs=[
                BusinessFactRefV1(
                    tenant_id=str(tenant_id),
                    source_system="business_tool_service",
                    resource_type="order",
                    resource_id="ORD-MERCHANT-A-SESSION",
                    resource_version=None,
                    data_freshness_at=datetime.now(UTC),
                    retrieved_at=datetime.now(UTC),
                )
            ],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=3,
            audit_ref="audit/merchant-a-session-tool",
        ),
        raw_result_ref=None,
        raw_result_hash="sha256:merchantasessiontool",
    )
    stored = (
        await session.execute(
            select(ToolResultRecord).where(ToolResultRecord.tool_result_id == "tool-result-merchant-a-session")
        )
    ).scalar_one()
    stored.prompt_summary = "merchant-a tool_summaries text contains ORD-MERCHANT-A-SESSION and RF-MERCHANT-A-SESSION."
    await MemoryService(SessionMemoryRepository(session)).write_session_memory(
        candidate=SessionMemoryWriteCandidate(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            run_id=prior_run_id,
            explicit_slots={
                "merchant_id": _slot(merchant_a),
                "order_id": _slot("ORD-MERCHANT-A-SESSION"),
                "refund_case_id": _slot("RF-MERCHANT-A-SESSION"),
            },
            last_intent="refund_troubleshooting",
            session_summary="merchant-a active_slots rolling_summary ORD-MERCHANT-A-SESSION",
        )
    )
    return prior_run_id


@pytest.mark.asyncio
async def test_load_session_memory_is_scoped_to_same_tenant_user_thread(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    other_user = seeded_session["users"]["other_support"]
    repository = SessionMemoryRepository(session)
    await repository.insert_active(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id="thread-isolation",
        active_slots_json=_envelope({"order_id": _slot("ORD-1001")}),
        session_summary="same thread summary",
        unresolved_questions_json=["same thread question"],
        last_intent="refund_troubleshooting",
        last_business_context_refs_json={"order": "ORD-1001"},
    )
    service = MemoryService(repository)

    same_scope = await service.load_session_memory(
        user.tenant_id,
        user.id,
        "thread-isolation",
        current_intent="refund_troubleshooting",
    )
    different_thread = await service.load_session_memory(
        user.tenant_id,
        user.id,
        "thread-other",
        current_intent="refund_troubleshooting",
    )
    different_user = await service.load_session_memory(
        user.tenant_id,
        other_user.id,
        "thread-isolation",
        current_intent="refund_troubleshooting",
    )
    different_tenant = await service.load_session_memory(
        seeded_session["other_tenant"].id,
        user.id,
        "thread-isolation",
        current_intent="refund_troubleshooting",
    )

    assert same_scope.continuity_claimed is True
    assert same_scope.active_slots == {"order_id": "ORD-1001"}
    assert same_scope.slot_metadata["order_id"]["tenant_id"] == str(user.tenant_id)
    assert same_scope.slot_metadata["order_id"]["user_id"] == str(user.id)
    assert same_scope.slot_metadata["order_id"]["thread_id"] == "thread-isolation"
    assert different_thread.continuity_claimed is False
    assert different_thread.active_slots == {}
    assert different_user.continuity_claimed is False
    assert different_user.active_slots == {}
    assert different_tenant.continuity_claimed is False
    assert different_tenant.active_slots == {}


@pytest.mark.asyncio
async def test_load_session_memory_filters_expired_and_incompatible_slots(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    repository = SessionMemoryRepository(session)
    await repository.insert_active(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id="thread-slot-filter",
        active_slots_json=_envelope(
            {
                "order_id": _slot("ORD-FRESH"),
                "refund_case_id": _slot("RF-EXPIRED", expires_at=datetime.now(UTC) - timedelta(minutes=1)),
                "ticket_id": _slot("TKT-INCOMPATIBLE", intents=["complaint_escalation"]),
            }
        ),
    )

    view = await MemoryService(repository).load_session_memory(
        user.tenant_id,
        user.id,
        "thread-slot-filter",
        current_intent="refund_troubleshooting",
    )

    assert view.active_slots == {"order_id": "ORD-FRESH"}
    assert set(view.slot_metadata) == {"order_id"}


@pytest.mark.asyncio
async def test_load_session_memory_reuses_business_id_slots_across_related_followup_intents(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    repository = SessionMemoryRepository(session)
    await repository.insert_active(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id="thread-related-followup",
        active_slots_json=_envelope(
            {
                "order_id": _slot("ORD-STATUS", intents=["order_status_inquiry"]),
                "action_type": _slot("inquiry", intents=["order_status_inquiry"]),
            }
        ),
    )

    view = await MemoryService(repository).load_session_memory(
        user.tenant_id,
        user.id,
        "thread-related-followup",
        current_intent="refund_troubleshooting",
    )

    assert view.active_slots == {"order_id": "ORD-STATUS"}
    assert view.slot_metadata["order_id"]["intent_compatible"] is True


@pytest.mark.asyncio
async def test_session_context_excludes_cross_merchant_slots_summary_messages_and_tool_summaries(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    thread_id = "thread-session-context-cross-merchant"
    merchant_a = str(seeded_session["merchant"].id)
    merchant_b = str(seeded_session["second_merchant"].id)
    await _seed_merchant_a_prompt_context(session, seeded_session, thread_id=thread_id, merchant_a=merchant_a)
    current_run_id = await _insert_run(session, seeded_session, thread_id=thread_id)
    trusted_context = _trusted_context(seeded_session, merchant_id=merchant_b, thread_id=thread_id, run_id=current_run_id)

    result = await _session_context_load()(
        {
            "tenant_id": trusted_context.tenant_id,
            "user_id": trusted_context.user_id,
            "thread_id": thread_id,
            "current_run_id": str(current_run_id),
            "primary_intent": "refund_troubleshooting",
            "extracted_slots": {"merchant_id": merchant_b, "order_id": "ORD-MERCHANT-B-CURRENT"},
            "trace_steps": [],
        },
        {"configurable": {"session": session, "trusted_context": trusted_context}},
    )

    serialized = json.dumps(
        {
            "session_context": result["session_context"],
            "session_context_bundle": result["session_context_bundle"],
        },
        ensure_ascii=False,
    )
    assert "ORD-MERCHANT-B-CURRENT" in serialized
    for forbidden in (
        merchant_a,
        "ORD-MERCHANT-A-SESSION",
        "RF-MERCHANT-A-SESSION",
        "merchant-a active_slots rolling_summary",
        "merchant-a recent message",
        "merchant-a assistant recent message",
        "merchant-a tool_summaries text",
    ):
        assert forbidden not in serialized
    assert "cross_merchant_session_context_filtered" in result["session_context_load_status"]["filter_reasons"]


@pytest.mark.asyncio
async def test_session_context_filters_production_trusted_context_dict_without_explicit_merchant(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    thread_id = "thread-session-context-production-trusted-dict"
    merchant_a = str(seeded_session["merchant"].id)
    merchant_b = str(seeded_session["second_merchant"].id)
    await _seed_merchant_a_prompt_context(session, seeded_session, thread_id=thread_id, merchant_a=merchant_a)
    current_run_id = await _insert_run(session, seeded_session, thread_id=thread_id)
    trusted_context = _trusted_context(seeded_session, merchant_id=merchant_b, thread_id=thread_id, run_id=current_run_id)

    result = await _session_context_load()(
        {
            "tenant_id": trusted_context.tenant_id,
            "user_id": trusted_context.user_id,
            "thread_id": thread_id,
            "current_run_id": str(current_run_id),
            "primary_intent": "refund_troubleshooting",
            "trace_steps": [],
        },
        {"configurable": {"session": session, "trusted_context": trusted_context.model_dump(mode="json")}},
    )

    serialized = json.dumps(
        {
            "session_context": result["session_context"],
            "session_context_bundle": result["session_context_bundle"],
        },
        ensure_ascii=False,
    )
    assert result["session_context"]["active_slots"] == {"merchant_id": merchant_b}
    for forbidden in (
        merchant_a,
        "ORD-MERCHANT-A-SESSION",
        "RF-MERCHANT-A-SESSION",
        "merchant-a active_slots rolling_summary",
        "merchant-a recent message",
        "merchant-a assistant recent message",
        "merchant-a tool_summaries text",
    ):
        assert forbidden not in serialized
    assert "cross_merchant_session_context_filtered" in result["session_context_load_status"]["filter_reasons"]
    assert "merchant_scope_denied" in result["session_context_load_status"]["filter_reasons"]


@pytest.mark.asyncio
async def test_session_context_does_not_let_merchant_a_active_slot_override_merchant_b_current_turn(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    thread_id = "thread-session-context-current-turn-wins"
    merchant_a = "merchant-a"
    merchant_b = "merchant-b"
    current_run_id = await _insert_run(session, seeded_session, thread_id=thread_id)
    await MemoryService(SessionMemoryRepository(session)).write_session_memory(
        candidate=SessionMemoryWriteCandidate(
            tenant_id=seeded_session["tenant"].id,
            user_id=seeded_session["users"]["cs_zhang"].id,
            thread_id=thread_id,
            run_id=current_run_id,
            explicit_slots={"merchant_id": _slot(merchant_a), "order_id": _slot("ORD-MERCHANT-A-SESSION")},
            last_intent="refund_troubleshooting",
            session_summary="merchant-a continuity should be dropped",
        )
    )
    trusted_context = _trusted_context(seeded_session, merchant_id=merchant_b, thread_id=thread_id, run_id=current_run_id)

    result = await _session_context_load()(
        {
            "tenant_id": trusted_context.tenant_id,
            "user_id": trusted_context.user_id,
            "thread_id": thread_id,
            "current_run_id": str(current_run_id),
            "primary_intent": "refund_troubleshooting",
            "extracted_slots": {"merchant_id": merchant_b},
            "trace_steps": [],
        },
        {"configurable": {"session": session, "trusted_context": trusted_context}},
    )

    assert result["session_context"]["active_slots"]["merchant_id"] == merchant_b
    assert result["session_context"]["active_slots"].get("order_id") != "ORD-MERCHANT-A-SESSION"
    assert "cross_merchant_session_context_filtered" in result["session_context_load_status"]["filter_reasons"]
