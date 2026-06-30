from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from src.agent.run_scope import (
    AGENT_RUN_SCOPE_CLASSIFICATIONS,
    BUSINESS_MERCHANT,
    MERCHANT_NOT_REQUIRED,
    POLICY_ONLY,
    UNKNOWN_LEGACY,
    AgentRunScopeFacts,
    classify_agent_run_scope,
)
from src.agent.state import AgentState
from src.approvals.schemas import TargetMerchantBindingV1
from src.business.schemas import BusinessFactResultV1
from src.tools.contracts import BusinessFactRefV1


def _business_fact_ref(*, merchant_id: str = "merchant-1") -> dict[str, Any]:
    return {
        "schema_version": "business_fact_ref.v1",
        "tenant_id": "tenant-1",
        "source_system": "business_fact_service",
        "resource_type": "order",
        "resource_id": "order-1",
        "merchant_id": merchant_id,
    }


def _target_merchant_ref(*, merchant_id: str = "merchant-1") -> dict[str, Any]:
    return TargetMerchantBindingV1(
        target_merchant_id=merchant_id,
        source="business_fact_ref",
        business_fact_ref=_business_fact_ref(merchant_id=merchant_id),
    ).model_dump(mode="json")


def _business_fact_result(
    *,
    merchant_id: str = "merchant-1",
    status: str = "ok",
    scope_check_result: str = "allowed",
    source_system: str = "business_fact_service",
) -> dict[str, Any]:
    return BusinessFactResultV1(
        tenant_id="tenant-1",
        status=status,
        fact={"merchant_id": merchant_id, "order_no": "ORD-1"},
        business_fact_refs=[BusinessFactRefV1.model_validate(_business_fact_ref(merchant_id=merchant_id))],
        resource_version="v1",
        data_freshness_at=datetime(2026, 6, 30, tzinfo=UTC),
        source_system=source_system,
        scope_check_result=scope_check_result,
        missing_required_facts=[],
        safe_errors=[],
    ).model_dump(mode="json")


def test_agent_run_scope_literals_are_closed_set() -> None:
    assert AGENT_RUN_SCOPE_CLASSIFICATIONS == {
        BUSINESS_MERCHANT,
        POLICY_ONLY,
        MERCHANT_NOT_REQUIRED,
        UNKNOWN_LEGACY,
    }


def test_valid_target_merchant_binding_classifies_business_merchant() -> None:
    facts = classify_agent_run_scope(
        {
            "tenant_id": "tenant-1",
            "current_intent": "refund_troubleshooting",
            "target_merchant_id": "merchant-1",
            "target_merchant_ref": _target_merchant_ref(merchant_id="merchant-1"),
        }
    )

    assert facts == AgentRunScopeFacts(
        scope_classification=BUSINESS_MERCHANT,
        target_merchant_id="merchant-1",
        target_merchant_ref=_target_merchant_ref(merchant_id="merchant-1"),
        scope_source="target_merchant_binding_v1",
        scope_reason_codes=[],
    )


def test_matching_approval_plan_binding_classifies_business_merchant() -> None:
    target_ref = _target_merchant_ref(merchant_id="merchant-1")

    facts = classify_agent_run_scope(
        {
            "tenant_id": "tenant-1",
            "target_merchant_id": "merchant-1",
            "target_merchant_ref": target_ref,
            "approval_plan": {
                "target_merchant_id": "merchant-1",
                "target_merchant_ref": target_ref,
            },
        }
    )

    assert facts.scope_classification == BUSINESS_MERCHANT
    assert facts.target_merchant_id == "merchant-1"
    assert facts.target_merchant_ref == target_ref
    assert facts.scope_source == "approval_plan_target_merchant_binding_v1"


def test_service_approved_business_fact_result_classifies_business_merchant() -> None:
    facts = classify_agent_run_scope(
        {
            "tenant_id": "tenant-1",
            "business_fact_results": [_business_fact_result(merchant_id="merchant-2")],
        }
    )

    assert facts.scope_classification == BUSINESS_MERCHANT
    assert facts.target_merchant_id == "merchant-2"
    assert facts.target_merchant_ref is not None
    assert facts.target_merchant_ref["target_merchant_id"] == "merchant-2"
    assert facts.target_merchant_ref["source"] == "business_fact_result"


