from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.events import classify_event_family
from src.tools.catalog import ToolCatalog, ToolDescriptor
from src.tools.contracts import ToolCallContext, ToolResultV2
from src.tools.executors.action import ActionToolExecutor
from src.tools.executors.business import BusinessToolExecutor
from src.tools.executors.knowledge import KnowledgeToolExecutor
from src.tools.executors.memory import MemoryToolExecutor
from src.tools.manager_results import result
from src.tools.validation import validate_json_value


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


class ToolExecutor(Protocol):
    def has_tool(self, name: str) -> bool: ...

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2: ...


class UnifiedToolManager:
    def __init__(
        self,
        *,
        descriptors: list[ToolDescriptor] | None = None,
        executors: dict[str, ToolExecutor] | list[ToolExecutor] | None = None,
    ) -> None:
        catalog = descriptors if descriptors is not None else ToolCatalog().descriptors()
        self._descriptors = {descriptor.name: descriptor for descriptor in catalog}
        self._executors = self._executor_registry(executors or {})

    @classmethod
    def with_defaults(cls, session: AsyncSession) -> UnifiedToolManager:
        return cls(
            executors={
                "business": BusinessToolExecutor(session),
                "knowledge": KnowledgeToolExecutor(session),
                "memory": MemoryToolExecutor(),
                "action": ActionToolExecutor(session),
            }
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
            return result("not_found", "Requested tool is not registered", code="TOOL_NOT_FOUND", source="caller")
        if ctx.caller_node not in descriptor.caller_allowlist:
            return result("permission_denied", "Caller is not allowed to invoke this tool", code="CALLER_NOT_ALLOWED")
        if not _side_effect_allowed(ctx.caller_node, descriptor):
            return result(
                "permission_denied",
                "Caller is not allowed to execute this tool side effect",
                code="SIDE_EFFECT_BLOCKED",
            )
        if descriptor.required_permission not in ctx.permissions:
            return result("permission_denied", "Required tool permission is missing", code="PERMISSION_REQUIRED")

        try:
            validate_json_value(args, descriptor.input_schema)
        except (TypeError, ValueError):
            return result("invalid_request", "Tool input failed validation", code="INVALID_TOOL_INPUT")
        if descriptor.requires_approval and ctx.approval_ref is None:
            return result("permission_denied", "Required approval context is missing", code="APPROVAL_REQUIRED")
        if descriptor.requires_safety_snapshot and ctx.safety_snapshot_ref is None:
            return result("permission_denied", "Required safety snapshot is missing", code="SAFETY_SNAPSHOT_REQUIRED")
        if descriptor.requires_idempotency_key and not ctx.idempotency_key:
            return result("invalid_request", "Required idempotency key is missing", code="IDEMPOTENCY_KEY_REQUIRED")

        executor = self._executor_for(descriptor)
        if executor is None or not executor.has_tool(name):
            return result("unavailable", "Tool is declared but unavailable", code="TOOL_UNAVAILABLE", source="tool")

        try:
            tool_result = await executor.execute(name, args, ctx)
        except Exception:
            return result("error", "Tool executor failed", code="EXECUTOR_ERROR", source="adapter")
        if not isinstance(tool_result, ToolResultV2):
            return result(
                "invalid_response",
                "Tool executor returned an invalid response",
                code="INVALID_EXECUTOR_RESPONSE",
                source="adapter",
            )
        try:
            if tool_result.data is not None:
                validate_json_value(tool_result.data, descriptor.output_schema)
        except (TypeError, ValueError):
            return result(
                "invalid_response",
                "Tool executor returned an invalid response",
                code="INVALID_EXECUTOR_RESPONSE",
                source="adapter",
            )
        return tool_result

    def event_family(self, name: str) -> str:
        descriptor = self._descriptors.get(name)
        if descriptor and descriptor.event_family == "tool_call_*":
            return "tool_call"
        if descriptor and descriptor.event_family == "rag_retrieval_*":
            return "rag_retrieval"
        if descriptor and descriptor.event_family == "action":
            return "action"
        return classify_event_family(name)

    def _executor_for(self, descriptor: ToolDescriptor) -> ToolExecutor | None:
        if descriptor.executor is None:
            return None
        return self._executors.get(descriptor.executor)

    def _executor_registry(
        self,
        executors: dict[str, ToolExecutor] | list[ToolExecutor],
    ) -> dict[str, ToolExecutor]:
        if isinstance(executors, dict):
            return dict(executors)

        registry: dict[str, ToolExecutor] = {}
        for executor in executors:
            executor_name = getattr(executor, "executor_name", None)
            if isinstance(executor_name, str):
                registry[executor_name] = executor
                continue
            get_tools = getattr(executor, "get_tools", None)
            if callable(get_tools):
                for descriptor in get_tools().values():
                    if isinstance(descriptor, ToolDescriptor) and descriptor.executor:
                        registry[descriptor.executor] = executor
        return registry


def _side_effect_allowed(caller_node: str, descriptor: ToolDescriptor) -> bool:
    if caller_node == "investigate":
        return descriptor.kind != "write" and descriptor.side_effect in {"read_only", "retrieval"}
    if caller_node == "execute_action":
        return descriptor.kind == "write" and descriptor.side_effect == "write"
    return descriptor.side_effect in {"none", "read_only", "retrieval"}
