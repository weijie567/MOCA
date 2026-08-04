---
phase: 57
slug: risk-gate-and-approval-gate-canonicalization
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-07
completed: 2026-07-07
---

# Phase 57 - Validation Strategy

> Per-phase validation contract and closeout evidence for CAGM-08.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/agent/test_graph.py tests/test_graph_routing.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_phase34_approval_action_boundaries.py tests/architecture/test_approval_boundaries.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_phase22_action_boundary.py tests/test_approval_gate.py tests/test_approval_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py tests/agent/test_graph_vocabulary.py tests/test_agent_runs_api.py tests/agent/test_trace.py tests/test_trace_api.py -q --tb=short` |
| **Estimated runtime** | ~5 minutes locally after 57-05 closeout |

## Five-Plan Wave Map

| Plan | Wave | Closeout role | Summary evidence |
|------|------|---------------|------------------|
| 57-01 | wave 1 | Canonical `risk_gate` callable and Phase 58-scoped legacy wrapper/import compatibility. | `57-01-SUMMARY.md` |
| 57-02 | wave 2 | Active graph/router/baseline cutover to current-run `risk_gate` route values. | `57-02-SUMMARY.md` |
| 57-03 | wave 3 | Trusted approval edit resume canonicalization and ordinary-chat approval boundary hardening. | `57-03-SUMMARY.md` |
| 57-04 | wave 4 | Runtime vocabulary/API/frontend/eval/diagnostic projection closeout. | `57-04-SUMMARY.md` |
| 57-05 | wave 5 | Docs, architecture debt, validation artifact, and static legacy-hit classification closeout. | `57-05-SUMMARY.md` |

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 57-01-01 | 01 | 1 | CAGM-08 | T-57-05 | Canonical callable emits current-run `risk_gate` identity while legacy surface is compatibility-only. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q --tb=short` | yes | green |
| 57-02-01 | 02 | 2 | CAGM-08 | T-57-05 | Active graph registers `risk_gate`, claim routing and approval edit rerisk route maps target canonical node, and impacted approval service tests expect `risk_gate`. | architecture/integration/service | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/rag_context/test_routing.py tests/test_approval_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py -q --tb=short` | yes | green |
| 57-03-01 | 03 | 3 | CAGM-08 | T-57-01 / T-57-03 | Trusted edit resume reroutes to `risk_gate`; ordinary chat cannot produce trusted approval. | API/service/safety | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py tests/agent/test_intent_routing.py -q --tb=short` | yes | green |
| 57-04-01 | 04 | 4 | CAGM-08 | T-57-05 | Current-run vocabulary/API/frontend/eval/diagnostics use `risk_gate`; legacy key is projection compatibility only. | projection/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short` plus `npm --prefix frontend run build` | yes | green |
| 57-05-01 | 05 | 5 | CAGM-08 | T-57-05 | Docs, architecture debt, validation artifact, and static legacy-hit classification distinguish current authority from historical compatibility. | docs/static | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "... assert not missing; assert not bad ..."` and scoped tracked-file classifier below | yes | green |

## Final Approved-Entrypoint Evidence

