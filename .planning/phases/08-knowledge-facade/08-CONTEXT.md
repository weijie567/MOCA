# Phase 8: Knowledge Facade - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning
**Source:** /gsd-discuss-phase 8 (interactive, A/B/C/D areas)

<domain>

## Phase Boundary

Phase 8 routes policy evidence retrieval through a new KnowledgeService facade. It delivers the canonical EvidenceRefV1 producer and state migration, deterministic claim-support citation validation, explicit effective-time propagation, and tenant-over-global retrieval behavior where the underlying policy schema supports the required fields. The facade path must preserve the existing strong_evidence, partial_evidence, and no_evidence outcomes while satisfying the Phase 7 owner gate.

Fixed non-scope:

- No pgvector or embedding stack change.
- No schema migration or knowledge persistence.
- No runtime read-switch or configuration flag.
- No write/action tools.
- No dependency on Phase 9's ToolCallContext or unimplemented tool_context.v2.

Requirements:

- KNOW-01
- KNOW-02
- KNOW-03

</domain>

<decisions>

## Implementation Decisions

### A. Facade Boundary & Module Placement

- **D-A1 — New knowledge package:** KnowledgeService lives in a new `src/knowledge/` package containing facade, schemas, and adapter modules, symmetric with Phase 9's `src/business_tools/`. Existing `src/rag/*` remains in place and is wrapped or called by an adapter. This matches the naming in spec §19.
- **D-A2 — Lightweight trusted context:** The facade accepts a new lightweight KnowledgeContext containing `tenant_id`, `user_id`, `role`, `run_id`, and `effective_at`, not the spec's ToolCallContext. ToolCallContext and tool_context.v2 are owned by Phase 9, while Phase 8 depends only on Phase 7. Phase 8 must not introduce a forward dependency on Phase 9's unimplemented contract. This is recorded as a Spec Consistency Finding.
- **D-A3 — Direct facade switch, no runtime read-switch:** Phase 8 introduces no runtime read-switch or config flag. This is a portfolio/demo architecture refactor, not a live gradual-rollout migration; it adds no schema migration, real external side effects, or high-risk write actions. Legacy `search_policy` and retriever capability remains available inside LegacyRagKnowledgeAdapter, while `retrieve_policy_evidence` switches directly to `KnowledgeService.search(...)`. Rollback is by git revert or adapter rollback, not a runtime config flag. Contract tests and golden cases must prove strong/partial/no-evidence behavior, EvidenceRefV1, citation, tenant behavior, and effective-time behavior through the facade path. Related baseline and spec files are updated for consistency at wrap-up.
- **D-A4 — Result contract and node mapping:** The facade returns the spec's `knowledge_search_result.v2`, including status, evidence_refs, citation_validation, best_score, threshold, and retrieval and rerank config versions. The node maps that result into AgentState.

### B. EvidenceRefV1 Schema & State Migration

- **D-B1 — Canonical schema ownership:** Canonical EvidenceRefV1 is defined in `src/knowledge/schemas.py`. Phase 8 owns KnowledgeService and is the sole producer of EvidenceRefV1. `src/rag/schemas.py` remains the legacy/internal retrieval schema and is adapted into `src/knowledge/schemas.py::EvidenceRefV1`. Phase 13 and Phase 15 must import this canonical type and must not define reduced EvidenceRef variants for snapshot or replay. A neutral `src/contracts/` package is deferred until later phases prove a broader cross-domain contract package is necessary.
- **D-B2 — Fixed derivation semantics:** `evidence_id = '{doc_key}/{chunk_id}@{policy_version}'`. `text_hash` is SHA-256 of normalized chunk text UTF-8 bytes, formatted as `sha256:<lowercase hex>`. `policy_version` comes from the policy document or chunk stable version field and is never substituted by `retrieved_at` or current time. `rank` comes from KnowledgeService final return order, preferring post-rerank 1-based rank. Planning may inspect actual PolicyDocument and PolicyChunk field names and map them in LegacyRagKnowledgeAdapter. If `doc_key`, `chunk_id`, or `policy_version` is missing, the Phase 8 plan must list it as a schema/adapter gap and define a deterministic fallback or block that item from COVERED. Evidence ID derivation is not planner discretion.
- **D-B3 — Score retention and hash projection rule:** Knowledge results and AgentState retain a bare float score. Any future snapshot/hash builder must strip score first, retain rank, and use a rank-aware canonical sort. Phase 8 implements only the producer side and clearly documents this rule for Phase 13. Phase 8 does not implement the snapshot/hash projection helper.
- **D-B4 — State and consumer migration:** Migrate `src/agent/state.py` EvidenceRef to the full EvidenceRefV1 fields. Change the evidence_refs merge key from `(doc_key, chunk_id)` to `evidence_id`. Update `retrieve_policy_evidence` node `_merge_evidence_refs` and the `generate_recommendation` consumer side consistently.

