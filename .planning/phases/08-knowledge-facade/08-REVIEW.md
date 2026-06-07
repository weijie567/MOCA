---
phase: 08-knowledge-facade
reviewed: 2026-06-07T07:18:11Z
depth: standard
files_reviewed: 35
files_reviewed_list:
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/retrieve_policy_evidence.py
  - src/agent/state.py
  - src/agent/trace.py
  - src/api/routers/agent_runs.py
  - src/knowledge/__init__.py
  - src/knowledge/adapters.py
  - src/knowledge/citation.py
  - src/knowledge/config.py
  - src/knowledge/schemas.py
  - src/knowledge/service.py
  - src/knowledge/text_hash.py
  - src/rag/ingestion.py
  - src/repositories/policy_document_repo.py
  - tests/agent/test_graph.py
  - tests/agent/test_nodes/test_assess_risk_and_approval.py
  - tests/agent/test_nodes/test_generate_recommendation.py
  - tests/agent/test_nodes/test_retrieve_policy_evidence.py
  - tests/agent/test_trace.py
  - tests/conftest.py
  - tests/knowledge/conftest.py
  - tests/knowledge/datasets/citation_membership_v1.json
  - tests/knowledge/test_citation_membership.py
  - tests/knowledge/test_citation_membership_eval.py
  - tests/knowledge/test_effective_time.py
  - tests/knowledge/test_evidence_projection.py
  - tests/knowledge/test_facade_integration.py
  - tests/knowledge/test_facade_status.py
  - tests/knowledge/test_tenant_scope.py
  - tests/knowledge/test_text_hash.py
  - tests/test_agent_runs_api.py
  - tests/test_ingestion.py
findings:
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-06-07T07:18:11Z
**Depth:** standard
**Files Reviewed:** 35
**Status:** issues_found

## Summary

The facade establishes canonical evidence identity, tenant-scoped retrieval, citation membership validation, and no-action safety routing. Three correctness gaps remain: the recommendation model cannot see policy content, effective-time filtering can lose valid candidates, and the public partial-evidence control is ignored.

Verification: the full explicitly scoped test suite passed (`79 passed`, one third-party deprecation warning). The findings below are untested edge cases.

## Warnings

### WR-01: Recommendation Generation Receives No Policy Content

**File:** `src/agent/nodes/generate_recommendation.py:73-85`
**Issue:** `_summarize_evidence` sends only identity/version/score metadata to the LLM. `EvidenceRefV1` also contains no excerpt or summary, so the model never sees the retrieved policy text it is expected to use when generating `recommended_action` and `reasoning_summary`. Citation membership can still pass because it only verifies that an ID exists, allowing unsupported recommendations to be presented as policy-grounded.
**Fix:** Add a safe policy excerpt or per-evidence summary to the knowledge result consumed by this node and include it in the generation prompt. Add an integration test whose recommendation depends on a distinctive rule present only in the retrieved policy content.

### WR-02: Effective-Time Filtering Happens After Candidate Truncation

**File:** `src/knowledge/adapters.py:85-97`
**Issue:** `search_similar` applies its SQL `LIMIT` before the adapter removes future-dated chunks. If enough high-similarity future policies fill the candidate window, an effective current policy ranked below that window is never returned, and the facade incorrectly reports `no_evidence`. The existing effective-time test mocks the repository with both candidates and does not exercise this truncation path.
**Fix:** Pass `effective_date` into `PolicyChunkRepository.search_similar` and apply `PolicyChunk.effective_date <= effective_date` in SQL before ordering and limiting. Add a repository/integration test where future rows fill the initial top-k but a valid current row must still be returned.

### WR-03: `allow_partial_evidence=False` Is Ignored

**File:** `src/knowledge/service.py:55-64`
**Issue:** The public request contract exposes `allow_partial_evidence`, but the service returns `partial_evidence` unchanged regardless of the flag. A caller explicitly requiring strong evidence can therefore receive and act on partial evidence.
**Fix:** When the adapter returns `partial_evidence` and `request.allow_partial_evidence` is false, return `no_evidence` with empty evidence refs, or reject the unsupported option explicitly. Add tests covering both flag values.

---

_Reviewed: 2026-06-07T07:18:11Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
