---
phase: 63
slug: safety-taxonomy-and-risk-vocabulary
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-10
---

# Phase 63 — Validation Strategy

> Per-phase validation contract for safety taxonomy, action canonicalization, risk vocabulary, action draft, and intent/routing parity.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| Backend framework | pytest 9.0.3 with pytest-asyncio 1.3.0 |
| Config files | `pyproject.toml` |
| Quick taxonomy command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py -q --tb=short` |
| Drift guard command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_safety_taxonomy_boundaries.py -q --tb=short` |
| Full focused phase command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/approvals/test_hash_binding.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_safety_taxonomy_boundaries.py -q --tb=short` |
| Lint command | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check <changed files>` |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 63-TASK-01 | 01 | 1 | SC-63-1, D-63-01..04, D-63-13 | T-63-01, T-63-02 | Canonical action type and action keyword taxonomy has one owner; executable actions are separated from dispositions. | unit/parity | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py -q --tb=short` | ❌ W0 new file | ⬜ pending |
| 63-TASK-02 | 02 | 2 | SC-63-2, D-63-05..07, D-63-11..12, D-63-14 | T-63-03, T-63-04 | Risk severity and risk disposition are separated while legacy `risk_level` remains compatible. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py -q --tb=short` | ✅ existing files, new cases needed | ⬜ pending |
| 63-TASK-03 | 03 | 3 | SC-63-1, SC-63-3, D-63-02..04 | T-63-02, T-63-05 | `action_draft` uses the shared taxonomy and rejects non-executable dispositions before ToolPlatform. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/test_execute_action.py -q --tb=short` | ✅ existing files, new cases needed | ⬜ pending |
| 63-TASK-04 | 04 | 4 | SC-63-3, D-63-08..10, D-63-15 | T-63-06, T-63-07 | Intent/routing safety checks derive from shared policy/taxonomy sources and preserve ordinary-chat approval fail-closed behavior. | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py -q --tb=short` | ✅ existing files, new cases needed | ⬜ pending |
| 63-TASK-05 | 05 | 5 | D-63-15..16 | T-63-08 | Static drift guards prevent duplicate local action/risk taxonomy from returning outside the canonical owner. | architecture/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_safety_taxonomy_boundaries.py -q --tb=short` | ❌ W0 new file | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/agent/test_safety_taxonomy.py` covers canonical taxonomy owner, alias resolution, executable-vs-disposition split, risk severity/disposition normalization, and current risk/draft canonicalization parity.
- [ ] `tests/architecture/test_safety_taxonomy_boundaries.py` forbids duplicated `FULL_REFUND_TERMS`, `ACTIONABLE_ACTIONS`, local `_canonical_action_type`, and local pre-route action keyword sets outside the canonical owner.
- [ ] Existing risk/action/intent tests receive targeted cases for `manual_review` as disposition-only and no `risk_level == "manual_review" | "blocked"` routing dependency.

---

## Manual-Only Verifications

All core Phase 63 behaviors should have automated verification. No manual-only behavior is required unless an execution agent discovers a compatibility case that cannot be tested without external runtime state.

---

## Security Validation Focus

| Threat Ref | Threat | Required Automated Evidence |
|------------|--------|-----------------------------|
| T-63-01 | Action taxonomy drift causes risk and draft to canonicalize differently. | Shared taxonomy unit tests and drift guard tests. |
| T-63-02 | `manual_review` or `blocked` crosses into executable action payloads. | Taxonomy tests plus action-draft ToolPlatform boundary tests. |
| T-63-03 | Risk disposition is treated as severity. | Risk-gate tests for explicit severity/disposition normalization. |
| T-63-04 | LLM risk output overrides deterministic policy. | Risk-gate tests preserving backend-owned deterministic rule/verification gates. |
| T-63-05 | Action draft bypasses approval/hash/snapshot binding compatibility. | Existing action/approval binding regressions remain green. |
| T-63-06 | Pre-route action keyword drift bypasses safety routing. | Intent-policy tests deriving keyword behavior from taxonomy aliases. |
| T-63-07 | Evidence-required/action-bound routing drifts from intent definitions. | Intent-policy/routing parity tests. |
| T-63-08 | Future contributors reintroduce hardcoded local taxonomy sets. | Architecture/static drift tests. |

---

## Validation Sign-Off

- [x] All Phase 63 source decisions have an automated verification lane.
- [x] Sampling continuity defined; each plan has focused test commands.
- [x] Wave 0 gaps are explicit and must be scheduled by the planner.
- [x] No watch-mode flags in required commands.
- [x] `nyquist_compliant: true` set in frontmatter for the strategy.
- [ ] Wave 0 tests created during implementation.
- [ ] Final focused verification command green.

**Approval:** approved 2026-07-10 for planning; implementation evidence pending.
