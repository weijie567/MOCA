---
phase: 08
plan: 08-08
status: complete
started: 2026-06-11T17:30:00Z
completed: 2026-06-11T18:00:00Z
tasks_completed: 3
tasks_total: 3
deviations: WR-01 transient-state-channel approach superseded by 08-09 (checkpoint leak blocker)
---

# 08-08 SUMMARY: Gap Closure — WR-01 policy-text regression + WR-02 citation audit + IN-01 exception scope

## What Changed

Three post-08-07 review findings (08-REVIEW.md) addressed:

1. **WR-01 (policy-text regression)** — Phase 8 switched the recommendation evidence source to hash-only `EvidenceRefV1`, leaving `generate_recommendation` with zero policy substance to ground its output. 08-08 restored bounded policy text via a transient `AgentState.retrieved_evidence_payloads` channel intended never to touch persistence/API/hash/projection. **This approach was subsequently found unsafe and superseded by 08-09** (see Deviations).

2. **WR-02 (citation audit inconsistency)** — Fixed in `generate_recommendation.py`: with a mixed member/non-member citation set where some refs survive, `validate_membership` is now re-run on the surviving refs so the persisted `citation_validation` record matches the emitted `recommended_action`. Previously a run could report `completed` while the audit said citations were invalid (stale pre-drop `is_valid=False`).

3. **IN-01 (exception scope)** — Narrowed the `except (ValidationError, ValueError, TimeoutError, Exception)` tuple at `generate_recommendation.py` and `assess_risk_and_approval.py` to `(ValidationError, ValueError, TimeoutError)`, so programming errors (`KeyError`/`AttributeError`/`TypeError`) propagate instead of being swallowed as transient.

## Key Files Modified

- `src/agent/nodes/generate_recommendation.py` — WR-01 transient channel (later reverted by 08-09); WR-02 re-validation; IN-01 narrowed except
- `src/agent/nodes/assess_risk_and_approval.py` — IN-01 narrowed except
- `src/knowledge/config.py` — bounded policy-text config
- `tests/agent/test_nodes/test_generate_recommendation.py` — WR-01/WR-02 tests
- `tests/agent/test_nodes/test_assess_risk_and_approval.py` — IN-01 test
- `tests/test_agent_runs_api.py` — API evidence output has no `text`

## Deviations

WR-02 and IN-01 landed as planned and remain. **WR-01's transient-state-channel design was a blind spot**: Codex phase-acceptance pass #1 found that `AsyncPostgresSaver` serializes the entire `AgentState` into the Postgres checkpoint after every super-step, so `retrieved_evidence_payloads` (full policy text) persisted between the `retrieve_policy_evidence` and `generate_recommendation` super-steps — violating the hash-only red line (CONTEXT D-B3). This BLOCKER was closed in **08-09** by replacing the channel with in-node re-fetch. See `08-09-SUMMARY.md` and `08-VERIFICATION.md`.

## Test Results

WR-02 / IN-01 tests pass; WR-01 channel later removed in 08-09. Final phase suite after 08-09: 292 passed, 0 failed (recorded in 08-VERIFICATION.md).

## Self-Check: PASSED (with documented deviation)

- [x] All 3 tasks executed
- [x] Committed (combined gap-closure commit d6c2989)
- [x] SUMMARY.md created (retroactive)
- [~] WR-01 approach superseded by 08-09 — deviation documented above
- [x] Phase suite green after 08-09 closure
