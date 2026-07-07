---
phase: 58
slug: canonical-graph-cutover-and-no-debt-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-08
---

# Phase 58 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio 1.3.0; frontend build via npm/Vite |
| **Config file** | `pyproject.toml`; frontend scripts in `frontend/package.json` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py -q --tb=short` |
| **Full suite command** | See "Phase Gate Commands" below |
| **Estimated runtime** | ~6-8 minutes for broad backend suite plus frontend build, based on Phase 57 closeout timing |

---

## Sampling Rate

- **After every task commit:** Run the focused command for the changed ownership boundary.
- **After every plan wave:** Run graph baseline, graph vocabulary, and impacted API/node suites.
- **Before `$gsd-verify-work`:** Broad phase gate, static classifier, ruff, frontend build, and `git diff --check` must be green.
- **Max feedback latency:** focused suites should stay under 180 seconds where possible; broad closeout may exceed this.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 58-01-01 | 01 | TBD | CAGM-09 | T-58-01 / T-58-05 | Active graph nodes/routes stay canonical and main graph vocabulary stops advertising active runtime compatibility aliases. | architecture/static/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py -q --tb=short` | yes | pending |
| 58-02-01 | 02 | TBD | CAGM-09 | T-58-05 | Legacy wrapper/import-test surfaces are deleted or moved behind canonical/private implementation modules without resurrecting old graph names. | unit/import/static | Planner must set final command after test/file rename; current candidates include `tests/agent/test_nodes/test_risk_gate.py`, `tests/agent/test_nodes/test_generate_recommendation.py`, and `tests/agent/test_phase22_action_boundary.py`. | partial | pending |
| 58-03-01 | 03 | TBD | CAGM-09 | T-58-02 / T-58-03 | Current-run trace/API/SSE/frontend/eval surfaces use canonical names; historical rows remain readable only through bounded historical projection. | API/integration/frontend/eval | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/eval/test_phase35_replay_eval_gates.py tests/eval/test_phase35_release_monitoring_manifests.py -q --tb=short` and `npm --prefix frontend run build` | yes | pending |
| 58-04-01 | 04 | TBD | CAGM-09 | T-58-01 / T-58-04 | Historical approval retry metadata never authorizes a legacy graph resume; graph/API output emits canonical `risk_gate` only. | API/security/routing | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short` | yes | pending |
| 58-05-01 | 05 | TBD | CAGM-09 | T-58-02 / T-58-06 | Docs, architecture debt, and final classifier prove zero active-runtime legacy debt and zero unclassified rows. | docs/static | `UV_CACHE_DIR=/tmp/uv-cache uv run python <phase58_static_classifier>` and `UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check` | classifier TBD | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] Activate `tests/architecture/test_canonical_graph_baseline.py::test_final_no_debt_gate_is_marked_phase58_scope` as a real final no-debt assertion.
- [ ] Add or update a Phase 58 static legacy-hit classifier that reports total hits, file count, category counts, zero active-runtime legacy hits, zero unclassified rows, and explicit generated-artifact exclusions.
- [ ] Rename or rewrite test files whose filenames encode deleted legacy node names if wrapper modules are removed.

---

## Phase Gate Commands

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest \
  tests/architecture/test_canonical_graph_baseline.py \
  tests/architecture/test_phase32_static_contract.py \
  tests/architecture/test_memory_contract_delta.py \
  tests/architecture/test_phase33_rag_claim_boundaries.py \
  tests/architecture/test_phase34_approval_action_boundaries.py \
  tests/architecture/test_approval_boundaries.py \
  tests/agent/test_graph.py \
  tests/test_graph_routing.py \
  tests/agent/test_graph_vocabulary.py \
  tests/agent/test_trace.py \
  tests/test_trace_api.py \
  tests/test_agent_runs_api.py \
  tests/test_approval_api.py \
  tests/test_approval_gate.py \
  tests/approvals/test_needs_info_resume.py \
  tests/approvals/test_service_transitions.py \
  tests/agent/test_nodes/test_contextual_intent_resolve.py \
  tests/agent/test_nodes/test_slot_resolution_gate.py \
  tests/agent/test_memory_context_load.py \
  tests/agent/test_nodes/test_risk_gate.py \
  tests/agent/test_phase22_action_boundary.py \
  tests/actions/test_phase34_action_draft_bindings.py \
  tests/eval/test_phase35_replay_eval_gates.py \
  tests/eval/test_phase35_release_monitoring_manifests.py \
  -q --tb=short

UV_CACHE_DIR=/tmp/uv-cache uv run ruff check \
  src/agent src/api src/approvals src/repositories \
  tests/architecture tests/agent tests/test_graph_routing.py \
  tests/test_agent_runs_api.py tests/test_trace_api.py tests/test_approval_api.py tests/test_approval_gate.py

npm --prefix frontend run build
UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check
```

Planner/executor must update these commands if wrapper deletion renames or removes legacy test files.

---

## Static Legacy-Hit Classifier Contract

The final classifier must scan at least:

- `classify_intent`
- `session_memory_load`
- `extract_slots`
- `long_term_memory_retrieve`
- `generate_recommendation`
- `assess_risk_and_approval`
- `route_after_intent`
- `route_after_slots`

Required outputs:

- total hits and files scanned
- category counts by ownership boundary
- zero active-runtime legacy hits
- zero unclassified rows
- explicit exclusions for generated Phase 58 validation/research artifacts to avoid recursive self-counting

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Production historical DB row counts for old graph node names | CAGM-09 | Research did not connect to production or sample DB state. The phase decision forbids bulk rewrite, so source tests can prove behavior without requiring DB mutation. | Optional release checklist item only: if production observability is available, query counts for historical node names and confirm they are read-only historical rows, not current-run writes. |

---

## Threat References

| Threat Ref | STRIDE | Required Mitigation |
|------------|--------|---------------------|
| T-58-01 | Spoofing / Elevation of privilege | Legacy route values such as `assess_risk_and_approval` must not be accepted as graph resume authority; canonical `risk_gate` only. |
| T-58-02 | Repudiation / Tampering | Historical trace/replay readability must not be presented as current runtime graph behavior. |
| T-58-03 | Tampering | Current-run API/SSE/frontend/eval projections must not reintroduce legacy graph names as current labels. |
| T-58-04 | Elevation of privilege | Approval retry canonicalization must preserve tenant/run/hash/snapshot/version validation. |
| T-58-05 | Tampering / Maintainability | Deleted legacy wrappers must not be resurrected through tests, eval patch paths, or import convenience aliases. |
| T-58-06 | Repudiation | Docs and architecture debt must distinguish target contract, implemented current state, and historical references. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing references.
- [ ] No watch-mode flags.
- [ ] Feedback latency < 180s for focused suites.
- [ ] `nyquist_compliant: true` set in frontmatter after approved command evidence is recorded.

**Approval:** pending
