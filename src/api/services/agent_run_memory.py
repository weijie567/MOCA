from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.memory_write import memory_write
from src.agent.routing import project_run_terminal
from src.agent.trace import append_agent_steps
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.db.models import AgentRun, AgentStep, User
from src.memory.case_working_context_lifecycle import (
    CaseWorkingContextLifecycleAdapter,
    CaseWorkingContextLifecycleResult,
)
from src.memory.write_isolation import run_memory_side_effect_in_isolated_session
from src.memory.thread_summary import ThreadRollingSummaryService


FINALIZER_NODE = "agent_run_memory_finalize"
FINALIZER_SOURCE = "agent_runs.finalizer"
_SUCCESS_MEMORY_STATUSES = {"completed", "written", "merged_after_conflict"}
_SKIPPED_MEMORY_STATUSES = {"disabled", "skipped"}
_FAILED_MEMORY_STATUSES = {"failed", "fallback", "conflict"}


@dataclass(frozen=True)
class AgentRunMemoryFinalizeResult:
    status: str
    assistant_message_id: str | None
    thread_summary_id: str | None
    memory_write_status: str
    memory_write_result: dict[str, Any]
    case_working_context_status: str
    case_working_context_result: dict[str, Any]
    trace_steps: list[dict[str, Any]]


@dataclass(frozen=True)
class TerminalMemoryWriteExecution:
    result: dict[str, Any]
    duration_ms: int


@dataclass(frozen=True)
class TerminalCaseWorkingContextWriteExecution:
    result: dict[str, Any]
    duration_ms: int


def build_agent_run_finalizer_input_state(run: AgentRun, user: User) -> dict[str, Any]:
    return {
        "user_query": run.input_query,
        "thread_id": run.thread_id,
        "tenant_id": str(run.tenant_id),
        "user_id": str(user.id),
        "role": user.role,
        "current_run_id": str(run.id),
    }


async def persist_agent_run_memory_finalize_trace_steps(
    *,
    session: AsyncSession,
    run: AgentRun,
    prior_trace_steps: list[dict[str, Any]],
    finalizer_trace_steps: list[dict[str, Any]],
    suppress_errors: bool = True,
) -> None:
    if not finalizer_trace_steps:
        return

    existing_finalizer_step_id = (
        await session.execute(
            select(AgentStep.id)
            .where(
                AgentStep.run_id == run.id,
                AgentStep.node_name == FINALIZER_NODE,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing_finalizer_step_id is not None:
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
        if not suppress_errors:
            raise


async def finalize_completed_agent_run_memory(
    *,
    session: AsyncSession,
    run: AgentRun,
    user: User,
    input_state: dict[str, Any],
    final_state: dict[str, Any],
    final_status: str,
    final_response: str | None,
    trace_steps: list[dict[str, Any]],
    trace_id: str | None = None,
    conversation_service: ConversationService | None = None,
) -> AgentRunMemoryFinalizeResult:
    started_at = _now_iso()
    run_terminal = project_run_terminal(final_state)
    terminal_blocked = run_terminal.applies and not run_terminal.memory_eligible
    if final_status != "completed" or not _has_final_response(final_response) or terminal_blocked:
        if run_terminal.status == "error":
            reason_code = "action_terminal_failed"
        elif run_terminal.status in {"manual_review", "refused"}:
            reason_code = f"{run_terminal.status}_terminal"
        else:
            reason_code = "not_completed_path"
        return AgentRunMemoryFinalizeResult(
            status="skipped",
            assistant_message_id=None,
            thread_summary_id=None,
            memory_write_status="skipped",
            memory_write_result={"status": "skipped", "reason_code": reason_code},
            case_working_context_status="skipped",
            case_working_context_result={"status": "skipped", "reason_code": reason_code},
            trace_steps=[],
        )

    conversation_repository = _conversation_repository(session, conversation_service)
    conversation_service = conversation_service or ConversationService(conversation_repository)
    assistant_message = await conversation_service.append_or_get_assistant_message_for_run(
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        thread_id=run.thread_id,
        run_id=run.id,
        content=str(final_response),
        trace_id=trace_id,
        metadata_json={"status": "completed", "source": FINALIZER_SOURCE},
    )
    thread_summary = await ThreadRollingSummaryService(conversation_repository).persist_thread_summary(
        tenant_id=run.tenant_id,
        user_id=run.user_id,
        thread_id=run.thread_id,
        run_id=run.id,
    )
    await session.commit()
    memory_write_execution = await _run_terminal_memory_write(
        session=session,
        run=run,
        user=user,
        input_state=input_state,
        final_state=final_state,
        final_response=str(final_response),
        trace_steps=trace_steps,
        trace_id=trace_id,
    )
    memory_write_result = memory_write_execution.result
    memory_write_status = _canonical_memory_write_status(memory_write_result)
    case_working_context_execution = await _run_terminal_case_working_context_write(
        session=session,
        run=run,
        user=user,
        final_state=final_state,
        final_response=str(final_response),
    )
    case_working_context_result = case_working_context_execution.result
    case_working_context_status = _canonical_case_working_context_status(case_working_context_result)
    trace_step = _trace_step(
        started_at=started_at,
        assistant_message_id=str(assistant_message.message_id),
        thread_summary_id=str(thread_summary.id) if thread_summary is not None else None,
        memory_write_status=memory_write_status,
        memory_write_result=memory_write_result,
        memory_write_duration_ms=memory_write_execution.duration_ms,
        case_working_context_status=case_working_context_status,
        case_working_context_result=case_working_context_result,
        case_working_context_duration_ms=case_working_context_execution.duration_ms,
    )
    return AgentRunMemoryFinalizeResult(
        status="completed" if memory_write_status == "completed" else memory_write_status,
        assistant_message_id=str(assistant_message.message_id),
        thread_summary_id=str(thread_summary.id) if thread_summary is not None else None,
        memory_write_status=memory_write_status,
        memory_write_result=memory_write_result,
        case_working_context_status=case_working_context_status,
        case_working_context_result=case_working_context_result,
        trace_steps=[trace_step],
    )


def _conversation_repository(
    session: AsyncSession,
    conversation_service: ConversationService | None,
) -> ConversationRepository:
    repository = getattr(conversation_service, "repository", None)
    if repository is not None:
        return repository
    return ConversationRepository(session)


async def _run_terminal_memory_write(
    *,
    session: AsyncSession,
    run: AgentRun,
    user: User,
    input_state: dict[str, Any],
    final_state: dict[str, Any],
    final_response: str,
    trace_steps: list[dict[str, Any]],
    trace_id: str | None,
) -> TerminalMemoryWriteExecution:
    started = perf_counter()
    memory_state = _memory_state(
        run=run,
        user=user,
        input_state=input_state,
        final_state=final_state,
        final_response=final_response,
        trace_steps=trace_steps,
    )
    memory_state = _terminal_memory_write_state(memory_state)
    try:
        result_state = await run_memory_side_effect_in_isolated_session(
            session,
            lambda memory_session: memory_write(
                memory_state,
                {"configurable": {"session": memory_session, "trace_id": trace_id or ""}},
            ),
        )
    except TimeoutError:
        return TerminalMemoryWriteExecution(
            result={"status": "skipped", "reason_code": "write_timeout"},
            duration_ms=_duration_ms(started),
        )
    except Exception as exc:
        return TerminalMemoryWriteExecution(
            result={"status": "error", "reason_code": "write_failed", "error_type": type(exc).__name__},
            duration_ms=_duration_ms(started),
        )

    result = result_state.get("memory_write_result") if isinstance(result_state, dict) else None
    if isinstance(result, dict):
        return TerminalMemoryWriteExecution(result=dict(result), duration_ms=_duration_ms(started))
    return TerminalMemoryWriteExecution(
        result={"status": "failed", "reason_code": "missing_memory_write_result"},
        duration_ms=_duration_ms(started),
    )


async def _run_terminal_case_working_context_write(
    *,
    session: AsyncSession,
    run: AgentRun,
    user: User,
    final_state: dict[str, Any],
    final_response: str,
) -> TerminalCaseWorkingContextWriteExecution:
    started = perf_counter()
    try:
        lifecycle_result = await CaseWorkingContextLifecycleAdapter().write_after_terminal_success(
            session=session,
            tenant_id=run.tenant_id,
            user_id=user.id,
            thread_id=run.thread_id,
            run_id=run.id,
            final_state=final_state,
            final_response=final_response,
        )
    except TimeoutError:
        return TerminalCaseWorkingContextWriteExecution(
            result={
                "status": "error",
                "reason_code": "case_working_context_write_timeout",
                "error_type": "TimeoutError",
            },
            duration_ms=_duration_ms(started),
        )
    except Exception as exc:
        return TerminalCaseWorkingContextWriteExecution(
            result={
                "status": "error",
                "reason_code": "case_working_context_write_failed",
                "error_type": type(exc).__name__,
            },
            duration_ms=_duration_ms(started),
        )

    return TerminalCaseWorkingContextWriteExecution(
        result=_case_working_context_result_dict(lifecycle_result),
        duration_ms=_duration_ms(started),
    )


def _case_working_context_result_dict(result: CaseWorkingContextLifecycleResult) -> dict[str, Any]:
    if result.write_result is not None:
        return dict(result.write_result)
    status_ref = result.status_ref
    return {
        "status": status_ref.write_status or status_ref.status,
        "reason_code": status_ref.reason_code,
        "memory_id": None,
        "version": None,
    }


def _memory_state(
    *,
    run: AgentRun,
    user: User,
    input_state: dict[str, Any],
    final_state: dict[str, Any],
    final_response: str,
    trace_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    memory_state = {
        **input_state,
        **final_state,
        "final_response": final_response,
    }
    memory_state["tenant_id"] = str(run.tenant_id)
    memory_state["user_id"] = str(user.id)
    memory_state["thread_id"] = run.thread_id
    memory_state["current_run_id"] = str(run.id)
    memory_state["role"] = user.role
    if "trace_steps" not in memory_state:
        memory_state["trace_steps"] = list(trace_steps)
    return memory_state


def _terminal_memory_write_state(memory_state: dict[str, Any]) -> dict[str, Any]:
    terminal_state = dict(memory_state)
    terminal_state.pop("approval_result", None)
    terminal_state.pop("approval_required", None)
    risk_assessment = terminal_state.get("risk_assessment")
    if isinstance(risk_assessment, dict) and risk_assessment.get("approval_required") is True:
        sanitized_risk = dict(risk_assessment)
        sanitized_risk.pop("approval_required", None)
        terminal_state["risk_assessment"] = sanitized_risk
    return terminal_state


def _canonical_memory_write_status(memory_write_result: dict[str, Any]) -> str:
    status = str(memory_write_result.get("status") or "")
    if status in _SUCCESS_MEMORY_STATUSES:
        return "completed"
    if status in _SKIPPED_MEMORY_STATUSES:
        return "skipped"
    if status == "error":
        return "error"
    if status in _FAILED_MEMORY_STATUSES:
        return "failed"
    return "failed"


def _canonical_case_working_context_status(case_working_context_result: dict[str, Any]) -> str:
    status = str(case_working_context_result.get("status") or "")
    if status in {"written", "blocked", "conflict", "skipped", "error"}:
        return status
    return "error"


def _trace_step(
    *,
    started_at: str,
    assistant_message_id: str,
    thread_summary_id: str | None,
    memory_write_status: str,
    memory_write_result: dict[str, Any],
    memory_write_duration_ms: int,
    case_working_context_status: str,
    case_working_context_result: dict[str, Any],
    case_working_context_duration_ms: int,
) -> dict[str, Any]:
    return {
        "node": FINALIZER_NODE,
        "status": memory_write_status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": {
            "assistant_message_id": assistant_message_id,
            "thread_summary_id": thread_summary_id,
            "memory_write_status": memory_write_status,
            "memory_write_reason_code": memory_write_result.get("reason_code"),
            "memory_write_duration_ms": memory_write_duration_ms,
            "slot_count": memory_write_result.get("slot_count"),
            "fallback_reason": memory_write_result.get("fallback_reason"),
            "pii_decision": memory_write_result.get("decision"),
            "pii_classification": memory_write_result.get("pii_classification"),
            "case_working_context_status": case_working_context_status,
            "case_working_context_reason_code": case_working_context_result.get("reason_code"),
            "case_working_context_memory_id": case_working_context_result.get("memory_id"),
            "case_working_context_version": case_working_context_result.get("version"),
            "case_working_context_duration_ms": case_working_context_duration_ms,
        },
    }


def _has_final_response(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _duration_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))
