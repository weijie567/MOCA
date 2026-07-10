from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.approvals.schemas import (
    AUTO_ALLOWED_ACTION_BINDING_SCHEMA_VERSION,
    RISK_DECISION_SCHEMA_VERSION,
    ApprovalDecisionResult,
    ApprovalRequestCreateCommand,
    AutoAllowedActionBindingV1,
    RiskDecisionV1,
    TargetMerchantBindingV1,
    TrustedApprovalResultV1,
)
from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1


def _business_fact_ref() -> BusinessFactRefV1:
    return BusinessFactRefV1(
        tenant_id="tenant-1",
        source_system="moca_demo",
        resource_type="refund_case",
        resource_id="RF-1001",
        resource_version="v1",
        data_freshness_at=datetime(2026, 6, 29, 0, 0, tzinfo=UTC),
        retrieved_at=datetime(2026, 6, 29, 0, 1, tzinfo=UTC),
    )


def _evidence_ref() -> EvidenceRefV1:
    return EvidenceRefV1(
        tenant_id="tenant-1",
        evidence_id="refund-policy/chunk-001@v3",
        doc_key="refund-policy",
        chunk_id="chunk-001",
        policy_version="v3",
        text_hash="sha256:" + "a" * 64,
        retrieved_at="2026-06-29T00:00:00.000Z",
        retrieval_config_version="retrieval.v1",
        rank=1,
    )


def _risk_decision_payload() -> dict[str, object]:
    return {
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "action_id": "act-1",
        "action_payload_hash": "sha256:" + "b" * 64,
        "risk_level": "high",
        "reason_codes": ["refund_delay", "coupon_amount"],
        "policy_config_version": "approval-policy.v1",
        "risk_config_version": "risk-rules.v1",
        "approval_required": True,
        "evaluated_at": "2026-06-29T00:02:00.000Z",
        "risk_rule_ref": "risk-rule:coupon-high",
        "risk_reason": "Coupon amount requires manager review.",
    }


def _risk_decision() -> RiskDecisionV1:
    return RiskDecisionV1.model_validate(_risk_decision_payload())


def _target_merchant_ref() -> TargetMerchantBindingV1:
    return TargetMerchantBindingV1(
        target_merchant_id="merchant-1",
        source="business_fact_ref",
        business_fact_ref=_business_fact_ref().model_dump(mode="json"),
    )


def test_phase34_schema_version_literals_are_exported():
    assert RISK_DECISION_SCHEMA_VERSION == "risk_decision.v1"
    assert AUTO_ALLOWED_ACTION_BINDING_SCHEMA_VERSION == "auto_allowed_action_binding.v1"


def test_risk_decision_v1_rejects_unknown_fields():
    payload = _risk_decision_payload()
    payload["unexpected"] = "blocked"

    with pytest.raises(ValidationError):
        RiskDecisionV1.model_validate(payload)


def test_approval_request_create_command_carries_phase34_bindings():
    fact_ref = _business_fact_ref()
    evidence_ref = _evidence_ref()
    target_ref = _target_merchant_ref()
    risk_decision = _risk_decision()
    command = ApprovalRequestCreateCommand(
        tenant_id=uuid4(),
        run_id=uuid4(),
        thread_id="thread-1",
        requested_by=uuid4(),
        proposed_action={"schema_version": "proposed_action.v1", "action_id": "act-1"},
        action_payload_hash=risk_decision.action_payload_hash,
        safety_snapshot_ref="action_safety_snapshot/snap-1",
        safety_snapshot_hash="sha256:" + "c" * 64,
        approval_policy_id="coupon-high-v1",
        policy_version="approval-policy.v1",
        risk_level=risk_decision.risk_level,
        risk_rule_ref=risk_decision.risk_rule_ref,
        risk_reason=risk_decision.risk_reason,
        policy_config_version=risk_decision.policy_config_version,
        risk_config_version=risk_decision.risk_config_version,
        retrieval_config_version="retrieval.v1",
        evidence_refs=[evidence_ref],
        target_merchant_id="merchant-1",
        target_merchant_ref=target_ref,
        business_fact_refs=[fact_ref],
        verified_evidence_refs=[evidence_ref],
        claim_verification_ref="claim_verification_bundle/bundle-1",
        claim_verification_summary={"overall_status": "verified", "safe_support_ref_count": 1},
        risk_decision_ref="risk_decision/run-1/act-1",
        risk_decision=risk_decision,
        approval_idempotency_key="tenant-1:run-1:approval:act-1",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
    )

    assert command.target_merchant_id == "merchant-1"
    assert command.target_merchant_ref == target_ref
    assert command.business_fact_refs == [fact_ref]
    assert command.verified_evidence_refs == [evidence_ref]
    assert command.claim_verification_summary == {"overall_status": "verified", "safe_support_ref_count": 1}
    assert command.risk_decision == risk_decision
    assert command.approval_idempotency_key == "tenant-1:run-1:approval:act-1"


