from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
import uuid

from src.memory.case_working_context_lifecycle import (
    CaseWorkingContextLifecycleAdapter,
    build_active_cwc_payload,
    skipped_status,
    trusted_case_ref_from_state,
)


def test_trusted_case_ref_from_state_uses_active_slots_first() -> None:
    state = {
        "active_slots": {"refund_case_id": "RF-1"},
        "extracted_slots": {"refund_case_id": "RF-2"},
    }

    assert trusted_case_ref_from_state(state) == "RF-1"
    assert CaseWorkingContextLifecycleAdapter().trusted_case_ref_from_state(state) == "RF-1"


def test_trusted_case_ref_from_state_ignores_untrusted_memory_and_candidate_slots() -> None:
    state = {
        "candidate_slots": {"refund_case_id": "RF-CANDIDATE"},
        "session_memory": {"active_slots": {"refund_case_id": "RF-SESSION"}},
        "case_memory": [{"refund_case_id": "RF-CASE-MEMORY"}],
        "memory_context": {"case_items": [{"refund_case_id": "RF-MEMORY-CONTEXT"}]},
    }

    assert trusted_case_ref_from_state(state) is None


def test_trusted_case_ref_from_state_uses_extracted_slots_before_business_context() -> None:
    state = {
        "active_slots": {},
        "extracted_slots": {"refund_case_id": "RF-EXTRACTED"},
        "business_context": {"refund_case": {"refund_case_no": "RF-BUSINESS"}},
    }

    assert trusted_case_ref_from_state(state, include_business_context=True) == "RF-EXTRACTED"


def test_trusted_case_ref_from_state_accepts_business_context_only_when_enabled_in_order() -> None:
    state = {
        "business_context": {
            "refund_case": {
                "refund_case_no": "RF-NO",
                "refund_case_id": "RF-ID",
                "id": "RF-UUID",
            }
        }
    }

    assert trusted_case_ref_from_state(state) is None
    assert trusted_case_ref_from_state(state, include_business_context=True) == "RF-NO"

    no_case_no = {"business_context": {"refund_case": {"refund_case_id": "RF-ID", "id": "RF-UUID"}}}
    assert trusted_case_ref_from_state(no_case_no, include_business_context=True) == "RF-ID"

    only_id = {"business_context": {"refund_case": {"id": "RF-UUID"}}}
    assert trusted_case_ref_from_state(only_id, include_business_context=True) == "RF-UUID"


def test_build_active_cwc_payload_projects_hydrated_content_and_contextual_ref() -> None:
    tenant_id = uuid.uuid4()
    case_id = uuid.uuid4()
    memory_id = uuid.uuid4()
    run_id = uuid.uuid4()
    source_ref = {
        "source_type": "run_auto",
        "agent_run_id": str(run_id),
        "business_object_type": "refund_case",
        "business_object_id": str(case_id),
    }
    row = SimpleNamespace(
        id=memory_id,
        tenant_id=tenant_id,
        case_id=case_id,
        customer_request="用户询问退款进度",
        issue_type="refund_status",
        claims_json=[
            {
                "text": "用户称商品破损",
                "verified": False,
                "source_ref": source_ref,
            }
        ],
        verified_facts_json=[
            {
                "text": "退款单状态为 reviewing",
                "source_ref": source_ref,
                "observed_at": datetime(2026, 7, 3, 8, 0, tzinfo=UTC),
            }
        ],
        missing_info_json=["需要补充破损照片"],
        evidence_refs_json=[
            {"ref_type": "tool_result", "ref_id": "tool-result-1", "summary": "退款单状态为 reviewing"}
        ],
        actions_taken_json=[{"action": "查询退款单状态", "source_ref": source_ref}],
        policy_refs_json=[{"doc_id": "refund-policy", "chunk_id": "refund-policy#001", "version": "v1"}],
        agent_recommendations_json=[{"recommended_step": "要求用户上传照片", "staff_decision": None}],
        pending_tasks_json=["等待用户上传照片"],
        commitments_json=[{"text": "24 小时内回复用户", "confirmed_by_staff": True, "source_ref": source_ref}],
        next_action_json={"recommended_step": "发送照片补充说明", "blocked_by": ["missing_damage_photo"]},
        version=2,
        updated_by_run_id=run_id,
        source_ref_json=source_ref,
    )

    payload = build_active_cwc_payload(row)

    assert payload["content"]["authority_class"] == "contextual_only"
    assert payload["content"]["customer_request"] == "用户询问退款进度"
    assert payload["content"]["claims"][0]["text"] == "用户称商品破损"
    assert payload["ref"] == {
        "schema_version": "case_working_context_ref.v1",
        "authority_class": "contextual_only",
        "tenant_id": str(tenant_id),
        "case_id": str(case_id),
        "memory_id": str(memory_id),
        "version": 2,
        "source_ref": source_ref,
        "updated_by_run_id": str(run_id),
        "prompt_safe": True,
    }


def test_skipped_status_returns_contextual_status_without_implicit_read_or_write_flags() -> None:
    status = skipped_status(reason_code="skipped_no_case")

    assert status.schema_version == "case_working_context_lifecycle_status.v1"
    assert status.authority_class == "contextual_only"
    assert status.status == "skipped"
    assert status.reason_code == "skipped_no_case"
    assert status.read_status is None
    assert status.write_status is None
