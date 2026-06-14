from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.repository import SessionMemoryRepository


def _slots(value: str = "ORD-1001") -> dict:
    now = datetime.now(UTC)
    return {
        "schema_version": "session_slots.v1",
        "slots": {
            "order_id": {
                "value": value,
                "source": "explicit_user",
                "source_run_id": str(uuid.uuid4()),
                "updated_at": now.isoformat(),
                "expires_at": (now + timedelta(minutes=30)).isoformat(),
                "compatible_intents": ["refund_troubleshooting"],
            }
        },
    }


@pytest.mark.asyncio
async def test_repository_enforces_one_active_scope(session: AsyncSession, seeded_session: dict) -> None:
    unique_index_name = "uq_session_memories_active_scope"
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    repository = SessionMemoryRepository(session)

    first = await repository.insert_active(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id="thread-repo-active",
        active_slots_json=_slots("ORD-1001"),
    )
    await session.commit()

    with pytest.raises(IntegrityError):
        await repository.insert_active(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id="thread-repo-active",
            active_slots_json=_slots("ORD-1002"),
        )
    assert unique_index_name == "uq_session_memories_active_scope"
    await session.rollback()

    await repository.soft_delete(first.id)
    replacement = await repository.insert_active(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id="thread-repo-active",
        active_slots_json=_slots("ORD-1003"),
    )

    assert replacement.id != first.id
    assert replacement.deleted_at is None


@pytest.mark.asyncio
async def test_repository_cas_update_increments_version(session: AsyncSession, seeded_session: dict) -> None:
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    repository = SessionMemoryRepository(session)
    memory = await repository.insert_active(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id="thread-repo-cas",
        active_slots_json=_slots("ORD-1001"),
    )

    updated = await repository.cas_update(
        memory.id,
        expected_version=1,
        values={"active_slots_json": _slots("ORD-1002")},
    )
    await session.refresh(memory)
    stale = await repository.cas_update(
        memory.id,
        expected_version=1,
        values={"active_slots_json": _slots("ORD-1003")},
    )

    assert updated is True
    assert memory.version == 2
    assert stale is False
