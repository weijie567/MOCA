from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.actions.schemas import ActionDraftV2Data, DraftOutcomeV1
from src.approvals.schemas import RiskDecisionV1, TargetMerchantBindingV1
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


def _risk_decision() -> RiskDecisionV1:
    return RiskDecisionV1(
        tenant_id="tenant-1",
        run_id="run-1",
        action_id="act-1",
        action_payload_hash="sha256:" + "b" * 64,
        risk_level="high",
        reason_codes=["coupon_amount"],
        policy_config_version="approval-policy.v1",
        risk_config_version="risk-rules.v1",
        approval_required=True,
        evaluated_at="2026-06-29T00:02:00.000Z",
    )


def _target_merchant_ref() -> TargetMerchantBindingV1:
    return TargetMerchantBindingV1(
        target_merchant_id="merchant-1",
        source="business_fact_ref",
        business_fact_ref=_business_fact_ref().model_dump(mode="json"),
    )


def _draft_payload() -> dict[str, object]:
    risk_decision = _risk_decision()
    return {
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "draft_id": "draft-1",
        "proposed_action": {
            "schema_version": "proposed_action.v1",
            "action_id": "act-1",
            "action_type": "issue_coupon",
            "target_id": "RF-1001",
        },
        "action_payload_hash": risk_decision.action_payload_hash,
        "approval_ref": "approval_request/approval-1",
        "approval_revision_ref": "approval_request/approval-1@rev1",
        "safety_snapshot_ref": "action_safety_snapshot/snap-1",
        "safety_snapshot_hash": "sha256:" + "c" * 64,
        "target_id": "RF-1001",
        "target_merchant_id": "merchant-1",
        "target_merchant_ref": _target_merchant_ref().model_dump(mode="json"),
        "business_fact_refs": [_business_fact_ref().model_dump(mode="json")],
        "verified_evidence_refs": [_evidence_ref().model_dump(mode="json")],
        "claim_verification_ref": "claim_verification_bundle/bundle-1",
        "claim_verification_summary": {"overall_status": "verified", "safe_support_ref_count": 1},
        "risk_decision_ref": "risk_decision/run-1/act-1",
        "risk_decision": risk_decision.model_dump(mode="json"),
        "auto_allowed_binding_ref": None,
        "idempotency_key": "tenant-1:run-1:rev1:issue_coupon:RF-1001:sha256-bbbb",
        "status": "draft_created",
        "execution_mode": "demo",
        "draft_outcome": DraftOutcomeV1().model_dump(mode="json"),
    }


def test_action_draft_v2_data_rejects_unknown_phase34_fields():
    payload = _draft_payload()
    payload["unexpected"] = "blocked"

    with pytest.raises(ValidationError):
        ActionDraftV2Data.model_validate(payload)


def test_action_draft_v2_data_exposes_phase34_binding_refs():
    draft = ActionDraftV2Data.model_validate(_draft_payload())

    assert draft.target_merchant_id == "merchant-1"
    assert draft.target_merchant_ref == _target_merchant_ref()
    assert draft.business_fact_refs == [_business_fact_ref()]
    assert draft.verified_evidence_refs == [_evidence_ref()]
    assert draft.claim_verification_summary == {"overall_status": "verified", "safe_support_ref_count": 1}
    assert draft.risk_decision == _risk_decision()
    assert draft.risk_decision_ref == "risk_decision/run-1/act-1"


def test_action_draft_v2_data_rejects_unvalidated_business_fact_dicts():
    payload = _draft_payload()
    payload["business_fact_refs"] = [{"resource_type": "refund_case", "resource_id": "RF-1001"}]

    with pytest.raises(ValidationError):
        ActionDraftV2Data.model_validate(payload)


def test_action_draft_v2_data_rejects_unvalidated_risk_decision_dicts():
    payload = _draft_payload()
    risk_decision = dict(payload["risk_decision"])
    risk_decision["schema_version"] = "risk_decision.v999"
    payload["risk_decision"] = risk_decision

    with pytest.raises(ValidationError):
        ActionDraftV2Data.model_validate(payload)
