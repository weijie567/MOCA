# Phase 9: Business Tool Facade - Context

**Gathered:** 2026-06-06
**Status:** Seeded (pre-planning) — only the existing-code relationship is locked; full discuss-phase still pending
**Source:** Reviewer-confirmed codebase fact about prior tool registry implementation

<domain>
## Phase Boundary

Phase 9 routes read business tools through a `BusinessToolService` facade using the trusted
`ToolCallContext` (`tool_context.v2`) and typed `ToolResult` (`tool_result.v2`) contracts from
`docs/contract-spec.md` Section 12. Read tools must go through the facade; nodes must stop calling
repo/tool internals directly. Write/action execution stays outside this facade. Business tool results
carry provenance via `source_system`, `data_freshness_at`, and `business_fact_refs`; they do not reuse
the policy EvidenceRefV1, so Phase 9 has no schema dependency on Phase 8.

Requirements: TOOL-01, TOOL-02, TOOL-03.
</domain>

<decisions>
## Implementation Decisions

### Relationship to existing tool registry (LOCKED)

There is pre-existing tool code in the repo from the **previous v1.1 "Agentic Investigation"
planning line** (now replaced). It was never wired into the main graph and was designed for a
bounded read-only investigator, not for the Phase 9 facade. Phase 9 must treat it as follows:

- **Files:** `src/agent/tools/registry.py`, `src/agent/tools/contracts.py`,
  `tests/agent/test_tools/test_registry.py`, `tests/agent/test_tools/test_tool_contracts.py`,
  and the adapter layer they import (`src/agent/tools/adapters.py`).
- **Reuse:** the **business-tool adapter layer** (`get_order_adapter`, `get_refund_case_adapter`,
  `get_ticket_adapter`) and tenant-scoped fetch logic; the summary-field projection that avoids
  exposing raw upstream payloads. Business tool results use `business_fact_refs` for provenance and
  must not emit policy `EvidenceRefV1`.
- **Do NOT own policy knowledge:** `search_policy_adapter` and policy EvidenceRef extraction
  (`_evidence_refs_from_data` for policy chunks) belong to the Phase 8 KnowledgeService, not the
  BusinessToolService. Phase 9 does not re-own Knowledge/RAG retrieval or policy evidence production
  and emits business-fact provenance through `business_fact_refs` only.
- **Replace:** `ToolInvocationContext` (5 fields) must be replaced by the spec `ToolCallContext`
  (`tool_context.v2`, ~18 fields incl. permissions, merchant_scope, thread_id/run_id/trace_id,
  tool_call_id, deadline_at, idempotency_key, policy_snapshot_ref). The 2-state
  `ToolExecutionResult` (success/error) must be replaced by the 9+ state `ToolResult`
  (`tool_result.v2`: success/partial_success/not_found/permission_denied/timeout/unavailable/
  conflict/invalid_request/invalid_response).
- **Drop:** the old registry's `investigator` / `allowed_in_investigator` /
  `INVESTIGATOR_TOOL_NAMES` whitelist code semantics from the replaced v1.1 planning line.
  Phase 10's `investigate` is a bounded read-only tool loop and bounded caller of
  `BusinessToolService` (P10-DEV-02); the facade must be loop-ready but does not implement loop
  control. `max_iterations`, tool selection, termination judgement, and result consumption/routing
  belong to Phase 10's loop/router; the facade owns the per-call boundary. P10-DEV-02 reverses only
  the "no bounded caller" stance: the old whitelist implementation must still be dropped, and the
  locked service-layer reuse decision above remains unaffected.
- **Do NOT** assume the existing registry already satisfies any Phase 9 contract. The spec
  (`docs/contract-spec.md` §8 producer annotation (top of §8) and the Phase 7 baseline current-evidence row) records it
  as current evidence with the explicit gap: "main graph nodes still call concrete tool functions
  directly, not through BusinessToolService."

**Why this is locked here:** to claim the orphaned prior-line code (no roadmap phase currently
owns it) and to stop the planner from either re-building the adapters from scratch or being
misled by the obsolete investigator whitelist / 2-state result semantics.

### Open for discuss-phase
- Exact `BusinessToolService` module location (spec suggests `src/business_tools/service.py`).
- Whether any facade persistence/audit table is introduced (if yes, Phase 9 owns its
  migration/read-switch/rollback per decomposition schema-ownership rules; if no, record `N/A`).
- Per-tool timeout/partial-success handling at the facade per-call boundary. Fallback-vs-clarification
  routing belongs to Phase 10's `route_after_investigate`; routing/consumption is not a Phase 9
  facade open question.
- Phase 9 planning gate: `BusinessFactRefV1` schema must be imported from contract-spec and implemented before Phase 9 execution; adapters must populate tenant_id/source_system/resource_type/resource_id/retrieved_at and data_freshness_at where available.
</decisions>

<canonical_refs>
## Canonical References

Downstream agents MUST read these before planning or implementing.

- `docs/contract-spec.md` Section 12.5 — `ToolCallContext`/`ToolRequest`/`ToolResult` v2 definitions;
  Section 8.4 — `BusinessToolService.fetch_context` signature; `docs/contract-spec.md` §8 producer annotation (top of §8) and the Phase 7 baseline current-evidence row — current-evidence
  gap ("main graph nodes still call concrete tool functions directly"); Section 9.4 `business_context_fetch`
  node contract; Section 8.0 — canonical `TrustedContext` that `ToolCallContext` projects; `docs/migration-plan.md`
  Section 19 Phase 9 row. (Use section numbers, not line numbers; the spec was split into four files.)
- `docs/agent-architecture-phase-decomposition.md` — Phase 9 boundary, dependency (Phase 7),
  schema-ownership rule for any introduced facade persistence.
- `.planning/phases/07-contract-baseline/07-CONTRACT-BASELINE.md` — coverage matrix and follow-up
  register entries that name Phase 9 as owner.
- `.planning/phases/10-state-lifecycle-routing-migration/10-04-PLAN.md`
  `<phase_9_loop_facing_contract>` — required loop-facing design input (anti-rework payload) for
  building Phase 9 `BusinessToolService` loop-ready.
- `src/agent/tools/registry.py`, `src/agent/tools/contracts.py`, `src/agent/tools/adapters.py` —
  existing prior-line tool code (see locked decision above).
- `src/agent/nodes/load_business_context.py` — current direct-call node Phase 9 must migrate.
</canonical_refs>

<deferred>
## Deferred Ideas

None recorded yet — full deferral list to be set during discuss-phase.
</deferred>

---

*Phase: 09-business-tool-facade*
*Context seeded 2026-06-06 — registry relationship locked; remaining context pending discuss-phase*
