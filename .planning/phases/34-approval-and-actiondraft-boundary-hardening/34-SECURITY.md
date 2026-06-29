---
phase: 34
slug: approval-and-actiondraft-boundary-hardening
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-29
verified: 2026-06-29T09:00:39Z
---

# Phase 34 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| graph state -> approval/action contracts | LLM- and graph-produced material becomes typed service input only after strict DTO validation. | Proposed action, target merchant binding, business/evidence/claim refs, risk decisions, hashes, snapshot refs |
| ORM/migration -> service authorization | Persisted binding fields become authorization facts for manager scope and draft creation. | ApprovalRequest and ActionDraft binding columns |
| recommendation/claim state -> risk_gate | Actionable LLM output enters deterministic risk and binding validation. | Verified claims, evidence refs, business facts, proposed action |
| risk_gate -> approval_gate/action_draft | Route authority crosses from graph state into approval or draft creation. | Approval plans, auto-allowed bindings, risk decisions |
| approval API actor -> ApprovalService | Authenticated human reviewer commands enter service transition logic. | Approval decisions, edit/respond info, actor identity |
| ApprovalService result -> graph resume | Trusted resume payload crosses from API/service into LangGraph. | `approval_result.v1`, permissions, trusted context |
| graph interrupt -> API bridge | Structured approval interrupt data crosses from graph runtime into ApprovalService creation. | Approval interrupt payload and Phase 34 binding fields |
| API bridge -> live client projection | Safe approval-required payloads are shown to clients without raw authority bodies. | Summaries, refs, revisions, payload/snapshot hashes |
| graph trusted result -> action_draft node | Approval or auto binding authorizes draft creation. | Trusted approval result or auto-allowed binding |
| action_draft node -> ToolPlatform/ActionService | Node-only write tool crosses into durable draft persistence. | Draft args plus binding material |
| draft persistence -> user/prompt projections | Stored draft material is summarized for response, trace, and working state. | Safe draft refs/counts/summaries |
| completed implementation -> release readiness | Static/focused validation proves authority and execution boundaries. | Test and static scan evidence |
| Phase 34 scope -> Phase 35 scope | Broad trace/run API projection hardening remains deferred. | Explicit deferral record, not runtime authority |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-34-01-01 | Tampering | `src/approvals/schemas.py` | mitigate | Strict `RiskDecisionV1`, `TargetMerchantBindingV1`, `AutoAllowedActionBindingV1`, and approval binding fields use typed Pydantic contracts; covered by `tests/approvals/test_phase34_boundary_bindings.py` and Phase 34 focused suite. | closed |
| T-34-01-02 | Information Disclosure | `ActionDraftV2Data` / ORM JSON fields | mitigate | Draft data stores safe refs/summaries and static scans found no action execution/outbox/reconciliation/compensation surfaces. | closed |
| T-34-01-03 | Repudiation | migration 018 | mitigate | Migration/model parity persists target merchant, business/evidence/claim/risk, payload hash, snapshot, idempotency, and revision fields; covered by migration and action draft tests. | closed |
| T-34-02-01 | Elevation of Privilege | `route_after_risk` | mitigate | `route_after_risk` requires exact `approval_plan` or `auto_allowed_action_binding.v1`; security pytest covered hash mismatch and strict auto-allowed binding validation. | closed |
| T-34-02-02 | Tampering | `assess_risk_and_approval` | mitigate | Risk binding material is built from service-approved business facts and verified claim/evidence refs; node and graph tests passed in Phase 34 focused/UAT suites. | closed |
| T-34-02-03 | Spoofing | `approval_gate` responsibility boundary | mitigate | Static tests prove `approval_gate` does not own blocked/approval-required/auto-draft routing and cannot call `ApprovalService.decide`. | closed |
| T-34-03-01 | Elevation of Privilege | `src/api/routers/approvals.py` | mitigate | Manager approval list/get/decide checks persisted `target_merchant_id`; same-merchant allow and cross/missing-target deny tests passed. | closed |
| T-34-03-02 | Spoofing | `_resume_graph_config` | mitigate | Approval resume uses `TrustedContextFactory.create_from_request` with `server_tool_permissions` only; static scan confirmed no `server_merchant_scope` use in approval router. | closed |
| T-34-03-03 | Tampering | `ApprovalService._decision_result` | mitigate | Trusted resume payloads include exact persisted active-revision binding refs/hashes; action draft and approval binding mismatch tests passed. | closed |
| T-34-04-01 | Tampering | interrupt binding fields | mitigate | Agent-runs bridge copies Phase 34 interrupt bindings into `ApprovalRequestCreateCommand` and fails closed on missing/malformed required fields; bridge coverage passed. | closed |
| T-34-04-02 | Spoofing | run/action identity | mitigate | Trusted run/user context and proposed action identity validation remain authoritative; spoofed payload/checkpoint tests passed. | closed |
| T-34-04-03 | Information Disclosure | `approval_required` payload | mitigate | Live approval-required projection exposes summaries/refs/revisions, not raw proposed action/debug/snapshot/action authority bodies; agent_runs safe projection tests passed. | closed |
| T-34-05-01 | Spoofing | `src/agent/nodes/action_draft.py` | mitigate | Action draft accepts only service-produced `approval_result.v1` or strict `auto_allowed_action_binding.v1` matching tenant/run/hash/snapshot/target refs. | closed |
| T-34-05-02 | Tampering | `src/actions/service.py` | mitigate | ActionService validates exact approval or auto binding against persisted snapshot and approval/draft binding material before insert/reuse. | closed |
| T-34-05-03 | Repudiation | `src/repositories/action_draft_repo.py` | mitigate | Draft idempotency includes approval revision or auto marker plus payload hash, and repository reuse compares Phase 34 binding fields. | closed |
| T-34-05-04 | Information Disclosure | `src/agent/working_state.py` | mitigate | Working-state projection exposes safe refs/counts and summaries while excluding raw payload/snapshot/approval bodies; focused suite and UAT passed. | closed |
| T-34-05-05 | Elevation of Privilege | no-real-execution boundary | mitigate | Static/focused tests and manual `rg` scans found no external execution/outbox/reconciliation/compensation records or execution-implying production wording. | closed |
| T-34-06-01 | Elevation of Privilege | static guards | mitigate | Final static guards cover approval spoofing, approval_gate risk ownership, wildcard resume, requested_by merchant shortcuts, and agent_runs bridge coverage. | closed |
| T-34-06-02 | Repudiation | validation artifact | mitigate | `34-VALIDATION.md`, `34-VERIFICATION.md`, and `34-UAT.md` record exact commands, results, and post-review verification evidence. | closed |
| T-34-06-03 | Tampering | no-real-execution boundary | mitigate | Static tests forbid execution/outbox/reconciliation/compensation surfaces and execution-positive wording; manual scans also returned no production matches. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

