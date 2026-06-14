from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError

from src.db.models import SessionMemory
from src.memory.repository import SessionMemoryRepository
from src.memory.schemas import CaseMemorySearchItem, CaseMemorySearchResult, SessionSlotsEnvelopeV1
from src.tools.contracts import ToolCallContext


class CaseMemorySearchService:
    def __init__(self, repository: SessionMemoryRepository | None = None, *, enabled: bool = True) -> None:
        self.repository = repository
        self.enabled = enabled

    async def search(
        self,
        *,
        query: str,
        context: ToolCallContext,
        limit: int = 5,
    ) -> CaseMemorySearchResult:
        if not self.enabled or self.repository is None:
            return _unavailable("TOOL_UNAVAILABLE", "Case memory search is not available")
        try:
            tenant_id = UUID(context.tenant_id)
            user_id = UUID(context.user_id)
        except ValueError:
            return _unavailable("INVALID_CONTEXT", "Case memory search context is invalid")

        try:
            memories = await self.repository.search_active(
                tenant_id=tenant_id,
                user_id=user_id,
                query=query,
                limit=limit,
            )
        except Exception:
            return _unavailable("SEARCH_ERROR", "Case memory search failed")

        terms = _query_terms(query)
        items = [_project_memory(memory, terms) for memory in memories]
        return CaseMemorySearchResult(
            status="success",
            items=items,
            summary=f"Found {len(items)} relevant case memory item(s)" if items else "No relevant case memory found",
        )


def _unavailable(error_code: str, summary: str) -> CaseMemorySearchResult:
    return CaseMemorySearchResult(status="unavailable", items=[], summary=summary, error_code=error_code)


def _project_memory(memory: SessionMemory, terms: set[str]) -> CaseMemorySearchItem:
    active_slots = _active_slots(memory)
    unresolved_questions = list(memory.unresolved_questions_json or [])[:5]
    business_refs = dict(memory.last_business_context_refs_json or {})
    searchable_text = json.dumps(
        {
            "active_slots": active_slots,
            "session_summary": memory.session_summary,
            "unresolved_questions": unresolved_questions,
            "last_intent": memory.last_intent,
            "last_business_context_refs": business_refs,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).lower()
    score = float(sum(1 for term in terms if term and term in searchable_text))
    if score == 0.0 and not terms:
        score = 1.0

    return CaseMemorySearchItem(
        memory_id=str(memory.id),
        thread_id=memory.thread_id,
        version=memory.version,
        score=score,
        active_slots=active_slots,
        session_summary=_bounded(memory.session_summary),
        unresolved_questions=unresolved_questions,
        last_intent=memory.last_intent,
        last_business_context_refs=business_refs,
        updated_at=memory.updated_at,
    )


def _active_slots(memory: SessionMemory) -> dict[str, str]:
    try:
        envelope = SessionSlotsEnvelopeV1.model_validate(memory.active_slots_json)
    except ValidationError:
        return {}

    now = datetime.now(UTC)
    slots: dict[str, str] = {}
    for name, slot in envelope.slots.items():
        expires_at = slot.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at > now:
            slots[name] = slot.value
    return slots


def _query_terms(query: str) -> set[str]:
    normalized = query.strip().lower()
    if not normalized:
        return set()
    terms = {term for term in normalized.split() if term}
    if len(normalized) <= 64:
        terms.add(normalized)
    return terms


def _bounded(value: str | None, limit: int = 500) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return f"{value[:limit]}..."
