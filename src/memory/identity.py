"""Single owner for versioned memory-candidate identity construction."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.common.canonical_hash import CanonicalHashError, canonical_hash
from src.memory.case_working_context_schemas import CaseWorkingContextWriteCandidate
from src.memory.schemas import (
    CaseMemoryWriteCandidate,
    LongTermMemoryWriteCandidate,
    MemorySourceRefV1,
    SessionMemoryWriteCandidate,
)


MEMORY_IDENTITY_VERSION = "memory_identity.v1"
MEMORY_CONTENT_HASH_SCHEMA_VERSION = f"{MEMORY_IDENTITY_VERSION}.content"
MEMORY_CANONICAL_HASH_SCHEMA_VERSION = f"{MEMORY_IDENTITY_VERSION}.canonical"
MEMORY_SOURCE_HASH_SCHEMA_VERSION = f"{MEMORY_IDENTITY_VERSION}.source"
MEMORY_CANDIDATE_HASH_SCHEMA_VERSION = f"{MEMORY_IDENTITY_VERSION}.candidate"
LEGACY_MEMORY_IDENTITY_PROFILE = "nfkc_casefold_legacy"
MEMORY_IDENTITY_PROFILE = "nfc_selective_v2"
MemoryIdentityProfile = Literal["nfkc_casefold_legacy", "nfc_selective_v2"]

_V2_CONTENT_HASH_SCHEMA_VERSION = f"{MEMORY_IDENTITY_VERSION}.{MEMORY_IDENTITY_PROFILE}.content"
_V2_SOURCE_HASH_SCHEMA_VERSION = f"{MEMORY_IDENTITY_VERSION}.{MEMORY_IDENTITY_PROFILE}.source"
_V2_CANDIDATE_HASH_SCHEMA_VERSION = f"{MEMORY_IDENTITY_VERSION}.{MEMORY_IDENTITY_PROFILE}.candidate"

ALLOWED_SOURCE_REF_KEYS = frozenset(
    {
        "source_type",
        "run_id",
        "event_id",
        "conversation_message_id",
        "tool_result_id",
        "agent_run_id",
        "business_object_type",
        "business_object_id",
        "policy_version",
        "outcome_id",
    }
)

_SHA256_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_WHITESPACE_RE = re.compile(r"\s+")

_CONTENT_HASH_FIELDS = {"schema_version", "memory_type", "normalized_content"}
_CANONICAL_IDENTITY_FIELDS = {
    "schema_version",
    "tenant_id",
    "memory_type",
    "scope_type",
    "scope_id",
    "content_hash",
}
_SOURCE_IDENTITY_FIELDS = {"schema_version", *ALLOWED_SOURCE_REF_KEYS}
_SOURCE_IDENTITY_NULLABLE_FIELDS = ALLOWED_SOURCE_REF_KEYS - {"source_type"}
_SOURCE_IDENTITY_DISCRIMINATORS = frozenset(
    {
        "event_id",
        "conversation_message_id",
        "tool_result_id",
        "agent_run_id",
        "business_object_id",
        "outcome_id",
    }
)
_CANDIDATE_HASH_FIELDS = {
    "schema_version",
    "tenant_id",
    "memory_type",
    "scope_type",
    "scope_id",
    "content_hash",
    "source_identity_hash",
}
_ENUM_LIKE_CONTENT_FIELDS = frozenset(
    {
        "authority_class",
        "business_object_type",
        "decision",
        "issue_type",
        "last_intent",
        "memory_kind",
        "pii_classification",
        "reason_code",
        "ref_type",
        "schema_version",
        "source",
        "source_type",
    }
)
_T = TypeVar("_T", bound=BaseModel)


class MemoryIdentityError(ValueError):
    """Raised when a memory identity input is not canonicalizable."""


class MemoryCandidateIdentityV1(BaseModel):
    """Frozen output reused by memory stores, events, dedupe, and projections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    identity_profile: MemoryIdentityProfile = MEMORY_IDENTITY_PROFILE
    tenant_id: str
    memory_type: str
    scope_type: str
    scope_id: str
    normalized_source_ref: MemorySourceRefV1 | None = None
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_identity_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    candidate_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def normalize_memory_content(
    content: str,
    *,
    identity_profile: MemoryIdentityProfile = LEGACY_MEMORY_IDENTITY_PROFILE,
) -> str:
    """Normalize content under an explicit profile.

    The default remains the historical profile so existing compatibility callers
    cannot silently reinterpret stored hashes. New candidate builders always use
    :data:`MEMORY_IDENTITY_PROFILE`.
    """

    if not isinstance(content, str):
        raise MemoryIdentityError("content must be a string")
    if identity_profile == LEGACY_MEMORY_IDENTITY_PROFILE:
        normalized = unicodedata.normalize("NFKC", content).casefold()
    elif identity_profile == MEMORY_IDENTITY_PROFILE:
        normalized = unicodedata.normalize("NFC", content)
    else:
        raise MemoryIdentityError(f"unknown memory identity profile: {identity_profile!r}")
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def canonical_memory_content_hash(
    *,
    memory_type: str,
    content: str,
    identity_profile: MemoryIdentityProfile = LEGACY_MEMORY_IDENTITY_PROFILE,
) -> str:
    """Hash content under an explicit profile and memory-type namespace."""

    if identity_profile == LEGACY_MEMORY_IDENTITY_PROFILE:
        schema_version = MEMORY_CONTENT_HASH_SCHEMA_VERSION
    elif identity_profile == MEMORY_IDENTITY_PROFILE:
        schema_version = _V2_CONTENT_HASH_SCHEMA_VERSION
    else:
        raise MemoryIdentityError(f"unknown memory identity profile: {identity_profile!r}")

    return _hash(
        {
            "schema_version": schema_version,
            "memory_type": _require_non_empty_string(memory_type, field_name="memory_type"),
            "normalized_content": normalize_memory_content(content, identity_profile=identity_profile),
        },
        schema_version=schema_version,
        allowed_fields=_CONTENT_HASH_FIELDS,
    )


