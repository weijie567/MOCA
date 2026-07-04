---
phase: 48-narrow-long-term-explicit-preference-memory
reviewed: 2026-07-04T02:21:10Z
depth: deep
files_reviewed: 25
files_reviewed_list:
  - docs/architecture-overview.md
  - docs/contract-spec.md
  - docs/memory-contract-delta.md
  - src/agent/nodes/memory_write.py
  - src/api/routers/memory.py
  - src/api/schemas/memory.py
  - src/auth/jwt.py
  - src/auth/permissions.py
  - src/memory/long_term.py
  - src/memory/policy.py
  - src/memory/preference_capture.py
  - src/memory/repository.py
  - src/memory/schemas.py
  - src/memory/semantic_episode.py
  - src/memory/write_service.py
  - tests/agent/test_memory_write_node.py
  - tests/architecture/test_memory_contract_delta.py
  - tests/memory/test_long_term_memory_repository.py
  - tests/memory/test_long_term_memory_service.py
  - tests/memory/test_memory_policy.py
  - tests/memory/test_memory_write_service.py
  - tests/memory/test_phase48_long_term_preference_alignment.py
  - tests/memory/test_reviewed_memory_context_boundary.py
  - tests/memory/test_semantic_episode_projection.py
  - tests/test_memory_review_api.py
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 48: Code Review Report

**Reviewed:** 2026-07-04T02:21:10Z
**Depth:** deep
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Deep re-review covered the Phase 48 memory contract docs, long-term preference write/retrieval path, memory write facade, review API, auth scope changes, semantic episode projection, and tests. The admin-only memory review fix is present: `MEMORY_REVIEW_ROLES` is now admin-only and the API tests cover manager/support rejection.

One current warning remains in the state-origin case-memory provenance gate. The latest fix rejects untrusted case-scoped closed-case candidates, but merchant-scoped state candidates can still enter review without the required closed-case source identity.

## Warnings

### WR-01: Merchant-scoped state case candidates can bypass closed-case source provenance

**File:** `/Users/ming/projects/MOCA/src/memory/write_service.py:336`
**Issue:** `_state_case_candidate_allowed` accepts merchant-scoped review-required case candidates when trusted merchant scope allows the merchant, but it does not require a `source_ref` for `closed_case_cwc_candidate`. A state-provided candidate with `scope_type="merchant"`, `source_type="closed_case_cwc_candidate"`, and no `source_ref` is therefore proposed as a pending case memory candidate. Downstream, `CaseMemoryService._candidate_source_ref_json` stores only `{"source_type": ...}` when `source_ref` is absent, so the pending memory loses the normalized closed-case provenance required by the memory contract. This is not an immediate prompt-injection path because the candidate still needs review, but it weakens the review/audit boundary and can publish provenance-free case memory if approved.
**Fix:** Require closed-case source provenance before accepting state-origin `closed_case_cwc_candidate` for both merchant and case scopes. Keep the merchant trusted-scope check, but make it additional to source identity validation. Add a regression test for `scope_type="merchant"` with missing or incomplete `source_ref`.

```python
def _state_case_candidate_allowed(
    candidate: CaseMemoryWriteCandidate,
    *,
    trusted_context: Any | None,
) -> bool:
    if candidate.source_type not in REVIEW_REQUIRED_CASE_SOURCE_TYPES:
        return False
    if candidate.source_type == "closed_case_cwc_candidate" and not _closed_case_source_ref_allowed(candidate):
        return False
    if candidate.scope_type == "merchant":
        return _trusted_merchant_scope_allows(candidate.scope_id, trusted_context=trusted_context)
    if candidate.scope_type == "case":
        return candidate.source_ref is not None and candidate.source_ref.business_object_id == candidate.scope_id
    return False


def _closed_case_source_ref_allowed(candidate: CaseMemoryWriteCandidate) -> bool:
    source_ref = candidate.source_ref
    return (
        source_ref is not None
        and source_ref.business_object_type == "refund_case"
        and bool(source_ref.business_object_id)
        and bool(source_ref.event_id)
    )
```

## Verification

Targeted existing tests pass with the project-approved entrypoint:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_memory_write_service.py::test_memory_write_service_rejects_untrusted_case_state_candidates tests/test_memory_review_api.py::test_memory_review_api_requires_admin_role
```

Result: 6 passed, 1 warning. A targeted one-off probe against `MemoryWriteService.propose_candidates` confirmed the remaining merchant-scope gap by returning a `CaseMemoryWriteCandidate` with `source_ref=None`.

---

_Reviewed: 2026-07-04T02:21:10Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
