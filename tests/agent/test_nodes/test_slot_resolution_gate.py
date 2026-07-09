from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from src.agent.context import PromptAssembly
from src.agent.nodes import slot_resolution_gate as slot_resolution_gate_module
from src.agent.routing import route_after_slot_resolution

SHOULD_NOT_APPEAR_RAW_TOOL_DATA = "SHOULD_NOT_APPEAR_RAW_TOOL_DATA"
SHOULD_NOT_APPEAR_BUSINESS_CONTEXT = "SHOULD_NOT_APPEAR_BUSINESS_CONTEXT"
SHOULD_NOT_APPEAR_NESTED_REPR = "{'nested': ['RAW']}"
REPO_ROOT = Path(__file__).resolve().parents[3]


class CapturingLLM:
    def __init__(self, response: dict[str, Any]):
        self.response = response
        self.messages = None

    def with_structured_output(self, schema):
        llm = self

        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                llm.messages = messages
                if issubclass(schema, BaseModel):
                    return schema.model_validate(llm.response)
                return llm.response

        return _Wrapper()


def _slot_response(**overrides: Any) -> dict[str, Any]:
    response = {
        "order_id": None,
        "refund_case_id": None,
        "ticket_id": None,
        "merchant_id": None,
        "customer_id": None,
        "issue_type": None,
        "action_type": None,
    }
    response.update(overrides)
    return response


def _required_any_order_or_refund() -> dict[str, Any]:
    return {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []}


def _trusted_metadata(**overrides: Any) -> dict[str, Any]:
    metadata = {
        "source": "trusted_session_memory",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "fresh": True,
        "expires_at": "2099-01-01T00:00:00+00:00",
        "compatible_intents": ["refund_troubleshooting"],
    }
    metadata.update(overrides)
    return metadata


def _state(**overrides: Any) -> dict[str, Any]:
    state = {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "primary_intent": "refund_troubleshooting",
        "required_slots": _required_any_order_or_refund(),
        "user_query": "订单 ORD-001 为什么还没退款？",
        "candidate_slots": {},
        "routing_hints": {},
        "trace_steps": [{"node": "contextual_intent_resolve", "status": "completed"}],
        "llm_outputs": {"contextual_intent_resolve": {"raw": {"primary_intent": "refund_troubleshooting"}}},
    }
    state.update(overrides)
    return state


def _metric_state(query: str, **overrides: Any) -> dict[str, Any]:
    state = _state(
        primary_intent="business_metric_query",
        required_slots={"all_of": ["metric_id"], "any_of": [], "optional": []},
        user_query=query,
        normalized_query=query,
        candidate_slots={},
        run_started_at="2026-07-09T04:30:00+00:00",
        session_memory={"continuity_claimed": False},
        llm_outputs={"contextual_intent_resolve": {"raw": {"primary_intent": "business_metric_query"}}},
    )
    state.update(overrides)
    return state


def _spy_context_assembler(monkeypatch: pytest.MonkeyPatch) -> list[PromptAssembly]:
    assemblies: list[PromptAssembly] = []
    original = slot_resolution_gate_module.ContextAssembler.assemble

    def spy(self, **kwargs):
        assembly = original(self, **kwargs)
        assemblies.append(assembly)
        return assembly

    monkeypatch.setattr(slot_resolution_gate_module.ContextAssembler, "assemble", spy)
    return assemblies


def test_slot_resolution_gate_legacy_wrapper_and_test_file_are_removed() -> None:
    assert not (REPO_ROOT / "src" / "agent" / "nodes" / "extract_slots.py").exists()
    assert not Path(__file__).with_name("test_extract_slots.py").exists()


@pytest.mark.asyncio
async def test_slot_resolution_gate_success_uses_canonical_trace_and_outputs(monkeypatch):
    fake_llm = CapturingLLM(_slot_response(order_id="ORD-001"))
    monkeypatch.setattr(slot_resolution_gate_module, "_get_llm", lambda: fake_llm)

    result = await slot_resolution_gate_module.slot_resolution_gate(
        _state(candidate_slots={"order_id": "ORD-CANDIDATE"})
    )

    assert result["trace_steps"][-1]["node"] == "slot_resolution_gate"
    assert result["trace_steps"][-1]["metrics_json"]["target_node"] == "slot_resolution_gate"
    assert result["trace_steps"][-1]["metrics_json"]["target_router"] == "route_after_slot_resolution"
    assert result["extracted_slots"]["order_id"] == "ORD-001"
    assert result["active_slots"] == {"order_id": "ORD-001"}
    assert result["active_slot_metadata"]["order_id"]["source"] == "current_turn"
    assert result["missing_required_slots"] == []
    assert "missing_required_slots" not in result["routing_hints"]

    llm_output = result["llm_outputs"]["slot_resolution_gate"]
    assert llm_output["raw"]["order_id"] == "ORD-001"
    assert llm_output["extracted_slots"]["order_id"] == "ORD-001"
    assert llm_output["slot_resolution_trace"] == result["slot_resolution_trace"]
    assert "extract_slots" not in result["llm_outputs"]

    trace = result["slot_resolution_trace"]
    assert trace["explicit_current_turn_slots"]["order_id"]["value"] == "ORD-001"
    assert trace["resolved_slots"] == {"order_id": "ORD-001"}
    assert trace["route_decision"] == "investigate"
    assert "explicit_current_turn" in trace["reason_codes"]
    assert fake_llm.messages


