# Phase 63: Safety Taxonomy And Risk Vocabulary - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 18 planned/new/modified files
**Analogs found:** 18 / 18

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/agent/safety/taxonomy.py` | utility / registry | transform | `src/business/query/registry.py`, `src/agent/graph_vocabulary.py` | exact |
| `src/agent/safety/__init__.py` | package export | import/export | `src/business/query/__init__.py`, `src/actions/__init__.py` | exact |
| `src/agent/nodes/risk_gate.py` | LangGraph node / service | event-driven state transform | existing `src/agent/nodes/risk_gate.py` + `src/agent/graph_vocabulary.py` | exact |
| `src/agent/nodes/action_draft.py` | LangGraph node / ToolPlatform boundary | event-driven state transform + tool I/O | existing `src/agent/nodes/action_draft.py` | exact |
| `src/agent/intent_policy.py` | policy registry / classifier utility | transform | existing `IntentPolicyRegistry` in `src/agent/intent_policy.py` | exact |
| `src/agent/routing.py` | router utility | event-driven decision | existing registry-consuming routes in `src/agent/routing.py` | exact |
| `src/agent/schemas.py` | schema model | validation / transform | existing Pydantic schemas in same file | exact |
| `src/approvals/schemas.py` | compatibility schema model | validation / durable payload | `RiskDecisionV1`, `AutoAllowedActionBindingV1` | exact |
| `src/actions/schemas.py` | compatibility schema model | validation / durable payload | `ActionDraftV2Data`, `DraftOutcomeV1` | exact |
| `tests/agent/test_safety_taxonomy.py` | unit / parity test | transform verification | `tests/agent/test_intent_policy_registry.py`, `tests/agent/test_intent_routing.py` | role-match |
| `tests/agent/test_nodes/test_risk_gate.py` | async node test | event-driven state transform verification | existing risk-gate tests | exact |
| `tests/agent/test_phase22_action_boundary.py` | integration boundary test | event-driven fail-closed verification | existing non-allow verifier tests | exact |
| `tests/actions/test_action_draft_v2.py` | schema/store integration test | CRUD + validation | existing action-draft v2 tests | exact |
| `tests/actions/test_phase34_action_draft_bindings.py` | service integration test | CRUD + binding validation | existing Phase 34 binding tests | exact |
| `tests/agent/test_intent_policy_registry.py` | registry parity test | transform verification | existing registry parity tests | exact |
| `tests/agent/test_intent_routing.py` | router/policy integration test | event-driven decision verification | existing routing parity tests | exact |
| `tests/test_execute_action.py` | action draft boundary test | tool I/O / fail-closed | existing action draft ToolPlatform tests | exact |
| `tests/architecture/test_safety_taxonomy_boundaries.py` | architecture / static drift guard | static file scan | `tests/architecture/test_action_draft_boundaries.py` | exact |

## Pattern Assignments

### `src/agent/safety/taxonomy.py` (utility / registry, transform)

**Primary analog:** `src/business/query/registry.py`

**Secondary analog:** `src/agent/graph_vocabulary.py`

**Imports pattern** (`src/business/query/registry.py` lines 1-6):

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
```

**Descriptor pattern** (`src/business/query/registry.py` lines 8-15):

```python
@dataclass(frozen=True, slots=True)
class BusinessQueryOperationDescriptor:
    id: str
    compatible_resource_ids: frozenset[str]
    metric_ids: frozenset[str] = frozenset()
    group_by_field_ids: frozenset[str] = frozenset()
    comparison_metric_ids: frozenset[str] = frozenset()
```

**Read-only registry pattern** (`src/business/query/registry.py` lines 81-118):

```python
def _read_only_mapping[T](values: Mapping[str, T]) -> Mapping[str, T]:
    return MappingProxyType(dict(values))


class BusinessQueryRegistry:
    def __init__(
        self,
        *,
        operations: Mapping[str, BusinessQueryOperationDescriptor],
        resources: Mapping[str, BusinessQueryResourceDescriptor],
        metrics: Mapping[str, BusinessMetricDescriptor],
        time_presets: Mapping[str, BusinessQueryTimePresetDescriptor],
        fields: Mapping[str, BusinessQueryFieldDescriptor],
        sorts: Mapping[str, BusinessQuerySortDescriptor],
        statuses: Mapping[str, BusinessQueryStatusDescriptor],
    ) -> None:
        self._operations = _read_only_mapping(operations)
        self._resources = _read_only_mapping(resources)
        self._metrics = _read_only_mapping(metrics)
        self._time_presets = _read_only_mapping(time_presets)
        self._fields = _read_only_mapping(fields)
        self._sorts = _read_only_mapping(sorts)
        self._statuses = _read_only_mapping(statuses)
        self._metric_aliases = _read_only_mapping(
            {
                alias: metric.id
                for metric in self._metrics.values()
                for alias in metric.parser_aliases
            }
        )
```

**Vocabulary helper pattern** (`src/agent/graph_vocabulary.py` lines 18-25, 73-75, 157-170):

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
_ENTRY_BY_KIND_AND_NAME = MappingProxyType({(entry.kind, entry.legacy_name): entry for entry in _ENTRIES})
```

```python
def graph_vocabulary_entry(name: str, *, kind: TargetGraphKind | None = None) -> GraphVocabularyEntry | None:
    if kind is not None:
        return _ENTRY_BY_KIND_AND_NAME.get((kind, name))
    matches = [entry for entry in _ENTRIES if entry.legacy_name == name]
    if len(matches) == 1:
        return matches[0]
    return None


def target_graph_name(name: str, *, kind: TargetGraphKind | None = None) -> str:
    entry = graph_vocabulary_entry(name, kind=kind)
    if entry is None:
        return name
    return entry.target_name
```

**Pattern to copy for Phase 63:**

- Define frozen/slotted dataclasses for executable actions, dispositions, action resolution, pre-route action match, and normalized risk vocabulary.
- Store canonical descriptor tuples/mappings once in this module.
- Build alias maps with comprehensions from descriptors, not parallel hand-written sets.
- Return `frozenset`, tuples, or `MappingProxyType`; do not expose mutable dictionaries/sets.
- Helpers should include `resolve_action_text`, `canonical_executable_action_type`, `is_executable_action_type`, `is_actionable_recommendation`, `action_pre_route_match`, and risk severity/disposition normalization.

**Pitfalls:**

- Do not return `manual_review` or `blocked` from an executable-action helper.
- Preserve current compatibility aliases before changing call sites; Phase 63 context requires RED parity tests first.
- Keep ToolPlatform action coverage conservative: coupon/compensation/refund/full refund/partial refund compatibility only; no new write tools.

---

### `src/agent/safety/__init__.py` (package export, import/export)

**Analog:** `src/business/query/__init__.py`

**Re-export pattern** (`src/business/query/__init__.py` lines 1-13, 33-57):

```python
from __future__ import annotations

