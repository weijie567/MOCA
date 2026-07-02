from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

import asyncpg
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.conversation.repository import ConversationRepository
from src.conversation.schemas import ConversationMessageCreate
from src.db.models import AgentRun, Base, Merchant, Order, RefundCase, Tenant, ThreadCaseLink, User
from src.memory.thread_case_links import ThreadCaseLinkRepository
from tests.conftest import TEST_DATABASE_URL, _ensure_test_database


@pytest.fixture
async def phase44_session_factory():
    try:
        await _ensure_test_database(TEST_DATABASE_URL)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Phase 44 PostgreSQL unavailable: {exc}")

    engine = create_async_engine(TEST_DATABASE_URL, future=True, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


async def _seed_link_scope(session: AsyncSession) -> dict:
    tenant = Tenant(id=uuid.uuid4(), name=f"phase44-link-tenant-{uuid.uuid4()}", status="active")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        username=f"phase44-link-user-{uuid.uuid4()}",
        password_hash="hash",
        role="admin",
        is_active=True,
    )
    merchant = Merchant(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        merchant_name="Phase 44 Link Shop",
        category="electronics",
        risk_level="low",
    )
    order = Order(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        merchant_id=merchant.id,
        order_no=f"ORD-PHASE44-LINK-{uuid.uuid4()}",
        buyer_name="测试用户",
        item_name="蓝牙耳机",
        amount=Decimal("199.00"),
        currency="CNY",
        status="delivered",
    )
    first_case = RefundCase(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order.id,
        refund_case_no=f"RF-PHASE44-LINK-{uuid.uuid4()}",
        reason_code="damaged",
        reason_text="收到商品破损",
        status="reviewing",
        requested_amount=Decimal("199.00"),
    )
    second_case = RefundCase(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        order_id=order.id,
        refund_case_no=f"RF-PHASE44-LINK-{uuid.uuid4()}",
        reason_code="quality_issue",
        reason_text="商品质量问题",
        status="reviewing",
        requested_amount=Decimal("89.00"),
    )
    run = AgentRun(
        id=uuid.uuid4(),
        thread_id=f"phase44-link-thread-{uuid.uuid4()}",
        tenant_id=tenant.id,
        user_id=user.id,
        input_query="测试线程案件关联",
        final_status="completed",
        scope_classification="unknown_legacy",
        started_at=datetime.now(UTC),
    )
    session.add_all([tenant, user, merchant, order, first_case, second_case, run])
    await session.flush()
    return {
        "tenant": tenant,
        "user": user,
        "merchant": merchant,
        "order": order,
        "first_case": first_case,
        "second_case": second_case,
        "run": run,
    }


