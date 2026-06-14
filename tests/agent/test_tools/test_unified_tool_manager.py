from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.agent.events import classify_event_family
from src.tools.executors import (
    ActionToolExecutor,
    BusinessToolExecutor,
    KnowledgeToolExecutor,
    MemoryToolExecutor,
)
from src.tools.catalog import ToolCatalog
from src.tools.contracts import ToolCallContext, ToolResultV2
from src.tools.manager import UnifiedToolManager
from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import EvidenceRefV1, KnowledgeSearchResult
from src.memory.schemas import CaseMemorySearchResult


INVESTIGATE_TOOLS = {
    "get_order",
    "get_refund_case",
    "get_ticket",
    "get_logistics",
    "get_merchant_risk",
    "search_policy",
    "search_sop",
    "search_case_memory",
}


def _ctx(
    *,
    tool: str = "get_order",
    permissions: list[str] | None = None,
    caller_node: str = "investigate",
    idempotency_key: str | None = None,
    merchant_scope: Any | None = None,
) -> ToolCallContext:
    return ToolCallContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        role="support",
        permissions=[f"tool:{name}" for name in INVESTIGATE_TOOLS] if permissions is None else permissions,
        merchant_scope={"merchant_ids": ["*"]} if merchant_scope is None else merchant_scope,
        session_id=None,
        thread_id="thread-1",
        run_id=str(uuid4()),
        trace_id="trace-1",
        request_id=str(uuid4()),
        tool_call_id=str(uuid4()),
        caller_node=caller_node,
        deadline_at=datetime.now(UTC),
        effective_at=datetime.now(UTC).isoformat(),
        attempt=1,
        max_attempts=1,
        idempotency_key=idempotency_key,
        policy_snapshot_ref=None,
    )


class _FakeExecutor:
    def __init__(self, name: str, result: Any) -> None:
        descriptor = next(item for item in ToolCatalog().descriptors() if item.name == name)
        self._tools = {name: descriptor}
        self.result = result
        self.calls: list[tuple[str, dict[str, Any], ToolCallContext]] = []

    def get_tools(self):
        return dict(self._tools)

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext):
        self.calls.append((name, args, ctx))
        return self.result


def _success_result(source_system: str = "fake") -> ToolResultV2:
    return ToolResultV2(
        status="success",
        data={"ok": True},
        summary="ok",
        source_system=source_system,
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=None,
        retryable=False,
        retry_after_ms=None,
        latency_ms=1,
        audit_ref=None,
    )


def test_descriptor_discovery_returns_investigate_allowlist_only():
    manager = UnifiedToolManager()

    descriptors = manager.descriptors("investigate")

    assert {descriptor.name for descriptor in descriptors} == INVESTIGATE_TOOLS
    assert all(descriptor.kind != "write" for descriptor in descriptors)
    assert "create_coupon_grant_draft" not in {descriptor.name for descriptor in descriptors}


def test_descriptor_discovery_uses_business_registry_catalog():
    catalog = {descriptor.name: descriptor.model_dump() for descriptor in ToolCatalog().descriptors()}
    manager = UnifiedToolManager()

    for descriptor in manager.descriptors("investigate"):
        assert descriptor.model_dump() == catalog[descriptor.name]


def test_descriptor_event_family_agrees_with_classifier():
    manager = UnifiedToolManager()

    for descriptor in manager.descriptors("investigate"):
        assert manager.event_family(descriptor.name) == classify_event_family(descriptor.name)


@pytest.mark.asyncio
async def test_invoke_get_order_delegates_to_business_tool_service(monkeypatch):
    called = {}

    async def fake_invoke(self, name, args, ctx):
        del self
        called["value"] = (name, args, ctx.caller_node)
        return _success_result("business_tool_service")

    monkeypatch.setattr("src.business.service.BusinessToolService.invoke_tool", fake_invoke)
    manager = UnifiedToolManager(executors=[BusinessToolExecutor(session=object())])

    result = await manager.invoke("get_order", {"order_no": "ORD-TEST-001"}, _ctx(tool="get_order"))

    assert result.status == "success"
    assert result.source_system == "business_tool_service"
    assert called["value"] == ("get_order", {"order_no": "ORD-TEST-001"}, "investigate")


