from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel


class FakeLLM:
    """Deterministic fake LLM for CI. Returns predetermined structured outputs.
    Implements the ChatOpenAI interface used by nodes (ainvoke + with_structured_output).
    Per D-11b: CI must not depend on real LLM API.
    """

    def __init__(self, response_dict: dict[str, Any]):
        """response_dict: maps to a dict that will be returned as structured output."""
        self._response = response_dict

    async def ainvoke(self, messages, **kwargs):
        from langchain_core.messages import AIMessage

        return AIMessage(content=json.dumps(self._response, ensure_ascii=False))

    def with_structured_output(self, schema):
        fake = self

        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                if issubclass(schema, BaseModel):
                    return schema.model_validate(fake._response)
                return fake._response

        return _Wrapper()


@pytest.fixture
def fake_llm_intent():
    return FakeLLM({"intent": "refund_troubleshooting", "confidence": 0.95, "reasoning": "test"})


@pytest.fixture
def fake_llm_slots():
    return FakeLLM(
        {
            "order_id": "ORD-001",
            "refund_case_id": None,
            "ticket_id": None,
            "merchant_id": None,
            "customer_id": None,
            "issue_type": "超时未退款",
        }
    )


@pytest.fixture
def fake_llm_recommendation():
    return FakeLLM(
        {
            "recommended_action": "建议退款",
            "reasoning_summary": "根据规则",
            "evidence_refs": [
                {
                    "doc_key": "policy_refund_timeout",
                    "chunk_id": "chunk_001",
                    "title": "退款超时规则",
                    "section": "第一条",
                }
            ],
            "confidence": 0.85,
            "risk_level": "low",
            "missing_info": [],
        }
    )


@pytest.fixture
def fake_llm_risk():
    return FakeLLM(
        {"risk_level": "low", "risk_reason": "standard refund", "approval_required": False, "rule_ref": "LR-01"}
    )


@pytest.fixture
def fake_llm_final():
    return FakeLLM(
        {
            "response_text": "根据 policy_refund_timeout / chunk_001，建议退款。",
            "evidence_citations": ["根据 policy_refund_timeout / chunk_001"],
            "final_status": "completed",
        }
    )


@pytest.fixture
def base_state():
    return {
        "thread_id": "test-thread",
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "role": "support_agent",
        "user_query": "订单ORD-001为什么还没退款？",
    }
