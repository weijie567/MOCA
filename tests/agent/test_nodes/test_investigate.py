from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.investigate import investigate
from src.db.models import AgentRun, AgentTraceEvent
from src.knowledge.schemas import EvidenceRefV1
from src.platform.trusted_context import MerchantScopeV1, TrustedContext
from src.tools.catalog import ToolCatalog
from src.tools.contracts import (
    BusinessFactRefV1,
    ToolCallContext,
    ToolError,
    ToolInvocationOutcome,
    ToolPolicyDecision,
    ToolResultProjectionV1,
    ToolResultV2,
    ToolViewV1,
)
from src.tools.projection import ToolResultProjector


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


def _default_trusted_context(permissions: list[str]) -> dict[str, Any]:
    return TrustedContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        role="support",
        permissions=permissions,
        merchant_scope=MerchantScopeV1(merchant_ids=["*"]),
        session_id=None,
        thread_id="thread-1",
        run_id=str(uuid4()),
        trace_id="trace-1",
        locale=None,
    ).model_dump(mode="json")


def _config(manager, events: list[dict[str, Any]], **overrides):
    async def event_emitter(**payload):
        events.append(payload)

    permissions = [f"tool:{descriptor.name}" for descriptor in ToolCatalog().descriptors()]
    configurable = {
        "tool_manager": manager,
        "event_emitter": event_emitter,
        "trusted_context": _default_trusted_context(permissions),
        "permissions": permissions,
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
        self._platform = _FakePlatform(self)

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


class _FakePlatform:
    """Minimal ToolPlatform facade wrapping FakeManager for tests."""

    def __init__(self, manager: FakeManager) -> None:
        self._manager = manager
        self._projector = ToolResultProjector()
        self.last_visibility_decisions = None

    async def visible_tools(
        self, *, caller: str, ctx: ToolCallContext, session: Any = None,
    ) -> list[ToolViewV1]:
        from src.tools.policy import ToolPolicyEngine, project_prompt_safe_input_schema

        engine = ToolPolicyEngine()
        decisions = engine.visibility_decisions(caller=caller, ctx=ctx)
        self.last_visibility_decisions = decisions
        views = []
        for decision in decisions:
            if decision.decision != "visible":
                continue
            descriptor = self._manager._descriptors.get(decision.tool_name)
            if descriptor is None:
                continue
            views.append(
                ToolViewV1(
                    name=descriptor.name,
                    description=descriptor.description,
                    input_schema=project_prompt_safe_input_schema(descriptor.input_schema),
                    safe_usage_notes=[],
                    result_contract_version="tool_result.v2",
                )
            )
        return views

    async def invoke(
        self, tool_name: str, args: dict[str, Any], ctx: ToolCallContext, *, session: Any = None,
    ) -> ToolInvocationOutcome:
        result = await self._manager.invoke(tool_name, args, ctx)
        projection = self._projector.project(
            tool_name=tool_name, result=result, tool_call_id=ctx.tool_call_id,
        )
        _status_to_reason = {
            "unavailable": "tool_unavailable",
            "permission_denied": "missing_permission",
        }
        decision = ToolPolicyDecision(
            tool_name=tool_name,
            caller=ctx.caller_node,
            decision_stage="runtime_auth",
            decision="allowed" if result.status == "success" else "denied",
            reason_codes=(
                ["visible"] if result.status == "success"
                else [_status_to_reason.get(result.status, "missing_permission")]
            ),
            required_scopes=[],
            matched_scope=None,
            policy_version="tool_policy.v1",
            data_classification="internal",
            runtime_available=result.status != "unavailable",
        )
        return ToolInvocationOutcome(
            tool_result=result,
            projection=projection,
            policy_decision=decision,
            policy_event_id=None,
        )

    def descriptor(self, name: str):
        return self._manager._descriptors.get(name)

    def event_family(self, name: str) -> str | None:
        descriptor = self._manager._descriptors.get(name)
        if descriptor is None:
            return None
        family = descriptor.event_family
        if family == "tool_call_*":
            return "tool_call"
        if family == "rag_retrieval_*":
            return "rag_retrieval"
        if family == "action":
            return "action"
        return None


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


def _case_memory_success() -> ToolResultV2:
    return ToolResultV2(
        status="success",
        data={
            "items": [
                {
                    "case_memory_id": "case-memory-1",
                    "excerpt": "Reviewed refund timeout precedent.",
                    "applicability": "Similar delayed refund case.",
                    "outcome": "Context only.",
                    "score": 0.92,
                    "policy_refs": [{"doc_key": "refund_policy", "chunk_id": "chunk-1"}],
                    "source_refs": [{"business_object_id": "refund-case-1"}],
                    "raw_tool_payload": {"secret": "must-not-leak"},
                }
            ]
        },
        summary="case memory found",
        source_system="case_memory_service",
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
async def test_investigate_consumes_trusted_context_config_not_agentstate_permission_scope():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"get_order": _business_success()})
    state = _state([{"next_tool": "get_order", "args": {"order_no": "ORD-001"}, "reason": "test"}])
    state["permissions"] = ["tool:search_policy"]
    state["merchant_scope"] = {"merchant_ids": ["merchant-from-AgentState"]}
    trusted_context = TrustedContext(
        tenant_id=state["tenant_id"],
        user_id=state["user_id"],
        role=state["role"],
        permissions=["tool:get_order"],
        merchant_scope=MerchantScopeV1(merchant_ids=["merchant-from-trusted-config"]),
        session_id=None,
        thread_id=state["thread_id"],
        run_id=state["current_run_id"],
        trace_id="trace-from-trusted-config",
        locale=None,
    )

    await investigate(
        state,
        _config(
            manager,
            events,
            trusted_context=trusted_context,
            permissions=["tool:search_policy"],
            merchant_scope={"merchant_ids": ["merchant-from-config-legacy"]},
        ),
    )

    # AgentState merchant_scope and permissions must never be authority for tool calls.
    tool_context = manager.calls[0][2]
    assert tool_context.permissions == ["tool:get_order"]
    assert tool_context.merchant_scope == {"schema_version": "merchant_scope.v1", "merchant_ids": ["merchant-from-trusted-config"], "categories": None, "risk_levels": None, "match_rule": "all_provided_dimensions"}
    assert tool_context.trace_id == "trace-from-trusted-config"


