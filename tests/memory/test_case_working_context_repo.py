from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from pydantic import ValidationError

from src.memory.case_working_context_schemas import (
    CaseWorkingContextActionTakenV1,
    CaseWorkingContextClaimV1,
    CaseWorkingContextCommitmentV1,
    CaseWorkingContextContentV1,
    CaseWorkingContextVerifiedFactV1,
    CaseWorkingContextWriteCandidate,
)
from src.memory.schemas import MemorySourceRefV1


def _source_ref(**overrides: str) -> MemorySourceRefV1:
    payload = {
        "source_type": "deterministic_tool_result",
        "run_id": str(uuid.uuid4()),
        "business_object_type": "refund_case",
        "business_object_id": str(uuid.uuid4()),
    }
    payload.update(overrides)
    return MemorySourceRefV1.model_validate(payload)


def test_schema_claims_facts_actions_and_commitments_require_source_refs() -> None:
    source_ref = _source_ref()
    claim = CaseWorkingContextClaimV1(text="用户称商品破损", verified=False, source_ref=source_ref)
    fact = CaseWorkingContextVerifiedFactV1(
        text="退款单状态为 reviewing",
        source_ref=source_ref,
        observed_at=datetime.now(UTC),
    )
    action = CaseWorkingContextActionTakenV1(action="已查询退款单", source_ref=source_ref)
    commitment = CaseWorkingContextCommitmentV1(text="客服承诺 24 小时内回复", confirmed_by_staff=True, source_ref=source_ref)

    assert claim.source_ref == source_ref
    assert fact.source_ref == source_ref
    assert action.source_ref == source_ref
    assert commitment.confirmed_by_staff is True
    assert commitment.source_ref == source_ref

    with pytest.raises(ValidationError):
        CaseWorkingContextClaimV1.model_validate({"text": "missing source", "verified": False})
    with pytest.raises(ValidationError):
        CaseWorkingContextVerifiedFactV1.model_validate(
            {"text": "missing source", "observed_at": datetime.now(UTC)}
        )
    with pytest.raises(ValidationError):
        CaseWorkingContextActionTakenV1.model_validate({"action": "missing source"})
    with pytest.raises(ValidationError):
        CaseWorkingContextCommitmentV1.model_validate({"text": "missing confirmed flag", "source_ref": source_ref})


def test_schema_claims_and_verified_facts_are_distinct_types() -> None:
    source_ref = _source_ref()
    claim = CaseWorkingContextClaimV1(text="用户称商品破损", verified=False, source_ref=source_ref)
    fact = CaseWorkingContextVerifiedFactV1(
        text="系统确认物流已签收",
        source_ref=source_ref,
        observed_at=datetime.now(UTC),
    )

    with pytest.raises(ValidationError):
        CaseWorkingContextVerifiedFactV1.model_validate(claim.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        CaseWorkingContextClaimV1.model_validate(fact.model_dump(mode="json"))


def test_schema_content_forbids_extra_keys_and_defaults_lists() -> None:
    content = CaseWorkingContextContentV1()

    assert content.authority_class == "contextual_only"
    assert content.claims == []
    assert content.verified_facts == []
    assert content.missing_info == []
    assert content.evidence_refs == []
    assert content.actions_taken == []
    assert content.policy_refs == []
    assert content.agent_recommendations == []
    assert content.pending_tasks == []
    assert content.commitments == []
    assert content.next_action.recommended_step is None
    assert content.next_action.blocked_by == []

    with pytest.raises(ValidationError):
        CaseWorkingContextContentV1.model_validate({"unexpected": "forbidden"})


def test_schema_write_candidate_requires_scope_source_ref_and_content() -> None:
    source_ref = _source_ref()
    candidate = CaseWorkingContextWriteCandidate(
        tenant_id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        updated_by_run_id=None,
        source_ref=source_ref,
        expected_version=None,
        content=CaseWorkingContextContentV1(customer_request="用户询问退款进度"),
    )

    assert candidate.source_ref == source_ref
    assert candidate.pii_classification == "none"
    assert candidate.content.customer_request == "用户询问退款进度"

    with pytest.raises(ValidationError):
        CaseWorkingContextWriteCandidate.model_validate(
            {
                "tenant_id": str(uuid.uuid4()),
                "case_id": str(uuid.uuid4()),
                "updated_by_run_id": None,
                "expected_version": None,
                "content": {},
            }
        )
