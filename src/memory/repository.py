from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
import uuid

from sqlalchemy import Text, and_, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import LongTermMemory, MemoryTombstone, MemoryWriteEvent, SessionMemory
from src.memory.policy import (
    MEMORY_POLICY_AUTHORITY_CLASS,
    MEMORY_POLICY_VERSION,
    PROMPT_SAFE_PII_CLASSIFICATIONS,
    PUBLISHED_LONG_TERM_SOURCE_TYPES,
)
from src.memory.schemas import LongTermMemoryView, LongTermMemoryWriteCandidate
from src.memory.tombstones import source_identity_hash_for_tombstone


LONG_TERM_MEMORY_TYPE = "long_term_fact"
SESSION_MEMORY_TYPE = "session_slot"
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

        result = await self.session.execute(
            select(SessionMemory).where(and_(*filters)).execution_options(populate_existing=True)
        )
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

    async def emit_write_event(
        self,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        memory_id: uuid.UUID | None,
        decision: str,
        reason_code: str,
        pii_classification: str,
        candidate_hash: str,
        source_ref_json: dict[str, Any],
        policy_version: str = MEMORY_POLICY_VERSION,
        blocked_by: list[str] | None = None,
        authority_class: str = MEMORY_POLICY_AUTHORITY_CLASS,
    ) -> MemoryWriteEvent:
        event = MemoryWriteEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            run_id=run_id,
            memory_type=SESSION_MEMORY_TYPE,
            memory_id=memory_id,
            decision=decision,
            reason_code=reason_code,
            policy_version=policy_version,
            blocked_by_json=list(blocked_by or []),
            authority_class=authority_class,
            pii_classification=pii_classification,
            candidate_hash=candidate_hash,
            source_ref_json=source_ref_json,
        )
        self.session.add(event)
        await self.session.flush()
        return event


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
        supersedes: uuid.UUID | None = None,
        version: int | None = None,
        is_current: bool = True,
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
            version=version or 1,
            supersedes=supersedes,
            is_current=is_current,
            valid_from=_aware(now),
            expires_at=candidate.expires_at,
            created_by_run_id=candidate.run_id,
        )
        self.session.add(memory)
        await self.session.flush()
        return memory

    async def get_active_by_content_hash(
        self,
        *,
        tenant_id: uuid.UUID,
        scope_type: str,
        scope_id: str,
        content_hash: str,
        now: datetime | None = None,
    ) -> LongTermMemory | None:
        now = _aware(now)
        result = await self.session.execute(
            select(LongTermMemory)
            .where(
                LongTermMemory.tenant_id == tenant_id,
                LongTermMemory.scope_type == scope_type,
                LongTermMemory.scope_id == scope_id,
                LongTermMemory.content_hash == content_hash,
                LongTermMemory.deleted_at.is_(None),
                LongTermMemory.is_current.is_(True),
                LongTermMemory.review_status.in_(PUBLISHED_LONG_TERM_REVIEW_STATUSES),
                or_(LongTermMemory.expires_at.is_(None), LongTermMemory.expires_at > now),
            )
            .order_by(LongTermMemory.updated_at.desc(), LongTermMemory.created_at.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def retire_expired_current_by_content_hash(
        self,
        *,
        tenant_id: uuid.UUID,
        scope_type: str,
        scope_id: str,
        content_hash: str,
        now: datetime | None = None,
    ) -> None:
        now = _aware(now)
        await self.session.execute(
            update(LongTermMemory)
            .where(
                LongTermMemory.tenant_id == tenant_id,
                LongTermMemory.scope_type == scope_type,
                LongTermMemory.scope_id == scope_id,
                LongTermMemory.content_hash == content_hash,
                LongTermMemory.deleted_at.is_(None),
                LongTermMemory.is_current.is_(True),
                LongTermMemory.expires_at.is_not(None),
                LongTermMemory.expires_at <= now,
            )
            .values(is_current=False, updated_at=func.now())
        )
        await self.session.flush()

    async def retire_unpublished_current_by_content_hash(
        self,
        *,
        tenant_id: uuid.UUID,
        scope_type: str,
        scope_id: str,
        content_hash: str,
    ) -> None:
        await self.session.execute(
            update(LongTermMemory)
            .where(
                LongTermMemory.tenant_id == tenant_id,
                LongTermMemory.scope_type == scope_type,
                LongTermMemory.scope_id == scope_id,
                LongTermMemory.content_hash == content_hash,
                LongTermMemory.deleted_at.is_(None),
                LongTermMemory.is_current.is_(True),
                LongTermMemory.review_status.not_in(PUBLISHED_LONG_TERM_REVIEW_STATUSES),
            )
            .values(is_current=False, updated_at=func.now())
        )
        await self.session.flush()

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
        policy_version: str = MEMORY_POLICY_VERSION,
        blocked_by: list[str] | None = None,
        authority_class: str = MEMORY_POLICY_AUTHORITY_CLASS,
    ) -> MemoryWriteEvent:
        event = MemoryWriteEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            run_id=run_id,
            memory_type=memory_type,
            memory_id=memory_id,
            decision=decision,
            reason_code=reason_code,
            policy_version=policy_version,
            blocked_by_json=list(blocked_by or []),
            authority_class=authority_class,
            pii_classification=pii_classification,
            candidate_hash=candidate_hash,
            source_ref_json=source_ref_json,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def create_tombstone(
        self,
        *,
        tenant_id: uuid.UUID,
        memory_type: str,
        scope_type: str,
        scope_id: str,
        content_hash: str | None,
        source_ref_json: dict[str, Any] | None,
        reason_code: str,
        source_identity_hash: str | None = None,
        created_by_user_id: uuid.UUID | None = None,
        created_by_run_id: uuid.UUID | None = None,
        expires_at: datetime | None = None,
        now: datetime | None = None,
    ) -> MemoryTombstone:
        now = _aware(now)
        source_ref_json = dict(source_ref_json or {})
        resolved_source_identity_hash = source_identity_hash or source_identity_hash_for_tombstone(source_ref_json)
        if content_hash is None and resolved_source_identity_hash is None:
            raise ValueError("content_hash or source_identity_hash is required for memory tombstone")

        await self._retire_expired_tombstones(
            tenant_id=tenant_id,
            memory_type=memory_type,
            scope_type=scope_type,
            scope_id=scope_id,
            content_hash=content_hash,
            source_identity_hash=resolved_source_identity_hash,
            now=now,
        )
        existing = await self.active_tombstone_matches(
            tenant_id=tenant_id,
            memory_type=memory_type,
            scope_type=scope_type,
            scope_id=scope_id,
            content_hash=content_hash,
            source_identity_hash=resolved_source_identity_hash,
            now=now,
        )
        if existing is not None:
            return existing

        tombstone = MemoryTombstone(
            tenant_id=tenant_id,
            memory_type=memory_type,
            scope_type=scope_type,
            scope_id=scope_id,
            content_hash=content_hash,
            source_ref_json=source_ref_json,
            source_identity_hash=resolved_source_identity_hash,
            reason_code=reason_code,
            created_by_user_id=created_by_user_id,
            created_by_run_id=created_by_run_id,
            expires_at=expires_at,
        )
        self.session.add(tombstone)
        await self.session.flush()
        return tombstone

    async def _retire_expired_tombstones(
        self,
        *,
        tenant_id: uuid.UUID,
        memory_type: str,
        scope_type: str,
        scope_id: str,
        content_hash: str | None,
        source_identity_hash: str | None,
        now: datetime,
    ) -> None:
        identity_filters = []
        if content_hash is not None:
            identity_filters.append(MemoryTombstone.content_hash == content_hash)
        if source_identity_hash is not None:
            identity_filters.append(MemoryTombstone.source_identity_hash == source_identity_hash)
        if not identity_filters:
            return
        await self.session.execute(
            update(MemoryTombstone)
            .where(
                MemoryTombstone.tenant_id == tenant_id,
                MemoryTombstone.memory_type == memory_type,
                MemoryTombstone.scope_type == scope_type,
                MemoryTombstone.scope_id == scope_id,
                MemoryTombstone.deleted_at.is_(None),
                MemoryTombstone.expires_at.is_not(None),
                MemoryTombstone.expires_at <= now,
                or_(*identity_filters),
            )
            .values(deleted_at=now)
        )
        await self.session.flush()

    async def active_tombstone_matches(
        self,
        *,
        tenant_id: uuid.UUID,
        memory_type: str,
        scope_type: str,
        scope_id: str,
        content_hash: str | None,
        source_identity_hash: str | None,
        now: datetime | None = None,
    ) -> MemoryTombstone | None:
        now = _aware(now)
        base_filters = [
            MemoryTombstone.tenant_id == tenant_id,
            MemoryTombstone.memory_type == memory_type,
            MemoryTombstone.scope_type == scope_type,
            MemoryTombstone.scope_id == scope_id,
            MemoryTombstone.deleted_at.is_(None),
            or_(MemoryTombstone.expires_at.is_(None), MemoryTombstone.expires_at > now),
        ]
        if content_hash is not None:
            result = await self.session.execute(
                select(MemoryTombstone)
                .where(*base_filters, MemoryTombstone.content_hash == content_hash)
                .order_by(MemoryTombstone.created_at.desc())
                .limit(1)
                .execution_options(populate_existing=True)
            )
            tombstone = result.scalar_one_or_none()
            if tombstone is not None:
                return tombstone

        if source_identity_hash is not None:
            result = await self.session.execute(
                select(MemoryTombstone)
                .where(*base_filters, MemoryTombstone.source_identity_hash == source_identity_hash)
                .order_by(MemoryTombstone.created_at.desc())
                .limit(1)
                .execution_options(populate_existing=True)
            )
            return result.scalar_one_or_none()

        return None

    async def check_tombstone_before_write(
        self,
        *,
        tenant_id: uuid.UUID,
        memory_type: str,
        scope_type: str,
        scope_id: str,
        content_hash: str | None,
        source_identity_hash: str | None,
        now: datetime | None = None,
    ) -> MemoryTombstone | None:
        return await self.active_tombstone_matches(
            tenant_id=tenant_id,
            memory_type=memory_type,
            scope_type=scope_type,
            scope_id=scope_id,
            content_hash=content_hash,
            source_identity_hash=source_identity_hash,
            now=now,
        )

    async def get_memory(self, *, tenant_id: uuid.UUID, memory_id: uuid.UUID) -> LongTermMemory | None:
        result = await self.session.execute(
            select(LongTermMemory)
            .where(LongTermMemory.tenant_id == tenant_id, LongTermMemory.id == memory_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_pending_review(self, *, tenant_id: uuid.UUID, limit: int = 50) -> list[LongTermMemory]:
        result = await self.session.execute(
            select(LongTermMemory)
            .where(
                LongTermMemory.tenant_id == tenant_id,
                LongTermMemory.review_status == "needs_review",
                LongTermMemory.deleted_at.is_(None),
            )
            .order_by(LongTermMemory.created_at.desc())
            .limit(max(1, min(limit, 100)))
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def update_review_status(
        self,
        *,
        tenant_id: uuid.UUID,
        memory_id: uuid.UUID,
        review_status: str,
        is_current: bool | None = None,
        source_type: str | None = None,
        source_ref_json: dict[str, Any] | None = None,
        source_identity_hash: str | None = None,
        expected_review_status: str | None = None,
        now: datetime | None = None,
    ) -> LongTermMemory | None:
        now = _aware(now)
        memory = await self.get_memory(tenant_id=tenant_id, memory_id=memory_id)
        if memory is None:
            return None
        if expected_review_status is not None and memory.review_status != expected_review_status:
            raise ValueError(f"long-term memory review requires {expected_review_status} status")
        if memory.deleted_at is not None or memory.review_status in {"deleted", "tombstoned", "superseded"}:
            raise ValueError("long-term memory review requires an active needs_review row")
        if review_status == "approved" and memory.expires_at is not None and _aware(memory.expires_at) <= now:
            raise ValueError("long-term memory approval requires an unexpired row")
        if review_status == "approved" and memory.supersedes is not None:
            previous = await self.get_memory(tenant_id=tenant_id, memory_id=memory.supersedes)
            if (
                previous is None
                or previous.deleted_at is not None
                or previous.is_current is not True
                or previous.review_status not in PUBLISHED_LONG_TERM_REVIEW_STATUSES
                or (previous.expires_at is not None and _aware(previous.expires_at) <= now)
            ):
                raise ValueError("superseded long-term memory is not current")
            previous.is_current = False
            previous.review_status = "superseded"
            previous.superseded_at = now
            previous.superseded_by = memory.id
        elif review_status == "approved" and is_current is True:
            await self.retire_expired_current_by_content_hash(
                tenant_id=memory.tenant_id,
                scope_type=memory.scope_type,
                scope_id=memory.scope_id,
                content_hash=memory.content_hash,
                now=now,
            )
            existing = await self.get_active_by_content_hash(
                tenant_id=memory.tenant_id,
                scope_type=memory.scope_type,
                scope_id=memory.scope_id,
                content_hash=memory.content_hash,
                now=now,
            )
            if existing is not None and existing.id != memory.id:
                raise ValueError("active long-term memory already exists for content")
        if source_type is not None:
            memory.source_type = source_type
        if source_ref_json is not None:
            memory.source_ref_json = source_ref_json
        if source_identity_hash is not None:
            memory.source_identity_hash = source_identity_hash
        memory.review_status = review_status
        if is_current is not None:
            memory.is_current = is_current
        await self.session.flush()
        return memory

    async def mark_deleted(
        self, *, tenant_id: uuid.UUID, memory_id: uuid.UUID, now: datetime | None = None
    ) -> LongTermMemory | None:
        memory = await self.get_memory(tenant_id=tenant_id, memory_id=memory_id)
        if memory is None:
            return None
        memory.review_status = "deleted"
        memory.is_current = False
        memory.deleted_at = _aware(now)
        await self.session.flush()
        return memory

    async def forget_memory(
        self,
        *,
        tenant_id: uuid.UUID,
        memory_id: uuid.UUID,
        memory_type: str,
        reason_code: str,
        run_id: uuid.UUID,
        now: datetime | None = None,
        review_status: str = "tombstoned",
    ) -> tuple[LongTermMemory, MemoryTombstone] | None:
        memory = await self.get_memory(tenant_id=tenant_id, memory_id=memory_id)
        if memory is None:
            return None
        now = _aware(now)
        memory.review_status = review_status
        memory.is_current = False
        memory.deleted_at = now
        tombstone = await self.create_tombstone(
            tenant_id=memory.tenant_id,
            memory_type=memory_type,
            scope_type=memory.scope_type,
            scope_id=memory.scope_id,
            content_hash=memory.content_hash,
            source_ref_json=dict(memory.source_ref_json or {}),
            source_identity_hash=memory.source_identity_hash,
            reason_code=reason_code,
            created_by_run_id=run_id,
            expires_at=memory.expires_at,
        )
        await self.session.flush()
        return memory, tombstone

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
                LongTermMemory.memory_kind == "preference",
                LongTermMemory.source_type.in_(tuple(PUBLISHED_LONG_TERM_SOURCE_TYPES)),
                LongTermMemory.review_status.in_(PUBLISHED_LONG_TERM_REVIEW_STATUSES),
                LongTermMemory.deleted_at.is_(None),
                LongTermMemory.is_current.is_(True),
                or_(LongTermMemory.expires_at.is_(None), LongTermMemory.expires_at > now),
                LongTermMemory.pii_classification.in_(tuple(PROMPT_SAFE_PII_CLASSIFICATIONS)),
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
        semantic_kind=_long_term_semantic_kind(memory.memory_kind),
        content=_bounded_content(memory.content),
        source_type=memory.source_type,
        source_ref=dict(memory.source_ref_json or {}),
        review_status=memory.review_status,
        version=memory.version,
        valid_from=memory.valid_from,
        expires_at=memory.expires_at,
    )


def _long_term_semantic_kind(memory_kind: str) -> str:
    return {
        "fact": "durable_profile_fact",
        "preference": "merchant_preference",
        "constraint": "operational_constraint",
        "pattern": "merchant_pattern",
    }.get(memory_kind, "durable_profile_fact")


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