### C. Citation Claim-Support Upgrade

- **D-C1 — Deterministic claim-support validator:** Phase 8 defines a `claim_results` structure mapping each claim to `evidence_id[]` and a verdict. The validator is deterministic: every material claim must reference an `evidence_id` present in evidence_refs; a missing or wrong reference is unsupported. There is no LLM judge, inheriting old D-06e. This covers the spec's citation_validation.v2 structure.
- **D-C2 — Structured material claims from recommendation:** `generate_recommendation` produces structured material claims, each carrying evidence ID references, and the validator checks them. This cross-node change is the spec-required path.
- **D-C3 — Legacy validator encapsulation:** Existing `src/rag/citation_validator.py` is demoted to a legacy adapter internal. The new claim-support validator lives in `src/knowledge/`, consistent with adapter encapsulation.

### D. Tenant-over-Global, Effective-Time & Owner Gate

- **D-D1 — Conditional query-layer behavior:** Research and planning first check whether PolicyDocument and PolicyChunk already have tenant/global scope and effective-from/to fields. If present, the facade implements tenant-over-global and effective filtering at the query layer. If missing, the plan lists a schema gap, implements a deterministic adapter degrade such as treating all items as tenant-scoped with no effective filtering, and marks that contract PARTIAL/DEFERRED_WITH_OWNER. It must not be forced to COVERED. Phase 8 introduces no schema migration.
- **D-D2 — Explicit effective time:** KnowledgeContext carries `effective_at`, defaulted to run start time rather than adapter-internal wall-clock query time. The node injects it from state/run. This matches spec §8.3.
- **D-D3 — Blocking evaluation gate:** Phase 8 explicitly declares the RAG groundedness/citation evaluation as BLOCKING. Dataset owner is Phase 8; dataset version and hash must be stated in the Phase 8 plan. Failure blocks Phase 8 exit. This satisfies the REQUIREMENTS planning rule and the Phase 7 gate.
- **D-D4 — KNOW-03 owner gate and rollback:** Phase 8 adds no persistence and no schema change. Rollback is git revert or LegacyRagKnowledgeAdapter rollback. The deviation from spec §19's runtime node rollback to old `search_policy` is recorded in Spec Consistency Findings, and the Phase 7 baseline and spec are synchronized at wrap-up.

### Claude's Discretion

Exact KnowledgeContext field typing, internal adapter method names, query-rewrite handling location, and PolicyChunk field-mapping details are left to research and planning within the locked rules above.

</decisions>

<spec_consistency_findings>

## Spec Consistency Findings

