# Phase 8: Knowledge Facade - Research

**Researched:** 2026-06-07
**Phase:** 08-knowledge-facade
**Requirements:** KNOW-01, KNOW-02, KNOW-03
**Source:** Direct main-session research (per user preference: no researcher sub-agent)

> Scope note: This phase is a **backend refactor** of policy evidence retrieval into a `KnowledgeService` facade. There is **no UI surface** — the plan-phase UI gate is a false positive (matched substring "ui" in "Phase 8" wording). Treat as `--skip-ui`. AI-SPEC is intentionally absent (see Eval Discipline below).

---

## 1. Objective

Answer: "What do I need to know to PLAN Phase 8 well?"

Phase 8 routes `retrieve_policy_evidence` through a new `src/knowledge/` facade producing canonical `EvidenceRefV1`, migrates `AgentState` evidence fields, switches citation validation to `evidence_id` membership, propagates explicit `effective_at`, and declares a BLOCKING citation-membership eval gate. No schema migration, no pgvector change, no runtime read-switch, no write tools.

---

## 2. Normative Contract Anchors (read before planning)

| Anchor | Location | What it fixes |
| --- | --- | --- |
| KnowledgeService signature | `docs/contract-spec.md` §8.3 | `PolicyKnowledgeService.search(request: KnowledgeSearchRequest, context: KnowledgeContext) -> KnowledgeSearchResult` |
| `knowledge_search_request.v2` | §8.3 JSON | query, primary_intent, business_context_refs, filters{tenant_id, merchant_id, policy_types, effective_at, locale}, retrieval_config_version, rerank_config_version, max_results, allow_partial_evidence |
| `knowledge_search_result.v2` | §8.3 JSON | schema_version, status, query_rewrite, retrieval/rerank config versions, best_score, threshold, evidence_refs[], citation_validation{validator_version, claim_results[]}, summary, error |
| Canonical EvidenceRefV1 table | §8.3 | required: schema_version(`evidence_ref.v1`), tenant_id, evidence_id, doc_key, chunk_id, policy_version, text_hash(`sha256:<lowercase hex>`), retrieved_at(RFC3339 UTC), retrieval_config_version; optional: score, rank(positive int) |
| `evidence_text_hash.v1` normalization | §8.3 | NFC → strip leading/trailing whitespace → internal newlines to `\n` → **no case-folding** → SHA-256 of UTF-8 bytes → `sha256:<lowercase hex>`. Golden cases REQUIRED in Phase 8 tests. |
| Canonical projection / rank-aware sort | §8.3 (also §10 rows 489–490, 584–585, 605) | snapshot/hash strips `score`, retains `rank`; sort `(rank, evidence_id, text_hash)` when all have rank, else `(evidence_id, text_hash)`; never trust retrieval order |
| KnowledgeContext projection | §8.0 + §8.3 | projection of `trusted_context.v1`: `tenant_id, user_id, role, merchant_scope, run_id, trace_id, locale` + run-derived `effective_at`. MUST NOT add fields absent from §8.0. `filters.merchant_id` must be validated against `merchant_scope` before use. |
| Knowledge rules | §8.3 | tenant-scoped wins over global (global is fallback only — **deferred for P8, see §6**); `effective_at` explicit, defaults to run start; partial evidence cannot authorize writes unless policy allows; `no_evidence` for policy-required actions → insufficient/manual, not action draft |
| Eval row | `docs/eval-test-plan.md` §20 | citation membership = `evidence_id ∈ retrieved evidence`; **must NOT** be counted as semantic claim support; semantic groundedness/support is a separate deferred eval |
| Phase 7 baseline | `.planning/phases/07-contract-baseline/07-CONTRACT-BASELINE.md` | EvidenceRefV1/`evidence_id` DEFERRED_WITH_OWNER → Phase 8 owner; direct cutover + rag-adapter rollback; TrustedContext code-level type converges at Phase 10 (P8 consumes §8.0 field set, not a shared runtime type) |
| Planning rules | `.planning/REQUIREMENTS.md` lines 47, 49 | every DEFERRED_WITH_OWNER row names owner+rationale+dependency+acceptance gate; every eval gate names blocking status, dataset owner/version/hash, failure impact |

---

## 3. Current Code Inventory (verified 2026-06-07)

