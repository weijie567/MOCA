# Phase 57: Risk Gate and Approval Gate Canonicalization - Pattern Map

**Mapped:** 2026-07-07  
**Files analyzed:** 34  
**Analogs found:** 34 / 34

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/nodes/risk_gate.py` | graph node | request-response transform | `src/agent/nodes/recommendation_generation.py` + `src/agent/nodes/assess_risk_and_approval.py` | exact |
| `src/agent/nodes/assess_risk_and_approval.py` | compatibility graph node | request-response transform | `src/agent/nodes/generate_recommendation.py` | exact |
| `src/agent/nodes/approval_gate.py` | graph node | event-driven interrupt/resume | `src/agent/nodes/approval_gate.py` | exact |
| `src/agent/graph.py` | graph config | request-response routing | Phase 56 `recommendation_generation` registration in `src/agent/graph.py` | exact |
| `src/agent/routing.py` | route utility | request-response routing | `route_after_claim_verify` / Phase 56 canonical route constants | exact |
| `src/agent/graph_vocabulary.py` | projection utility | transform | Phase 56 `generate_recommendation -> recommendation_generation` entries | exact |
| `src/approvals/schemas.py` | model/schema | request-response validation | `TrustedApprovalResultV1` / `ApprovalDecisionCommand` | exact |
| `src/approvals/service.py` | service | CRUD + event-driven approval lifecycle | `_edit_decision`, `_result`, binding assertions | exact |
| `src/api/routers/approvals.py` | controller/route | request-response + graph resume | `decide_approval`, retry reconstruction, `_should_resume_graph` | exact |
| `src/api/routers/agent_runs.py` | controller/streaming projection | streaming | Phase 56 SSE target-node projection | exact |
| `frontend/src/components/timeline/TimelineStep.tsx` | component | streaming display | existing node message map | role-match |
| `scripts/eval_agent.py` | eval utility | batch | Phase 56 graph-contract patched/legacy node harness | exact |
| `scripts/diagnose_latency.py` | diagnostic utility | batch | existing synthetic step list | role-match |
| `tests/agent/test_nodes/test_risk_gate.py` | test | request-response transform | `tests/agent/test_nodes/test_generate_recommendation.py` + `tests/agent/test_nodes/test_assess_risk_and_approval.py` | exact |
| `tests/agent/test_nodes/test_assess_risk_and_approval.py` | test | request-response transform | Phase 56 compatibility tests in `test_generate_recommendation.py` | exact |
| `tests/agent/test_phase22_action_boundary.py` | test | request-response safety boundary | existing risk/action boundary tests | exact |
| `tests/agent/test_graph.py` | test | graph request-response | Phase 56 graph registration assertions | exact |
| `tests/test_graph_routing.py` | test | request-response routing | existing fail-closed route tests | exact |
| `tests/agent/rag_context/test_routing.py` | test | request-response routing | existing claim-verify route tests | exact |
| `tests/test_approval_gate.py` | test | event-driven interrupt/resume | existing approval gate tests | exact |
| `tests/test_approval_api.py` | test | request-response + graph resume | existing edit resume/retry tests | exact |
| `tests/agent/test_graph_vocabulary.py` | test | transform/projection | Phase 56 runtime/compatibility vocabulary tests | exact |
| `tests/test_agent_runs_api.py` | test | streaming/projection | Phase 56 SSE projection tests | exact |
| `tests/agent/test_trace.py` | test | transform/projection | Phase 56 trace projection tests | exact |
| `tests/test_trace_api.py` | test | transform/projection | Phase 56 trace API projection tests | exact |
| `tests/architecture/graph_baseline.py` | architecture test fixture | static transform | current baseline fixture | exact |
| `tests/architecture/test_canonical_graph_baseline.py` | architecture test | static transform | Phase 56 baseline closeout tests | exact |
| `tests/architecture/test_phase57_risk_gate_canonicalization.py` | architecture test | static transform | `test_canonical_graph_baseline.py` | role-match |
| `docs/current-langgraph-architecture.md` | documentation | documentation transform | Phase 56 current-source graph closeout table | exact |
| `docs/architecture-overview.md` | documentation | documentation transform | current/target graph wording sections | role-match |
| `docs/target-agent-platform-architecture-plan.md` | documentation | documentation transform | target risk/approval authority notes | exact |
| `README.md` | documentation | documentation transform | current runtime graph diagram | role-match |
| `.planning/ARCHITECTURE-DEBT.md` | planning ledger | documentation append | Phase 56 closeout debt entry | exact |
| `moca.egg-info/SOURCES.txt` | generated package metadata | file-I/O | existing source list rows | role-match |

## Pattern Assignments

### `src/agent/nodes/risk_gate.py` (graph node, request-response transform)

**Analog:** `src/agent/nodes/recommendation_generation.py` plus `src/agent/nodes/assess_risk_and_approval.py`

**Imports/canonical wrapper pattern** (`src/agent/nodes/recommendation_generation.py` lines 1-20):
```python
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from src.agent.nodes.generate_recommendation import _CANONICAL_NODE, _generate_recommendation_with_identity
from src.agent.state import AgentState


async def recommendation_generation(state: AgentState, config: RunnableConfig = None) -> dict:
    """Canonical recommendation generation graph node.

    The legacy `generate_recommendation` callable remains importable for
    compatibility; this callable owns current canonical trace/output identity.
    """
    return await _generate_recommendation_with_identity(
        state,
        config,
        output_key=_CANONICAL_NODE,
        trace_node=_CANONICAL_NODE,
    )
