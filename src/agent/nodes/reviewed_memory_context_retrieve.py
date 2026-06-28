from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.state import AgentState
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.context_refs import ReviewedMemoryContextBundle, ReviewedMemoryContextRetrieveStatusV1
from src.memory.context_service import MemoryContextService
from src.memory.long_term import LongTermMemoryService
from src.memory.repository import LongTermMemoryRepository

_SERVICE_ERROR_CODE = "REVIEWED_MEMORY_CONTEXT_UNAVAILABLE"
_BUNDLE_SCHEMA_VERSION = "reviewed_memory_context_bundle.v1"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def reviewed_memory_context_retrieve(
    state: AgentState,
    config: RunnableConfig,
    *,
    memory_context_service_cls: Any | None = None,
    long_term_memory_repository_cls: Any | None = None,
    case_memory_repository_cls: Any | None = None,
    long_term_memory_service_cls: Any | None = None,
    case_memory_service_cls: Any | None = None,
) -> dict:
    """Load reviewed long-term/case memory through the trusted-scope memory boundary."""
    started_at = _now_iso()
    configurable = (config.get("configurable") or {}) if config else {}
    try:
        context_service = _context_service(
            configurable,
            memory_context_service_cls=memory_context_service_cls or MemoryContextService,
            long_term_memory_repository_cls=long_term_memory_repository_cls or LongTermMemoryRepository,
            case_memory_repository_cls=case_memory_repository_cls or CaseMemoryRepository,
            long_term_memory_service_cls=long_term_memory_service_cls or LongTermMemoryService,
            case_memory_service_cls=case_memory_service_cls or CaseMemoryService,
        )
        bundle = await context_service.load_reviewed_memory_context(
            trusted_context=configurable.get("trusted_context"),
            current_slots=_current_turn_slots(state),
            trusted_business_context=_trusted_business_context(state, configurable),
            requested_scopes=_requested_scopes(state, configurable),
            query=_case_memory_query(state),
            case_type=_case_type(state),
            limit=5,
        )
    except Exception:
        bundle = _empty_bundle(
            fallback_reason="service_error",
            status="unavailable",
            trusted_context=configurable.get("trusted_context"),
            current_slots=_current_turn_slots(state),
        )
        result = _context_result(state, started_at, bundle=bundle)
        result["node_errors"] = (state.get("node_errors") or []) + [
            {"node": "reviewed_memory_context_retrieve", "error_code": _SERVICE_ERROR_CODE}
        ]
        return result

    return _context_result(state, started_at, bundle=bundle)


def _context_service(
    configurable: Mapping[str, Any],
    *,
    memory_context_service_cls: Any,
    long_term_memory_repository_cls: Any,
    case_memory_repository_cls: Any,
    long_term_memory_service_cls: Any,
    case_memory_service_cls: Any,
) -> MemoryContextService:
    existing = configurable.get("memory_context_service")
    if existing is not None:
        return existing

    session = configurable.get("session")
    long_term_service = configurable.get("long_term_memory_service")
    case_service = configurable.get("case_memory_service")
    if long_term_service is None and session is not None:
        long_term_service = long_term_memory_service_cls(long_term_memory_repository_cls(session))
    if case_service is None and session is not None:
        case_service = case_memory_service_cls(case_memory_repository_cls(session))
    return memory_context_service_cls(
        long_term_memory_service=long_term_service,
        case_memory_service=case_service,
    )


def _context_result(state: AgentState, started_at: str, *, bundle: ReviewedMemoryContextBundle) -> dict[str, Any]:
    memory_context = bundle.model_dump(mode="json")
    memory_context["schema_version"] = _BUNDLE_SCHEMA_VERSION
    long_term_items = list(memory_context["long_term_items"])
    case_items = list(memory_context["case_items"])
    status_ref = dict(memory_context["status_ref"])
    metrics = _metrics(memory_context)
    step = {
        "node": "reviewed_memory_context_retrieve",
        "status": "completed",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": metrics,
    }
    return {
        "memory_context": memory_context,
        "memory_context_bundle": memory_context,
        "reviewed_memory_context_retrieve_status": status_ref,
        "long_term_memory": long_term_items,
        "case_memory": case_items,
        "llm_outputs": {
            **(state.get("llm_outputs") or {}),
            "reviewed_memory_context_retrieve": metrics,
        },
        "trace_steps": (state.get("trace_steps") or []) + [step],
    }


