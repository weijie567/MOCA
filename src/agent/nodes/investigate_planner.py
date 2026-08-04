from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator


INVESTIGATE_ALLOWED_TOOL_NAMES = frozenset(
    {
        "get_order",
        "get_refund_case",
        "get_ticket",
        "get_logistics",
        "get_merchant_risk",
        "business_query",
        "query_business_metric",
        "search_policy",
        "search_sop",
        "search_case_memory",
    }
)
INVESTIGATE_STOP_REASONS = frozenset(
    {
        "enough_evidence",
        "no_more_useful_tools",
        "max_iterations_reached",
        "unrecoverable_error",
    }
)


class InvestigatePlannerDecision(BaseModel):
    """Structured decision contract for one investigate ReAct iteration."""

    model_config = ConfigDict(extra="forbid")

    next_tool: str | None = None
    args: dict[str, Any] | None = None
    reason: str | None = None
    stop: Literal[True] | None = None
    stop_reason: (
        Literal[
            "enough_evidence",
            "no_more_useful_tools",
            "max_iterations_reached",
            "unrecoverable_error",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def _validate_choice(self) -> "InvestigatePlannerDecision":
        has_tool_fields = any(value is not None for value in (self.next_tool, self.args, self.reason))
        has_stop_fields = self.stop is True or self.stop_reason is not None
        if has_tool_fields == has_stop_fields:
            raise ValueError("Planner output must contain exactly one tool action or one stop decision")
        if has_stop_fields:
            if self.stop is not True or self.stop_reason not in INVESTIGATE_STOP_REASONS:
                raise ValueError("Planner stop output must contain stop=true and a valid stop_reason")
            return self
        if not isinstance(self.next_tool, str) or not self.next_tool.strip():
            raise ValueError("Planner tool output must contain next_tool")
        if not isinstance(self.args, dict):
            raise ValueError("Planner tool output must contain object args")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("Planner tool output must contain reason")
        return self

    def to_step(self) -> dict[str, Any]:
        if self.stop is True:
            return {"stop": True, "stop_reason": self.stop_reason}
        return {
            "next_tool": self.next_tool,
            "args": dict(self.args or {}),
            "reason": self.reason,
        }


def parse_investigate_planner_decision(raw: Any) -> dict[str, Any]:
    """Parse and strictly validate raw planner output into the runtime step shape."""

    payload = _raw_to_payload(raw)
    try:
        decision = InvestigatePlannerDecision.model_validate(payload)
    except (ValidationError, ValueError) as exc:
        raise ValueError("Planner output failed schema validation") from exc
    return decision.to_step()


def _raw_to_payload(raw: Any) -> Any:
    if isinstance(raw, InvestigatePlannerDecision):
        return raw.model_dump(exclude_none=True)
    if isinstance(raw, BaseModel):
        return raw.model_dump(exclude_none=True)
    if isinstance(raw, dict):
        return raw
    content = getattr(raw, "content", None)
    if isinstance(content, str):
        return _json_payload(content)
    if isinstance(raw, str):
        return _json_payload(raw)
    raise ValueError("Planner output must be a JSON object")


def _json_payload(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Planner output must be valid JSON") from exc
