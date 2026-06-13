from __future__ import annotations

import pytest

from src.agent.nodes.receive_request import receive_request


def _base_state() -> dict:
    return {
        "thread_id": "test-thread",
        "tenant_id": "tenant-001",
        "user_id": "user-001",
        "role": "support_agent",
        "user_query": "订单ORD-001为什么还没退款？",
    }


EPHEMERAL_FIELDS = [
    "normalized_query",
    "current_intent",
    "primary_intent",
    "requested_operation",
    "extracted_slots",
    "business_context",
    "retrieved_evidence",
    "policy_evidence",
    "retrieval_status",
    "best_score",
    "termination_reason",
    "case_memory",
    "claim_dependency_map",
    "session_memory",
    "long_term_memory",
    "recommendation_draft",
    "risk_assessment",
    "proposed_action",
    "approval_result",
    "action_result",
    "final_response",
]

IDENTITY_FIELDS = {"tenant_id", "user_id", "role", "thread_id"}


@pytest.mark.asyncio
async def test_reset_nulls_all_new_ephemeral_fields():
    state = {
        **_base_state(),
        "primary_intent": "refund",
        "requested_operation": "refund_status",
        "retrieval_status": "strong_evidence",
        "best_score": 0.91,
        "termination_reason": "max_iterations_reached",
        "policy_evidence": [{"evidence_id": "policy/chunk@v1"}],
        "case_memory": [{"case_id": "case-1"}],
        "claim_dependency_map": [{"claim": "refund"}],
        "session_memory": {"last_order": "ORD-001"},
        "long_term_memory": [{"merchant_id": "merchant-1"}],
    }

    result = await receive_request(state)

    for field in (
        "primary_intent",
        "requested_operation",
        "retrieval_status",
        "best_score",
        "termination_reason",
        "policy_evidence",
        "case_memory",
        "claim_dependency_map",
        "session_memory",
        "long_term_memory",
    ):
        assert result.get(field) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("field", EPHEMERAL_FIELDS)
async def test_cross_turn_isolation_table(field):
    result = await receive_request({**_base_state(), field: "STALE"})

    assert result.get(field) is None


@pytest.mark.asyncio
async def test_identity_fields_not_reset():
    result = await receive_request(_base_state())

    assert set(result) & IDENTITY_FIELDS == set()


@pytest.mark.asyncio
async def test_llm_output_cannot_overwrite_identity():
    state = {
        **_base_state(),
        "llm_outputs": {"tenant_id": "evil-tenant", "role": "admin"},
    }

    result = await receive_request(state)

    assert set(result) & IDENTITY_FIELDS == set()
    assert result["llm_outputs"] == {}


@pytest.mark.asyncio
async def test_current_run_id_preserved_or_minted():
    preserved = await receive_request({**_base_state(), "current_run_id": "api-run-001"})
    minted = await receive_request(_base_state())

    assert preserved["current_run_id"] == "api-run-001"
    assert isinstance(minted["current_run_id"], str)
    assert minted["current_run_id"]
