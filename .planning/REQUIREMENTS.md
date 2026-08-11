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

- [x] **SC-64.1-1**: Every actionable recommendation, including Chinese and English variants, resolves through the canonical action taxonomy before material claims and routing; unknown, ambiguous, and schema-invalid candidates fail closed.
- [x] **SC-64.1-2**: One deterministic backend evaluator covers configured high-, medium-, and low-risk rules, and LLM/config failures cannot downgrade risk or auto-allow an unproven action.
- [x] **SC-64.1-3**: Approval list/get/SSE/decide share one versioned decision-context contract that the frontend echoes without inference; stale, mismatched, cross-scope, and ambiguous outcomes fail closed.
- [x] **SC-64.1-4**: Auto-allowed demo draft creation requires a durable server-minted, one-use capability bound to trusted scope, actor, action, hashes, risk decision, expiry, and the sole permitted handler.
- [x] **SC-64.1-5**: End-to-end safety and terminal-state tests prove denied, stale, malformed, unsupported, authorization, draft, and audit failures cannot create an unauthorized draft or report successful completion.

### Evidence Identity Immutable Replay And Memory Provenance

- [x] **SC-64.2-1**: Only successful, complete, scope-valid authoritative tool or retrieval observations with validated canonical source references can enter CWC `verified_facts`; all denied, unavailable, stale, malformed, partial, timeout, error, unresolved, and compatibility-only observations remain non-authoritative and cannot enter reviewed case memory as verified facts.
- [x] **SC-64.2-2**: Evidence identity has one tenant-bound canonical computation and validation path shared by ingestion, retrieval, agent state, APIs, memory, approval snapshots, and replay; forged, mismatched, cross-scope, and ambiguous legacy aliases fail closed without existence leakage.
- [x] **SC-64.2-3**: Re-ingestion and correction retain immutable document/chunk/evidence versions, and replay resolves the exact original version, content hash, scope, and integrity binding after supersession, archival, expiry, or tombstoning; compatibility backfill upgrades only uniquely provable legacy refs.
- [x] **SC-64.2-4**: Nodes, services, events, stores, deduplication, and review flows consume one version-aware memory candidate identity owner, while reviewed case-memory records preserve real tenant/scope, source status/authority, source run/event/evidence refs, reviewer decision, candidate identity, and correction/supersession lineage.
- [x] **SC-64.2-5**: Database uniqueness, lifecycle compare-and-set, idempotent services, and PostgreSQL concurrency tests prevent duplicate candidates or competing reviews and enforce deterministic expiry, rejection, correction, supersession, deletion, and tombstone no-resurrection behavior without merging distinct identities.

### Token-Aware Policy Chunking And Reindex Validation

- [ ] **SC-64.4-1**: One versioned model-to-tokenizer contract provides deterministic offline counts for the configured embedding model and has a provider-backed parity check against reported usage without exposing credentials or production text.
- [ ] **SC-64.4-2**: Every final embedding input, including title, section, table headers, overlap, and allowed source context, stays within the configured token maximum; existing structural/provenance boundaries remain intact and identical source plus configuration produces identical chunks.
- [ ] **SC-64.4-3**: Production ingestion, dry-run, and golden validation consume one authoritative chunk assembly contract, with regression coverage for Chinese, English, mixed text, long unpunctuated text, tables, OCR content, URLs, numbers, and tokenizer failure behavior.
- [ ] **SC-64.4-4**: Chunker/tokenizer/model versions and actual token counts are auditable, and rechunking cannot silently reuse incompatible policy/chunk/evidence identity or break historical replay semantics established by Phase 64.2.
- [ ] **SC-64.4-5**: Reindexing is isolated, resumable, and rollback-safe so failures preserve the prior usable index and no tenant observes a partially mixed old/new corpus.
- [ ] **SC-64.4-6**: A versioned A/B report compares character- and token-aware candidates on Phase 64.3 Hit@1/3/5, MRR, anchor/locator coverage, format parity, duplicate rate, chunk count, latency, and embedding token cost; the selected configuration satisfies explicit non-regression gates and existing RAG tests pass.

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
| SC-64.1-1 | Phase 64.1 | Complete |
| SC-64.1-2 | Phase 64.1 | Complete |
| SC-64.1-3 | Phase 64.1 | Complete |
| SC-64.1-4 | Phase 64.1 | Complete |
| SC-64.1-5 | Phase 64.1 | Complete |
| SC-64.2-1 | Phase 64.2 | Complete |
| SC-64.2-2 | Phase 64.2 | Complete |
| SC-64.2-3 | Phase 64.2 | Complete |
| SC-64.2-4 | Phase 64.2 | Complete |
| SC-64.2-5 | Phase 64.2 | Complete |
| SC-64.4-1 | Phase 64.4 | Planned |
| SC-64.4-2 | Phase 64.4 | Planned |
| SC-64.4-3 | Phase 64.4 | Planned |
| SC-64.4-4 | Phase 64.4 | Planned |
| SC-64.4-5 | Phase 64.4 | Planned |
| SC-64.4-6 | Phase 64.4 | Planned |

**Coverage:**
- v2.2 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0

---
*Requirements defined: 2026-07-09*
*Last updated: 2026-08-11 for Phase 64.4 planning*
