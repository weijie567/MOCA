from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from src.agent.intent_policy import REQUIRED_SLOT_POLICY
from src.config import settings
from src.memory.policy import (
    REVIEW_REQUIRED_CASE_SOURCE_TYPES,
    REVIEW_REQUIRED_LONG_TERM_SOURCE_TYPES,
    case_memory_policy_decision,
    long_term_memory_policy_decision,
    session_memory_policy_decision,
)
from src.memory.preference_capture import build_explicit_user_preference_candidate
from src.memory.schemas import (
    CaseMemoryWriteCandidate,
    CaseMemoryWriteResult,
    LongTermMemoryWriteCandidate,
    LongTermMemoryWriteResult,
    SessionMemoryWriteCandidate,
    SessionMemoryWriteResult,
    SessionSlotV1,
)
from src.platform.trusted_context import MerchantScopeV1, merchant_scope_allows


MemoryWriteCandidate = SessionMemoryWriteCandidate | LongTermMemoryWriteCandidate | CaseMemoryWriteCandidate
MemoryWriteResult = SessionMemoryWriteResult | LongTermMemoryWriteResult | CaseMemoryWriteResult


_PROHIBITED_PII_MARKERS = {"身份证", "手机号", "password", "secret"}
_CROSS_INTENT_BUSINESS_ID_SLOTS = {"order_id", "refund_case_id", "ticket_id"}
_SENSITIVE_PII_PATTERNS = (
    re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\w)"),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|credential|passwd|pwd)\b\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
)


class MemoryWriteService:
    def __init__(
        self,
        session_memory_service: Any | None = None,
        *,
        long_term_memory_service: Any | None = None,
        case_memory_service: Any | None = None,
    ) -> None:
        self.session_memory_service = session_memory_service
        self.long_term_memory_service = long_term_memory_service
        self.case_memory_service = case_memory_service

    def propose_candidates(
        self,
        state: Mapping[str, Any],
        *,
        requested_types: Sequence[str] | None = None,
        trusted_context: Any | None = None,
    ) -> list[MemoryWriteCandidate]:
        requested = {str(item) for item in requested_types} if requested_types is not None else {"session"}
        candidates: list[MemoryWriteCandidate] = []
        if "session" in requested:
            candidates.append(_build_session_candidate(state))
        preference_candidate = build_explicit_user_preference_candidate(state, trusted_context=trusted_context)
        if preference_candidate is not None and _candidate_type_allowed(
            preference_candidate,
            requested_types=requested_types,
        ):
            candidates.append(preference_candidate)
        candidates.extend(
            _explicit_candidates(
                state.get("memory_write_candidates"),
                state=state,
                requested_types=requested_types,
                trusted_context=trusted_context,
            )
        )
        return candidates

    def evaluate_policy(self, candidate: MemoryWriteCandidate):
        if isinstance(candidate, SessionMemoryWriteCandidate):
            return session_memory_policy_decision(candidate.pii_classification)
        if isinstance(candidate, LongTermMemoryWriteCandidate):
            return long_term_memory_policy_decision(
                candidate.source_type,
                candidate.source_ref,
                pii_classification=candidate.pii_classification,
            )
        if isinstance(candidate, CaseMemoryWriteCandidate):
            return case_memory_policy_decision(
                candidate.source_type,
                candidate.source_ref,
                pii_classification=candidate.pii_classification,
            )
        raise TypeError(f"unsupported memory write candidate: {type(candidate)!r}")

    async def apply_policy_and_write(
        self,
        candidates: Sequence[MemoryWriteCandidate],
    ) -> MemoryWriteResult:
        if not candidates:
            return SessionMemoryWriteResult(
                status="skipped",
                version=None,
                decision="skip",
                reason_code="no_candidates",
                pii_classification="none",
            )
        candidate = candidates[0]
        return await self.apply_policy_and_write_candidate(candidate)

    async def apply_policy_and_write_all(
        self,
        candidates: Sequence[MemoryWriteCandidate],
    ) -> list[MemoryWriteResult]:
        return [await self.apply_policy_and_write_candidate(candidate) for candidate in candidates]

    async def apply_policy_and_write_candidate(self, candidate: MemoryWriteCandidate) -> MemoryWriteResult:
        if isinstance(candidate, SessionMemoryWriteCandidate):
            return await self._write_session_candidate(candidate)
        if isinstance(candidate, LongTermMemoryWriteCandidate):
            if self.long_term_memory_service is None:
                raise RuntimeError("long_term_memory_service is required for long-term memory writes")
            return await self.long_term_memory_service.write_memory(candidate)
        if isinstance(candidate, CaseMemoryWriteCandidate):
            if self.case_memory_service is None:
                raise RuntimeError("case_memory_service is required for case memory writes")
            return await self.case_memory_service.submit_case_memory_candidate(candidate)
        raise TypeError(f"unsupported memory write candidate: {type(candidate)!r}")

    async def _write_session_candidate(self, candidate: SessionMemoryWriteCandidate) -> SessionMemoryWriteResult:
        if candidate.decision == "skip":
            return SessionMemoryWriteResult(
                status="skipped",
                version=None,
                decision="skip",
                reason_code=candidate.reason_code,
                pii_classification=candidate.pii_classification,
            )
        if self.session_memory_service is None:
            raise RuntimeError("session_memory_service is required for session memory writes")
        return await self.session_memory_service.write_session_memory(candidate)


