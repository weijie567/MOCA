from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from pydantic import ValidationError

from src.agent.working_state import WorkingStateV1, WorkingToolResultRef
from src.tools.contracts import ToolResultPromptSummary


_BUSINESS_ID_RE = re.compile(r"\b(?:ORD|RF|TK|MER|REFUND|ORDER)-[A-Z0-9-]+\b")
_UNSAFE_KEY_TOKENS = (
    "raw",
    "payload",
    "body",
    "full",
    "private",
    "reasoning",
    "debug",
    "trace",
    "snapshot",
    "hash",
    "completion",
    "authority",
)
_BUSINESS_SAFE_KEYS = (
    "id",
    "order_id",
    "order_no",
    "refund_case_id",
    "refund_case_no",
    "ticket_id",
    "merchant_id",
    "status",
    "merchant_risk_level",
    "requested_amount",
    "approved_amount",
    "amount",
    "currency",
    "refund_reason",
    "logistics_status",
    "source_system",
    "resource_type",
    "resource_id",
    "resource_version",
    "summary",
)
_REF_SAFE_KEYS = (
    "source_system",
    "resource_type",
    "resource_id",
    "resource_version",
    "evidence_id",
    "doc_key",
    "chunk_id",
    "policy_version",
    "rank",
    "score",
    "summary",
)
_POLICY_SAFE_KEYS = ("evidence_id", "doc_key", "chunk_id", "policy_version", "title", "section")
_TOOL_REF_KEYS = ("resource_type", "resource_id", "source_system", "evidence_id", "doc_key", "chunk_id")
_MAX_LINE_CHARS = 500


def project_working_state_for_prompt(working_state: WorkingStateV1, *, max_chars: int = 1600) -> str:
    lines: list[str] = []
    _append_line(lines, "schema", working_state.schema_version)
    _append_line(lines, "thread", working_state.thread_id)
    _append_line(lines, "run", working_state.run_id)
    _append_line(lines, "turn", working_state.turn_id)
    _append_line(lines, "goal", working_state.current_goal)
    _append_line(lines, "intent", working_state.current_intent)
    _append_line(lines, "active_slots", _format_mapping(working_state.active_slots, _BUSINESS_SAFE_KEYS))
    _append_line(lines, "open_questions", _format_sequence(working_state.open_questions))
    _append_line(lines, "constraints", _format_sequence(working_state.constraints))
    _append_line(lines, "business_refs", _format_ref_list(working_state.business_context_refs))
    _append_line(lines, "evidence_refs", _format_ref_list(working_state.retrieved_evidence_refs))
    for result in working_state.recent_tool_results:
        _append_line(lines, "tool_result", project_tool_result_summary(result))
    if working_state.pending_confirmation:
        _append_line(lines, "pending_confirmation", _format_mapping(working_state.pending_confirmation, _BUSINESS_SAFE_KEYS))
    if working_state.draft_artifact:
        _append_line(lines, "draft_artifact", _format_mapping(working_state.draft_artifact.model_dump(), _BUSINESS_SAFE_KEYS))
    return _bounded("\n".join(lines), max_chars)


def project_business_context_for_prompt(context: Mapping[str, Any] | None, *, max_chars: int = 1200) -> str:
    mapping = _mapping(context)
    if not mapping:
        return ""

    lines: list[str] = []
    for key in ("order", "refund_case", "ticket", "merchant", "logistics", "merchant_risk"):
        nested = _mapping(mapping.get(key))
        formatted = _format_mapping(nested, _BUSINESS_SAFE_KEYS)
        if formatted:
            _append_line(lines, key, formatted)

    top_level = _format_mapping(mapping, _BUSINESS_SAFE_KEYS)
    if top_level:
        _append_line(lines, "business", top_level)

    refs = _format_ref_list(_mapping_sequence(mapping.get("business_fact_refs")))
    if refs:
        _append_line(lines, "business_refs", refs)

    return _bounded("\n".join(lines), max_chars)


def project_tool_result_summary(value: ToolResultPromptSummary | WorkingToolResultRef | Mapping[str, Any], *, max_chars: int = 900) -> str:
    summary = _tool_summary_model(value)
    if summary is None:
        return ""

    lines = [
        f"tool={summary.tool_name}",
        f"status={summary.status}",
        f"tool_call_id={summary.tool_call_id}",
        f"tool_result_id={summary.tool_result_id}",
    ]
    prompt_summary = _safe_scalar(summary.prompt_summary) or _safe_scalar(summary.summary)
    if prompt_summary:
        lines.append(f"summary={_bounded(prompt_summary, _MAX_LINE_CHARS)}")
    business_refs = _format_ref_list(summary.business_fact_refs, keys=_TOOL_REF_KEYS)
    if business_refs:
        lines.append(f"business_refs={business_refs}")
    policy_refs = _format_ref_list(summary.policy_evidence_refs, keys=_TOOL_REF_KEYS)
    if policy_refs:
        lines.append(f"policy_refs={policy_refs}")
    if summary.raw_result_ref:
        lines.append(f"raw_result_ref={_bounded(summary.raw_result_ref, 160)}")
    if summary.audit_ref:
        lines.append(f"audit_ref={_bounded(summary.audit_ref, 160)}")
    return _bounded("; ".join(lines), max_chars)


