from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from src.agent.nodes.assess_risk_and_approval import _assess_risk_and_approval_with_identity
from src.agent.state import AgentState

_CANONICAL_NODE = "risk_gate"


async def risk_gate(state: AgentState, config: RunnableConfig = None) -> dict:
    """Canonical risk/action graph node.

    The legacy `assess_risk_and_approval` callable remains importable for
    compatibility; this callable owns current canonical trace/output identity.
    """
    return await _assess_risk_and_approval_with_identity(
        state,
        config,
        output_key=_CANONICAL_NODE,
        trace_node=_CANONICAL_NODE,
    )
