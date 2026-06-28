from __future__ import annotations

import uuid

from src.agent.nodes import session_memory_load as session_memory_load_module
from src.agent.nodes.session_memory_load import session_memory_load
from src.memory.schemas import SessionMemoryBundle, SessionMemoryView


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


async def test_session_memory_load_without_bundle_returns_empty_fallback(monkeypatch):
    monkeypatch.setattr(session_memory_load_module.settings, "session_memory_enabled", True)

    result = await session_memory_load(_state(), {"configurable": {"session": object()}})

    memory = result["session_memory"]
    metrics = result["trace_steps"][-1]["metrics_json"]
    assert memory["active_slots"] == {}
    assert memory["slot_metadata"] == {}
    assert memory["source"] == "unavailable"
    assert memory["fallback_reason"] == "missing_session_memory_bundle"
    assert metrics["slot_count"] == 0
    assert metrics["continuity_claimed"] is False


async def test_session_memory_load_attaches_session_memory_bundle(monkeypatch):
    monkeypatch.setattr(session_memory_load_module.settings, "session_memory_enabled", True)
    run_id = str(uuid.uuid4())

    class FakeSession:
        async def execute(self, *args, **kwargs):
            raise AssertionError("bundle service should not hit the repository in this test")

    class FakeBundleService:
        def __init__(self, *, conversation_service, memory_service) -> None:
            self.conversation_service = conversation_service
            self.memory_service = memory_service

        async def load_session_memory_bundle(self, **kwargs):
            assert kwargs["run_id"] == run_id
            slot_continuity = SessionMemoryView(
                source="postgres_session_memory",
                continuity_claimed=True,
                active_slots={"order_id": "ORD-BUNDLE-NODE"},
                slot_metadata={"order_id": {"source": "trusted_session_memory"}},
                version=9,
            )
            return SessionMemoryBundle(
                tenant_id=str(kwargs["tenant_id"]),
                user_id=str(kwargs["user_id"]),
                thread_id=kwargs["thread_id"],
                run_id=str(kwargs["run_id"]),
                rolling_summary={
                    "summary_id": "summary-node",
                    "summary_text": "bundle rolling summary for ORD-BUNDLE-NODE",
                },
                recent_messages=[],
                tool_summaries=[],
                slot_continuity=slot_continuity,
            )

    monkeypatch.setattr(session_memory_load_module, "SessionMemoryBundleService", FakeBundleService)

    result = await session_memory_load(
        {**_state(), "current_run_id": run_id},
        {"configurable": {"session": FakeSession()}},
    )

    assert result["session_memory"]["active_slots"] == {"order_id": "ORD-BUNDLE-NODE"}
    assert result["session_memory"]["version"] == 9
    assert result["session_memory_bundle"]["rolling_summary"]["summary_text"] == (
        "bundle rolling summary for ORD-BUNDLE-NODE"
    )
    assert result["session_memory_bundle"]["slot_continuity"]["active_slots"]["order_id"] == "ORD-BUNDLE-NODE"
    assert result["session_context"]["active_slots"]["order_id"] == "ORD-BUNDLE-NODE"
    assert result["session_context_bundle"]["schema_version"] == "session_context_bundle.v1"
    assert result["session_context_load_status"]["schema_version"] == "session_context_load_status.v1"
    assert result["session_context_load_status"]["authority_class"] == "contextual_only"


