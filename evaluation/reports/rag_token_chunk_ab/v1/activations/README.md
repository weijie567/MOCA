# RAG token chunk activation receipts

`rag_token_chunk_activation.v1` is the independent, create-only evidence stage
after immutable provider parity and `rag_token_chunk_selection.v1` selection.
It never modifies either upstream artifact.

Each receipt is stored at
`{tenant_id}/{rollout_epoch-as-20-digits}.json`. The database pointer event is
committed first. The receipt command then opens a new session, re-reads the
exact append-only `policy_corpus_activation_history` row and live rollout
pointer, and re-hashes the selection, terminal run, and provider parity files
before using an atomic create-only filesystem link.

The receipt binds the tenant/history sequence, event reason, from/to corpora,
before/after epochs, canonical database-row hash, actor and committed time,
selection file/payload hash, terminal run hash, provider parity hash, candidate
run identity, source manifest, tokenizer configuration, and previous receipt
file hash. The first selected cutover uses `genesis`; rollback and selected
restoration chain to the preceding receipt.

`scripts/reindex_policies.py activate` performs one pointer transaction and
only after that commit creates the corresponding receipt. If the process stops
between those stages, `reconcile-receipts` reconstructs missing bytes
deterministically from committed history. Existing matching bytes are accepted
idempotently. Missing predecessors, mismatched history/pointer/artifacts, or
changed receipt bytes fail closed and are never rewritten.

The nullable database `receipt_hash` column remains untouched: activation
history is protected by the append-only trigger, and the receipt hashes that
committed row rather than creating a circular mutable dependency.