def _metrics(memory_context: Mapping[str, Any]) -> dict[str, Any]:
    long_term_items = memory_context.get("long_term_items") if isinstance(memory_context.get("long_term_items"), list) else []
    case_items = memory_context.get("case_items") if isinstance(memory_context.get("case_items"), list) else []
    status_ref = memory_context.get("status_ref") if isinstance(memory_context.get("status_ref"), Mapping) else {}
    fallback_reason = status_ref.get("fallback_reason")
    filter_reasons = status_ref.get("filter_reasons") if isinstance(status_ref.get("filter_reasons"), list) else []
    return {
        "source": _source(long_term_items=long_term_items, case_items=case_items, fallback_reason=fallback_reason),
        "fallback_reason": fallback_reason,
        "long_term_count": len(long_term_items),
        "case_count": len(case_items),
        "filter_reasons": filter_reasons,
    }


def _source(*, long_term_items: list[Any], case_items: list[Any], fallback_reason: Any) -> str:
    if long_term_items or case_items:
        return "reviewed_memory"
    if fallback_reason in {"service_error", "missing_memory_context_services"}:
        return "reviewed_memory_unavailable"
    if fallback_reason:
        return "reviewed_memory_skipped"
    return "no_reviewed_memory"


def _empty_bundle(
    *,
    fallback_reason: str,
    status: str,
    trusted_context: Any | None,
    current_slots: Mapping[str, Any] | None,
) -> ReviewedMemoryContextBundle:
    status_ref = ReviewedMemoryContextRetrieveStatusV1(
        status=status,
        trusted_scope_inputs=_trusted_scope_inputs(trusted_context=trusted_context, current_slots=current_slots),
        effective_scopes=[],
        filter_reasons=[fallback_reason],
        retrieved_refs=[],
        fallback_reason=fallback_reason,
    )
    return ReviewedMemoryContextBundle(long_term_items=[], case_items=[], status_ref=status_ref)


def _trusted_scope_inputs(*, trusted_context: Any | None, current_slots: Mapping[str, Any] | None) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    trusted = trusted_context if isinstance(trusted_context, Mapping) else {}
    for key in ("tenant_id", "user_id", "thread_id", "run_id", "trace_id", "role"):
        value = trusted.get(key)
        if value is not None:
            inputs[key] = value
    merchant_scope = trusted.get("merchant_scope")
    if isinstance(merchant_scope, Mapping):
        inputs["merchant_scope"] = list(merchant_scope.get("merchant_ids") or [])
    if current_slots:
        inputs["current_slots"] = dict(current_slots)
    return inputs


def _current_turn_slots(state: AgentState) -> dict[str, Any]:
    extracted = state.get("extracted_slots")
    if not isinstance(extracted, Mapping):
        return {}
    return {str(key): value for key, value in extracted.items() if value not in (None, "")}


def _trusted_business_context(state: AgentState, configurable: Mapping[str, Any]) -> dict[str, Any] | None:
    context = state.get("business_context")
    if isinstance(context, Mapping) and context:
        return dict(context)
    if _uses_legacy_actor_merchant_scope(state):
        merchant_id = _single_actor_merchant_id(configurable.get("trusted_context"))
        if merchant_id is not None:
            return {"merchant_id": merchant_id, "source": "trusted_context_actor_scope"}
    return None


def _uses_legacy_actor_merchant_scope(state: AgentState) -> bool:
    routing_hints = state.get("routing_hints")
    return isinstance(routing_hints, Mapping) and routing_hints.get("needs_long_term_memory") is True


def _single_actor_merchant_id(trusted_context: Any | None) -> str | None:
    trusted = trusted_context if isinstance(trusted_context, Mapping) else {}
    merchant_scope = trusted.get("merchant_scope")
    if not isinstance(merchant_scope, Mapping):
        return None
    merchant_ids = [str(value) for value in merchant_scope.get("merchant_ids") or [] if str(value) != "*"]
    return merchant_ids[0] if len(merchant_ids) == 1 else None


def _requested_scopes(state: AgentState, configurable: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    value = configurable.get("requested_memory_scopes")
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    state_value = state.get("requested_memory_scopes")
    if isinstance(state_value, list):
        return [dict(item) for item in state_value if isinstance(item, Mapping)]
    return None


def _case_type(state: AgentState) -> str | None:
    value = state.get("primary_intent") or state.get("current_intent")
    if not value:
        return None
    return str(value)[:64]


def _case_memory_query(state: AgentState) -> str | None:
    for key in ("user_query", "normalized_query"):
        value = state.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:500]
    return None
