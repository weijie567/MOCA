from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import AgentRun
from src.memory.repository import SessionMemoryRepository
from src.memory.schemas import SessionMemoryWriteCandidate, SessionSlotV1
from src.memory.service import MemoryService


def _slot(value: str, *, run_id: UUID | None = None, intents: list[str] | None = None) -> SessionSlotV1:
    now = datetime.now(UTC)
    return SessionSlotV1(
        value=value,
        source="explicit_user",
        source_run_id=str(run_id or uuid4()),
        updated_at=now,
        expires_at=now + timedelta(minutes=30),
        compatible_intents=intents or ["refund_troubleshooting"],
    )


def _envelope(slots: dict[str, SessionSlotV1]) -> dict:
    return {
        "schema_version": "session_slots.v1",
        "slots": {key: slot.model_dump(mode="json") for key, slot in slots.items()},
    }


async def _insert_run(session: AsyncSession, seeded_session: dict, thread_id: str) -> UUID:
    run_id = uuid4()
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=seeded_session["tenant"].id,
            user_id=seeded_session["users"]["cs_zhang"].id,
            thread_id=thread_id,
            input_query="session memory concurrency",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return run_id


def _candidate(
    seeded_session: dict,
    *,
    thread_id: str,
    run_id: UUID,
    expected_version: int,
    slots: dict[str, SessionSlotV1],
    session_summary: str,
    unresolved_questions: list[str],
    last_intent: str,
    last_business_context_refs: dict,
) -> SessionMemoryWriteCandidate:
    return SessionMemoryWriteCandidate(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id=thread_id,
        run_id=run_id,
        expected_version=expected_version,
        explicit_slots=slots,
        session_summary=session_summary,
        unresolved_questions=unresolved_questions,
        last_intent=last_intent,
        last_business_context_refs=last_business_context_refs,
        pii_classification="none",
        decision="write",
        reason_code="eligible",
    )


async def _write_with_new_session(session_factory, candidate: SessionMemoryWriteCandidate):
    async with session_factory() as session:
        result = await MemoryService(SessionMemoryRepository(session)).write_session_memory(candidate)
        await session.commit()
        return result


@pytest.mark.asyncio
async def test_concurrent_first_writes_to_empty_scope_merge_without_lost_updates(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    thread_id = "thread-concurrent-empty-scope"
    first_run = await _insert_run(session, seeded_session, thread_id)
    second_run = await _insert_run(session, seeded_session, thread_id)
    await session.commit()
    session_factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)

    first = _candidate(
        seeded_session,
        thread_id=thread_id,
        run_id=first_run,
        expected_version=1,
        slots={"order_id": _slot("ORD-FIRST", run_id=first_run)},
        session_summary="first empty-scope summary",
        unresolved_questions=["first empty-scope question"],
        last_intent="refund_troubleshooting",
        last_business_context_refs={"order": "ORD-FIRST"},
    )
    second = _candidate(
        seeded_session,
        thread_id=thread_id,
        run_id=second_run,
        expected_version=1,
        slots={"refund_case_id": _slot("RF-SECOND", run_id=second_run)},
        session_summary="second empty-scope summary",
        unresolved_questions=["second empty-scope question"],
        last_intent="refund_troubleshooting",
        last_business_context_refs={"refund_case": "RF-SECOND"},
    )

    results = await asyncio.gather(
        _write_with_new_session(session_factory, first),
        _write_with_new_session(session_factory, second),
    )

    view = await MemoryService(SessionMemoryRepository(session)).load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        thread_id,
        current_intent="refund_troubleshooting",
    )
    assert {result.status for result in results} <= {"written", "merged_after_conflict"}
    assert view.active_slots["order_id"] == "ORD-FIRST"
    assert view.active_slots["refund_case_id"] == "RF-SECOND"
    assert "first empty-scope question" in view.unresolved_questions
    assert "second empty-scope question" in view.unresolved_questions
    assert view.last_business_context_refs == {"order": "ORD-FIRST", "refund_case": "RF-SECOND"}


@pytest.mark.asyncio
async def test_concurrent_replacement_of_expired_scope_merges_without_lost_updates(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    thread_id = "thread-concurrent-expired-scope"
    first_run = await _insert_run(session, seeded_session, thread_id)
    second_run = await _insert_run(session, seeded_session, thread_id)
    repository = SessionMemoryRepository(session)
    await repository.insert_active(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id=thread_id,
        active_slots_json=_envelope({"order_id": _slot("ORD-EXPIRED")}),
        session_summary="expired summary",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    await session.commit()
    session_factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)

    first = _candidate(
        seeded_session,
        thread_id=thread_id,
        run_id=first_run,
        expected_version=1,
        slots={"order_id": _slot("ORD-FRESH", run_id=first_run)},
        session_summary="fresh order summary",
        unresolved_questions=[],
        last_intent="refund_troubleshooting",
        last_business_context_refs={"order": "ORD-FRESH"},
    )
    second = _candidate(
        seeded_session,
        thread_id=thread_id,
        run_id=second_run,
        expected_version=1,
        slots={"refund_case_id": _slot("RF-FRESH", run_id=second_run)},
        session_summary="fresh refund summary",
        unresolved_questions=[],
        last_intent="refund_troubleshooting",
        last_business_context_refs={"refund_case": "RF-FRESH"},
    )

    results = await asyncio.gather(
        _write_with_new_session(session_factory, first),
        _write_with_new_session(session_factory, second),
    )

    view = await MemoryService(SessionMemoryRepository(session)).load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        thread_id,
        current_intent="refund_troubleshooting",
    )
    assert {result.status for result in results} <= {"written", "merged_after_conflict"}
    assert view.active_slots["order_id"] == "ORD-FRESH"
    assert view.active_slots["refund_case_id"] == "RF-FRESH"
    assert view.last_business_context_refs == {"order": "ORD-FRESH", "refund_case": "RF-FRESH"}


