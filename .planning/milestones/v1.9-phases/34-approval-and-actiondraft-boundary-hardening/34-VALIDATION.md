---
phase: 34
slug: approval-and-actiondraft-boundary-hardening
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-29
audited: 2026-06-29T09:05:33Z
---

# Phase 34 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/test_approval_gate.py tests/test_execute_action.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_graph.py tests/architecture/test_approval_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_phase34_approval_action_boundaries.py tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py -q --tb=short` |
| **Estimated runtime** | ~7 minutes observed for the final focused suite |

---

## Sampling Rate

- **After every task commit:** Run the quick command plus the directly touched file's focused test.
- **After every plan wave:** Run the full focused suite command.
- **Before `$gsd-verify-work`:** Full focused suite must be green.
- **Max feedback latency:** 120 seconds for focused checks.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 34-01-W0 | 01 | 0 | APF-15 | T-34-01 / T-34-02 | Approval/action binding tests exist before implementation. | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_phase34_boundary_bindings.py -q --tb=short` | ✅ | ✅ green |
| 34-02-W0 | 02 | 0 | APF-16 | T-34-03 | `risk_gate` owns route decisions; approval gate cannot re-decide risk. | router | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q --tb=short` | ✅ | ✅ green |
| 34-03-W0 | 03 | 0 | APF-15 | T-34-04 | Manager approval access is same-merchant only; missing target fails closed. | API/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/platform/test_merchant_scope.py -q --tb=short` | ✅ | ✅ green |
| 34-04-W0 | 04 | 0 | APF-15/APF-16 | T-34-01 / T-34-02 / T-34-04 | agent_runs interrupt bridge preserves Phase 34 bindings and safe approval-required projection. | API/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_runs_api.py -q --tb=short` | ✅ | ✅ green |
| 34-05-W0 | 05 | 0 | APF-15/APF-16 | T-34-02 / T-34-05 | Action draft validates exact trusted approval or durable auto binding and remains demo-only. | service/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/actions/test_phase34_action_draft_bindings.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` | ✅ | ✅ green |
| 34-06-W0 | 06 | 0 | APF-15/APF-16 | T-34-01..T-34-05 | Final closure covers spoofing, hash mismatch, manager scope, wildcard scope, agent_runs bridge, and no real execution. | focused suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_graph.py tests/architecture/test_approval_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_phase34_approval_action_boundaries.py tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py -q --tb=short` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/approvals/test_phase34_boundary_bindings.py` — APF-15 approval binding fields, target merchant fail-closed legacy rows, and payload/business/evidence/claim/risk mismatch invalidation.
- [x] `tests/actions/test_phase34_action_draft_bindings.py` — APF-15 draft binding fields, durable auto-allowed binding if enabled, and exact target merchant/snapshot/hash validation.
- [x] `tests/architecture/test_phase34_approval_action_boundaries.py` — static guard for no external execution/outbox/action execution records and no wildcard `server_merchant_scope` outside admin/system-only contracts.
- [x] Update `tests/test_agent_runs_api.py` — preserve Phase 34 binding fields through approval interrupts and keep `approval_required` payloads safe.
- [x] Update `tests/test_approval_api.py` — replace interim manager-403-only tests with same-merchant allow, cross-merchant deny, and missing-target deny tests after manager target binding exists.
- [x] Update `tests/test_graph_routing.py` — add `risk_gate` vocabulary/alias and durable auto-allowed route tests if Phase 34 enables auto-draft.

---

## Manual-Only Verifications

All phase behaviors should have automated verification. Manual review is limited to reading final plan/review artifacts for scope alignment and checking that no deferred real-execution work was pulled into Phase 34.

---

## Threat Model

| Ref | Threat | STRIDE | Required Mitigation | Test Anchor |
|-----|--------|--------|---------------------|-------------|
| T-34-01 | Ordinary chat spoofs approval or action authority. | Spoofing / Elevation of Privilege | Only ApprovalService/API-created `approval_result.v1` is trusted; graph rejects untrusted or mismatched approval result state. | `tests/agent/test_graph.py`, `tests/test_approval_gate.py`, `tests/test_approval_api.py` |
| T-34-02 | Payload, evidence, business fact, claim, or risk binding changes after approval. | Tampering | Compare exact action payload hash and safety snapshot hash/ref; material changes create a new approval revision and cannot create draft from old approval. | `tests/approvals/test_phase34_boundary_bindings.py`, `tests/actions/test_phase34_action_draft_bindings.py` |
| T-34-03 | `approval_gate` re-decides risk/approval policy and bypasses `risk_gate`. | Elevation of Privilege | `risk_gate` owns blocked/approval-required/auto-draft routing; `approval_gate` only executes approval plan and trusted resume state machine. | `tests/test_graph_routing.py`, `tests/architecture/test_approval_boundaries.py` |
| T-34-04 | Manager sees or decides another merchant's approval. | Information Disclosure / Elevation of Privilege | ApprovalRequest/ActionDraft carry target merchant or scoped BusinessFactRef authority; manager access fails closed when missing, ambiguous, or outside scope. | `tests/test_approval_api.py`, `tests/platform/test_merchant_scope.py` |
| T-34-05 | Phase introduces real external execution or response wording implies execution. | Tampering / Repudiation | Keep demo `ActionDraft` + `draft_outcome.v1(status=not_executed_demo, external_side_effect=false)`; no external adapters/outbox/execution rows. | `tests/architecture/test_action_draft_boundaries.py`, `tests/actions/test_action_draft_v2.py` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s for per-task focused checks
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** complete

---

## Final Closure

Closed on 2026-06-29 after the Phase 34 focused suite and static gates passed.

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_graph.py tests/architecture/test_approval_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/architecture/test_phase34_approval_action_boundaries.py tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py -q --tb=short` — 400 passed, 22 warnings in 411.00s.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/approvals src/actions src/agent/nodes/assess_risk_and_approval.py src/agent/nodes/approval_gate.py src/agent/nodes/action_draft.py src/agent/graph.py src/agent/graph_vocabulary.py src/api/routers/agent_runs.py src/api/routers/approvals.py src/api/schemas/agent_runs.py src/api/schemas/approvals.py tests/approvals tests/actions tests/architecture/test_phase34_approval_action_boundaries.py tests/test_agent_runs_api.py tests/test_approval_api.py tests/test_execute_action.py tests/test_graph_routing.py` — all checks passed.
- `git diff --check` — passed.

## Validation Audit 2026-06-29

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

State A audit completed on 2026-06-29T09:05:33Z against the existing `34-VALIDATION.md`, all six `34-*-PLAN.md` files, all six `34-*-SUMMARY.md` files, `34-VERIFICATION.md`, `34-UAT.md`, and `34-SECURITY.md`.

Requirement-to-task coverage remains complete:

- `34-01-W0` covers APF-15 contract and persistence binding tests.
- `34-02-W0` covers APF-16 `risk_gate` routing ownership and fail-closed route behavior.
- `34-03-W0` covers APF-15/APF-16 approval service, manager scope, and no-wildcard resume behavior.
- `34-04-W0` covers APF-15/APF-16 agent_runs interrupt binding preservation and safe live approval-required projection.
- `34-05-W0` covers APF-15/APF-16 action draft exact binding validation, safe projections, idempotency, and no-real-execution boundaries.
- `34-06-W0` covers final static/focused closure for spoofing, binding mismatch, manager scope, wildcard scope, bridge preservation, and no real execution.

Post-review WR-03/WR-04 edit and needs-info rerisk/rebind semantics are covered by `34-UAT.md` and `34-REVIEW.md`: service-level supersede produces trusted rerisk/rebind material without creating an unbound replacement approval, and replacement approvals are created only after the resumed graph emits a new approval interrupt. This is covered by `tests/approvals/test_needs_info_resume.py`, `tests/test_approval_api.py::test_decide_edit_rebinds_replacement_approval_from_resume_interrupt`, and `tests/test_approval_api.py::test_decide_edit_resume_failure_can_retry_and_rebind_without_new_decision`; no additional Nyquist gap was found.

Audit commands:

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/test_approval_gate.py tests/test_execute_action.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` — 100 passed, 1 warning in 10.46s.
- Prior UAT final focused suite in `34-UAT.md`: 403 passed, 22 warnings in 389.10s.
- Security focused pytest in `34-SECURITY.md`: 20 passed, 1 warning in 28.98s.

No test files were generated in this audit because all Phase 34 requirements already have automated verification.
