from __future__ import annotations

from datetime import UTC, datetime
from importlib import import_module
import json
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.conversation.repository import ConversationRepository
from src.db.models import AgentRun, ConversationSummary, LongTermMemory
from src.memory.long_term import LongTermMemoryService
from src.memory.repository import LongTermMemoryRepository, SessionMemoryRepository


RAW_TOOL_PAYLOAD_SHOULD_NOT_APPEAR = "RAW_TOOL_PAYLOAD_SHOULD_NOT_APPEAR"
FULL_POLICY_TEXT_SHOULD_NOT_APPEAR = "FULL_POLICY_TEXT_SHOULD_NOT_APPEAR"
APPROVAL_AUTHORITY_SHOULD_NOT_APPEAR = "APPROVAL_AUTHORITY_SHOULD_NOT_APPEAR"
ACTION_AUTHORITY_SHOULD_NOT_APPEAR = "ACTION_AUTHORITY_SHOULD_NOT_APPEAR"
REPLAY_DEBUG_BLOB_SHOULD_NOT_APPEAR = "REPLAY_DEBUG_BLOB_SHOULD_NOT_APPEAR"
EVIDENCE_REF_SHOULD_NOT_APPEAR = "EvidenceRefV1"


def _semantic_episode_module():
    return import_module("src.memory.semantic_episode")


async def _insert_run(session: AsyncSession, seeded_session: dict, thread_id: str) -> uuid.UUID:
    run_id = uuid.uuid4()
    user = seeded_session["users"]["cs_zhang"]
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=thread_id,
            input_query="semantic episode test",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


async def _semantic_summary(
    session: AsyncSession,
    seeded_session: dict,
    *,
    run_id: uuid.UUID,
    thread_id: str,
) -> ConversationSummary:
    user = seeded_session["users"]["cs_zhang"]
    repository = ConversationRepository(session)
    thread = await repository.get_or_create_thread(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id=thread_id,
        case_id="case-semantic-episode",
    )
    summary = ConversationSummary(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        thread_id=thread_id,
        conversation_thread_id=thread.id,
        case_id=thread.case_id,
        summary_type="thread_rolling",
        source_message_ids_json=[],
        source_tool_result_ids_json=[],
        summary_text="Prompt-safe summary: refund dispute required logistics proof before compensation.",
        summary_json={
            "schema_version": "thread_rolling_summary.v1",
            "semantic_episode": {
                "cross_case_patterns": [
                    {
                        "text": "Repeated refund disputes improve when support asks for logistics proof first.",
                        "raw_payload": RAW_TOOL_PAYLOAD_SHOULD_NOT_APPEAR,
                    }
                ],
                "similar_cases": [
                    {
                        "summary": "Similar delayed-delivery cases were resolved after merchant uploaded receipt proof.",
                        "evidence_refs": [
                            {
                                "schema_version": EVIDENCE_REF_SHOULD_NOT_APPEAR,
                                "full_policy_text": FULL_POLICY_TEXT_SHOULD_NOT_APPEAR,
                            }
                        ],
                    }
                ],
                "strategy_hints": [
                    {
                        "hint": "Ask for carrier receipt before drafting any compensation response.",
                        "approval_authority_body": APPROVAL_AUTHORITY_SHOULD_NOT_APPEAR,
                    }
                ],
                "preference_candidates": [
                    {
                        "preference": "Merchant prefers concise refund updates with one next step.",
                        "action_authority_body": ACTION_AUTHORITY_SHOULD_NOT_APPEAR,
                    }
                ],
                "replay_debug_blob": REPLAY_DEBUG_BLOB_SHOULD_NOT_APPEAR,
            },
            "run_id": str(run_id),
        },
    )
    session.add(summary)
    await session.flush()
    return summary


def _project_candidates(summary: ConversationSummary, seeded_session: dict, *, run_id: uuid.UUID):
    module = _semantic_episode_module()
    merchant = seeded_session["merchant"]
    return module.project_semantic_episode_candidates(
        tenant_id=merchant.tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id=str(merchant.id),
        summaries=[summary],
        tool_prompt_summaries=["Prompt-safe tool summary: carrier receipt is missing."],
    )


def _project_payload(payload: dict, seeded_session: dict, *, run_id: uuid.UUID):
    module = _semantic_episode_module()
    merchant = seeded_session["merchant"]
    return module.project_semantic_episode_candidates(
        tenant_id=merchant.tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id=str(merchant.id),
        summaries=[type("Summary", (), {"summary_json": {"semantic_episode": payload}, "summary_text": ""})()],
    )


