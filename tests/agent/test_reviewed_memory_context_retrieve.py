from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from src.platform.trusted_context import MerchantScopeV1, TrustedContext


def _trusted_context(*, merchant_ids: list[str]) -> TrustedContext:
    return TrustedContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        role="support",
        permissions=["tool:get_order", "tool:get_refund_case"],
        merchant_scope=MerchantScopeV1(merchant_ids=merchant_ids),
        thread_id="thread-reviewed-memory-context",
        run_id=str(uuid4()),
        trace_id="trace-reviewed-memory-context",
    )


def _state(**updates: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "thread_id": "thread-reviewed-memory-context",
        "current_run_id": str(uuid4()),
        "primary_intent": "refund_troubleshooting",
        "user_query": "请结合已审核记忆继续处理这个退款问题",
        "extracted_slots": {},
        "active_slots": {},
        "candidate_slots": {},
        "trace_steps": [],
    }
    values.update(updates)
    return values


def _reviewed_memory_context_retrieve() -> Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]:
    from src.agent.nodes.reviewed_memory_context_retrieve import reviewed_memory_context_retrieve

    return reviewed_memory_context_retrieve


def _assert_empty_context_bundle(result: dict[str, Any], *, fallback_reason: str) -> dict[str, Any]:
    memory_context = result["memory_context"]
    assert set(memory_context) == {
        "schema_version",
        "authority_class",
        "long_term_items",
        "case_items",
        "status_ref",
    }
    assert memory_context["schema_version"] == "reviewed_memory_context_bundle.v1"
    assert memory_context["authority_class"] == "contextual_only"
    assert memory_context["long_term_items"] == []
    assert memory_context["case_items"] == []
    assert result["reviewed_memory_context_retrieve_status"] == memory_context["status_ref"]
    assert memory_context["status_ref"]["fallback_reason"] == fallback_reason
    for status_key in ("status", "fallback_reason", "trusted_scope_inputs", "effective_scopes", "filter_reasons"):
        assert status_key not in memory_context
    return memory_context


async def test_reviewed_memory_context_retrieve_fails_closed_without_trusted_context() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()

    result = await reviewed_memory_context_retrieve(_state(), {"configurable": {"session": object()}})

    _assert_empty_context_bundle(result, fallback_reason="missing_trusted_context")


async def test_reviewed_memory_context_retrieve_fails_closed_without_actor_merchant_scope() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()

    class NoCallLongTermMemoryService:
        async def retrieve_profile_memory(self, **kwargs: Any) -> list[dict[str, Any]]:
            raise AssertionError("missing actor merchant scope must not query long-term memory")

    class NoCallCaseMemoryService:
        async def retrieve_reviewed(self, request: Any) -> Any:
            raise AssertionError("missing actor merchant scope must not query case memory")

    trusted_context = _trusted_context(merchant_ids=[])
    result = await reviewed_memory_context_retrieve(
        _state(tenant_id=trusted_context.tenant_id, user_id=trusted_context.user_id),
        {
            "configurable": {
                "session": object(),
                "trusted_context": trusted_context,
                "long_term_memory_service": NoCallLongTermMemoryService(),
                "case_memory_service": NoCallCaseMemoryService(),
            }
        },
    )

    memory_context = _assert_empty_context_bundle(result, fallback_reason="missing_actor_merchant_scope")
    assert memory_context["status_ref"]["status"] == "skipped"


async def test_reviewed_memory_context_retrieve_denies_out_of_scope_merchant() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-a"])

    result = await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            extracted_slots={"merchant_id": "merchant-b"},
        ),
        {"configurable": {"session": object(), "trusted_context": trusted_context}},
    )

    memory_context = _assert_empty_context_bundle(result, fallback_reason="merchant_scope_denied")
    assert "merchant_scope_denied:merchant-b" in memory_context["status_ref"]["filter_reasons"]


async def test_reviewed_memory_context_retrieve_does_not_use_session_memory_to_create_scope() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-b"])

    result = await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            session_memory={"active_slots": {"merchant_id": "merchant-b"}},
        ),
        {"configurable": {"session": object(), "trusted_context": trusted_context}},
    )

    memory_context = _assert_empty_context_bundle(result, fallback_reason="memory_scope_not_authority")
    assert "memory_scope_not_authority" in memory_context["status_ref"]["filter_reasons"]
    assert all(
        scope.get("scope_id") != "merchant-b"
        for scope in memory_context["status_ref"].get("effective_scopes", [])
        if scope.get("scope_type") == "merchant"
    )


async def test_reviewed_memory_context_retrieve_does_not_use_candidate_slots_to_create_scope() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-b"])

    class NoCallLongTermMemoryService:
        async def retrieve_profile_memory(self, **kwargs: Any) -> list[dict[str, Any]]:
            raise AssertionError("LLM candidate slots must not query long-term memory")

    class NoCallCaseMemoryService:
        async def retrieve_reviewed(self, request: Any) -> Any:
            raise AssertionError("LLM candidate slots must not query case memory")

    result = await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            extracted_slots={},
            candidate_slots={"merchant_id": "merchant-b"},
        ),
        {
            "configurable": {
                "session": object(),
                "trusted_context": trusted_context,
                "long_term_memory_service": NoCallLongTermMemoryService(),
                "case_memory_service": NoCallCaseMemoryService(),
            }
        },
    )

    memory_context = _assert_empty_context_bundle(result, fallback_reason="memory_scope_not_authority")
    assert "memory_scope_not_authority" in memory_context["status_ref"]["filter_reasons"]
    assert "current_slots" not in memory_context["status_ref"]["trusted_scope_inputs"]
    assert result.get("node_errors") is None


async def test_reviewed_memory_context_retrieve_keeps_legacy_aliases_empty_on_fail_closed() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()

    result = await reviewed_memory_context_retrieve(_state(), {"configurable": {"session": object()}})

    _assert_empty_context_bundle(result, fallback_reason="missing_trusted_context")
    assert result["long_term_memory"] == []
    assert result["case_memory"] == []
