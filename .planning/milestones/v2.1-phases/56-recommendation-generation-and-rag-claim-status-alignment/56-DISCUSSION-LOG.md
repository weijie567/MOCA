# Phase 56: Recommendation Generation and RAG Claim Status Alignment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-07
**Phase:** 56-recommendation-generation-and-rag-claim-status-alignment
**Mode:** `--auto`
**Areas discussed:** Active recommendation node cutover, RAG context status semantics, Claim verification gate, Compatibility and docs closeout, Verification shape

---

## Active Recommendation Node Cutover

| Option | Description | Selected |
|--------|-------------|----------|
| Canonical active node with scoped compatibility | Register `recommendation_generation` in the active graph, reuse legacy implementation only through an explicit wrapper/projection if needed. | yes |
| Keep active legacy node | Continue registering `generate_recommendation` and rely on route values/projection only. | no |
| Destructive rename everywhere | Rename every historical mention immediately, including tests/docs that may represent compatibility or history. | no |

**Auto choice:** Canonical active node with scoped compatibility.
**Notes:** This matches CAGM-07 and Phase 50 compatibility policy while avoiding Phase 58 cleanup work.

---

## RAG Context Status Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Finite status vocabulary with fail-closed router matrix | Keep statuses aligned with `VerifiedEvidencePackageV1.status` and make unsafe/missing/unknown states route safely. | yes |
| Existing behavior only | Depend on current package construction without strengthening router/status contract tests. | no |
| Add ad hoc statuses | Add new unplanned literals for special cases. | no |

**Auto choice:** Finite status vocabulary with fail-closed router matrix.
**Notes:** This preserves APF-13 and avoids ambiguous router behavior for stale, conflict, unauthorized, invalid hash, invalid scope, no evidence, and build error states.

---

## Claim Verification Gate

| Option | Description | Selected |
|--------|-------------|----------|
| Hard gate for material/action/user-visible claims | Route all material claims and proposed actions through `claim_verify`; only canonical bundle success can proceed. | yes |
| Let recommendation decide safety | Let generated draft fields or legacy route fields decide whether claims are safe. | no |
| Verify only action drafts | Verify proposed actions but allow answer claims to skip `claim_verify`. | no |

**Auto choice:** Hard gate for material/action/user-visible claims.
**Notes:** This matches APF-14 and CAGM-07. Legacy verifier fields may remain projections but cannot override `claim_verification_bundle`.

---

## Compatibility And Docs Closeout

| Option | Description | Selected |
|--------|-------------|----------|
| Ledgered compatibility until Phase 58 | Keep only necessary import/test/historical trace compatibility with owner, reason, projection, validation, and delete phase. | yes |
| No compatibility | Delete all `generate_recommendation` surfaces immediately. | no |
| Undocumented compatibility | Leave legacy names wherever tests happen to need them. | no |

**Auto choice:** Ledgered compatibility until Phase 58.
**Notes:** Phase 56 should mirror the successful Phase 55 pattern but for generation naming and RAG/claim status alignment.

---

## Verification Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Multiple small plans with focused tests | Split node/wrapper, graph/router, RAG/claim fail-closed, and docs/validation closeout. | yes |
| One large implementation plan | Combine graph cutover, status semantics, compatibility, docs, and final validation in one plan. | no |
| Skip status-specific tests | Rely on broad graph tests and existing APF tests only. | no |

**Auto choice:** Multiple small plans with focused tests.
**Notes:** This follows the MOCA plan granularity rule and keeps Phase 57/58 work out of Phase 56.

---

## the agent's Discretion

- Exact wrapper/module naming.
- Exact low-risk `partial` generation predicate, provided it remains deterministic and action-bound flows fail closed.
- Exact final-response wording for each fail-closed reason.

## Deferred Ideas

- Phase 57: `assess_risk_and_approval -> risk_gate` and risk/approval responsibility split.
- Phase 58: final no-debt deletion of retained compatibility aliases, wrappers, and historical display compatibility.
