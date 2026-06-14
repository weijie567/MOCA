from __future__ import annotations

from time import perf_counter
from typing import Any, Protocol, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.events import classify_event_family
from src.agent.tools.create_coupon_grant_draft import create_coupon_grant_draft
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
ACTION_TOOL_NAMES = {"create_coupon_grant_draft"}


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


class ActionToolExecutor:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._descriptors = {
            descriptor.name: descriptor
            for descriptor in ToolRegistry().descriptors()
            if descriptor.name in ACTION_TOOL_NAMES
        }

    def get_tools(self) -> dict[str, ToolDescriptor]:
        return dict(self._descriptors)

    def has_tool(self, name: str) -> bool:
        return name == "create_coupon_grant_draft"

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        if name != "create_coupon_grant_draft":
            return _result(
                "unavailable",
                "Tool is declared but unavailable",
                code="TOOL_UNAVAILABLE",
                source="tool",
                source_system="action_tool_executor",
            )

        started_at = perf_counter()
        raw_result = await create_coupon_grant_draft(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            run_id=ctx.run_id,
            approval_request_id=args.get("approval_request_id"),
            idempotency_key=ctx.idempotency_key or "",
            action_type=str(args["action_type"]),
            payload=dict(args["payload"]),
            session=self.session,
        )
        return _action_result(raw_result, started_at)


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
                ActionToolExecutor(session),
            ]
        )

    def descriptors(self, caller_node: str = "investigate") -> list[ToolDescriptor]:
        if caller_node == "investigate":
            return [
                descriptor
                for descriptor in self._descriptors.values()
                if caller_node in descriptor.caller_allowlist
                and descriptor.name in INVESTIGATE_TOOL_NAMES
                and descriptor.kind != "write"
                and descriptor.exposure == "planner_visible"
            ]
        return [descriptor for descriptor in self._descriptors.values() if caller_node in descriptor.caller_allowlist]

    def descriptor(self, name: str) -> ToolDescriptor | None:
        return self._descriptors.get(name)

    async def invoke(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        descriptor = self._descriptors.get(name)
        if descriptor is None:
            return _result("not_found", "Requested tool is not registered", code="TOOL_NOT_FOUND", source="caller")
        if ctx.caller_node not in descriptor.caller_allowlist:
            return _result("permission_denied", "Caller is not allowed to invoke this tool", code="CALLER_NOT_ALLOWED")
        if not _side_effect_allowed(ctx.caller_node, descriptor):
            return _result("permission_denied", "Caller is not allowed to execute this tool side effect", code="SIDE_EFFECT_BLOCKED")
        if descriptor.required_permission not in ctx.permissions:
            return _result("permission_denied", "Required tool permission is missing", code="PERMISSION_REQUIRED")

        try:
            _validate_json_value(args, descriptor.input_schema)
        except (TypeError, ValueError):
            return _result("invalid_request", "Tool input failed validation", code="INVALID_TOOL_INPUT")
        if descriptor.requires_approval and ctx.approval_ref is None:
            return _result("permission_denied", "Required approval context is missing", code="APPROVAL_REQUIRED")
        if descriptor.requires_safety_snapshot and ctx.safety_snapshot_ref is None:
            return _result("permission_denied", "Required safety snapshot is missing", code="SAFETY_SNAPSHOT_REQUIRED")
        if descriptor.requires_idempotency_key and not ctx.idempotency_key:
            return _result("invalid_request", "Required idempotency key is missing", code="IDEMPOTENCY_KEY_REQUIRED")

        executor = self._executor_for(name)
        if executor is None or not executor.has_tool(name):
            return _result("unavailable", "Tool is declared but unavailable", code="TOOL_UNAVAILABLE", source="tool")

        try:
            result = await executor.execute(name, args, ctx)
        except Exception:
            return _result("error", "Tool executor failed", code="EXECUTOR_ERROR", source="adapter")
        if not isinstance(result, ToolResultV2):
            return _result("invalid_response", "Tool executor returned an invalid response", code="INVALID_EXECUTOR_RESPONSE", source="adapter")
        try:
            if result.data is not None:
                _validate_json_value(result.data, descriptor.output_schema)
        except (TypeError, ValueError):
            return _result("invalid_response", "Tool executor returned an invalid response", code="INVALID_EXECUTOR_RESPONSE", source="adapter")
        return result

    def event_family(self, name: str) -> str:
        descriptor = self._descriptors.get(name)
        if descriptor and descriptor.event_family == "tool_call_*":
            return "tool_call"
        if descriptor and descriptor.event_family == "rag_retrieval_*":
            return "rag_retrieval"
        if descriptor and descriptor.event_family == "action":
            return "action"
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


def _side_effect_allowed(caller_node: str, descriptor: ToolDescriptor) -> bool:
    if caller_node == "investigate":
        return descriptor.kind != "write" and descriptor.side_effect in {"read_only", "retrieval"}
    if caller_node == "execute_action":
        return descriptor.kind == "write" and descriptor.side_effect == "write"
    return descriptor.side_effect in {"none", "read_only", "retrieval"}


def _action_result(raw_result: dict[str, Any], started_at: float) -> ToolResultV2:
    latency_ms = max(0, int((perf_counter() - started_at) * 1000))
    if not isinstance(raw_result, dict):
        return _result(
            "invalid_response",
            "Action executor returned an invalid response",
            code="INVALID_ACTION_RESPONSE",
            source="adapter",
            source_system="action_tool_executor",
        )
    if raw_result.get("status") == "success" and isinstance(raw_result.get("data"), dict):
        return ToolResultV2(
            status="success",
            data=dict(raw_result["data"]),
            summary="Action draft created",
            source_system="action_executor",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=None,
            retryable=False,
            retry_after_ms=None,
            latency_ms=latency_ms,
            audit_ref=None,
        )

    error = raw_result.get("error") if isinstance(raw_result.get("error"), dict) else {}
    retryable = bool(error.get("retryable", False))
    safe_message = "Action draft creation failed"
    return ToolResultV2(
        status="error",
        data=None,
        summary=safe_message,
        source_system="action_executor",
        data_freshness_at=None,
        policy_evidence_refs=[],
        business_fact_refs=[],
        error=ToolError(
            code=str(error.get("error_code") or "ACTION_DRAFT_FAILED"),
            safe_message=safe_message,
            retryable=retryable,
            source="adapter",
        ),
        retryable=retryable,
        retry_after_ms=None,
        latency_ms=latency_ms,
        audit_ref=None,
    )


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
