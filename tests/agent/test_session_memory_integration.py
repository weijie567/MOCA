from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.graph import build_graph
from src.agent.nodes import session_memory_load as session_memory_load_module
from src.agent.nodes.memory_write import memory_write
from src.agent.trace import write_agent_run
from src.db.models import User
from src.memory.repository import SessionMemoryRepository
from src.memory.service import MemoryService
from tests.agent.test_graph import _config, _patch_graph_dependencies


def _state(user: User, query: str, thread_id: str, *, run_id: str | None = None) -> dict:
    state = {
        "user_query": query,
        "thread_id": thread_id,
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.id),
        "role": user.role,
    }
    if run_id is not None:
        state["current_run_id"] = run_id
    return state


async def _persist_run(session: AsyncSession, user: User, thread_id: str, query: str) -> str:
    run_id = str(uuid4())
    await write_agent_run(
        session,
        run_id=run_id,
        thread_id=thread_id,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        input_query=query,
        final_status="completed",
        final_response="done",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        total_latency_ms=1,
    )
    return run_id


async def _write_order_memory(session: AsyncSession, user: User, thread_id: str, order_id: str = "ORD-1001") -> None:
    run_id = await _persist_run(session, user, thread_id, f"remember {order_id}")
    await memory_write(
        {
            "tenant_id": str(user.tenant_id),
            "user_id": str(user.id),
            "thread_id": thread_id,
            "current_run_id": run_id,
            "final_response": "已完成。",
            "primary_intent": "refund_troubleshooting",
            "extracted_slots": {"order_id": order_id},
            "active_slots": {"order_id": order_id},
            "clarification_request": None,
            "last_business_context_refs": {"order": order_id},
            "trace_steps": [],
            "node_errors": [],
        },
        {"configurable": {"session": session}},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_same_thread_vague_turn_inherits_session_order_and_reruns_investigation(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    thread_id = "integration-same-thread"
    await _write_order_memory(session, user, thread_id)
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state(user, "what about that refund?", thread_id),
        _config(deps["tool_manager"], deps["events"], thread_id, session=session),
    )

    assert final_state["active_slots"]["order_id"] == "ORD-1001"
    assert final_state["active_slot_metadata"]["order_id"]["source"] == "trusted_session_memory"
    assert final_state["active_slot_metadata"]["order_id"]["explicit_current_turn"] is False
    assert final_state["business_context"]["facts"]["order"]["order_no"] == "ORD-1001"
    assert [call[0] for call in deps["tool_manager"].calls] == ["get_order", "search_policy"]


@pytest.mark.asyncio
async def test_different_thread_vague_turn_does_not_reuse_session_order(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    await _write_order_memory(session, user, "integration-source-thread")
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state(user, "what about that refund?", "integration-other-thread"),
        _config(deps["tool_manager"], deps["events"], "integration-other-thread", session=session),
    )

    assert deps["tool_manager"].calls == []
    assert final_state["active_slots"] == {}
    assert final_state["clarification_request"]["reason"] == "missing_required_slots"


@pytest.mark.asyncio
async def test_unresolved_question_carryover_keeps_current_turn_slot_authoritative(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    thread_id = "integration-unresolved-question"
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    graph = build_graph(MemorySaver())
    first_state = await graph.ainvoke(
        _state(user, "帮我看看这笔退款为什么没到账", thread_id),
        _config(deps["tool_manager"], deps["events"], thread_id, session=session),
    )
    run_id = await _persist_run(session, user, thread_id, "missing slot turn")
    await memory_write(
        {**_state(user, "帮我看看这笔退款为什么没到账", thread_id), **first_state, "current_run_id": run_id},
        {"configurable": {"session": session}},
    )
    await session.commit()
    view = await MemoryService(SessionMemoryRepository(session)).load_session_memory(
        user.tenant_id,
        user.id,
        thread_id,
        current_intent="refund_troubleshooting",
    )
    assert view.unresolved_questions

    second_deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-1001")
    second_state = await graph.ainvoke(
        _state(user, "订单是 ORD-1001", thread_id),
        _config(second_deps["tool_manager"], second_deps["events"], thread_id, session=session),
    )

    assert second_state["active_slots"]["order_id"] == "ORD-1001"
    assert second_state["active_slot_metadata"]["order_id"]["source"] == "current_turn"
    assert second_state["business_context"]["facts"]["order"]["order_no"] == "ORD-1001"
    assert [call[0] for call in second_deps["tool_manager"].calls] == ["get_order", "search_policy"]


@pytest.mark.asyncio
async def test_disabled_and_unavailable_session_memory_fall_back_to_clarification(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    graph = build_graph(MemorySaver())

    monkeypatch.setattr(session_memory_load_module.settings, "session_memory_enabled", False)
    disabled_deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    disabled_state = await graph.ainvoke(
        _state(user, "that refund?", "integration-disabled-memory"),
        _config(disabled_deps["tool_manager"], disabled_deps["events"], "integration-disabled-memory", session=session),
    )
    assert disabled_deps["tool_manager"].calls == []
    assert disabled_state["session_memory"]["fallback_reason"] == "disabled"
    assert disabled_state["clarification_request"]["reason"] == "missing_required_slots"

    monkeypatch.setattr(session_memory_load_module.settings, "session_memory_enabled", True)

    class FailingMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def load_session_memory(self, tenant_id, user_id, thread_id, current_intent):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(session_memory_load_module, "MemoryService", FailingMemoryService)
    unavailable_deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    unavailable_state = await graph.ainvoke(
        _state(user, "that refund?", "integration-unavailable-memory"),
        _config(
            unavailable_deps["tool_manager"],
            unavailable_deps["events"],
            "integration-unavailable-memory",
            session=session,
        ),
    )
    assert unavailable_deps["tool_manager"].calls == []
    assert unavailable_state["session_memory"]["fallback_reason"] == "unavailable"
    assert unavailable_state["clarification_request"]["reason"] == "missing_required_slots"
