from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from src.memory.case_working_context_lifecycle import CaseWorkingContextLifecycleResult, lifecycle_status
from src.memory.context_refs import ReviewedMemoryContextBundle, ReviewedMemoryContextRetrieveStatusV1
from src.platform.trusted_context import MerchantScopeV1, TrustedContext

ALLOWED_USAGE_LABELS = {
    "session_continuity",
    "explicit_preference_memory",
    "reviewed_case_precedent",
    "case_working_context_status",
    "reviewed_memory_skipped",
    "reviewed_memory_unavailable",
}


def _trusted_context(*, merchant_ids: list[str]) -> TrustedContext:
    return TrustedContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        role="support",
        permissions=["tool:get_order", "tool:get_refund_case"],
        merchant_scope=MerchantScopeV1(merchant_ids=merchant_ids),
        thread_id="thread-memory-context-load",
        run_id=str(uuid4()),
        trace_id="trace-memory-context-load",
    )


def _state(**updates: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "tenant_id": str(uuid4()),
        "user_id": str(uuid4()),
        "thread_id": "thread-memory-context-load",
        "current_run_id": str(uuid4()),
        "primary_intent": "refund_troubleshooting",
        "user_query": "请结合已审核记忆继续处理这个退款问题",
        "extracted_slots": {},
        "active_slots": {},
        "candidate_slots": {},
        "trace_steps": [],
        "llm_outputs": {},
    }
    values.update(updates)
    return values


def _session_context_state() -> dict[str, Any]:
    return {
        "session_context_bundle": {
            "schema_version": "session_context_bundle.v1",
            "authority_class": "contextual_only",
            "session_context": {
                "schema_version": "session_context_memory.v1",
                "authority_class": "contextual_only",
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "thread_id": "thread-1",
                "run_id": "run-1",
                "slot_continuity": {
                    "source": "postgres_session_memory",
                    "continuity_claimed": True,
                    "active_slots": {"order_id": "ORD-MEMORY-CONTEXT-LOAD"},
                },
            },
        },
        "session_context_load_status": {
            "schema_version": "session_context_load_status.v1",
            "status": "loaded",
            "source": "session_memory_bundle_service",
            "authority_class": "contextual_only",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": "thread-1",
            "run_id": "run-1",
        },
    }


class FakeMemoryContextService:
    async def load_reviewed_memory_context(self, **kwargs: Any) -> ReviewedMemoryContextBundle:
        return ReviewedMemoryContextBundle(
            long_term_items=[
                {
                    "memory_id": "ltm-1",
                    "memory_kind": "preference",
                    "semantic_kind": "merchant_preference",
                    "content": "Merchant prefers concise updates.",
                }
            ],
            case_items=[{"case_memory_id": "case-1", "excerpt": "Reviewed case excerpt."}],
            status_ref=ReviewedMemoryContextRetrieveStatusV1(
                status="loaded",
                filter_reasons=["reviewed_prompt_safe"],
            ),
        )


class FakeCwcLifecycleAdapter:
    async def link_and_load_active(self, **kwargs: Any) -> CaseWorkingContextLifecycleResult:
        case_id = uuid4()
        return CaseWorkingContextLifecycleResult(
            case_id=case_id,
            case_working_context={"content": {"customer_request": "用户询问退款进度"}},
            status_ref=lifecycle_status(
                status="completed",
                resolve_status="resolved",
                link_status="linked",
                read_status="loaded",
                tenant_id=kwargs["tenant_id"],
                case_id=case_id,
                run_id=kwargs["run_id"],
                raw_case_ref="RF-MEMORY-CONTEXT-LOAD",
            ),
        )


async def test_memory_context_load_writes_canonical_metrics_labels_and_trace() -> None:
    from src.agent.nodes.memory_context_load import memory_context_load

    trusted_context = _trusted_context(merchant_ids=["merchant-a"])
    result = await memory_context_load(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            active_slots={"refund_case_id": "RF-MEMORY-CONTEXT-LOAD"},
            **_session_context_state(),
        ),
        {
            "configurable": {
                "session": object(),
                "trusted_context": trusted_context,
                "memory_context_service": FakeMemoryContextService(),
                "case_working_context_lifecycle_adapter": FakeCwcLifecycleAdapter(),
            }
        },
    )

    metrics = result["llm_outputs"]["memory_context_load"]
    assert metrics["source"] == "reviewed_memory"
    assert metrics["authority_class"] == "contextual_only"
    assert metrics["long_term_count"] == 1
    assert metrics["case_count"] == 1
    assert metrics["fallback_reason"] is None
    assert metrics["filter_reasons"] == ["reviewed_prompt_safe"]
    assert set(metrics["usage_labels"]) <= ALLOWED_USAGE_LABELS
    assert set(metrics["usage_labels"]) >= {
        "session_continuity",
        "explicit_preference_memory",
        "reviewed_case_precedent",
        "case_working_context_status",
    }
    assert "long_term_memory_retrieve" not in result["llm_outputs"]
    assert result["trace_steps"][-1]["node"] == "memory_context_load"
    assert result["trace_steps"][-1]["metrics_json"] == metrics


