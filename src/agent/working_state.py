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
VERIFIED_EVIDENCE_PROJECTION_STATUSES = frozenset({"verified", "partial"})


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
    target_merchant_id: str | None = None
    business_fact_ref_count: int = 0
    verified_evidence_ref_count: int = 0
    claim_verification_ref: str | None = None
    risk_decision_ref: str | None = None


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
    return _string_list(_session_context_memory(state).get("unresolved_questions"))


def _constraints(state: AgentState) -> list[str]:
    explicit = _string_list(state.get("constraints"))
    return explicit if explicit else list(DEFAULT_CONSTRAINTS)


def _business_context_refs(state: AgentState) -> list[dict[str, Any]]:
    explicit = _dict_list(state.get("business_context_refs"))
    if explicit:
        return explicit

    for value in (
        state.get("last_business_context_refs"),
        _session_context_memory(state).get("last_business_context_refs"),
    ):
        refs = _business_ref_payload(value)
        if refs:
            return refs

    context = _mapping(state.get("business_context"))
    return _dict_list(context.get("business_fact_refs"))


def _session_context_memory(state: AgentState) -> Mapping[str, Any]:
    session_context = _mapping(state.get("session_context"))
    if session_context:
        slot_continuity = _mapping(session_context.get("slot_continuity"))
        if slot_continuity:
            return slot_continuity
        if (
            "continuity_claimed" in session_context
            or "unresolved_questions" in session_context
            or "last_business_context_refs" in session_context
        ):
            return session_context
    return _mapping(state.get("session_memory"))


def _business_ref_payload(value: Any) -> list[dict[str, Any]]:
    mapping = _mapping(value)
    if not mapping:
        return []
    refs = _dict_list(mapping.get("business_fact_refs"))
    if refs:
        return refs
    return [_safe_mapping(mapping)]


def _retrieved_evidence_refs(state: AgentState) -> list[dict[str, Any]]:
    package = _mapping(state.get("verified_evidence_package"))
    status = _as_str(package.get("status"))
    if status not in VERIFIED_EVIDENCE_PROJECTION_STATUSES:
        return []

    evidence_map = _verified_evidence_map(state, package)
    safe_support_refs = _claim_safe_support_refs(state, evidence_map)
    if safe_support_refs:
        return safe_support_refs

    prompt_safe_refs = _package_prompt_safe_refs(package, evidence_map)
    if prompt_safe_refs:
        return prompt_safe_refs

    return _evidence_ref_list(list(evidence_map.values()))


def _claim_safe_support_refs(state: AgentState, evidence_map: Mapping[str, Any]) -> list[dict[str, Any]]:
    bundle = _mapping(state.get("claim_verification_bundle"))
    for value in (bundle.get("safe_support_refs"), state.get("safe_support_refs")):
        refs = _resolved_evidence_refs(value, evidence_map)
        if refs:
            return refs
    return []


def _package_prompt_safe_refs(package: Mapping[str, Any], evidence_map: Mapping[str, Any]) -> list[dict[str, Any]]:
    projection = _mapping(package.get("prompt_projection"))
    refs = _resolved_evidence_refs(projection.get("safe_refs"), evidence_map)
    if refs:
        return refs

    citation_refs = []
    for citation in _mapping_sequence(projection.get("citations")):
        ref_id = citation.get("evidence_id")
        if isinstance(ref_id, str) and ref_id:
            citation_refs.append(ref_id)
    return _resolved_evidence_refs(citation_refs, evidence_map)


def _verified_evidence_map(state: AgentState, package: Mapping[str, Any]) -> dict[str, Any]:
    refs: dict[str, Any] = {}
    for raw_map in (_mapping(package.get("evidence_map")), _mapping(state.get("evidence_map"))):
        for key, value in raw_map.items():
            evidence_id = _evidence_id(value) or str(key)
            refs[evidence_id] = value
    return refs


def _resolved_evidence_refs(value: Any, evidence_map: Mapping[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _sequence_values(value):
        resolved = evidence_map.get(item) if isinstance(item, str) else item
        mapping = _mapping(resolved)
        if not mapping:
            continue
        evidence_id = _evidence_id(mapping)
        if evidence_id and evidence_id in seen:
            continue
        if evidence_id:
            seen.add(evidence_id)
        refs.append(mapping)
    return _evidence_ref_list(refs)


def _sequence_values(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    return list(value)


def _evidence_id(value: Any) -> str | None:
    mapping = _mapping(value)
    evidence_id = mapping.get("evidence_id")
    return evidence_id if isinstance(evidence_id, str) and evidence_id else None


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
    draft = _mapping(state.get("action_draft"))
    artifact = _select_safe_fields(
        draft,
        (
            "draft_id",
            "action_type",
            "status",
            "summary",
            "target_merchant_id",
            "claim_verification_ref",
            "risk_decision_ref",
        ),
    )
    if not artifact:
        return None
    artifact["business_fact_ref_count"] = len(_mapping_sequence(draft.get("business_fact_refs")))
    artifact["verified_evidence_ref_count"] = len(_mapping_sequence(draft.get("verified_evidence_refs")))
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
    return [mapping for item in value if (mapping := _mapping(item))]


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return {}


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
