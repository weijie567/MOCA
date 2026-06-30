---
phase: 34
phase_name: approval-and-actiondraft-boundary-hardening
date: 2026-06-29T07:09:57Z
verified: 2026-06-29T07:09:57Z
status: passed
score: 24/24 must-haves verified
roadmap_score: 5/5 success criteria verified
plan_truth_score: 19/19 plan truths verified
requirements:
  - APF-15
  - APF-16
overrides_applied: 0
gaps: []
human_verification: []
deferred: []
re_verification: false
---

# Phase 34 Verification Report

**Phase Goal:** Bind action proposals, approval decisions, and action drafts to verified facts/evidence/claims/risk/snapshots while preserving the no-real-execution boundary.

**Status:** passed

## Goal Achievement

Phase 34 achieves the roadmap goal. The implementation binds approval/action authority to typed refs, persisted fields, risk decisions, payload hashes, safety snapshots, and target merchant scope. The graph keeps `risk_gate` routing ownership separate from `approval_gate`; action draft creation remains demo-draft-only and fails closed without exact approval or auto-allowed binding material.

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Action proposals and drafts bind structured payloads to business fact refs, verified evidence refs, claim verification refs, risk decisions, payload hashes, and safety snapshots. | VERIFIED | `src/approvals/schemas.py` defines strict `RiskDecisionV1`, `TargetMerchantBindingV1`, `AutoAllowedActionBindingV1`, and approval command/result fields. `src/actions/schemas.py` enriches `ActionDraftV2Data`; `src/db/models.py` and migration 018 persist matching fields. `ActionService` validates and persists exact bindings. |
| 2 | `risk_gate` owns blocked/approval-required/auto-draft routing while `approval_gate` only handles approval plan, trusted resume, interrupt, and revision state machine behavior. | VERIFIED | `src/agent/graph.py:67` routes after risk with `_approval_plan_ready` / `_auto_allowed_binding_ready`; `src/agent/graph_vocabulary.py:91` maps legacy `assess_risk_and_approval` to target `risk_gate`; `src/agent/nodes/approval_gate.py:26` only builds an interrupt from `approval_plan` and safe refs. |
| 3 | Tests prove ordinary chat cannot forge approval/action authority, payload changes invalidate old approval, and no full real external execution is introduced. | VERIFIED | Spot-checks passed for ordinary approval spoof rejection, stale hash rejection, action draft binding mismatch, and final static no-real-execution guards. `tests/architecture/test_phase34_approval_action_boundaries.py` scans production source for execution tables/workers and execution-positive wording. |
| 4 | ApprovalRequest and ActionDraft bind target merchant or scoped `BusinessFactRefV1`; manager queues and resume paths cannot use wildcard `server_merchant_scope` unless actor is admin. | VERIFIED | `src/api/routers/approvals.py:666` filters manager scope by persisted `target_merchant_id`; `src/api/routers/approvals.py:678` fail-closes out-of-scope approval access. `src/api/routers/approvals.py:608` creates trusted resume config with `server_tool_permissions` only and no `server_merchant_scope`. |
| 5 | Future system-owned wildcard approval/action jobs must use a separate trusted system context contract, not `TrustedContextFactory.create_from_request(user=...)`. | VERIFIED | No production approval/action resume path passes `server_merchant_scope`; static scan found only test assertions. Phase 34 does not introduce system-owned wildcard action jobs. |

**Score:** 24/24 must-haves verified: 5/5 roadmap criteria plus 19/19 plan truth checks.

## Required Artifacts

| Artifact / Area | Status | Evidence |
|---|---|---|
| Approval/action schemas | VERIFIED | `gsd-sdk query verify.artifacts` passed for Plans 34-01 through 34-04 and 34-06. Manual grep confirmed strict typed refs and binding fields in `src/approvals/schemas.py` and `src/actions/schemas.py`. |
| Persistence / migration | VERIFIED | `src/db/models.py` and `src/db/migrations/versions/018_phase34_approval_action_bindings.py` contain approval/action target merchant, business/evidence/claim/risk, idempotency, and auto-allowed binding columns. |
| Risk routing / vocabulary | VERIFIED | `src/agent/graph.py` imports `AutoAllowedActionBindingV1` and validates exact approval/auto bindings before routing; `src/agent/graph_vocabulary.py` declares `assess_risk_and_approval -> risk_gate`. |
| Approval service / API | VERIFIED | `ApprovalService.create_request` persists command-provided Phase 34 bindings; decision results and resume payloads use persisted request fields. Manager access is same-merchant only. |
| Agent runs approval bridge | VERIFIED | `_approval_create_command_from_interrupt` requires and validates Phase 34 fields before creating `ApprovalRequestCreateCommand`; safe SSE payloads expose summaries/refs only. |
| Action draft service / node | VERIFIED | `ActionService` rebuilds durable idempotency from trusted binding material, validates exact approval/auto bindings, and persists matching fields through `ActionDraftRepository`. |
| Final static guards | VERIFIED | `tests/architecture/test_phase34_approval_action_boundaries.py` covers approval spoofing, wildcard resume, manager shortcuts, no-real-execution source patterns, route validator presence, bridge coverage, and Phase 35 trace projection deferral. |

