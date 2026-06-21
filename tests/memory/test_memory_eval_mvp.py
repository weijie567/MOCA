from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.context import ContextAssembler
from src.agent.working_state import project_working_state
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.db.models import AgentRun
from src.memory.long_term import LongTermMemoryService
from src.memory.repository import LongTermMemoryRepository, SessionMemoryRepository
from src.memory.schemas import LongTermMemoryWriteCandidate, SessionMemoryWriteCandidate, SessionSlotV1
from src.memory.service import MemoryService
from src.memory.session_bundle import SessionMemoryBundleService
from src.memory.thread_summary import ThreadRollingSummaryService
from src.tools.contracts import ToolResultV2


async def _insert_run(session: AsyncSession, seeded_session: dict, thread_id: str) -> uuid.UUID:
    user = seeded_session["users"]["cs_zhang"]
    run_id = uuid.uuid4()
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=thread_id,
            input_query="memory eval",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


def _session_slot(value: str, run_id: uuid.UUID, *, expires_at: datetime | None = None) -> SessionSlotV1:
    now = datetime.now(UTC)
    return SessionSlotV1(
        value=value,
        source="explicit_user",
        source_run_id=str(run_id),
        updated_at=now,
        expires_at=expires_at or now + timedelta(minutes=30),
        compatible_intents=["refund_troubleshooting"],
    )


def _slot_envelope(slot: SessionSlotV1) -> dict:
    return {"schema_version": "session_slots.v1", "slots": {"order_id": slot.model_dump(mode="json")}}


