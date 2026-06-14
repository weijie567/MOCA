from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AgentRun
from src.memory.repository import SessionMemoryRepository
from src.memory.schemas import SessionMemoryWriteCandidate, SessionSlotV1
from src.memory.service import MemoryService


def _slot(
    value: str,
    *,
    run_id: str | None = None,
    expires_at: datetime | None = None,
    intents: list[str] | None = None,
) -> SessionSlotV1:
    now = datetime.now(UTC)
    return SessionSlotV1(
        value=value,
        source="explicit_user",
        source_run_id=run_id or str(uuid.uuid4()),
        updated_at=now,
        expires_at=expires_at or now + timedelta(minutes=30),
        compatible_intents=intents or ["refund_troubleshooting"],
    )


def _envelope(value: str, *, run_id: str | None = None, expires_at: datetime | None = None) -> dict:
    return {
        "schema_version": "session_slots.v1",
        "slots": {"order_id": _slot(value, run_id=run_id, expires_at=expires_at).model_dump(mode="json")},
    }


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


def _candidate(
    seeded_session: dict,
    *,
    thread_id: str,
    run_id: uuid.UUID | None = None,
    expected_version: int | None = None,
    slots: dict[str, SessionSlotV1] | None = None,
    session_summary: str | None = None,
    unresolved_questions: list[str] | None = None,
    last_intent: str | None = "refund_troubleshooting",
    last_business_context_refs: dict | None = None,
    pii_classification: str = "none",
    decision: str = "write",
    reason_code: str = "eligible",
) -> SessionMemoryWriteCandidate:
    return SessionMemoryWriteCandidate(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id=thread_id,
        run_id=run_id or uuid.uuid4(),
        expected_version=expected_version,
        explicit_slots=slots or {},
        unresolved_questions=unresolved_questions or [],
        last_intent=last_intent,
        session_summary=session_summary,
        last_business_context_refs=last_business_context_refs or {},
        pii_classification=pii_classification,
        decision=decision,
        reason_code=reason_code,
    )


@pytest.mark.asyncio
async def test_service_merge_current_explicit_overrides_existing(session: AsyncSession, seeded_session: dict) -> None:
    repository = SessionMemoryRepository(session)
    existing = await repository.insert_active(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id="thread-service-explicit",
        active_slots_json=_envelope("ORD-OLD"),
    )
    service = MemoryService(repository)

    result = await service.write_session_memory(
        _candidate(
            seeded_session,
            thread_id="thread-service-explicit",
            run_id=await _insert_run(session, seeded_session, "thread-service-explicit"),
            expected_version=existing.version,
            slots={"order_id": _slot("ORD-NEW")},
        )
    )
    view = await service.load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        "thread-service-explicit",
        current_intent="refund_troubleshooting",
    )

    assert result.status == "written"
    assert view.active_slots["order_id"] == "ORD-NEW"
    assert view.slot_metadata["order_id"]["source"] == "trusted_session_memory"


@pytest.mark.asyncio
async def test_service_merge_preserves_non_slot_fields_on_safe_cas_retry(
    session: AsyncSession, seeded_session: dict
) -> None:
    repository = SessionMemoryRepository(session)
    existing = await repository.insert_active(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id="thread-service-safe-cas",
        active_slots_json=_envelope("ORD-OLD"),
        session_summary="existing summary",
        unresolved_questions_json=["existing question"],
        last_intent="order_status_inquiry",
        last_business_context_refs_json={"order": "ORD-OLD"},
    )
    await repository.cas_update(
        existing.id,
        expected_version=existing.version,
        values={
            "session_summary": "concurrent summary",
            "unresolved_questions_json": ["existing question", "concurrent question"],
            "last_intent": "refund_troubleshooting",
            "last_business_context_refs_json": {"order": "ORD-OLD", "ticket": "TK-1"},
        },
    )
    service = MemoryService(repository)

    result = await service.write_session_memory(
        _candidate(
            seeded_session,
            thread_id="thread-service-safe-cas",
            run_id=await _insert_run(session, seeded_session, "thread-service-safe-cas"),
            expected_version=1,
            slots={"refund_case_id": _slot("RF-1")},
            session_summary="candidate summary",
            unresolved_questions=["candidate question"],
            last_intent="merchant_refund_policy",
            last_business_context_refs={"refund_case": "RF-1"},
        )
    )
    view = await service.load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        "thread-service-safe-cas",
        current_intent="refund_troubleshooting",
    )

    assert result.status == "merged_after_conflict"
    assert view.active_slots["order_id"] == "ORD-OLD"
    assert view.active_slots["refund_case_id"] == "RF-1"
    assert "concurrent summary" in (view.session_summary or "")
    assert "candidate summary" in (view.session_summary or "")
    assert "concurrent question" in view.unresolved_questions
    assert "candidate question" in view.unresolved_questions
    assert view.last_intent == "refund_troubleshooting"
    assert view.last_business_context_refs == {"order": "ORD-OLD", "ticket": "TK-1", "refund_case": "RF-1"}


