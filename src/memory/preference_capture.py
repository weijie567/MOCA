"""Deterministic explicit preference capture for long-term memory."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal
import re
import uuid

from pydantic import BaseModel, ConfigDict

from src.memory.schemas import LongTermMemoryWriteCandidate, MemorySourceRefV1
from src.platform.trusted_context import MerchantScopeV1, merchant_scope_allows


PreferencePiiClassification = Literal["none", "low", "sensitive", "prohibited"]

_EXPLICIT_PREFERENCE_PHRASES = (
    "remember this preference",
    "save this preference",
    "use this going forward",
    "记住这个偏好",
    "保存这个偏好",
    "以后按这个",
    "之后按这个",
)
_HARD_RULE_MARKERS = (
    "must refund",
    "must reject",
    "must approve",
    "always approve",
    "always reject",
    "必须退款",
    "必须拒绝",
    "必须通过",
    "一律退款",
    "一律拒绝",
    "必须执行",
)
_PROHIBITED_PII_MARKERS = {"身份证", "password", "secret"}
_SENSITIVE_PII_PATTERNS = (
    re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\w)"),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|credential|passwd|pwd)\b\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
)


class ExplicitPreferenceIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    phrase: str
    content: str


class PreferenceValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    valid: bool
    reason_code: str
    pii_classification: PreferencePiiClassification = "none"


def detect_explicit_preference_intent(text: str) -> ExplicitPreferenceIntent | None:
    for phrase in _EXPLICIT_PREFERENCE_PHRASES:
        match = re.search(re.escape(phrase), text, flags=re.IGNORECASE)
        if match is None:
            continue
        content = text[match.end() :].lstrip(" \t\r\n:：,，.-。")
        if not content:
            return None
        return ExplicitPreferenceIntent(phrase=phrase, content=content)
    return None


def validate_soft_preference_text(text: str) -> PreferenceValidationResult:
    lowered = text.casefold()
    if any(marker in lowered or marker in text for marker in _HARD_RULE_MARKERS):
        return PreferenceValidationResult(
            valid=False,
            reason_code="hard_rule_not_preference",
            pii_classification=classify_preference_pii(text),
        )
    return PreferenceValidationResult(
        valid=True,
        reason_code="eligible",
        pii_classification=classify_preference_pii(text),
    )


def classify_preference_pii(text: str) -> PreferencePiiClassification:
    lowered = text.casefold()
    if any(marker.casefold() in lowered for marker in _PROHIBITED_PII_MARKERS):
        return "prohibited"
    if any(pattern.search(text) for pattern in _SENSITIVE_PII_PATTERNS):
        return "sensitive"
    return "none"


def build_explicit_user_preference_candidate(
    state: Mapping[str, Any],
    *,
    trusted_context: Any | None = None,
) -> LongTermMemoryWriteCandidate | None:
    intent = detect_explicit_preference_intent(_state_text(state))
    if intent is None:
        return None

    validation = validate_soft_preference_text(intent.content)
    if not validation.valid or validation.pii_classification in {"sensitive", "prohibited"}:
        return None

    scope_id = _trusted_merchant_scope_id(state, trusted_context=trusted_context)
    if scope_id is None:
        return None

    tenant_id = uuid.UUID(str(state["tenant_id"]))
    run_id = uuid.UUID(str(state["current_run_id"]))
    return LongTermMemoryWriteCandidate(
        tenant_id=tenant_id,
        run_id=run_id,
        scope_type="merchant",
        scope_id=scope_id,
        memory_kind="preference",
        content=intent.content,
        source_type="explicit_user_preference",
        source_ref=MemorySourceRefV1(
            source_type="explicit_user_preference",
            run_id=str(run_id),
            agent_run_id=str(run_id),
            business_object_type="merchant",
            business_object_id=scope_id,
        ),
        confidence=1.0,
        pii_classification=validation.pii_classification,
    )


def _state_text(state: Mapping[str, Any]) -> str:
    for key in ("user_query", "normalized_query"):
        value = state.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _trusted_merchant_scope_id(state: Mapping[str, Any], *, trusted_context: Any | None) -> str | None:
    scope = _trusted_merchant_scope(trusted_context)
    if scope is None:
        return None

    for slot_source in ("active_slots", "extracted_slots"):
        slots = state.get(slot_source)
        if not isinstance(slots, Mapping):
            continue
        merchant_id = slots.get("merchant_id")
        if merchant_id and merchant_scope_allows(scope, merchant_id=str(merchant_id)):
            return str(merchant_id)

    merchant_ids = [merchant_id for merchant_id in scope.merchant_ids if merchant_id != "*"]
    if len(merchant_ids) == 1:
        return merchant_ids[0]
    return None


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