### Files Phase 8 wraps/adapts (legacy, stay in `src/rag/`)
- `src/rag/schemas.py` — `EvidenceItem`(doc_key, chunk_id, title, section, score, text), `RetrievalResult`(query, retrieval_status, evidence[], best_score, fallback_message), `CitationValidation`, `SearchRequest`. **No** policy_version/tenant_id/rank/text_hash/retrieved_at/evidence_id.
- `src/rag/retriever.py` — `Retriever.search(query, tenant_id, top_k, doc_type, risk_level)`. Rerank assigns a 1-based order (`_rerank_candidates`); thresholds: STRONG=0.70, MIN=0.55. **Truncates** `text=chunk.content[:300]`.
- `src/rag/citation_validator.py` — `validate_citations(cited_chunk_ids, retrieval_result)` keys on **bare `chunk_id`**.
- `src/repositories/policy_chunk_repo.py` — `search_similar(...)` returns `list[(PolicyChunk, score)]`; `selectinload(PolicyChunk.document)` already loads the parent doc.
- `src/agent/tools/search_policy.py` — tool returning `{status, data{retrieval_status, best_score, evidence[], fallback_message}, error}`. Catches timeout (`DB_TIMEOUT`) and generic (`SEARCH_ERROR`).

### Files Phase 8 migrates (callers/consumers)
- `src/agent/state.py` — `EvidenceRef` TypedDict = (doc_key, chunk_id, title, confidence, retrieved_at). Migrate to full EvidenceRefV1 fields. `evidence_refs: list[EvidenceRef]` is persistent; `retrieved_evidence: dict` ephemeral.
- `src/agent/nodes/retrieve_policy_evidence.py` — calls `search_policy` directly. `_merge_evidence_refs` keys on `(doc_key, chunk_id)` → change to `evidence_id`. `_evidence_refs_from_result` builds the reduced ref dict. Gate: `MIN_EVIDENCE_SCORE=0.55`.
- `src/agent/nodes/generate_recommendation.py` — imports `_merge_evidence_refs` from the retrieve node and `validate_citations` + `RetrievalResult` from `src/rag`. `_validated_evidence_refs` keys on `chunk_id`. Must emit structured material claims carrying `evidence_id` and feed the new membership validator.

### Models (NOT migrated — no schema change in P8)
- `PolicyDocument`(id, tenant_id NOT NULL, doc_key str(64), doc_type, title, **effective_date: date**, risk_level, **version: int default 1**, content). Unique (tenant_id, doc_key).
- `PolicyChunk`(id, tenant_id NOT NULL, doc_id FK, chunk_id str(64), section, content, risk_level, effective_date, embedding Vector(1024)). Reaches doc_key via `chunk.document.doc_key`.

### Test layout
- `tests/` flat + `tests/agent/test_nodes/`, `tests/agent/test_tools/`, `tests/integration/`.
- Existing: `tests/test_retriever.py`, `tests/test_rag_eval.py`, `tests/agent/test_nodes/test_retrieve_policy_evidence.py`, `tests/agent/test_nodes/test_generate_recommendation.py`, `tests/agent/test_tools/test_tool_contracts.py`. New knowledge contract/golden tests should follow these patterns (likely `tests/knowledge/` or `tests/test_knowledge_*`).

---

## 4. EvidenceRefV1 Field Derivation — Mapping & GAPS (D-B2 critical)

Per D-B2, evidence_id derivation is **NOT planner discretion**. The plan MUST pin each field or list it as a schema/adapter gap with a deterministic fallback (or block the item from COVERED).

| EvidenceRefV1 field | Source | Status |
| --- | --- | --- |
| `schema_version` | literal `evidence_ref.v1` | OK |
| `tenant_id` | `KnowledgeContext.tenant_id` (trusted) / `chunk.tenant_id` | OK |
| `doc_key` | `chunk.document.doc_key` | OK |
| `chunk_id` | `PolicyChunk.chunk_id` | OK |
| `evidence_id` | `'{doc_key}/{chunk_id}@{policy_version}'` | OK once policy_version pinned |
| `policy_version` | **AMBIGUOUS — see GAP-1** | **GAP** |
| `text_hash` | `evidence_text_hash.v1`(full chunk text) | **GAP-2 (truncation)** |
| `score` | rerank/vector score (bare float, retained) | OK |
| `rank` | 1-based final return order (post-rerank preferred) | OK (rerank already orders; assign rank at adapter mapping time) |
| `retrieved_at` | RFC3339 UTC at retrieval | OK |
| `retrieval_config_version` | **GAP-3** — no version literal in code today | **GAP** |