def _build_session_candidate(state: Mapping[str, Any]) -> SessionMemoryWriteCandidate:
    now = datetime.now(UTC)
    run_id = uuid.UUID(str(state.get("current_run_id")))
    intent = state.get("primary_intent") or state.get("current_intent")
    explicit_slots = _explicit_slots(state, run_id, str(intent) if intent else None, now)
    unresolved_questions = _unresolved_questions(state)
    session_summary = _session_summary(str(intent) if intent else None, explicit_slots)
    pii_classification = _classify_pii(
        state,
        explicit_slots,
        unresolved_questions=unresolved_questions,
        session_summary=session_summary,
    )
    policy_decision = session_memory_policy_decision(pii_classification)
    decision = "skip" if policy_decision.decision == "skip" else "write"
    session_memory = state.get("session_memory") if isinstance(state.get("session_memory"), dict) else {}
    expected_version = session_memory.get("version") if isinstance(session_memory.get("version"), int) else None
    return SessionMemoryWriteCandidate(
        tenant_id=uuid.UUID(str(state["tenant_id"])),
        user_id=uuid.UUID(str(state["user_id"])),
        thread_id=str(state["thread_id"]),
        run_id=run_id,
        explicit_slots=explicit_slots,
        unresolved_questions=unresolved_questions,
        last_intent=str(intent) if intent else None,
        session_summary=session_summary,
        last_business_context_refs=_last_business_context_refs(state),
        expected_version=expected_version,
        pii_classification=pii_classification,
        decision=decision,
        reason_code=policy_decision.reason_code,
    )


def _explicit_candidates(
    value: Any,
    *,
    state: Mapping[str, Any],
    requested_types: Sequence[str] | None,
    trusted_context: Any | None,
) -> list[MemoryWriteCandidate]:
    state_tenant_id = _state_uuid(state, "tenant_id")
    state_run_id = _state_uuid(state, "current_run_id")
    if state_tenant_id is None or state_run_id is None:
        return []

    candidates: list[MemoryWriteCandidate] = []
    for item in _candidate_items(value):
        candidate = _coerce_explicit_candidate(item)
        if (
            candidate is None
            or not _candidate_type_allowed(candidate, requested_types=requested_types)
            or not _state_candidate_identity_allowed(
                candidate,
                tenant_id=state_tenant_id,
                run_id=state_run_id,
                trusted_context=trusted_context,
            )
        ):
            continue
        candidates.append(candidate)
    return candidates


def _state_uuid(state: Mapping[str, Any], key: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(state[key]))
    except (KeyError, TypeError, ValueError):
        return None


def _candidate_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list | tuple):
        return list(value)
    return [value]


def _coerce_explicit_candidate(value: Any) -> MemoryWriteCandidate | None:
    if isinstance(value, SessionMemoryWriteCandidate | LongTermMemoryWriteCandidate | CaseMemoryWriteCandidate):
        return value
    if not isinstance(value, Mapping):
        return None
    memory_type = _explicit_memory_type(value)
    payload = {
        key: item
        for key, item in value.items()
        if key not in {"memory_type", "type", "kind", "schema_version"}
    }
    if memory_type == "session":
        return SessionMemoryWriteCandidate.model_validate(payload)
    if memory_type == "long_term":
        return LongTermMemoryWriteCandidate.model_validate(payload)
    if memory_type == "case":
        return CaseMemoryWriteCandidate.model_validate(payload)
    return None


