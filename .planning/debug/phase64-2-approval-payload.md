---
status: diagnosed
trigger: "Phase 64.2 UAT gap: high-risk approval integrations expose one approval_id and resume approve/reject/idempotent paths; four exact test nodes fail with KeyError approval_id after Phase 64.2 review fixes. Diagnose production regression versus stale fixture/contract only; do not fix."
created: 2026-08-06T03:46:59Z
updated: 2026-08-06T04:29:10Z
---

## Current Focus

hypothesis: CONFIRMED — `mock_graph` seeds an owner-minted immutable evidence ref but its `Base.metadata.create_all` database has no `EvidenceIdentityRollout` singleton; post-review exact current-evidence validation therefore rejects the candidate before approval routing
test: baseline four-node serial run versus the same four nodes with only a diagnostic valid enabled rollout singleton supplied outside the repository
expecting: confirmed by baseline `4 failed` and counterfactual `4 passed`; production approval serializer/resume path remains healthy
next_action: return diagnose-only root cause; repair should be confined to canonical approval test setup and must not restore legacy evidence fallback

reasoning_checkpoint:
  hypothesis: "The missing canonical-read rollout singleton in the shared approval fixture causes `validate_current_evidence` to fail closed at RAG context, so tests never receive an approval interrupt."
  confirming_evidence:
    - "Full response stops at rag_context_build with `no_evidence`, one rejected candidate, and no approval_gate."
    - "The ordinary fixture DB returns no `EvidenceIdentityRollout(id=1)`."
    - "Supplying only a DB-valid enabled rollout singleton makes all four exact nodes pass end-to-end."
  falsification_test: "If any exact node still lacked `approval_id` after supplying the valid rollout singleton, or if a successful interrupt serializer had a branch omitting the key, this hypothesis would be false."
  fix_rationale: "Align the approval fixture with the exact current-evidence control-plane contract; production fail-closed validation and approval payload code should remain unchanged."
  blind_spots: "No production deployment database was inspected; production correctness is inferred from migration 025 seeding the singleton, migration 026 activating canonical reads, and the repository counterfactual."

## Symptoms

expected: high-risk flow interrupts with exactly one approval payload containing `approval_id`; approve, reject, and idempotent approve resume paths expose one stable approval identity
actual: four high-risk approval integration nodes raise `KeyError: approval_id` while reading the interrupt payload
errors: `KeyError: approval_id` in `tests/integration/test_phase64_1_runtime_safety_matrix.py::test_high_action_uses_latest_decision_context_before_one_approved_draft` and three nodes in `tests/test_approval_integration.py` covering approve, reject, and idempotent approve
reproduction: run the four exact nodes serially with `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`; never use bare pytest or bare python
started: observed after Phase 64.2 review fixes; determine whether this is a production regression or stale fixture/contract

## Eliminated

- hypothesis: successful production approval interrupt payload omits `approval_id`
  evidence: `_create_approval_wait_payload_from_interrupt` unconditionally sets the key after request creation, the failing response never reaches `approval_gate`, and the enabled-rollout counterfactual exposes the key and passes.
  timestamp: 2026-08-06T04:25:30Z

- hypothesis: immutable document/chunk rows or the owner-minted evidence identity in `_seed_approval_policy` are mismatched
  evidence: with only the rollout control-plane precondition supplied, exact current binding validation accepts the same rows/ref and all four tests pass.
  timestamp: 2026-08-06T04:25:30Z

- hypothesis: approve, reject, and idempotent resume production paths independently regressed
  evidence: the baseline failures all occur before their first resume call; all four complete successfully under the same rollout-only counterfactual.
  timestamp: 2026-08-06T04:25:30Z

## Evidence

