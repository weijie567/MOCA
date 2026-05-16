from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.prompts import EXTRACT_SLOTS_SYSTEM
from src.agent.schemas import SlotExtractionResult
from src.agent.state import AgentState
from src.config import settings


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        openai_api_key=settings.dashscope_api_key,
        openai_api_base=settings.embedding_base_url,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )


def _trace_step(
    node: str,
    status: str,
    started_at: str,
    provider_latency_ms: int | None,
    retry_count: int,
    context_chars: int,
) -> dict[str, Any]:
    return {
        "node": node,
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "model_name": settings.llm_model,
        "prompt_tokens": None,
        "completion_tokens": None,
        "provider_latency_ms": provider_latency_ms,
        "retry_count": retry_count,
        "metrics_json": {
            "model": settings.llm_model,
            "provider": "dashscope",
            "context_chars": context_chars,
        },
    }


async def extract_slots(state: AgentState) -> dict:
    started_at = _now_iso()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": EXTRACT_SLOTS_SYSTEM},
        {"role": "user", "content": state.get("normalized_query") or state.get("user_query") or ""},
    ]
    structured_llm = _get_llm().with_structured_output(SlotExtractionResult)
    last_error: str | None = None
    provider_latency_ms: int | None = None
    retry_count = 0

    # retry_count records this node's manual structured-output retry loop, not LangGraph node retries.
    for attempt in range(2):
        retry_count = attempt
        try:
            t0 = time.perf_counter()
            result = await structured_llm.ainvoke(messages)
            provider_latency_ms = round((time.perf_counter() - t0) * 1000)
            extracted = result.model_dump()
            new_slots = {key: value for key, value in extracted.items() if value is not None}
            merged = {**(state.get("active_slots") or {}), **new_slots}
            outputs = {**(state.get("llm_outputs") or {}), "extract_slots": extracted}
            return {
                "extracted_slots": extracted,
                "active_slots": merged,
                "llm_outputs": outputs,
                "trace_steps": (state.get("trace_steps") or [])
                + [
                    _trace_step(
                        "extract_slots",
                        "completed",
                        started_at,
                        provider_latency_ms,
                        retry_count,
                        len(str(messages)),
                    )
                ],
            }
        except (ValidationError, ValueError, TimeoutError, Exception) as exc:
            provider_latency_ms = round((time.perf_counter() - t0) * 1000)
            last_error = str(exc)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Validation failed: {last_error}. Respond with valid JSON.",
                    }
                )

    return {
        "extracted_slots": {},
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "extract_slots", "error": last_error, "retry_count": 2}],
        "trace_steps": (state.get("trace_steps") or [])
        + [
            _trace_step(
                "extract_slots",
                "error",
                started_at,
                provider_latency_ms,
                retry_count,
                len(str(messages)),
            )
        ],
    }
