"""Graph-facing ToolPlatform facade.

ToolPlatform is the public entry point for graph nodes to discover visible
tools and invoke them.  It delegates visibility and runtime auth decisions
to ToolPolicyEngine, execution to ToolRuntime, and result projection to
ToolResultProjector.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.tools.catalog import ToolCatalog, ToolDescriptor
from src.tools.contracts import (
    ToolCallContext,
    ToolInvocationOutcome,
    ToolPolicyDecision,
    ToolResultProjectionV1,
    ToolResultV2,
    ToolViewV1,
)
from src.tools.policy import ToolPolicyEngine
from src.tools.projection import ToolResultProjector
from src.tools.runtime import ToolRuntime


class ToolPlatform:
    """Graph-facing public facade for tool visibility and invocation.

    Phase 29 establishes this as the target integration boundary.  After
    Phase 29, graph/tool-platform integration should target
    ``ToolPlatform.visible_tools(...)`` and ``ToolPlatform.invoke(...)``.
    """

    def __init__(
        self,
        *,
        catalog: ToolCatalog | None = None,
        executors: dict[str, Any] | None = None,
        policy_engine: ToolPolicyEngine | None = None,
        runtime: ToolRuntime | None = None,
        projector: ToolResultProjector | None = None,
    ) -> None:
        self._catalog = catalog or ToolCatalog()
        self._executors = executors if executors is not None else {}
        self._policy_engine = policy_engine or ToolPolicyEngine(catalog=self._catalog)
        self._projector = projector or ToolResultProjector()
        self._runtime = runtime or ToolRuntime(
            catalog=self._catalog,
            executors=self._executors,
            policy_engine=self._policy_engine,
            projector=self._projector,
        )
        # Retain last visibility decisions for orchestrator inspection.
        self.last_visibility_decisions: list[ToolPolicyDecision] | None = None

    @classmethod
    def with_defaults(cls, session: AsyncSession) -> ToolPlatform:
        """Construct a ToolPlatform with default executors from a DB session."""
        from src.tools.executors.action import ActionToolExecutor
        from src.tools.executors.business import BusinessToolExecutor
        from src.tools.executors.knowledge import KnowledgeToolExecutor
        from src.tools.executors.memory import MemoryToolExecutor

        catalog = ToolCatalog()
        executors = {
            "business": BusinessToolExecutor(session),
            "knowledge": KnowledgeToolExecutor(session),
            "memory": MemoryToolExecutor(session),
            "action": ActionToolExecutor(session),
        }
        return cls(catalog=catalog, executors=executors)

    async def visible_tools(
        self,
        *,
        caller: str,
        ctx: ToolCallContext,
        session: AsyncSession | None = None,
    ) -> list[ToolViewV1]:
        """Return prompt-safe ToolViewV1 entries for the given caller.

        Records full visibility decisions (including hidden and unavailable)
        in ``last_visibility_decisions`` outside the returned prompt list.
        """
        availability_map = self._runtime._build_availability_map()
        decisions = self._policy_engine.visibility_decisions(
            caller=caller, ctx=ctx, availability_map=availability_map,
        )
        self.last_visibility_decisions = decisions

        # Emit visibility event when session is available.
        if session is not None:
            await self._emit_visibility_event(
                decisions=decisions, ctx=ctx, session=session,
            )

        return self._policy_engine.tool_views_for_decisions(
            decisions, availability_map=availability_map,
        )

    async def invoke(
        self,
        tool_name: str,
        args: dict[str, Any],
        ctx: ToolCallContext,
        *,
        session: AsyncSession | None = None,
    ) -> ToolInvocationOutcome:
        """Invoke a tool through the full runtime chain.

        Returns a ToolInvocationOutcome with tool_result, projection,
        policy_decision, and optional policy_event_id.
        """
        tool_result, policy_decision, policy_event_id, projection = await self._runtime.invoke(
            tool_name, args, ctx, session=session,
        )
        return ToolInvocationOutcome(
            tool_result=tool_result,
            projection=projection,
            policy_decision=policy_decision,
            policy_event_id=policy_event_id,
        )

    def descriptor(self, tool_name: str) -> ToolDescriptor | None:
        """Return the raw descriptor for a tool (for lifecycle event metadata)."""
        return self._catalog.descriptor(tool_name)

    def event_family(self, tool_name: str) -> str | None:
        """Return the event family for a tool (for lifecycle event metadata)."""
        descriptor = self._catalog.descriptor(tool_name)
        if descriptor is None:
            return None
        if descriptor.event_family == "tool_call_*":
            return "tool_call"
        if descriptor.event_family == "rag_retrieval_*":
            return "rag_retrieval"
        if descriptor.event_family == "action":
            return "action"
        return None

    async def _emit_visibility_event(
        self,
        *,
        decisions: list[ToolPolicyDecision],
        ctx: ToolCallContext,
        session: AsyncSession,
    ) -> None:
        """Emit a batched visibility decision event."""
        from src.replay.decision_events import emit_decision_event

        tools_payload = []
        for decision in decisions:
            tools_payload.append({
                "tool_name": decision.tool_name,
                "decision": decision.decision,
                "reason_codes": decision.reason_codes,
                "runtime_available": decision.runtime_available,
                "data_classification": decision.data_classification,
            })

        try:
            await emit_decision_event(
                session,
                run_id=ctx.run_id,
                tenant_id=ctx.tenant_id,
                thread_id=ctx.thread_id,
                event_type="tool_policy_visibility_recorded",
                actor={"type": "agent", "id": "moca"},
                resource_refs={"caller": ctx.caller_node},
                redacted_payload={
                    "decision_stage": "visibility",
                    "tools": tools_payload,
                    "policy_version": self._policy_engine._policy_version,
                },
            )
        except Exception:
            # Visibility event emission must not block tool discovery.
            pass