@pytest.mark.asyncio
async def test_investigate_events_use_trusted_context_identity_not_agentstate(
    session: AsyncSession,
    seeded_session: dict,
):
    manager = FakeManager({"get_order": _business_success()})
    thread_id = "thread-investigate-trusted-events"
    trusted_run_id = await _insert_run(session, seeded_session, thread_id)
    state = _state([{"next_tool": "get_order", "args": {"order_no": "ORD-001"}, "reason": "test"}])
    state["tenant_id"] = str(uuid4())
    state["user_id"] = str(uuid4())
    state["thread_id"] = "legacy-thread-from-state"
    state["current_run_id"] = str(uuid4())
    trusted_context = TrustedContext(
        tenant_id=str(seeded_session["tenant"].id),
        user_id=str(seeded_session["users"]["cs_zhang"].id),
        role="support",
        permissions=["tool:get_order"],
        merchant_scope=MerchantScopeV1(merchant_ids=["*"]),
        session_id=None,
        thread_id=thread_id,
        run_id=trusted_run_id,
        trace_id="trace-from-trusted-event-context",
        locale=None,
    )

    await investigate(
        state,
        _config(
            manager,
            [],
            session=session,
            event_emitter=None,
            trusted_context=trusted_context.model_dump(mode="json"),
        ),
    )

    rows = (
        (
            await session.execute(
                select(AgentTraceEvent)
                .where(AgentTraceEvent.run_id == trusted_run_id)
                .order_by(AgentTraceEvent.sequence)
            )
        )
        .scalars()
        .all()
    )

    assert [row.event_type for row in rows] == ["tool_call_started", "tool_call_completed"]
    assert {str(row.tenant_id) for row in rows} == {trusted_context.tenant_id}
    assert {row.thread_id for row in rows} == {trusted_context.thread_id}
    assert {row.trace_id for row in rows} == {trusted_context.trace_id}


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
async def test_search_case_memory_tool_result_accumulates_contextual_case_memory():
    events: list[dict[str, Any]] = []
    manager = FakeManager({"search_case_memory": _case_memory_success()})
    plan = [{"next_tool": "search_case_memory", "args": {"query": "refund timeout"}, "reason": "precedent"}]

    result = await investigate(_state(plan), _config(manager, events))

    assert result["case_memory"][0]["case_memory_id"] == "case-memory-1"
    assert result["case_memory"][0]["excerpt"] == "Reviewed refund timeout precedent."
    assert result["case_memory"][0]["policy_refs"] == [{"doc_key": "refund_policy", "chunk_id": "chunk-1"}]
    assert result["policy_evidence"] == []
    assert "raw_tool_payload" not in str(result["case_memory"])
    assert "must-not-leak" not in str(result["case_memory"])


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
    assert "raw_payload" not in str(result["business_context"])


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


# --- Phase 29: investigate ToolPlatform integration (APF-06/APF-07) ---
# RED tests asserting investigate consumes ToolViewV1-only planner surfaces, enforces
# visible-does-not-imply-allowed runtime auth, accumulates projector output only, and
# never calls a compatibility manager's raw descriptors(...) for planner prompt assembly.
# Fail RED until Plan 29-04 rewires investigate onto ToolPlatform.