def _explicit_memory_type(value: Mapping[str, Any]) -> str | None:
    raw_type = value.get("memory_type") or value.get("type") or value.get("kind")
    if raw_type in {"session", "session_slot", "session_memory"}:
        return "session"
    if raw_type in {"long_term", "long_term_fact", "long_term_memory"}:
        return "long_term"
    if raw_type in {"case", "case_memory"}:
        return "case"
    if "explicit_slots" in value:
        return "session"
    if "content" in value and "source_type" in value:
        return "long_term"
    if "case_type" in value and "summary" in value:
        return "case"
    return None


def _candidate_type_allowed(candidate: MemoryWriteCandidate, *, requested_types: Sequence[str] | None) -> bool:
    if requested_types is None:
        return True
    requested = {str(item) for item in requested_types}
    if isinstance(candidate, SessionMemoryWriteCandidate):
        return "session" in requested
    if isinstance(candidate, LongTermMemoryWriteCandidate):
        return "long_term" in requested
    if isinstance(candidate, CaseMemoryWriteCandidate):
        return "case" in requested
    return False


def _state_candidate_identity_allowed(
    candidate: MemoryWriteCandidate,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    trusted_context: Any | None,
) -> bool:
    if candidate.tenant_id != tenant_id or candidate.run_id != run_id:
        return False
    if not _source_ref_identity_allowed(candidate, run_id=run_id):
        return False
    if isinstance(candidate, LongTermMemoryWriteCandidate):
        return _state_long_term_candidate_allowed(candidate, trusted_context=trusted_context)
    if isinstance(candidate, CaseMemoryWriteCandidate):
        return _state_case_candidate_allowed(candidate, trusted_context=trusted_context)
    return True


def _source_ref_identity_allowed(candidate: MemoryWriteCandidate, *, run_id: uuid.UUID) -> bool:
    source_ref = getattr(candidate, "source_ref", None)
    if source_ref is None:
        return True
    if getattr(source_ref, "source_type", None) != getattr(candidate, "source_type", None):
        return False
    for field in ("run_id", "agent_run_id"):
        value = getattr(source_ref, field, None)
        if value is not None and value != str(run_id):
            return False
    return True


def _state_long_term_candidate_allowed(
    candidate: LongTermMemoryWriteCandidate,
    *,
    trusted_context: Any | None,
) -> bool:
    if candidate.source_type not in REVIEW_REQUIRED_LONG_TERM_SOURCE_TYPES:
        return False
    if candidate.scope_type != "merchant":
        return False
    if not _trusted_merchant_scope_allows(candidate.scope_id, trusted_context=trusted_context):
        return False
    source_ref = candidate.source_ref
    if source_ref is not None and source_ref.business_object_type == "merchant":
        return source_ref.business_object_id == candidate.scope_id
    return True


def _state_case_candidate_allowed(
    candidate: CaseMemoryWriteCandidate,
    *,
    trusted_context: Any | None,
) -> bool:
    if candidate.source_type not in REVIEW_REQUIRED_CASE_SOURCE_TYPES:
        return False
    if candidate.source_type == "closed_case_cwc_candidate" and not _closed_case_source_ref_allowed(candidate):
        return False
    if candidate.scope_type == "merchant":
        if not _trusted_merchant_scope_allows(candidate.scope_id, trusted_context=trusted_context):
            return False
        source_ref = candidate.source_ref
        if source_ref is not None and source_ref.business_object_type == "merchant":
            return source_ref.business_object_id == candidate.scope_id
        return True
    if candidate.scope_type == "case":
        return _state_case_scope_source_ref_allowed(candidate)
    return False


def _state_case_scope_source_ref_allowed(candidate: CaseMemoryWriteCandidate) -> bool:
    if not _closed_case_source_ref_allowed(candidate):
        return False
    source_ref = candidate.source_ref
    return source_ref is not None and source_ref.business_object_id == candidate.scope_id


