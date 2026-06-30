---
phase: 36
slug: merchant-scope-db-hardening-role-cleanup
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-30
---

# Phase 36 - Validation Strategy

> Per-phase validation contract for merchant-scope DB hardening, role cleanup, migration gates, and trace/replay readiness.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio auto mode |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options] asyncio_mode = "auto"`) |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py tests/integration/test_auth.py tests/approvals/test_migration_contract.py tests/actions/test_phase34_action_draft_bindings.py tests/replay/test_phase35_trace_replay_permissions.py -q` |
| **Final focused regression command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py tests/integration/test_auth.py tests/agent/test_phase36_run_scope.py tests/approvals/test_phase36_scope_consistency.py tests/approvals/test_migration_contract.py tests/db/test_phase36_migration_preflight.py tests/replay/test_phase36_readiness.py tests/business/test_service.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/test_approval_api.py tests/test_trace_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` |
| **Estimated runtime** | Quick: ~60-180 seconds depending on DB readiness; full: project-dependent |

---

## Sampling Rate

- **After every task commit:** Run the focused test command for the touched surface using `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.
- **After every plan wave:** Run the quick command in the table above.
- **Before `$gsd-verify-work`:** Run the full suite command when local PostgreSQL is available.
- **Max feedback latency:** 3 task commits without an automated verification command is not allowed.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 36-01-role-scope | 36-01 | 1 | MSH-01, MSH-02, MSH-07 | T36-01 / T36-04 | Merchant-bound roles stay deny-first; wildcard business scope remains admin-only. | unit + static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py -q --tb=short` | Existing partial | pending |
| 36-02-tenant-identity | 36-02 | 1 | MSH-02, MSH-03, MSH-07 | T36-01 / T36-02 | Username lookup cannot become ambiguous; user merchant binding is tenant-consistent. | integration + migration contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/integration/test_auth.py tests/approvals/test_migration_contract.py -q --tb=short` | Existing partial | pending |
| 36-03-run-scope | 36-03 | 2 | MSH-04, MSH-07 | T36-03 / T36-04 / T36-06 | AgentRun scope uses trusted target merchant binding/classification; target fields are consistent with classification. | unit + integration + regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_phase36_run_scope.py tests/approvals/test_migration_contract.py tests/test_agent_runs_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` | Missing W0 for Phase 36 test | pending |
| 36-04-consistency | 36-04 | 3 | MSH-05, MSH-07 | T36-04 / T36-05 | Approval/action/snapshot target merchant facts cannot contradict run scope; ApprovalRequest creation is protected before flush. | service + regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_phase36_scope_consistency.py tests/actions/test_phase34_action_draft_bindings.py -q --tb=short` | Missing W0 for Phase 36 test | pending |
| 36-05-migration | 36-05 | 4 | MSH-02, MSH-03, MSH-04, MSH-05, MSH-06 | T36-01 / T36-02 / T36-03 / T36-05 / T36-06 | Migration rejects unsafe null/duplicate/cross-tenant/missing/malformed/contradictory/ambiguous data and never guesses merchant scope. | migration contract + DB smoke | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_migration_contract.py tests/db/test_phase36_migration_preflight.py -q --tb=short` | Missing W0 for DB preflight test | pending |
| 36-06-readiness-regression | 36-06 | 5 | MSH-07, MSH-08 | T36-01 / T36-02 / T36-03 / T36-04 / T36-05 / T36-06 | Readiness emits exactly one allowed value and final regressions prove no manager trace/replay visibility widening. | static + focused regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase36_readiness.py tests/business/test_service.py tests/knowledge/test_service.py tests/knowledge/test_tenant_scope.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_memory_evidence_boundary.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/rag_context/test_verifier.py tests/test_approval_api.py tests/test_trace_api.py tests/replay/test_phase35_trace_replay_permissions.py -q --tb=short` | Missing W0 for readiness test; regression files exist | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/agent/test_phase36_run_scope.py` - stubs for AgentRun target merchant binding and scope classification behavior.
- [ ] `tests/approvals/test_phase36_scope_consistency.py` - stubs for run/approval/action/snapshot target merchant contradiction cases.
- [ ] `tests/db/test_phase36_migration_preflight.py` - stubs or equivalent coverage for migration preflight clean/invalid/duplicate/contradictory/ambiguous data cases.
- [ ] `tests/replay/test_phase36_readiness.py` - stubs for readiness enum and no-widening linkage.
- [ ] `tests/integration/test_auth.py` - tenant-scoped username or transitional tenant-resolution tests.

Existing infrastructure covers pytest, async tests, FastAPI/httpx test clients, and PostgreSQL-backed fixtures. No new test framework is needed.

**wave_0_complete rationale:** `wave_0_complete: false` is intentionally unchanged before implementation because the Phase 36-specific test stubs do not all exist yet. The strategy, plan IDs, waves, and commands are mapped above; execution plans 36-03 through 36-06 create the missing stubs and may flip this to true only after those files exist.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Local PostgreSQL availability for live migration smoke | MSH-06 | The repository may not have a running local DB service in every agent session. | If DB tests fail due to connectivity only, record the exact failure and rerun after `docker compose up -d postgres`; do not treat bare environment failure as product failure. |
| Phase 37 readiness interpretation | MSH-08 | The readiness conclusion is an artifact consumed by a future phase, not a runtime API behavior. | Verify the phase summary or readiness artifact contains exactly one of `ready_with_agent_run_binding`, `ready_with_derived_refs_only`, or `not_ready`, with evidence and blockers. |

---

## Threat References

| Threat Ref | Threat | Required Mitigation |
|------------|--------|---------------------|
| T36-01 | Active merchant-bound user without merchant binding receives business access. | DB/service validation keeps role deny-first; tests cover null/invalid merchant binding. |
| T36-02 | Tenant-scoped username migration makes login ambiguous. | Auth lookup includes trusted tenant resolution or documented transitional invariant; tests cover same-tenant duplicate rejection and cross-tenant duplicate behavior. |
| T36-03 | AgentRun merchant scope is guessed from owner/thread/prompt/memory/RAG/LLM output. | Backfill and runtime persistence only use authoritative proof; tests/static checks reject forbidden inference sources. |
| T36-04 | Readiness proof or target projection widens run/status/evidence/trace/replay access. | Existing owner/admin-only guards remain; no same-merchant manager access is introduced in Phase 36. |
| T36-05 | Approval/action/snapshot target merchant facts contradict run scope. | Consistency checks reject or classify contradictions invalid. |
| T36-06 | Policy-only or unknown legacy runs become visible as merchant business runs. | Explicit scope classification keeps policy-only and unknown legacy fail-closed for business visibility. |

---

## Validation Sign-Off

- [x] All planned requirement areas have automated verification targets.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 coverage is mapped to concrete plans and commands; missing stubs are not claimed as already created.
- [x] No watch-mode flags.
- [x] All commands use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...` or the full-suite `uv run` entry; bare `pytest` is forbidden.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** draft for planner/checker consumption on 2026-06-30.
