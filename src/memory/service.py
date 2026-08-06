from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from src.agent.intent_policy import slot_intent_compatible
from src.db.models import SessionMemory
from src.memory.identity import (
    MemoryCandidateIdentityV1,
    build_session_memory_candidate_identity,
)
from src.memory.policy import BLOCKED_MEMORY_WRITE_PII_CLASSIFICATIONS, MEMORY_POLICY_VERSION
from src.memory.repository import SessionMemoryRepository
from src.memory.schemas import (
    SessionMemoryView,
    SessionMemoryWriteCandidate,
    SessionMemoryWriteResult,
    SessionSlotsEnvelopeV1,
)


_SUMMARY_CAP = 2000
_SUMMARY_TRUNCATION_MARKER = "\n\n[summary_truncated]"
BLOCKED_PII_CLASSIFICATIONS = BLOCKED_MEMORY_WRITE_PII_CLASSIFICATIONS


class SessionMemoryWriteResultWithIdentity(SessionMemoryWriteResult):
    """Session write result bound to the exact owner-produced identity."""

    identity: MemoryCandidateIdentityV1


class MemoryService:
    def __init__(self, repository: SessionMemoryRepository, *, enabled: bool = True) -> None:
        self.repository = repository
        self.enabled = enabled

    async def load_session_memory(
        self,
        tenant_id: Any,
        user_id: Any,
        thread_id: str,
        current_intent: str | None,
        now: datetime | None = None,
    ) -> SessionMemoryView:
        if not self.enabled:
            return _fallback_view("disabled")
        now = _aware(now)
        try:
            memory = await self.repository.get_active(tenant_id, user_id, thread_id, include_expired=True)
        except Exception:
            return _fallback_view("unavailable")
        if memory is None:
            return _fallback_view("missing_session")
        if _is_expired(memory.expires_at, now):
            return _fallback_view("expired")

        try:
            envelope = SessionSlotsEnvelopeV1.model_validate(memory.active_slots_json)
        except ValidationError:
            return _fallback_view("invalid_envelope")

        active_slots: dict[str, str] = {}
        slot_metadata: dict[str, dict[str, Any]] = {}
        intent_filter_applied = current_intent is not None
        for slot_name, slot in envelope.slots.items():
            if _is_expired(slot.expires_at, now):
                continue
            intent_compatible = (
                slot_intent_compatible(slot_name, slot.compatible_intents, current_intent)
                if intent_filter_applied
                else False
            )
            if intent_filter_applied and not intent_compatible:
                continue
            active_slots[slot_name] = slot.value
            slot_metadata[slot_name] = {
                "source": "trusted_session_memory",
                "tenant_id": str(memory.tenant_id),
                "user_id": str(memory.user_id),
                "thread_id": memory.thread_id,
                "fresh": True,
                "expires_at": slot.expires_at.isoformat(),
                "updated_at": slot.updated_at.isoformat(),
                "source_run_id": slot.source_run_id,
                "compatible_intents": list(slot.compatible_intents),
                "intent_compatible": intent_compatible,
                "intent_filter_applied": intent_filter_applied,
            }

        return SessionMemoryView(
            source="postgres_session_memory",
            continuity_claimed=bool(
                active_slots
                or memory.session_summary
                or memory.unresolved_questions_json
                or memory.last_intent
                or memory.last_business_context_refs_json
            ),
            active_slots=active_slots,
            slot_metadata=slot_metadata,
            session_summary=memory.session_summary,
            unresolved_questions=list(memory.unresolved_questions_json or []),
            last_intent=memory.last_intent,
            last_business_context_refs=dict(memory.last_business_context_refs_json or {}),
            version=memory.version,
        )

    async def write_session_memory(
        self,
        candidate: SessionMemoryWriteCandidate,
        now: datetime | None = None,
    ) -> SessionMemoryWriteResult:
        identity = build_session_memory_candidate_identity(candidate)
        if not self.enabled:
            return _write_result(
                candidate,
                identity,
                status="disabled",
                reason_code="disabled",
                fallback_reason="disabled",
            )
        if candidate.decision == "skip" or candidate.pii_classification in BLOCKED_PII_CLASSIFICATIONS:
            reason_code = (
                "pii_blocked" if candidate.pii_classification in BLOCKED_PII_CLASSIFICATIONS else candidate.reason_code
            )
            result = _write_result(
                candidate,
                identity,
                status="skipped",
                decision="skip",
                reason_code=reason_code,
            )
            return await self._with_write_event(candidate, identity, result, memory_id=None)

        now = _aware(now)
        try:
            existing = await self.repository.get_active(
                candidate.tenant_id,
                candidate.user_id,
                candidate.thread_id,
                include_expired=True,
            )
            if existing is not None and _is_expired(existing.expires_at, now):
                await self.repository.soft_delete(existing.id)
                return await self._insert_with_race_merge(
                    candidate,
                    identity,
                    now=now,
                    status="written",
                )
            if existing is None:
                return await self._insert_with_race_merge(
                    candidate,
                    identity,
                    now=now,
                    status="written",
                )

            expected_version = candidate.expected_version or existing.version
            merge = _merge_memory(existing, candidate, now=now, cas_retry=False)
            if merge.conflict_reason is not None:
                return await self._with_write_event(
                    candidate,
                    identity,
                    _write_result(
                        candidate,
                        identity,
                        status="conflict",
                        reason_code=merge.conflict_reason,
                        conflict_reason=merge.conflict_reason,
                        version=existing.version,
                    ),
                    memory_id=existing.id,
                )
            updated = await self.repository.cas_update(existing.id, expected_version, merge.values)
            if updated:
                return await self._with_write_event(
                    candidate,
                    identity,
                    _write_result(
                        candidate,
                        identity,
                        status="written",
                        reason_code=merge.reason_code,
                        version=expected_version + 1,
                    ),
                    memory_id=existing.id,
                )

            latest = await self.repository.get_active(
                candidate.tenant_id,
                candidate.user_id,
                candidate.thread_id,
                include_expired=True,
            )
            if latest is None:
                return await self._insert_with_race_merge(
                    candidate,
                    identity,
                    now=now,
                    status="merged_after_conflict",
                )
            if _is_expired(latest.expires_at, now):
                await self.repository.soft_delete(latest.id)
                return await self._insert_with_race_merge(
                    candidate,
                    identity,
                    now=now,
                    status="merged_after_conflict",
                )

            retry_merge = _merge_memory(latest, candidate, now=now, cas_retry=True)
            if retry_merge.conflict_reason is not None:
                return await self._with_write_event(
                    candidate,
                    identity,
                    _write_result(
                        candidate,
                        identity,
                        status="conflict",
                        reason_code=retry_merge.conflict_reason,
                        conflict_reason=retry_merge.conflict_reason,
                        version=latest.version,
                    ),
                    memory_id=latest.id,
                )
            retry_updated = await self.repository.cas_update(latest.id, latest.version, retry_merge.values)
            if retry_updated:
                return await self._with_write_event(
                    candidate,
                    identity,
                    _write_result(
                        candidate,
                        identity,
                        status="merged_after_conflict",
                        reason_code=retry_merge.reason_code,
                        version=latest.version + 1,
                    ),
                    memory_id=latest.id,
                )
            return await self._with_write_event(
                candidate,
                identity,
                _write_result(
                    candidate,
                    identity,
                    status="conflict",
                    reason_code="cas_retry_missed",
                    conflict_reason="cas_retry_missed",
                    version=latest.version,
                ),
                memory_id=latest.id,
            )
        except Exception:
            await self.repository.session.rollback()
            return _write_result(
                candidate,
                identity,
                status="fallback",
                reason_code="unavailable",
                fallback_reason="unavailable",
            )

    async def _insert(self, candidate: SessionMemoryWriteCandidate, *, now: datetime) -> SessionMemory:
        envelope = SessionSlotsEnvelopeV1(slots=candidate.explicit_slots)
        return await self.repository.insert_active(
            tenant_id=candidate.tenant_id,
            user_id=candidate.user_id,
            thread_id=candidate.thread_id,
            active_slots_json=envelope.model_dump(mode="json"),
            session_summary=candidate.session_summary,
            unresolved_questions_json=list(candidate.unresolved_questions),
            last_intent=candidate.last_intent,
            last_business_context_refs_json=dict(candidate.last_business_context_refs),
            last_run_id=candidate.run_id,
            expires_at=_max_expiry(candidate.explicit_slots, now),
        )

    async def _insert_with_race_merge(
        self,
        candidate: SessionMemoryWriteCandidate,
        identity: MemoryCandidateIdentityV1,
        *,
        now: datetime,
        status: str,
    ) -> SessionMemoryWriteResult:
        try:
            inserted = await self._insert(candidate, now=now)
            return await self._with_write_event(
                candidate,
                identity,
                _write_result(candidate, identity, status=status, version=inserted.version),
                memory_id=inserted.id,
            )
        except IntegrityError:
            await self.repository.session.rollback()
            return await self._merge_after_insert_race(candidate, identity, now=now)

    async def _merge_after_insert_race(
        self,
        candidate: SessionMemoryWriteCandidate,
        identity: MemoryCandidateIdentityV1,
        *,
        now: datetime,
    ) -> SessionMemoryWriteResult:
        latest = await self.repository.get_active(
            candidate.tenant_id,
            candidate.user_id,
            candidate.thread_id,
            include_expired=True,
        )
        if latest is None:
            inserted = await self._insert(candidate, now=now)
            return await self._with_write_event(
                candidate,
                identity,
                _write_result(
                    candidate,
                    identity,
                    status="merged_after_conflict",
                    version=inserted.version,
                ),
                memory_id=inserted.id,
            )
        if _is_expired(latest.expires_at, now):
            await self.repository.soft_delete(latest.id)
            inserted = await self._insert(candidate, now=now)
            return await self._with_write_event(
                candidate,
                identity,
                _write_result(
                    candidate,
                    identity,
                    status="merged_after_conflict",
                    version=inserted.version,
                ),
                memory_id=inserted.id,
            )

        merge = _merge_memory(latest, candidate, now=now, cas_retry=True)
        if merge.conflict_reason is not None:
            return await self._with_write_event(
                candidate,
                identity,
                _write_result(
                    candidate,
                    identity,
                    status="conflict",
                    reason_code=merge.conflict_reason,
                    conflict_reason=merge.conflict_reason,
                    version=latest.version,
                ),
                memory_id=latest.id,
            )
        updated = await self.repository.cas_update(latest.id, latest.version, merge.values)
        if updated:
            return await self._with_write_event(
                candidate,
                identity,
                _write_result(
                    candidate,
                    identity,
                    status="merged_after_conflict",
                    reason_code=merge.reason_code,
                    version=latest.version + 1,
                ),
                memory_id=latest.id,
            )
        return await self._with_write_event(
            candidate,
            identity,
            _write_result(
                candidate,
                identity,
                status="conflict",
                reason_code="cas_retry_missed",
                conflict_reason="cas_retry_missed",
                version=latest.version,
            ),
            memory_id=latest.id,
        )

    async def _with_write_event(
        self,
        candidate: SessionMemoryWriteCandidate,
        identity: MemoryCandidateIdentityV1,
        result: SessionMemoryWriteResult,
        *,
        memory_id,
    ) -> SessionMemoryWriteResult:
        result = result.model_copy(
            update={
                "memory_id": memory_id,
                "policy_version": MEMORY_POLICY_VERSION,
                "blocked_by": _blocked_by_for_result(result),
            }
        )
        try:
            result = result.model_copy(
                update={
                    "candidate_hash": identity.candidate_hash,
                    "identity": identity,
                }
            )
            async with self.repository.session.begin_nested():
                event = await self.repository.emit_write_event(
                    tenant_id=candidate.tenant_id,
                    run_id=candidate.run_id,
                    memory_id=memory_id,
                    decision=_event_decision(result),
                    reason_code=result.reason_code,
                    pii_classification=result.pii_classification,
                    candidate_hash=identity.candidate_hash,
                    source_ref_json=identity.normalized_source_ref.model_dump(mode="json", exclude_none=True),
                    policy_version=MEMORY_POLICY_VERSION,
                    blocked_by=result.blocked_by,
                )
        except Exception:
            return result
        return result.model_copy(update={"event_id": event.id})


