from __future__ import annotations

from typing import Any

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict


class SpikeState(TypedDict, total=False):
    prompt: str
    approval: dict[str, Any]


async def _interrupt_node(state: SpikeState) -> dict[str, Any]:
    decision = interrupt({"prompt": state["prompt"]})
    return {"approval": decision}


@pytest.mark.asyncio
async def test_interrupt_contract_spike():
    builder = StateGraph(SpikeState)
    builder.add_node("approval_gate", _interrupt_node)
    builder.add_edge(START, "approval_gate")
    builder.add_edge("approval_gate", END)
    graph = builder.compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "interrupt-contract-spike"}}

    interrupted = await graph.ainvoke({"prompt": "approve?"}, config)
    assert interrupted["__interrupt__"][0].value == {"prompt": "approve?"}

    resumed = await graph.ainvoke(Command(resume={"decision": "approve"}), config)
    assert resumed["approval"] == {"decision": "approve"}
