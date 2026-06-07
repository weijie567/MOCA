---
phase: 08-knowledge-facade
verified: 2026-06-07T07:28:16Z
status: gaps_found
score: 3/6 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Strong/partial/no-evidence behavior honors the public KnowledgeSearchRequest contract"
    status: partial
    reason: "The facade preserves adapter statuses, but ignores allow_partial_evidence=False and still returns actionable partial evidence."
    artifacts:
      - path: "src/knowledge/service.py"
        issue: "search() returns partial_evidence unchanged without consulting request.allow_partial_evidence."
    missing:
      - "Handle allow_partial_evidence=False by returning no_evidence with no refs or explicitly rejecting the unsupported option."
      - "Add tests for both allow_partial_evidence values."
  - truth: "Effective-time filtering cannot lose valid current evidence behind future-dated limited candidates"
    status: failed
    reason: "The repository applies SQL LIMIT before the adapter filters effective_date, so future rows can crowd valid current evidence out of the candidate window."
    artifacts:
      - path: "src/repositories/policy_chunk_repo.py"
        issue: "search_similar() has no effective_date predicate and applies .limit(top_k)."
      - path: "src/knowledge/adapters.py"
        issue: "effective_date filtering occurs only after search_similar() returns its limited rows."
      - path: "tests/knowledge/test_effective_time.py"
        issue: "The mocked repository returns both future and current rows, so the real pre-filter LIMIT failure is not exercised."
    missing:
      - "Pass effective_date to search_similar() and filter in SQL before ordering/limiting."
      - "Add a repository/integration test where future rows fill the initial top-k but current evidence must still be returned."
  - truth: "Tenant-over-global policy precedence is enforced"
    status: failed
    reason: "The roadmap goal and KNOW-02 require tenant-over-global behavior, but the current schema/query supports tenant-only retrieval. The documented owner is a generic later policy-scope phase that does not exist in the current roadmap, so it cannot be filtered as a valid later-phase deferral."
    artifacts:
      - path: "src/knowledge/service.py"
        issue: "Docstring records a deferral rather than implemented tenant-over-global precedence."
      - path: "src/repositories/policy_chunk_repo.py"
        issue: "Query requires PolicyDocument.tenant_id == tenant_id and has no global/default fallback path."
    missing:
      - "Implement and test tenant-over-global precedence, or add a concrete roadmap phase/requirement disposition that formally removes it from Phase 08 exit scope."
---

# Phase 8: Knowledge Facade Verification Report

**Phase Goal:** Route policy evidence retrieval through KnowledgeService with canonical EvidenceRefV1, citation validation, effective-time, and tenant-over-global behavior.
**Verified:** 2026-06-07T07:28:16Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Knowledge reads use `PolicyKnowledgeService` while the legacy RAG path remains available as adapter/rollback fallback | VERIFIED | `retrieve_policy_evidence.py:125-126` calls the facade; `adapters.py:9,28` retains `legacy_search_policy`; direct cutover/rollback is documented with no persistence/read-switch. |
| 2 | Canonical EvidenceRefV1, projection, version pin, evidence-ID membership, state, and reporting contracts are wired end to end | VERIFIED | `schemas.py`, `text_hash.py`, `citation.py`, ingestion version bump, node/state merge by `evidence_id`, and v2 reporting consumers are substantive and wired; focused/full suites pass. |
| 3 | Strong/partial/no-evidence behavior honors the public request contract | FAILED | Basic statuses pass, but `service.py:55-64` ignores `allow_partial_evidence`; direct spot-check returned `partial_evidence 1` with the flag false. |
| 4 | Effective-time filtering reliably returns valid in-effect evidence | FAILED | `policy_chunk_repo.py:43-60` orders/limits without effective date; `adapters.py:94-97` filters only afterward. |
| 5 | Tenant-over-global precedence is enforced | FAILED | Only tenant-scoped retrieval exists. The generic later policy-scope owner is not a phase in the current roadmap. |
| 6 | Migration/cutover is safely reversible without an unowned persistence/read-switch | VERIFIED | Service-only direct cutover; no new persistence/read-switch; retained adapter and git-revert rollback are documented and present. |

