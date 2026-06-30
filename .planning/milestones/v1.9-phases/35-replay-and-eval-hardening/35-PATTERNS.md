# Phase 35: Replay and Eval Hardening - Pattern Map

**Mapped:** 2026-06-29
**Files analyzed:** 31 artifact families
**Analogs found:** 29 / 31

## Pattern Summary

Phase 35 should be planned as six dependency-ordered plans, not as one broad `35-01-PLAN.md`. The roadmap currently lists `35-01-PLAN.md` only as a placeholder (`.planning/ROADMAP.md` lines 405-428); it must be replaced by multiple small plans because Phase 35 spans replay contracts, trace/replay proof and permissions, golden timelines, dev-contract eval gates, release/monitoring artifacts, and final closure.

Core patterns to copy:

1. Replay events are replay-owned. Add coverage through `src/replay/validators.py`, `src/replay/decision_events.py`, and `src/replay/service.py`; do not create a parallel event envelope.
2. Replay persistence validates event type, retention, redaction, resource refs, sequence, and operation pairing before writing `AgentTraceEvent`.
3. If any new replay event type is added, keep `src/replay/validators.py`, `src/db/models.py`, and a migration under `src/db/migrations/versions/` in sync.
4. Trace and replay business-data visibility stays owner/admin-only in Phase 35. Proof fields may be projected, but auth guards must not use `target_merchant_context` or `requested_by.user.merchant_id`.
5. Dev-contract tests should be deterministic `uv run pytest ...` tests. Bare `pytest` and bare `python -m pytest` are invalid for MOCA.
6. Release and monitoring manifests can report `statistical_gate_not_demonstrated`, `pending`, `not_applicable`, or `sample_only`; missing release-scale samples or production telemetry should not block Phase 35.

## Artifact Families and Existing Analogs

| New/Modified Artifact Family | Role | Data Flow | Closest Analog | Match Quality |
| --- | --- | --- | --- | --- |
| `eval/replay/phase35-coverage-matrix.v1.json` or equivalent | config/artifact | batch, transform | `eval/intent/coverage-manifest.v1.json`; `tests/agent/test_intent_manifest.py` | role-match |
| `tests/replay/test_phase35_coverage_matrix.py` | test | batch, transform | `tests/agent/test_intent_manifest.py`; `tests/architecture/test_phase33_rag_claim_boundaries.py` | role-match |
| `src/replay/validators.py` | utility/config | transform | same file event registry and redaction guards | exact |
| `src/db/models.py` `AgentTraceEvent` constraint | model | CRUD/schema | `AgentTraceEvent` event-type check | exact |
| New migration such as `src/db/migrations/versions/019_phase35_replay_events.py` | migration | schema/CRUD | `017_tool_policy_events.py`; `010_replay_event_v3.py` | exact |
| `src/api/routers/traces.py` | route/controller | request-response | same file trace/replay owner/admin guard | exact |
| `src/api/routers/agent_runs.py` | route/controller | request-response, streaming | static guard test in `tests/test_agent_runs_api.py` | role-match |
| `src/agent/merchant_context.py` | utility/projection | transform | same file `project_target_merchant_context` | exact |
| `src/tools/contracts.py` `BusinessFactRefV1` | model/schema | transform | existing strict Pydantic contract | exact |
| `src/business/schemas.py` `BusinessFactResultV1` | model/schema | transform | existing strict Pydantic contract | exact |
| `tests/replay/test_phase35_trace_replay_permissions.py` | test | request-response | `tests/replay/test_replay_api.py`; `tests/test_trace_api.py` | exact |
| `tests/replay/test_phase35_terminal_timelines.py` | test | CRUD, request-response | `tests/replay/test_lifecycle_finalizer.py`; `docs/eval-test-plan.md` | role-match |
| `tests/replay/fixtures/phase35_timelines/*` | test fixture | batch | no exact fixture analog found | no exact analog |
| `tests/replay/test_phase35_redaction_negatives.py` | test | CRUD, request-response | `tests/replay/test_replay_redaction_retention.py`; `tests/replay/test_replay_api.py` | exact |
| `tests/replay/test_phase35_operation_identity.py` | test | event-driven | `tests/replay/test_operation_pairing.py` | exact |
| `eval/replay/dev-contract-manifest.v1.json` | config/artifact | batch, transform | `eval/intent/coverage-manifest.v1.json` | role-match |
| `tests/eval/test_phase35_replay_eval_gates.py` | test | batch, transform | `tests/agent/test_intent_manifest.py` | role-match |
| `tests/architecture/test_phase35_replay_eval_boundaries.py` | test | static analysis | `tests/architecture/test_phase33_rag_claim_boundaries.py`; `test_phase34_approval_action_boundaries.py` | exact |
| `eval/replay/release-gate.v1.json` | config/artifact | batch | `eval/intent/m6-statistical-gate.v1.json` | role-match |
| `eval/replay/monitoring-gate.v1.json` | config/artifact | batch, monitoring | no exact monitoring manifest; use M6 release manifest and `scripts/eval_all.py` report status pattern | partial |
| Optional `scripts/eval_phase35_replay.py` | utility/script | batch | `scripts/eval_all.py`; `scripts/eval_agent.py` | role-match |
| `docs/evaluation.md` | documentation | batch/reporting | same file eval command/report docs | exact |
| `.planning/phases/35-.../35-VALIDATION.md` or closure artifact | documentation | batch | Phase 33 static command parser pattern in `test_phase33_rag_claim_boundaries.py` | partial |

