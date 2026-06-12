"""Declarative business-tool registry and dispatch boundary."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.tools.adapters import GetOrderInput, GetRefundCaseInput, GetTicketInput
from src.business_tools.schemas import ToolCallContext, ToolError, ToolResultV2


ToolAdapter = Callable[[BaseModel, ToolCallContext, AsyncSession], Awaitable[ToolResultV2]]


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: Literal["read", "retrieval", "write"]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: Literal["read", "retrieval", "write"]
    side_effect: Literal["none", "read_only", "retrieval", "write"]
    required_permission: str
    caller_allowlist: list[str]
    event_family: Literal["tool_call_*", "rag_retrieval_*"] | None
    resource_type: str | None


@dataclass(frozen=True)
class RegisteredTool:
    descriptor: ToolDescriptor
    adapter: ToolAdapter | None = None


_GENERIC_OBJECT_SCHEMA: dict[str, Any] = {"type": "object"}
_INPUT_MODELS: dict[str, type[BaseModel]] = {
    "get_order": GetOrderInput,
    "get_refund_case": GetRefundCaseInput,
    "get_ticket": GetTicketInput,
}
_IDENTIFIER_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_order": GetOrderInput.model_json_schema(),
    "get_refund_case": GetRefundCaseInput.model_json_schema(),
    "get_ticket": GetTicketInput.model_json_schema(),
    "get_logistics": {
        "type": "object",
        "properties": {"tracking_no": {"type": "string", "minLength": 1}},
        "required": ["tracking_no"],
    },
    "get_merchant_risk": {
        "type": "object",
        "properties": {"merchant_id": {"type": "string", "minLength": 1}},
        "required": ["merchant_id"],
    },
    "search_policy": {
        "type": "object",
        "properties": {"query": {"type": "string", "minLength": 1}},
        "required": ["query"],
    },
    "search_sop": {
        "type": "object",
        "properties": {"query": {"type": "string", "minLength": 1}},
        "required": ["query"],
    },
    "search_case_memory": {
        "type": "object",
        "properties": {"query": {"type": "string", "minLength": 1}},
        "required": ["query"],
    },
    "create_coupon_grant_draft": {
        "type": "object",
        "properties": {
            "merchant_id": {"type": "string", "minLength": 1},
            "amount": {"type": "number", "exclusiveMinimum": 0},
        },
        "required": ["merchant_id", "amount"],
    },
}


def _descriptor(
    name: str,
    *,
    kind: Literal["read", "retrieval", "write"],
    side_effect: Literal["read_only", "retrieval", "write"],
    caller_allowlist: list[str],
    event_family: Literal["tool_call_*", "rag_retrieval_*"] | None,
    resource_type: str | None,
) -> ToolDescriptor:
    return ToolDescriptor(
        name=name,
        kind=kind,
        input_schema=_IDENTIFIER_SCHEMAS[name],
        output_schema=_GENERIC_OBJECT_SCHEMA,
        risk_level=kind,
        side_effect=side_effect,
        required_permission=f"tool:{name}",
        caller_allowlist=caller_allowlist,
        event_family=event_family,
        resource_type=resource_type,
    )


def _default_descriptors() -> list[ToolDescriptor]:
    return [
        _descriptor(
            "get_order",
            kind="read",
            side_effect="read_only",
            caller_allowlist=["investigate"],
            event_family="tool_call_*",
            resource_type="order",
        ),
        _descriptor(
            "get_refund_case",
            kind="read",
            side_effect="read_only",
            caller_allowlist=["investigate"],
            event_family="tool_call_*",
            resource_type="refund_case",
        ),
        _descriptor(
            "get_ticket",
            kind="read",
            side_effect="read_only",
            caller_allowlist=["investigate"],
            event_family="tool_call_*",
            resource_type="ticket",
        ),
        _descriptor(
            "get_logistics",
            kind="read",
            side_effect="read_only",
            caller_allowlist=["investigate"],
            event_family="tool_call_*",
            resource_type="logistics",
        ),
        _descriptor(
            "get_merchant_risk",
            kind="read",
            side_effect="read_only",
            caller_allowlist=["investigate"],
            event_family="tool_call_*",
            resource_type="merchant_risk",
        ),
        _descriptor(
            "search_policy",
            kind="retrieval",
            side_effect="retrieval",
            caller_allowlist=["investigate"],
            event_family="rag_retrieval_*",
            resource_type=None,
        ),
        _descriptor(
            "search_sop",
            kind="retrieval",
            side_effect="retrieval",
            caller_allowlist=["investigate"],
            event_family="rag_retrieval_*",
            resource_type=None,
        ),
        _descriptor(
            "search_case_memory",
            kind="retrieval",
            side_effect="retrieval",
            caller_allowlist=["investigate"],
            event_family="rag_retrieval_*",
            resource_type=None,
        ),
        _descriptor(
            "create_coupon_grant_draft",
            kind="write",
            side_effect="write",
            caller_allowlist=[],
            # SCF-3: action_* deferred to Phase 17.
            event_family=None,
            resource_type=None,
        ),
    ]


def _default_adapters() -> dict[str, ToolAdapter]:
    """Load Phase 9 executable adapters when Plan 09-03 is present."""

    try:
        from src.business_tools.adapters import get_order_adapter, get_refund_case_adapter, get_ticket_adapter
    except ImportError:
        return {}
    return {
        "get_order": get_order_adapter,
        "get_refund_case": get_refund_case_adapter,
        "get_ticket": get_ticket_adapter,
    }


class ToolRegistry:
    def __init__(self, tools: Iterable[RegisteredTool] | None = None) -> None:
        if tools is None:
            adapters = _default_adapters()
            registered_tools = [
                RegisteredTool(descriptor=descriptor, adapter=adapters.get(descriptor.name))
                for descriptor in _default_descriptors()
            ]
        else:
            registered_tools = list(tools)

        self._tools: dict[str, RegisteredTool] = {}
        for tool in registered_tools:
            name = tool.descriptor.name
            if name in self._tools:
                raise ValueError(f"Duplicate tool registry entry: {name}")
            self._tools[name] = tool

    def descriptors(self) -> list[ToolDescriptor]:
        return [tool.descriptor for tool in self._tools.values()]

    # SCF-8: session is the explicit non-context DB runtime dependency; logical gate order is unchanged.
    async def invoke(
        self,
        name: str,
        input_data: dict[str, Any],
        ctx: ToolCallContext,
        session: AsyncSession,
    ) -> ToolResultV2:
        tool = self._tools.get(name)
        if tool is None:
            return self._result(
                "not_found",
                "Requested tool is not registered",
                code="TOOL_NOT_FOUND",
                source="caller",
            )

        descriptor = tool.descriptor
        if descriptor.kind == "write":
            return self._result(
                "permission_denied",
                "Write tools cannot execute through BusinessToolService",
                code="WRITE_TOOL_BLOCKED",
                source="caller",
            )

        if ctx.caller_node not in descriptor.caller_allowlist:
            return self._result(
                "permission_denied",
                "Caller is not allowed to invoke this tool",
                code="CALLER_NOT_ALLOWED",
                source="caller",
            )

        if descriptor.required_permission not in ctx.permissions:
            return self._result(
                "permission_denied",
                "Required tool permission is missing",
                code="PERMISSION_REQUIRED",
                source="caller",
            )

        try:
            input_model_type = _INPUT_MODELS.get(descriptor.name)
            if input_model_type is None:
                _validate_json_value(input_data, descriptor.input_schema)
                input_model = BaseModel.model_construct()
            else:
                input_model = input_model_type.model_validate(input_data)
        except (ValidationError, ValueError, TypeError):
            return self._result(
                "invalid_request",
                "Tool input failed validation",
                code="INVALID_TOOL_INPUT",
                source="caller",
            )

        adapter = tool.adapter
        if adapter is None:
            return self._result(
                "unavailable",
                "Tool is declared but unavailable",
                code="TOOL_UNAVAILABLE",
                source="tool",
            )

        try:
            result = await adapter(input_model, ctx, session)
        except Exception:
            return self._result(
                "error",
                "Tool adapter failed",
                code="ADAPTER_ERROR",
                source="adapter",
            )

        try:
            if not isinstance(result, ToolResultV2):
                raise TypeError("Adapter did not return ToolResultV2")
            if result.data is not None:
                _validate_json_value(result.data, descriptor.output_schema)
        except (ValueError, TypeError):
            return self._result(
                "invalid_response",
                "Tool adapter returned an invalid response",
                code="INVALID_ADAPTER_RESPONSE",
                source="adapter",
            )

        return result

    @staticmethod
    def _result(
        status: Literal["not_found", "permission_denied", "unavailable", "invalid_request", "invalid_response", "error"],
        summary: str,
        *,
        code: str,
        source: Literal["caller", "tool", "adapter"],
    ) -> ToolResultV2:
        return ToolResultV2(
            status=status,
            data=None,
            summary=summary,
            source_system="business_tool_registry",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=ToolError(code=code, safe_message=summary, retryable=False, source=source),
            retryable=False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )


def _validate_json_value(value: Any, schema: dict[str, Any]) -> None:
    """Validate the JSON Schema subset used by business-tool descriptors."""

    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            raise TypeError("Expected object")
        for required_name in schema.get("required", []):
            if required_name not in value:
                raise ValueError("Missing required property")
        properties = schema.get("properties", {})
        for property_name, property_schema in properties.items():
            if property_name in value:
                _validate_json_value(value[property_name], property_schema)
        if schema.get("additionalProperties") is False and any(name not in properties for name in value):
            raise ValueError("Unexpected property")
    elif expected_type == "array":
        if not isinstance(value, list):
            raise TypeError("Expected array")
        item_schema = schema.get("items", {})
        for item in value:
            _validate_json_value(item, item_schema)
    elif expected_type == "string":
        if not isinstance(value, str):
            raise TypeError("Expected string")
        if len(value) < schema.get("minLength", 0):
            raise ValueError("String is too short")
    elif expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("Expected integer")
    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("Expected number")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            raise ValueError("Number is below exclusive minimum")
    elif expected_type == "boolean" and not isinstance(value, bool):
        raise TypeError("Expected boolean")

    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Value is not in enum")
