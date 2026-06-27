from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from src.agent.events import emit_event
from src.agent.prompts import INSUFFICIENT_EVIDENCE_RESPONSE
from src.agent.state import AgentState
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.platform.context_projections import project_missing_trusted_visibility_context, project_to_tool_context
from src.platform.trusted_context import TrustedContext
from src.tools.contracts import ToolCallContext, ToolResultProjectionV1, ToolResultPromptSummary, ToolResultV2, ToolViewV1
from src.tools.platform import ToolPlatform


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

    attempted = accumulated_context.get("attempted") or set()
    unusable = accumulated_context.get("unusable") or set()
    slots = _case_slots(state)
    candidates = [
        ("get_order", {"order_no": slots.get("order_id")}),
        ("get_refund_case", {"refund_case_no": slots.get("refund_case_id")}),
        ("get_ticket", {"ticket_id": slots.get("ticket_id")}),
        ("search_policy", {"query": state.get("user_query") or state.get("normalized_query") or ""}),
    ]
    descriptor_names = {descriptor.name for descriptor in available_descriptors}
    for tool_name, args in candidates:
        key = _attempt_key(tool_name, args)
        if tool_name in descriptor_names and tool_name not in unusable and key not in attempted and all(args.values()):
            return {"next_tool": tool_name, "args": args, "reason": "deterministic investigation fallback"}
    return {"stop": True, "stop_reason": "no_more_useful_tools"}


async def investigate(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    configurable = config.get("configurable") or {}
    session = configurable.get("session")
    tool_platform = configurable.get("tool_platform")
    if tool_platform is None:
        tool_manager = configurable.get("tool_manager")
        if tool_manager is not None and hasattr(tool_manager, "_platform"):
            tool_platform = tool_manager._platform
        elif session is not None:
            tool_platform = ToolPlatform.with_defaults(session)
        else:
            tool_platform = ToolPlatform(executors={})

    max_iterations = _bounded_iterations(configurable.get("max_iterations", DEFAULT_MAX_ITERATIONS))
    max_attempts = int(configurable.get("max_attempts", 1))
    deadline_at = configurable.get("deadline_at")

    context: dict[str, Any] = {
        "attempted": set(),
        "unusable": set(),
        "facts": {},
        "business_fact_refs": [],
        "policy_refs": [],
        "errors": [],
        "tool_results": [],
        "case_memory": list(state.get("case_memory") or []),
        "claim_dependency_map": [],
        "retrieval_status": state.get("retrieval_status"),
        "best_score": state.get("best_score"),
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

        step = plan_next_step(state, context, tool_views)
        validation_error = _validate_planner_step(step, tool_views)
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
        if attempt_key in context["attempted"]:
            termination_reason = "no_more_useful_tools"
            break
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
            iteration,
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
        outcome = await tool_platform.invoke(tool_name, args, tool_ctx, session=session)
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
            "metrics_json": {"termination_reason": termination_reason, "calls_executed": calls_executed},
        }
    ]
    return {
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
        "recommendation_draft": _terminal_recommendation_draft(context),
        "termination_reason": termination_reason,
        "trace_steps": trace_steps,
    }


def _validate_planner_step(step: Any, tool_views: list[ToolViewV1]) -> dict[str, Any] | None:
    view_names = {view.name for view in tool_views}
    if not isinstance(step, dict):
        return _safe_error("INVALID_PLANNER_OUTPUT", "Planner output failed validation", "planner")
    has_stop = step.get("stop") is True
    has_tool = "next_tool" in step
    if has_stop == has_tool:
        return _safe_error("INVALID_PLANNER_OUTPUT", "Planner output must choose one action", "planner")
    if has_stop:
        return None
    tool_name = step.get("next_tool")
    if not isinstance(tool_name, str) or tool_name not in view_names:
        return _safe_error("INVALID_PLANNER_TOOL", "Planner selected an unavailable tool", "planner")
    if not isinstance(step.get("args"), dict):
        return _safe_error("INVALID_PLANNER_ARGS", "Planner tool arguments failed validation", "planner")
    return None


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
    }
    if result is not None and result.status in {"error", "invalid_request", "invalid_response"}:
        redacted_payload["termination_reason"] = "unrecoverable_error"
    if event_emitter is not None:
        await event_emitter(
            event_type=event_type, operation_id=operation_id, iteration=iteration, payload=redacted_payload
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
        iteration=iteration,
    )


def _accumulate_tool_result(
    context: dict[str, Any],
    descriptor: Any,
    tool_name: str,
    result: ToolResultV2,
    prompt_summary: ToolResultPromptSummary,
    full_projection: ToolResultProjectionV1,
) -> None:
    context["tool_results"].append(prompt_summary.model_dump(mode="json"))
    normalized = full_projection.normalized_result
    if result.status in FACT_STATUSES:
        if tool_name == "search_case_memory":
            context.setdefault("case_memory", []).extend(
                _case_memory_items_from_projection(normalized)
            )
        if result.business_fact_refs:
            for ref in result.business_fact_refs:
                ref_data = ref.model_dump(mode="json")
                context["business_fact_refs"].append(ref_data)
                context["facts"][ref.resource_type] = normalized
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
    slots = _case_slots(state)
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


def _terminal_recommendation_draft(context: dict[str, Any]) -> dict[str, Any] | None:
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


def _bounded_iterations(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_MAX_ITERATIONS
    return max(1, min(parsed, GLOBAL_MAX_ITERATIONS_CEILING))


def _canonical_stop_reason(value: Any) -> str:
    if value in {"enough_evidence", "no_more_useful_tools", "unrecoverable_error"}:
        return str(value)
    return "unrecoverable_error"


def _deadline_reached(deadline_at: Any) -> bool:
    return isinstance(deadline_at, datetime) and datetime.now(UTC) >= deadline_at


def _attempt_key(tool_name: str, args: dict[str, Any]) -> tuple[str, tuple[tuple[str, str], ...]]:
    return (tool_name, tuple(sorted((str(key), str(value)) for key, value in args.items())))


def _safe_error(code: str, safe_message: str, source: str) -> dict[str, Any]:
    return {"code": code, "safe_message": safe_message, "retryable": False, "source": source}


def _without_raw_payload(value: Any) -> Any:
    forbidden = {
        "raw",
        "raw_args",
        "raw_payload",
        "raw_tool_output",
        "raw_tool_payload",
        "replay_blob",
        "replay_debug_blob",
        "debug_blob",
        "approval_authority_body",
        "action_authority_body",
    }
    if isinstance(value, dict):
        return {key: _without_raw_payload(child) for key, child in value.items() if str(key).lower() not in forbidden}
    if isinstance(value, list):
        return [_without_raw_payload(item) for item in value]
    return value


def _case_memory_items(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return []
    items: list[dict[str, Any]] = []
    for item in data["items"]:
        if not isinstance(item, dict):
            continue
        case_memory_id = _safe_case_text(item.get("case_memory_id") or item.get("memory_id") or item.get("id"))
        excerpt = _safe_case_text(item.get("excerpt"))
        if not case_memory_id or not excerpt:
            continue
        projected: dict[str, Any] = {"case_memory_id": case_memory_id, "excerpt": excerpt}
        for key in ("applicability", "outcome", "caveats"):
            value = _safe_case_text(item.get(key))
            if value:
                projected[key] = value
        score = item.get("score")
        if isinstance(score, (int, float)):
            projected["score"] = float(score)
        for key in ("policy_refs", "source_refs"):
            refs = item.get(key)
            if isinstance(refs, list):
                projected[key] = _without_raw_payload(refs)
        items.append(projected)
    return items


def _safe_case_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized[:1500] or None


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