## Key Code Patterns to Copy

### Replay Registry, Redaction, and Retention

**Source:** `src/replay/validators.py` lines 8-32, 34-58, 90-134.

```python
REPLAY_EVENT_TYPES: set[str] = {
    "node_started",
    "node_completed",
    "node_failed",
    "run_status_changed",
    ...
    "tool_policy_visibility_recorded",
    "tool_policy_runtime_auth_recorded",
}

EVENT_RETENTION_CLASSIFICATION: dict[str, str] = {
    "node_started": "trace_event",
    ...
    "tool_policy_runtime_auth_recorded": "tool_policy_event",
}

def validate_event_type(event_type: str) -> None:
    if event_type not in REPLAY_EVENT_TYPES:
        raise ValueError(f"event_type {event_type!r} is not registered for ReplayEventV3")

def guard_redacted_payload(redacted_payload: dict[str, Any]) -> None:
    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in FORBIDDEN_REDACTED_PAYLOAD_KEYS:
                    raise ValueError(f"{path} must not carry {key}")
                walk(child, f"{path}.{key}")

    walk(redacted_payload, "redacted_payload")
```

Apply this to any new event type or payload convention. Add event literals to both `REPLAY_EVENT_TYPES` and `EVENT_RETENTION_CLASSIFICATION`.

### Replay-Owned Decision Event Emission

**Source:** `src/replay/decision_events.py` lines 59-115, 118-136.

```python
async def emit_decision_event(
    session: AsyncSession,
    *,
    replay_context: ReplayContext | None = None,
    run_id: UUID | str | None = None,
    tenant_id: UUID | str | None = None,
    thread_id: str | None = None,
    event_type: str,
    actor: dict[str, Any],
    resource_refs: dict[str, Any],
    redacted_payload: dict[str, Any],
    ...
) -> dict[str, Any]:
    identity = _resolve_identity(...)
    payload = _normalize_redacted_payload(...)
    refs = dict(resource_refs)

    guard_redacted_payload(payload)
    guard_resource_refs(refs)

    from src.replay.service import ReplayService

    raw_event = await ReplayService(session).append_event(
        run_id=identity["run_id"],
        tenant_id=identity["tenant_id"],
        thread_id=identity["thread_id"],
        trace_id=identity["trace_id"],
        event_type=event_type,
        actor=actor,
        resource_refs=refs,
        redacted_payload=payload,
        schema_version=SCHEMA_VERSION,
    )
    return DecisionEventEnvelopeV1.model_validate(raw_event).model_dump(mode="python")
```

Use `reason_code`, `reason_codes`, and `versions` normalization here rather than inventing per-domain replay envelopes.

### Replay Append and Projection

**Source:** `src/replay/service.py` lines 50-145, 147-174, 209-255.

```python
async def append_event(..., event_type: str, resource_refs: dict[str, Any], redacted_payload: dict[str, Any], ...):
    validate_event_type(event_type)
    retention_class = retention_for_event_type(event_type)
    guard_redacted_payload(redacted_payload)
    guard_resource_refs(resource_refs)

    safe_payload = dict(redacted_payload)
    ...
    pairing_result = validate_operation_pairing(existing_events, {...})
    sequence = await self._next_sequence_for_run(run_uuid)
    event_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{run_uuid}:{sequence}")
    row = AgentTraceEvent(..., event_type=event_type, redacted_payload=safe_payload, ...)
    self.session.add(row)
    await self.session.flush()
    return self.project_event(row, pairing_status=pairing_status)
```

```python
async def get_replay(self, run_id: uuid.UUID | str) -> dict[str, Any]:
    events = await self._events_for_run(run_uuid)
    timeline: list[dict[str, Any]] = []
    prior_events: list[AgentTraceEvent] = []
    for event in events:
        pairing_status = validate_operation_pairing(prior_events, event).pairing_status
        timeline.append(self.project_event(event, pairing_status=pairing_status, include_retention_class=False))
        prior_events.append(event)
    response = ReplayResponseV3(..., timeline=timeline, ...)
    return response.model_dump(mode="python", exclude_none=True)
```

New Phase 35 tests should assert this behavior through replay service/API output, not by rerunning LLMs, tools, RAG, or external actions.

### Event-Type Database Sync

**Source:** `src/db/models.py` lines 1250-1272 and `src/db/migrations/versions/017_tool_policy_events.py` lines 21-45.

```python
class AgentTraceEvent(TimestampMixin, Base):
    __tablename__ = "agent_trace_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_trace_events_run_seq"),
        CheckConstraint(
            "schema_version IN ('minimal_event_envelope.v1', 'replay_event.v3')",
            name="ck_agent_trace_events_schema_version",
        ),
        CheckConstraint(
            "event_type IN (..., 'tool_policy_runtime_auth_recorded', 'tool_policy_visibility_recorded')",
            name="ck_agent_trace_events_event_type",
        ),
        CheckConstraint("sequence > 0", name="ck_agent_trace_events_sequence_positive"),
        CheckConstraint("attempt IS NULL OR attempt > 0", name="ck_agent_trace_events_attempt_positive"),
    )
```

