from __future__ import annotations

import inspect
import re

import pytest

from src.memory.identity import (
    MemoryIdentityError,
    canonical_memory_candidate_hash,
    canonical_memory_content_hash,
    canonical_memory_identity_hash,
    canonical_source_identity_hash,
    normalize_memory_content,
)


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SOURCE_REF_KEYS = {
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
RAW_AUTHORITY_FIELDS = {
    "raw_payload",
    "raw_tool_output",
    "full_policy_text",
    "policy_evidence",
    "approval_authority_body",
    "action_authority_body",
    "replay_blob",
    "debug_blob",
}


def _source_ref(**overrides: str) -> dict[str, str]:
    source_ref = {
        "source_type": "conversation_message",
        "run_id": "run-1",
        "event_id": "event-1",
        "conversation_message_id": "msg-1",
        "tool_result_id": "tool-result-1",
        "agent_run_id": "agent-run-1",
        "business_object_type": "refund",
        "business_object_id": "RF-1001",
        "policy_version": "v3",
        "outcome_id": "outcome-1",
    }
    source_ref.update(overrides)
    return source_ref


def test_memory_content_hash_is_stable_across_whitespace() -> None:
    assert normalize_memory_content("  Refund  policy\npreference  ") == "refund policy preference"

    content_hash = canonical_memory_content_hash(
        memory_type="long_term_fact",
        content="Refund policy preference",
    )

    assert SHA256_RE.fullmatch(content_hash)
    assert content_hash == canonical_memory_content_hash(
        memory_type="long_term_fact",
        content="  Refund  policy\npreference  ",
    )
    assert content_hash != canonical_memory_content_hash(
        memory_type="case_memory",
        content="Refund policy preference",
    )


def test_memory_identity_hash_binds_scope_and_content() -> None:
    content_hash = canonical_memory_content_hash(
        memory_type="long_term_fact",
        content="Refund policy preference",
    )

    identity_hash = canonical_memory_identity_hash(
        tenant_id="tenant-1",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
    )

    assert SHA256_RE.fullmatch(identity_hash)
    assert identity_hash == canonical_memory_identity_hash(
        tenant_id="tenant-1",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
    )
    assert identity_hash != canonical_memory_identity_hash(
        tenant_id="tenant-2",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
    )


def test_memory_candidate_hash_binds_scope_content_and_source_identity() -> None:
    content_hash = canonical_memory_content_hash(
        memory_type="long_term_fact",
        content="Refund policy preference",
    )
    source_identity_hash = canonical_source_identity_hash(_source_ref())

    candidate_hash = canonical_memory_candidate_hash(
        tenant_id="tenant-1",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
    )

    assert SHA256_RE.fullmatch(candidate_hash)
    assert candidate_hash == canonical_memory_candidate_hash(
        tenant_id="tenant-1",
        memory_type="long_term_fact",
        scope_type="merchant",
        scope_id="merchant-1",
        content_hash=content_hash,
        source_identity_hash=source_identity_hash,
    )

    base_candidate = {
        "tenant_id": "tenant-1",
        "memory_type": "long_term_fact",
        "scope_type": "merchant",
        "scope_id": "merchant-1",
        "content_hash": content_hash,
        "source_identity_hash": source_identity_hash,
    }
    variations = [
        {"tenant_id": "tenant-2"},
        {"memory_type": "case_memory"},
        {"scope_type": "user"},
        {"scope_id": "merchant-2"},
        {"content_hash": canonical_memory_content_hash(memory_type="long_term_fact", content="Other")},
        {"source_identity_hash": canonical_source_identity_hash(_source_ref(event_id="event-2"))},
    ]

    for variation in variations:
        changed_candidate = base_candidate | variation
        assert candidate_hash != canonical_memory_candidate_hash(**changed_candidate)


def test_memory_candidate_hash_accepts_only_stable_envelope_fields() -> None:
    parameters = set(inspect.signature(canonical_memory_candidate_hash).parameters)

    assert parameters == {
        "tenant_id",
        "memory_type",
        "scope_type",
        "scope_id",
        "content_hash",
        "source_identity_hash",
    }
    assert parameters.isdisjoint(RAW_AUTHORITY_FIELDS)

    with pytest.raises(TypeError):
        canonical_memory_candidate_hash(
            tenant_id="tenant-1",
            memory_type="long_term_fact",
            scope_type="merchant",
            scope_id="merchant-1",
            content_hash="sha256:" + "a" * 64,
            source_identity_hash=None,
            raw_payload={"tool": "result"},
        )


def test_source_identity_hash_accepts_only_memory_source_ref_keys() -> None:
    source_identity_hash = canonical_source_identity_hash(_source_ref())

    assert SHA256_RE.fullmatch(source_identity_hash)
    assert source_identity_hash == canonical_source_identity_hash(dict(reversed(_source_ref().items())))
    assert source_identity_hash != canonical_source_identity_hash(_source_ref(event_id="event-2"))
    assert SOURCE_REF_KEYS == set(_source_ref())


def test_source_identity_rejects_unknown_keys() -> None:
    with pytest.raises(MemoryIdentityError, match="unknown"):
        canonical_source_identity_hash({"random_json_key": "x"})
