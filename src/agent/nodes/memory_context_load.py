from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.nodes.reviewed_memory_context_retrieve import reviewed_memory_context_retrieve
from src.agent.state import AgentState

_HELPER_NODE = "reviewed_memory_context_retrieve"
_CANONICAL_NODE = "memory_context_load"
_UNAVAILABLE_FALLBACK_REASONS = {"service_error", "missing_memory_context_services"}


async def memory_context_load(
    state: AgentState,
    config: RunnableConfig,
    *,
    memory_context_service_cls: Any | None = None,
    long_term_memory_repository_cls: Any | None = None,
    case_memory_repository_cls: Any | None = None,
    long_term_memory_service_cls: Any | None = None,
    case_memory_service_cls: Any | None = None,
    case_working_context_lifecycle_adapter_cls: Any | None = None,
) -> dict:
    """Canonical contextual memory graph node.

    The reviewed-memory helper owns storage/service semantics. This node owns
    active graph identity and the Phase 55 contextual-only metrics contract.
    """
    result = await reviewed_memory_context_retrieve(
        state,
        config,
        memory_context_service_cls=memory_context_service_cls,
        long_term_memory_repository_cls=long_term_memory_repository_cls,
        case_memory_repository_cls=case_memory_repository_cls,
        long_term_memory_service_cls=long_term_memory_service_cls,
        case_memory_service_cls=case_memory_service_cls,
        case_working_context_lifecycle_adapter_cls=case_working_context_lifecycle_adapter_cls,
    )
    result = dict(result)
    canonical_metrics = _canonical_metrics(state, result)
    result["llm_outputs"] = {
        **_without_legacy_metrics(state.get("llm_outputs")),
        **_without_legacy_metrics(result.get("llm_outputs")),
        _CANONICAL_NODE: canonical_metrics,
    }
    result["trace_steps"] = _canonical_trace_steps(state, result, canonical_metrics)
    if "node_errors" in result:
        result["node_errors"] = _canonical_node_errors(result.get("node_errors"))
    return result


def _canonical_metrics(state: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    long_term_memory = _list_value(result.get("long_term_memory"))
    case_memory = _list_value(result.get("case_memory"))
    status_ref = _mapping(result.get("reviewed_memory_context_retrieve_status"))
    fallback_reason = status_ref.get("fallback_reason")
    filter_reasons = _string_list(status_ref.get("filter_reasons"))
    source = _source(
        long_term_memory=long_term_memory,
        case_memory=case_memory,
        fallback_reason=fallback_reason,
    )
    return {
        "source": source,
        "authority_class": "contextual_only",
        "usage_labels": _usage_labels(state, result, source=source),
        "long_term_count": len(long_term_memory),
        "case_count": len(case_memory),
        "fallback_reason": fallback_reason if fallback_reason is None else str(fallback_reason),
        "filter_reasons": filter_reasons,
    }


def _usage_labels(state: Mapping[str, Any], result: Mapping[str, Any], *, source: str) -> list[str]:
    labels: list[str] = []
    if _has_session_continuity(state, result):
        labels.append("session_continuity")
    if _list_value(result.get("long_term_memory")):
        labels.append("explicit_preference_memory")
    if _list_value(result.get("case_memory")):
        labels.append("reviewed_case_precedent")
    if result.get("case_working_context_lifecycle_status") is not None:
        labels.append("case_working_context_status")
    if source == "reviewed_memory_skipped":
        labels.append("reviewed_memory_skipped")
    if source == "reviewed_memory_unavailable":
        labels.append("reviewed_memory_unavailable")
    return list(dict.fromkeys(labels))


def _source(*, long_term_memory: list[Any], case_memory: list[Any], fallback_reason: Any) -> str:
    if long_term_memory or case_memory:
        return "reviewed_memory"
    if fallback_reason in _UNAVAILABLE_FALLBACK_REASONS:
        return "reviewed_memory_unavailable"
    if fallback_reason:
        return "reviewed_memory_skipped"
    return "no_reviewed_memory"


def _canonical_trace_steps(
    state: Mapping[str, Any],
    result: Mapping[str, Any],
    canonical_metrics: Mapping[str, Any],
) -> list[Any]:
    prior_steps = _list_value(state.get("trace_steps"))
    trace_steps = _list_value(result.get("trace_steps"))
    canonical_steps: list[Any] = []
    for index, step in enumerate(trace_steps):
        if index >= len(prior_steps) and isinstance(step, Mapping) and step.get("node") == _HELPER_NODE:
            updated_step = dict(step)
            updated_step["node"] = _CANONICAL_NODE
            updated_step["metrics_json"] = dict(canonical_metrics)
            canonical_steps.append(updated_step)
        else:
            canonical_steps.append(step)
    return canonical_steps


def _canonical_node_errors(errors: Any) -> list[Any]:
    mapped_errors: list[Any] = []
    for error in _list_value(errors):
        if isinstance(error, Mapping) and error.get("node") == _HELPER_NODE:
            mapped_error = dict(error)
            mapped_error["node"] = _CANONICAL_NODE
            mapped_errors.append(mapped_error)
        else:
            mapped_errors.append(error)
    return mapped_errors


def _without_legacy_metrics(value: Any) -> dict[str, Any]:
    metrics = dict(value) if isinstance(value, Mapping) else {}
    metrics.pop("long_term_memory_retrieve", None)
    return metrics


def _has_session_continuity(state: Mapping[str, Any], result: Mapping[str, Any]) -> bool:
    if isinstance(state.get("session_context_load_status"), Mapping):
        return True
    bundle = _mapping(result.get("memory_context_bundle"))
    return isinstance(bundle.get("session_context"), Mapping)


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
