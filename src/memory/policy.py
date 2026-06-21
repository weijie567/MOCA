"""Shared safety policy for prompt-facing memory surfaces."""

from __future__ import annotations


PROMPT_SAFE_PII_CLASSIFICATIONS = frozenset({"none", "low"})
BLOCKED_MEMORY_WRITE_PII_CLASSIFICATIONS = frozenset({"sensitive", "prohibited"})


def is_prompt_safe_pii_classification(value: str | None) -> bool:
    return value in PROMPT_SAFE_PII_CLASSIFICATIONS


def is_blocked_memory_write_pii_classification(value: str | None) -> bool:
    return value in BLOCKED_MEMORY_WRITE_PII_CLASSIFICATIONS
