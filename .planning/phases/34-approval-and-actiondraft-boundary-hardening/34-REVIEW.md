---
phase: 34-approval-and-actiondraft-boundary-hardening
reviewed: 2026-06-29T07:25:33Z
depth: deep
files_reviewed: 39
files_reviewed_list:
  - src/actions/drafts.py
  - src/actions/schemas.py
  - src/actions/service.py
  - src/agent/graph.py
  - src/agent/graph_vocabulary.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/approval_gate.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/state.py
  - src/agent/working_state.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - src/api/schemas/agent_runs.py
  - src/api/schemas/approvals.py
  - src/approvals/policy.py
  - src/approvals/repository.py
  - src/approvals/schemas.py
  - src/approvals/service.py
  - src/db/migrations/versions/018_phase34_approval_action_bindings.py
  - src/db/models.py
  - src/repositories/action_draft_repo.py
  - src/tools/catalog.py
  - src/tools/executors/action.py
  - tests/actions/test_action_draft_v2.py
  - tests/actions/test_phase34_action_draft_bindings.py
  - tests/agent/test_nodes/test_assess_risk_and_approval.py
  - tests/agent/test_nodes/test_final_response.py
  - tests/agent/test_working_state.py
  - tests/approvals/test_migration_contract.py
  - tests/approvals/test_phase34_boundary_bindings.py
  - tests/approvals/test_service_transitions.py
  - tests/architecture/test_action_draft_boundaries.py
  - tests/architecture/test_phase34_approval_action_boundaries.py
  - tests/test_agent_runs_api.py
  - tests/test_approval_api.py
  - tests/test_approval_gate.py
  - tests/test_approval_models.py
  - tests/test_execute_action.py
  - tests/test_graph_routing.py
findings:
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 34: Code Review Report

**Reviewed:** 2026-06-29T07:25:33Z
**Depth:** deep
**Files Reviewed:** 39
**Status:** issues_found

## Warnings

### WR-01: Live approval interrupts reject the risk gate's claim-verification output

**File:** `src/api/routers/agent_runs.py:848`

**Issue:** `_approval_create_command_from_interrupt` requires both `claim_verification_ref` and `claim_verification_summary`, and rejects the interrupt when any required field is falsy. The actual risk gate writes `claim_verification_ref: None` into the approval plan and state (`src/agent/nodes/assess_risk_and_approval.py:654`, `src/agent/nodes/assess_risk_and_approval.py:815`), and `approval_gate` forwards that value unchanged (`src/agent/nodes/approval_gate.py:65`). A real approval-required run can therefore fail with `ApprovalInterruptValidationError(["claim_verification_ref"])` before an `ApprovalRequest` is created.

**Impact:** The Phase 34 approval-required path can dead-end at runtime even though the risk gate produced a verified claim summary and durable risk/snapshot bindings. The current API tests miss this because their fake interrupt helper injects a synthetic `claim_verification_ref` (`tests/test_agent_runs_api.py:678`) instead of using the real risk-gate payload shape.

**Fix:** Make the producer and consumer agree on the contract. Either have `assess_risk_and_approval` persist a stable `claim_verification_ref`, or change the interrupt validator to require `claim_verification_ref` OR `claim_verification_summary` and pass a nullable ref into `ApprovalRequestCreateCommand`.

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
    "target_merchant_id",
    "target_merchant_ref",
    "business_fact_refs",
    "verified_evidence_refs",
    "risk_decision_ref",
    "risk_decision",
]
missing = [field for field in required_fields if not interrupt_data.get(field)]
if not (interrupt_data.get("claim_verification_ref") or interrupt_data.get("claim_verification_summary")):
    missing.append("claim_verification")
