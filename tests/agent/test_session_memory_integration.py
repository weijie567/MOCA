from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.graph import build_graph
from src.agent.nodes import contextual_intent_resolve as contextual_intent_module
from src.agent.nodes import session_context_load as session_context_load_module
from src.agent.nodes.memory_write import memory_write
from src.agent.trace import write_agent_run
from src.agent.graph_vocabulary import project_trace_step_for_contract
from src.db.models import User
from src.memory.repository import SessionMemoryRepository
from src.memory.service import MemoryService
from tests.agent.conftest import FakeLLM
from tests.agent.test_graph import _config, _patch_graph_dependencies


def _state(user: User, query: str, thread_id: str, *, run_id: str | None = None) -> dict:
    state = {
        "user_query": query,
        "thread_id": thread_id,
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.id),
        "role": user.role,
    }
    if run_id is not None:
        state["current_run_id"] = run_id
    return state


async def _persist_run(session: AsyncSession, user: User, thread_id: str, query: str) -> str:
    run_id = str(uuid4())
    await write_agent_run(
        session,
        run_id=run_id,
        thread_id=thread_id,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        input_query=query,
        final_status="completed",
        final_response="done",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        total_latency_ms=1,
    )
    return run_id


async def _write_order_memory(session: AsyncSession, user: User, thread_id: str, order_id: str = "ORD-1001") -> None:
    run_id = await _persist_run(session, user, thread_id, f"remember {order_id}")
    await memory_write(
        {
            "tenant_id": str(user.tenant_id),
            "user_id": str(user.id),
            "thread_id": thread_id,
            "current_run_id": run_id,
            "final_response": "已完成。",
            "primary_intent": "refund_troubleshooting",
            "extracted_slots": {"order_id": order_id},
            "active_slots": {"order_id": order_id},
            "clarification_request": None,
            "last_business_context_refs": {"order": order_id},
            "trace_steps": [],
            "node_errors": [],
        },
        {"configurable": {"session": session}},
    )
    await session.commit()


def _slot_envelope(
    value: str,
    *,
    source_run_id: str,
    expires_at: datetime | None = None,
    compatible_intents: list[str] | None = None,
) -> dict:
    now = datetime.now(UTC)
    expiry = expires_at or now + timedelta(minutes=30)
    return {
        "schema_version": "session_slots.v1",
        "slots": {
            "order_id": {
                "value": value,
                "source": "explicit_user",
                "source_run_id": source_run_id,
                "updated_at": now.isoformat(),
                "expires_at": expiry.isoformat(),
                "compatible_intents": compatible_intents or ["refund_troubleshooting"],
                "business_object_type": "order",
                "business_object_id": value,
            }
        },
    }


async def _write_order_status_memory(
    session: AsyncSession,
    user: User,
    thread_id: str,
    order_id: str = "ORD-1001",
) -> None:
    run_id = await _persist_run(session, user, thread_id, f"status {order_id}")
    await memory_write(
        {
            "tenant_id": str(user.tenant_id),
            "user_id": str(user.id),
            "thread_id": thread_id,
            "current_run_id": run_id,
            "final_response": "已查询到订单信息。",
            "primary_intent": "order_status_inquiry",
            "requested_operation": "read_status",
            "extracted_slots": {"order_id": order_id, "issue_type": "refund_status", "action_type": "inquiry"},
            "active_slots": {"order_id": order_id, "issue_type": "refund_status", "action_type": "inquiry"},
            "clarification_request": None,
            "last_business_context_refs": {"business_fact_refs": [{"resource_type": "order", "resource_id": order_id}]},
            "trace_steps": [],
            "node_errors": [],
        },
        {"configurable": {"session": session}},
    )
    await session.commit()


@pytest.mark.asyncio
async def test_same_thread_vague_turn_inherits_session_order_and_reruns_investigation(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    thread_id = "integration-same-thread"
    await _write_order_memory(session, user, thread_id)
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state(user, "what about that refund?", thread_id),
        _config(deps["tool_platform"], deps["events"], thread_id, session=session),
    )

    assert final_state["active_slots"]["order_id"] == "ORD-1001"
    assert final_state["active_slot_metadata"]["order_id"]["source"] == "trusted_session_memory"
    assert final_state["active_slot_metadata"]["order_id"]["explicit_current_turn"] is False
    assert final_state["business_context"]["facts"]["order"]["order_no"] == "ORD-1001"
    assert [call[0] for call in deps["tool_platform"].calls] == ["get_order", "search_policy"]
    nodes = [step["node"] for step in final_state["trace_steps"]]
    assert nodes.index("session_context_load") < nodes.index("contextual_intent_resolve")


