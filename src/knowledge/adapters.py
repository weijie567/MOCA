from __future__ import annotations

from typing import Any

from src.knowledge.retrieval import PolicyRetrievalEngine

__all__ = ["LegacyRagKnowledgeAdapter", "legacy_search_policy"]


class LegacyRagKnowledgeAdapter(PolicyRetrievalEngine):
    """Compatibility alias for the knowledge-owned retrieval engine."""


async def legacy_search_policy(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Compatibility wrapper for the old agent tool entrypoint."""

    from src.agent.tools.search_policy import search_policy

    return await search_policy(*args, **kwargs)