def _planner_forbidden_tokens() -> set[str]:
    return {
        "ToolDescriptor",
        "create_coupon_grant_draft",
        "side_effect",
        "required_permission",
        "caller_allowlist",
        "event_family",
        "executor",
        "risk_level",
        "exposure",
    }


@pytest.mark.asyncio
async def test_investigate_planner_surface_exposes_only_tool_view_fields():
    from src.tools.platform import ToolPlatform
    from src.tools.contracts import ToolViewV1

    platform = ToolPlatform.with_defaults(session=None)
    ctx = ToolCallContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        role="support",
        permissions=[f"tool:{name}" for name in (
            "get_order", "get_refund_case", "get_ticket", "get_logistics",
            "get_merchant_risk", "search_policy", "search_sop", "search_case_memory",
        )],
        merchant_scope={"merchant_ids": ["*"]},
        session_id=None,
        thread_id="thread-1",
        run_id=str(uuid4()),
        trace_id="trace-1",
        request_id=str(uuid4()),
        tool_call_id="visibility-test",
        caller_node="investigate",
    )
    views = await platform.visible_tools(caller="investigate", ctx=ctx, session=None)

    assert views
    assert all(isinstance(view, ToolViewV1) for view in views)
    blob = str([view.model_dump() for view in views])
    for token in _planner_forbidden_tokens():
        assert token not in blob, f"planner-visible payload must not leak {token!r}"
    assert "create_coupon_grant_draft" not in {view.name for view in views}


@pytest.mark.asyncio
async def test_investigate_visible_tool_still_requires_runtime_auth():
    from src.tools.platform import ToolPlatform
    from src.tools.contracts import ToolInvocationOutcome

    platform = ToolPlatform.with_defaults(session=None)
    ctx = ToolCallContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        role="support",
        permissions=[],  # visible but missing required permission
        merchant_scope={"merchant_ids": ["*"]},
        session_id=None,
        thread_id="thread-1",
        run_id=str(uuid4()),
        trace_id="trace-1",
        request_id=str(uuid4()),
        tool_call_id="runtime-auth-test",
        caller_node="investigate",
    )

    outcome = await platform.invoke("get_order", {"order_no": "ORD-1"}, ctx, session=None)

    assert isinstance(outcome, ToolInvocationOutcome)
    assert outcome.tool_result.status == "permission_denied"
    assert outcome.policy_decision.decision_stage == "runtime_auth"
    assert outcome.policy_decision.decision == "denied"


@pytest.mark.asyncio
async def test_investigate_graph_state_consumes_projection_not_raw_data():
    from src.tools.platform import ToolPlatform

    raw_sentinels = {"raw_payload", "raw_tool_output", "private_reasoning", "secret", "debug_trace"}
    platform = ToolPlatform.with_defaults(session=None)
    result = _business_success_with_raw_payload()
    result.data = {
        "id": "ORD-RAW-001",
        "raw_payload": {"customer_phone": "13800000000"},
        "raw_tool_output": "<upstream>",
        "private_reasoning": "cot",
        "secret": "sk-xxx",
        "debug_trace": "stack",
    }
    projection = platform.projector.project(
        tool_name="get_order", result=result, tool_call_id="tc-1", tool_result_id="tr-1"
    )

    serialized = str(projection.normalized_result) + str(projection.prompt_projection) + str(projection.text_for_prompt)
    for sentinel in raw_sentinels:
        assert sentinel not in serialized


@pytest.mark.asyncio
async def test_investigate_planner_does_not_call_raw_descriptors_when_visible_tools_available():
    # Regression: when ToolPlatform.visible_tools(...) is available, planner prompt/context
    # assembly must not fall back to a compatibility manager's raw descriptors(...).
    from src.tools.platform import ToolPlatform

    class _RaisingDescriptorManager:
        def descriptors(self, caller_node: str = "investigate"):
            raise AssertionError("planner must use ToolPlatform.visible_tools, not raw descriptors(...)")

        def descriptor(self, name: str):
            raise AssertionError("planner must not read raw descriptors")

    events: list[dict[str, Any]] = []
    platform = ToolPlatform.with_defaults(session=None)
    plan = [{"next_tool": "get_order", "args": {"order_no": "ORD-001"}, "reason": "fact"}]
    config = _config(_RaisingDescriptorManager(), events)
    config["configurable"]["tool_platform"] = platform

    # If planner prompt assembly honors visible_tools(...), descriptors(...) is never called
    # and the run proceeds without the AssertionError surfacing as a planner failure.
    result = await investigate(_state(plan), config)
    assert result["termination_reason"] != "unrecoverable_error" or not any(
        "raw descriptors" in str(error) for error in result.get("business_context", {}).get("errors", [])
    )
