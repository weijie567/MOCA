from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from src.agent.nodes.generate_recommendation import _CANONICAL_NODE, _generate_recommendation_with_identity
from src.agent.state import AgentState


async def recommendation_generation(state: AgentState, config: RunnableConfig = None) -> dict:
    """Canonical recommendation generation graph node.

    The legacy `generate_recommendation` callable remains importable for
    compatibility; this callable owns current canonical trace/output identity.
    """
    return await _generate_recommendation_with_identity(
        state,
        config,
        output_key=_CANONICAL_NODE,
        trace_node=_CANONICAL_NODE,
    )