def test_no_business_indicators_are_non_business_with_null_target() -> None:
    facts = classify_agent_run_scope({"current_intent": "small_talk"})

    assert facts.scope_classification in {POLICY_ONLY, MERCHANT_NOT_REQUIRED}
    assert facts.target_merchant_id is None
    assert facts.target_merchant_ref is None


def test_missing_target_for_business_path_is_unknown_legacy() -> None:
    facts = classify_agent_run_scope({"current_intent": "refund_troubleshooting"})

    assert facts.scope_classification == UNKNOWN_LEGACY
    assert facts.target_merchant_id is None
    assert facts.target_merchant_ref is None
    assert "no_authoritative_scope_proof" in facts.scope_reason_codes


def test_mixed_target_merchant_proof_fails_closed() -> None:
    facts = classify_agent_run_scope(
        {
            "tenant_id": "tenant-1",
            "target_merchant_id": "merchant-1",
            "target_merchant_ref": _target_merchant_ref(merchant_id="merchant-1"),
            "business_fact_results": [_business_fact_result(merchant_id="merchant-2")],
        }
    )

    assert facts.scope_classification == UNKNOWN_LEGACY
    assert facts.target_merchant_id is None
    assert facts.target_merchant_ref is None
    assert "mixed_target_merchant_proof" in facts.scope_reason_codes


def test_malformed_target_merchant_ref_is_rejected_fail_closed() -> None:
    facts = classify_agent_run_scope(
        {
            "tenant_id": "tenant-1",
            "current_intent": "refund_troubleshooting",
            "target_merchant_id": "merchant-1",
            "target_merchant_ref": {
                "schema_version": "target_merchant_binding.v1",
                "target_merchant_id": "merchant-1",
            },
        }
    )

    assert facts.scope_classification == UNKNOWN_LEGACY
    assert facts.target_merchant_id is None
    assert facts.target_merchant_ref is None
    assert "malformed_target_merchant_ref" in facts.scope_reason_codes


@pytest.mark.parametrize(
    "state",
    [
        {"requested_by": "user-1", "current_intent": "refund_troubleshooting"},
        {"user": {"merchant_id": "merchant-1"}, "current_intent": "refund_troubleshooting"},
        {"thread_id": "tenant:user:thread", "current_intent": "refund_troubleshooting"},
        {"input_query": "order ORD-1 for merchant-1", "current_intent": "refund_troubleshooting"},
        {"final_response": "merchant-1 was mentioned", "current_intent": "refund_troubleshooting"},
        {"target_merchant_context": {"status": "resolved"}, "current_intent": "refund_troubleshooting"},
        {"replay_authorization_proof": {"proof_status": "resolved"}, "current_intent": "refund_troubleshooting"},
    ],
)
def test_forbidden_weak_sources_do_not_classify_business_merchant(state: dict[str, Any]) -> None:
    facts = classify_agent_run_scope(state)

    assert facts.scope_classification == UNKNOWN_LEGACY
    assert facts.target_merchant_id is None
    assert facts.target_merchant_ref is None


def test_untrusted_or_denied_business_fact_results_do_not_classify_business_merchant() -> None:
    for payload in (
        _business_fact_result(merchant_id="merchant-1", status="permission_denied", scope_check_result="denied"),
        _business_fact_result(merchant_id="merchant-1", source_system="raw_tool_payload"),
        _business_fact_result(merchant_id="merchant-1", status="not_found"),
    ):
        facts = classify_agent_run_scope({"business_fact_results": [payload], "current_intent": "refund_troubleshooting"})
        assert facts.scope_classification == UNKNOWN_LEGACY
        assert facts.target_merchant_id is None
        assert facts.target_merchant_ref is None


def test_agent_state_declares_optional_run_scope_fields() -> None:
    annotations = AgentState.__annotations__

    assert annotations["target_merchant_id"]
    assert annotations["target_merchant_ref"]
    assert annotations["scope_classification"]
    assert annotations["scope_source"]
    assert annotations["scope_reason_codes"]


def test_target_merchant_binding_schema_rejects_malformed_ref() -> None:
    with pytest.raises(ValidationError):
        TargetMerchantBindingV1.model_validate(
            {
                "schema_version": "target_merchant_binding.v1",
                "target_merchant_id": "merchant-1",
            }
        )
