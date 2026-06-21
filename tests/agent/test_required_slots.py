from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.agent.routing import (
    detect_slot_invalidations,
    missing_required_slots,
    resolve_slots_for_completeness,
    resolve_slots_with_metadata,
    route_after_slots,
)


def test_missing_required_slots_all_of_any_of_and_optional():
    missing = missing_required_slots(
        {"all_of": ["action_type"], "any_of": [["order_id", "refund_case_id"]], "optional": ["amount"]},
        {"order_id": "ORD-1"},
    )

    assert missing == [{"all_of": ["action_type"]}]
    assert missing_required_slots({"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []}, {}) == [
        {"any_of": ["order_id", "refund_case_id"]}
    ]


def test_candidate_slots_and_stale_active_slots_do_not_satisfy_policy():
    state = {
        "primary_intent": "refund_troubleshooting",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "candidate_slots": {"order_id": "ORD-1"},
        "active_slots": {"order_id": "ORD-STALE", "refund_case_id": "RF-STALE"},
        "extracted_slots": {},
        "session_memory": {"continuity_claimed": False, "active_slots": {"refund_case_id": "RF-SESSION-STALE"}},
    }

    assert route_after_slots(state) == "clarification_gate"


def test_session_memory_continuity_claimed_without_metadata_fails_closed():
    state = {
        "primary_intent": "refund_troubleshooting",
        "required_slots": {"all_of": [], "any_of": [["order_id", "refund_case_id"]], "optional": []},
        "extracted_slots": {},
        "session_memory": {"continuity_claimed": True, "active_slots": {"order_id": "ORD-NO-META"}},
    }

    assert resolve_slots_for_completeness(state) == {}
    assert route_after_slots(state) == "clarification_gate"


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
    assert route_after_slots(state) == "investigate"


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


def test_trusted_session_memory_rejects_wrong_tenant_user_thread_expired_and_incompatible():
    cases = [
        {"tenant_id": "wrong-tenant"},
        {"user_id": "wrong-user"},
        {"thread_id": "wrong-thread"},
        {"fresh": False, "expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
        {"compatible_intents": ["order_status_inquiry"], "intent_compatible": False},
        {"expires_at": "not-a-date"},
        {"compatible_intents": [], "intent_compatible": False},
    ]

    for metadata_update in cases:
        state = _trusted_state(metadata_update)
        assert resolve_slots_for_completeness(state) == {}
        assert route_after_slots(state) == "clarification_gate"


def test_trusted_session_memory_explicit_override_wins():
    state = _trusted_state(value="ORD-SESSION")
    state["extracted_slots"] = {"order_id": "ORD-CURRENT"}

    resolved = resolve_slots_for_completeness(state)

    assert resolved["order_id"] == "ORD-CURRENT"
    assert route_after_slots(state) == "investigate"


def test_slot_invalidation_prevents_trusted_session_inheritance():
    state = _trusted_state(value="ORD-SESSION")
    state["user_query"] = "不是这个订单"

    resolved, metadata = resolve_slots_with_metadata(state)

    assert "order_id" not in resolved
    assert metadata["order_id"]["source"] == "invalidated_trusted_session_memory"
    assert metadata["order_id"]["invalidated_by_current_query"] is True
    assert route_after_slots(state) == "clarification_gate"


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
    assert route_after_slots(state) == "investigate"


def test_detect_slot_invalidations_for_refund_and_broad_switches():
    assert set(detect_slot_invalidations("换成刚才那个退款单")) == {"refund_case_id"}
    assert set(detect_slot_invalidations("不是这个，是另一个")) == {"order_id", "refund_case_id", "ticket_id"}


def test_required_slots_mismatch_fails_closed():
    assert (
        route_after_slots(
            {
                "primary_intent": "refund_troubleshooting",
                "required_slots": {"all_of": ["forged"], "any_of": [], "optional": []},
                "extracted_slots": {"order_id": "ORD-1"},
            }
        )
        == "clarification_gate"
    )