def _closed_case_source_ref_allowed(candidate: CaseMemoryWriteCandidate) -> bool:
    if candidate.source_type != "closed_case_cwc_candidate":
        return False
    source_ref = candidate.source_ref
    if source_ref is None:
        return False
    return (
        source_ref.business_object_type == "refund_case"
        and bool(source_ref.business_object_id)
        and bool(source_ref.event_id)
    )


def _trusted_merchant_scope_allows(scope_id: str, *, trusted_context: Any | None) -> bool:
    scope = _trusted_merchant_scope(trusted_context)
    if scope is None:
        return False
    return merchant_scope_allows(scope, merchant_id=scope_id)


def _trusted_merchant_scope(trusted_context: Any | None) -> MerchantScopeV1 | None:
    if trusted_context is None:
        return None
    raw_scope = (
        trusted_context.get("merchant_scope")
        if isinstance(trusted_context, Mapping)
        else getattr(trusted_context, "merchant_scope", None)
    )
    if raw_scope is None:
        return None
    if isinstance(raw_scope, MerchantScopeV1):
        return raw_scope
    if isinstance(raw_scope, Mapping):
        return MerchantScopeV1.model_validate(raw_scope)
    return None


def _explicit_slots(
    state: Mapping[str, Any],
    run_id: uuid.UUID,
    intent: str | None,
    now: datetime,
) -> dict[str, SessionSlotV1]:
    extracted = state.get("extracted_slots") if isinstance(state.get("extracted_slots"), dict) else {}
    expires_at = now + timedelta(seconds=settings.session_memory_ttl_seconds)
    slots: dict[str, SessionSlotV1] = {}
    for key, value in extracted.items():
        if value in (None, ""):
            continue
        slots[key] = SessionSlotV1(
            value=str(value),
            source="explicit_user",
            source_run_id=str(run_id),
            updated_at=now,
            expires_at=expires_at,
            compatible_intents=_compatible_intents_for_slot(str(key), intent),
        )
    return slots


def _compatible_intents_for_slot(slot_name: str, current_intent: str | None) -> list[str]:
    if slot_name not in _CROSS_INTENT_BUSINESS_ID_SLOTS:
        return [current_intent] if current_intent else []

    compatible = [
        intent
        for intent, policy in REQUIRED_SLOT_POLICY.items()
        if slot_name in _required_slot_names(policy.model_dump())
    ]
    if current_intent and current_intent not in compatible:
        compatible.append(current_intent)
    return compatible


def _required_slot_names(policy: dict[str, Any]) -> set[str]:
    names = set(str(slot) for slot in policy.get("all_of") or [])
    names.update(str(slot) for slot in policy.get("optional") or [])
    for group in policy.get("any_of") or []:
        if isinstance(group, list):
            names.update(str(slot) for slot in group)
    return names


def _unresolved_questions(state: Mapping[str, Any]) -> list[str]:
    clarification = state.get("clarification_request")
    if not isinstance(clarification, dict):
        return []
    questions = clarification.get("questions")
    if not isinstance(questions, list):
        return []
    return [str(question) for question in questions if question]


def _session_summary(intent: str | None, explicit_slots: dict[str, SessionSlotV1]) -> str | None:
    if not intent and not explicit_slots:
        return None
    slot_names = ",".join(sorted(explicit_slots)) or "none"
    summary = f"Session turn completed; intent={intent or 'unknown'}; explicit_slots={slot_names}."
    return summary[: settings.session_memory_summary_max_chars]


def _last_business_context_refs(state: Mapping[str, Any]) -> dict[str, Any]:
    refs = state.get("last_business_context_refs")
    return dict(refs) if isinstance(refs, dict) else {}


def _classify_pii(
    state: Mapping[str, Any],
    explicit_slots: dict[str, SessionSlotV1],
    *,
    unresolved_questions: list[str],
    session_summary: str | None,
) -> str:
    values = [slot.value for slot in explicit_slots.values()]
    values.extend(unresolved_questions)
    if session_summary:
        values.append(session_summary)
    final_response = state.get("final_response")
    if isinstance(final_response, str):
        values.append(final_response)
    text = " ".join(values).lower()
    if any(marker.lower() in text for marker in _PROHIBITED_PII_MARKERS):
        return "prohibited"
    if any(pattern.search(text) for pattern in _SENSITIVE_PII_PATTERNS):
        return "sensitive"
    return "none"