class _MergeResult:
    def __init__(
        self,
        values: dict[str, Any],
        conflict_reason: str | None = None,
        reason_code: str | None = None,
    ) -> None:
        self.values = values
        self.conflict_reason = conflict_reason
        self.reason_code = reason_code


def _merge_memory(
    memory: SessionMemory,
    candidate: SessionMemoryWriteCandidate,
    *,
    now: datetime,
    cas_retry: bool,
) -> _MergeResult:
    try:
        existing_envelope = SessionSlotsEnvelopeV1.model_validate(memory.active_slots_json)
    except ValidationError:
        existing_envelope = SessionSlotsEnvelopeV1()

    merged_slots = {
        slot_name: slot for slot_name, slot in existing_envelope.slots.items() if not _is_expired(slot.expires_at, now)
    }
    for slot_name, candidate_slot in candidate.explicit_slots.items():
        existing_slot = merged_slots.get(slot_name)
        if (
            cas_retry
            and existing_slot is not None
            and existing_slot.value != candidate_slot.value
            and existing_slot.source_run_id != candidate_slot.source_run_id
        ):
            return _MergeResult({}, "explicit_slot_conflict")
        merged_slots[slot_name] = candidate_slot

    existing_refs = dict(memory.last_business_context_refs_json or {})
    merged_refs = dict(existing_refs)
    for key, value in candidate.last_business_context_refs.items():
        if cas_retry and key in existing_refs and existing_refs[key] != value:
            return _MergeResult({}, "business_context_ref_conflict")
        merged_refs[key] = value

    session_summary, summary_reason = _merge_summary(memory.session_summary, candidate.session_summary)
    last_intent, last_intent_conflict = _merge_last_intent(
        memory.last_intent, candidate.last_intent, cas_retry=cas_retry
    )
    if last_intent_conflict is not None:
        return _MergeResult({}, last_intent_conflict)

    values = {
        "active_slots_json": SessionSlotsEnvelopeV1(slots=merged_slots).model_dump(mode="json"),
        "session_summary": session_summary,
        "unresolved_questions_json": _merge_unresolved(
            memory.unresolved_questions_json or [],
            candidate.unresolved_questions,
        ),
        "last_intent": last_intent,
        "last_business_context_refs_json": merged_refs,
        "last_run_id": candidate.run_id,
        "expires_at": _max_expiry(merged_slots, now),
    }
    return _MergeResult(values, reason_code=summary_reason)


def _fallback_view(reason: str) -> SessionMemoryView:
    return SessionMemoryView(
        source=reason,
        continuity_claimed=False,
        active_slots={},
        slot_metadata={},
        fallback_reason=reason,
    )


def _write_result(
    candidate: SessionMemoryWriteCandidate,
    identity: MemoryCandidateIdentityV1,
    *,
    status: str,
    reason_code: str | None = None,
    memory_id: Any | None = None,
    version: int | None = None,
    decision: str | None = None,
    conflict_reason: str | None = None,
    fallback_reason: str | None = None,
    candidate_hash: str | None = None,
    event_id: Any | None = None,
    blocked_by: list[str] | None = None,
) -> SessionMemoryWriteResultWithIdentity:
    resolved_reason_code = reason_code or candidate.reason_code
    return SessionMemoryWriteResultWithIdentity(
        status=status,
        memory_id=memory_id,
        version=version,
        decision=decision or candidate.decision,
        reason_code=resolved_reason_code,
        policy_version=MEMORY_POLICY_VERSION,
        blocked_by=blocked_by
        or _blocked_by_for_values(
            status=status,
            reason_code=resolved_reason_code,
            conflict_reason=conflict_reason,
            fallback_reason=fallback_reason,
        ),
        pii_classification=candidate.pii_classification,
        candidate_hash=candidate_hash or identity.candidate_hash,
        identity=identity,
        event_id=event_id,
        conflict_reason=conflict_reason,
        fallback_reason=fallback_reason,
    )