async def test_memory_context_load_forwards_reviewed_memory_injection_seams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.agent.nodes import memory_context_load as module

    captured: dict[str, Any] = {}

    async def fake_reviewed_memory_context_retrieve(
        state: dict[str, Any],
        config: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "long_term_memory": [],
            "case_memory": [],
            "reviewed_memory_context_retrieve_status": {"fallback_reason": None, "filter_reasons": []},
            "llm_outputs": {},
            "trace_steps": [{"node": "reviewed_memory_context_retrieve", "metrics_json": {}}],
        }

    monkeypatch.setattr(module, "reviewed_memory_context_retrieve", fake_reviewed_memory_context_retrieve)
    injection_values = {
        "memory_context_service_cls": object(),
        "long_term_memory_repository_cls": object(),
        "case_memory_repository_cls": object(),
        "long_term_memory_service_cls": object(),
        "case_memory_service_cls": object(),
        "case_working_context_lifecycle_adapter_cls": object(),
    }

    result = await module.memory_context_load(_state(), {"configurable": {}}, **injection_values)

    assert captured == injection_values
    assert result["llm_outputs"]["memory_context_load"]["authority_class"] == "contextual_only"
    assert result["trace_steps"][-1]["node"] == "memory_context_load"


async def test_memory_context_load_missing_trusted_context_skips_without_exception() -> None:
    from src.agent.nodes.memory_context_load import memory_context_load

    result = await memory_context_load(_state(), {"configurable": {"session": object()}})

    assert result["long_term_memory"] == []
    assert result["case_memory"] == []
    metrics = result["llm_outputs"]["memory_context_load"]
    assert metrics["source"] == "reviewed_memory_skipped"
    assert metrics["fallback_reason"] == "missing_trusted_context"
    assert "reviewed_memory_skipped" in metrics["usage_labels"]
    assert set(metrics["usage_labels"]) <= ALLOWED_USAGE_LABELS


async def test_memory_context_load_service_error_is_unavailable_and_maps_node_errors() -> None:
    from src.agent.nodes.memory_context_load import memory_context_load

    class FailingMemoryContextService:
        async def load_reviewed_memory_context(self, **kwargs: Any) -> ReviewedMemoryContextBundle:
            raise RuntimeError("memory service unavailable")

    result = await memory_context_load(
        _state(),
        {"configurable": {"memory_context_service": FailingMemoryContextService()}},
    )

    metrics = result["llm_outputs"]["memory_context_load"]
    assert metrics["source"] == "reviewed_memory_unavailable"
    assert metrics["fallback_reason"] == "service_error"
    assert "reviewed_memory_unavailable" in metrics["usage_labels"]
    assert set(metrics["usage_labels"]) <= ALLOWED_USAGE_LABELS
    assert result["node_errors"][-1] == {
        "node": "memory_context_load",
        "error_code": "REVIEWED_MEMORY_CONTEXT_UNAVAILABLE",
    }


async def test_long_term_memory_retrieve_delegates_to_canonical_node_and_keeps_legacy_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.agent.nodes import long_term_memory_retrieve as module

    calls: list[dict[str, Any]] = []

    async def fake_memory_context_load(state: dict[str, Any], config: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        calls.append({"state": state, "config": config, "kwargs": kwargs})
        return {
            "long_term_memory": [{"memory_id": "ltm-1"}],
            "case_memory": [{"case_memory_id": "case-1"}],
            "reviewed_memory_context_retrieve_status": {"fallback_reason": None},
            "llm_outputs": {
                "memory_context_load": {
                    "source": "reviewed_memory",
                    "authority_class": "contextual_only",
                    "usage_labels": ["explicit_preference_memory", "reviewed_case_precedent"],
                    "long_term_count": 1,
                    "case_count": 1,
                    "fallback_reason": None,
                    "filter_reasons": [],
                }
            },
            "trace_steps": [],
        }

    monkeypatch.setattr(module, "memory_context_load", fake_memory_context_load)

    result = await module.long_term_memory_retrieve(_state(), {"configurable": {}})

    assert calls
    assert result["llm_outputs"]["memory_context_load"]["authority_class"] == "contextual_only"
    assert result["llm_outputs"]["long_term_memory_retrieve"] == {
        "source": "reviewed_memory",
        "continuity_claimed": True,
        "retrieved": 2,
        "profile_count": 1,
        "case_count": 1,
        "fallback_reason": None,
    }
