---
phase: 31
slug: memory-platform-boundary
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-28
---

# Phase 31 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` (`asyncio_mode = "auto"`) |
| Quick run command | `uv run pytest tests/agent/test_session_memory_load.py -q` |
| Full suite command | `uv run pytest tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py tests/memory/test_session_memory_isolation.py tests/memory/test_long_term_memory_repository.py tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py tests/agent/test_memory_write_node.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/tools/test_merchant_scope_static.py -q` |
| Estimated runtime | Unknown; DB-backed groups must run serially because the shared `moca_test` fixture drops/recreates metadata. |

---

## Sampling Rate

- **After every task commit:** run `uv run pytest tests/agent/test_session_memory_load.py -q` plus the nearest test file for touched modules.
- **After every plan wave:** run the full focused suite above, serially.
- **Before `$gsd-verify-work`:** full focused suite must be green, including new Phase 31 tests.
- **Max feedback latency:** Keep per-task checks under the nearest focused pytest command; do not parallelize DB-backed pytest processes with the current shared database fixture.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 1 | APF-09 | T-31-01 | Agent-facing `SessionContextMemory` / `session_context_load_status.v1` exists while legacy `session_memory` remains a compatibility alias. | unit/integration | `uv run pytest tests/agent/test_session_memory_load.py tests/memory/test_session_memory_bundle.py -q` | existing plus W0 additions | pending |
| 31-01-02 | 01 | 1 | APF-10 | T-31-02 | `SessionContextRef` and `ReviewedMemoryRef` carry `authority_class=contextual_only` and cannot satisfy evidence/business/action/replay authority. | unit | `uv run pytest tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py -q` | existing plus W0 additions | pending |
| 31-02-01 | 02 | 2 | APF-10 | T-31-03 | Reviewed long-term/case retrieval fails closed for missing or denied trusted merchant scope. | unit/integration | `uv run pytest tests/tools/test_merchant_scope_static.py tests/memory/test_session_memory_isolation.py -q` plus new Phase 31 retrieval scope tests | existing plus W0 additions | pending |
| 31-02-02 | 02 | 2 | APF-10 | T-31-04 | Merchant A session, long-term, or case memory cannot enter Merchant B prompt context. | integration | `uv run pytest tests/memory/test_session_memory_isolation.py tests/memory/test_case_memory_retrieval.py -q` plus new cross-merchant tests | existing plus W0 additions | pending |
| 31-03-01 | 03 | 2 | APF-10 | T-31-05 | `memory_write_decision.v2`-compatible status records stable decision/status/reason/scope/source/PII/review metadata. | unit/integration | `uv run pytest tests/agent/test_memory_write_node.py tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py -q` | existing plus W0 additions | pending |
| 31-03-02 | 03 | 2 | APF-10 | T-31-06 | PII blocked, tombstoned, deleted, expired, rejected, superseded, and needs_review memory cannot become prompt-facing reviewed context. | unit/integration | `uv run pytest tests/memory/test_long_term_memory_service.py tests/memory/test_case_memory_retrieval.py tests/memory/test_memory_tombstones.py -q` | existing | pending |
| 31-04-01 | 04 | 3 | APF-09, APF-10 | T-31-07 | Audit-ready memory load/retrieve/write status refs are contextual-only handoff metadata, not replay truth. | unit/integration | `uv run pytest tests/agent/test_memory_evidence_boundary.py tests/agent/test_memory_write_node.py -q` plus new status-ref tests | existing plus W0 additions | pending |

---

## Wave 0 Requirements

- [ ] Add or extend tests for `SessionContextMemory`, `SessionContextRef`, and `session_context_load_status.v1` while preserving legacy `session_memory` / `session_memory_bundle` compatibility.
- [ ] Add or extend tests for `ReviewedMemoryRef`, `reviewed_memory_context_retrieve_status.v1`, and structured `memory_context_bundle.long_term_items` / `memory_context_bundle.case_items`.
- [ ] Add cross-merchant negative tests proving merchant A session summaries, prompt-safe tool summaries, long-term memory, and case memory cannot enter merchant B prompt context.
- [ ] Add fail-closed tests for reviewed retrieval when `TrustedContext` is missing, actor merchant scope is missing, merchant scope is denied, case merchant cannot be verified, tenant/global scope is requested without allowlist, memory is deleted/expired/unreviewed, or PII is not prompt-safe.
- [ ] Add `memory_write_decision.v2` projection tests across session write skip/write/error and long-term/case needs_review, write_blocked, tombstone, and supersede paths.
- [ ] Repair or explicitly reclassify `tests/agent/test_memory_evidence_boundary.py::test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority`, currently failing with expected `UNSUPPORTED` vs actual `INSUFFICIENT`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Decide whether reviewed memory retrieval moves after `investigate` in Phase 31 or uses the guarded MVP path before Phase 32. | APF-10 | This is a graph-boundary planning decision that may depend on plan granularity and blast radius. | Inspect the final PLAN files and confirm each reviewed retrieval task either moves graph placement after trusted business lookup or adds explicit trusted-scope fail-closed guards. |

---

## Known RED Items

- `uv run pytest tests/agent/test_memory_evidence_boundary.py::test_agent_runs_memory_context_is_not_policy_business_action_or_replay_authority -q` currently fails because the test expects `VerificationOutcome.UNSUPPORTED` while the verifier returns `VerificationOutcome.INSUFFICIENT`.
- DB-backed pytest groups must not be launched in parallel until test database isolation is changed; current shared `moca_test` setup can race during metadata drop/create.

---

## Validation Sign-Off

- [x] All planned behavior categories map to an automated command or Wave 0 addition.
- [x] Sampling continuity: no 3 consecutive tasks should run without an automated verify command.
- [x] Wave 0 covers all missing target-boundary assertions.
- [x] No watch-mode flags.
- [x] DB-backed checks documented as serial-only.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending
