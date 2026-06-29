# Phase 34: Approval and ActionDraft Boundary Hardening - Pattern Map

**Mapped:** 2026-06-29  
**Files analyzed:** 53  
**Analogs found:** 53 / 53

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/approvals/schemas.py` | model | request-response | `src/approvals/schemas.py` | exact |
| `src/actions/schemas.py` | model | request-response | `src/actions/schemas.py` | exact |
| `src/db/models.py` | model | CRUD | `src/db/models.py` | exact |
| `src/db/migrations/versions/018_phase34_approval_action_bindings.py` | migration | batch | `src/db/migrations/versions/008_approval_state_machine.py`; `src/db/migrations/versions/009_action_draft_v2.py` | role-match |
| `src/approvals/snapshots.py` | utility/model | transform | `src/approvals/snapshots.py` | exact |
| `src/approvals/snapshot_service.py` | service | CRUD | `src/approvals/snapshot_service.py` | exact |
| `src/agent/state.py` | model | event-driven | `src/agent/state.py` | exact |
| `src/agent/nodes/assess_risk_and_approval.py` | component | event-driven | `src/agent/nodes/assess_risk_and_approval.py` | exact |
| `src/agent/graph.py` | route | event-driven | `src/agent/graph.py` | exact |
| `src/agent/graph_vocabulary.py` | config | transform | `src/agent/graph_vocabulary.py` | exact |
| `src/agent/nodes/approval_gate.py` | component | event-driven | `src/agent/nodes/approval_gate.py` | exact |
| `src/approvals/service.py` | service | CRUD | `src/approvals/service.py` | exact |
| `src/approvals/repository.py` | repository | CRUD | `src/approvals/repository.py` | exact |
| `src/approvals/policy.py` | service | request-response | `src/approvals/policy.py` | exact |
| `src/api/routers/approvals.py` | controller | request-response | `src/api/routers/approvals.py` | exact |
| `src/api/schemas/approvals.py` | model | request-response | `src/api/schemas/approvals.py` | exact |
| `src/platform/trusted_context.py` | provider | request-response | `src/platform/trusted_context.py` | exact |
| `src/actions/service.py` | service | CRUD | `src/actions/service.py` | exact |
| `src/actions/drafts.py` | service | CRUD | `src/actions/drafts.py` | exact |
| `src/repositories/action_draft_repo.py` | repository | CRUD | `src/repositories/action_draft_repo.py` | exact |
| `src/agent/nodes/action_draft.py` | component | event-driven | `src/agent/nodes/action_draft.py` | exact |
| `src/agent/nodes/final_response.py` | component | transform | `src/agent/nodes/final_response.py` | exact |
| `src/agent/working_state.py` | utility | transform | `src/agent/working_state.py` | exact |
| `src/tools/catalog.py` | config | request-response | `src/tools/catalog.py` | exact |
| `src/tools/runtime.py` | service | request-response | `src/tools/runtime.py` | exact |
| `src/tools/platform.py` | provider | request-response | `src/tools/platform.py` | exact |
| `src/tools/policy.py` | service | request-response | `src/tools/policy.py` | exact |
| `src/tools/executors/action.py` | service | request-response | `src/tools/executors/action.py` | exact |
| `src/api/routers/agent_runs.py` | controller | streaming | `src/api/routers/agent_runs.py` | exact |
| `src/api/routers/traces.py` | controller | request-response | `src/api/routers/traces.py` | exact |
| `src/repositories/trace_repo.py` | repository | CRUD/transform | `src/repositories/trace_repo.py` | exact |
| `src/api/schemas/agent_runs.py` | model | streaming | `src/api/schemas/agent_runs.py` | exact |
| `tests/approvals/test_phase34_boundary_bindings.py` | test | CRUD | `tests/approvals/test_hash_binding.py`; `tests/approvals/test_migration_contract.py` | role-match |
| `tests/actions/test_phase34_action_draft_bindings.py` | test | CRUD | `tests/actions/test_action_draft_v2.py`; `tests/test_execute_action.py` | role-match |
| `tests/architecture/test_phase34_approval_action_boundaries.py` | test | transform/static | `tests/architecture/test_action_draft_boundaries.py`; `tests/architecture/test_approval_boundaries.py` | role-match |
| `tests/approvals/test_migration_contract.py` | test | batch | `tests/approvals/test_migration_contract.py` | exact |
| `tests/approvals/test_hash_binding.py` | test | CRUD | `tests/approvals/test_hash_binding.py` | exact |
| `tests/approvals/test_service_transitions.py` | test | CRUD | `tests/approvals/test_service_transitions.py` | exact |
| `tests/actions/test_action_draft_v2.py` | test | CRUD | `tests/actions/test_action_draft_v2.py` | exact |
| `tests/test_execute_action.py` | test | event-driven | `tests/test_execute_action.py` | exact |
| `tests/test_graph_routing.py` | test | event-driven | `tests/test_graph_routing.py` | exact |
| `tests/agent/test_nodes/test_assess_risk_and_approval.py` | test | event-driven | `tests/agent/test_nodes/test_assess_risk_and_approval.py` | exact |
| `tests/test_approval_api.py` | test | request-response | `tests/test_approval_api.py` | exact |
| `tests/test_agent_runs_api.py` | test | streaming | `tests/test_agent_runs_api.py` | exact |
| `tests/test_approval_gate.py` | test | event-driven | `tests/test_approval_gate.py` | exact |
| `tests/test_approval_integration.py` | test | request-response | `tests/test_approval_integration.py` | exact |
| `tests/approvals/test_canonical_hash.py` | test | transform | `tests/approvals/test_canonical_hash.py` | exact |
| `tests/approvals/test_multi_level_contract.py` | test | CRUD | `tests/approvals/test_multi_level_contract.py` | exact |
| `tests/approvals/test_single_level_runtime.py` | test | CRUD | `tests/approvals/test_single_level_runtime.py` | exact |
| `tests/architecture/test_approval_boundaries.py` | test | transform/static | `tests/architecture/test_approval_boundaries.py` | exact |
| `tests/architecture/test_action_draft_boundaries.py` | test | transform/static | `tests/architecture/test_action_draft_boundaries.py` | exact |
| `tests/architecture/test_phase33_rag_claim_boundaries.py` | test | transform/static | `tests/architecture/test_phase33_rag_claim_boundaries.py` | exact |
| `tests/platform/test_merchant_scope.py` | test | request-response | `tests/platform/test_merchant_scope.py` | exact |
| `tests/tools/test_merchant_scope_static.py` | test | transform/static | `tests/tools/test_merchant_scope_static.py` | exact |
| `tests/agent/test_graph.py` | test | event-driven | `tests/agent/test_graph.py` | exact |

## Pattern Assignments

### Contracts and Persistence Bindings

**Apply to:** `src/approvals/schemas.py`, `src/actions/schemas.py`, `src/db/models.py`, `src/db/migrations/versions/018_phase34_approval_action_bindings.py`, `src/approvals/snapshots.py`, `src/approvals/snapshot_service.py`, `tests/approvals/test_phase34_boundary_bindings.py`, `tests/actions/test_phase34_action_draft_bindings.py`, `tests/approvals/test_migration_contract.py`, `tests/actions/test_action_draft_v2.py`

**Strict DTO imports and version literals**  
**Analog:** `src/approvals/schemas.py` lines 5-15
```python
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.knowledge.schemas import EvidenceRefV1

ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION = "action_safety_snapshot.v1"
PROPOSED_ACTION_SCHEMA_VERSION = "proposed_action.v1"
APPROVAL_RESULT_SCHEMA_VERSION = "approval_result.v1"
```

**Approval command/result binding fields**  
**Analog:** `src/approvals/schemas.py` lines 29-50, 75-105, 126-151
```python
class ApprovalRequestCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    run_id: UUID
    thread_id: str = Field(min_length=1)
    requested_by: UUID
    proposed_action: dict[str, Any]
    action_payload_hash: str | None = None
    safety_snapshot_ref: str | None = None
    safety_snapshot_hash: str | None = None
    approval_policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    risk_rule_ref: str | None = None
    risk_reason: str | None = None
    policy_config_version: str = Field(min_length=1)
    risk_config_version: str = Field(min_length=1)
    retrieval_config_version: str = Field(min_length=1)
    evidence_refs: list[EvidenceRefV1] = Field(min_length=1)
