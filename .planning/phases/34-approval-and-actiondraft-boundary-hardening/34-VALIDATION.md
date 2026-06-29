---
phase: 34
slug: approval-and-actiondraft-boundary-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-29
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
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals tests/actions/test_action_draft_v2.py tests/test_approval_api.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_graph.py tests/architecture/test_approval_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py -q --tb=short` |
| **Estimated runtime** | ~90 seconds |

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
| 34-01-W0 | 01 | 0 | APF-15 | T-34-01 / T-34-02 | Approval/action binding tests exist before implementation. | contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals/test_phase34_boundary_bindings.py -q --tb=short` | ❌ W0 | ⬜ pending |
| 34-02-W0 | 02 | 0 | APF-16 | T-34-03 | `risk_gate` owns route decisions; approval gate cannot re-decide risk. | router | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py -q --tb=short` | ✅ | ⬜ pending |
| 34-03-W0 | 03 | 0 | APF-15 | T-34-04 | Manager approval access is same-merchant only; missing target fails closed. | API/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/platform/test_merchant_scope.py -q --tb=short` | ✅ | ⬜ pending |
| 34-04-W0 | 04 | 0 | APF-15/APF-16 | T-34-02 / T-34-05 | Action draft validates exact trusted approval or durable auto binding and remains demo-only. | service/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/actions/test_phase34_action_draft_bindings.py tests/architecture/test_action_draft_boundaries.py -q --tb=short` | ❌ W0 | ⬜ pending |
| 34-05-W0 | 05 | 0 | APF-15/APF-16 | T-34-01..T-34-05 | Final closure covers spoofing, hash mismatch, manager scope, wildcard scope, and no real execution. | focused suite | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/approvals tests/actions/test_action_draft_v2.py tests/test_approval_api.py tests/test_approval_gate.py tests/test_execute_action.py tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_graph.py tests/architecture/test_approval_boundaries.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_phase33_rag_claim_boundaries.py tests/platform/test_merchant_scope.py tests/tools/test_merchant_scope_static.py -q --tb=short` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/approvals/test_phase34_boundary_bindings.py` — APF-15 approval binding fields, target merchant fail-closed legacy rows, and payload/business/evidence/claim/risk mismatch invalidation.
- [ ] `tests/actions/test_phase34_action_draft_bindings.py` — APF-15 draft binding fields, durable auto-allowed binding if enabled, and exact target merchant/snapshot/hash validation.
- [ ] `tests/architecture/test_phase34_approval_action_boundaries.py` — static guard for no external execution/outbox/action execution records and no wildcard `server_merchant_scope` outside admin/system-only contracts.
- [ ] Update `tests/test_approval_api.py` — replace interim manager-403-only tests with same-merchant allow, cross-merchant deny, and missing-target deny tests after manager target binding exists.
- [ ] Update `tests/test_graph_routing.py` — add `risk_gate` vocabulary/alias and durable auto-allowed route tests if Phase 34 enables auto-draft.

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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
