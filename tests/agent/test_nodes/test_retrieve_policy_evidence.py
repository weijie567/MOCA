from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agent.nodes import retrieve_policy_evidence as retrieve_policy_evidence_module
from src.knowledge.config import RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import ToolCallContext, ToolError, ToolResultV2


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
) -> ToolResultV2:
    tool_status = "success"
    tool_error = None
    if status == "no_evidence":
        tool_status = "not_found"
    elif status == "error":
        tool_status = "error"
        error = error or {"error_code": "SEARCH_ERROR", "message": "Policy search failed", "retryable": False}
        tool_error = ToolError(
            code=str(error["error_code"]),
            safe_message=str(error["message"]),
            retryable=bool(error.get("retryable", False)),
            source="upstream",
        )
    return ToolResultV2(
        status=tool_status,
        data={"retrieval_status": status, "best_score": best_score, "threshold": 0.55},
        summary=f"Policy search returned {status}",
        source_system="policy_knowledge_service",
        data_freshness_at=None,
        policy_evidence_refs=[] if tool_error else evidence_refs or [],
        business_fact_refs=[],
        error=tool_error,
        retryable=bool(tool_error.retryable) if tool_error else False,
        retry_after_ms=None,
        latency_ms=1,
        audit_ref=None,
    )


class FakeManager:
    def __init__(self, result: ToolResultV2):
        self.result = result
        self.calls: list[tuple[str, dict, ToolCallContext]] = []

    async def invoke(self, name: str, args: dict, ctx: ToolCallContext) -> ToolResultV2:
        self.calls.append((name, args, ctx))
        if "tool:search_policy" not in ctx.permissions:
            return ToolResultV2(
                status="permission_denied",
                data=None,
                summary="Required tool permission is missing",
                source_system="unified_tool_manager",
                data_freshness_at=None,
                policy_evidence_refs=[],
                business_fact_refs=[],
                error=ToolError(
                    code="PERMISSION_REQUIRED",
                    safe_message="Required tool permission is missing",
                    retryable=False,
                    source="caller",
                ),
                retryable=False,
                retry_after_ms=None,
                latency_ms=0,
                audit_ref=None,
            )
        return self.result


def _config(
    *,
    permissions: list[str] | None = None,
    merchant_scope: object = None,
    manager: FakeManager | None = None,
) -> dict:
    configurable = {
        "session": AsyncMock(),
        "permissions": ["tool:search_policy"] if permissions is None else permissions,
        "tool_manager": manager or FakeManager(_result()),
    }
    if merchant_scope is not None:
        configurable["merchant_scope"] = merchant_scope
    return {"configurable": configurable}


@pytest.mark.asyncio
@pytest.mark.parametrize("permissions", [None, [], ["tool:get_order"]])
async def test_retrieve_policy_evidence_denies_without_search_permission(base_state, permissions):
    manager = FakeManager(_result())
    config = {"configurable": {"session": AsyncMock(), "tool_manager": manager}}
    if permissions is not None:
        config["configurable"]["permissions"] = permissions

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(base_state, config)

    assert len(manager.calls) == 1
    assert result["retrieved_evidence"]["status"] == "error"
    assert result["retrieved_evidence"]["error"]["error_code"] == "PERMISSION_REQUIRED"
    assert result["evidence_refs"] == []
    assert result["node_errors"][-1]["error"]["error_code"] == "PERMISSION_REQUIRED"
    assert result["trace_steps"][-1]["status"] == "error"


@pytest.mark.asyncio
async def test_evidence_gate_no_evidence(base_state):
    manager = FakeManager(_result(status="no_evidence", best_score=0.0))

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        _config(manager=manager),
    )

    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["evidence_refs"] == []


@pytest.mark.asyncio
async def test_retrieve_policy_evidence_writes_facade_payload_and_canonical_refs(base_state):
    evidence = _evidence()
    manager = FakeManager(_result(evidence_refs=[evidence]))
    run_started_at = "2026-06-07T02:29:00+00:00"

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        {**base_state, "run_started_at": run_started_at, "current_run_id": "run-1"},
        _config(manager=manager),
    )

    assert result["retrieved_evidence"]["schema_version"] == "knowledge_search_result.v2"
    assert result["evidence_refs"][0]["evidence_id"] == evidence.evidence_id
    assert result["evidence_refs"][0]["text_hash"] == evidence.text_hash
    tool_name, args, context = manager.calls[0]
    assert tool_name == "search_policy"
    assert args["query"]
    assert context.effective_at == run_started_at
    assert result["trace_steps"][-1]["tools_called"] == ["search_policy"]


