from __future__ import annotations

from src.agent.nodes import session_memory_load as session_memory_load_module
from src.agent.nodes.session_memory_load import session_memory_load
from src.memory.schemas import SessionMemoryView


def _state() -> dict:
    return {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "primary_intent": "refund_troubleshooting",
        "trace_steps": [],
    }


async def test_session_memory_load_disabled_returns_empty_fallback(monkeypatch):
    monkeypatch.setattr(session_memory_load_module.settings, "session_memory_enabled", False)

    result = await session_memory_load(_state(), {"configurable": {"session": object()}})

    memory = result["session_memory"]
    metrics = result["trace_steps"][-1]["metrics_json"]
    assert memory["continuity_claimed"] is False
    assert memory["active_slots"] == {}
    assert memory["source"] == "disabled"
    assert memory["fallback_reason"] == "disabled"
    assert metrics["fallback_reason"] == "disabled"


async def test_session_memory_load_without_async_session_returns_empty_fallback(monkeypatch):
    monkeypatch.setattr(session_memory_load_module.settings, "session_memory_enabled", True)

    result = await session_memory_load(_state(), {"configurable": {}})

    memory = result["session_memory"]
    assert memory["continuity_claimed"] is False
    assert memory["active_slots"] == {}
    assert memory["source"] in {"empty_adapter", "unavailable"}
    assert memory["fallback_reason"] == "missing_async_session"


async def test_session_memory_load_uses_memory_service_view(monkeypatch):
    monkeypatch.setattr(session_memory_load_module.settings, "session_memory_enabled", True)

    class FakeMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            self.repository = repository
            self.enabled = enabled

        async def load_session_memory(self, tenant_id, user_id, thread_id, current_intent):
            return SessionMemoryView(
                source="postgres_session_memory",
                continuity_claimed=True,
                active_slots={"order_id": "ORD-SESSION-001"},
                slot_metadata={
                    "order_id": {
                        "source": "trusted_session_memory",
                        "tenant_id": tenant_id,
                        "user_id": user_id,
                        "thread_id": thread_id,
                        "fresh": True,
                        "compatible_intents": [current_intent],
                    }
                },
                session_summary="用户正在排查 ORD-SESSION-001。",
                unresolved_questions=["需要确认退款通道"],
                last_intent=current_intent,
                last_business_context_refs={"order": "ORD-SESSION-001"},
                version=7,
            )

    monkeypatch.setattr(session_memory_load_module, "MemoryService", FakeMemoryService)

    result = await session_memory_load(_state(), {"configurable": {"session": object()}})

    memory = result["session_memory"]
    metrics = result["trace_steps"][-1]["metrics_json"]
    assert memory["active_slots"] == {"order_id": "ORD-SESSION-001"}
    assert memory["slot_metadata"]["order_id"]["source"] == "trusted_session_memory"
    assert memory["session_summary"]
    assert memory["unresolved_questions"] == ["需要确认退款通道"]
    assert memory["version"] == 7
    assert metrics["slot_count"] == 1
    assert metrics["continuity_claimed"] is True


async def test_session_memory_load_service_error_returns_unavailable(monkeypatch):
    monkeypatch.setattr(session_memory_load_module.settings, "session_memory_enabled", True)

    class FailingMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def load_session_memory(self, tenant_id, user_id, thread_id, current_intent):
            raise RuntimeError("database exploded")

    monkeypatch.setattr(session_memory_load_module, "MemoryService", FailingMemoryService)

    result = await session_memory_load(_state(), {"configurable": {"session": object()}})

    memory = result["session_memory"]
    metrics = result["trace_steps"][-1]["metrics_json"]
    assert memory["source"] == "unavailable"
    assert memory["continuity_claimed"] is False
    assert memory["fallback_reason"] == "unavailable"
    assert metrics["fallback_reason"] == "unavailable"