def canonical_memory_identity_hash(
    *,
    tenant_id: str,
    memory_type: str,
    scope_type: str,
    scope_id: str,
    content_hash: str,
) -> str:
    """Hash the active canonical memory identity across tenant, type, scope, and content."""

    return _hash(
        {
            "schema_version": MEMORY_CANONICAL_HASH_SCHEMA_VERSION,
            "tenant_id": _require_non_empty_string(tenant_id, field_name="tenant_id"),
            "memory_type": _require_non_empty_string(memory_type, field_name="memory_type"),
            "scope_type": _require_non_empty_string(scope_type, field_name="scope_type"),
            "scope_id": _require_non_empty_string(scope_id, field_name="scope_id"),
            "content_hash": _require_sha256_hash(content_hash, field_name="content_hash"),
        },
        schema_version=MEMORY_CANONICAL_HASH_SCHEMA_VERSION,
        allowed_fields=_CANONICAL_IDENTITY_FIELDS,
    )


def canonical_source_identity_hash(
    source_ref: Mapping[str, Any],
    *,
    identity_profile: MemoryIdentityProfile = LEGACY_MEMORY_IDENTITY_PROFILE,
) -> str | None:
    """Hash a typed source ref without reinterpreting legacy callers."""

    if identity_profile == MEMORY_IDENTITY_PROFILE:
        return _source_identity_hash_v2(_normalize_source_ref_v2(source_ref))
    if identity_profile != LEGACY_MEMORY_IDENTITY_PROFILE:
        raise MemoryIdentityError(f"unknown memory identity profile: {identity_profile!r}")

    if not isinstance(source_ref, Mapping):
        raise MemoryIdentityError("source_ref must be a mapping")

    unknown_keys = set(source_ref) - ALLOWED_SOURCE_REF_KEYS
    if unknown_keys:
        raise MemoryIdentityError(f"unknown source identity fields: {sorted(unknown_keys)}")

    if not source_ref or all(value is None for value in source_ref.values()):
        return None

    source_type = source_ref.get("source_type")
    if not isinstance(source_type, str) or not source_type.strip():
        raise MemoryIdentityError("source_type is required for source identity")
    if not any(_has_source_discriminator(source_ref.get(key)) for key in _SOURCE_IDENTITY_DISCRIMINATORS):
        return None

    complete_source_ref = {
        key: _normalize_optional_source_value(source_ref.get(key), field_name=key)
        for key in sorted(ALLOWED_SOURCE_REF_KEYS)
    }
    complete_source_ref["source_type"] = source_type.strip()

    return _hash(
        {
            "schema_version": MEMORY_SOURCE_HASH_SCHEMA_VERSION,
            **complete_source_ref,
        },
        schema_version=MEMORY_SOURCE_HASH_SCHEMA_VERSION,
        allowed_fields=_SOURCE_IDENTITY_FIELDS,
        nullable_fields=_SOURCE_IDENTITY_NULLABLE_FIELDS,
    )