```

**Risk implementation imports to preserve** (`src/agent/nodes/assess_risk_and_approval.py` lines 12-32):
```python
import yaml
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from src.agent.context import ContextAssembler, PromptAssembly
from src.agent.context.session_memory_bundle import load_session_prompt_context
from src.agent.prompts import ASSESS_RISK_SYSTEM
from src.agent.routing import _has_allowed_action_recommendation
from src.agent.schemas import RiskAssessment
from src.agent.state import AgentState
from src.agent.working_state import project_working_state
from src.approvals.snapshot_service import (
    ActionSafetySnapshotPersistenceError,
    compute_action_payload_hash,
    persist_action_safety_snapshot,
)
from src.approvals.snapshots import build_action_safety_snapshot
from src.approvals.schemas import PROPOSED_ACTION_SCHEMA_VERSION
from src.approvals.schemas import AutoAllowedActionBindingV1, RiskDecisionV1, TargetMerchantBindingV1
from src.approvals.schemas import TrustedApprovalResultV1
```

**Core output identity to change to canonical** (`src/agent/nodes/assess_risk_and_approval.py` lines 70-92, 1172-1188):
```python
def _trace_step(
    status: str,
    started_at: str,
    provider_latency_ms: int | None = None,
    retry_count: int = 0,
    context_chars: int = 0,
) -> dict[str, Any]:
    return {
        "node": "assess_risk_and_approval",
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "model_name": settings.llm_model,
        ...
    }
```

```python
outputs = {**(state.get("llm_outputs") or {}), "assess_risk_and_approval": assessment}
result = {
    "risk_assessment": assessment,
    "proposed_action": proposed_action,
    "llm_outputs": outputs,
    "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at, ...)],
}
return await _attach_snapshot_binding(...)
```

**Copy rule:** Introduce canonical constants equivalent to `_CANONICAL_NODE = "risk_gate"` and pass/use the canonical identity for current-run `llm_outputs`, `trace_steps[*].node`, and `node_errors`. Keep any legacy identity path explicit and Phase 58-scoped.

**Snapshot/approval binding behavior to preserve** (`src/agent/nodes/assess_risk_and_approval.py` lines 683-715, 750-784, 897-1046):
```python
def _approval_plan(...):
    return {
        "schema_version": "approval_plan.v1",
        "approval_required": assessment.get("approval_required") is True,
        "policy_id": "default-approval-policy",
        "policy_version": POLICY_CONFIG_VERSION,
        "action_payload_hash": action_payload_hash,
        "safety_snapshot_ref": safety_snapshot_ref,
        "safety_snapshot_hash": safety_snapshot_hash,
        "risk_decision_ref": risk_decision_ref,
        "risk_decision": risk_decision.model_dump(mode="json"),
        "approval_idempotency_key": approval_idempotency_key,
        ...
    }
```

```python
def _phase34_fail_closed_result(...):
    safe_assessment = {
        **assessment,
        "approval_required": False,
        "blocked": True,
        "risk_level": "manual_review",
        "risk_reason": reason,
    }
    return {
        **result,
        "risk_assessment": safe_assessment,
        "proposed_action": None,
        "approval_plan": None,
        "risk_decision": None,
        ...
        "safety_snapshot_verified": False,
        "final_response": SAFE_MANUAL_REVIEW_RESPONSE,
    }
```

```python
action_payload_hash = compute_action_payload_hash(proposed_action)
...
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
    target_merchant_id=target_merchant_ref.target_merchant_id,
    target_merchant_ref=target_merchant_ref.model_dump(mode="json"),
    business_fact_refs=[ref.model_dump(mode="json") for ref in business_fact_refs],
    created_at=_fixed_millisecond_now(),
    created_by=user_id,
)
```

### `src/agent/nodes/assess_risk_and_approval.py` (compatibility graph node, request-response transform)

**Analog:** `src/agent/nodes/generate_recommendation.py`

**Compatibility metadata pattern** (`src/agent/nodes/generate_recommendation.py` lines 54-69):
```python
_LEGACY_NODE = "generate_recommendation"
_CANONICAL_NODE = "recommendation_generation"
HISTORICAL_TRACE_PROJECTION = "HISTORICAL_TRACE_PROJECTION"
IMPORT_TEST_COMPATIBILITY = "IMPORT_TEST_COMPATIBILITY"
DELETE_BY_PHASE_58 = "DELETE_BY_PHASE_58"
PHASE_56_COMPATIBILITY_ALIAS = {
    "legacy_surface": _LEGACY_NODE,
    "canonical_owner": _CANONICAL_NODE,
    "reason": IMPORT_TEST_COMPATIBILITY,
    "trace_projection": HISTORICAL_TRACE_PROJECTION,
    "validation_tests": (
        "tests/agent/test_nodes/test_generate_recommendation.py",
        "tests/agent/test_phase22_recommendation_integration.py",
    ),
    "delete_phase": DELETE_BY_PHASE_58,
}
```

**Compatibility callable pattern** (`src/agent/nodes/generate_recommendation.py` lines 192-208):
```python
async def generate_recommendation(state: AgentState, config: RunnableConfig = None) -> dict:
    """Compatibility wrapper for historical imports/tests until Phase 58."""
    return await _generate_recommendation_with_identity(
        state,
        config,
        output_key=_LEGACY_NODE,
        trace_node=_LEGACY_NODE,
    )


async def _generate_recommendation_with_identity(
    state: AgentState,
    config: RunnableConfig = None,
    *,
    output_key: str,
    trace_node: str,
) -> dict:
```

**Test pattern for metadata and current/legacy identity split** (`tests/agent/test_nodes/test_generate_recommendation.py` lines 277-353):
```python
def test_generate_recommendation_compatibility_metadata_is_phase58_scoped():
    source = inspect.getsource(generate_recommendation_module)
    for marker in (
        "PHASE_56_COMPATIBILITY_ALIAS",
        "HISTORICAL_TRACE_PROJECTION",
        "IMPORT_TEST_COMPATIBILITY",
        "DELETE_BY_PHASE_58",
    ):
        assert marker in source
    ...

async def test_canonical_recommendation_generation_writes_canonical_identity_only(...):
    result = await recommendation_generation_module.recommendation_generation(...)
    assert "recommendation_generation" in result["llm_outputs"]
    assert "generate_recommendation" not in result["llm_outputs"]
    assert result["trace_steps"][-1]["node"] == "recommendation_generation"

async def test_legacy_generate_recommendation_keeps_import_compatibility_identity(...):
    result = await generate_recommendation_module.generate_recommendation(...)
    assert "generate_recommendation" in result["llm_outputs"]
    assert "recommendation_generation" not in result["llm_outputs"]
    assert result["trace_steps"][-1]["node"] == "generate_recommendation"
```

### `src/agent/graph.py` (graph config, request-response routing)

**Analog:** Phase 56 `recommendation_generation` registration in the same file.

**Imports to change** (`src/agent/graph.py` lines 23-33):
```python
from src.agent.nodes.assess_risk_and_approval import assess_risk_and_approval
from src.agent.nodes.approval_gate import approval_gate
...
from src.agent.nodes.recommendation_generation import recommendation_generation
```

**Active registration pattern** (`src/agent/graph.py` lines 267-285):
```python
builder.add_node("recommendation_generation", recommendation_generation, retry_policy=_llm_retry)
builder.add_node("claim_verify", claim_verify)
builder.add_node("assess_risk_and_approval", assess_risk_and_approval, retry_policy=_llm_retry)
builder.add_node("clarification_gate", clarification_gate)
builder.add_node("approval_gate", approval_gate)
builder.add_node("action_draft", action_draft)
```

**Conditional edge pattern to canonicalize** (`src/agent/graph.py` lines 347-374):
```python
builder.add_conditional_edges(
    "claim_verify",
    route_after_claim_verify,
    {
        "assess_risk_and_approval": "assess_risk_and_approval",
        "final_response": "final_response",
    },
)
builder.add_conditional_edges(
    "assess_risk_and_approval",
    route_after_risk,
    {
        "assess_risk_and_approval": "assess_risk_and_approval",
        "approval_gate": "approval_gate",
        "action_draft": "action_draft",
        "final_response": "final_response",
    },
)
builder.add_conditional_edges(
    "approval_gate",
    route_after_approval,
    {
        "approval_gate": "approval_gate",
        "assess_risk_and_approval": "assess_risk_and_approval",
        "action_draft": "action_draft",
        "final_response": "final_response",
    },
)
```

**Copy rule:** Follow the Phase 56 pattern: active registration and route-map destinations must use the canonical node key. After cutover, `claim_verify -> risk_gate`, `risk_gate -> ...`, and approval edit rerisk path map should route to `risk_gate`. Do not keep `assess_risk_and_approval` as an active path-map destination except in an explicitly labeled historical compatibility adapter outside active graph registration.

### `src/agent/routing.py` (route utility, request-response routing)

**Analog:** existing route constant + defensive wrapper pattern.

**Route allowlist pattern** (`src/agent/routing.py` lines 23-29):
```python
_INVESTIGATE_ROUTES = {"final_response", "clarification_gate", "rag_context_build", "recommendation_generation"}
_RECOMMENDATION_ROUTES = {"claim_verify", "final_response"}
RAG_CONTEXT_STATUSES = set(SCHEMA_RAG_CONTEXT_STATUSES)
_RAG_CONTEXT_ROUTES = {"recommendation_generation", "clarification_gate", "final_response"}
_CLAIM_VERIFY_ROUTES = {"assess_risk_and_approval", "final_response"}
```

**Fail-closed route wrapper** (`src/agent/routing.py` lines 534-542):
```python
def route_after_claim_verify(state: AgentState) -> str:
    """Route only from claim bundle state to registered graph node keys."""
    try:
        route = _route_after_claim_verify(state)
    except Exception:
        return "final_response"
    if route in _CLAIM_VERIFY_ROUTES:
        return route
    return "final_response"
```

**Claim gate must preserve Phase 56 action authority** (`src/agent/routing.py` lines 581-590):
```python
def _route_after_claim_verify(state: AgentState) -> str:
    if _claim_verify_has_blocked_claims(state):
        return "final_response"
    bundle = _claim_verification_bundle(state)
    if not bundle:
        return "final_response"
    route = bundle.get("route")
    overall_status = bundle.get("overall_status")
    if route != "continue" or overall_status not in {"verified", "not_required"}:
        return "final_response"
```

**Copy rule:** Change only the registered route value from `assess_risk_and_approval` to `risk_gate`; do not weaken the claim verification / allowed action recommendation conditions.

### `src/agent/graph.py` `route_after_risk` / `route_after_approval` (routing helpers)

**Analog:** current fail-closed helpers in `src/agent/graph.py`.

**Risk route fail-closed pattern** (`src/agent/graph.py` lines 70-89):
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
    approval_plan = state.get("approval_plan") if isinstance(state.get("approval_plan"), dict) else {}
    if risk.get("blocked") is True or approval_plan.get("route") == "blocked":
        return "final_response"
    if risk.get("approval_required") is True:
        return "approval_gate" if _approval_plan_ready(state, approval_plan) else "final_response"
    if risk.get("approval_required") is False:
        return "action_draft" if _auto_allowed_binding_ready(state) else "final_response"
    return "final_response"
```

**Approval edit rerisk pattern to canonicalize** (`src/agent/graph.py` lines 132-150):
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

**Trusted result validation pattern** (`src/agent/graph.py` lines 246-259):
```python
def _trusted_approval_result(state: AgentState) -> TrustedApprovalResultV1 | None:
    result = state.get("approval_result") or {}
    if any(not result.get(field) for field in APPROVAL_RESULT_REQUIRED_FIELDS):
        return None
    try:
        trusted = TrustedApprovalResultV1.model_validate(result)
    except ValidationError:
        return None
    if str(trusted.tenant_id) != str(state.get("tenant_id") or ""):
        return None
    if str(trusted.run_id) != str(state.get("current_run_id") or ""):
        return None
```

### `src/agent/nodes/approval_gate.py` (graph node, event-driven interrupt/resume)

**Analog:** current file. Keep this node narrow; do not move risk/action policy into it.

**Interrupt-only pattern** (`src/agent/nodes/approval_gate.py` lines 26-85):
```python
async def approval_gate(state: AgentState) -> dict:
    """Interrupt graph execution until a human approval decision resumes it."""
    started_at = _now_iso()
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action") or {}
    approval_plan = state.get("approval_plan") if isinstance(state.get("approval_plan"), dict) else {}
    ...
    # interrupt_payload proposed_action is display-only; ApprovalService owns persistence.
    interrupt_payload = {
        "run_id": state.get("current_run_id"),
        "tenant_id": state.get("tenant_id"),
        "user_id": state.get("user_id"),
        "proposed_action": proposed,
        "risk_level": risk.get("risk_level"),
        "risk_reason": risk.get("risk_reason"),
        ...
        "approval_plan": approval_plan,
        ...
        "allowed_decision_types": ["accept", "approve", "edit", "respond", "reject", "ignore"],
        "expires_at": (datetime.now(UTC) + timedelta(hours=APPROVAL_TIMEOUT_HOURS)).isoformat(),
    }

    decision = interrupt(interrupt_payload)
    if not isinstance(decision, dict) or decision.get("schema_version") != "approval_result.v1":
        return {
            "approval_result": None,
            "final_response": "审批结果无效，已停止执行高风险操作。",
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }

    return {
        "approval_result": decision,
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("completed", started_at)],
    }
```

### `src/approvals/schemas.py` (model/schema, request-response validation)

**Analog:** current approval command/result schemas.

**Trusted command pattern** (`src/approvals/schemas.py` lines 147-177):
```python
class ApprovalDecisionCommand(BaseModel):
    """Trusted server-side decision command for one request/level/assignment binding."""

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
    ...
```

**Trusted graph resume payload pattern** (`src/approvals/schemas.py` lines 198-232):
```python
class TrustedApprovalResultV1(BaseModel):
    """Trusted graph resume payload produced only by ApprovalService."""

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
    ...
    new_action_payload_hash: str | None = None
    edited_action: dict[str, Any] | None = None
    resume_route: str | None = None
```

### `src/approvals/service.py` (service, CRUD + event-driven approval lifecycle)

**Analog:** current `ApprovalService.decide`, edit decision, result construction, binding assertions.

**Transition/binding pattern** (`src/approvals/service.py` lines 194-230):
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
            self.repository.assert_request_versions(...)
            self._assert_pending_request(request)
            ...
            self.policy.assert_not_self_approval(...)
```

**Edit rerisk route to canonicalize** (`src/approvals/service.py` lines 532-567):
```python
event = await emit_approval_decided(
    ...
    metadata={
        "resume_route": "assess_risk_and_approval",
        "pending_rebind": True,
    },
    resource_refs={
        "old_action_payload_hash": request.action_payload_hash,
        ...
        "new_action_payload_hash": snapshot.action_payload_hash,
    },
)
return self._result(
    ...
    new_action_payload_hash=snapshot.action_payload_hash,
    edited_action=command.edited_action,
    resume_route="assess_risk_and_approval",
)
```

**Trusted result construction pattern** (`src/approvals/service.py` lines 735-769):
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
    **binding_fields,
    decided_by=actor_id,
    decided_at=decided_at,
    ...
    resume_route=resume_route,
).model_dump(mode="json")
```

**Hash/snapshot binding assertions** (`src/approvals/service.py` lines 866-891):
```python
def _assert_request_binding(request: ApprovalRequest, command: ApprovalDecisionCommand) -> None:
    if request.run_id != command.run_id or request.thread_id != command.thread_id:
        raise ApprovalTransitionError("approval_conflict")

async def _assert_snapshot_binding(self, request: ApprovalRequest) -> None:
    snapshot = await self.repository.get_snapshot_by_ref_or_hash(...)
    if snapshot is None or snapshot.action_payload_hash != request.action_payload_hash:
        raise ApprovalTransitionError("approval_not_executable")
    self._assert_snapshot_scope_matches_binding(...)

@staticmethod
def _assert_hash_binding(request: ApprovalRequest, command: ApprovalDecisionCommand) -> None:
    if request.action_payload_hash != command.action_payload_hash or request.safety_snapshot_hash != command.safety_snapshot_hash:
        raise ApprovalTransitionError("approval_hash_mismatch")
```

### `src/api/routers/approvals.py` (controller/route, request-response + graph resume)

**Analog:** current approval decide API.

**Auth/trusted command construction pattern** (`src/api/routers/approvals.py` lines 55-132):
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
    ...
    command = ApprovalDecisionCommand(
        approval_id=approval.id,
        tenant_id=user.tenant_id,
        run_id=approval.run_id,
        thread_id=approval.thread_id,
        level_id=context.level.id,
        assignment_id=context.assignment.id,
        actor_id=user.id,
        actor_role=user.role,
        decision_type=body.decision_type,
        expected_request_version=body.expected_request_version,
        expected_level_version=body.expected_level_version,
        expected_assignment_version=body.expected_assignment_version,
        expected_revision=body.expected_revision,
        action_payload_hash=body.action_payload_hash,
        safety_snapshot_hash=body.safety_snapshot_hash,
        reason=body.reason,
        edited_action=body.edited_action,
        response_text=body.response_text,
    )
```

**Retry compatibility reconstruction to update carefully** (`src/api/routers/approvals.py` lines 570-609):
```python
metadata = event.metadata_json or {}
resource_refs = event.resource_refs_json or {}
...
if decision.decision_type == "edit":
    edited_action = decision.edited_action_json
    new_action_payload_hash = resource_refs.get("new_action_payload_hash")
    resume_route = metadata.get("resume_route")
    if (
        not edited_action
        or body.edited_action != edited_action
        or not new_action_payload_hash
        or resume_route != "assess_risk_and_approval"
    ):
        raise ApprovalTransitionError("approval_conflict")

trusted = TrustedApprovalResultV1(
    ...
    edited_action=edited_action,
    new_action_payload_hash=new_action_payload_hash,
    resume_route=resume_route,
).model_dump(mode="json")
```

**Graph resume decision to canonicalize** (`src/api/routers/approvals.py` lines 756-761):
```python
def _should_resume_graph(result) -> bool:
    if not result.resume_payload:
        return False
    if result.decision_type == "edit":
        return result.resume_payload.get("resume_route") == "assess_risk_and_approval"
    return result.decision_type in {"accept", "approve", "reject", "ignore"}
```

**Response echo pattern** (`src/api/routers/approvals.py` lines 830-855):
```python
def _to_response(approval, *, result=None) -> ApprovalResponse:
    return ApprovalResponse(
        id=str(approval.id),
        run_id=str(approval.run_id),
        thread_id=approval.thread_id,
        ...
        new_action_payload_hash=getattr(result, "new_action_payload_hash", None) if result else None,
        resume_route=(result.resume_payload or {}).get("resume_route") if result and result.resume_payload else None,
        requested_by=str(approval.requested_by),
```

### Projection/API/frontend/eval files

**Apply to:** `src/agent/graph_vocabulary.py`, `src/api/routers/agent_runs.py`, `frontend/src/components/timeline/TimelineStep.tsx`, `scripts/eval_agent.py`, `scripts/diagnose_latency.py`, `tests/agent/test_graph_vocabulary.py`, `tests/test_agent_runs_api.py`, `tests/agent/test_trace.py`, `tests/test_trace_api.py`.

**Graph vocabulary dataclass and reason-code pattern** (`src/agent/graph_vocabulary.py` lines 13-38, 55-60):
```python
@dataclass(frozen=True)
class GraphVocabularyEntry:
    legacy_name: str
    target_name: str
    kind: TargetGraphKind
    status: TargetGraphStatus
    runnable: bool
    reason_codes: tuple[str, ...] = ()
```

```python
_PHASE56_RECOMMENDATION_ALIAS_REASON_CODES = (
    "PHASE_56_COMPATIBILITY_ALIAS",
    "HISTORICAL_TRACE_PROJECTION",
    "IMPORT_TEST_COMPATIBILITY",
    "DELETE_BY_PHASE_58",
)
```

**Runtime plus compatibility alias pattern** (`src/agent/graph_vocabulary.py` lines 144-173):
```python
_entry(
    "generate_recommendation",
    "recommendation_generation",
    "node",
    "compatibility_alias",
    True,
    _PHASE56_RECOMMENDATION_ALIAS_REASON_CODES,
),
_entry(
    "recommendation_generation",
    "recommendation_generation",
    "node",
    "runtime",
    True,
),
...
_entry(
    "assess_risk_and_approval",
    "risk_gate",
    "node",
    "compatibility_alias",
    True,
    ("RISK_GATE_PROJECTED_FROM_ASSESS_RISK_AND_APPROVAL",),
),
```

**Trace projection preserves implementation name** (`src/agent/graph_vocabulary.py` lines 219-229):
```python
def project_trace_step_for_contract(step: Mapping[str, Any]) -> dict[str, Any]:
    implementation_node = str(step.get("node") or "unknown")
    entry = graph_vocabulary_entry(implementation_node, kind="node") or graph_vocabulary_entry(
        implementation_node, kind="router"
    )
    projected = dict(step)
    projected["implementation_node"] = implementation_node
    projected["target_node"] = implementation_node if entry is None else entry.target_name
    projected["target_graph_status"] = "unknown_passthrough" if entry is None else entry.status
    projected["target_graph_runnable"] = True if entry is None else entry.runnable
    return projected
```

**SSE node label and target projection pattern** (`src/api/routers/agent_runs.py` lines 56-68, 1138-1153, 1187-1196):
```python
NODE_MESSAGES: dict[str, str] = {
    ...
    "recommendation_generation": "正在生成处理建议",
    "generate_recommendation": "正在生成处理建议",
    "assess_risk_and_approval": "正在评估风险",
    "approval_gate": "需要审批，等待人工决策",
}
```

```python
if node_name:
    data["target_node_name"] = target_graph_name(node_name, kind="node")
return {"data": json.dumps(data, ensure_ascii=False)}
```

```python
if node_name == "assess_risk_and_approval":
    risk = _as_mapping(update_mapping.get("risk_assessment"))
    if risk.get("risk_level"):
        payload["risk_level"] = risk["risk_level"]
```

**Frontend label map** (`frontend/src/components/timeline/TimelineStep.tsx` lines 5-15):
```tsx
const NODE_MESSAGES: Record<string, string> = {
  receive_request: '正在接收请求',
  classify_intent: '正在识别意图',
  extract_slots: '正在提取关键信息',
  investigate: '正在调查订单和规则',
  recommendation_generation: '正在生成处理建议',
  generate_recommendation: '正在生成处理建议',
  assess_risk_and_approval: '正在判断风险等级',
  approval_gate: '需要审批，等待人工决策',
  execute_action: '正在执行操作',
  final_response: '已完成',
}
```

**Eval harness pattern** (`scripts/eval_agent.py` lines 60-73, 805-810, 886-888):
```python
GRAPH_CONTRACT_PATCHED_NODES = {
    "contextual_intent_resolve",
    "slot_resolution_gate",
    "recommendation_generation",
    "assess_risk_and_approval",
}
GRAPH_CONTRACT_LEGACY_NODES = {
    "classify_intent",
    "session_memory_load",
    "extract_slots",
    "long_term_memory_retrieve",
    "generate_recommendation",
    "execute_action",
}
```

```python
patches = [
    patch.object(contextual_intent_module, "_get_llm", lambda: fake_llms["contextual_intent_resolve"]),
    patch.object(slot_resolution_module, "_get_llm", lambda: fake_llms["slot_resolution_gate"]),
    patch.object(recommendation_impl_module, "_get_llm", lambda: fake_llms["recommendation_generation"]),
    patch.object(assess_risk_module, "_get_llm", lambda: fake_llms["assess_risk_and_approval"]),
    patch.object(assess_risk_module, "persist_action_safety_snapshot", _ci_persist_action_safety_snapshot),
]
```

```python
if case.get("expected_approval_required") or category in {"approval_approved", "approval_rejected", "approval_required"}:
    nodes.append("assess_risk_and_approval")
```

### Test Files

**Apply to:** `tests/agent/test_nodes/test_risk_gate.py`, `tests/agent/test_nodes/test_assess_risk_and_approval.py`, `tests/agent/test_phase22_action_boundary.py`, `tests/agent/test_graph.py`, `tests/test_graph_routing.py`, `tests/agent/rag_context/test_routing.py`, `tests/test_approval_gate.py`, `tests/test_approval_api.py`, `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`, optional `tests/architecture/test_phase57_risk_gate_canonicalization.py`.

**Risk binding test pattern** (`tests/agent/test_nodes/test_assess_risk_and_approval.py` lines 383-444):
```python
async def test_phase34_approval_required_writes_risk_gate_bindings(monkeypatch, base_state):
    ...
    result = await assess_risk_module.assess_risk_and_approval(state)

    assert result["target_merchant_id"] == "merchant-1"
    assert result["business_fact_refs"][0]["resource_id"] == "RF-1001"
    assert result["verified_evidence_refs"] == [evidence_ref]
    assert result["risk_decision_ref"] == f"risk_decision::{result['action_payload_hash']}"
    RiskDecisionV1.model_validate(result["risk_decision"])
    plan = result["approval_plan"]
    assert plan["schema_version"] == "approval_plan.v1"
    assert plan["approval_required"] is True
    assert plan["action_payload_hash"] == result["action_payload_hash"]
    assert plan["safety_snapshot_ref"] == result["safety_snapshot_ref"]
    assert plan["safety_snapshot_hash"] == result["safety_snapshot_hash"]
```

**Fail-closed risk-route tests** (`tests/test_graph_routing.py` lines 493-553):
```python
def test_route_after_risk_fails_closed_when_approval_plan_binding_missing(missing_field):
    state = _risk_route_state()
    state["approval_plan"].pop(missing_field)

    assert route_after_risk(state) == "final_response"

def test_route_after_risk_routes_auto_allowed_only_with_exact_binding():
    state = _risk_route_state(risk_assessment={"approval_required": False, "risk_level": "low"})
    state["auto_allowed_binding"] = _auto_allowed_binding_payload(state)

    assert route_after_risk(state) == "action_draft"

    state["auto_allowed_binding"]["safety_snapshot_hash"] = "sha256:" + "9" * 64
    assert route_after_risk(state) == "final_response"
```

**Approval route trusted/untrusted tests to canonicalize** (`tests/test_graph_routing.py` lines 577-605):
```python
def test_route_after_approval_returns_final_response_on_untrusted_ordinary_payload():
    assert route_after_approval({"approval_result": {"decision": "approve"}}) == "final_response"

def test_route_after_approval_sends_edit_to_risk_reroute_not_action_draft():
    state = _approval_route_state(
        approval_overrides={
            "decision_type": "edit",
            "status": "superseded",
            "new_action_payload_hash": "sha256:" + "3" * 64,
            "resume_route": "assess_risk_and_approval",
        }
    )

    assert route_after_approval(state) == "assess_risk_and_approval"
```

**Graph registration tests to canonicalize** (`tests/agent/test_graph.py` lines 976-1006):
```python
def test_phase56_recommendation_generation_and_claim_verify_are_registered_as_runnable_graph_nodes():
    graph = build_graph(MemorySaver())
    nodes = set(graph.get_graph().nodes)
    conditional_edges = {(edge.source, edge.target) for edge in graph.get_graph().edges if edge.conditional}

    assert "recommendation_generation" in nodes
    assert "generate_recommendation" not in nodes
    assert "claim_verify" in nodes
    assert ("recommendation_generation", "claim_verify") in conditional_edges
    assert ("claim_verify", "assess_risk_and_approval") in conditional_edges

def test_approval_gate_edit_branch_is_registered_in_compiled_graph():
    graph = build_graph(MemorySaver()).get_graph()
    conditional_edges = {(edge.source, edge.target) for edge in graph.edges if edge.conditional}

    assert ("approval_gate", "assess_risk_and_approval") in conditional_edges
    assert ("approval_gate", "action_draft") in conditional_edges
```

**Claim-route tests to canonicalize** (`tests/agent/rag_context/test_routing.py` lines 326-390):
```python
route = route_after_claim_verify(state)

assert route == expected_route
assert route in {"assess_risk_and_approval", "final_response"}
assert route != "continue"
...
assert route == "assess_risk_and_approval"
```

**Architecture baseline pattern** (`tests/architecture/graph_baseline.py` lines 11-57, 95-110):
```python
TARGET_CANONICAL_GRAPH_NODES = frozenset(
    {
        ...
        "claim_verify",
        "risk_gate",
        "approval_gate",
        "action_draft",
        ...
    }
)

CURRENT_ACTIVE_GRAPH_NODES_BASELINE = frozenset(
    {
        ...
        "claim_verify",
        "assess_risk_and_approval",
        ...
    }
)

MIGRATION_MODE_LEGACY_NODE_MAP = {
    "assess_risk_and_approval": {
        "target": "risk_gate",
        "delete_phase": "Phase 57",
        "owner_requirement": "CAGM-08",
    },
}
```

```python
("claim_verify", "route_after_claim_verify"): {
    "assess_risk_and_approval": "assess_risk_and_approval",
    "final_response": "final_response",
},
("approval_gate", "route_after_approval"): {
    "approval_gate": "approval_gate",
    "assess_risk_and_approval": "assess_risk_and_approval",
    "action_draft": "action_draft",
    "final_response": "final_response",
},
```

**Baseline test closeout pattern** (`tests/architecture/test_canonical_graph_baseline.py` lines 65-98):
```python
def test_migration_mode_maps_every_active_legacy_node_to_target() -> None:
    active_legacy_nodes = CURRENT_ACTIVE_GRAPH_NODES_BASELINE - TARGET_CANONICAL_GRAPH_NODES

    assert active_legacy_nodes == frozenset(MIGRATION_MODE_LEGACY_NODE_MAP)
    assert MIGRATION_MODE_LEGACY_NODE_MAP == {
        "assess_risk_and_approval": {
            "target": "risk_gate",
            "delete_phase": "Phase 57",
            "owner_requirement": "CAGM-08",
        },
    }
```

For Phase 57, this should invert: active legacy set should no longer include `assess_risk_and_approval`; retained references belong in graph vocabulary or compatibility tests only.

**Approval API edit/retry tests to canonicalize** (`tests/test_approval_api.py` lines 820-852, 916-986, 1025-1048):
```python
async def test_decide_edit_supersedes_and_resumes_risk_reroute(...):
    ...
    assert command.resume["schema_version"] == "approval_result.v1"
    assert command.resume["decision_type"] == "edit"
    assert command.resume["status"] == "superseded"
    assert command.resume["resume_route"] == "assess_risk_and_approval"
    assert command.resume["edited_action"] == edited_action
    assert command.resume["new_action_payload_hash"] == payload["data"]["new_action_payload_hash"]
```

```python
first_resume = dict(graph.calls[0][0].resume)
assert first_resume["decision_type"] == "edit"
assert first_resume["status"] == "superseded"
assert first_resume["resume_route"] == "assess_risk_and_approval"
...
retry_resume = dict(graph.calls[1][0].resume)
...
for key in (..., "resume_route"):
    assert retry_resume[key] == first_resume[key]
```

**Projection tests to copy for `risk_gate`** (`tests/agent/test_graph_vocabulary.py` lines 221-263; `tests/test_agent_runs_api.py` lines 1032-1068; `tests/agent/test_trace.py` lines 265-284):
```python
def test_phase56_recommendation_generation_runtime_entry_is_identity_mapped() -> None:
    entry = graph_vocabulary_entry("recommendation_generation", kind="node")
    projected = project_trace_step_for_contract({"node": "recommendation_generation", "status": "completed"})
    assert entry.target_name == "recommendation_generation"
    assert entry.status == "runtime"
    assert projected["target_graph_status"] == "runtime"

def test_phase56_generate_recommendation_alias_projects_to_canonical_target_without_rewrite() -> None:
    entry = graph_vocabulary_entry("generate_recommendation", kind="node")
    projected = project_trace_step_for_contract({"node": "generate_recommendation", "status": "completed"})
    assert entry.target_name == "recommendation_generation"
    assert entry.status == "compatibility_alias"
    assert projected["node"] == "generate_recommendation"
    assert projected["implementation_node"] == "generate_recommendation"
```

```python
assert data["node_name"] == "generate_recommendation"
assert data["target_node_name"] == "recommendation_generation"
```

```python
assert summary["nodes_executed"] == ["generate_recommendation", "recommendation_generation"]
assert summary["target_nodes_executed"] == ["recommendation_generation", "recommendation_generation"]
```

### Documentation and Debt Files

**Apply to:** `docs/current-langgraph-architecture.md`, `docs/architecture-overview.md`, `docs/target-agent-platform-architecture-plan.md`, `README.md`, `.planning/ARCHITECTURE-DEBT.md`.

**Current-source doc migration table pattern** (`docs/current-langgraph-architecture.md` lines 88-108):
```markdown
## 当前迁移兼容面

历史 traces 或测试/import surface 中仍可能出现 ... 这些名称只通过 `src/agent/graph_vocabulary.py` 投影到 canonical owner，不能作为 active graph registration、active route destination 或 active policy route value。

| Legacy surface | Canonical owner | Reason | Trace projection | Validation | Delete phase |
...
| Former active `generate_recommendation` graph node and route destination | `recommendation_generation` / Phase 56 CAGM-07 | Phase 56 active graph cutover is complete; persisted traces and direct wrapper callers may still carry the old implementation name | `generate_recommendation -> recommendation_generation`, status `compatibility_alias`, reason codes include `PHASE_56_COMPATIBILITY_ALIAS`, `HISTORICAL_TRACE_PROJECTION`, `IMPORT_TEST_COMPATIBILITY`, `DELETE_BY_PHASE_58`; active graph registers `recommendation_generation`, not `generate_recommendation` | ... | Phase 58 |
| `assess_risk_and_approval` active node | `risk_gate` / Phase 57 CAGM-08 | Risk/approval canonicalization is Phase 57-owned | `assess_risk_and_approval -> risk_gate`, status `compatibility_alias` | Architecture baseline keeps this as active legacy migration row | Phase 57 |
```

**Target authority wording to preserve** (`docs/target-agent-platform-architecture-plan.md` lines 330-340, 336-338):
```markdown
- `risk_gate` 是 canonical node；当前 runtime baseline 中的 `assess_risk_and_approval` 只能作为 legacy alias 映射到该语义，不表示它会替代后续 `approval_gate`。
- `claim_verify` 验证的是 `recommendation_generation` 产出的 material claims / proposed action claim，因此应在生成之后；如果只是 generation 前的证据充足性检查，应归入 `rag_context_build` 或 `route_after_rag_context`。
```

**README/current graph pattern to update** (`README.md` lines 43-67):
```markdown
下图是当前源码 runtime 快照，反映 `src/agent/graph.py` 仍在使用的 legacy/canonical 混合节点名；它不是目标态架构图。
...
V -->|verified action path| G[assess_risk_and_approval]
...
G -->|high risk| I[approval_gate]
G -->|auto draft allowed| J[action_draft]
```

**Architecture debt closeout pattern** (`.planning/ARCHITECTURE-DEBT.md` lines 294-299):
```markdown
- **问题现象/根因**：Phase 56 前后存在三类会混淆当前 authority 的残留面...
- **处理状态**：✅ 已修复验证。`src/agent/graph_vocabulary.py` 将 `recommendation_generation` 标为 runtime node，并将 `generate_recommendation -> recommendation_generation` 标为 Phase 56 `compatibility_alias`...
- **证据**：Phase 56 Plan 56-04；commits ...；文件 ...
- **验证**：`UV_CACHE_DIR=/tmp/uv-cache uv run pytest ... -q --tb=short` → `474 passed, 1 skipped, 32 warnings`...
- **剩余风险**：🟡 Phase 57 仍负责 `assess_risk_and_approval -> risk_gate` active rename 与 approval/risk boundary canonicalization...
```

### `moca.egg-info/SOURCES.txt` (generated package metadata, file-I/O)

**Analog:** existing source list rows (`moca.egg-info/SOURCES.txt` lines 51-55):
```text
src/agent/nodes/__init__.py
src/agent/nodes/action_draft.py
src/agent/nodes/approval_gate.py
src/agent/nodes/assess_risk_and_approval.py
src/agent/nodes/clarification_gate.py
```

If `src/agent/nodes/risk_gate.py` is added and this generated metadata is committed in the repo, planner should include a packaging refresh/verification step. Do not hand-edit this file unless the project already expects generated metadata to be tracked manually.

## Shared Patterns

### Canonical Node Cutover With Compatibility Alias

**Source:** `src/agent/nodes/recommendation_generation.py`, `src/agent/nodes/generate_recommendation.py`, `src/agent/graph_vocabulary.py`  
**Apply to:** `risk_gate.py`, `assess_risk_and_approval.py`, graph vocabulary, node tests, trace/API projection tests.

Use a canonical current-run callable and a narrow legacy import/test wrapper with `HISTORICAL_TRACE_PROJECTION`, `IMPORT_TEST_COMPATIBILITY`, and `DELETE_BY_PHASE_58` metadata. Current graph registration and route values must use the canonical name.

### Route Values Equal Active Graph Node Keys

**Source:** `src/agent/graph.py` lines 347-374; `src/agent/routing.py` lines 23-29, 534-542.  
**Apply to:** `graph.py`, `routing.py`, architecture baseline tests, graph integration tests.

Every router return value must be accepted by its registered path map and point to an active graph node key. For Phase 57, `risk_gate` is the active key; `assess_risk_and_approval` cannot remain a current-run router value.

### Fail-Closed Action/Risk Binding Chain

**Source:** `src/agent/graph.py` lines 70-89; `src/agent/nodes/assess_risk_and_approval.py` lines 750-784, 897-1046; `tests/test_graph_routing.py` lines 493-553.  
**Apply to:** `risk_gate.py`, route tests, action-boundary tests.

Preserve fail-closed behavior for missing/invalid claim verification, business facts, evidence refs, action payload hash, safety snapshot ref/hash, approval plan, risk decision ref, and auto-allowed binding.

### Trusted Approval Boundary

**Source:** `src/api/routers/approvals.py` lines 55-132; `src/approvals/service.py` lines 194-230, 866-891; `src/approvals/schemas.py` lines 147-232.  
**Apply to:** approval API/service/schema tests, `route_after_approval`, `approval_gate.py`.

Only authenticated API/inbox service paths should construct `TrustedApprovalResultV1`. Ordinary chat approval-like text remains untrusted and must route to `final_response` or earlier safety handling, not `approval_gate`, `risk_gate`, or `action_draft`.

### Historical Projection Without Stored Trace Rewrite

**Source:** `src/agent/graph_vocabulary.py` lines 219-229; `src/api/routers/agent_runs.py` lines 1138-1153; `tests/test_agent_runs_api.py` lines 1032-1068; `tests/agent/test_trace.py` lines 265-284.  
**Apply to:** graph vocabulary, trace APIs, SSE payloads, frontend/eval/docs.

Preserve implementation node names for historical rows and expose canonical target names through projection fields. Do not bulk rewrite historical traces in Phase 57.

## No Analog Found

No phase file lacks a usable codebase analog. The only weak match is `moca.egg-info/SOURCES.txt`, which is generated metadata rather than a source pattern; planner should decide whether a package metadata refresh is required after adding `risk_gate.py`.

## Metadata

**Analog search scope:** `src/agent`, `src/approvals`, `src/api/routers`, `tests/agent`, `tests/architecture`, `tests/test_approval_api.py`, `tests/test_graph_routing.py`, `tests/test_agent_runs_api.py`, `frontend/src/components/timeline`, `scripts`, `docs`, `.planning/ARCHITECTURE-DEBT.md`, `moca.egg-info/SOURCES.txt`.  
**Files scanned:** 80+ candidate files via `rg --files` / targeted `rg`; 24 primary analog files read with line-numbered excerpts.  
**Pattern extraction date:** 2026-07-07.  
**Project instructions loaded:** `AGENTS.md`, `CLAUDE.md`; no `.claude/skills` or `.agents/skills` directories exist in this repo.  
**Verification command rule:** all future test commands in plans must use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` or an approved `.venv/bin/...` entrypoint; bare `pytest` and bare `python -m pytest` are invalid in MOCA.