@pytest.mark.asyncio
async def test_concurrent_non_conflicting_writes_merge_without_lost_updates(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    thread_id = "thread-concurrent-safe-merge"
    first_run = await _insert_run(session, seeded_session, thread_id)
    second_run = await _insert_run(session, seeded_session, thread_id)
    repository = SessionMemoryRepository(session)
    existing = await repository.insert_active(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id=thread_id,
        active_slots_json=_envelope({"merchant_id": _slot("M-1001")}),
        session_summary="existing summary",
        unresolved_questions_json=["existing question"],
        last_intent="refund_troubleshooting",
        last_business_context_refs_json={"merchant": "M-1001"},
    )
    await session.commit()
    session_factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)

    first = _candidate(
        seeded_session,
        thread_id=thread_id,
        run_id=first_run,
        expected_version=existing.version,
        slots={"order_id": _slot("ORD-1001", run_id=first_run)},
        session_summary="order summary",
        unresolved_questions=["order question"],
        last_intent="refund_troubleshooting",
        last_business_context_refs={"order": "ORD-1001"},
    )
    second = _candidate(
        seeded_session,
        thread_id=thread_id,
        run_id=second_run,
        expected_version=existing.version,
        slots={"refund_case_id": _slot("RF-1001", run_id=second_run)},
        session_summary="refund summary",
        unresolved_questions=["refund question"],
        last_intent="refund_troubleshooting",
        last_business_context_refs={"refund_case": "RF-1001"},
    )

    results = await asyncio.gather(
        _write_with_new_session(session_factory, first),
        _write_with_new_session(session_factory, second),
    )

    view = await MemoryService(SessionMemoryRepository(session)).load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        thread_id,
        current_intent="refund_troubleshooting",
    )
    assert {result.status for result in results} <= {"written", "merged_after_conflict"}
    assert view.version is not None and view.version >= 2
    assert view.active_slots["merchant_id"] == "M-1001"
    assert view.active_slots["order_id"] == "ORD-1001"
    assert view.active_slots["refund_case_id"] == "RF-1001"
    assert "existing question" in view.unresolved_questions
    assert "order question" in view.unresolved_questions
    assert "refund question" in view.unresolved_questions
    assert "order summary" in (view.session_summary or "")
    assert "refund summary" in (view.session_summary or "")
    assert view.last_business_context_refs == {
        "merchant": "M-1001",
        "order": "ORD-1001",
        "refund_case": "RF-1001",
    }


@pytest.mark.asyncio
async def test_concurrent_explicit_slot_conflict_returns_reason_code(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    thread_id = "thread-concurrent-slot-conflict"
    first_run = await _insert_run(session, seeded_session, thread_id)
    second_run = await _insert_run(session, seeded_session, thread_id)
    repository = SessionMemoryRepository(session)
    existing = await repository.insert_active(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id=thread_id,
        active_slots_json=_envelope({"merchant_id": _slot("M-1001")}),
    )
    await session.commit()
    session_factory = async_sessionmaker(session.bind, expire_on_commit=False, class_=AsyncSession)
    first = _candidate(
        seeded_session,
        thread_id=thread_id,
        run_id=first_run,
        expected_version=existing.version,
        slots={"order_id": _slot("ORD-A", run_id=first_run)},
        session_summary="first summary",
        unresolved_questions=[],
        last_intent="refund_troubleshooting",
        last_business_context_refs={},
    )
    second = _candidate(
        seeded_session,
        thread_id=thread_id,
        run_id=second_run,
        expected_version=existing.version,
        slots={"order_id": _slot("ORD-B", run_id=second_run)},
        session_summary="second summary",
        unresolved_questions=[],
        last_intent="refund_troubleshooting",
        last_business_context_refs={},
    )

    results = await asyncio.gather(
        _write_with_new_session(session_factory, first),
        _write_with_new_session(session_factory, second),
    )

    conflict = [result for result in results if result.status == "conflict"]
    assert len(conflict) == 1
    assert conflict[0].reason_code == "explicit_slot_conflict"
    assert conflict[0].conflict_reason == "explicit_slot_conflict"


@pytest.mark.asyncio
async def test_stale_expected_version_merges_safe_fields_and_conflicts_json_overwrite(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    thread_id = "thread-stale-version-json-conflict"
    run_id = await _insert_run(session, seeded_session, thread_id)
    repository = SessionMemoryRepository(session)
    existing = await repository.insert_active(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id=thread_id,
        active_slots_json=_envelope({"order_id": _slot("ORD-1001")}),
        last_business_context_refs_json={"order": "ORD-1001"},
    )
    stale_version = existing.version
    await repository.cas_update(
        existing.id,
        expected_version=stale_version,
        values={"last_business_context_refs_json": {"order": "ORD-CONCURRENT"}},
    )
    result = await MemoryService(repository).write_session_memory(
        _candidate(
            seeded_session,
            thread_id=thread_id,
            run_id=run_id,
            expected_version=stale_version,
            slots={"refund_case_id": _slot("RF-1001", run_id=run_id)},
            session_summary="candidate summary",
            unresolved_questions=["candidate question"],
            last_intent="refund_troubleshooting",
            last_business_context_refs={"order": "ORD-CANDIDATE"},
        )
    )

    assert result.status == "conflict"
    assert result.reason_code == "business_context_ref_conflict"
    assert result.conflict_reason == "business_context_ref_conflict"
