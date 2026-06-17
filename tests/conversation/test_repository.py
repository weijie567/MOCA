from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from pydantic import ValidationError
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
async def test_append_messages_preserves_tenant_thread_run_order(session: AsyncSession, seeded_session: dict) -> None:
    from src.conversation.repository import ConversationRepository
    from src.conversation.schemas import ConversationMessageCreate

    repository = ConversationRepository(session)
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    thread_id = "thread-conversation-order"
    first_run_id = await _insert_run(session, seeded_session, thread_id)
    second_run_id = await _insert_run(session, seeded_session, thread_id)

    thread = await repository.get_or_create_thread(tenant_id=tenant_id, user_id=user_id, thread_id=thread_id)
    first = await repository.append_message(
        ConversationMessageCreate(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            run_id=first_run_id,
            role="user",
            content="用户第一句",
        )
    )
    second = await repository.append_message(
        ConversationMessageCreate(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            run_id=second_run_id,
            role="assistant",
            content="助手回复",
        )
    )

    messages = await repository.list_messages(tenant_id=tenant_id, thread_id=thread_id)

    assert thread.id == first.conversation_thread_id == second.conversation_thread_id
    assert [message.message_index for message in messages] == [1, 2]
    assert [message.run_id for message in messages] == [first_run_id, second_run_id]
    assert [message.content for message in messages] == ["用户第一句", "助手回复"]


def test_tool_message_rejects_raw_payload_keys() -> None:
    from src.conversation.schemas import ConversationMessageCreate
    from src.conversation.service import ConversationService

    service = ConversationService(repository=None)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ConversationMessageCreate(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            thread_id="thread-raw-tool",
            run_id=uuid.uuid4(),
            role="tool",
            content="safe summary",
            metadata_json={"raw_payload": {"secret": "do-not-store"}},
        )
    with pytest.raises(ValueError, match="raw_tool_output"):
        service.validate_safe_message_payload(
            content="safe",
            metadata_json={"raw_tool_output": {"full": "payload"}},
        )


@pytest.mark.asyncio
async def test_thread_lookup_is_tenant_scoped(session: AsyncSession, seeded_session: dict) -> None:
    from src.conversation.repository import ConversationRepository

    repository = ConversationRepository(session)
    thread_id = "thread-tenant-scoped"

    await repository.get_or_create_thread(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id=thread_id,
    )
    await repository.get_or_create_thread(
        tenant_id=seeded_session["other_tenant"].id,
        user_id=seeded_session["users"]["other_support"].id,
        thread_id=thread_id,
    )

    own_thread = await repository.get_thread(tenant_id=seeded_session["tenant"].id, thread_id=thread_id)
    other_thread = await repository.get_thread(tenant_id=seeded_session["other_tenant"].id, thread_id=thread_id)
    missing_cross_tenant = await repository.get_thread(
        tenant_id=seeded_session["other_tenant"].id,
        thread_id="missing-thread",
    )

    assert own_thread is not None
    assert other_thread is not None
    assert own_thread.id != other_thread.id
    assert missing_cross_tenant is None
