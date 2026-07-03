from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.memory.context_refs import (
    CaseWorkingContextLifecycleStatusV1,
    CaseWorkingContextRef,
    MemoryContextBundle,
    MemoryWriteDecisionV2,
    ReviewedMemoryContextBundle,
    ReviewedMemoryContextRetrieveStatusV1,
    ReviewedMemoryRef,
    SessionContextLoadStatusV1,
    SessionContextRef,
)
from src.memory.schemas import SessionContextMemory, SessionMemoryView


_HASH = "sha256:" + ("a" * 64)


def _session_context_ref_payload() -> dict:
    return {
        "schema_version": "session_context_ref.v1",
        "authority_class": "contextual_only",
        "tenant_id": "tenant-memory-boundary",
        "user_id": "user-memory-boundary",
        "thread_id": "thread-memory-boundary",
        "run_id": "run-memory-boundary",
        "source": "session_context_load",
        "ref_id": "session-context-ref-1",
    }


def _reviewed_memory_ref_payload(memory_type: str = "long_term") -> dict:
    return {
        "schema_version": "reviewed_memory_ref.v1",
        "authority_class": "contextual_only",
        "tenant_id": "tenant-memory-boundary",
        "memory_type": memory_type,
        "scope_type": "merchant",
        "scope_id": "merchant-1",
        "memory_id": f"{memory_type}-memory-1",
        "review_status": "approved",
        "source_identity_hash": _HASH,
        "prompt_safe": True,
    }


def _case_working_context_ref_payload() -> dict:
    return {
        "schema_version": "case_working_context_ref.v1",
        "authority_class": "contextual_only",
        "tenant_id": "tenant-memory-boundary",
        "case_id": "case-memory-boundary",
        "memory_id": "case-working-context-1",
        "version": 3,
        "source_ref": {"source_type": "run_auto", "agent_run_id": "run-memory-boundary"},
        "updated_by_run_id": "run-memory-boundary",
        "prompt_safe": True,
    }


def _case_working_context_status_payload() -> dict:
    return {
        "schema_version": "case_working_context_lifecycle_status.v1",
        "authority_class": "contextual_only",
        "status": "loaded",
        "resolve_status": "resolved",
        "link_status": "linked",
        "read_status": "read_active",
        "write_status": "skipped",
        "reason_code": "active_context_loaded",
        "filter_reasons": ["trusted_case_ref"],
        "tenant_id": "tenant-memory-boundary",
        "case_id": "case-memory-boundary",
        "run_id": "run-memory-boundary",
        "raw_case_ref": "RF-1",
    }


def _session_context() -> SessionContextMemory:
    return SessionContextMemory(
        tenant_id="tenant-memory-boundary",
        user_id="user-memory-boundary",
        thread_id="thread-memory-boundary",
        run_id="run-memory-boundary",
        slot_continuity=SessionMemoryView(
            source="postgres_session_memory",
            continuity_claimed=True,
            active_slots={"refund_case_id": "RF-1"},
        ),
    )


def test_session_context_ref_is_contextual_only_and_thread_scoped() -> None:
    ref = SessionContextRef.model_validate(_session_context_ref_payload())

    assert ref.schema_version == "session_context_ref.v1"
    assert ref.authority_class == "contextual_only"
    assert ref.tenant_id == "tenant-memory-boundary"
    assert ref.user_id == "user-memory-boundary"
    assert ref.thread_id == "thread-memory-boundary"
    assert ref.run_id == "run-memory-boundary"
    assert ref.source == "session_context_load"
    assert ref.ref_id == "session-context-ref-1"


@pytest.mark.parametrize("memory_type", ["long_term", "case"])
def test_reviewed_memory_ref_is_contextual_only_and_review_scoped(memory_type: str) -> None:
    ref = ReviewedMemoryRef.model_validate(_reviewed_memory_ref_payload(memory_type))

    assert ref.schema_version == "reviewed_memory_ref.v1"
    assert ref.authority_class == "contextual_only"
    assert ref.tenant_id == "tenant-memory-boundary"
    assert ref.memory_type == memory_type
    assert ref.scope_type == "merchant"
    assert ref.scope_id == "merchant-1"
    assert ref.memory_id == f"{memory_type}-memory-1"
    assert ref.review_status == "approved"
    assert ref.source_identity_hash == _HASH
    assert ref.prompt_safe is True


def test_case_working_context_ref_is_contextual_only_and_prompt_safe() -> None:
    ref = CaseWorkingContextRef.model_validate(_case_working_context_ref_payload())

    assert ref.schema_version == "case_working_context_ref.v1"
    assert ref.authority_class == "contextual_only"
    assert ref.tenant_id == "tenant-memory-boundary"
    assert ref.case_id == "case-memory-boundary"
    assert ref.memory_id == "case-working-context-1"
    assert ref.version == 3
    assert ref.source_ref == {"source_type": "run_auto", "agent_run_id": "run-memory-boundary"}
    assert ref.updated_by_run_id == "run-memory-boundary"
    assert ref.prompt_safe is True