**Score:** 3/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `src/knowledge/schemas.py` | Canonical request/result/EvidenceRefV1/projection contracts | VERIFIED | Exact canonical fields, stable builder, rank-aware projection. |
| `src/knowledge/text_hash.py` | `evidence_text_hash.v1` | VERIFIED | NFC/newline/strip/SHA-256 implementation with golden tests. |
| `src/knowledge/citation.py` | Evidence-ID membership validator | VERIFIED | Pure deterministic membership validation; correctly not semantic support. |
| `src/knowledge/service.py` | Facade semantics and scope controls | PARTIAL | Wired and tenant-scoped, but ignores `allow_partial_evidence` and does not implement tenant-over-global. |
| `src/knowledge/adapters.py` | Legacy retrieval adapter with canonical refs/effective-time | PARTIAL | Canonical mapping is real; effective-time filtering is downstream of repository LIMIT. |
| `src/rag/ingestion.py` | Content-stable policy version pin | VERIFIED | Locks row and bumps version only when content changes before overwrite. |
| `src/agent/nodes/retrieve_policy_evidence.py` | Active facade read path | VERIFIED | Builds context/request, invokes facade, maps result and safety drafts. |
| `src/agent/nodes/generate_recommendation.py` | Structured claims and membership validation | VERIFIED | Membership wiring is real; semantic groundedness is explicitly outside Phase 08 contract. |
| `src/agent/trace.py`, `src/api/routers/agent_runs.py` | v2 evidence reporting | VERIFIED | Reads `evidence_refs`, falls back for legacy data, dedupes by `evidence_id`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| Retrieval node | `PolicyKnowledgeService` | `search(request, context)` | WIRED | Active runtime read path. |
| `PolicyKnowledgeService` | `LegacyRagKnowledgeAdapter` | `adapter.retrieve(...)` | PARTIAL | Response mapping works; public partial-evidence control is not applied. |
| Adapter | `PolicyChunkRepository` | `search_similar(...)` | PARTIAL | Tenant scope is passed, but effective date is not pushed before LIMIT. |
| Recommendation node | Citation validator | `validate_membership(claims, evidence_models)` | WIRED | Validates full `evidence_id` membership. |
| Ingestion | Policy version identity | locked document update | WIRED | Content change bumps version in the same transaction. |

### Data-Flow Trace

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `LegacyRagKnowledgeAdapter` | `evidence_refs` | Repository chunks and scores | Yes, but candidate set can be incorrectly truncated before effective filtering | PARTIAL |
| Retrieval node | `retrieved_evidence` / state refs | `PolicyKnowledgeService.search` | Yes | FLOWING |
| Recommendation node | policy prompt context | canonical refs only | No policy content; accepted as non-blocking because semantic support is explicitly deferred | DEFERRED/NON-BLOCKING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 08 focused suites | `uv run pytest tests/knowledge ... tests/test_agent_runs_api.py -q` | 75 passed | PASS |
| Full regression suite | `uv run pytest -q --tb=short` | 273 passed, 1 third-party deprecation warning | PASS |
| Reject partial evidence when disallowed | Inline `PolicyKnowledgeService.search` with `allow_partial_evidence=False` | Printed `partial_evidence 1` | FAIL |
| Effective filter before repository LIMIT | Code trace of repository and adapter | SQL LIMIT precedes adapter effective-date filter | FAIL |

### Requirements Coverage

| Requirement | Source Plans | Status | Evidence |
|---|---|---|---|
| KNOW-01 | 08-02, 08-04, 08-05 | PARTIAL | Facade and basic statuses are wired, but `allow_partial_evidence=False` is ignored. |
| KNOW-02 | 08-01 through 08-06 | BLOCKED | Canonical evidence/citation/projection contracts pass; effective-time correctness and tenant-over-global behavior do not. |
| KNOW-03 | 08-04, 08-05 | SATISFIED | No persistence/read-switch introduced; direct cutover has retained-adapter and git-revert rollback. |

No orphaned Phase 08 requirement IDs were found: all of KNOW-01, KNOW-02, and KNOW-03 appear in plan bodies and `.planning/REQUIREMENTS.md`.

### `08-REVIEW.md` Warning Assessment

| Warning | Classification | Requirement/Scope Assessment |
|---|---|---|
| WR-01: Recommendation receives no policy content | Valid deferred/non-blocking | Phase 08's normative citation contract is membership-only; semantic support is explicitly a separate deferred contract. This remains a real product risk, but it does not make the Phase 08 membership contract fail. |
| WR-02: Effective-time filtering after candidate truncation | Blocking gap | Violates 08-02 plan-body must-have and KNOW-02 effective-time enforcement. Passing test is misleading because it mocks both candidates after repository truncation. |
| WR-03: `allow_partial_evidence=False` ignored | Blocking gap | Violates the public request contract and strong/partial/no-evidence semantics under KNOW-01. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `src/knowledge/service.py` | 55-64 | Public control field ignored | Blocker | Caller cannot require strong-only evidence. |
| `src/repositories/policy_chunk_repo.py` | 43-60 | Filter applied in downstream layer after LIMIT | Blocker | Valid current evidence can be lost and reported as no evidence. |
| `src/agent/nodes/generate_recommendation.py` | 73-85 | Policy content absent from recommendation prompt | Warning | Semantic unsupported recommendations can pass membership; explicitly deferred from Phase 08. |

### Gaps Summary

The KnowledgeService boundary, canonical evidence identity/projection, citation membership, runtime cutover, safety routing, reporting migration, and rollback path are real and tested. Phase 08 still fails its full goal because effective-time behavior is incorrect at the repository boundary, the public partial-evidence control is ignored, and tenant-over-global behavior remains unimplemented without a concrete later roadmap phase.

---

_Verified: 2026-06-07T07:28:16Z_
_Verifier: Claude (gsd-verifier)_
