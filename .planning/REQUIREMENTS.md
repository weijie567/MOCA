# Requirements: MOCA v2.2 Product Experience Fixes

**Defined:** 2026-07-09
**Core Value:** When a merchant or support agent asks about a refund issue, the system must retrieve relevant business data and rules, provide an evidence-backed answer, and ensure any risky action goes through approval before execution — never silently executing something irreversible.

## v2.2 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Response UX

- [x] **UX-01**: User receives an accurate, non-evidence-claiming response for greetings and standalone small talk.
- [x] **UX-02**: User receives a clear unsupported-capability response when asking for a capability the system does not support.
- [x] **UX-03**: User sees clarification prompts that explain why an identifier or filter is needed and what inputs are accepted.
- [x] **UX-04**: User never sees final-response wording that claims RAG/policy evidence was used when the run did not retrieve or verify evidence.

### Business Metrics

- [x] **MET-01**: User can ask natural-language operational metric questions such as order count, refund count, pending ticket count, coupon issuance count, and merchant refund rate.
- [x] **MET-02**: Metric queries support explicit metric, resource type, time range, status filter, and merchant filter slots where applicable.
- [x] **MET-03**: Metric responses include the numeric answer plus the scope, time range, filters, and data freshness used to compute it.
- [x] **MET-04**: Missing or ambiguous metric scope is handled by clarification instead of guessing a hidden statistic.

### Scope And Permissions

- [x] **SCOPE-01**: Support users can only receive metric answers for their authorized merchant scope.
- [x] **SCOPE-02**: Manager users can only receive metric answers for the merchants or merchant groups they manage.
- [x] **SCOPE-03**: Admin users can only receive metric answers inside their configured management scope, not by bypassing tenant or merchant boundaries.
- [x] **SCOPE-04**: Unauthorized metric queries fail closed without revealing whether out-of-scope resources or merchants exist.

### Agent Console

- [x] **CONSOLE-01**: User can distinguish direct responses, clarification requests, unsupported requests, evidence-backed answers, and metric answers in the timeline.
- [x] **CONSOLE-02**: User can see a concise reason when the agent asks for more information or refuses an unsupported capability.
- [x] **CONSOLE-03**: User can retry or start a new query after unsupported, clarification, or error outcomes without stale state leaking into the next run.

### UX Regression

- [x] **EVAL-01**: The project has a repeatable UX regression set for the concrete prompts that previously produced confusing behavior.
- [x] **EVAL-02**: The UX regression set covers role/scope cases for support, manager, and admin metric queries.
- [x] **EVAL-03**: Local validation documents the expected Agent Console behavior for v2.2 demo flows.

### Runtime Safety And Approval Contract Repair

- [ ] **SC-64.1-1**: Every actionable recommendation, including Chinese and English variants, resolves through the canonical action taxonomy before material claims and routing; unknown, ambiguous, and schema-invalid candidates fail closed.
- [ ] **SC-64.1-2**: One deterministic backend evaluator covers configured high-, medium-, and low-risk rules, and LLM/config failures cannot downgrade risk or auto-allow an unproven action.
- [ ] **SC-64.1-3**: Approval list/get/SSE/decide share one versioned decision-context contract that the frontend echoes without inference; stale, mismatched, cross-scope, and ambiguous outcomes fail closed.
- [ ] **SC-64.1-4**: Auto-allowed demo draft creation requires a durable server-minted, one-use capability bound to trusted scope, actor, action, hashes, risk decision, expiry, and the sole permitted handler.
- [ ] **SC-64.1-5**: End-to-end safety and terminal-state tests prove denied, stale, malformed, unsupported, authorization, draft, and audit failures cannot create an unauthorized draft or report successful completion.

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Analytics Expansion

- **ANL-01**: User can group metrics by day, merchant, category, or status and compare periods.
- **ANL-02**: User can export metric answers or reports.
- **ANL-03**: User can view chart-based dashboards for metric trends.
- **ANL-04**: User can schedule recurring metric reports.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Arbitrary SQL or free-form database exploration | Violates ToolPlatform, trusted context, and scope boundaries. |
| Cross-tenant analytics | Not needed for demo UX and unsafe without separate tenant-admin contracts. |
| Full BI dashboard or chart builder | v2.2 is an Agent Console UX milestone, not an analytics product milestone. |
| Real external action execution | Remains owned by the future External Action Execution milestone. |
| Using memory or RAG as metric authority | Metrics must come from scoped business facts / business data queries. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| UX-01 | Phase 61 | Complete |
| UX-02 | Phase 61 | Complete |
| UX-03 | Phase 61 | Complete |
| UX-04 | Phase 61 | Complete |
| MET-01 | Phase 61 | Complete |
| MET-02 | Phase 61 | Complete |
| MET-03 | Phase 61 | Complete |
| MET-04 | Phase 61 | Complete |
| SCOPE-01 | Phase 61 | Complete |
| SCOPE-02 | Phase 61 | Complete |
| SCOPE-03 | Phase 61 | Complete |
| SCOPE-04 | Phase 61 | Complete |
| CONSOLE-01 | Phase 61 | Complete |
| CONSOLE-02 | Phase 61 | Complete |
| CONSOLE-03 | Phase 61 | Complete |
| EVAL-01 | Phase 61 | Complete |
| EVAL-02 | Phase 61 | Complete |
| EVAL-03 | Phase 61 | Complete |
| SC-64.1-1 | Phase 64.1 | Pending |
| SC-64.1-2 | Phase 64.1 | Pending |
| SC-64.1-3 | Phase 64.1 | Pending |
| SC-64.1-4 | Phase 64.1 | Pending |
| SC-64.1-5 | Phase 64.1 | Pending |

**Coverage:**
- v2.2 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0

---
*Requirements defined: 2026-07-09*
*Last updated: 2026-07-10 for Phase 64.1 planning*
