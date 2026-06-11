---
phase: 08-knowledge-facade
verified: 2026-06-11T19:00:00Z
status: complete
score: 5/6 must-haves verified (1 explicitly deferred)
overrides_applied: 0
gaps:
  - truth: "Tenant-over-global policy precedence is enforced"
    status: deferred
    reason: "CONTEXT.md D-D1 explicitly defers tenant-over-global to a later policy-scope phase. REQUIREMENTS.md KNOW-02 mentions it but the CONTEXT deferral takes precedence for Phase 8 exit scope. No roadmap phase currently owns this; it should be assigned when a policy-scope phase is planned."
    artifacts:
      - path: "src/knowledge/service.py"
        issue: "Docstring records a deferral rather than implemented tenant-over-global precedence."
      - path: "src/repositories/policy_chunk_repo.py"
        issue: "Query requires PolicyDocument.tenant_id == tenant_id and has no global/default fallback path."
    missing:
      - "Assign a concrete roadmap phase to own tenant-over-global with schema-and-query acceptance gate."
---

# Phase 8: Knowledge Facade Verification Report

**Phase Goal:** Route policy evidence retrieval through KnowledgeService with canonical EvidenceRefV1, citation validation, effective-time, and tenant-over-global behavior.
**Verified:** 2026-06-11T19:00:00Z
**Status:** complete (1 explicitly deferred item: tenant-over-global, CONTEXT D-D1)
**Re-verification:** Yes — after 08-07 + 08-08 + 08-09 gap closure (two independent Codex acceptance passes)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Knowledge reads use `PolicyKnowledgeService` while the legacy RAG path remains available as adapter/rollback fallback | VERIFIED | `retrieve_policy_evidence.py:125-126` calls the facade; `adapters.py:9,28` retains `legacy_search_policy`; direct cutover/rollback is documented. |
| 2 | Canonical EvidenceRefV1, projection, version pin, evidence-ID membership, state, and reporting contracts are wired end to end | VERIFIED | `schemas.py`, `text_hash.py`, `citation.py`, ingestion version bump, node/state merge by `evidence_id`, and v2 reporting consumers pass. |
| 3 | Strong/partial/no-evidence behavior honors the public request contract | VERIFIED | `service.py:55` — `allow_partial_evidence=False` now returns `no_evidence` with empty refs. `test_partial_evidence_suppressed_when_disallowed` passes. |
| 4 | Effective-time filtering reliably returns valid in-effect evidence | VERIFIED | `policy_chunk_repo.py:69-70` — `effective_date` SQL WHERE applied before ORDER BY/LIMIT. `adapters.py:92` passes `effective_date` to repo. `test_effective_date_passed_to_repository` passes. |
| 5 | Tenant-over-global precedence is enforced | DEFERRED | Only tenant-scoped retrieval exists. CONTEXT.md D-D1 explicitly defers to a later policy-scope phase. No roadmap phase currently owns this. |
| 6 | Migration/cutover is safely reversible without an unowned persistence/read-switch | VERIFIED | Service-only direct cutover; no new persistence/read-switch; retained adapter and git-revert rollback are documented. |

**Score:** 5/6 truths verified (1 deferred with explicit disposition)

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 08 focused suites | `uv run pytest tests/knowledge ... tests/test_agent_runs_api.py -q` | 39 knowledge + all others passed | PASS |
| Full regression suite | `uv run pytest -q --tb=short` | 277 passed | PASS |
| Reject partial evidence when disallowed | `test_partial_evidence_suppressed_when_disallowed` | Returns `no_evidence` with empty refs | PASS |
| Effective filter before repository LIMIT | `test_effective_date_passed_to_repository` | `effective_date` passed to `search_similar()` | PASS |

### Gap Closure Summary (08-07)

| Gap | Original Status | After 08-07 | Fix |
|-----|----------------|-------------|-----|
| `allow_partial_evidence=False` ignored | FAILED | VERIFIED | `service.py` — flag checked before building result |
| Effective-time after LIMIT | FAILED | VERIFIED | `policy_chunk_repo.py` — SQL WHERE before ORDER BY/LIMIT |
| Tenant-over-global unimplemented | FAILED | DEFERRED | No code change; CONTEXT.md D-D1 defers |

