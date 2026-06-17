from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import LongTermMemory, MemoryTombstone
from src.memory.identity import canonical_memory_content_hash, canonical_source_identity_hash
from src.memory.repository import LongTermMemoryRepository
from src.memory.schemas import LongTermMemoryView


def _memory(
    *,
    tenant_id: uuid.UUID,
    scope_type: str,
    scope_id: str,
    content: str,
    review_status: str = "auto_approved",
    is_current: bool = True,
    deleted_at: datetime | None = None,
    expires_at: datetime | None = None,
    pii_classification: str = "none",
    source_identity_hash: str | None = None,
) -> LongTermMemory:
    return LongTermMemory(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        memory_kind="preference",
        content=content,
        content_hash=canonical_memory_content_hash(memory_type="long_term_fact", content=content),
        source_type="human_reviewed",
        source_ref_json={"source_type": "human_reviewed"},
        source_identity_hash=source_identity_hash,
        confidence=Decimal("0.9000"),
        pii_classification=pii_classification,
        review_status=review_status,
        is_current=is_current,
        expires_at=expires_at,
        deleted_at=deleted_at,
    )


@pytest.mark.asyncio
async def test_retrieve_profile_memory_excludes_unpublished_states(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    now = datetime.now(UTC)
    tenant_id = seeded_session["tenant"].id
    other_tenant_id = seeded_session["other_tenant"].id
    scope_type = "merchant"
    scope_id = str(seeded_session["merchant"].id)
    other_scope_id = str(uuid.uuid4())

    visible_auto = _memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        content="Visible auto-approved memory.",
        review_status="auto_approved",
    )
    visible_approved = _memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        content="Visible manually approved memory.",
        review_status="approved",
    )
    rejected = _memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        content="Rejected memory must not surface.",
        review_status="rejected",
    )
    needs_review = _memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        content="Needs-review memory must not surface.",
        review_status="needs_review",
    )
    deleted = _memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        content="Deleted memory must not surface.",
        deleted_at=now,
    )
    expired = _memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        content="Expired memory must not surface.",
        expires_at=now - timedelta(seconds=1),
    )
    prohibited = _memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        content="Prohibited PII memory must not surface.",
        pii_classification="prohibited",
    )
    superseded = _memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        content="Superseded memory must not surface.",
        review_status="superseded",
        is_current=False,
    )
    cross_tenant = _memory(
        tenant_id=other_tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        content="Cross-tenant memory must not surface.",
    )
    out_of_scope = _memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=other_scope_id,
        content="Out-of-scope memory must not surface.",
    )
    tombstoned = _memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        content="Tombstoned memory must not surface.",
    )
    source_identity_hash = canonical_source_identity_hash({"source_type": "conversation_message", "event_id": "event-1"})
    source_tombstoned = _memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        content="Source-tombstoned memory must not surface.",
        source_identity_hash=source_identity_hash,
    )
    session.add_all(
        [
            visible_auto,
            visible_approved,
            rejected,
            needs_review,
            deleted,
            expired,
            prohibited,
            superseded,
            cross_tenant,
            out_of_scope,
            tombstoned,
            source_tombstoned,
        ]
    )
    await session.flush()
    session.add(
        MemoryTombstone(
            tenant_id=tenant_id,
            memory_type="long_term_fact",
            scope_type=scope_type,
            scope_id=scope_id,
            content_hash=tombstoned.content_hash,
            source_ref_json={"source_type": "explicit_user_preference"},
            source_identity_hash=None,
            reason_code="user_deleted",
        )
    )
    session.add(
        MemoryTombstone(
            tenant_id=tenant_id,
            memory_type="long_term_fact",
            scope_type=scope_type,
            scope_id=scope_id,
            content_hash=None,
            source_ref_json={"source_type": "conversation_message", "event_id": "event-1"},
            source_identity_hash=source_identity_hash,
            reason_code="source_deleted",
        )
    )
    await session.flush()

    rows = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
        now=now,
    )

    contents = {row.content for row in rows}
    assert contents == {"Visible auto-approved memory.", "Visible manually approved memory."}
    assert all(row.review_status in {"auto_approved", "approved"} for row in rows)
    assert all(row.tenant_id == str(tenant_id) for row in rows)
    assert all(row.scope_type == scope_type and row.scope_id == scope_id for row in rows)


@pytest.mark.asyncio
async def test_retrieve_profile_memory_returns_bounded_views(session: AsyncSession, seeded_session: dict) -> None:
    tenant_id = seeded_session["tenant"].id
    scope_type = "merchant"
    scope_id = str(seeded_session["merchant"].id)
    session.add(
        _memory(
            tenant_id=tenant_id,
            scope_type=scope_type,
            scope_id=scope_id,
            content="x" * 1200,
            review_status="approved",
        )
    )
    await session.flush()

    rows = await LongTermMemoryRepository(session).retrieve_profile_memory(
        tenant_id=tenant_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )

    assert len(rows) == 1
    assert isinstance(rows[0], LongTermMemoryView)
    assert not isinstance(rows[0], LongTermMemory)
    assert len(rows[0].content) <= 1000
    assert "[memory_truncated]" in rows[0].content
