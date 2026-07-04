from __future__ import annotations

from uuid import uuid4

import pytest

from src.memory.schemas import (
    CaseMemoryWriteCandidate,
    CaseMemoryWriteResult,
    LongTermMemoryWriteCandidate,
    LongTermMemoryWriteResult,
    SessionMemoryWriteCandidate,
    SessionMemoryWriteResult,
)
from src.memory.write_service import MemoryWriteService

_SHA = "sha256:" + "a" * 64


def _state(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "thread_id": "thread-memory-write-service",
        "current_run_id": str(uuid4()),
        "final_response": "done",
        "primary_intent": "refund_troubleshooting",
        "extracted_slots": {"order_id": "ORD-1001", "refund_case_id": None},
        "session_memory": {"version": 7},
        "clarification_request": {"questions": ["请补充退款通道状态。"]},
        "last_business_context_refs": {"business_fact_refs": [{"resource_type": "order", "resource_id": "ORD-1001"}]},
    }
    values.update(updates)
    return values


def _trusted_context(*merchant_ids: str) -> dict[str, object]:
    return {"merchant_scope": {"merchant_ids": list(merchant_ids)}}


class FakeSessionMemoryService:
    def __init__(self) -> None:
        self.candidates = []

    async def write_session_memory(self, candidate):
        self.candidates.append(candidate)
        return SessionMemoryWriteResult(
            status="written",
            version=8,
            decision="write",
            reason_code="eligible",
            pii_classification=candidate.pii_classification,
        )


class FakeLongTermMemoryService:
    def __init__(self) -> None:
        self.candidates = []

    async def write_memory(self, candidate):
        self.candidates.append(candidate)
        return LongTermMemoryWriteResult(
            status="needs_review",
            memory_id=None,
            review_status="needs_review",
            decision="needs_review",
            reason_code="requires_review",
            pii_classification=candidate.pii_classification,
            candidate_hash=_SHA,
            content_hash=_SHA,
            source_identity_hash=None,
        )


class FakeCaseMemoryService:
    def __init__(self) -> None:
        self.candidates = []

    async def submit_case_memory_candidate(self, candidate):
        self.candidates.append(candidate)
        return CaseMemoryWriteResult(
            status="written",
            memory_id=None,
            review_status="auto_approved",
            decision="write",
            reason_code="auto_approved_source",
            pii_classification=candidate.pii_classification,
            candidate_hash=_SHA,
            content_hash=_SHA,
            source_identity_hash=None,
        )


def test_memory_write_service_proposes_session_candidate() -> None:
    service = MemoryWriteService(FakeSessionMemoryService())

    candidate = service.propose_candidates(_state())[0]

    assert set(candidate.explicit_slots) == {"order_id"}
    assert candidate.explicit_slots["order_id"].value == "ORD-1001"
    assert "refund_troubleshooting" in candidate.explicit_slots["order_id"].compatible_intents
    assert "action_request" in candidate.explicit_slots["order_id"].compatible_intents
    assert candidate.unresolved_questions == ["请补充退款通道状态。"]
    assert candidate.expected_version == 7
    assert candidate.decision == "write"


def test_memory_write_service_defaults_to_session_memory_write_candidate_only() -> None:
    service = MemoryWriteService(FakeSessionMemoryService())

    candidates = service.propose_candidates(_state())

    assert len(candidates) == 1
    assert isinstance(candidates[0], SessionMemoryWriteCandidate)
    assert not any(isinstance(candidate, LongTermMemoryWriteCandidate) for candidate in candidates)
    assert not any(isinstance(candidate, CaseMemoryWriteCandidate) for candidate in candidates)


def test_memory_write_service_does_not_infer_ordinary_chat_as_long_term_preference() -> None:
    service = MemoryWriteService(FakeSessionMemoryService())

    candidates = service.propose_candidates(
        _state(user_query="Merchant prefers concise updates."),
        trusted_context=_trusted_context("merchant-1"),
    )

    assert len(candidates) == 1
    assert isinstance(candidates[0], SessionMemoryWriteCandidate)
    assert not any(isinstance(candidate, LongTermMemoryWriteCandidate) for candidate in candidates)