def build_session_memory_candidate_identity(
    candidate: SessionMemoryWriteCandidate | Mapping[str, Any],
) -> MemoryCandidateIdentityV1:
    """Build the complete versioned identity for one session write candidate."""

    typed = _validate_candidate(candidate, SessionMemoryWriteCandidate)
    source_ref = {
        "source_type": "session_memory_write",
        "run_id": str(typed.run_id),
        "agent_run_id": str(typed.run_id),
    }
    content = {
        "schema_version": "session_memory_write_candidate.v1",
        "tenant_id": str(typed.tenant_id),
        "user_id": str(typed.user_id),
        "thread_id": typed.thread_id,
        "run_id": str(typed.run_id),
        "explicit_slots": {
            key: slot.model_dump(mode="json") for key, slot in sorted(typed.explicit_slots.items())
        },
        "unresolved_questions": list(typed.unresolved_questions),
        "last_intent": typed.last_intent,
        "session_summary": typed.session_summary,
        "last_business_context_refs": dict(typed.last_business_context_refs),
        "expected_version": typed.expected_version,
        "pii_classification": typed.pii_classification,
        "decision": typed.decision,
        "reason_code": typed.reason_code,
    }
    return _build_v2_candidate_identity(
        tenant_id=str(typed.tenant_id),
        memory_type="session_slot",
        scope_type="thread",
        scope_id=typed.thread_id,
        content=content,
        source_ref=source_ref,
    )


def build_long_term_memory_candidate_identity(
    candidate: LongTermMemoryWriteCandidate | Mapping[str, Any] | Any,
    *,
    source_ref: Mapping[str, Any] | None = None,
) -> MemoryCandidateIdentityV1:
    """Build identity for a reviewed long-term-memory candidate."""

    if not isinstance(candidate, LongTermMemoryWriteCandidate | Mapping):
        return _build_stored_candidate_identity(
            tenant_id=str(candidate.tenant_id),
            memory_type="long_term_fact",
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            content=candidate.content,
            stored_content_hash=candidate.content_hash,
            source_ref=source_ref if source_ref is not None else dict(candidate.source_ref_json or {}),
            stored_source_identity_hash=candidate.source_identity_hash,
            require_source_match=source_ref is None,
        )
    typed = _validate_candidate(candidate, LongTermMemoryWriteCandidate)
    return _build_v2_candidate_identity(
        tenant_id=str(typed.tenant_id),
        memory_type="long_term_fact",
        scope_type=typed.scope_type,
        scope_id=typed.scope_id,
        content=typed.content,
        source_ref=_candidate_source_ref(typed),
    )


