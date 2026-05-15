from __future__ import annotations

import pytest

from src.agent.nodes.final_response import final_response


@pytest.mark.asyncio
async def test_final_response_uses_deterministic_citation_template(base_state):
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "解释退款超时规则",
            "reasoning_summary": "商家需要在规定时效内处理退款。",
            "evidence_refs": [
                {
                    "doc_key": "refund_policy",
                    "chunk_id": "refund_policy_006",
                    "title": "退款规则",
                    "section": "超时自动退款",
                }
            ],
        },
        "risk_assessment": {
            "risk_level": "low",
            "risk_reason": "Policy explanation only.",
            "approval_required": False,
            "rule_ref": "LR-01",
        },
    }

    result = await final_response(state)

    assert "根据 refund_policy / refund_policy_006" in result["final_response"]
    assert result["llm_outputs"]["final_response"]["final_status"] == "completed"
    assert result["trace_steps"][-1]["model_name"] == "deterministic-template"
