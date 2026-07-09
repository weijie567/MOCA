from __future__ import annotations

import inspect
import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from src.agent.events import emit_event
from src.agent.nodes.investigate_planner import (
    INVESTIGATE_ALLOWED_TOOL_NAMES,
    INVESTIGATE_STOP_REASONS,
    InvestigatePlannerDecision,
    parse_investigate_planner_decision,
)
from src.agent.prompts import INSUFFICIENT_EVIDENCE_RESPONSE, INVESTIGATE_PLANNER_SYSTEM
from src.agent.state import AgentState, business_query_context_binding
from src.business.schemas import BusinessMetricQueryInput
from src.business.query.registry import BUSINESS_QUERY_REGISTRY
from src.business.query.schemas import BusinessQueryResultV1, BusinessQuerySpec, metric_input_to_business_query
from src.config import settings
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.platform.context_projections import project_missing_trusted_visibility_context, project_to_tool_context
from src.platform.trusted_context import TrustedContext
from src.tools.contracts import ToolCallContext, ToolResultProjectionV1, ToolResultPromptSummary, ToolResultV2, ToolViewV1
from src.tools.platform import ToolPlatform
from src.tools.validation import validate_json_value


DEFAULT_MAX_ITERATIONS = 3
GLOBAL_MAX_ITERATIONS_CEILING = 5
MIN_EVIDENCE_SCORE = 0.55
TERMINAL_STATUSES = {"success", "partial_success", "not_found", "permission_denied", "unavailable", "error"}
FACT_STATUSES = {"success", "partial_success"}
_ACTION_ORIENTED_INTENTS = {"refund_troubleshooting", "compensation_suggestion"}
_CASE_SLOT_RESOURCES = {
    "order_id": ("get_order", "order"),
    "refund_case_id": ("get_refund_case", "refund_case"),
    "ticket_id": ("get_ticket", "ticket"),
}
_METRIC_TOOL_NAME = "query_business_metric"
_BUSINESS_QUERY_TOOL_NAME = "business_query"


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.dashscope_api_key,
        openai_api_base=settings.embedding_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )


def plan_next_step(
    state: AgentState,
    accumulated_context: dict[str, Any],
    available_descriptors: list[Any],
) -> dict[str, Any]:
    scripted = state.get("_investigate_plan")
    if isinstance(scripted, list) and scripted:
        index = int(accumulated_context.get("script_index") or 0)
        if index < len(scripted) and isinstance(scripted[index], dict):
            accumulated_context["script_index"] = index + 1
            return scripted[index]
        return {"stop": True, "stop_reason": "no_more_useful_tools"}

    return _deterministic_fallback_plan_next_step(state, accumulated_context, available_descriptors)


def _deterministic_fallback_plan_next_step(
    state: AgentState,
    accumulated_context: dict[str, Any],
    available_descriptors: list[Any],
) -> dict[str, Any]:
    attempted = accumulated_context.get("attempted") or set()
    unusable = accumulated_context.get("unusable") or set()
    descriptor_names = {descriptor.name for descriptor in available_descriptors}
    business_query_step = _business_query_fallback_step(state, descriptor_names, attempted, unusable)
    if business_query_step is not None:
        return business_query_step
    metric_step = _metric_fallback_step(state, descriptor_names, attempted, unusable)
    if metric_step is not None:
        return metric_step
    if _is_metric_intent(state):
        return {"stop": True, "stop_reason": "no_more_useful_tools"}

    slots = _case_slots_for_loop(state, accumulated_context.get("discovered_slots"))
    candidates = [
        ("get_order", {"order_no": slots.get("order_id")}),
        ("get_refund_case", {"refund_case_no": slots.get("refund_case_id")}),
        ("get_ticket", {"ticket_id": slots.get("ticket_id")}),
        ("search_policy", {"query": state.get("user_query") or state.get("normalized_query") or ""}),
    ]
    for tool_name, args in candidates:
        key = _attempt_key(tool_name, args)
        if tool_name in descriptor_names and tool_name not in unusable and key not in attempted and all(args.values()):
            return {"next_tool": tool_name, "args": args, "reason": "deterministic investigation fallback"}
    return {"stop": True, "stop_reason": "no_more_useful_tools"}


def _metric_fallback_step(
    state: AgentState,
    descriptor_names: set[str],
    attempted: set[Any],
    unusable: set[Any],
) -> dict[str, Any] | None:
    args = _metric_args_from_active_slots(state)
    if args is None:
        return None
    key = _attempt_key(_METRIC_TOOL_NAME, args)
    if _METRIC_TOOL_NAME not in descriptor_names or _METRIC_TOOL_NAME in unusable or key in attempted:
        return None
    return {
        "next_tool": _METRIC_TOOL_NAME,
        "args": args,
        "reason": "deterministic business metric fallback",
    }


def _business_query_fallback_step(
    state: AgentState,
    descriptor_names: set[str],
    attempted: set[Any],
    unusable: set[Any],
) -> dict[str, Any] | None:
    args = _business_query_args_from_active_slots(state)
    if args is None:
        return None
    key = _attempt_key(_BUSINESS_QUERY_TOOL_NAME, args)
    if _BUSINESS_QUERY_TOOL_NAME not in descriptor_names or _BUSINESS_QUERY_TOOL_NAME in unusable or key in attempted:
        return None
    return {
        "next_tool": _BUSINESS_QUERY_TOOL_NAME,
        "args": args,
        "reason": "deterministic business query drilldown fallback",
    }


def _business_query_args_from_active_slots(state: AgentState) -> dict[str, Any] | None:
    if not _is_metric_intent(state):
        return None
    active_slots = state.get("active_slots") if isinstance(state.get("active_slots"), dict) else {}
    spec = active_slots.get("business_query_spec")
    if not isinstance(spec, dict):
        return None
    try:
        return BusinessQuerySpec.model_validate(spec).model_dump(mode="json", exclude_none=True)
    except ValidationError:
        return None


