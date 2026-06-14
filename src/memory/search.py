from __future__ import annotations

from src.memory.schemas import CaseMemorySearchResult
from src.tools.contracts import ToolCallContext


class CaseMemorySearchService:
    """Searchable case/long-term memory service placeholder."""

    async def search(self, *, query: str, context: ToolCallContext) -> CaseMemorySearchResult:
        del query, context
        return CaseMemorySearchResult(
            status="unavailable",
            items=[],
            summary="Case memory search is not available",
            error_code="TOOL_UNAVAILABLE",
        )