@pytest.mark.asyncio
async def test_service_merge_without_slots_does_not_expire_context_only_memory(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    now = datetime.now(UTC)
    repository = SessionMemoryRepository(session)
    existing = await repository.insert_active(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id="thread-service-context-only",
        active_slots_json={"schema_version": "session_slots.v1", "slots": {}},
        session_summary="existing context",
        unresolved_questions_json=["existing question"],
        last_intent="refund_troubleshooting",
    )
    service = MemoryService(repository)

    result = await service.write_session_memory(
        _candidate(
            seeded_session,
            thread_id="thread-service-context-only",
            run_id=await _insert_run(session, seeded_session, "thread-service-context-only"),
            expected_version=existing.version,
            slots={},
            session_summary="new context",
            unresolved_questions=["new question"],
            last_intent="refund_troubleshooting",
        ),
        now=now,
    )
    view = await service.load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        "thread-service-context-only",
        current_intent="refund_troubleshooting",
        now=now + timedelta(seconds=1),
    )

    assert result.status == "written"
    assert view.continuity_claimed is True
    assert view.active_slots == {}
    assert "existing context" in (view.session_summary or "")
    assert "new context" in (view.session_summary or "")
    assert "existing question" in view.unresolved_questions
    assert "new question" in view.unresolved_questions


@pytest.mark.asyncio
async def test_service_cas_miss_reloads_and_merges_or_conflicts(session: AsyncSession, seeded_session: dict) -> None:
    repository = SessionMemoryRepository(session)
    existing = await repository.insert_active(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id="thread-service-cas-conflict",
        active_slots_json=_envelope("ORD-LATEST", run_id="latest-run"),
    )
    await repository.cas_update(existing.id, expected_version=1, values={"active_slots_json": _envelope("ORD-LATEST")})
    service = MemoryService(repository)

    result = await service.write_session_memory(
        _candidate(
            seeded_session,
            thread_id="thread-service-cas-conflict",
            run_id=await _insert_run(session, seeded_session, "thread-service-cas-conflict"),
            expected_version=1,
            slots={"order_id": _slot("ORD-CANDIDATE", run_id="candidate-run")},
        )
    )

    assert result.status in {"merged_after_conflict", "conflict"}
    assert result.status == "conflict"
    assert result.reason_code == "explicit_slot_conflict"
    assert result.conflict_reason == "explicit_slot_conflict"


@pytest.mark.asyncio
async def test_service_write_after_expired_active_row_reuses_or_replaces_scope(
    session: AsyncSession, seeded_session: dict
) -> None:
    repository = SessionMemoryRepository(session)
    await repository.insert_active(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id="thread-service-expired-write",
        active_slots_json=_envelope("ORD-EXPIRED", expires_at=datetime.now(UTC) - timedelta(minutes=5)),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    service = MemoryService(repository)

    result = await service.write_session_memory(
        _candidate(
            seeded_session,
            thread_id="thread-service-expired-write",
            run_id=await _insert_run(session, seeded_session, "thread-service-expired-write"),
            slots={"order_id": _slot("ORD-FRESH")},
        )
    )
    view = await service.load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        "thread-service-expired-write",
        current_intent="refund_troubleshooting",
    )

    assert result.status == "written"
    assert view.active_slots["order_id"] == "ORD-FRESH"


