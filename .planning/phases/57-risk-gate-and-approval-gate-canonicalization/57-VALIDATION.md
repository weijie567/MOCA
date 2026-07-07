---
phase: 57
slug: risk-gate-and-approval-gate-canonicalization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-07
---

# Phase 57 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py tests/architecture/test_approval_boundaries.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_phase22_action_boundary.py tests/test_approval_gate.py tests/test_approval_api.py tests/agent/test_graph_vocabulary.py tests/test_agent_runs_api.py tests/agent/test_trace.py tests/test_trace_api.py -q --tb=short` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run the narrow automated command for the touched surface.
- **After every plan wave:** Run the quick command plus the plan-specific family below.
- **Before `$gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 180 seconds for focused suites.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 57-01-01 | 01 | 1 | CAGM-08 | T-57-05 | Canonical callable emits current-run `risk_gate` identity while legacy surface is compatibility-only. | unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q --tb=short` | add canonical coverage | pending |
| 57-02-01 | 02 | 2 | CAGM-08 | T-57-05 | Active graph registers `risk_gate`, not `assess_risk_and_approval`; route maps target canonical node. | architecture/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py -q --tb=short` | yes | pending |
| 57-03-01 | 03 | 3 | CAGM-08 | T-57-01 / T-57-03 | Trusted edit resume reroutes to `risk_gate`; ordinary chat cannot produce trusted approval. | API/service/safety | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py tests/agent/test_intent_routing.py -q --tb=short` | yes | pending |
| 57-04-01 | 04 | 4 | CAGM-08 | T-57-05 | Current-run vocabulary/API/frontend/eval/diagnostics use `risk_gate`; legacy key is projection compatibility only. | projection/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short` | yes | pending |
| 57-05-01 | 05 | 5 | CAGM-08 | T-57-05 | Docs, architecture debt, validation artifact, and static legacy-hit classification distinguish current authority from historical compatibility. | docs/static | `UV_CACHE_DIR=/tmp/uv-cache uv run python -c "from pathlib import Path; text=Path('.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-VALIDATION.md').read_text(); required=['57-05-01','Static Legacy-Hit Classification','UV_CACHE_DIR=/tmp/uv-cache uv run pytest']; missing=[s for s in required if s not in text]; raise SystemExit('missing validation markers: '+', '.join(missing)) if missing else None"` | yes | pending |

*Status: pending, green, red, flaky*

---

## Wave 0 Requirements

- [ ] `tests/agent/test_nodes/test_risk_gate.py` or equivalent canonical coverage - current node identity and compatibility behavior for CAGM-08.
- [ ] `tests/architecture/test_phase57_risk_gate_canonicalization.py` or equivalent baseline coverage - reject active current-run `assess_risk_and_approval` registration/routes after Phase 57.
- [ ] Update `tests/architecture/graph_baseline.py` so `risk_gate` is active and any retained `assess_risk_and_approval` row is compatibility-only.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Historical production database rows, if any, are not bulk-mutated by Phase 57. | CAGM-08 | Local test DB may not contain real historical approval event metadata or trace rows. | Inspect plan summary and diff for no data migration that rewrites historical `agent_steps.node_name` or `approval_events.metadata_json`; compatibility should be projection/retry only and Phase 58-scoped. |

---

## Static Legacy-Hit Classification

Plan 57-05 must update this section after execution by scanning remaining `assess_risk_and_approval` hits with an approved command such as `UV_CACHE_DIR=/tmp/uv-cache uv run python -c ...`. Each remaining hit must be assigned exactly one category:

- `historical_compatibility_projection` - stored trace/API/frontend display compatibility that preserves historical implementation node names while projecting target `risk_gate`.
- `legacy_wrapper_or_import_test` - `src/agent/nodes/assess_risk_and_approval.py` wrapper, direct import tests, or compatibility metadata with `DELETE_BY_PHASE_58`.
- `previous_state_documentation` - docs or planning text that explicitly describes the pre-Phase 57 state.
- `phase58_deletion_candidate` - migration residue intentionally left for Phase 58 final no-debt cleanup.

No `assess_risk_and_approval` hit may be classified as current active graph registration, current router return value, current eval node, or current approval resume route after Phase 57.

---

## Security Notes

| Threat Ref | STRIDE | Required Mitigation |
|------------|--------|---------------------|
| T-57-01 | Spoofing / Elevation of privilege | Ordinary approval-like chat stays unsupported/untrusted; only authenticated API/inbox constructs `TrustedApprovalResultV1`. |
| T-57-02 | Tampering | Tenant/run/approval id, payload hash, snapshot ref/hash, and config versions remain validated before graph resume/action draft. |
| T-57-03 | Elevation of privilege | Trusted edit resume must route to `risk_gate`, not directly to `action_draft`. |
| T-57-04 | Tampering | Missing evidence, missing claim support, missing snapshot/hash, or invalid policy/risk/retrieval versions fail closed before approval/action. |
| T-57-05 | Repudiation / Tampering | Legacy `assess_risk_and_approval` handling is historical compatibility only and marked `DELETE_BY_PHASE_58`; active runtime registration and routes use `risk_gate`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
