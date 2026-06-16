---
phase: 14-demo-action-executor-boundary
verified: 2026-06-16T03:02:09Z
status: gaps_found
score: 7/10 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Hash/revision mismatches are rejected and final response wording never claims real execution."
    status: failed
    reason: "Final wording is draft-only, but ActionService does not recompute the persisted payload hash. A caller can pass a valid approved action_payload_hash/safety snapshot tuple while persisting a different payload as the draft proposed_action body."
    artifacts:
      - path: "src/actions/service.py"
        issue: "create_coupon_grant_draft validates the provided hash tuple at lines 81-88, then persists payload at line 110 without computing hash(payload) or checking action_type against the payload."
      - path: "tests/agent/test_tools/test_create_coupon_grant_draft.py"
        issue: "Existing positive tests pass small payloads such as {'target_id': 'RF-1001'} with hashes produced from ApprovalRequest.proposed_action, so the mismatch path is normalized rather than rejected."
    missing:
      - "Compute the canonical proposed_action hash from payload before draft persistence and reject ACTION_BINDING_MISMATCH when it differs from action_payload_hash."
      - "Add a regression test proving a payload/hash mismatch is rejected and no ActionDraft is created."
  - truth: "Hash/revision guards cannot authorize demo draft creation without approved binding or durable auto-allowed evidence."
    status: failed
    reason: "When approval_request_id is omitted, _validate_action_binding returns auto_allowed for any existing snapshot tuple. The snapshot row does not prove that the action was low-risk or auto-allowed, so a pending/high-risk approval snapshot can be used to create a draft without approval."
    artifacts:
      - path: "src/actions/service.py"
        issue: "approval_request_id is None returns _ValidatedActionBinding(revision_marker='auto_allowed') at lines 184-185 after only snapshot tuple lookup."
      - path: "tests/agent/test_tools/test_create_coupon_grant_draft.py"
        issue: "test_create_coupon_grant_draft_auto_allowed_key_is_service_owned creates a normal pending approval request and expects approval_request_id=None to succeed."
    missing:
      - "Persist and verify a durable auto_allowed decision before allowing no-approval draft creation, or require an approved approval_request_id until that binding exists."
      - "Add regression tests proving pending/high-risk approval snapshots cannot create drafts by omitting approval_request_id."
  - truth: "The action_draft write boundary enforces configured tool permissions and cannot self-authorize the write tool."
    status: failed
    reason: "The action_draft node appends tool:create_coupon_grant_draft to its own ToolCallContext permissions before invoking UnifiedToolManager, making the manager's PERMISSION_REQUIRED check ineffective at the write boundary."
    artifacts:
      - path: "src/agent/nodes/action_draft.py"
        issue: "lines 195-197 synthesize the write permission when it is absent."
      - path: "src/tools/manager.py"
        issue: "line 85 checks descriptor.required_permission, but the caller has already been upgraded by the node."
      - path: "tests/test_execute_action.py"
        issue: "No test asserts missing tool permission returns PERMISSION_REQUIRED; existing node tests invoke with only a session config and expect success."
    missing:
      - "Stop adding tool permissions inside action_draft; pass only permissions supplied by the trusted orchestration/auth boundary."
      - "Add a regression test proving action_draft without tool:create_coupon_grant_draft returns a permission error and creates no draft."
deferred:
  - truth: "ReplayEventV3, lifecycle finalizer, richer replay API, retention, and read-switch are not implemented in Phase 14."
    addressed_in: "Phase 15"
    evidence: "ROADMAP Phase 15 goal: Implement ReplayEventV3, run lifecycle finalizer, shared sequence allocator, redaction/retention, and replay read-switch."
  - truth: "External execution, outbox, reconciliation, compensation, and adapter dispatch are not implemented in Phase 14."
    addressed_in: "Phase 17"
    evidence: "ROADMAP Phase 17 goal: Implement external action execution with transactional claim/outbox, reconciliation, and compensation."
  - truth: "Frontend timeline label cleanup for legacy execute_action wording is not implemented in Phase 14."
    addressed_in: "Phase 15"
    evidence: "14-COVERAGE.md records frontend timeline label cleanup as Phase 15 Replay Event Contract owned."
