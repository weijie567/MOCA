from __future__ import annotations

from src.knowledge.retrieval import PolicyRetrievalEngine

__all__ = ["LegacyRagKnowledgeAdapter"]


class LegacyRagKnowledgeAdapter(PolicyRetrievalEngine):
    """Compatibility alias for the knowledge-owned retrieval engine."""