```python
def upgrade() -> None:
    op.drop_constraint("ck_agent_trace_events_event_type", "agent_trace_events", type_="check")
    op.create_check_constraint(
        "ck_agent_trace_events_event_type",
        "agent_trace_events",
        "event_type IN (..., 'tool_policy_runtime_auth_recorded', 'tool_policy_visibility_recorded')",
    )

def downgrade() -> None:
    op.drop_constraint("ck_agent_trace_events_event_type", "agent_trace_events", type_="check")
    op.create_check_constraint(...previous_event_type_set...)
```

Critical Phase 35 rule: if dedicated events are added for trusted context, intent/slot policy, business fact scope/freshness, RAG validation, claim verification, or risk decisions, update `src/replay/validators.py`, `src/db/models.py`, and the migration/check constraint together.

### Owner/Admin Trace and Replay Guard

**Source:** `src/api/routers/traces.py` lines 20-39, 76-93.

```python
ADMIN_RUN_VISIBILITY_ROLES = {"admin"}

@router.get("/{run_id}/trace", response_model=ApiResponse)
async def get_run_trace(..., user: User = Security(get_current_user, scopes=["agent:chat"])) -> ApiResponse:
    run = await repo.get_run(run_uuid, user.tenant_id)
    if not run:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})

    if run.user_id != user.id and user.role not in ADMIN_RUN_VISIBILITY_ROLES:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})
```

```python
@router.get("/{run_id}/replay", response_model=ApiResponse)
async def get_run_replay(...):
    run = await repo.get_run(run_uuid, user.tenant_id)
    if not run:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Run not found"})
    if run.user_id != user.id and user.role not in ADMIN_RUN_VISIBILITY_ROLES:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Cannot view this run"})

    replay_response = await ReplayService(session).get_replay(run_uuid)
```

**Tests to copy:** `tests/replay/test_replay_api.py` lines 138-166; `tests/test_trace_api.py` lines 145-174; `tests/test_agent_runs_api.py` lines 1326-1351.

```python
def test_replay_visibility_guard_remains_admin_only_and_ignores_target_merchant_context():
    assert traces_router.ADMIN_RUN_VISIBILITY_ROLES == {"admin"}
    assert "target_merchant_context" not in inspect.getsource(traces_router.get_run_replay)

for viewer in (support, manager, merchant, supervisor, approval_manager):
    response = await client.get(f"/api/v1/agent-runs/{run_id}/replay", headers=_auth_header(viewer, ["agent:chat"]))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
```

Add Phase 35 negatives proving `requested_by.user.merchant_id` is not used as an authorization shortcut. The closest existing static pattern is `tests/architecture/test_phase34_approval_action_boundaries.py` lines 67-73:

```python
source = _source(APPROVALS_ROUTER_PATH)
assert "server_merchant_scope" not in source
assert re.search(r"requested_by.*merchant", source) is None
assert re.search(r"merchant_id.*requested_by", source) is None
```

### Target Merchant and Business Fact Proof Projection

**Source:** `src/agent/merchant_context.py` lines 43-70, 103-114, 151-167.

```python
def project_target_merchant_context(state: Mapping[str, Any]) -> dict[str, Any]:
    explicit = state.get("target_merchant_context")
    if isinstance(explicit, Mapping):
        explicit_status = explicit.get("status")
        if explicit_status in {"deferred", "unavailable", "not_applicable"}:
            return _status(explicit_status, source=_safe_source(...), reason_codes=_safe_reason_codes(...))

    approved_refs = _service_approved_business_fact_refs(state)
    if approved_refs:
        return _status("resolved", source="business_fact_refs", reason_codes=[], business_fact_ref_count=len(approved_refs))
    if _has_malformed_or_denied_business_context(state):
        return _status("unavailable", source="business_fact_refs", reason_codes=[UNAVAILABLE_REASON])
    if _is_business_scoped_path(state):
        return _status("deferred", source="business_fact_refs", reason_codes=[DEFERRED_REASON])
    return _status("not_applicable", source="intent_policy", reason_codes=[])
```

```python
def _is_service_approved_business_fact_ref(ref: Mapping[str, Any], *, tenant_id: str | None) -> bool:
    if ref.get("schema_version") not in {None, "business_fact_ref.v1"}:
        return False
    if not _non_empty_str(ref.get("resource_type")) or not _non_empty_str(ref.get("resource_id")):
        return False
    if tenant_id and ref.get("tenant_id") != tenant_id:
        return False
    if ref.get("source_system") not in _TRUSTED_REF_SOURCES:
        return False
    return True
```

**Tests to copy:** `tests/agent/test_trace.py` lines 164-190, 232-257, 260-294.

```python
projection = project_target_merchant_context(state)
assert projection == {
    "schema_version": "target_merchant_context.v1",
    "status": "resolved",
    "source": "business_fact_refs",
    "reason_codes": [],
    "business_fact_ref_count": 1,
}
for forbidden in ("ORD-SECRET-001", "MERCHANT-SECRET", "TICKET-SECRET"):
    assert forbidden not in serialized
```

Existing strict schemas:

**Source:** `src/tools/contracts.py` lines 58-69 and `src/business/schemas.py` lines 20-41.

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
class BusinessFactResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok", "partial", "not_found", "permission_denied", "stale", "unavailable", "invalid_request"]
    business_fact_refs: list[BusinessFactRefV1]
    scope_check_result: Literal["allowed", "denied", "not_applicable", "unknown"]
    safe_errors: list[ToolError]
