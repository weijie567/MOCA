from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.approvals.schemas import RiskDecisionV1, TargetMerchantBindingV1
from src.knowledge.schemas import EvidenceRefV1
from src.tools.contracts import BusinessFactRefV1


class DraftOutcomeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["draft_outcome.v1"] = "draft_outcome.v1"
    status: Literal["not_executed_demo"] = "not_executed_demo"
    external_side_effect: Literal[False] = False
    tenant_id: str | None = None
    run_id: str | None = None
    draft_id: str | None = None
    created_at: str | None = None


class ActionDraftV2Data(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["action_draft.v2"] = "action_draft.v2"
    tenant_id: str
    run_id: str
    draft_id: str
    proposed_action: dict[str, Any]
    action_payload_hash: str
    approval_ref: str | None = None
    approval_revision_ref: str | None
    safety_snapshot_ref: str
    safety_snapshot_hash: str
    target_id: str
    target_merchant_id: str | None = None
    target_merchant_ref: TargetMerchantBindingV1 | None = None
    business_fact_refs: list[BusinessFactRefV1] = Field(default_factory=list)
    verified_evidence_refs: list[EvidenceRefV1] = Field(default_factory=list)
    claim_verification_ref: str | None = None
    claim_verification_summary: dict[str, Any] | None = None
    risk_decision_ref: str | None = None
    risk_decision: RiskDecisionV1 | None = None
    auto_allowed_binding_ref: str | None = None
    idempotency_key: str
    status: str
    execution_mode: Literal["demo"]
    draft_version: int = 1
    lifecycle_status: str = "active"
    retention_policy: str = "phase14_demo_draft"
    draft_outcome: DraftOutcomeV1
    created_at: str | None = None


class ActionDraftData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    idempotency_key: str
    status: str
    created: bool
    idempotent_reused: bool


class ActionToolCompatResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    data: dict[str, Any]
    error: dict[str, Any]