@pytest.mark.asyncio
async def test_business_service_permission_error_preserves_tool_result_status():
    executor = _FakeExecutor(
        "get_order",
        ToolResultV2(
            status="permission_denied",
            data=None,
            summary="Required tool permission is missing",
            source_system="business_tool_service",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        ),
    )
    manager = UnifiedToolManager(executors=[executor])

    result = await manager.invoke("get_order", {"order_no": "ORD-TEST-001"}, _ctx(tool="get_order"))

    assert result.status == "permission_denied"
    assert result.source_system == "business_tool_service"


@pytest.mark.asyncio
async def test_search_policy_uses_unified_dispatch():
    evidence = EvidenceRefV1.build(
        tenant_id=str(uuid4()),
        doc_key="refund_policy",
        chunk_id="refund_policy#001",
        policy_version="v1",
        text="七天无理由退款规则",
        retrieved_at=datetime.now(UTC).isoformat(),
        retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
        score=0.91,
        rank=1,
    )

    class FakePolicyService:
        async def search(self, request, context):
            assert request.query == "refund policy"
            assert context.merchant_scope == ["*"]
            return KnowledgeSearchResult(
                status="strong_evidence",
                retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
                rerank_config_version=RERANK_CONFIG_VERSION,
                best_score=0.91,
                threshold=0.55,
                evidence_refs=[evidence],
                summary="policy found",
            )

    manager = UnifiedToolManager(executors=[KnowledgeToolExecutor(session=None, service=FakePolicyService())])

    result = await manager.invoke("search_policy", {"query": "refund policy"}, _ctx(tool="search_policy"))

    assert result.status == "success"
    assert result.source_system == "policy_knowledge_service"
    assert result.policy_evidence_refs == [evidence]
    assert result.data["retrieval_status"] == "strong_evidence"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("merchant_scope", "expected_scope"),
    [
        ({"merchant_ids": ["merchant-1"]}, ["merchant-1"]),
        (["merchant-legacy"], ["merchant-legacy"]),
        ({"categories": ["electronics"]}, []),
        ({"merchant_ids": [123]}, []),
        ({}, []),
    ],
)
async def test_search_policy_projects_merchant_scope_for_knowledge_service(merchant_scope, expected_scope):
    class FakePolicyService:
        async def search(self, request, context):
            del request
            assert context.merchant_scope == expected_scope
            return KnowledgeSearchResult(
                status="no_evidence",
                retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
                rerank_config_version=RERANK_CONFIG_VERSION,
                best_score=0.0,
                threshold=0.55,
                evidence_refs=[],
            )

    manager = UnifiedToolManager(executors=[KnowledgeToolExecutor(session=None, service=FakePolicyService())])

    result = await manager.invoke(
        "search_policy",
        {"query": "refund policy"},
        _ctx(tool="search_policy", merchant_scope=merchant_scope),
    )

    assert result.status == "not_found"


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["search_sop", "search_case_memory"])
async def test_declared_future_tools_return_unavailable(tool_name):
    manager = UnifiedToolManager(executors=[KnowledgeToolExecutor(session=None, service=object()), MemoryToolExecutor()])

    result = await manager.invoke(tool_name, {"query": "refund"}, _ctx(tool=tool_name))

    assert result.status == "unavailable"


@pytest.mark.asyncio
async def test_search_case_memory_dispatches_to_memory_search_service():
    class FakeMemorySearchService:
        def __init__(self) -> None:
            self.calls = []

        async def search(self, *, query, context):
            self.calls.append((query, context))
            return CaseMemorySearchResult(
                status="unavailable",
                items=[],
                summary="Case memory search is not available",
                error_code="TOOL_UNAVAILABLE",
            )

    service = FakeMemorySearchService()
    manager = UnifiedToolManager(executors=[MemoryToolExecutor(service=service)])

    result = await manager.invoke("search_case_memory", {"query": "similar refund case"}, _ctx(tool="search_case_memory"))

    assert result.status == "unavailable"
    assert service.calls[0][0] == "similar refund case"


@pytest.mark.asyncio
async def test_unknown_tool_returns_not_found():
    result = await UnifiedToolManager().invoke("unknown_tool", {}, _ctx())

    assert result.status == "not_found"
    assert result.error is not None
    assert "secret" not in result.error.safe_message.lower()


@pytest.mark.asyncio
async def test_write_tool_blocked_before_executor_dispatch():
    executor = _FakeExecutor("create_coupon_grant_draft", _success_result())
    manager = UnifiedToolManager(executors=[executor])

    result = await manager.invoke(
        "create_coupon_grant_draft",
        {"merchant_id": "m1", "amount": 1},
        _ctx(tool="create_coupon_grant_draft", permissions=["tool:create_coupon_grant_draft"]),
    )

    assert result.status == "permission_denied"
    assert executor.calls == []