```

Use the fail-closed service pattern from `src/business/service.py` lines 68-87, 237-238, 480-526:

```python
def _merchant_scope_allows(...) -> bool:
    if merchant_scope is None:
        return False
    try:
        scope = MerchantScopeV1.model_validate(merchant_scope)
    except (TypeError, ValueError, ValidationError):
        return False
    return scope.allows(...)

if not _merchant_scope_allows(ctx.merchant_scope):
    return self._permission_denied_result(resource_name, ctx.tenant_id)

return BusinessFactResultV1(
    tenant_id=tenant_id,
    status=status,
    fact=None,
    business_fact_refs=[],
    scope_check_result=scope_check_result,
    missing_required_facts=[resource_name],
    safe_errors=safe_errors,
)
```

### Golden Replay Timelines

**Source:** `src/replay/lifecycle.py` lines 20-182, 184-217.

```python
async def mark_running(...): return await self._append_status_event(status="running", reason_code=reason_code, ...)
async def mark_interrupted(...): return await self._append_status_event(status="interrupted", ...)
async def mark_resumed(...): return await self._append_status_event(status="resumed", ...)
async def mark_completed(...): return await self._append_status_event(status="completed", ...)
async def mark_rejected(...): return await self._append_status_event(status="rejected", ...)
async def mark_expired(...): return await self._append_status_event(status="expired", ...)
async def mark_error(...): return await self._append_status_event(status="error", ...)
async def mark_cancelled(...): return await self._append_status_event(status="cancelled", ...)

return await self.replay_service.append_event(
    event_type="run_status_changed",
    actor={"type": "system", "id": "run_lifecycle_service"},
    resource_refs={"run_id": str(run_uuid)},
    redacted_payload=payload,
)
```

**Tests to copy:** `tests/replay/test_lifecycle_finalizer.py` lines 65-91, 115-161, 164-200.

```python
rows = await _lifecycle_rows(session, run_id)
assert [row.sequence for row in rows] == [1, 2]
assert [row.redacted_payload["status"] for row in rows] == ["running", "completed"]
assert _required_lifecycle_payload(rows[1].redacted_payload) == {
    "status": "completed",
    "previous_status": "running",
    "reason_code": "normal_completed",
}
```

```python
@pytest.mark.parametrize(
    ("method_name", "status", "reason_code", "extra_kwargs"),
    [
        ("mark_rejected", "rejected", "approval_rejected", {}),
        ("mark_expired", "expired", "approval_expired", {}),
        ("mark_error", "error", "graph_error", {"error_code": "GRAPH_ERROR"}),
        ("mark_cancelled", "cancelled", "client_cancelled", {}),
    ],
)
async def test_rejected_expired_error_cancelled_lifecycles_append_safe_terminal_status(...):
    ...
```

Use `docs/eval-test-plan.md` lines 313-399 as the target timeline examples for normal completed, interrupted/resumed, error, cancelled, responded/needs-info, and expired runs. Phase 35 must also cover rejected.

### Operation Identity

**Source:** `tests/replay/test_operation_pairing.py` lines 32-58, 61-77, 97-110, 113-123.

```python
started = _event("tool_call_started", operation_id=operation_id)
completed = _event("tool_call_completed", operation_id=operation_id)
result = validate_operation_pairing([started], completed)
assert result.pairing_status == OperationPairingStatus.PAIRED

with pytest.raises(OperationPairingError, match="operation_id"):
    validate_operation_pairing([], _event("tool_call_started", operation_id=None, attempt=1))
```

Phase 35 golden timelines should assert operation IDs for started/terminal pairs where operation events exist, plus `parent_operation_id` and incremented `attempt` for retries.

### Redaction and Raw Payload Negatives

**Source:** `tests/replay/test_replay_redaction_retention.py` lines 39-74, 77-93, 97-141.

```python
def test_redaction_guard_rejects_recursive_unsafe_keys():
    expected_forbidden = {"raw", "data", "arguments", "prompt", "raw_prompt", "raw_args", "raw_payload", ...}
    assert expected_forbidden <= FORBIDDEN_REDACTED_PAYLOAD_KEYS
    for key in sorted(expected_forbidden):
        with pytest.raises(ValueError, match=key):
            guard_redacted_payload({"safe": [{"nested": {key: "unsafe"}}]})
```

```python
for key in ("raw_prompt", "raw_args", "raw_payload", "raw_tool_output", "secret", "credential", "pii"):
    with pytest.raises(ValueError, match=key):
        await service.append_event(..., redacted_payload={"summary": {key: "unsafe"}})
```

**API projection analog:** `tests/replay/test_replay_api.py` lines 202-241, 244-273.

```python
for forbidden in (
    "verified_evidence_package",
    "claim_verification_bundle",
    "debug_projection",
    "verifier_projection",
    "RAW_SEMANTIC_SHOULD_NOT_LEAK",
):
    assert forbidden not in response.text

assert "raw_payload" not in response_text
assert "secret-coupon-code" not in response_text
assert "proposed_action" not in response_text
assert "action_execution_started" not in response_text
```

**Tool policy event analog:** `tests/replay/test_tool_policy_events.py` lines 80-90, 93-159, 162-197.

```python
assert TOOL_POLICY_VISIBILITY_EVENT in REPLAY_EVENT_TYPES
assert EVENT_RETENTION_CLASSIFICATION[TOOL_POLICY_RUNTIME_AUTH_EVENT] == "tool_policy_event"

