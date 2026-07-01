from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.events import emit_event
from src.agent.state import AgentState
from src.config import settings
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.context_service import MemoryContextService
from src.memory.identity import (
    MemoryIdentityError,
    canonical_memory_candidate_hash,
    canonical_memory_content_hash,
    canonical_source_identity_hash,
)
from src.memory.long_term import LongTermMemoryService
from src.memory.repository import LongTermMemoryRepository, SessionMemoryRepository
from src.memory.schemas import (
    CaseMemoryWriteCandidate,
    LongTermMemoryWriteCandidate,
    SessionMemoryWriteCandidate,
    SessionMemoryWriteResult,
)
from src.memory.service import MemoryService
from src.memory.write_service import MemoryWriteCandidate, MemoryWriteResult, MemoryWriteService


_MEMORY_WRITE_DECISION_SCHEMA_VERSION = "memory_write_decision.v2"
_MEMORY_CONTEXT_SERVICE = MemoryContextService()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def memory_write(state: AgentState, config: RunnableConfig) -> dict:
    started_at = _now_iso()
    final_response = state.get("final_response")
    if not final_response:
        return _skipped(state, started_at, "not_completed_path")
    if _approval_or_interrupted(state):
        return _skipped(state, started_at, "not_completed_path")
    if settings.session_memory_enabled is False:
        return _skipped(state, started_at, "disabled")

    configurable = config.get("configurable") or {}
    session = configurable.get("session")
    if session is None:
        return _skipped(state, started_at, "missing_async_session")
    memory_operation_id = uuid.uuid4()

    try:
        result = await asyncio.wait_for(
            _write_with_service(state, session, configurable, started_at, operation_id=memory_operation_id),
            timeout=settings.session_memory_write_timeout_seconds,
        )
        return result
    except TimeoutError:
        rollback = getattr(session, "rollback", None)
        if callable(rollback):
            await rollback()
        return _skipped(state, started_at, "write_timeout", final_response=final_response)
    except Exception:
        rollback = getattr(session, "rollback", None)
        if callable(rollback):
            await rollback()
        await _emit_memory_event(
            state,
            configurable,
            session,
            "memory_write_failed",
            {"status": "error"},
            operation_id=memory_operation_id,
        )
        return _error(state, started_at, final_response)


async def _write_with_service(
    state: AgentState,
    session: Any,
    configurable: dict[str, Any],
    started_at: str,
    *,
    operation_id: uuid.UUID,
) -> dict:
    write_service = MemoryWriteService(
        MemoryService(SessionMemoryRepository(session), enabled=settings.session_memory_enabled),
        long_term_memory_service=LongTermMemoryService(LongTermMemoryRepository(session)),
        case_memory_service=CaseMemoryService(CaseMemoryRepository(session)),
    )
    candidates = write_service.propose_candidates(state)
    candidate = _session_candidate(candidates)
    if candidate.decision == "skip":
        results = await write_service.apply_policy_and_write_all(candidates)
        result = _session_result(candidates, results)
        return _completed(state, started_at, result, candidate, candidates=candidates, results=results)

    await _emit_memory_event(
        state,
        configurable,
        session,
        "memory_write_started",
        {
            "status": "started",
            "slot_count": len(candidate.explicit_slots),
            "has_unresolved_questions": bool(candidate.unresolved_questions),
        },
        operation_id=operation_id,
    )
    results = await write_service.apply_policy_and_write_all(candidates)
    result = _session_result(candidates, results)
    event_type = "memory_write_completed" if result.status not in {"error", "fallback"} else "memory_write_failed"
    await _emit_memory_event(
        state,
        configurable,
        session,
        event_type,
        {
            "status": result.status,
            "slot_count": len(candidate.explicit_slots),
            "has_unresolved_questions": bool(candidate.unresolved_questions),
            "fallback_reason": result.fallback_reason,
        },
        operation_id=operation_id,
    )
    return _completed(state, started_at, result, candidate, candidates=candidates, results=results)


def _session_candidate(candidates: list[MemoryWriteCandidate]) -> SessionMemoryWriteCandidate:
    for candidate in candidates:
        if isinstance(candidate, SessionMemoryWriteCandidate):
            return candidate
    raise RuntimeError("session memory candidate is required")