def build_case_memory_candidate_identity(
    candidate: CaseMemoryWriteCandidate | Mapping[str, Any] | Any,
) -> MemoryCandidateIdentityV1:
    """Build identity for a reviewed case-memory candidate."""

    if not isinstance(candidate, CaseMemoryWriteCandidate | Mapping):
        source_ref = dict(candidate.source_ref_json or {})
        content = _case_memory_content(
            source_type=str(source_ref.get("source_type") or ""),
            summary=candidate.summary,
            excerpt=candidate.excerpt,
            applicability=candidate.applicability,
            outcome=candidate.outcome,
            caveats=candidate.caveats,
        )
        return _build_stored_candidate_identity(
            tenant_id=str(candidate.tenant_id),
            memory_type="case_memory",
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            content=content,
            stored_content_hash=candidate.content_hash,
            source_ref=source_ref,
            stored_source_identity_hash=candidate.source_identity_hash,
        )
    typed = _validate_candidate(candidate, CaseMemoryWriteCandidate)
    content = _case_memory_content(
        source_type=typed.source_type,
        summary=typed.summary,
        excerpt=typed.excerpt,
        applicability=typed.applicability,
        outcome=typed.outcome,
        caveats=typed.caveats,
    )
    return _build_v2_candidate_identity(
        tenant_id=str(typed.tenant_id),
        memory_type="case_memory",
        scope_type=typed.scope_type,
        scope_id=typed.scope_id,
        content=content,
        source_ref=_candidate_source_ref(typed),
    )


def build_case_working_context_candidate_identity(
    candidate: CaseWorkingContextWriteCandidate | Mapping[str, Any],
) -> MemoryCandidateIdentityV1:
    """Build identity for one trusted Case Working Context write."""

    typed = _validate_candidate(candidate, CaseWorkingContextWriteCandidate)
    return _build_v2_candidate_identity(
        tenant_id=str(typed.tenant_id),
        memory_type="case_working_context",
        scope_type="case",
        scope_id=str(typed.case_id),
        content=typed.content.model_dump(mode="json"),
        source_ref=typed.source_ref.model_dump(mode="json", exclude_none=True),
    )


def canonical_memory_candidate_hash(
    *,
    tenant_id: str,
    memory_type: str,
    scope_type: str,
    scope_id: str,
    content_hash: str,
    source_identity_hash: str | None = None,
) -> str:
    """Hash the stable write-event/candidate envelope for memory writes."""

    return _hash(
        {
            "schema_version": MEMORY_CANDIDATE_HASH_SCHEMA_VERSION,
            "tenant_id": _require_non_empty_string(tenant_id, field_name="tenant_id"),
            "memory_type": _require_non_empty_string(memory_type, field_name="memory_type"),
            "scope_type": _require_non_empty_string(scope_type, field_name="scope_type"),
            "scope_id": _require_non_empty_string(scope_id, field_name="scope_id"),
            "content_hash": _require_sha256_hash(content_hash, field_name="content_hash"),
            "source_identity_hash": _optional_sha256_hash(
                source_identity_hash,
                field_name="source_identity_hash",
            ),
        },
        schema_version=MEMORY_CANDIDATE_HASH_SCHEMA_VERSION,
        allowed_fields=_CANDIDATE_HASH_FIELDS,
        nullable_fields={"source_identity_hash"},
    )


