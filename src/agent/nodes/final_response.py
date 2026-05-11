from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.prompts import FINAL_RESPONSE_SYSTEM, INSUFFICIENT_EVIDENCE_RESPONSE
from src.agent.schemas import FinalResponseOutput
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


def _trace_step(status: str, started_at: str) -> dict[str, Any]:
    return {
        "node": "final_response",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "model_name": settings.llm_model,
        "prompt_tokens": None,
        "completion_tokens": None,
    }


def _insufficient_response(draft: dict[str, Any]) -> str:
    missing_info = draft.get("missing_info") or []
    if not missing_info:
        return INSUFFICIENT_EVIDENCE_RESPONSE
    return f"{INSUFFICIENT_EVIDENCE_RESPONSE}\n缺少信息：{'、'.join(str(item) for item in missing_info)}"


def _retrieval_error_response(draft: dict[str, Any]) -> str:
    missing_info = draft.get("missing_info") or []
    suffix = f"原因：{'、'.join(str(item) for item in missing_info)}" if missing_info else ""
    return f"系统暂时无法检索政策依据，请稍后重试或联系人工客服。{suffix}"


async def final_response(state: AgentState) -> dict:
    started_at = _now_iso()
    draft = state.get("recommendation_draft") or {}
    if draft.get("recommended_action") == "retrieval_error":
        return {
            "final_response": _retrieval_error_response(draft),
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }
    if draft.get("recommended_action") in {"insufficient_evidence", "citation_invalid"}:
        return {
            "final_response": _insufficient_response(draft),
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
        }

    messages: list[dict[str, str]] = [
        {"role": "system", "content": FINAL_RESPONSE_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Recommendation draft: {draft}\n"
                f"Risk assessment: {state.get('risk_assessment') or {}}\n"
                f"User query: {state.get('user_query') or ''}"
            ),
        },
    ]
    structured_llm = _get_llm().with_structured_output(FinalResponseOutput)
    last_error: str | None = None

    for attempt in range(2):
        try:
            result = await structured_llm.ainvoke(messages)
            outputs = {**(state.get("llm_outputs") or {}), "final_response": result.model_dump()}
            return {
                "final_response": result.response_text,
                "llm_outputs": outputs,
                "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
            }
        except (ValidationError, ValueError, TimeoutError, Exception) as exc:
            last_error = str(exc)
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Validation failed: {last_error}. Respond with valid JSON.",
                    }
                )

    return {
        "final_response": "系统处理出现问题，请稍后重试或联系人工客服。",
        "node_errors": (state.get("node_errors") or [])
        + [{"node": "final_response", "error": last_error, "retry_count": 2}],
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
    }