from src.business.query.registry import (
    BUSINESS_QUERY_REGISTRY,
    BusinessMetricDescriptor,
    BusinessQueryFieldDescriptor,
    BusinessQueryOperationDescriptor,
    BusinessQueryRegistry,
    BusinessQueryResourceDescriptor,
    BusinessQuerySortDescriptor,
    BusinessQueryStatusDescriptor,
    BusinessQueryTimePresetDescriptor,
)
```

```python
__all__ = [
    "BUSINESS_QUERY_REGISTRY",
    "BUSINESS_QUERY_API_PAYLOAD_FIELDS",
    "BusinessQueryAnswerContext",
    "BusinessQueryCompiler",
    "BusinessQueryCursor",
    "BusinessQueryFilterSet",
    "BusinessMetricDescriptor",
    "BusinessQueryFieldDescriptor",
    "BusinessQueryOperationDescriptor",
    "BusinessQueryRegistry",
    "BusinessQueryResultCursor",
    "BusinessQueryResultV1",
    "BusinessQueryResourceDescriptor",
    "BusinessQueryScopeSummary",
    "BusinessQuerySort",
    "BusinessQuerySpec",
    "BusinessQuerySortDescriptor",
    "BusinessQueryStatusDescriptor",
    "BusinessQueryTimePresetDescriptor",
    "business_query_response_text",
    "metric_input_to_business_query",
    "safe_business_query_api_payload",
    "safe_business_query_metadata",
]
```

**Small package pattern** (`src/actions/__init__.py` lines 1-5):

```python
from __future__ import annotations

from src.actions.service import ActionService, create_coupon_grant_draft

__all__ = ["ActionService", "create_coupon_grant_draft"]
```

**Pattern to copy for Phase 63:**

- Add `from __future__ import annotations`.
- Re-export only stable public helpers/descriptors from `taxonomy.py`.
- Keep `__all__` explicit.
- Avoid pulling in graph nodes or heavy runtime dependencies from `__init__.py`.

---

### `src/agent/nodes/risk_gate.py` (LangGraph node / service, event-driven state transform)

**Analog:** existing `src/agent/nodes/risk_gate.py`

**Current duplicate taxonomy to replace** (`src/agent/nodes/risk_gate.py` lines 37-52):

```python
RISK_RULES_PATH = Path("rules/risk_rules.yaml")
POLICY_CONFIG_VERSION = "approval-policy.v1"
RISK_CONFIG_VERSION = "risk-rules.v1"
DEFAULT_RETRIEVAL_CONFIG_VERSION = "retrieval.v1"
SAFE_MANUAL_REVIEW_RESPONSE = "操作需要人工复核，当前未创建可执行审批或动作草稿。"
APPROVAL_DECISION_TYPES = ["accept", "approve", "edit", "respond", "reject", "ignore"]
FULL_REFUND_TERMS = ("full_refund", "全额退款", "全额退", "整单退款")
ACTIONABLE_ACTIONS = {
    "issue_coupon",
    "approve_refund",
    "full_refund",
    "partial_refund",
    "compensation",
    "manual_review",
}
NO_ACTION_RECOMMENDATIONS = {"insufficient_evidence", "citation_invalid", "retrieval_error"}
```

**Current actionability pattern to migrate** (`src/agent/nodes/risk_gate.py` lines 156-180):

```python
def _is_actionable_recommendation(action: Any) -> bool:
    action_text = str(action or "").lower()
    return any(actionable in action_text for actionable in ACTIONABLE_ACTIONS)
```

```python
def _action_requires_claim_bundle(state: AgentState, draft: dict[str, Any]) -> bool:
    if state.get("proposed_action"):
        return True
    action = draft.get("recommended_action")
    return action not in NO_ACTION_RECOMMENDATIONS and _is_actionable_recommendation(action)
```

**Current canonicalizer to replace** (`src/agent/nodes/risk_gate.py` lines 281-298):

```python
def _canonical_action_type(action: Any) -> str:
    action_text = str(action or "")
    lowered = action_text.lower()
    if lowered in ACTIONABLE_ACTIONS:
        return lowered
    if any(term in action_text for term in ("拒绝", "不建议", "无法支持")) or "reject" in lowered:
        return "manual_review"
    if any(term in lowered for term in ("coupon", "compensation", "compensate")) or any(
        term in action_text for term in ("补偿", "券", "赔付")
    ):
        return "issue_coupon"
    if any(term in action_text for term in FULL_REFUND_TERMS):
        return "full_refund"
    if "partial_refund" in lowered or "部分退款" in action_text:
        return "partial_refund"
    if "refund" in lowered or "退款" in action_text:
        return "approve_refund"
    return "manual_review"
```

**Proposed-action construction pattern** (`src/agent/nodes/risk_gate.py` lines 301-331):

```python
def _build_proposed_action(
    *,
    state: AgentState,
    draft: dict[str, Any],
    context: dict[str, Any],
    assessment: dict[str, Any],
    evidence_refs: list[EvidenceRefV1],
) -> dict[str, Any]:
    refund_case = _business_context_resource(context, "refund_case")
    order = _business_context_resource(context, "order")
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

**Risk decision compatibility pattern** (`src/agent/nodes/risk_gate.py` lines 607-640):

```python
def _risk_reason_codes(assessment: dict[str, Any], state: AgentState) -> list[str]:
    reason_codes = {str(code) for code in (_claim_verification_summary(state) or {}).get("reason_codes") or []}
    for key in ("risk_level", "rule_ref"):
        value = assessment.get(key)
        if value:
            reason_codes.add(str(value))
    if assessment.get("approval_required") is True:
        reason_codes.add("approval_required")
    if assessment.get("approval_required") is False:
        reason_codes.add("auto_allowed_candidate")
    return sorted(reason_codes)
```

```python
def _risk_decision(
    *,
    state: AgentState,
    proposed_action: dict[str, Any],
    assessment: dict[str, Any],
    action_payload_hash: str,
) -> RiskDecisionV1:
    return RiskDecisionV1(
        tenant_id=str(state.get("tenant_id") or ""),
        run_id=str(state.get("current_run_id") or ""),
        action_id=str(proposed_action.get("action_id") or ""),
        action_payload_hash=action_payload_hash,
        risk_level=str(assessment.get("risk_level") or ""),
        reason_codes=_risk_reason_codes(assessment, state),
        policy_config_version=POLICY_CONFIG_VERSION,
        risk_config_version=RISK_CONFIG_VERSION,
        approval_required=assessment.get("approval_required") is True,
        evaluated_at=_now_iso(),
        risk_rule_ref=str(assessment.get("rule_ref")) if assessment.get("rule_ref") else None,
        risk_reason=str(assessment.get("risk_reason")) if assessment.get("risk_reason") else None,
    )
```

**Fail-closed pattern to preserve while separating disposition** (`src/agent/nodes/risk_gate.py` lines 762-796):

