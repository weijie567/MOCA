from __future__ import annotations

from typing import Any, Protocol, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.events import classify_event_family
from src.business_tools.registry import ToolDescriptor, ToolRegistry, _validate_json_value
from src.business_tools.schemas import ToolCallContext, ToolError, ToolResultV2
from src.business_tools.service import BusinessToolService
from src.knowledge.adapters import LegacyRagKnowledgeAdapter
from src.knowledge.config import RERANK_CONFIG_VERSION, RETRIEVAL_CONFIG_VERSION
from src.knowledge.schemas import KnowledgeContext, KnowledgeSearchFilters, KnowledgeSearchRequest
from src.knowledge.service import PolicyKnowledgeService


INVESTIGATE_TOOL_NAMES = {
    "get_order",
    "get_refund_case",
    "get_ticket",
    "get_logistics",
    "get_merchant_risk",
    "search_policy",
    "search_sop",
    "search_case_memory",
}
BUSINESS_TOOL_NAMES = {"get_order", "get_refund_case", "get_ticket", "get_logistics", "get_merchant_risk"}
KNOWLEDGE_TOOL_NAMES = {"search_policy", "search_sop"}
MEMORY_TOOL_NAMES = {"search_case_memory"}


class ToolExecutor(Protocol):
    def get_tools(self) -> dict[str, ToolDescriptor]: ...

    def has_tool(self, name: str) -> bool: ...

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2: ...


class BusinessToolExecutor:
    def __init__(self, session: AsyncSession) -> None:
        self.service = BusinessToolService.with_default_registry(session)
        self._descriptors = {
            descriptor.name: descriptor
            for descriptor in ToolRegistry().descriptors()
            if descriptor.name in BUSINESS_TOOL_NAMES
        }

    def get_tools(self) -> dict[str, ToolDescriptor]:
        return dict(self._descriptors)

    def has_tool(self, name: str) -> bool:
        return name in self._descriptors

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        return await self.service.invoke_tool(name, args, ctx)


class KnowledgeToolExecutor:
    def __init__(
        self,
        session: AsyncSession,
        service: PolicyKnowledgeService | None = None,
    ) -> None:
        self.service = service or PolicyKnowledgeService(LegacyRagKnowledgeAdapter(session))
        self._descriptors = {
            descriptor.name: descriptor
            for descriptor in ToolRegistry().descriptors()
            if descriptor.name in KNOWLEDGE_TOOL_NAMES
        }

    def get_tools(self) -> dict[str, ToolDescriptor]:
        return dict(self._descriptors)

    def has_tool(self, name: str) -> bool:
        return name == "search_policy"

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        if name != "search_policy":
            return _result(
                "unavailable",
                "Tool is declared but unavailable",
                code="TOOL_UNAVAILABLE",
                source="tool",
                source_system="knowledge_tool_executor",
            )

        request = KnowledgeSearchRequest(
            query=str(args["query"]),
            primary_intent=args.get("primary_intent"),
            filters=KnowledgeSearchFilters(
                tenant_id=ctx.tenant_id,
                merchant_id=args.get("merchant_id"),
                effective_at=ctx.deadline_at.isoformat() if ctx.deadline_at else None,
                locale=None,
            ),
            retrieval_config_version=RETRIEVAL_CONFIG_VERSION,
            rerank_config_version=RERANK_CONFIG_VERSION,
            max_results=int(args.get("max_results") or 5),
            allow_partial_evidence=bool(args.get("allow_partial_evidence", True)),
        )
        result = await self.service.search(
            request,
            KnowledgeContext(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                role=ctx.role,
                merchant_scope=_knowledge_merchant_scope(ctx.merchant_scope),
                run_id=ctx.run_id,
                trace_id=ctx.trace_id,
                locale=None,
                effective_at=ctx.deadline_at.isoformat() if ctx.deadline_at else "",
            ),
        )
        status_map = {
            "strong_evidence": "success",
            "partial_evidence": "success",
            "no_evidence": "not_found",
            "error": "error",
        }
        error = None
        if result.error:
            error = ToolError(
                code=str(result.error.get("error_code") or "KNOWLEDGE_SEARCH_ERROR"),
                safe_message=str(result.error.get("message") or "Policy search failed"),
                retryable=bool(result.error.get("retryable", False)),
                source="upstream",
            )
        return ToolResultV2(
            status=status_map[result.status],
            data={
                "retrieval_status": result.status,
                "best_score": result.best_score,
                "threshold": result.threshold,
                "summary": result.summary,
            },
            summary=result.summary or f"Policy search returned {result.status}",
            source_system="policy_knowledge_service",
            data_freshness_at=None,
            policy_evidence_refs=result.evidence_refs,
            business_fact_refs=[],
            error=error,
            retryable=bool(error.retryable) if error else False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )


