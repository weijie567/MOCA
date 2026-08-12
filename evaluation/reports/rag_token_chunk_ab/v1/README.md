# RAG token chunk A/B artifacts

`rag_token_chunk_ab.v1` compares the named `CharacterCompatibilityAssembler`
incumbent with the production `PolicyEmbeddingInputAssembler` candidate over
the sealed Phase 64.3 corpus and ordered 45 answerable / 54 total cases.

- `runs/{run_id}.json` is the canonical, create-only terminal owner for every
  `selected_pass`, `candidate_failed`, `unavailable`, or `execution_error` run.
- `runs/{run_id}.md` is a deterministic display-only projection. Rounded
  decimals never feed selection; canonical gates retain raw numerators and
  denominators and use exact rational comparisons.
- `selections/{selection_id}.json` and `.md` exist only for a full-provider
  `selected_pass`. The decision is immutable and contains no activation,
  pointer, cutover, rollback, history, or receipt fields.

Plan 09 retains the same-run internal algorithm and contract tests, but the
production `run-ab` dispatch is now unconditionally disabled. File-backed
attempt budgets cannot provide globally non-forgeable provider authority.
Live-provider execution, any pointer change, the reversible cutover drill, and
the independent hash-chained activation receipt series therefore remain
incomplete and require a new post-PR rollout phase with a DB-backed unique
budget.
The receipt schema, tenant/sequence path, reconciliation behavior, and
DB-commit-before-file order are documented in `activations/README.md`.
Credential-free tests and deterministic providers must never be represented as
final live selection evidence.

The historical invocation shape is retained only as contract context; invoking
it now returns exit 4 with `live_provider_execution_disabled` immediately after
parse/current UTC and before root, manifest, DB, reservation, artifact, or
provider work. There is no CLI flag or environment override:

```text
uv run python scripts/eval_rag_token_chunk_ab.py \
  --candidate-state <create-only-complete-candidate-state.json> \
  --parity-report <create-only-live-parity.json> \
  --probe-fixture-hash sha256:<64-hex> \
  --submitted-content-hash sha256:<64-hex> \
  --run-id <uuid> --selection-id <uuid>
```

The internal test algorithm verifies the sealed Phase64.3 manifest, Gold, baseline identity,
45/54 counts and baseline artifact; rechecks the active character source and
inactive token candidate before and after both roles; and runs each role inside
a root transaction that is always rolled back. Internal nested transactions
still exercise production ingestion/COW/retrieval, while no rollout pointer or
history mutation is committed. Every invocation attempts a create-only run
JSON/Markdown pair. Only a full-provider pass with fresh parity, complete
candidate proofs and all exact gates writes the separate selection pair. None
of those provider-capable operations are production-dispatch reachable in the
current phase; Plans 18–20 and SC-64.4-5/6 remain incomplete.
