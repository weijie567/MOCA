from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun


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

    messages = await repository.list_messages(tenant_id=tenant_id, thread_id=thread_id)

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
    conversation_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in Path("src/conversation").glob("*.py")
    )

    assert "case_id" in migration_source
    assert "case_memories" not in migration_source
    assert "memory_tombstones" not in migration_source
    assert "embedding" not in migration_source
    assert "vector" not in migration_source
    assert "search_case_memory" not in conversation_sources
