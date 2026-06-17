from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.investigate import investigate
from src.db.models import AgentRun
from src.knowledge.schemas import EvidenceRefV1
from src.tools.catalog import ToolCatalog
from src.tools.contracts import BusinessFactRefV1, ToolCallContext, ToolError, ToolResultV2


def _state(plan: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "thread_id": "thread-1",
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "role": "support",
        "current_run_id": str(uuid4()),
        "user_query": "订单退款为什么超时？",
        "_investigate_plan": plan,
    }


def _config(manager, events: list[dict[str, Any]], **overrides):
    async def event_emitter(**payload):
        events.append(payload)

    configurable = {
        "tool_manager": manager,
        "event_emitter": event_emitter,
        "permissions": [f"tool:{descriptor.name}" for descriptor in ToolCatalog().descriptors()],
        "merchant_scope": {"merchant_ids": ["*"]},
        "trace_id": "trace-1",
        "max_iterations": 3,
        "max_attempts": 1,
    }
    configurable.update(overrides)
    return {"configurable": configurable}


class FakeManager:
    def __init__(self, results: dict[str, ToolResultV2]) -> None:
        self._descriptors = {descriptor.name: descriptor for descriptor in ToolCatalog().descriptors()}
        self.results = results
        self.calls: list[tuple[str, dict[str, Any], ToolCallContext]] = []

    def descriptors(self, caller_node: str = "investigate"):
        return [
            descriptor
            for descriptor in self._descriptors.values()
            if caller_node in descriptor.caller_allowlist and descriptor.kind != "write"
        ]

    def descriptor(self, name: str):
        return self._descriptors.get(name)

    def event_family(self, name: str) -> str:
        family = self._descriptors[name].event_family
        return "rag_retrieval" if family == "rag_retrieval_*" else "tool_call"

    async def invoke(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        self.calls.append((name, args, ctx))
        return self.results[name]


def _business_success(resource_type: str = "order", resource_id: str = "ORD-001") -> ToolResultV2:
    ref = BusinessFactRefV1(
        tenant_id=str(uuid4()),
        source_system="moca",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_version=None,
        data_freshness_at=datetime.now(UTC),
        retrieved_at=datetime.now(UTC),
    )
    return ToolResultV2(
        status="success",
        data={"id": resource_id, "status": "delivered"},
        summary="business fact loaded",
        source_system="business_tool_service",
        data_freshness_at=datetime.now(UTC),
        policy_evidence_refs=[],
        business_fact_refs=[ref],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=2,
        audit_ref=None,
    )


def _business_success_with_raw_payload(resource_type: str = "order", resource_id: str = "ORD-RAW-001") -> ToolResultV2:
    ref = BusinessFactRefV1(
        tenant_id=str(uuid4()),
        source_system="moca",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_version=None,
        data_freshness_at=datetime.now(UTC),
        retrieved_at=datetime.now(UTC),
    )
    return ToolResultV2(
        status="success",
        data={
            "id": resource_id,
            "raw_payload": {"customer_phone": "13800000000", "nested": ["SHOULD_NOT_APPEAR"]},
        },
        summary="business fact loaded",
        source_system="business_tool_service",
        data_freshness_at=datetime.now(UTC),
        policy_evidence_refs=[],
        business_fact_refs=[ref],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=2,
        audit_ref="audit/tool-result/ORD-RAW-001",
    )


async def _insert_run(session: AsyncSession, seeded_session: dict, thread_id: str) -> str:
    run_id = uuid4()
    session.add(
        AgentRun(
            id=run_id,
            tenant_id=seeded_session["tenant"].id,
            user_id=seeded_session["users"]["cs_zhang"].id,
            thread_id=thread_id,
            input_query="test",
            final_status="completed",
            started_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return str(run_id)


def _policy_success(status: str = "strong_evidence", score: float = 0.91) -> ToolResultV2:
    ref = EvidenceRefV1.build(
        tenant_id=str(uuid4()),
        doc_key="refund_policy",
        chunk_id="refund_policy#001",
        policy_version="v1",
        text="退款政策",
        retrieved_at=datetime.now(UTC).isoformat(),
        retrieval_config_version="test",
        score=score,
        rank=1,
    )
    return ToolResultV2(
        status="success",
        data={"retrieval_status": status, "best_score": score},
        summary="policy found",
        source_system="policy_knowledge_service",
        data_freshness_at=None,
        policy_evidence_refs=[ref],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=3,
        audit_ref=None,
    )


def _policy_not_found() -> ToolResultV2:
    return ToolResultV2(
        status="not_found",
        data={"retrieval_status": "no_evidence", "best_score": 0.0},
        summary="no policy found",
        source_system="policy_knowledge_service",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=3,
        audit_ref=None,
    )


def _policy_retrieval_error() -> ToolResultV2:
    return ToolResultV2(
        status="error",
        data={"retrieval_status": "error", "best_score": 0.0},
        summary="policy search failed",
        source_system="policy_knowledge_service",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=ToolError(
            code="KNOWLEDGE_SEARCH_ERROR", safe_message="Policy search failed", retryable=False, source="upstream"
        ),
        retryable=False,
        retry_after_ms=None,
        latency_ms=3,
        audit_ref=None,
    )


def _error(status: str, code: str = "TOOL_UNAVAILABLE", message: str = "unavailable") -> ToolResultV2:
    return ToolResultV2(
        status=status,
        data=None,
        summary=message,
        source_system="unified_tool_manager",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=ToolError(code=code, safe_message=message, retryable=False, source="tool"),
        retryable=False,
        retry_after_ms=None,
        latency_ms=1,
        audit_ref=None,
    )


@pytest.mark.asyncio
async def test_max_iterations_reached_does_not_degrade_retrieval_status():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"search_policy": _policy_success("strong_evidence", 0.9)})
    plan = [{"next_tool": "search_policy", "args": {"query": f"q{i}"}, "reason": "test"} for i in range(5)]

    result = await investigate(_state(plan), _config(manager, events, max_iterations=2))

    assert len(manager.calls) == 2
    assert result["termination_reason"] == "max_iterations_reached"
    assert result["retrieval_status"] == "strong_evidence"


@pytest.mark.asyncio
async def test_deadline_and_attempt_controls_map_to_unrecoverable_error():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"search_policy": _policy_success()})
    plan = [{"next_tool": "search_policy", "args": {"query": "refund"}, "reason": "test"}]

    deadline_result = await investigate(
        _state(plan),
        _config(manager, events, deadline_at=datetime.now(UTC) - timedelta(seconds=1)),
    )
    attempts_result = await investigate(_state(plan), _config(manager, events, max_attempts=0))

    assert deadline_result["termination_reason"] == "unrecoverable_error"
    assert attempts_result["termination_reason"] == "unrecoverable_error"
    assert manager.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "plan",
    [
        [{"bad": "shape"}],
        [{"next_tool": "get_order", "args": {}, "stop": True, "stop_reason": "enough_evidence"}],
        [{"next_tool": "unknown_tool", "args": {}, "reason": "bad"}],
        [{"next_tool": "create_coupon_grant_draft", "args": {"merchant_id": "m1", "amount": 1}, "reason": "bad"}],
    ],
)
async def test_invalid_planner_output_rejected_before_manager_dispatch(plan):
    events: list[dict[str, Any]] = []
    manager = FakeManager({"get_order": _business_success()})

    result = await investigate(_state(plan), _config(manager, events))

    assert result["termination_reason"] == "unrecoverable_error"
    assert manager.calls == []