def _metric_args_from_active_slots(state: AgentState) -> dict[str, Any] | None:
    if not _is_metric_intent(state):
        return None
    active_slots = state.get("active_slots") if isinstance(state.get("active_slots"), dict) else {}
    metric_id = _safe_slot_value(active_slots.get("metric_id"))
    if not metric_id:
        return None

    time_preset = _safe_slot_value(active_slots.get("metric_time_preset"))
    start_at = _safe_slot_value(active_slots.get("metric_time_range_start"))
    end_at = _safe_slot_value(active_slots.get("metric_time_range_end"))
    has_time_range = bool(start_at and end_at)
    if metric_id not in BUSINESS_QUERY_REGISTRY.metric_ids():
        return None

    if time_preset and not BUSINESS_QUERY_REGISTRY.metric_accepts_time_preset(metric_id, time_preset):
        return None
    if not time_preset and not has_time_range:
        default_time_preset = BUSINESS_QUERY_REGISTRY.default_time_preset_for_metric(metric_id)
        if default_time_preset is None:
            return None
        time_preset = default_time_preset

    args: dict[str, Any] = {"metric_id": metric_id}
    if time_preset:
        args["time_preset"] = time_preset
    if has_time_range:
        args["start_at"] = start_at
        args["end_at"] = end_at
    merchant_id = _safe_slot_value(active_slots.get("merchant_id"))
    if merchant_id:
        args["merchant_id"] = merchant_id
    status_filter = _safe_status_filter(active_slots.get("status_filter"))
    if status_filter:
        args["status_filter"] = status_filter
    return args


def _is_metric_intent(state: AgentState) -> bool:
    return (state.get("primary_intent") or state.get("current_intent")) == "business_metric_query"


def _safe_status_filter(value: Any) -> list[str]:
    if isinstance(value, str):
        safe_value = _safe_slot_value(value)
        return [safe_value] if safe_value else []
    if not isinstance(value, list):
        return []
    safe_values = [_safe_slot_value(item) for item in value]
    return [item for item in safe_values if item]