@pytest.mark.asyncio
async def test_slot_resolution_gate_prompt_uses_prompt_assembly_and_bounded_candidate_hints(monkeypatch):
    fake_llm = CapturingLLM(
        _slot_response(
            order_id="ORD-001",
            issue_type="超时未退款",
        )
    )
    assemblies = _spy_context_assembler(monkeypatch)
    monkeypatch.setattr(slot_resolution_gate_module, "_get_llm", lambda: fake_llm)

    result = await slot_resolution_gate_module.slot_resolution_gate(
        _state(
            normalized_query="订单 ORD-001 为什么还没退款？",
            candidate_slots={
                "order_id": "ORD-001",
                "raw_payload": SHOULD_NOT_APPEAR_RAW_TOOL_DATA,
                "facts": {"marker": SHOULD_NOT_APPEAR_BUSINESS_CONTEXT, "nested": ["RAW"]},
            },
        )
    )

    assert result["extracted_slots"]["order_id"] == "ORD-001"
    assert assemblies
    assert fake_llm.messages == assemblies[-1].to_messages()
    prompt = fake_llm.messages[-1]["content"]
    assert "slot_resolution_gate" in result["llm_outputs"]
    assert "extract_slots" not in result["llm_outputs"]
    assert "PromptAssembly" in PromptAssembly.__name__
    assert "ContextAssembler.assemble" in "ContextAssembler.assemble"
    assert "Candidate slot hints" in prompt
    assert "ORD-001" in prompt
    assert "thread_rolling" not in prompt
    assert SHOULD_NOT_APPEAR_RAW_TOOL_DATA not in prompt
    assert SHOULD_NOT_APPEAR_BUSINESS_CONTEXT not in prompt
    assert SHOULD_NOT_APPEAR_NESTED_REPR not in prompt


@pytest.mark.asyncio
async def test_slot_resolution_gate_candidate_only_input_does_not_satisfy_required_slots(monkeypatch):
    fake_llm = CapturingLLM(_slot_response())
    monkeypatch.setattr(slot_resolution_gate_module, "_get_llm", lambda: fake_llm)

    result = await slot_resolution_gate_module.slot_resolution_gate(
        _state(candidate_slots={"order_id": "ORD-CANDIDATE"})
    )

    assert result["extracted_slots"]["order_id"] is None
    assert result["active_slots"] == {}
    assert result["active_slot_metadata"] == {}
    assert result["missing_required_slots"] == [{"any_of": ["order_id", "refund_case_id"]}]
    assert result["routing_hints"]["missing_required_slots"] == [{"any_of": ["order_id", "refund_case_id"]}]
    assert result["slot_resolution_trace"]["candidate_slots"] == {"order_id": "ORD-CANDIDATE"}
    assert result["slot_resolution_trace"]["resolved_slots"] == {}
    assert result["slot_resolution_trace"]["route_decision"] == "clarification_gate"
    assert "missing_required_slots" in result["slot_resolution_trace"]["reason_codes"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "metric_id", "preset", "resource_type"),
    [
        ("今天有多少退款单", "refund_case_count", "today", "refund_case"),
        ("本周补偿券发了多少", "coupon_record_count", "this_week", "action_draft"),
    ],
)
async def test_slot_resolution_gate_deterministically_extracts_locked_metric_prompts(
    monkeypatch,
    query,
    metric_id,
    preset,
    resource_type,
) -> None:
    fake_llm = CapturingLLM(_slot_response())
    monkeypatch.setattr(slot_resolution_gate_module, "_get_llm", lambda: fake_llm)

    result = await slot_resolution_gate_module.slot_resolution_gate(_metric_state(query))

    assert result["extracted_slots"]["metric_id"] == metric_id
    assert result["active_slots"]["metric_id"] == metric_id
    assert result["active_slots"]["metric_time_preset"] == preset
    assert result["active_slots"]["resource_type"] == resource_type
    assert result["missing_required_slots"] == []
    assert result["slot_resolution_trace"]["route_decision"] == "investigate"
    assert "deterministic_metric_slot_parser" in result["slot_resolution_trace"]["reason_codes"]