- timestamp: 2026-08-06T03:50:20Z
  checked: `.planning/STATE.md`, Phase 64.2 UAT, knowledge-base presence, and worktree status
  found: UAT records that all focused Phase 64.2 gates and the pre-review full suite passed, while the post-review full suite newly has four approval-payload `KeyError` failures; no debug knowledge base exists; shared planning artifacts were already modified/untracked before this session.
  implication: this is a differential regression after review fixes, and existing planning artifacts must be preserved; there is no known-pattern diagnosis to assume.

- timestamp: 2026-08-06T03:50:20Z
  checked: common bug pattern map against `KeyError: approval_id`
  found: the symptom matches Data Shape/API Contract (missing required field or changed response shape) and Null/Undefined/Missing Return families; the shared post-review timing also makes stale fixture/data setup a competing hypothesis.
  implication: inspect both producer shape and precondition/fixture validity before attributing the failure to production.

- timestamp: 2026-08-06T03:54:30Z
  checked: both failing test modules and fixture references
  found: the exact approval-integration nodes are approve, reject, and idempotent approve; all four failures post to `/api/v1/agent/chat` with the same query and inject the same `mock_graph`, then index `approval_id` before asserting HTTP/status shape. The high-risk matrix imports Phase 64.2-sensitive evidence payload helpers for its direct-node tests, but its failing chat path also uses `mock_graph`.
  implication: one shared setup/path can explain all four failures; the exception alone does not establish that an interrupted approval payload was actually returned.

- timestamp: 2026-08-06T03:59:10Z
  checked: `mock_graph`, canonical policy seeding, approval gate, and API interrupt serializer
  found: `mock_graph` now seeds a real `PolicyDocumentVersion`/`PolicyChunkVersion`, mints an `EvidenceRefV1` through `EvidenceVersionRepository`, and returns it through the knowledge tool. The approval API's `_create_approval_wait_payload_from_interrupt` unconditionally returns `approval_id` after `ApprovalService.create_request`; there is no interrupted-success branch that omits this key.
  implication: a response missing `approval_id` most likely did not traverse successful approval interrupt handling; observing the actual chat response will distinguish pre-approval fail-closed behavior from an interrupt serializer regression.

- timestamp: 2026-08-06T04:03:50Z
  checked: isolated approve-node reproduction with valid MOCA test entrypoint and full locals
  found: HTTP 200 succeeds but returns `final_status=completed`, nodes stop after `rag_context_build`/`final_response`, and `rag_claim_summary` is `rag_context_status=no_evidence`, `rejected_candidate_count=1`, `verified_evidence_count=0`; `approval_gate` is never executed.
  implication: `KeyError` is a downstream stale assertion symptom, not an approval payload omission. The causative divergence is canonical evidence rejection before recommendation/risk/approval; identify why the shared repository-minted evidence is rejected.

- timestamp: 2026-08-06T04:09:40Z
  checked: review commit `941a9f7`, `validate_current_evidence`, current canonical retrieval, immutable repository, and `_seed_approval_policy`
  found: the review fix replaced compatibility validation with `validate_current_evidence`, which calls `get_current_identities_by_keys`; that repository method first requires the singleton rollout row to have `canonical_reads_enabled=true` and no quarantine. `_seed_approval_policy` creates matching current/immutable document and chunk rows and owner-mints the ref, but never activates canonical reads.
  implication: the leading falsifiable cause is an incomplete/stale integration fixture relative to the post-review current-evidence contract, not a missing field in the approval payload. A canonical-read-only counterfactual can establish causality.

- timestamp: 2026-08-06T04:13:30Z
  checked: mandated serial reproduction of all four exact nodes
  found: all four fail deterministically at their first `wait_payload["approval_id"]` / `chat_payload["data"]["approval_id"]` access; no approve/reject/resume assertion is reached. The isolated full-locals run already showed the common actual shape is completed `no_evidence` before `approval_gate`.
  implication: failures are one shared pre-approval setup regression rather than three independent resume/idempotency regressions.

