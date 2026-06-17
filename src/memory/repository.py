from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
import uuid

from sqlalchemy import Text, and_, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import LongTermMemory, MemoryTombstone, MemoryWriteEvent, SessionMemory
from src.memory.schemas import LongTermMemoryView, LongTermMemoryWriteCandidate


LONG_TERM_MEMORY_TYPE = "long_term_fact"
PUBLISHED_LONG_TERM_REVIEW_STATUSES = ("auto_approved", "approved")
_LONG_TERM_MEMORY_CONTENT_CAP = 1000


class SessionMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        *,
        include_expired: bool = False,
    ) -> SessionMemory | None:
        filters = [
            SessionMemory.tenant_id == tenant_id,
            SessionMemory.user_id == user_id,
            SessionMemory.thread_id == thread_id,
            SessionMemory.deleted_at.is_(None),
        ]
        if not include_expired:
            filters.append(or_(SessionMemory.expires_at.is_(None), SessionMemory.expires_at > func.now()))

        result = await self.session.execute(select(SessionMemory).where(and_(*filters)).execution_options(populate_existing=True))
        return result.scalar_one_or_none()

    async def insert_active(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        thread_id: str,
        active_slots_json: dict[str, Any] | None = None,
        session_summary: str | None = None,
        unresolved_questions_json: list[Any] | None = None,
        last_intent: str | None = None,
        last_business_context_refs_json: dict[str, Any] | None = None,
        last_run_id: uuid.UUID | None = None,
        expires_at: datetime | None = None,
    ) -> SessionMemory:
        memory = SessionMemory(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            active_slots_json=active_slots_json or {"schema_version": "session_slots.v1", "slots": {}},
            session_summary=session_summary,
            unresolved_questions_json=unresolved_questions_json or [],
            last_intent=last_intent,
            last_business_context_refs_json=last_business_context_refs_json or {},
            last_run_id=last_run_id,
            expires_at=expires_at,
        )
        self.session.add(memory)
        await self.session.flush()
        return memory

    async def search_active(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        limit: int = 5,
    ) -> list[SessionMemory]:
        filters = [
            SessionMemory.tenant_id == tenant_id,
            SessionMemory.user_id == user_id,
            SessionMemory.deleted_at.is_(None),
            or_(SessionMemory.expires_at.is_(None), SessionMemory.expires_at > func.now()),
        ]

        terms = _search_terms(query)
        if terms:
            searchable_fields = [
                SessionMemory.session_summary,
                SessionMemory.last_intent,
                cast(SessionMemory.active_slots_json, Text),
                cast(SessionMemory.unresolved_questions_json, Text),
                cast(SessionMemory.last_business_context_refs_json, Text),
            ]
            filters.append(
                or_(
                    *[
                        field.ilike(f"%{_escape_like(term)}%", escape="\\")
                        for term in terms[:8]
                        for field in searchable_fields
                    ]
                )
            )

        result = await self.session.execute(
            select(SessionMemory)
            .where(and_(*filters))
            .order_by(SessionMemory.updated_at.desc(), SessionMemory.created_at.desc())
            .limit(max(limit, 1))
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def cas_update(self, memory_id: uuid.UUID, expected_version: int, values: dict[str, Any]) -> bool:
        update_values = dict(values)
        update_values["version"] = SessionMemory.version + 1
        update_values["updated_at"] = func.now()
        result = await self.session.execute(
            update(SessionMemory)
            .where(
                SessionMemory.id == memory_id,
                SessionMemory.version == expected_version,
                SessionMemory.deleted_at.is_(None),
            )
            .values(**update_values)
        )
        await self.session.flush()
        return result.rowcount == 1

    async def soft_delete(self, memory_id: uuid.UUID) -> None:
        await self.session.execute(
            update(SessionMemory)
            .where(SessionMemory.id == memory_id, SessionMemory.deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC), updated_at=func.now())
        )
        await self.session.flush()


class LongTermMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert_memory(
        self,
        candidate: LongTermMemoryWriteCandidate,
        *,
        content_hash: str,
        source_ref_json: dict[str, Any],
        source_identity_hash: str | None,
        review_status: str,
        now: datetime | None = None,
    ) -> LongTermMemory:
        memory = LongTermMemory(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            memory_kind=candidate.memory_kind,
            content=candidate.content,
            content_hash=content_hash,
            source_type=candidate.source_type,
            source_ref_json=source_ref_json,
            source_identity_hash=source_identity_hash,
            confidence=Decimal(str(candidate.confidence)),
            pii_classification=candidate.pii_classification,
            review_status=review_status,
            valid_from=_aware(now),
            expires_at=candidate.expires_at,
            created_by_run_id=candidate.run_id,
        )
        self.session.add(memory)
        await self.session.flush()
        return memory

    async def emit_write_event(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        memory_type: str,
        memory_id: uuid.UUID | None,
        decision: str,
        reason_code: str,
        pii_classification: str,
        candidate_hash: str,
        source_ref_json: dict[str, Any],
    ) -> MemoryWriteEvent:
        event = MemoryWriteEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            run_id=run_id,
            memory_type=memory_type,
            memory_id=memory_id,
            decision=decision,
            reason_code=reason_code,
            pii_classification=pii_classification,
            candidate_hash=candidate_hash,
            source_ref_json=source_ref_json,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def retrieve_profile_memory(
        self,
        *,
        tenant_id: uuid.UUID,
        scope_type: str | None = None,
        scope_id: str | None = None,
        scopes: Sequence[tuple[str, str]] | None = None,
        now: datetime | None = None,
        limit: int = 10,
    ) -> list[LongTermMemoryView]:
        now = _aware(now)
        scope_filter = _scope_filter(scope_type=scope_type, scope_id=scope_id, scopes=scopes)
        active_tombstone = (
            select(MemoryTombstone.id)
            .where(
                MemoryTombstone.tenant_id == LongTermMemory.tenant_id,
                MemoryTombstone.memory_type == LONG_TERM_MEMORY_TYPE,
                MemoryTombstone.scope_type == LongTermMemory.scope_type,
                MemoryTombstone.scope_id == LongTermMemory.scope_id,
                MemoryTombstone.deleted_at.is_(None),
                or_(MemoryTombstone.expires_at.is_(None), MemoryTombstone.expires_at > now),
                or_(
                    and_(
                        MemoryTombstone.content_hash.is_not(None),
                        MemoryTombstone.content_hash == LongTermMemory.content_hash,
                    ),
                    and_(
                        MemoryTombstone.source_identity_hash.is_not(None),
                        LongTermMemory.source_identity_hash.is_not(None),
                        MemoryTombstone.source_identity_hash == LongTermMemory.source_identity_hash,
                    ),
                ),
            )
            .exists()
        )
        result = await self.session.execute(
            select(LongTermMemory)
            .where(
                LongTermMemory.tenant_id == tenant_id,
                scope_filter,
                LongTermMemory.review_status.in_(PUBLISHED_LONG_TERM_REVIEW_STATUSES),
                LongTermMemory.deleted_at.is_(None),
                LongTermMemory.is_current.is_(True),
                or_(LongTermMemory.expires_at.is_(None), LongTermMemory.expires_at > now),
                LongTermMemory.pii_classification != "prohibited",
                ~active_tombstone,
            )
            .order_by(LongTermMemory.updated_at.desc(), LongTermMemory.created_at.desc())
            .limit(max(1, min(limit, 50)))
            .execution_options(populate_existing=True)
        )
        return [_to_long_term_view(memory) for memory in result.scalars().all()]


def _search_terms(query: str) -> list[str]:
    normalized = query.strip().lower()
    if not normalized:
        return []
    terms = [term for term in normalized.split() if term]
    if len(normalized) <= 64:
        terms.append(normalized)
    deduped: list[str] = []
    for term in terms:
        if term not in deduped:
            deduped.append(term)
    return deduped


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _scope_filter(
    *,
    scope_type: str | None,
    scope_id: str | None,
    scopes: Sequence[tuple[str, str]] | None,
):
    if scopes:
        return or_(
            *[
                and_(LongTermMemory.scope_type == current_scope_type, LongTermMemory.scope_id == current_scope_id)
                for current_scope_type, current_scope_id in scopes
            ]
        )
    if scope_type is None or scope_id is None:
        raise ValueError("scope_type/scope_id or scopes is required")
    return and_(LongTermMemory.scope_type == scope_type, LongTermMemory.scope_id == scope_id)


def _to_long_term_view(memory: LongTermMemory) -> LongTermMemoryView:
    return LongTermMemoryView(
        memory_id=str(memory.id),
        tenant_id=str(memory.tenant_id),
        scope_type=memory.scope_type,
        scope_id=memory.scope_id,
        memory_kind=memory.memory_kind,
        content=_bounded_content(memory.content),
        source_type=memory.source_type,
        source_ref=dict(memory.source_ref_json or {}),
        review_status=memory.review_status,
        version=memory.version,
        valid_from=memory.valid_from,
        expires_at=memory.expires_at,
    )


def _bounded_content(value: str) -> str:
    if len(value) <= _LONG_TERM_MEMORY_CONTENT_CAP:
        return value
    return value[: _LONG_TERM_MEMORY_CONTENT_CAP - 20].rstrip() + "\n[memory_truncated]"


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