### Gap Closure Summary (08-08 + 08-09)

A fresh code review (08-REVIEW.md, post-08-07) plus Claude adjudication and Codex cross-verification surfaced three more findings; 08-08 fixed two and re-introduced one blocker that 08-09 closed.

| Finding | Origin | Status | Fix |
|---------|--------|--------|-----|
| WR-01 recommendation node receives no policy text (regression vs pre-Phase-8) | review + git `b9050db1~1` | VERIFIED | 08-09: `generate_recommendation` re-fetches chunk content in-node, hash-verified, fail-closed; text never enters AgentState |
| WR-02 mixed-citation audit inconsistency (`completed` while `is_valid=False`) | review + trace.py | VERIFIED | 08-08: re-run `validate_membership` on surviving refs so audit matches `recommended_action` |
| IN-01 over-broad `except (..., Exception)` swallows programming errors | review | VERIFIED | 08-08: narrowed to `(ValidationError, ValueError, TimeoutError)` at both named sites |
| **BLOCKER**: 08-08 transient `AgentState.retrieved_evidence_payloads` leaks policy text into Postgres checkpoint | Codex acceptance pass #1 | RESOLVED | 08-09: transient state channel fully reverted; in-node re-fetch keeps text in node-local scope + prompt only |

**08-09 red-line design:** `AsyncPostgresSaver` (graph.py:97) serializes the entire AgentState per super-step, so any state field carrying text would persist. 08-09 removes the channel entirely — `generate_recommendation` re-reads content via `PolicyChunkRepository.get_contents_by_evidence_keys(tenant_id, keys)` (single batched query, tenant + (doc_key, chunk_id) scoped), verifies `evidence_text_hash(content) == ref.text_hash` (drift guard), and fails closed on missing/duplicate/cross-tenant/hash-mismatch. Policy text lives only in node-local variables and the LLM prompt string; it is never written to any returned state field.

**Two independent Codex acceptance passes:** pass #1 → INCOMPLETE (checkpoint blocker); pass #2 (after 08-09) → COMPLETE. Full suite: 292 passed, 0 failed.

Non-blocking follow-ups (not Phase 8 exit blockers):
- `generate_recommendation.py:155` emits an `AsyncMock ... never awaited` RuntimeWarning under `test_graph.py` — a test-mock artifact (graph tests use `MagicMock`, not `AsyncMock`, for the session, exercising the fail-closed degrade path), not a product defect. Test-hygiene cleanup.

### Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|---|---|---|---|
| KNOW-01 | 08-02, 08-04, 08-05, 08-07, 08-08 | SATISFIED | Facade, statuses, `allow_partial_evidence` enforcement, and policy-grounded recommendation (in-node text) pass. |
| KNOW-02 | 08-01 through 08-09 | PARTIAL | EvidenceRefV1/citation/projection/effective-time/citation-audit pass. Tenant-over-global deferred (CONTEXT D-D1). |
| KNOW-03 | 08-04, 08-05, 08-09 | SATISFIED | No persistence/read-switch; policy text stays out of checkpoint via in-node re-fetch; git-revert/adapter rollback. |

### Disposition: Tenant-over-global

CONTEXT.md D-D1: "Global-policy / tenant-over-global behavior is non-MVP and DEFERRED_WITH_OWNER to a later policy-scope phase with a schema-and-query acceptance gate; it is not a Phase 8 blocking exit."

Resolution: Phase 8 exit scope covers tenant-scoped behavior only. Tenant-over-global requires a future phase with schema migration. No roadmap phase currently owns this — it should be assigned when a policy-scope phase is planned.

---

_Verified: 2026-06-11T19:00:00Z_
_Verifier: Claude (adjudicator) + Codex (two independent acceptance passes)_
_Re-verification after 08-07 + 08-08 + 08-09 gap closure — PHASE COMPLETE_
