---
phase: 14-demo-action-executor-boundary
fixed_at: 2026-06-16T06:43:36Z
review_path: .planning/phases/14-demo-action-executor-boundary/14-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 14: Code Review Fix Report

**Fixed at:** 2026-06-16T06:43:36Z
**Source review:** `.planning/phases/14-demo-action-executor-boundary/14-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 4
- Fixed: 4
- Skipped: 0

## Fixed Issues

### WR-01: Trace Timeline Exposes Draft Idempotency Keys

**Files modified:** `src/repositories/trace_repo.py`, `tests/test_trace_api.py`
**Commit:** 054ff21
**Applied fix:** Removed `idempotency_key` from action draft timeline detail and added a regression using a production-shaped key containing `RF-SECRET`.

### WR-02: `_safe_draft_outcome` Returns Arbitrary JSONB

**Files modified:** `src/repositories/trace_repo.py`, `tests/test_trace_api.py`
**Commit:** 907091f
**Applied fix:** Projected draft outcomes through a `DraftOutcomeV1` allowlist/validation path with safe fallback defaults, plus a regression for unexpected JSONB keys.

### WR-03: Auto-Allowed Routing Depends On A Draft Path The Service Rejects

**Files modified:** `src/agent/graph.py`, `src/agent/nodes/action_draft.py`, `tests/test_graph_routing.py`, `tests/test_execute_action.py`, `tests/agent/test_graph.py`
**Commit:** 70727bf
**Applied fix:** Routed Phase 14 no-approval candidates to `final_response`, removed the risk-route edge to `action_draft`, and made direct `action_draft` calls fail closed without durable auto-allowed binding.

### WR-04: `create_or_get` Is Not Idempotent Under Concurrent Inserts

**Files modified:** `src/repositories/action_draft_repo.py`, `tests/actions/test_action_draft_v2.py`
**Commit:** 282ec94
**Applied fix:** Replaced select-then-insert with PostgreSQL `ON CONFLICT DO NOTHING` followed by a tenant/key re-select and binding check, plus a concurrent exact-key reuse regression.

---

_Fixed: 2026-06-16T06:43:36Z_
_Fixer: Codex (gsd-code-fixer)_
_Iteration: 1_

---

# Phase 14: Code Review Fix Report — Round 2

**Fixed at:** 2026-06-16T07:30:22Z
**Source review:** `.planning/phases/14-demo-action-executor-boundary/14-REVIEW.md` (re-review, deep + Codex cross-review)
**Executor:** Codex (per MOCA AGENTS.md big-change routing) · **Verified:** Claude
**Iteration:** 1 (single pass)

**Summary:**
- Findings in scope: 3 (all Warning)
- Fixed: 3
- Skipped: 0
- Status: all_fixed
- Commits: none yet (working-tree only, awaiting user decision per Git rules)

> Note: Round 2 finding numbers (WR-R2-*) are independent of Round 1's WR-01~WR-04 above; the source re-review reused WR-01/02/03 labels for different issues, renumbered here to avoid collision.

## Fixed Issues

### WR-R2-01: Per-turn reset leaves stale Phase 14 safety bindings

**Files modified:** `src/agent/nodes/receive_request.py`, `tests/agent/test_nodes/test_receive_request.py`
**Applied fix:** Reset block now clears `approval_revision_refs`, `action_payload_hash`, `safety_snapshot_ref`, `safety_snapshot_hash`, `safety_snapshot_verified`, `policy_config_version`, `risk_config_version`, `retrieval_config_version`, `auto_allowed` to `None` (None as unbound sentinel, including the list-typed field). Regression `test_receive_request_clears_phase14_action_bindings` seeds stale bindings and asserts all nine clear.

### WR-R2-02: Successful draft tool result did not fail closed on missing/invalid draft_outcome

**Files modified:** `src/agent/nodes/action_draft.py`, `tests/test_execute_action.py`
**Applied fix:** `_draft_update_from_tool_result` no longer synthesizes a `not_executed_demo` success. Missing/empty/invalid `draft_outcome` on a success result → error result via new `_invalid_draft_outcome_result` (`ToolResultV2` status `invalid_response`, `ToolError(code="INVALID_DRAFT_OUTCOME")`) + error trace status. Reuses existing `DraftOutcomeV1`/`ToolError` contracts. Regressions for missing and invalid outcome assert error + `INVALID_DRAFT_OUTCOME` + no leaked draft fields.

### WR-R2-03: Trace projection masked invalid persisted outcomes as safe demo default

**Files modified:** `src/repositories/trace_repo.py`, `tests/test_trace_api.py`
**Applied fix:** On `ValidationError`, `_safe_draft_outcome` returns `{"status": "invalid_draft_outcome", "external_side_effect": False}` instead of success-semantics `DraftOutcomeV1()`. Claude verified both consumers (`traces.py:66`, `trace_repo.py:119`) embed the dict directly without re-validating, so the out-of-enum status is safe. Regression asserts invalid projection and status ≠ `not_executed_demo`.

## Verification (Claude, independent re-run)

```
uv run pytest tests/agent/test_nodes/test_receive_request.py tests/test_execute_action.py tests/test_trace_api.py -q
36 passed, 1 warning in 12.17s
```

Single warning is a pre-existing `LangChainPendingDeprecationWarning`, unrelated.

## Known limitations

- Only the three findings' minimal relevant tests were run; broader suite / typecheck not run this pass.
- No commit created; working-tree changes await user decision.

---

_Fixed: 2026-06-16T07:30:22Z_
_Executor: Codex · Verified: Claude_
_Iteration: 1_
