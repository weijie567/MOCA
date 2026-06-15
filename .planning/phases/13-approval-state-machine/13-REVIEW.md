---
phase: 13-approval-state-machine
reviewed: 2026-06-15T00:00:00Z
depth: deep
files_reviewed: 49
files_reviewed_list:
  - .env.example
  - src/agent/events.py
  - src/agent/graph.py
  - src/agent/nodes/approval_gate.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/execute_action.py
  - src/agent/nodes/final_response.py
  - src/agent/state.py
  - src/api/routers/agent.py
  - src/api/routers/agent_runs.py
  - src/api/routers/approvals.py
  - src/api/schemas/approvals.py
  - src/approvals/__init__.py
  - src/approvals/events.py
  - src/approvals/policy.py
  - src/approvals/repository.py
  - src/approvals/schemas.py
  - src/approvals/service.py
  - src/approvals/sla_scanner.py
  - src/approvals/snapshot_service.py
  - src/approvals/snapshots.py
  - src/common/__init__.py
  - src/common/canonical_hash.py
  - src/config.py
  - src/db/migrations/versions/008_approval_state_machine.py
  - src/db/models.py
  - tests/agent/test_events.py
  - tests/agent/test_graph.py
  - tests/approvals/phase13_eval_manifest.json
  - tests/approvals/test_canonical_hash.py
  - tests/approvals/test_events.py
  - tests/approvals/test_hash_binding.py
  - tests/approvals/test_migration_contract.py
  - tests/approvals/test_multi_level_contract.py
  - tests/approvals/test_needs_info_resume.py
  - tests/approvals/test_service_transitions.py
  - tests/approvals/test_single_level_runtime.py
  - tests/approvals/test_sla_scanner.py
  - tests/approvals/test_snapshots.py
  - tests/architecture/test_approval_boundaries.py
  - tests/test_approval_api.py
  - tests/test_approval_gate.py
  - tests/test_approval_integration.py
  - tests/test_approval_models.py
  - tests/test_execute_action.py
  - tests/test_graph_routing.py
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-06-15
**Depth:** deep
**Files Reviewed:** 49 (45 readable; `.env.example` is blocked by the secrets permission policy and was not read)
**Status:** issues_found

## Summary

Phase 13 implements an executable v2 approval state machine with canonical hashing, immutable action-safety snapshots, optimistic-locked transitions, and LangGraph resume integration. The core security and correctness invariants are well covered:

- **Identity/replay binding is solid.** `ApprovalService.decide` re-asserts request binding, snapshot binding, hash binding, and version/revision expectations under `with_for_update()` row locks (`repository.lock_request` / `lock_current_level` / `lock_assignment`). Both `graph.py::_trusted_approval_result` and `execute_action.py::_trusted_approval_result` independently re-validate tenant/run/hash equality against state before authorizing, so a tampered resume payload cannot authorize execution.
- **Self-approval and role gating** are enforced both at the API layer (`_assert_approval_reviewer`, scope `approvals:review`, `requested_by == user.id` 403) and in the domain (`policy.assert_not_self_approval`, `policy.assert_actor_can_review`) — defense in depth.
- **Snapshot integrity** uses CanonicalHashProfile v1 with forbidden-key rejection (`FORBIDDEN_SNAPSHOT_KEYS`), fixed-millisecond UTC timestamps, and a persist-then-reload verification in `persist_action_safety_snapshot`.
- **Optimistic concurrency**: row locks plus explicit `assert_*_version` checks make concurrent decisions on the same request resolve to `approval_conflict`. The `uq_approval_requests_active_revision` partial unique index and `uq_approval_decisions_winning_accept_level` index enforce single-active-revision and single-winning-accept at the DB level.
- The graph resume thread id (`_graph_thread_id` = `{tenant}:{requested_by}:{thread}`) correctly reconstructs the *requester's* checkpoint thread, not the approver's, matching `_checkpoint_thread_id`.
- The SLA scanner is correctly feature-gated off (`approval_sla_scanner_enabled=False`) and deferred to Phase 15.