def test_trusted_approval_result_carries_action_draft_validation_bindings():
    fact_ref = _business_fact_ref()
    evidence_ref = _evidence_ref()
    target_ref = _target_merchant_ref()
    risk_decision = _risk_decision()
    result = TrustedApprovalResultV1(
        approval_id=uuid4(),
        tenant_id=uuid4(),
        run_id=uuid4(),
        status="approved",
        decision_type="approve",
        revision=1,
        request_version=2,
        level_version=3,
        assignment_version=4,
        action_payload_hash=risk_decision.action_payload_hash,
        safety_snapshot_ref="action_safety_snapshot/snap-1",
        safety_snapshot_hash="sha256:" + "c" * 64,
        decided_by=uuid4(),
        decided_at=datetime.now(UTC),
        target_merchant_id="merchant-1",
        target_merchant_ref=target_ref,
        business_fact_refs=[fact_ref],
        verified_evidence_refs=[evidence_ref],
        claim_verification_ref="claim_verification_bundle/bundle-1",
        claim_verification_summary={"overall_status": "verified"},
        risk_decision_ref="risk_decision/run-1/act-1",
        risk_decision=risk_decision,
        approval_idempotency_key="tenant-1:run-1:approval:act-1",
    )

    dumped = result.model_dump(mode="json")
    assert dumped["target_merchant_id"] == "merchant-1"
    assert dumped["business_fact_refs"][0]["schema_version"] == "business_fact_ref.v1"
    assert dumped["verified_evidence_refs"][0]["schema_version"] == "evidence_ref.v1"
    assert dumped["risk_decision"]["schema_version"] == "risk_decision.v1"
    assert dumped["approval_idempotency_key"] == "tenant-1:run-1:approval:act-1"


def test_approval_decision_result_preserves_phase34_resume_payload_bindings():
    fact_ref = _business_fact_ref()
    evidence_ref = _evidence_ref()
    risk_decision = _risk_decision()
    decision = ApprovalDecisionResult(
        approval_id=uuid4(),
        tenant_id=uuid4(),
        run_id=uuid4(),
        status="approved",
        decision_type="approve",
        revision=1,
        request_version=2,
        level_version=3,
        assignment_version=4,
        action_payload_hash=risk_decision.action_payload_hash,
        safety_snapshot_ref="action_safety_snapshot/snap-1",
        safety_snapshot_hash="sha256:" + "c" * 64,
        decided_by=uuid4(),
        decided_at=datetime.now(UTC),
        decision_id=uuid4(),
        event_id=uuid4(),
        graph_thread_id="tenant:user:thread",
        target_merchant_id="merchant-1",
        business_fact_refs=[fact_ref],
        verified_evidence_refs=[evidence_ref],
        risk_decision_ref="risk_decision/run-1/act-1",
        risk_decision=risk_decision,
        approval_idempotency_key="tenant-1:run-1:approval:act-1",
    )

    assert decision.target_merchant_id == "merchant-1"
    assert decision.business_fact_refs == [fact_ref]
    assert decision.verified_evidence_refs == [evidence_ref]
    assert decision.risk_decision_ref == "risk_decision/run-1/act-1"


def test_auto_allowed_action_binding_requires_typed_safe_refs():
    binding = AutoAllowedActionBindingV1(
        tenant_id="tenant-1",
        run_id="run-1",
        target_merchant_id="merchant-1",
        action_payload_hash="sha256:" + "b" * 64,
        safety_snapshot_ref="action_safety_snapshot/snap-1",
        safety_snapshot_hash="sha256:" + "c" * 64,
        risk_decision_ref="risk_decision/run-1/act-1",
        idempotency_key="tenant-1:run-1:auto_allowed:issue_coupon:RF-1001:sha256-bbbb",
        business_fact_refs=[_business_fact_ref()],
        verified_evidence_refs=[_evidence_ref()],
        claim_verification_ref="claim_verification_bundle/bundle-1",
        claim_verification_summary={"overall_status": "verified"},
    )

    assert binding.schema_version == "auto_allowed_action_binding.v1"
    assert binding.business_fact_refs[0].resource_id == "RF-1001"
    assert binding.verified_evidence_refs[0].evidence_id == "refund-policy/chunk-001@v3"


def test_legacy_auto_allowed_binding_cannot_impersonate_a_server_capability():
    payload = {
        "schema_version": "auto_allowed_action_binding.v1",
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "target_merchant_id": "merchant-1",
        "action_payload_hash": "sha256:" + "b" * 64,
        "safety_snapshot_ref": "action_safety_snapshot/snap-1",
        "safety_snapshot_hash": "sha256:" + "c" * 64,
        "risk_decision_ref": "risk_decision/run-1/act-1",
        "idempotency_key": "legacy-key",
        "business_fact_refs": [_business_fact_ref().model_dump(mode="json")],
        "verified_evidence_refs": [_evidence_ref().model_dump(mode="json")],
        "capability_ref": "aac_client_asserted",
        "handler": "create_coupon_grant_draft",
    }

    with pytest.raises(ValidationError):
        AutoAllowedActionBindingV1.model_validate(payload)
