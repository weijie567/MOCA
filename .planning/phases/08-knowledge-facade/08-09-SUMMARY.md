---
phase: 08
plan: 08-09
status: complete
started: 2026-06-11T18:00:00Z
completed: 2026-06-11T18:45:00Z
tasks_completed: 3
tasks_total: 3
deviations: none
---

# 08-09 SUMMARY: WR-01 red-line fix — fetch policy text in-node, never through AgentState/checkpoint

## What Changed

Closed the BLOCKER that 08-08's WR-01 fix introduced. 08-08 carried policy text through `AgentState.retrieved_evidence_payloads`; because the graph compiles with `AsyncPostgresSaver` (graph.py:97), LangGraph serializes the entire `AgentState` into the Postgres checkpoint after every super-step, persisting full policy text between the `retrieve_policy_evidence` and `generate_recommendation` super-steps. `Field(exclude=True)` only strips `model_dump()`; it cannot stop a state channel from being checkpointed. This violated the hash-only red line (CONTEXT D-B3).

The fix replaces the transient-state channel with **in-node re-fetch**:

1. **Removed the transient channel** — `AgentState.retrieved_evidence_payloads` and the `RetrievedEvidencePayload` type fully reverted; `rg "RetrievedEvidencePayload|retrieved_evidence_payloads" src tests` returns no matches.

2. **In-node content re-fetch** — `generate_recommendation` re-reads chunk content at prompt-build time via `PolicyChunkRepository.get_contents_by_evidence_keys(tenant_id, keys)` (single batched query, tenant + `(doc_key, chunk_id)` scoped) using the canonical `evidence_refs` already in state. Content is verified with `evidence_text_hash(content) == ref.text_hash` (drift guard) and **fails closed** on missing / duplicate / cross-tenant / hash-mismatch. Policy text lives only in node-local variables and the LLM prompt string — never in AgentState, checkpoint, trace, audit, or `EvidenceRefV1`.

3. **Tests updated** — removed-channel tests replaced; added checkpoint-leak proof asserting no AgentState field / serialized state dump carries policy text after the two nodes run.

## Key Files Modified

- `src/agent/nodes/generate_recommendation.py` — in-node hash-verified re-fetch, fail-closed
- `src/repositories/policy_chunk_repo.py` — `get_contents_by_evidence_keys` batched, tenant+key scoped
- `src/agent/state.py` — transient channel removed
- `tests/agent/test_nodes/test_generate_recommendation.py` — re-fetch + fail-closed + leak-proof tests
- `tests/repositories/test_policy_chunk_repo.py` — batched-fetch repo tests
- `tests/knowledge/test_evidence_projection.py` — projection unchanged, no text

## Test Results

- Full suite — 292 passed, 0 failed (2 independent Codex acceptance passes: pass #1 INCOMPLETE on the 08-08 checkpoint blocker, pass #2 COMPLETE after this fix).
- Non-blocking: `generate_recommendation.py:155` emits an `AsyncMock never awaited` RuntimeWarning under `test_graph.py` — test-mock artifact, not a product defect (test-hygiene follow-up).

## Self-Check: PASSED

- [x] All 3 tasks executed
- [x] Committed (combined gap-closure commit d6c2989)
- [x] SUMMARY.md created (retroactive)
- [x] No deviations from plan
- [x] Full suite green; checkpoint leak proof passes; Phase 8 verified COMPLETE
