# Embedding tokenizer parity v1

`check_embedding_tokenizer_parity.py` writes one strict `embedding_tokenizer_parity.v1` JSON artifact per provider attempt:

```text
evaluation/reports/rag_embedding_tokenizer/v1/
└── runs/
    └── <configuration-sha256>/
        └── <run-uuid>.json
```

The final path is created with atomic create-only semantics. A prior run is never overwritten. Reports contain only allowlisted configuration identity, timestamps, region class, safe probe labels, exact-input hashes, offline/request-level counts, aggregate counts, and `passed | quarantined | unavailable` status. They never contain probe text, policy text, credentials, URLs, raw provider responses, filesystem paths, or exception details.

## Execution

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/check_embedding_tokenizer_parity.py
```

The command accepts only the structured safe-probe fixture, output root, and optional run UUID. It does not accept final strings. It builds synthetic `ParsedBlock` objects and submits only `PolicyEmbeddingInputAssembler.embedding_input` values: ten one-input requests followed by one ten-input aggregate request.

- `passed`: all ten request-level `prompt_tokens` exactly equal their offline final-input counts, and the aggregate request `prompt_tokens` exactly equals the offline sum. Request-level `total_tokens` is retained truthfully but is not reinterpreted as tokenizer accounting.
- `quarantined`: any reported single or aggregate count differs.
- `unavailable`: credentials, provider service, or complete request-level usage is unavailable. This is not a pass or a quality failure.

Selection callers must use `require_fresh_provider_parity` with the exact tokenizer configuration fingerprint, provider/model/dimensions, probe-fixture hash, submitted-content hash, and maximum age. Offline tests intentionally do not mock or fabricate a successful provider run; a real `passed` artifact is produced only by the live command.
