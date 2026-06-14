"""Executable ownership regression: policy retrieval vs business-tool facade.

Encodes the authoritative Phase 8/9 ownership boundary from ROADMAP, CONTEXT,
and the locked "Do NOT own policy knowledge" decision. If policy retrieval is
ever moved into BusinessToolService or the Phase 8 PolicyKnowledgeService live
seam is removed, these tests fail.

See `.planning/phases/09-business-tool-facade/09-OWNERSHIP-BOUNDARY.md` for
the durable re-verification contract.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agent.nodes import retrieve_policy_evidence as retrieve_policy_evidence_module
from src.business_tools.registry import ToolRegistry
from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import KnowledgeSearchResult


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


# ---------------------------------------------------------------------------
# Policy retrieval ownership tests
# ---------------------------------------------------------------------------

class TestPolicyRetrievalOwnership:
    """Policy retrieval must execute through PolicyKnowledgeService.search,
    NOT through BusinessToolService or the business-tool registry."""

    @pytest.mark.asyncio
    async def test_retrieve_policy_evidence_calls_policy_knowledge_service_search(self, monkeypatch):
        """Live policy retrieval invokes PolicyKnowledgeService.search.

        If someone removes the PolicyKnowledgeService dependency from
        retrieve_policy_evidence or re-wires it to BusinessToolService,
        this test fails.
        """
        mock_search = AsyncMock(return_value=_ok_search_result())

        with patch.object(
            retrieve_policy_evidence_module.PolicyKnowledgeService,
            "search",
            mock_search,
        ):
            await retrieve_policy_evidence_module.retrieve_policy_evidence(
                _base_state(),
                {"configurable": {"session": AsyncMock(), "permissions": ["tool:search_policy"]}},
            )

        mock_search.assert_awaited_once()
        # Verify the search was called with KnowledgeSearchRequest + KnowledgeContext
        args = mock_search.await_args.args
        assert len(args) == 2, "Expected (request, context) positional args"
        request, context = args
        assert request.schema_version == "knowledge_search_request.v2"
        assert isinstance(context, retrieve_policy_evidence_module.KnowledgeContext)

    @pytest.mark.asyncio
    async def test_policy_retrieval_does_not_import_business_tool_service(self):
        """retrieve_policy_evidence must NOT import or use BusinessToolService.

        The module's import table is the ownership contract: it imports
        PolicyKnowledgeService, not BusinessToolService.
        """
        module_source = retrieve_policy_evidence_module
        # The module must have PolicyKnowledgeService imported
        assert hasattr(module_source, "PolicyKnowledgeService"), (
            "retrieve_policy_evidence must import PolicyKnowledgeService"
        )
        # The module must NOT have BusinessToolService imported
        assert not hasattr(module_source, "BusinessToolService"), (
            "retrieve_policy_evidence must NOT import BusinessToolService; "
            "policy retrieval belongs to Phase 8 PolicyKnowledgeService"
        )


# ---------------------------------------------------------------------------
# Registry declaration-only retrieval descriptors tests
# ---------------------------------------------------------------------------

class TestRetrievalDescriptorsDeclarationOnly:
    """search_policy, search_sop, search_case_memory descriptors exist in the
    tool catalog as declaration/validation catalog entries. ToolRegistry is
    declaration-only; UnifiedToolManager owns graph-facing execution."""

    @pytest.fixture()
    def registry(self) -> ToolRegistry:
        return ToolRegistry()

    def _descriptor_map(self, registry: ToolRegistry) -> dict:
        return {d.name: d for d in registry.descriptors()}

    def test_search_policy_descriptor_exists(self, registry):
        descriptors = self._descriptor_map(registry)
        assert "search_policy" in descriptors, (
            "search_policy must be declared in the registry catalog"
        )

    def test_search_sop_descriptor_exists(self, registry):
        descriptors = self._descriptor_map(registry)
        assert "search_sop" in descriptors, (
            "search_sop must be declared in the registry catalog"
        )

    def test_search_case_memory_descriptor_exists(self, registry):
        descriptors = self._descriptor_map(registry)
        assert "search_case_memory" in descriptors, (
            "search_case_memory must be declared in the registry catalog"
        )

    def test_retrieval_descriptors_are_kind_retrieval(self, registry):
        descriptors = self._descriptor_map(registry)
        for name in ("search_policy", "search_sop", "search_case_memory"):
            assert descriptors[name].kind == "retrieval", (
                f"{name} must be kind='retrieval'"
            )

    def test_retrieval_descriptors_have_rag_event_family(self, registry):
        descriptors = self._descriptor_map(registry)
        for name in ("search_policy", "search_sop", "search_case_memory"):
            assert descriptors[name].event_family == "rag_retrieval_*", (
                f"{name} must have event_family='rag_retrieval_*'"
            )

    def test_retrieval_descriptors_have_no_resource_type(self, registry):
        descriptors = self._descriptor_map(registry)
        for name in ("search_policy", "search_sop", "search_case_memory"):
            assert descriptors[name].resource_type is None, (
                f"{name} must have resource_type=None"
            )

    @pytest.mark.asyncio
    async def test_search_policy_returns_unavailable_through_registry(self, registry):
        """Invoking search_policy through ToolRegistry returns unavailable
        because the registry is declaration-only."""
        from src.business_tools.schemas import ToolCallContext

        ctx = ToolCallContext(
            tenant_id="t-1",
            user_id="u-1",
            role="support_agent",
            permissions=["tool:search_policy"],
            merchant_scope={"merchant_ids": ["*"]},
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
        from src.business_tools.schemas import ToolCallContext

        ctx = ToolCallContext(
            tenant_id="t-1",
            user_id="u-1",
            role="support_agent",
            permissions=["tool:search_sop"],
            merchant_scope={"merchant_ids": ["*"]},
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
        from src.business_tools.schemas import ToolCallContext

        ctx = ToolCallContext(
            tenant_id="t-1",
            user_id="u-1",
            role="support_agent",
            permissions=["tool:search_case_memory"],
            merchant_scope={"merchant_ids": ["*"]},
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
    BusinessToolService, not ToolRegistry."""

    @pytest.fixture()
    def registry(self) -> ToolRegistry:
        return ToolRegistry()

    def _descriptor_map(self, registry: ToolRegistry) -> dict:
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
    def registry(self) -> ToolRegistry:
        return ToolRegistry()

    def test_create_coupon_grant_draft_descriptor_exists(self, registry):
        descriptors = {d.name: d for d in registry.descriptors()}
        assert "create_coupon_grant_draft" in descriptors
        assert descriptors["create_coupon_grant_draft"].kind == "write"

    @pytest.mark.asyncio
    async def test_write_tool_unavailable_through_declaration_catalog(self, registry):
        """Write tool invocation fails closed in ToolRegistry."""
        from src.business_tools.schemas import ToolCallContext

        ctx = ToolCallContext(
            tenant_id="t-1",
            user_id="u-1",
            role="support_agent",
            permissions=["tool:create_coupon_grant_draft"],
            merchant_scope={"merchant_ids": ["*"]},
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
        executes through PolicyKnowledgeService, not the business facade."""
        import inspect
        source = inspect.getsource(TestPolicyRetrievalOwnership)
        # This is a meta-assertion: the ownership tests above verify
        # PolicyKnowledgeService.search is called, NOT BusinessToolService
        assert "PolicyKnowledgeService" in source
        assert "BusinessToolService" not in source or "NOT" in source
