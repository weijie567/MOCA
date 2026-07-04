# Requirements: MOCA v2.1 Core Subsystem Hardening

**Defined:** 2026-07-01 (rescoped 2026-07-02 from "Tool Platform Hardening" to "Core Subsystem Hardening")
**Core Value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.

**Milestone goal:** Clear architecture debt across MOCA's core subsystems (tool call / intent recognition / RAG / memory, tracked in `.planning/ARCHITECTURE-DEBT.md`) so each subsystem's contracts are as sound as the codebase allows and `docs/contract-spec.md` agrees with the implementation. This is an umbrella hardening milestone: defect-fix / debt-clearing work is appended as the next integer phase; new user-facing capability opens a new milestone.

## Tool Platform Requirements (Phase 37-41)

### Tool Contract Integrity

- [x] **TPH-01**: Each of the eight registered tools (`get_order`, `get_refund_case`, `get_ticket`, `get_logistics`, `get_merchant_risk`, `search_policy`, `search_sop`, `search_case_memory`) declares a real `output_schema` for `ToolResultV2.data`, and the `ToolRuntime` output-validation gate enforces it — an executor result whose `data` fails the declared schema is mapped to an `invalid_response` `ToolResultV2` instead of passing through, replacing the current no-op `{"type":"object"}`.
- [x] **TPH-02**: `docs/contract-spec.md` §12.5/§12.6 normative type definitions match the implemented contract fields — adding the implemented-but-unspecified fields (`ToolDescriptor.executor` / `exposure` / `requires_approval` / `requires_safety_snapshot` / `requires_idempotency_key`, `event_family` value `action`, `ToolPolicyDecision.runtime_available` / `availability_summary`, `ToolCallContext.effective_at` / `approval_ref` / `safety_snapshot_ref`) — without redefining, widening, or renaming any §8.0-locked `TrustedContext`-projected identity field. Spec change goes through the dual-AI review workflow.
- [x] **TPH-05**: Close post-TPH-01 validation gaps confirmed from source review: `create_coupon_grant_draft` must use a strict action-draft output schema, domain-scope handoff markers must have an architecture/backstop test tied to BusinessFactService merchant-scope/no-leak enforcement, and the local `validate_json_value` subset must implement or meta-block every descriptor schema keyword it advertises. This must not change the `ToolResultV2` envelope, `ToolCallContext` §8.0 identity fields, BusinessFactService ownership runtime split, `docs/contract-spec.md`, or `UnifiedToolManager` compatibility behavior.
- [x] **TPH-06**: Remove the `UnifiedToolManager` legacy compatibility adapter and converge graph-facing tool dispatch, injection seams, tests, public exports, and `docs/contract-spec.md` on `ToolPlatform` as the single canonical entrypoint. This is a breaking cleanup/API decision and must include implementation code review before milestone archive.

### Tool Declaration Consolidation

- [x] **TPH-03**: Tool declarations resolve from a single-source registry; duplicate hardcoded lists (`catalog._IDENTIFIER_SCHEMAS`, `manager.INVESTIGATE_TOOL_NAMES`) are either derived from that registry or consistency-checked against it, so adding or changing a tool does not require hand-editing multiple lists (satisfies spec §12.6 single-declaration / no-drift rule).

### Runtime / Policy Internal Convergence

- [x] **TPH-04**: `ToolRuntime` failure paths produce their `(error result, projection, decision event, outcome tuple)` through one shared helper rather than ten duplicated branches, and `ToolPolicyEngine.runtime_auth` expresses its authorization checks as a declarative gate sequence — with existing tool-platform, policy, and runtime tests remaining green and no change to any external contract shape.

## Intent Recognition Requirements (Phase 42+)

> Subsystem debt is tracked in `.planning/ARCHITECTURE-DEBT.md` §2 (ID-01..ID-04, ID-DESIGN). Requirement IDs use the `IDR-` prefix.

- [x] **IDR-01**: Intent recognition's three coupled responsibilities are decoupled into three explicit, single-direction, independently-testable layers communicating only through frozen data contracts: semantic layer (`SemanticIntent`), risk-authorization layer (`RiskDecision` + declarative `RISK_POLICY_TABLE`), and confidence-clarification layer (`ClarificationDecision`). Keyword arbitration (`derive_keyword_signals` + `arbitrate_intent`) is explicit — a keyword candidate may override the LLM primary only when the LLM itself listed the intent or raw confidence is below the ordinary threshold (fixes ID-01). Risk resolution is table-driven with the dead if-elif branch removed (fixes ID-03). Behavior-equivalent refactor: the sole registered behavior change is that `"这个不算投诉吧，我就是问下退款进度"` no longer mis-escalates to `complaint_escalation`. `calibrated_confidence` is a placeholder parameter only — real calibration (ID-02) remains unaddressed. Multi-intent / TaskPlan (ID-04) is out of scope for this requirement.
- [x] **IDR-02**: Intent recognition preserves multi-intent utterances as a bounded tier-A `TaskPlan` while keeping the existing single-intent route contract intact: N=1 remains behavior-equivalent, N>1 records ordered `TaskStep`s, normalizes only explicit modifier cases, processes only s1 in the current turn, and exposes all later steps as `deferred_steps` in trace and final response. This fixes the ID-04 failure mode where secondary user requests are silently dropped, without adding automatic dependency execution, DAG/resume behavior, new LLM calls, `IntentResultV3` schema changes, prompt changes, confidence calibration, or new risk-tier enums.

## Memory Requirements (Phase 44+)