event = await emit_decision_event(..., event_type=TOOL_POLICY_RUNTIME_AUTH_EVENT, redacted_payload={...})
assert _has_forbidden_key(event["redacted_payload"]) is None

with pytest.raises(Exception):
    await emit_decision_event(..., redacted_payload={..., forbidden_key: forbidden_value})
```

### Dev-Contract Static and Forbidden-Behavior Tests

**Source:** `tests/architecture/test_phase33_rag_claim_boundaries.py` lines 100-154, 186-250.

```python
assert RAG_CONTEXT_STATUSES == {
    "not_required",
    "verified",
    "partial",
    "no_evidence",
    "unauthorized",
    "stale",
    "conflict",
    "invalid_hash",
    "invalid_scope",
    "build_error",
}

router_source = "\n".join([...])
for forbidden in ROUTER_FORBIDDEN_SNIPPETS:
    assert forbidden not in router_source
```

```python
sanitized = sanitize_rag_claim_payload(payload)
serialized = json.dumps(sanitized, ensure_ascii=False, sort_keys=True)
assert set(sanitized["rag_claim_summary"]) == APPROVED_PHASE33_SUMMARY_KEYS
for forbidden in ("verified_evidence_package", "claim_verification_bundle", "debug_projection", ...):
    assert forbidden not in serialized
```

**Source:** `tests/architecture/test_phase34_approval_action_boundaries.py` lines 75-88, 91-103, 127-137.

```python
for path in sorted(SRC_ROOT.rglob("*.py")):
    tree = ast.parse(_source(path), filename=str(path))
    ...
    if table_name in FORBIDDEN_EXECUTION_TABLES:
        violations.append(...)
assert violations == []

for phrase in FORBIDDEN_EXECUTION_WORDING:
    assert phrase not in _source(FINAL_RESPONSE_PATH)
```

**Action/risk fail-closed analogs:**

`tests/agent/test_nodes/test_assess_risk_and_approval.py` lines 190-264:

```python
class ExplodingLLM:
    def with_structured_output(self, schema):
        raise AssertionError("no-action recommendation should not call the LLM")

result = await assess_risk_module.assess_risk_and_approval(state)
assert result["proposed_action"] is None
```

`tests/agent/test_nodes/test_assess_risk_and_approval.py` lines 400-433:

```python
result = await assess_risk_module.assess_risk_and_approval(state)
assert result["proposed_action"] is None
assert result["approval_plan"] is None
assert result["auto_allowed_binding"] is None
assert result["risk_assessment"]["risk_level"] == "manual_review"
```

`tests/agent/test_nodes/test_rag_context_build.py` lines 203-286:

```python
assert result["rag_context_status"] == "invalid_hash"
assert package["evidence_map"] == {}
assert "tenant_mismatch" in package["reason_codes"]
assert "latest_version_invalid" in package["reason_codes"]
assert wrong_tenant.evidence_id not in ordinary_surface
```

`tests/agent/test_nodes/test_claim_verify.py` lines 233-296:

```python
assert result["claim_verification_bundle"]["route"] == "final_response"
assert result["blocked_claims"] == ["claim-business", "claim-action"]
assert result["safe_support_refs"] == []
assert result["verification_route"] == "refuse"
assert all(
    claim_result["allows_action_recommendation"] is False
    for claim_result in result["claim_verification_bundle"]["claim_results"]
)
```

`tests/actions/test_phase34_action_draft_bindings.py` lines 205-226 and 342-404:

```python
result = await create_coupon_grant_draft(..., **_phase34_tool_kwargs(request, target_merchant_id="merchant-other"))
assert result["status"] == "error"
assert result["error"]["error_code"] == "APPROVAL_BINDING_MISMATCH"
await _assert_no_drafts(session, request.run_id)
```

```python
assert result["status"] == "error"
assert result["error"]["error_code"] == "AUTO_ALLOWED_BINDING_MISMATCH"
await _assert_no_drafts(session, run_id)
```

### Eval Manifest and Gate Separation

**Source:** `eval/intent/coverage-manifest.v1.json` lines 1-12 and `eval/intent/m6-statistical-gate.v1.json` lines 1-24.

```json
{
  "schema_version": "coverage_manifest.v1",
  "dataset_version": "intent-golden.v1",
  "dataset_hash": "sha256:...",
  "owner": "Phase 11 Intent / Clarification",
  "gate_scope": "phase_11_contract",
  "blocking": "phase_exit",
  "failure_impact": "block_phase_11_verification",
  "coverage_status": "complete",
  "m6_statistical_gate_path": "eval/intent/m6-statistical-gate.v1.json"
}
```

```json
{
  "schema_version": "m6_statistical_gate.v1",
  "gate_scope": "m6_release",
  "blocking": "release_safety_sensitive_confidence_assisted_routing",
  "failure_impact": "block_m6_release_not_phase_11_exit",
  "coverage_status": "incomplete",
  "default_gate_status": "statistical_gate_not_demonstrated"
}
```

**Schema and validator analog:** `src/agent/intent_manifest.py` lines 43-72, 98-121, 204-214, 229-253.

```python
class CoverageManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["coverage_manifest.v1"]
    gate_scope: Literal["phase_11_contract"]
    blocking: Literal["phase_exit"]
    failure_impact: Literal["block_phase_11_verification"]
    coverage_status: Literal["complete", "incomplete", "invalid"]

