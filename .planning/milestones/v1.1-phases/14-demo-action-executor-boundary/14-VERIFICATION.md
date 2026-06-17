---
phase: 14-demo-action-executor-boundary
verified: 2026-06-16T04:34:04Z
status: passed
score: "10/10 must-haves verified"
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: "7/10"
  gaps_closed:
    - "Payload/hash mismatch now recomputes canonical compute_action_payload_hash(payload), returns ACTION_BINDING_MISMATCH, and creates no ActionDraft row."
    - "No-approval draft authorization now fails closed with AUTO_ALLOWED_BINDING_REQUIRED because snapshot existence alone is not durable auto_allowed evidence."
    - "The action_draft node no longer grants itself tool:create_coupon_grant_draft; missing permission returns PERMISSION_REQUIRED before executor dispatch."
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "ReplayEventV3, lifecycle finalizer, richer replay API, retention, read-switch, and frontend timeline cleanup are not Phase 14 scope."
    addressed_in: "Phase 15"
    evidence: "ROADMAP Phase 15 goal: Implement ReplayEventV3, run lifecycle finalizer, shared sequence allocator, redaction/retention, and replay read-switch; 14-COVERAGE.md marks frontend timeline cleanup DEFERRED_WITH_OWNER to Phase 15."
  - truth: "External execution, outbox, reconciliation, compensation, and adapter dispatch are not Phase 14 scope."
    addressed_in: "Phase 17"
    evidence: "ROADMAP Phase 17 goal: Implement external action execution with transactional claim/outbox, reconciliation, and compensation."
---

# Phase 14: Demo Action Executor Boundary Verification Report