> Subsystem debt is tracked in `.planning/ARCHITECTURE-DEBT.md` (memory subsystem, the fourth core subsystem). Core redesign requirement IDs use the `MEM-` prefix; urgent inserted compatibility cleanups use the `MEM-COMPAT-` prefix. Design input: `.planning/MEMORY-REDESIGN-DECISIONS.md` (D1–D5, P1=many-to-many, P2=standalone table, P3=long_term kept narrow). Red line D5: MUST NOT rename `case_memories` / `long_term_memories` tables.

- [x] **MEM-01**: A case-scoped durable working-context layer exists as a new standalone `case_working_contexts` table, keyed by `(tenant_id, case_id)`, holding the current case's working state (customer request, claims, verified facts, missing info, actions taken, policy refs, agent recommendations + staff decisions, pending tasks, commitments, next action). It is non-authoritative (`authority_class = contextual_only`), human-correctable, versioned, and every write is bound to trusted `run_id` + `source_ref`. Claims and verified facts are stored as separate structures; tool-derived facts store only a reference/summary plus `observed_at` and never replace the business system of record; policy body text and sensitive raw PII are never stored. Phase 44 provides the callable audited write service and durable read/write surface; graph run-completion auto-update hook wiring is deferred to Phase 45 memory lifecycle wiring. This does NOT change the session-memory layer, does NOT extract precedents, and does NOT rename existing memory tables.
- [x] **MEM-02**: thread↔case is modeled as an explicit many-to-many association (a thread may touch multiple cases; a case may span multiple threads/handoffs), supplementing the single nullable `case_id` / `refund_case_id` foreign-key columns for working-context linkage. The association is the join surface used to resolve a case's working context regardless of which thread the current turn runs in. Existing single-FK columns are not dropped in this phase (no destructive migration); the new association table is additive.
- [x] **MEM-03**: Session context is repositioned after Case Working Context lands: `session_memories` remains thread-scoped short-lived conversational context only, with clear read/write boundaries and contract tests preventing it from becoming cross-case durable state, reviewed precedent, long-term preference memory, policy evidence, business fact authority, approval/action authority, or replay truth. This phase must preserve existing `session_memories` table identity unless planning explicitly proves a migration is required.
- [x] **MEM-04**: `case_memories` is locked as reviewed case precedent, not active case working state. Closed-case precedent generation is introduced only as a governed candidate path from finalized Case Working Context into `case_memories` review flow, with metadata-first retrieval semantics, `needs_review`/audit behavior, and no destructive table rename.
- [x] **MEM-05**: `long_term_memories` is narrowed to explicit tenant preference memory. Writes happen only from explicit "remember this preference" / admin-save / reviewed candidate paths, not generic automatic run summarization, and must not store order/refund/ticket state, policy rules, approvals, action authorization, sensitive raw PII, or business system truth.
- [ ] **MEM-COMPAT-01**: Active memory-context compatibility readers are migrated to canonical surfaces without destructive renames: thread↔case relationship reads use `thread_case_links` / `ThreadCaseLinkRepository` instead of `conversation_threads.case_id`; agent routing, working-state projection, and prompt/session context helpers read `session_context` / `session_context_bundle` before legacy `session_memory` / `session_memory_bundle`; reviewed-memory loading gains canonical `needs_reviewed_memory_context` while `needs_long_term_memory` remains an alias. This cleanup must not rename/drop memory tables, `conversation_threads.case_id`, public memory API routes, graph trace node names, `long_term_fact` storage identity, `session_memory_*` config names, or the debug-only legacy precedent service.

## Future Requirements

_None beyond active Phase 48.1 compatibility cleanup._

## Out of Scope

| Feature | Reason |
|---------|--------|
| Changing `ToolCallContext` identity fields | Locked by spec §8.0 as `TrustedContext` projections — MUST NOT redefine/widen/rename. |
| Rebuilding domain ownership / merchant-scope enforcement | Already implemented in BusinessFactService (`_merchant_scope_allows` + no-leak); not a gap. |
| High-blast-radius `ToolResultV2` field additions/removals | 7 external consumers; defer envelope field changes, keep this milestone to `output_schema` (data-shape) enforcement only. |
| New tools or new executors | Milestone is contract/impl hardening of existing 8 tools, not capability expansion. |
| New policy gates (rate limit, cost budget) | TPH-04 only makes the gate pipeline declarative to enable future gates; it does not add them. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TPH-03 | Phase 37 | Complete |
| TPH-04 | Phase 37 | Complete; DB-backed pytest pending local PostgreSQL |
| TPH-01 | Phase 38 | Complete; DB-backed pytest passed |
| TPH-02 | Phase 39 | Complete |
| TPH-05 | Phase 40 | Complete |
| TPH-06 | Phase 41 | Complete |
| IDR-01 | Phase 42 | Complete (retroactively registered; code committed at `a0a98e4`) |
| IDR-02 | Phase 43 | Complete |
| MEM-01 | Phase 44 / Phase 45 | Complete (write service/read-write surface delivered in Phase 44; graph lifecycle hook delivered in Phase 45) |
| MEM-02 | Phase 44 | Complete |
| MEM-03 | Phase 46 | Complete |
| MEM-04 | Phase 47 | Complete |
| MEM-05 | Phase 48 | Complete |
| MEM-COMPAT-01 | Phase 48.1 | Pending |

**Coverage:** 14/14 v2.1 requirements mapped. 13 complete, 1 pending. No orphans, no duplicates. (Tool platform: TPH-01..06 / Phase 37-41. Intent recognition: IDR-01 / Phase 42, IDR-02 / Phase 43. Memory: MEM-01/02 / Phase 44-45, MEM-03 / Phase 46, MEM-04 / Phase 47, MEM-05 / Phase 48, MEM-COMPAT-01 / Phase 48.1.)
