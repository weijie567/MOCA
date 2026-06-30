---
phase: 31
slug: memory-platform-boundary
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-28
updated: 2026-06-28T11:48:05Z
validated: 2026-06-28T11:48:05Z
---

# Phase 31 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` (`asyncio_mode = "auto"`) |
| Quick run command | `uv run pytest tests/memory/test_context_refs.py tests/agent/test_session_memory_load.py tests/agent/test_nodes/test_receive_request.py -q` |
| Full suite command | `uv run pytest tests/memory/test_context_refs.py tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py tests/memory/test_session_memory_isolation.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_memory_write_node.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_material_claims.py tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py tests/memory/test_memory_tombstones.py tests/tools/test_merchant_scope_static.py -q` |
| Estimated runtime | Unknown; DB-backed groups must run serially because the shared `moca_test` fixture drops/recreates metadata. |

---

## Sampling Rate

- **After every task commit:** run `uv run pytest tests/memory/test_context_refs.py tests/agent/test_session_memory_load.py tests/agent/test_nodes/test_receive_request.py -q` plus the nearest test file for touched modules.
- **After every plan wave:** run the full focused suite above, serially.
- **Before `$gsd-verify-work`:** full focused suite must be green, including new Phase 31 tests.
- **Max feedback latency:** Keep per-task checks under the nearest focused pytest command; do not parallelize DB-backed pytest processes with the current shared database fixture.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 31-01 | 0 | APF-09, APF-10 | T-31-authority-forgery | RED tests pin `SessionContextRef`, `ReviewedMemoryRef`, `SessionContextLoadStatusV1`, `ReviewedMemoryContextRetrieveStatusV1`, `ReviewedMemoryContextBundle`, and `MemoryWriteDecisionV2` with complete D-25 fields and `authority_class=contextual_only`. | unit/integration RED | `bash -lc 'set +e; uv run pytest tests/memory/test_context_refs.py tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py -q; status=$?; test "$status" -ne 0'` | existing plus W0 additions | green |
| 31-01-02 | 31-01 | 0 | APF-10 | T-31-authority-forgery | Known memory-authority outcome drift is repaired/reclassified and contextual-only refs/status refs are rejected as evidence/business/approval/action/replay authority. | unit RED/repair | `uv run pytest tests/agent/test_memory_evidence_boundary.py::test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority -q` plus RED full-file command | existing plus W0 additions | green |
| 31-02-01 | 31-02 | 0 | APF-10 | T-31-cross-merchant | RED tests pin fail-closed reviewed retrieval and prove merchant A session slots, rolling summaries, recent messages, tool summaries, long-term memory, and case memory cannot enter merchant B prompt context. | unit/integration RED | `bash -lc 'set +e; uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_session_memory_isolation.py -q; status=$?; test "$status" -ne 0'` | existing plus W0 additions | green |
| 31-02-02 | 31-02 | 0 | APF-10 | T-31-write-rollback | RED tests pin `memory_write_decision.v2` status metadata, timeout/no-rollback behavior, PII block, needs_review, tombstone, and supersede lifecycle outcomes. | unit/integration RED | `bash -lc 'set +e; uv run pytest tests/agent/test_memory_write_node.py tests/memory/test_reviewed_memory_context_boundary.py -q; status=$?; test "$status" -ne 0'` | existing plus W0 additions | green |
| 31-03-01 | 31-03 | 1 | APF-09, APF-10 | T-31-authority-forgery | Strict memory DTOs include complete D-25 identity/status/ref/count/fallback fields and do not import authority DTOs. | unit/integration | `uv run pytest tests/memory/test_context_refs.py tests/agent/test_memory_evidence_boundary.py -q` | planned `src/memory/context_refs.py` | green |
| 31-03-02 | 31-03 | 1 | APF-09, APF-10 | T-31-pii-leakage | `SessionContextMemory` projection and `MemoryContextService` facade exist without persistence renames or direct repository ownership. | unit/integration | `uv run pytest tests/memory/test_context_refs.py tests/memory/test_session_memory_bundle.py -q` | planned facade/projection files | green |
| 31-04-01 | 31-04 | 2 | APF-09, APF-10 | T-31-replay-confusion | `AgentState` and `receive_request` reset `session_context`, `session_context_bundle`, `session_context_load_status`, `memory_context`, `memory_context_bundle`, and `reviewed_memory_context_retrieve_status` every turn. | unit | `uv run pytest tests/agent/test_nodes/test_receive_request.py -q` | existing plus implementation additions | green |
| 31-04-02 | 31-04 | 2 | APF-09, APF-10 | T-31-cross-merchant | `session_context_load` returns target/legacy fields together and filters merchant A session slots/summaries/messages/tool summaries from merchant B prompt context. | unit/integration | `uv run pytest tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py tests/memory/test_session_memory_isolation.py tests/agent/test_empty_session_adapter.py -q` | planned `session_context_load.py` | green |
| 31-05-01 | 31-05 | 3 | APF-10 | T-31-cross-merchant | `MemoryContextService.load_reviewed_memory_context` consumes trusted scope, fails closed for missing/denied/unverified scope, and returns contextual-only reviewed bundles. | unit/integration | `uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_reviewed_memory_context_boundary.py -q` | existing plus implementation additions | green |
| 31-05-02 | 31-05 | 3 | APF-10 | T-31-pii-leakage | `reviewed_memory_context_retrieve` returns `memory_context`, optional `memory_context_bundle`, `reviewed_memory_context_retrieve_status`, and legacy aliases from one guarded output. | unit/integration | `uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_graph.py::test_long_term_memory_reviewed_retrieval_safe_empty_when_no_reviewed_rows tests/agent/test_graph.py::test_long_term_memory_reviewed_retrieval_safe_empty_when_unavailable tests/agent/test_graph.py::test_long_term_memory_reviewed_snippets_flow_into_graph_state -q` | planned target node | green |
| 31-06-01 | 31-06 | 4 | APF-10 | T-31-write-rollback | `memory_write` emits `memory_write_decision.v2` on write/skip/error/timeout paths while preserving final response and legacy `memory_write_result`. | unit/integration | `uv run pytest tests/agent/test_memory_write_node.py tests/memory/test_reviewed_memory_context_boundary.py -q` | existing plus implementation additions | green |
| 31-06-02 | 31-06 | 4 | APF-10 | T-31-authority-forgery | Verifier rejects contextual-only memory refs/status refs as policy/business/action/material-claim/replay authority. | unit | `uv run pytest tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_material_claims.py -q` | existing plus verifier additions | green |
| 31-06-03 | 31-06 | 4 | APF-09, APF-10 | T-31-cross-merchant, T-31-authority-forgery, T-31-pii-leakage, T-31-tombstone-revival, T-31-write-rollback | Final focused Phase 31 suite covers all new contract, reset, scope, write, authority, and lifecycle tests serially. | final serial | `uv run pytest tests/memory/test_context_refs.py tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py tests/memory/test_session_memory_isolation.py tests/agent/test_nodes/test_receive_request.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_memory_write_node.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_material_claims.py tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py tests/memory/test_memory_tombstones.py tests/tools/test_merchant_scope_static.py -q` and `git diff --check` | all planned files | green |

