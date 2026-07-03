---
phase: 47
slug: case-precedent-repositioning-and-closed-case-candidate-gener
status: draft
nyquist_compliant: true
wave_0_complete: false
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
| Full suite command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_memory_policy.py tests/test_memory_review_api.py tests/agent/test_case_working_context_lifecycle.py tests/agent/test_reviewed_memory_context_retrieve.py tests/tools/test_catalog.py -q` |
| Estimated runtime | ~60-120 seconds once new Phase 47 tests exist |

---

## Sampling Rate

- **After every task commit:** Run the task's `<verify><automated>` command. Commands must use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`; bare `pytest` and bare `python -m pytest` are invalid verification.
- **After every plan wave:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_memory_policy.py tests/test_memory_review_api.py -q`.
- **Before `$gsd-verify-work 47`:** Run the full suite command and `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check` on touched Python and test files.
- **Max feedback latency:** 120 seconds for scoped memory checks.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 47-01-01 | 01 | 1 | MEM-04 | T-47-03 / T-47-04 | `case_memories` is locked as reviewed precedent and protected tables are not destructively renamed or dropped | static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py -x -q` | no - Wave 0 | pending |
| 47-01-02 | 01 | 1 | MEM-04 | T-47-03 | `closed_case_cwc_candidate` is review-required and not auto-approved | unit/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py tests/memory/test_memory_policy.py -x -q` | partial | pending |
| 47-02-01 | 02 | 2 | MEM-04 | T-47-01 / T-47-06 | Non-terminal close statuses skip without creating `case_memories` rows | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` | no - Wave 0 | pending |
| 47-02-02 | 02 | 2 | MEM-04 | T-47-02 / T-47-04 | Projection uses allowlisted CWC summaries and blocks raw PII, raw tool payloads, policy body text, authority bodies, and replay/debug blobs | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_phase47_case_precedent_alignment.py -x -q` | no - Wave 0 | pending |
| 47-03-01 | 03 | 3 | MEM-04 | T-47-01 / T-47-02 / T-47-05 | Terminal trusted close creates one `needs_review` candidate through existing `CaseMemoryService` review/audit path | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` | no - Wave 0 | pending |
| 47-03-02 | 03 | 3 | MEM-04 | T-47-05 | Duplicate close/CWC/source identity dedupes via existing duplicate handling and emits or preserves observable write-event behavior | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py -x -q` | no - Wave 0 | pending |
| 47-03-03 | 03 | 3 | MEM-04 | T-47-03 | Generated candidates are pending-review visible but invisible to reviewed retrieval until approved | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/test_memory_review_api.py -x -q` | partial | pending |
| 47-04-01 | 04 | 4 | MEM-04 | T-47-02 / T-47-04 | Merchant-scope and exact case-scope metadata/text retrieval works without embeddings and keeps tenant/PII filters | integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_case_precedent_generation.py tests/memory/test_case_memory_retrieval.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_reviewed_memory_context_retrieve.py tests/tools/test_catalog.py -x -q` | partial | pending |
| 47-04-02 | 04 | 4 | MEM-04 | T-47-04 / T-47-06 | Contract docs, implementation map, and Phase 48 DEFER-3 trace remain aligned without implementing preference memory | static/docs | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase47_case_precedent_alignment.py -x -q` | no - Wave 0 | pending |

*Status: pending / green / red / flaky.*

---

## Wave 0 Requirements

- [ ] `tests/memory/test_phase47_case_precedent_alignment.py` - static semantic lock, destructive-schema guard, source-type policy guard, forbidden payload/import guard, approved pytest-command guard, and DEFER-3 carry-forward guard.
- [ ] `tests/memory/test_case_precedent_generation.py` - behavioral tests for trusted close seam, active CWC read, projection, skip reasons, idempotency, review gate, PII block, and merchant-scope retrieval.
- [ ] `tests/memory/test_memory_policy.py` - add `closed_case_cwc_candidate` review-required and not-auto-approved coverage.
- [ ] Add generated-precedent review/retrieval assertions to existing retrieval/review tests only if `test_case_precedent_generation.py` cannot cover the behavior without duplication.

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

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing test files listed above.
- [ ] No watch-mode flags.
- [ ] Feedback latency < 120 seconds for scoped memory checks.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending
