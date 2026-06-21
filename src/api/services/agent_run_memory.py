from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.nodes.memory_write import memory_write
from src.conversation.repository import ConversationRepository
from src.conversation.service import ConversationService
from src.db.models import AgentRun, User
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
    trace_steps: list[dict[str, Any]]


@dataclass(frozen=True)
class TerminalMemoryWriteExecution:
    result: dict[str, Any]
    duration_ms: int


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
    if final_status != "completed" or not _has_final_response(final_response):
        return AgentRunMemoryFinalizeResult(
            status="skipped",
            assistant_message_id=None,
            thread_summary_id=None,
            memory_write_status="skipped",
            memory_write_result={"status": "skipped", "reason_code": "not_completed_path"},
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
    trace_step = _trace_step(
        started_at=started_at,
        assistant_message_id=str(assistant_message.message_id),
        thread_summary_id=str(thread_summary.id) if thread_summary is not None else None,
        memory_write_status=memory_write_status,
        memory_write_result=memory_write_result,
        memory_write_duration_ms=memory_write_execution.duration_ms,
    )
    return AgentRunMemoryFinalizeResult(
        status="completed" if memory_write_status == "completed" else memory_write_status,
        assistant_message_id=str(assistant_message.message_id),
        thread_summary_id=str(thread_summary.id) if thread_summary is not None else None,
        memory_write_status=memory_write_status,
        memory_write_result=memory_write_result,
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


def _trace_step(
    *,
    started_at: str,
    assistant_message_id: str,
    thread_summary_id: str | None,
    memory_write_status: str,
    memory_write_result: dict[str, Any],
    memory_write_duration_ms: int,
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
        },
    }


def _has_final_response(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _duration_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))