@pytest.mark.asyncio
async def test_every_execution_uses_unified_tool_manager():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"get_order": _business_success()})
    plan = [{"next_tool": "get_order", "args": {"order_no": "ORD-001"}, "reason": "test"}]

    result = await investigate(_state(plan), _config(manager, events))

    assert [call[0] for call in manager.calls] == ["get_order"]
    assert result["business_context"]["facts"]["order"]["id"] == "ORD-001"


@pytest.mark.asyncio
async def test_action_intent_without_case_identifier_marks_missing_fact():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"search_policy": _policy_success()})
    state = _state([{"next_tool": "search_policy", "args": {"query": "refund"}, "reason": "policy"}])
    state["current_intent"] = "refund_troubleshooting"

    result = await investigate(state, _config(manager, events))

    assert result["business_context"]["missing_required_facts"] == ["case_identifier"]


@pytest.mark.asyncio
async def test_requested_case_identifier_without_fact_marks_specific_missing_resource():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"get_order": _error("not_found", code="NOT_FOUND", message="not found")})
    state = _state([{"next_tool": "get_order", "args": {"order_no": "ORD-MISSING"}, "reason": "fact"}])
    state["current_intent"] = "refund_troubleshooting"
    state["extracted_slots"] = {"order_id": "ORD-MISSING"}

    result = await investigate(state, _config(manager, events))

    assert result["business_context"]["missing_required_facts"] == ["order"]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["get_logistics", "search_sop", "search_case_memory"])
