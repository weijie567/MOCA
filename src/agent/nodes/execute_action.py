from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from src.agent.nodes.action_draft import action_draft
from src.agent.state import AgentState


async def execute_action(state: AgentState, config: RunnableConfig) -> dict:
    """Phase 14 compatibility shim for legacy execute_action checkpoints.

    Owner: Phase 14 action-draft-boundary.
    Removal gate: Phase 15 Replay Event Contract before Phase 15 verification,
    target no later than 2026-07-16 unless Phase 15 is replanned.
    """

    return await action_draft(state, config)
