from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.prompts import CLASSIFY_INTENT_SYSTEM
from src.agent.schemas import IntentResult
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


def _trace_step(node: str, status: str, started_at: str) -> dict[str, Any]:
    return {
        "node": node,
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "model_name": settings.llm_model,
        "prompt_tokens": None,
        "completion_tokens": None,
    }


async def classify_intent(state: AgentState) -> dict:
    started_at = _now_iso()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": CLASSIFY_INTENT_SYSTEM},
        {"role": "user", "content": state.get("user_query") or ""},
    ]
    structured_llm = _get_llm().with_structured_output(IntentResult)
    last_error: str | None = None

    for attempt in range(2):
        try:
            result = await structured_llm.ainvoke(messages)
            outputs = {**(state.get("llm_outputs") or {}), "classify_intent": result.model_dump()}
            return {
                "current_intent": result.intent,
                "last_intent": result.intent,
                "llm_outputs": outputs,
                "trace_steps": (state.get("trace_steps") or []) + [_trace_step("classify_intent", "completed", started_at)],
            }
        except (ValidationError, ValueError) as exc:
            last_error = str(exc)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Validation failed: {last_error}. Respond with valid JSON.",
                    }
                )

    return {
        "current_intent": "unknown",
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "classify_intent", "error": last_error, "retry_count": 2}],
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("classify_intent", "error", started_at)],
    }