def test_memory_write_service_does_not_semantically_infer_preference_like_chat() -> None:
    service = MemoryWriteService(FakeSessionMemoryService())

    candidates = service.propose_candidates(
        _state(user_query="我们一般喜欢简短回复退款问题。"),
        trusted_context=_trusted_context("merchant-1"),
    )

    assert len(candidates) == 1
    assert isinstance(candidates[0], SessionMemoryWriteCandidate)
    assert not any(isinstance(candidate, LongTermMemoryWriteCandidate) for candidate in candidates)


@pytest.mark.parametrize(
    "query",
    [
        "Remember this preference: merchant prefers concise refund updates.",
        "记住这个偏好：低金额退款场景优先使用安抚性解释。",
        "记住这个偏好：商家偏好简短退款说明。",
        "以后按这个：退款回复先给证据再给结论。",
        "保存这个偏好：低金额售后优先使用安抚话术。",
    ],
)
def test_memory_write_service_adds_explicit_user_preference_candidate_for_deterministic_phrase(query: str) -> None:
    service = MemoryWriteService(FakeSessionMemoryService())

    candidates = service.propose_candidates(
        _state(user_query=query),
        trusted_context=_trusted_context("merchant-1"),
    )
    long_term_candidates = [candidate for candidate in candidates if isinstance(candidate, LongTermMemoryWriteCandidate)]

    assert len(long_term_candidates) == 1
    candidate = long_term_candidates[0]
    assert candidate.source_type == "explicit_user_preference"
    assert candidate.memory_kind == "preference"
    assert candidate.scope_type == "merchant"
    assert candidate.scope_id == "merchant-1"
    assert candidate.source_ref is not None
    assert candidate.source_ref.business_object_type == "merchant"
    assert candidate.source_ref.business_object_id == "merchant-1"


def test_memory_write_service_rejects_hard_rule_text_as_preference() -> None:
    service = MemoryWriteService(FakeSessionMemoryService())

    candidates = service.propose_candidates(
        _state(user_query="记住这个偏好：低于10元必须退款。"),
        trusted_context=_trusted_context("merchant-1"),
    )

    assert len(candidates) == 1
    assert isinstance(candidates[0], SessionMemoryWriteCandidate)
    assert not any(isinstance(candidate, LongTermMemoryWriteCandidate) for candidate in candidates)


def test_memory_write_service_explicit_chat_preference_requires_single_trusted_merchant_scope() -> None:
    service = MemoryWriteService(FakeSessionMemoryService())

    candidates = service.propose_candidates(
        _state(user_query="保存这个偏好：低金额售后优先使用安抚话术。"),
        trusted_context=_trusted_context("merchant-1", "merchant-2"),
    )

    assert len(candidates) == 1
    assert isinstance(candidates[0], SessionMemoryWriteCandidate)


def test_memory_write_service_uses_current_merchant_slot_when_trusted_scope_allows() -> None:
    service = MemoryWriteService(FakeSessionMemoryService())

    candidates = service.propose_candidates(
        _state(
            user_query="保存这个偏好：低金额售后优先使用安抚话术。",
            active_slots={"merchant_id": "merchant-2"},
        ),
        trusted_context=_trusted_context("merchant-1", "merchant-2"),
    )
    long_term_candidates = [candidate for candidate in candidates if isinstance(candidate, LongTermMemoryWriteCandidate)]

    assert len(long_term_candidates) == 1
    assert long_term_candidates[0].scope_type == "merchant"
    assert long_term_candidates[0].scope_id == "merchant-2"


def test_memory_write_service_rejects_tenant_scope_explicit_user_preference_from_state() -> None:
    service = MemoryWriteService(FakeSessionMemoryService())
    tenant_id = uuid4()
    run_id = uuid4()

    candidates = service.propose_candidates(
        _state(
            tenant_id=str(tenant_id),
            current_run_id=str(run_id),
            memory_write_candidates=[
                {
                    "memory_type": "long_term",
                    "tenant_id": tenant_id,
                    "run_id": run_id,
                    "scope_type": "tenant",
                    "scope_id": str(tenant_id),
                    "memory_kind": "preference",
                    "content": "Tenant-wide preference must not come from chat state.",
                    "source_type": "explicit_user_preference",
                }
            ],
        )
    )

    assert len(candidates) == 1
    assert isinstance(candidates[0], SessionMemoryWriteCandidate)


