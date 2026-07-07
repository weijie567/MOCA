from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langchain_core.runnables import RunnableConfig

from src.agent.nodes.memory_context_load import memory_context_load
from src.agent.state import AgentState
from src.memory.case_memory import CaseMemoryRepository, CaseMemoryService
from src.memory.long_term import LongTermMemoryService
from src.memory.repository import LongTermMemoryRepository


async def long_term_memory_retrieve(state: AgentState, config: RunnableConfig) -> dict:
    """Compatibility wrapper for the reviewed memory context boundary."""
    result = await memory_context_load(
        state,
        config,
        long_term_memory_repository_cls=LongTermMemoryRepository,
        case_memory_repository_cls=CaseMemoryRepository,
        long_term_memory_service_cls=LongTermMemoryService,
        case_memory_service_cls=CaseMemoryService,
    )
    legacy_metrics = _legacy_metrics(result)
    result["llm_outputs"] = {
        **(state.get("llm_outputs") or {}),
        **(result.get("llm_outputs") or {}),
        "long_term_memory_retrieve": legacy_metrics,
    }
    return result


def _legacy_metrics(result: Mapping[str, Any]) -> dict[str, Any]:
    long_term_memory = result.get("long_term_memory") if isinstance(result.get("long_term_memory"), list) else []
    case_memory = result.get("case_memory") if isinstance(result.get("case_memory"), list) else []
    status_ref = (
        result.get("reviewed_memory_context_retrieve_status")
        if isinstance(result.get("reviewed_memory_context_retrieve_status"), Mapping)
        else {}
    )
    fallback_reason = status_ref.get("fallback_reason")
    source = _legacy_source(
        long_term_memory=long_term_memory,
        case_memory=case_memory,
        fallback_reason=fallback_reason,
    )
    retrieved = len(long_term_memory) + len(case_memory)
    return {
        "source": source,
        "continuity_claimed": retrieved > 0,
        "retrieved": retrieved,
        "profile_count": len(long_term_memory),
        "case_count": len(case_memory),
        "fallback_reason": fallback_reason,
    }


def _legacy_source(*, long_term_memory: list[Any], case_memory: list[Any], fallback_reason: Any) -> str:
    if long_term_memory or case_memory:
        return "reviewed_memory"
    if fallback_reason in {"service_error", "missing_memory_context_services"}:
        return "reviewed_memory_unavailable"
    return "no_reviewed_memory"