async def test_session_context_load_direct_node_returns_target_and_legacy_fields(monkeypatch):
    from src.agent.nodes import session_context_load as session_context_load_module
    from src.agent.nodes.session_context_load import session_context_load

    monkeypatch.setattr(session_context_load_module.settings, "session_memory_enabled", True)
    run_id = str(uuid.uuid4())

    class FakeSession:
        async def execute(self, *args, **kwargs):
            raise AssertionError("bundle service should not hit the repository in this test")

    class FakeBundleService:
        def __init__(self, *, conversation_service, memory_service) -> None:
            self.conversation_service = conversation_service
            self.memory_service = memory_service

        async def load_session_memory_bundle(self, **kwargs):
            slot_continuity = SessionMemoryView(
                source="postgres_session_memory",
                continuity_claimed=True,
                active_slots={"order_id": "ORD-CONTEXT-DIRECT"},
                slot_metadata={"order_id": {"source": "trusted_session_memory"}},
                version=11,
            )
            return SessionMemoryBundle(
                tenant_id=str(kwargs["tenant_id"]),
                user_id=str(kwargs["user_id"]),
                thread_id=kwargs["thread_id"],
                run_id=str(kwargs["run_id"]),
                rolling_summary={
                    "summary_id": "summary-context-direct",
                    "summary_text": "direct target node rolling summary",
                },
                recent_messages=[],
                tool_summaries=[],
                slot_continuity=slot_continuity,
            )

    monkeypatch.setattr(session_context_load_module, "SessionMemoryBundleService", FakeBundleService)

    result = await session_context_load(
        {**_state(), "current_run_id": run_id},
        {"configurable": {"session": FakeSession()}},
    )

    assert result["session_context"]["active_slots"] == {"order_id": "ORD-CONTEXT-DIRECT"}
    assert result["session_context_bundle"]["schema_version"] == "session_context_bundle.v1"
    assert result["session_context_load_status"]["schema_version"] == "session_context_load_status.v1"
    assert result["session_context_load_status"]["authority_class"] == "contextual_only"
    assert result["session_memory"]["active_slots"] == {"order_id": "ORD-CONTEXT-DIRECT"}
    assert result["session_memory_bundle"]["schema_version"] == "session_memory_bundle.v1"
    assert result["trace_steps"][-1]["node"] == "session_context_load"


async def test_session_memory_load_fails_closed_when_bundle_load_fails(monkeypatch):
    monkeypatch.setattr(session_memory_load_module.settings, "session_memory_enabled", True)
    run_id = str(uuid.uuid4())

    class FakeSession:
        async def execute(self, *args, **kwargs):
            raise AssertionError("direct slot continuity fake should avoid repository reads")

    class FakeMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            self.repository = repository
            self.enabled = enabled

        async def load_session_memory(self, tenant_id, user_id, thread_id, current_intent):
            raise AssertionError("bundle failure must not fall back to direct slot-continuity reads")

    class FailingBundleService:
        def __init__(self, *, conversation_service, memory_service) -> None:
            pass

        async def load_session_memory_bundle(self, **kwargs):
            raise RuntimeError("prompt context unavailable")

    monkeypatch.setattr(session_memory_load_module, "MemoryService", FakeMemoryService)
    monkeypatch.setattr(session_memory_load_module, "SessionMemoryBundleService", FailingBundleService)

    result = await session_memory_load(
        {**_state(), "current_run_id": run_id},
        {"configurable": {"session": FakeSession()}},
    )

    assert result["session_memory"]["active_slots"] == {}
    assert result["session_memory"]["continuity_claimed"] is False
    assert result["session_memory"]["fallback_reason"] == "unavailable"
    assert "session_memory_bundle" not in result


async def test_session_memory_load_service_error_returns_unavailable(monkeypatch):
    monkeypatch.setattr(session_memory_load_module.settings, "session_memory_enabled", True)
    run_id = str(uuid.uuid4())

    class FakeSession:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("conversation unavailable")

    class FailingMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def load_session_memory(self, tenant_id, user_id, thread_id, current_intent):
            raise RuntimeError("database exploded")

    monkeypatch.setattr(session_memory_load_module, "MemoryService", FailingMemoryService)

    result = await session_memory_load({**_state(), "current_run_id": run_id}, {"configurable": {"session": FakeSession()}})

    memory = result["session_memory"]
    metrics = result["trace_steps"][-1]["metrics_json"]
    assert memory["source"] == "empty_adapter"
    assert memory["continuity_claimed"] is False
    assert memory["fallback_reason"] == "unavailable"
    assert metrics["fallback_reason"] == "unavailable"
    assert result["session_memory_bundle"]["fallback_reasons"]["slot_continuity"] == "unavailable"
