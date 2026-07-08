from __future__ import annotations

from langchain_core.runnables import RunnableConfig

import src.agent.nodes.risk_gate as _canonical
from src.agent.state import AgentState


async def assess_risk_and_approval(state: AgentState, config: RunnableConfig = None) -> dict:
    """Legacy import wrapper; canonical implementation lives in risk_gate."""
    return await _canonical.risk_gate(state, config)


def __getattr__(name: str):
    return getattr(_canonical, name)
