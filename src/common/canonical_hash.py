"""Canonical JSON and hash helpers for hashable MOCA contracts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

HASH_PROFILE_VERSION = "hash_profile.v1"

_MONEY_AMOUNT_RE = re.compile(r"^-?(0|[1-9][0-9]*)\.[0-9]{2}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_FIXED_MILLISECOND_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class CanonicalHashError(ValueError):
    """Raised when a value cannot be represented under CanonicalHashProfile v1."""


def canonical_json(
    value: Mapping[str, Any],
    *,
    schema_version: str,
    allowed_fields: set[str] | None = None,
    nullable_fields: set[str] | None = None,
) -> str:
    """Return MOCA Canonical JSON v1 for a complete hashable mapping."""

    if not isinstance(value, Mapping):
        raise CanonicalHashError("canonical_json value must be a mapping")

    nullable = nullable_fields or set()
    if allowed_fields is not None:
        keys = set(value)
        unknown = keys - allowed_fields
        if unknown:
            raise CanonicalHashError(f"unknown fields: {sorted(unknown)}")
        absent = allowed_fields - keys
        if absent:
            raise CanonicalHashError(f"absent fields: {sorted(absent)}")

    if value.get("schema_version") not in (None, schema_version):
        raise CanonicalHashError(f"schema_version {value.get('schema_version')!r} does not match {schema_version!r}")

    normalized = _normalize_value(value, nullable_fields=nullable, path=())
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def hash_input_bytes(schema_version: str, canonical: str) -> bytes:
    """Return the exact bytes hashed by CanonicalHashProfile v1."""

    return f"{HASH_PROFILE_VERSION}\n{schema_version}\n{canonical}".encode("utf-8")


def canonical_hash(
    value: Mapping[str, Any],
    *,
    schema_version: str,
    allowed_fields: set[str] | None = None,
    nullable_fields: set[str] | None = None,
) -> str:
    """Return ``sha256:<lowercase hex>`` for a hashable contract mapping."""

    canonical = canonical_json(
        value,
        schema_version=schema_version,
        allowed_fields=allowed_fields,
        nullable_fields=nullable_fields,
    )
    digest = hashlib.sha256(hash_input_bytes(schema_version, canonical)).hexdigest()
    return f"sha256:{digest}"


def _normalize_value(value: Any, *, nullable_fields: set[str], path: tuple[str, ...]) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise CanonicalHashError(f"non-string key at {_format_path(path)}")
            normalized[key] = _normalize_value(
                value[key],
                nullable_fields=nullable_fields,
                path=(*path, key),
            )
        return normalized

    if isinstance(value, list):
        return [_normalize_value(item, nullable_fields=nullable_fields, path=(*path, "[]")) for item in value]

    if value is None:
        field_name = path[-1] if path else ""
        if field_name not in nullable_fields:
            raise CanonicalHashError(f"null is not allowed for {_format_path(path)}")
        return None

    if isinstance(value, datetime):
        return _format_datetime(value, path=path)

    if isinstance(value, float):
        raise CanonicalHashError(f"bare JSON float is not allowed at {_format_path(path)}")

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        _validate_integer(value, path=path)
        _validate_field_semantics(value, path=path)
        return value

    if isinstance(value, str):
        _validate_field_semantics(value, path=path)
        return value

    raise CanonicalHashError(f"unsupported canonical JSON value at {_format_path(path)}: {type(value).__name__}")


def _validate_integer(value: int, *, path: tuple[str, ...]) -> None:
    if str(value) == "-0":
        raise CanonicalHashError(f"negative zero is not allowed at {_format_path(path)}")


def _validate_field_semantics(value: int | str, *, path: tuple[str, ...]) -> None:
    field_name = path[-1] if path else ""

    if field_name == "amount":
        if not isinstance(value, str) or not _MONEY_AMOUNT_RE.fullmatch(value):
            raise CanonicalHashError(
                f"amount must be a normalized decimal string with fixed 2-digit scale at {_format_path(path)}"
            )
        return

    if field_name == "currency" and isinstance(value, str) and not _CURRENCY_RE.fullmatch(value):
        raise CanonicalHashError(f"currency must be uppercase ISO-4217 at {_format_path(path)}")

    if field_name.endswith("_at") and isinstance(value, str):
        if not _FIXED_MILLISECOND_UTC_RE.fullmatch(value):
            raise CanonicalHashError(f"datetime string must use fixed millisecond UTC at {_format_path(path)}")


def _format_datetime(value: datetime, *, path: tuple[str, ...]) -> str:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise CanonicalHashError(f"datetime must be timezone-aware UTC at {_format_path(path)}")
    if value.microsecond % 1000 != 0:
        raise CanonicalHashError(f"datetime must have fixed millisecond precision at {_format_path(path)}")
    normalized = value.astimezone(UTC)
    return normalized.strftime("%Y-%m-%dT%H:%M:%S.") + f"{normalized.microsecond // 1000:03d}Z"


def _format_path(path: tuple[str, ...]) -> str:
    return ".".join(path) if path else "<root>"
