from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
import pytest

from src.agent.nodes import slot_resolution_gate as slot_resolution_gate_module
from src.agent.routing import route_after_slot_resolution


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
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
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