---

## Wave 0 Requirements

- [x] Add or extend tests for `SessionContextMemory`, `SessionContextRef`, and `session_context_load_status.v1` while preserving legacy `session_memory` / `session_memory_bundle` compatibility.
- [x] Add or extend tests for `ReviewedMemoryRef`, `reviewed_memory_context_retrieve_status.v1`, and structured `memory_context_bundle.long_term_items` / `memory_context_bundle.case_items`.
- [x] Add cross-merchant negative tests proving merchant A active session slots, rolling summaries, recent messages, prompt-safe tool summaries, long-term memory, and case memory cannot enter merchant B prompt context.
- [x] Add fail-closed tests for reviewed retrieval when `TrustedContext` is missing, actor merchant scope is missing, merchant scope is denied, case merchant cannot be verified, tenant/global scope is requested without allowlist, memory is deleted/expired/unreviewed, or PII is not prompt-safe.
- [x] Add `memory_write_decision.v2` projection tests across session write skip/write/error and long-term/case needs_review, write_blocked, tombstone, and supersede paths.
- [x] Repair or explicitly reclassify `tests/agent/test_memory_evidence_boundary.py::test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority`, formerly failing with expected `UNSUPPORTED` vs actual `INSUFFICIENT`.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Known RED Items

None. Former `UNSUPPORTED` vs `INSUFFICIENT` item is reclassified and covered by automated tests. DB-backed tests remain serial-only infrastructure guidance, not a RED item.

## Validation Audit 2026-06-28T11:48:05Z

| Metric | Count |
|--------|-------|
| Apparent gaps audited | 5 |
| Real coverage gaps found | 0 |
| Tests added | 0 |
| Escalated | 0 |

---

## Validation Sign-Off

- [x] All planned behavior categories map to an automated command or Wave 0 addition.
- [x] Sampling continuity: no 3 consecutive tasks should run without an automated verify command.
- [x] Wave 0 covers all missing target-boundary assertions.
- [x] No watch-mode flags.
- [x] DB-backed checks documented as serial-only.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-28T11:48:05Z
