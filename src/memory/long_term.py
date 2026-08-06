"""Reviewed long-term profile memory service boundary."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from src.memory.identity import MemoryCandidateIdentityV1, build_long_term_memory_candidate_identity
from src.memory.policy import (
    is_blocked_memory_write_pii_classification,
    long_term_memory_policy_decision,
    long_term_review_status_for_source,
)
from src.memory.preference_capture import validate_soft_preference_text
from src.memory.repository import LONG_TERM_MEMORY_TYPE, PUBLISHED_LONG_TERM_REVIEW_STATUSES, LongTermMemoryRepository
from src.memory.schemas import (
    LongTermMemoryWriteCandidate,
    LongTermMemoryWriteResult,
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

    async def list_pending_review(self, *, tenant_id, limit: int = 50):
        return await self.repository.list_pending_review(tenant_id=tenant_id, limit=limit)

    async def write_memory(
        self,
        candidate: LongTermMemoryWriteCandidate,
        now: datetime | None = None,
    ) -> LongTermMemoryWriteResult:
        now = _aware(now)
        identity = build_long_term_memory_candidate_identity(candidate)
        policy_decision = _policy_decision_for_candidate(candidate)
        tombstone = await self.repository.check_tombstone_before_write(
            tenant_id=candidate.tenant_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
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
                memory_type=LONG_TERM_MEMORY_TYPE,
                memory_id=None,
                decision="skip",
                reason_code="tombstone_match",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity.candidate_hash,
                source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
                blocked_by=["tombstone_match"],
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="tombstone_match",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity.candidate_hash,
                content_hash=identity.content_hash,
                source_identity_hash=identity.source_identity_hash,
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
                candidate_hash=identity.candidate_hash,
                source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
                **_policy_event_kwargs(policy_decision),
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="pii_blocked",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity.candidate_hash,
                content_hash=identity.content_hash,
                source_identity_hash=identity.source_identity_hash,
                event_id=event.id,
            )

        if candidate.memory_kind != "preference":
            return await _emit_skipped_candidate_result(
                self.repository,
                candidate=candidate,
                run_id=candidate.run_id,
                identity=identity,
                policy_decision=policy_decision,
                reason_code="not_preference_memory_kind",
                blocked_by=["memory_kind"],
            )

        hard_rule_reason = _hard_rule_preference_reason(candidate.content)
        if hard_rule_reason is not None:
            return await _emit_skipped_candidate_result(
                self.repository,
                candidate=candidate,
                run_id=candidate.run_id,
                identity=identity,
                policy_decision=policy_decision,
                reason_code=hard_rule_reason,
                blocked_by=["preference_text"],
            )

        if policy_decision.decision == "skip":
            return await _emit_skipped_candidate_result(
                self.repository,
                candidate=candidate,
                run_id=candidate.run_id,
                identity=identity,
                policy_decision=policy_decision,
                reason_code=policy_decision.reason_code,
                blocked_by=list(policy_decision.blocked_by),
            )

        await self.repository.retire_expired_current_by_content_hash(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            content_hash=identity.content_hash,
            now=now,
        )
        await self.repository.retire_unpublished_current_by_content_hash(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            content_hash=identity.content_hash,
        )
        existing = await self.repository.get_active_by_content_hash(
            tenant_id=candidate.tenant_id,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            content_hash=identity.content_hash,
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
                candidate_hash=identity.candidate_hash,
                source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
                blocked_by=["duplicate_active_identity"],
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=existing.id,
                review_status=existing.review_status,
                decision="skip",
                reason_code="duplicate_active_identity",
                pii_classification=candidate.pii_classification,
                candidate_hash=identity.candidate_hash,
                content_hash=identity.content_hash,
                source_identity_hash=identity.source_identity_hash,
                event_id=event.id,
            )

        review_status = policy_decision.review_status or "needs_review"
        memory = await self.repository.insert_memory(
            candidate,
            content_hash=identity.content_hash,
            source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
            source_identity_hash=identity.source_identity_hash,
            review_status=review_status,
            now=now,
            is_current=review_status in PUBLISHED_LONG_TERM_REVIEW_STATUSES,
        )
        event = await self.repository.emit_write_event(
            tenant_id=candidate.tenant_id,
            run_id=candidate.run_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            memory_id=memory.id,
            decision=policy_decision.decision,
            reason_code=policy_decision.reason_code,
            pii_classification=candidate.pii_classification,
            candidate_hash=identity.candidate_hash,
            source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
            **_policy_event_kwargs(policy_decision),
        )
        return LongTermMemoryWriteResult(
            status="written" if review_status == "auto_approved" else "needs_review",
            memory_id=memory.id,
            review_status=review_status,
            decision=policy_decision.decision,
            reason_code=policy_decision.reason_code,
            pii_classification=candidate.pii_classification,
            candidate_hash=identity.candidate_hash,
            content_hash=identity.content_hash,
            source_identity_hash=identity.source_identity_hash,
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
        pending = await self.repository.get_memory(tenant_id=tenant_id, memory_id=memory_id)
        if pending is None:
            raise ValueError("long-term memory not found")
        if pending.memory_kind != "preference":
            raise ValueError("long-term approval requires preference memory")
        if _hard_rule_preference_reason(pending.content) is not None:
            raise ValueError("long-term approval requires soft preference content")
        reviewed_source_ref = {**dict(pending.source_ref_json or {}), "source_type": "human_reviewed"}
        memory = await self.repository.update_review_status(
            tenant_id=tenant_id,
            memory_id=memory_id,
            review_status="approved",
            is_current=True,
            source_type="human_reviewed",
            source_ref_json=reviewed_source_ref,
            source_identity_hash=build_long_term_memory_candidate_identity(
                pending,
                source_ref=reviewed_source_ref,
            ).source_identity_hash,
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
            candidate_hash=build_long_term_memory_candidate_identity(memory).candidate_hash,
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
            candidate_hash=build_long_term_memory_candidate_identity(memory).candidate_hash,
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
            candidate_hash=build_long_term_memory_candidate_identity(memory).candidate_hash,
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
            candidate_hash=build_long_term_memory_candidate_identity(memory).candidate_hash,
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

        identity = build_long_term_memory_candidate_identity(replacement_candidate)
        policy_decision = _policy_decision_for_candidate(replacement_candidate)
        tombstone = await self.repository.check_tombstone_before_write(
            tenant_id=replacement_candidate.tenant_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            scope_type=replacement_candidate.scope_type,
            scope_id=replacement_candidate.scope_id,
            content_hash=identity.content_hash,
            source_identity_hash=identity.source_identity_hash,
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
                candidate_hash=identity.candidate_hash,
                source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
                blocked_by=["tombstone_match"],
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="tombstone_match",
                pii_classification=replacement_candidate.pii_classification,
                candidate_hash=identity.candidate_hash,
                content_hash=identity.content_hash,
                source_identity_hash=identity.source_identity_hash,
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
                candidate_hash=identity.candidate_hash,
                source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
                **_policy_event_kwargs(policy_decision),
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="pii_blocked",
                pii_classification=replacement_candidate.pii_classification,
                candidate_hash=identity.candidate_hash,
                content_hash=identity.content_hash,
                source_identity_hash=identity.source_identity_hash,
                event_id=event.id,
            )

        if replacement_candidate.memory_kind != "preference":
            return await _emit_skipped_candidate_result(
                self.repository,
                candidate=replacement_candidate,
                run_id=run_id,
                identity=identity,
                policy_decision=policy_decision,
                reason_code="not_preference_memory_kind",
                blocked_by=["memory_kind"],
            )

        hard_rule_reason = _hard_rule_preference_reason(replacement_candidate.content)
        if hard_rule_reason is not None:
            return await _emit_skipped_candidate_result(
                self.repository,
                candidate=replacement_candidate,
                run_id=run_id,
                identity=identity,
                policy_decision=policy_decision,
                reason_code=hard_rule_reason,
                blocked_by=["preference_text"],
            )

        if policy_decision.decision == "skip":
            return await _emit_skipped_candidate_result(
                self.repository,
                candidate=replacement_candidate,
                run_id=run_id,
                identity=identity,
                policy_decision=policy_decision,
                reason_code=policy_decision.reason_code,
                blocked_by=list(policy_decision.blocked_by),
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
                candidate_hash=identity.candidate_hash,
                source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
                blocked_by=["expired_candidate"],
            )
            return LongTermMemoryWriteResult(
                status="skipped",
                memory_id=None,
                review_status=None,
                decision="skip",
                reason_code="expired_candidate",
                pii_classification=replacement_candidate.pii_classification,
                candidate_hash=identity.candidate_hash,
                content_hash=identity.content_hash,
                source_identity_hash=identity.source_identity_hash,
                event_id=event.id,
            )

        review_status = policy_decision.review_status or "needs_review"
        replacement_is_current = review_status == "auto_approved"
        if replacement_is_current:
            previous.is_current = False
            previous.review_status = "superseded"
            previous.superseded_at = now
        replacement = await self.repository.insert_memory(
            replacement_candidate,
            content_hash=identity.content_hash,
            source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
            source_identity_hash=identity.source_identity_hash,
            review_status=review_status,
            now=now,
            supersedes=previous.id,
            version=previous.version + 1,
            is_current=replacement_is_current,
        )
        if replacement_is_current:
            previous.superseded_by = replacement.id
        decision = "supersede" if replacement_is_current else policy_decision.decision
        event = await self.repository.emit_write_event(
            tenant_id=replacement_candidate.tenant_id,
            run_id=run_id,
            memory_type=LONG_TERM_MEMORY_TYPE,
            memory_id=replacement.id,
            decision=decision,
            reason_code=reason_code,
            pii_classification=replacement_candidate.pii_classification,
            candidate_hash=identity.candidate_hash,
            source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
            **_policy_event_kwargs(policy_decision),
        )
        return LongTermMemoryWriteResult(
            status="written" if review_status == "auto_approved" else "needs_review",
            memory_id=replacement.id,
            review_status=review_status,
            decision=decision,
            reason_code=reason_code,
            pii_classification=replacement_candidate.pii_classification,
            candidate_hash=identity.candidate_hash,
            content_hash=identity.content_hash,
            source_identity_hash=identity.source_identity_hash,
            event_id=event.id,
        )


def _review_status_for_source(source_type: str) -> str:
    return long_term_review_status_for_source(source_type)


def _review_status_for_candidate(candidate: LongTermMemoryWriteCandidate) -> str:
    return long_term_review_status_for_source(candidate.source_type, candidate.source_ref)


def _policy_decision_for_candidate(candidate: LongTermMemoryWriteCandidate):
    return long_term_memory_policy_decision(
        candidate.source_type,
        candidate.source_ref,
        pii_classification=candidate.pii_classification,
    )


def _hard_rule_preference_reason(content: str) -> str | None:
    validation = validate_soft_preference_text(content)
    if validation.valid:
        return None
    return validation.reason_code


def _policy_event_kwargs(policy_decision) -> dict[str, Any]:
    return {
        "policy_version": policy_decision.policy_version,
        "blocked_by": list(policy_decision.blocked_by),
        "authority_class": policy_decision.authority_class,
    }


async def _emit_skipped_candidate_result(
    repository: LongTermMemoryRepository,
    *,
    candidate: LongTermMemoryWriteCandidate,
    run_id,
    identity: MemoryCandidateIdentityV1,
    policy_decision,
    reason_code: str,
    blocked_by: list[str],
) -> LongTermMemoryWriteResult:
    event = await repository.emit_write_event(
        tenant_id=candidate.tenant_id,
        run_id=run_id,
        memory_type=LONG_TERM_MEMORY_TYPE,
        memory_id=None,
        decision="skip",
        reason_code=reason_code,
        pii_classification=candidate.pii_classification,
        candidate_hash=identity.candidate_hash,
        source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
        policy_version=policy_decision.policy_version,
        blocked_by=blocked_by,
        authority_class=policy_decision.authority_class,
    )
    return LongTermMemoryWriteResult(
        status="skipped",
        memory_id=None,
        review_status=None,
        decision="skip",
        reason_code=reason_code,
        pii_classification=candidate.pii_classification,
        candidate_hash=identity.candidate_hash,
        content_hash=identity.content_hash,
        source_identity_hash=identity.source_identity_hash,
        event_id=event.id,
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