async def test_unavailable_tools_recorded_through_manager_path(tool_name):
    events: list[dict[str, Any]] = []
    manager = FakeManager({tool_name: _error("unavailable")})
    args = {"query": "refund"} if tool_name.startswith("search_") else {"tracking_no": "T1"}
    plan = [{"next_tool": tool_name, "args": args, "reason": "test"}]

    result = await investigate(_state(plan), _config(manager, events))

    assert [call[0] for call in manager.calls] == [tool_name]
    assert result["business_context"]["errors"][0]["code"] == "TOOL_UNAVAILABLE"
    assert result["tool_results"][0]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_unavailable_tool_not_retried_with_same_args():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"search_sop": _error("unavailable")})
    plan = [
        {"next_tool": "search_sop", "args": {"query": "refund"}, "reason": "test"},
        {"next_tool": "search_sop", "args": {"query": "refund"}, "reason": "retry"},
    ]

    result = await investigate(_state(plan), _config(manager, events, max_iterations=3))

    assert [call[0] for call in manager.calls] == ["search_sop"]
    assert result["termination_reason"] == "no_more_useful_tools"


@pytest.mark.asyncio
async def test_no_write_gate_fields_or_authoritative_citation_refs():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"get_order": _business_success()})
    plan = [{"next_tool": "get_order", "args": {"order_no": "ORD-001"}, "reason": "test"}]

    result = await investigate(_state(plan), _config(manager, events))

    assert "proposed_action" not in result
    assert "risk_assessment" not in result
    assert "approval_result" not in result
    assert "action_result" not in result
    assert "evidence_refs" not in result


@pytest.mark.asyncio
async def test_permission_denied_preserves_successful_facts_without_denied_fact_leak():
    events: list[dict[str, Any]] = []
    manager = FakeManager(
        {
            "get_order": _business_success("order", "ORD-001"),
            "get_merchant_risk": _error("permission_denied", code="FORBIDDEN", message="Access denied"),
        }
    )
    plan = [
        {"next_tool": "get_order", "args": {"order_no": "ORD-001"}, "reason": "ok"},
        {"next_tool": "get_merchant_risk", "args": {"merchant_id": "M-SECRET"}, "reason": "deny"},
    ]

    result = await investigate(_state(plan), _config(manager, events))

    assert "order" in result["business_context"]["facts"]
    assert "merchant_risk" not in result["business_context"]["facts"]
    assert result["business_context"]["errors"][0]["resource"] == "merchant_risk"
    assert "M-SECRET" not in str(result["business_context"]["errors"])


@pytest.mark.asyncio
async def test_claim_dependency_map_uses_typed_refs_from_results():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"get_order": _business_success(), "search_policy": _policy_success()})
    state = _state(
        [
            {"next_tool": "get_order", "args": {"order_no": "ORD-001"}, "reason": "fact"},
            {"next_tool": "search_policy", "args": {"query": "refund"}, "reason": "policy"},
        ]
    )
    state["claim_dependency_map"] = [{"claim_id": "planner-claim", "depends_on_refs": []}]

    result = await investigate(state, _config(manager, events))

    refs = [ref for item in result["claim_dependency_map"] for ref in item["depends_on_refs"]]
    assert {"resource_type": "order", "resource_id": "ORD-001"} in refs
    assert any(ref["resource_type"] == "policy" for ref in refs)
    assert all(item["claim_id"] != "planner-claim" for item in result["claim_dependency_map"])


