# RAG token chunk execution diagnostics

`rag_token_chunk_execution_diagnostic.v1` is a strict, create-only sidecar for
`execution_error` A/B runs. It records only the run ID and exact terminal-run
hash; the failing `character_incumbent`, `token_candidate`, or
`shared_preflight` role; an optional format; allowlisted stage/reason and
provider classifications; outer-rollback attempted/proved flags; safe
timestamps, hashes, and counts. Raw exceptions, tracebacks, provider payloads,
prompts or policy content, credentials/DSNs, absolute paths, and
selection/activation/pointer authority are forbidden.

An execution error is readable only through its
`rag_token_chunk_execution_bundle.v1` commit manifest:

- `runs/{run_id}.json` and `.md` retain the byte-compatible
  `rag_token_chunk_ab.v1` terminal run and deterministic projection.
- `diagnostics/{run_id}.json` and `.md` contain the diagnostic sidecar and its
  deterministic projection.
- `commits/{run_id}/manifest.json` binds the exact SHA-256 of all four files and
  is the only reader-visible commit point.

Writers first create and fsync all four canonical files under the unreferenced
`.staging/{run_id}/` directory. They then publish the final files with
create-only links, fsync the containing directories, stage and fsync the
manifest, and atomically rename its one-file commit directory into place.
Crashes before that rename leave an unreadable partial bundle. A retry may
complete only byte-identical staged/final content; any mismatch fails closed
without publishing a manifest. Existing committed bundles are immutable and
idempotently revalidated.

Non-execution outcomes continue to use the existing run publication path.
They never create diagnostics. Diagnostics cannot create a selection, mutate
rollout pointer/history, activate a corpus, or authorize a provider retry; the
separately reviewed Plan 12 budget owns any retry decision.