```python
def _phase34_fail_closed_result(
    result: dict[str, Any],
    assessment: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
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
        "risk_decision_ref": None,
        "target_merchant_id": None,
        "target_merchant_ref": None,
        "business_fact_refs": [],
        "verified_evidence_refs": [],
        "claim_verification_ref": None,
        "claim_verification_summary": None,
        "approval_idempotency_key": None,
        "auto_allowed_binding": None,
        "auto_allowed": False,
        "action_payload_hash": None,
        "safety_snapshot_ref": None,
        "safety_snapshot_hash": None,
        "safety_snapshot_verified": False,
        "final_response": SAFE_MANUAL_REVIEW_RESPONSE,
    }
```

**Binding attachment pattern to preserve** (`src/agent/nodes/risk_gate.py` lines 824-892):

```python
risk_decision = _risk_decision(
    state=state,
    proposed_action=proposed_action,
    assessment=assessment,
    action_payload_hash=action_payload_hash,
)
risk_decision_ref = f"risk_decision:{str(state.get('current_run_id') or '')}:{action_payload_hash}"
approval_idempotency_key = _approval_idempotency_key(
    state=state,
    proposed_action=proposed_action,
    action_payload_hash=action_payload_hash,
    safety_snapshot_hash=safety_snapshot_hash,
    risk_decision_ref=risk_decision_ref,
)
```

```python
return {
    **result,
    "risk_assessment": assessment,
    "proposed_action": proposed_action,
    "action_payload_hash": action_payload_hash,
    "safety_snapshot_ref": safety_snapshot_ref,
    "safety_snapshot_hash": safety_snapshot_hash,
    "target_merchant_id": target_merchant_ref.target_merchant_id,
    "target_merchant_ref": target_merchant_ref.model_dump(mode="json"),
    "business_fact_refs": [ref.model_dump(mode="json") for ref in business_fact_refs],
    "verified_evidence_refs": [ref.model_dump(mode="json") for ref in evidence_refs],
    "claim_verification_ref": None,
    "claim_verification_summary": claim_summary,
    "risk_decision_ref": risk_decision_ref,
    "risk_decision": risk_decision.model_dump(mode="json"),
    "approval_idempotency_key": approval_idempotency_key,
    "approval_plan": approval_plan,
    "auto_allowed_binding": auto_allowed_binding,
}
```

**Migration instructions:**

- Replace local `FULL_REFUND_TERMS`, `ACTIONABLE_ACTIONS`, `_is_actionable_recommendation`, and `_canonical_action_type` with imports from `src.agent.safety.taxonomy`.
- In `_build_proposed_action`, only accept canonical executable actions. If taxonomy resolution yields `manual_review` / `blocked` disposition or no executable action, return fail-closed state before approval/snapshot binding.
- Add explicit `risk_severity` and `risk_disposition` to internal risk assessment dictionaries or normalize before every routing/action decision, while preserving legacy `risk_level` in `RiskDecisionV1`.
- Preserve `_phase34_fail_closed_result` behavior: clear proposed action, approval plan, risk decision, snapshot hashes, auto-allowed binding, and return `SAFE_MANUAL_REVIEW_RESPONSE`.
- Keep deterministic backend policy authoritative over LLM `RiskAssessment`.

**Pitfalls:**

- Current code writes `risk_level="manual_review"` in fail-closed paths. Phase 63 must not make `RiskAssessment.risk_level` accept dispositions; add separate semantics instead.
- Current reason-code construction includes `risk_level`; if legacy `risk_level` remains compatibility-only, include explicit severity/disposition reason codes deliberately.
- Snapshot/hash/binding construction must remain byte-for-byte stable enough for Phase 34 tests.

---

### `src/agent/nodes/action_draft.py` (LangGraph node / ToolPlatform boundary, event-driven + tool I/O)

**Analog:** existing `src/agent/nodes/action_draft.py`

**Current duplicate taxonomy to replace** (`src/agent/nodes/action_draft.py` lines 19-28):

```python
FULL_REFUND_TERMS = ("full_refund", "全额退款", "全额退", "整单退款")
ACTION_TOOL_NAME = "create_coupon_grant_draft"
ACTIONABLE_ACTIONS = {
    "issue_coupon",
    "approve_refund",
    "full_refund",
    "partial_refund",
    "compensation",
    "manual_review",
}
```

**Current canonicalizer to replace** (`src/agent/nodes/action_draft.py` lines 65-82):

```python
def _canonical_action_type(action: Any) -> str:
    action_text = str(action or "")
    lowered = action_text.lower()
    if lowered in ACTIONABLE_ACTIONS:
        return lowered
    if any(term in action_text for term in ("拒绝", "不建议", "无法支持")) or "reject" in lowered:
        return "manual_review"
    if any(term in lowered for term in ("coupon", "compensation", "compensate")) or any(
        term in action_text for term in ("补偿", "券", "赔付")
    ):
        return "issue_coupon"
    if any(term in action_text for term in FULL_REFUND_TERMS):
        return "full_refund"
    if "partial_refund" in lowered or "部分退款" in action_text:
        return "partial_refund"
    if "refund" in lowered or "退款" in action_text:
        return "approve_refund"
    return "manual_review"
```

**Verifier/claim fail-closed gate pattern** (`src/agent/nodes/action_draft.py` lines 104-159):

```python
def _verification_blocks_action(state: AgentState) -> bool:
    route = _verification_route(state)
    if route is not None and route != "allow":
        return True
    return _claim_bundle_blocks_action(state)
```

```python
def _claim_bundle_blocks_action(state: AgentState) -> bool:
    if not state.get("proposed_action"):
        return False
    bundle = _claim_verification_bundle(state)
    if bundle is None:
        return True
    if bundle.get("route") != "continue":
        return True
    if bundle.get("overall_status") not in {"verified", "not_required"}:
        return True
    if _non_empty_list(state.get("blocked_claims")) or _non_empty_list(bundle.get("blocked_claims")):
        return True
    return not _has_allowed_action_recommendation(bundle)
```

**Trusted approval binding pattern** (`src/agent/nodes/action_draft.py` lines 226-266):

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
if not _approval_phase34_binding_matches(state, trusted):
    return None
return trusted
```

**Auto-allowed binding pattern** (`src/agent/nodes/action_draft.py` lines 287-326):

```python
def _trusted_auto_allowed_binding(
    state: AgentState,
    trusted_context: TrustedContext | None,
) -> dict[str, Any] | None:
    raw_binding = state.get("auto_allowed_binding")
    if not isinstance(raw_binding, dict):
        return None
    try:
        trusted = AutoAllowedActionBindingV1.model_validate(raw_binding)
    except ValidationError:
        return None
    if not trusted.risk_decision_ref:
        return None
```

```python
if (
    trusted.action_payload_hash != state.get("action_payload_hash")
    or trusted.safety_snapshot_ref != state.get("safety_snapshot_ref")
    or trusted.safety_snapshot_hash != state.get("safety_snapshot_hash")
):
    return None