**Phase Goal:** Enforce the durable draft-only demo boundary with exact approval/snapshot binding.
**Verified:** 2026-06-16T04:34:04Z
**Status:** passed
**Re-verification:** Yes - after gap-closure plan 14-07

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Demo mode creates durable `action_drafts` and `draft_outcome.v1`. | VERIFIED | `ActionDraft` declares v2 fields and `draft_outcome` in `src/db/models.py:579`; `ActionService.create_coupon_grant_draft` persists through `ActionDraftStore.create_or_get` at `src/actions/service.py:116` and writes `draft_outcome` at `src/actions/service.py:128` and `src/actions/service.py:139`. |
| 2 | Demo mode creates no `action_executions` row or external side effect. | VERIFIED | `tests/actions/test_action_draft_v2.py:214` proves metadata has no Phase 17 external tables; `tests/actions/test_action_draft_v2.py:232` proves migration 009 does not create them; `tests/agent/test_events.py:288` rejects `action_execution_*` event emission. |
| 3 | Payload/hash mismatch is rejected before persistence and no draft row is created. | VERIFIED | `src/actions/service.py:82` recomputes `compute_action_payload_hash(payload)` before draft persistence; `src/actions/service.py:89` returns `ACTION_BINDING_MISMATCH` if the computed hash or payload `action_type` differs; tests at `tests/agent/test_tools/test_create_coupon_grant_draft.py:446` and `tests/agent/test_tools/test_create_coupon_grant_draft.py:471` assert error plus no `ActionDraft` rows through `_assert_no_drafts_for_run`. |
| 4 | No-approval authorization fails closed until durable `auto_allowed` evidence exists. | VERIFIED | `src/actions/service.py:201` returns `AUTO_ALLOWED_BINDING_REQUIRED` when `approval_request_id is None`, after validating that snapshot existence is insufficient; no service return path creates `_ValidatedActionBinding(...auto_allowed...)`. Tests cover pending/high-risk omitted approval at `tests/agent/test_tools/test_create_coupon_grant_draft.py:309`, approved-but-omitted approval at `tests/agent/test_tools/test_create_coupon_grant_draft.py:367`, and bare snapshot rejection at `tests/agent/test_tools/test_create_coupon_grant_draft.py:405`, each asserting no draft rows. |
| 5 | Missing `target_id` fails closed and final idempotency keys are service-owned and bounded. | VERIFIED | `src/actions/service.py:78` rejects missing target before persistence; `_build_idempotency_key` constructs the D-12 raw key and hashes overlong material into `key_sha256:<digest>` at `src/actions/service.py:287`; `tests/agent/test_tools/test_create_coupon_grant_draft.py:523` covers raw and bounded key behavior. Node caller keys remain non-final input; `tests/test_execute_action.py:234` asserts the node does not build the final service key. |
| 6 | Exact idempotent reuse rejects mismatched safety snapshot binding. | VERIFIED | `src/repositories/action_draft_repo.py:42` checks an existing draft with `_same_binding`; `_same_binding` compares tenant, run, action type, target, payload hash, snapshot ref, and snapshot hash at `src/repositories/action_draft_repo.py:98`; `tests/actions/test_action_draft_v2.py:272` covers mismatched snapshot hash conflict. |
| 7 | Canonical graph node is `action_draft`; `execute_action` remains a quarantined shim. | VERIFIED | `src/agent/graph.py:23` imports `action_draft`, `src/agent/graph.py:131` registers only `action_draft`, and `src/agent/graph.py:188` routes it to `final_response`. `src/agent/nodes/execute_action.py:9` only delegates to `action_draft` and carries the Phase 15 removal gate. Static guards in `tests/architecture/test_action_draft_boundaries.py:109` and `tests/architecture/test_action_draft_boundaries.py:121` prevent regression. |
| 8 | The `action_draft` write boundary enforces configured tool permissions and cannot self-authorize. | VERIFIED | `src/agent/nodes/action_draft.py:195` uses only `configurable["permissions"]`; no `permissions.append` exists in the node. `src/tools/manager.py:85` returns `PERMISSION_REQUIRED` before executor dispatch if the required permission is absent. `tests/test_execute_action.py:151` asserts missing permission returns `PERMISSION_REQUIRED`, produces no `action_draft`/`draft_outcome` update, and calls the fake executor zero times. |
| 9 | Approved resume may supply write permission only from the trusted API/approval boundary. | VERIFIED | `src/api/routers/approvals.py:537` builds resume config; `src/api/routers/approvals.py:539` appends `tool:create_coupon_grant_draft` only when the trusted `ApprovalDecisionResult` is `accept`/`approve` and `approved`. Integration coverage at `tests/test_approval_integration.py:20` proves approved resume creates one durable draft and rejected resume creates none. |
| 10 | API/final wording and coverage stay draft-only with no open Phase 14 MISSING rows. | VERIFIED | `src/api/routers/approvals.py:552` treats only `draft_outcome.status == not_executed_demo` with `external_side_effect is False` as success; `src/agent/nodes/final_response.py:134` uses the same predicate and `src/agent/nodes/final_response.py:152` says a draft was created and no external action was executed. `tests/agent/test_nodes/test_final_response.py:159` rejects legacy `action_result.status == success`; `14-COVERAGE.md:74` records no open Phase 14 gaps and rows `14-COVERAGE.md:46-48` defer Phase 15/17 work with owners. |

