from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes import memory_write as memory_write_module
from src.agent.nodes.memory_write import memory_write
from src.agent.trace import write_agent_run
from src.db.models import AgentTraceEvent, SessionMemory
from src.memory.schemas import SessionMemoryWriteResult


def _state(**updates: object) -> dict:
    values: dict[str, object] = {
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "thread_id": "thread-memory-write",
        "current_run_id": str(uuid4()),
        "final_response": "最终回复已经生成。",
        "primary_intent": "refund_troubleshooting",
        "extracted_slots": {"order_id": "ORD-1001", "refund_case_id": None},
        "active_slots": {"order_id": "ORD-1001", "refund_case_id": "RF-INHERITED"},
        "active_slot_metadata": {
            "order_id": {"source": "current_turn", "explicit_current_turn": True},
            "refund_case_id": {"source": "trusted_session_memory", "explicit_current_turn": False},
        },
        "session_memory": {"version": 3},
        "clarification_request": {"questions": ["请补充退款通道状态。"]},
        "last_business_context_refs": {"business_fact_refs": [{"resource_type": "order", "resource_id": "ORD-1001"}]},
        "trace_steps": [],
        "node_errors": [],
    }
    values.update(updates)
    return values


async def test_memory_write_node_skips_when_final_response_missing():
    result = await memory_write(_state(final_response=None), {"configurable": {"session": object()}})

    assert result["memory_write_result"]["status"] == "skipped"
    assert result["memory_write_result"]["reason_code"] == "not_completed_path"
    assert result["memory_write_decision"]["schema_version"] == "memory_write_decision.v2"
    assert result["memory_write_decision"]["authority_class"] == "contextual_only"
    assert result["memory_write_decision"]["status"] == "skipped"
    assert result["memory_write_decision"]["decision"] == "skip"
    assert result["memory_write_decision"]["reason_code"] == "not_completed_path"
    assert result["trace_steps"][-1]["node"] == "memory_write"


