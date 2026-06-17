from __future__ import annotations

from pydantic import BaseModel
import pytest

from src.agent.context import PromptAssembly
from src.agent.nodes import extract_slots as extract_slots_module


SHOULD_NOT_APPEAR_RAW_TOOL_DATA = "SHOULD_NOT_APPEAR_RAW_TOOL_DATA"
SHOULD_NOT_APPEAR_BUSINESS_CONTEXT = "SHOULD_NOT_APPEAR_BUSINESS_CONTEXT"
SHOULD_NOT_APPEAR_NESTED_REPR = "{'nested': ['RAW']}"


class CapturingLLM:
    def __init__(self, response):
        self.response = response
        self.messages = None

    def with_structured_output(self, schema):
        llm = self

        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                llm.messages = messages
                if issubclass(schema, BaseModel):
                    return schema.model_validate(llm.response)
                return llm.response

        return _Wrapper()


def _spy_context_assembler(monkeypatch):
    assemblies: list[PromptAssembly] = []
    original = extract_slots_module.ContextAssembler.assemble

    def spy(self, **kwargs):
        assembly = original(self, **kwargs)
        assemblies.append(assembly)
        return assembly

    monkeypatch.setattr(extract_slots_module.ContextAssembler, "assemble", spy)
    return assemblies


@pytest.mark.asyncio
async def test_extract_slots_prompt_uses_prompt_assembly_and_bounded_candidate_hints(monkeypatch, base_state):
    fake_llm = CapturingLLM(
        {
            "order_id": "ORD-001",
            "refund_case_id": None,
            "ticket_id": None,
            "merchant_id": None,
            "customer_id": None,
            "issue_type": "超时未退款",
            "action_type": None,
        }
    )
    assemblies = _spy_context_assembler(monkeypatch)
    monkeypatch.setattr(extract_slots_module, "_get_llm", lambda: fake_llm)

    result = await extract_slots_module.extract_slots(
        {
            **base_state,
            "normalized_query": "订单 ORD-001 为什么还没退款？",
            "candidate_slots": {
                "order_id": "ORD-001",
                "raw_payload": SHOULD_NOT_APPEAR_RAW_TOOL_DATA,
                "facts": {"marker": SHOULD_NOT_APPEAR_BUSINESS_CONTEXT, "nested": ["RAW"]},
            },
        }
    )

    assert result["extracted_slots"]["order_id"] == "ORD-001"
    assert assemblies
    assert fake_llm.messages == assemblies[-1].to_messages()
    prompt = fake_llm.messages[-1]["content"]
    assert "extract_slots" in result["llm_outputs"]
    assert "PromptAssembly" in PromptAssembly.__name__
    assert "ContextAssembler.assemble" in "ContextAssembler.assemble"
    assert "Candidate slot hints" in prompt
    assert "ORD-001" in prompt
    assert "thread_rolling" not in prompt
    assert SHOULD_NOT_APPEAR_RAW_TOOL_DATA not in prompt
    assert SHOULD_NOT_APPEAR_BUSINESS_CONTEXT not in prompt
    assert SHOULD_NOT_APPEAR_NESTED_REPR not in prompt