def _session_result(
    candidates: list[MemoryWriteCandidate],
    results: list[MemoryWriteResult],
) -> SessionMemoryWriteResult:
    for candidate, result in zip(candidates, results, strict=False):
        if isinstance(candidate, SessionMemoryWriteCandidate) and isinstance(result, SessionMemoryWriteResult):
            return result
    raise RuntimeError("session memory write result is required")


def _completed(
    state: AgentState,
    started_at: str,
    result: SessionMemoryWriteResult,
    candidate: SessionMemoryWriteCandidate,
    *,
    candidates: list[MemoryWriteCandidate] | None = None,
    results: list[MemoryWriteResult] | None = None,
) -> dict:
    result_dict = result.model_dump(mode="json")
    decision = _memory_write_decision(state, result_dict, candidate=candidate)
    output = {
        "final_response": state.get("final_response"),
        "memory_write_candidates": [_candidate_projection(item) for item in (candidates or [candidate])],
        "memory_write_result": result_dict,
        "memory_write_decision": decision,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, result_dict, decision)],
    }
    if results is not None and len(results) > 1:
        output["memory_write_results"] = [item.model_dump(mode="json") for item in results]
    return output


def _skipped(
    state: AgentState,
    started_at: str,
    reason_code: str,
    *,
    final_response: str | None = None,
) -> dict:
    result = {
        "status": "skipped",
        "decision": "skip",
        "reason_code": reason_code,
        "pii_classification": "none",
    }
    if reason_code == "write_timeout":
        result["fallback_reason"] = "write_timeout"
    decision = _memory_write_decision(state, result, fallback_reason=result.get("fallback_reason"))
    return {
        "final_response": final_response if final_response is not None else state.get("final_response"),
        "memory_write_result": result,
        "memory_write_decision": decision,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, result, decision)],
    }


def _error(state: AgentState, started_at: str, final_response: str | None) -> dict:
    result = {
        "status": "error",
        "decision": "skip",
        "reason_code": "write_failed",
        "pii_classification": "none",
    }
    decision = _memory_write_decision(state, result, reason_code_override="write_error")
    return {
        "final_response": final_response,
        "memory_write_result": result,
        "memory_write_decision": decision,
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "memory_write", "error_code": "SESSION_MEMORY_WRITE_FAILED"}],
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, result, decision)],
    }


def _trace_step(started_at: str, result: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "node": "memory_write",
        "status": result.get("status"),
        "started_at": started_at,
        "completed_at": _now_iso(),
        "provider_latency_ms": None,
        "retry_count": 0,
        "metrics_json": {
            "status": result.get("status"),
            "decision": result.get("decision"),
            "reason_code": result.get("reason_code"),
            "fallback_reason": result.get("fallback_reason"),
            "memory_write_decision_schema_version": decision.get("schema_version")
            or _MEMORY_WRITE_DECISION_SCHEMA_VERSION,
        },
    }


def _candidate_projection(candidate: MemoryWriteCandidate) -> dict[str, Any]:
    if isinstance(candidate, LongTermMemoryWriteCandidate):
        return {
            "memory_type": "long_term",
            "scope_type": candidate.scope_type,
            "scope_id": candidate.scope_id,
            "source_type": candidate.source_type,
            "memory_kind": candidate.memory_kind,
            "pii_classification": candidate.pii_classification,
        }
    if isinstance(candidate, CaseMemoryWriteCandidate):
        return {
            "memory_type": "case",
            "scope_type": candidate.scope_type,
            "scope_id": candidate.scope_id,
            "case_type": candidate.case_type,
            "source_type": candidate.source_type,
            "pii_classification": candidate.pii_classification,
        }
    return {
        "memory_type": "session",
        "slot_names": sorted(candidate.explicit_slots),
        "has_unresolved_questions": bool(candidate.unresolved_questions),
        "last_intent": candidate.last_intent,
        "decision": candidate.decision,
        "reason_code": candidate.reason_code,
        "pii_classification": candidate.pii_classification,
    }


