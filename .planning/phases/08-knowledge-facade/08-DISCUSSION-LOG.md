# Phase 8: Knowledge Facade - Discussion Log

Do not use as input to planning/research/execution agents; decisions are in CONTEXT.md

**Date:** 2026-06-06
**Phase:** 8-knowledge-facade
**Areas discussed:** Facade Boundary; EvidenceRefV1 Schema & State Migration; Citation Claim-Support; Tenant-over-Global/Effective-Time/Owner Gate

## Area Selection Preamble

| Option | Description | Selected |
|---|---|---|
| A only | Discuss facade boundary and module placement only. | |
| A/B/C/D | Discuss all four locked decision areas. | ✓ |
| Defer discussion | Leave Phase 8 context ungathered. | |

**User's choice:** Discuss A/B/C/D areas.

**Notes:** The discussion covered the complete Phase 8 boundary needed for planning while preserving all stated non-scope.

## A1 — Facade Package Placement

| Option | Description | Selected |
|---|---|---|
| New `src/knowledge/` package | Add facade, schemas, and adapter modules; keep and wrap `src/rag/*`. | ✓ |
| Put facade in `src/rag/` | Extend the legacy retrieval package directly. | |
| Put facade in `src/contracts/` | Introduce a neutral cross-domain contract package now. | |

**User's choice:** Create the KnowledgeService facade in a new `src/knowledge/` package.

**Notes:** The package is symmetric with Phase 9's `src/business_tools/`; old `src/rag/*` remains in place behind an adapter.

## A2 — Trusted Context Type

| Option | Description | Selected |
|---|---|---|
| New KnowledgeContext | Use `tenant_id`, `user_id`, `role`, `run_id`, and `effective_at`. | ✓ |
| Phase 9 ToolCallContext | Depend on unimplemented tool_context.v2. | |
| No context object | Pass individual values or use adapter-local defaults. | |

**User's choice:** Define and use a lightweight KnowledgeContext.

**Notes:** ToolCallContext is Phase 9-owned and Phase 8 depends only on Phase 7. This avoids a forward dependency and is recorded as a Spec Consistency Finding.

## A3 — Read-Switch and Rollback Strategy

| Option | Description | Selected |
|---|---|---|
| Direct facade switch | Switch the node directly, preserve legacy capability in LegacyRagKnowledgeAdapter, and roll back by git revert or adapter rollback. | ✓ |
| Runtime config read-switch | Keep old and new node paths selectable at runtime. | |
| Remove legacy path | Delete old RAG capability after facade introduction. | |

**User's choice:** No runtime read-switch or config flag; use a direct facade switch with LegacyRagKnowledgeAdapter.

**Notes:** This is a portfolio/demo architecture refactor, not a live gradual-rollout migration. Phase 8 adds no schema migration, real external side effects, or high-risk write actions. Contract tests and golden cases must prove the facade path. Baseline and spec consistency are updated at wrap-up.

## A4 — Facade Result Contract

| Option | Description | Selected |
|---|---|---|
| `knowledge_search_result.v2` | Return status, evidence_refs, citation_validation, best_score, threshold, and retrieval/rerank config versions. | ✓ |
| Legacy RetrievalResult | Return the existing RAG result unchanged. | |
| AgentState-shaped result | Make the service return node state fields directly. | |

**User's choice:** Return the spec's `knowledge_search_result.v2`.

**Notes:** The node maps the facade result into AgentState.

## B1 — Canonical EvidenceRefV1 Ownership

| Option | Description | Selected |
|---|---|---|
| `src/knowledge/schemas.py` | KnowledgeService owns and solely produces canonical EvidenceRefV1. | ✓ |
| `src/rag/schemas.py` | Promote the legacy retrieval schema to canonical. | |
| New `src/contracts/` | Create a neutral contract package in Phase 8. | |

**User's choice:** Define canonical EvidenceRefV1 in `src/knowledge/schemas.py`.

**Notes:** Legacy RAG schemas adapt into the canonical type. Phase 13 and Phase 15 must import it and must not define reduced variants. A neutral contracts package is deferred.

## B2 — EvidenceRefV1 Derivation

| Option | Description | Selected |
|---|---|---|
| Fixed deterministic derivation | Use the locked evidence_id, text_hash, policy_version, and rank rules. | ✓ |
| Planner-selected derivation | Let planning choose identifiers and hash semantics. | |
| Timestamp-derived version | Substitute retrieval/current time when policy version is absent. | |

**User's choice:** Use the fixed canonical derivation rule.

**Notes:** `evidence_id = '{doc_key}/{chunk_id}@{policy_version}'`; `text_hash = sha256(normalized chunk text UTF-8 bytes)` formatted `sha256:<lowercase hex>`; policy_version must come from a stable policy document/chunk version field and never from time; rank follows final service order, preferring post-rerank 1-based rank. Missing required fields must be recorded as schema/adapter gaps with a deterministic fallback or block the item from COVERED.

## B3 — Score and Snapshot Hash Projection

| Option | Description | Selected |
|---|---|---|
| Retain score; document projection | Keep bare float score in results/state; future snapshots strip score, retain rank, and sort rank-aware. | ✓ |
| Remove score now | Exclude score from service results and AgentState. | |
| Implement projection helper now | Add the Phase 13 snapshot/hash helper in Phase 8. | |

**User's choice:** Retain bare float score and document the Phase 13 hash-projection rule.

**Notes:** Phase 8 implements the producer side only. Snapshot/hash projection helper remains owned by Phase 13.