@pytest.mark.asyncio
async def test_semantic_episode_projection_creates_candidates_only(session: AsyncSession, seeded_session: dict) -> None:
    thread_id = "semantic-episode-candidates-only"
    run_id = await _insert_run(session, seeded_session, thread_id)
    summary = await _semantic_summary(session, seeded_session, run_id=run_id, thread_id=thread_id)

    candidates = _project_candidates(summary, seeded_session, run_id=run_id)

    assert {candidate.kind for candidate in candidates} == {"preference_candidate"}
    assert {candidate.source_type for candidate in candidates} == {"semantic_episode_candidate"}
    assert all(candidate.review_status == "needs_review" for candidate in candidates)
    assert all(
        candidate.to_long_term_memory_candidate().source_type == "semantic_episode_candidate"
        for candidate in candidates
    )
    assert all(candidate.to_long_term_memory_candidate().memory_kind == "preference" for candidate in candidates)
    persisted = await session.scalar(
        select(func.count()).select_from(LongTermMemory).where(LongTermMemory.tenant_id == seeded_session["tenant"].id)
    )
    assert persisted == 0


@pytest.mark.asyncio
async def test_semantic_episode_does_not_project_patterns_strategy_or_similar_cases_to_long_term(
    session: AsyncSession, seeded_session: dict
) -> None:
    run_id = await _insert_run(session, seeded_session, "semantic-episode-no-patterns")

    candidates = _project_payload(
        {
            "cross_case_patterns": [{"text": "Repeated refund disputes improve after proof collection."}],
            "similar_cases": [{"summary": "Similar cases used carrier receipt proof."}],
            "strategy_hints": [{"hint": "Ask for receipt before drafting compensation."}],
        },
        seeded_session,
        run_id=run_id,
    )

    assert candidates == []


@pytest.mark.asyncio
async def test_semantic_episode_candidate_requires_review_before_retrieval(
    session: AsyncSession, seeded_session: dict
) -> None:
    thread_id = "semantic-episode-review-required"
    run_id = await _insert_run(session, seeded_session, thread_id)
    summary = await _semantic_summary(session, seeded_session, run_id=run_id, thread_id=thread_id)
    candidate = _project_candidates(summary, seeded_session, run_id=run_id)[0]
    service = LongTermMemoryService(LongTermMemoryRepository(session))

    result = await service.write_memory(candidate.to_long_term_memory_candidate())
    row = await session.get(LongTermMemory, result.memory_id)
    retrieved = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=candidate.tenant_id,
        scope_type=candidate.scope_type,
        scope_id=candidate.scope_id,
    )

    assert result.status == "needs_review"
    assert result.review_status == "needs_review"
    assert row is not None
    assert row.review_status == "needs_review"
    assert retrieved == []


@pytest.mark.asyncio
async def test_semantic_episode_projection_does_not_modify_session_memory(
    session: AsyncSession, seeded_session: dict
) -> None:
    thread_id = "semantic-episode-session-memory-isolation"
    run_id = await _insert_run(session, seeded_session, thread_id)
    user = seeded_session["users"]["cs_zhang"]
    repository = SessionMemoryRepository(session)
    await repository.insert_active(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id=thread_id,
        active_slots_json={"schema_version": "session_slots.v1", "slots": {"order_no": {"value": "ORD-KEEP"}}},
        session_summary="existing session memory summary",
        unresolved_questions_json=["keep this unresolved question"],
        last_intent="refund_troubleshooting",
    )
    summary = await _semantic_summary(session, seeded_session, run_id=run_id, thread_id=thread_id)

    _project_candidates(summary, seeded_session, run_id=run_id)
    active = await repository.get_active(user.tenant_id, user.id, thread_id)
    row_count = await session.scalar(
        select(func.count()).where(
            LongTermMemory.tenant_id == user.tenant_id,
        )
    )

    assert active is not None
    assert active.session_summary == "existing session memory summary"
    assert active.unresolved_questions_json == ["keep this unresolved question"]
    assert active.last_intent == "refund_troubleshooting"
    assert active.active_slots_json["slots"]["order_no"]["value"] == "ORD-KEEP"
    assert row_count == 0


@pytest.mark.asyncio
async def test_semantic_episode_projection_output_is_prompt_safe(session: AsyncSession, seeded_session: dict) -> None:
    thread_id = "semantic-episode-prompt-safe"
    run_id = await _insert_run(session, seeded_session, thread_id)
    summary = await _semantic_summary(session, seeded_session, run_id=run_id, thread_id=thread_id)

    candidates = _project_candidates(summary, seeded_session, run_id=run_id)
    serialized = json.dumps(
        [candidate.model_dump(mode="json") for candidate in candidates],
        ensure_ascii=False,
        sort_keys=True,
    )

    assert "Prompt-safe tool summary" in serialized
    for forbidden in (
        RAW_TOOL_PAYLOAD_SHOULD_NOT_APPEAR,
        FULL_POLICY_TEXT_SHOULD_NOT_APPEAR,
        APPROVAL_AUTHORITY_SHOULD_NOT_APPEAR,
        ACTION_AUTHORITY_SHOULD_NOT_APPEAR,
        REPLAY_DEBUG_BLOB_SHOULD_NOT_APPEAR,
        EVIDENCE_REF_SHOULD_NOT_APPEAR,
        "raw_payload",
        "full_policy_text",
        "approval_authority_body",
        "action_authority_body",
        "replay_debug_blob",
    ):
        assert forbidden not in serialized
