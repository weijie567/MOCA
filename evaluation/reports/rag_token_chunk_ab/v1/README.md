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

Plan 09 provides the production-capable same-run command and contract tests.
Plan 10 owns live-provider execution, any pointer change, the reversible
cutover drill, and the independent hash-chained activation receipt series.
Credential-free tests and deterministic providers must never be represented as
final live selection evidence.