---

# Phase 14: Demo Action Executor Boundary Verification Report

**Phase Goal:** Enforce the durable draft-only demo boundary with exact approval/snapshot binding.  
**Verified:** 2026-06-16T03:02:09Z  
**Status:** gaps_found  
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Demo mode creates durable action_drafts and draft_outcome.v1. | VERIFIED | `ActionDraft` has v2 fields and `draft_outcome`; `ActionService` persists via `ActionDraftStore.create_or_get`; `tests/actions/test_action_draft_v2.py` covers persisted outcome. |
| 2 | Demo mode creates no action execution row or external side effect. | VERIFIED | No Phase 17 tables in metadata/migration; no `action_execution_*` event registration; focused pytest passed. |
| 3 | Hash/revision mismatches are rejected and final response wording never claims real execution. | FAILED | Wording is verified, but payload/hash mismatch is not rejected: `src/actions/service.py` persists `payload` without recomputing `action_payload_hash`. |
| 4 | No-approval draft creation is authorized only by durable auto-allowed evidence. | FAILED | `src/actions/service.py` treats any matching snapshot tuple as `auto_allowed` when `approval_request_id is None`. |
| 5 | Missing target_id fails closed and idempotency keys are service-owned. | VERIFIED | `TARGET_ID_REQUIRED` check exists; final persisted key is rebuilt by service and ignores caller key. |
| 6 | Exact idempotent reuse rejects mismatched safety snapshot binding. | VERIFIED | Repository `_same_binding` checks tenant/run/action/target/payload hash/snapshot ref/snapshot hash; tests cover mismatched snapshot hash conflict. |
| 7 | Canonical graph node is `action_draft`; `execute_action` is a quarantined shim. | VERIFIED | Graph registers `action_draft`; shim delegates only; static import tests pass. |
| 8 | The action_draft write boundary enforces tool permissions. | FAILED | `action_draft` self-adds `tool:create_coupon_grant_draft`, bypassing `UnifiedToolManager` permission enforcement. |
| 9 | API/final success surfaces use draft_outcome and draft-only wording. | VERIFIED | `approvals.py` and `final_response.py` require `not_executed_demo` and `external_side_effect is False`; forbidden wording tests pass. |
| 10 | Coverage has no open Phase 14 MISSING rows and defers Phase 15/17 work with owners. | VERIFIED | `rg MISSING 14-COVERAGE.md` returns no matches; deferred rows name Phase 15 and Phase 17 owners. |

**Score:** 7/10 truths verified

### Deferred Items

