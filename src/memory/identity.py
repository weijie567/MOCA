"""Canonical memory identity helpers for reviewed long-term and case memory."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from src.common.canonical_hash import CanonicalHashError, canonical_hash


MEMORY_IDENTITY_VERSION = "memory_identity.v1"
MEMORY_CONTENT_HASH_SCHEMA_VERSION = f"{MEMORY_IDENTITY_VERSION}.content"
MEMORY_CANONICAL_HASH_SCHEMA_VERSION = f"{MEMORY_IDENTITY_VERSION}.canonical"
MEMORY_SOURCE_HASH_SCHEMA_VERSION = f"{MEMORY_IDENTITY_VERSION}.source"
MEMORY_CANDIDATE_HASH_SCHEMA_VERSION = f"{MEMORY_IDENTITY_VERSION}.candidate"

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


class MemoryIdentityError(ValueError):
    """Raised when a memory identity input is not canonicalizable."""


def normalize_memory_content(content: str) -> str:
    """Return memory content normalized for stable identity matching."""

    if not isinstance(content, str):
        raise MemoryIdentityError("content must be a string")
    normalized = unicodedata.normalize("NFKC", content).casefold()
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def canonical_memory_content_hash(*, memory_type: str, content: str) -> str:
    """Hash normalized memory content in a memory-type-specific namespace."""

    return _hash(
        {
            "schema_version": MEMORY_CONTENT_HASH_SCHEMA_VERSION,
            "memory_type": _require_non_empty_string(memory_type, field_name="memory_type"),
            "normalized_content": normalize_memory_content(content),
        },
        schema_version=MEMORY_CONTENT_HASH_SCHEMA_VERSION,
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


def canonical_source_identity_hash(source_ref: Mapping[str, Any]) -> str | None:
    """Hash a typed memory source ref, or return ``None`` for an empty source ref."""

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