def test_session_context_load_status_records_contextual_load_metadata() -> None:
    status = SessionContextLoadStatusV1.model_validate(
        {
            "schema_version": "session_context_load_status.v1",
            "status": "loaded",
            "source": "postgres_session_memory",
            "authority_class": "contextual_only",
            "tenant_id": "tenant-memory-boundary",
            "user_id": "user-memory-boundary",
            "thread_id": "thread-memory-boundary",
            "run_id": "run-memory-boundary",
            "loaded_refs": [_session_context_ref_payload()],
            "fallback_reason": None,
            "slot_count": 1,
            "recent_message_count": 2,
            "tool_summary_count": 1,
            "filter_reasons": ["cross_merchant_session_context_filtered"],
        }
    )

    assert status.schema_version == "session_context_load_status.v1"
    assert status.status == "loaded"
    assert status.source == "postgres_session_memory"
    assert status.authority_class == "contextual_only"
    assert status.tenant_id == "tenant-memory-boundary"
    assert status.user_id == "user-memory-boundary"
    assert status.thread_id == "thread-memory-boundary"
    assert status.run_id == "run-memory-boundary"
    assert status.loaded_refs[0].ref_id == "session-context-ref-1"
    assert status.fallback_reason is None
    assert status.slot_count == 1
    assert status.recent_message_count == 2
    assert status.tool_summary_count == 1
    assert status.filter_reasons == ["cross_merchant_session_context_filtered"]


def test_reviewed_memory_context_retrieve_status_records_scope_filters_and_refs() -> None:
    status = ReviewedMemoryContextRetrieveStatusV1.model_validate(
        {
            "schema_version": "reviewed_memory_context_retrieve_status.v1",
            "status": "loaded",
            "authority_class": "contextual_only",
            "trusted_scope_inputs": {"tenant_id": "tenant-memory-boundary", "merchant_scope": ["merchant-1"]},
            "effective_scopes": [{"scope_type": "merchant", "scope_id": "merchant-1"}],
            "filter_reasons": ["reviewed_prompt_safe"],
            "retrieved_refs": [_reviewed_memory_ref_payload()],
            "fallback_reason": None,
        }
    )

    assert status.schema_version == "reviewed_memory_context_retrieve_status.v1"
    assert status.status == "loaded"
    assert status.authority_class == "contextual_only"
    assert status.trusted_scope_inputs["merchant_scope"] == ["merchant-1"]
    assert status.effective_scopes == [{"scope_type": "merchant", "scope_id": "merchant-1"}]
    assert status.filter_reasons == ["reviewed_prompt_safe"]
    assert status.retrieved_refs[0].memory_id == "long_term-memory-1"
    assert status.fallback_reason is None


def test_case_working_context_lifecycle_status_records_explicit_lifecycle_fields() -> None:
    status = CaseWorkingContextLifecycleStatusV1.model_validate(_case_working_context_status_payload())

    assert status.schema_version == "case_working_context_lifecycle_status.v1"
    assert status.authority_class == "contextual_only"
    assert status.status == "loaded"
    assert status.resolve_status == "resolved"
    assert status.link_status == "linked"
    assert status.read_status == "read_active"
    assert status.write_status == "skipped"
    assert status.reason_code == "active_context_loaded"
    assert status.filter_reasons == ["trusted_case_ref"]
    assert status.tenant_id == "tenant-memory-boundary"
    assert status.case_id == "case-memory-boundary"
    assert status.run_id == "run-memory-boundary"
    assert status.raw_case_ref == "RF-1"


def test_reviewed_memory_context_bundle_keeps_long_term_and_case_refs_separate() -> None:
    bundle = ReviewedMemoryContextBundle.model_validate(
        {
            "schema_version": "reviewed_memory_context_bundle.v1",
            "authority_class": "contextual_only",
            "tenant_id": "tenant-memory-boundary",
            "long_term_items": [{"content": "merchant preference", "ref": _reviewed_memory_ref_payload("long_term")}],
            "case_items": [{"content": "case precedent", "ref": _reviewed_memory_ref_payload("case")}],
            "retrieve_status": {
                "schema_version": "reviewed_memory_context_retrieve_status.v1",
                "status": "loaded",
                "authority_class": "contextual_only",
                "trusted_scope_inputs": {"tenant_id": "tenant-memory-boundary"},
                "effective_scopes": [{"scope_type": "merchant", "scope_id": "merchant-1"}],
                "filter_reasons": [],
                "retrieved_refs": [_reviewed_memory_ref_payload("long_term"), _reviewed_memory_ref_payload("case")],
                "fallback_reason": None,
            },
        }
    )

    assert bundle.schema_version == "reviewed_memory_context_bundle.v1"
    assert bundle.authority_class == "contextual_only"
    assert bundle.long_term_items[0]["ref"].memory_type == "long_term"
    assert bundle.case_items[0]["ref"].memory_type == "case"
    assert bundle.retrieve_status.schema_version == "reviewed_memory_context_retrieve_status.v1"


