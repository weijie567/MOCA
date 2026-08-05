"""Reviewed case-memory service and metadata-first retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import uuid

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import and_, literal, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CaseMemory, MemoryTombstone, MemoryWriteEvent
from src.knowledge.schemas import EvidenceRefV1
from src.memory.identity import (
    ALLOWED_SOURCE_REF_KEYS,
    MEMORY_IDENTITY_PROFILE,
    MemoryCandidateIdentityV1,
    build_case_memory_candidate_identity,
    canonical_source_identity_hash,
)
from src.memory.policy import (
    MEMORY_POLICY_AUTHORITY_CLASS,
    MEMORY_POLICY_VERSION,
    PROMPT_SAFE_PII_CLASSIFICATIONS,
    case_memory_policy_decision,
    case_memory_review_status_for_source,
    is_blocked_memory_write_pii_classification,
)
from src.memory.schemas import (
    CaseMemoryReviewDecision,
    CaseMemoryProvenanceEnvelope,
    CaseMemoryProvenanceV1,
    CaseMemorySearchItem,
    CaseMemorySearchRequest,
    CaseMemorySearchResult,
    CaseMemoryWriteCandidate,
    CaseMemoryWriteResult,
)
from src.memory.tombstones import source_identity_hash_for_tombstone


CASE_MEMORY_TYPE = "case_memory"
PUBLISHED_CASE_REVIEW_STATUSES = ("auto_approved", "approved")
ACTIVE_CASE_DUPLICATE_REVIEW_STATUSES = ("auto_approved", "needs_review", "approved")
_RESOLVED_PROVENANCE_STATUSES = ("canonical", "legacy_resolved")
_PROVENANCE_ADAPTER = TypeAdapter(CaseMemoryProvenanceEnvelope)


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
        identity_algorithm_version: str,
        candidate_hash: str,
        identity_resolution_status: str,
        provenance_json: dict[str, Any],
        lifecycle_version: int,
        review_status: str,
        now: datetime | None = None,
        reviewed_by_user_id: uuid.UUID | None = None,
        review_reason: str | None = None,
    ) -> CaseMemory:
        provenance = CaseMemoryProvenanceV1.model_validate(provenance_json)
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
            policy_refs_json=_validated_policy_refs(candidate.policy_refs, tenant_id=candidate.tenant_id),
            source_ref_json=source_ref_json,
            source_identity_hash=source_identity_hash,
            identity_algorithm_version=identity_algorithm_version,
            candidate_hash=candidate_hash,
            identity_resolution_status=identity_resolution_status,
            provenance_json=provenance_json,
            lifecycle_version=lifecycle_version,
            corrects_case_memory_id=provenance.corrects_case_memory_id,
            supersedes_case_memory_id=provenance.supersedes_case_memory_id,
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

    async def get_case_memory(self, *, tenant_id: uuid.UUID, case_memory_id: uuid.UUID) -> CaseMemory | None:
        result = await self.session.execute(
            select(CaseMemory)
            .where(CaseMemory.tenant_id == tenant_id, CaseMemory.id == case_memory_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_pending_review(self, *, tenant_id: uuid.UUID, limit: int = 50) -> list[CaseMemory]:
        result = await self.session.execute(
            select(CaseMemory)
            .where(
                CaseMemory.tenant_id == tenant_id,
                CaseMemory.review_status == "needs_review",
                CaseMemory.deleted_at.is_(None),
            )
            .order_by(CaseMemory.created_at.desc())
            .limit(max(1, min(limit, 100)))
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

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
        resolved_source_identity_hash = source_identity_hash or (
            canonical_source_identity_hash(
                source_ref_json,
                identity_profile=MEMORY_IDENTITY_PROFILE,
            )
            if source_ref_json
            else source_identity_hash_for_tombstone(source_ref_json)
        )
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

    async def get_active_duplicate(
        self,
        *,
        tenant_id: uuid.UUID,
        scope_type: str,
        scope_id: str,
        content_hash: str,
        source_identity_hash: str | None,
        now: datetime | None = None,
    ) -> tuple[CaseMemory, str] | None:
        now = _aware(now)
        base_filters = [
            CaseMemory.tenant_id == tenant_id,
            CaseMemory.scope_type == scope_type,
            CaseMemory.scope_id == scope_id,
            CaseMemory.deleted_at.is_(None),
            CaseMemory.review_status.in_(ACTIVE_CASE_DUPLICATE_REVIEW_STATUSES),
            or_(CaseMemory.expires_at.is_(None), CaseMemory.expires_at > now),
        ]
        result = await self.session.execute(
            select(CaseMemory)
            .where(*base_filters, CaseMemory.content_hash == content_hash)
            .order_by(CaseMemory.updated_at.desc(), CaseMemory.created_at.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        duplicate = result.scalar_one_or_none()
        if duplicate is not None:
            return duplicate, "duplicate_active_identity"

        if source_identity_hash is not None:
            result = await self.session.execute(
                select(CaseMemory)
                .where(*base_filters, CaseMemory.source_identity_hash == source_identity_hash)
                .order_by(CaseMemory.updated_at.desc(), CaseMemory.created_at.desc())
                .limit(1)
                .execution_options(populate_existing=True)
            )
            duplicate = result.scalar_one_or_none()
            if duplicate is not None:
                return duplicate, "duplicate_active_source_identity"

        return None

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
            CaseMemory.pii_classification.in_(tuple(PROMPT_SAFE_PII_CLASSIFICATIONS)),
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
        identity = build_case_memory_candidate_identity(candidate)
        provenance = _resolved_candidate_provenance(candidate=candidate, identity=identity)
        policy_decision = _policy_decision_for_candidate(candidate)
        tombstone = await self.repository.check_tombstone_before_write(
            tenant_id=candidate.tenant_id,
            memory_type=CASE_MEMORY_TYPE,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            content_hash=identity.content_hash,
            source_identity_hash=identity.source_identity_hash,
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
                candidate_hash=identity.candidate_hash,
                source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
                blocked_by=["tombstone_match"],
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

        if is_blocked_memory_write_pii_classification(candidate.pii_classification):
            event = await self.repository.emit_write_event(
                tenant_id=candidate.tenant_id,
                run_id=candidate.run_id,
                memory_type=CASE_MEMORY_TYPE,
                memory_id=None,
                decision="skip",
                reason_code="pii_blocked",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity.candidate_hash,
                source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
                **_policy_event_kwargs(policy_decision),
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

        duplicate = await self.repository.get_active_duplicate(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            content_hash=identity.content_hash,
            source_identity_hash=identity.source_identity_hash,
            now=now,
        )
        if duplicate is not None:
            memory, reason_code = duplicate
            event = await self.repository.emit_write_event(
                tenant_id=candidate.tenant_id,
                run_id=candidate.run_id,
                memory_type=CASE_MEMORY_TYPE,
                memory_id=memory.id,
                decision="skip",
                reason_code=reason_code,
                pii_classification=candidate.pii_classification,
                candidate_hash=identity.candidate_hash,
                source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
                blocked_by=[reason_code],
            )
            return _write_result(
                status="skipped",
                memory_id=memory.id,
                review_status=memory.review_status,
                decision="skip",
                reason_code=reason_code,
                candidate=candidate,
                identity=identity,
                event_id=event.id,
            )

        review_status = policy_decision.review_status or "needs_review"
        memory = await self.repository.insert_case_memory(
            candidate,
            content_hash=identity.content_hash,
            source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
            source_identity_hash=identity.source_identity_hash,
            identity_algorithm_version="memory_identity.v1",
            candidate_hash=identity.candidate_hash,
            identity_resolution_status=provenance.resolution_status,
            provenance_json=provenance.model_dump(mode="json", exclude_none=True),
            lifecycle_version=1,
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
            decision=policy_decision.decision,
            reason_code=policy_decision.reason_code,
            pii_classification=candidate.pii_classification,
            candidate_hash=identity.candidate_hash,
            source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
            **_policy_event_kwargs(policy_decision),
        )
        return _write_result(
            status="written" if review_status == "auto_approved" else "needs_review",
            memory_id=memory.id,
            review_status=review_status,
            decision=policy_decision.decision,
            reason_code=policy_decision.reason_code,
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
            candidate_hash=build_case_memory_candidate_identity(memory).candidate_hash,
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
            candidate_hash=build_case_memory_candidate_identity(memory).candidate_hash,
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

    async def list_pending_review(self, *, tenant_id: uuid.UUID, limit: int = 50) -> list[CaseMemory]:
        return await self.repository.list_pending_review(tenant_id=tenant_id, limit=limit)

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
            candidate_hash=build_case_memory_candidate_identity(memory).candidate_hash,
            source_ref_json=dict(memory.source_ref_json or {}),
        )


def _review_status_for_source(source_type: str) -> str:
    return case_memory_review_status_for_source(source_type)


def _review_status_for_candidate(candidate: CaseMemoryWriteCandidate) -> str:
    return case_memory_review_status_for_source(candidate.source_type, candidate.source_ref)


def _policy_decision_for_candidate(candidate: CaseMemoryWriteCandidate):
    return case_memory_policy_decision(
        candidate.source_type,
        candidate.source_ref,
        pii_classification=candidate.pii_classification,
    )


def _policy_event_kwargs(policy_decision) -> dict[str, Any]:
    return {
        "policy_version": policy_decision.policy_version,
        "blocked_by": list(policy_decision.blocked_by),
        "authority_class": policy_decision.authority_class,
    }


def _write_result(
    *,
    status: str,
    memory_id: uuid.UUID | None,
    review_status: str | None,
    decision: str,
    reason_code: str,
    candidate: CaseMemoryWriteCandidate,
    identity: MemoryCandidateIdentityV1,
    event_id: uuid.UUID,
) -> CaseMemoryWriteResult:
    return CaseMemoryWriteResult(
        status=status,
        memory_id=memory_id,
        review_status=review_status,
        decision=decision,
        reason_code=reason_code,
        pii_classification=candidate.pii_classification,
        candidate_hash=identity.candidate_hash,
        content_hash=identity.content_hash,
        source_identity_hash=identity.source_identity_hash,
        event_id=event_id,
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
        policy_refs=_bounded_policy_refs(memory.policy_refs_json or []),
        source_refs=_safe_source_refs(memory.source_ref_json or {}),
    )


def _validated_policy_refs(refs: list[dict[str, Any]], *, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for value in refs:
        try:
            ref = EvidenceRefV1.model_validate(value)
        except ValidationError as exc:
            raise ValueError("case memory policy refs require canonical EvidenceRefV1 values") from exc
        if (
            ref.tenant_id != str(tenant_id)
            or ref.scope_type != "tenant_policy"
            or ref.scope_id != str(tenant_id)
            or ref.to_canonical_identity() is None
        ):
            raise ValueError("case memory policy refs require exact tenant-policy canonical scope")
        validated.append(ref.model_dump(mode="json", exclude_none=True))
    return validated


def _bounded_policy_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bounded: list[dict[str, Any]] = []
    for value in refs:
        try:
            ref = EvidenceRefV1.model_validate(value)
        except ValidationError:
            continue
        payload = ref.model_dump(mode="json", exclude_none=True, exclude={"score"})
        bounded.append(payload)
    return bounded


def _resolved_candidate_provenance(
    *,
    candidate: CaseMemoryWriteCandidate,
    identity: MemoryCandidateIdentityV1,
) -> CaseMemoryProvenanceV1:
    if identity.normalized_source_ref is None or identity.source_identity_hash is None:
        raise ValueError("case memory insert requires a resolved source identity")
    provenance = candidate.provenance or CaseMemoryProvenanceV1(
        resolution_status="canonical",
        tenant_id=candidate.tenant_id,
        scope_type=candidate.scope_type,
        scope_id=candidate.scope_id,
        memory_authority_class="contextual_only",
        source_authorities=[],
        source_run_id=candidate.run_id,
        source_event_id=identity.normalized_source_ref.event_id,
        evidence_refs=[],
        business_fact_refs=[],
        identity_algorithm_version="memory_identity.v1",
        identity_profile=identity.identity_profile,
        candidate_hash=identity.candidate_hash,
        content_hash=identity.content_hash,
        source_identity_hash=identity.source_identity_hash,
    )
    expected = {
        "tenant_id": candidate.tenant_id,
        "scope_type": candidate.scope_type,
        "scope_id": candidate.scope_id,
        "source_run_id": candidate.run_id,
        "source_event_id": identity.normalized_source_ref.event_id,
        "identity_algorithm_version": "memory_identity.v1",
        "identity_profile": identity.identity_profile,
        "candidate_hash": identity.candidate_hash,
        "content_hash": identity.content_hash,
        "source_identity_hash": identity.source_identity_hash,
    }
    for field_name, value in expected.items():
        if getattr(provenance, field_name) != value:
            raise ValueError("case memory provenance does not match tenant, scope, source, or identity")
    expected_policy_refs = _validated_policy_refs(candidate.policy_refs, tenant_id=candidate.tenant_id)
    provenance_policy_refs = [
        ref.model_dump(mode="json", exclude_none=True) for ref in provenance.evidence_refs
    ]
    if expected_policy_refs != provenance_policy_refs:
        raise ValueError("case memory provenance evidence refs do not match candidate policy refs")
    if provenance.source_cwc_id is not None:
        expected_outcome_id = f"cwc:{provenance.source_cwc_id}:v{provenance.source_cwc_revision}"
        if identity.normalized_source_ref.outcome_id != expected_outcome_id:
            raise ValueError("case memory provenance CWC revision does not match the source identity")
    return provenance


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
