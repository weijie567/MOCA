from __future__ import annotations

from typing import Any

from src.agent.rag_context import metrics as metrics_module


def _case_with_risk_hints(risk_hints: list[str]) -> dict[str, Any]:
    return {
        "input": {
            "claims": [
                {
                    "claim_id": "claim-1",
                    "risk_hints": risk_hints,
                }
            ]
        }
    }


def test_manual_review_sensitive_counts_as_level3_trigger() -> None:
    assert metrics_module._level3_triggered(_case_with_risk_hints(["manual_review_sensitive"]), "supported")


def test_metric_level3_trigger_markers_preserve_existing_semantics() -> None:
    assert metrics_module._level3_triggered(_case_with_risk_hints(["high_risk"]), "supported")
    assert metrics_module._level3_triggered(_case_with_risk_hints(["semantic_timeout"]), "supported")
    assert metrics_module._level3_triggered(_case_with_risk_hints(["semantic_provider_error"]), "supported")
    assert metrics_module._level3_triggered(_case_with_risk_hints(["semantic_malformed_output"]), "supported")
    assert not metrics_module._level3_triggered(_case_with_risk_hints(["authority_checked"]), "supported")