| Command | Result |
|---------|--------|
| `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from pathlib import Path; docs=['docs/current-langgraph-architecture.md','docs/architecture-overview.md','docs/target-agent-platform-architecture-plan.md','README.md','.planning/ARCHITECTURE-DEBT.md']; missing=[p for p in docs if 'risk_gate' not in Path(p).read_text()]; bad=[]; active=['G[assess_risk_and_approval]','Risk[assess_risk_and_approval]','assess_risk_and_approval[assess_risk_and_approval','Phase 57-owned active legacy node','resume_route assess_risk_and_approval']; [bad.append((p,m)) for p in docs for m in active if m in Path(p).read_text()]; assert not missing, 'missing risk_gate in '+', '.join(missing); assert not bad, 'active legacy doc references: '+str(bad)"` | pass |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase34_approval_action_boundaries.py::test_phase34_risk_gate_runtime_alias_is_declared -q --tb=short` | `1 passed, 1 warning` after updating stale Phase 34 guard to Phase 57 alias semantics |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_phase34_approval_action_boundaries.py tests/architecture/test_approval_boundaries.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_phase22_action_boundary.py tests/test_approval_gate.py tests/test_approval_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py tests/agent/test_graph_vocabulary.py tests/test_agent_runs_api.py tests/agent/test_trace.py tests/test_trace_api.py -q --tb=short` | `437 passed, 1 skipped, 29 warnings` |
| `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent src/approvals src/api tests/architecture tests/agent tests/test_graph_routing.py tests/test_approval_api.py tests/test_approval_gate.py tests/test_agent_runs_api.py tests/test_trace_api.py` | pass |
| `npm --prefix frontend run build` | pass |
| `UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check` | pass |

## Static Legacy-Hit Classification