- timestamp: 2026-08-06T04:15:40Z
  checked: first canonical-read counterfactual setup
  found: `session.get(EvidenceIdentityRollout, 1)` returned `None`; the ordinary shared integration DB fixture has no rollout singleton, rather than merely having the flag disabled.
  implication: `get_current_identities_by_keys` necessarily raises `CanonicalReadUnavailable` before it can compare the correctly minted ref with current heads. The diagnostic counterfactual must supply the missing enabled control-plane row.

- timestamp: 2026-08-06T04:18:10Z
  checked: attempted insertion of an enabled rollout singleton for the counterfactual
  found: PostgreSQL rejected an internally inconsistent diagnostic row because `canonical_reads_enabled=true` requires `dual_write_enabled_at IS NOT NULL`; no product path was exercised in that attempt.
  implication: rerun with the minimum DB-constraint-valid enabled rollout state. This is an experiment-setup correction, not evidence against the missing-rollout hypothesis.

- timestamp: 2026-08-06T04:20:20Z
  checked: isolated approve-node counterfactual with a valid enabled rollout singleton supplied externally
  found: the exact test passes end-to-end (`1 passed`), including interrupt payload extraction, approval decision, resume, and one action draft, without changing repository product/test files.
  implication: the missing rollout control-plane fixture is causally sufficient to explain the failure, while the approval payload/resume production path is healthy under canonical evidence availability.

- timestamp: 2026-08-06T04:25:30Z
  checked: all four exact nodes under the same diagnostic valid enabled-rollout counterfactual
  found: `4 passed, 9 warnings in 16.31s`; the Phase 64.1 high-action decision-context test plus approve, reject, and idempotent approve integration tests all complete.
  implication: root cause is confirmed as stale/incomplete test fixture control-plane state. The Phase 64.2 review fix exposed it but did not regress approval payload or resume behavior.

- timestamp: 2026-08-06T04:25:30Z
  checked: production migration versus ordinary test schema setup
  found: migration 025 inserts `EvidenceIdentityRollout(id=1)` and migration 026 enables canonical reads after staged reconciliation, whereas `tests/conftest.py::test_engine` uses `Base.metadata.create_all`, which creates the table but does not execute migration data seeding; `_seed_approval_policy` adds immutable rows/ref only.
  implication: migrated production state has an explicit control-plane path that the shared integration fixture bypasses. Suggested repair belongs in approval/canonical-evidence test setup, not production validation.

- timestamp: 2026-08-06T04:29:10Z
  checked: process table after all serial PostgreSQL reproductions/counterfactuals
  found: no `pytest`, `uv`, or Python process with a pytest command remains.
  implication: no authorized DB/integration test run was left in the background, so subsequent shared PostgreSQL validation is safe to start serially.

## Resolution

root_cause: `tests/conftest.py::test_engine` builds schema with `Base.metadata.create_all` and therefore does not execute migration 025's rollout-singleton insert. `_seed_approval_policy` was migrated to create current and immutable evidence rows and owner-mint an exact ref, but it omitted the current-read rollout control plane. Review commit `941a9f7` correctly changed `build_verified_context` to `validate_current_evidence`, whose `get_current_identities_by_keys` fails closed when the singleton is missing. The chat therefore returns completed `no_evidence` before `approval_gate`; the tests' `KeyError` mislabels that ordinary response as a malformed approval payload.
fix: not applied (diagnose-only). Suggested direction: add a fixture-local, production-consistent canonical rollout setup for `mock_graph` / `_seed_approval_policy` (prefer a reusable helper that creates the singleton and advances dual-write/current-read state coherently), then retain the exact validator and existing `approval_id` assertions. Do not seed globally in `test_engine` without auditing tests that intentionally create/omit rollout state, and do not restore compatibility fallback.
verification: baseline exact four-node serial run = `4 failed` with `KeyError`; isolated full-locals payload = completed `no_evidence`, one rejected candidate, zero verified evidence, no approval gate; external rollout-only counterfactual = isolated approve `1 passed` and all exact nodes `4 passed`.
files_changed: []
