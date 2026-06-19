from __future__ import annotations

import inspect
from typing import Any

import pytest


def _load_budget_config():
    from src.knowledge.config import (
        QUERY_REWRITE_CONFIG_VERSION,
        RERANK_PROVIDER_ENABLED,
        RERANK_PROVIDER_MAX_RETRIES,
        RERANK_STAGE_TIMEOUT_SECONDS,
        RETRIEVAL_DIAGNOSTICS_VERSION,
        RETRIEVAL_TOTAL_TIMEOUT_SECONDS,
        REWRITE_STAGE_TIMEOUT_SECONDS,
    )

    return {
        "QUERY_REWRITE_CONFIG_VERSION": QUERY_REWRITE_CONFIG_VERSION,
        "RETRIEVAL_DIAGNOSTICS_VERSION": RETRIEVAL_DIAGNOSTICS_VERSION,
        "REWRITE_STAGE_TIMEOUT_SECONDS": REWRITE_STAGE_TIMEOUT_SECONDS,
        "RERANK_STAGE_TIMEOUT_SECONDS": RERANK_STAGE_TIMEOUT_SECONDS,
        "RETRIEVAL_TOTAL_TIMEOUT_SECONDS": RETRIEVAL_TOTAL_TIMEOUT_SECONDS,
        "RERANK_PROVIDER_ENABLED": RERANK_PROVIDER_ENABLED,
        "RERANK_PROVIDER_MAX_RETRIES": RERANK_PROVIDER_MAX_RETRIES,
    }


def _load_rerank_api():
    from src.knowledge.rerank import RerankCandidate, RerankConfig, RerankerProviderAdapter, rerank_candidates_for_query

    return RerankCandidate, RerankConfig, RerankerProviderAdapter, rerank_candidates_for_query


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def test_rewrite_rerank_budget_constants_are_versioned() -> None:
    config = _load_budget_config()

    assert config["QUERY_REWRITE_CONFIG_VERSION"].startswith("query_rewrite.")
    assert config["RETRIEVAL_DIAGNOSTICS_VERSION"].startswith("retrieval_diagnostics.")
    assert 0 < config["REWRITE_STAGE_TIMEOUT_SECONDS"] < config["RETRIEVAL_TOTAL_TIMEOUT_SECONDS"]
    assert 0 < config["RERANK_STAGE_TIMEOUT_SECONDS"] < config["RETRIEVAL_TOTAL_TIMEOUT_SECONDS"]
    assert config["RETRIEVAL_TOTAL_TIMEOUT_SECONDS"] <= 15.0
    assert config["RERANK_PROVIDER_ENABLED"] is False
    assert 0 <= config["RERANK_PROVIDER_MAX_RETRIES"] <= 2


@pytest.mark.asyncio
async def test_stage_timeout_provider_error_malformed_budget_disabled_fallbacks() -> None:
    config_constants = _load_budget_config()
    RerankCandidate, RerankConfig, RerankerProviderAdapter, rerank_candidates_for_query = _load_rerank_api()
    candidates = [
        RerankCandidate(
            doc_key="refund_policy",
            chunk_id="refund_policy_001",
            title="退款规则",
            section="仅退款已发货",
            policy_version="v1",
            text="商家已经发货时，客服应先核实物流状态和商家举证。",
            score=0.72,
            rank=1,
            selected_by=("dense", "sparse"),
        )
    ]

    class TimeoutProvider(RerankerProviderAdapter):
        async def rerank(self, **_kwargs):
            raise TimeoutError("provider timeout")

    class ErrorProvider(RerankerProviderAdapter):
        async def rerank(self, **_kwargs):
            raise RuntimeError("provider error")

    class MalformedProvider(RerankerProviderAdapter):
        async def rerank(self, **_kwargs):
            return [{"chunk_id": "refund_policy_001"}]

    scenarios = [
        (None, "provider_disabled", {"provider_enabled": config_constants["RERANK_PROVIDER_ENABLED"]}),
        (
            TimeoutProvider(),
            "provider_timeout",
            {"provider_enabled": True, "provider_timeout_seconds": config_constants["RERANK_STAGE_TIMEOUT_SECONDS"]},
        ),
        (ErrorProvider(), "provider_error", {"provider_enabled": True}),
        (MalformedProvider(), "provider_malformed_output", {"provider_enabled": True}),
        (MalformedProvider(), "budget_overflow", {"provider_enabled": True, "max_candidate_text_chars": 8}),
    ]

    for provider, expected_reason, overrides in scenarios:
        ranked = await _maybe_await(
            rerank_candidates_for_query(
                query="商家已发货还能仅退款吗？",
                candidates=candidates,
                config=RerankConfig(
                    max_provider_retries=config_constants["RERANK_PROVIDER_MAX_RETRIES"],
                    **overrides,
                ),
                provider=provider,
            )
        )

        assert [candidate.chunk_id for candidate in ranked] == ["refund_policy_001"]
        assert ranked[0].fallback_reason == expected_reason