Items not met in Phase 14 but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
| --- | --- | --- | --- |
| 1 | ReplayEventV3/lifecycle/read-switch | Phase 15 | ROADMAP Phase 15 goal names ReplayEventV3, lifecycle finalizer, retention, and read-switch. |
| 2 | External execution/outbox/reconciliation/compensation | Phase 17 | ROADMAP Phase 17 goal names external execution with transactional claim/outbox, reconciliation, and compensation. |
| 3 | Frontend timeline label cleanup | Phase 15 | `14-COVERAGE.md` marks this DEFERRED_WITH_OWNER to Phase 15. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| Plan 14-01 artifacts | v2 schemas, ORM, migration, tests | VERIFIED | `gsd-sdk verify.artifacts` passed 4/4. Alembic current is `009_action_draft_v2 (head)`. |
| Plan 14-02 artifacts | state reset, service, repository, executor, tests | VERIFIED_WITH_GAPS | `gsd-sdk verify.artifacts` passed 7/7, but `src/actions/service.py` has goal-level binding gaps. |
| Plan 14-03 artifacts | canonical node, shim, graph, boundary tests | VERIFIED_WITH_GAPS | `gsd-sdk verify.artifacts` passed 5/5, but `src/agent/nodes/action_draft.py` self-grants tool permission. |
| Plan 14-04 artifacts | approval/final wording and tests | VERIFIED | `gsd-sdk verify.artifacts` passed 5/5. |
| Plan 14-05 artifacts | safe events, trace projection, tests | VERIFIED | `gsd-sdk verify.artifacts` passed 7/7. |
| Plan 14-06 artifacts | negative boundary tests and coverage | VERIFIED_WITH_GAPS | `gsd-sdk verify.artifacts` passed 6/6, but coverage misses the review-confirmed binding/permission gaps. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| 14-01 key links | schemas/migration to ORM | column/constants matching | VERIFIED | `gsd-sdk verify.key-links` passed 2/2. |
| 14-02 key links | executor -> service -> repo; reset -> state | service calls and state fields | VERIFIED | `gsd-sdk verify.key-links` passed 3/3. |
| 14-03 key links | graph -> action_draft; catalog -> manager | route keys and allowlist guard | VERIFIED_WITH_GAP | Static links pass 2/2; permission enforcement is bypassed by node self-grant. |
| 14-04 key links | approvals/final -> draft_outcome | success sentinel migration | VERIFIED | `gsd-sdk verify.key-links` passed 2/2. |
| 14-05 key links | service -> events; executor -> service; trace repo -> router | event emission and projection | VERIFIED | `gsd-sdk verify.key-links` passed 3/3. |
| 14-06 key links | tests -> shim/source/coverage | static scans and coverage mapping | VERIFIED_WITH_GAP | Static links pass 3/3; tests do not cover payload/hash mismatch, no-approval bypass, or missing permission. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `src/actions/service.py` | `payload`, `action_payload_hash`, `safety_snapshot_*` | Tool args from `ActionToolExecutor` / `action_draft` | Partially | HOLLOW_BINDING - hash tuple is validated against snapshot rows, but not against the payload being persisted. |
| `src/actions/service.py` | `approval_request_id` / `auto_allowed` | Tool args and `_validate_action_binding` | Partially | HOLLOW_AUTH - no-approval path relies only on snapshot tuple existence, not durable auto-allowed evidence. |
| `src/repositories/action_draft_repo.py` | `draft_outcome` | `ActionService._draft_outcome` | Yes | FLOWING - persisted on `ActionDraft` and refreshed with draft id. |
| `src/agent/nodes/action_draft.py` | `permissions` | Runnable config | No | HOLLOW_PERMISSION - missing permission is replaced inside the node before manager validation. |
| `src/api/routers/approvals.py` | `draft_outcome` | `action_draft` update | Yes | FLOWING - missing or side-effecting outcomes become reconciliation errors. |
| `src/agent/nodes/final_response.py` | `draft_outcome` | AgentState | Yes | FLOWING - final text is produced only for not-executed demo outcomes. |
| `src/repositories/trace_repo.py` | `draft_outcome` | `ActionDraft.draft_outcome` | Yes | FLOWING - trace/timeline projection includes safe outcome and excludes raw payload. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Focused Phase 14 code slice | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/actions/test_action_draft_v2.py tests/architecture/test_action_draft_boundaries.py tests/agent/test_nodes/test_final_response.py -q --tb=short` | Sandbox run hit PostgreSQL `PermissionError`; approved rerun passed `39 passed, 1 warning`. | PASS |
| Live migration head | `UV_CACHE_DIR=/tmp/uv-cache uv run alembic current` | `009_action_draft_v2 (head)` | PASS |
| Artifact checks | `gsd-sdk query verify.artifacts` for 14-01..14-06 | All six plans passed, 34/34 artifacts. | PASS |
| Key link checks | `gsd-sdk query verify.key-links` for 14-01..14-06 | All six plans passed, 15/15 links. | PASS |
| Coverage MISSING rows | `rg -n "MISSING" 14-COVERAGE.md` | No matches in `14-COVERAGE.md`; matches only in generic REQUIREMENTS planning text. | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| DEMO-01 | 14-01..14-06 | Demo mode creates durable draft and draft_outcome only, with no execution row or external side effect. | SATISFIED | Durable `ActionDraft`/`draft_outcome` persistence, no external tables/events/imports, no raw trace payload; focused tests pass. |
| DEMO-02 | 14-01..14-06 | Demo wording and hash/revision guards cannot claim or authorize real execution. | BLOCKED | Wording and approved-request status checks pass, but payload/hash mismatch and no-approval snapshot bypass mean guards can authorize an unbound draft. |

### Code Review Findings Re-Evaluated

| Finding | Independent Status | Evidence | Verification Impact |
| --- | --- | --- | --- |
| CR-01 payload can differ from approved hash | CONFIRMED | `src/actions/service.py` validates tuple at lines 81-88 and persists `payload` at line 110 with no `compute_action_payload_hash` call. | Blocking gap against exact approval/snapshot binding. |
| CR-02 no-approval bypass | CONFIRMED | `approval_request_id is None` returns `auto_allowed` at lines 184-185 after only snapshot lookup; test at lines 292-324 expects this from a pending approval context. | Blocking gap against hash/revision authorization guard. |
| CR-03 node self-grants permission | CONFIRMED | `action_draft.py` lines 195-197 appends missing permission; manager check at line 85 is therefore ineffective. | Blocking gap against write boundary. |
| WR-01 action_draft response not ActionDraftV2Data | CONFIRMED WARNING | `_action_draft_data` omits `proposed_action`, `approval_ref`, `draft_outcome`, and `created_at` required by `ActionDraftV2Data`. | Not the primary roadmap goal, but should be fixed or renamed as a projection schema. |
| WR-02 key length can exceed DB column | CONFIRMED WARNING | `_build_idempotency_key` concatenates long fields; `ActionDraft.idempotency_key` is `String(256)`. | Reliability risk; not an external execution gap, but should be fixed before broad target ids. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `src/actions/service.py` | 110 | Persists unverified `payload` under provided `action_payload_hash` | Blocker | Draft proposed_action body can be unbound from approved hash material. |
| `src/actions/service.py` | 184-185 | Treats any valid snapshot tuple as `auto_allowed` when approval id is omitted | Blocker | Pending/high-risk approval snapshot can become a demo draft without approval. |
| `src/agent/nodes/action_draft.py` | 195-197 | Self-grants required write-tool permission | Blocker | `UnifiedToolManager` permission gate is bypassed at the write boundary. |
| `src/actions/service.py` | 296-315 | `action_draft.v2` projection omits fields required by `ActionDraftV2Data` | Warning | Schema-labeled response cannot be validated by the schema contract. |
| `src/actions/service.py` / `src/db/models.py` | 276 / 593 | Composite idempotency key may exceed `String(256)` | Warning | Valid long targets can produce generic draft creation failure. |

### Human Verification Required

None. The remaining failures are source-verifiable and testable with automated regressions.

### Gaps Summary

Phase 14 achieved much of the durable draft-only surface: the schema is at head, draft_outcome is persisted and projected, final/API wording no longer claims real execution, external execution tables/events/imports are absent, and the canonical graph node/shim boundaries are wired.

The phase goal is not achieved because "exact approval/snapshot binding" is not actually enforced at the payload boundary, no-approval draft creation is not tied to durable auto-allowed evidence, and the graph node bypasses its own write-tool permission gate. These are not deferred Phase 15/17 items; they are Phase 14 boundary guarantees.

---

_Verified: 2026-06-16T03:02:09Z_  
_Verifier: Claude (gsd-verifier)_
