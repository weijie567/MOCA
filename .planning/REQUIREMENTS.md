# Requirements: MOCA v1.8 Intent Routing Safety Hardening

**Defined:** 2026-06-21  
**Milestone:** v1.8 Intent Routing Safety Hardening

## Core Value

When a merchant or support agent asks about a refund issue, the system must retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure any risky action goes through approval before execution -- never silently executing something irreversible.

## Milestone Goal

Harden MOCA's ordinary-chat intent/routing layer for production-style multi-turn safety: raw LLM classification remains advisory, deterministic policy produces the effective classification and route, risk is tiered by intent/operation/role/channel, workflow state can answer pending clarifications before reclassification, and inherited slots can be traced, reset, and evaluated.

## v1 Requirements

### Classification Traceability

- [ ] **IRS-01:** Agent traces expose raw LLM classification, deterministic pre-route decision, policy overrides, effective classification, risk tier, final route, and reason codes for every ordinary-chat intent/routing decision.
- [ ] **IRS-02:** Business code consumes the effective classification and route decision, not the raw LLM classification, and tests prove policy overrides are audit-visible.

### Risk Tier Policy

- [ ] **IRS-03:** Ordinary-chat risk policy resolves a `RiskTier` from primary intent, requested operation, user role, channel, and routing hints.
- [ ] **IRS-04:** Approval decisions or direct execution attempts in ordinary chat resolve to a blocked or approval-gated tier without writing approval, action, or execution authority state.
- [ ] **IRS-05:** Existing high-risk intent behavior remains backward-compatible until callers migrate to risk tiers.

### Workflow-State-First Routing

- [ ] **IRS-06:** The graph checks active workflow state before ordinary classification so pending slot clarifications can treat short identifier replies as answers to the current flow.
- [ ] **IRS-07:** Ambiguous short replies such as "继续吧", "同意", or "就按上面的处理" cannot execute actions or approve decisions when no trusted pending flow exists.

### Slot Provenance and Invalidation

- [ ] **IRS-08:** Active slot metadata records provenance, confidence, observed time, compatibility, tenant/user/thread scope, and whether the value was explicit in the current turn or inherited from trusted memory.
- [ ] **IRS-09:** Deterministic invalidation/reset handles user negation or context switching such as "不是这个订单", "换另一个", and "我说的是另外一个工单".
- [ ] **IRS-10:** Explicit current-turn slots continue to override inherited slots, and invalidated inherited slots cannot satisfy required slot completeness.

### Evaluation and Regression Coverage

- [ ] **IRS-11:** Intent golden or focused regression cases verify expected primary intent, requested operation, route, risk tier, clarification reason, and memory inheritance/invalidation behavior.
- [ ] **IRS-12:** Approval/action boundary regressions prove the new trace/risk/workflow/slot logic preserves existing evidence, business fact, memory, approval, action, and replay authority boundaries.

## v2 / Future Requirements

- [ ] **IRS-FUT-01:** Manifest-owned deterministic blockers and hard-negative pattern groups for every future intent.
- [ ] **IRS-FUT-02:** Separate `ResponseMode` taxonomy for direct answers, evidence-grounded answers, business-fact answers, policy-plus-fact recommendations, draft replies, clarification, refusal, and handoff.
- [ ] **IRS-FUT-03:** Full PR admission checklist for newly added intents, including multi-turn, memory, prompt-injection, unsafe-action, and channel/capability cases.

## Out of Scope

| Feature | Reason |
|---------|--------|
| LLM free-routing or agent-selected tools | Violates MOCA's deterministic routing and tool/capability boundary. |
| Real external action execution | Still owned by future Phase 17 External Action Execution. |
| Approval UI or approval lifecycle redesign | This milestone only blocks unsafe ordinary-chat decisions and preserves existing approval boundaries. |
| Full response-mode taxonomy rollout | Tracked as `IRS-FUT-02`; v1.8 keeps scope to trace/risk/workflow/slot hardening. |
| Memory as policy evidence, business fact, approval/action authority, or replay truth | Violates established v1.7 memory authority boundaries. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| IRS-01 | Phase 25 | Pending |
| IRS-02 | Phase 25 | Pending |
| IRS-03 | Phase 25 | Pending |
| IRS-04 | Phase 25 | Pending |
| IRS-05 | Phase 25 | Pending |
| IRS-06 | Phase 25 | Pending |
| IRS-07 | Phase 25 | Pending |
| IRS-08 | Phase 25 | Pending |
| IRS-09 | Phase 25 | Pending |
| IRS-10 | Phase 25 | Pending |
| IRS-11 | Phase 25 | Pending |
| IRS-12 | Phase 25 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---
*Requirements defined: 2026-06-21 for v1.8 Intent Routing Safety Hardening.*