def _build_v2_candidate_identity(
    *,
    tenant_id: str,
    memory_type: str,
    scope_type: str,
    scope_id: str,
    content: str | Mapping[str, Any],
    source_ref: Mapping[str, Any],
) -> MemoryCandidateIdentityV1:
    normalized_source_ref = _normalize_source_ref_v2(source_ref)
    source_identity_hash = _source_identity_hash_v2(normalized_source_ref)
    normalized_content = _normalize_content_value(content)
    content_text = (
        normalized_content
        if isinstance(normalized_content, str)
        else json.dumps(normalized_content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    content_hash = canonical_memory_content_hash(
        memory_type=memory_type,
        content=content_text,
        identity_profile=MEMORY_IDENTITY_PROFILE,
    )
    candidate_hash = _candidate_hash_v2(
        tenant_id=tenant_id,
        memory_type=memory_type,
        scope_type=scope_type,
        scope_id=scope_id,
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
    )
    return MemoryCandidateIdentityV1(
        identity_profile=MEMORY_IDENTITY_PROFILE,
        tenant_id=tenant_id,
        memory_type=memory_type,
        scope_type=scope_type,
        scope_id=scope_id,
        normalized_source_ref=normalized_source_ref,
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
        candidate_hash=candidate_hash,
    )


def _build_stored_candidate_identity(
    *,
    tenant_id: str,
    memory_type: str,
    scope_type: str,
    scope_id: str,
    content: str,
    stored_content_hash: str,
    source_ref: Mapping[str, Any],
    stored_source_identity_hash: str | None,
    require_source_match: bool = True,
) -> MemoryCandidateIdentityV1:
    for identity_profile in (MEMORY_IDENTITY_PROFILE, LEGACY_MEMORY_IDENTITY_PROFILE):
        content_hash = canonical_memory_content_hash(
            memory_type=memory_type,
            content=content,
            identity_profile=identity_profile,
        )
        if content_hash != stored_content_hash:
            continue
        if identity_profile == MEMORY_IDENTITY_PROFILE:
            try:
                normalized_source_ref = _normalize_source_ref_v2(source_ref)
                source_identity_hash = _source_identity_hash_v2(normalized_source_ref)
            except MemoryIdentityError:
                continue
            candidate_hash = _candidate_hash_v2(
                tenant_id=tenant_id,
                memory_type=memory_type,
                scope_type=scope_type,
                scope_id=scope_id,
                content_hash=content_hash,
                source_identity_hash=source_identity_hash,
            )
        else:
            try:
                normalized_source_ref = MemorySourceRefV1.model_validate(source_ref)
            except ValidationError as exc:
                raise MemoryIdentityError(str(exc)) from exc
            source_identity_hash = canonical_source_identity_hash(source_ref)
            candidate_hash = canonical_memory_candidate_hash(
                tenant_id=tenant_id,
                memory_type=memory_type,
                scope_type=scope_type,
                scope_id=scope_id,
                content_hash=content_hash,
                source_identity_hash=source_identity_hash,
            )
        if require_source_match and source_identity_hash != stored_source_identity_hash:
            continue
        return MemoryCandidateIdentityV1(
            identity_profile=identity_profile,
            tenant_id=tenant_id,
            memory_type=memory_type,
            scope_type=scope_type,
            scope_id=scope_id,
            normalized_source_ref=normalized_source_ref,
            content_hash=content_hash,
            source_identity_hash=source_identity_hash,
            candidate_hash=candidate_hash,
        )
    raise MemoryIdentityError("stored memory identity does not match its legacy or current profile")


def _case_memory_content(
    *,
    source_type: str,
    summary: str,
    excerpt: str | None,
    applicability: str | None,
    outcome: str | None,
    caveats: str | None,
) -> str:
    if source_type != "closed_case_cwc_candidate":
        return summary
    return "\n".join(part for part in (summary, excerpt, applicability, outcome, caveats) if part)


def _candidate_source_ref(
    candidate: LongTermMemoryWriteCandidate | CaseMemoryWriteCandidate,
) -> dict[str, Any]:
    source_ref = candidate.source_ref.model_dump(mode="json", exclude_none=True) if candidate.source_ref else {}
    supplied_source_type = source_ref.get("source_type")
    if supplied_source_type is not None and supplied_source_type != candidate.source_type:
        raise MemoryIdentityError("source_ref.source_type must match candidate.source_type")
    source_ref["source_type"] = candidate.source_type
    if not any(_has_source_discriminator(source_ref.get(key)) for key in _SOURCE_IDENTITY_DISCRIMINATORS):
        source_ref.setdefault("run_id", str(candidate.run_id))
        source_ref["agent_run_id"] = str(candidate.run_id)
    return source_ref


def _normalize_source_ref_v2(source_ref: Mapping[str, Any]) -> MemorySourceRefV1:
    if not isinstance(source_ref, Mapping):
        raise MemoryIdentityError("source_ref must be a mapping")
    unknown_keys = set(source_ref) - ALLOWED_SOURCE_REF_KEYS
    if unknown_keys:
        raise MemoryIdentityError(f"unknown source identity fields: {sorted(unknown_keys)}")
    source_type = source_ref.get("source_type")
    if not isinstance(source_type, str) or not source_type.strip():
        raise MemoryIdentityError("source_type is required for source identity")
    if not any(_has_source_discriminator(source_ref.get(key)) for key in _SOURCE_IDENTITY_DISCRIMINATORS):
        raise MemoryIdentityError("source identity requires a durable discriminator")
    normalized = {
        key: _normalize_v2_string(value, field_name=key)
        for key, value in source_ref.items()
        if value is not None
    }
    try:
        return MemorySourceRefV1.model_validate(normalized)
    except ValidationError as exc:
        raise MemoryIdentityError(str(exc)) from exc


def _source_identity_hash_v2(source_ref: MemorySourceRefV1) -> str:
    complete_source_ref = {
        key: getattr(source_ref, key)
        for key in sorted(ALLOWED_SOURCE_REF_KEYS)
    }
    return _hash(
        {"schema_version": _V2_SOURCE_HASH_SCHEMA_VERSION, **complete_source_ref},
        schema_version=_V2_SOURCE_HASH_SCHEMA_VERSION,
        allowed_fields=_SOURCE_IDENTITY_FIELDS,
        nullable_fields=_SOURCE_IDENTITY_NULLABLE_FIELDS,
    )


def _candidate_hash_v2(
    *,
    tenant_id: str,
    memory_type: str,
    scope_type: str,
    scope_id: str,
    content_hash: str,
    source_identity_hash: str,
) -> str:
    return _hash(
        {
            "schema_version": _V2_CANDIDATE_HASH_SCHEMA_VERSION,
            "tenant_id": _normalize_v2_string(tenant_id, field_name="tenant_id"),
            "memory_type": _normalize_v2_string(memory_type, field_name="memory_type"),
            "scope_type": _normalize_v2_string(scope_type, field_name="scope_type"),
            "scope_id": _normalize_v2_string(scope_id, field_name="scope_id"),
            "content_hash": _require_sha256_hash(content_hash, field_name="content_hash"),
            "source_identity_hash": _require_sha256_hash(
                source_identity_hash,
                field_name="source_identity_hash",
            ),
        },
        schema_version=_V2_CANDIDATE_HASH_SCHEMA_VERSION,
        allowed_fields=_CANDIDATE_HASH_FIELDS,
        nullable_fields={"source_identity_hash"},
    )


def _normalize_content_value(value: Any, *, field_name: str | None = None) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise MemoryIdentityError("memory content keys must be strings")
            normalized[key] = _normalize_content_value(value[key], field_name=key)
        return normalized
    if isinstance(value, list):
        return [_normalize_content_value(item, field_name=field_name) for item in value]
    if isinstance(value, str):
        return _normalize_v2_string(value, field_name=field_name)
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MemoryIdentityError("memory content floats must be finite")
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    raise MemoryIdentityError(f"unsupported memory content value: {type(value).__name__}")


def _normalize_v2_string(value: Any, *, field_name: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MemoryIdentityError(f"{field_name or 'value'} must be a non-empty string")
    normalized = normalize_memory_content(value, identity_profile=MEMORY_IDENTITY_PROFILE)
    if field_name in _ENUM_LIKE_CONTENT_FIELDS:
        normalized = normalized.lower()
    return normalized


def _validate_candidate(value: _T | Mapping[str, Any], model_type: type[_T]) -> _T:
    try:
        return model_type.model_validate(value)
    except ValidationError as exc:
        raise MemoryIdentityError(str(exc)) from exc


def _hash(
    value: Mapping[str, Any],
    *,
    schema_version: str,
    allowed_fields: set[str],
    nullable_fields: set[str] | None = None,
) -> str:
    try:
        return canonical_hash(
            value,
            schema_version=schema_version,
            allowed_fields=allowed_fields,
            nullable_fields=nullable_fields,
        )
    except CanonicalHashError as exc:
        raise MemoryIdentityError(str(exc)) from exc


def _require_non_empty_string(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MemoryIdentityError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_sha256_hash(value: str, *, field_name: str) -> str:
    normalized = _require_non_empty_string(value, field_name=field_name)
    if not _SHA256_HASH_RE.fullmatch(normalized):
        raise MemoryIdentityError(f"{field_name} must be a sha256 hash")
    return normalized


def _optional_sha256_hash(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_sha256_hash(value, field_name=field_name)


def _has_source_discriminator(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalize_optional_source_value(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name=field_name)
