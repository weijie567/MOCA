from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CaseMemory
from src.memory.case_working_context_lifecycle import CaseWorkingContextLifecycleResult, lifecycle_status
from src.memory.context_refs import ReviewedMemoryContextBundle, ReviewedMemoryContextRetrieveStatusV1
from src.memory.identity import canonical_memory_content_hash
from src.platform.trusted_context import MerchantScopeV1, TrustedContext


def _trusted_context(
    *,
    merchant_ids: list[str],
    tenant_id: str | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> TrustedContext:
    return TrustedContext(
        tenant_id=tenant_id or str(uuid4()),
        user_id=user_id or str(uuid4()),
        role="support",
        permissions=["tool:get_order", "tool:get_refund_case"],
        merchant_scope=MerchantScopeV1(merchant_ids=merchant_ids),
        thread_id="thread-reviewed-memory-context",
        run_id=run_id or str(uuid4()),
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
                    "active_slots": {"order_id": "ORD-UNIFIED-BUNDLE"},
                },
                "policy_topic_hints": ["refund_policy@v1"],
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
                    "semantic_kind": "merchant_preference",
                    "content": "Merchant prefers concise updates.",
                }
            ],
            case_items=[{"case_memory_id": "case-1", "excerpt": "Reviewed case excerpt."}],
            status_ref=ReviewedMemoryContextRetrieveStatusV1(status="loaded"),
        )


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


async def test_reviewed_memory_context_retrieve_uses_actor_scope_for_canonical_reviewed_memory_hint() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-c"])

    class CapturingMemoryContextService:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def load_reviewed_memory_context(self, **kwargs: Any) -> ReviewedMemoryContextBundle:
            self.calls.append(kwargs)
            return ReviewedMemoryContextBundle(status_ref=ReviewedMemoryContextRetrieveStatusV1(status="loaded"))

    service = CapturingMemoryContextService()

    await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            routing_hints={"needs_reviewed_memory_context": True},
        ),
        {"configurable": {"trusted_context": trusted_context, "memory_context_service": service}},
    )

    assert service.calls[0]["trusted_business_context"] == {
        "merchant_id": "merchant-c",
        "source": "trusted_context_actor_scope",
    }


async def test_reviewed_memory_context_retrieve_keeps_actor_scope_for_legacy_long_term_hint() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-c"])

    class CapturingMemoryContextService:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def load_reviewed_memory_context(self, **kwargs: Any) -> ReviewedMemoryContextBundle:
            self.calls.append(kwargs)
            return ReviewedMemoryContextBundle(status_ref=ReviewedMemoryContextRetrieveStatusV1(status="loaded"))

    service = CapturingMemoryContextService()

    await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            routing_hints={"needs_long_term_memory": True},
        ),
        {"configurable": {"trusted_context": trusted_context, "memory_context_service": service}},
    )

    assert service.calls[0]["trusted_business_context"] == {
        "merchant_id": "merchant-c",
        "source": "trusted_context_actor_scope",
    }


async def test_reviewed_memory_context_retrieve_keeps_legacy_aliases_empty_on_fail_closed() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()

    result = await reviewed_memory_context_retrieve(_state(), {"configurable": {"session": object()}})

    _assert_empty_context_bundle(result, fallback_reason="missing_trusted_context")
    assert result["long_term_memory"] == []
    assert result["case_memory"] == []


async def test_reviewed_memory_context_retrieve_emits_unified_bundle_when_session_context_exists() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    state = _state(**_session_context_state())

    result = await reviewed_memory_context_retrieve(
        state,
        {"configurable": {"memory_context_service": FakeMemoryContextService()}},
    )

    assert result["memory_context"]["schema_version"] == "reviewed_memory_context_bundle.v1"
    assert result["memory_context_bundle"]["schema_version"] == "memory_context_bundle.v1"
    assert result["memory_context_bundle"]["session_context"]["policy_topic_hints"] == ["refund_policy@v1"]
    assert result["memory_context_bundle"]["long_term_items"][0]["semantic_kind"] == "merchant_preference"


