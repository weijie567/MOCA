# Recovery authorization artifacts

This directory is the canonical repository-owned namespace for
`rag_token_chunk_recovery_authorization.v1` artifacts.

An authorization is published only after `selected_pass`. It is separate from
the immutable `rag_token_chunk_ab.v1` run and `rag_token_chunk_selection.v1`
bytes and binds one canonical recovery-budget manifest, one ordinal
reservation, the exact candidate state, provider parity, terminal run, and
selection file by identity and SHA-256.

Production activation accepts only this repository's canonical
`evaluation/reports/rag_token_chunk_ab/v1` root. Existing authorization bytes
are reconciled only when byte-identical; missing, copied, symlinked, tampered,
or conflicting lineage fails before pointer CAS. Temporary roots are supported
only by deterministic unit-level artifact APIs.