1. Spec §8.3 uses `context: ToolCallContext`, but tool_context.v2 is Phase 9-owned and Phase 8 depends only on Phase 7. Phase 8 uses a lightweight KnowledgeContext instead. Readiness impact: avoids a forward dependency. Owner: Phase 8 defines KnowledgeContext; Phase 9/Phase 10 may later reconcile it to ToolCallContext.
2. Spec §19 Phase 8 rollback says `可回滚 node 到旧 search_policy`, implying a runtime node-level rollback. Phase 8 decisions D-A3 and D-D4 instead use LegacyRagKnowledgeAdapter plus git revert with no runtime read-switch, justified by the portfolio/demo non-production context. Readiness impact: no runtime read-switch artifact. Owner: Phase 8. Action: synchronize spec §19 and the Phase 7 baseline note at wrap-up.
3. Tenant-over-global and effective-time behavior depend on PolicyDocument or PolicyChunk having scope and effective fields, which current source does not confirm. If absent, this contract is PARTIAL/DEFERRED_WITH_OWNER, owner Phase 8, with acceptance gate of facade query-layer filtering tests once fields exist. It is not COVERED.

</spec_consistency_findings>

<canonical_refs>

## Canonical References

### Spec & decomposition

- `docs/agent-architecture-spec.md` §8.3 — Knowledge/RAG target, KnowledgeSearchRequest/Result v2, canonical EvidenceRefV1 table, and knowledge rules; §19 Phase 8 migration row around line 2732; §20 knowledge contract eval row.
- `docs/agent-architecture-phase-decomposition.md` — Phase 8 boundary, dependency on Phase 7, and schema-ownership rule for any introduced facade persistence.

### Phase 7 baseline

- `.planning/phases/07-contract-baseline/07-CONTRACT-BASELINE.md` — Knowledge/RAG/EvidenceRefV1 DEFERRED_WITH_OWNER row and evidence_id register entry naming Phase 8 as owner.

### Current MOCA source evidence

- `src/agent/nodes/retrieve_policy_evidence.py` — current direct-call node Phase 8 migrates to facade.
- `src/agent/tools/search_policy.py` — current tool wrapped by LegacyRagKnowledgeAdapter.
- `src/rag/retriever.py`, `src/rag/schemas.py`, `src/rag/citation_validator.py`, `src/repositories/policy_chunk_repo.py` — legacy retrieval and citation internals to wrap or adapt.
- `src/agent/state.py` — EvidenceRef TypedDict and evidence_refs/retrieved_evidence fields to migrate.
- `src/agent/nodes/generate_recommendation.py` — recommendation consumer that must emit structured material claims.

### Planning state

- `.planning/REQUIREMENTS.md` — KNOW-01..03 and planning requirements covering the coverage matrix, eval gate metadata, and migration ownership rules.
- `.planning/ROADMAP.md` — Phase 8 row and success criteria.

</canonical_refs>

<code_context>

## Existing Code Insights

### Reusable Assets

- Existing retriever, embedder, and pgvector path remains in place behind the adapter.
- Reranking already produces an internal 1-based rank.
- Existing retrieval schemas already express `strong_evidence`, `partial_evidence`, and `no_evidence`.
- The existing chunk-membership citation validator can remain as a legacy adapter internal.

### Established Patterns

- Tool results use the dictionary shape `{status, data, error}`.
- Nodes record `trace_steps`.
- The retrieval node currently merges `evidence_refs`; Phase 8 changes its merge identity to `evidence_id`.

### Integration Points

- `retrieve_policy_evidence` node switches from the direct tool call to KnowledgeService.
- `generate_recommendation` emits structured material claims and remains consistent with migrated evidence references.
- AgentState evidence fields migrate to the canonical EvidenceRefV1 representation.

</code_context>

<deferred>

## Deferred Ideas

- Neutral `src/contracts/` package, until a later phase proves a cross-domain need.
- Snapshot/hash projection helper, owned by Phase 13.
- ToolCallContext reconciliation, owned by Phase 9/10.
- Query-rewrite enrichment beyond current behavior, unless research shows it is required for the evaluation gate.
- Any real persistence or audit table for knowledge. Introducing one would make Phase 8 own its migration, read-switch, and rollback, and is currently out of scope.

</deferred>

---
*Phase: 08-knowledge-facade*
*Context gathered: 2026-06-06 via /gsd-discuss-phase*
