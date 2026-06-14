from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.repository import SessionMemoryRepository
from src.memory.schemas import SessionSlotV1
from src.memory.search import CaseMemorySearchService
from src.tools.contracts import ToolCallContext
from src.tools.executors.memory import MemoryToolExecutor


def _slot(value: str) -> SessionSlotV1:
    now = datetime.now(UTC)
    return SessionSlotV1(
        value=value,
        source="explicit_user",
        source_run_id=str(uuid4()),
        updated_at=now,
        expires_at=now + timedelta(days=7),
        compatible_intents=["refund_troubleshooting"],
    )


def _ctx(*, tenant_id: str, user_id: str) -> ToolCallContext:
    return ToolCallContext(
        tenant_id=tenant_id,
        user_id=user_id,
        role="support_agent",
        permissions=["tool:search_case_memory"],
        merchant_scope={"merchant_ids": ["*"]},
        thread_id="thread-current",
        run_id=str(uuid4()),
        trace_id="trace-memory",
        request_id=str(uuid4()),
        tool_call_id=str(uuid4()),
        caller_node="investigate",
    )


@pytest.mark.asyncio
async def test_case_memory_search_reads_session_memory_storage(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    other_user_id = seeded_session["users"]["merchant_wang"].id
    repository = SessionMemoryRepository(session)
    await repository.insert_active(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id="thread-prior-hit",
        active_slots_json={"schema_version": "session_slots.v1", "slots": {"order_id": _slot("ORD-777").model_dump(mode="json")}},
        session_summary="用户之前咨询退款超时，客服已建议核实支付通道。",
        unresolved_questions_json=["还缺少支付通道回执"],
        last_intent="refund_troubleshooting",
        last_business_context_refs_json={"order_no": "ORD-777"},
    )
    await repository.insert_active(
        tenant_id=tenant_id,
        user_id=other_user_id,
        thread_id="thread-other-user",
        session_summary="退款超时但属于其他用户",
    )

    result = await CaseMemorySearchService(repository).search(
        query="退款超时",
        context=_ctx(tenant_id=str(tenant_id), user_id=str(user_id)),
    )

    assert result.status == "success"
    assert len(result.items) == 1
    item = result.items[0]
    assert item.thread_id == "thread-prior-hit"
    assert item.active_slots["order_id"] == "ORD-777"
    assert item.last_business_context_refs["order_no"] == "ORD-777"


@pytest.mark.asyncio
async def test_memory_tool_executor_projects_items_as_json(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    repository = SessionMemoryRepository(session)
    await repository.insert_active(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id="thread-json-hit",
        session_summary="补偿券审批历史案例",
        last_intent="compensation_request",
    )
    executor = MemoryToolExecutor(session)

    result = await executor.execute(
        "search_case_memory",
        {"query": "补偿券审批"},
        _ctx(tenant_id=str(tenant_id), user_id=str(user_id)),
    )

    assert result.status == "success"
    assert result.data is not None
    assert result.data["items"][0]["thread_id"] == "thread-json-hit"
    assert isinstance(result.data["items"][0]["updated_at"], str)
