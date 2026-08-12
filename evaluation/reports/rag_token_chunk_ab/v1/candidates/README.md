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
   descriptor verbatim; it cannot generate a replacement UUID or lease. The
   command commits and durably publishes exact `claimed/v1/index0`, then uses a
   separate transaction to recover/resume and publish exact
   `building/v2/index0`. A crash at either boundary re-enters the same run.
3. If a process exits after a DB commit and before state publication, run
   `recover-state`. It locks only the exact tenant/run, requires one matching
   row plus all current source/evidence authority, and publishes the exact
   current state without mutation or renewal. The one historical Plan 15 shape
   (`building/v2/index0` with only canonical v2 present) may derive only its
   field-identical `claimed/v1/index0` predecessor; no other missing history is
   inferred. Lease or parity expiry refuses before any artifact write.
4. `build-next-reviewed` is production-disabled. Its dispatch returns exit 4
   with `live_provider_execution_disabled` before DB, root, artifact, budget,
   reservation, or provider work. The file-backed per-document ordinal cannot
   serve as globally non-forgeable production authority, even with canonical
   path and no-follow hardening. The internal build algorithm remains available
   only to deterministic tests.
5. `validate-reviewed` is allowed only after every ordered document has
   advanced through the reviewed path.
6. A complete candidate crosses into A-B authority only through
   `eval_rag_token_chunk_ab.py issue-recovery-budget`. That command strict-loads
   this canonical state and descriptor, captures current UTC internally, and
   requires it to be strictly earlier than both immutable expiries before live
   DB/source/evidence proof or manifest publication. `building`, `built`, or
   `validating` candidates cannot mint a recovery budget.

The older `claim`, `resume`, and `validate` subcommands remain compatibility
tools. Legacy `build-next` is also production-disabled with the same stable
refusal. Their outputs cannot satisfy this reviewed descriptor, state, or
budget authority and are not accepted for the future rebuild.

This directory contains contracts only. It does not claim a live candidate,
invoke the provider, mutate the evaluation DB, reserve a Plan 12 A/B slot, or
create selection/activation evidence. Restoring any provider-capable production
build requires a new post-PR rollout phase with a DB-backed unique budget;
there is no CLI flag or environment override. Plans 18–20 and SC-64.4-5/6
remain incomplete.

Build result artifacts retain only allowlisted safe codes, counts, and hashes.
Raw exception text, provider payloads, policy content, credentials, DSNs, and
filesystem paths have no serialized field.
