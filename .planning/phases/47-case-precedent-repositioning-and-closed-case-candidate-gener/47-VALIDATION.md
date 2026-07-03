---
phase: 47
slug: case-precedent-repositioning-and-closed-case-candidate-gener
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-03
---

# Phase 47 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 with pytest-asyncio 1.3.0 in the active uv environment |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"` |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_memory_policy.py -x -q` |
| Focused Phase 47 command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_case_memory_retrieval.py tests/memory/test_case_precedent_generation.py tests/memory/test_memory_policy.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_reviewed_memory_context_boundary.py tests/test_memory_review_api.py tests/tools/test_catalog.py -q` |
| Estimated runtime | ~120 seconds for the current focused Phase 47 suite |

---

## Sampling Rate

- **After every task commit:** Run the task's `<verify><automated>` command. Commands must use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`; bare `pytest` and bare `python -m pytest` are invalid verification.
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_memory_policy.py tests/test_memory_review_api.py -q`.
- **Before `$gsd-verify-work 47`:** Run the focused Phase 47 command and `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check` on touched Python and test files.
- **Max feedback latency:** 120 seconds for scoped memory checks.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 47-01-01 | 01 | 1 | MEM-04 | T-47-03 / T-47-04 | `case_memories` is locked as reviewed precedent and protected tables are not destructively renamed or dropped | static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py -x -q` | yes | green |
| 47-01-02 | 01 | 1 | MEM-04 | T-47-03 | `closed_case_cwc_candidate` is review-required and not auto-approved | unit/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_memory_policy.py -x -q` | yes | green |
| 47-02-01 | 02 | 2 | MEM-04 | T-47-01 / T-47-06 | Non-terminal close statuses skip without creating `case_memories` rows | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` | yes | green |
| 47-02-02 | 02 | 2 | MEM-04 | T-47-02 / T-47-04 | Projection uses allowlisted CWC summaries and blocks raw PII, raw tool payloads, policy body text, authority bodies, and replay/debug blobs | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_phase47_case_precedent_alignment.py -x -q` | yes | green |
| 47-03-01 | 03 | 3 | MEM-04 | T-47-01 / T-47-02 / T-47-05 | Terminal trusted close creates one `needs_review` candidate through existing `CaseMemoryService` review/audit path | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` | yes | green |
| 47-03-02 | 03 | 3 | MEM-04 | T-47-05 | Duplicate close/CWC/source identity dedupes via existing duplicate handling and emits or preserves observable write-event behavior | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` | yes | green |
| 47-03-03 | 03 | 3 | MEM-04 | T-47-03 | Generated candidates are pending-review visible but invisible to reviewed retrieval until approved | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/test_memory_review_api.py -x -q` | yes | green |
| 47-04-01 | 04 | 4 | MEM-04 | T-47-02 / T-47-04 | Merchant-scope and exact case-scope metadata/text retrieval works without embeddings and keeps tenant/PII filters | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/tools/test_catalog.py -x -q` | yes | green |
| 47-04-02 | 04 | 4 | MEM-04 | T-47-04 / T-47-06 | Contract docs, implementation map, and Phase 48 DEFER-3 trace remain aligned without implementing preference memory | static/docs | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py -x -q` | yes | green |

*Status: pending / green / red / flaky.*

---

## Wave 0 Requirements

- [x] `tests/memory/test_phase47_case_precedent_alignment.py` - static semantic lock, destructive-schema guard, source-type policy guard, forbidden payload/import guard, approved pytest-command guard, and DEFER-3 carry-forward guard.
- [x] `tests/memory/test_case_precedent_generation.py` - behavioral tests for trusted close seam, active CWC read, projection, skip reasons, idempotency, review gate, PII block, and merchant-scope retrieval.
- [x] `tests/memory/test_memory_policy.py` - add `closed_case_cwc_candidate` review-required and not-auto-approved coverage.
- [x] Add generated-precedent review/retrieval assertions to existing retrieval/review tests only if `test_case_precedent_generation.py` cannot cover the behavior without duplication.

---

