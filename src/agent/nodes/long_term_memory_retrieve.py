from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.long_term import LongTermMemoryService
from src.memory.repository import LongTermMemoryRepository
from src.memory.schemas import CaseMemorySearchRequest


_PROFILE_KEYS = ("memory_id", "memory_kind", "content", "source_type", "source_ref", "review_status", "version")
_CASE_KEYS = ("case_memory_id", "excerpt", "applicability", "outcome", "caveats", "score", "source_refs", "policy_refs")
_SOURCE_REF_KEYS = {
    "source_type",
    "run_id",
    "event_id",
    "conversation_message_id",
    "tool_result_id",
    "agent_run_id",
    "business_object_type",
    "business_object_id",
    "policy_version",
    "outcome_id",
}
_CASE_POLICY_REF_KEYS = {"doc_key", "chunk_id", "policy_version", "policy_family", "title", "section"}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def long_term_memory_retrieve(state: AgentState, config: RunnableConfig) -> dict:
    """Load reviewed long-term and case memory as contextual prompt snippets."""
    started_at = _now_iso()
    configurable = (config.get("configurable") or {}) if config else {}
    session = configurable.get("session")
    tenant_id = _uuid_or_none(state.get("tenant_id"))

    profile_service = configurable.get("long_term_memory_service")
    case_service = configurable.get("case_memory_service")
    if tenant_id is None or (session is None and (profile_service is None or case_service is None)):
        return _memory_result(
            state,
            started_at,
            source="reviewed_memory_unavailable",
            long_term_memory=[],
            case_memory=[],
            fallback_reason="missing_dependencies",
        )

    try:
        if profile_service is None:
            profile_service = LongTermMemoryService(LongTermMemoryRepository(session))
        if case_service is None:
            case_service = CaseMemoryService(CaseMemoryRepository(session))

        scopes = _memory_scopes(state)
        profile_items = await profile_service.retrieve_profile_memory(
            tenant_id=tenant_id,
            scopes=scopes,
            limit=5,
        )
        case_result = await case_service.retrieve_reviewed(
            CaseMemorySearchRequest(
                tenant_id=tenant_id,
                scopes=scopes,
                case_type=_case_type(state),
                limit=5,
            )
        )
    except Exception:
        result = _memory_result(
            state,
            started_at,
            source="reviewed_memory_unavailable",
            long_term_memory=[],
            case_memory=[],
            fallback_reason="service_error",
        )
        result["node_errors"] = (state.get("node_errors") or []) + [
            {"node": "long_term_memory_retrieve", "error_code": "REVIEWED_MEMORY_UNAVAILABLE"}
        ]
        return result

    long_term_memory = [_item for item in profile_items if (_item := _project_profile_memory(item))]
    case_memory = [_item for item in getattr(case_result, "items", []) if (_item := _project_case_memory(item))]
    source = "reviewed_memory" if long_term_memory or case_memory else "no_reviewed_memory"
    return _memory_result(
        state,
        started_at,
        source=source,
        long_term_memory=long_term_memory,
        case_memory=case_memory,
        fallback_reason=None,
    )


def _memory_result(
    state: AgentState,
    started_at: str,
    *,
    source: str,
    long_term_memory: list[dict[str, Any]],
    case_memory: list[dict[str, Any]],
    fallback_reason: str | None,
) -> dict[str, Any]:
    retrieved = len(long_term_memory) + len(case_memory)
    continuity_claimed = retrieved > 0
    metrics = {
        "source": source,
        "continuity_claimed": continuity_claimed,
        "retrieved": retrieved,
        "profile_count": len(long_term_memory),
        "case_count": len(case_memory),
        "fallback_reason": fallback_reason,
    }
    step = {
        "node": "long_term_memory_retrieve",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": metrics,
    }
    return {
        "long_term_memory": long_term_memory,
        "case_memory": case_memory,
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "long_term_memory_retrieve": metrics,
        },
        "trace_steps": (state.get("trace_steps") or []) + [step],
    }


def _uuid_or_none(value: Any) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _memory_scopes(state: AgentState) -> list[tuple[str, str]]:
    slots = _merged_slots(state)
    candidates = [
        ("tenant", state.get("tenant_id")),
        ("user", state.get("user_id")),
        ("thread", state.get("thread_id")),
        ("merchant", slots.get("merchant_id")),
        ("case", slots.get("refund_case_id")),
    ]
    scopes: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for scope_type, raw_scope_id in candidates:
        scope_id = str(raw_scope_id or "").strip()
        if not scope_id:
            continue
        scope = (scope_type, scope_id)
        if scope not in seen:
            scopes.append(scope)
            seen.add(scope)
    return scopes


def _merged_slots(state: AgentState) -> dict[str, Any]:
    slots: dict[str, Any] = {}
    for candidate in (state.get("active_slots"), state.get("extracted_slots"), state.get("candidate_slots")):
        if isinstance(candidate, Mapping):
            slots.update({str(key): value for key, value in candidate.items() if value is not None})
    return slots


def _case_type(state: AgentState) -> str | None:
    value = state.get("primary_intent") or state.get("current_intent")
    if not value:
        return None
    return str(value)[:64]


def _project_profile_memory(item: Any) -> dict[str, Any] | None:
    mapping = _mapping(item)
    content = _safe_text(mapping.get("content") or mapping.get("summary"))
    if not content:
        return None
    projected = _select_keys(mapping, _PROFILE_KEYS)
    projected["content"] = content
    if "source_ref" in projected:
        projected["source_ref"] = _safe_ref_mapping(projected["source_ref"], _SOURCE_REF_KEYS)
    if not projected.get("source_ref"):
        projected.pop("source_ref", None)
    return projected


def _project_case_memory(item: Any) -> dict[str, Any] | None:
    mapping = _mapping(item)
    case_memory_id = _safe_text(mapping.get("case_memory_id") or mapping.get("memory_id") or mapping.get("id"))
    excerpt = _safe_text(mapping.get("excerpt") or mapping.get("summary"))
    if not case_memory_id or not excerpt:
        return None
    projected = _select_keys(mapping, _CASE_KEYS)
    projected["case_memory_id"] = case_memory_id
    projected["excerpt"] = excerpt
    if "source_refs" in projected:
        projected["source_refs"] = _safe_ref_list(projected["source_refs"], _SOURCE_REF_KEYS)
    if "policy_refs" in projected:
        projected["policy_refs"] = _safe_ref_list(projected["policy_refs"], _CASE_POLICY_REF_KEYS)
    return projected


def _mapping(item: Any) -> dict[str, Any]:
    if item is None:
        return {}
    if hasattr(item, "model_dump"):
        return dict(item.model_dump(mode="json", exclude_none=True))
    if isinstance(item, Mapping):
        return dict(item)
    return {key: value for key, value in vars(item).items() if not key.startswith("_")}


def _select_keys(mapping: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: _json_safe(mapping[key]) for key in keys if key in mapping and mapping[key] is not None}


def _safe_ref_mapping(value: Any, allowed_keys: set[str]) -> dict[str, Any]:
    mapping = _mapping(value)
    return {key: _safe_text(mapping[key]) for key in allowed_keys if key in mapping and _safe_text(mapping[key])}


def _safe_ref_list(value: Any, allowed_keys: set[str]) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        values = [value]
    elif isinstance(value, list | tuple):
        values = list(value)
    else:
        values = []
    return [ref for item in values if (ref := _safe_ref_mapping(item, allowed_keys))]


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, int | float | bool):
        return str(value)
    return ""


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value