class MemoryToolExecutor:
    def __init__(self) -> None:
        self._descriptors = {
            descriptor.name: descriptor
            for descriptor in ToolRegistry().descriptors()
            if descriptor.name in MEMORY_TOOL_NAMES
        }

    def get_tools(self) -> dict[str, ToolDescriptor]:
        return dict(self._descriptors)

    def has_tool(self, name: str) -> bool:
        return False

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        del name, args, ctx
        return _result(
            "unavailable",
            "Tool is declared but unavailable",
            code="TOOL_UNAVAILABLE",
            source="tool",
            source_system="memory_tool_executor",
        )


class UnifiedToolManager:
    def __init__(
        self,
        *,
        descriptors: list[ToolDescriptor] | None = None,
        executors: list[ToolExecutor] | None = None,
    ) -> None:
        catalog = descriptors if descriptors is not None else ToolRegistry().descriptors()
        self._descriptors = {descriptor.name: descriptor for descriptor in catalog}
        self._executors = executors or []

    @classmethod
    def with_defaults(cls, session: AsyncSession) -> UnifiedToolManager:
        return cls(
            executors=[
                BusinessToolExecutor(session),
                KnowledgeToolExecutor(session),
                MemoryToolExecutor(),
            ]
        )

    def descriptors(self, caller_node: str = "investigate") -> list[ToolDescriptor]:
        return [
            descriptor
            for descriptor in self._descriptors.values()
            if caller_node in descriptor.caller_allowlist
            and descriptor.name in INVESTIGATE_TOOL_NAMES
            and descriptor.kind != "write"
        ]

    def descriptor(self, name: str) -> ToolDescriptor | None:
        return self._descriptors.get(name)

    async def invoke(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        descriptor = self._descriptors.get(name)
        if descriptor is None:
            return _result("not_found", "Requested tool is not registered", code="TOOL_NOT_FOUND", source="caller")
        if ctx.caller_node not in descriptor.caller_allowlist:
            return _result("permission_denied", "Caller is not allowed to invoke this tool", code="CALLER_NOT_ALLOWED")
        if descriptor.kind == "write" or descriptor.side_effect not in {"read_only", "retrieval"}:
            return _result("permission_denied", "Write tools cannot execute from investigate", code="WRITE_TOOL_BLOCKED")
        if descriptor.required_permission not in ctx.permissions:
            return _result("permission_denied", "Required tool permission is missing", code="PERMISSION_REQUIRED")

        try:
            _validate_json_value(args, descriptor.input_schema)
        except (TypeError, ValueError):
            return _result("invalid_request", "Tool input failed validation", code="INVALID_TOOL_INPUT")

        executor = self._executor_for(name)
        if executor is None or not executor.has_tool(name):
            return _result("unavailable", "Tool is declared but unavailable", code="TOOL_UNAVAILABLE", source="tool")

        try:
            result = await executor.execute(name, args, ctx)
        except Exception:
            return _result("error", "Tool executor failed", code="EXECUTOR_ERROR", source="adapter")
        if not isinstance(result, ToolResultV2):
            return _result("invalid_response", "Tool executor returned an invalid response", code="INVALID_EXECUTOR_RESPONSE", source="adapter")
        return result

    def event_family(self, name: str) -> str:
        descriptor = self._descriptors.get(name)
        if descriptor and descriptor.event_family == "tool_call_*":
            return "tool_call"
        if descriptor and descriptor.event_family == "rag_retrieval_*":
            return "rag_retrieval"
        return classify_event_family(name)

    def _executor_for(self, name: str) -> ToolExecutor | None:
        for executor in self._executors:
            if name in executor.get_tools():
                return executor
        return None


def _knowledge_merchant_scope(value: object) -> list[str]:
    raw_ids: object = value.get("merchant_ids") if isinstance(value, dict) else value
    if not isinstance(raw_ids, list) or not raw_ids:
        return []
    if not all(isinstance(item, str) and item for item in raw_ids):
        return []
    return list(raw_ids)


def _result(
    status: Literal["not_found", "permission_denied", "unavailable", "invalid_request", "invalid_response", "error"],
    summary: str,
    *,
    code: str,
    source: Literal["caller", "tool", "adapter"] = "caller",
    source_system: str = "unified_tool_manager",
) -> ToolResultV2:
    return ToolResultV2(
        status=status,
        data=None,
        summary=summary,
        source_system=source_system,
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=ToolError(code=code, safe_message=summary, retryable=False, source=source),
        retryable=False,
        retry_after_ms=None,
        latency_ms=0,
        audit_ref=None,
    )