@pytest.mark.asyncio
async def test_slot_resolution_gate_accepts_pending_ticket_current_snapshot_without_time_range(monkeypatch) -> None:
    fake_llm = CapturingLLM(_slot_response())
    monkeypatch.setattr(slot_resolution_gate_module, "_get_llm", lambda: fake_llm)

    result = await slot_resolution_gate_module.slot_resolution_gate(_metric_state("待处理工单有多少"))

    assert result["active_slots"]["metric_id"] == "pending_ticket_count"
    assert result["active_slots"]["metric_time_preset"] == "current_snapshot"
    assert result["active_slots"]["resource_type"] == "ticket"
    assert result["active_slots"]["status_filter"] == ["open", "in_progress"]
    assert result["missing_required_slots"] == []
    assert result["slot_resolution_trace"]["route_decision"] == "investigate"


@pytest.mark.asyncio
async def test_slot_resolution_gate_order_count_current_requires_time_not_order_id(monkeypatch) -> None:
    fake_llm = CapturingLLM(_slot_response(order_id="ORD-SHOULD-NOT-MATTER"))
    monkeypatch.setattr(slot_resolution_gate_module, "_get_llm", lambda: fake_llm)

    result = await slot_resolution_gate_module.slot_resolution_gate(_metric_state("当前有多少订单"))

    assert result["active_slots"]["metric_id"] == "order_count"
    assert result["active_slots"]["resource_type"] == "order"
    assert "order_id" not in result["active_slots"]
    assert result["missing_required_slots"] == [{"all_of": ["metric_time_range"]}]
    assert "metric_time_range_required" in result["slot_resolution_trace"]["reason_codes"]
    assert result["slot_resolution_trace"]["route_decision"] == "clarification_gate"


@pytest.mark.asyncio
async def test_slot_resolution_gate_merges_pending_metric_time_answer_with_active_flow(monkeypatch) -> None:
    fake_llm = CapturingLLM(_slot_response())
    monkeypatch.setattr(slot_resolution_gate_module, "_get_llm", lambda: fake_llm)

    result = await slot_resolution_gate_module.slot_resolution_gate(
        _metric_state(
            "本周",
            candidate_slots={
                "metric_id": "order_count",
                "resource_type": "order",
                "metric_time_preset": "this_week",
            },
            routing_hints={
                "workflow_state_resolution": "answered_pending_metric_time_range",
                "metric_slot_parser": "active_flow_state",
            },
            active_flow_state={
                "kind": "pending_required_slot",
                "resolved_slots": {"metric_id": "order_count", "resource_type": "order"},
            },
        )
    )

    assert result["active_slots"]["metric_id"] == "order_count"
    assert result["active_slots"]["resource_type"] == "order"
    assert result["active_slots"]["metric_time_preset"] == "this_week"
    assert result["active_slots"]["metric_time_range_start"] == "2026-07-06T00:00:00+08:00"
    assert result["active_slots"]["metric_time_range_end"] == "2026-07-13T00:00:00+08:00"
    assert result["missing_required_slots"] == []
    assert result["slot_resolution_trace"]["route_decision"] == "investigate"
    assert "deterministic_metric_slot_parser" in result["slot_resolution_trace"]["reason_codes"]


