---
phase: 04-approval-workflow-audit
reviewed: 2026-05-16T12:47:27Z
depth: deep
files_reviewed: 37
files_reviewed_list:
  - src/db/models.py
  - src/db/migrations/versions/004_latency_metrics.py
  - src/db/migrations/versions/005_approval_tables.py
  - src/agent/state.py
  - src/agent/trace.py
  - src/agent/graph.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/approval_gate.py
  - src/agent/nodes/execute_action.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/classify_intent.py
  - src/agent/nodes/extract_slots.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/load_business_context.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/retrieve_policy_evidence.py
  - src/agent/tools/create_coupon_grant_draft.py
  - src/repositories/approval_repo.py
  - src/repositories/action_draft_repo.py
  - src/repositories/trace_repo.py
  - src/api/routers/agent.py
  - src/api/routers/approvals.py
  - src/api/routers/traces.py
  - src/api/main.py
  - src/api/schemas/approvals.py
  - scripts/diagnose_latency.py
  - tests/test_latency_instrumentation.py
  - tests/test_approval_models.py
  - tests/test_approval_gate.py
  - tests/test_execute_action.py
  - tests/test_graph_routing.py
  - tests/test_approval_api.py
  - tests/test_trace_api.py
  - tests/test_interrupt_contract_spike.py
  - tests/test_approval_integration.py
  - tests/test_interception_rate.py
  - tests/conftest.py
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-05-16T12:47:27Z
**Depth:** deep
**Files Reviewed:** 37
**Status:** issues_found

## Summary

Reviewed the Phase 04 approval workflow, graph interrupt/resume path, repositories, trace API, migrations, diagnostic script, and related tests. The main approval bypass controls are present, but the decision endpoint still has a concurrency/idempotency flaw that can resume the graph more than once for the same approval. Trace replay also misses the approval gate in the real LangGraph interrupt shape and exposes more proposed-action detail than the trace sanitization contract says it should.

## Critical Issues

### CR-01: Concurrent Idempotent Decisions Can Resume The Graph Twice

**File:** `src/api/routers/approvals.py:54`

**Issue:** `was_pending` is computed from an unlocked read before `ApprovalRepository.decide()` takes the row lock. Two concurrent `approve` requests can both read `pending`; the first one transitions and resumes, while the second blocks on `with_for_update()`, returns the already-approved row idempotently, and still resumes because its stale `was_pending` flag is `True`. This violates the single-resume/idempotency contract and can duplicate approval steps, post-resume trace rows, and any future non-draft side effects behind `execute_action`.

**Fix:**
Move the transition decision inside the locked repository operation and return whether this call actually changed the state. Only add decision/resume events when `transitioned` is true.

```python
# repository
async def decide(...) -> tuple[ApprovalRequest, bool]:
    approval = await self.get_by_id_for_update(approval_id, tenant_id)
    if approval.status == "approved" and decision == "approve":
        return approval, False
    if approval.status == "rejected" and decision == "reject":
        return approval, False
    # pending path
    approval.status = "approved" if decision == "approve" else "rejected"
    ...
    return approval, True

# router
updated, transitioned = await repo.decide(...)
if transitioned:
    await repo.add_step(...)
    await graph.ainvoke(Command(resume=resume_payload), config)
```

Add a concurrency test with two independent sessions racing the same pending approval and assert exactly one graph resume and one action draft.

## Warnings

### WR-01: Persisted Trace Skips The Approval Gate After Real Interrupt/Resume

**File:** `src/api/routers/approvals.py:97`

**Issue:** After resume, the router finds the `approval_gate` trace step and appends only steps after it (`idx + 1`). In the installed LangGraph interrupt contract, `aget_state()` at interrupt time contains only pre-node state; the `approval_gate` trace step is produced only after `Command(resume=...)`. That means the persisted `agent_steps` timeline omits the approval gate itself. The current test fake includes `approval_gate` in `aget_state()` (`tests/test_approval_api.py:50`), which does not match real `MemorySaver` behavior and gives false confidence.

**Fix:** Persist an explicit interrupted `approval_gate` step in `_handle_interrupt()`, or append from the `approval_gate` index after resume when the pre-interrupt persisted steps do not already include it. Add a MemorySaver-backed assertion that DB `agent_steps` include `approval_gate` between risk assessment and final/execute steps.

### WR-02: Trace Timeline Exposes Full Proposed Action Including Model-Derived Reasoning

**File:** `src/repositories/trace_repo.py:77`

**Issue:** `build_timeline()` exposes `approval.proposed_action` wholesale. That object is built with `reasoning_summary` from the recommendation draft (`src/agent/nodes/assess_risk_and_approval.py:141`), so the trace endpoint can leak model-generated reasoning and target identifiers despite the Phase 04 trace contract saying raw model output/action payload data should be omitted.

**Fix:** Sanitize timeline approval details, for example:

```python
def _safe_proposed_action(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_type": action.get("action_type"),
        "amount": action.get("amount"),
        "currency": action.get("currency"),
    }
```

Keep full proposed action only on the approval review endpoint if reviewers need it. Add a trace API test with a sensitive `reasoning_summary` and assert it is absent from the timeline response.

## Info

### IN-01: Final Run Latency Is Overwritten With Resume-Only Latency

**File:** `src/api/routers/approvals.py:94`

**Issue:** Interrupted runs are first persisted with pre-interrupt `total_latency_ms` in `src/api/routers/agent.py:190`, but approval resume updates `total_latency_ms` to only `resume_latency_ms`. Audit and diagnostic consumers will see the post-resume segment as the whole run, which makes run-level latency inaccurate.

**Fix:** Preserve cumulative latency. Load the existing `AgentRun.total_latency_ms` and add `resume_latency_ms`, or store separate `pre_interrupt_latency_ms` / `resume_latency_ms` fields if segmented timing is desired.

---

_Reviewed: 2026-05-16T12:47:27Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
