from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agent.nodes import retrieve_policy_evidence as retrieve_policy_evidence_module
from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1, KnowledgeContext, KnowledgeSearchResult


def _evidence(*, policy_version: str = "v1", chunk_id: str = "chunk_001") -> EvidenceRefV1:
    return EvidenceRefV1.build(
        tenant_id="tenant",
        doc_key="policy_refund_timeout",
        chunk_id=chunk_id,
        policy_version=policy_version,
        text="规则摘录",
        retrieved_at="2026-06-07T02:30:00+00:00",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.82,
        rank=1,
    )


def _result(
    *,
    status: str = "strong_evidence",
    best_score: float = 0.82,
    evidence_refs: list[EvidenceRefV1] | None = None,
    error: dict | None = None,
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        status=status,
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        best_score=best_score,
        threshold=0.55,
        evidence_refs=evidence_refs or [],
        error=error,
    )


def _mock_search(monkeypatch, result: KnowledgeSearchResult) -> AsyncMock:
    search = AsyncMock(return_value=result)
    monkeypatch.setattr(retrieve_policy_evidence_module.PolicyKnowledgeService, "search", search)
    return search


@pytest.mark.asyncio
async def test_evidence_gate_no_evidence(monkeypatch, base_state):
    _mock_search(monkeypatch, _result(status="no_evidence", best_score=0.0))

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {"session": AsyncMock()}},
    )

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["evidence_refs"] == []


@pytest.mark.asyncio
async def test_retrieve_policy_evidence_writes_facade_payload_and_canonical_refs(monkeypatch, base_state):
    evidence = _evidence()
    search = _mock_search(monkeypatch, _result(evidence_refs=[evidence]))
    run_started_at = "2026-06-07T02:29:00+00:00"

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        {**base_state, "run_started_at": run_started_at, "current_run_id": "run-1"},
        {"configurable": {"session": AsyncMock()}},
    )

    assert result["retrieved_evidence"]["schema_version"] == "knowledge_search_result.v2"
    assert result["evidence_refs"][0]["evidence_id"] == evidence.evidence_id
    assert result["evidence_refs"][0]["text_hash"] == evidence.text_hash
    request, context = search.await_args.args
    assert request.filters.effective_at == run_started_at
    assert context.effective_at == run_started_at
    assert result["trace_steps"][-1]["tools_called"] == ["knowledge_service.search"]


@pytest.mark.asyncio
async def test_retrieve_policy_evidence_preserves_previous_refs_on_low_score(monkeypatch, base_state):
    prior_ref = _evidence(policy_version="v1").model_dump()
    _mock_search(monkeypatch, _result(status="partial_evidence", best_score=0.3, evidence_refs=[_evidence()]))

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        {**base_state, "evidence_refs": [prior_ref]},
        {"configurable": {"session": AsyncMock()}},
    )

    assert result["evidence_refs"] == [prior_ref]
    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_merge_keeps_same_chunk_from_distinct_policy_versions(monkeypatch, base_state):
    prior_ref = _evidence(policy_version="v1").model_dump()
    current_ref = _evidence(policy_version="v2")
    _mock_search(monkeypatch, _result(evidence_refs=[current_ref]))

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        {**base_state, "evidence_refs": [prior_ref]},
        {"configurable": {"session": AsyncMock()}},
    )

    assert [ref["evidence_id"] for ref in result["evidence_refs"]] == [
        prior_ref["evidence_id"],
        current_ref.evidence_id,
    ]


@pytest.mark.asyncio
async def test_search_error_records_node_error_not_insufficient_evidence(monkeypatch, base_state):
    _mock_search(
        monkeypatch,
        _result(
            status="error",
            best_score=0.0,
            error={"error_code": "DB_TIMEOUT", "message": "Policy search timeout", "retryable": True},
        ),
    )

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {"session": AsyncMock()}},
    )

    assert result["recommendation_draft"]["recommended_action"] == "retrieval_error"
    assert result["node_errors"][0]["error"]["error_code"] == "DB_TIMEOUT"
    assert result["trace_steps"][-1]["status"] == "error"


# --- Merchant scope projection tests (09-07) ---


@pytest.mark.asyncio
async def test_structured_merchant_ids_projected_to_knowledge_context(monkeypatch, base_state):
    """Structured dict with merchant_ids must reach KnowledgeContext.merchant_scope unchanged."""
    search = _mock_search(monkeypatch, _result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {
            "session": AsyncMock(),
            "merchant_scope": {"merchant_ids": ["merchant-1"]},
        }},
    )

    _, context = search.await_args.args
    assert isinstance(context, KnowledgeContext)
    assert context.merchant_scope == ["merchant-1"]


@pytest.mark.asyncio
async def test_legacy_list_merchant_scope_preserved(monkeypatch, base_state):
    """Legacy list merchant_scope passes through unchanged."""
    search = _mock_search(monkeypatch, _result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {
            "session": AsyncMock(),
            "merchant_scope": ["merchant-legacy"],
        }},
    )

    _, context = search.await_args.args
    assert context.merchant_scope == ["merchant-legacy"]


@pytest.mark.asyncio
async def test_missing_merchant_scope_fails_closed_to_empty_list(monkeypatch, base_state):
    """Missing merchant_scope becomes empty list, not unrestricted None."""
    search = _mock_search(monkeypatch, _result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {"session": AsyncMock()}},
    )

    _, context = search.await_args.args
    assert context.merchant_scope == []


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_scope", [
    None,
    "not-a-list-or-dict",
    42,
    {"merchant_ids": None},
    {"merchant_ids": "not-a-list"},
    {"merchant_ids": []},
    {"merchant_ids": [123, True]},
    {"categories": ["electronics"]},
    {},
])
async def test_malformed_merchant_scope_fails_closed(monkeypatch, base_state, bad_scope):
    """Malformed or non-string structured merchant IDs become [], never None."""
    search = _mock_search(monkeypatch, _result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {
            "session": AsyncMock(),
            "merchant_scope": bad_scope,
        }},
    )

    _, context = search.await_args.args
    assert context.merchant_scope == [], f"Expected fail-closed [] for {bad_scope!r}, got {context.merchant_scope!r}"


@pytest.mark.asyncio
async def test_other_structured_dimensions_not_misinterpreted_as_merchant_ids(monkeypatch, base_state):
    """Dict with categories/risk_levels but no merchant_ids must not infer merchant IDs."""
    search = _mock_search(monkeypatch, _result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {
            "session": AsyncMock(),
            "merchant_scope": {"categories": ["electronics"], "risk_levels": ["high"]},
        }},
    )

    _, context = search.await_args.args
    assert context.merchant_scope == []


@pytest.mark.asyncio
async def test_structured_merchant_ids_multiple_values(monkeypatch, base_state):
    """Multiple merchant IDs in structured scope are all preserved."""
    search = _mock_search(monkeypatch, _result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        {"configurable": {
            "session": AsyncMock(),
            "merchant_scope": {"merchant_ids": ["merchant-a", "merchant-b", "merchant-c"]},
        }},
    )

    _, context = search.await_args.args
    assert context.merchant_scope == ["merchant-a", "merchant-b", "merchant-c"]