return _json_safe(raw_binding)
```

**Core ToolPlatform invocation pattern** (`src/agent/nodes/action_draft.py` lines 445-556):

```python
async def action_draft(state: AgentState, config: RunnableConfig) -> dict:
    """Create a durable demo action draft through the node-only tool boundary."""
    started_at = _now_iso()
    if _verification_blocks_action(state):
        return {
            "action_result": {
                "status": "error",
                "data": {},
                "error": {
                    "error_code": "VERIFIER_NOT_ALLOW",
                    "message": "Recommendation verification did not allow action draft creation",
                    "retryable": False,
                },
            },
            "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
        }
```

```python
action_type = _canonical_action_type(proposed.get("action_type"))
proposed = {**proposed, "action_type": action_type}
```

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

**Migration instructions:**

- Import `canonical_executable_action_type` / `resolve_action_text` / `is_executable_action_type` from `src.agent.safety.taxonomy`.
- Replace lines 512-513 with taxonomy resolution and an explicit error return when the resolution is a disposition or unknown value.
- Continue returning error-state dictionaries before `_invoke_action_tool`; do not throw for user/LLM taxonomy failures.
- Preserve approval and auto-allowed binding checks before tool invocation.
- Preserve `caller_node="action_draft"` and `ACTION_TOOL_NAME = "create_coupon_grant_draft"`.

**Pitfalls:**

- Existing `tests/test_execute_action.py` line 619 expects legacy freeform rejection text to canonicalize to `manual_review`; Phase 63 should update this expectation to "non-executable disposition is rejected before ToolPlatform" rather than pass `manual_review` to the tool.
- Do not use taxonomy migration to broaden from demo draft to real external execution.
- Do not bypass trusted context just because action type is canonical.

---

### `src/agent/intent_policy.py` (policy registry / classifier utility, transform)

**Analog:** existing `IntentPolicyRegistry`

**Definition metadata pattern** (`src/agent/intent_policy.py` lines 19-29):

```python
@dataclass(frozen=True)
class IntentDefinition:
    name: IntentLiteral
    required_slots: RequiredSlotExpression
    initial_route: IntentRouteLiteral
    precedence: int
    direct_response: bool = False
    evidence_required: bool = True
    high_risk: bool = False
    critical_route_class: bool = False
```

**Registry API pattern** (`src/agent/intent_policy.py` lines 293-354):

```python
class IntentPolicyRegistry:
    """Read-only view over current intent policy constants."""

    def definitions(self) -> Mapping[str, IntentDefinition]:
        return MappingProxyType(INTENT_DEFINITIONS)

    def get_definition(self, name: str) -> IntentDefinition | None:
        return INTENT_DEFINITIONS.get(name)
```

```python
    def requires_evidence(self, intent: str) -> bool:
        definition = self.get_definition(intent)
        if definition is None:
            return True
        return definition.evidence_required

    def is_high_risk_intent(self, intent: str) -> bool:
        return intent in HIGH_RISK_INTENTS

    def is_critical_route_intent(self, intent: str) -> bool:
        return intent in CRITICAL_ROUTE_CLASSES
