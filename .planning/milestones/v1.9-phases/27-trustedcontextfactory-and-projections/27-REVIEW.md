---
phase: 27-trustedcontextfactory-and-projections
reviewed: "2026-06-22T22:57:09Z"
depth: deep
files_reviewed: 24
findings_count: 1
files_reviewed_list:
  - src/agent/intent_policy.py
  - src/agent/nodes/action_draft.py
  - src/agent/nodes/investigate.py
  - src/api/routers/agent.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - src/api/routers/search.py
  - src/platform/__init__.py
  - src/platform/context_projections.py
  - src/platform/trusted_context.py
  - src/tools/executors/knowledge.py
  - tests/agent/test_intent_policy_registry.py
  - tests/agent/test_nodes/test_investigate.py
  - tests/agent/test_tools/test_unified_tool_manager.py
  - tests/architecture/test_trusted_context_boundaries.py
  - tests/knowledge/test_tenant_scope.py
  - tests/platform/test_context_projections.py
  - tests/platform/test_merchant_scope.py
  - tests/platform/test_trusted_context.py
  - tests/platform/test_trusted_context_factory.py
  - tests/test_agent_runs_api.py
  - tests/test_approval_api.py
  - tests/test_execute_action.py
  - tests/test_search_integration.py
findings:
  critical: 1
  warning: 0
  info: 0
  total: 1
status: issues_found
---

# Phase 27: Code Review Report

**Reviewed:** 2026-06-22T22:57:09Z
**Depth:** deep
**Files Reviewed:** 24
**Status:** issues_found

## Summary

Reviewed the explicit Phase 27 scope at deep depth, tracing canonical `TrustedContext` identity from API routes into graph config, tool projections, approval creation/resume, action draft reconciliation, merchant-scope projection, and the related tests.

Most seams now derive legacy config from canonical `TrustedContext`, and the previous restrictive merchant-scope projection issue is fixed in current code. One critical approval/action trust-boundary gap remains: graph interrupt payload identity is not validated in the shared approval creation path, so one route can still persist spoofed proposed-action identity.

## Critical Issues

### CR-01: Shared Approval Interrupt Path Accepts Spoofed Proposed-Action Identity

**File:** `src/api/routers/agent_runs.py:699`

**Issue:** The SSE/run-stream interrupt path calls `_create_approval_wait_payload_from_interrupt()` without validating the graph-controlled `interrupt_data["proposed_action"]` identity against the canonical persisted run and authenticated tenant. The chat route added a local `_validate_interrupt_action_run_binding()` at `src/api/routers/agent.py:361`, but that check only covers `proposed_action.run_id`, does not check `proposed_action.tenant_id`, and does not protect the shared agent-runs path. The shared helper then persists `proposed_action` unchanged at `src/api/routers/agent_runs.py:832-839` under the canonical `ApprovalRequest.run_id`.

A compromised or buggy graph node can therefore submit an interrupt whose approval row is bound to the trusted run/tenant while the hashed and later drafted action payload still carries a different `run_id` or `tenant_id`. That breaks the Phase 27 invariant that action/approval safety bindings use canonical TrustedContext identity only, and the current tests only cover chat `run_id` spoofing, not SSE spoofing or tenant spoofing.

**Fix:**

Move identity validation into the shared approval command construction path so both `/agent/chat` and `/agent-runs/{run_id}/events` fail closed before approval creation. Reject missing or mismatched proposed-action identity fields rather than normalizing them after hash/snapshot creation.

```python
def _validate_interrupt_action_identity(
    interrupt_data: dict[str, Any],
    *,
    user: User,
    run_id: UUID,
) -> None:
    proposed_action = interrupt_data.get("proposed_action")
    if not isinstance(proposed_action, dict):
        return

    mismatches: list[str] = []
    expected = {
        "tenant_id": str(user.tenant_id),
        "run_id": str(run_id),
    }
    for field, expected_value in expected.items():
        if str(proposed_action.get(field) or "") != expected_value:
            mismatches.append(f"proposed_action.{field}")

    if mismatches:
        raise ApprovalInterruptValidationError(mismatches)
```

Call this at the start of `_approval_create_command_from_interrupt()` before parsing evidence refs or constructing `ApprovalRequestCreateCommand`. Then either remove the chat-local `_validate_interrupt_action_run_binding()` or replace it with the shared check to avoid drift.

Add regression coverage in `tests/test_agent_runs_api.py` for SSE interrupts where `proposed_action.run_id` and `proposed_action.tenant_id` are spoofed, asserting an `APPROVAL_NOT_EXECUTABLE` error event and zero `ApprovalRequest` rows for both trusted and spoofed IDs. Extend the existing chat spoof tests to cover `proposed_action.tenant_id` mismatch as well.

---

_Reviewed: 2026-06-22T22:57:09Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
