"""Reviewed long-term profile memory service boundary."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from src.memory.identity import (
    canonical_memory_candidate_hash,
    canonical_memory_content_hash,
    canonical_source_identity_hash,
)
from src.memory.policy import is_blocked_memory_write_pii_classification
from src.memory.repository import LONG_TERM_MEMORY_TYPE, PUBLISHED_LONG_TERM_REVIEW_STATUSES, LongTermMemoryRepository
from src.memory.schemas import (
    LongTermMemoryWriteCandidate,
    LongTermMemoryWriteResult,
)


AUTO_APPROVED_LONG_TERM_SOURCE_TYPES = frozenset(
    {
        "explicit_user_preference",
        "explicit_admin_preference",
        "human_reviewed",
        "deterministic_tool_result",
        "confirmed_business_outcome",
        "approved_approval_state",
    }
)
REVIEW_REQUIRED_LONG_TERM_SOURCE_TYPES = frozenset(
    {
        "llm_candidate",
        "semantic_episode_candidate",
        "summary_candidate",
        "cross_case_pattern_candidate",
        "behavior_inference",
    }
)


class LongTermMemoryService:
    def __init__(self, repository: LongTermMemoryRepository) -> None:
        self.repository = repository

    async def retrieve_profile_memory(
        self,
        *,
        tenant_id,
        scope_type: str | None = None,
        scope_id: str | None = None,
        scopes: Sequence[tuple[str, str]] | None = None,
        now: datetime | None = None,
        limit: int = 10,
    ):
        return await self.repository.retrieve_profile_memory(
            tenant_id=tenant_id,
            scope_type=scope_type,
            scope_id=scope_id,
            scopes=scopes,
            now=now,
            limit=limit,
        )

    async def write_memory(
        self,
        candidate: LongTermMemoryWriteCandidate,
        now: datetime | None = None,
    ) -> LongTermMemoryWriteResult:
        now = _aware(now)
        identity = _candidate_identity(candidate)
        tombstone = await self.repository.check_tombstone_before_write(
            tenant_id=candidate.tenant_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
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
                memory_type=LONG_TERM_MEMORY_TYPE,
                memory_id=None,
                decision="skip",
                reason_code="tombstone_match",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                source_ref_json=identity["source_ref_json"],
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="tombstone_match",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                content_hash=identity["content_hash"],
                source_identity_hash=identity["source_identity_hash"],
                event_id=event.id,
            )

        if is_blocked_memory_write_pii_classification(candidate.pii_classification):
            event = await self.repository.emit_write_event(
                tenant_id=candidate.tenant_id,
                run_id=candidate.run_id,
                memory_type=LONG_TERM_MEMORY_TYPE,
                memory_id=None,
                decision="skip",
                reason_code="pii_blocked",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                source_ref_json=identity["source_ref_json"],
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="pii_blocked",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                content_hash=identity["content_hash"],
                source_identity_hash=identity["source_identity_hash"],
                event_id=event.id,
            )

        await self.repository.retire_expired_current_by_content_hash(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            content_hash=identity["content_hash"],
            now=now,
        )
        await self.repository.retire_unpublished_current_by_content_hash(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            content_hash=identity["content_hash"],
        )
        existing = await self.repository.get_active_by_content_hash(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            content_hash=identity["content_hash"],
            now=now,
        )
        if existing is not None:
            event = await self.repository.emit_write_event(
                tenant_id=candidate.tenant_id,
                run_id=candidate.run_id,
                memory_type=LONG_TERM_MEMORY_TYPE,
                memory_id=existing.id,
                decision="skip",
                reason_code="duplicate_active_identity",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                source_ref_json=identity["source_ref_json"],
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=existing.id,
                review_status=existing.review_status,
                decision="skip",
                reason_code="duplicate_active_identity",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                content_hash=identity["content_hash"],
                source_identity_hash=identity["source_identity_hash"],
                event_id=event.id,
            )

        review_status = _review_status_for_source(candidate.source_type)
        decision = "write" if review_status == "auto_approved" else "needs_review"
        reason_code = "auto_approved_source" if review_status == "auto_approved" else "requires_review"
        memory = await self.repository.insert_memory(
            candidate,
            content_hash=identity["content_hash"],
            source_ref_json=identity["source_ref_json"],
            source_identity_hash=identity["source_identity_hash"],
            review_status=review_status,
            now=now,
            is_current=review_status in PUBLISHED_LONG_TERM_REVIEW_STATUSES,
        )
        event = await self.repository.emit_write_event(
            tenant_id=candidate.tenant_id,
            run_id=candidate.run_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            memory_id=memory.id,
            decision=decision,
            reason_code=reason_code,
            pii_classification=candidate.pii_classification,
            candidate_hash=identity["candidate_hash"],
            source_ref_json=identity["source_ref_json"],
        )
        return LongTermMemoryWriteResult(
            status="written" if review_status == "auto_approved" else "needs_review",
            memory_id=memory.id,
            review_status=review_status,
            decision=decision,
            reason_code=reason_code,
            pii_classification=candidate.pii_classification,
            candidate_hash=identity["candidate_hash"],
            content_hash=identity["content_hash"],
            source_identity_hash=identity["source_identity_hash"],
            event_id=event.id,
        )

    async def approve_memory(
        self,
        *,
        tenant_id,
        memory_id,
        run_id,
        reason_code: str = "approved",
        now: datetime | None = None,
    ):
        memory = await self.repository.update_review_status(
            tenant_id=tenant_id,
            memory_id=memory_id,
            review_status="approved",
            is_current=True,
            expected_review_status="needs_review",
            now=now,
        )
        if memory is None:
            raise ValueError("long-term memory not found")
        return await self.repository.emit_write_event(
            tenant_id=tenant_id,
            run_id=run_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            memory_id=memory.id,
            decision="write",
            reason_code=reason_code,
            pii_classification=memory.pii_classification,
            candidate_hash=_candidate_hash_for_memory(memory),
            source_ref_json=dict(memory.source_ref_json or {}),
        )

    async def reject_memory(
        self,
        *,
        tenant_id,
        memory_id,
        run_id,
        reason_code: str = "rejected",
    ):
        memory = await self.repository.update_review_status(
            tenant_id=tenant_id,
            memory_id=memory_id,
            review_status="rejected",
            is_current=False,
            expected_review_status="needs_review",
        )
        if memory is None:
            raise ValueError("long-term memory not found")
        return await self.repository.emit_write_event(
            tenant_id=tenant_id,
            run_id=run_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            memory_id=memory.id,
            decision="skip",
            reason_code=reason_code,
            pii_classification=memory.pii_classification,
            candidate_hash=_candidate_hash_for_memory(memory),
            source_ref_json=dict(memory.source_ref_json or {}),
        )

    async def delete_memory(
        self,
        *,
        tenant_id,
        memory_id,
        run_id,
        reason_code: str = "deleted",
        now: datetime | None = None,
    ):
        forgotten = await self.repository.forget_memory(
            tenant_id=tenant_id,
            memory_id=memory_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            reason_code=reason_code,
            run_id=run_id,
            now=now,
            review_status="deleted",
        )
        if forgotten is None:
            raise ValueError("long-term memory not found")
        memory, _tombstone = forgotten
        return await self.repository.emit_write_event(
            tenant_id=tenant_id,
            run_id=run_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            memory_id=memory.id,
            decision="delete",
            reason_code=reason_code,
            pii_classification=memory.pii_classification,
            candidate_hash=_candidate_hash_for_memory(memory),
            source_ref_json=dict(memory.source_ref_json or {}),
        )

    async def forget_long_term_memory(
        self,
        *,
        tenant_id,
        memory_id,
        run_id,
        reason_code: str = "forgotten",
        now: datetime | None = None,
    ):
        forgotten = await self.repository.forget_memory(
            tenant_id=tenant_id,
            memory_id=memory_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            reason_code=reason_code,
            run_id=run_id,
            now=now,
        )
        if forgotten is None:
            raise ValueError("long-term memory not found")
        memory, _tombstone = forgotten
        return await self.repository.emit_write_event(
            tenant_id=tenant_id,
            run_id=run_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            memory_id=memory.id,
            decision="tombstone",
            reason_code=reason_code,
            pii_classification=memory.pii_classification,
            candidate_hash=_candidate_hash_for_memory(memory),
            source_ref_json=dict(memory.source_ref_json or {}),
        )

    async def forget_memory(self, **kwargs):
        return await self.forget_long_term_memory(**kwargs)

    async def supersede_memory(
        self,
        *,
        tenant_id,
        memory_id,
        replacement_candidate: LongTermMemoryWriteCandidate,
        run_id,
        reason_code: str = "correction",
        now: datetime | None = None,
    ) -> LongTermMemoryWriteResult:
        now = _aware(now)
        previous = await self.repository.get_memory(tenant_id=tenant_id, memory_id=memory_id)
        if previous is None:
            raise ValueError("long-term memory not found")
        if replacement_candidate.tenant_id != tenant_id:
            raise ValueError("replacement candidate tenant does not match memory tenant")
        if (
            replacement_candidate.scope_type != previous.scope_type
            or replacement_candidate.scope_id != previous.scope_id
        ):
            raise ValueError("replacement candidate scope does not match memory scope")
        if not _is_current_published(previous, now):
            raise ValueError("long-term memory supersede requires current published row")

        identity = _candidate_identity(replacement_candidate)
        tombstone = await self.repository.check_tombstone_before_write(
            tenant_id=replacement_candidate.tenant_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            scope_type=replacement_candidate.scope_type,
            scope_id=replacement_candidate.scope_id,
            content_hash=identity["content_hash"],
            source_identity_hash=identity["source_identity_hash"],
            now=now,
        )
        if tombstone is not None:
            event = await self.repository.emit_write_event(
                tenant_id=replacement_candidate.tenant_id,
                run_id=run_id,
                memory_type=LONG_TERM_MEMORY_TYPE,
                memory_id=None,
                decision="skip",
                reason_code="tombstone_match",
                pii_classification=replacement_candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                source_ref_json=identity["source_ref_json"],
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="tombstone_match",
                pii_classification=replacement_candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                content_hash=identity["content_hash"],
                source_identity_hash=identity["source_identity_hash"],
                event_id=event.id,
            )

        if is_blocked_memory_write_pii_classification(replacement_candidate.pii_classification):
            event = await self.repository.emit_write_event(
                tenant_id=replacement_candidate.tenant_id,
                run_id=run_id,
                memory_type=LONG_TERM_MEMORY_TYPE,
                memory_id=None,
                decision="skip",
                reason_code="pii_blocked",
                pii_classification=replacement_candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                source_ref_json=identity["source_ref_json"],
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="pii_blocked",
                pii_classification=replacement_candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                content_hash=identity["content_hash"],
                source_identity_hash=identity["source_identity_hash"],
                event_id=event.id,
            )

        if _is_expired(replacement_candidate.expires_at, now):
            event = await self.repository.emit_write_event(
                tenant_id=replacement_candidate.tenant_id,
                run_id=run_id,
                memory_type=LONG_TERM_MEMORY_TYPE,
                memory_id=None,
                decision="skip",
                reason_code="expired_candidate",
                pii_classification=replacement_candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                source_ref_json=identity["source_ref_json"],
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="expired_candidate",
                pii_classification=replacement_candidate.pii_classification,
                candidate_hash=identity["candidate_hash"],
                content_hash=identity["content_hash"],
                source_identity_hash=identity["source_identity_hash"],
                event_id=event.id,
            )

        review_status = _review_status_for_source(replacement_candidate.source_type)
        replacement_is_current = review_status == "auto_approved"
        if replacement_is_current:
            previous.is_current = False
            previous.review_status = "superseded"
            previous.superseded_at = now
        replacement = await self.repository.insert_memory(
            replacement_candidate,
            content_hash=identity["content_hash"],
            source_ref_json=identity["source_ref_json"],
            source_identity_hash=identity["source_identity_hash"],
            review_status=review_status,
            now=now,
            supersedes=previous.id,
            version=previous.version + 1,
            is_current=replacement_is_current,
        )
        if replacement_is_current:
            previous.superseded_by = replacement.id
        decision = "supersede" if replacement_is_current else "needs_review"
        event = await self.repository.emit_write_event(
            tenant_id=replacement_candidate.tenant_id,
            run_id=run_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            memory_id=replacement.id,
            decision=decision,
            reason_code=reason_code,
            pii_classification=replacement_candidate.pii_classification,
            candidate_hash=identity["candidate_hash"],
            source_ref_json=identity["source_ref_json"],
        )
        return LongTermMemoryWriteResult(
            status="written" if review_status == "auto_approved" else "needs_review",
            memory_id=replacement.id,
            review_status=review_status,
            decision=decision,
            reason_code=reason_code,
            pii_classification=replacement_candidate.pii_classification,
            candidate_hash=identity["candidate_hash"],
            content_hash=identity["content_hash"],
            source_identity_hash=identity["source_identity_hash"],
            event_id=event.id,
        )


def _review_status_for_source(source_type: str) -> str:
    if source_type in AUTO_APPROVED_LONG_TERM_SOURCE_TYPES:
        return "auto_approved"
    if source_type in REVIEW_REQUIRED_LONG_TERM_SOURCE_TYPES:
        return "needs_review"
    return "needs_review"


def _candidate_identity(candidate: LongTermMemoryWriteCandidate) -> dict[str, Any]:
    source_ref_json = _source_ref_json(candidate)
    content_hash = canonical_memory_content_hash(
        memory_type=LONG_TERM_MEMORY_TYPE,
        content=candidate.content,
    )
    source_identity_hash = canonical_source_identity_hash(source_ref_json)
    candidate_hash = canonical_memory_candidate_hash(
        tenant_id=str(candidate.tenant_id),
        memory_type=LONG_TERM_MEMORY_TYPE,
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


def _source_ref_json(candidate: LongTermMemoryWriteCandidate) -> dict[str, Any]:
    if candidate.source_ref is None:
        return {"source_type": candidate.source_type}
    source_ref_json = candidate.source_ref.model_dump(exclude_none=True)
    source_ref_json["source_type"] = candidate.source_type
    return source_ref_json


def _candidate_hash_for_memory(memory) -> str:
    return canonical_memory_candidate_hash(
        tenant_id=str(memory.tenant_id),
        memory_type=LONG_TERM_MEMORY_TYPE,
        scope_type=memory.scope_type,
        scope_id=memory.scope_id,
        content_hash=memory.content_hash,
        source_identity_hash=memory.source_identity_hash,
    )


def _is_current_published(memory, now: datetime) -> bool:
    return (
        memory.deleted_at is None
        and memory.is_current is True
        and memory.review_status in PUBLISHED_LONG_TERM_REVIEW_STATUSES
        and not _is_expired(memory.expires_at, now)
    )


def _is_expired(expires_at: datetime | None, now: datetime) -> bool:
    return expires_at is not None and _aware(expires_at) <= now


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
