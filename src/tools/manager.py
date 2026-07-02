from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.events import classify_event_family
from src.tools.catalog import RegisteredTool, ToolCatalog, ToolDescriptor, investigate_tool_names
from src.tools.contracts import ToolCallContext, ToolResultV2, ToolViewV1
from src.tools.executors.action import ActionToolExecutor
from src.tools.executors.business import BusinessToolExecutor
from src.tools.executors.knowledge import KnowledgeToolExecutor
from src.tools.executors.memory import MemoryToolExecutor
from src.tools.platform import ToolPlatform


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
        # Build ToolPlatform as the internal policy/runtime owner.
        # When custom descriptors are provided, build a ToolCatalog from them
        # so the platform's policy engine sees the same descriptors.
        if descriptors is not None:
            platform_catalog = ToolCatalog(
                tools=[RegisteredTool(descriptor=d) for d in descriptors]
            )
        else:
            platform_catalog = ToolCatalog()
        self._platform = ToolPlatform(
            catalog=platform_catalog,
            executors=self._executors,
        )

    @classmethod
    def with_defaults(cls, session: AsyncSession) -> UnifiedToolManager:
        return cls(
            executors={
                "business": BusinessToolExecutor(session),
                "knowledge": KnowledgeToolExecutor(session),
                "memory": MemoryToolExecutor(session),
                "action": ActionToolExecutor(session),
            }
        )

    def descriptors(self, caller_node: str = "investigate") -> list[ToolDescriptor]:
        if caller_node == "investigate":
            investigate_names = investigate_tool_names(self._descriptors.values())
            return [
                descriptor
                for descriptor in self._descriptors.values()
                if descriptor.name in investigate_names
            ]
        return [descriptor for descriptor in self._descriptors.values() if caller_node in descriptor.caller_allowlist]

    async def visible_tools(
        self,
        *,
        caller: str,
        ctx: ToolCallContext,
        session: Any = None,
    ) -> list[ToolViewV1]:
        """Delegate to ToolPlatform for prompt-safe planner visibility."""
        return await self._platform.visible_tools(caller=caller, ctx=ctx, session=session)

    def descriptor(self, name: str) -> ToolDescriptor | None:
        return self._descriptors.get(name)

    async def invoke(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        """Delegate to ToolPlatform.invoke and return the ToolResultV2 for backward compat."""
        outcome = await self._platform.invoke(name, args, ctx, session=None)
        return outcome.tool_result

    def event_family(self, name: str) -> str:
        descriptor = self._descriptors.get(name)
        if descriptor and descriptor.event_family == "tool_call_*":
            return "tool_call"
        if descriptor and descriptor.event_family == "rag_retrieval_*":
            return "rag_retrieval"
        if descriptor and descriptor.event_family == "action":
            return "action"
        return classify_event_family(name)

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