**Verifier note:** `verify.artifacts` reported a literal Plan 34-05 pattern miss because `action_outbox_events` is no longer in `tests/architecture/test_action_draft_boundaries.py`. Equivalent final no-real-execution coverage exists in `tests/architecture/test_phase34_approval_action_boundaries.py` and passed. `verify.key-links` also missed the risk-gate alias by literal regex; manual inspection verified it at `src/agent/graph_vocabulary.py:91`.

## Key Link Verification

| Link | Status | Evidence |
|---|---|---|
| Risk gate -> approval/action schemas | VERIFIED | `assess_risk_and_approval.py` imports and validates `RiskDecisionV1`, `TargetMerchantBindingV1`, `AutoAllowedActionBindingV1`, `BusinessFactRefV1`, and `EvidenceRefV1`. |
| Graph routing -> risk/approval/action nodes | VERIFIED | `route_after_risk` returns `approval_gate` only with exact `approval_plan`, and `action_draft` only with strict `AutoAllowedActionBindingV1`; otherwise `final_response`. |
| Approval gate -> agent_runs bridge -> ApprovalService | VERIFIED | Interrupt payload carries structured refs; `agent_runs` maps those fields to `ApprovalRequestCreateCommand`; `ApprovalService` persists them. |
| ApprovalService -> trusted resume -> action_draft | VERIFIED | `TrustedApprovalResultV1` is built from persisted request fields; `action_draft` rechecks Phase 34 bindings before invoking the node-only tool. |
| ActionService -> ActionDraftRepository | VERIFIED | `create_or_get` persists binding fields and rejects idempotency reuse when binding material differs. |

## Data-Flow Trace

| Flow | Source | Sink | Status |
|---|---|---|---|
| Risk binding material | `assess_risk_and_approval` builds refs, risk decision, hashes, snapshot refs, target merchant, and `approval_plan`. | `route_after_risk` and `approval_gate` | FLOWING |
| Approval request binding | `approval_gate` interrupt fields validated by `agent_runs`. | `ApprovalService.create_request` -> `ApprovalRequest` columns | FLOWING |
| Trusted approval result | Persisted `ApprovalRequest` binding fields. | `TrustedApprovalResultV1.resume_payload` -> `action_draft` | FLOWING |
| Action draft binding | Approval result or `AutoAllowedActionBindingV1` plus current state. | `ActionService` -> `ActionDraftRepository` -> `ActionDraft` columns | FLOWING |
| Safe projection | Persisted result / draft records. | SSE `approval_required`, working state `draft_artifact`, final response draft-only text | FLOWING |

## Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| APF-15 | SATISFIED | Contracts, approval decisions, and action drafts carry structured payload/hash/snapshot and business/evidence/claim/risk bindings through schemas, DB columns, ApprovalService, agent_runs, ActionService, and ActionDraftRepository. Tests cover typed DTOs, migration/ORM parity, bridge preservation, exact mismatch rejection, and safe projections. |
| APF-16 | SATISFIED | `risk_gate` semantics live in `assess_risk_and_approval` plus `route_after_risk`; `approval_gate` has no blocked/approval-required/auto-draft ownership. Tests cover route fail-closed behavior, ordinary spoof rejection, edit reroute, and static approval_gate responsibility boundaries. |

## Checks Performed

| Check | Result |
|---|---|
| `gsd-sdk query roadmap.get-phase 34 --raw` | Confirmed five Phase 34 success criteria and APF-15/APF-16. |
| `gsd-sdk query verify.artifacts/key-links` for all six plans | Passed except two literal false positives manually resolved as noted above. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase34_approval_action_boundaries.py tests/test_graph_routing.py::test_route_after_risk_fails_closed_when_approval_plan_hash_mismatches_state tests/test_graph_routing.py::test_route_after_approval_returns_final_response_on_untrusted_ordinary_payload tests/test_execute_action.py::test_execute_action_blocks_when_phase34_approval_binding_mismatches_state tests/actions/test_phase34_action_draft_bindings.py::test_create_coupon_grant_draft_rejects_phase34_approval_binding_mismatch -q --tb=short` | 14 passed, 1 warning in 5.21s. |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py::test_manager_approval_review_paths_allow_same_merchant tests/test_approval_api.py::test_manager_approval_review_paths_deny_cross_merchant tests/test_approval_api.py::test_manager_approval_review_paths_deny_missing_target_merchant tests/test_approval_api.py::test_decide_approve_builds_command_from_authenticated_actor_and_resumes_with_service_payload -q --tb=short` | 4 passed, 1 warning in 16.29s. |
| Static scan for TODO/FIXME/placeholders in touched production/test files | No matches. |
| Static scan for production `server_merchant_scope`, `requested_by.*merchant`, `merchant_id.*requested_by` shortcuts | No production matches; only test assertions. |
| Static scan for production real-execution table/worker names and execution-positive wording | No production matches. |
| `git diff --check` | Passed. |
| `git status --short` before writing this artifact | Clean. |

## Anti-Patterns Found

None blocking. No production placeholders, wildcard resume shortcuts, requested_by merchant authorization shortcut, real-execution storage/worker definitions, or execution-positive response wording were found.

## Human Verification Required

None.

## Gaps Summary

None. The Phase 35 trace/run API projection deferral is explicitly recorded in `34-CONTEXT.md` and `34-VALIDATION.md`; it is not a Phase 34 gap because Phase 34 closed persistence and live approval-required projection safety.

---

_Verified: 2026-06-29T07:09:57Z_
_Verifier: Codex (gsd phase verifier)_