def test_memory_context_bundle_accepts_optional_case_working_context_without_merging_reviewed_items() -> None:
    bundle = MemoryContextBundle.model_validate(
        {
            "schema_version": "memory_context_bundle.v1",
            "authority_class": "contextual_only",
            "session_context": _session_context().model_dump(mode="json"),
            "long_term_items": [{"content": "merchant preference", "ref": _reviewed_memory_ref_payload("long_term")}],
            "case_items": [{"content": "reviewed case precedent", "ref": _reviewed_memory_ref_payload("case")}],
            "case_working_context": {
                "content": {"customer_request": "用户询问退款进度"},
                "ref": _case_working_context_ref_payload(),
            },
            "case_working_context_status_ref": _case_working_context_status_payload(),
        }
    )

    assert bundle.authority_class == "contextual_only"
    assert bundle.long_term_items[0]["ref"]["memory_type"] == "long_term"
    assert bundle.case_items[0]["ref"]["memory_type"] == "case"
    assert bundle.case_working_context == {
        "content": {"customer_request": "用户询问退款进度"},
        "ref": _case_working_context_ref_payload(),
    }
    assert bundle.case_working_context_status_ref is not None
    assert bundle.case_working_context_status_ref.status == "loaded"


def test_memory_write_decision_v2_records_contextual_write_boundary() -> None:
    decision = MemoryWriteDecisionV2.model_validate(
        {
            "schema_version": "memory_write_decision.v2",
            "status": "skipped",
            "decision": "skip",
            "authority_class": "contextual_only",
            "memory_type": "long_term",
            "memory_id": None,
            "scope": {"scope_type": "merchant", "scope_id": "merchant-1"},
            "candidate_hash": _HASH,
            "source_identity_hash": _HASH,
            "pii_classification": "none",
            "review_status": "needs_review",
            "reason_code": "temporary_chat",
            "fallback_reason": None,
        }
    )

    assert decision.schema_version == "memory_write_decision.v2"
    assert decision.status == "skipped"
    assert decision.decision == "skip"
    assert decision.authority_class == "contextual_only"
    assert decision.memory_type == "long_term"
    assert decision.memory_id is None
    assert decision.scope == {"scope_type": "merchant", "scope_id": "merchant-1"}
    assert decision.candidate_hash == _HASH
    assert decision.source_identity_hash == _HASH
    assert decision.pii_classification == "none"
    assert decision.review_status == "needs_review"
    assert decision.reason_code == "temporary_chat"
    assert decision.policy_version == "memory_write_policy.v1"
    assert decision.blocked_by == []
    assert decision.fallback_reason is None


def test_memory_context_ref_module_does_not_import_authority_dtos() -> None:
    source = Path("src/memory/context_refs.py").read_text()

    assert "EvidenceRefV1" not in source
    assert "BusinessFactRefV1" not in source
    assert "ApprovalRequestCreateCommand" not in source
    assert "ReplayEventV3" not in source
    assert "ActionDraft" not in source
    assert "ActionSafetySnapshot" not in source


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (SessionContextRef, _session_context_ref_payload()),
        (ReviewedMemoryRef, _reviewed_memory_ref_payload()),
        (
            CaseWorkingContextRef,
            _case_working_context_ref_payload(),
        ),
        (
            CaseWorkingContextLifecycleStatusV1,
            _case_working_context_status_payload(),
        ),
        (
            SessionContextLoadStatusV1,
            {
                "schema_version": "session_context_load_status.v1",
                "status": "loaded",
                "source": "postgres_session_memory",
                "authority_class": "contextual_only",
                "tenant_id": "tenant-memory-boundary",
                "user_id": "user-memory-boundary",
                "thread_id": "thread-memory-boundary",
                "run_id": "run-memory-boundary",
                "loaded_refs": [_session_context_ref_payload()],
                "fallback_reason": None,
                "slot_count": 1,
                "recent_message_count": 1,
                "tool_summary_count": 1,
            },
        ),
        (
            ReviewedMemoryContextRetrieveStatusV1,
            {
                "schema_version": "reviewed_memory_context_retrieve_status.v1",
                "status": "loaded",
                "authority_class": "contextual_only",
                "trusted_scope_inputs": {"tenant_id": "tenant-memory-boundary"},
                "effective_scopes": [{"scope_type": "merchant", "scope_id": "merchant-1"}],
                "filter_reasons": [],
                "retrieved_refs": [_reviewed_memory_ref_payload()],
                "fallback_reason": None,
            },
        ),
        (
            MemoryWriteDecisionV2,
            {
                "schema_version": "memory_write_decision.v2",
                "status": "skipped",
                "decision": "skip",
                "authority_class": "contextual_only",
                "memory_type": "long_term",
                "memory_id": None,
                "scope": {"scope_type": "merchant", "scope_id": "merchant-1"},
                "candidate_hash": _HASH,
                "source_identity_hash": _HASH,
                "pii_classification": "none",
                "review_status": "needs_review",
                "reason_code": "temporary_chat",
                "fallback_reason": None,
            },
        ),
    ],
)
def test_contextual_memory_dtos_reject_extra_fields(model, payload: dict) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload | {"EvidenceRefV1": {"evidence_id": "forged"}})
