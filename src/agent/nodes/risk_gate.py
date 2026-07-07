from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from src.agent.nodes import assess_risk_and_approval as _risk_impl
from src.agent.state import AgentState

_CANONICAL_NODE = "risk_gate"


def _get_llm():
    return _risk_impl._get_llm()


async def persist_action_safety_snapshot(*args, **kwargs):
    return await _risk_impl.persist_action_safety_snapshot(*args, **kwargs)


async def risk_gate(state: AgentState, config: RunnableConfig = None) -> dict:
    """Canonical risk/action graph node.

    The legacy `assess_risk_and_approval` callable remains importable for
    compatibility; this callable owns current canonical trace/output identity.
    """
    return await _risk_impl._assess_risk_and_approval_with_identity(
        state,
        config,
        output_key=_CANONICAL_NODE,
        trace_node=_CANONICAL_NODE,
        get_llm=_get_llm,
        persist_snapshot=persist_action_safety_snapshot,
    )
