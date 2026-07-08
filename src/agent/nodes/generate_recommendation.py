from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import src.agent.nodes.recommendation_generation as _canonical
from src.agent.state import AgentState


async def generate_recommendation(state: AgentState, config: RunnableConfig = None) -> dict:
    """Legacy import wrapper; canonical implementation lives in recommendation_generation."""
    return await _canonical.recommendation_generation(state, config)


def __getattr__(name: str):
    return getattr(_canonical, name)