async def test_reviewed_memory_context_retrieve_invokes_cwc_lifecycle_adapter_with_trusted_context() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-a"])
    calls: list[dict[str, Any]] = []
    case_id = uuid4()

    class FakeCwcLifecycleAdapter:
        async def link_and_load_active(self, **kwargs: Any) -> CaseWorkingContextLifecycleResult:
            calls.append(kwargs)
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
                    raw_case_ref="RF-CWC-1",
                ),
            )

    session = object()
    result = await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            active_slots={"refund_case_id": "RF-CWC-1"},
            **_session_context_state(),
        ),
        {
            "configurable": {
                "session": session,
                "trusted_context": trusted_context,
                "memory_context_service": FakeMemoryContextService(),
                "case_working_context_lifecycle_adapter": FakeCwcLifecycleAdapter(),
            }
        },
    )

    assert calls[0]["session"] is session
    assert str(calls[0]["tenant_id"]) == trusted_context.tenant_id
    assert str(calls[0]["user_id"]) == trusted_context.user_id
    assert calls[0]["thread_id"] == trusted_context.thread_id
    assert str(calls[0]["run_id"]) == trusted_context.run_id
    assert calls[0]["state"]["active_slots"] == {"refund_case_id": "RF-CWC-1"}
    assert result["case_working_context"] == {"content": {"customer_request": "用户询问退款进度"}}
    assert result["case_working_context_lifecycle_status"]["read_status"] == "loaded"


async def test_reviewed_memory_context_retrieve_merges_cwc_into_unified_memory_context_bundle() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-a"])
    case_id = uuid4()

    class FakeCwcLifecycleAdapter:
        async def link_and_load_active(self, **kwargs: Any) -> CaseWorkingContextLifecycleResult:
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
                    raw_case_ref="RF-CWC-1",
                ),
            )

    result = await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            active_slots={"refund_case_id": "RF-CWC-1"},
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

    bundle = result["memory_context_bundle"]
    assert bundle["schema_version"] == "memory_context_bundle.v1"
    assert bundle["session_context"]["policy_topic_hints"] == ["refund_policy@v1"]
    assert bundle["long_term_items"][0]["semantic_kind"] == "merchant_preference"
    assert bundle["case_items"][0]["excerpt"] == "Reviewed case excerpt."
    assert bundle["reviewed_status_ref"]["status"] == "loaded"
    assert bundle["case_working_context"] == {"content": {"customer_request": "用户询问退款进度"}}
    assert bundle["case_working_context_status_ref"]["read_status"] == "loaded"


async def test_reviewed_memory_context_retrieve_skipped_cwc_status_does_not_change_reviewed_memory() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-a"])

    result = await reviewed_memory_context_retrieve(
        _state(tenant_id=trusted_context.tenant_id, user_id=trusted_context.user_id, active_slots={}),
        {
            "configurable": {
                "session": object(),
                "trusted_context": trusted_context,
                "memory_context_service": FakeMemoryContextService(),
            }
        },
    )

    assert result["long_term_memory"][0]["semantic_kind"] == "merchant_preference"
    assert result["case_memory"][0]["excerpt"] == "Reviewed case excerpt."
    assert result["case_working_context"] is None
    assert result["case_working_context_lifecycle_status"]["status"] == "skipped"
    assert result["case_working_context_lifecycle_status"]["reason_code"] == "skipped_no_case"


