from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest


RAW_SEMANTIC_PROMPT = "RAW_SEMANTIC_PROMPT_SHOULD_NOT_LEAK"
PRIVATE_REASONING = "PRIVATE_CHAIN_OF_THOUGHT_SHOULD_NOT_LEAK"


def _load_semantic_api():
    from src.agent.rag_context.verifier import (
        SemanticSupportVerifier,
        SemanticVerificationOutcome,
        SemanticVerifierConfig,
        should_run_level3_semantic_verification,
    )

    return (
        SemanticSupportVerifier,
        SemanticVerificationOutcome,
        SemanticVerifierConfig,
        should_run_level3_semantic_verification,
    )


def _value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


class FakeSemanticProvider:
    def __init__(
        self,
        response: dict[str, Any] | None = None,
        *,
        exc: Exception | None = None,
        delay_seconds: float = 0,
    ) -> None:
        self.response = response
        self.exc = exc
        self.delay_seconds = delay_seconds
        self.requests: list[Any] = []

    async def verify(self, request: Any) -> dict[str, Any]:
        self.requests.append(request)
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.exc is not None:
            raise self.exc
        return self.response or {
            "outcome": "supported",
            "confidence": 0.92,
            "reason_codes": ["fake_supported"],
        }


def _claim(claim_id: str = "claim-1", **overrides: Any) -> dict[str, Any]:
    payload = {
        "claim_id": claim_id,
        "claim_text": "Delivered order compensation requires verified policy and order support.",
        "authority_class": "policy_claim",
        "risk_level": "low",
        "risk_hints": [],
        "level2_outcome": "supported",
        "evidence_snippets": [
            {
                "citation_id": "C1",
                "evidence_id": "policy_refund_timeout/chunk_001@v3",
                "text": "Delivered order compensation requires verified policy and order support.",
            }
        ],
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        (_claim(risk_level="low", authority_class="policy_claim", level2_outcome="supported"), False),
        (_claim(risk_level="high"), True),
        (_claim(authority_class="action_recommendation_claim"), True),
        (_claim(risk_hints=["conflict"]), True),
        (_claim(risk_hints=["stale_evidence"]), True),
        (_claim(risk_hints=["ocr_low_confidence"]), True),
        (_claim(level2_outcome="ambiguous"), True),
        (_claim(risk_hints=["manual_review_sensitive"]), True),
    ],
)
def test_level3_triggers_only_for_configured_risk_cases(case: dict[str, Any], expected: bool) -> None:
    """VER-04: Level 3 semantic support is conditional, not always-on."""
    (
        _SemanticSupportVerifier,
        _SemanticVerificationOutcome,
        _SemanticVerifierConfig,
        should_run_level3_semantic_verification,
    ) = _load_semantic_api()

    assert should_run_level3_semantic_verification(case) is expected


def test_default_semantic_verifier_budgets_are_explicit_and_versioned() -> None:
    """VER-05: default Level 3 budgets are pinned and config-versioned."""
    _SemanticSupportVerifier, _SemanticVerificationOutcome, SemanticVerifierConfig, _trigger = _load_semantic_api()

    config = SemanticVerifierConfig()

    assert config.max_claims_per_run == 6
    assert config.max_evidence_snippets_per_claim == 3
    assert config.max_input_chars_per_run == 12_000
    assert config.timeout_seconds == 15
    assert config.provider_retries == 0
    assert config.config_version == "semantic_verifier.v1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "expected_reason"),
    [
        (FakeSemanticProvider(delay_seconds=0.05), "semantic_provider_timeout"),
        (FakeSemanticProvider(exc=RuntimeError("provider unavailable")), "semantic_provider_error"),
        (FakeSemanticProvider(response={"private_reasoning": PRIVATE_REASONING}), "semantic_provider_malformed"),
    ],
)
async def test_semantic_provider_timeout_error_and_malformed_output_fail_closed(
    provider: FakeSemanticProvider,
    expected_reason: str,
) -> None:
    """VER-05: timeout, provider error, and malformed output return non-allow outcomes."""
    SemanticSupportVerifier, SemanticVerificationOutcome, SemanticVerifierConfig, _trigger = _load_semantic_api()
    verifier = SemanticSupportVerifier(
        provider=provider,
        config=SemanticVerifierConfig(timeout_seconds=0.01, provider_retries=0),
    )

    result = await verifier.verify_claims(
        [_claim(risk_level="high")],
        context_bundle={
            "verifier_context": {
                "safe_refs": ["policy_refund_timeout/chunk_001@v3"],
                "raw_prompt": RAW_SEMANTIC_PROMPT,
            }
        },
    )

    safe_json = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

    assert _value(result.outcome) == SemanticVerificationOutcome.FAIL_CLOSED.value
    assert result.allows_claims is False
    assert expected_reason in result.reason_codes
    assert result.provider_retries_attempted == 0
    assert RAW_SEMANTIC_PROMPT not in safe_json
    assert PRIVATE_REASONING not in safe_json


@pytest.mark.asyncio
async def test_semantic_budget_overflow_fails_closed_without_calling_provider() -> None:
    """VER-05: budget overflow is fail-closed and does not call the semantic provider."""
    SemanticSupportVerifier, SemanticVerificationOutcome, SemanticVerifierConfig, _trigger = _load_semantic_api()
    provider = FakeSemanticProvider()
    verifier = SemanticSupportVerifier(provider=provider, config=SemanticVerifierConfig(max_claims_per_run=6))
    claims = [_claim(claim_id=f"claim-{index}", risk_level="high") for index in range(1, 8)]

    result = await verifier.verify_claims(claims, context_bundle={"verifier_context": {}})

    assert _value(result.outcome) == SemanticVerificationOutcome.FAIL_CLOSED.value
    assert result.allows_claims is False
    assert "semantic_budget_claim_count_exceeded" in result.reason_codes
    assert provider.requests == []