```
```python
class ApprovalDecisionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: UUID
    tenant_id: UUID
    run_id: UUID
    thread_id: str = Field(min_length=1)
    level_id: UUID
    assignment_id: UUID
    actor_id: UUID
    actor_role: str = Field(min_length=1)
    decision_type: ApprovalDecisionType
    expected_request_version: int = Field(ge=1)
    expected_level_version: int = Field(ge=1)
    expected_assignment_version: int = Field(ge=1)
    expected_revision: int = Field(ge=1)
    action_payload_hash: str = Field(min_length=1)
    safety_snapshot_hash: str = Field(min_length=1)
```
```python
class TrustedApprovalResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["approval_result.v1"] = APPROVAL_RESULT_SCHEMA_VERSION
    approval_id: UUID
    tenant_id: UUID
    run_id: UUID
    status: ApprovalRequestStatus
    decision_type: ApprovalDecisionType
    revision: int = Field(ge=1)
    request_version: int = Field(ge=1)
    level_version: int = Field(ge=1)
    assignment_version: int = Field(ge=1)
    action_payload_hash: str
    safety_snapshot_ref: str
    safety_snapshot_hash: str
```

**Action draft contract and demo outcome**  
**Analog:** `src/actions/schemas.py` lines 9-41
```python
class DraftOutcomeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["draft_outcome.v1"] = "draft_outcome.v1"
    status: Literal["not_executed_demo"] = "not_executed_demo"
    external_side_effect: Literal[False] = False


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
    idempotency_key: str
```

**Business fact, verified evidence, and claim refs**  
**Analogs:** `src/tools/contracts.py` lines 58-69; `src/knowledge/schemas.py` lines 32-43, 126-145, 185-195
```python
class BusinessFactRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["business_fact_ref.v1"] = "business_fact_ref.v1"
    tenant_id: str
    source_system: str
    resource_type: Literal["order", "refund_case", "ticket", "logistics", "merchant_risk"]
    resource_id: str
    resource_version: str | None
    data_freshness_at: datetime | None
    retrieved_at: datetime
```
```python
class EvidenceRefV1(BaseModel):
    schema_version: Literal["evidence_ref.v1"] = "evidence_ref.v1"
    tenant_id: str
    evidence_id: str
    doc_key: str
    chunk_id: str
    policy_version: str
    text_hash: str
    retrieved_at: str
    retrieval_config_version: str
```
```python
class ClaimVerificationBundleV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["claim_verification_bundle.v1"] = "claim_verification_bundle.v1"
    overall_status: ClaimBundleOverallStatus
    route: ClaimBundleRoute
    claim_results: list[ClaimVerificationResultV1] = Field(default_factory=list)
    blocked_claims: list[str] = Field(default_factory=list)
    safe_support_refs: list[EvidenceRefV1] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    verifier_policy_version: str
