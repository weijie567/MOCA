from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from src.memory.case_memory import CaseMemoryService
from src.memory.policy import (
    AUTO_APPROVED_CASE_SOURCE_TYPES,
    DISALLOWED_LONG_TERM_SOURCE_TYPES,
    MEMORY_POLICY_VERSION,
    PUBLISHED_LONG_TERM_SOURCE_TYPES,
    REVIEW_REQUIRED_CASE_SOURCE_TYPES,
    case_memory_policy_decision,
    case_memory_review_status_for_source,
    long_term_memory_policy_decision,
    long_term_review_status_for_source,
    session_memory_policy_decision,
)
from src.memory.schemas import CaseMemoryWriteCandidate, LongTermMemoryWriteCandidate


def test_long_term_only_explicit_preference_sources_auto_publish() -> None:
    assert PUBLISHED_LONG_TERM_SOURCE_TYPES == frozenset(
        {"explicit_user_preference", "explicit_admin_preference", "human_reviewed"}
    )

    for source_type in PUBLISHED_LONG_TERM_SOURCE_TYPES:
        decision = long_term_memory_policy_decision(source_type)
        assert decision.decision == "write"
        assert decision.review_status == "auto_approved"
        assert decision.reason_code == "auto_approved_source"

    semantic_decision = long_term_memory_policy_decision("semantic_episode_candidate")
    assert semantic_decision.decision == "needs_review"
    assert semantic_decision.review_status == "needs_review"
    assert semantic_decision.blocked_by == ["source_requires_review"]

    for source_type in DISALLOWED_LONG_TERM_SOURCE_TYPES:
        decision = long_term_memory_policy_decision(source_type)
        assert decision.decision == "skip"
        assert decision.review_status is None
        assert decision.reason_code == "source_type_not_allowed"
        assert decision.blocked_by == ["source_type_not_allowed"]


def test_memory_policy_decision_is_auditable_for_long_term_sources() -> None:
    decision = long_term_memory_policy_decision("semantic_episode_candidate")

    assert decision.decision == "needs_review"
    assert decision.review_status == "needs_review"
    assert decision.reason_code == "requires_review"
    assert decision.policy_version == MEMORY_POLICY_VERSION
    assert decision.blocked_by == ["source_requires_review"]
    assert decision.authority_class == "contextual_only"


def test_memory_policy_decision_blocks_sensitive_pii_before_write() -> None:
    decision = session_memory_policy_decision("sensitive")

    assert decision.memory_type == "session"
    assert decision.decision == "skip"
    assert decision.review_status is None
    assert decision.reason_code == "pii_blocked"
    assert decision.blocked_by == ["pii_classification"]


def test_long_term_non_semantic_automatic_candidates_are_not_allowed() -> None:
    assert long_term_memory_policy_decision("llm_candidate").decision == "skip"
    assert long_term_memory_policy_decision("summary_candidate").reason_code == "source_type_not_allowed"
    assert long_term_memory_policy_decision("deterministic_tool_result").decision == "skip"
    assert long_term_review_status_for_source("semantic_episode_candidate") == "needs_review"


def test_long_term_write_candidate_defaults_to_preference_kind() -> None:
    candidate = LongTermMemoryWriteCandidate(
        tenant_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        scope_type="merchant",
        scope_id="merchant-1",
        content="Merchant prefers concise refund summaries.",
        source_type="explicit_user_preference",
    )

    assert candidate.memory_kind == "preference"


def test_case_memory_only_explicit_review_sources_auto_publish() -> None:
    assert case_memory_review_status_for_source("human_reviewed") == "auto_approved"
    assert case_memory_review_status_for_source("explicit_admin_preference") == "auto_approved"
    assert case_memory_review_status_for_source("deterministic_tool_result") == "needs_review"
    assert case_memory_review_status_for_source("confirmed_business_outcome") == "needs_review"
    assert case_memory_review_status_for_source("approved_approval_state") == "needs_review"
    assert case_memory_review_status_for_source("llm_candidate") == "needs_review"
    assert case_memory_review_status_for_source("closed_case_cwc_candidate") == "needs_review"
    assert case_memory_policy_decision("human_reviewed").decision == "write"
    assert case_memory_policy_decision("human_reviewed").review_status == "auto_approved"
    assert case_memory_policy_decision("deterministic_tool_result").decision == "needs_review"
    closed_case_decision = case_memory_policy_decision("closed_case_cwc_candidate")
    assert closed_case_decision.decision == "needs_review"
    assert closed_case_decision.review_status == "needs_review"
    assert closed_case_decision.blocked_by == ["source_requires_review"]
    assert "closed_case_cwc_candidate" in REVIEW_REQUIRED_CASE_SOURCE_TYPES
    assert "closed_case_cwc_candidate" not in AUTO_APPROVED_CASE_SOURCE_TYPES


