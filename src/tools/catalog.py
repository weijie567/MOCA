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
    description: str = ""
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
@dataclass(frozen=True)
class _ToolDeclaration:
    name: str
    kind: Literal["read", "retrieval", "write"]
    input_schema: dict[str, Any]
    side_effect: Literal["read_only", "retrieval", "write"]
    caller_allowlist: tuple[str, ...]
    event_family: Literal["tool_call_*", "rag_retrieval_*", "action"] | None
    resource_type: str | None
    executor: Literal["business", "knowledge", "memory", "action"] | None = None
    description: str = ""
    exposure: Literal["planner_visible", "node_only", "internal"] = "planner_visible"
    requires_approval: bool = False
    requires_safety_snapshot: bool = False
    requires_idempotency_key: bool = False


_TOOL_DECLARATIONS: tuple[_ToolDeclaration, ...] = (
    _ToolDeclaration(
        name="get_order",
        kind="read",
        input_schema={
            "type": "object",
            "properties": {"order_no": {"type": "string", "minLength": 1}},
            "required": ["order_no"],
        },
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="order",
        executor="business",
    ),
    _ToolDeclaration(
        name="get_refund_case",
        kind="read",
        input_schema={
            "type": "object",
            "properties": {"refund_case_no": {"type": "string", "minLength": 1}},
            "required": ["refund_case_no"],
        },
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="refund_case",
        executor="business",
    ),
    _ToolDeclaration(
        name="get_ticket",
        kind="read",
        input_schema={
            "type": "object",
            "properties": {"ticket_id": {"type": "string", "minLength": 1}},
            "required": ["ticket_id"],
        },
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="ticket",
        executor="business",
    ),
    _ToolDeclaration(
        name="get_logistics",
        kind="read",
        input_schema={
            "type": "object",
            "properties": {"tracking_no": {"type": "string", "minLength": 1}},
            "required": ["tracking_no"],
        },
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="logistics",
        executor="business",
    ),
    _ToolDeclaration(
        name="get_merchant_risk",
        kind="read",
        input_schema={
            "type": "object",
            "properties": {"merchant_id": {"type": "string", "minLength": 1}},
            "required": ["merchant_id"],
        },
        side_effect="read_only",
        caller_allowlist=("investigate",),
        event_family="tool_call_*",
        resource_type="merchant_risk",
        executor="business",
    ),
    _ToolDeclaration(
        name="search_policy",
        kind="retrieval",
        input_schema={
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
        side_effect="retrieval",
        caller_allowlist=("investigate",),
        event_family="rag_retrieval_*",
        resource_type=None,
        executor="knowledge",
    ),
    _ToolDeclaration(
        name="search_sop",
        kind="retrieval",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 1}},
            "required": ["query"],
        },
        side_effect="retrieval",
        caller_allowlist=("investigate",),
        event_family="rag_retrieval_*",
        resource_type=None,
        executor="knowledge",
    ),
    _ToolDeclaration(
        name="search_case_memory",
        description=(
            "Retrieve reviewed case memory precedents from the reviewed case store. "
            "Returned snippets are contextual only, not policy evidence or action authority."
        ),
        kind="retrieval",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 1}},
            "required": ["query"],
        },
        side_effect="retrieval",
        caller_allowlist=("investigate",),
        event_family="rag_retrieval_*",
        resource_type=None,
        executor="memory",
    ),
    _ToolDeclaration(
        name="create_coupon_grant_draft",
        kind="write",
        input_schema={
            "type": "object",
            "properties": {
                "approval_request_id": {"type": "string", "minLength": 1},
                "action_type": {"type": "string", "minLength": 1},
                "payload": {"type": "object"},
                "action_payload_hash": {"type": "string", "minLength": 1},
                "safety_snapshot_ref": {"type": "string", "minLength": 1},
                "safety_snapshot_hash": {"type": "string", "minLength": 1},
                "target_merchant_id": {"type": "string", "minLength": 1},
                "target_merchant_ref": {"type": "object"},
                "business_fact_refs": {"type": "array", "items": {"type": "object"}},
                "verified_evidence_refs": {"type": "array", "items": {"type": "object"}},
                "claim_verification_ref": {"type": "string", "minLength": 1},
                "claim_verification_summary": {"type": "object"},
                "risk_decision_ref": {"type": "string", "minLength": 1},
                "risk_decision": {"type": "object"},
                "auto_allowed_binding": {"type": "object"},
            },
            "required": [
                "action_type",
                "payload",
                "action_payload_hash",
                "safety_snapshot_ref",
                "safety_snapshot_hash",
            ],
        },
        side_effect="write",
        caller_allowlist=("action_draft",),
        event_family="action",
        resource_type=None,
        executor="action",
        exposure="node_only",
        requires_safety_snapshot=True,
        requires_idempotency_key=True,
    ),
)
_IDENTIFIER_SCHEMAS = {declaration.name: declaration.input_schema for declaration in _TOOL_DECLARATIONS}


def _descriptor(declaration: _ToolDeclaration) -> ToolDescriptor:
    return ToolDescriptor(
        name=declaration.name,
        description=declaration.description,
        kind=declaration.kind,
        input_schema=declaration.input_schema,
        output_schema=_GENERIC_OBJECT_SCHEMA,
        risk_level=declaration.kind,
        side_effect=declaration.side_effect,
        required_permission=f"tool:{declaration.name}",
        caller_allowlist=list(declaration.caller_allowlist),
        event_family=declaration.event_family,
        resource_type=declaration.resource_type,
        executor=declaration.executor,
        exposure=declaration.exposure,
        requires_approval=declaration.requires_approval,
        requires_safety_snapshot=declaration.requires_safety_snapshot,
        requires_idempotency_key=declaration.requires_idempotency_key,
    )


def _default_descriptors() -> list[ToolDescriptor]:
    return [_descriptor(declaration) for declaration in _TOOL_DECLARATIONS]


def investigate_tool_names(descriptors: Iterable[ToolDescriptor] | None = None) -> frozenset[str]:
    source = descriptors if descriptors is not None else _default_descriptors()
    return frozenset(
        descriptor.name
        for descriptor in source
        if "investigate" in descriptor.caller_allowlist
        and descriptor.kind != "write"
        and descriptor.exposure == "planner_visible"
    )


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