@pytest.mark.asyncio
async def test_service_initial_slot_insert_expires_row_level_continuity(
    session: AsyncSession, seeded_session: dict
) -> None:
    now = datetime.now(UTC)
    thread_id = "thread-service-initial-row-expiry"
    repository = SessionMemoryRepository(session)
    service = MemoryService(repository)

    result = await service.write_session_memory(
        _candidate(
            seeded_session,
            thread_id=thread_id,
            run_id=await _insert_run(session, seeded_session, thread_id),
            slots={"order_id": _slot("ORD-TTL", expires_at=now + timedelta(seconds=1))},
            session_summary="summary generated from ORD-TTL",
            unresolved_questions=["question generated from ORD-TTL"],
            last_intent="refund_troubleshooting",
            last_business_context_refs={"order": "ORD-TTL"},
        ),
        now=now,
    )
    view = await service.load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        thread_id,
        current_intent="refund_troubleshooting",
        now=now + timedelta(seconds=2),
    )

    assert result.status == "written"
    assert view.source == "expired"
    assert view.continuity_claimed is False
    assert view.active_slots == {}


@pytest.mark.asyncio
async def test_service_fallback_result_is_typed(session: AsyncSession, seeded_session: dict) -> None:
    repository = SessionMemoryRepository(session)
    service = MemoryService(repository)

    missing = await service.load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        "thread-service-missing",
        current_intent="refund_troubleshooting",
    )
    disabled = await MemoryService(repository, enabled=False).load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        "thread-service-disabled",
        current_intent="refund_troubleshooting",
    )
    expired_row = await repository.insert_active(
        tenant_id=seeded_session["tenant"].id,
        user_id=seeded_session["users"]["cs_zhang"].id,
        thread_id="thread-service-expired-read",
        active_slots_json=_envelope("ORD-EXPIRED", expires_at=datetime.now(UTC) - timedelta(minutes=5)),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    expired = await service.load_session_memory(
        expired_row.tenant_id,
        expired_row.user_id,
        expired_row.thread_id,
        current_intent="refund_troubleshooting",
    )

    assert missing.continuity_claimed is False
    assert missing.fallback_reason == "missing_session"
    assert disabled.source == "disabled"
    assert disabled.active_slots == {}
    assert expired.source == "expired"
    assert expired.continuity_claimed is False


@pytest.mark.asyncio
async def test_write_decision_subset_is_observable(session: AsyncSession, seeded_session: dict) -> None:
    repository = SessionMemoryRepository(session)
    service = MemoryService(repository)

    result = await service.write_session_memory(
        _candidate(
            seeded_session,
            thread_id="thread-service-pii",
            run_id=await _insert_run(session, seeded_session, "thread-service-pii"),
            slots={"order_id": _slot("ORD-SENSITIVE")},
            pii_classification="prohibited",
            decision="skip",
            reason_code="pii_blocked",
        )
    )
    view = await service.load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        "thread-service-pii",
        current_intent="refund_troubleshooting",
    )

    assert result.pii_classification == "prohibited"
    assert result.decision == "skip"
    assert result.reason_code == "pii_blocked"
    assert result.status == "skipped"
    assert view.continuity_claimed is False


@pytest.mark.asyncio
async def test_service_blocks_sensitive_pii_even_when_candidate_requests_write(
    session: AsyncSession, seeded_session: dict
) -> None:
    repository = SessionMemoryRepository(session)
    service = MemoryService(repository)

    result = await service.write_session_memory(
        _candidate(
            seeded_session,
            thread_id="thread-service-sensitive-pii",
            run_id=await _insert_run(session, seeded_session, "thread-service-sensitive-pii"),
            slots={"order_id": _slot("13800138000")},
            pii_classification="sensitive",
            decision="write",
            reason_code="eligible",
        )
    )
    view = await service.load_session_memory(
        seeded_session["tenant"].id,
        seeded_session["users"]["cs_zhang"].id,
        "thread-service-sensitive-pii",
        current_intent="refund_troubleshooting",
    )

    assert result.status == "skipped"
    assert result.decision == "skip"
    assert result.reason_code == "pii_blocked"
    assert result.pii_classification == "sensitive"
    assert view.continuity_claimed is False