## B4 — AgentState and Consumer Migration

| Option | Description | Selected |
|---|---|---|
| Full EvidenceRefV1 migration | Migrate state, merge by evidence_id, and update retrieval and recommendation nodes consistently. | ✓ |
| Keep reduced state refs | Store only the current reduced EvidenceRef fields. | |
| Add parallel fields | Keep old refs and add a second canonical list. | |

**User's choice:** Migrate AgentState EvidenceRef to full EvidenceRefV1 and merge by `evidence_id`.

**Notes:** Update `_merge_evidence_refs` and the `generate_recommendation` consumer side to maintain consistency.

## C1 — Claim-Support Validation

| Option | Description | Selected |
|---|---|---|
| Deterministic evidence_id validation | Define claim_results and mark missing/wrong references unsupported. | ✓ |
| Keep chunk-membership only | Continue validating only cited chunk IDs. | |
| Add an LLM judge | Use model judgment for claim support. | |

**User's choice:** Implement deterministic claim-support validation.

**Notes:** Each material claim maps to `evidence_id[]` plus a verdict. Every referenced evidence ID must exist in evidence_refs. No LLM judge, inheriting old D-06e.

## C2 — Material Claim Producer

| Option | Description | Selected |
|---|---|---|
| `generate_recommendation` emits claims | Produce structured material claims with evidence ID references for validation. | ✓ |
| Derive claims in validator | Have the validator parse unstructured recommendation text. | |
| Validate retrieval output only | Avoid a cross-node recommendation change. | |

**User's choice:** Make `generate_recommendation` produce structured material claims.

**Notes:** This cross-node change is the spec-required claim-support path.

## C3 — Validator Placement

| Option | Description | Selected |
|---|---|---|
| New validator in `src/knowledge/` | Keep old chunk validator as a legacy adapter internal. | ✓ |
| Upgrade `src/rag/citation_validator.py` | Keep canonical validation in the legacy package. | |
| Put validator in recommendation node | Implement validation inline in the consumer. | |

**User's choice:** Place the new claim-support validator in `src/knowledge/`.

**Notes:** Existing `src/rag/citation_validator.py` is demoted to a legacy adapter internal, consistent with facade encapsulation.

## D1 — Tenant-over-Global and Effective Field Availability

| Option | Description | Selected |
|---|---|---|
| Inspect, then conditionally implement/degrade | Implement query-layer behavior if fields exist; otherwise record a gap, deterministically degrade, and mark PARTIAL/DEFERRED_WITH_OWNER. | ✓ |
| Add missing schema fields | Introduce a Phase 8 schema migration. | |
| Assume fields exist | Mark behavior COVERED without confirmation. | |

**User's choice:** Inspect actual PolicyDocument/PolicyChunk fields first and conditionally implement or degrade.

**Notes:** If scope/effective fields are absent, treat behavior deterministically, such as all items tenant-scoped with no effective filtering, and do not force COVERED. Phase 8 introduces no schema migration.

## D2 — Effective-Time Source

| Option | Description | Selected |
|---|---|---|
| KnowledgeContext run start time | Carry `effective_at`, defaulted from run start time, and inject it from state/run. | ✓ |
| Adapter wall clock | Default at query execution inside the adapter. | |
| Omit effective_at | Leave effective-time out of the Phase 8 contract. | |

**User's choice:** Carry `effective_at` in KnowledgeContext and default it to run start time.

**Notes:** The adapter must not use its internal wall-clock query time as the default.

## D3 — Evaluation Owner Gate

| Option | Description | Selected |
|---|---|---|
| Blocking Phase 8 gate | RAG groundedness/citation eval is BLOCKING; Phase 8 owns dataset, version, and hash; failure blocks exit. | ✓ |
| Informational eval | Run evaluation without blocking Phase 8 exit. | |
| Defer eval ownership | Leave the Phase 7 gate unresolved. | |

**User's choice:** Declare RAG groundedness/citation evaluation BLOCKING with Phase 8 dataset ownership.

**Notes:** The Phase 8 plan must state dataset version and hash. Failure blocks Phase 8 exit and satisfies the REQUIREMENTS planning rule and Phase 7 owner gate.

## D4 — KNOW-03 Migration and Rollback Gate

| Option | Description | Selected |
|---|---|---|
| No persistence/schema change | Use git revert or LegacyRagKnowledgeAdapter rollback and record the spec deviation. | ✓ |
| Runtime node rollback switch | Add a runtime route back to old `search_policy`. | |
| Add knowledge persistence | Introduce schema migration and associated read-switch/rollback artifacts. | |

**User's choice:** Add no persistence or schema change; use git revert or LegacyRagKnowledgeAdapter rollback.

**Notes:** This deviates from spec §19's `可回滚 node 到旧 search_policy` runtime rollback implication. Record the deviation in Spec Consistency Findings and synchronize the Phase 7 baseline and spec at wrap-up.

## Claude's Discretion

Exact KnowledgeContext field typing, internal adapter method names, query-rewrite handling location, and PolicyChunk field-mapping details are left to research and planning within the locked decisions.

## Deferred Ideas

- Neutral `src/contracts/` package until a later phase proves a cross-domain need.
- Snapshot/hash projection helper, owned by Phase 13.
- ToolCallContext reconciliation, owned by Phase 9/10.
- Query-rewrite enrichment beyond current behavior unless research shows it is required for the evaluation gate.
- Any real persistence or audit table for knowledge, which would make Phase 8 own its migration, read-switch, and rollback.
