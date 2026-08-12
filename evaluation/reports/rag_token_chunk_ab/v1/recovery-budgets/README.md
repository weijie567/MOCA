# RAG token chunk recovery budgets

`rag_token_chunk_recovery_budget.v1` is the fixed, create-only authority for
Phase 64.4 Plan 12 live selection recovery. Its identity is
`phase64.4-plan12-live-selection-recovery`; the maximum is exactly two
provider attempts. The manifest binds the three immutable Plan 10 terminal
run hashes, the unchanged live baseline proof, sealed Phase 64.3 inputs, the
inactive candidate identity, the fresh tokenizer-parity identity, provider
and model identity, and locked `512/384/48` chunk parameters.

Production has one authority namespace only: the checked repository's resolved
`evaluation/reports/rag_token_chunk_ab/v1` root. The CLI rejects alternate,
copied, outside, or symlinked `--output-root` values before loading a candidate
or constructing a provider. Injectable temporary roots remain available only
to unit-level store APIs.

The manifest is written once at the canonical
`recovery-budgets/phase64.4-plan12-live-selection-recovery/manifest.json`. It
also binds the canonical repository-relative Plan 13 state path and exact state
file/descriptor hashes, corpus/run/lease owner/state version/config identity,
source manifest/current corpus/epoch, evidence rollout, and fresh parity
run/file/config/probe/content identity.
Immediately before a provider is constructed, the entry point atomically
re-hashes and strict-loads that exact candidate state plus the fresh parity
report, then publishes `attempts/01.json` or `attempts/02.json` with the new run
and selection UUIDs and candidate-state SHA. The create-only hard-link is the
reservation commit point.
A crash after reservation consumes that ordinal; missing terminal evidence
does not authorize the next ordinal. Concurrent writers get one winner and a
refusal, never two attempts for one ordinal.

The retry matrix is closed:

- `selected_pass`, every `candidate_failed`, every safety failure, and every
  identity or evidence ambiguity stop.
- `execution_error` may authorize ordinal 2 only through a hash-valid,
  manifest-committed Plan 11 bundle whose diagnostic is exactly the
  allowlisted transient provider failure and proves the outer rollback from a
  fresh session. Missing/uncommitted bundles, rollback failure, setup/resource
  proof failures, and unclassified reasons stop for separate review.
- `unavailable` has no diagnostic sidecar. It may authorize ordinal 2 only
  for an allowlisted terminal reason and a different hashed prerequisite
  state. An unchanged prerequisite hash or any sidecar stops.

Reservations and authority decisions contain UUIDs, hashes, ordinals, typed
reason codes, and timestamps only. They never contain raw exceptions,
tracebacks, provider payloads, prompts or policy content, credentials, DSNs,
absolute paths, activation fields, pointer mutations, or history authority.
Plan 10 run/selection identities are explicitly rejected before provider
construction, and no third Plan 12 reservation can be created.
