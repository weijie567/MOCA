"""Declarative catalog for all graph-facing tool capabilities."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.tools.contracts import ToolError, ToolResultV2


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
    event_family: Literal["tool_call_*", "rag_retrieval_*", "action"] | None
    resource_type: str | None
    executor: Literal["business", "knowledge", "memory", "action"] | None = None
    exposure: Literal["planner_visible", "node_only", "internal"] = "planner_visible"
    requires_approval: bool = False
    requires_safety_snapshot: bool = False
    requires_idempotency_key: bool = False


@dataclass(frozen=True)
class RegisteredTool:
    descriptor: ToolDescriptor
    adapter: Any | None = None


_GENERIC_OBJECT_SCHEMA: dict[str, Any] = {"type": "object"}
_IDENTIFIER_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_order": {
        "type": "object",
        "properties": {"order_no": {"type": "string", "minLength": 1}},
        "required": ["order_no"],
    },
    "get_refund_case": {
        "type": "object",
        "properties": {"refund_case_no": {"type": "string", "minLength": 1}},
        "required": ["refund_case_no"],
    },
    "get_ticket": {
        "type": "object",
        "properties": {"ticket_id": {"type": "string", "minLength": 1}},
        "required": ["ticket_id"],
    },
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
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "primary_intent": {"type": "string", "minLength": 1},
            "merchant_id": {"type": "string", "minLength": 1},
            "max_results": {"type": "integer"},
            "allow_partial_evidence": {"type": "boolean"},
        },
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
            "approval_request_id": {"type": "string", "minLength": 1},
            "action_type": {"type": "string", "minLength": 1},
            "payload": {"type": "object"},
            "action_payload_hash": {"type": "string", "minLength": 1},
            "safety_snapshot_ref": {"type": "string", "minLength": 1},
            "safety_snapshot_hash": {"type": "string", "minLength": 1},
        },
        "required": ["action_type", "payload", "action_payload_hash", "safety_snapshot_ref", "safety_snapshot_hash"],
    },
}


def _descriptor(
    name: str,
    *,
    kind: Literal["read", "retrieval", "write"],
    side_effect: Literal["read_only", "retrieval", "write"],
    caller_allowlist: list[str],
    event_family: Literal["tool_call_*", "rag_retrieval_*", "action"] | None,
    resource_type: str | None,
    executor: Literal["business", "knowledge", "memory", "action"] | None = None,
    exposure: Literal["planner_visible", "node_only", "internal"] = "planner_visible",
    requires_approval: bool = False,
    requires_safety_snapshot: bool = False,
    requires_idempotency_key: bool = False,
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
        executor=executor,
        exposure=exposure,
        requires_approval=requires_approval,
        requires_safety_snapshot=requires_safety_snapshot,
        requires_idempotency_key=requires_idempotency_key,
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
            executor="business",
        ),
        _descriptor(
            "get_refund_case",
            kind="read",
            side_effect="read_only",
            caller_allowlist=["investigate"],
            event_family="tool_call_*",
            resource_type="refund_case",
            executor="business",
        ),
        _descriptor(
            "get_ticket",
            kind="read",
            side_effect="read_only",
            caller_allowlist=["investigate"],
            event_family="tool_call_*",
            resource_type="ticket",
            executor="business",
        ),
        _descriptor(
            "get_logistics",
            kind="read",
            side_effect="read_only",
            caller_allowlist=["investigate"],
            event_family="tool_call_*",
            resource_type="logistics",
            executor="business",
        ),
        _descriptor(
            "get_merchant_risk",
            kind="read",
            side_effect="read_only",
            caller_allowlist=["investigate"],
            event_family="tool_call_*",
            resource_type="merchant_risk",
            executor="business",
        ),
        _descriptor(
            "search_policy",
            kind="retrieval",
            side_effect="retrieval",
            caller_allowlist=["investigate"],
            event_family="rag_retrieval_*",
            resource_type=None,
            executor="knowledge",
        ),
        _descriptor(
            "search_sop",
            kind="retrieval",
            side_effect="retrieval",
            caller_allowlist=["investigate"],
            event_family="rag_retrieval_*",
            resource_type=None,
            executor="knowledge",
        ),
        _descriptor(
            "search_case_memory",
            kind="retrieval",
            side_effect="retrieval",
            caller_allowlist=["investigate"],
            event_family="rag_retrieval_*",
            resource_type=None,
            executor="memory",
        ),
        _descriptor(
            "create_coupon_grant_draft",
            kind="write",
            side_effect="write",
            caller_allowlist=["execute_action"],
            event_family="action",
            resource_type=None,
            executor="action",
            exposure="node_only",
            requires_safety_snapshot=True,
            requires_idempotency_key=True,
        ),
    ]


class ToolCatalog:
    def __init__(self, tools: Iterable[RegisteredTool] | None = None) -> None:
        if tools is None:
            registered_tools = [RegisteredTool(descriptor=descriptor) for descriptor in _default_descriptors()]
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

    def descriptor(self, name: str) -> ToolDescriptor | None:
        tool = self._tools.get(name)
        return tool.descriptor if tool else None

    async def invoke(
        self,
        name: str,
        input_data: dict[str, Any],
        ctx: Any,
        session: Any,
    ) -> ToolResultV2:
        """Compatibility shim: the catalog never executes tools."""

        del input_data, ctx, session
        tool = self._tools.get(name)
        if tool is None:
            return self._result(
                "not_found",
                "Requested tool is not registered",
                code="TOOL_NOT_FOUND",
                source="caller",
            )
        return self._result(
            "unavailable",
            "ToolCatalog is declaration-only; use UnifiedToolManager",
            code="TOOL_REGISTRY_DECLARATION_ONLY",
            source="tool",
        )

    @staticmethod
    def _result(
        status: Literal["not_found", "unavailable"],
        summary: str,
        *,
        code: str,
        source: Literal["caller", "tool"],
    ) -> ToolResultV2:
        return ToolResultV2(
            status=status,
            data=None,
            summary=summary,
            source_system="tool_catalog",
            data_freshness_at=None,
            policy_evidence_refs=[],
            business_fact_refs=[],
            error=ToolError(code=code, safe_message=summary, retryable=False, source=source),
            retryable=False,
            retry_after_ms=None,
            latency_ms=0,
            audit_ref=None,
        )