def _memory_write_decision(
    state: AgentState,
    result: dict[str, Any],
    *,
    candidate: SessionMemoryWriteCandidate | None = None,
    fallback_reason: str | None = None,
    reason_code_override: str | None = None,
) -> dict[str, Any]:
    projected_result = dict(result)
    if reason_code_override is not None:
        projected_result["reason_code"] = reason_code_override
    if candidate is not None:
        projected_result.update(_session_candidate_identity(candidate))
        memory_id = _session_memory_id(candidate, projected_result)
        if memory_id is not None:
            projected_result["memory_id"] = memory_id
    decision = _MEMORY_CONTEXT_SERVICE.project_memory_write_decision(
        projected_result,
        memory_type="session",
        scope=_session_write_scope(state, candidate),
        fallback_reason=fallback_reason,
    )
    return decision.model_dump(mode="json")


def _session_candidate_identity(candidate: SessionMemoryWriteCandidate) -> dict[str, str | None]:
    try:
        source_identity_hash = canonical_source_identity_hash(
            {"source_type": "agent_run", "agent_run_id": str(candidate.run_id)}
        )
        content_hash = canonical_memory_content_hash(
            memory_type="session",
            content=json.dumps(
                {
                    "explicit_slots": {
                        key: slot.value for key, slot in sorted(candidate.explicit_slots.items())
                    },
                    "last_intent": candidate.last_intent or "",
                    "session_summary": candidate.session_summary or "",
                    "unresolved_questions": [str(question) for question in candidate.unresolved_questions],
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
        return {
            "candidate_hash": canonical_memory_candidate_hash(
                tenant_id=str(candidate.tenant_id),
                memory_type="session",
                scope_type="thread",
                scope_id=candidate.thread_id,
                content_hash=content_hash,
                source_identity_hash=source_identity_hash,
            ),
            "source_identity_hash": source_identity_hash,
        }
    except MemoryIdentityError:
        return {}


def _session_memory_id(candidate: SessionMemoryWriteCandidate, result: dict[str, Any]) -> str | None:
    if result.get("status") not in {"written", "merged_after_conflict"}:
        return None
    version = result.get("version")
    if version is None:
        return None
    return f"session:{candidate.tenant_id}:{candidate.user_id}:{candidate.thread_id}:v{version}"


def _session_write_scope(
    state: AgentState,
    candidate: SessionMemoryWriteCandidate | None,
) -> dict[str, Any]:
    return {
        "scope_type": "thread",
        "tenant_id": str(candidate.tenant_id) if candidate is not None else _optional_state_str(state, "tenant_id"),
        "user_id": str(candidate.user_id) if candidate is not None else _optional_state_str(state, "user_id"),
        "thread_id": candidate.thread_id if candidate is not None else _optional_state_str(state, "thread_id"),
        "run_id": str(candidate.run_id) if candidate is not None else _optional_state_str(state, "current_run_id"),
    }


def _optional_state_str(state: AgentState, key: str) -> str | None:
    value = state.get(key)
    return str(value) if value is not None else None


def _approval_or_interrupted(state: AgentState) -> bool:
    if state.get("approval_result") or state.get("approval_required"):
        return True
    risk = state.get("risk_assessment")
    if isinstance(risk, dict) and risk.get("approval_required") is True:
        return True
    return state.get("final_status") == "interrupted"


async def _emit_memory_event(
    state: AgentState,
    configurable: dict[str, Any],
    session: Any,
    event_type: str,
    payload: dict[str, Any],
    *,
    operation_id: uuid.UUID | None = None,
) -> None:
    run_id = state.get("current_run_id")
    tenant_id = state.get("tenant_id")
    thread_id = state.get("thread_id")
    if not run_id or not tenant_id or not thread_id:
        return
    try:
        await emit_event(
            session,
            run_id=run_id,
            tenant_id=tenant_id,
            thread_id=str(thread_id),
            event_type=event_type,
            actor={"type": "agent", "id": "moca"},
            resource_refs={"memory_type": "session_memory"},
            redacted_payload={key: value for key, value in payload.items() if value is not None},
            trace_id=configurable.get("trace_id"),
            operation_id=operation_id,
        )
    except Exception:
        return
