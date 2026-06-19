from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import AgentRun, Tenant, User


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

    messages = await repository.list_messages(tenant_id=tenant_id, user_id=user_id, thread_id=thread_id)

    assert thread.id == first.conversation_thread_id == second.conversation_thread_id
    assert [message.message_index for message in messages] == [1, 2]
    assert [message.run_id for message in messages] == [first_run_id, second_run_id]
    assert [message.content for message in messages] == ["用户第一句", "助手回复"]


@pytest.mark.asyncio
async def test_concurrent_first_message_append_reuses_single_thread(test_engine) -> None:
    from src.conversation.repository import ConversationRepository
    from src.conversation.schemas import ConversationMessageCreate

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    thread_id = "thread-concurrent-first-append"
    run_ids = [uuid.uuid4() for _ in range(5)]
    async with session_factory() as setup_session:
        setup_session.add(Tenant(id=tenant_id, name="concurrent-thread-tenant", status="active"))
        setup_session.add(
            User(
                id=user_id,
                tenant_id=tenant_id,
                username="concurrent_thread_user",
                password_hash="hash",
                role="support",
                is_active=True,
            )
        )
        setup_session.add_all(
            AgentRun(
                id=run_id,
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                input_query=f"test {index}",
                final_status="completed",
                started_at=datetime.now(UTC),
            )
            for index, run_id in enumerate(run_ids)
        )
        await setup_session.commit()

    async def append_from_worker(index: int) -> tuple[uuid.UUID, int]:
        async with session_factory() as worker_session:
            row = await ConversationRepository(worker_session).append_message(
                ConversationMessageCreate(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    thread_id=thread_id,
                    run_id=run_ids[index],
                    role="user",
                    content=f"并发首句 {index}",
                )
            )
            await worker_session.commit()
            return row.conversation_thread_id, row.message_index

    results = await asyncio.gather(*(append_from_worker(index) for index in range(len(run_ids))))

    assert {thread_id for thread_id, _message_index in results} == {results[0][0]}
    assert sorted(message_index for _thread_id, message_index in results) == [1, 2, 3, 4, 5]


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

    own_thread = await repository.get_thread(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id=thread_id,
    )
    other_thread = await repository.get_thread(
        tenant_id=seeded_session["other_tenant"].id,
        user_id=seeded_session["users"]["other_support"].id,
        thread_id=thread_id,
    )
    missing_cross_tenant = await repository.get_thread(
        tenant_id=seeded_session["other_tenant"].id,
        user_id=seeded_session["users"]["other_support"].id,
        thread_id="missing-thread",
    )

    assert own_thread is not None
    assert other_thread is not None
    assert own_thread.id != other_thread.id
    assert missing_cross_tenant is None


@pytest.mark.asyncio
async def test_thread_lookup_is_user_scoped_within_tenant(session: AsyncSession, seeded_session: dict) -> None:
    from src.conversation.repository import ConversationRepository

    repository = ConversationRepository(session)
    tenant_id = seeded_session["tenant"].id
    support_user_id = seeded_session["users"]["cs_zhang"].id
    merchant_user_id = seeded_session["users"]["merchant_wang"].id
    thread_id = "thread-user-scoped"

    support_thread = await repository.get_or_create_thread(
        tenant_id=tenant_id,
        user_id=support_user_id,
        thread_id=thread_id,
    )
    merchant_thread = await repository.get_or_create_thread(
        tenant_id=tenant_id,
        user_id=merchant_user_id,
        thread_id=thread_id,
    )

    assert support_thread.id != merchant_thread.id
    assert (
        await repository.get_thread(tenant_id=tenant_id, user_id=support_user_id, thread_id=thread_id) == support_thread
    )
    assert (
        await repository.get_thread(tenant_id=tenant_id, user_id=merchant_user_id, thread_id=thread_id)
        == merchant_thread
    )
