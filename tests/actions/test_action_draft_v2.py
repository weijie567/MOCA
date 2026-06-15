from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.actions.schemas import ActionDraftV2Data, DraftOutcomeV1


def _draft_payload() -> dict[str, object]:
    return {
        "tenant_id": "tenant-1",
        "run_id": "run-1",
        "draft_id": "draft-1",
        "proposed_action": {
            "schema_version": "proposed_action.v1",
            "action_type": "issue_coupon",
            "target_id": "RF-1001",
        },
        "action_payload_hash": "sha256:" + "a" * 64,
        "approval_ref": "approval_request/approval-1",
        "approval_revision_ref": "approval_request/approval-1@rev1",
        "safety_snapshot_ref": "action_safety_snapshot/snap-1",
        "safety_snapshot_hash": "sha256:" + "b" * 64,
        "target_id": "RF-1001",
        "idempotency_key": "tenant-1:run-1:rev1:issue_coupon:RF-1001:sha256-aaaa",
        "status": "draft_created",
        "execution_mode": "demo",
        "draft_outcome": DraftOutcomeV1().model_dump(mode="json"),
    }


def test_draft_outcome_v1_defaults_to_not_executed_demo():
    outcome = DraftOutcomeV1()

    assert outcome.schema_version == "draft_outcome.v1"
    assert outcome.status == "not_executed_demo"
    assert outcome.external_side_effect is False


@pytest.mark.parametrize(
    "missing_field",
    [
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
        "target_id",
        "approval_revision_ref",
        "draft_outcome",
        "execution_mode",
    ],
)
def test_action_draft_v2_data_requires_phase14_binding_fields(missing_field: str):
    payload = _draft_payload()
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        ActionDraftV2Data.model_validate(payload)


def test_action_draft_v2_data_rejects_unknown_fields():
    payload = _draft_payload()
    payload["unexpected"] = "blocked"

    with pytest.raises(ValidationError):
        ActionDraftV2Data.model_validate(payload)


def test_action_draft_v2_data_exposes_demo_contract_literals():
    draft = ActionDraftV2Data.model_validate(_draft_payload())

    assert draft.schema_version == "action_draft.v2"
    assert draft.execution_mode == "demo"
    assert draft.draft_outcome.schema_version == "draft_outcome.v1"
    assert draft.draft_outcome.status == "not_executed_demo"
    assert draft.draft_outcome.external_side_effect is False