@pytest.mark.asyncio
async def test_retrieve_policy_evidence_preserves_previous_refs_on_low_score(base_state):
    prior_ref = _evidence(policy_version="v1").model_dump()
    manager = FakeManager(_result(status="partial_evidence", best_score=0.3, evidence_refs=[_evidence()]))

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        {**base_state, "evidence_refs": [prior_ref]},
        _config(manager=manager),
    )

    assert result["evidence_refs"] == [prior_ref]
    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_merge_keeps_same_chunk_from_distinct_policy_versions(base_state):
    prior_ref = _evidence(policy_version="v1").model_dump()
    current_ref = _evidence(policy_version="v2")
    manager = FakeManager(_result(evidence_refs=[current_ref]))

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        {**base_state, "evidence_refs": [prior_ref]},
        _config(manager=manager),
    )

    assert [ref["evidence_id"] for ref in result["evidence_refs"]] == [
        prior_ref["evidence_id"],
        current_ref.evidence_id,
    ]


@pytest.mark.asyncio
async def test_search_error_records_node_error_not_insufficient_evidence(base_state):
    manager = FakeManager(
        _result(
            status="error",
            best_score=0.0,
            error={"error_code": "DB_TIMEOUT", "message": "Policy search timeout", "retryable": True},
        )
    )

    result = await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        _config(manager=manager),
    )

    assert result["recommendation_draft"]["recommended_action"] == "retrieval_error"
    assert result["node_errors"][0]["error"]["error_code"] == "DB_TIMEOUT"
    assert result["trace_steps"][-1]["status"] == "error"


# --- Merchant scope projection tests (09-07) ---


@pytest.mark.asyncio
async def test_structured_merchant_ids_reach_tool_context(base_state):
    """Structured dict with merchant_ids must reach ToolCallContext unchanged."""
    manager = FakeManager(_result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        _config(merchant_scope={"merchant_ids": ["merchant-1"]}, manager=manager),
    )

    _, _, context = manager.calls[0]
    assert context.merchant_scope == {"merchant_ids": ["merchant-1"]}


@pytest.mark.asyncio
async def test_legacy_list_merchant_scope_preserved(base_state):
    """Legacy list merchant_scope passes through unchanged."""
    manager = FakeManager(_result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        _config(merchant_scope=["merchant-legacy"], manager=manager),
    )

    _, _, context = manager.calls[0]
    assert context.merchant_scope == ["merchant-legacy"]


@pytest.mark.asyncio
async def test_missing_merchant_scope_fails_closed_to_empty_dict(base_state):
    """Missing merchant_scope becomes empty dict, not unrestricted None."""
    manager = FakeManager(_result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        _config(manager=manager),
    )

    _, _, context = manager.calls[0]
    assert context.merchant_scope == {}


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
async def test_malformed_merchant_scope_fails_closed(base_state, bad_scope):
    """Non-dict/list merchant_scope values become {}, never unrestricted None."""
    manager = FakeManager(_result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        _config(merchant_scope=bad_scope, manager=manager),
    )

    _, _, context = manager.calls[0]
    expected = bad_scope if isinstance(bad_scope, (dict, list)) else {}
    assert context.merchant_scope == expected


@pytest.mark.asyncio
async def test_other_structured_dimensions_preserved_for_executor_projection(base_state):
    """Dict with categories/risk_levels is preserved for executor fail-closed projection."""
    manager = FakeManager(_result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        _config(merchant_scope={"categories": ["electronics"], "risk_levels": ["high"]}, manager=manager),
    )

    _, _, context = manager.calls[0]
    assert context.merchant_scope == {"categories": ["electronics"], "risk_levels": ["high"]}


@pytest.mark.asyncio
async def test_structured_merchant_ids_multiple_values(base_state):
    """Multiple merchant IDs in structured scope are all preserved."""
    manager = FakeManager(_result(status="no_evidence", best_score=0.0))

    await retrieve_policy_evidence_module.retrieve_policy_evidence(
        base_state,
        _config(merchant_scope={"merchant_ids": ["merchant-a", "merchant-b", "merchant-c"]}, manager=manager),
    )

    _, _, context = manager.calls[0]
    assert context.merchant_scope == {"merchant_ids": ["merchant-a", "merchant-b", "merchant-c"]}
