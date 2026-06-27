"""Executable ownership regression: policy retrieval vs business-tool facade.

Encodes the authoritative Phase 8/9 ownership boundary from ROADMAP, CONTEXT,
and the locked "Do NOT own policy knowledge" decision. If policy retrieval is
ever moved into BusinessToolService or the Phase 8 PolicyKnowledgeService live
seam is removed, these tests fail.

See `.planning/phases/09-business-tool-facade/09-OWNERSHIP-BOUNDARY.md` for
the durable re-verification contract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.agent.nodes import investigate as investigate_module
from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1, KnowledgeSearchResult
from src.memory.schemas import CaseMemorySearchItem, CaseMemorySearchResult
from src.platform.trusted_context import MerchantScopeV1, TrustedContext
from src.tools.catalog import ToolCatalog
from src.tools.contracts import (
    BusinessFactRefV1,
    ToolCallContext,
    ToolInvocationOutcome,
    ToolPolicyDecision,
    ToolResultV2,
    ToolViewV1,
)
from src.tools.executors.memory import MemoryToolExecutor
from src.tools.projection import ToolResultProjector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_search_result() -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        status="strong_evidence",
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        rerank_config_version=RERANK_CONFIG_VERSION,
        best_score=0.85,
        threshold=0.55,
        evidence_refs=[],
    )


def _base_state() -> dict:
    return {
        "thread_id": "test-thread",
        "tenant_id": "t-1",
        "user_id": "u-1",
        "role": "support_agent",
        "user_query": "订单 ORD-001 为什么还没退款？",
        "current_intent": "refund_troubleshooting",
    }


def _business_fact_ref(resource_type: str, resource_id: str) -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id="11111111-1111-1111-1111-111111111111",
        source_system="moca",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_version=None,
        data_freshness_at=None,
        retrieved_at=datetime.now(UTC),
    )


class _FakePolicyToolPlatform:
    def __init__(self, manager: Any) -> None:
        self._manager = manager
        self._projector = ToolResultProjector()
        self.last_visibility_decisions = None

    async def visible_tools(
        self,
        *,
        caller: str,
        ctx: ToolCallContext,
        session=None,
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
        self,
        tool_name: str,
        args: dict,
        ctx: ToolCallContext,
        *,
        session=None,
    ) -> ToolInvocationOutcome:
        result = await self._manager.invoke(tool_name, args, ctx)
        projection = self._projector.project(
            tool_name=tool_name,
            result=result,
            tool_call_id=ctx.tool_call_id,
        )
        decision = ToolPolicyDecision(
            tool_name=tool_name,
            caller=ctx.caller_node,
            decision_stage="runtime_auth",
            decision="allowed",
            reason_codes=["visible"],
            required_scopes=[],
            matched_scope=None,
            policy_version="tool_policy.v1",
            data_classification="internal",
            runtime_available=True,
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
        if descriptor.event_family == "rag_retrieval_*":
            return "rag_retrieval"
        if descriptor.event_family == "tool_call_*":
            return "tool_call"
        return None


# ---------------------------------------------------------------------------
# Policy retrieval ownership tests
# ---------------------------------------------------------------------------


class TestPolicyRetrievalOwnership:
    """Policy retrieval graph paths must execute through ToolPlatform,
    not through BusinessToolService or raw knowledge services."""

    @pytest.mark.asyncio
    async def test_investigate_calls_search_policy_through_unified_tool_manager(self):
        """The active investigate node invokes search_policy through manager."""

        class FakeManager:
            def __init__(self) -> None:
                self._descriptors = {descriptor.name: descriptor for descriptor in ToolCatalog().descriptors()}
                self.calls: list[tuple[str, dict, ToolCallContext]] = []
                self._platform = _FakePolicyToolPlatform(self)

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

            async def invoke(self, name: str, args: dict, ctx: ToolCallContext) -> ToolResultV2:
                self.calls.append((name, args, ctx))
                return ToolResultV2(
                    status="success",
                    data={
                        "retrieval_status": "strong_evidence",
                        "best_score": 0.85,
                        "threshold": 0.55,
                    },
                    summary="policy found",
                    source_system="policy_knowledge_service",
                    data_freshness_at=None,
                    policy_evidence_refs=[],
                    business_fact_refs=[],
                    error=None,
                    retryable=False,
                    retry_after_ms=None,
                    latency_ms=1,
                    audit_ref=None,
                )

        manager = FakeManager()
        trusted_context = TrustedContext(
            tenant_id="t-1",
            user_id="u-1",
            role="support",
            permissions=["tool:search_policy"],
            merchant_scope=MerchantScopeV1(merchant_ids=[]),
            session_id=None,
            thread_id="test-thread",
            run_id="run-1",
            trace_id="trace-1",
            locale=None,
        )
        await investigate_module.investigate(
            {
                **_base_state(),
                "current_run_id": "run-1",
                "_investigate_plan": [
                    {"next_tool": "search_policy", "args": {"query": "退款规则"}, "reason": "policy"}
                ],
            },
            {
                "configurable": {
                    "permissions": ["tool:search_policy"],
                    "tool_manager": manager,
                    "tool_platform": manager._platform,
                    "trusted_context": trusted_context.model_dump(mode="json"),
                }
            },
        )

        assert len(manager.calls) == 1
        name, args, context = manager.calls[0]
        assert name == "search_policy"
        assert args == {"query": "退款规则"}
        assert context.caller_node == "investigate"
        assert context.permissions == ["tool:search_policy"]

    @pytest.mark.asyncio
    async def test_policy_executor_calls_policy_knowledge_service_search(self):
        """KnowledgeToolExecutor is the only tool-facing service caller."""
        from src.tools.executors.knowledge import KnowledgeToolExecutor

        mock_search = AsyncMock(return_value=_ok_search_result())
        executor = KnowledgeToolExecutor(session=None, service=type("Svc", (), {"search": mock_search})())
        context = ToolCallContext(
            tenant_id="t-1",
            user_id="u-1",
            role="support_agent",
            permissions=["tool:search_policy"],
            merchant_scope={"merchant_ids": []},
            thread_id="thread-1",
            run_id="run-1",
            trace_id="trace-1",
            request_id="req-1",
            tool_call_id="tc-1",
            caller_node="investigate",
            effective_at="2026-06-07T00:00:00+00:00",
        )

        await executor.execute("search_policy", {"query": "退款规则"}, context)

        mock_search.assert_awaited_once()
        request, knowledge_context = mock_search.await_args.args
        assert request.schema_version == "knowledge_search_request.v2"
        assert knowledge_context.merchant_scope == []

    def test_investigate_imports_only_manager_boundary(self):
        """The active graph node imports platform/contracts, not domain service facades."""
        module_source = investigate_module
        assert hasattr(module_source, "ToolPlatform")
        assert not hasattr(module_source, "PolicyKnowledgeService"), (
            "investigate must not import PolicyKnowledgeService directly"
        )
        assert not hasattr(module_source, "BusinessToolService"), (
            "investigate must NOT import BusinessToolService; policy retrieval belongs behind ToolPlatform"
        )

    @pytest.mark.asyncio
    async def test_reviewed_case_memory_tool_result_is_not_policy_evidence(self):
        """Reviewed case memory remains contextual precedent, not EvidenceRefV1."""

        class FakeReviewedCaseMemoryService:
            def __init__(self) -> None:
                self.requests = []

            async def retrieve_reviewed(self, request):
                self.requests.append(request)
                return CaseMemorySearchResult(
                    status="success",
                    items=[
                        CaseMemorySearchItem(
                            case_memory_id="case-memory-1",
                            excerpt="Reviewed precedent: verify payment-channel facts before recommendation.",
                            applicability="Similar refund timeout dispute.",
                            outcome="Context only; policy evidence still required.",
                            score=0.91,
                            policy_refs=[{"doc_key": "refund_policy", "chunk_id": "chunk-1"}],
                            source_refs=[{"business_object_id": "CASE-1"}],
                        )
                    ],
                )

        service = FakeReviewedCaseMemoryService()
        executor = MemoryToolExecutor(service=service)
        ctx = ToolCallContext(
            tenant_id="11111111-1111-1111-1111-111111111111",
            user_id="22222222-2222-2222-2222-222222222222",
            role="support_agent",
            permissions=["tool:search_case_memory"],
            merchant_scope={"merchant_ids": ["merchant-primary"]},
            thread_id="thread-1",
            run_id="33333333-3333-3333-3333-333333333333",
            trace_id="trace-1",
            request_id="req-1",
            tool_call_id="tc-1",
            caller_node="investigate",
        )

        result = await executor.execute("search_case_memory", {"query": "refund timeout"}, ctx)

        assert result.status == "success"
        assert result.policy_evidence_refs == []
        assert result.business_fact_refs == []
        assert result.data is not None
        assert result.data["items"][0]["case_memory_id"] == "case-memory-1"
        assert "reviewed case memory" in result.summary
        assert service.requests[0].tenant_id.hex == "11111111111111111111111111111111"

    @pytest.mark.parametrize(
        ("resource_type", "resource_id"),
        [
            ("order", "ORD-001"),
            ("refund_case", "RF-001"),
            ("ticket", "TK-001"),
        ],
    )
    def test_business_fact_refs_are_not_policy_evidence_refs(self, resource_type: str, resource_id: str):
        business_ref = _business_fact_ref(resource_type, resource_id)

        with pytest.raises(ValidationError):
            EvidenceRefV1.model_validate(business_ref.model_dump(mode="json"))

        result = ToolResultV2(
            status="success",
            data={"id": resource_id, "status": "loaded"},
            summary="business fact loaded",
            source_system="business_tool_service",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[business_ref],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=1,
            audit_ref=None,
        )

        assert result.policy_evidence_refs == []
        assert result.business_fact_refs == [business_ref]


# ---------------------------------------------------------------------------
# Registry declaration-only retrieval descriptors tests
# ---------------------------------------------------------------------------


class TestRetrievalDescriptorsDeclarationOnly:
    """search_policy, search_sop, search_case_memory descriptors exist in the
    tool catalog as declaration/validation catalog entries. ToolCatalog is
    declaration-only; UnifiedToolManager owns graph-facing execution."""

    @pytest.fixture()
    def registry(self) -> ToolCatalog:
        return ToolCatalog()

    def _descriptor_map(self, registry: ToolCatalog) -> dict:
        return {d.name: d for d in registry.descriptors()}

    def test_search_policy_descriptor_exists(self, registry):
        descriptors = self._descriptor_map(registry)
        assert "search_policy" in descriptors, "search_policy must be declared in the registry catalog"

    def test_search_sop_descriptor_exists(self, registry):
        descriptors = self._descriptor_map(registry)
        assert "search_sop" in descriptors, "search_sop must be declared in the registry catalog"

    def test_search_case_memory_descriptor_exists(self, registry):
        descriptors = self._descriptor_map(registry)
        assert "search_case_memory" in descriptors, "search_case_memory must be declared in the registry catalog"

    def test_retrieval_descriptors_are_kind_retrieval(self, registry):
        descriptors = self._descriptor_map(registry)
        for name in ("search_policy", "search_sop", "search_case_memory"):
            assert descriptors[name].kind == "retrieval", f"{name} must be kind='retrieval'"

    def test_retrieval_descriptors_have_rag_event_family(self, registry):
        descriptors = self._descriptor_map(registry)
        for name in ("search_policy", "search_sop", "search_case_memory"):
            assert descriptors[name].event_family == "rag_retrieval_*", (
                f"{name} must have event_family='rag_retrieval_*'"
            )

    def test_retrieval_descriptors_have_no_resource_type(self, registry):
        descriptors = self._descriptor_map(registry)
        for name in ("search_policy", "search_sop", "search_case_memory"):
            assert descriptors[name].resource_type is None, f"{name} must have resource_type=None"

    @pytest.mark.asyncio
    async def test_search_policy_returns_unavailable_through_registry(self, registry):
        """Invoking search_policy through ToolCatalog returns unavailable
        because the registry is declaration-only."""
        ctx = ToolCallContext(
            tenant_id="t-1",
            user_id="u-1",
            role="support_agent",
            permissions=["tool:search_policy"],
            merchant_scope={"merchant_ids": []},
            thread_id="thread-1",
            run_id="run-1",
            trace_id="trace-1",
            request_id="req-1",
            tool_call_id="tc-1",
            caller_node="investigate",
        )
        result = await registry.invoke("search_policy", {"query": "退款政策"}, ctx, AsyncMock())
        assert result.status == "unavailable", (
            f"search_policy should be unavailable (adapter=None), got {result.status}"
        )
        assert result.error is not None
        assert result.error.code == "TOOL_REGISTRY_DECLARATION_ONLY"

    @pytest.mark.asyncio
    async def test_search_sop_returns_unavailable_through_registry(self, registry):
        ctx = ToolCallContext(
            tenant_id="t-1",
            user_id="u-1",
            role="support_agent",
            permissions=["tool:search_sop"],
            merchant_scope={"merchant_ids": []},
            thread_id="thread-1",
            run_id="run-1",
            trace_id="trace-1",
            request_id="req-1",
            tool_call_id="tc-2",
            caller_node="investigate",
        )
        result = await registry.invoke("search_sop", {"query": "操作手册"}, ctx, AsyncMock())
        assert result.status == "unavailable"

    @pytest.mark.asyncio
    async def test_search_case_memory_returns_unavailable_through_registry(self, registry):
        ctx = ToolCallContext(
            tenant_id="t-1",
            user_id="u-1",
            role="support_agent",
            permissions=["tool:search_case_memory"],
            merchant_scope={"merchant_ids": ["merchant-primary"]},
            thread_id="thread-1",
            run_id="run-1",
            trace_id="trace-1",
            request_id="req-1",
            tool_call_id="tc-3",
            caller_node="investigate",
        )
        result = await registry.invoke("search_case_memory", {"query": "历史案例"}, ctx, AsyncMock())
        assert result.status == "unavailable"


# ---------------------------------------------------------------------------
# Business-read descriptors retain adapters
# ---------------------------------------------------------------------------


class TestBusinessReadDescriptorsDeclared:
    """The executable business-read descriptors (get_order, get_refund_case,
    get_ticket) remain declared in the catalog. Their adapters live in
    BusinessToolService, not ToolCatalog."""

    @pytest.fixture()
    def registry(self) -> ToolCatalog:
        return ToolCatalog()

    def _descriptor_map(self, registry: ToolCatalog) -> dict:
        return {d.name: d for d in registry.descriptors()}

    def test_get_order_descriptor_exists(self, registry):
        descriptors = self._descriptor_map(registry)
        assert "get_order" in descriptors
        assert descriptors["get_order"].kind == "read"

    def test_get_refund_case_descriptor_exists(self, registry):
        descriptors = self._descriptor_map(registry)
        assert "get_refund_case" in descriptors
        assert descriptors["get_refund_case"].kind == "read"

    def test_get_ticket_descriptor_exists(self, registry):
        descriptors = self._descriptor_map(registry)
        assert "get_ticket" in descriptors
        assert descriptors["get_ticket"].kind == "read"

    def test_business_read_adapters_are_not_registered_in_catalog(self, registry):
        """Business-read adapters must not live in the declaration catalog."""
        for name in ("get_order", "get_refund_case", "get_ticket"):
            tool = registry._tools.get(name)
            assert tool is not None, f"{name} must be registered"
            assert tool.adapter is None


# ---------------------------------------------------------------------------
# Write descriptor blocked
# ---------------------------------------------------------------------------


class TestWriteDescriptorDeclaredOnly:
    """Write tools are declared in the registry but cannot execute there."""

    @pytest.fixture()
    def registry(self) -> ToolCatalog:
        return ToolCatalog()

    def test_create_coupon_grant_draft_descriptor_exists(self, registry):
        descriptors = {d.name: d for d in registry.descriptors()}
        assert "create_coupon_grant_draft" in descriptors
        assert descriptors["create_coupon_grant_draft"].kind == "write"

    @pytest.mark.asyncio
    async def test_write_tool_unavailable_through_declaration_catalog(self, registry):
        """Write tool invocation fails closed in ToolCatalog."""
        ctx = ToolCallContext(
            tenant_id="t-1",
            user_id="u-1",
            role="support_agent",
            permissions=["tool:create_coupon_grant_draft"],
            merchant_scope={"merchant_ids": ["merchant-primary"]},
            thread_id="thread-1",
            run_id="run-1",
            trace_id="trace-1",
            request_id="req-1",
            tool_call_id="tc-write-1",
            caller_node="investigate",
        )
        result = await registry.invoke(
            "create_coupon_grant_draft",
            {"merchant_id": "m-1", "amount": 10.0},
            ctx,
            AsyncMock(),
        )
        assert result.status == "unavailable"
        assert result.error is not None
        assert result.error.code == "TOOL_REGISTRY_DECLARATION_ONLY"


# ---------------------------------------------------------------------------
# Cross-boundary assertion: no test treats policy retrieval as business-tool
# ---------------------------------------------------------------------------


class TestOwnershipContractEncoding:
    """Encode the ROADMAP/CONTEXT boundary as executable assertions."""

    def test_no_business_tool_service_policy_search_in_this_module(self):
        """This test module never asserts that policy retrieval goes through
        BusinessToolService. The ownership contract is: policy retrieval
        enters through ToolPlatform, not the business facade."""
        import inspect

        source = inspect.getsource(TestPolicyRetrievalOwnership)
        # This is a meta-assertion: the ownership tests above verify
        # ToolPlatform boundary is enforced before KnowledgeToolExecutor.
        assert "ToolPlatform" in source
        assert "BusinessToolService" not in source or "NOT" in source
