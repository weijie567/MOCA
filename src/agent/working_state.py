"""Prompt-safe projection of the current AgentState."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.agent.state import AgentState
from src.tools.contracts import ToolResultPromptSummary

PROMPT_UNSAFE_STATE_KEYS = frozenset(
    {
        "business_context",
        "retrieved_evidence",
        "approval_result",
        "proposed_action",
        "action_draft",
        "draft_outcome",
        "llm_outputs",
        "trace_steps",
        "node_errors",
    }
)
PROMPT_UNSAFE_FIELD_NAMES = frozenset(
    {
        "raw",
        "raw_args",
        "raw_payload",
        "raw_prompt",
        "raw_tool_output",
        "payload",
        "body",
        "full_text",
        "text",
        "completion",
        "raw_completion",
        "private_reasoning",
        "reasoning",
        "snapshot_json",
        "safety_snapshot_json",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
        "action_payload_hash",
        "edited_action_json",
        "proposed_action",
        "approval_result",
        "draft_outcome",
        "traceback",
        "debug",
    }
)
TOOL_RESULT_KEYS = frozenset(
    {
        "tool_call_id",
        "tool_result_id",
        "tool_name",
        "status",
        "summary",
        "prompt_summary",
        "business_fact_refs",
        "policy_evidence_refs",
        "raw_result_ref",
        "audit_ref",
    }
)
EVIDENCE_REF_KEYS = frozenset(
    {
        "schema_version",
        "tenant_id",
        "evidence_id",
        "doc_key",
        "chunk_id",
        "policy_version",
        "text_hash",
        "retrieved_at",
        "retrieval_config_version",
        "score",
        "rank",
    }
)
DEFAULT_CONSTRAINTS = [
    "tool facts override session memory",
    "policy evidence is required before recommendation",
    "high risk action requires approval",
]


class WorkingToolResultRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_call_id: str
    tool_result_id: str
    tool_name: str
    status: str
    summary: str
    prompt_summary: str
    business_fact_refs: list[dict[str, Any]] = Field(default_factory=list)
    policy_evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    raw_result_ref: str | None = None
    audit_ref: str | None = None


class WorkingDraftArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str | None = None
    action_type: str | None = None
    status: str | None = None
    summary: str | None = None


class WorkingStateV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["working_state.v1"] = "working_state.v1"
    thread_id: str | None = None
    run_id: str | None = None
    turn_id: str | None = None
    current_goal: str | None = None
    current_intent: str | None = None
    active_slots: dict[str, Any] = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    business_context_refs: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    recent_tool_results: list[WorkingToolResultRef] = Field(default_factory=list)
    pending_confirmation: dict[str, Any] | None = None
    draft_artifact: WorkingDraftArtifact | None = None


def project_working_state(state: AgentState) -> WorkingStateV1:
    """Project AgentState into a strict prompt-facing working-state view."""

    return WorkingStateV1(
        thread_id=_as_str(state.get("thread_id")),
        run_id=_as_str(state.get("run_id") or state.get("current_run_id")),
        turn_id=_as_str(state.get("turn_id")),
        current_goal=_current_goal(state),
        current_intent=_current_intent(state),
        active_slots=_safe_mapping(state.get("active_slots")),
        open_questions=_open_questions(state),
        constraints=_constraints(state),
        business_context_refs=_business_context_refs(state),
        retrieved_evidence_refs=_retrieved_evidence_refs(state),
        recent_tool_results=_recent_tool_results(state),
        pending_confirmation=_pending_confirmation(state),
        draft_artifact=_draft_artifact(state),
    )


def _current_goal(state: AgentState) -> str | None:
    return _as_str(
        state.get("current_goal")
        or state.get("requested_operation")
        or state.get("current_intent")
        or state.get("primary_intent")
    )


def _current_intent(state: AgentState) -> str | None:
    return _as_str(state.get("current_intent") or state.get("primary_intent") or state.get("last_intent"))


def _open_questions(state: AgentState) -> list[str]:
    explicit = _string_list(state.get("open_questions"))
    if explicit:
        return explicit
    session_memory = _mapping(state.get("session_memory"))
    return _string_list(session_memory.get("unresolved_questions"))


def _constraints(state: AgentState) -> list[str]:
    explicit = _string_list(state.get("constraints"))
    return explicit if explicit else list(DEFAULT_CONSTRAINTS)


def _business_context_refs(state: AgentState) -> list[dict[str, Any]]:
    explicit = _dict_list(state.get("business_context_refs"))
    if explicit:
        return explicit

    for value in (
        state.get("last_business_context_refs"),
        _mapping(state.get("session_memory")).get("last_business_context_refs"),
    ):
        refs = _business_ref_payload(value)
        if refs:
            return refs

    context = _mapping(state.get("business_context"))
    return _dict_list(context.get("business_fact_refs"))


def _business_ref_payload(value: Any) -> list[dict[str, Any]]:
    mapping = _mapping(value)
    if not mapping:
        return []
    refs = _dict_list(mapping.get("business_fact_refs"))
    if refs:
        return refs
    return [_safe_mapping(mapping)]


def _retrieved_evidence_refs(state: AgentState) -> list[dict[str, Any]]:
    for value in (
        state.get("retrieved_evidence_refs"),
        state.get("evidence_refs"),
        state.get("policy_evidence"),
        _mapping(state.get("retrieved_evidence")).get("evidence_refs"),
    ):
        refs = _evidence_ref_list(value)
        if refs:
            return refs
    return []


def _recent_tool_results(state: AgentState) -> list[WorkingToolResultRef]:
    results: list[WorkingToolResultRef] = []
    for value in _mapping_sequence(state.get("tool_results")):
        payload = {key: _safe_value(value.get(key)) for key in TOOL_RESULT_KEYS if key in value}
        try:
            prompt_summary = ToolResultPromptSummary.model_validate(payload)
            results.append(WorkingToolResultRef.model_validate(prompt_summary.model_dump(mode="json")))
        except ValidationError:
            continue
    return results


def _pending_confirmation(state: AgentState) -> dict[str, Any] | None:
    for value in (state.get("pending_confirmation"), state.get("clarification_request")):
        mapping = _mapping(value)
        if not mapping:
            continue
        safe = _select_safe_fields(mapping, ("confirmation_id", "question", "status", "summary"))
        if safe:
            return safe
    return None


def _draft_artifact(state: AgentState) -> WorkingDraftArtifact | None:
    artifact = _select_safe_fields(
        _mapping(state.get("action_draft")), ("draft_id", "action_type", "status", "summary")
    )
    if not artifact:
        return None
    return WorkingDraftArtifact.model_validate(artifact)


def _select_safe_fields(value: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for key in keys:
        if key not in value:
            continue
        safe_value = _safe_value(value[key])
        if safe_value is not None:
            selected[key] = safe_value
    return selected


def _evidence_ref_list(value: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for item in _mapping_sequence(value):
        safe = {key: _safe_value(item.get(key)) for key in EVIDENCE_REF_KEYS if key in item}
        if safe:
            refs.append(safe)
    return refs


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [_safe_mapping(item) for item in _mapping_sequence(value)]


def _mapping_sequence(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_mapping(value: Any) -> dict[str, Any]:
    mapping = _mapping(value)
    return {
        str(key): _safe_value(item)
        for key, item in mapping.items()
        if str(key) not in PROMPT_UNSAFE_FIELD_NAMES and _safe_value(item) is not None
    }


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return _safe_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_safe_value(item) for item in value if _safe_value(item) is not None]
    return str(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    return [item for item in (_as_str(item) for item in value) if item]


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


__all__ = [
    "WorkingDraftArtifact",
    "WorkingStateV1",
    "WorkingToolResultRef",
    "project_working_state",
]
