from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from src.agent.tools.adapters import (
    SearchPolicyInput,
    search_policy_adapter,
)
from src.agent.tools.contracts import (
    ToolExecutionError,
    ToolExecutionResult,
    ToolInvocationContext,
    ToolRegistryEntry,
    ToolResultStatus,
)


class ToolOutput(BaseModel):
    status: ToolResultStatus
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
        when_to_use=when_to_use,
        required_identifiers=required_identifiers,
        result_summary_fields=result_summary_fields,
    )


def _default_tools() -> list[RegisteredTool]:
    return [
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

    async def invoke(self, name: str, input_data: dict[str, Any], context: ToolInvocationContext) -> ToolExecutionResult:
        tool = self._tools.get(name)
        if tool is None:
            return self._rejection("not_found", f"Tool {name!r} is not registered")

        if (
            context.caller != "retrieve_policy_evidence"
            or tool.entry.name != "search_policy"
            or tool.entry.risk_level != "retrieval"
            or tool.entry.side_effect != "retrieval"
        ):
            return self._rejection("unsafe_tool_request", f"{context.caller} is not allowed to invoke {name!r}")

        try:
            validated_input = tool.entry.input_schema.model_validate(input_data)
        except ValidationError as exc:
            return self._rejection("validation_error", str(exc))

        try:
            raw_result = await tool.adapter(validated_input, context)
        except Exception as exc:
            return self._rejection("tool_error", str(exc), retryable=True)

        try:
            return self._to_execution_result(tool.entry, raw_result)
        except (ValidationError, AttributeError, TypeError) as exc:
            return self._rejection("validation_error", str(exc))

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
        if not issubclass(output_schema, ToolOutput):
            raise ValueError(f"Tool {entry.name!r} output_schema must inherit ToolOutput")
        if not entry.description or not entry.when_to_use:
            raise ValueError(f"Tool {entry.name!r} must include prompt selection metadata")

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
            evidence_refs=_policy_evidence_refs_from_data(data),
        )

    def _rejection(self, error_code: str, message: str, *, retryable: bool = False) -> ToolExecutionResult:
        return ToolExecutionResult(
            status="error",
            error=ToolExecutionError(error_code=error_code, message=message, retryable=retryable),
        )


def _policy_evidence_refs_from_data(data: dict[str, Any]) -> list[dict[str, Any]]:
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
                "section": item.get("section"),
                "confidence": item.get("score"),
            }
        )
    return refs