async def test_reviewed_memory_context_retrieve_keeps_generated_precedent_separate_from_active_cwc() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-a"])
    case_id = uuid4()

    class GeneratedPrecedentMemoryContextService:
        async def load_reviewed_memory_context(self, **kwargs: Any) -> ReviewedMemoryContextBundle:
            return ReviewedMemoryContextBundle(
                long_term_items=[],
                case_items=[
                    {
                        "case_memory_id": "generated-precedent-1",
                        "excerpt": "Approved closed_case_cwc_candidate precedent.",
                    }
                ],
                status_ref=ReviewedMemoryContextRetrieveStatusV1(status="loaded"),
            )

    class ActiveCwcAdapter:
        async def link_and_load_active(self, **kwargs: Any) -> CaseWorkingContextLifecycleResult:
            return CaseWorkingContextLifecycleResult(
                case_id=case_id,
                case_working_context={"content": {"customer_request": "当前案件仍按 CWC 单独读取"}},
                status_ref=lifecycle_status(
                    status="completed",
                    resolve_status="resolved",
                    link_status="linked",
                    read_status="loaded",
                    tenant_id=kwargs["tenant_id"],
                    case_id=case_id,
                    run_id=kwargs["run_id"],
                    raw_case_ref="RF-CWC-SEPARATE",
                ),
            )

    result = await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            active_slots={"refund_case_id": "RF-CWC-SEPARATE"},
            **_session_context_state(),
        ),
        {
            "configurable": {
                "session": object(),
                "trusted_context": trusted_context,
                "memory_context_service": GeneratedPrecedentMemoryContextService(),
                "case_working_context_lifecycle_adapter": ActiveCwcAdapter(),
            }
        },
    )

    assert result["case_memory"] == [
        {
            "case_memory_id": "generated-precedent-1",
            "excerpt": "Approved closed_case_cwc_candidate precedent.",
        }
    ]
    assert result["case_working_context"] == {"content": {"customer_request": "当前案件仍按 CWC 单独读取"}}
    assert result["memory_context_bundle"]["case_items"] == result["case_memory"]
    assert result["memory_context_bundle"]["case_working_context"] == result["case_working_context"]


async def test_reviewed_memory_context_retrieve_real_service_uses_issue_type_not_primary_intent(
    session: AsyncSession,
    seeded_session: dict[str, Any],
) -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    tenant_id = seeded_session["tenant"].id
    user_id = seeded_session["users"]["cs_zhang"].id
    merchant_id = str(seeded_session["merchant"].id)
    trusted_context = _trusted_context(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        run_id=str(uuid4()),
        merchant_ids=[merchant_id],
    )
    summary = "Closed refund case precedent: refund_dispute."
    precedent = CaseMemory(
        id=uuid4(),
        tenant_id=tenant_id,
        scope_type="merchant",
        scope_id=merchant_id,
        case_type="refund_dispute",
        summary=summary,
        excerpt="Approved closed_case_cwc_candidate refund_dispute precedent for damaged goods.",
        applicability="Use only as reviewed precedent for similar refund disputes within merchant scope.",
        outcome="Refund approved after staff review.",
        caveats="Contextual precedent only.",
        content_hash=canonical_memory_content_hash(memory_type="case_memory", content=summary),
        policy_family="refund",
        policy_version="2026-01",
        policy_refs_json=[{"doc_key": "refund_policy", "chunk_id": "c-1", "policy_version": "2026-01"}],
        source_ref_json={
            "source_type": "closed_case_cwc_candidate",
            "business_object_type": "refund_case",
            "business_object_id": str(seeded_session["refund_case"].id),
        },
        source_identity_hash=None,
        embedding=None,
        review_status="approved",
        reviewed_by_user_id=user_id,
        reviewed_at=datetime.now(UTC),
        pii_classification="none",
    )
    session.add(precedent)
    await session.flush()

    result = await reviewed_memory_context_retrieve(
        _state(
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            primary_intent="refund_troubleshooting",
            active_slots={"issue_type": "refund_dispute"},
            extracted_slots={"merchant_id": merchant_id},
            user_query="refund_dispute precedent",
        ),
        {"configurable": {"session": session, "trusted_context": trusted_context}},
    )

    assert result["case_memory"][0]["case_memory_id"] == str(precedent.id)
    assert "closed_case_cwc_candidate" in result["case_memory"][0]["source_refs"][0]["source_type"]
    assert result["reviewed_memory_context_retrieve_status"]["status"] == "loaded"
    assert result["case_working_context_lifecycle_status"]["reason_code"] == "skipped_no_case"