def project_policy_refs_for_prompt(snippets: Sequence[Any] | None, *, max_chars: int = 6000) -> str:
    lines: list[str] = []
    for item in _sequence(snippets):
        mapping = _mapping(item.model_dump(mode="json") if hasattr(item, "model_dump") else item)
        fields = _format_mapping(mapping, _POLICY_SAFE_KEYS)
        text = _safe_scalar(mapping.get("text") or mapping.get("excerpt") or mapping.get("snippet"))
        if text:
            fields = f"{fields}; excerpt={_bounded(text, 1800)}" if fields else f"excerpt={_bounded(text, 1800)}"
        if fields:
            lines.append(fields)
    return _bounded("\n".join(lines), max_chars)


def project_recent_message_for_prompt(message: Mapping[str, Any], *, max_chars: int = 500) -> str:
    role = _safe_scalar(message.get("role")) or "message"
    content = _safe_scalar(message.get("content")) or ""
    if not content:
        return ""
    return _bounded(f"{role}: {content}", max_chars)


def project_candidate_slot_hints_for_prompt(candidate_slots: Mapping[str, Any] | None, *, max_chars: int = 700) -> str:
    mapping = _mapping(candidate_slots)
    formatted = _format_mapping(mapping, tuple(str(key) for key in mapping.keys()))
    if not formatted:
        return ""
    return _bounded(f"Candidate slot hints: {formatted}. Validate against the user text; do not copy hints blindly.", max_chars)


def extract_business_ids_from_prompt_parts(*parts: Any) -> list[str]:
    found: set[str] = set()
    for part in parts:
        if isinstance(part, str):
            found.update(_BUSINESS_ID_RE.findall(part))
        elif isinstance(part, Mapping):
            found.update(_BUSINESS_ID_RE.findall(project_business_context_for_prompt(part, max_chars=4000)))
        elif isinstance(part, Sequence) and not isinstance(part, str | bytes | bytearray):
            found.update(extract_business_ids_from_prompt_parts(*part))
    return sorted(found)


def _tool_summary_model(value: ToolResultPromptSummary | WorkingToolResultRef | Mapping[str, Any]) -> ToolResultPromptSummary | None:
    if isinstance(value, ToolResultPromptSummary):
        return value
    if isinstance(value, WorkingToolResultRef):
        return ToolResultPromptSummary.model_validate(value.model_dump(mode="json"))
    mapping = _mapping(value)
    payload = {
        key: mapping.get(key)
        for key in (
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
        )
        if key in mapping
    }
    try:
        return ToolResultPromptSummary.model_validate(payload)
    except ValidationError:
        return None


def _format_ref_list(values: Sequence[Any] | None, keys: Sequence[str] = _REF_SAFE_KEYS) -> str:
    items: list[str] = []
    for item in _sequence(values):
        formatted = _format_mapping(_mapping(item), keys)
        if formatted:
            items.append(formatted)
    return " | ".join(items)


def _format_mapping(mapping: Mapping[str, Any], keys: Sequence[str]) -> str:
    parts: list[str] = []
    for key in keys:
        if key not in mapping or _is_unsafe_key(key):
            continue
        value = _safe_scalar(mapping.get(key))
        if value:
            parts.append(f"{key}={_bounded(value, 180)}")
    return ", ".join(parts)


def _append_line(lines: list[str], label: str, value: Any) -> None:
    if value is None:
        return
    text = _safe_scalar(value)
    if text:
        lines.append(f"{label}: {_bounded(text, _MAX_LINE_CHARS)}")


def _safe_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, bool | int | float):
        return str(value)
    return ""


def _format_sequence(values: Sequence[Any] | None) -> str:
    items = [_safe_scalar(value) for value in _sequence(values)]
    return "; ".join(item for item in items if item)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_sequence(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in _sequence(value) if isinstance(item, Mapping)]


def _sequence(value: Any) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    return list(value)


def _is_unsafe_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _UNSAFE_KEY_TOKENS)


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _bounded(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    marker = " [truncated]"
    return value[: max(0, max_chars - len(marker))] + marker