## Threat References

| Threat Ref | Threat | Required Mitigation |
|------------|--------|---------------------|
| T-47-01 | Spoofed or premature close event creates precedent before real case closure | Internal trusted seam, explicit terminal status allowlist, no public close endpoint, skip non-terminal statuses |
| T-47-02 | Cross-tenant or wrong-merchant precedent retrieval | Preserve tenant filters, resolve merchant through `RefundCase -> Order.merchant_id`, keep source case identity in `source_ref_json` |
| T-47-03 | Generated candidate bypasses reviewer governance | `closed_case_cwc_candidate` is review-required, retrieval excludes `needs_review`, review API remains the publication path |
| T-47-04 | Raw PII, raw tool payload, policy body, authority body, or replay/debug blob leaks into precedent | Deterministic allowlist projection, policy PII block, prompt-safe retrieval guard, static forbidden-payload tests |
| T-47-05 | Duplicate close events create repeated precedents | Reuse source/content identity hashes, duplicate checks, tombstone checks, and write events |
| T-47-06 | CWC claims become verified facts, policy authority, or action authority | Keep claims and verified facts separate and include fixed caveats that precedent is not policy/action/current-state authority |

---

## Manual-Only Verifications

All Phase 47 success criteria should have automated verification. Product confirmation of the exact terminal refund-case status allowlist is a planning assumption, not a manual verification gate.

## Validation Audit 2026-07-04

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Tests added | 0 |
| Resolved by new tests | 0 |
| Escalated | 0 |

| Coverage Point | Evidence | Status |
|----------------|----------|--------|
| WR-01: distinct same-merchant closed precedents do not collapse while identical projected content dedupes | `tests/memory/test_case_precedent_generation.py::test_same_merchant_closed_cases_with_distinct_projected_content_create_separate_candidates`, `tests/memory/test_case_precedent_generation.py::test_different_close_event_with_same_content_dedupes_by_content_hash_reason`, and `src/memory/case_memory.py::_candidate_content_identity_text` | green |
| WR-02: reviewed-memory node filters generated precedents by `issue_type`, not `primary_intent` | `tests/agent/test_reviewed_memory_context_retrieve.py::test_reviewed_memory_context_retrieve_real_service_uses_issue_type_not_primary_intent` and `src/agent/nodes/reviewed_memory_context_retrieve.py::_case_type` | green |
| Appendix cleanup: `case_memories` storage model matches scope-based ORM and rejects legacy fields | `docs/contract-spec.md` `case_memories` appendix and `tests/memory/test_phase47_case_precedent_alignment.py::test_contract_case_memory_storage_model_matches_scope_based_orm` | green |
| Security/UAT consistency | `47-SECURITY.md` has `threats_open: 0`; `47-UAT.md` has 6/6 self-verified backend UAT checks passing; both rely on the same focused Phase 47 suite shape | green |

## Final Automated Results

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_case_memory_retrieval.py tests/memory/test_case_precedent_generation.py tests/memory/test_memory_policy.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_reviewed_memory_context_boundary.py tests/test_memory_review_api.py tests/tools/test_catalog.py -q` -> `123 passed, 1 warning in 118.14s (0:01:58)`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py -q` -> `11 passed, 1 warning in 0.03s`.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/nodes/reviewed_memory_context_retrieve.py src/memory/case_memory.py src/memory/case_precedent.py src/memory/policy.py src/memory/schemas.py src/repositories/refund_repo.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_case_memory_retrieval.py tests/memory/test_case_precedent_generation.py tests/memory/test_memory_policy.py tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_reviewed_memory_context_boundary.py tests/test_memory_review_api.py tests/tools/test_catalog.py` -> `All checks passed!`.

The pytest warning is the existing LangGraph/LangChain pending deprecation warning from `.venv/lib/python3.12/site-packages/langgraph/checkpoint/serde/encrypted.py`.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing test files listed above.
- [x] No watch-mode flags.
- [x] Feedback latency < 120 seconds for scoped memory checks.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** green after post-review Nyquist audit on 2026-07-04.
