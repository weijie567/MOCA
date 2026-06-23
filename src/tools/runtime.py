"""Tool runtime: hard boundary chain before and after executor dispatch."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.tools.catalog import ToolCatalog, ToolDescriptor
from src.tools.contracts import (
    ToolCallContext,
    ToolInvocationOutcome,
    ToolPolicyDecision,
    ToolResultProjectionV1,
    ToolResultV2,
    ToolError,
)
from src.tools.manager_results import result as safe_result
from src.tools.policy import ToolPolicyEngine
from src.tools.projection import ToolResultProjector
from src.tools.validation import validate_json_value


class ToolRuntime:
    """Centralizes the runtime invocation chain.

    Gate order:
    1. Descriptor lookup
    2. Input schema validation (BEFORE runtime_auth — unvalidated args must
       never enter resource_scope_binding or decision event resource_refs)
    3. Runtime auth decision (ToolPolicyEngine.runtime_auth)
    4. Side-effect gate (already in runtime_auth)
    5. Approval/safety/idempotency gates (already in runtime_auth)
    6. Executor dispatch
    7. Output schema validation
    8. Result projection (ToolResultProjector)
    9. Safe error mapping
    10. Decision event emission
    """

    def __init__(
        self,
        *,
        catalog: ToolCatalog | None = None,
        executors: dict[str, Any] | None = None,
        policy_engine: ToolPolicyEngine | None = None,
        projector: ToolResultProjector | None = None,
    ) -> None:
        self._catalog = catalog or ToolCatalog()
        self._executors = executors or {}
        self._policy_engine = policy_engine or ToolPolicyEngine(catalog=self._catalog)
        self._projector = projector or ToolResultProjector()

    def has_tool(self, name: str) -> bool:
        """Check if an executor is registered for the given tool name."""
        descriptor = self._catalog.descriptor(name)
        if descriptor is None or descriptor.executor is None:
            return False
        executor = self._executors.get(descriptor.executor)
        return executor is not None and executor.has_tool(name)

    async def invoke(
        self,
        tool_name: str,
        args: dict[str, Any],
        ctx: ToolCallContext,
        *,
        session: AsyncSession | None = None,
    ) -> tuple[ToolResultV2, ToolPolicyDecision, str | None, ToolResultProjectionV1]:
        """Execute the full runtime chain.

        Returns:
            (tool_result, policy_decision, policy_event_id, projection)
        """
        # Step 1: Descriptor lookup
        descriptor = self._catalog.descriptor(tool_name)
        if descriptor is None:
            decision = self._policy_engine.runtime_auth(
                tool_name=tool_name, args=args, ctx=ctx,
                availability_map=self._build_availability_map(),
            )
            error_result = safe_result(
                "not_found", "Requested tool is not registered",
                code="TOOL_NOT_FOUND", source="caller",
            )
            projection = self._projector.project(
                tool_name=tool_name, result=error_result, tool_call_id=ctx.tool_call_id,
            )
            event_id = await self._emit_decision_event(
                decision=decision, ctx=ctx, session=session,
            )
            return error_result, decision, event_id, projection

        # Step 2: Input schema validation (BEFORE runtime_auth so unvalidated
        # args never enter resource_scope_binding or decision event resource_refs)
        try:
            validate_json_value(args, descriptor.input_schema)
        except (TypeError, ValueError):
            decision = self._denied_decision(
                tool_name=tool_name, ctx=ctx,
                reason_codes=["schema_invalid"],
                required_scopes=[descriptor.required_permission],
            )
            error_result = safe_result(
                "invalid_request", "Tool input failed validation",
                code="INVALID_TOOL_INPUT", source="caller",
            )
            projection = self._projector.project(
                tool_name=tool_name, result=error_result, tool_call_id=ctx.tool_call_id,
            )
            event_id = await self._emit_decision_event(
                decision=decision, ctx=ctx, session=session,
            )
            return error_result, decision, event_id, projection

        # Step 3: Runtime auth decision (after schema validation so only
        # validated args enter resource_scope_binding)
        availability_map = self._build_availability_map()
        decision = self._policy_engine.runtime_auth(
            tool_name=tool_name, args=args, ctx=ctx,
            availability_map=availability_map,
        )

        # Step 4-5: Side-effect, approval, safety, idempotency (already in runtime_auth)
        if decision.decision == "denied":
            error_result = self._safe_denial_result(decision)
            projection = self._projector.project(
                tool_name=tool_name, result=error_result, tool_call_id=ctx.tool_call_id,
            )
            event_id = await self._emit_decision_event(
                decision=decision, ctx=ctx, session=session,
            )
            return error_result, decision, event_id, projection

        # Step 6: Executor dispatch
        executor = self._executors.get(descriptor.executor) if descriptor.executor else None
        if executor is None or not executor.has_tool(tool_name):
            decision = self._denied_decision(
                tool_name=tool_name, ctx=ctx,
                reason_codes=["tool_unavailable"],
                required_scopes=[descriptor.required_permission],
                runtime_available=False,
                availability_summary=f"Tool {tool_name!r} executor is unavailable",
            )
            error_result = safe_result(
                "unavailable", "Tool is declared but unavailable",
                code="TOOL_UNAVAILABLE", source="tool",
            )
            projection = self._projector.project(
                tool_name=tool_name, result=error_result, tool_call_id=ctx.tool_call_id,
            )
            event_id = await self._emit_decision_event(
                decision=decision, ctx=ctx, session=session,
            )
            return error_result, decision, event_id, projection

        try:
            tool_result = await executor.execute(tool_name, args, ctx)
        except Exception:
            error_result = safe_result(
                "error", "Tool executor failed",
                code="EXECUTOR_ERROR", source="adapter",
            )
            projection = self._projector.project(
                tool_name=tool_name, result=error_result, tool_call_id=ctx.tool_call_id,
            )
            event_id = await self._emit_decision_event(
                decision=decision, ctx=ctx, session=session,
            )
            return error_result, decision, event_id, projection

        if not isinstance(tool_result, ToolResultV2):
            error_result = safe_result(
                "invalid_response", "Tool executor returned an invalid response",
                code="INVALID_EXECUTOR_RESPONSE", source="adapter",
            )
            projection = self._projector.project(
                tool_name=tool_name, result=error_result, tool_call_id=ctx.tool_call_id,
            )
            event_id = await self._emit_decision_event(
                decision=decision, ctx=ctx, session=session,
            )
            return error_result, decision, event_id, projection

        # Step 7: Output schema validation
        try:
            if tool_result.data is not None:
                validate_json_value(tool_result.data, descriptor.output_schema)
        except (TypeError, ValueError):
            error_result = safe_result(
                "invalid_response", "Tool executor returned an invalid response",
                code="INVALID_EXECUTOR_RESPONSE", source="adapter",
            )
            projection = self._projector.project(
                tool_name=tool_name, result=error_result, tool_call_id=ctx.tool_call_id,
            )
            event_id = await self._emit_decision_event(
                decision=decision, ctx=ctx, session=session,
            )
            return error_result, decision, event_id, projection

        # Step 8: Result projection
        projection = self._projector.project(
            tool_name=tool_name, result=tool_result, tool_call_id=ctx.tool_call_id,
        )

        # Step 10: Decision event emission (success path)
        event_id = await self._emit_decision_event(
            decision=decision, ctx=ctx, session=session,
        )

        return tool_result, decision, event_id, projection

    def _build_availability_map(self) -> dict[str, bool]:
        """Build availability map from executor registry."""
        availability: dict[str, bool] = {}
        for descriptor in self._catalog.descriptors():
            if descriptor.executor is None:
                availability[descriptor.name] = False
                continue
            executor = self._executors.get(descriptor.executor)
            availability[descriptor.name] = (
                executor is not None and executor.has_tool(descriptor.name)
            )
        return availability

    def _denied_decision(
        self,
        *,
        tool_name: str,
        ctx: ToolCallContext,
        reason_codes: list[str],
        required_scopes: list[str],
        runtime_available: bool = True,
        availability_summary: str | None = None,
    ) -> ToolPolicyDecision:
        return ToolPolicyDecision(
            tool_name=tool_name,
            caller=ctx.caller_node,
            decision_stage="runtime_auth",
            decision="denied",
            reason_codes=reason_codes,
            required_scopes=required_scopes,
            matched_scope=None,
            policy_version=self._policy_engine._policy_version,
            data_classification="internal",
            resource_scope_binding=None,
            runtime_available=runtime_available,
            availability_summary=availability_summary,
        )

    def _safe_denial_result(self, decision: ToolPolicyDecision) -> ToolResultV2:
        """Map a policy denial to a safe ToolResultV2 error."""
        code_map = {
            "caller_not_allowed": "CALLER_NOT_ALLOWED",
            "missing_permission": "PERMISSION_REQUIRED",
            "scope_denied": "SCOPE_DENIED",
            "side_effect_blocked": "SIDE_EFFECT_BLOCKED",
            "schema_invalid": "INVALID_TOOL_INPUT",
            "approval_required": "APPROVAL_REQUIRED",
            "safety_snapshot_required": "SAFETY_SNAPSHOT_REQUIRED",
            "idempotency_required": "IDEMPOTENCY_KEY_REQUIRED",
            "tool_unavailable": "TOOL_UNAVAILABLE",
        }
        status_map = {
            "tool_unavailable": "unavailable",
            "schema_invalid": "invalid_request",
            "idempotency_required": "invalid_request",
        }
        primary_reason = decision.reason_codes[0] if decision.reason_codes else "tool_unavailable"
        code = code_map.get(primary_reason, "POLICY_DENIED")
        message = f"Tool invocation denied: {primary_reason}"
        status = status_map.get(primary_reason, "permission_denied")
        return safe_result(status, message, code=code, source="policy")

    async def _emit_decision_event(
        self,
        *,
        decision: ToolPolicyDecision,
        ctx: ToolCallContext,
        session: AsyncSession | None,
    ) -> str | None:
        """Emit a runtime auth decision event if session is available."""
        if session is None:
            return None

        from src.replay.decision_events import emit_decision_event

        try:
            event = await emit_decision_event(
                session,
                run_id=ctx.run_id,
                tenant_id=ctx.tenant_id,
                thread_id=ctx.thread_id,
                event_type="tool_policy_runtime_auth_recorded",
                actor={"type": "agent", "id": "moca"},
                resource_refs={
                    "tool_name": decision.tool_name,
                    "tool_call_id": ctx.tool_call_id,
                    "resource_type": "tool",
                },
                redacted_payload={
                    "decision_stage": decision.decision_stage,
                    "tool_name": decision.tool_name,
                    "decision": decision.decision,
                    "reason_codes": decision.reason_codes,
                    "policy_version": decision.policy_version,
                    "data_classification": decision.data_classification,
                    "runtime_available": decision.runtime_available,
                },
                reason_codes=decision.reason_codes,
                versions={"policy_version": decision.policy_version},
            )
            return str(event.get("event_id")) if event else None
        except Exception:
            # Event emission must not block tool invocation.
            return None