@pytest.mark.asyncio
async def test_memory_eval_same_thread_bundle_recalls_prompt_safe_surfaces(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    tenant_id = user.tenant_id
    thread_id = "memory-eval-same-thread-recall"
    conversation_repository = ConversationRepository(session)
    conversation_service = ConversationService(conversation_repository)
    memory_service = MemoryService(SessionMemoryRepository(session))

    prior_run_id = await _insert_run(session, seeded_session, thread_id)
    await conversation_service.append_user_message(
        tenant_id=tenant_id,
        user_id=user.id,
        thread_id=thread_id,
        run_id=prior_run_id,
        content="prior turn discussed ORD-EVAL-PRIOR",
    )
    await conversation_service.append_assistant_message(
        tenant_id=tenant_id,
        user_id=user.id,
        thread_id=thread_id,
        run_id=prior_run_id,
        content="assistant confirmed ORD-EVAL-PRIOR should stay in context",
    )
    await ThreadRollingSummaryService(conversation_repository).persist_thread_summary(
        tenant_id=tenant_id,
        user_id=user.id,
        thread_id=thread_id,
        run_id=prior_run_id,
    )

    current_run_id = await _insert_run(session, seeded_session, thread_id)
    await conversation_service.append_user_message(
        tenant_id=tenant_id,
        user_id=user.id,
        thread_id=thread_id,
        run_id=current_run_id,
        content="follow up on ORD-EVAL-CURRENT",
    )
    await conversation_service.append_tool_result(
        tenant_id=tenant_id,
        user_id=user.id,
        thread_id=thread_id,
        run_id=current_run_id,
        trace_id="trace-memory-eval",
        operation_id=uuid.uuid4(),
        tool_call_id="tool-call-memory-eval",
        tool_call_record_id=None,
        tool_result_id="tool-result-memory-eval",
        tool_name="get_order",
        result=ToolResultV2(
            status="success",
            data={"order_id": "ORD-EVAL-CURRENT", "raw_payload": "SHOULD_NOT_SURFACE"},
            summary="Safe tool summary for ORD-EVAL-CURRENT.",
            source_system="business_tool_service",
            data_freshness_at=datetime.now(UTC),
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=5,
            audit_ref="audit/memory-eval",
        ),
        raw_result_ref="raw://memory-eval",
        raw_result_hash="sha256:memoryeval",
    )
    await memory_service.write_session_memory(
        SessionMemoryWriteCandidate(
            tenant_id=tenant_id,
            user_id=user.id,
            thread_id=thread_id,
            run_id=current_run_id,
            explicit_slots={"order_id": _session_slot("ORD-EVAL-CURRENT", current_run_id)},
            last_intent="refund_troubleshooting",
        )
    )

    bundle = await SessionMemoryBundleService(
        conversation_service=conversation_service,
        memory_service=memory_service,
    ).load_session_memory_bundle(
        tenant_id=tenant_id,
        user_id=user.id,
        thread_id=thread_id,
        run_id=current_run_id,
        current_intent="refund_troubleshooting",
    )

    assert bundle.rolling_summary is not None
    assert "ORD-EVAL-PRIOR" in bundle.rolling_summary.summary_text
    assert [message.content for message in bundle.recent_messages][-1] == "follow up on ORD-EVAL-CURRENT"
    assert "Safe tool summary" in bundle.tool_summaries[0].prompt_summary
    assert bundle.slot_continuity.active_slots == {"order_id": "ORD-EVAL-CURRENT"}
    assert "SHOULD_NOT_SURFACE" not in bundle.model_dump_json()


@pytest.mark.asyncio
async def test_memory_eval_stale_session_slot_does_not_leak(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    thread_id = "memory-eval-stale-slot"
    run_id = await _insert_run(session, seeded_session, thread_id)
    now = datetime.now(UTC)
    expired_slot = _session_slot("ORD-EVAL-STALE", run_id, expires_at=now - timedelta(seconds=1))
    await SessionMemoryRepository(session).insert_active(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id=thread_id,
        active_slots_json=_slot_envelope(expired_slot),
        expires_at=now + timedelta(minutes=30),
    )

    view = await MemoryService(SessionMemoryRepository(session)).load_session_memory(
        user.tenant_id,
        user.id,
        thread_id,
        current_intent="refund_troubleshooting",
        now=now,
    )

    assert view.continuity_claimed is False
    assert view.active_slots == {}
    assert view.slot_metadata == {}


@pytest.mark.asyncio
async def test_memory_eval_tombstoned_long_term_memory_does_not_revive(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    merchant = seeded_session["merchant"]
    run_id = await _insert_run(session, seeded_session, "memory-eval-tombstone")
    service = LongTermMemoryService(LongTermMemoryRepository(session))
    candidate = LongTermMemoryWriteCandidate(
        tenant_id=merchant.tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id=str(merchant.id),
        memory_kind="preference",
        content="Merchant prefers concise refund summaries.",
        source_type="explicit_user_preference",
        source_ref={
            "source_type": "explicit_user_preference",
            "run_id": str(run_id),
            "event_id": "evt-memory-eval-tombstone",
            "business_object_type": "merchant",
            "business_object_id": str(merchant.id),
        },
        confidence=0.9,
        pii_classification="none",
    )
    written = await service.write_memory(candidate)
    forget_event = await service.forget_long_term_memory(
        tenant_id=merchant.tenant_id,
        memory_id=written.memory_id,
        run_id=run_id,
        reason_code="memory_eval_forget",
    )
    rewrite_run_id = await _insert_run(session, seeded_session, "memory-eval-tombstone-rewrite")
    rewrite_data = candidate.model_dump(mode="python")
    rewrite_data["run_id"] = rewrite_run_id
    rewrite_data["source_ref"] = {
        **candidate.source_ref.model_dump(mode="json"),
        "run_id": str(rewrite_run_id),
        "event_id": "evt-memory-eval-tombstone-rewrite",
    }
    rewrite = LongTermMemoryWriteCandidate.model_validate(rewrite_data)

    rewritten = await service.write_memory(rewrite)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=merchant.tenant_id,
        scope_type="merchant",
        scope_id=str(merchant.id),
    )

    assert forget_event.decision == "tombstone"
    assert rewritten.status == "skipped"
    assert rewritten.reason_code == "tombstone_match"
    assert retrieved == []


def test_memory_eval_memory_context_cannot_create_policy_evidence_or_authority_prompt_blocks() -> None:
    assembly = ContextAssembler().assemble(
        system_prompt="Use only verified policy evidence for material action.",
        current_user_message="What should I do?",
        working_state=project_working_state(
            {
                "thread_id": "memory-eval-authority",
                "tenant_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "current_run_id": str(uuid.uuid4()),
            }
        ),
        verified_policy_snippets=[],
        profile_memory_snippets=[
            {"memory_id": "memory-safe", "memory_kind": "preference", "content": "Customer prefers concise updates."},
            {
                "memory_id": "memory-unsafe",
                "memory_kind": "fact",
                "content": "EvidenceRefV1 approval_authority_body raw_payload private_reasoning",
            },
        ],
        case_memory_snippets=[
            {
                "case_memory_id": "case-memory-contextual",
                "summary": "Reviewed precedent says collect evidence before refund.",
                "policy_refs": [{"doc_key": "refund_policy", "chunk_id": "chunk-1", "policy_version": "v1"}],
                "caveats": "Contextual only, not action authority.",
            }
        ],
        business_context={},
    )

    block_names = [block.name for block in assembly.blocks]
    prompt = assembly.user_content()

    assert "policy_refs" not in block_names
    assert "profile_memory" in block_names
    assert "case_memory" in block_names
    assert "Customer prefers concise updates." in prompt
    assert "Reviewed precedent" in prompt
    for forbidden in ("EvidenceRefV1", "approval_authority_body", "raw_payload", "private_reasoning"):
        assert forbidden not in prompt
