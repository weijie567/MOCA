from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.events import emit_event
from src.agent.state import AgentState
from src.config import settings
from src.memory.repository import SessionMemoryRepository
from src.memory.schemas import SessionMemoryWriteCandidate, SessionMemoryWriteResult, SessionSlotV1
from src.memory.service import MemoryService


_PROHIBITED_PII_MARKERS = {"身份证", "手机号", "password", "secret"}


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

    try:
        result = await asyncio.wait_for(
            _write_with_service(state, session, configurable, started_at),
            timeout=settings.session_memory_write_timeout_seconds,
        )
        return result
    except TimeoutError:
        return _skipped(state, started_at, "write_timeout", final_response=final_response)
    except Exception:
        await _emit_memory_event(state, configurable, session, "memory_write_failed", {"status": "error"})
        return _error(state, started_at, final_response)


async def _write_with_service(
    state: AgentState,
    session: Any,
    configurable: dict[str, Any],
    started_at: str,
) -> dict:
    candidate = _build_candidate(state)
    if candidate.decision == "skip":
        result = SessionMemoryWriteResult(
            status="skipped",
            version=None,
            decision="skip",
            reason_code=candidate.reason_code,
            pii_classification=candidate.pii_classification,
        )
        return _completed(state, started_at, result, candidate)

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
    )
    service = MemoryService(SessionMemoryRepository(session), enabled=settings.session_memory_enabled)
    try:
        result = await service.write_session_memory(candidate)
    except Exception:
        await _emit_memory_event(state, configurable, session, "memory_write_failed", {"status": "error"})
        raise
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
    )
    return _completed(state, started_at, result, candidate)


def _build_candidate(state: AgentState) -> SessionMemoryWriteCandidate:
    now = datetime.now(UTC)
    run_id = uuid.UUID(str(state.get("current_run_id")))
    intent = state.get("primary_intent") or state.get("current_intent")
    explicit_slots = _explicit_slots(state, run_id, intent, now)
    pii_classification = _classify_pii(state, explicit_slots)
    decision = "skip" if pii_classification == "prohibited" else "write"
    reason_code = "pii_blocked" if decision == "skip" else "eligible"
    session_memory = state.get("session_memory") if isinstance(state.get("session_memory"), dict) else {}
    expected_version = session_memory.get("version") if isinstance(session_memory.get("version"), int) else None
    return SessionMemoryWriteCandidate(
        tenant_id=uuid.UUID(str(state["tenant_id"])),
        user_id=uuid.UUID(str(state["user_id"])),
        thread_id=str(state["thread_id"]),
        run_id=run_id,
        explicit_slots=explicit_slots,
        unresolved_questions=_unresolved_questions(state),
        last_intent=str(intent) if intent else None,
        session_summary=_session_summary(intent, explicit_slots),
        last_business_context_refs=_last_business_context_refs(state),
        expected_version=expected_version,
        pii_classification=pii_classification,
        decision=decision,
        reason_code=reason_code,
    )


def _explicit_slots(
    state: AgentState,
    run_id: uuid.UUID,
    intent: str | None,
    now: datetime,
) -> dict[str, SessionSlotV1]:
    extracted = state.get("extracted_slots") if isinstance(state.get("extracted_slots"), dict) else {}
    compatible_intents = [intent] if intent else []
    expires_at = now + timedelta(seconds=settings.session_memory_ttl_seconds)
    slots: dict[str, SessionSlotV1] = {}
    for key, value in extracted.items():
        if value in (None, ""):
            continue
        slots[key] = SessionSlotV1(
            value=str(value),
            source="explicit_user",
            source_run_id=str(run_id),
            updated_at=now,
            expires_at=expires_at,
            compatible_intents=compatible_intents,
        )
    return slots


def _unresolved_questions(state: AgentState) -> list[str]:
    clarification = state.get("clarification_request")
    if not isinstance(clarification, dict):
        return []
    questions = clarification.get("questions")
    if not isinstance(questions, list):
        return []
    return [str(question) for question in questions if question]


def _session_summary(intent: str | None, explicit_slots: dict[str, SessionSlotV1]) -> str | None:
    if not intent and not explicit_slots:
        return None
    slot_names = ",".join(sorted(explicit_slots)) or "none"
    summary = f"Session turn completed; intent={intent or 'unknown'}; explicit_slots={slot_names}."
    return summary[: settings.session_memory_summary_max_chars]


def _last_business_context_refs(state: AgentState) -> dict[str, Any]:
    refs = state.get("last_business_context_refs")
    return dict(refs) if isinstance(refs, dict) else {}


def _classify_pii(state: AgentState, explicit_slots: dict[str, SessionSlotV1]) -> str:
    values = [slot.value for slot in explicit_slots.values()]
    final_response = state.get("final_response")
    if isinstance(final_response, str):
        values.append(final_response)
    text = " ".join(values).lower()
    if any(marker.lower() in text for marker in _PROHIBITED_PII_MARKERS):
        return "prohibited"
    return "none"


def _completed(
    state: AgentState,
    started_at: str,
    result: SessionMemoryWriteResult,
    candidate: SessionMemoryWriteCandidate,
) -> dict:
    result_dict = result.model_dump(mode="json")
    return {
        "final_response": state.get("final_response"),
        "memory_write_candidates": [_candidate_projection(candidate)],
        "memory_write_result": result_dict,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, result_dict)],
    }


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
    return {
        "final_response": final_response if final_response is not None else state.get("final_response"),
        "memory_write_result": result,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, result)],
    }


def _error(state: AgentState, started_at: str, final_response: str | None) -> dict:
    result = {
        "status": "error",
        "decision": "skip",
        "reason_code": "write_failed",
        "pii_classification": "none",
    }
    return {
        "final_response": final_response,
        "memory_write_result": result,
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "memory_write", "error_code": "SESSION_MEMORY_WRITE_FAILED"}],
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step(started_at, result)],
    }


def _trace_step(started_at: str, result: dict[str, Any]) -> dict[str, Any]:
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
        },
    }


def _candidate_projection(candidate: SessionMemoryWriteCandidate) -> dict[str, Any]:
    return {
        "slot_names": sorted(candidate.explicit_slots),
        "has_unresolved_questions": bool(candidate.unresolved_questions),
        "last_intent": candidate.last_intent,
        "decision": candidate.decision,
        "reason_code": candidate.reason_code,
        "pii_classification": candidate.pii_classification,
    }


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
        )
    except Exception:
        return