The full reviewed test subset (`tests/approvals`, `tests/test_graph_routing.py`, `tests/agent/test_graph.py`, `tests/architecture/test_approval_boundaries.py`) passes: **165 passed** (verified via `.venv/bin/python -m pytest`).

No Critical issues were found. The Warnings concern cross-transaction consistency between the approval decision and the LangGraph checkpointer, exception-mapping precision, a dropped `reason` field, and a latent legacy-request gap in the (currently disabled) SLA path. Info items are maintainability notes.

## Warnings

### WR-01: Graph resume checkpoint and approval decision are not in the same transaction

**File:** `src/api/routers/approvals.py:75-87`, `src/api/main.py:31-34`
**Issue:** `decide_approval` calls `_resume_graph_after_decision` (which runs `graph.ainvoke(Command(resume=...))`) *before* `await session.commit()`. The LangGraph checkpointer is built at startup from a **separate** connection (`AsyncPostgresSaver.from_conn_string(settings.checkpointer_database_url)`), so checkpoint writes during the resume are committed on their own connection, independent of the request `session` transaction that holds the approval decision and the action drafts created by `execute_action` (which uses `config["configurable"]["session"]`, i.e. the request session).

If `session.commit()` at line 82 fails (or the request is rolled back) after a successful resume, the checkpoint has already advanced past the `approval_gate` interrupt while the approval `decided`/version rows and the action draft roll back. A subsequent decide/resume attempt would find the checkpoint already past the interrupt, leaving graph state and approval state inconsistent (graph "executed" an approval that no longer exists in the DB).
**Fix:** Make failure semantics explicit and recoverable. Either (a) commit the approval decision before resuming and treat the resume as a separate, idempotent step keyed on `approval_id`/`revision` so a failed resume can be retried without re-deciding, or (b) detect a checkpoint-advance-without-committed-decision and reconcile. At minimum add a regression test for "resume succeeds, outer commit fails". This is partly inherent to LangGraph's separate checkpointer, so the goal is explicit recoverable handling rather than silent divergence.

### WR-02: Broad `ValidationError` catch in `decide`/`attach_info` can mask result-projection failures as `approval_not_executable`

**File:** `src/approvals/service.py:230-231`, `281-282`, `746-770`
**Issue:** `decide` and `attach_info` wrap the whole body in `except (ActionSafetySnapshotPersistenceError, CanonicalHashError, ValidationError)` → `approval_not_executable`. `_result` constructs `TrustedApprovalResultV1(...)` at the end of an otherwise-successful transition (after versions were incremented and the decision row inserted). If that construction raises `ValidationError`, it is mapped to `approval_not_executable` and the savepoint rolls back — safe, but the surfaced code is misleading (the request *was* executable; the result projection failed), masking a genuine result-schema regression behind a generic 409.
**Fix:** Narrow the `ValidationError` catch to the snapshot/binding sections, or catch result-construction errors separately and raise `approval_invalid_result` (already used at line 770 for the schema_version guard) so projection failures are not conflated with executability failures.

### WR-03: Reviewer `reason` is never persisted on `ApprovalRequest` and is always `null` in the API response

**File:** `src/approvals/service.py:725-746` (`_result`), `src/api/routers/approvals.py:256` (`_to_response`), `src/db/models.py:346`
**Issue:** `_result` sets `request.decision`, `request.decided_by`, and `request.decided_at`, but never sets `request.reason`. The reason is only written to the `ApprovalDecision.reason` audit row (`repository.insert_decision`). `ApprovalResponse.reason` is populated from `approval.reason` (the request column), so a reviewer's reject/approve reason is always returned as `null` to clients even when supplied. The existing API test (`tests/test_approval_api.py:425`) passes a reason but does not assert it in the response, so this gap is uncaught.
**Fix:** In `_result`, set `request.reason = reason` alongside the other decision fields (or have `_to_response` read it from the latest decision row / transition result). Add a test asserting `payload["data"]["reason"]` round-trips after a reject.