```

Add an integration test that feeds actual `assess_risk_and_approval -> approval_gate -> _approval_create_command_from_interrupt` output, including the current summary-only claim binding.

### WR-02: Edit decisions emit a risk reroute payload, but the API never resumes the graph

**File:** `src/api/routers/approvals.py:650`

**Issue:** `ApprovalService._edit` returns a resume payload with `decision_type="edit"` and `resume_route="assess_risk_and_approval"` (`src/approvals/service.py:558`, `src/approvals/service.py:570`), and `route_after_approval` explicitly routes that trusted payload back to the risk gate (`src/agent/graph.py:149`). The API gate excludes edits from `_should_resume_graph`, so `decide_approval` commits the supersede result without invoking `_run_resume_lifecycle` (`src/api/routers/approvals.py:132`). The API test currently asserts this no-resume behavior (`tests/test_approval_api.py:733`), which contradicts the service and graph contract.

**Impact:** Reviewer edits dead-end instead of being re-risked and rebound. The user sees a superseded approval response, but the agent run is not resumed to `assess_risk_and_approval`, so no fresh claim/risk/snapshot/merchant binding is produced for the edited action.

**Fix:** Resume only trusted edit results that explicitly request the risk route, and update the API test to assert a risk resume rather than zero graph calls.

```python
def _should_resume_graph(result) -> bool:
    if not result.resume_payload:
        return False
    if result.decision_type == "edit":
        return result.resume_payload.get("resume_route") == "assess_risk_and_approval"
    return result.decision_type in {"accept", "approve", "reject", "ignore"}
```

The resume path also needs to feed the edited action into the state that risk gate consumes, so the new hash is revalidated rather than treated as approval authority.

### WR-03: Superseding edit/info approvals are persisted without Phase 34 binding fields

**File:** `src/approvals/service.py:504`

**Issue:** `_edit` creates the superseding pending `ApprovalRequest` without passing `target_merchant_id`, `target_merchant_ref`, `business_fact_refs`, `verified_evidence_refs`, claim verification fields, risk decision fields, or `approval_idempotency_key` into `create_request_with_single_level` (`src/approvals/service.py:504`). `_supersede_from_info` has the same omission (`src/approvals/service.py:689`). The normal create path does pass these bindings (`src/approvals/service.py:106`), and the repository supports them.

**Impact:** The new pending approval row can be missing the exact merchant/evidence/claim/risk bindings Phase 34 relies on. Managers cannot see or decide missing-target approvals because `_approval_scope_allowed` requires `approval.target_merchant_id` (`src/api/routers/approvals.py:666`), and any later action draft would fail binding validation. Combined with WR-02, an edit can leave behind a pending approval that is neither properly scoped nor executable.

**Fix:** Do not create a new pending approval row until the edit has been rerun through risk gate and rebuilt with fresh Phase 34 bindings. If the placeholder row must exist, mark it non-executable/non-reviewable until rebound, or pass only verified binding fields that are still exact for the edited action.

```python
new_request, _new_level, _new_assignment, _event = await self.repository.create_request_with_single_level(
    ...,
    target_merchant_id=rebuilt.target_merchant_id,
    target_merchant_ref=rebuilt.target_merchant_ref,
    business_fact_refs=rebuilt.business_fact_refs,
    verified_evidence_refs=rebuilt.verified_evidence_refs,
    claim_verification_ref=rebuilt.claim_verification_ref,
    claim_verification_summary=rebuilt.claim_verification_summary,
    risk_decision_ref=rebuilt.risk_decision_ref,
    risk_decision=rebuilt.risk_decision,
    approval_idempotency_key=rebuilt.approval_idempotency_key,
)
```

## Summary

Deep review traced the Phase 34 call chain from `risk_gate` through `approval_gate`, the agent-run interrupt bridge, `ApprovalService`, approval API resume handling, and `action_draft` binding validation. No critical issues were found. The three warnings are behavioral boundary regressions around approval-required creation and edit/supersede rebinding.

No tests were run during this review; findings are based on source and test trace analysis.

---

_Reviewed: 2026-06-29T07:25:33Z_
_Reviewer: Codex (gsd-code-reviewer)_
_Depth: deep_
