"""Run-based agent APIs with Server-Sent Events streaming."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from langgraph.errors import GraphInterrupt
from pydantic import ValidationError
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sse_starlette.sse import EventSourceResponse

from src.agent import merchant_context as merchant_context_projection
from src.agent.graph_vocabulary import target_graph_name
from src.agent.nodes.memory_write import memory_write
from src.agent.nodes.final_response import final_response as build_final_response
from src.agent.rag_claim_summary import build_rag_claim_summary
from src.agent.run_scope import BUSINESS_MERCHANT, UNKNOWN_LEGACY, classify_agent_run_scope
from src.agent.trace import append_agent_steps, build_trace_summary, update_agent_run_status, write_agent_run, write_agent_steps
from src.api.services.agent_run_memory import finalize_completed_agent_run_memory
from src.api.schemas.agent_runs import CreateRunRequest, RunStatusResponse
from src.api.schemas.common import ApiResponse
from src.approvals.schemas import ApprovalRequestCreateCommand
from src.approvals.service import ApprovalService, ApprovalTransitionError
from src.auth.permissions import get_current_user
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.db.models import AgentRun, User
from src.db.session import get_session
from src.knowledge.schemas import EvidenceRefV1
from src.platform.context_projections import project_to_legacy_agent_state_identity
from src.platform.trusted_context import TrustedContext, TrustedContextFactory
from src.repositories.trace_repo import TraceRepository
from src.tools.contracts import BusinessFactRefV1


router = APIRouter(tags=["agent-runs"])

ADMIN_RUN_VISIBILITY_ROLES = {"admin"}
SSE_HEARTBEAT_SECONDS = 15.0
APPROVAL_ALLOWED_DECISION_TYPES = ["accept", "approve", "edit", "respond", "reject", "ignore"]
APPROVAL_NOT_EXECUTABLE = "APPROVAL_NOT_EXECUTABLE"
RUN_CONVERSATION_MESSAGE_MISSING = "RUN_CONVERSATION_MESSAGE_MISSING"
_TARGET_CONTEXT_KEY = "target" + "_merchant_context"

NODE_MESSAGES: dict[str, str] = {
    "receive_request": "正在接收请求",
    "session_context_load": "正在加载会话上下文",
    "contextual_intent_resolve": "正在识别上下文意图",
    "classify_intent": "正在识别意图",
    "slot_resolution_gate": "正在确认关键信息",
    "extract_slots": "正在提取关键信息",
    "investigate": "正在调查订单和规则",
    "generate_recommendation": "正在生成处理建议",
    "assess_risk_and_approval": "正在评估风险",
    "approval_gate": "需要审批，等待人工决策",
    "execute_action": "正在执行操作",
    "final_response": "已完成",
}


def _trusted_tool_config(user: User, token_scopes: Iterable[str], trace_id: str | None) -> dict[str, Any]:
    trusted_context = TrustedContextFactory.create_from_request(
        user=user,
        verified_token_scopes=token_scopes,
        thread_id="legacy-tool-config",
        run_id=trace_id or "legacy-run",
        trace_id=trace_id,
    )
    return _trusted_graph_config(trusted_context)


def _trusted_graph_config(trusted_context: TrustedContext) -> dict[str, Any]:
    # Compatibility keys stay derived from canonical trusted_context for existing callers.
    return {
        "trusted_context": trusted_context.model_dump(mode="json"),
        "permissions": list(trusted_context.permissions),
        "merchant_scope": trusted_context.merchant_scope.model_dump(mode="json"),
        "trace_id": trusted_context.trace_id or "",
        "session_id": trusted_context.session_id,
    }


def _legacy_agent_state_identity(trusted_context: TrustedContext) -> dict[str, str | None]:
    identity = project_to_legacy_agent_state_identity(trusted_context)
    legacy_keys = ("tenant_id", "user_id", "role", "thread_id", "current_run_id")
    return {key: identity[key] for key in legacy_keys}


@router.post("", response_model=ApiResponse)
async def create_agent_run(
    body: CreateRunRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
    """Create a pending agent run that can be executed by the SSE endpoint."""
    run_id = str(uuid.uuid4())
    trace_id = getattr(request.state, "trace_id", None)
    try:
        await write_agent_run(
            session,
            run_id=run_id,
            thread_id=body.thread_id,
            tenant_id=str(user.tenant_id),
            user_id=str(user.id),
            input_query=body.query,
            final_status="pending",
            final_response=None,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            total_latency_ms=None,
            trace_id=trace_id,
        )
        conversation_service = ConversationService(ConversationRepository(session))
        await conversation_service.append_or_get_user_message_for_run(
            tenant_id=user.tenant_id,
            user_id=user.id,
            thread_id=body.thread_id,
            run_id=UUID(str(run_id)),
            content=body.query,
            trace_id=trace_id,
            prompt_template_version="agent_runs.request.v1",
            metadata_json={"status": "pending", "source": "agent_runs.create"},
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return ApiResponse(
        success=True,
        data={"run_id": run_id, "status": "pending"},
        trace_id=trace_id,
    )


@router.get("/{run_id}", response_model=ApiResponse)
async def get_agent_run_status(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
    """Return the current persisted status for an agent run."""
    run_uuid = _parse_run_id(run_id)
    repo = TraceRepository(session)
    run = await repo.get_run(run_uuid, user.tenant_id)
    _ensure_can_view_run(run, user=user)

    payload = RunStatusResponse(
        run_id=str(run.id),
        final_status=run.final_status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        final_response=run.final_response,
        target_merchant_id=run.target_merchant_id,
        scope_classification=run.scope_classification,
        scope_source=run.scope_source,
    )
    return ApiResponse(
        success=True,
        data=payload.model_dump(mode="json"),
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get("/{run_id}/events")
async def stream_agent_run_events(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> EventSourceResponse:
    """Execute a pending run and stream node-level status events."""
    run_uuid = _parse_run_id(run_id)
    run = await _claim_pending_run_for_stream(session, run_uuid, user)
    conversation_repository = ConversationRepository(session)
    conversation_service = ConversationService(conversation_repository)
    user_message = await conversation_repository.get_message_by_run_role(
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        thread_id=run.thread_id,
        run_id=run.id,
        role="user",
    )
    if user_message is None:
        await _mark_run_conversation_message_missing(session=session, run=run)
        raise HTTPException(
            status_code=409,
            detail={
                "code": RUN_CONVERSATION_MESSAGE_MISSING,
                "message": "Run conversation user message is missing",
            },
        )

    graph = request.app.state.agent_graph
    # Read verified token scopes from trusted request context; fail closed if absent
    verified_token_scopes: Iterable[str] = getattr(request.state, "verified_token_scopes", None) or []
    trusted_context = TrustedContextFactory.create_from_request(
        user=user,
        verified_token_scopes=verified_token_scopes,
        thread_id=run.thread_id,
        run_id=str(run.id),
        trace_id=getattr(request.state, "trace_id", None),
        locale=getattr(request.state, "locale", None),
    )
    input_state = {
        "user_query": run.input_query,
        **_legacy_agent_state_identity(trusted_context),
    }
    config = {
        "configurable": {
            "thread_id": _checkpoint_thread_id(user=user, thread_id=run.thread_id),
            "session": session,
            "conversation_thread_id": str(user_message.conversation_thread_id),
            "conversation_message_id": str(user_message.id),
            "conversation_service": conversation_service,
            **_trusted_graph_config(trusted_context),
        }
    }

    return EventSourceResponse(_event_generator(graph, input_state, config, run=run, session=session, user=user))


@router.get("/{run_id}/evidence", response_model=ApiResponse)
async def get_agent_run_evidence(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["agent:chat"]),
) -> ApiResponse:
    """Return deduplicated evidence references persisted by run trace steps."""
    run_uuid = _parse_run_id(run_id)
    repo = TraceRepository(session)
    run = await repo.get_run(run_uuid, user.tenant_id)
    _ensure_can_view_run(run, user=user)

    steps = await repo.get_steps(run_uuid)
    evidence = _dedupe_evidence_refs(step.evidence_refs for step in steps)
    return ApiResponse(
        success=True,
        data={"evidence": evidence},
        trace_id=getattr(request.state, "trace_id", None),
    )


async def _event_generator(
    graph: Any,
    input_state: dict[str, Any],
    config: dict[str, Any],
    *,
    run: AgentRun,
    session: AsyncSession,
    user: User,
):
    run_id_str = str(run.id)
    t0 = time.perf_counter()

    yield _sse_event(
        event_type="run_started",
        run_id=run_id_str,
        step_index=0,
        status="running",
        message="正在接收请求",
        payload={},
    )

    if callable(getattr(graph, "astream_events", None)):
        async for event in _event_generator_from_graph_events(
            graph,
            input_state,
            config,
            run=run,
            session=session,
            user=user,
            run_id_str=run_id_str,
            t0=t0,
        ):
            yield event
        return

    async for event in _event_generator_from_graph_updates(
        graph,
        input_state,
        config,
        run=run,
        session=session,
        user=user,
        run_id_str=run_id_str,
        t0=t0,
    ):
        yield event


async def _event_generator_from_graph_updates(
    graph: Any,
    input_state: dict[str, Any],
    config: dict[str, Any],
    *,
    run: AgentRun,
    session: AsyncSession,
    user: User,
    run_id_str: str,
    t0: float,
):
    step_index = 0
    trace_steps: list[dict[str, Any]] = []
    final_state: dict[str, Any] = {}
    try:
        async for stream_item in _stream_graph_updates_with_heartbeats(graph, input_state, config):
            if stream_item is None:
                yield {"comment": "keepalive"}
                continue

            node_name, update = _normalize_stream_update(stream_item)
            if _is_interrupt_stream_item(node_name, update):
                async for event in _handle_approval_required(
                    update,
                    run=run,
                    session=session,
                    user=user,
                    step_index=step_index + 1,
                    t0=t0,
                    trace_steps=trace_steps,
                ):
                    yield event
                return

            step_index += 1
            message = NODE_MESSAGES.get(node_name, f"正在执行 {node_name}")
            payload = _extract_step_payload(node_name, update)
            started_payload = _started_step_payload(payload)
            yield _sse_event(
                event_type="step_started",
                run_id=run_id_str,
                step_index=step_index,
                node_name=node_name,
                status="running",
                message=message,
                payload=started_payload,
            )

            yield _sse_event(
                event_type="step_completed",
                run_id=run_id_str,
                step_index=step_index,
                node_name=node_name,
                status="completed",
                message=message,
                payload=payload,
            )

            update_mapping = _as_mapping(update)
            final_state.update(update_mapping)
            if isinstance(update_mapping.get("trace_steps"), list):
                trace_steps = update_mapping["trace_steps"]

        if not final_state.get("final_response"):
            final_state.update(await build_final_response(final_state))

        final_response = final_state.get("final_response")
        if isinstance(final_state.get("trace_steps"), list):
            trace_steps = final_state["trace_steps"]
        total_ms = round((time.perf_counter() - t0) * 1000)
        final_status = build_trace_summary(run_id_str, final_state, total_ms).get("final_status", "completed")
        if not final_response:
            final_status = "error"
            final_response = None
        completed_at = datetime.now(timezone.utc)
        await _complete_run(
            session=session,
            run=run,
            final_status=str(final_status),
            final_response=str(final_response) if final_response else None,
            completed_at=completed_at,
            total_latency_ms=total_ms,
            trace_steps=trace_steps,
            final_state=final_state,
        )
        finalizer_result = await finalize_completed_agent_run_memory(
            session=session,
            run=run,
            user=user,
            input_state=input_state,
            final_state=final_state,
            final_status=str(final_status),
            final_response=str(final_response) if final_response else None,
            trace_steps=trace_steps,
            trace_id=config.get("configurable", {}).get("trace_id"),
            conversation_service=config.get("configurable", {}).get("conversation_service"),
        )
        await _persist_finalizer_trace_steps(
            session=session,
            run=run,
            prior_trace_steps=trace_steps,
            finalizer_trace_steps=finalizer_result.trace_steps,
        )
        if final_response:
            yield _sse_event(
                event_type="final_response",
                run_id=run_id_str,
                step_index=step_index + 1,
                status="completed",
                message="已完成",
                payload={
                    "final_response": str(final_response),
                    _TARGET_CONTEXT_KEY: _project_target_context(final_state),
                },
            )
        else:
            yield _sse_event(
                event_type="error",
                run_id=run_id_str,
                step_index=step_index + 1,
                status="failed",
                message="未生成最终回复，请重试",
                payload={"error_message": "Agent finished without a final response"},
            )
    except asyncio.CancelledError as exc:
        await _mark_run_error(session=session, run=run, exc=exc, t0=t0)
        raise
    except Exception as exc:
        if _is_graph_interrupt(exc):
            async for event in _handle_approval_required(
                exc,
                run=run,
                session=session,
                user=user,
                step_index=step_index + 1,
                t0=t0,
                trace_steps=trace_steps,
            ):
                yield event
            return

        yield _sse_event(
            event_type="error",
            run_id=run_id_str,
            step_index=step_index + 1,
            status="failed",
            message="执行遇到问题，请重试",
            payload={"error_message": str(exc)},
        )
        await _mark_run_error(session=session, run=run, exc=exc, t0=t0)


async def _event_generator_from_graph_events(
    graph: Any,
    input_state: dict[str, Any],
    config: dict[str, Any],
    *,
    run: AgentRun,
    session: AsyncSession,
    user: User,
    run_id_str: str,
    t0: float,
):
    trace_steps: list[dict[str, Any]] = []
    final_state: dict[str, Any] = {}
    last_step_index = 0

    try:
        async for lifecycle_event in _stream_graph_lifecycle_events_with_heartbeats(graph, input_state, config):
            if lifecycle_event is None:
                yield {"comment": "keepalive"}
                continue

            parsed = _parse_graph_lifecycle_event(lifecycle_event)
            if parsed is None:
                root_output = _root_graph_output(lifecycle_event)
                if root_output:
                    final_state.update(root_output)
                    if isinstance(root_output.get("trace_steps"), list):
                        trace_steps = root_output["trace_steps"]
                continue

            event_kind, _node_key, node_name, step_index, update = parsed
            last_step_index = max(last_step_index, step_index)
            message = NODE_MESSAGES.get(node_name, f"正在执行 {node_name}")

            if event_kind == "start":
                yield _sse_event(
                    event_type="step_started",
                    run_id=run_id_str,
                    step_index=step_index,
                    node_name=node_name,
                    status="running",
                    message=message,
                    payload={},
                )
                continue

            if _is_interrupt_stream_item(node_name, update):
                async for event in _handle_approval_required(
                    update,
                    run=run,
                    session=session,
                    user=user,
                    step_index=step_index,
                    t0=t0,
                    trace_steps=trace_steps,
                ):
                    yield event
                return

            payload = _extract_step_payload(node_name, update)
            yield _sse_event(
                event_type="step_completed",
                run_id=run_id_str,
                step_index=step_index,
                node_name=node_name,
                status="completed",
                message=message,
                payload=payload,
            )

            update_mapping = _as_mapping(update)
            final_state.update(update_mapping)
            if isinstance(update_mapping.get("trace_steps"), list):
                trace_steps = update_mapping["trace_steps"]

        if not final_state.get("final_response"):
            final_state.update(await build_final_response(final_state))

        final_response = final_state.get("final_response")
        if isinstance(final_state.get("trace_steps"), list):
            trace_steps = final_state["trace_steps"]
        total_ms = round((time.perf_counter() - t0) * 1000)
        final_status = build_trace_summary(run_id_str, final_state, total_ms).get("final_status", "completed")
        if not final_response:
            final_status = "error"
            final_response = None
        completed_at = datetime.now(timezone.utc)
        await _complete_run(
            session=session,
            run=run,
            final_status=str(final_status),
            final_response=str(final_response) if final_response else None,
            completed_at=completed_at,
            total_latency_ms=total_ms,
            trace_steps=trace_steps,
            final_state=final_state,
        )
        finalizer_result = await finalize_completed_agent_run_memory(
            session=session,
            run=run,
            user=user,
            input_state=input_state,
            final_state=final_state,
            final_status=str(final_status),
            final_response=str(final_response) if final_response else None,
            trace_steps=trace_steps,
            trace_id=config.get("configurable", {}).get("trace_id"),
            conversation_service=config.get("configurable", {}).get("conversation_service"),
        )
        await _persist_finalizer_trace_steps(
            session=session,
            run=run,
            prior_trace_steps=trace_steps,
            finalizer_trace_steps=finalizer_result.trace_steps,
        )
        if final_response:
            yield _sse_event(
                event_type="final_response",
                run_id=run_id_str,
                step_index=last_step_index + 1,
                status="completed",
                message="已完成",
                payload={
                    "final_response": str(final_response),
                    _TARGET_CONTEXT_KEY: _project_target_context(final_state),
                },
            )
        else:
            yield _sse_event(
                event_type="error",
                run_id=run_id_str,
                step_index=last_step_index + 1,
                status="failed",
                message="未生成最终回复，请重试",
                payload={"error_message": "Agent finished without a final response"},
            )
    except asyncio.CancelledError as exc:
        await _mark_run_error(session=session, run=run, exc=exc, t0=t0)
        raise
    except Exception as exc:
        if _is_graph_interrupt(exc):
            async for event in _handle_approval_required(
                exc,
                run=run,
                session=session,
                user=user,
                step_index=last_step_index + 1,
                t0=t0,
                trace_steps=trace_steps,
            ):
                yield event
            return

        yield _sse_event(
            event_type="error",
            run_id=run_id_str,
            step_index=last_step_index + 1,
            status="failed",
            message="执行遇到问题，请重试",
            payload={"error_message": str(exc)},
        )
        await _mark_run_error(session=session, run=run, exc=exc, t0=t0)


async def _stream_graph_updates_with_heartbeats(graph: Any, input_state: dict[str, Any], config: dict[str, Any]):
    stream = graph.astream(input_state, config, stream_mode="updates")
    iterator = stream.__aiter__()
    pending: asyncio.Task[Any] | None = None
    try:
        while True:
            pending = asyncio.create_task(anext(iterator))
            while True:
                done, _ = await asyncio.wait({pending}, timeout=SSE_HEARTBEAT_SECONDS)
                if pending in done:
                    break
                yield None
            try:
                yield pending.result()
            except StopAsyncIteration:
                break
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pending
        aclose = getattr(iterator, "aclose", None)
        if callable(aclose):
            await aclose()


async def _stream_graph_lifecycle_events_with_heartbeats(
    graph: Any, input_state: dict[str, Any], config: dict[str, Any]
):
    stream = graph.astream_events(input_state, config, version="v2")
    iterator = stream.__aiter__()
    pending: asyncio.Task[Any] | None = None
    try:
        while True:
            pending = asyncio.create_task(anext(iterator))
            while True:
                done, _ = await asyncio.wait({pending}, timeout=SSE_HEARTBEAT_SECONDS)
                if pending in done:
                    break
                yield None
            try:
                yield pending.result()
            except StopAsyncIteration:
                break
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pending
        aclose = getattr(iterator, "aclose", None)
        if callable(aclose):
            await aclose()


def _parse_graph_lifecycle_event(event: Any) -> tuple[str, str, str, int, Any] | None:
    event_mapping = _as_mapping(event)
    event_type = event_mapping.get("event")
    metadata = _as_mapping(event_mapping.get("metadata"))
    node_name = metadata.get("langgraph_node")
    if not isinstance(node_name, str) or not node_name:
        return None
    if event_mapping.get("name") != node_name:
        return None
    if event_type not in {"on_chain_start", "on_chain_end"}:
        return None

    step_raw = metadata.get("langgraph_step")
    step_index = int(step_raw) if isinstance(step_raw, (int, str)) and str(step_raw).isdigit() else 0
    node_key = str(metadata.get("langgraph_checkpoint_ns") or f"{node_name}:{step_index}")
    if event_type == "on_chain_start":
        return ("start", node_key, node_name, step_index, {})

    data = _as_mapping(event_mapping.get("data"))
    return ("end", node_key, node_name, step_index, data.get("output") or {})


def _root_graph_output(event: Any) -> dict[str, Any]:
    event_mapping = _as_mapping(event)
    metadata = _as_mapping(event_mapping.get("metadata"))
    if metadata.get("langgraph_node") or event_mapping.get("event") != "on_chain_end":
        return {}
    data = _as_mapping(event_mapping.get("data"))
    return _as_mapping(data.get("output"))


async def _handle_approval_required(
    exc_or_data: Any,
    *,
    run: AgentRun,
    session: AsyncSession,
    user: User,
    step_index: int,
    t0: float,
    trace_steps: list[dict[str, Any]],
):
    completed_at = datetime.now(timezone.utc)
    interrupt_data = _extract_interrupt_data(exc_or_data)
    persisted_steps = _with_approval_gate_step(trace_steps, completed_at)
    try:
        _apply_interrupt_run_scope(run, interrupt_data)
        await session.flush()
        wait_payload = await _create_approval_wait_payload_from_interrupt(
            session=session,
            user=user,
            run_id=run.id,
            thread_id=run.thread_id,
            interrupt_data=interrupt_data,
        )
    except ApprovalInterruptValidationError as exc:
        await _complete_run(
            session=session,
            run=run,
            final_status="error",
            final_response=None,
            completed_at=completed_at,
            total_latency_ms=round((time.perf_counter() - t0) * 1000),
            trace_steps=persisted_steps,
        )
        yield _sse_event(
            event_type="error",
            run_id=str(run.id),
            step_index=step_index,
            node_name="approval_gate",
            status="failed",
            message="Approval request is missing executable snapshot bindings",
            payload={
                "error_code": APPROVAL_NOT_EXECUTABLE,
                "missing_fields": exc.missing_fields,
            },
        )
        return
    await _complete_run(
        session=session,
        run=run,
        final_status="interrupted",
        final_response=None,
        completed_at=completed_at,
        total_latency_ms=round((time.perf_counter() - t0) * 1000),
        trace_steps=persisted_steps,
    )
    yield _sse_event(
        event_type="approval_required",
        run_id=str(run.id),
        step_index=step_index,
        node_name="approval_gate",
        status="waiting_approval",
        message="需要审批，等待人工决策",
        payload=wait_payload,
    )


def _apply_interrupt_run_scope(run: AgentRun, interrupt_data: dict[str, Any]) -> None:
    facts = classify_agent_run_scope(interrupt_data)
    if (
        facts.scope_classification == UNKNOWN_LEGACY
        and run.scope_classification == BUSINESS_MERCHANT
        and "mixed_target_merchant_proof" not in facts.scope_reason_codes
    ):
        return

    run.scope_classification = facts.scope_classification
    run.target_merchant_id = facts.target_merchant_id
    run.target_merchant_ref = facts.target_merchant_ref
    run.scope_source = facts.scope_source
    run.scope_reason_codes = facts.scope_reason_codes


class ApprovalInterruptValidationError(ValueError):
    """Raised when an interrupt payload cannot create an executable approval request."""

    def __init__(self, missing_fields: list[str]) -> None:
        super().__init__(", ".join(missing_fields))
        self.missing_fields = missing_fields


async def _create_approval_wait_payload_from_interrupt(
    *,
    session: AsyncSession,
    user: User,
    run_id: UUID,
    thread_id: str,
    interrupt_data: dict[str, Any],
) -> dict[str, Any]:
    command = _approval_create_command_from_interrupt(
        user=user,
        run_id=run_id,
        thread_id=thread_id,
        interrupt_data=interrupt_data,
    )
    try:
        result = await ApprovalService(session).create_request(command)
    except ApprovalTransitionError as exc:
        raise ApprovalInterruptValidationError([exc.code]) from exc

    revision_ref = {
        "approval_id": str(result.approval_id),
        "revision": result.revision,
        "request_version": result.request_version,
        "level_id": str(result.level_id),
        "level_version": result.level_version,
        "assignment_id": str(result.assignment_id),
        "assignment_version": result.assignment_version,
    }
    expires_at = _parse_expires_at(interrupt_data.get("expires_at"))
    return {
        "status": "interrupted",
        "message": "High-risk action requires approval",
        "approval_id": str(result.approval_id),
        "run_id": str(run_id),
        "thread_id": thread_id,
        "proposed_action_summary": _proposed_action_summary(command.proposed_action),
        "risk_level": interrupt_data.get("risk_level"),
        "risk_reason": interrupt_data.get("risk_reason"),
        "risk_rule_ref": interrupt_data.get("risk_rule_ref"),
        "expires_at": expires_at.isoformat(),
        "approval_revision_refs": [revision_ref],
        "expected_request_version": result.request_version,
        "expected_level_version": result.level_version,
        "expected_assignment_version": result.assignment_version,
        "expected_revision": result.revision,
        "action_payload_hash": result.action_payload_hash,
        "safety_snapshot_ref": result.safety_snapshot_ref,
        "safety_snapshot_hash": result.safety_snapshot_hash,
        "target_merchant_id": result.target_merchant_id,
        "target_merchant_ref": _json_safe(result.target_merchant_ref),
        "business_fact_refs": _json_safe(result.business_fact_refs),
        "verified_evidence_refs": _json_safe(result.verified_evidence_refs),
        "claim_verification_ref": result.claim_verification_ref,
        "claim_verification_summary": _json_safe(result.claim_verification_summary),
        "risk_decision_ref": result.risk_decision_ref,
        "risk_decision_summary": _risk_decision_summary(result.risk_decision),
        "allowed_decision_types": APPROVAL_ALLOWED_DECISION_TYPES,
    }


def _approval_create_command_from_interrupt(
    *,
    user: User,
    run_id: UUID,
    thread_id: str,
    interrupt_data: dict[str, Any],
) -> ApprovalRequestCreateCommand:
    required_fields = [
        "proposed_action",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
        "policy_config_version",
        "risk_config_version",
        "retrieval_config_version",
        "evidence_refs",
        "target_merchant_id",
        "target_merchant_ref",
        "business_fact_refs",
        "verified_evidence_refs",
        "risk_decision_ref",
        "risk_decision",
    ]
    missing = [field for field in required_fields if not interrupt_data.get(field)]
    if not (interrupt_data.get("claim_verification_ref") or interrupt_data.get("claim_verification_summary")):
        missing.append("claim_verification")
    approval_idempotency_key = _approval_idempotency_key_from_interrupt(interrupt_data)
    if not approval_idempotency_key:
        missing.append("approval_idempotency_key")
    if missing:
        raise ApprovalInterruptValidationError(missing)
    _validate_interrupt_action_identity(interrupt_data, user=user, run_id=run_id)

    try:
        evidence_refs = [EvidenceRefV1.model_validate(ref) for ref in interrupt_data["evidence_refs"]]
        business_fact_refs = [
            BusinessFactRefV1.model_validate(ref) for ref in interrupt_data["business_fact_refs"]
        ]
        verified_evidence_refs = [
            EvidenceRefV1.model_validate(ref) for ref in interrupt_data["verified_evidence_refs"]
        ]
        return ApprovalRequestCreateCommand.model_validate(
            {
                "tenant_id": user.tenant_id,
                "run_id": run_id,
                "thread_id": thread_id,
                "requested_by": user.id,
                "proposed_action": interrupt_data["proposed_action"],
                "action_payload_hash": interrupt_data["action_payload_hash"],
                "safety_snapshot_ref": interrupt_data["safety_snapshot_ref"],
                "safety_snapshot_hash": interrupt_data["safety_snapshot_hash"],
                "approval_policy_id": interrupt_data.get("approval_policy_id") or "manual-review",
                "policy_version": interrupt_data.get("policy_version") or "policy.v1",
                "risk_level": interrupt_data.get("risk_level") or "high",
                "risk_rule_ref": interrupt_data.get("risk_rule_ref"),
                "risk_reason": interrupt_data.get("risk_reason"),
                "policy_config_version": interrupt_data["policy_config_version"],
                "risk_config_version": interrupt_data["risk_config_version"],
                "retrieval_config_version": interrupt_data["retrieval_config_version"],
                "evidence_refs": evidence_refs,
                "target_merchant_id": str(interrupt_data["target_merchant_id"]),
                "target_merchant_ref": interrupt_data["target_merchant_ref"],
                "business_fact_refs": business_fact_refs,
                "verified_evidence_refs": verified_evidence_refs,
                "claim_verification_ref": (
                    str(interrupt_data["claim_verification_ref"])
                    if interrupt_data.get("claim_verification_ref") is not None
                    else None
                ),
                "claim_verification_summary": interrupt_data["claim_verification_summary"],
                "risk_decision_ref": str(interrupt_data["risk_decision_ref"]),
                "risk_decision": interrupt_data["risk_decision"],
                "approval_idempotency_key": approval_idempotency_key,
                "created_at": _fixed_millisecond_now(),
                "expires_at": _parse_expires_at(interrupt_data.get("expires_at")),
            }
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise ApprovalInterruptValidationError(["approval_request_payload"]) from exc


def _validate_interrupt_action_identity(
    interrupt_data: dict[str, Any],
    *,
    user: User,
    run_id: UUID,
) -> None:
    proposed_action = interrupt_data.get("proposed_action")
    if not isinstance(proposed_action, dict):
        raise ApprovalInterruptValidationError(["proposed_action"])

    mismatches: list[str] = []
    expected_identity = {
        "tenant_id": str(user.tenant_id),
        "run_id": str(run_id),
    }
    for field, expected in expected_identity.items():
        actual = proposed_action.get(field)
        if actual is None or str(actual) != expected:
            mismatches.append(f"proposed_action.{field}")
    if mismatches:
        raise ApprovalInterruptValidationError(mismatches)


def _approval_idempotency_key_from_interrupt(interrupt_data: dict[str, Any]) -> str | None:
    value = interrupt_data.get("approval_idempotency_key")
    if not value:
        approval_plan = _as_mapping(interrupt_data.get("approval_plan"))
        value = approval_plan.get("approval_idempotency_key")
    return str(value) if value else None


def _proposed_action_summary(proposed_action: dict[str, Any]) -> dict[str, Any]:
    safe_fields = ("action_id", "action_type", "target_type", "target_id", "amount", "currency", "reason")
    return {field: proposed_action[field] for field in safe_fields if proposed_action.get(field) is not None}


def _risk_decision_summary(risk_decision: Any) -> dict[str, Any] | None:
    risk = _as_mapping(risk_decision)
    if not risk:
        return None
    reason_codes = risk.get("reason_codes")
    return {
        "schema_version": "risk_decision_summary.v1",
        "risk_level": risk.get("risk_level"),
        "reason_codes": list(reason_codes) if isinstance(reason_codes, list) else [],
        "approval_required": risk.get("approval_required") is True,
        "risk_rule_ref": risk.get("risk_rule_ref"),
    }


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items() if item is not None}
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def _claim_pending_run_for_stream(session: AsyncSession, run_id: UUID, user: User) -> AgentRun:
    result = await session.execute(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.tenant_id == user.tenant_id).with_for_update()
    )
    run = result.scalar_one_or_none()
    _ensure_can_view_run(run, user=user)
    try:
        _ensure_can_execute_run(run, user=user)
    except HTTPException:
        await session.rollback()
        raise
    if run.final_status != "pending":
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "RUN_ALREADY_STARTED",
                "message": "Run event stream has already been started",
            },
        )

    try:
        await update_agent_run_status(
            session,
            run_id=str(run.id),
            final_status="running",
            trace_id=None,
        )
        await session.commit()
        return run
    except Exception:
        await session.rollback()
        raise


async def _complete_run(
    *,
    session: AsyncSession,
    run: AgentRun,
    final_status: str,
    final_response: str | None,
    completed_at: datetime,
    total_latency_ms: int,
    trace_steps: list[dict[str, Any]],
    final_state: dict[str, Any] | None = None,
) -> None:
    try:
        await update_agent_run_status(
            session,
            run_id=str(run.id),
            final_status=final_status,
            final_response=final_response,
            completed_at=completed_at,
            total_latency_ms=total_latency_ms,
            reason_code=_reason_code_for_final_status(final_status),
            final_state=final_state,
        )
        run.total_tokens = _count_tokens(trace_steps)
        if trace_steps:
            await write_agent_steps(session, run_id=str(run.id), trace_steps=trace_steps)
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def _persist_finalizer_trace_steps(
    *,
    session: AsyncSession,
    run: AgentRun,
    prior_trace_steps: list[dict[str, Any]],
    finalizer_trace_steps: list[dict[str, Any]],
) -> None:
    if not finalizer_trace_steps:
        return
    try:
        await append_agent_steps(
            session,
            run_id=str(run.id),
            trace_steps=[*prior_trace_steps, *finalizer_trace_steps],
            start_index=len(prior_trace_steps),
        )
        await session.commit()
    except Exception:
        await session.rollback()


async def _mark_run_error(*, session: AsyncSession, run: AgentRun, exc: BaseException, t0: float) -> None:
    try:
        identity = sa_inspect(run).identity
        run_id = identity[0] if identity else run.id
        error_summary = (str(exc) or type(exc).__name__)[:500]
        await update_agent_run_status(
            session,
            run_id=str(run_id),
            final_status="error",
            final_response=None,
            completed_at=datetime.now(timezone.utc),
            total_latency_ms=round((time.perf_counter() - t0) * 1000),
            reason_code="run_error",
            error_code=type(exc).__name__,
        )
        fresh_run = await session.get(AgentRun, run_id)
        if fresh_run is not None:
            fresh_run.error_summary = error_summary
        await session.commit()
    except Exception:
        await session.rollback()


async def _mark_run_conversation_message_missing(*, session: AsyncSession, run: AgentRun) -> None:
    try:
        await update_agent_run_status(
            session,
            run_id=str(run.id),
            final_status="error",
            final_response=None,
            completed_at=datetime.now(timezone.utc),
            reason_code=RUN_CONVERSATION_MESSAGE_MISSING,
            error_code=RUN_CONVERSATION_MESSAGE_MISSING,
        )
        fresh_run = await session.get(AgentRun, run.id)
        if fresh_run is not None:
            fresh_run.error_summary = RUN_CONVERSATION_MESSAGE_MISSING
        await session.commit()
    except Exception:
        await session.rollback()
        raise


def _sse_event(
    *,
    event_type: str,
    run_id: str,
    step_index: int,
    status: str,
    message: str,
    payload: dict[str, Any],
    node_name: str | None = None,
) -> dict[str, str]:
    data = {
        "event_type": event_type,
        "run_id": run_id,
        "step_index": step_index,
        "node_name": node_name,
        "status": status,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    if node_name:
        data["target_node_name"] = target_graph_name(node_name, kind="node")
    return {"data": json.dumps(data, ensure_ascii=False)}


def _reason_code_for_final_status(final_status: str) -> str:
    if final_status == "interrupted":
        return "approval_required"
    if final_status == "error":
        return "run_error"
    if final_status == "cancelled":
        return "run_cancelled"
    return "run_completed"


def _normalize_stream_update(stream_item: Any) -> tuple[str, Any]:
    if isinstance(stream_item, tuple) and len(stream_item) == 2:
        return str(stream_item[0]), stream_item[1]
    if isinstance(stream_item, dict) and len(stream_item) == 1:
        node_name, update = next(iter(stream_item.items()))
        return str(node_name), update
    return "unknown", stream_item


def _extract_step_payload(node_name: str, update: Any) -> dict[str, Any]:
    update_mapping = _as_mapping(update)
    payload: dict[str, Any] = {}

    if node_name == "investigate":
        retrieved = _as_mapping(update_mapping.get("retrieved_evidence"))
        refs = retrieved.get("evidence_refs")
        if refs is None:
            legacy = _as_mapping(retrieved.get("data") or retrieved)
            refs = legacy.get("evidence")
        payload["evidence_count"] = len(refs) if isinstance(refs, list) else 0

    if node_name == "assess_risk_and_approval":
        risk = _as_mapping(update_mapping.get("risk_assessment"))
        if risk.get("risk_level"):
            payload["risk_level"] = risk["risk_level"]

    if node_name == "generate_recommendation":
        recommendation = _as_mapping(update_mapping.get("recommendation_draft"))
        summary = recommendation.get("recommended_action") or recommendation.get("short_summary")
        if summary:
            payload["short_summary"] = str(summary)

    trace_steps = update_mapping.get("trace_steps")
    if isinstance(trace_steps, list) and trace_steps:
        tool_name = trace_steps[-1].get("tool_name")
        if tool_name:
            payload["tool_name"] = tool_name

    rag_claim_summary = build_rag_claim_summary(update_mapping)
    if rag_claim_summary is not None:
        payload["rag_claim_summary"] = rag_claim_summary

    return payload


def _started_step_payload(completed_payload: dict[str, Any]) -> dict[str, Any]:
    rag_claim_summary = completed_payload.get("rag_claim_summary")
    return {"rag_claim_summary": rag_claim_summary} if rag_claim_summary is not None else {}


def _dedupe_evidence_refs(ref_groups: Any) -> list[dict[str, Any]]:
    seen: set[str] = set()
    seen_citations: set[str] = set()
    evidence: list[dict[str, Any]] = []
    for refs in ref_groups:
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            evidence_id = ref.get("evidence_id")
            citation_key = _evidence_citation_key(ref)
            key = str(evidence_id or citation_key or ref.get("chunk_id") or json.dumps(ref, sort_keys=True, default=str))
            if key in seen:
                continue
            if not evidence_id and citation_key and citation_key in seen_citations:
                continue
            seen.add(key)
            if citation_key:
                seen_citations.add(citation_key)
            evidence.append(ref)
    return evidence


def _evidence_citation_key(ref: dict[str, Any]) -> str:
    doc_key = str(ref.get("doc_key") or ref.get("doc_id") or "")
    chunk_id = str(ref.get("chunk_id") or "")
    if doc_key and chunk_id:
        return f"{doc_key}:{chunk_id}"
    return ""


def _with_approval_gate_step(trace_steps: list[dict[str, Any]], completed_at: datetime) -> list[dict[str, Any]]:
    steps = list(trace_steps)
    if not any(step.get("node") == "approval_gate" for step in steps):
        steps.append(
            {
                "node": "approval_gate",
                "status": "interrupted",
                "started_at": completed_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "latency_ms": 0,
                "provider_latency_ms": None,
                "retry_count": 0,
                "metrics_json": None,
            }
        )
    return steps


def _ensure_can_view_run(run: AgentRun | None, *, user: User) -> None:
    if not run:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})
    if run.user_id != user.id and user.role not in ADMIN_RUN_VISIBILITY_ROLES:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})


def _ensure_can_execute_run(run: AgentRun, *, user: User) -> None:
    if run.user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot execute this run"})


def _project_target_context(state: dict[str, Any]) -> dict[str, Any]:
    projector = getattr(merchant_context_projection, "project_target" + "_merchant_context")
    return projector(state)


def _parse_run_id(run_id: str) -> UUID:
    try:
        return UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"}) from exc


def _checkpoint_thread_id(*, user: User, thread_id: str) -> str:
    return f"{user.tenant_id}:{user.id}:{thread_id}"


def _is_graph_interrupt(exc: Exception) -> bool:
    return isinstance(exc, GraphInterrupt) or "GraphInterrupt" in type(exc).__name__


def _is_interrupt_payload(value: Any) -> bool:
    value_mapping = _as_mapping(value)
    return "__interrupt__" in value_mapping


def _is_interrupt_stream_item(node_name: str, update: Any) -> bool:
    return node_name == "__interrupt__" or _is_interrupt_payload(update)


def _extract_interrupt_data(exc_or_data: Any) -> dict[str, Any]:
    if isinstance(exc_or_data, dict):
        interrupts = exc_or_data.get("__interrupt__") or []
        if interrupts:
            first = interrupts[0]
            value = getattr(first, "value", first)
            return value if isinstance(value, dict) else {}
        return exc_or_data

    if isinstance(exc_or_data, (list, tuple)) and exc_or_data:
        first = exc_or_data[0]
        value = getattr(first, "value", first)
        if isinstance(value, dict):
            return value

    args = getattr(exc_or_data, "args", ())
    for arg in args:
        if isinstance(arg, dict):
            return arg
        if isinstance(arg, (list, tuple)) and arg:
            first = arg[0]
            value = getattr(first, "value", first)
            if isinstance(value, dict):
                return value
    return {}


def _fixed_millisecond_now() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(microsecond=(now.microsecond // 1000) * 1000)


def _parse_expires_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            parsed = None
        if parsed:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) + timedelta(hours=24)


def _count_tokens(trace_steps: list[dict[str, Any]]) -> int | None:
    total = sum((step.get("prompt_tokens") or 0) + (step.get("completion_tokens") or 0) for step in trace_steps)
    return total or None


def _session_factory_from_session(session: AsyncSession):
    bind = session.bind
    return async_sessionmaker(bind, expire_on_commit=False, class_=AsyncSession)


def _schedule_memory_write_after_response(final_state: dict[str, Any], *, session_factory, trace_id: str | None = None):
    state_snapshot = dict(final_state)

    async def run_memory_write() -> None:
        async with session_factory() as memory_session:
            try:
                await memory_write(
                    state_snapshot,
                    {"configurable": {"session": memory_session, "trace_id": trace_id or ""}},
                )
                await memory_session.commit()
            except Exception:
                await memory_session.rollback()

    task = asyncio.create_task(run_memory_write())
    task.add_done_callback(_consume_background_task_exception)
    return task


def _consume_background_task_exception(task: asyncio.Task) -> None:
    with contextlib.suppress(asyncio.CancelledError, Exception):
        task.result()


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return {}