def _event_decision(result: SessionMemoryWriteResult) -> str:
    if result.status in {"conflict", "skipped", "disabled", "fallback", "error"}:
        return "skip"
    return "write" if result.decision == "write" else "skip"


def _blocked_by_for_result(result: SessionMemoryWriteResult) -> list[str]:
    if result.blocked_by:
        return list(result.blocked_by)
    return _blocked_by_for_values(
        status=result.status,
        reason_code=result.reason_code,
        conflict_reason=result.conflict_reason,
        fallback_reason=result.fallback_reason,
    )


def _blocked_by_for_values(
    *,
    status: str,
    reason_code: str,
    conflict_reason: str | None,
    fallback_reason: str | None,
) -> list[str]:
    if reason_code == "pii_blocked":
        return ["pii_classification"]
    if conflict_reason:
        return [conflict_reason]
    if fallback_reason:
        return [fallback_reason]
    if status in {"conflict", "skipped", "disabled", "fallback", "error"} and reason_code:
        return [reason_code]
    return []


def _merge_summary(existing: str | None, candidate: str | None) -> tuple[str | None, str | None]:
    if not existing:
        return _bounded_summary(candidate), "summary_truncated" if candidate and len(candidate) > _SUMMARY_CAP else None
    if not candidate or candidate == existing:
        return existing, None
    combined = f"{existing}\n\n{candidate}"
    if len(combined) <= _SUMMARY_CAP:
        return combined, None
    return _bounded_summary_with_candidate(existing, candidate), "summary_truncated"