@pytest.mark.asyncio
async def test_policy_retrieval_semantics_survive_tool_result_flattening():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"search_policy": _policy_success("partial_evidence", 0.61)})
    plan = [{"next_tool": "search_policy", "args": {"query": "refund"}, "reason": "policy"}]

    result = await investigate(_state(plan), _config(manager, events))

    assert result["retrieval_status"] == "partial_evidence"
    assert result["best_score"] == 0.61
    assert result["policy_evidence"]
    assert result["tool_results"][0]["policy_evidence_refs"]


@pytest.mark.asyncio
async def test_investigate_state_tool_results_are_prompt_safe_refs(session: AsyncSession, seeded_session: dict):
    events: list[dict[str, Any]] = []
    manager = FakeManager({"get_order": _business_success_with_raw_payload()})
    thread_id = "thread-investigate-tool-projection"
    state = _state([{"next_tool": "get_order", "args": {"order_no": "ORD-RAW-001"}, "reason": "test"}])
    state["tenant_id"] = str(seeded_session["tenant"].id)
    state["user_id"] = str(seeded_session["users"]["cs_zhang"].id)
    state["thread_id"] = thread_id
    state["current_run_id"] = await _insert_run(session, seeded_session, thread_id)

    result = await investigate(_state([]) | state, _config(manager, events, session=session))

    projection = result["tool_results"][0]

    assert {
        "tool_call_id",
        "tool_result_id",
        "tool_name",
        "status",
        "summary",
        "prompt_summary",
        "business_fact_refs",
        "policy_evidence_refs",
    } <= set(projection)
    assert "data" not in projection
    assert "raw_payload" not in projection
    assert "13800000000" not in str(projection)
    assert "SHOULD_NOT_APPEAR" not in str(projection)


@pytest.mark.asyncio
async def test_no_evidence_result_sets_insufficient_recommendation_draft():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"search_policy": _policy_not_found()})
    plan = [{"next_tool": "search_policy", "args": {"query": "refund"}, "reason": "policy"}]

    result = await investigate(_state(plan), _config(manager, events))

    assert result["retrieval_status"] == "no_evidence"
    assert result["recommendation_draft"]["recommended_action"] == "insufficient_evidence"
    assert result["recommendation_draft"]["evidence_refs"] == []


@pytest.mark.asyncio
async def test_retrieval_error_result_sets_error_recommendation_draft():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"search_policy": _policy_retrieval_error()})
    plan = [{"next_tool": "search_policy", "args": {"query": "refund"}, "reason": "policy"}]

    result = await investigate(_state(plan), _config(manager, events))

    assert result["retrieval_status"] == "error"
    assert result["recommendation_draft"]["recommended_action"] == "retrieval_error"
    assert result["recommendation_draft"]["missing_info"] == ["Policy search failed"]


@pytest.mark.asyncio
async def test_event_classification_iteration_and_redacted_payload():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"get_order": _business_success(), "search_policy": _policy_success()})
    plan = [
        {"next_tool": "get_order", "args": {"order_no": "ORD-001"}, "reason": "fact"},
        {"next_tool": "search_policy", "args": {"query": "refund"}, "reason": "policy"},
    ]

    await investigate(_state(plan), _config(manager, events))

    assert [event["event_type"] for event in events] == [
        "tool_call_started",
        "tool_call_completed",
        "rag_retrieval_started",
        "rag_retrieval_completed",
    ]
    assert [event["iteration"] for event in events] == [1, 1, 2, 2]
    assert all("raw" not in str(event["payload"]).lower() for event in events)
    assert all("arguments" not in event["payload"] for event in events)
