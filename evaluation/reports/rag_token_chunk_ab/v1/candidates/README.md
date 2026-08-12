# Reviewed policy candidate recovery artifacts

`policy_reindex_recovery_descriptor.v1` is the create-only authority for one
future inactive candidate. It is sealed before `claim-reviewed` and fixes the
tenant, run token, generation, lease owner and absolute expiry, exact tokenizer
config, fresh parity file/config/probe/content/times, source manifest/current
corpus/epoch, and evidence rollout version. The lease window is at most two
hours and is never renewed by recovery.

The canonical root layout is:

```text
tenants/{tenant_id}/runs/{run_token}/
  descriptor.json
  states/{state_version:08d}.json
  build-budget/manifest.json
  build-budget/documents/{document_index:08d}/attempts/{ordinal:02d}.json
  build-budget/documents/{document_index:08d}/results/{ordinal:02d}.json
```

Every descriptor, state, budget, reservation, and result is canonical JSON.
Writers stage and fsync bytes, atomically publish with a no-replace hard link,
and fsync the parent directory. Descriptor conflicts always refuse. An exact
state replay is idempotent; truncated or different bytes refuse.

## Operator protocol

1. Run `seal-descriptor` with a reviewed artifact root and the retained fresh
   parity report. This is read-only against DB authority and does not claim a
   candidate.
2. Run `claim-reviewed` with that root, tenant, and run token. It consumes the
   descriptor verbatim; it cannot generate a replacement UUID or lease.
3. If a process exits after a DB commit and before state publication, run
   `recover-state`. It locks only the exact tenant/run, requires one matching
   row plus all current source/evidence authority, and publishes the exact
   current state without mutation or renewal.
4. `build-next-reviewed` requires the canonical descriptor, current state, and
   build budget. It reserves a per-document ordinal before constructing
   `EmbeddingService(max_retries=1)`. A crash consumes the ordinal. Ordinal 2
   requires the same DB document/state and an allowlisted safe result from
   ordinal 1. Two ordinals exhaust the document permanently.
5. `validate-reviewed` is allowed only after every ordered document has
   advanced through the reviewed path.

The older `claim`, `resume`, `build-next`, and `validate` subcommands remain
compatibility tools. Their outputs cannot satisfy this reviewed descriptor,
state, or budget authority and are not accepted for the future rebuild.

This directory contains contracts only in Plan 13. It does not claim a live
candidate, invoke the provider, mutate the evaluation DB, reserve a Plan 12 A/B
slot, or create selection/activation evidence. Live work remains owned by the
later reviewed plan.

Build result artifacts retain only allowlisted safe codes, counts, and hashes.
Raw exception text, provider payloads, policy content, credentials, DSNs, and
filesystem paths have no serialized field.