```

**Risk-policy table pattern** (`src/agent/intent_policy.py` lines 539-620):

```python
RISK_POLICY_TABLE: Mapping[tuple[str, str, str], RiskDecision] = MappingProxyType(
    {
        ("approval_decision", "*", "*"): RiskDecision(
            tier="forbidden_in_chat",
            evidence_required=False,
            approval_required=False,
            reason_codes=("approval_chat_not_trusted",),
        ),
        ("read_status", "*", "*"): RiskDecision(
            tier="read_only",
            evidence_required=True,
            approval_required=False,
            reason_codes=("operation_read_status",),
        ),
```

**Pre-route action keyword block to migrate** (`src/agent/intent_policy.py` lines 678-743):

```python
def detect_pre_route(query: str) -> PreRouteDecision:
    text = query or ""
    lowered = text.lower()
    if is_short_approval_or_action_reply(text):
        return PreRouteDecision(
            disposition="approval_chat_not_trusted",
            requested_operation="advise",
            reason_codes=["approval_chat_not_trusted"],
            requires_clarification=True,
        )
```

```python
    english_action_terms = ("execute", "refund now", "override")
    chinese_action_terms = ("直接退款", "执行", "发券", "创建")
    if any(token in lowered for token in english_action_terms) or any(token in text for token in chinese_action_terms):
        return PreRouteDecision(
            disposition="safety_sensitive",
            requested_operation="execute_action",
            reason_codes=["critical_write"],
            requires_clarification=False,
        )
```

**Compensation cue block to migrate or source from taxonomy aliases** (`src/agent/intent_policy.py` lines 1197-1226):

```python
def _has_compensation_action_cue(text: str, lowered: str) -> bool:
    has_compensation_term = any(token in lowered for token in ("compensation", "coupon")) or any(
        token in text for token in ("补偿", "券", "赔付")
    )
    if not has_compensation_term:
        return False
```

```python
    return any(
        token in lowered
        for token in (
            "suggest",
            "proposal",
            "propose",
            "offer",
            "issue",
            "grant",
            "amount",
            "how much",
        )
    ) or any(token in text for token in ("建议", "方案", "给", "发券", "创建", "金额", "多少", "要补偿", "该给"))
```

**Migration instructions:**

- Keep `IntentDefinition` and `IntentPolicyRegistry` as the source for evidence/high-risk/critical-route policy.
- Move action keyword terms and action alias matching into `src.agent.safety.taxonomy`; `detect_pre_route` should call taxonomy helper and then map a result to `PreRouteDecision`.
- Keep approval-chat handling before action keyword handling, preserving ordinary chat approval decisions as untrusted.
- Keep `PreRouteDecision` disposition literals unchanged unless a plan deliberately widens schema and updates routing/tests.

**Pitfalls:**

- Do not leave `english_action_terms` / `chinese_action_terms` as another source of truth after migration.
- Do not let taxonomy action aliases override hard-negative policy-question cases such as compensation policy questions.
- Avoid changing risk tiers while migrating action keywords; that is separate from risk severity/disposition.

---

### `src/agent/routing.py` (router utility, event-driven decision)

**Analog:** existing registry-consuming routing pattern

**Imports and local drift point** (`src/agent/routing.py` lines 8-25):

```python
from src.agent.intent_policy import (
    INTENT_POLICY_REGISTRY,
    SLOT_POLICY_REGISTRY,
    PreRouteDecision,
    SlotInheritanceContext,
    confidence_requires_clarification,
)
```

```python
MIN_EVIDENCE_SCORE = 0.55
_FACT_ONLY_INTENTS = {"order_status_inquiry"}
_ACTION_BOUND_INTENTS = {"action_request", "compensation_suggestion", "complaint_escalation"}
```

**Registry-consuming route pattern** (`src/agent/routing.py` lines 433-464):

```python
def _route_after_contextual_intent(state: AgentState) -> str:
    intent = _intent(state)
    requested_operation = state.get("requested_operation") or "advise"
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    if requested_operation == "approval_decision":
        return "clarification_gate"
```

```python
    if confidence_requires_clarification(intent, requested_operation, state.get("intent_confidence"), pre_route):
        return "clarification_gate"
    if INTENT_POLICY_REGISTRY.is_direct_response_intent(intent):
        return "final_response"
    route = INTENT_POLICY_REGISTRY.route_for_intent(intent)
    if route is None:
        return "clarification_gate"
    policy = SLOT_POLICY_REGISTRY.required_slots_for(intent)
    if policy.all_of or policy.any_of:
        return "slot_resolution_gate"
    return route
```

**Policy evidence fallback to remove/derive** (`src/agent/routing.py` lines 1116-1135):

```python
def _policy_evidence_required(state: AgentState) -> bool:
    evidence_policy = state.get("evidence_policy")
    if isinstance(evidence_policy, dict) and isinstance(evidence_policy.get("evidence_required"), bool):
        return bool(evidence_policy["evidence_required"])
    routing_hints = state.get("routing_hints") if isinstance(state.get("routing_hints"), dict) else {}
    if isinstance(routing_hints.get("policy_evidence_required"), bool):
        return bool(routing_hints["policy_evidence_required"])
    requested_operation = state.get("requested_operation")
    if requested_operation in {"draft_action", "execute_action", "escalate"}:
        return True
    intent = _intent(state)
    return intent in {
        "policy_qa",
        "refund_troubleshooting",
        "compensation_suggestion",
        "ticket_reply_draft",
        "appeal_or_unban",
        "complaint_escalation",
        "action_request",
    }
```

**Action-bound/high-risk fallback to remove/derive** (`src/agent/routing.py` lines 1177-1198):

```python
def _action_bound_or_high_risk(state: AgentState) -> bool:
    requested_operation = state.get("requested_operation")
    if requested_operation in {"approval_decision", "draft_action", "execute_action", "escalate"}:
        return True
    if _intent(state) in _ACTION_BOUND_INTENTS:
        return True
    if _non_empty_sequence(state.get("risk_signals")):
        return True
```

**Migration instructions:**

- Replace `_ACTION_BOUND_INTENTS` with registry-derived checks (`INTENT_POLICY_REGISTRY.is_high_risk_intent`, `requires_evidence`, and/or a new explicit API on the registry).
- Replace the final hardcoded intent set in `_policy_evidence_required` with `INTENT_POLICY_REGISTRY.requires_evidence(_intent(state))`, while preserving override precedence for `state["evidence_policy"]`, `routing_hints`, and action-like operations.
- Preserve fail-closed wrappers: public route functions catch exceptions and return safe fallback routes.

**Pitfalls:**

- Do not make routing import concrete node modules or taxonomy descriptors that create circular imports.
- Do not remove operation-based fail-closed checks for `draft_action`, `execute_action`, `escalate`.
- Add parity tests before removing local sets so business metric and direct response intents keep current behavior.

---

### `src/agent/schemas.py`, `src/approvals/schemas.py`, `src/actions/schemas.py` (schema models, validation / compatibility)

**Agent risk schema analog** (`src/agent/schemas.py` lines 151-155):

```python
class RiskAssessment(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    risk_reason: str
    approval_required: bool
    rule_ref: str | None = None
```

**Approval compatibility analog** (`src/approvals/schemas.py` lines 32-50):

```python
class RiskDecisionV1(BaseModel):
    """Risk-gate decision bound to an exact proposed action payload hash."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["risk_decision.v1"] = RISK_DECISION_SCHEMA_VERSION
    tenant_id: str
    run_id: str
    action_id: str
    action_payload_hash: str
    risk_level: str
    reason_codes: list[str]
    policy_config_version: str
    risk_config_version: str
    approval_required: bool
    evaluated_at: str
    risk_rule_ref: str | None = None
    risk_reason: str | None = None
```

**Action draft compatibility analog** (`src/actions/schemas.py` lines 25-54):

```python
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
```

**Pattern to copy for Phase 63:**

- Keep Pydantic boundary models strict (`ConfigDict(extra="forbid")`) where already strict.
- Treat `RiskAssessment.risk_level` as severity only.
- Treat `RiskDecisionV1.risk_level` as compatibility string during migration; add explicit optional fields only if the plan chooses additive schema expansion with tests.
- Do not tighten `RiskDecisionV1.risk_level` to a literal enum without persisted/API compatibility tests.
- Do not make `ActionDraftV2Data.action_type` a public enum in this phase unless service/store compatibility tests prove it safe; caller-side executable guard is the minimum Phase 63 safety requirement.

---

### `tests/agent/test_safety_taxonomy.py` (unit / parity, transform verification)

**Analogs:** `tests/agent/test_intent_policy_registry.py`, `tests/agent/test_intent_routing.py`

**Registry parity pattern** (`tests/agent/test_intent_policy_registry.py` lines 34-47):

```python
def test_intent_policy_registry_mirrors_existing_constants() -> None:
    registry = IntentPolicyRegistry()

    assert registry.definitions() == INTENT_DEFINITIONS
    assert registry.intent_names() == tuple(INTENT_DEFINITIONS)
    assert registry.precedence_order() == PRECEDENCE_INTENTS
    assert registry.route_policy() == INTENT_ROUTE_POLICY
    assert registry.direct_response_intents() == frozenset(DIRECT_RESPONSE_INTENTS)
    assert registry.evidence_required_intents() == frozenset(EVIDENCE_REQUIRED_INTENTS)
    assert registry.high_risk_intents() == frozenset(HIGH_RISK_INTENTS)
```

**Read-only registry test pattern** (`tests/agent/test_intent_policy_registry.py` lines 127-139):

```python
def test_registries_are_read_only() -> None:
    intent_registry = IntentPolicyRegistry()
    slot_registry = SlotPolicyRegistry()

    with pytest.raises(TypeError):
        intent_registry.definitions()["policy_qa"] = INTENT_DEFINITIONS["unsupported"]
    with pytest.raises(TypeError):
        intent_registry.route_policy()["policy_qa"] = "final_response"
    with pytest.raises(TypeError):
        slot_registry.required_slot_policy()["policy_qa"] = RequiredSlotExpression(all_of=["merchant_id"])
```

**Pre-route current behavior pattern** (`tests/agent/test_intent_routing.py` lines 71-80):

```python
def test_detect_pre_route_approval_chat_and_hard_negatives():
    decision = detect_pre_route("approve APR-1")
    assert decision.disposition == "approval_chat_not_trusted"
    assert decision.requested_operation == "advise"
    assert "approval_chat_not_trusted" in decision.reason_codes

    assert detect_pre_route("通过订单号 ORD-1 查询退款状态").disposition == "none"
    assert detect_pre_route("通过规则判断是否要补偿").disposition == "none"
    assert detect_pre_route("accept language preference").disposition == "none"
```

**Test cases to add:**

- Canonical action matrix: `issue_coupon`, `compensation`/coupon aliases, `approve_refund`, `full_refund`, `partial_refund`.
- Disposition matrix: reject/no-support/default -> `manual_review` disposition, not executable action.
- `blocked` and `manual_review` are non-executable.
- `is_actionable_recommendation` uses aliases but excludes dispositions.
- `action_pre_route_match` covers current `execute`, `refund now`, `override`, `直接退款`, `执行`, `发券`, `创建` behavior.
- `normalize_risk_vocabulary` separates severity `low|medium|high` from disposition `allow|approval_required|manual_review|blocked`.

---

### `tests/agent/test_nodes/test_risk_gate.py` and `tests/agent/test_phase22_action_boundary.py` (async node tests, fail-closed verification)

**Analog:** existing risk-gate tests

**No-action and actionable parity pattern** (`tests/agent/test_nodes/test_risk_gate.py` lines 200-253):

```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "recommended_action",
    ["insufficient_evidence", "citation_invalid", "retrieval_error"],
)
async def test_no_action_recommendations_never_propose_action(monkeypatch, base_state, recommended_action):
    class ExplodingLLM:
        def with_structured_output(self, schema):
            raise AssertionError("no-action recommendation should not call the LLM")
```

```python
async def test_actionable_recommendation_still_proposes_action(monkeypatch, base_state):
    monkeypatch.setattr(
        risk_gate_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "risk_level": "low",
                "risk_reason": "standard compensation",
                "approval_required": False,
                "rule_ref": "LR-01",
            }
        ),
    )
```

**Fail-closed missing target pattern** (`tests/agent/test_nodes/test_risk_gate.py` lines 476-510):

```python
@pytest.mark.asyncio
async def test_phase34_missing_target_merchant_fails_closed_without_approval_plan(monkeypatch, base_state):
    tenant_id = base_state["tenant_id"]
    monkeypatch.setattr(
        risk_gate_module,
        "_get_llm",
        lambda: FakeLLM(
            {
                "risk_level": "high",
                "risk_reason": "Coupon amount requires manager approval.",
                "approval_required": True,
                "rule_ref": "HR-COUPON",
            }
        ),
    )
```

```python
    assert result["proposed_action"] is None
    assert result["approval_plan"] is None
    assert result["auto_allowed_binding"] is None
    assert result["final_response"] == "操作需要人工复核，当前未创建可执行审批或动作草稿。"
    assert result["risk_assessment"]["risk_level"] == "manual_review"
```

**Non-allow verifier pattern to migrate to disposition assertions** (`tests/agent/test_phase22_action_boundary.py` lines 200-237):

```python
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "route"),
    [
        ("unsupported", "insufficient_evidence"),
        ("conflicting", "manual_review"),
        ("stale", "manual_review"),
        ("unauthorized", "refuse"),
        ("hash_mismatch", "refuse"),
        ("latest_version_invalid", "refuse"),
        ("business_fact_missing", "insufficient_evidence"),
        ("semantic_ambiguous", "manual_review"),
    ],
)
async def test_non_allow_verifier_outcomes_block_proposed_actions_and_snapshot_evidence(
    monkeypatch: pytest.MonkeyPatch,
    base_state: dict[str, Any],
    outcome: str,
    route: str,
) -> None:
```

```python
    assert result["proposed_action"] is None
    assert result.get("action_payload_hash") is None
    assert result.get("safety_snapshot_ref") is None
    assert result.get("safety_snapshot_hash") is None
    assert result.get("safety_snapshot_verified") is not True
    assert result["risk_assessment"]["approval_required"] is False
    assert result["risk_assessment"]["risk_level"] in {"manual_review", "blocked", "low"}
```

**Action draft non-allow pattern** (`tests/agent/test_phase22_action_boundary.py` lines 448-539):

```python
result = await action_draft(
    state,
    {"configurable": {"session": object(), "action_tool_platform": ExplodingActionToolPlatform()}},
)

assert result.get("action_draft") is None
assert result.get("draft_outcome") is None
assert result["action_result"]["status"] == "error"
assert result["action_result"]["error"]["error_code"] == "VERIFIER_NOT_ALLOW"
```

**Test migration instructions:**

- Change assertions that allow `risk_level in {"manual_review", "blocked", "low"}` to explicit severity/disposition assertions.
- Add cases proving non-allow routes set `risk_disposition` to `manual_review` or `blocked` while keeping `risk_severity` valid.
- Keep `ExplodingLLM` and `ExplodingActionToolPlatform` patterns to prove backend gates run before LLM/tool side effects.

---

### `tests/actions/test_action_draft_v2.py`, `tests/actions/test_phase34_action_draft_bindings.py`, `tests/test_execute_action.py` (action draft and binding tests)

**ActionDraft schema/store analog** (`tests/actions/test_action_draft_v2.py` lines 231-274):

```python
def test_draft_outcome_v1_defaults_to_not_executed_demo():
    outcome = DraftOutcomeV1()

    assert outcome.schema_version == "draft_outcome.v1"
    assert outcome.status == "not_executed_demo"
    assert outcome.external_side_effect is False
```

```python
def test_action_draft_v2_data_exposes_demo_contract_literals():
    draft = ActionDraftV2Data.model_validate(_draft_payload())

    assert draft.schema_version == "action_draft.v2"
    assert draft.execution_mode == "demo"
    assert draft.draft_outcome.schema_version == "draft_outcome.v1"
    assert draft.draft_outcome.status == "not_executed_demo"
    assert draft.draft_outcome.external_side_effect is False
```

**Approval binding mismatch pattern** (`tests/actions/test_phase34_action_draft_bindings.py` lines 224-245):

```python
@pytest.mark.asyncio
async def test_create_coupon_grant_draft_rejects_phase34_approval_binding_mismatch(
    session: AsyncSession,
    seeded_session,
):
    request = await _approved_phase34_request(session, seeded_session)
    user_id = seeded_session["users"]["cs_zhang"].id
```

```python
    assert result["status"] == "error"
    assert result["error"]["error_code"] == "APPROVAL_BINDING_MISMATCH"
    await _assert_no_drafts(session, request.run_id)
```

**Auto-allowed binding patterns** (`tests/actions/test_phase34_action_draft_bindings.py` lines 286-449, 452-531):

```python
@pytest.mark.asyncio
async def test_create_coupon_grant_draft_accepts_exact_auto_allowed_binding(
    session: AsyncSession,
    seeded_session,
):
```

```python
assert draft.approval_request_id is None
assert draft.approval_revision_ref == f"auto_allowed:{binding['risk_decision_ref']}"
assert draft.auto_allowed_binding_ref == f"auto_allowed:{binding['risk_decision_ref']}"
assert len(draft.idempotency_key) <= 256
assert draft.idempotency_key.startswith(f"{tenant_id}:{run_id}:auto_allowed_sha256:")
```

```python
assert result["status"] == "error"
assert result["error"]["error_code"] == "AUTO_ALLOWED_BINDING_MISMATCH"
await _assert_no_drafts(session, run_id)
```

**Tool invocation success/fail-closed pattern** (`tests/test_execute_action.py` lines 295-311, 643-656):

```python
@pytest.mark.asyncio
async def test_action_draft_with_service_approval_result_creates_draft(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()

    result = await action_draft_module.action_draft(state, _trusted_config(state))

    assert result["action_draft"]["schema_version"] == "action_draft.v2"
    assert result["draft_outcome"]["status"] == "not_executed_demo"
    assert result["draft_outcome"]["external_side_effect"] is False
    assert result["execution_mode"] == "demo"
    assert result["action_result"]["status"] != "success"
    assert result["trace_steps"][-1]["tool_name"] == "create_coupon_grant_draft"
    assert result["trace_steps"][-1]["node"] == "action_draft"
    assert result["trace_steps"][-1]["status"] == "completed"
    create_draft.assert_awaited_once()
```

```python
@pytest.mark.asyncio
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

**Legacy canonicalization test to rewrite** (`tests/test_execute_action.py` lines 607-621):

```python
@pytest.mark.asyncio
async def test_execute_action_canonicalizes_legacy_freeform_action_type(monkeypatch):
    create_draft = AsyncMock(return_value=_success_result())
    monkeypatch.setattr("src.tools.executors.action.ActionService.create_coupon_grant_draft", create_draft)
    state = _approved_state()
    state["proposed_action"]["action_type"] = (
        "拒绝600元补偿请求。根据补偿规则，订单实付金额599元对应的最高体验补偿标准为50元。"
    )

    await action_draft_module.action_draft(state, _trusted_config(state))

    _, kwargs = create_draft.await_args
    assert kwargs["action_type"] == "manual_review"
    assert "manual_review" not in kwargs["idempotency_key"]
    assert len(kwargs["action_type"]) <= 64
```

**Test migration instructions:**

- Keep binding mismatch and no-draft assertions unchanged.
- Rewrite the legacy freeform canonicalization case so `manual_review` is rejected before `create_coupon_grant_draft` is awaited.
- Add an explicit `blocked`/`manual_review` disposition test for action draft.
- Preserve demo-only assertions: `not_executed_demo`, `external_side_effect is False`, and no `action_result.status == "success"` sentinel.

---

### `tests/agent/test_intent_policy_registry.py` and `tests/agent/test_intent_routing.py` (registry parity and routing tests)

**Intent-derived view pattern** (`tests/agent/test_intent_routing.py` lines 49-68):

```python
def test_intent_policy_views_are_derived_from_definitions():
    assert all(name == definition.name for name, definition in INTENT_DEFINITIONS.items())
    assert len({definition.precedence for definition in INTENT_DEFINITIONS.values()}) == len(INTENT_DEFINITIONS)
    assert all(
        not definition.direct_response or definition.initial_route == "final_response"
        for definition in INTENT_DEFINITIONS.values()
    )
    assert ORDINARY_INTENTS == tuple(INTENT_DEFINITIONS)
    assert REQUIRED_SLOT_POLICY == {name: definition.required_slots for name, definition in INTENT_DEFINITIONS.items()}
    assert INTENT_ROUTE_POLICY == {name: definition.initial_route for name, definition in INTENT_DEFINITIONS.items()}
    assert PRECEDENCE_INTENTS == tuple(
        name for name, _definition in sorted(INTENT_DEFINITIONS.items(), key=lambda item: item[1].precedence)
    )
    assert DIRECT_RESPONSE_INTENTS == {
        name for name, definition in INTENT_DEFINITIONS.items() if definition.direct_response
    }
    assert EVIDENCE_REQUIRED_INTENTS == {
        name for name, definition in INTENT_DEFINITIONS.items() if definition.evidence_required
    }
    assert HIGH_RISK_INTENTS == {name for name, definition in INTENT_DEFINITIONS.items() if definition.high_risk}
```

**Safety-sensitive pre-route pattern** (`tests/agent/test_intent_routing.py` lines 410-437):

```python
@pytest.mark.parametrize("llm_intent", ["policy_qa", "refund_troubleshooting"])
def test_safety_sensitive_pre_route_forces_action_request_policy(llm_intent):
    result = IntentResultV3.model_validate(
        {
            "schema_version": "intent_result.v3",
            "primary_intent": llm_intent,
            "requested_operation": "advise",
            "confidence": 0.97,
            "calibrated_confidence": 0.94,
            "secondary_intents": [],
            "required_slots": {"all_of": [], "any_of": [], "optional": []},
            "candidate_slots": {"order_id": "ORD-7001"},
            "routing_hints": {},
            "classifier_version": "intent_classifier.v2",
            "calibration_version": "calibration.unverified",
            "reason_codes": ["llm_misclassified_write"],
        }
    )
    pre_route = detect_pre_route("请对ORD-7001直接退款")
```

```python
    assert update["primary_intent"] == "action_request"
    assert update["requested_operation"] == "execute_action"
    assert update["risk_tier"] == "approval_required"
    assert update["classification_trace"]["effective_classification"]["primary_intent"] == "action_request"
    assert update["required_slots"]["all_of"] == ["action_type"]
```

**Routing registry consumer static pattern** (`tests/agent/test_intent_routing.py` lines 484-553):

```python
def test_route_after_contextual_intent_consumes_registry_route_policy(monkeypatch):
    class FakeIntentRegistry:
        def is_direct_response_intent(self, intent: str) -> bool:
            return False

        def route_for_intent(self, intent: str) -> str | None:
            return "investigate"
```

```python
def test_intent_consumers_do_not_read_policy_constants_directly():
    routing_source = inspect.getsource(routing_module)
    contextual_intent_source = inspect.getsource(contextual_intent_module)

    forbidden = ("DIRECT_RESPONSE_INTENTS", "INTENT_ROUTE_POLICY", "REQUIRED_SLOT_POLICY")
    for token in forbidden:
        assert token not in routing_source
        assert token not in contextual_intent_source
```

**Migration instructions:**

- Add parity checks that evidence-required/action-bound routing is derived from `INTENT_DEFINITIONS` / `IntentPolicyRegistry`.
- Add tests that `detect_pre_route` consumes taxonomy action aliases, not private tuples.
- Keep existing approval-chat and hard-negative tests.

---

### `tests/architecture/test_safety_taxonomy_boundaries.py` (architecture/static drift guard, static file scan)

**Analog:** `tests/architecture/test_action_draft_boundaries.py`

**Static source helper pattern** (`tests/architecture/test_action_draft_boundaries.py` lines 1-18, 36-55):

```python
from __future__ import annotations

import ast
import re
from pathlib import Path
```

```python
ROOT = Path(__file__).resolve().parents[2]
NODE_PATH = ROOT / "src" / "agent" / "nodes" / "action_draft.py"
SHIM_PATH = ROOT / "src" / "agent" / "nodes" / "execute_action.py"
CATALOG_PATH = ROOT / "src" / "tools" / "catalog.py"
GRAPH_PATH = ROOT / "src" / "agent" / "graph.py"
POLICY_PATH = ROOT / "src" / "tools" / "policy.py"
SOURCE_ROOTS = (
    ROOT / "src" / "actions",
    ROOT / "src" / "agent",
    ROOT / "src" / "api",
    ROOT / "src" / "repositories",
    ROOT / "src" / "tools",
)
```

```python
def _source(path: Path) -> str:
    return path.read_text()


def _function_names(path: Path) -> set[str]:
    tree = ast.parse(_source(path))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)}


def _import_targets(path: Path) -> list[str]:
    tree = ast.parse(_source(path))
    imports: list[str] = []
```

**Forbidden token scan pattern** (`tests/architecture/test_action_draft_boundaries.py` lines 142-168):

```python
def test_demo_action_sources_do_not_import_external_execution_paths() -> None:
    violations: list[tuple[str, str]] = []
    for root in SOURCE_ROOTS:
        for path in sorted(root.glob("**/*.py")):
            for module in _import_targets(path):
                normalized = module.lower()
                if any(part in normalized for part in FORBIDDEN_EXTERNAL_IMPORT_PARTS):
                    violations.append((str(path.relative_to(ROOT)), module))

    assert violations == []
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

**Tool boundary static pattern** (`tests/architecture/test_action_draft_boundaries.py` lines 98-109):

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

**Static guard instructions:**

- Add `CANONICAL_TAXONOMY_PATH = ROOT / "src" / "agent" / "safety" / "taxonomy.py"`.
- Scan `src/agent/nodes/risk_gate.py`, `src/agent/nodes/action_draft.py`, `src/agent/intent_policy.py`, and `src/agent/routing.py`.
- Forbid duplicate `FULL_REFUND_TERMS`, `ACTIONABLE_ACTIONS`, local `_canonical_action_type`, and private pre-route action keyword tuples outside the taxonomy owner.
- Prefer AST checks for function definitions/imports and line scans for exact constants/regex snippets.
- Allow the taxonomy owner to contain the canonical definitions.

**Pitfalls:**

- Do not make the guard too broad by banning words like `manual_review` everywhere; that value must still appear in tests, schemas, and compatibility payloads.
- Report violations as `(relative_path, line_no, token)` so future failures are actionable.
- Do not scan generated caches or `.planning/` artifacts.

## Shared Patterns

### Immutable Registry Ownership

**Sources:** `src/business/query/registry.py`, `src/agent/intent_policy.py`, `src/agent/graph_vocabulary.py`

**Apply to:** `src/agent/safety/taxonomy.py`, `src/agent/intent_policy.py`, `src/agent/routing.py`

Use frozen descriptors, `MappingProxyType`, `frozenset`, explicit registry methods, and module-level singleton registries. Avoid returning mutable structures.

### Backend-Owned Safety Decisions

**Sources:** `src/agent/nodes/risk_gate.py`, `src/agent/nodes/action_draft.py`, `tests/agent/test_phase22_action_boundary.py`

**Apply to:** risk gate, action draft, intent pre-route, routing.

LLM output can suggest severity/action text, but backend deterministic code owns canonical action resolution, approval requirement, blocking, snapshot/hash binding, and draft gating.

### Compatibility Fields

**Sources:** `src/approvals/schemas.py`, `src/actions/schemas.py`

**Apply to:** approval/action schemas and risk/action node outputs.

Keep legacy `risk_level`, `risk_decision`, and `action_type` payloads readable. Add semantic helpers or additive fields before tightening enums or persisted constraints.

### Fail-Closed Error Shape

**Sources:** `src/agent/nodes/risk_gate.py` lines 762-796, `src/agent/nodes/action_draft.py` lines 445-481.

**Apply to:** disposition-only action resolution, non-allow verifier routes, missing bindings, missing trusted context.

Return structured error/final-response updates and clear action-capable state before ToolPlatform or approval creation.

### ToolPlatform Boundary

**Sources:** `src/agent/nodes/action_draft.py`, `tests/architecture/test_action_draft_boundaries.py`

**Apply to:** action draft migration and tests.

Preserve `caller_node="action_draft"`, `create_coupon_grant_draft`, node-only allowlist, trusted context, and demo-only draft outcomes.

## Pitfalls And Guardrails

| Pitfall | Evidence | Guardrail |
|---------|----------|-----------|
| Treating `manual_review` as executable | `ACTIONABLE_ACTIONS` currently includes it in both risk and draft nodes. | Taxonomy must classify it as disposition-only; action draft rejects before ToolPlatform. |
| Expanding `RiskAssessment.risk_level` to routing outcomes | `RiskAssessment` allows only `low|medium|high`; runtime currently writes `manual_review` in fail-closed paths. | Add explicit severity/disposition normalization and update tests. |
| Breaking approval/hash binding | Risk gate builds `RiskDecisionV1`, approval plan, snapshot hashes, and auto-allowed binding together. | Keep Phase 34 binding tests green. |
| Leaving pre-route keyword drift | `intent_policy.detect_pre_route` has private action keyword tuples. | Move action keyword classification to taxonomy helper and add static drift guard. |
| Keeping routing fallback sets | `routing._ACTION_BOUND_INTENTS` and `_policy_evidence_required` duplicate policy. | Derive from `INTENT_POLICY_REGISTRY` / definitions, with parity tests. |
| Broadening into state-machine/DB CHECK hardening | Phase context defers broader status constraints. | Record debt for suggested Phase 67 unless required for Phase 63 safety. |
| Invalid validation command | Project forbids bare `pytest` and bare `python -m pytest`. | Use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` and `UV_CACHE_DIR=/tmp/uv-cache uv run ruff ...`. |

## Validation Command Patterns

**Source:** `.planning/phases/63-safety-taxonomy-and-risk-vocabulary/63-VALIDATION.md` lines 22-25.

Quick taxonomy:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py -q --tb=short
```

Static drift guard:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_safety_taxonomy_boundaries.py -q --tb=short
```

Full focused phase command:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/approvals/test_hash_binding.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_safety_taxonomy_boundaries.py -q --tb=short
```

Lint changed files:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check <changed files>
```

## No Analog Found

None. Every planned new/modified file has a close role/data-flow analog in the current codebase.

## Metadata

**Analog search scope:** `src/agent`, `src/actions`, `src/approvals`, `src/business/query`, `tests/agent`, `tests/actions`, `tests/architecture`, `tests/test_execute_action.py`

**Primary files read:** phase context/research/validation; `risk_gate.py`; `action_draft.py`; `intent_policy.py`; `routing.py`; agent/approval/action schemas; required action/intent tests; risk-gate/action-boundary/execute-action tests; registry and architecture-test analogs.

**Files scanned with `rg`:** source/test Python files under `src` and `tests`, plus the Phase 63 planning directory.

**Pattern extraction date:** 2026-07-10