### GAP-1 — `policy_version` ambiguity (MUST resolve before COVERED)
`PolicyDocument` exposes both `version: int` (default 1) and `effective_date: date`. The spec is internally inconsistent: `evidence_id` example `policy_refund_timeout/chunk_001@v3` implies `@v{version}`, but the EvidenceRefV1 JSON shows `"policy_version": "2026-06-01"` (an `effective_date`). **Recommended resolution for the planner:** pin `policy_version = f"v{PolicyDocument.version}"` (stable document version field, matches the `@v3` evidence_id form and D-B2's "stable version field; never substituted by retrieved_at/current time"). `effective_date` then feeds `effective_at` filtering, not identity. If the planner instead chooses `effective_date`, the `evidence_id` example must be reconciled. Either way: **one deterministic rule, fixed by a golden test, recorded as a Spec Consistency Finding.** `PolicyChunk` has no own version field, so chunk-level version must inherit from the parent document.

### GAP-2 — `text_hash` must hash FULL chunk text, not display text
`Retriever` sets `text=chunk.content[:300]` and `search_policy` only surfaces that truncated `text`. Hashing the truncated display string would make `text_hash` unstable vs. the real chunk and break Phase 13 reproduction. **The LegacyRagKnowledgeAdapter must hash `chunk.content` (full) via `evidence_text_hash.v1`**, which means the adapter needs access to the chunk object (or the repo must surface full content), not just the tool's truncated payload. This argues for the adapter calling `Retriever`/repo directly rather than going through the truncating `search_policy` tool for hash material. Flag as an adapter-boundary decision.

### GAP-3 — config version literals
No `retrieval_config_version`/`rerank_config_version` literal exists in code (only module constants). Planner must define stable literals (spec examples use `retrieval.v3`, `rerank.v2`) and a single source for them, referenced by both request and each EvidenceRefV1. Threshold (`0.70`) and MIN (`0.55`) map to result `threshold`/gating.

---

## 5. Facade Architecture (within locked D-A rules)

```
src/knowledge/
  __init__.py
  schemas.py        # KnowledgeContext, KnowledgeSearchRequest(.v2), KnowledgeSearchResult(.v2),
                    # EvidenceRefV1 (canonical, sole producer), CitationValidationResult, ClaimResult
  service.py        # PolicyKnowledgeService.search(request, context) -> result (facade; query rewrite,
                    # threshold, no-evidence fallback orchestration; merchant_scope check on filters.merchant_id)
  adapters.py       # LegacyRagKnowledgeAdapter: wraps Retriever/PolicyChunkRepository/EmbeddingService;
                    # maps PolicyChunk -> EvidenceRefV1 (FULL-text hash, rank, policy_version); owns legacy search_policy path
  citation.py       # evidence_id membership validator (validator_version literal); produces claim_results[]
  text_hash.py      # evidence_text_hash.v1 normalization + sha256 (or inline in schemas)
```

- `EvidenceRefV1` lives in `src/knowledge/schemas.py` (D-B1). `src/rag/schemas.py` stays legacy/internal. No `src/contracts/` package (deferred).
- `retrieve_policy_evidence` node switches from `search_policy(...)` to `KnowledgeService.search(request, context)` (D-A3 direct switch). `search_policy` + retriever remain reachable inside the adapter for rollback.
- Node maps `knowledge_search_result.v2` into `AgentState` (`retrieved_evidence` = full payload retaining score; `evidence_refs` merged/deduped by `evidence_id`).
- `KnowledgeContext.effective_at` injected by the node from state/run start (D-D2), not adapter wall-clock.
- Legacy citation validator (`src/rag/citation_validator.py`) demoted to adapter internal (D-C3); new `evidence_id` membership validator in `src/knowledge/citation.py` (D-C1/D-C2).

---

## 6. Tenant / Global / Effective-Time

- `PolicyDocument.tenant_id` is **NOT NULL**; there is no global-policy scope and P8 adds no migration → **tenant-over-global is DEFERRED_WITH_OWNER** to a later policy-scope phase (D-D1). P8 implements deterministic **tenant-scoped** behavior only. The DEFERRED row must name: owner (later policy-scope phase), rationale (no schema/global column in MVP), dependency (schema+query migration), acceptance gate (schema-and-query tenant-over-global tests). The §8.3 "tenant wins over global" rule is therefore **not** a P8 blocking exit — record as a Spec Consistency Finding.
- `effective_at`: explicit on KnowledgeContext, defaults to run start; node injects it; adapter filters policy by `effective_date <= effective_at` (deterministic, no wall-clock).

---

## 7. Eval Discipline (carry into the plan — user caveat)

AI-SPEC is intentionally skipped (architecture + deterministic eval already locked in `contract-spec.md §8.3` and `08-CONTEXT.md`). The plan MUST still:

1. **Pin the citation-membership eval dataset**: state dataset **owner = Phase 8**, an explicit **version** string, and a **content hash** (per REQUIREMENTS line 49 and D-D3). Declare it **BLOCKING** with failure impact ("no_evidence/failed membership must NOT emit a deterministic action recommendation; membership must NOT be treated as semantic support").
2. **Mark AI-SPEC intentionally absent** with the recorded reason ("refactor; framework + deterministic eval gate already locked in contract-spec §8.3 / 08-CONTEXT") so downstream review does not misflag it as a gap.
3. **Confirm semantic groundedness/support has a named owner** as a separate deferred eval (eval-test-plan §20) — it must not be silently superseded by the membership gate.

---

## 8. Golden / Contract Tests the plan must include (Nyquist Dimension 8)

1. `evidence_text_hash.v1` golden cases — NFC, whitespace strip, newline `\n`, no case-fold, `sha256:<lowercase hex>` (§8.3 requires golden cases).
2. **EvidenceRefV1 canonical projection golden bytes** (D-B3): score stripped, rank retained, rank-aware sort `(rank, evidence_id, text_hash)` / `(evidence_id, text_hash)`. Catches projection error at P8 rather than at Phase 13 hash reproduction. (Producer-side projection contract only — NOT the CanonicalHashProfile/hash-profile implementation, which is Phase 13.)
3. `evidence_id` derivation golden (fixed policy_version rule from GAP-1).
4. Status contract tests through the facade: strong / partial / no_evidence preserved (KNOW-01).
5. Citation membership tests: cited `evidence_id ∈ evidence_refs` passes; missing/wrong fails; empty citations fails (KNOW-02 / D-C1).
6. Effective-time test: explicit `effective_at` filters deterministically; default = run start (D-D2).
7. Tenant-scoped determinism test; tenant-over-global explicitly deferred (no P8 test, owner recorded).
8. Node migration tests: `_merge_evidence_refs` dedupes by `evidence_id`; `retrieve_policy_evidence` + `generate_recommendation` consume migrated refs; gate routes no_evidence → insufficient (KNOW-03 behavior).

---

## Validation Architecture

**Nyquist sampling rationale:** Phase 8 is a contract-producing refactor where silent projection/derivation drift is the dominant failure mode (it only surfaces phases later at snapshot/replay). Validation must therefore be **deterministic golden-byte and membership assertions**, sampled at every contract boundary the facade introduces, not behavioral smoke tests alone.

| Validation dimension | What is sampled | Method | Blocking? |
| --- | --- | --- | --- |
| EvidenceRefV1 canonical projection | golden bytes (score-stripped, rank-aware sort) | golden file compare | Yes |
| evidence_text_hash.v1 | normalization + sha256 golden cases | golden compare | Yes |
| evidence_id derivation | fixed policy_version rule | golden compare | Yes |
| Retrieval status semantics | strong/partial/no_evidence through facade | contract test | Yes |
| Citation membership | evidence_id ∈ evidence_refs verdict | contract test | Yes (eval gate) |
| Effective-time propagation | explicit effective_at, run-start default | contract test | Yes |
| Tenant scoping | deterministic tenant-scoped retrieval | contract test | Yes |
| State/consumer migration | merge-by-evidence_id, node consumption | node tests | Yes |
| Tenant-over-global | (deferred — owner recorded, no P8 test) | n/a | Deferred |

**Citation-membership eval gate:** BLOCKING. Dataset owner = Phase 8; version + content hash to be fixed in the PLAN. Membership ≠ semantic support; semantic groundedness is a separate deferred eval with its own owner.

---

## 9. Open Decisions Left to Planning (within locked rules)

- Exact `KnowledgeContext` typing (pydantic vs TypedDict) — match project convention (rag uses pydantic `BaseModel`).
- Adapter method names and whether the adapter calls `Retriever`/repo directly (needed for full-text hash, GAP-2) vs. through `search_policy`.
- Query-rewrite location (node vs facade) — keep current behavior unless eval gate requires more (deferred otherwise).
- New test module placement (`tests/knowledge/` vs flat `tests/test_knowledge_*`).
- `policy_version` final rule (GAP-1 recommendation: `v{version}`) — must be one deterministic choice + golden + Spec Consistency Finding.

---

## RESEARCH COMPLETE
