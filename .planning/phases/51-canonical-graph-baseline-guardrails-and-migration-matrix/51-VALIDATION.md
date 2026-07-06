---
phase: 51
slug: canonical-graph-baseline-guardrails-and-migration-matrix
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-06
---

# Phase 51 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` via project `uv` environment |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/architecture/test_canonical_graph_baseline.py -q` |
| **Full suite command** | `uv run pytest tests/architecture -q` |
| **Estimated runtime** | ~20-60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/architecture/test_canonical_graph_baseline.py -q`
- **After every plan wave:** Run the plan-specific architecture command listed below
- **Before `$gsd-verify-work`:** `uv run pytest tests/architecture -q` and `git diff --check` must pass
- **Max feedback latency:** 60 seconds for the focused Phase 51 test file

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 51-01-01 | 01 | 0 | CAGM-02 | — | Static helpers parse source without importing graph/runtime providers | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py -q` | ✅ | ✅ green |
| 51-01-02 | 01 | 1 | CAGM-02 | — | Target 15-node canonical set and current 14-node baseline are explicit constants | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_target_canonical_graph_node_set_is_exact_phase50_contract -q` | ✅ | ✅ green |
| 51-01-03 | 01 | 1 | CAGM-02 | — | Migration-mode matrix maps every active legacy node to a canonical owner and deletion phase | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_migration_mode_maps_every_active_legacy_node_to_target -q` | ✅ | ✅ green |
| 51-02-01 | 02 | 1 | CAGM-02 | — | Current registered graph nodes are source-verified from `builder.add_node(...)` | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_current_active_graph_node_set_matches_phase51_baseline -q` | ✅ | ✅ green |
| 51-02-02 | 02 | 1 | CAGM-02 | — | Router path maps, return values, and legacy destinations are source-verified in migration mode | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_router_return_values_are_covered_by_registered_path_maps -q` | ✅ | ✅ green |
| 51-02-03 | 02 | 1 | CAGM-02 | — | Forbidden helper/lifecycle names cannot drift into registered main-chain graph nodes | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_forbidden_internal_or_lifecycle_names_are_not_registered_graph_nodes -q` | ✅ | ✅ green |
| 51-02-04 | 02 | 1 | CAGM-02 | — | `slot_extraction` drift fails with instructions to update contract docs before promotion | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_slot_extraction_drift_is_explicitly_rejected -q` | ✅ | ✅ green |
| 51-02-05 | 02 | 1 | CAGM-02 | — | Final exact no-debt gate is present but skipped/xfail until Phase 58 | architecture/static | `uv run pytest tests/architecture/test_canonical_graph_baseline.py::test_final_no_debt_gate_is_marked_phase58_scope -q` | ✅ | ✅ skipped by design |
| 51-03-01 | 03 | 1 | CAGM-02 | — | Planning ledger records that runtime graph remains legacy/canonical mixed until later phases | docs/static | `git diff --check` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/architecture/graph_baseline.py` or equivalent helper/constants module.
- [x] `tests/architecture/test_canonical_graph_baseline.py` with stubs or first complete tests for CAGM-02.
- [x] No new test framework installation required; existing `pytest` / `uv` infrastructure covers this phase.

---

## Manual-Only Verifications

All Phase 51 behaviors have automated or static verification. Manual review is still required for plan quality and architecture-debt wording, but no user-facing runtime flow needs manual testing in this phase.

---

## Validation Sign-Off

### Command Results

- `uv run pytest tests/architecture/test_canonical_graph_baseline.py -q` — passed: 9 passed, 1 skipped, 1 warning.
- `uv run pytest tests/architecture -q` — passed: 79 passed, 2 skipped, 1 warning.
- `uv run ruff check tests/architecture/graph_baseline.py tests/architecture/test_canonical_graph_baseline.py` — passed.
- `git diff --check` — passed.
- `git diff --exit-code -- src/agent/graph.py src/agent/routing.py src/agent/graph_vocabulary.py` — passed; protected runtime graph files no diff.
- `51-REVIEW.md` — clean code review; 0 critical, 0 warning, 0 info findings after guardrail false-negative fixes.

Phase 51 made no runtime graph behavior change. The active runtime graph remains legacy/canonical mixed until Phases 52-58 migrate and clean it up; the final exact no-debt gate remains Phase 58 scope.

- [x] All tasks have automated verify commands or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing test-file references
- [x] No watch-mode flags
- [x] Feedback latency target is under 60 seconds for focused Phase 51 checks
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-06