async def test_reviewed_memory_context_retrieve_does_not_use_session_context_as_cwc_identity() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-a"])
    tempting_session_context = _session_context_state()
    tempting_session_context["session_context_bundle"]["session_context"]["slot_continuity"]["active_slots"] = {
        "refund_case_id": "RF-FROM-SESSION-CONTEXT"
    }

    result = await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            session_memory={"active_slots": {"refund_case_id": "RF-FROM-SESSION-MEMORY"}},
            session_context={"active_slots": {"refund_case_id": "RF-FROM-RAW-SESSION-CONTEXT"}},
            **tempting_session_context,
        ),
        {
            "configurable": {
                "session": object(),
                "trusted_context": trusted_context,
                "memory_context_service": FakeMemoryContextService(),
            }
        },
    )

    assert result["long_term_memory"][0]["semantic_kind"] == "merchant_preference"
    assert result["case_memory"][0]["excerpt"] == "Reviewed case excerpt."
    assert result["case_working_context"] is None
    assert result["memory_context_bundle"]["case_working_context"] is None
    assert result["case_working_context_lifecycle_status"]["status"] == "skipped"
    assert result["case_working_context_lifecycle_status"]["reason_code"] == "skipped_no_case"
    assert result.get("node_errors") is None


async def test_reviewed_memory_context_retrieve_missing_trusted_context_skips_cwc_without_adapter_call() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()

    class NoCallCwcLifecycleAdapter:
        async def link_and_load_active(self, **kwargs: Any) -> CaseWorkingContextLifecycleResult:
            raise AssertionError("missing trusted context must not invoke CWC adapter")

    result = await reviewed_memory_context_retrieve(
        _state(active_slots={"refund_case_id": "RF-CWC-1"}),
        {
            "configurable": {
                "session": object(),
                "memory_context_service": FakeMemoryContextService(),
                "case_working_context_lifecycle_adapter": NoCallCwcLifecycleAdapter(),
            }
        },
    )

    assert result["case_working_context"] is None
    assert result["case_working_context_lifecycle_status"]["status"] == "skipped"
    assert result["case_working_context_lifecycle_status"]["reason_code"] == "missing_trusted_context"


async def test_reviewed_memory_context_retrieve_cwc_adapter_error_adds_node_error_but_keeps_reviewed_memory() -> None:
    reviewed_memory_context_retrieve = _reviewed_memory_context_retrieve()
    trusted_context = _trusted_context(merchant_ids=["merchant-a"])

    class FailingCwcLifecycleAdapter:
        async def link_and_load_active(self, **kwargs: Any) -> CaseWorkingContextLifecycleResult:
            raise RuntimeError("cwc unavailable")

    result = await reviewed_memory_context_retrieve(
        _state(
            tenant_id=trusted_context.tenant_id,
            user_id=trusted_context.user_id,
            active_slots={"refund_case_id": "RF-CWC-1"},
        ),
        {
            "configurable": {
                "session": object(),
                "trusted_context": trusted_context,
                "memory_context_service": FakeMemoryContextService(),
                "case_working_context_lifecycle_adapter": FailingCwcLifecycleAdapter(),
            }
        },
    )

    assert result["long_term_memory"][0]["semantic_kind"] == "merchant_preference"
    assert result["case_memory"][0]["excerpt"] == "Reviewed case excerpt."
    assert result["case_working_context"] is None
    assert result["case_working_context_lifecycle_status"]["status"] == "error"
    assert result["node_errors"][-1] == {
        "node": "reviewed_memory_context_retrieve",
        "error_code": "CASE_WORKING_CONTEXT_LOAD_FAILED",
    }