@pytest.mark.asyncio
async def test_agent_runs_session_slots_explicit_current_turn_overrides_inherited(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    thread_id = "integration-agent-runs-current-turn-overrides-memory"
    await _write_order_memory(session, user, thread_id, order_id="ORD-INHERITED-001")
    current_run_id = await _persist_run(session, user, thread_id, "current run ORD-CURRENT-001")
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-CURRENT-001")
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state(user, "订单是 ORD-CURRENT-001，继续查这笔退款", thread_id, run_id=current_run_id),
        _config(deps["tool_platform"], deps["events"], thread_id, session=session),
    )

    assert final_state["session_memory"]["active_slots"]["order_id"] == "ORD-INHERITED-001"
    assert final_state["session_memory"]["slot_metadata"]["order_id"]["source"] == "trusted_session_memory"
    assert final_state["active_slots"]["order_id"] == "ORD-CURRENT-001"
    assert final_state["active_slot_metadata"]["order_id"]["source"] == "current_turn"
    assert final_state["active_slot_metadata"]["order_id"]["explicit_current_turn"] is True
    assert final_state["business_context"]["facts"]["order"]["order_no"] == "ORD-CURRENT-001"


@pytest.mark.asyncio
async def test_agent_runs_session_memory_wrong_scope_fails_closed(
    session: AsyncSession,
    seeded_session: dict,
) -> None:
    from src.agent.routing import resolve_slots_for_completeness, route_after_slot_resolution

    user = seeded_session["users"]["cs_zhang"]
    repository = SessionMemoryRepository(session)
    service = MemoryService(repository)
    source_thread_id = "integration-agent-runs-memory-source-scope"
    source_run_id = await _persist_run(session, user, source_thread_id, "remember ORD-SCOPE-001")
    await repository.insert_active(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id=source_thread_id,
        active_slots_json=_slot_envelope("ORD-SCOPE-001", source_run_id=source_run_id),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    expired_thread_id = "integration-agent-runs-memory-expired-scope"
    expired_run_id = await _persist_run(session, user, expired_thread_id, "remember ORD-EXPIRED-001")
    await repository.insert_active(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id=expired_thread_id,
        active_slots_json=_slot_envelope(
            "ORD-EXPIRED-001",
            source_run_id=expired_run_id,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        ),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    incompatible_thread_id = "integration-agent-runs-memory-incompatible-scope"
    incompatible_run_id = await _persist_run(session, user, incompatible_thread_id, "remember ORD-INCOMPATIBLE-001")
    await repository.insert_active(
        tenant_id=user.tenant_id,
        user_id=user.id,
        thread_id=incompatible_thread_id,
        active_slots_json=_slot_envelope(
            "ORD-INCOMPATIBLE-001",
            source_run_id=incompatible_run_id,
            compatible_intents=["ticket_reply_draft"],
        ),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    cases = [
        (user.tenant_id, user.id, "integration-agent-runs-memory-wrong-thread"),
        (uuid4(), user.id, source_thread_id),
        (user.tenant_id, uuid4(), source_thread_id),
        (user.tenant_id, user.id, expired_thread_id),
        (user.tenant_id, user.id, incompatible_thread_id),
    ]
    for tenant_id, user_id, thread_id in cases:
        view = await service.load_session_memory(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            current_intent="refund_troubleshooting",
        )
        state = {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "thread_id": thread_id,
            "primary_intent": "refund_troubleshooting",
            "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
            "extracted_slots": {},
            "session_memory": view.model_dump(mode="json"),
        }

        assert view.continuity_claimed is False or view.active_slots == {}
        assert resolve_slots_for_completeness(state) == {}
        assert route_after_slot_resolution(state) == "clarification_gate"


@pytest.mark.asyncio
async def test_next_step_followup_reuses_prior_order_status_memory_instead_of_action_type_clarification(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    thread_id = "integration-next-step-followup"
    await _write_order_status_memory(session, user, thread_id, order_id="ORD-2024-001")
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    monkeypatch.setattr(
        contextual_intent_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "schema_version": "intent_result.v3",
                "primary_intent": "action_request",
                "requested_operation": "advise",
                "confidence": 0.82,
                "calibrated_confidence": 0.82,
                "secondary_intents": ["order_status_inquiry"],
                "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
                "candidate_slots": {},
                "routing_hints": {"clarification_reason": "missing_order_reference"},
                "classifier_version": "intent_classifier.v2",
                "calibration_version": "calibration.unverified",
                "reason_codes": ["action_handling_question", "missing_context_reference"],
            }
        ),
    )
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state(user, "那这个订单下一步应该怎么处理？", thread_id),
        _config(deps["tool_platform"], deps["events"], thread_id, session=session),
    )

    assert final_state["current_intent"] == "refund_troubleshooting"
    assert final_state["requested_operation"] == "read_status"
    assert final_state["active_slots"]["order_id"] == "ORD-2024-001"
    assert final_state["active_slot_metadata"]["order_id"]["source"] == "trusted_session_memory"
    assert final_state.get("clarification_request") is None
    assert "请提供操作类型" not in final_state["final_response"]
    assert final_state["business_context"]["facts"]["order"]["order_no"] == "ORD-2024-001"
    assert [call[0] for call in deps["tool_platform"].calls] == ["get_order", "search_policy"]


@pytest.mark.asyncio
async def test_pending_slot_short_reply_uses_pre_intent_same_thread_session_context(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    thread_id = "integration-pending-slot-short-reply"
    await _write_order_memory(session, user, thread_id, order_id="ORD-1001")
    deps = _patch_graph_dependencies(monkeypatch, intent="policy_qa", order_id=None)
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        {
            **_state(user, "ORD-1001", thread_id),
            "last_intent": "refund_troubleshooting",
            "requested_operation": "read_status",
            "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
            "clarification_request": {
                "reason": "missing_required_slots",
                "blocked_nodes": ["investigate"],
                "clarification_request_id": "clarify-short-reply",
            },
        },
        _config(deps["tool_platform"], deps["events"], thread_id, session=session),
    )

    nodes = [step["node"] for step in final_state["trace_steps"]]
    assert nodes[:4] == ["receive_request", "safety_pre_route", "session_context_load", "contextual_intent_resolve"]
    assert nodes.index("contextual_intent_resolve") < nodes.index("slot_resolution_gate")
    assert "long_term_memory_retrieve" not in nodes
    assert final_state["session_context"]["active_slots"]["order_id"] == "ORD-1001"
    assert final_state["session_memory"]["active_slots"]["order_id"] == "ORD-1001"
    assert final_state["active_slots"]["order_id"] == "ORD-1001"
    assert final_state.get("clarification_request") is None
    assert [call[0] for call in deps["tool_platform"].calls] == ["get_order", "search_policy"]


@pytest.mark.asyncio
async def test_different_thread_vague_turn_does_not_reuse_session_order(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    await _write_order_memory(session, user, "integration-source-thread")
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(
        _state(user, "what about that refund?", "integration-other-thread"),
        _config(deps["tool_platform"], deps["events"], "integration-other-thread", session=session),
    )

    assert deps["tool_platform"].calls == []
    assert final_state["active_slots"] == {}
    assert final_state["clarification_request"]["reason"] == "missing_required_slots"


@pytest.mark.asyncio
async def test_unresolved_question_carryover_keeps_current_turn_slot_authoritative(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    thread_id = "integration-unresolved-question"
    deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    graph = build_graph(MemorySaver())
    first_state = await graph.ainvoke(
        _state(user, "帮我看看这笔退款为什么没到账", thread_id),
        _config(deps["tool_platform"], deps["events"], thread_id, session=session),
    )
    run_id = await _persist_run(session, user, thread_id, "missing slot turn")
    await memory_write(
        {**_state(user, "帮我看看这笔退款为什么没到账", thread_id), **first_state, "current_run_id": run_id},
        {"configurable": {"session": session}},
    )
    await session.commit()
    view = await MemoryService(SessionMemoryRepository(session)).load_session_memory(
        user.tenant_id,
        user.id,
        thread_id,
        current_intent="refund_troubleshooting",
    )
    assert view.unresolved_questions

    second_deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id="ORD-1001")
    second_state = await graph.ainvoke(
        _state(user, "订单是 ORD-1001", thread_id),
        _config(second_deps["tool_platform"], second_deps["events"], thread_id, session=session),
    )

    assert second_state["active_slots"]["order_id"] == "ORD-1001"
    assert second_state["active_slot_metadata"]["order_id"]["source"] == "current_turn"
    assert second_state["business_context"]["facts"]["order"]["order_no"] == "ORD-1001"
    assert [call[0] for call in second_deps["tool_platform"].calls] == ["get_order", "search_policy"]


@pytest.mark.asyncio
async def test_disabled_and_unavailable_session_memory_fall_back_to_clarification(
    session: AsyncSession,
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = seeded_session["users"]["cs_zhang"]
    graph = build_graph(MemorySaver())

    monkeypatch.setattr(session_context_load_module.settings, "session_memory_enabled", False)
    disabled_deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    disabled_state = await graph.ainvoke(
        _state(user, "that refund?", "integration-disabled-memory"),
        _config(
            disabled_deps["tool_platform"], disabled_deps["events"], "integration-disabled-memory", session=session
        ),
    )
    assert disabled_deps["tool_platform"].calls == []
    assert disabled_state["session_memory"]["fallback_reason"] == "disabled"
    assert disabled_state["clarification_request"]["reason"] == "missing_required_slots"

    monkeypatch.setattr(session_context_load_module.settings, "session_memory_enabled", True)

    class FailingMemoryService:
        def __init__(self, repository, *, enabled: bool = True) -> None:
            pass

        async def load_session_memory(self, tenant_id, user_id, thread_id, current_intent):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(session_context_load_module, "MemoryService", FailingMemoryService)
    unavailable_deps = _patch_graph_dependencies(monkeypatch, intent="refund_troubleshooting", order_id=None)
    unavailable_state = await graph.ainvoke(
        _state(user, "that refund?", "integration-unavailable-memory"),
        _config(
            unavailable_deps["tool_platform"],
            unavailable_deps["events"],
            "integration-unavailable-memory",
            session=session,
        ),
    )
    assert unavailable_deps["tool_platform"].calls == []
    assert unavailable_state["session_memory"]["fallback_reason"] == "unavailable"
    assert unavailable_state["clarification_request"]["reason"] == "missing_required_slots"


@pytest.mark.asyncio
async def test_slot_resolution_gate_loads_agent_runs_prompt_context_from_trusted_config(
    seeded_session: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from src.agent.nodes import slot_resolution_gate as slot_resolution_gate_module
    from tests.agent.conftest import FakeLLM

    user = seeded_session["users"]["cs_zhang"]
    thread_id = "integration-agent-runs-extract-context"
    run_id = str(uuid4())
    calls: list[dict] = []
    assemblies: list[dict] = []

    class FakeConversationService:
        async def load_prompt_context(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                latest_thread_summary=SimpleNamespace(summary_text="Prior summary mentions ORD-PRIOR-001."),
                recent_messages=[
                    SimpleNamespace(role="user", content="之前那个订单是 ORD-PRIOR-001"),
                    SimpleNamespace(role="assistant", content="我会继续按安全边界处理。"),
                ],
                tool_prompt_summaries=[
                    SimpleNamespace(
                        id=uuid4(),
                        tool_call_id="tool-call-prior",
                        tool_result_id="tool-result-prior",
                        tool_name="get_order",
                        status="success",
                        summary="Raw summary should not be preferred.",
                        prompt_summary="Prompt-safe tool summary for ORD-PRIOR-001.",
                        business_fact_refs_json=[{"resource_type": "order", "resource_id": "ORD-PRIOR-001"}],
                        policy_evidence_refs_json=[],
                        raw_result_ref="tool-results/prior",
                        audit_ref="audit/prior",
                    )
                ],
            )

    original_assemble = slot_resolution_gate_module.ContextAssembler.assemble

    def spy_assemble(self, **kwargs):
        assemblies.append(kwargs)
        return original_assemble(self, **kwargs)

    monkeypatch.setattr(slot_resolution_gate_module.ContextAssembler, "assemble", spy_assemble)
    monkeypatch.setattr(
        slot_resolution_gate_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "order_id": "ORD-CURRENT-001",
                "refund_case_id": None,
                "ticket_id": None,
                "merchant_id": None,
                "customer_id": None,
                "issue_type": "refund_status",
                "action_type": None,
            }
        ),
    )

    result = await slot_resolution_gate_module.slot_resolution_gate(
        _state(user, "当前订单是 ORD-CURRENT-001，继续处理这个退款", thread_id, run_id=run_id),
        {
            "configurable": {
                "session": object(),
                "conversation_service": FakeConversationService(),
                "conversation_thread_id": str(uuid4()),
                "conversation_message_id": str(uuid4()),
            }
        },
    )

    assert calls == [
        {
            "tenant_id": str(user.tenant_id),
            "user_id": str(user.id),
            "thread_id": thread_id,
            "run_id": run_id,
            "max_recent_messages": 8,
        }
    ]
    assert result["active_slots"]["order_id"] == "ORD-CURRENT-001"
    assert result["trace_steps"][-1]["node"] == "slot_resolution_gate"
    projected_step = project_trace_step_for_contract(result["trace_steps"][-1])
    assert projected_step["target_node"] == "slot_resolution_gate"
    assert projected_step["target_graph_status"] == "runtime"
    assert assemblies
    assembly_kwargs = assemblies[0]
    assert assembly_kwargs["thread_rolling_summary"] == "Prior summary mentions ORD-PRIOR-001."
    assert assembly_kwargs["recent_messages"] == [
        {"role": "user", "content": "之前那个订单是 ORD-PRIOR-001"},
        {"role": "assistant", "content": "我会继续按安全边界处理。"},
    ]
    assert assembly_kwargs["tool_result_summaries"][0].prompt_summary == "Prompt-safe tool summary for ORD-PRIOR-001."
    assert assembly_kwargs["current_user_message"] == "当前订单是 ORD-CURRENT-001，继续处理这个退款"