**Score:** 10/10 truths verified

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
| --- | --- | --- | --- |
| 1 | ReplayEventV3, lifecycle finalizer, richer replay API, retention/read-switch, and frontend timeline cleanup | Phase 15 | ROADMAP Phase 15 goal names replay/lifecycle/read-switch work; `14-COVERAGE.md:46` and `14-COVERAGE.md:48` mark these `DEFERRED_WITH_OWNER`. |
| 2 | External execution, outbox, reconciliation, compensation, and adapter dispatch | Phase 17 | ROADMAP Phase 17 goal names external execution with transactional claim/outbox, reconciliation, and compensation; `14-COVERAGE.md:47` marks it `DEFERRED_WITH_OWNER`. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/actions/service.py` | Canonical payload/hash/action_type validation, approval binding, service-owned idempotency, v2 projection | VERIFIED | Exists and substantive. Recomputes hash at line 82, rejects mismatch at line 89, rejects omitted approval at line 201, builds bounded keys at line 287, validates `ActionDraftV2Data` at line 343. |
| `src/agent/nodes/action_draft.py` | Canonical node, trusted permission passthrough, no self-grant | VERIFIED | Exists and wired. Uses config permissions at line 195, creates `ToolCallContext`, invokes `UnifiedToolManager` at line 240; no `permissions.append` in this file. |
| `src/api/routers/approvals.py` | Trusted approved-resume permission propagation and draft_outcome reconciliation | VERIFIED | `_resume_graph_config` supplies permission only for approved accept/approve results at lines 537-545; `_is_successful_demo_draft_outcome` is draft-only at lines 552-557. |
| `src/tools/manager.py` | Write permission gate before executor dispatch | VERIFIED | `UnifiedToolManager.invoke` checks caller allowlist and side effect first, then returns `PERMISSION_REQUIRED` at line 86 before executor selection/execution. |
| `src/db/models.py` | Durable `ActionDraft` with v2 fields and bounded key column | VERIFIED | `ActionDraft` table at line 579; tenant-scoped idempotency uniqueness at line 582; `idempotency_key` is `String(256)` at line 593; `draft_outcome` is persisted at line 603. |
| `tests/agent/test_tools/test_create_coupon_grant_draft.py` | DB-backed regressions for payload mismatch, no-approval fail-closed paths, v2 projection, bounded keys | VERIFIED | Contains `ACTION_BINDING_MISMATCH`, `AUTO_ALLOWED_BINDING_REQUIRED`, `ActionDraftV2Data.model_validate`, `key_sha256`, and no-draft row assertions. |
| `tests/test_execute_action.py` | Graph-node permission regression | VERIFIED | Missing-permission test at line 151 asserts `PERMISSION_REQUIRED`, no draft fields, and zero executor calls. |
| `tests/actions/test_action_draft_v2.py` | v2 schema, store exact reuse, no external tables | VERIFIED | Covers v2 fields, metadata/migration absence of Phase 17 tables, exact reuse, and snapshot mismatch conflicts. |
| `tests/architecture/test_action_draft_boundaries.py` | Static owner/quarantine boundary tests | VERIFIED | Verifies canonical graph node, shim delegation, caller allowlist, action_result success ban, and no external-path imports. |
| `.planning/phases/14-demo-action-executor-boundary/14-COVERAGE.md` | Final coverage map with no Phase 14 MISSING rows | VERIFIED | Marks GOAL/DEMO-01/DEMO-02 covered, lists Phase 15/17 deferrals with owners, and records no open Phase 14 gaps. |

**GSD literal-check note:** `gsd-sdk query verify.artifacts 14-02-PLAN.md` reports 6/7 because the old plan artifact expected the literal string `auto_allowed` in `src/actions/service.py`. Plan 14-07 deliberately changed the current Phase 14 service contract to fail closed with `AUTO_ALLOWED_BINDING_REQUIRED` because no durable auto-allowed marker exists. This is a stale literal expectation, not a goal gap.

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `src/actions/service.py` | `src.approvals.snapshot_service.compute_action_payload_hash` | Import and call before persistence | VERIFIED | Import at `src/actions/service.py:15`; call at `src/actions/service.py:82`; mismatch returns before `draft_store.create_or_get`. |
| `src/actions/service.py` | `ActionSafetySnapshot` / `ApprovalRequest` | `_validate_action_binding` | VERIFIED | Snapshot tuple is looked up at `src/actions/service.py:186`; omitted approval fails closed at line 201; explicit approved request binding checks run at lines 207-226. |
| `src/actions/service.py` | `ActionDraftStore` / `ActionDraftRepository` | `draft_store.create_or_get` | VERIFIED | Service calls store at line 116; repository persists only after exact-binding validation at `src/repositories/action_draft_repo.py:55`. |
| `src/agent/nodes/action_draft.py` | `src/tools/manager.py` | `UnifiedToolManager.invoke` with configured permissions | VERIFIED | Node imports manager at line 13, sets `ToolCallContext.permissions` from config at line 201, and invokes manager at line 240; manager enforces permission at `src/tools/manager.py:85`. |
| `src/api/routers/approvals.py` | `src/agent/nodes/action_draft.py` | Resume reconciliation and trusted config | VERIFIED | `_resume_graph_after_decision` builds config at line 260 and `_reconcile_approved_action_draft` calls `action_draft` at line 528. |
| `src/agent/graph.py` | `src/agent/nodes/action_draft.py` | Graph registration and routing | VERIFIED | Imported at line 23, registered at line 131, and routed at lines 174, 184, and 188. |
| `src/agent/nodes/final_response.py` | `AgentState.draft_outcome` | Final wording predicate | VERIFIED | `final_response` reads `draft_outcome` at line 190 and uses `_is_successful_demo_draft_outcome` at lines 134-139. |
| `src/actions/service.py` | `src/agent/events.py` / trace projection | Safe `action_draft_created` refs and `draft_outcome` projection | VERIFIED | Service emits safe refs at `src/actions/service.py:245`; tests prove no raw payload in trace projections and no `action_execution_*` events. |

**GSD literal-check note:** `gsd-sdk query verify.key-links 14-07-PLAN.md` reports 1/3 because the escaped pattern `compute_action_payload_hash\\(` did not match the real source and the tool did not resolve the `UnifiedToolManager` import as a target reference. Manual source tracing verifies both links.

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `src/actions/service.py` | `payload` / `action_payload_hash` | Tool args from `ActionToolExecutor` | Yes | FLOWING - payload hash is recomputed from the actual `payload` at line 82 and must match the supplied binding before persistence. |
| `src/actions/service.py` | `approval_request_id` | Tool args / trusted approval resume | Yes | FLOWING - no-approval returns `AUTO_ALLOWED_BINDING_REQUIRED`; explicit approvals must match tenant/run/status/hash/snapshot at lines 207-226. |
| `src/actions/service.py` | `idempotency_key` | Service-owned `_build_idempotency_key` | Yes | FLOWING - caller key is overwritten with a service-built bounded key before repository persistence. |
| `src/agent/nodes/action_draft.py` | `permissions` | Runnable config from API/orchestration boundary | Yes | FLOWING - node passes configured permissions only; manager blocks missing permission before executor dispatch. |
| `src/api/routers/approvals.py` | `permissions` | `ApprovalDecisionResult` | Yes | FLOWING - approved accept/approve decisions are the only resume path that adds the write permission. |
| `src/api/routers/approvals.py` | `draft_outcome` | `action_draft` update | Yes | FLOWING - API reconciliation treats only `not_executed_demo` and `external_side_effect is False` as success. |
| `src/agent/nodes/final_response.py` | `draft_outcome` | AgentState | Yes | FLOWING - final response says draft created only when draft outcome proves no external side effect. |
| `src/repositories/action_draft_repo.py` | Existing draft binding | Database row lookup by tenant/idempotency key | Yes | FLOWING - reuse returns an existing draft only when all binding fields match. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| 14-07 focused regressions | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_tools/test_create_coupon_grant_draft.py tests/test_execute_action.py -q --tb=short` | Orchestrator result: `38 passed, 1 warning` | PASS |
| 14-07 lint | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/actions/service.py src/agent/nodes/action_draft.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/test_execute_action.py` | Orchestrator result: all checks passed | PASS |
| Focused Phase 14 regression suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_execute_action.py tests/test_approval_integration.py tests/test_trace_api.py tests/agent/test_graph.py tests/agent/test_nodes/test_final_response.py tests/agent/test_tools/test_create_coupon_grant_draft.py tests/architecture/test_action_draft_boundaries.py tests/actions/test_action_draft_v2.py tests/agent/test_events.py tests/agent/test_nodes/test_receive_request.py -q --tb=short` | Orchestrator result: `125 passed, 1 warning` | PASS |
| Schema drift | `gsd-sdk query verify.schema-drift 14` | `valid: true`, no issues | PASS |
| Artifact checks | `gsd-sdk query verify.artifacts` for 14-01..14-07 | 14-01, 14-03, 14-04, 14-05, 14-06, and 14-07 passed; 14-02 has stale `auto_allowed` literal note above | PASS_WITH_NOTE |
| Key-link checks | `gsd-sdk query verify.key-links` for 14-01..14-07 | 14-01..14-06 passed; 14-07 has literal/import-resolution note above and is manually verified | PASS_WITH_NOTE |
| Static external-side-effect scan | `rg -n 'action_executions|action_outbox_events|action_reconciliation_jobs|action_compensation_records' src tests` | Only negative test constants in `tests/actions/test_action_draft_v2.py` | PASS |
| Static event scan | `rg -n 'action_execution_' src tests` | Only negative tests assert absence/rejection | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| DEMO-01 | 14-01..14-07 | Demo mode creates durable draft and `draft_outcome` only, with no execution row or external side effect. | SATISFIED | `ActionDraft` v2 persistence, `draft_outcome.v1`, no Phase 17 tables/events, safe trace projections, and focused pytest `125 passed`. |
| DEMO-02 | 14-01..14-07 | Demo wording and hash/revision guards cannot claim or authorize real execution. | SATISFIED | Payload/hash/action_type mismatch rejection, omitted-approval fail-closed tests, write-tool permission enforcement, approved-resume trusted permission path, and final/API wording tests. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| None | - | Blocking stub/placeholder/self-grant/external-execution pattern scan | - | No blocker anti-patterns found in reviewed Phase 14 files. |
| `src/api/routers/approvals.py` | 540 | `permissions.append(ACTION_DRAFT_PERMISSION)` | Info | Acceptable trusted boundary: permission is appended only for approved accept/approve `ApprovalDecisionResult`, not inside `action_draft`. |
| `src/agent/nodes/action_draft.py` | 213 | Caller-local `auto_allowed` string in pre-service idempotency key | Info | Not authorization evidence and not the persisted key; service ignores caller key and fails closed when `approval_request_id` is omitted. |
| `tests/actions/test_action_draft_v2.py` | 111 | Store fixture uses `approval_revision_ref="auto_allowed"` | Info | Lower-level store fixture only; service-level no-approval authorization is blocked by `AUTO_ALLOWED_BINDING_REQUIRED`. |

### Disconfirmation Checks

| Check | Finding | Impact |
| --- | --- | --- |
| Requirements status candidate | `.planning/REQUIREMENTS.md` now marks DEMO-02 complete after Phase 14 gap closure verification. | Aligned with this report's DEMO-02 SATISFIED finding from source/test evidence. |
| Misleading check candidate | Literal `gsd-sdk` checks miss post-14-07 intent in two places: stale `auto_allowed` text from 14-02 and two 14-07 key links. | Manually source-verified; documented above so future readers do not misread tool output as a blocker. |
| Uncovered future path candidate | Durable no-approval `auto_allowed` enablement is not implemented. | Intentional Phase 14 behavior is fail-closed; tests prove current no-approval paths do not authorize drafts. A future auto-allowed feature must add its own durable marker and tests. |

### Human Verification Required

None. All Phase 14 goal claims are source-verifiable and covered by automated/static checks.

### Gaps Summary

No gaps remain. Plan 14-07 closes all three stale verification failures:

- `ActionService` binds persisted payloads to canonical `compute_action_payload_hash(payload)` and rejects mismatch before persistence.
- `approval_request_id is None` fails closed with `AUTO_ALLOWED_BINDING_REQUIRED` until durable auto-allowed evidence exists.
- `action_draft` no longer self-grants `tool:create_coupon_grant_draft`; missing permission returns `PERMISSION_REQUIRED` before executor dispatch, while approved resume receives permission only from the trusted API/approval boundary.

The previously passing Phase 14 truths still pass: durable draft/outcome persistence, no external execution side effects, service-owned bounded idempotency, exact reuse conflict checks, canonical graph node and quarantined shim, draft-only API/final wording, and owned Phase 15/17 deferrals.

---

_Verified: 2026-06-16T04:34:04Z_
_Verifier: Claude (gsd-verifier)_
