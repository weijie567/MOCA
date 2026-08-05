# Phase 57: Risk Gate and Approval Gate Canonicalization - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-07-07
**Phase:** 57-risk-gate-and-approval-gate-canonicalization
**Mode:** autopilot auto-discuss
**Areas discussed:** Canonical risk node cutover, Risk and approval responsibility split, Trusted approval boundary, Projection and validation closeout

---

## Canonical Risk Node Cutover

| Option | Description | Selected |
|--------|-------------|----------|
| Active `risk_gate` with narrow Phase 58-scoped legacy compatibility | Create/use canonical `risk_gate` active graph identity now, preserving direct import/test/historical compatibility for `assess_risk_and_approval` only when labeled and tested. | yes |
| Repository-wide destructive rename | Rename every historical reference immediately. Faster cleanup, but high risk to historical docs/tests and out of Phase 57 scope. | |
| Leave active `assess_risk_and_approval` until Phase 58 | Lowest implementation risk, but fails CAGM-08 and Phase 57 success criteria. | |

**Auto-selected choice:** Active `risk_gate` with narrow Phase 58-scoped legacy compatibility.
**Notes:** Mirrors the Phase 56 `recommendation_generation` cutover pattern. Active graph registration and current-run route values must become canonical in Phase 57.

---

## Risk and Approval Responsibility Split

| Option | Description | Selected |
|--------|-------------|----------|
| `risk_gate` owns risk/action policy and snapshot binding; `approval_gate` owns request/resume lifecycle | Matches Phase 50 authority matrix and `docs/contract-spec.md` target semantics. | yes |
| Move approval resume validation into `risk_gate` | Makes rerisk simpler, but blurs the trusted approval state-machine boundary. | |
| Keep current combined semantics hidden behind a renamed node only | Superficial rename; risks leaving approval/risk ownership ambiguous. | |

**Auto-selected choice:** `risk_gate` owns risk/action policy and snapshot binding; `approval_gate` owns request/resume lifecycle.
**Notes:** Edit/superseded approval resumes must route back to `risk_gate` for rerisk; accept/approve pending loops stay in `approval_gate`.

---

## Trusted Approval Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Trusted approval only through authenticated ApprovalService/API resume payloads | Preserves tenant/user/role/version/hash checks and blocks ordinary chat approval text. | yes |
| Let ordinary chat approval-like text influence approval result when intent confidence is high | Unsafe; violates contract and Phase 57 success criteria. | |
| Treat `approval_decision` as a normal requested operation | Already rejected by intent policy and eval contracts. | |

**Auto-selected choice:** Trusted approval only through authenticated ApprovalService/API resume payloads.
**Notes:** Tests must keep ordinary chat approval text out of `approval_gate`, `action_draft`, and trusted graph resume.

---

## Projection and Validation Closeout

| Option | Description | Selected |
|--------|-------------|----------|
| Update runtime vocabulary/API/frontend/eval/docs/debt after active cutover | Keeps user-visible and audit surfaces aligned with current runtime identity. | yes |
| Only update backend graph and leave projections/docs for Phase 58 | Creates confusing current-run traces and weakens Phase 57 acceptance evidence. | |
| Rewrite target contract first | Not needed unless implementation finds a real spec conflict; target contract already names `risk_gate`. | |

**Auto-selected choice:** Update runtime vocabulary/API/frontend/eval/docs/debt after active cutover.
**Notes:** Current-run identity should be `risk_gate`; historical `assess_risk_and_approval` display can project to canonical with explicit compatibility labeling until Phase 58.

---

## the agent's Discretion

- Exact module/wrapper structure.
- Exact compatibility metadata constant names.
- Exact display copy for risk-gate timeline labels.

## Deferred Ideas

- Phase 58 deletes remaining compatibility aliases and final historical-current projection debt.