Scan command evidence:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -c "import subprocess, collections; pat='assess_risk_and_approval'; roots=['README.md','docs','src','tests','frontend','scripts','eval','rules','.planning/ARCHITECTURE-DEBT.md','.planning/ROADMAP.md','.planning/REQUIREMENTS.md','.planning/STATE.md','.planning/phases/57-risk-gate-and-approval-gate-canonicalization']; exclude={'.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md'}; res=subprocess.run(['git','grep','-n',pat,'--',*roots],text=True,capture_output=True); ... classify by path/category; assert no unclassified rows"
```

Scope:

- Included: `README.md`, `docs/`, `src/`, `tests/`, `frontend/`, `scripts/`, `eval/`, `rules/`, top-level planning ledgers, and active Phase 57 planning artifacts.
- Excluded: this generated `57-VALIDATION.md` report itself, to avoid recursive self-counting.
- Total hits: 421
- Files: 49
- unclassified_rows: 0

Category counts:

| Category | Count | Meaning |
|----------|------:|---------|
| `historical_compatibility_projection` | 40 | Trace/API/frontend vocabulary and tests preserving stored historical names while projecting to `risk_gate`. |
| `legacy_wrapper_or_import_test` | 47 | Legacy wrapper implementation, direct import tests, compatibility tests, or risk-rule comments retained until Phase 58. |
| `previous_state_documentation` | 322 | Historical planning/research/review/summary/docs text describing pre-cutover state or migration context. |
| `phase58_deletion_candidate` | 12 | Explicit deletion candidates such as persisted retry constants, old dev-contract manifest rows, and stale historical docs/tests for Phase 58 cleanup. |

Path/category rows:

| Path group | Category | Hits |
|------------|----------|-----:|
| `.planning/ARCHITECTURE-DEBT.md` | `previous_state_documentation` | 26 |
| `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` | `previous_state_documentation` | 8 |
| `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-*-PLAN.md` | `previous_state_documentation` | 79 |
| `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-*-SUMMARY.md` | `previous_state_documentation` | 32 |
| `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md`, `57-RESEARCH.md`, `57-PATTERNS.md`, review/discussion artifacts | `previous_state_documentation` | 161 |
| `README.md`, `docs/architecture-overview.md`, `docs/current-langgraph-architecture.md`, `docs/target-agent-platform-architecture-plan.md` | `previous_state_documentation` | 13 |
| `docs/current-implementation-map.md`, `docs/security-and-permission.md`, `docs/memory-contract-delta.md` | `previous_state_documentation` | 3 |
| `src/agent/graph_vocabulary.py`, `src/api/routers/agent_runs.py`, `frontend/src/components/timeline/TimelineStep.tsx` | `historical_compatibility_projection` | 5 |
| `tests/agent/test_graph_vocabulary.py`, `tests/agent/test_trace.py`, `tests/test_trace_api.py`, `tests/test_agent_runs_api.py`, architecture projection/static guards | `historical_compatibility_projection` | 35 |
| `src/agent/nodes/assess_risk_and_approval.py`, `src/agent/nodes/risk_gate.py`, `rules/risk_rules.yaml` | `legacy_wrapper_or_import_test` | 9 |
| direct legacy import/compatibility tests (`tests/agent/test_nodes/*`, `tests/agent/test_phase22_action_boundary.py`, `tests/test_graph_routing.py`, `tests/test_interception_rate.py`, `tests/conftest.py`) | `legacy_wrapper_or_import_test` | 38 |
| `src/api/routers/approvals.py`, `tests/test_approval_api.py`, `tests/test_approval_gate.py` | `phase58_deletion_candidate` | 6 |
| `eval/replay/dev-contract-manifest.v1.json` | `phase58_deletion_candidate` | 6 |

No remaining hit is classified as current active graph registration, current router return value, current eval node, or current approval resume route.

## Manual-Only Verification

| Behavior | Requirement | Result |
|----------|-------------|--------|
| Historical production database rows, if any, are not bulk-mutated by Phase 57. | CAGM-08 | No Phase 57 plan added a data migration rewriting `agent_steps.node_name` or `approval_events.metadata_json`; compatibility is projection/retry-only and Phase 58-scoped. |

## Security Notes

| Threat Ref | STRIDE | Required Mitigation | Status |
|------------|--------|---------------------|--------|
| T-57-01 | Spoofing / Elevation of privilege | Ordinary approval-like chat stays unsupported/untrusted; only authenticated API/inbox constructs `TrustedApprovalResultV1`. | green |
| T-57-02 | Tampering | Tenant/run/approval id, payload hash, snapshot ref/hash, and config versions remain validated before graph resume/action draft. | green |
| T-57-03 | Elevation of privilege | Trusted edit resume routes to `risk_gate`, not directly to `action_draft`. | green |
| T-57-04 | Tampering | Missing evidence, missing claim support, missing snapshot/hash, or invalid policy/risk/retrieval versions fail closed before approval/action. | green |
| T-57-05 | Repudiation / Tampering | Legacy `assess_risk_and_approval` handling is historical compatibility only and marked `DELETE_BY_PHASE_58`; active runtime registration and routes use `risk_gate`. | green |

## Validation Audit 2026-07-08

| Metric | Result |
|--------|--------|
| State | A - existing validation report audited |
| Requirement | CAGM-08 |
| Plans covered | 57-01, 57-02, 57-03, 57-04, 57-05 |
| gaps_found | 0 |
| resolved | 0 |
| escalated | 0 |
| tests_created | 0 |
| manual_only_blockers | 0 |
| nyquist_compliant | true |

Audit evidence:

- `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from pathlib import Path; p=Path('.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md'); text=p.read_text(); required=['57-01-01','57-02-01','57-03-01','57-04-01','57-05-01','Static Legacy-Hit Classification','Total hits: 421','unclassified_rows: 0','nyquist_compliant: true']; missing=[s for s in required if s not in text]; assert not missing, 'missing validation markers: '+', '.join(missing); print('phase57-validation-artifact-guard: pass')"` - `phase57-validation-artifact-guard: pass`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_phase34_approval_action_boundaries.py tests/architecture/test_approval_boundaries.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_phase22_action_boundary.py tests/test_approval_gate.py tests/test_approval_api.py tests/approvals/test_needs_info_resume.py tests/approvals/test_service_transitions.py tests/agent/test_graph_vocabulary.py tests/test_agent_runs_api.py tests/agent/test_trace.py tests/test_trace_api.py -q --tb=short` - `437 passed, 1 skipped, 29 warnings in 304.17s`

## Validation Sign-Off

- [x] All tasks have automated verification or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 canonical `risk_gate` and active graph guardrails are covered.
- [x] No watch-mode flags.
- [x] Feedback latency < 180s for focused suites; full closeout suite ran in 5m08s.
- [x] `nyquist_compliant: true` set in frontmatter after approved command evidence was recorded.

**Approval:** complete