@pytest.mark.asyncio
async def test_action_tool_requires_idempotency_key():
    executor = _FakeExecutor("create_coupon_grant_draft", _success_result())
    manager = UnifiedToolManager(executors=[executor])

    result = await manager.invoke(
        "create_coupon_grant_draft",
        {"action_type": "issue_coupon", "payload": {"target_id": "refund-1"}},
        _ctx(
            tool="create_coupon_grant_draft",
            caller_node="execute_action",
            permissions=["tool:create_coupon_grant_draft"],
        ),
    )

    assert result.status == "invalid_request"
    assert result.error is not None
    assert result.error.code == "IDEMPOTENCY_KEY_REQUIRED"
    assert executor.calls == []


@pytest.mark.asyncio
async def test_execute_action_caller_can_dispatch_action_tool(monkeypatch):
    draft_id = str(uuid4())

    create_draft = AsyncMock(
        return_value={
            "status": "success",
            "data": {
                "draft_id": draft_id,
                "idempotency_key": "idem-1",
                "status": "draft_created",
                "created": True,
                "idempotent_reused": False,
            },
            "error": {},
        }
    )
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    manager = UnifiedToolManager(executors=[ActionToolExecutor(session=object())])

    result = await manager.invoke(
        "create_coupon_grant_draft",
        {"approval_request_id": str(uuid4()), "action_type": "issue_coupon", "payload": {"target_id": "refund-1"}},
        _ctx(
            tool="create_coupon_grant_draft",
            caller_node="execute_action",
            permissions=["tool:create_coupon_grant_draft"],
            idempotency_key="idem-1",
        ),
    )

    assert result.status == "success"
    assert result.data is not None
    assert result.data["draft_id"] == draft_id
    create_draft.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_permission_returns_permission_denied():
    executor = _FakeExecutor("get_order", _success_result())
    result = await UnifiedToolManager(executors=[executor]).invoke(
        "get_order",
        {"order_no": "ORD-TEST-001"},
        _ctx(permissions=[]),
    )

    assert result.status == "permission_denied"
    assert executor.calls == []


@pytest.mark.asyncio
async def test_invalid_input_returns_invalid_request():
    executor = _FakeExecutor("get_order", _success_result())
    result = await UnifiedToolManager(executors=[executor]).invoke("get_order", {}, _ctx(tool="get_order"))

    assert result.status == "invalid_request"
    assert executor.calls == []


@pytest.mark.asyncio
async def test_malformed_executor_return_becomes_invalid_response():
    manager = UnifiedToolManager(executors=[_FakeExecutor("get_order", {"not": "a ToolResultV2"})])

    result = await manager.invoke("get_order", {"order_no": "ORD-TEST-001"}, _ctx(tool="get_order"))

    assert result.status == "invalid_response"


@pytest.mark.asyncio
async def test_output_schema_failure_returns_invalid_response_without_raw_data():
    raw_sentinel = "RAW-MANAGER-SENTINEL"
    descriptor = next(item for item in ToolCatalog().descriptors() if item.name == "get_order").model_copy(
        update={
            "output_schema": {
                "type": "object",
                "properties": {"order_no": {"type": "string"}},
                "required": ["order_no"],
                "additionalProperties": False,
            }
        }
    )
    executor = _FakeExecutor("get_order", _success_result())
    executor._tools = {"get_order": descriptor}
    executor.result = _success_result()
    executor.result.data = {"unexpected": raw_sentinel}
    manager = UnifiedToolManager(descriptors=[descriptor], executors=[executor])

    result = await manager.invoke("get_order", {"order_no": "ORD-TEST-001"}, _ctx(tool="get_order"))

    assert result.status == "invalid_response"
    assert result.data is None
    assert raw_sentinel not in str(result.model_dump())


@pytest.mark.asyncio
async def test_manager_generated_errors_have_no_raw_payload_or_secret():
    result = await UnifiedToolManager().invoke("missing", {"raw": "secret"}, _ctx())

    assert result.status == "not_found"
    assert result.data is None
    assert result.error is not None
    assert "secret" not in result.summary.lower()
    assert "raw" not in result.error.safe_message.lower()