```

**ORM binding fields**  
**Analog:** `src/db/models.py` lines 667-707, 934-960
```python
class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "run_id", "revision", name="uq_approval_requests_tenant_run_revision"),
        CheckConstraint(
            "status IN ('pending', 'needs_info', 'approved', 'rejected', 'cancelled', 'expired', 'superseded')",
            name="ck_approval_requests_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    schema_version: Mapped[str | None] = mapped_column(String(48), default="approval_request.v2")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    approval_policy_id: Mapped[str | None] = mapped_column(String(64))
    policy_version: Mapped[str | None] = mapped_column(String(64))
    revision: Mapped[int | None] = mapped_column()
    version: Mapped[int | None] = mapped_column(default=1)
    action_payload_hash: Mapped[str | None] = mapped_column(String(128))
    safety_snapshot_ref: Mapped[str | None] = mapped_column(String(128))
    safety_snapshot_hash: Mapped[str | None] = mapped_column(String(128))
    legacy_non_executable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```
```python
class ActionDraft(TimestampMixin, Base):
    __tablename__ = "action_drafts"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_action_drafts_tenant_idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True)
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("approval_requests.id"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    schema_version: Mapped[str | None] = mapped_column(String(48), default="action_draft.v2")
    target_id: Mapped[str | None] = mapped_column(String(128))
    approval_revision_ref: Mapped[str | None] = mapped_column(String(128))
    action_payload_hash: Mapped[str | None] = mapped_column(String(128))
    safety_snapshot_ref: Mapped[str | None] = mapped_column(String(128))
    safety_snapshot_hash: Mapped[str | None] = mapped_column(String(128))
```

**Migration shape: nullable/backfillable columns, named constraints, deterministic legacy handling**  
**Analogs:** `src/db/migrations/versions/008_approval_state_machine.py` lines 42-117; `src/db/migrations/versions/009_action_draft_v2.py` lines 26-50
```python
def upgrade() -> None:
    for column in (
        sa.Column("schema_version", sa.String(length=48)),
        sa.Column("approval_policy_id", sa.String(length=64)),
        sa.Column("policy_version", sa.String(length=64)),
        sa.Column("revision", sa.Integer()),
        sa.Column("version", sa.Integer()),
        sa.Column("action_payload_hash", sa.String(length=128)),
        sa.Column("safety_snapshot_ref", sa.String(length=128)),
        sa.Column("safety_snapshot_hash", sa.String(length=128)),
        sa.Column("legacy_non_executable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("superseded_by_request_id", postgresql.UUID(as_uuid=True)),
        sa.Column("clarification_request_id", sa.String(length=128)),
    ):
        op.add_column("approval_requests", column)
```
```python
op.execute(
    """
    WITH ranked_legacy AS (
        SELECT
            id,
            row_number() over (
                partition by tenant_id, run_id
                order by created_at, id
            ) AS deterministic_revision
        FROM approval_requests
        WHERE revision IS NULL
    )
    UPDATE approval_requests
    SET revision = ranked_legacy.deterministic_revision
    FROM ranked_legacy
    WHERE approval_requests.id = ranked_legacy.id
    """
)
```
```python
def upgrade() -> None:
    op.drop_constraint(_LEGACY_KEY_CONSTRAINT, "action_drafts", type_="unique")

    for column in (
        sa.Column("schema_version", sa.String(length=48), server_default="action_draft.v2"),
        sa.Column("target_id", sa.String(length=128)),
        sa.Column("approval_revision_ref", sa.String(length=128)),
        sa.Column("action_payload_hash", sa.String(length=128)),
        sa.Column("safety_snapshot_ref", sa.String(length=128)),
        sa.Column("safety_snapshot_hash", sa.String(length=128)),
        sa.Column("draft_outcome", postgresql.JSONB(astext_type=sa.Text())),
    ):
        op.add_column("action_drafts", column)
```

**Canonical snapshot/hash pattern**  
**Analogs:** `src/approvals/snapshot_service.py` lines 45-72; `src/approvals/snapshots.py` lines 44-61, 96-147
```python
def compute_action_payload_hash(proposed_action: dict[str, Any]) -> str:
    return canonical_hash(
        proposed_action,
        schema_version=PROPOSED_ACTION_SCHEMA_VERSION,
        allowed_fields=PROPOSED_ACTION_HASH_FIELDS,
        nullable_fields={"amount", "currency"},
    )
```
```python
class ActionSafetySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["action_safety_snapshot.v1"] = ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION
    tenant_id: str
    run_id: str
    snapshot_id: str
    snapshot_ref: str
    policy_config_version: str
    risk_config_version: str
    retrieval_config_version: str
    evidence: list[EvidenceRefV1]
    evidence_ids: list[str]
    action_payload_hash: str
    created_at: str
    immutable_hash: str
```
```python
projection = snapshot_hash_projection(data)
immutable_hash = canonical_hash(
    projection,
    schema_version=ACTION_SAFETY_SNAPSHOT_SCHEMA_VERSION,
    allowed_fields=SNAPSHOT_HASH_FIELDS,
)
```

**Test pattern for schema/migration contracts**  
**Analogs:** `tests/approvals/test_migration_contract.py` lines 58-118; `tests/actions/test_action_draft_v2.py` lines 152-194, 198-230
```python
def test_approval_request_v2_columns_and_named_constraints_are_declared():
    assert {
        "schema_version",
        "approval_policy_id",
        "policy_version",
        "risk_level",
        "risk_rule_ref",
        "revision",
        "version",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
        "legacy_non_executable",
    }.issubset(_column_names("approval_requests"))
```
```python
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
```

### Risk Gate Binding and Graph Routing

**Apply to:** `src/agent/nodes/assess_risk_and_approval.py`, `src/agent/graph.py`, `src/agent/graph_vocabulary.py`, `src/agent/state.py`, `tests/test_graph_routing.py`, `tests/agent/test_nodes/test_assess_risk_and_approval.py`, `tests/agent/test_graph.py`, `tests/architecture/test_phase33_rag_claim_boundaries.py`

**Risk-gate imports should use existing snapshot/evidence contracts**  
**Analog:** `src/agent/nodes/assess_risk_and_approval.py` lines 16-30
```python
from src.agent.context import ContextAssembler, PromptAssembly
from src.agent.working_state import project_working_state
from src.approvals.snapshot_service import (
    ActionSafetySnapshotPersistenceError,
    compute_action_payload_hash,
    persist_action_safety_snapshot,
)
from src.approvals.snapshots import build_action_safety_snapshot
from src.approvals.schemas import PROPOSED_ACTION_SCHEMA_VERSION
from src.knowledge.schemas import ClaimVerificationBundleV1, EvidenceRefV1, canonical_evidence_projection
```

**Claim verification gate before risk/proposal/snapshot**  
**Analog:** `src/agent/nodes/assess_risk_and_approval.py` lines 174-212, 254-270
```python
def _claim_verification_bundle(state: AgentState) -> dict[str, Any] | None:
    raw_bundle = state.get("claim_verification_bundle")
    if raw_bundle is None:
        return None
    if isinstance(raw_bundle, ClaimVerificationBundleV1):
        return raw_bundle.model_dump(mode="python")
    if isinstance(raw_bundle, dict):
        try:
            return ClaimVerificationBundleV1.model_validate(raw_bundle).model_dump(mode="python")
        except ValidationError:
            return {
                "overall_status": "error",
                "route": "final_response",
                "claim_results": [],
                "blocked_claims": ["malformed_claim_verification_bundle"],
                "safe_support_refs": [],
            }
```
```python
def _blocked_action_gate_state(state: AgentState, started_at: str, reason_code: str) -> dict[str, Any]:
    bundle = _claim_verification_bundle(state)
    return {
        "risk_assessment": _blocked_verifier_risk(state, reason_code),
        "proposed_action": None,
        "approval_plan": None,
        "approval_result": None,
        "action_draft": None,
        "draft_outcome": None,
        "action_result": None,
        "action_payload_hash": None,
        "safety_snapshot_ref": None,
        "safety_snapshot_hash": None,
        "safety_snapshot_verified": False,
        "auto_allowed": False,
```

**Structured proposed action construction**  
**Analog:** `src/agent/nodes/assess_risk_and_approval.py` lines 297-327
```python
def _build_proposed_action(
    *,
    state: AgentState,
    draft: dict[str, Any],
    context: dict[str, Any],
    assessment: dict[str, Any],
    evidence_refs: list[EvidenceRefV1],
) -> dict[str, Any]:
    refund_case = context.get("refund_case") or {}
    order = context.get("order") or {}
    amount = _extract_compensation_amount(draft, context)
    action_type = _canonical_action_type(draft.get("recommended_action"))
    target_type, target_id = _action_target(refund_case=refund_case, order=order)
    run_id = str(state.get("current_run_id") or "")
    return {
        "schema_version": PROPOSED_ACTION_SCHEMA_VERSION,
        "tenant_id": str(state.get("tenant_id") or ""),
        "run_id": run_id,
        "action_id": str(draft.get("action_id") or f"act:{run_id}:{action_type}:{target_id}"),
        "action_type": action_type,
        "target_type": target_type,
        "target_id": target_id,
        "amount": _canonical_amount(amount),
        "currency": "CNY" if amount is not None else None,
        "args": {
            "risk_level": str(assessment.get("risk_level") or ""),
            "rule_ref": str(assessment.get("rule_ref") or ""),
        },
        "reason": str(draft.get("reasoning_summary") or assessment.get("risk_reason") or ""),
        "evidence_refs": canonical_evidence_projection(evidence_refs),
    }
```

**Snapshot attach/fail-closed pattern**  
**Analog:** `src/agent/nodes/assess_risk_and_approval.py` lines 435-536
```python
proposed_action = _build_proposed_action(
    state=state,
    draft=draft,
    context=context,
    assessment=assessment,
    evidence_refs=evidence_refs,
)
action_payload_hash = compute_action_payload_hash(proposed_action)
session = (config or {}).get("configurable", {}).get("session") if config else None
if session is None:
    raise ActionSafetySnapshotPersistenceError("session unavailable for snapshot persistence")

snapshot = await persist_action_safety_snapshot(
    session,
    tenant_id=tenant_id,
    run_id=run_id,
    proposed_action=proposed_action,
    action_payload_hash=action_payload_hash,
    policy_config_version=POLICY_CONFIG_VERSION,
    risk_config_version=RISK_CONFIG_VERSION,
    retrieval_config_version=_retrieval_config_version(evidence_refs),
    evidence_refs=evidence_refs,
    created_at=_fixed_millisecond_now(),
    created_by=user_id,
)
```
```python
except (ActionSafetySnapshotPersistenceError, TypeError, ValueError, ValidationError) as exc:
    safe_assessment = {
        **assessment,
        "approval_required": False,
        "risk_level": "manual_review",
        "risk_reason": f"Action safety snapshot could not be verified: {exc}",
    }
    return {
        **result,
        "risk_assessment": safe_assessment,
        "proposed_action": None,
        "auto_allowed": False,
        "safety_snapshot_verified": False,
        "final_response": "操作需要人工复核，当前未创建可执行审批或动作草稿。",
```

**Router pattern: deterministic and side-effect-free**  
**Analog:** `src/agent/graph.py` lines 64-79, 134-179
```python
def route_after_risk(state: AgentState) -> str:
    """Route based on risk assessment and proposed action."""
    if not _verification_allows_action_path(state):
        return "final_response"
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action")
    if not proposed:
        return "final_response"
    if not _snapshot_binding_ready(state):
        return "final_response"
    if state.get("safety_snapshot_verified") is not True:
        return "final_response"
    if risk.get("approval_required"):
        return "approval_gate"
    # Phase 14 has no durable auto-allowed binding, so no-approval actions fail closed.
    return "final_response"
```
```python
def route_after_approval(state: AgentState) -> str:
    """Route after a trusted ApprovalService resume result."""
    result = _trusted_approval_result(state)
    if result is None:
        return "final_response"
    decision_type = result.decision_type
    status = result.status
    if (
        decision_type == "edit"
        and status == "superseded"
        and result.resume_route == "assess_risk_and_approval"
        and result.new_action_payload_hash
    ):
        return "assess_risk_and_approval"
    if decision_type in {"accept", "approve"} and status == "approved":
        return "action_draft"
    if decision_type in {"accept", "approve"} and status == "pending":
        return "approval_gate"
    return "final_response"
```

**State and vocabulary entries**  
**Analogs:** `src/agent/state.py` lines 127-142; `src/agent/graph_vocabulary.py` lines 41-47
```python
# Phase 4: approval workflow fields.
proposed_action: dict[str, Any] | None
approval_result: dict[str, Any] | None
approval_revision_refs: list[dict[str, Any]] | None
action_payload_hash: str | None
safety_snapshot_ref: str | None
safety_snapshot_hash: str | None
safety_snapshot_verified: bool | None
policy_config_version: str | None
risk_config_version: str | None
retrieval_config_version: str | None
auto_allowed: bool | None
action_draft: dict[str, Any] | None
draft_outcome: dict[str, Any] | None
execution_mode: str | None
action_result: dict[str, Any] | None
```
```python
_ENTRIES: tuple[GraphVocabularyEntry, ...] = (
    _entry("receive_request", "receive_request", "node", "runtime", True),
    _entry("investigate", "investigate", "node", "runtime", True),
    _entry("clarification_gate", "clarification_gate", "node", "runtime", True),
    _entry("approval_gate", "approval_gate", "node", "runtime", True),
    _entry("action_draft", "action_draft", "node", "runtime", True),
    _entry("final_response", "final_response", "node", "runtime", True),
```

**Risk/router tests to copy**  
**Analogs:** `tests/test_graph_routing.py` lines 96-149, 152-229, 233-297; `tests/agent/test_nodes/test_assess_risk_and_approval.py` lines 168-191
```python
def test_route_after_risk_returns_approval_gate_when_required_snapshot_refs_are_present():
    assert route_after_risk(_risk_route_state()) == "approval_gate"


def test_route_after_risk_returns_final_response_for_auto_allowed_snapshot_verified_action():
    state = _risk_route_state(risk_assessment={"approval_required": False, "risk_level": "low"})

    assert route_after_risk(state) == "final_response"
```
```python
def test_route_after_approval_returns_final_response_on_untrusted_ordinary_payload():
    assert route_after_approval({"approval_result": {"decision": "approve"}}) == "final_response"
```
```python
async def test_missing_claim_bundle_for_actionable_recommendation_withholds_action(monkeypatch, base_state):
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("missing claim bundle must block before risk LLM or action proposal")

    monkeypatch.setattr(assess_risk_module, "_get_llm", lambda: ExplodingLLM())
    state = {
        **base_state,
        "recommendation_draft": {
            "recommended_action": "issue_coupon",
            "reasoning_summary": "Issue a small service recovery coupon.",
        },
        "business_context": {"order": {"id": "order-1", "status": "paid"}},
    }

    result = await assess_risk_module.assess_risk_and_approval(state)

    assert result["proposed_action"] is None
    assert result.get("action_payload_hash") is None
    assert result.get("safety_snapshot_ref") is None
    assert result.get("safety_snapshot_hash") is None
    assert result.get("safety_snapshot_verified") is False
```

### Approval Gate, ApprovalService, and Manager Scope

**Apply to:** `src/agent/nodes/approval_gate.py`, `src/approvals/service.py`, `src/approvals/repository.py`, `src/approvals/policy.py`, `src/api/routers/approvals.py`, `src/api/schemas/approvals.py`, `src/platform/trusted_context.py`, `tests/test_approval_api.py`, `tests/approvals/test_service_transitions.py`, `tests/approvals/test_hash_binding.py`, `tests/platform/test_merchant_scope.py`, `tests/tools/test_merchant_scope_static.py`

**Approval gate is display/interrupt only**  
**Analog:** `src/agent/nodes/approval_gate.py` lines 26-64
```python
async def approval_gate(state: AgentState) -> dict:
    """Interrupt graph execution until a human approval decision resumes it."""
    started_at = _now_iso()
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action") or {}

    # interrupt_payload proposed_action is display-only; ApprovalService owns persistence.
    interrupt_payload = {
        "run_id": state.get("current_run_id"),
        "tenant_id": state.get("tenant_id"),
        "user_id": state.get("user_id"),
        "proposed_action": proposed,
        "risk_level": risk.get("risk_level"),
        "risk_reason": risk.get("risk_reason"),
        "risk_rule_ref": risk.get("rule_ref"),
        "approval_revision_refs": state.get("approval_revision_refs") or [],
        "action_payload_hash": state.get("action_payload_hash"),
        "safety_snapshot_ref": state.get("safety_snapshot_ref"),
        "safety_snapshot_hash": state.get("safety_snapshot_hash"),
```

**ApprovalService create/decide pattern**  
**Analog:** `src/approvals/service.py` lines 77-130, 173-232, 752-811
```python
async def create_request(self, command: ApprovalRequestCreateCommand) -> ApprovalRequestCreateResult:
    self._assert_create_context(command)
    try:
        async with self.session.begin_nested():
            snapshot = await self._load_or_persist_snapshot(command)
            assignment_plan = self.policy.default_single_level_assignment(
                now=command.created_at,
                required_role=command.required_role,
                mode=command.level_mode,
            )
            request, level, assignment, event = await self.repository.create_request_with_single_level(
                tenant_id=command.tenant_id,
                run_id=command.run_id,
                thread_id=command.thread_id,
                requested_by=command.requested_by,
                proposed_action=command.proposed_action,
                approval_policy_id=command.approval_policy_id,
                policy_version=command.policy_version,
                risk_level=command.risk_level,
                risk_rule_ref=command.risk_rule_ref,
                action_payload_hash=snapshot.action_payload_hash,
                safety_snapshot_ref=snapshot.safety_snapshot_ref,
                safety_snapshot_hash=snapshot.safety_snapshot_hash,
```
```python
async def decide(self, command: ApprovalDecisionCommand) -> ApprovalDecisionResult:
    try:
        async with self.session.begin_nested():
            request = await self.repository.lock_request(command.approval_id, command.tenant_id)
            if request is None:
                raise ApprovalTransitionError("approval_not_found")

            self._assert_executable_request(request)
            self._assert_request_binding(request, command)
            await self._assert_snapshot_binding(request)
            self._assert_hash_binding(request, command)
            self.repository.assert_request_versions(
                request,
                expected_request_version=command.expected_request_version,
                expected_revision=command.expected_revision,
            )
```
```python
trusted = TrustedApprovalResultV1(
    approval_id=request.id,
    tenant_id=request.tenant_id,
    run_id=request.run_id,
    status=request.status,
    decision_type=decision_type,
    revision=request.revision,
    request_version=request.version,
    level_version=level.version,
    assignment_version=assignment.version,
    action_payload_hash=request.action_payload_hash,
    safety_snapshot_ref=request.safety_snapshot_ref,
    safety_snapshot_hash=request.safety_snapshot_hash,
    decided_by=actor_id,
    decided_at=decided_at,
    reason=reason,
    clarification_request_id=clarification_request_id,
    superseded_by_request_id=superseded_by_request_id,
    new_action_payload_hash=new_action_payload_hash,
    edited_action=edited_action,
    resume_route=resume_route,
).model_dump(mode="json")
```

**Repository event/resource-ref pattern**  
**Analog:** `src/approvals/repository.py` lines 161-199, 299-348
```python
request = ApprovalRequest(
    tenant_id=tenant_id,
    run_id=run_id,
    thread_id=thread_id,
    schema_version="approval_request.v2",
    status="pending",
    approval_policy_id=approval_policy_id,
    policy_version=policy_version,
    revision=request_revision,
    version=1,
    action_payload_hash=action_payload_hash,
    safety_snapshot_ref=safety_snapshot_ref,
    safety_snapshot_hash=safety_snapshot_hash,
    legacy_non_executable=False,
    requested_by=requested_by,
    proposed_action=proposed_action,
    risk_level=risk_level,
    risk_rule_ref=risk_rule_ref,
    risk_reason=risk_reason,
    expires_at=expires_at,
)
```
```python
safe_resource_refs = {
    "request_ref": f"approval_request:{request.id}:r{request.revision}",
    "revision_ref": f"approval_revision:{request.id}:r{request.revision}:v{request.version}",
    "request_version": request.version,
    "action_payload_hash": request.action_payload_hash,
    "safety_snapshot_ref": request.safety_snapshot_ref,
    "safety_snapshot_hash": request.safety_snapshot_hash,
    **(resource_refs or {}),
}
```

**API auth/error/resume pattern**  
**Analog:** `src/api/routers/approvals.py` lines 49-130, 574-641, 651-681
```python
@router.post("/{approval_id}/decide", response_model=ApiResponse)
async def decide_approval(
    approval_id: str,
    body: DecideRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Security(get_current_user, scopes=["approvals:review"]),
) -> ApiResponse:
    _assert_approval_reviewer(user)

    approval_uuid = _parse_approval_id(approval_id)
    service = ApprovalService(session)
```
```python
trusted_context = TrustedContextFactory.create_from_request(
    user=actor_user,
    verified_token_scopes=frozenset(),
    thread_id=result.graph_thread_id,
    run_id=str(result.run_id),
    trace_id=getattr(request.state, "trace_id", "") or "",
    server_tool_permissions=permissions,
)
```
```python
def _approval_http_error(exc: ApprovalTransitionError) -> HTTPException:
    if exc.code == "approval_not_found":
        return HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Approval not found"})
    if exc.code == "approval_forbidden":
        return HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": str(exc)})
    if exc.code == "approval_hash_mismatch":
        return HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Approval hash mismatch"})
    if exc.code == "approval_not_executable":
        return HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Approval is not executable"})
    return HTTPException(status_code=409, detail={"code": "CONFLICT", "message": str(exc)})
```

**Trusted merchant scope pattern**  
**Analog:** `src/platform/trusted_context.py` lines 25-70, 106-215
```python
class MerchantScopeV1(BaseModel):
    """Merchant scope with deny-first, all-provided-dimensions semantics."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["merchant_scope.v1"] = MERCHANT_SCOPE_SCHEMA_VERSION
    merchant_ids: list[str]
    categories: list[str] | None = None
    risk_levels: list[str] | None = None
    match_rule: Literal["all_provided_dimensions"] = "all_provided_dimensions"
```
```python
if role in MERCHANT_BOUND_ROLES:
    merchant_id = getattr(user, "merchant_id", None)
    return MerchantScopeV1(merchant_ids=[str(merchant_id)] if merchant_id is not None else [])

if role in PLATFORM_ADMIN_ROLES:
    return MerchantScopeV1(merchant_ids=["*"])

return MerchantScopeV1(merchant_ids=[])
```
```python
if "*" in override_scope.merchant_ids:
    raise ValueError("server merchant scope cannot widen non-admin merchant scope")

allowed_ids = set(base_scope.merchant_ids)
requested_ids = set(override_scope.merchant_ids)
if not requested_ids.issubset(allowed_ids):
    raise ValueError("server merchant scope cannot add merchant ids for non-admin actors")
```

**Current manager interim guard to replace**  
**Analogs:** `src/approvals/policy.py` lines 9-48; `tests/test_approval_api.py` lines 847-871
```python
APPROVAL_ROLES = {"admin"}
```
```python
def assert_actor_can_review(self, *, actor_role: str, assigned_role: str | None = None) -> None:
    if actor_role not in self.allowed_roles:
        raise ApprovalPolicyError("approval_forbidden", "actor role cannot review approvals")
    if assigned_role and actor_role != assigned_role and actor_role != "admin":
        raise ApprovalPolicyError("approval_forbidden", "actor role does not match assignment")
```
```python
async def test_manager_approval_review_paths_return_403(
    client: AsyncClient,
    session: AsyncSession,
    seeded_session,
    monkeypatch,
):
    bundle = await _create_approval(session, seeded_session, thread_id="thread-manager-deny")
    monkeypatch.setattr(app.state, "agent_graph", FakeResumeGraph(), raising=False)
    manager_headers = await _manager_headers(client)

    list_response = await client.get("/api/v1/approvals", headers=manager_headers)
    get_response = await client.get(f"/api/v1/approvals/{bundle.approval.id}", headers=manager_headers)
    decide_response = await client.post(
        f"/api/v1/approvals/{bundle.approval.id}/decide",
        json=_decision_body(bundle),
        headers=manager_headers,
    )

    assert list_response.status_code == 403
    assert get_response.status_code == 403
    assert decide_response.status_code == 403
```

**Manager scope tests to copy when restoring access**  
**Analogs:** `tests/platform/test_merchant_scope.py` lines 80-113; `tests/tools/test_merchant_scope_static.py` lines 12-22
```python
@pytest.mark.parametrize("role", ["support", "manager", "merchant"])
def test_require_merchant_access_allows_merchant_bound_same_merchant(role: str) -> None:
    merchant_id = UUID("00000000-0000-0000-0000-000000000001")

    require_merchant_access(_user(role=role, merchant_id=merchant_id), str(merchant_id), resource_name="orders")
```
```python
@pytest.mark.parametrize(
    ("role", "actor_merchant_id", "target_merchant_id"),
    [
        ("support", None, "merchant-target"),
        ("manager", "merchant-primary", "merchant-other"),
        ("merchant", "merchant-primary", "merchant-other"),
        ("supervisor", "merchant-primary", "merchant-primary"),
    ],
)
def test_require_merchant_access_fails_closed(...):
    with pytest.raises(HTTPException) as exc_info:
        require_merchant_access(...)

    assert exc_info.value.status_code == 403
```
```python
def test_production_business_scope_wildcards_stay_inside_trusted_context_factory() -> None:
    offenders: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if path == TRUSTED_FACTORY:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _WildcardMerchantScopeVisitor(path)
        visitor.visit(tree)
        offenders.extend(visitor.offenders)

    assert offenders == []
```

**Hash/revision negative tests**  
**Analogs:** `tests/approvals/test_hash_binding.py` lines 75-160, 173-201; `tests/approvals/test_service_transitions.py` lines 174-193, 236-254
```python
async def test_changed_action_payload_hash_fails_closed(session: AsyncSession, seeded_session):
    request, level, assignment = await _approval_bundle(session, seeded_session)
    actor_id = seeded_session["users"]["admin_user"].id

    await _assert_transition_error(
        session,
        _decision_command(
            request,
            level,
            assignment,
            actor_id=actor_id,
            action_payload_hash="sha256:" + "9" * 64,
        ),
        code="approval_hash_mismatch",
    )
```
```python
payload = {
    "approval_id": request.id,
    "tenant_id": request.tenant_id,
    "run_id": request.run_id,
    "thread_id": request.thread_id,
    "level_id": level.id,
    "assignment_id": assignment.id,
    "actor_id": actor_id,
    "actor_role": actor_role,
    "decision_type": decision_type,
    "expected_request_version": request.version,
    "expected_level_version": level.version,
    "expected_assignment_version": assignment.version,
    "expected_revision": request.revision,
    "action_payload_hash": request.action_payload_hash,
    "safety_snapshot_hash": request.safety_snapshot_hash,
}
```

### Action Draft, Tool Boundary, and No-Real-Execution Projection

**Apply to:** `src/actions/service.py`, `src/actions/drafts.py`, `src/repositories/action_draft_repo.py`, `src/agent/nodes/action_draft.py`, `src/tools/catalog.py`, `src/tools/runtime.py`, `src/tools/platform.py`, `src/tools/policy.py`, `src/tools/executors/action.py`, `src/agent/nodes/final_response.py`, `src/agent/working_state.py`, `tests/test_execute_action.py`, `tests/actions/test_action_draft_v2.py`, `tests/architecture/test_action_draft_boundaries.py`

**Trusted approval validation in node**  
**Analog:** `src/agent/nodes/action_draft.py` lines 233-273
```python
def _approval_result_is_action_authorizing(
    state: AgentState,
    approval: dict[str, Any],
    trusted_context: TrustedContext | None,
) -> bool:
    trusted = _trusted_approval_result(state, approval, trusted_context)
    if trusted is None:
        return False
    return trusted.decision_type in {"accept", "approve"} and trusted.status == "approved"
```
```python
if (
    trusted.action_payload_hash != state.get("action_payload_hash")
    or trusted.safety_snapshot_ref != state.get("safety_snapshot_ref")
    or trusted.safety_snapshot_hash != state.get("safety_snapshot_hash")
):
    return None
```

**Node fail-closed before tool invocation**  
**Analog:** `src/agent/nodes/action_draft.py` lines 274-322
```python
if risk.get("approval_required") and not approval_accepted:
    return {
        "action_result": {
            "status": "error",
            "data": {},
            "error": {
                "error_code": "NOT_APPROVED",
                "message": "Action requires approval but was not approved",
                "retryable": False,
            },
        },
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
    }
if not approval_accepted:
    return {
        "action_result": {
            "status": "error",
            "data": {},
            "error": {
                "error_code": "AUTO_ALLOWED_BINDING_REQUIRED",
                "message": "No-approval action draft requires a durable auto-allowed binding",
                "retryable": False,
            },
        },
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
    }
```

**Tool context and node-only invocation**  
**Analog:** `src/agent/nodes/action_draft.py` lines 343-377
```python
tool_ctx = project_to_tool_context(
    trusted_context,
    request_id=configurable.get("request_id") or run_id,
    tool_call_id=f"{run_id}:action_draft:{ACTION_TOOL_NAME}",
    caller_node="action_draft",
    deadline_at=configurable.get("deadline_at"),
    attempt=1,
    max_attempts=1,
    idempotency_key=f"action_draft_{run_id}_{approval_id or 'auto_allowed'}",
    approval_ref=approval_id,
    safety_snapshot_ref=state.get("safety_snapshot_ref")
    or approval.get("safety_snapshot_ref")
    or risk.get("safety_snapshot_ref")
    or risk.get("snapshot_ref"),
    policy_snapshot_ref=None,
)
```

**ActionService exact binding and idempotency**  
**Analog:** `src/actions/service.py` lines 75-115, 177-232, 287-300
```python
if not action_payload_hash or not safety_snapshot_ref or not safety_snapshot_hash:
    return _tool_error("ACTION_BINDING_REQUIRED", "Action draft requires exact safety binding", retryable=False)

target_id = _target_id(payload)
if target_id is None:
    return _tool_error("TARGET_ID_REQUIRED", "Action draft target_id is required", retryable=False)
try:
    computed_payload_hash = compute_action_payload_hash(payload)
except (CanonicalHashError, TypeError, ValueError):
    return _tool_error(
        "ACTION_BINDING_MISMATCH",
        "Action draft payload does not match approved safety binding",
        retryable=False,
    )
if computed_payload_hash != action_payload_hash or str(payload.get("action_type") or "") != action_type:
    return _tool_error(
        "ACTION_BINDING_MISMATCH",
        "Action draft payload does not match approved safety binding",
        retryable=False,
    )
```
```python
if approval_request_id is None:
    return _tool_error(
        "AUTO_ALLOWED_BINDING_REQUIRED",
        "No-approval action draft requires a durable auto-allowed binding",
        retryable=False,
    )
```
```python
raw_key = f"{tenant_id}:{run_id}:{revision_marker}:{action_type}:{target_id}:{action_payload_hash}"
if len(raw_key) <= 256:
    return raw_key
digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
return f"{tenant_id}:{run_id}:{revision_marker}:key_sha256:{digest}"
```

**Draft persistence idempotency conflict pattern**  
**Analog:** `src/repositories/action_draft_repo.py` lines 37-88, 108-127
```python
insert_stmt = (
    insert(ActionDraft)
    .values(
        run_id=run_id,
        tenant_id=tenant_id,
        approval_request_id=approval_request_id,
        idempotency_key=idempotency_key,
        schema_version="action_draft.v2",
        target_id=target_id,
        approval_revision_ref=approval_revision_ref,
        action_payload_hash=action_payload_hash,
        safety_snapshot_ref=safety_snapshot_ref,
        safety_snapshot_hash=safety_snapshot_hash,
        action_type=action_type,
        status="draft_created",
        payload=payload,
        draft_outcome=draft_outcome,
        execution_mode=execution_mode,
    )
    .on_conflict_do_nothing(
        constraint="uq_action_drafts_tenant_idempotency_key",
    )
    .returning(ActionDraft.id)
)
```
```python
def _same_binding(
    draft: ActionDraft,
    *,
    run_id: UUID,
    tenant_id: UUID,
    action_type: str,
    target_id: str,
    action_payload_hash: str,
    safety_snapshot_ref: str,
    safety_snapshot_hash: str,
) -> bool:
    return (
        draft.tenant_id == tenant_id
        and draft.run_id == run_id
        and draft.action_type == action_type
        and draft.target_id == target_id
        and draft.action_payload_hash == action_payload_hash
        and draft.safety_snapshot_ref == safety_snapshot_ref
        and draft.safety_snapshot_hash == safety_snapshot_hash
    )
```

**Tool catalog/policy pattern**  
**Analogs:** `src/tools/catalog.py` lines 89-100, 217-228; `src/tools/policy.py` lines 316-341
```python
"create_coupon_grant_draft": {
    "type": "object",
    "properties": {
        "approval_request_id": {"type": "string", "minLength": 1},
        "action_type": {"type": "string", "minLength": 1},
        "payload": {"type": "object"},
        "action_payload_hash": {"type": "string", "minLength": 1},
        "safety_snapshot_ref": {"type": "string", "minLength": 1},
        "safety_snapshot_hash": {"type": "string", "minLength": 1},
    },
    "required": ["action_type", "payload", "action_payload_hash", "safety_snapshot_ref", "safety_snapshot_hash"],
}
```
```python
_descriptor(
    "create_coupon_grant_draft",
    kind="write",
    side_effect="write",
    caller_allowlist=["action_draft"],
    event_family="action",
    resource_type=None,
    executor="action",
    exposure="node_only",
    requires_safety_snapshot=True,
    requires_idempotency_key=True,
)
```
```python
if ctx.caller_node not in descriptor.caller_allowlist:
    reason_codes.append("caller_not_allowed")

if descriptor.required_permission not in ctx.permissions:
    reason_codes.append("missing_permission")

if descriptor.side_effect == "write":
    if not (ctx.caller_node == "action_draft" and descriptor.kind == "write"):
        reason_codes.append("side_effect_blocked")

if descriptor.requires_safety_snapshot and not ctx.safety_snapshot_ref:
    reason_codes.append("safety_snapshot_required")
if descriptor.requires_idempotency_key and not ctx.idempotency_key:
    reason_codes.append("idempotency_required")
```

**Action executor pattern**  
**Analog:** `src/tools/executors/action.py` lines 13-47
```python
class ActionToolExecutor:
    executor_name = "action"

    def __init__(self, session: AsyncSession, service: ActionService | None = None) -> None:
        self.service = service or ActionService(session)

    def has_tool(self, name: str) -> bool:
        return name == "create_coupon_grant_draft"

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolCallContext) -> ToolResultV2:
        if name != "create_coupon_grant_draft":
            return result(
                "unavailable",
                "Tool is declared but unavailable",
                code="TOOL_UNAVAILABLE",
                source="tool",
                source_system="action_tool_executor",
            )

        raw_result = await self.service.create_coupon_grant_draft(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            run_id=ctx.run_id,
            approval_request_id=args.get("approval_request_id"),
            idempotency_key=ctx.idempotency_key or "",
            action_type=str(args["action_type"]),
            payload=dict(args["payload"]),
            action_payload_hash=str(args.get("action_payload_hash") or ""),
            safety_snapshot_ref=str(args.get("safety_snapshot_ref") or ""),
            safety_snapshot_hash=str(args.get("safety_snapshot_hash") or ""),
```

**Final response and projection wording**  
**Analogs:** `src/agent/nodes/final_response.py` lines 597-644, 751-765; `src/agent/working_state.py` lines 13-24, 106-150, 309-315
```python
def _is_successful_demo_draft_outcome(draft_outcome: object) -> bool:
    return (
        isinstance(draft_outcome, dict)
        and draft_outcome.get("status") == "not_executed_demo"
        and draft_outcome.get("external_side_effect") is False
    )
```
```python
def _draft_created_text(prefix: str, draft_id: str) -> str:
    return f"{prefix}：补偿草稿已创建（草稿ID：{draft_id}），{DEMO_NOT_EXECUTED_TEXT}。"
```
```python
PROMPT_UNSAFE_STATE_KEYS = frozenset(
    {
        "business_context",
        "retrieved_evidence",
        "approval_result",
        "proposed_action",
        "action_draft",
        "draft_outcome",
        "llm_outputs",
        "trace_steps",
        "node_errors",
    }
)
```
```python
def _draft_artifact(state: AgentState) -> WorkingDraftArtifact | None:
    artifact = _select_safe_fields(
        _mapping(state.get("action_draft")), ("draft_id", "action_type", "status", "summary")
    )
    if not artifact:
        return None
    return WorkingDraftArtifact.model_validate(artifact)
```

**Action-draft tests to copy**  
**Analogs:** `tests/test_execute_action.py` lines 255-420; `tests/actions/test_action_draft_v2.py` lines 241-309; `tests/architecture/test_action_draft_boundaries.py` lines 90-112, 163-210
```python
@pytest.mark.parametrize(
    "missing_field",
    [
        "revision",
        "request_version",
        "level_version",
        "assignment_version",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
    ],
)
async def test_execute_action_blocks_when_approval_result_binding_field_missing(monkeypatch, missing_field: str):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["approval_result"].pop(missing_field)

    result = await action_draft_module.action_draft(state, {"configurable": {"session": object()}})

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "NOT_APPROVED"
    create_draft.assert_not_awaited()
```
```python
async def test_execute_action_without_required_approval_fails_closed(monkeypatch):
    create_draft = AsyncMock()
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["risk_assessment"] = {"approval_required": False}
    state["approval_result"] = None

    result = await action_draft_module.action_draft(state, _trusted_config())

    assert result["action_result"]["status"] == "error"
    assert result["action_result"]["error"]["error_code"] == "AUTO_ALLOWED_BINDING_REQUIRED"
    assert "draft_outcome" not in result
    create_draft.assert_not_awaited()
```
```python
def test_create_coupon_grant_draft_is_node_only_for_action_draft() -> None:
    descriptor = next(
        descriptor for descriptor in ToolCatalog().descriptors() if descriptor.name == "create_coupon_grant_draft"
    )

    assert descriptor.caller_allowlist == ["action_draft"]
    assert descriptor.exposure == "node_only"
    assert descriptor.requires_safety_snapshot is True
    assert _side_effect_allowed("action_draft", descriptor) is True
    assert _side_effect_allowed("execute_action", descriptor) is False
```
```python
def test_working_state_exposes_only_safe_action_draft_artifact() -> None:
    working_state = project_working_state(
        {
            "thread_id": "thread-action-boundary",
            "current_run_id": "run-action-boundary",
            "action_draft": {
                "draft_id": "draft-001",
                "action_type": "coupon_grant",
                "status": "draft_created",
                "summary": "Created a demo coupon draft.",
                "payload": {"amount": 50, "secret": "ACTION_PAYLOAD_SHOULD_NOT_APPEAR"},
                "proposed_action": {"body": "PROPOSED_ACTION_SHOULD_NOT_APPEAR"},
                "snapshot_json": {"secret": "SNAPSHOT_JSON_SHOULD_NOT_APPEAR"},
                "edited_action_json": {"secret": "EDITED_ACTION_SHOULD_NOT_APPEAR"},
                "safety_snapshot_hash": "SAFETY_HASH_SHOULD_NOT_APPEAR",
            },
            "draft_outcome": {
                "status": "not_executed_demo",
                "payload": {"secret": "DRAFT_OUTCOME_SHOULD_NOT_APPEAR"},
            },
        }
    )
```

### Agent Run, Trace, and API Projection Updates

**Apply to:** `src/api/routers/agent_runs.py`, `src/api/routers/traces.py`, `src/repositories/trace_repo.py`, `src/api/schemas/agent_runs.py`, `tests/test_agent_runs_api.py`

**Approval wait payload creation from interrupt**  
**Analog:** `src/api/routers/agent_runs.py` lines 767-818, 819-867
```python
async def _create_approval_wait_payload_from_interrupt(
    *,
    session: AsyncSession,
    user: User,
    run_id: UUID,
    thread_id: str,
    interrupt_data: dict[str, Any],
) -> dict[str, Any]:
    command = _approval_create_command_from_interrupt(
        user=user,
        run_id=run_id,
        thread_id=thread_id,
        interrupt_data=interrupt_data,
    )
    try:
        result = await ApprovalService(session).create_request(command)
    except ApprovalTransitionError as exc:
        raise ApprovalInterruptValidationError([exc.code]) from exc
```
```python
required_fields = [
    "proposed_action",
    "action_payload_hash",
    "safety_snapshot_ref",
    "safety_snapshot_hash",
    "policy_config_version",
    "risk_config_version",
    "retrieval_config_version",
    "evidence_refs",
]
missing = [field for field in required_fields if not interrupt_data.get(field)]
if missing:
    raise ApprovalInterruptValidationError(missing)
```

**SSE payload schema pattern**  
**Analog:** `src/api/schemas/agent_runs.py` lines 24-34
```python
class SseEventPayload(BaseModel):
    evidence_count: int | None = None
    tool_name: str | None = None
    risk_level: str | None = None
    short_summary: str | None = None
    approval_id: str | None = None
    proposed_action: dict[str, Any] | None = None
    final_response: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    rag_claim_summary: dict[str, Any] | None = None
```

**Trace projection pattern**  
**Analogs:** `src/api/routers/traces.py` lines 40-64, 120-144; `src/repositories/trace_repo.py` lines 15-24, 85-124, 135-150
```python
steps = await repo.get_steps(run_uuid)
approvals = await repo.get_approvals(run_uuid)
approval_steps = await repo.get_approval_steps([approval.id for approval in approvals])
drafts = await repo.get_action_drafts(run_uuid)
timeline = repo.build_timeline(steps, approvals, approval_steps, drafts)
rag_claim_summary = repo.build_rag_claim_summary(steps)

trace_data = TraceResponse(
    run_id=str(run.id),
    thread_id=run.thread_id,
    final_status=run.final_status,
    started_at=run.started_at,
    completed_at=run.completed_at,
    total_latency_ms=run.total_latency_ms,
    steps=[_to_trace_step_response(step) for step in steps],
    approvals=[_to_approval_response(approval) for approval in approvals],
    action_drafts=[
        {
            "id": str(draft.id),
            "action_type": draft.action_type,
            "status": draft.status,
            "draft_outcome": _safe_draft_outcome(draft),
        }
        for draft in drafts
    ],
```
```python
def _safe_proposed_action(action: dict[str, Any] | None) -> dict[str, Any]:
    action = action or {}
    return {
        "action_type": action.get("action_type"),
        "amount": action.get("amount"),
        "currency": action.get("currency"),
    }
```
```python
def _safe_draft_outcome(draft: ActionDraft) -> dict[str, Any]:
    outcome = draft.draft_outcome if isinstance(draft.draft_outcome, dict) else {}
    projected = {key: outcome[key] for key in _DRAFT_OUTCOME_KEYS if key in outcome}
    try:
        return DraftOutcomeV1.model_validate(projected).model_dump(mode="json")
    except ValidationError:
        return {"status": "invalid_draft_outcome", "external_side_effect": False}
```

**Agent run API test pattern**  
**Analog:** `tests/test_agent_runs_api.py` lines 1530-1593
```python
async def test_event_generator_treats_stream_interrupt_node_as_approval_required(
    session: AsyncSession,
    seeded_session,
):
    user = seeded_session["users"]["cs_zhang"]
    run = await _create_run(session, tenant_id=user.tenant_id, user_id=user.id, final_status="running")
    await session.commit()

    generator = _event_generator(
        StreamInterruptGraph(),
        _stream_input(run, user),
        {"configurable": {"thread_id": run.thread_id, "session": session}},
        run=run,
        session=session,
        user=user,
    )

    approval_event = None
    async for event in generator:
        if "data" in event and '"event_type": "approval_required"' in event["data"]:
            approval_event = event

    assert approval_event is not None
    approval_data = _event_data(approval_event)
    assert {"approval_id", "proposed_action", "risk_level"}.issubset(approval_data["payload"])
    assert {
        "approval_revision_refs",
        "expected_request_version",
        "expected_level_version",
        "expected_assignment_version",
        "expected_revision",
        "action_payload_hash",
        "safety_snapshot_ref",
        "safety_snapshot_hash",
        "allowed_decision_types",
    }.issubset(approval_data["payload"])
```

### Static and Architecture Closure

**Apply to:** `tests/architecture/test_phase34_approval_action_boundaries.py`, `tests/architecture/test_approval_boundaries.py`, `tests/architecture/test_action_draft_boundaries.py`, `tests/architecture/test_phase33_rag_claim_boundaries.py`, `tests/agent/test_graph.py`

**Approval ownership static guard**  
**Analog:** `tests/architecture/test_approval_boundaries.py` lines 35-84
```python
def test_approval_routers_do_not_import_legacy_approval_repository() -> None:
    violations: list[tuple[str, str]] = []
    for path in (
        ROOT / "src" / "api" / "routers" / "approvals.py",
        ROOT / "src" / "api" / "routers" / "agent.py",
        ROOT / "src" / "api" / "routers" / "agent_runs.py",
    ):
        for module in _imports(path):
            if module == "src.repositories.approval_repo" or module.startswith("src.repositories.approval_repo."):
                violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []
```
```python
def test_approval_service_is_canonical_transition_owner() -> None:
    service_path = ROOT / "src" / "approvals" / "service.py"
    assert service_path.exists()
    classes = [node.name for node in ast.walk(ast.parse(service_path.read_text())) if isinstance(node, ast.ClassDef)]

    assert "ApprovalService" in classes
```

**No real execution / no success sentinel guards**  
**Analog:** `tests/architecture/test_action_draft_boundaries.py` lines 68-112, 146-160
```python
def test_execute_action_is_phase14_compatibility_shim_only() -> None:
    source = _source(SHIM_PATH)

    assert "Phase 14 compatibility shim" in source
    assert "Owner: Phase 14 action-draft-boundary" in source
    assert "Phase 15 Replay Event Contract" in source
    assert "2026-07-16" in source
    assert "execute_action" in _function_names(SHIM_PATH)
    assert "return await action_draft(state, config)" in source
    for forbidden in ("UnifiedToolManager", "ActionToolExecutor", "ActionService", "ActionDraftRepository"):
        assert forbidden not in source
```
```python
def test_source_does_not_depend_on_action_result_success_sentinel() -> None:
    allowed = {
        "src/agent/nodes/action_draft.py",  # compatibility output construction only; guarded above.
    }
    violations: list[tuple[str, int, str]] = []
    for root in SOURCE_ROOTS:
        for path in sorted(root.glob("**/*.py")):
            relative = str(path.relative_to(ROOT))
            if relative in allowed:
                continue
            for line_no, line in enumerate(_source(path).splitlines(), start=1):
                if ACTION_RESULT_SUCCESS_PATTERN.search(line):
                    violations.append((relative, line_no, line.strip()))

    assert violations == []
```

**Ordinary chat cannot forge approval authority**  
**Analog:** `tests/agent/test_graph.py` lines 959-967
```python
async def test_approval_chat_routes_to_clarification_without_tools(monkeypatch):
    deps = _patch_graph_dependencies(monkeypatch, intent="policy_qa")
    graph = build_graph(MemorySaver())

    final_state = await graph.ainvoke(_state("approve APR-1"), _config(deps["tool_manager"], deps["events"]))

    assert deps["tool_manager"].calls == []
    assert final_state["clarification_request"]["reason"] == "approval_chat_not_trusted"
    assert "审批操作需要通过审批入口处理" in final_state["final_response"]
```

**RAG/claim router totality and safe summary pattern**  
**Analog:** `tests/architecture/test_phase33_rag_claim_boundaries.py` lines 100-143, 186-240
```python
def test_rag_and_claim_routers_are_total_and_side_effect_free() -> None:
    claim_routes = {
        route_after_claim_verify({}),
        route_after_claim_verify({"blocked_claims": ["claim-1"]}),
        route_after_claim_verify(
            {
                "claim_verification_bundle": {
                    "overall_status": "verified",
                    "route": "continue",
                    "claim_results": [],
                    "blocked_claims": [],
                    "safe_support_refs": [],
                },
                "proposed_action": {"action_type": "issue_coupon"},
            }
        ),
    }

    assert claim_routes <= {"assess_risk_and_approval", "final_response"}
```
```python
sanitized = sanitize_rag_claim_payload(payload)
serialized = json.dumps(sanitized, ensure_ascii=False, sort_keys=True)

assert set(sanitized["rag_claim_summary"]) == APPROVED_PHASE33_SUMMARY_KEYS
assert sanitized["rag_claim_summary"]["verified_evidence_count"] == 1
assert sanitized["rag_claim_summary"]["safe_support_ref_count"] == 1
for forbidden in (
    "verified_evidence_package",
    "claim_verification_bundle",
    "debug_projection",
    "verifier_projection",
    "RAW_SEMANTIC_SHOULD_NOT_LEAK",
    "OCR_SHOULD_NOT_LEAK",
    "candidate-only",
):
    assert forbidden not in serialized
```

## Shared Patterns

### Strict Contract Models

**Source:** `src/approvals/schemas.py`, `src/actions/schemas.py`, `src/knowledge/schemas.py`, `src/platform/trusted_context.py`  
**Apply to:** All new `ActionProposalV1`, `RiskDecisionV1`, `ApprovalResultV1`, approval/draft/API DTO fields.

Use `BaseModel` with `model_config = ConfigDict(extra="forbid")`, explicit `schema_version` literals, and typed refs (`EvidenceRefV1`, `BusinessFactRefV1`, claim bundle summaries) instead of raw dict authority.

### Hash and Snapshot Authority

**Source:** `src/approvals/snapshot_service.py`, `src/approvals/snapshots.py`  
**Apply to:** `risk_gate`, `ApprovalService`, `ActionService`, tests.

Use `compute_action_payload_hash`, `persist_action_safety_snapshot`, and `ActionSafetySnapshot` ref/hash validation. Do not create new hash profiles or rebuild snapshots in `approval_gate` or `action_draft`.

### Fail-Closed Routing

**Source:** `src/agent/graph.py`, `src/agent/nodes/assess_risk_and_approval.py`, `src/agent/nodes/action_draft.py`  
**Apply to:** `route_after_risk`, `route_after_approval`, auto-allowed binding checks, claim verification checks.

Missing proposed action, missing binding refs, missing snapshot verification, untrusted approval result, unsupported action claim, or missing durable auto-allowed binding routes to `final_response` or a safe error, never to draft creation.

### Trusted Context and Merchant Scope

**Source:** `src/platform/trusted_context.py`, `src/api/routers/approvals.py`, `tests/tools/test_merchant_scope_static.py`  
**Apply to:** manager approval list/get/decide restore, approval resume, action tool calls.

Human resume contexts are created from `TrustedContextFactory.create_from_request(user=...)`. Server code may inject `tool:*` permissions, but non-admin actors must not receive wildcard `server_merchant_scope`. Manager authorization must compare explicit target merchant binding with trusted merchant scope.

### Approval State Machine Ownership

**Source:** `src/approvals/service.py`, `src/approvals/repository.py`, `tests/architecture/test_approval_boundaries.py`  
**Apply to:** approval creation, decisions, edit/respond/revision handling.

`ApprovalService` owns locked row reads, expected-version checks, hash/snapshot checks, policy checks, decision insertion, trusted resume payload generation, and domain errors. API routers map those errors to HTTP responses and should not mutate approval state directly.

### Node-Only Action Tool Boundary

**Source:** `src/tools/catalog.py`, `src/tools/policy.py`, `src/tools/runtime.py`, `src/tools/executors/action.py`  
**Apply to:** action draft creation and any auto-allowed draft path.

Keep `create_coupon_grant_draft` `exposure="node_only"` and `caller_allowlist=["action_draft"]`. Tool policy must enforce caller, permission, side-effect, safety snapshot, and idempotency gates before `ActionToolExecutor`.

### Safe Projection and No Real Execution

**Source:** `src/actions/schemas.py`, `src/agent/nodes/final_response.py`, `src/agent/working_state.py`, `src/repositories/trace_repo.py`  
**Apply to:** prompt working-state projections, API/trace payloads, final responses.

Expose safe refs/summaries and `draft_outcome.v1(status="not_executed_demo", external_side_effect=false)`. Do not expose raw `proposed_action`, raw action payloads, snapshot JSON, approval bodies, or final wording that implies real refund/coupon/ticket execution.

### Validation Entry Point

**Source:** `AGENTS.md`; `34-CONTEXT.md` D-30  
**Apply to:** all plan verification commands.

Use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` or `.venv/bin/pytest ...`. Bare `pytest` and bare `python -m pytest` are invalid in this repository.

## No Analog Found

All classified files have usable analogs. New Phase 34 tests and the new migration should copy existing role-match patterns:

| File | Role | Data Flow | Use Instead |
|---|---|---|---|
| `src/db/migrations/versions/018_phase34_approval_action_bindings.py` | migration | batch | `008_approval_state_machine.py` and `009_action_draft_v2.py` |
| `tests/approvals/test_phase34_boundary_bindings.py` | test | CRUD | `tests/approvals/test_hash_binding.py` and `tests/approvals/test_migration_contract.py` |
| `tests/actions/test_phase34_action_draft_bindings.py` | test | CRUD | `tests/actions/test_action_draft_v2.py` and `tests/test_execute_action.py` |
| `tests/architecture/test_phase34_approval_action_boundaries.py` | test | transform/static | `tests/architecture/test_approval_boundaries.py`, `tests/architecture/test_action_draft_boundaries.py`, and `tests/tools/test_merchant_scope_static.py` |

## Metadata

**Analog search scope:** `src/approvals`, `src/actions`, `src/agent`, `src/api`, `src/db`, `src/tools`, `src/platform`, `src/repositories`, `tests/approvals`, `tests/actions`, `tests/architecture`, `tests/agent`, `tests/platform`, `tests/tools`.  
**Files scanned:** 393 files from `rg --files src tests`.  
**Pattern extraction date:** 2026-06-29.  
**Project instructions loaded:** `AGENTS.md`, `CLAUDE.md`.  
**Project skill dirs:** `.claude/skills` and `.agents/skills` were not present.
