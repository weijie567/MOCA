"""Exact tombstone identity helpers for memory no-rewrite protection."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from src.db.models import MemoryTombstone
from src.memory.identity import canonical_source_identity_hash


def source_identity_hash_for_tombstone(source_ref_json: Mapping[str, Any] | None) -> str | None:
    """Return a tombstone source identity hash from allowed source-ref fields only."""

    if not source_ref_json:
        return None
    return canonical_source_identity_hash(source_ref_json)


def active_tombstone_matches(
    tombstone: MemoryTombstone,
    *,
    content_hash: str | None,
    source_identity_hash: str | None,
    now: datetime | None = None,
) -> bool:
    """Match only exact canonical content identity or exact allowed source identity."""

    now = _aware(now)
    if tombstone.deleted_at is not None:
        return False
    if tombstone.expires_at is not None and tombstone.expires_at <= now:
        return False
    if content_hash is not None and tombstone.content_hash == content_hash:
        return True
    if source_identity_hash is not None and tombstone.source_identity_hash == source_identity_hash:
        return True
    return False


def check_tombstone_before_write(
    tombstone: MemoryTombstone | None,
    *,
    content_hash: str | None,
    source_identity_hash: str | None,
    now: datetime | None = None,
) -> MemoryTombstone | None:
    """Return the matching tombstone that should block a candidate write."""

    if tombstone is None:
        return None
    if active_tombstone_matches(
        tombstone,
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
        now=now,
    ):
        return tombstone
    return None


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
