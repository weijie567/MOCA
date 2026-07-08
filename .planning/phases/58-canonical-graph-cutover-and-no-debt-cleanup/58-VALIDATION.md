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
| **Framework** | pytest 9.0.3 with pytest-asyncio 1.3.0; frontend build/test via npm/Vite/Vitest |
| **Config file** | `pyproject.toml`; frontend scripts in `frontend/package.json` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py -q --tb=short` |
| **Full suite command** | See "Phase Gate Commands" below |
| **Estimated runtime** | ~6-9 minutes for broad backend suite plus frontend build/test, based on Phase 57 closeout timing |

---

## Sampling Rate

- **After every task commit:** Run the focused command for the changed ownership boundary.
- **After every plan wave:** Run graph baseline, graph vocabulary, and impacted API/node suites.
- **Before `$gsd-verify-work`:** Broad phase gate, static classifier, ruff, frontend build, frontend test, tracked metadata proof, and `git diff --check` must be green.
- **Max feedback latency:** focused suites should stay under 180 seconds where possible; broad closeout may exceed this.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 58-01-01 | 01 | 1 | CAGM-09 | T-58-01 / T-58-05 | Active graph nodes/routes stay canonical, legacy route delegates stop being public current route authority, and main graph vocabulary stops advertising active runtime compatibility aliases. | architecture/static/unit/routing | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_intent_golden_contract.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py -q --tb=short` | yes | pending |
| 58-02-01 | 02 | 2 | CAGM-09 | T-58-05 | Recommendation and risk implementation ownership moves into canonical modules with current-run canonical identity and direct test filenames migrate to canonical names. | unit/import/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_recommendation_generation.py tests/agent/test_nodes/test_risk_gate.py -q --tb=short` | after 58-02 | pending |
| 58-03-01 | 03 | 3 | CAGM-09 | T-58-05 | Recommendation/risk legacy wrappers are deleted, direct tests use canonical filenames/imports, and static guards block wrapper resurrection. | unit/import/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_recommendation_generation.py tests/agent/test_nodes/test_risk_gate.py tests/architecture/test_phase33_rag_claim_boundaries.py -q --tb=short` | after 58-03 | pending |
| 58-04-01 | 04 | 4 | CAGM-09 | T-58-05 | Intent/session legacy wrappers/helpers are deleted or internalized, and direct legacy-named tests are migrated to canonical suites. | unit/import/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_contextual_intent_resolve.py tests/agent/test_nodes/test_session_context_load.py tests/agent/test_intent_adapter.py -q --tb=short` | after 58-04 | pending |
| 58-05-01 | 05 | 5 | CAGM-09 | T-58-05 | Slot/memory legacy wrappers/helpers are deleted or internalized, and direct legacy-named tests are migrated to canonical suites. | unit/import/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_slot_resolution_gate.py tests/agent/test_memory_context_load.py -q --tb=short` | after 58-05 | pending |
| 58-06-01 | 06 | 6 | CAGM-09 | T-58-05 | Graph/routing/shared fixture patch seams use canonical modules and public canonical route helpers only. | graph/routing/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_intent_routing.py tests/agent/test_intent_golden_contract.py tests/agent/test_required_slots.py tests/agent/test_session_memory_integration.py tests/agent/test_empty_session_adapter.py -q --tb=short` | yes | pending |
| 58-07-01 | 07 | 7 | CAGM-09 | T-58-05 | Integration and architecture import coverage uses canonical modules and static guards reject deleted wrapper/test paths. | integration/architecture/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_action_boundary.py tests/test_interception_rate.py tests/knowledge/test_facade_integration.py tests/agent/test_memory_evidence_boundary.py tests/architecture/test_phase32_static_contract.py tests/architecture/test_memory_contract_delta.py tests/architecture/test_phase33_rag_claim_boundaries.py -q --tb=short` | yes | pending |
| 58-08-01 | 08 | 8 | CAGM-09 | T-58-02 / T-58-03 | Current-run trace/API/SSE/frontend/eval surfaces use canonical names; historical rows remain readable only through bounded historical projection. | API/integration/frontend/eval | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/eval/test_phase35_replay_eval_gates.py tests/eval/test_phase35_release_monitoring_manifests.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short`, `npm --prefix frontend run build`, and `npm --prefix frontend run test` | yes | pending |
| 58-09-01 | 09 | 8 | CAGM-09 | T-58-01 / T-58-04 | Historical approval retry metadata never authorizes a legacy graph resume; graph/API output emits canonical `risk_gate` only. | API/security/routing | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short` | yes | pending |
| 58-10-01 | 10 | 9 | CAGM-09 | T-58-02 / T-58-06 | Docs, architecture debt, final classifier, and tracked metadata proof show zero active-runtime legacy debt, zero current-docs legacy authority, and zero unclassified rows. | docs/static/metadata | `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict`, tracked `moca.egg-info/SOURCES.txt` proof command, and `UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check` | after 58-01 | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] Activate `tests/architecture/test_canonical_graph_baseline.py::test_final_no_debt_gate_is_marked_phase58_scope` as a real final no-debt assertion.
- [ ] Remove or internalize public `route_after_intent` and `route_after_slots` route delegates and prove canonical route helpers still behave the same.
- [ ] Add or update a Phase 58 static legacy-hit classifier that reports total hits, file count, category counts, zero active-runtime legacy hits, zero current-docs legacy authority hits if tracked separately, zero unclassified rows, and explicit generated-artifact exclusions.
- [ ] Preserve the strict-mode rule that `--strict` fails on active/current/unclassified rows but does not require `total_hits == 0`.
- [ ] Rename or rewrite test files whose filenames encode deleted legacy node names when wrapper modules are removed across Plans 58-03 through 58-05.

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
  tests/agent/test_intent_routing.py \
  tests/agent/test_intent_golden_contract.py \
  tests/agent/test_required_slots.py \
  tests/agent/test_session_memory_integration.py \
  tests/agent/test_graph_vocabulary.py \
  tests/agent/test_trace.py \
  tests/test_trace_api.py \
  tests/test_agent_runs_api.py \
  tests/test_approval_api.py \
  tests/test_approval_gate.py \
  tests/approvals/test_needs_info_resume.py \
  tests/approvals/test_service_transitions.py \
  tests/agent/test_nodes/test_contextual_intent_resolve.py \
  tests/agent/test_nodes/test_session_context_load.py \
  tests/agent/test_nodes/test_slot_resolution_gate.py \
  tests/agent/test_memory_context_load.py \
  tests/agent/test_nodes/test_recommendation_generation.py \
  tests/agent/test_nodes/test_risk_gate.py \
  tests/agent/test_phase22_recommendation_integration.py \
  tests/agent/test_phase22_action_boundary.py \
  tests/test_interception_rate.py \
  tests/knowledge/test_facade_integration.py \
  tests/agent/test_memory_evidence_boundary.py \
  tests/actions/test_phase34_action_draft_bindings.py \
  tests/eval/test_phase35_replay_eval_gates.py \
  tests/eval/test_phase35_release_monitoring_manifests.py \
  -q --tb=short

