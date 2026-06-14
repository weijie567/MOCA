from __future__ import annotations

from src.agent.nodes.classify_intent import intent_result_to_state
from src.agent.schemas import IntentResultV3


def test_intent_result_to_state_uses_policy_required_slots_and_forbidden_writes():
    result = IntentResultV3.model_validate(
        {
            "schema_version": "intent_result.v3",
            "primary_intent": "refund_troubleshooting",
            "requested_operation": "advise",
            "confidence": 0.86,
            "calibrated_confidence": 0.81,
            "secondary_intents": ["compensation_suggestion"],
            "required_slots": {
                "all_of": ["forged_slot"],
                "any_of": [["not_runtime"]],
                "optional": ["merchant_id"],
            },
            "candidate_slots": {"order_id": "ORD-1001"},
            "routing_hints": {"needs_business_context": True},
            "classifier_version": "intent_classifier.v2",
            "calibration_version": "calibration.unverified",
            "reason_codes": ["refund_keywords"],
        }
    )

    update = intent_result_to_state(result, prior_llm_outputs={"previous": {"ok": True}})

    assert update["primary_intent"] == "refund_troubleshooting"
    assert update["current_intent"] == "refund_troubleshooting"
    assert update["intent_confidence"] == 0.86
    assert update["required_slots"] == {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []}
    assert update["candidate_slots"] == {"order_id": "ORD-1001"}
    metadata = update["llm_outputs"]["intent_classification"]["eval_metadata"]
    assert metadata["calibrated_confidence"] == 0.81
    assert metadata["llm_required_slots"]["all_of"] == ["forged_slot"]
    forbidden = {
        "approval_result",
        "trusted_approval_result",
        "resume",
        "command",
        "extracted_slots",
        "active_slots",
        "risk_signals",
        "final_response",
        "tool_results",
        "action_result",
        "proposed_action",
    }
    assert forbidden.isdisjoint(update)