@pytest.mark.asyncio
async def test_slot_resolution_gate_records_current_inherited_and_replacement_provenance(monkeypatch):
    fake_llm = CapturingLLM(_slot_response(order_id="ORD-CURRENT"))
    monkeypatch.setattr(slot_resolution_gate_module, "_get_llm", lambda: fake_llm)
    state = _state(
        session_memory={
            "continuity_claimed": True,
            "active_slots": {"order_id": "ORD-SESSION", "refund_case_id": "RF-SESSION"},
            "slot_metadata": {
                "order_id": _trusted_metadata(),
                "refund_case_id": _trusted_metadata(),
            },
        }
    )

    result = await slot_resolution_gate_module.slot_resolution_gate(state)
    trace = result["slot_resolution_trace"]

    assert result["active_slots"] == {"order_id": "ORD-CURRENT", "refund_case_id": "RF-SESSION"}
    assert trace["explicit_current_turn_slots"]["order_id"]["value"] == "ORD-CURRENT"
    assert trace["inherited_session_slots"]["refund_case_id"]["value"] == "RF-SESSION"
    assert trace["conflicting_slots"]["order_id"]["current_value"] == "ORD-CURRENT"
    assert trace["conflicting_slots"]["order_id"]["inherited_value"] == "ORD-SESSION"
    assert trace["route_decision"] == "investigate"
    assert "accepted_inherited_session_slot" in trace["reason_codes"]
    assert "conflicting_slot_replaced_by_current_turn" in trace["reason_codes"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "state_overrides", "bucket", "reason_code"),
    [
        (
            "invalidated",
            {
                "user_query": "不是这个订单",
                "session_memory": {
                    "continuity_claimed": True,
                    "active_slots": {"order_id": "ORD-SESSION"},
                    "slot_metadata": {"order_id": _trusted_metadata()},
                },
            },
            "invalidated_slots",
            "slot_invalidated",
        ),
        (
            "stale",
            {
                "session_memory": {
                    "continuity_claimed": True,
                    "active_slots": {"order_id": "ORD-STALE"},
                    "slot_metadata": {"order_id": _trusted_metadata(expires_at="not-a-date")},
                },
            },
            "stale_slots",
            "stale_slot",
        ),
        (
            "incompatible",
            {
                "session_memory": {
                    "continuity_claimed": True,
                    "active_slots": {"order_id": "ORD-INCOMPATIBLE"},
                    "slot_metadata": {"order_id": _trusted_metadata(compatible_intents=["small_talk"])},
                },
            },
            "incompatible_slots",
            "intent_incompatible",
        ),
        (
            "unresolved_conflict",
            {
                "session_memory": {
                    "continuity_claimed": True,
                    "active_slots": {"order_id": "ORD-A"},
                    "slot_metadata": {
                        "order_id": _trusted_metadata(
                            slot_resolution_conflict={
                                "values": ["ORD-A", "ORD-B"],
                                "source": "trusted_session_memory",
                            }
                        )
                    },
                },
            },
            "conflicting_slots",
            "unresolved_inherited_slot_conflict",
        ),
    ],
)
async def test_slot_resolution_gate_records_rejected_inherited_categories(
    monkeypatch,
    name,
    state_overrides,
    bucket,
    reason_code,
):
    del name
    fake_llm = CapturingLLM(_slot_response())
    monkeypatch.setattr(slot_resolution_gate_module, "_get_llm", lambda: fake_llm)

    result = await slot_resolution_gate_module.slot_resolution_gate(_state(**state_overrides))
    trace = result["slot_resolution_trace"]

    assert result["active_slots"] == {}
    assert result["missing_required_slots"] == [{"any_of": ["order_id", "refund_case_id"]}]
    assert trace[bucket]["order_id"]["value"].startswith("ORD")
    assert trace["route_decision"] == "clarification_gate"
    assert reason_code in trace["reason_codes"]
    assert "missing_required_slots" in trace["reason_codes"]


@pytest.mark.asyncio
async def test_slot_resolution_gate_llm_validation_error_strictly_fails_closed(monkeypatch):
    fake_llm = CapturingLLM({"order_id": {"not": "a string"}})
    monkeypatch.setattr(slot_resolution_gate_module, "_get_llm", lambda: fake_llm)
    state = _state(
        session_memory={
            "continuity_claimed": True,
            "active_slots": {"order_id": "ORD-SESSION"},
            "slot_metadata": {"order_id": _trusted_metadata()},
        }
    )

    result = await slot_resolution_gate_module.slot_resolution_gate(state)

    assert result["extracted_slots"] == {}
    assert result["active_slots"] == {}
    assert result["active_slot_metadata"] == {}
    assert result["missing_required_slots"] == [{"any_of": ["order_id", "refund_case_id"]}]
    assert result["routing_hints"]["missing_required_slots"] == [{"any_of": ["order_id", "refund_case_id"]}]
    assert result["node_errors"][-1]["node"] == "slot_resolution_gate"
    assert result["trace_steps"][-1]["node"] == "slot_resolution_gate"
    assert result["slot_resolution_trace"]["route_decision"] == "clarification_gate"
    assert result["slot_resolution_trace"]["resolved_slots"] == {}
    assert "llm_slot_extraction_error" in result["slot_resolution_trace"]["reason_codes"]
    assert "accepted_inherited_session_slot" not in result["slot_resolution_trace"]["reason_codes"]

    merged_state = {**state, **result}
    assert route_after_slot_resolution(merged_state) == "clarification_gate"


def test_slot_resolution_metric_parser_uses_business_query_registry_metadata() -> None:
    source = Path("src/agent/nodes/slot_resolution_gate.py").read_text()

    assert "BUSINESS_QUERY_REGISTRY" in source
    for forbidden in (
        'slots["metric_id"] = "order_count"',
        'slots["metric_id"] = "refund_case_count"',
        'slots["metric_id"] = "pending_ticket_count"',
        'slots["metric_id"] = "coupon_record_count"',
        'slots["metric_id"] = "merchant_refund_rate"',
        'slots["metric_time_preset"] = "current_snapshot"',
    ):
        assert forbidden not in source