UV_CACHE_DIR=/tmp/uv-cache uv run ruff check \
  src/agent src/api src/approvals src/repositories \
  scripts/classify_phase58_legacy_hits.py scripts/eval_agent.py scripts/diagnose_latency.py \
  tests/architecture tests/agent tests/test_graph_routing.py \
  tests/test_interception_rate.py tests/knowledge \
  tests/test_agent_runs_api.py tests/test_trace_api.py tests/test_approval_api.py tests/test_approval_gate.py tests/eval

npm --prefix frontend run build
npm --prefix frontend run test
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/classify_phase58_legacy_hits.py --strict
git ls-files --error-unmatch moca.egg-info/SOURCES.txt >/dev/null 2>&1 && ! rg -n "src/agent/nodes/(generate_recommendation|assess_risk_and_approval|classify_intent|session_memory_load|extract_slots|long_term_memory_retrieve)\\.py|tests/agent/test_nodes/test_(generate_recommendation|assess_risk_and_approval|classify_intent|extract_slots)\\.py|tests/agent/test_session_memory_load\\.py" moca.egg-info/SOURCES.txt || ! git ls-files --error-unmatch moca.egg-info/SOURCES.txt >/dev/null 2>&1
UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check
```

The closeout suite intentionally uses canonical replacement paths such as `tests/agent/test_nodes/test_recommendation_generation.py`, `tests/agent/test_nodes/test_session_context_load.py`, and `tests/agent/test_nodes/test_memory_context_load.py`. Legacy-named direct tests should be gone by Plans 58-03 through 58-05 unless a plan summary records an explicit internal/historical-only classifier category.

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
- zero current-docs legacy authority hits when tracked as a separate strict-failing category
- zero unclassified rows
- explicit exclusions for generated Phase 58 validation/research artifacts to avoid recursive self-counting
- `--strict` does not require `total_hits == 0`; legitimate historical/reference/classifier rows may remain when classified
- tracked metadata rows, including `moca.egg-info/SOURCES.txt`, are removed or categorized so stale deleted module/test paths cannot survive as active/current references

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
