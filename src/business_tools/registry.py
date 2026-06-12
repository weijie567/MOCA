"""Declarative business-tool registry and dispatch boundary."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.tools.adapters import GetOrderInput, GetRefundCaseInput, GetTicketInput
from src.business_tools.schemas import ToolCallContext, ToolResultV2


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