def test_closed_case_cwc_candidate_validates_as_case_memory_write_candidate() -> None:
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()

    candidate = CaseMemoryWriteCandidate(
        tenant_id=tenant_id,
        run_id=run_id,
        scope_type="case",
        scope_id="case-closed",
        case_type="refund_dispute",
        summary="Closed case CWC projection enters review.",
        excerpt="Closed case generated a candidate precedent.",
        source_type="closed_case_cwc_candidate",
        source_ref={
            "source_type": "closed_case_cwc_candidate",
            "run_id": str(run_id),
            "event_id": "close-event-1",
            "business_object_type": "refund_case",
            "business_object_id": "case-closed",
            "outcome_id": "cwc-row-1:v3",
        },
    )

    assert candidate.source_type == "closed_case_cwc_candidate"


class _FakeCaseMemoryRepository:
    def __init__(self) -> None:
        self.insert_kwargs = None
        self.event_kwargs = None

    async def check_tombstone_before_write(self, **kwargs):
        return None

    async def get_active_duplicate(self, **kwargs):
        return None

    async def get_exact_identity_claim(self, **kwargs):
        return None

    async def insert_case_memory(self, candidate, **kwargs):
        self.insert_kwargs = kwargs
        return SimpleNamespace(id=uuid.uuid4(), review_status=kwargs["review_status"])

    async def create_identity_claim(self, *, memory):
        return SimpleNamespace(owner_case_memory_id=memory.id)

    async def emit_write_event(self, **kwargs):
        self.event_kwargs = kwargs
        return SimpleNamespace(id=uuid.uuid4())


@pytest.mark.asyncio
@pytest.mark.parametrize("source_type", ["deterministic_tool_result", "closed_case_cwc_candidate"])
async def test_case_memory_service_requires_review_for_candidates_without_database(source_type: str) -> None:
    repository = _FakeCaseMemoryRepository()
    service = CaseMemoryService(repository)  # type: ignore[arg-type]
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    candidate = CaseMemoryWriteCandidate(
        tenant_id=tenant_id,
        run_id=run_id,
        scope_type="case",
        scope_id="case-1",
        case_type="refund_dispute",
        summary="Deterministic case extraction still needs review.",
        excerpt="Tool result summarized a case precedent.",
        source_type=source_type,
        source_ref={
            "source_type": source_type,
            "run_id": str(run_id),
            "event_id": "close-event-1" if source_type == "closed_case_cwc_candidate" else None,
            "business_object_type": "refund_case",
            "business_object_id": "case-1",
            "outcome_id": "cwc-row-1:v3" if source_type == "closed_case_cwc_candidate" else None,
        },
    )

    result = await service.submit_case_memory_candidate(candidate)

    assert result.status == "needs_review"
    assert result.review_status == "needs_review"
    assert result.decision == "needs_review"
    assert result.reason_code == "requires_review"
    assert repository.insert_kwargs is not None
    assert repository.insert_kwargs["review_status"] == "needs_review"
    assert repository.event_kwargs is not None
    assert repository.event_kwargs["decision"] == "needs_review"
    assert repository.event_kwargs["policy_version"] == "memory_write_policy.v1"
    assert repository.event_kwargs["blocked_by"] == ["source_requires_review"]
    assert repository.event_kwargs["authority_class"] == "contextual_only"


@pytest.mark.asyncio
@pytest.mark.parametrize("source_type", ["human_reviewed", "explicit_admin_preference"])
async def test_case_memory_service_auto_publishes_reviewed_admin_sources_without_database(source_type: str) -> None:
    repository = _FakeCaseMemoryRepository()
    service = CaseMemoryService(repository)  # type: ignore[arg-type]
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    candidate = CaseMemoryWriteCandidate(
        tenant_id=tenant_id,
        run_id=run_id,
        scope_type="case",
        scope_id="case-reviewed",
        case_type="refund_dispute",
        summary="Reviewed/admin case extraction can publish.",
        excerpt="Human reviewed this precedent.",
        source_type=source_type,
        source_ref={
            "source_type": source_type,
            "run_id": str(run_id),
            "business_object_type": "refund_case",
            "business_object_id": "case-reviewed",
        },
    )

    result = await service.submit_case_memory_candidate(candidate)

    assert result.status == "written"
    assert result.review_status == "auto_approved"
    assert result.decision == "write"
    assert result.reason_code == "auto_approved_source"
    assert repository.insert_kwargs is not None
    assert repository.insert_kwargs["review_status"] == "auto_approved"