class M6StatisticalGate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gate_scope: Literal["m6_release"]
    failure_impact: Literal["block_m6_release_not_phase_11_exit"]
    coverage_status: Literal["complete", "incomplete", "missing", "invalid"]
    default_gate_status: Literal["statistical_gate_not_demonstrated"]
```

```python
if m6.default_gate_status != "statistical_gate_not_demonstrated":
    errors.append("M6 gate incorrectly claims demonstration")
if coverage.gate_scope == m6.gate_scope:
    errors.append("contract dataset is incorrectly treated as M6 corpus")
```

**Tests to copy:** `tests/agent/test_intent_manifest.py` lines 22-35, 53-72, 100-125.

```python
def test_phase_11_contract_and_m6_release_gate_are_separate():
    coverage = json.loads(COVERAGE.read_text())
    m6 = json.loads(M6.read_text())
    assert coverage["gate_scope"] == "phase_11_contract"
    assert coverage["failure_impact"] == "block_phase_11_verification"
    assert m6["gate_scope"] == "m6_release"
    assert m6["failure_impact"] == "block_m6_release_not_phase_11_exit"
    assert m6["default_gate_status"] == "statistical_gate_not_demonstrated"
```

### Eval Script and Report Pattern

**Source:** `scripts/eval_all.py` lines 29-40, 43-80, 228-251. `Makefile` lines 15-34. `docs/evaluation.md` lines 87-147.

```python
DEFAULT_OUTPUT = "evaluation/reports/latest.json"
DEFAULT_MARKDOWN = "evaluation/reports/latest.md"

def _parser() -> argparse.ArgumentParser:
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to write unified JSON report")
    parser.add_argument("--agent-mode", choices=("ci", "live"), default="ci", help="Agent evaluation mode")
    parser.add_argument("--timestamp", action="store_true", ...)
    return parser

async def run_all_evals(agent_mode: str = "ci") -> dict[str, Any]:
    rag_eval_summary = await run_rag_eval()
    agent_eval_summary = await run_agent_eval(mode=agent_mode)
    return _build_unified_report(rag_eval_summary, agent_eval_summary)
```

```python
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
markdown_path.write_text(markdown, encoding="utf-8")
sys.exit(0 if report["overall_status"] == "pass" else 1)
```

```make
test:
	uv run pytest

eval:
	uv run python scripts/eval_all.py

eval-agent:
	uv run python scripts/eval_agent.py