@pytest.mark.asyncio
async def test_memory_write_service_apply_policy_and_write_uses_session_service() -> None:
    session_service = FakeSessionMemoryService()
    service = MemoryWriteService(session_service)
    candidates = service.propose_candidates(_state())

    result = await service.apply_policy_and_write(candidates)

    assert result.status == "written"
    assert len(session_service.candidates) == 1
    assert session_service.candidates[0] == candidates[0]


@pytest.mark.asyncio
async def test_memory_write_service_blocks_sensitive_pii_before_repository_write() -> None:
    session_service = FakeSessionMemoryService()
    service = MemoryWriteService(session_service)
    candidates = service.propose_candidates(_state(extracted_slots={"order_id": "手机号 13800138000"}))

    result = await service.apply_policy_and_write(candidates)

    assert result.status == "skipped"
    assert result.reason_code == "pii_blocked"
    assert session_service.candidates == []


@pytest.mark.asyncio
async def test_memory_write_service_routes_long_term_candidate_through_facade() -> None:
    long_term_service = FakeLongTermMemoryService()
    service = MemoryWriteService(FakeSessionMemoryService(), long_term_memory_service=long_term_service)
    candidate = LongTermMemoryWriteCandidate(
        tenant_id=uuid4(),
        run_id=uuid4(),
        scope_type="merchant",
        scope_id="merchant-1",
        memory_kind="preference",
        content="Merchant prefers concise refund updates.",
        source_type="semantic_episode_candidate",
    )

    policy_decision = service.evaluate_policy(candidate)
    result = await service.apply_policy_and_write([candidate])

    assert policy_decision.decision == "needs_review"
    assert result.status == "needs_review"
    assert long_term_service.candidates == [candidate]


@pytest.mark.asyncio
async def test_memory_write_service_routes_case_candidate_through_facade() -> None:
    case_service = FakeCaseMemoryService()
    service = MemoryWriteService(FakeSessionMemoryService(), case_memory_service=case_service)
    candidate = CaseMemoryWriteCandidate(
        tenant_id=uuid4(),
        run_id=uuid4(),
        scope_type="case",
        scope_id="case-1",
        case_type="refund_dispute",
        summary="Reviewed precedent summary.",
        excerpt="Reviewed case excerpt.",
        source_type="human_reviewed",
    )

    policy_decision = service.evaluate_policy(candidate)
    result = await service.apply_policy_and_write([candidate])

    assert policy_decision.decision == "write"
    assert result.status == "written"
    assert case_service.candidates == [candidate]


@pytest.mark.asyncio
async def test_memory_write_service_proposes_explicit_long_term_and_case_candidates_from_state() -> None:
    session_service = FakeSessionMemoryService()
    long_term_service = FakeLongTermMemoryService()
    case_service = FakeCaseMemoryService()
    tenant_id = uuid4()
    run_id = uuid4()
    service = MemoryWriteService(
        session_service,
        long_term_memory_service=long_term_service,
        case_memory_service=case_service,
    )

    candidates = service.propose_candidates(
        _state(
            tenant_id=str(tenant_id),
            current_run_id=str(run_id),
            memory_write_candidates=[
                {
                    "memory_type": "long_term",
                    "tenant_id": tenant_id,
                    "run_id": run_id,
                    "scope_type": "merchant",
                    "scope_id": "merchant-1",
                    "memory_kind": "preference",
                    "content": "Merchant prefers concise refund updates.",
                    "source_type": "semantic_episode_candidate",
                },
                {
                    "memory_type": "case",
                    "tenant_id": tenant_id,
                    "run_id": run_id,
                    "scope_type": "case",
                    "scope_id": "case-1",
                    "case_type": "refund_dispute",
                    "summary": "Reviewed precedent summary.",
                    "excerpt": "Reviewed case excerpt.",
                    "source_type": "human_reviewed",
                },
            ],
        )
    )

    results = await service.apply_policy_and_write_all(candidates)

    assert isinstance(candidates[0], SessionMemoryWriteCandidate)
    assert isinstance(candidates[1], LongTermMemoryWriteCandidate)
    assert isinstance(candidates[2], CaseMemoryWriteCandidate)
    assert len(session_service.candidates) == 1
    assert len(long_term_service.candidates) == 1
    assert len(case_service.candidates) == 1
    assert [result.status for result in results] == ["written", "needs_review", "written"]