### WR-04: SLA scanner and `expire_due_request` do not exclude legacy/non-executable requests

**File:** `src/approvals/sla_scanner.py:48-57`, `src/approvals/service.py:284-310`
**Issue:** `ApprovalSlaScanner.scan` selects all `status == "pending"` rows with `expires_at <= now` without filtering `legacy_non_executable IS FALSE` or `schema_version == "approval_request.v2"`, and `expire_due_request` only checks status/expiry. A legacy (`approval_request.v1`, non-executable) pending row migrated by `008` could therefore be transitioned to `expired` and emit `approval_expired` events through the executable v2 event path, even though every other transition guards executability via `_assert_executable_request`. The scanner is feature-disabled in Phase 13, so this is not reachable in production today, but it is a latent gap to close before Phase 15 enables the scanner.
**Fix:** Add `ApprovalRequest.legacy_non_executable.is_(False)` and `schema_version == "approval_request.v2"` to the scanner query (mirroring `list_pending_requests`), and/or assert executability inside `expire_due_request` before transitioning.

## Info

### IN-01: `attach_approval_info` instantiates `ApprovalService` three times in one request

**File:** `src/api/routers/approvals.py:116,120`
**Issue:** `attach_info` and `get_request` are each invoked on a freshly constructed `ApprovalService(session)`. Correct (same session/transaction) but wasteful and obscures intent.
**Fix:** Build one `service = ApprovalService(session)` and reuse it, as `decide_approval` does.

### IN-02: `_respond` reassigns an already-set `clarification_request_id`

**File:** `src/approvals/service.py:394,405`
**Issue:** `clarification_request_id = request.clarification_request_id or f"approval-clarify:{uuid4()}"` then unconditionally reassigns `request.clarification_request_id`. Harmless given `_assert_pending_request` blocks a second `respond`, but the reuse-vs-new intent is unclear.
**Fix:** Assign only when generating a new id, or add a clarifying comment.

### IN-03: `_to_response` mixes `result` and `approval` sources with nested `getattr`/`or` logic

**File:** `src/api/routers/approvals.py:244-250`
**Issue:** The `superseded_by_request_id` expression chains `getattr(result, ..., None) or approval.superseded_by_request_id` twice inside a conditional; `new_action_payload_hash` and `resume_route` use similar defensive `getattr`/`or {}`. Hard to read and easy to break.
**Fix:** Extract a helper that resolves each field from `result` first, falling back to `approval`, with explicit branches.

### IN-04: `assess_risk_and_approval` recomputes `_retrieval_config_version(evidence_refs)` multiple times per branch

**File:** `src/agent/nodes/assess_risk_and_approval.py:301-319,336,368-370`
**Issue:** `_retrieval_config_version(evidence_refs)` is recomputed several times when building the result dict. Pure function, so correct, just duplicated. (Performance is out of v1 scope; flagged as a readability nit only.)
**Fix:** Compute once into a local and reuse.

### IN-05: Edit resume payload carries the superseded request's bindings plus `new_action_payload_hash` — subtle and undocumented

**File:** `src/agent/graph.py:68-87`, `src/approvals/service.py:536-549`
**Issue:** On `edit`, `_result` returns the *old* (superseded) request's `action_payload_hash`/`safety_snapshot_*` in `resume_payload`, while `new_action_payload_hash` carries the new request's hash. `route_after_approval` requires `result.new_action_payload_hash` and routes to `assess_risk_and_approval` to rebuild bindings; the edit path is not auto-resumed by the API (`_should_resume_graph` excludes `edit`). This is internally consistent and correct, but the dual-hash contract is subtle.
**Fix:** Add an inline comment in `_edit`/`route_after_approval` documenting that the resume payload intentionally carries old-request bindings plus `new_action_payload_hash`, and that edit must re-run `assess_risk_and_approval` rather than `execute_action`, so a future change does not start trusting the old hashes for execution.

---

_Reviewed: 2026-06-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
