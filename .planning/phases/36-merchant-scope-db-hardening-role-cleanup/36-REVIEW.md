---
phase: 36-merchant-scope-db-hardening-role-cleanup
reviewed: 2026-06-30T13:12:53Z
depth: standard
files_reviewed: 37
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 36: Code Review Report

**Status:** clean after adjudication and fixes
**Initial reviewer:** gsd-code-reviewer
**Final adjudicator:** Codex

## Summary

The initial review found three warnings. Codex verified all three against repository code, judged them true, implemented fixes, and reran the relevant gates. No unresolved review findings remain.

## Resolved Findings

### WR-01: Real business reads omitted `merchant_id`

**Verdict:** true.

`assess_risk_and_approval` requires the selected business resource to carry `merchant_id` before it can derive `TargetMerchantBindingV1`. The real order/refund/ticket adapters used strict projections that did not include `merchant_id`, so the default adapter path could fail closed even after an authorized business read.

**Fix:** Added authorized `merchant_id` output to demo order/refund/ticket reads and to the strict adapter projections. Added/updated default-registry business tests to assert the real business fact surface includes the expected merchant id.

### WR-02: Auto-allowed drafts could run before persisted `AgentRun` scope was updated

**Verdict:** true.

The normal graph path can enter `action_draft` after a low-risk auto-allowed decision before final run-state persistence has reclassified the `AgentRun` from `unknown_legacy` to `business_merchant`.

**Fix:** `ActionService` now validates the snapshot and auto-allowed binding first, then atomically promotes an `unknown_legacy` run with empty target fields to `business_merchant` only when the validated binding supplies the target merchant proof. Existing `business_merchant` mismatches and non-empty legacy scope conflicts still fail closed. The auto-allowed action test now starts from a newly created `unknown_legacy` run and asserts successful draft creation plus persisted scope promotion.

### WR-03: Auto-allowed binding did not validate stored `risk_decision` payload

**Verdict:** true.

The previous auto-allowed path compared `risk_decision_ref` but did not validate the submitted `risk_decision` payload before persisting it on the draft.

**Fix:** `ActionService` now canonical-validates `RiskDecisionV1` through the existing binding material path and requires tenant id, run id, action payload hash, and `approval_required is False` to match the auto-allowed draft. Added a tamper test that keeps `risk_decision_ref` and the rest of the binding unchanged while changing the stored risk decision payload; the service rejects it with `AUTO_ALLOWED_BINDING_MISMATCH`.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_service.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short` -> 49 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_adapters.py tests/business/test_service.py tests/tools/test_tool_platform.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short` -> 112 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/business/test_service.py tests/actions/test_phase34_action_draft_bindings.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/test_graph_routing.py tests/approvals/test_phase36_scope_consistency.py tests/test_approval_api.py -q --tb=short` -> 175 passed, 1 warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py tests/integration/test_auth.py tests/agent/test_phase36_run_scope.py tests/approvals/test_phase36_scope_consistency.py tests/approvals/test_migration_contract.py tests/db/test_phase36_migration_preflight.py tests/replay/test_phase36_readiness.py tests/business/test_service.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/test_approval_api.py tests/test_trace_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` -> 287 passed, 3 warnings.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests` -> All checks passed.
- `git diff --check` -> passed.
