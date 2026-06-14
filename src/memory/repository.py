from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import Text, and_, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import SessionMemory


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