@pytest.mark.asyncio
async def test_link_thread_to_case_inserts_and_dedupes_active_row(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_link_scope(session)
            conversation = ConversationRepository(session)
            thread = await conversation.get_or_create_thread(
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id="phase44-link-dedup",
            )
            repository = ThreadCaseLinkRepository(session)

            first = await repository.link_thread_to_case(
                tenant_id=scope["tenant"].id,
                conversation_thread_id=thread.id,
                thread_id=thread.thread_id,
                case_id=scope["first_case"].id,
                link_source="run_auto",
                linked_by_run_id=scope["run"].id,
            )
            second = await repository.link_thread_to_case(
                tenant_id=scope["tenant"].id,
                conversation_thread_id=thread.id,
                thread_id=thread.thread_id,
                case_id=scope["first_case"].id,
                link_source="run_auto",
                linked_by_run_id=scope["run"].id,
            )
            active_count = await session.scalar(
                select(func.count())
                .select_from(ThreadCaseLink)
                .where(
                    ThreadCaseLink.tenant_id == scope["tenant"].id,
                    ThreadCaseLink.conversation_thread_id == thread.id,
                    ThreadCaseLink.case_id == scope["first_case"].id,
                    ThreadCaseLink.deleted_at.is_(None),
                )
            )

    assert first.id == second.id
    assert first.link_source == "run_auto"
    assert first.linked_by_run_id == scope["run"].id
    assert active_count == 1


@pytest.mark.asyncio
async def test_thread_case_link_lists_many_to_many_in_both_directions(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_link_scope(session)
            conversation = ConversationRepository(session)
            first_thread = await conversation.get_or_create_thread(
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id="phase44-link-thread-a",
            )
            second_thread = await conversation.get_or_create_thread(
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id="phase44-link-thread-b",
            )
            repository = ThreadCaseLinkRepository(session)
            await repository.link_thread_to_case(
                tenant_id=scope["tenant"].id,
                conversation_thread_id=first_thread.id,
                thread_id=first_thread.thread_id,
                case_id=scope["first_case"].id,
                link_source="staff_manual",
                linked_by_run_id=scope["run"].id,
            )
            await repository.link_thread_to_case(
                tenant_id=scope["tenant"].id,
                conversation_thread_id=first_thread.id,
                thread_id=first_thread.thread_id,
                case_id=scope["second_case"].id,
                link_source="staff_manual",
                linked_by_run_id=scope["run"].id,
            )
            await repository.link_thread_to_case(
                tenant_id=scope["tenant"].id,
                conversation_thread_id=second_thread.id,
                thread_id=second_thread.thread_id,
                case_id=scope["first_case"].id,
                link_source="import",
            )

            cases_for_thread = await repository.list_cases_for_thread(
                tenant_id=scope["tenant"].id,
                conversation_thread_id=first_thread.id,
            )
            threads_for_case = await repository.list_threads_for_case(
                tenant_id=scope["tenant"].id,
                case_id=scope["first_case"].id,
            )

    assert set(cases_for_thread) == {scope["first_case"].id, scope["second_case"].id}
    assert {link.conversation_thread_id for link in threads_for_case} == {first_thread.id, second_thread.id}
    assert {link.thread_id for link in threads_for_case} == {"phase44-link-thread-a", "phase44-link-thread-b"}


@pytest.mark.asyncio
async def test_link_thread_to_case_rejects_unknown_link_source_before_insert(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_link_scope(session)
            thread = await ConversationRepository(session).get_or_create_thread(
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id="phase44-link-invalid-source",
            )
            repository = ThreadCaseLinkRepository(session)

            with pytest.raises(ValueError, match="link_source"):
                await repository.link_thread_to_case(
                    tenant_id=scope["tenant"].id,
                    conversation_thread_id=thread.id,
                    thread_id=thread.thread_id,
                    case_id=scope["first_case"].id,
                    link_source="silent_auto",
                    linked_by_run_id=scope["run"].id,
                )
            active_count = await session.scalar(select(func.count()).select_from(ThreadCaseLink))

    assert active_count == 0


@pytest.mark.asyncio
async def test_conversation_link_case_is_explicit_and_deduped(phase44_session_factory) -> None:
    async with phase44_session_factory() as session:
        async with session.begin():
            scope = await _seed_link_scope(session)
            repository = ConversationRepository(session)
            await repository.append_message(
                ConversationMessageCreate(
                    tenant_id=scope["tenant"].id,
                    user_id=scope["user"].id,
                    thread_id="phase44-explicit-link",
                    run_id=scope["run"].id,
                    role="user",
                    content="用户询问退款进度",
                )
            )
            count_after_append = await session.scalar(select(func.count()).select_from(ThreadCaseLink))

            first = await repository.link_case(
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id="phase44-explicit-link",
                case_id=scope["first_case"].id,
                link_source="run_auto",
                linked_by_run_id=scope["run"].id,
            )
            second = await repository.link_case(
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id="phase44-explicit-link",
                case_id=scope["first_case"].id,
                link_source="run_auto",
                linked_by_run_id=scope["run"].id,
            )
            active_count = await session.scalar(
                select(func.count())
                .select_from(ThreadCaseLink)
                .where(
                    ThreadCaseLink.tenant_id == scope["tenant"].id,
                    ThreadCaseLink.case_id == scope["first_case"].id,
                    ThreadCaseLink.deleted_at.is_(None),
                )
            )
            thread = await repository.get_thread(
                tenant_id=scope["tenant"].id,
                user_id=scope["user"].id,
                thread_id="phase44-explicit-link",
            )

    assert count_after_append == 0
    assert first.id == second.id
    assert active_count == 1
    assert thread is not None
    assert first.conversation_thread_id == thread.id