def _merge_unresolved(existing: list[Any], candidate: list[Any]) -> list[Any]:
    merged: list[Any] = []
    seen: set[str] = set()
    for item in [*existing, *candidate]:
        key = repr(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _merge_last_intent(
    existing: str | None, candidate: str | None, *, cas_retry: bool
) -> tuple[str | None, str | None]:
    if cas_retry and existing and candidate and existing != candidate:
        return None, "last_intent_conflict"
    return candidate or existing, None


def _bounded_summary(value: str | None) -> str | None:
    if value is None or len(value) <= _SUMMARY_CAP:
        return value
    budget = _SUMMARY_CAP - len(_SUMMARY_TRUNCATION_MARKER)
    return f"{value[:budget].rstrip()}{_SUMMARY_TRUNCATION_MARKER}"


def _bounded_summary_with_candidate(existing: str, candidate: str) -> str:
    candidate_budget = min(len(candidate), max(200, _SUMMARY_CAP // 4))
    separator = "\n\n"
    existing_budget = _SUMMARY_CAP - len(_SUMMARY_TRUNCATION_MARKER) - len(separator) - candidate_budget
    if existing_budget < 0:
        candidate_budget = _SUMMARY_CAP - len(_SUMMARY_TRUNCATION_MARKER)
        return f"{candidate[:candidate_budget].rstrip()}{_SUMMARY_TRUNCATION_MARKER}"
    return (
        f"{existing[:existing_budget].rstrip()}"
        f"{separator}"
        f"{candidate[:candidate_budget].rstrip()}"
        f"{_SUMMARY_TRUNCATION_MARKER}"
    )


def _max_expiry(slots: dict[str, Any], now: datetime) -> datetime | None:
    expiries = [slot.expires_at for slot in slots.values() if slot.expires_at is not None]
    if not expiries:
        return None
    return max(expiries)


def _is_expired(expires_at: datetime | None, now: datetime) -> bool:
    return expires_at is not None and _aware(expires_at) <= now


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
