# Phase 34: Approval and ActionDraft Boundary Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `34-CONTEXT.md` -- this log preserves the alternatives considered.

**Date:** 2026-06-29T02:18:44Z
**Phase:** 34-approval-and-actiondraft-boundary-hardening
**Areas discussed:** Contract and persistence boundary; Risk gate vs approval gate split; Manager merchant scope; Auto-draft strategy; No-real-execution boundary
**Interaction note:** `request_user_input` was unavailable in Codex Default mode. Per workflow fallback, Codex selected the recommended "discuss all" path and conservative defaults based on repository evidence.

---

## Contract and Persistence Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| First-class binding fields | Extend current approval/action contracts and persistence with target merchant, business fact refs, verified evidence refs, claim verification refs, risk decision refs, payload hash, and safety snapshot binding. | yes |
| Service-only projection | Keep DB shape mostly unchanged and reconstruct bindings from service/graph state when needed. | |
| New full table family | Introduce a larger normalized approval/action schema rewrite now. | |

**Selected default:** First-class binding fields.
**Notes:** Existing tables and services are mature enough to extend. Service-only reconstruction would weaken manager-scoped queues and Phase 35 replay handoff. A full table rewrite is more scope than Phase 34 needs.

---

## Risk Gate vs Approval Gate Split

| Option | Description | Selected |
|--------|-------------|----------|
| Compatibility-first split | Keep existing runtime compatibility where needed, but make target `risk_gate` ownership explicit and keep `approval_gate` limited to approval plan execution/resume. | yes |
| Physical node rewrite now | Rename/rebuild the graph around new physical nodes immediately. | |
| Leave combined legacy node | Continue letting legacy `assess_risk_and_approval` own mixed risk/approval semantics. | |

**Selected default:** Compatibility-first split.
**Notes:** Phase 32 established target graph vocabulary without requiring breaking runtime renames. Phase 34 should extract responsibilities and test target semantics without a wholesale graph rewrite.

---

## Manager Merchant Scope

| Option | Description | Selected |
|--------|-------------|----------|
| BusinessFactRef-derived target merchant | Restore manager list/get/decide only when approval/action records carry a target merchant derived from scoped business fact authority. | yes |
| Requested-by approximation | Infer approval visibility from `requested_by.user.merchant_id`. | |
| Keep manager disabled | Leave Phase 29.5 admin-only guard in place for Phase 34. | |

**Selected default:** BusinessFactRef-derived target merchant.
**Notes:** Phase 29.5 explicitly rejected the requested-by approximation. Phase 34 owns target merchant binding, so same-merchant manager approval should be restored only when binding is explicit and scoped.

---

## Auto-Draft Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Contract now, conservative enablement | Define durable auto-allowed binding owned by `risk_gate`; keep no-approval drafts fail-closed unless that exact binding exists. | yes |
| Approval-only MVP | Keep every action-bearing path approval-required and defer auto-draft entirely. | |
| Broad low-risk auto-draft | Create low-risk drafts directly from transient `approval_required=false` state. | |

**Selected default:** Contract now, conservative enablement.
**Notes:** APF-16 requires `risk_gate` to own auto-draft decisions, but current code safely rejects no-approval drafts. The conservative path preserves that safety while defining the binding needed for future or narrowly enabled auto-drafts.

---

## No-Real-Execution Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Demo draft only | Preserve `action_draft` + `draft_outcome.v1(status=not_executed_demo)` as the terminal write path. | yes |
| Execution placeholder tables | Add action execution records or outbox placeholders without real adapters. | |
| Real external execution | Add external refund/coupon/ticket side-effect execution. | |

**Selected default:** Demo draft only.
**Notes:** Roadmap, requirements, target architecture, and contract spec all keep real external execution out of v1.9 / Phase 34.

---

## the agent's Discretion

- Exact class names and file split are left to planning.
- Exact migration order is left to planning, but the context recommends multiple dependency-ordered plans.
- Exact event payload names are left to planning, with Phase 28 redaction/resource-ref rules as constraints.

## Deferred Ideas

- Full external action execution/outbox/reconciliation.
- Broad Phase 35 replay/eval hardening.
- Future trusted system context for system-owned wildcard approval/action jobs.