async def investigate(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable.get("session")
    tool_platform = configurable.get("tool_platform")
    if tool_platform is None:
        if session is not None:
            tool_platform = ToolPlatform.with_defaults(session)
        else:
            tool_platform = ToolPlatform(executors={})

    max_iterations = _bounded_iterations(configurable.get("max_iterations", DEFAULT_MAX_ITERATIONS))
    max_attempts = int(configurable.get("max_attempts", 1))
    deadline_at = configurable.get("deadline_at")

    context: dict[str, Any] = {
        "base_slots": _case_slots(state),
        "discovered_slots": {},
        "attempted": set(),
        "attempt_count_by_key": {},
        "unusable": set(),
        "observations": [],
        "facts": {},
        "business_fact_refs": [],
        "policy_refs": [],
        "errors": [],
        "tool_results": [],
        "case_memory": list(state.get("case_memory") or []),
        "claim_dependency_map": [],
        "retrieval_status": state.get("retrieval_status"),
        "best_score": state.get("best_score"),
        "planner_errors": [],
        "planner_fallback_count": 0,
        "business_query_context_update": None,
    }
    termination_reason = "no_more_useful_tools"
    calls_executed = 0

    # Build visibility context and get ToolViewV1 entries for planner.
    trusted_context = _trusted_context_from_config(configurable)
    visibility_ctx = _build_visibility_context(trusted_context, configurable, state)
    visibility_caller = visibility_ctx.caller_node
    tool_views = await tool_platform.visible_tools(
        caller=visibility_caller, ctx=visibility_ctx, session=session,
    )
    if trusted_context is None:
        termination_reason = "unrecoverable_error"
        context["errors"].append(
            _safe_error("MISSING_TRUSTED_CONTEXT", "Trusted context is required for tool execution", "tool")
        )

    for iteration in range(1, max_iterations + 1):
        if trusted_context is None:
            break
        if _deadline_reached(deadline_at):
            termination_reason = "unrecoverable_error"
            break
        if max_attempts < 1:
            termination_reason = "unrecoverable_error"
            break

        step, validation_error = await _plan_next_step_with_fallback(
            state,
            context,
            tool_views,
            tool_platform,
            configurable,
            iteration,
        )
        if validation_error is not None:
            termination_reason = "unrecoverable_error"
            context["errors"].append(validation_error)
            break
        if step.get("stop") is True:
            termination_reason = _canonical_stop_reason(step.get("stop_reason"))
            break

        tool_name = step["next_tool"]
        args = step.get("args") or {}
        attempt_key = _attempt_key(tool_name, args)
        attempt_count_by_key = context["attempt_count_by_key"]
        attempt_count = int(attempt_count_by_key.get(attempt_key, 0))
        if attempt_count >= max_attempts:
            termination_reason = "no_more_useful_tools"
            break
        attempt_number = attempt_count + 1
        attempt_count_by_key[attempt_key] = attempt_number
        context["attempted"].add(attempt_key)
        if trusted_context is None:
            termination_reason = "unrecoverable_error"
            context["errors"].append(
                _safe_error("MISSING_TRUSTED_CONTEXT", "Trusted context is required for tool execution", "tool")
            )
            break

        descriptor = tool_platform.descriptor(tool_name)
        family = tool_platform.event_family(tool_name)
        operation_id = uuid4()
        tool_ctx = _build_tool_context(
            trusted_context,
            configurable,
            tool_name,
            operation_id,
            attempt_number,
            max_attempts,
            deadline_at,
            state.get("run_started_at") or _now_iso(),
        )
        await _emit_tool_event(configurable, session, tool_ctx, descriptor, family, operation_id, iteration, "started")
        tool_call_record = await _append_tool_call_record(
            configurable,
            session,
            tool_name,
            args,
            tool_ctx,
            operation_id,
        )
        try:
            outcome = await tool_platform.invoke(tool_name, args, tool_ctx, session=session)
        except Exception:
            termination_reason = "unrecoverable_error"
            context["errors"].append(
                _safe_error("TOOL_PLATFORM_ERROR", "Tool platform invocation failed", "tool_platform")
            )
            await _emit_tool_event(
                configurable,
                session,
                tool_ctx,
                descriptor,
                family,
                operation_id,
                iteration,
                "failed",
            )
            break
        result = outcome.tool_result
        calls_executed += 1
        terminal = (
            "completed" if result.status in {"success", "partial_success", "not_found", "unavailable"} else "failed"
        )
        await _emit_tool_event(
            configurable,
            session,
            tool_ctx,
            descriptor,
            family,
            operation_id,
            iteration,
            terminal,
            result=result,
        )
        prompt_summary = await _append_tool_result_record(
            configurable,
            session,
            tool_name,
            tool_ctx,
            operation_id,
            result,
            tool_call_record,
            projection=outcome.projection,
        )
        _accumulate_tool_result(context, descriptor, tool_name, result, prompt_summary, outcome.projection)
        _record_business_query_drilldown_context(state, context, tool_name, args, result)
        if result.status == "unavailable":
            context["unusable"].add(tool_name)
        if result.status not in TERMINAL_STATUSES:
            termination_reason = "unrecoverable_error"
            break
    else:
        termination_reason = "max_iterations_reached"

    if calls_executed == 0 and termination_reason == "no_more_useful_tools":
        context["retrieval_status"] = context["retrieval_status"] or "no_evidence"

    business_context = {
        "facts": context["facts"],
        "business_fact_refs": context["business_fact_refs"],
        "tool_results": context["tool_results"],
        "missing_required_facts": _missing_required_facts(state, context),
        "errors": context["errors"],
        "status": _business_status(context),
    }
    trace_steps = (state.get("trace_steps") or []) + [
        {
            "node": "investigate",
            "status": "completed",
            "started_at": started_at,
            "completed_at": _now_iso(),
            "tools_called": [item["tool_name"] for item in context["tool_results"]],
            "provider_latency_ms": None,
            "retry_count": 0,
            "metrics_json": {
                "termination_reason": termination_reason,
                "calls_executed": calls_executed,
                "planner_fallback_count": context["planner_fallback_count"],
            },
        }
    ]
    update = {
        "business_context": business_context,
        "policy_evidence": context["policy_refs"],
        "retrieved_evidence": {
            "status": context["retrieval_status"],
            "best_score": context["best_score"],
            "evidence_refs": context["policy_refs"],
            "policy_refs": context["policy_refs"],
        },
        "retrieval_status": context["retrieval_status"],
        "best_score": context["best_score"],
        "case_memory": context["case_memory"],
        "claim_dependency_map": context["claim_dependency_map"],
        "tool_results": context["tool_results"],
        "last_business_context_refs": {"business_fact_refs": context["business_fact_refs"], "loaded_at": _now_iso()},
        "recommendation_draft": _terminal_recommendation_draft(state, context),
        "termination_reason": termination_reason,
        "trace_steps": trace_steps,
    }
    if isinstance(context.get("business_query_context_update"), dict):
        update.update(context["business_query_context_update"])
    return update


async def _plan_next_step_with_fallback(
    state: AgentState,
    context: dict[str, Any],
    tool_views: list[ToolViewV1],
    tool_platform: Any,
    configurable: dict[str, Any],
    iteration: int,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    try:
        step = await _planner_next_step(state, context, tool_views, configurable, iteration)
        validation_error = _validate_planner_step(step, tool_views, tool_platform)
        if validation_error is None:
            return step, None
        _record_planner_fallback(context, validation_error)
    except Exception as exc:
        _record_planner_fallback(
            context,
            _safe_error("INVALID_PLANNER_OUTPUT", "Planner output failed validation", "planner")
            | {"detail": exc.__class__.__name__},
        )

    fallback_step = _deterministic_fallback_plan_next_step(state, context, tool_views)
    fallback_error = _validate_planner_step(fallback_step, tool_views, tool_platform)
    if fallback_error is not None:
        return {"stop": True, "stop_reason": "unrecoverable_error"}, fallback_error
    return fallback_step, None


async def _planner_next_step(
    state: AgentState,
    context: dict[str, Any],
    tool_views: list[ToolViewV1],
    configurable: dict[str, Any],
    iteration: int,
) -> dict[str, Any]:
    scripted = _scripted_planner_step(state, context)
    if scripted is not None:
        return parse_investigate_planner_decision(scripted)
    if _is_metric_intent(state):
        return _deterministic_fallback_plan_next_step(state, context, tool_views)

    planner_input = _planner_input_payload(state, context, tool_views, iteration)
    injected_planner = configurable.get("investigate_planner")
    if injected_planner is not None:
        raw = _invoke_injected_planner(injected_planner, planner_input)
        if inspect.isawaitable(raw):
            raw = await raw
        return parse_investigate_planner_decision(raw)

    messages = [
        {"role": "system", "content": INVESTIGATE_PLANNER_SYSTEM},
        {"role": "user", "content": _safe_jsonish(planner_input)},
    ]
    structured_llm = _get_llm().with_structured_output(InvestigatePlannerDecision)
    t0 = time.perf_counter()
    raw_decision = await structured_llm.ainvoke(messages)
    context["planner_provider_latency_ms"] = round((time.perf_counter() - t0) * 1000)
    return parse_investigate_planner_decision(raw_decision)


def _scripted_planner_step(state: AgentState, context: dict[str, Any]) -> dict[str, Any] | None:
    scripted = state.get("_investigate_plan")
    if not isinstance(scripted, list) or not scripted:
        return None
    index = int(context.get("script_index") or 0)
    if index < len(scripted) and isinstance(scripted[index], dict):
        context["script_index"] = index + 1
        return scripted[index]
    return {"stop": True, "stop_reason": "no_more_useful_tools"}


def _invoke_injected_planner(planner: Any, planner_input: dict[str, Any]) -> Any:
    if callable(planner):
        return planner(planner_input)
    if hasattr(planner, "ainvoke"):
        return planner.ainvoke(planner_input)
    return planner


def _planner_input_payload(
    state: AgentState,
    context: dict[str, Any],
    tool_views: list[ToolViewV1],
    iteration: int,
) -> dict[str, Any]:
    return {
        "user_query": _safe_case_text(state.get("user_query")),
        "normalized_query": _safe_case_text(state.get("normalized_query")),
        "primary_intent": state.get("primary_intent") or state.get("current_intent"),
        "requested_operation": state.get("requested_operation"),
        "current_resolved_slots": _case_slots_for_loop(state, context.get("discovered_slots")),
        "loop_local_discovered_slots": dict(context.get("discovered_slots") or {}),
        "projected_observations": _projected_observation_summaries(context),
        "allowed_tools": [_tool_view_payload(view) for view in tool_views],
        "iteration": iteration,
        "previous_attempted_keys": _attempted_key_payload(context.get("attempted") or set()),
    }


def _tool_view_payload(view: ToolViewV1) -> dict[str, Any]:
    return {
        "name": view.name,
        "description": view.description,
        "input_schema": view.input_schema,
        "safe_usage_notes": view.safe_usage_notes,
        "result_contract_version": view.result_contract_version,
    }


def _projected_observation_summaries(context: dict[str, Any]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for item in context.get("observations") or context.get("tool_results") or []:
        if not isinstance(item, dict):
            continue
        observations.append(
            {
                "tool_name": item.get("tool_name"),
                "status": item.get("status"),
                "prompt_summary": item.get("prompt_summary"),
                "business_fact_refs": item.get("business_fact_refs") or [],
                "policy_evidence_refs": item.get("policy_evidence_refs") or [],
            }
        )
    return observations


def _attempted_key_payload(attempted: set[Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for key in attempted:
        if not isinstance(key, tuple) or len(key) != 2:
            continue
        args = key[1]
        payload.append(
            {
                "tool_name": key[0],
                "args": dict(args) if isinstance(args, tuple) else {},
            }
        )
    return sorted(payload, key=lambda item: (str(item["tool_name"]), str(item["args"])))


def _record_planner_fallback(context: dict[str, Any], error: dict[str, Any]) -> None:
    context["planner_fallback_count"] = int(context.get("planner_fallback_count") or 0) + 1
    context.setdefault("planner_errors", []).append(error)


def _validate_planner_step(step: Any, tool_views: list[ToolViewV1], tool_platform: Any | None = None) -> dict[str, Any] | None:
    views_by_name = {view.name: view for view in tool_views}
    if not isinstance(step, dict):
        return _safe_error("INVALID_PLANNER_OUTPUT", "Planner output failed validation", "planner")
    has_stop = step.get("stop") is True
    has_tool = "next_tool" in step
    if has_stop == has_tool:
        return _safe_error("INVALID_PLANNER_OUTPUT", "Planner output must choose one action", "planner")
    if has_stop:
        if set(step) != {"stop", "stop_reason"} or step.get("stop_reason") not in INVESTIGATE_STOP_REASONS:
            return _safe_error("INVALID_PLANNER_OUTPUT", "Planner stop reason failed validation", "planner")
        return None
    tool_name = step.get("next_tool")
    if set(step) != {"next_tool", "args", "reason"}:
        return _safe_error("INVALID_PLANNER_OUTPUT", "Planner tool output failed validation", "planner")
    if not isinstance(tool_name, str):
        return _safe_error("INVALID_PLANNER_TOOL", "Planner selected an invalid tool", "planner")
    if tool_name not in INVESTIGATE_ALLOWED_TOOL_NAMES:
        return _safe_error("INVALID_PLANNER_TOOL", "Planner selected a tool outside investigate allowlist", "planner")
    if tool_name not in views_by_name:
        return _safe_error("INVALID_PLANNER_TOOL", "Planner selected an unavailable tool", "planner")
    if not isinstance(step.get("args"), dict):
        return _safe_error("INVALID_PLANNER_ARGS", "Planner tool arguments failed validation", "planner")
    if not isinstance(step.get("reason"), str) or not step["reason"].strip():
        return _safe_error("INVALID_PLANNER_OUTPUT", "Planner tool reason failed validation", "planner")
    descriptor = tool_platform.descriptor(tool_name) if tool_platform is not None and hasattr(tool_platform, "descriptor") else None
    descriptor_error = _validate_investigate_tool_descriptor(descriptor)
    if descriptor_error is not None:
        return descriptor_error
    schema = descriptor.input_schema if descriptor is not None else views_by_name[tool_name].input_schema
    try:
        _validate_tool_args(step["args"], schema)
    except (TypeError, ValueError):
        return _safe_error("INVALID_PLANNER_ARGS", "Planner tool arguments failed validation", "planner")
    return None


def _validate_investigate_tool_descriptor(descriptor: Any) -> dict[str, Any] | None:
    if descriptor is None:
        return None
    if getattr(descriptor, "kind", None) == "write" or getattr(descriptor, "side_effect", None) == "write":
        return _safe_error("INVALID_PLANNER_TOOL", "Planner selected a write tool", "planner")
    if getattr(descriptor, "kind", None) not in {"read", "retrieval"}:
        return _safe_error("INVALID_PLANNER_TOOL", "Planner selected a non-read tool", "planner")
    if getattr(descriptor, "side_effect", None) not in {"read_only", "retrieval"}:
        return _safe_error("INVALID_PLANNER_TOOL", "Planner selected a side-effecting tool", "planner")
    if "investigate" not in (getattr(descriptor, "caller_allowlist", None) or []):
        return _safe_error("INVALID_PLANNER_TOOL", "Planner selected a tool outside investigate caller scope", "planner")
    if getattr(descriptor, "exposure", None) != "planner_visible":
        return _safe_error("INVALID_PLANNER_TOOL", "Planner selected a non-visible tool", "planner")
    return None


def _validate_tool_args(args: dict[str, Any], schema: dict[str, Any]) -> None:
    validate_json_value(args, schema)
    properties = schema.get("properties")
    if isinstance(properties, dict):
        unexpected = set(args) - set(properties)
        if unexpected:
            raise ValueError("Unexpected planner tool argument")


def _build_tool_context(
    trusted_context: TrustedContext,
    configurable: dict[str, Any],
    tool_name: str,
    operation_id: Any,
    attempt: int,
    max_attempts: int,
    deadline_at: Any,
    effective_at: str,
) -> ToolCallContext:
    return project_to_tool_context(
        trusted_context,
        request_id=configurable.get("request_id") or str(uuid4()),
        tool_call_id=str(operation_id),
        caller_node="investigate",
        deadline_at=deadline_at,
        effective_at=effective_at,
        attempt=attempt,
        max_attempts=max_attempts,
        idempotency_key=f"{trusted_context.run_id}:{tool_name}:{operation_id}",
        policy_snapshot_ref=None,
    )


def _build_visibility_context(
    trusted_context: TrustedContext | None,
    configurable: dict[str, Any],
    state: AgentState,
) -> ToolCallContext:
    """Build a ToolCallContext for visibility checks (no operation_id needed)."""
    if trusted_context is not None:
        return project_to_tool_context(
            trusted_context,
            request_id=configurable.get("request_id") or str(uuid4()),
            tool_call_id=f"visibility:{state.get('run_id', 'unknown')}",
            caller_node="investigate",
        )
    return project_missing_trusted_visibility_context(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        run_id=str(state.get("run_id") or uuid4()),
        request_id=str(uuid4()),
        tool_call_id=f"visibility:{state.get('run_id', 'unknown')}",
    )


def _trusted_context_from_config(configurable: dict[str, Any]) -> TrustedContext | None:
    raw_context = configurable.get("trusted_context")
    if raw_context is None:
        return None
    try:
        return TrustedContext.model_validate(raw_context)
    except ValidationError:
        return None


async def _append_tool_call_record(
    configurable: dict[str, Any],
    session: Any,
    tool_name: str,
    args: dict[str, Any],
    tool_ctx: ToolCallContext,
    operation_id: Any,
) -> Any | None:
    if not _can_persist_conversation_tool_records(configurable, session):
        return None
    service = _conversation_service(configurable, session)
    return await service.append_tool_call(
        tenant_id=tool_ctx.tenant_id,
        user_id=tool_ctx.user_id,
        thread_id=tool_ctx.thread_id,
        run_id=tool_ctx.run_id,
        trace_id=tool_ctx.trace_id,
        tool_call_id=tool_ctx.tool_call_id,
        tool_name=tool_name,
        caller_node=tool_ctx.caller_node,
        operation_id=operation_id,
        attempt=tool_ctx.attempt,
        arguments=args,
        argument_summary_json=_argument_summary(tool_name, args),
        redaction_policy_version="conversation_redaction.v1",
        conversation_message_id=configurable.get("conversation_message_id"),
    )


async def _append_tool_result_record(
    configurable: dict[str, Any],
    session: Any,
    tool_name: str,
    tool_ctx: ToolCallContext,
    operation_id: Any,
    result: ToolResultV2,
    tool_call_record: Any | None,
    projection: ToolResultProjectionV1 | None = None,
) -> ToolResultPromptSummary:
    tool_result_id = str(uuid4())
    if not _can_persist_conversation_tool_records(configurable, session):
        return _project_tool_result(
            tool_call_id=tool_ctx.tool_call_id,
            tool_result_id=tool_result_id,
            tool_name=tool_name,
            result=result,
            raw_result_ref=None,
            projection=projection,
        )
    service = _conversation_service(configurable, session)
    return await service.append_tool_result(
        tenant_id=tool_ctx.tenant_id,
        user_id=tool_ctx.user_id,
        thread_id=tool_ctx.thread_id,
        run_id=tool_ctx.run_id,
        trace_id=tool_ctx.trace_id,
        operation_id=operation_id,
        tool_call_id=tool_ctx.tool_call_id,
        tool_call_record_id=getattr(tool_call_record, "id", None),
        tool_result_id=tool_result_id,
        tool_name=tool_name,
        result=result,
        raw_result_ref=None,
        raw_result_hash=None,
        conversation_message_id=configurable.get("conversation_message_id"),
        projection=projection,
    )


def _can_persist_conversation_tool_records(configurable: dict[str, Any], session: Any) -> bool:
    return (
        session is not None
        and hasattr(session, "execute")
        and hasattr(session, "flush")
        and configurable.get("conversation_message_id") is not None
    )


def _conversation_service(configurable: dict[str, Any], session: Any) -> ConversationService:
    service = configurable.get("conversation_service")
    if isinstance(service, ConversationService):
        return service
    return ConversationService(ConversationRepository(session))


def _argument_summary(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "tool_argument_summary.v1",
        "tool_name": tool_name,
        "argument_keys": sorted(str(key) for key in args),
        "argument_count": len(args),
    }


def _project_tool_result(
    *,
    tool_call_id: str,
    tool_result_id: str,
    tool_name: str,
    result: ToolResultV2,
    raw_result_ref: str | None,
    projection: ToolResultProjectionV1 | None = None,
) -> ToolResultPromptSummary:
    # Use projection data when available; fall back to building from result.
    if projection is not None:
        prompt_text = projection.text_for_prompt or ""
        prompt_proj = projection.prompt_projection
        business_fact_refs = prompt_proj.get("business_fact_refs", [])
        policy_evidence_refs = prompt_proj.get("policy_candidate_refs", [])
        return ToolResultPromptSummary(
            tool_call_id=tool_call_id,
            tool_result_id=tool_result_id,
            tool_name=tool_name,
            status=result.status,
            summary=result.summary,
            prompt_summary=prompt_text or _safe_prompt_summary(
                tool_name=tool_name,
                status=result.status,
                summary=result.summary,
                source_system=result.source_system,
                business_fact_refs=business_fact_refs,
                policy_evidence_refs=policy_evidence_refs,
            ),
            business_fact_refs=business_fact_refs,
            policy_evidence_refs=policy_evidence_refs,
            raw_result_ref=raw_result_ref,
            audit_ref=result.audit_ref,
        )

    business_fact_refs = [ref.model_dump(mode="json") for ref in result.business_fact_refs]
    policy_evidence_refs = [ref.model_dump(mode="json") for ref in result.policy_evidence_refs]
    prompt_summary = _safe_prompt_summary(
        tool_name=tool_name,
        status=result.status,
        summary=result.summary,
        source_system=result.source_system,
        business_fact_refs=business_fact_refs,
        policy_evidence_refs=policy_evidence_refs,
    )
    return ToolResultPromptSummary(
        tool_call_id=tool_call_id,
        tool_result_id=tool_result_id,
        tool_name=tool_name,
        status=result.status,
        summary=result.summary,
        prompt_summary=prompt_summary,
        business_fact_refs=business_fact_refs,
        policy_evidence_refs=policy_evidence_refs,
        raw_result_ref=raw_result_ref,
        audit_ref=result.audit_ref,
    )


def _safe_prompt_summary(
    *,
    tool_name: str,
    status: str,
    summary: str,
    source_system: str,
    business_fact_refs: list[dict[str, Any]],
    policy_evidence_refs: list[dict[str, Any]],
) -> str:
    business_refs = [
        f"{ref.get('resource_type')}:{ref.get('resource_id')}"
        for ref in business_fact_refs
        if ref.get("resource_type") and ref.get("resource_id")
    ]
    evidence_refs = [str(ref.get("evidence_id")) for ref in policy_evidence_refs if ref.get("evidence_id")]
    parts = [f"{tool_name} {status} from {source_system}", " ".join(summary.split())[:240]]
    if business_refs:
        parts.append(f"business refs: {', '.join(business_refs[:5])}")
    if evidence_refs:
        parts.append(f"policy refs: {', '.join(evidence_refs[:5])}")
    return " | ".join(parts)


async def _emit_tool_event(
    configurable: dict[str, Any],
    session: Any,
    tool_ctx: ToolCallContext,
    descriptor: Any,
    family: str,
    operation_id: Any,
    iteration: int,
    status: str,
    *,
    result: ToolResultV2 | None = None,
) -> None:
    event_emitter = configurable.get("event_emitter")
    event_type = f"{family}_{status}"
    redacted_payload = {
        "tool_name": descriptor.name if descriptor is not None else "unknown",
        "status": result.status if result is not None else status,
        "latency_ms": result.latency_ms if result is not None else None,
        "tool_call_id": tool_ctx.tool_call_id,
        "attempt": tool_ctx.attempt,
    }
    if result is not None and result.status in {"error", "invalid_request", "invalid_response"}:
        redacted_payload["termination_reason"] = "unrecoverable_error"
    if event_emitter is not None:
        await event_emitter(
            event_type=event_type,
            operation_id=operation_id,
            parent_operation_id=_parent_operation_id(configurable),
            tool_call_id=tool_ctx.tool_call_id,
            attempt=tool_ctx.attempt,
            iteration=iteration,
            payload=redacted_payload,
        )
        return
    if session is None:
        return
    await emit_event(
        session,
        run_id=tool_ctx.run_id,
        tenant_id=tool_ctx.tenant_id,
        thread_id=tool_ctx.thread_id,
        event_type=event_type,
        actor={"type": "agent", "id": "moca"},
        resource_refs={"tool": descriptor.name if descriptor is not None else "unknown"},
        redacted_payload=redacted_payload,
        trace_id=tool_ctx.trace_id,
        operation_id=operation_id,
        parent_operation_id=_parent_operation_id(configurable),
        tool_call_id=tool_ctx.tool_call_id,
        attempt=tool_ctx.attempt,
        iteration=iteration,
    )


def _parent_operation_id(configurable: dict[str, Any]) -> Any | None:
    return configurable.get("node_operation_id") or configurable.get("investigate_operation_id")


def _accumulate_tool_result(
    context: dict[str, Any],
    descriptor: Any,
    tool_name: str,
    result: ToolResultV2,
    prompt_summary: ToolResultPromptSummary,
    full_projection: ToolResultProjectionV1,
) -> None:
    prompt_summary_payload = prompt_summary.model_dump(mode="json")
    context["tool_results"].append(prompt_summary_payload)
    context.setdefault("observations", []).append(prompt_summary_payload)
    normalized = full_projection.normalized_result
    if result.status in FACT_STATUSES:
        _discover_loop_slots_from_projection(context, tool_name, full_projection)
        if tool_name == "search_case_memory":
            context.setdefault("case_memory", []).extend(
                _case_memory_items_from_projection(normalized)
            )
        if result.business_fact_refs:
            for ref in result.business_fact_refs:
                ref_data = ref.model_dump(mode="json")
                context["business_fact_refs"].append(ref_data)
                context["facts"][ref.resource_type] = _business_fact_payload_for_context(
                    ref.resource_type,
                    result,
                    normalized,
                )
                context["claim_dependency_map"].append(
                    {
                        "claim_id": f"business:{ref.resource_type}:{ref.resource_id}",
                        "depends_on_refs": [{"resource_type": ref.resource_type, "resource_id": ref.resource_id}],
                    }
                )
        if result.policy_evidence_refs:
            context["policy_refs"].extend([ref.model_dump(mode="json") for ref in result.policy_evidence_refs])
            for ref in result.policy_evidence_refs:
                context["claim_dependency_map"].append(
                    {
                        "claim_id": f"policy:{ref.evidence_id}",
                        "depends_on_refs": [{"resource_type": "policy", "resource_id": ref.evidence_id}],
                    }
                )
    # Use normalized_result for retrieval status, not raw result.data.
    retrieval_status = normalized.get("retrieval_status")
    best_score = normalized.get("best_score")
    if retrieval_status in {"strong_evidence", "partial_evidence", "no_evidence", "error"}:
        context["retrieval_status"] = retrieval_status
    if isinstance(best_score, (int, float)):
        context["best_score"] = float(best_score)
    if result.status not in FACT_STATUSES:
        resource_type = descriptor.resource_type if descriptor is not None and descriptor.resource_type else tool_name
        error = (
            result.error.model_dump(mode="json")
            if result.error is not None
            else _safe_error(result.status.upper(), result.summary, resource_type)
        )
        error["resource"] = resource_type
        context["errors"].append(error)


def _business_fact_payload_for_context(
    resource_type: str,
    result: ToolResultV2,
    normalized: dict[str, Any],
) -> dict[str, Any]:
    if resource_type != "business_query" or not isinstance(result.data, dict):
        return normalized
    payload = result.data.get("business_query")
    return payload if isinstance(payload, dict) else normalized


def _record_business_query_drilldown_context(
    state: AgentState,
    context: dict[str, Any],
    tool_name: str,
    args: dict[str, Any],
    result: ToolResultV2,
) -> None:
    if tool_name == _METRIC_TOOL_NAME:
        if result.status not in FACT_STATUSES:
            context["business_query_context_update"] = _clear_business_query_drilldown_context()
            return
        update = _metric_business_query_drilldown_context_update(state, args, result)
        if update is not None:
            context["business_query_context_update"] = update
        return
    if tool_name != _BUSINESS_QUERY_TOOL_NAME:
        return
    if result.status not in FACT_STATUSES:
        context["business_query_context_update"] = _clear_business_query_drilldown_context()
        return
    update = _business_query_drilldown_context_update(state, result)
    context["business_query_context_update"] = update or _clear_business_query_drilldown_context()


def _business_query_drilldown_context_update(state: AgentState, result: ToolResultV2) -> dict[str, Any] | None:
    business_query = _safe_business_query_result(result)
    if business_query is None or business_query.answer_context is None:
        return None

    answer_context = business_query.answer_context.model_dump(mode="json")
    cursor = None
    if business_query.cursor is not None:
        cursor = business_query.cursor.model_dump(mode="json")
    elif business_query.answer_context.cursor is not None:
        cursor = business_query.answer_context.cursor.model_dump(mode="json")
    expected_slot_type = _expected_slot_type_for_business_query_context(answer_context, cursor)
    return {
        "last_query_spec": business_query.answer_context.query_spec.model_dump(mode="json"),
        "last_answer_context": answer_context,
        "result_cursor": cursor,
        "expected_slot_type": expected_slot_type,
        "expected_slot_context": {
            "schema_version": "business_query_expected_slot_context.v1",
            "purpose": "business_query_drilldown",
            "context_binding": business_query_context_binding(state),
            "operation": business_query.operation,
            "resource": business_query.resource,
            "allowed_drilldowns": list(business_query.answer_context.allowed_drilldowns),
            "fields_shown": list(business_query.answer_context.fields_shown),
        },
    }


def _metric_business_query_drilldown_context_update(
    state: AgentState,
    args: dict[str, Any],
    result: ToolResultV2,
) -> dict[str, Any] | None:
    try:
        metric_args = dict(args)
        if metric_args.get("time_preset"):
            metric_args.pop("start_at", None)
            metric_args.pop("end_at", None)
        metric_input = BusinessMetricQueryInput.model_validate(metric_args)
        query_spec = metric_input_to_business_query(metric_input)
    except ValidationError:
        return None
    answer_context = _metric_business_query_answer_context(query_spec, result)
    expected_slot_type = _expected_slot_type_for_business_query_context(answer_context, None)
    return {
        "last_query_spec": query_spec.model_dump(mode="json"),
        "last_answer_context": answer_context,
        "result_cursor": None,
        "expected_slot_type": expected_slot_type,
        "expected_slot_context": {
            "schema_version": "business_query_expected_slot_context.v1",
            "purpose": "business_query_drilldown",
            "context_binding": business_query_context_binding(state),
            "operation": query_spec.operation,
            "resource": query_spec.resource,
            "allowed_drilldowns": list(answer_context["allowed_drilldowns"]),
            "fields_shown": list(answer_context["fields_shown"]),
        },
    }


def _metric_business_query_answer_context(
    query_spec: BusinessQuerySpec,
    result: ToolResultV2,
) -> dict[str, Any]:
    metric_id = query_spec.metric_id or ""
    data = result.data if isinstance(result.data, dict) else {}
    allowed_drilldowns = ["list"] if query_spec.operation == "aggregate" and query_spec.resource == "order" else []
    return {
        "schema_version": "business_query_answer_context.v1",
        "query_spec": query_spec.model_dump(mode="json"),
        "result_refs": [metric_id] if metric_id else [],
        "allowed_drilldowns": allowed_drilldowns,
        "fields_shown": [metric_id] if metric_id else [],
        "cursor": None,
        "scope": _metric_business_query_scope(data),
        "time_summary": _metric_business_query_time_summary(query_spec, data),
        "filter_summary": _metric_business_query_filter_summary(query_spec),
    }


def _metric_business_query_scope(data: dict[str, Any]) -> dict[str, Any] | None:
    scope = data.get("scope")
    if not isinstance(scope, dict):
        return None
    scope_label = scope.get("scope_label")
    if not isinstance(scope_label, str) or not scope_label.strip():
        return None
    return {"scope_label": scope_label.strip()}


def _metric_business_query_time_summary(query_spec: BusinessQuerySpec, data: dict[str, Any]) -> str | None:
    if query_spec.time_preset:
        return query_spec.time_preset
    time_range = data.get("time_range")
    if isinstance(time_range, dict):
        preset = time_range.get("preset")
        if isinstance(preset, str) and preset:
            return preset
    return None


def _metric_business_query_filter_summary(query_spec: BusinessQuerySpec) -> str | None:
    status_filter = query_spec.filters.status_filter
    return ",".join(status_filter) if status_filter else None


def _safe_business_query_result(result: ToolResultV2) -> BusinessQueryResultV1 | None:
    if not isinstance(result.data, dict):
        return None
    payload = result.data.get("business_query")
    if not isinstance(payload, dict):
        return None
    # Validate only the stable BusinessQueryResultV1 contract fields. Raw executor/debug
    # keys may exist in malformed tool data but must not enter drilldown state.
    stable_payload = {
        key: value
        for key, value in payload.items()
        if key in BusinessQueryResultV1.model_fields
    }
    try:
        return BusinessQueryResultV1.model_validate(stable_payload)
    except ValidationError:
        return None


def _expected_slot_type_for_business_query_context(
    answer_context: dict[str, Any],
    cursor: dict[str, Any] | None,
) -> str | None:
    allowed_drilldowns = answer_context.get("allowed_drilldowns")
    if isinstance(allowed_drilldowns, list) and allowed_drilldowns:
        return "field_request"
    if isinstance(cursor, dict) and cursor.get("has_more") is True:
        return "cursor_request"
    return None


def _clear_business_query_drilldown_context() -> dict[str, Any]:
    return {
        "last_query_spec": None,
        "last_answer_context": None,
        "result_cursor": None,
        "expected_slot_type": None,
        "expected_slot_context": None,
    }


def _business_status(context: dict[str, Any]) -> str:
    if context["facts"] and not context["errors"]:
        return "complete"
    if context["facts"]:
        return "partial"
    if context["errors"]:
        return "error"
    return "insufficient"


def _missing_required_facts(state: AgentState, context: dict[str, Any]) -> list[str]:
    facts = context["facts"]
    slots = _case_slots_for_loop(state, context.get("discovered_slots"))
    failed_tools = {
        result.get("tool_name")
        for result in context["tool_results"]
        if isinstance(result, dict) and result.get("status") != "success"
    }
    missing = [
        resource_name
        for slot_name, (tool_name, resource_name) in _CASE_SLOT_RESOURCES.items()
        if slots.get(slot_name) and tool_name in failed_tools and resource_name not in facts
    ]
    intent = state.get("primary_intent") or state.get("current_intent")
    if intent in _ACTION_ORIENTED_INTENTS and not facts and not any(slots.values()):
        missing.append("case_identifier")
    return list(dict.fromkeys(missing))


def _terminal_recommendation_draft(state: AgentState, context: dict[str, Any]) -> dict[str, Any] | None:
    if _is_metric_intent(state):
        return None
    retrieval_status = context["retrieval_status"]
    best_score = context["best_score"]
    if retrieval_status == "error":
        return _retrieval_error_draft(context["errors"])
    if retrieval_status in {"no_evidence", None}:
        return _insufficient_evidence_draft()
    if isinstance(best_score, (int, float)) and best_score < MIN_EVIDENCE_SCORE:
        return _insufficient_evidence_draft(["Policy evidence score below threshold"])
    return None


def _insufficient_evidence_draft(missing_info: list[str] | None = None) -> dict[str, Any]:
    return {
        "recommended_action": "insufficient_evidence",
        "reasoning_summary": INSUFFICIENT_EVIDENCE_RESPONSE,
        "evidence_refs": [],
        "confidence": 0.0,
        "risk_level": "low",
        "missing_info": missing_info or ["No relevant policy found"],
    }


def _retrieval_error_draft(errors: list[dict[str, Any]]) -> dict[str, Any]:
    message = "Policy retrieval failed"
    for error in errors:
        if not isinstance(error, dict):
            continue
        safe_message = error.get("safe_message") or error.get("message")
        if isinstance(safe_message, str) and safe_message:
            message = safe_message
            break
    return {
        "recommended_action": "retrieval_error",
        "reasoning_summary": "Policy retrieval failed due to an infrastructure error.",
        "evidence_refs": [],
        "confidence": 0.0,
        "risk_level": "low",
        "missing_info": [message],
    }


def _case_slots(state: AgentState) -> dict[str, Any]:
    extracted = state.get("extracted_slots") if isinstance(state.get("extracted_slots"), dict) else {}
    active = state.get("active_slots") if isinstance(state.get("active_slots"), dict) else {}
    return {slot_name: extracted.get(slot_name) or active.get(slot_name) for slot_name in _CASE_SLOT_RESOURCES}


def _case_slots_for_loop(state: AgentState, discovered_slots: Any | None = None) -> dict[str, Any]:
    base_slots = _case_slots(state)
    discovered = discovered_slots if isinstance(discovered_slots, dict) else {}
    merged = dict(base_slots)
    aliases = {
        "order_id": ("order_id", "order_no"),
        "refund_case_id": ("refund_case_id", "refund_case_no"),
        "ticket_id": ("ticket_id",),
    }
    for target_key, source_keys in aliases.items():
        if merged.get(target_key):
            continue
        for source_key in source_keys:
            value = _safe_slot_value(discovered.get(source_key))
            if value:
                merged[target_key] = value
                break
    return merged


def _discover_loop_slots_from_projection(
    context: dict[str, Any],
    tool_name: str,
    projection: ToolResultProjectionV1,
) -> None:
    discovered = context.setdefault("discovered_slots", {})
    normalized = projection.normalized_result if isinstance(projection.normalized_result, dict) else {}
    prompt_projection = projection.prompt_projection if isinstance(projection.prompt_projection, dict) else {}

    if tool_name == "get_order":
        _merge_discovered_slot(discovered, "order_no", normalized.get("order_no"))
        _merge_discovered_slot(discovered, "order_id", normalized.get("order_no") or normalized.get("id"))
        _merge_discovered_slot(discovered, "merchant_id", normalized.get("merchant_id"))
    elif tool_name == "get_refund_case":
        _merge_discovered_slot(discovered, "refund_case_no", normalized.get("refund_case_no"))
        _merge_discovered_slot(discovered, "refund_case_id", normalized.get("refund_case_no") or normalized.get("id"))
        _merge_discovered_slot(discovered, "merchant_id", normalized.get("merchant_id"))
    elif tool_name == "get_ticket":
        _merge_discovered_slot(
            discovered,
            "ticket_id",
            normalized.get("ticket_id") or normalized.get("ticket_no") or normalized.get("id"),
        )
        _merge_discovered_slot(discovered, "merchant_id", normalized.get("merchant_id"))
    elif tool_name == "get_logistics":
        _merge_discovered_slot(discovered, "tracking_no", normalized.get("tracking_no") or normalized.get("id"))
    elif tool_name == "get_merchant_risk":
        _merge_discovered_slot(discovered, "merchant_id", normalized.get("merchant_id") or normalized.get("id"))

    for ref in _structured_ref_list(prompt_projection.get("business_fact_refs")):
        resource_type = ref.get("resource_type")
        resource_id = ref.get("resource_id")
        if resource_type == "order":
            _merge_discovered_slot(discovered, "order_id", resource_id)
        elif resource_type == "refund_case":
            _merge_discovered_slot(discovered, "refund_case_id", resource_id)
        elif resource_type == "ticket":
            _merge_discovered_slot(discovered, "ticket_id", resource_id)
        elif resource_type == "logistics":
            _merge_discovered_slot(discovered, "tracking_no", resource_id)
        elif resource_type == "merchant_risk":
            _merge_discovered_slot(discovered, "merchant_risk_ref", resource_id)

    relation_hints = prompt_projection.get("relation_hints")
    if not isinstance(relation_hints, dict):
        relation_hints = normalized.get("relation_hints")
    if isinstance(relation_hints, dict):
        _merge_discovered_slot(discovered, "refund_case_id", relation_hints.get("latest_refund_case_id"))
        _merge_discovered_slot(discovered, "ticket_id", relation_hints.get("latest_ticket_id"))
        _merge_discovered_slot(discovered, "tracking_no", relation_hints.get("tracking_no"))
        _merge_discovered_slot(discovered, "merchant_id", relation_hints.get("merchant_id"))


def _structured_ref_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _merge_discovered_slot(discovered: dict[str, Any], key: str, value: Any) -> None:
    safe_value = _safe_slot_value(value)
    if safe_value and key not in discovered:
        discovered[key] = safe_value


def _safe_slot_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized[:128] if normalized else None


def _bounded_iterations(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_MAX_ITERATIONS
    return max(1, min(parsed, GLOBAL_MAX_ITERATIONS_CEILING))


def _canonical_stop_reason(value: Any) -> str:
    if value in {"enough_evidence", "no_more_useful_tools", "max_iterations_reached", "unrecoverable_error"}:
        return str(value)
    return "unrecoverable_error"


def _deadline_reached(deadline_at: Any) -> bool:
    return isinstance(deadline_at, datetime) and datetime.now(UTC) >= deadline_at


def _attempt_key(tool_name: str, args: dict[str, Any]) -> tuple[str, tuple[tuple[str, str], ...]]:
    return (tool_name, tuple(sorted((str(key), str(value)) for key, value in args.items())))


def _safe_error(code: str, safe_message: str, source: str) -> dict[str, Any]:
    return {"code": code, "safe_message": safe_message, "retryable": False, "source": source}


def _safe_case_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized[:1500] or None


def _safe_jsonish(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _case_memory_items_from_projection(normalized: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract case-memory items from projector-normalized result.

    Reads from normalized_result (safe projected surface) rather than raw
    result.data to prevent raw payloads from entering graph state.
    """
    items = normalized.get("_case_memory_items")
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entry: dict[str, Any] = {}
        for key in (
            "case_id", "case_memory_id", "memory_id", "id",
            "similarity", "score",
            "snippet", "excerpt",
            "outcome", "applicability", "caveats",
        ):
            if key in item and isinstance(item[key], (str, int, float, bool)):
                entry[key] = item[key]
        for key in ("policy_refs", "source_refs"):
            refs = item.get(key)
            if isinstance(refs, list):
                entry[key] = refs
        if entry:
            result.append(entry)
    return result


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
