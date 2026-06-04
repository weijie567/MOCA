from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from src.agent.tools.adapters import (
    GetOrderInput,
    GetRefundCaseInput,
    GetTicketInput,
    SearchPolicyInput,
    get_order_adapter,
    get_refund_case_adapter,
    get_ticket_adapter,
    search_policy_adapter,
)
from src.agent.tools.contracts import (
    ToolExecutionError,
    ToolExecutionResult,
    ToolInvocationContext,
    ToolRegistryEntry,
)


INVESTIGATOR_TOOL_NAMES = frozenset({"get_order", "get_refund_case", "get_ticket", "search_policy"})
_READ_CONTEXT_TOOL_NAMES = frozenset({"get_order", "get_refund_case", "get_ticket"})
_RETRIEVAL_CONTEXT_TOOL_NAMES = frozenset({"search_policy"})
_SAFE_INVESTIGATOR_RISKS = frozenset({"read", "retrieval"})
_SAFE_INVESTIGATOR_SIDE_EFFECTS = frozenset({"none", "read_only", "retrieval"})


class ToolOutput(BaseModel):
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] = Field(default_factory=dict)


ToolAdapter = Callable[[BaseModel, ToolInvocationContext], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class RegisteredTool:
    entry: ToolRegistryEntry
    adapter: ToolAdapter


def _entry(
    *,
    name: str,
    description: str,
    input_schema: type[BaseModel],
    risk_level: str,
    side_effect: str,
    when_to_use: str,
    required_identifiers: list[str],
    result_summary_fields: list[str],
) -> ToolRegistryEntry:
    return ToolRegistryEntry(
        name=name,
        description=description,
        input_schema=input_schema,
        output_schema=ToolOutput,
        risk_level=risk_level,
        side_effect=side_effect,
        allowed_in_investigator=True,
        when_to_use=when_to_use,
        required_identifiers=required_identifiers,
        result_summary_fields=result_summary_fields,
    )


def _default_tools() -> list[RegisteredTool]:
    return [
        RegisteredTool(
            entry=_entry(
                name="get_order",
                description="Fetch a tenant-scoped order and relation hints by order number.",
                input_schema=GetOrderInput,
                risk_level="read",
                side_effect="read_only",
                when_to_use="Use when the request includes an order number or needs order status and relation hints.",
                required_identifiers=["order_no"],
                result_summary_fields=["order_no", "status", "amount", "currency", "relation_hints"],
            ),
            adapter=get_order_adapter,
        ),
        RegisteredTool(
            entry=_entry(
                name="get_refund_case",
                description="Fetch a tenant-scoped refund case by refund case number.",
                input_schema=GetRefundCaseInput,
                risk_level="read",
                side_effect="read_only",
                when_to_use="Use when the request includes a refund case number or needs refund status and reason.",
                required_identifiers=["refund_case_no"],
                result_summary_fields=[
                    "refund_case_no",
                    "status",
                    "reason_code",
                    "reason_text",
                    "requested_amount",
                    "approved_amount",
                ],
            ),
            adapter=get_refund_case_adapter,
        ),
        RegisteredTool(
            entry=_entry(
                name="get_ticket",
                description="Fetch a tenant-scoped support ticket summary by id or ticket number.",
                input_schema=GetTicketInput,
                risk_level="read",
                side_effect="read_only",
                when_to_use="Use when the request includes a support ticket id or ticket number.",
                required_identifiers=["ticket_id"],
                result_summary_fields=["ticket_no", "status", "channel", "summary"],
            ),
            adapter=get_ticket_adapter,
        ),
        RegisteredTool(
            entry=_entry(
                name="search_policy",
                description="Search tenant-scoped policy evidence.",
                input_schema=SearchPolicyInput,
                risk_level="retrieval",
                side_effect="retrieval",
                when_to_use="Use when policy evidence or refund rules are needed.",
                required_identifiers=["query"],
                result_summary_fields=["retrieval_status", "best_score", "fallback_message"],
            ),
            adapter=search_policy_adapter,
        ),
    ]


class ToolRegistry:
    def __init__(self, tools: Iterable[RegisteredTool] | None = None) -> None:
        registered_tools = list(_default_tools() if tools is None else tools)
        self._tools: dict[str, RegisteredTool] = {}
        for tool in registered_tools:
            self._validate_registered_tool(tool)
            if tool.entry.name in self._tools:
                raise ValueError(f"Duplicate tool registry entry: {tool.entry.name}")
            self._tools[tool.entry.name] = tool

    def investigator_tool_names(self) -> list[str]:
        return sorted(name for name, tool in self._tools.items() if tool.entry.allowed_in_investigator)

    def investigator_tools(self) -> list[ToolRegistryEntry]:
        return [self._tools[name].entry for name in self.investigator_tool_names()]

    async def invoke(self, name: str, input_data: dict[str, Any], context: ToolInvocationContext) -> ToolExecutionResult:
        tool = self._tools.get(name)
        if tool is None:
            return self._rejection("not_found", f"Tool {name!r} is not registered")

        if not self._caller_can_invoke(tool.entry, context):
            return self._rejection("unsafe_tool_request", f"{context.caller} is not allowed to invoke {name!r}")

        try:
            validated_input = tool.entry.input_schema.model_validate(input_data)
        except ValidationError as exc:
            return self._rejection("validation_error", str(exc))

        try:
            raw_result = await tool.adapter(validated_input, context)
        except Exception as exc:
            return self._rejection("tool_error", str(exc), retryable=True)

        return self._to_execution_result(tool.entry, raw_result)

    def _validate_registered_tool(self, tool: RegisteredTool) -> None:
        entry = tool.entry
        if not isinstance(entry, ToolRegistryEntry):
            raise ValueError("Tool registry definitions must include typed ToolRegistryEntry metadata")
        if not callable(tool.adapter):
            raise ValueError(f"Tool {entry.name!r} must include an async adapter")
        input_schema = getattr(entry, "input_schema", None)
        output_schema = getattr(entry, "output_schema", None)
        if not isinstance(input_schema, type) or not issubclass(input_schema, BaseModel):
            raise ValueError(f"Tool {entry.name!r} must declare a Pydantic input_schema")
        if not isinstance(output_schema, type) or not issubclass(output_schema, BaseModel):
            raise ValueError(f"Tool {entry.name!r} must declare a Pydantic output_schema")
        if not entry.description or not entry.when_to_use:
            raise ValueError(f"Tool {entry.name!r} must include prompt selection metadata")
        if entry.allowed_in_investigator and entry.name not in INVESTIGATOR_TOOL_NAMES:
            raise ValueError(f"Tool {entry.name!r} is not in the investigator allowlist")
        if entry.allowed_in_investigator:
            if entry.risk_level not in _SAFE_INVESTIGATOR_RISKS:
                raise ValueError(f"Tool {entry.name!r} has unsafe investigator risk metadata")
            if entry.side_effect not in _SAFE_INVESTIGATOR_SIDE_EFFECTS:
                raise ValueError(f"Tool {entry.name!r} has unsafe investigator side-effect metadata")

    def _caller_can_invoke(self, entry: ToolRegistryEntry, context: ToolInvocationContext) -> bool:
        if context.caller == "investigator":
            return (
                entry.allowed_in_investigator
                and entry.name in INVESTIGATOR_TOOL_NAMES
                and entry.risk_level in _SAFE_INVESTIGATOR_RISKS
                and entry.side_effect in _SAFE_INVESTIGATOR_SIDE_EFFECTS
            )
        if context.caller == "load_business_context":
            return entry.name in _READ_CONTEXT_TOOL_NAMES and entry.risk_level == "read"
        if context.caller == "retrieve_policy_evidence":
            return entry.name in _RETRIEVAL_CONTEXT_TOOL_NAMES and entry.risk_level == "retrieval"
        if context.caller == "execute_action":
            return False
        return False

    def _to_execution_result(self, entry: ToolRegistryEntry, raw_result: dict[str, Any]) -> ToolExecutionResult:
        output = entry.output_schema.model_validate(raw_result)
        if output.status == "error":
            error = output.error or {}
            return ToolExecutionResult(
                status="error",
                error=ToolExecutionError(
                    error_code="tool_error",
                    message=str(error.get("message") or "Tool execution failed"),
                    retryable=bool(error.get("retryable", False)),
                ),
            )

        data = output.data or {}
        return ToolExecutionResult(
            status="success",
            summary={field: data[field] for field in entry.result_summary_fields if field in data},
            evidence_refs=_evidence_refs_from_data(data),
        )

    def _rejection(self, error_code: str, message: str, *, retryable: bool = False) -> ToolExecutionResult:
        return ToolExecutionResult(
            status="error",
            error=ToolExecutionError(error_code=error_code, message=message, retryable=retryable),
        )


def _evidence_refs_from_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for item in data.get("evidence") or []:
        doc_key = item.get("doc_key")
        chunk_id = item.get("chunk_id")
        if not doc_key or not chunk_id:
            continue
        refs.append(
            {
                "doc_key": str(doc_key),
                "chunk_id": str(chunk_id),
                "title": item.get("title"),
                "confidence": item.get("score"),
            }
        )
    return refs
