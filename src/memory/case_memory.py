"""Reviewed case-memory service and metadata-first retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import uuid

from sqlalchemy import and_, literal, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CaseMemory, MemoryTombstone, MemoryWriteEvent
from src.memory.identity import (
    ALLOWED_SOURCE_REF_KEYS,
    canonical_memory_candidate_hash,
    canonical_memory_content_hash,
    canonical_source_identity_hash,
)
from src.memory.schemas import (
    CaseMemoryReviewDecision,
    CaseMemorySearchItem,
    CaseMemorySearchRequest,
    CaseMemorySearchResult,
    CaseMemoryWriteCandidate,
    CaseMemoryWriteResult,
)
from src.memory.tombstones import source_identity_hash_for_tombstone


CASE_MEMORY_TYPE = "case_memory"
PUBLISHED_CASE_REVIEW_STATUSES = ("auto_approved", "approved")
AUTO_APPROVED_CASE_SOURCE_TYPES = frozenset(
    {
        "explicit_admin_preference",
        "human_reviewed",
        "deterministic_tool_result",
        "confirmed_business_outcome",
        "approved_approval_state",
    }
)
REVIEW_REQUIRED_CASE_SOURCE_TYPES = frozenset(
    {
        "llm_candidate",
        "semantic_episode_candidate",
        "summary_candidate",
        "cross_case_pattern_candidate",
        "behavior_inference",
    }
)
_POLICY_REF_KEYS = frozenset({"doc_key", "chunk_id", "policy_version", "policy_family"})


class CaseMemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert_case_memory(
        self,
        candidate: CaseMemoryWriteCandidate,
        *,
        content_hash: str,
        source_ref_json: dict[str, Any],
        source_identity_hash: str | None,
        review_status: str,
        now: datetime | None = None,
        reviewed_by_user_id: uuid.UUID | None = None,
        review_reason: str | None = None,
    ) -> CaseMemory:
        memory = CaseMemory(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            case_type=candidate.case_type,
            summary=candidate.summary,
            excerpt=candidate.excerpt,
            applicability=candidate.applicability,
            outcome=candidate.outcome,
            caveats=candidate.caveats,
            content_hash=content_hash,
            policy_family=candidate.policy_family,
            policy_version=candidate.policy_version,
            policy_refs_json=_safe_policy_refs(candidate.policy_refs),
            source_ref_json=source_ref_json,
            source_identity_hash=source_identity_hash,
            embedding=candidate.embedding,
            review_status=review_status,
            reviewed_by_user_id=reviewed_by_user_id,
            reviewed_at=_aware(now) if reviewed_by_user_id is not None else None,
            review_reason=review_reason,
            pii_classification=candidate.pii_classification,
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

    async def get_case_memory(self, *, tenant_id: uuid.UUID, case_memory_id: uuid.UUID) -> CaseMemory | None:
        result = await self.session.execute(
            select(CaseMemory)
            .where(CaseMemory.tenant_id == tenant_id, CaseMemory.id == case_memory_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def approve_case_memory(
        self,
        *,
        tenant_id: uuid.UUID,
        case_memory_id: uuid.UUID,
        reviewer_user_id: uuid.UUID | None,
        review_reason: str | None,
        now: datetime | None = None,
    ) -> CaseMemory | None:
        memory = await self.get_case_memory(tenant_id=tenant_id, case_memory_id=case_memory_id)
        if memory is None:
            return None
        if memory.review_status != "needs_review":
            raise ValueError("case memory approval requires needs_review status")
        now = _aware(now)
        memory.review_status = "approved"
        memory.reviewed_by_user_id = reviewer_user_id
        memory.reviewed_at = now
        memory.review_reason = review_reason
        await self.session.flush()
        return memory

    async def reject_case_memory(
        self,
        *,
        tenant_id: uuid.UUID,
        case_memory_id: uuid.UUID,
        reviewer_user_id: uuid.UUID | None,
        review_reason: str | None,
        now: datetime | None = None,
    ) -> CaseMemory | None:
        memory = await self.get_case_memory(tenant_id=tenant_id, case_memory_id=case_memory_id)
        if memory is None:
            return None
        if memory.review_status != "needs_review":
            raise ValueError("case memory rejection requires needs_review status")
        now = _aware(now)
        memory.review_status = "rejected"
        memory.reviewed_by_user_id = reviewer_user_id
        memory.reviewed_at = now
        memory.review_reason = review_reason
        await self.session.flush()
        return memory

    async def mark_deleted(
        self,
        *,
        tenant_id: uuid.UUID,
        case_memory_id: uuid.UUID,
        review_status: str,
        now: datetime | None = None,
    ) -> CaseMemory | None:
        memory = await self.get_case_memory(tenant_id=tenant_id, case_memory_id=case_memory_id)
        if memory is None:
            return None
        memory.review_status = review_status
        memory.deleted_at = _aware(now)
        await self.session.flush()
        return memory

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

    async def search_reviewed(self, request: CaseMemorySearchRequest) -> CaseMemorySearchResult:
        now = _aware(request.now)
        filters = self._metadata_filters(request=request, now=now)

        if request.query_embedding is not None:
            distance_expr = CaseMemory.embedding.cosine_distance(request.query_embedding)
            score_expr = 1 - distance_expr
            stmt = (
                select(CaseMemory, score_expr.label("score"))
                .where(*filters, CaseMemory.embedding.is_not(None))
                .order_by(distance_expr, CaseMemory.review_status.asc(), CaseMemory.created_at.asc())
            )
        else:
            score_expr = literal(1.0)
            query_filter = _query_text_filter(request.query)
            if query_filter is not None:
                filters.append(query_filter)
            stmt = (
                select(CaseMemory, score_expr.label("score"))
                .where(*filters)
                .order_by(CaseMemory.updated_at.desc(), CaseMemory.created_at.desc())
            )

        result = await self.session.execute(stmt.limit(request.limit).execution_options(populate_existing=True))
        ranked_rows = _light_rerank(
            rows=[(row[0], float(row[1])) for row in result.all()],
            request=request,
        )
        items = [_to_search_item(memory, score) for memory, score in ranked_rows[: request.limit]]
        return CaseMemorySearchResult(status="success" if items else "empty", items=items)

    def _metadata_filters(self, *, request: CaseMemorySearchRequest, now: datetime) -> list[Any]:
        filters = [
            CaseMemory.tenant_id == request.tenant_id,
            _scope_filter(request),
            CaseMemory.review_status.in_(PUBLISHED_CASE_REVIEW_STATUSES),
            CaseMemory.deleted_at.is_(None),
            or_(CaseMemory.expires_at.is_(None), CaseMemory.expires_at > now),
            CaseMemory.pii_classification != "prohibited",
            ~self._active_tombstone_exists(now=now),
        ]
        if request.case_type is not None:
            filters.append(CaseMemory.case_type == request.case_type)
        if request.policy_family is not None:
            filters.append(or_(CaseMemory.policy_family.is_(None), CaseMemory.policy_family == request.policy_family))
        if request.policy_version is not None:
            filters.append(
                or_(CaseMemory.policy_version.is_(None), CaseMemory.policy_version == request.policy_version)
            )
        return filters

    def _active_tombstone_exists(self, *, now: datetime):
        return (
            select(MemoryTombstone.id)
            .where(
                MemoryTombstone.tenant_id == CaseMemory.tenant_id,
                MemoryTombstone.memory_type == CASE_MEMORY_TYPE,
                MemoryTombstone.scope_type == CaseMemory.scope_type,
                MemoryTombstone.scope_id == CaseMemory.scope_id,
                MemoryTombstone.deleted_at.is_(None),
                or_(MemoryTombstone.expires_at.is_(None), MemoryTombstone.expires_at > now),
                or_(
                    and_(
                        MemoryTombstone.content_hash.is_not(None),
                        MemoryTombstone.content_hash == CaseMemory.content_hash,
                    ),
                    and_(
                        MemoryTombstone.source_identity_hash.is_not(None),
                        CaseMemory.source_identity_hash.is_not(None),
                        MemoryTombstone.source_identity_hash == CaseMemory.source_identity_hash,
                    ),
                ),
            )
            .exists()
        )


class CaseMemoryService:
    def __init__(self, repository: CaseMemoryRepository) -> None:
        self.repository = repository

    async def submit_case_memory_candidate(
        self,
        candidate: CaseMemoryWriteCandidate,
        now: datetime | None = None,
    ) -> CaseMemoryWriteResult:
        now = _aware(now)
        identity = _candidate_identity(candidate)
        tombstone = await self.repository.check_tombstone_before_write(
            tenant_id=candidate.tenant_id,
            memory_type=CASE_MEMORY_TYPE,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            content_hash=identity["content_hash"],
            source_identity_hash=identity["source_identity_hash"],
            now=now,
        )
        if tombstone is not None:
            event = await self.repository.emit_write_event(
                tenant_id=candidate.tenant_id,
                run_id=candidate.run_id,
                memory_type=CASE_MEMORY_TYPE,
                memory_id=None,
                decision="skip",
                reason_code="tombstone_match",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                source_ref_json=identity["source_ref_json"],
            )
            return _write_result(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="tombstone_match",
                candidate=candidate,
                identity=identity,
                event_id=event.id,
            )

        if candidate.pii_classification == "prohibited":
            event = await self.repository.emit_write_event(
                tenant_id=candidate.tenant_id,
                run_id=candidate.run_id,
                memory_type=CASE_MEMORY_TYPE,
                memory_id=None,
                decision="skip",
                reason_code="pii_blocked",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                source_ref_json=identity["source_ref_json"],
            )
            return _write_result(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="pii_blocked",
                candidate=candidate,
                identity=identity,
                event_id=event.id,
            )

        review_status = _review_status_for_source(candidate.source_type)
        decision = "write" if review_status == "auto_approved" else "needs_review"
        reason_code = "auto_approved_source" if review_status == "auto_approved" else "requires_review"
        memory = await self.repository.insert_case_memory(
            candidate,
            content_hash=identity["content_hash"],
            source_ref_json=identity["source_ref_json"],
            source_identity_hash=identity["source_identity_hash"],
            review_status=review_status,
            now=now,
            reviewed_by_user_id=None,
            review_reason=None,
        )
        event = await self.repository.emit_write_event(
            tenant_id=candidate.tenant_id,
            run_id=candidate.run_id,
            memory_type=CASE_MEMORY_TYPE,
            memory_id=memory.id,
            decision=decision,
            reason_code=reason_code,
            pii_classification=candidate.pii_classification,
            candidate_hash=identity["candidate_hash"],
            source_ref_json=identity["source_ref_json"],
        )
        return _write_result(
            status="written" if review_status == "auto_approved" else "needs_review",
            memory_id=memory.id,
            review_status=review_status,
            decision=decision,
            reason_code=reason_code,
            candidate=candidate,
            identity=identity,
            event_id=event.id,
        )

    async def approve_case_memory(
        self,
        decision: CaseMemoryReviewDecision,
        now: datetime | None = None,
    ) -> MemoryWriteEvent:
        memory = await self.repository.approve_case_memory(
            tenant_id=decision.tenant_id,
            case_memory_id=decision.case_memory_id,
            reviewer_user_id=decision.reviewer_user_id,
            review_reason=decision.review_reason,
            now=now,
        )
        if memory is None:
            raise ValueError("case memory not found")
        return await self.repository.emit_write_event(
            tenant_id=decision.tenant_id,
            run_id=decision.run_id,
            memory_type=CASE_MEMORY_TYPE,
            memory_id=memory.id,
            decision="write",
            reason_code=decision.reason_code,
            pii_classification=memory.pii_classification,
            candidate_hash=_candidate_hash_for_memory(memory),
            source_ref_json=dict(memory.source_ref_json or {}),
        )

    async def reject_case_memory(
        self,
        decision: CaseMemoryReviewDecision,
        now: datetime | None = None,
    ) -> MemoryWriteEvent:
        memory = await self.repository.reject_case_memory(
            tenant_id=decision.tenant_id,
            case_memory_id=decision.case_memory_id,
            reviewer_user_id=decision.reviewer_user_id,
            review_reason=decision.review_reason,
            now=now,
        )
        if memory is None:
            raise ValueError("case memory not found")
        return await self.repository.emit_write_event(
            tenant_id=decision.tenant_id,
            run_id=decision.run_id,
            memory_type=CASE_MEMORY_TYPE,
            memory_id=memory.id,
            decision="skip",
            reason_code=decision.reason_code,
            pii_classification=memory.pii_classification,
            candidate_hash=_candidate_hash_for_memory(memory),
            source_ref_json=dict(memory.source_ref_json or {}),
        )

    async def delete_case_memory(
        self,
        *,
        tenant_id: uuid.UUID,
        case_memory_id: uuid.UUID,
        run_id: uuid.UUID,
        reason_code: str = "deleted",
        now: datetime | None = None,
    ) -> MemoryWriteEvent:
        memory = await self._delete_or_tombstone(
            tenant_id=tenant_id,
            case_memory_id=case_memory_id,
            run_id=run_id,
            reason_code=reason_code,
            review_status="deleted",
            event_decision="delete",
            now=now,
        )
        return memory

    async def forget_case_memory(
        self,
        *,
        tenant_id: uuid.UUID,
        case_memory_id: uuid.UUID,
        run_id: uuid.UUID,
        reason_code: str = "forgotten",
        now: datetime | None = None,
    ) -> MemoryWriteEvent:
        return await self._delete_or_tombstone(
            tenant_id=tenant_id,
            case_memory_id=case_memory_id,
            run_id=run_id,
            reason_code=reason_code,
            review_status="tombstoned",
            event_decision="tombstone",
            now=now,
        )

    async def retrieve_reviewed(self, request: CaseMemorySearchRequest) -> CaseMemorySearchResult:
        return await self.repository.search_reviewed(request)

    async def _delete_or_tombstone(
        self,
        *,
        tenant_id: uuid.UUID,
        case_memory_id: uuid.UUID,
        run_id: uuid.UUID,
        reason_code: str,
        review_status: str,
        event_decision: str,
        now: datetime | None = None,
    ) -> MemoryWriteEvent:
        memory = await self.repository.mark_deleted(
            tenant_id=tenant_id,
            case_memory_id=case_memory_id,
            review_status=review_status,
            now=now,
        )
        if memory is None:
            raise ValueError("case memory not found")
        await self.repository.create_tombstone(
            tenant_id=memory.tenant_id,
            memory_type=CASE_MEMORY_TYPE,
            scope_type=memory.scope_type,
            scope_id=memory.scope_id,
            content_hash=memory.content_hash,
            source_ref_json=dict(memory.source_ref_json or {}),
            source_identity_hash=memory.source_identity_hash,
            reason_code=reason_code,
            created_by_run_id=run_id,
            expires_at=memory.expires_at,
        )
        return await self.repository.emit_write_event(
            tenant_id=tenant_id,
            run_id=run_id,
            memory_type=CASE_MEMORY_TYPE,
            memory_id=memory.id,
            decision=event_decision,
            reason_code=reason_code,
            pii_classification=memory.pii_classification,
            candidate_hash=_candidate_hash_for_memory(memory),
            source_ref_json=dict(memory.source_ref_json or {}),
        )


def _candidate_identity(candidate: CaseMemoryWriteCandidate) -> dict[str, Any]:
    source_ref_json = _source_ref_json(candidate)
    content_hash = canonical_memory_content_hash(
        memory_type=CASE_MEMORY_TYPE,
        content=candidate.summary,
    )
    source_identity_hash = canonical_source_identity_hash(source_ref_json)
    candidate_hash = canonical_memory_candidate_hash(
        tenant_id=str(candidate.tenant_id),
        memory_type=CASE_MEMORY_TYPE,
        scope_type=candidate.scope_type,
        scope_id=candidate.scope_id,
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
    )
    return {
        "source_ref_json": source_ref_json,
        "content_hash": content_hash,
        "source_identity_hash": source_identity_hash,
        "candidate_hash": candidate_hash,
    }


def _source_ref_json(candidate: CaseMemoryWriteCandidate) -> dict[str, Any]:
    if candidate.source_ref is None:
        return {"source_type": candidate.source_type}
    source_ref_json = candidate.source_ref.model_dump(exclude_none=True)
    source_ref_json["source_type"] = candidate.source_type
    return source_ref_json


def _review_status_for_source(source_type: str) -> str:
    if source_type in AUTO_APPROVED_CASE_SOURCE_TYPES:
        return "auto_approved"
    if source_type in REVIEW_REQUIRED_CASE_SOURCE_TYPES:
        return "needs_review"
    return "needs_review"


def _write_result(
    *,
    status: str,
    memory_id: uuid.UUID | None,
    review_status: str | None,
    decision: str,
    reason_code: str,
    candidate: CaseMemoryWriteCandidate,
    identity: dict[str, Any],
    event_id: uuid.UUID,
) -> CaseMemoryWriteResult:
    return CaseMemoryWriteResult(
        status=status,
        memory_id=memory_id,
        review_status=review_status,
        decision=decision,
        reason_code=reason_code,
        pii_classification=candidate.pii_classification,
        candidate_hash=identity["candidate_hash"],
        content_hash=identity["content_hash"],
        source_identity_hash=identity["source_identity_hash"],
        event_id=event_id,
    )


def _candidate_hash_for_memory(memory: CaseMemory) -> str:
    return canonical_memory_candidate_hash(
        tenant_id=str(memory.tenant_id),
        memory_type=CASE_MEMORY_TYPE,
        scope_type=memory.scope_type,
        scope_id=memory.scope_id,
        content_hash=memory.content_hash,
        source_identity_hash=memory.source_identity_hash,
    )


def _scope_filter(request: CaseMemorySearchRequest):
    if request.scopes:
        return or_(
            *[
                and_(CaseMemory.scope_type == current_scope_type, CaseMemory.scope_id == current_scope_id)
                for current_scope_type, current_scope_id in request.scopes
            ]
        )
    if request.scope_type is None or request.scope_id is None:
        raise ValueError("scope_type/scope_id or scopes is required")
    return and_(CaseMemory.scope_type == request.scope_type, CaseMemory.scope_id == request.scope_id)


def _light_rerank(
    *,
    rows: list[tuple[CaseMemory, float]],
    request: CaseMemorySearchRequest,
) -> list[tuple[CaseMemory, float]]:
    scored: list[tuple[CaseMemory, float, int]] = []
    for index, (memory, semantic_similarity) in enumerate(rows):
        policy_match = 0.0
        if request.policy_family and memory.policy_family == request.policy_family:
            policy_match += 0.03
        if request.policy_version and memory.policy_version == request.policy_version:
            policy_match += 0.03
        recency = 0.0
        if memory.updated_at is not None:
            age_seconds = max((_aware(request.now) - _aware(memory.updated_at)).total_seconds(), 0.0)
            recency = max(0.0, 0.01 - min(age_seconds / 86_400_000, 0.01))
        text_match = _text_match_score(memory, request.query)
        scored.append((memory, semantic_similarity + policy_match + recency + text_match, index))
    scored.sort(key=lambda item: (-item[1], item[2]))
    return [(memory, score) for memory, score, _ in scored]


def _query_text_filter(query: str | None):
    terms = _search_terms(query)
    if not terms:
        return None
    fields = (
        CaseMemory.summary,
        CaseMemory.excerpt,
        CaseMemory.applicability,
        CaseMemory.outcome,
        CaseMemory.caveats,
    )
    return or_(*[field.ilike(f"%{_escape_like(term)}%", escape="\\") for term in terms for field in fields])


def _text_match_score(memory: CaseMemory, query: str | None) -> float:
    terms = _search_terms(query)
    if not terms:
        return 0.0
    searchable = " ".join(
        str(value or "")
        for value in (
            memory.summary,
            memory.excerpt,
            memory.applicability,
            memory.outcome,
            memory.caveats,
        )
    ).lower()
    matches = sum(1 for term in terms if term in searchable)
    return min(0.08, matches * 0.02)


def _search_terms(query: str | None) -> list[str]:
    if query is None:
        return []
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


def _to_search_item(memory: CaseMemory, score: float) -> CaseMemorySearchItem:
    return CaseMemorySearchItem(
        case_memory_id=str(memory.id),
        excerpt=memory.excerpt,
        applicability=memory.applicability,
        outcome=memory.outcome,
        caveats=memory.caveats,
        score=score,
        policy_refs=_safe_policy_refs(memory.policy_refs_json or []),
        source_refs=_safe_source_refs(memory.source_ref_json or {}),
    )


def _safe_policy_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_refs: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        safe = {key: str(value) for key, value in ref.items() if key in _POLICY_REF_KEYS and value is not None}
        if safe:
            safe_refs.append(safe)
    return safe_refs


def _safe_source_refs(source_ref_json: dict[str, Any]) -> list[dict[str, Any]]:
    safe = {
        key: str(value)
        for key, value in source_ref_json.items()
        if key in ALLOWED_SOURCE_REF_KEYS and value is not None
    }
    return [safe] if safe else []


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
