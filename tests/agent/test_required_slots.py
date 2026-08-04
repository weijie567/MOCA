from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.agent.intent_policy import SLOT_POLICY_REGISTRY, SlotInheritanceContext
import src.agent.routing as routing_module
from src.agent.routing import (
    BUSINESS_DEMO_TIMEZONE,
    detect_slot_invalidations,
    missing_required_slots,
    resolve_slots_for_completeness,
    resolve_slots_with_metadata,
    route_after_slot_resolution,
)
from src.business.query.registry import BUSINESS_QUERY_REGISTRY


def _slot_policy_context(**overrides) -> SlotInheritanceContext:
    values = {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "intent": "refund_troubleshooting",
        "max_age_seconds": 3600,
        "current_time": datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return SlotInheritanceContext(**values)


def test_missing_required_slots_all_of_any_of_and_optional():
    missing = missing_required_slots(
        {"all_of": ["action_type"], "any_of": [["order_id", "refund_case_id"]], "optional": ["amount"]},
        {"order_id": "ORD-1"},
    )

    assert missing == [{"all_of": ["action_type"]}]
    assert missing_required_slots({"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []}, {}) == [
        {"any_of": ["order_id", "refund_case_id"]}
    ]


def test_slot_policy_registry_missing_required_slots_matches_router_shape():
    missing = SLOT_POLICY_REGISTRY.missing_required_slots(
        {"all_of": ["action_type"], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        {"order_id": "ORD-1"},
    )

    assert missing == [{"all_of": ["action_type"]}]


def test_slot_policy_registry_accepts_trusted_session_memory() -> None:
    decision = SLOT_POLICY_REGISTRY.accepts_inherited_slot(
        "order_id",
        {
            "source": "trusted_session_memory",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": "thread-1",
            "expires_at": "2026-06-28T12:05:00+00:00",
            "compatible_intents": ["refund_troubleshooting"],
        },
        _slot_policy_context(),
    )

    assert decision.accepted is True
    assert decision.reason_code == "accepted"
    assert decision.source == "trusted_session_memory"


def test_slot_policy_registry_rejects_invalidated_slot() -> None:
    decision = SLOT_POLICY_REGISTRY.accepts_inherited_slot(
        "order_id",
        {
            "source": "trusted_session_memory",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": "thread-1",
            "expires_at": "2026-06-28T12:05:00+00:00",
            "compatible_intents": ["refund_troubleshooting"],
        },
        _slot_policy_context(),
        invalidation={"slot": "order_id", "reason": "negated_or_switched_context"},
    )

    assert decision.accepted is False
    assert decision.reason_code == "slot_invalidated"
    assert decision.source == "trusted_session_memory"


def test_slot_policy_registry_rejects_untrusted_scope_stale_and_incompatible_slots() -> None:
    base = {
        "source": "trusted_session_memory",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "expires_at": "2026-06-28T12:05:00+00:00",
        "compatible_intents": ["refund_troubleshooting"],
    }
    cases = [
        ({}, "missing_metadata", None),
        ({**base, "source": "raw_memory"}, "untrusted_source", "raw_memory"),
        ({**base, "tenant_id": "wrong-tenant"}, "tenant_mismatch", "trusted_session_memory"),
        ({**base, "user_id": "wrong-user"}, "user_mismatch", "trusted_session_memory"),
        ({**base, "thread_id": "wrong-thread"}, "thread_mismatch", "trusted_session_memory"),
        ({**base, "expires_at": "2026-06-28T11:59:00+00:00"}, "stale_slot", "trusted_session_memory"),
        ({**base, "expires_at": "not-a-date"}, "stale_slot", "trusted_session_memory"),
        ({**base, "compatible_intents": ["small_talk"]}, "intent_incompatible", "trusted_session_memory"),
    ]

    for metadata, reason_code, source in cases:
        decision = SLOT_POLICY_REGISTRY.accepts_inherited_slot(
            "order_id",
            metadata,
            _slot_policy_context(),
        )

        assert decision.accepted is False
        assert decision.reason_code == reason_code
        assert decision.source == source


def test_candidate_slots_and_stale_active_slots_do_not_satisfy_policy():
    state = {
        "primary_intent": "refund_troubleshooting",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "candidate_slots": {"order_id": "ORD-1"},
        "active_slots": {"order_id": "ORD-STALE", "refund_case_id": "RF-STALE"},
        "extracted_slots": {},
        "session_memory": {"continuity_claimed": False, "active_slots": {"refund_case_id": "RF-SESSION-STALE"}},
    }

    assert route_after_slot_resolution(state) == "clarification_gate"


def test_session_memory_continuity_claimed_without_metadata_fails_closed():
    state = {
        "primary_intent": "refund_troubleshooting",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "extracted_slots": {},
        "session_memory": {"continuity_claimed": True, "active_slots": {"order_id": "ORD-NO-META"}},
    }

    assert resolve_slots_for_completeness(state) == {}
    assert route_after_slot_resolution(state) == "clarification_gate"


def test_trusted_session_memory_synthetic_hook_and_current_turn_override():
    state = {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "primary_intent": "refund_troubleshooting",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "extracted_slots": {"order_id": "ORD-CURRENT"},
        "session_memory": {
            "continuity_claimed": True,
            "active_slots": {"order_id": "ORD-SESSION", "refund_case_id": "RF-SESSION"},
            "slot_metadata": {
                "refund_case_id": {
                    "source": "trusted_session_memory",
                    "tenant_id": "tenant-1",
                    "user_id": "user-1",
                    "thread_id": "thread-1",
                    "fresh": True,
                    "intent_compatible": True,
                }
            },
        },
    }

    resolved = resolve_slots_for_completeness(state)
    assert resolved["order_id"] == "ORD-CURRENT"
    assert resolved["refund_case_id"] == "RF-SESSION"
    assert route_after_slot_resolution(state) == "investigate"


def _trusted_state(metadata_updates: dict | None = None, *, value: str = "ORD-SESSION") -> dict:
    metadata = {
        "source": "trusted_session_memory",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "fresh": True,
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "compatible_intents": ["refund_troubleshooting"],
    }
    metadata.update(metadata_updates or {})
    return {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "primary_intent": "refund_troubleshooting",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "extracted_slots": {},
        "session_memory": {
            "continuity_claimed": True,
            "active_slots": {"order_id": value},
            "slot_metadata": {"order_id": metadata},
        },
    }


def _pre_intent_slot_metadata(
    *,
    compatible_intents: list[str],
    intent_compatible: bool = False,
) -> dict:
    return {
        "source": "trusted_session_memory",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "fresh": True,
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "compatible_intents": compatible_intents,
        "intent_compatible": intent_compatible,
        "intent_filter_applied": False,
    }


def test_trusted_session_memory_rejects_wrong_tenant_user_thread_expired_and_incompatible():
    cases = [
        {"tenant_id": "wrong-tenant"},
        {"user_id": "wrong-user"},
        {"thread_id": "wrong-thread"},
        {"fresh": False, "expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
        {"compatible_intents": ["small_talk"], "intent_compatible": False},
        {"expires_at": "not-a-date"},
        {"compatible_intents": [], "intent_compatible": False},
    ]

    for metadata_update in cases:
        state = _trusted_state(metadata_update)
        assert resolve_slots_for_completeness(state) == {}
        assert route_after_slot_resolution(state) == "clarification_gate"


def test_pre_intent_session_context_rejects_incompatible_non_business_slot():
    state = {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "primary_intent": "action_request",
        "required_slots": {"all_of": ["action_type"], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "extracted_slots": {"order_id": "ORD-CURRENT"},
        "session_context": {
            "slot_continuity": {
                "continuity_claimed": True,
                "active_slots": {"action_type": "issue_coupon"},
                "slot_metadata": {
                    "action_type": _pre_intent_slot_metadata(
                        compatible_intents=["compensation_suggestion"],
                        intent_compatible=True,
                    )
                },
            }
        },
    }

    resolved, metadata = resolve_slots_with_metadata(state)

    assert resolved == {"order_id": "ORD-CURRENT"}
    assert "action_type" not in metadata
    assert route_after_slot_resolution(state) == "clarification_gate"


def test_pre_intent_session_context_preserves_cross_intent_business_id_slot():
    state = {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "primary_intent": "action_request",
        "required_slots": {"all_of": ["action_type"], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "extracted_slots": {"action_type": "issue_coupon"},
        "session_context": {
            "slot_continuity": {
                "continuity_claimed": True,
                "active_slots": {"order_id": "ORD-PRE-INTENT"},
                "slot_metadata": {
                    "order_id": _pre_intent_slot_metadata(
                        compatible_intents=["refund_troubleshooting"],
                    )
                },
            }
        },
    }

    resolved, metadata = resolve_slots_with_metadata(state)

    assert resolved == {"action_type": "issue_coupon", "order_id": "ORD-PRE-INTENT"}
    assert metadata["order_id"]["source"] == "trusted_session_memory"
    assert route_after_slot_resolution(state) == "investigate"


def test_trusted_session_memory_explicit_override_wins():
    state = _trusted_state(value="ORD-SESSION")
    state["extracted_slots"] = {"order_id": "ORD-CURRENT"}

    resolved = resolve_slots_for_completeness(state)

    assert resolved["order_id"] == "ORD-CURRENT"
    assert route_after_slot_resolution(state) == "investigate"


def test_slot_invalidation_prevents_trusted_session_inheritance():
    state = _trusted_state(value="ORD-SESSION")
    state["user_query"] = "不是这个订单"

    resolved, metadata = resolve_slots_with_metadata(state)

    assert "order_id" not in resolved
    assert metadata["order_id"]["source"] == "invalidated_trusted_session_memory"
    assert metadata["order_id"]["invalidated_by_current_query"] is True
    assert route_after_slot_resolution(state) == "clarification_gate"


def test_rejected_stale_inherited_slot_resolution_is_idempotent_on_second_pass():
    state = _trusted_state(
        {"fresh": False, "expires_at": (datetime(2026, 6, 28, 11, 59, tzinfo=UTC)).isoformat()},
        value="ORD-STALE",
    )
    state["run_started_at"] = "2026-06-28T12:00:00+00:00"

    first_resolved, first_metadata = resolve_slots_with_metadata(state)
    state["active_slots"] = first_resolved
    state["active_slot_metadata"] = first_metadata
    second_resolved, second_metadata = resolve_slots_with_metadata(state)

    assert first_resolved == {}
    assert second_resolved == {}
    assert "order_id" not in first_metadata
    assert "order_id" not in second_metadata
    assert route_after_slot_resolution(state) == "clarification_gate"


def test_current_turn_slot_replaces_invalidated_session_slot_with_provenance():
    state = _trusted_state(value="ORD-SESSION")
    state["user_query"] = "不是这个订单，是 ORD-CURRENT"
    state["run_started_at"] = "2026-06-21T10:00:00+00:00"
    state["extracted_slots"] = {"order_id": "ORD-CURRENT"}

    resolved, metadata = resolve_slots_with_metadata(state)

    assert resolved["order_id"] == "ORD-CURRENT"
    assert metadata["order_id"]["source"] == "current_turn"
    assert metadata["order_id"]["provenance_source"] == "current_query"
    assert metadata["order_id"]["observed_at"] == "2026-06-21T10:00:00+00:00"
    assert metadata["order_id"]["previous_trusted_session_value"] == "ORD-SESSION"
    assert metadata["order_id"]["slot_invalidation"]["slot"] == "order_id"
    assert route_after_slot_resolution(state) == "investigate"


def test_detect_slot_invalidations_for_refund_and_broad_switches():
    assert set(detect_slot_invalidations("换成刚才那个退款单")) == {"refund_case_id"}
    assert set(detect_slot_invalidations("不是这个，是另一个")) == {"order_id", "refund_case_id", "ticket_id"}


def test_required_slots_mismatch_fails_closed():
    assert (
        route_after_slot_resolution(
            {
                "primary_intent": "refund_troubleshooting",
                "required_slots": {"all_of": ["forged"], "any_of": [], "optional": []},
                "extracted_slots": {"order_id": "ORD-1"},
            }
        )
        == "clarification_gate"
    )


def _slot_resolution(state: dict) -> dict:
    return routing_module.resolve_slots_with_provenance(state)


def _metric_state(**overrides) -> dict:
    state = {
        "primary_intent": "business_metric_query",
        "requested_operation": "read_status",
        "required_slots": {"all_of": ["metric_id"], "any_of": [], "optional": []},
        "run_started_at": "2026-07-09T04:30:00+00:00",
        "extracted_slots": {},
        "candidate_slots": {},
        "session_memory": {"continuity_claimed": False},
    }
    state.update(overrides)
    return state


def test_metric_slot_policy_uses_business_query_registry_source_of_truth() -> None:
    source = Path("src/agent/routing.py").read_text()

    assert "BUSINESS_QUERY_REGISTRY" in source
    assert routing_module.SUPPORTED_METRIC_IDS == BUSINESS_QUERY_REGISTRY.metric_ids()
    for forbidden in (
        "SUPPORTED_METRIC_IDS = frozenset(",
        "METRIC_RESOURCE_TYPES:",
        "METRIC_STATUS_ALLOWLISTS:",
        "METRIC_EVENT_OR_RATE_IDS",
    ):
        assert forbidden not in source


def test_metric_slot_policy_locks_metric_ids_and_candidate_hints_do_not_satisfy() -> None:
    candidate_only = _metric_state(candidate_slots={"metric_id": "order_count", "metric_time_preset": "today"})
    unsupported = _metric_state(extracted_slots={"metric_id": "gross_margin"})

    candidate_result = _slot_resolution(candidate_only)
    unsupported_result = _slot_resolution(unsupported)

    assert candidate_result["resolved_slots"] == {}
    assert candidate_result["missing_required_slots"] == [{"all_of": ["metric_id"]}]
    assert route_after_slot_resolution(candidate_only) == "clarification_gate"

    assert unsupported_result["resolved_slots"] == {}
    assert unsupported_result["missing_required_slots"] == [{"all_of": ["metric_id"]}]
    assert "unsupported_metric_id" in unsupported_result["slot_resolution_trace"]["reason_codes"]


def test_metric_time_presets_use_business_demo_timezone_boundaries() -> None:
    assert str(BUSINESS_DEMO_TIMEZONE) == "Asia/Shanghai"

    cases = [
        ("today", "2026-07-09T00:00:00+08:00", "2026-07-10T00:00:00+08:00"),
        ("this_week", "2026-07-06T00:00:00+08:00", "2026-07-13T00:00:00+08:00"),
        ("this_month", "2026-07-01T00:00:00+08:00", "2026-08-01T00:00:00+08:00"),
        ("this_quarter", "2026-07-01T00:00:00+08:00", "2026-10-01T00:00:00+08:00"),
        ("this_year", "2026-01-01T00:00:00+08:00", "2027-01-01T00:00:00+08:00"),
    ]

    for preset, start, end in cases:
        state = _metric_state(extracted_slots={"metric_id": "refund_case_count", "metric_time_preset": preset})
        result = _slot_resolution(state)

        assert result["resolved_slots"]["metric_time_range_start"] == start
        assert result["resolved_slots"]["metric_time_range_end"] == end
        assert result["resolved_slots"]["resource_type"] == "refund_case"
        assert result["route_decision"] == "investigate"


def test_metric_explicit_time_range_is_inclusive_start_exclusive_end_and_validated() -> None:
    valid = _metric_state(
        extracted_slots={
            "metric_id": "coupon_record_count",
            "metric_time_range_start": "2026-07-01",
            "metric_time_range_end": "2026-07-08",
        }
    )
    reversed_range = _metric_state(
        extracted_slots={
            "metric_id": "refund_case_count",
            "metric_time_range_start": "2026-07-08",
            "metric_time_range_end": "2026-07-01",
        }
    )
    future_range = _metric_state(
        extracted_slots={
            "metric_id": "order_count",
            "metric_time_range_start": "2026-07-10",
            "metric_time_range_end": "2026-07-11",
        }
    )

    valid_result = _slot_resolution(valid)
    reversed_result = _slot_resolution(reversed_range)
    future_result = _slot_resolution(future_range)

    assert valid_result["resolved_slots"]["metric_time_range_start"] == "2026-07-01T00:00:00+08:00"
    assert valid_result["resolved_slots"]["metric_time_range_end"] == "2026-07-08T00:00:00+08:00"
    assert valid_result["route_decision"] == "investigate"

    assert reversed_result["missing_required_slots"] == [{"all_of": ["metric_time_range"]}]
    assert "invalid_metric_time_range" in reversed_result["slot_resolution_trace"]["reason_codes"]
    assert future_result["missing_required_slots"] == [{"all_of": ["metric_time_range"]}]
    assert "future_metric_time_range" in future_result["slot_resolution_trace"]["reason_codes"]


def test_metric_conditional_completeness_for_snapshot_event_and_rate_metrics() -> None:
    pending_ticket = _metric_state(extracted_slots={"metric_id": "pending_ticket_count"})
    current_orders = _metric_state(
        extracted_slots={"metric_id": "order_count", "metric_time_preset": "current_snapshot"}
    )
    merchant_rate_missing = _metric_state(extracted_slots={"metric_id": "merchant_refund_rate"})
    merchant_rate_complete = _metric_state(
        extracted_slots={
            "metric_id": "merchant_refund_rate",
            "merchant_id": "merchant-a",
            "metric_time_preset": "this_month",
        }
    )

    pending_result = _slot_resolution(pending_ticket)
    current_orders_result = _slot_resolution(current_orders)
    merchant_missing_result = _slot_resolution(merchant_rate_missing)
    merchant_complete_result = _slot_resolution(merchant_rate_complete)

    assert pending_result["resolved_slots"]["metric_id"] == "pending_ticket_count"
    assert pending_result["resolved_slots"]["resource_type"] == "ticket"
    assert pending_result["resolved_slots"]["metric_time_preset"] == "current_snapshot"
    assert pending_result["resolved_slots"]["status_filter"] == ["open", "in_progress"]
    assert pending_result["route_decision"] == "investigate"

    assert current_orders_result["resolved_slots"]["metric_id"] == "order_count"
    assert current_orders_result["resolved_slots"]["resource_type"] == "order"
    assert current_orders_result["missing_required_slots"] == [{"all_of": ["metric_time_range"]}]
    assert "metric_time_range_required" in current_orders_result["slot_resolution_trace"]["reason_codes"]

    assert merchant_missing_result["missing_required_slots"] == [
        {"all_of": ["merchant_filter"]},
        {"all_of": ["metric_time_range"]},
    ]
    assert merchant_complete_result["resolved_slots"]["resource_type"] == "merchant_metric"
    assert merchant_complete_result["route_decision"] == "investigate"


def test_metric_status_filters_are_metric_specific_and_never_arbitrary_text() -> None:
    accepted_order_status = _metric_state(
        extracted_slots={"metric_id": "order_count", "metric_time_preset": "today", "status_filter": "paid"}
    )
    rejected_order_status = _metric_state(
        extracted_slots={"metric_id": "order_count", "metric_time_preset": "today", "status_filter": "cancelled"}
    )
    rejected_rate_status = _metric_state(
        extracted_slots={
            "metric_id": "merchant_refund_rate",
            "merchant_id": "merchant-a",
            "metric_time_preset": "today",
            "status_filter": "approved",
        }
    )

    accepted_result = _slot_resolution(accepted_order_status)
    rejected_order_result = _slot_resolution(rejected_order_status)
    rejected_rate_result = _slot_resolution(rejected_rate_status)

    assert accepted_result["resolved_slots"]["status_filter"] == "paid"
    assert accepted_result["route_decision"] == "investigate"
    assert "status_filter" not in rejected_order_result["resolved_slots"]
    assert rejected_order_result["missing_required_slots"] == [{"all_of": ["metric_status_filter"]}]
    assert "unsupported_metric_status_filter" in rejected_order_result["slot_resolution_trace"]["reason_codes"]
    assert "status_filter" not in rejected_rate_result["resolved_slots"]
    assert rejected_rate_result["missing_required_slots"] == [{"all_of": ["metric_status_filter"]}]


def test_slot_resolution_trace_records_explicit_current_turn_slot():
    state = {
        "primary_intent": "refund_troubleshooting",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "extracted_slots": {"order_id": "ORD-CURRENT"},
        "candidate_slots": {"order_id": "ORD-CANDIDATE"},
    }

    result = _slot_resolution(state)
    trace = result["slot_resolution_trace"]

    assert result["resolved_slots"]["order_id"] == "ORD-CURRENT"
    assert trace["schema"] == "slot_resolution_trace.phase54"
    assert trace["policy_owner"] == "SlotPolicyRegistry"
    assert trace["extracted_slots"]["order_id"] == "ORD-CURRENT"
    assert trace["candidate_slots"]["order_id"] == "ORD-CANDIDATE"
    assert trace["explicit_current_turn_slots"]["order_id"]["value"] == "ORD-CURRENT"
    assert trace["resolved_slots"]["order_id"] == "ORD-CURRENT"
    assert trace["route_decision"] == "investigate"
    assert "explicit_current_turn" in trace["reason_codes"]


def test_slot_resolution_trace_records_accepted_inherited_slot():
    result = _slot_resolution(_trusted_state(value="ORD-SESSION"))
    trace = result["slot_resolution_trace"]

    assert result["resolved_slots"]["order_id"] == "ORD-SESSION"
    assert trace["inherited_session_slots"]["order_id"]["value"] == "ORD-SESSION"
    assert trace["route_decision"] == "investigate"
    assert "accepted_inherited_session_slot" in trace["reason_codes"]


def test_slot_resolution_trace_records_invalidated_slot_and_missing_route():
    state = _trusted_state(value="ORD-SESSION")
    state["user_query"] = "不是这个订单"

    result = _slot_resolution(state)
    trace = result["slot_resolution_trace"]

    assert "order_id" not in result["resolved_slots"]
    assert trace["invalidated_slots"]["order_id"]["value"] == "ORD-SESSION"
    assert trace["missing_required_slots"] == [{"any_of": ["order_id", "refund_case_id"]}]
    assert result["missing_required_slots"] == [{"any_of": ["order_id", "refund_case_id"]}]
    assert routing_module.route_after_slot_resolution(state) == "clarification_gate"
    assert "slot_invalidated" in trace["reason_codes"]
    assert "missing_required_slots" in trace["reason_codes"]


def test_slot_resolution_trace_records_stale_and_incompatible_inherited_slots():
    stale = _trusted_state({"expires_at": "not-a-date"}, value="ORD-STALE")
    incompatible = _trusted_state({"compatible_intents": ["small_talk"]}, value="ORD-INCOMPATIBLE")

    stale_result = _slot_resolution(stale)
    incompatible_result = _slot_resolution(incompatible)

    assert "order_id" not in stale_result["resolved_slots"]
    assert stale_result["slot_resolution_trace"]["stale_slots"]["order_id"]["value"] == "ORD-STALE"
    assert stale_result["slot_resolution_trace"]["route_decision"] == "clarification_gate"
    assert "stale_slot" in stale_result["slot_resolution_trace"]["reason_codes"]
    assert routing_module.route_after_slot_resolution(stale) == "clarification_gate"

    assert "order_id" not in incompatible_result["resolved_slots"]
    assert incompatible_result["slot_resolution_trace"]["incompatible_slots"]["order_id"]["value"] == "ORD-INCOMPATIBLE"
    assert incompatible_result["slot_resolution_trace"]["route_decision"] == "clarification_gate"
    assert "intent_incompatible" in incompatible_result["slot_resolution_trace"]["reason_codes"]
    assert routing_module.route_after_slot_resolution(incompatible) == "clarification_gate"


def test_slot_resolution_trace_records_validated_current_turn_replacement_conflict():
    state = _trusted_state(value="ORD-SESSION")
    state["extracted_slots"] = {"order_id": "ORD-CURRENT"}

    result = _slot_resolution(state)
    trace = result["slot_resolution_trace"]

    assert result["resolved_slots"]["order_id"] == "ORD-CURRENT"
    assert trace["conflicting_slots"]["order_id"]["current_value"] == "ORD-CURRENT"
    assert trace["conflicting_slots"]["order_id"]["inherited_value"] == "ORD-SESSION"
    assert trace["explicit_current_turn_slots"]["order_id"]["value"] == "ORD-CURRENT"
    assert trace["route_decision"] == "investigate"
    assert "conflicting_slot_replaced_by_current_turn" in trace["reason_codes"]


def test_slot_resolution_trace_rejects_unresolved_trusted_session_conflict_marker():
    state = _trusted_state(
        {
            "slot_resolution_conflict": {
                "values": ["ORD-A", "ORD-B"],
                "source": "trusted_session_memory",
            }
        },
        value="ORD-A",
    )

    result = _slot_resolution(state)
    trace = result["slot_resolution_trace"]

    assert "order_id" not in result["resolved_slots"]
    assert "order_id" not in result["slot_metadata"]
    assert trace["conflicting_slots"]["order_id"]["values"] == ["ORD-A", "ORD-B"]
    assert trace["conflicting_slots"]["order_id"]["source"] == "trusted_session_memory"
    assert "slot_resolution_conflict" not in result["slot_metadata"].get("order_id", {})
    assert trace["route_decision"] == "clarification_gate"
    assert routing_module.route_after_slot_resolution(state) == "clarification_gate"
    assert "unresolved_inherited_slot_conflict" in trace["reason_codes"]


def test_slot_resolution_trace_records_missing_required_slots():
    state = {
        "primary_intent": "action_request",
        "required_slots": {"all_of": ["action_type"], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "extracted_slots": {"order_id": "ORD-1"},
    }

    result = _slot_resolution(state)

    assert result["resolved_slots"] == {"order_id": "ORD-1"}
    assert result["missing_required_slots"] == [{"all_of": ["action_type"]}]
    assert result["slot_resolution_trace"]["missing_required_slots"] == [{"all_of": ["action_type"]}]
    assert result["slot_resolution_trace"]["route_decision"] == "clarification_gate"
    assert "missing_required_slots" in result["slot_resolution_trace"]["reason_codes"]


def test_slot_resolution_trace_keeps_candidate_slots_candidate_only():
    state = {
        "primary_intent": "refund_troubleshooting",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "candidate_slots": {"order_id": "ORD-CANDIDATE"},
        "extracted_slots": {},
    }

    result = _slot_resolution(state)

    assert result["slot_resolution_trace"]["candidate_slots"] == {"order_id": "ORD-CANDIDATE"}
    assert result["resolved_slots"] == {}
    assert "order_id" not in result["slot_resolution_trace"]["resolved_slots"]
    assert result["slot_resolution_trace"]["route_decision"] == "clarification_gate"
    assert routing_module.route_after_slot_resolution(state) == "clarification_gate"


def test_slot_resolution_trace_preserves_wr01_non_business_rejection_and_business_id_acceptance():
    non_business_state = {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "primary_intent": "action_request",
        "required_slots": {"all_of": ["action_type"], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "extracted_slots": {"order_id": "ORD-CURRENT"},
        "session_context": {
            "slot_continuity": {
                "continuity_claimed": True,
                "active_slots": {"action_type": "issue_coupon"},
                "slot_metadata": {
                    "action_type": _pre_intent_slot_metadata(
                        compatible_intents=["compensation_suggestion"],
                        intent_compatible=True,
                    )
                },
            }
        },
    }
    business_id_state = {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "primary_intent": "compensation_suggestion",
        "required_slots": {
            "all_of": ["action_type"],
            "any_of": [["order_id", "refund_case_id", "ticket_id"]],
            "optional": ["amount"],
        },
        "extracted_slots": {"action_type": "issue_coupon"},
        "session_context": {
            "slot_continuity": {
                "continuity_claimed": True,
                "active_slots": {
                    "order_id": "ORD-PRE-INTENT",
                    "refund_case_id": "RF-PRE-INTENT",
                    "ticket_id": "TKT-PRE-INTENT",
                },
                "slot_metadata": {
                    "order_id": _pre_intent_slot_metadata(compatible_intents=["refund_troubleshooting"]),
                    "refund_case_id": _pre_intent_slot_metadata(compatible_intents=["refund_troubleshooting"]),
                    "ticket_id": _pre_intent_slot_metadata(compatible_intents=["ticket_reply_draft"]),
                },
            }
        },
    }

    non_business = _slot_resolution(non_business_state)
    business_id = _slot_resolution(business_id_state)

    assert "action_type" not in non_business["resolved_slots"]
    assert non_business["slot_resolution_trace"]["incompatible_slots"]["action_type"]["value"] == "issue_coupon"
    assert routing_module.route_after_slot_resolution(non_business_state) == "clarification_gate"

    assert business_id["resolved_slots"] == {
        "action_type": "issue_coupon",
        "order_id": "ORD-PRE-INTENT",
        "refund_case_id": "RF-PRE-INTENT",
        "ticket_id": "TKT-PRE-INTENT",
    }
    for slot in ("order_id", "refund_case_id", "ticket_id"):
        assert (
            business_id["slot_resolution_trace"]["inherited_session_slots"][slot]["value"]
            == business_id["resolved_slots"][slot]
        )
    assert routing_module.route_after_slot_resolution(business_id_state) == "investigate"


def test_current_turn_business_id_replacement_records_cross_intent_conflict_provenance():
    state = {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "thread_id": "thread-1",
        "primary_intent": "compensation_suggestion",
        "required_slots": {
            "all_of": ["action_type"],
            "any_of": [["order_id", "refund_case_id", "ticket_id"]],
            "optional": ["amount"],
        },
        "extracted_slots": {"action_type": "issue_coupon", "order_id": "ORD-CURRENT"},
        "session_context": {
            "slot_continuity": {
                "continuity_claimed": True,
                "active_slots": {"order_id": "ORD-INHERITED"},
                "slot_metadata": {"order_id": _pre_intent_slot_metadata(compatible_intents=["refund_troubleshooting"])},
            }
        },
    }

    result = _slot_resolution(state)
    trace = result["slot_resolution_trace"]

    assert result["resolved_slots"]["order_id"] == "ORD-CURRENT"
    assert result["slot_metadata"]["order_id"]["previous_trusted_session_value"] == "ORD-INHERITED"
    assert trace["conflicting_slots"]["order_id"] == {
        "current_value": "ORD-CURRENT",
        "inherited_value": "ORD-INHERITED",
        "source": "trusted_session_memory",
        "resolution": "current_turn_replacement",
    }
    assert "conflicting_slot_replaced_by_current_turn" in trace["reason_codes"]
    assert routing_module.route_after_slot_resolution(state) == "investigate"


def test_legacy_slot_route_delegate_is_not_public_current_route_authority():
    legacy_route_helper = "".join(("route_after_", "slots"))
    state = _trusted_state(value="ORD-SESSION")

    assert routing_module.route_after_slot_resolution(state) == "investigate"
    assert not hasattr(routing_module, legacy_route_helper)