```

If Phase 35 adds a script, follow the `scripts/eval_all.py` pattern for `--output`, `--timestamp`, JSON/Markdown report pair, and deterministic default mode.

## Per-Plan File Map for Six Recommended Slices

### 35-01 - Coverage Matrix and Replay Contract Inventory

Goal: create the deterministic acceptance map before behavior changes.

| File/Artifact | Role | Data Flow | Analog to Copy |
| --- | --- | --- | --- |
| `eval/replay/phase35-coverage-matrix.v1.json` or equivalent | config/artifact | batch, transform | `eval/intent/coverage-manifest.v1.json` lines 1-12 |
| `tests/replay/test_phase35_coverage_matrix.py` | test | batch, transform | `tests/agent/test_intent_manifest.py` lines 22-35, 53-72 |
| `src/replay/validators.py` if new event types are needed | utility/config | transform | `src/replay/validators.py` lines 8-58 |
| `src/db/models.py` if new event types are needed | model | schema/CRUD | `src/db/models.py` lines 1250-1272 |
| New migration if new event types are needed | migration | schema/CRUD | `src/db/migrations/versions/017_tool_policy_events.py` lines 21-45 |

Planning note: matrix rows should include trusted context projection, intent policy, slot policy, memory load/write policy, tool visibility/runtime auth, business fact read/scope/freshness, RAG validation, claim verification, risk decision, approval lifecycle, and action draft.

If recommending new replay event types, explicitly require synchronized edits to `src/replay/validators.py`, `src/db/models.py`, and migrations. Otherwise prefer existing generic events plus stricter payload conventions.

### 35-02 - Trace/Replay Proof Fields and Owner/Admin-Only Permission Hardening

Goal: make future same-merchant proof inspectable without opening same-merchant access in Phase 35.

| File/Artifact | Role | Data Flow | Analog to Copy |
| --- | --- | --- | --- |
| `src/api/routers/traces.py` | route/controller | request-response | owner/admin guard lines 20-39, 76-93 |
| `src/api/routers/agent_runs.py` | route/controller | request-response, streaming | static guard test `tests/test_agent_runs_api.py` lines 1326-1351 |
| `src/agent/merchant_context.py` | utility/projection | transform | lines 43-70, 103-114, 151-167 |
| `src/tools/contracts.py` | model/schema | transform | `BusinessFactRefV1` lines 58-69 |
| `src/business/schemas.py` | model/schema | transform | `BusinessFactResultV1` lines 20-41 |
| `tests/replay/test_phase35_trace_replay_permissions.py` | test | request-response | `tests/replay/test_replay_api.py` lines 138-166 |
| `tests/test_trace_api.py` | test | request-response | lines 145-174 |
| `tests/test_agent_runs_api.py` | test | request-response, streaming | lines 1326-1351 |
| `tests/agent/test_trace.py` | test | transform | lines 164-190, 232-294 |

Acceptance pattern:

- Cross-tenant remains 404.
- Same-tenant non-owner remains 403.
- `support`, `manager`, `merchant`, `supervisor`, and `approval_manager` cannot read another user's business-data run/trace/replay.
- Static tests prove `target_merchant_context` and `requested_by.user.merchant_id` are not used by authorization guards.
- Proof projection may expose status/source/counts/reason codes, but not raw merchant IDs, order IDs, ticket IDs, raw user queries, or raw tool payloads.

### 35-03 - Golden Replay Timelines, Operation Identity, and Redaction Negatives

Goal: turn lifecycle/replay behavior into golden dev-contract tests for every P0 terminal/current timeline.

| File/Artifact | Role | Data Flow | Analog to Copy |
| --- | --- | --- | --- |
| `tests/replay/test_phase35_terminal_timelines.py` | test | CRUD, request-response | `tests/replay/test_lifecycle_finalizer.py` lines 65-200 |
| `tests/replay/fixtures/phase35_timelines/*` if used | test fixture | batch | no exact existing fixture analog; keep small and JSON-only |
| `tests/replay/test_phase35_operation_identity.py` | test | event-driven | `tests/replay/test_operation_pairing.py` lines 32-123 |
| `tests/replay/test_phase35_redaction_negatives.py` | test | CRUD, request-response | `tests/replay/test_replay_redaction_retention.py` lines 39-141 |
| `src/replay/lifecycle.py` only for fixes | service | event-driven | lines 20-217 |
| `src/replay/service.py` only for fixes | service | CRUD, event projection | lines 50-174, 209-255 |
| `src/replay/validators.py` only for fixes | utility/config | transform | lines 60-134 |

Acceptance pattern:

- Cover normal completed, interrupted approval-required, resumed, rejected, responded/needs-info, expired, error, and cancelled timelines.
- Assert sequence/order and `final_status`/current interrupted status.
- Assert operation pairing where operation IDs exist.
- Assert no raw prompt, raw tool payload, ticket/order/refund PII, raw action payload, secrets, or unsafe debug payloads in replay API output.
- Do not rerun LLMs, tools, RAG, or external actions to produce replay timelines.

### 35-04 - Dev-Contract Eval Gate and Forbidden-Behavior Datasets

Goal: make deterministic forbidden behavior block Phase 35 through pytest-backed gates.

| File/Artifact | Role | Data Flow | Analog to Copy |
| --- | --- | --- | --- |
| `eval/replay/dev-contract-manifest.v1.json` | config/artifact | batch | `eval/intent/coverage-manifest.v1.json` lines 1-12 |
| `tests/eval/test_phase35_replay_eval_gates.py` | test | batch | `tests/agent/test_intent_manifest.py` lines 22-35, 100-125 |
| `tests/architecture/test_phase35_replay_eval_boundaries.py` | test | static analysis | `tests/architecture/test_phase33_rag_claim_boundaries.py` lines 100-250; `test_phase34_approval_action_boundaries.py` lines 75-137 |
| Existing RAG/claim tests | test | transform | `test_rag_context_build.py` lines 203-286; `test_claim_verify.py` lines 233-296 |
| Existing risk/action tests | test | event-driven, CRUD | `test_assess_risk_and_approval.py` lines 190-264, 400-433; action tests above |

Acceptance pattern:

- Unsupported claims block before risk/approval/action.
- No-evidence recommendations do not produce deterministic action recommendations.
- Stale or wrong-scope `BusinessFactRefV1` does not enter action paths.
- Invalid-scope evidence does not enter action paths.
- Approval/action binding mismatch or payload hash mismatch does not produce action drafts.
- Release/monitoring manifest format validation can be a dev-contract blocker; release sample volume and production telemetry absence are not blockers.

### 35-05 - Release and Monitoring Artifact Manifests

Goal: artifactize future release/monitoring gates without blocking Phase 35 on unavailable production-scale data.

| File/Artifact | Role | Data Flow | Analog to Copy |
| --- | --- | --- | --- |
| `eval/replay/release-gate.v1.json` | config/artifact | batch | `eval/intent/m6-statistical-gate.v1.json` lines 1-24 |
| `eval/replay/monitoring-gate.v1.json` | config/artifact | monitoring/batch | no exact analog; combine M6 status semantics with `scripts/eval_all.py` report fields |
| `tests/eval/test_phase35_release_monitoring_manifests.py` | test | batch | `tests/agent/test_intent_manifest.py` lines 27-35, 64-72 |
| Optional `scripts/eval_phase35_replay.py` | utility/script | batch | `scripts/eval_all.py` lines 29-80, 228-251 |
| `docs/evaluation.md` | documentation | batch/reporting | lines 87-147 |

Acceptance pattern:

- Release artifact includes dataset version/hash, coverage manifest hash, command entrypoint, metrics, pass/fail/statistical_gate_not_demonstrated status, and sample-size or coverage gaps.
- Monitoring artifact defines replay completeness, drift, false-negative trend, tool deny reasons, RAG no-evidence trend, and memory write quality.
- Monitoring missing data status should be explicit: `pending`, `not_applicable`, or `sample_only`.
- Manifest tests validate schema and status semantics without requiring production telemetry.

### 35-06 - Final Static/Focused/Eval Closure

Goal: prove APF-17/APF-18 are mapped, tested, and documented without broadening scope.

| File/Artifact | Role | Data Flow | Analog to Copy |
| --- | --- | --- | --- |
| `docs/evaluation.md` if artifact discovery changes | documentation | batch/reporting | lines 87-147 |
| `.planning/phases/35-.../35-VALIDATION.md` or closure artifact | documentation | batch | Phase 33 artifact command parser pattern, `test_phase33_rag_claim_boundaries.py` lines 243-250 and 290-316 |
| Focused final test commands | verification | batch | Research verification commands lines 211-269; Makefile lines 15-34 |
| No real external execution files | architecture constraint | event-driven | `test_phase34_approval_action_boundaries.py` lines 75-88 |

Acceptance pattern:

- Run focused replay/API/eval/architecture commands with `uv run pytest ...`.
- Run `uv run ruff check src/ tests/ scripts/`.
- Confirm APF-17/APF-18 traceability from matrix to tests.
- Confirm no broad `35-01-PLAN.md` remains as the only plan.
- Confirm no physical microservice split and no real external execution was introduced.
- Record any spec-vs-MVP delta rather than silently diverging from `docs/contract-spec.md`.

## Verification Patterns

Only repository-scoped commands are valid. Use `uv run pytest ...` or `.venv/bin/pytest ...`. Bare `pytest` and bare `python -m pytest` are invalid in MOCA.

Focused existing commands to preserve:

```bash
uv run pytest tests/replay/test_decision_events.py tests/replay/test_replay_service.py tests/replay/test_sequence_allocator.py tests/replay/test_operation_pairing.py -q
```

```bash
uv run pytest tests/replay/test_replay_redaction_retention.py tests/replay/test_tool_policy_events.py tests/replay/test_lifecycle_finalizer.py tests/replay/test_replay_api.py -q
```

```bash
uv run pytest tests/test_trace_api.py tests/test_agent_runs_api.py -q
```

```bash
uv run pytest tests/agent/test_trace.py tests/agent/test_memory_write_node.py tests/agent/test_nodes/test_rag_context_build.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q
```

```bash
uv run pytest tests/actions/test_phase34_action_draft_bindings.py tests/actions/test_action_draft_v2.py tests/approvals/test_events.py tests/test_approval_api.py -q
```

```bash
uv run pytest tests/agent/test_intent_manifest.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_phase34_approval_action_boundaries.py tests/architecture/test_tool_boundaries.py -q
```

Likely new Phase 35 commands:

```bash
uv run pytest tests/replay/test_phase35_coverage_matrix.py -q
```

```bash
uv run pytest tests/replay/test_phase35_terminal_timelines.py tests/replay/test_phase35_trace_replay_permissions.py -q
```

```bash
uv run pytest tests/eval/test_phase35_replay_eval_gates.py tests/architecture/test_phase35_replay_eval_boundaries.py -q
```

Eval/report smoke commands:

```bash
uv run python scripts/eval_agent.py --mode ci
```

```bash
uv run python scripts/eval_all.py --agent-mode ci
```

Lint/static command:

```bash
uv run ruff check src/ tests/ scripts/
```

## Planning Risks

1. The roadmap placeholder `35-01-PLAN.md` is only a placeholder. A single broad plan would violate Phase 35 context decisions D-20/D-21 and project plan-granularity rules.
2. New event types can pass Python-level tests but fail database persistence if `src/replay/validators.py`, `src/db/models.py`, and the Alembic-style migration constraint are not updated together.
3. Adding proof fields must not open same-merchant trace/replay visibility. Phase 35 should prove future proof readiness while owner/admin-only authorization remains closed.
4. `requested_by.user.merchant_id` is not acceptable same-merchant authorization proof. Add static and API negatives for this exact shortcut.
5. Release and monitoring artifacts must not accidentally become dev-contract blockers because sample volume or production telemetry is unavailable.
6. Redaction tests must cover API projection, not only append-time validation, because unsafe values can also leak through replay/trace summaries.
7. Replay must remain audit replay. Tests should inspect stored events, stable refs, hashes, versions, reason codes, safe summaries, and redacted payloads, not rerun model/tool/RAG behavior.
8. Spec-vs-implementation gaps must be recorded. Do not silently reinterpret `docs/contract-spec.md`; either correct the spec or record MVP scope/decision notes.

## No Analog Found

| Artifact | Role | Data Flow | Reason |
| --- | --- | --- | --- |
| `tests/replay/fixtures/phase35_timelines/*` | test fixture | batch | Existing replay tests build rows inline; no current fixture directory pattern was found. Keep fixtures minimal if introduced. |
| `eval/replay/monitoring-gate.v1.json` | config/artifact | monitoring/batch | Existing eval artifacts cover contract/release gates, not production monitoring schema. Reuse M6 status semantics plus eval report format. |

## Metadata

**Analog search scope:** `src/`, `tests/`, `eval/`, `scripts/`, `docs/`, `src/db/migrations/versions/`, `.planning/ROADMAP.md`
**Primary analog files read:** `src/replay/validators.py`, `src/replay/service.py`, `src/replay/decision_events.py`, `src/replay/lifecycle.py`, `src/api/routers/traces.py`, `src/agent/merchant_context.py`, `src/tools/contracts.py`, `src/business/schemas.py`, `src/business/service.py`, `src/db/models.py`, replay/API/architecture/action/eval tests, eval manifests, `scripts/eval_all.py`, `docs/evaluation.md`, `Makefile`
**Pattern extraction date:** 2026-06-29

## PATTERN MAPPING COMPLETE