async def test_memory_write_node_writes_explicit_slots_and_unresolved_questions(monkeypatch):
    candidates = []

    class FakeMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def write_session_memory(self, candidate):
            candidates.append(candidate)
            return SessionMemoryWriteResult(
                status="written",
                version=4,
                decision="write",
                reason_code="eligible",
                pii_classification="none",
            )

    monkeypatch.setattr(memory_write_module, "MemoryService", FakeMemoryService)

    result = await memory_write(_state(), {"configurable": {"session": object()}})

    assert result["memory_write_result"]["status"] == "written"
    assert result["memory_write_decision"]["schema_version"] == "memory_write_decision.v2"
    assert result["memory_write_decision"]["status"] == "written"
    assert result["memory_write_decision"]["decision"] == "write"
    assert result["memory_write_decision"]["memory_type"] == "session"
    assert result["memory_write_decision"]["authority_class"] == "contextual_only"
    assert result["memory_write_decision"]["candidate_hash"].startswith("sha256:")
    assert result["memory_write_decision"]["scope"]["thread_id"] == "thread-memory-write"
    assert result["trace_steps"][-1]["metrics_json"]["memory_write_decision_schema_version"] == (
        "memory_write_decision.v2"
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert set(candidate.explicit_slots) == {"order_id"}
    assert candidate.explicit_slots["order_id"].value == "ORD-1001"
    assert "order_status_inquiry" in candidate.explicit_slots["order_id"].compatible_intents
    assert "refund_troubleshooting" in candidate.explicit_slots["order_id"].compatible_intents
    assert "action_request" in candidate.explicit_slots["order_id"].compatible_intents
    assert "refund_case_id" not in candidate.explicit_slots
    assert candidate.unresolved_questions == ["请补充退款通道状态。"]
    assert candidate.last_intent == "refund_troubleshooting"
    assert candidate.session_summary
    assert candidate.last_business_context_refs == {
        "business_fact_refs": [{"resource_type": "order", "resource_id": "ORD-1001"}]
    }
    assert candidate.expected_version == 3


async def test_memory_write_failure_preserves_final_response(monkeypatch):
    class FailingMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def write_session_memory(self, candidate):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(memory_write_module, "MemoryService", FailingMemoryService)
    state = _state(final_response="不可变最终回复")

    result = await memory_write(state, {"configurable": {"session": object()}})

    assert result["final_response"] == "不可变最终回复"
    assert result["memory_write_result"]["status"] == "error"
    assert result["memory_write_decision"]["schema_version"] == "memory_write_decision.v2"
    assert result["memory_write_decision"]["status"] == "error"
    assert result["memory_write_decision"]["decision"] == "skip"
    assert result["memory_write_decision"]["reason_code"] == "write_error"
    assert result["node_errors"][-1]["error_code"] == "SESSION_MEMORY_WRITE_FAILED"


async def test_memory_write_timeout_preserves_final_response(monkeypatch):
    monkeypatch.setattr(memory_write_module.settings, "session_memory_write_timeout_seconds", 0.01)

    class SlowMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def write_session_memory(self, candidate):
            await asyncio.sleep(0.1)
            raise AssertionError("timeout should cancel before completion")

    monkeypatch.setattr(memory_write_module, "MemoryService", SlowMemoryService)
    started = time.perf_counter()

    result = await memory_write(_state(final_response="及时返回"), {"configurable": {"session": object()}})

    assert time.perf_counter() - started < 0.08
    assert result["final_response"] == "及时返回"
    assert result["memory_write_result"]["status"] == "skipped"
    assert result["memory_write_result"]["reason_code"] == "write_timeout"
    assert result["memory_write_decision"]["schema_version"] == "memory_write_decision.v2"
    assert result["memory_write_decision"]["status"] == "skipped"
    assert result["memory_write_decision"]["decision"] == "skip"
    assert result["memory_write_decision"]["reason_code"] == "write_timeout"
    assert result["memory_write_decision"]["fallback_reason"] == "write_timeout"


async def test_memory_write_timeout_rolls_back_started_event_before_scheduler_commit(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch,
):
    monkeypatch.setattr(memory_write_module.settings, "session_memory_write_timeout_seconds", 0.01)
    user = seeded_session["users"]["cs_zhang"]
    run_id = str(uuid4())
    thread_id = "thread-memory-write-timeout-rollback"
    await write_agent_run(
        session,
        run_id=run_id,
        thread_id=thread_id,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        input_query="remember order",
        final_status="completed",
        final_response="done",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        total_latency_ms=1,
    )
    await session.commit()

    class SlowMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def write_session_memory(self, candidate):
            await asyncio.sleep(0.1)
            raise AssertionError("timeout should cancel before completion")

    monkeypatch.setattr(memory_write_module, "MemoryService", SlowMemoryService)

    result = await memory_write(
        _state(
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            thread_id=thread_id,
            current_run_id=run_id,
            final_response="及时返回",
        ),
        {"configurable": {"session": session, "trace_id": "timeout-rollback-test"}},
    )
    await session.commit()
    rows = (
        (await session.execute(select(AgentTraceEvent).where(AgentTraceEvent.run_id == UUID(run_id)))).scalars().all()
    )

    assert result["memory_write_result"]["status"] == "skipped"
    assert result["memory_write_result"]["reason_code"] == "write_timeout"
    assert result["memory_write_decision"]["status"] == "skipped"
    assert result["memory_write_decision"]["reason_code"] == "write_timeout"
    assert result["memory_write_decision"]["fallback_reason"] == "write_timeout"
    assert rows == []


async def test_memory_write_initial_insert_uses_configured_slot_ttl_for_row_expiry(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch,
):
    monkeypatch.setattr(memory_write_module.settings, "session_memory_ttl_seconds", 5)
    user = seeded_session["users"]["cs_zhang"]
    run_id = str(uuid4())
    thread_id = "thread-memory-write-configured-ttl"
    await write_agent_run(
        session,
        run_id=run_id,
        thread_id=thread_id,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        input_query="remember order",
        final_status="completed",
        final_response="done",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        total_latency_ms=1,
    )
    await session.commit()
    before_write = datetime.now(UTC)

    result = await memory_write(
        _state(
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            thread_id=thread_id,
            current_run_id=run_id,
            extracted_slots={"order_id": "ORD-TTL-NODE"},
        ),
        {"configurable": {"session": session, "trace_id": "ttl-row-test"}},
    )
    await session.commit()
    row = (
        await session.execute(
            select(SessionMemory).where(
                SessionMemory.tenant_id == user.tenant_id,
                SessionMemory.user_id == user.id,
                SessionMemory.thread_id == thread_id,
                SessionMemory.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    assert result["memory_write_result"]["status"] == "written"
    assert row.expires_at is not None
    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    assert before_write < expires_at <= before_write + timedelta(seconds=6)


async def test_memory_write_lifecycle_trace_events_share_non_null_operation_id(
    session: AsyncSession,
    seeded_session: dict,
):
    user = seeded_session["users"]["cs_zhang"]
    run_id = str(uuid4())
    thread_id = "thread-memory-write-operation-id"
    await write_agent_run(
        session,
        run_id=run_id,
        thread_id=thread_id,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        input_query="remember order",
        final_status="completed",
        final_response="done",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        total_latency_ms=1,
    )
    await session.commit()

    result = await memory_write(
        _state(
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            thread_id=thread_id,
            current_run_id=run_id,
            final_response="可写入记忆",
            extracted_slots={"order_id": "ORD-OPERATION-ID"},
        ),
        {"configurable": {"session": session, "trace_id": "memory-write-operation-id-test"}},
    )
    rows = (
        (
            await session.execute(
                select(AgentTraceEvent)
                .where(AgentTraceEvent.run_id == UUID(run_id))
                .order_by(AgentTraceEvent.sequence)
            )
        )
        .scalars()
        .all()
    )

    assert result["memory_write_result"]["status"] == "written"
    assert [row.event_type for row in rows] == ["memory_write_started", "memory_write_completed"]
    assert all(row.operation_id is not None for row in rows)
    assert len({row.operation_id for row in rows}) == 1


async def test_memory_write_failure_events_carry_non_null_operation_id(monkeypatch):
    emissions = []

    class FailingMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def write_session_memory(self, candidate):
            raise RuntimeError("database unavailable")

    async def spy_emit_event(session, **kwargs):
        emissions.append(kwargs)
        return {
            "schema_version": "minimal_event_envelope.v1",
            "event_id": uuid4(),
            "sequence": len(emissions),
            "operation_id": kwargs.get("operation_id"),
            "run_id": UUID(str(kwargs["run_id"])),
            "tenant_id": UUID(str(kwargs["tenant_id"])),
            "thread_id": kwargs["thread_id"],
            "trace_id": kwargs.get("trace_id"),
            "event_type": kwargs["event_type"],
            "occurred_at": datetime.now(UTC),
            "actor": kwargs["actor"],
            "resource_refs": kwargs["resource_refs"],
            "redaction_policy_version": "redaction.v1",
            "redacted_payload": kwargs["redacted_payload"],
        }

    monkeypatch.setattr(memory_write_module, "MemoryService", FailingMemoryService)
    monkeypatch.setattr(memory_write_module, "emit_event", spy_emit_event)

    result = await memory_write(_state(), {"configurable": {"session": object(), "trace_id": "failure-op-test"}})

    event_types = [event["event_type"] for event in emissions]
    operation_ids = [event["operation_id"] for event in emissions]
    assert result["memory_write_result"]["status"] == "error"
    assert event_types == ["memory_write_started", "memory_write_failed"]
    assert all(operation_id is not None for operation_id in operation_ids)
    assert len(set(operation_ids)) == 1


async def test_memory_write_prohibited_pii_skips_without_persisting(monkeypatch):
    called = False

    class FakeMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def write_session_memory(self, candidate):
            nonlocal called
            called = True
            return SessionMemoryWriteResult(
                status="written",
                version=4,
                decision="write",
                reason_code="eligible",
                pii_classification="none",
            )

    monkeypatch.setattr(memory_write_module, "MemoryService", FakeMemoryService)

    result = await memory_write(
        _state(extracted_slots={"order_id": "身份证 110101199001011234"}),
        {"configurable": {"session": object()}},
    )

    assert called is False
    assert result["memory_write_result"]["status"] == "skipped"
    assert result["memory_write_result"]["decision"] == "skip"
    assert result["memory_write_result"]["pii_classification"] == "prohibited"
    assert result["memory_write_result"]["reason_code"] == "pii_blocked"
    assert result["memory_write_decision"]["schema_version"] == "memory_write_decision.v2"
    assert result["memory_write_decision"]["status"] == "skipped"
    assert result["memory_write_decision"]["decision"] == "skip"
    assert result["memory_write_decision"]["pii_classification"] == "prohibited"
    assert result["memory_write_decision"]["reason_code"] == "pii_blocked"


@pytest.mark.parametrize("raw_identifier", ["13800138000", "110101199001011234", "api_key=sk_test_1234567890"])
async def test_memory_write_raw_sensitive_pii_skips_without_persisting(monkeypatch, raw_identifier: str):
    called = False

    class FakeMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def write_session_memory(self, candidate):
            nonlocal called
            called = True
            return SessionMemoryWriteResult(
                status="written",
                version=4,
                decision="write",
                reason_code="eligible",
                pii_classification="none",
            )

    monkeypatch.setattr(memory_write_module, "MemoryService", FakeMemoryService)

    result = await memory_write(
        _state(extracted_slots={"order_id": raw_identifier}),
        {"configurable": {"session": object()}},
    )

    assert called is False
    assert result["memory_write_result"]["status"] == "skipped"
    assert result["memory_write_result"]["decision"] == "skip"
    assert result["memory_write_result"]["pii_classification"] == "sensitive"
    assert result["memory_write_result"]["reason_code"] == "pii_blocked"
    assert result["memory_write_decision"]["status"] == "skipped"
    assert result["memory_write_decision"]["decision"] == "skip"
    assert result["memory_write_decision"]["pii_classification"] == "sensitive"
    assert result["memory_write_decision"]["reason_code"] == "pii_blocked"