No accepted risks.

---

## Security Verification Evidence

Security focused pytest:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_phase34_approval_action_boundaries.py tests/test_graph_routing.py::test_route_after_risk_fails_closed_when_approval_plan_hash_mismatches_state tests/test_graph_routing.py::test_route_after_approval_returns_final_response_on_untrusted_ordinary_payload tests/test_execute_action.py::test_execute_action_blocks_when_phase34_approval_binding_mismatches_state tests/actions/test_phase34_action_draft_bindings.py::test_create_coupon_grant_draft_rejects_phase34_approval_binding_mismatch tests/test_approval_api.py::test_manager_approval_review_paths_allow_same_merchant tests/test_approval_api.py::test_manager_approval_review_paths_deny_cross_merchant tests/test_approval_api.py::test_manager_approval_review_paths_deny_missing_target_merchant tests/test_agent_runs_api.py::test_agent_chat_interrupt_uses_trusted_run_id_when_payload_and_checkpoint_spoof tests/test_agent_runs_api.py::test_event_generator_treats_stream_interrupt_node_as_approval_required -q --tb=short
```

Result: `20 passed, 1 warning in 28.98s`.

Static scans:

```bash
rg -n "server_merchant_scope|requested_by.*merchant|merchant_id.*requested_by" src || true
```

Result: only generic `src/platform/trusted_context.py` support code matched; `src/api/routers/approvals.py` contains no `server_merchant_scope`, requested_by merchant shortcut, or merchant_id requested_by shortcut.

```bash
rg -n "action_executions|action_outbox_events|action_reconciliation_jobs|action_compensation_records|outbox|external_side_effect\s*=\s*true|status\s*=\s*executed" src/actions src/tools src/repositories src/agent src/api || true
```

Result: no matches.

```bash
rg -n "已发券|已退款|coupon issued|refund completed|ticket closed|successfully issued|successfully refunded" src || true
```

Result: no matches.

```bash
rg -n "TODO|FIXME|HACK|placeholder|not implemented|pass #|security" src/approvals src/actions src/agent/nodes/approval_gate.py src/agent/nodes/action_draft.py src/agent/nodes/assess_risk_and_approval.py src/api/routers/approvals.py src/api/routers/agent_runs.py tests/architecture/test_phase34_approval_action_boundaries.py || true
```

Result: no matches.

Prior broader verification remains green in `34-UAT.md`: Phase 34 focused suite `403 passed, 22 warnings in 389.10s`; ruff relevant Phase 34 scope passed; `git diff --check` passed.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-29 | 20 | 20 | 0 | Codex |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-29
