from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.repository import SessionMemoryRepository
from src.memory.schemas import SessionSlotV1
from src.memory.service import MemoryService


def _slot(
    value: str,
    *,
    expires_at: datetime | None = None,
    intents: list[str] | None = None,
) -> SessionSlotV1:
    now = datetime.now(UTC)
    return SessionSlotV1(
        value=value,
        source="explicit_user",
        source_run_id=str(uuid4()),
        updated_at=now,
        expires_at=expires_at or now + timedelta(minutes=30),
        compatible_intents=intents or ["refund_troubleshooting"],
    )


def _envelope(slots: dict[str, SessionSlotV1]) -> dict:
    return {
        "schema_version": "session_slots.v1",
        "slots": {key: slot.model_dump(mode="json") for key, slot in slots.items()},
    }


@pytest.mark.asyncio
async def test_load_session_memory_is_scoped_to_same_tenant_user_thread(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    other_user = seeded_session["users"]["other_support"]
    repository = SessionMemoryRepository(session)
    await repository.insert_active(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id="thread-isolation",
        active_slots_json=_envelope({"order_id": _slot("ORD-1001")}),
        session_summary="same thread summary",
        unresolved_questions_json=["same thread question"],
        last_intent="refund_troubleshooting",
        last_business_context_refs_json={"order": "ORD-1001"},
    )
    service = MemoryService(repository)

    same_scope = await service.load_session_memory(
        user.tenant_id,
        user.id,
        "thread-isolation",
        current_intent="refund_troubleshooting",
    )
    different_thread = await service.load_session_memory(
        user.tenant_id,
        user.id,
        "thread-other",
        current_intent="refund_troubleshooting",
    )
    different_user = await service.load_session_memory(
        user.tenant_id,
        other_user.id,
        "thread-isolation",
        current_intent="refund_troubleshooting",
    )
    different_tenant = await service.load_session_memory(
        seeded_session["other_tenant"].id,
        user.id,
        "thread-isolation",
        current_intent="refund_troubleshooting",
    )

    assert same_scope.continuity_claimed is True
    assert same_scope.active_slots == {"order_id": "ORD-1001"}
    assert same_scope.slot_metadata["order_id"]["tenant_id"] == str(user.tenant_id)
    assert same_scope.slot_metadata["order_id"]["user_id"] == str(user.id)
    assert same_scope.slot_metadata["order_id"]["thread_id"] == "thread-isolation"
    assert different_thread.continuity_claimed is False
    assert different_thread.active_slots == {}
    assert different_user.continuity_claimed is False
    assert different_user.active_slots == {}
    assert different_tenant.continuity_claimed is False
    assert different_tenant.active_slots == {}


@pytest.mark.asyncio
async def test_load_session_memory_filters_expired_and_incompatible_slots(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    repository = SessionMemoryRepository(session)
    await repository.insert_active(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id="thread-slot-filter",
        active_slots_json=_envelope(
            {
                "order_id": _slot("ORD-FRESH"),
                "refund_case_id": _slot("RF-EXPIRED", expires_at=datetime.now(UTC) - timedelta(minutes=1)),
                "ticket_id": _slot("TKT-INCOMPATIBLE", intents=["complaint_escalation"]),
            }
        ),
    )

    view = await MemoryService(repository).load_session_memory(
        user.tenant_id,
        user.id,
        "thread-slot-filter",
        current_intent="refund_troubleshooting",
    )

    assert view.active_slots == {"order_id": "ORD-FRESH"}
    assert set(view.slot_metadata) == {"order_id"}
