# Phase 9: Business Tool Facade - Context

**Gathered:** 2026-06-06
**Status:** Seeded (pre-planning) — only the existing-code relationship is locked; full discuss-phase still pending
**Source:** Reviewer-confirmed codebase fact about prior tool registry implementation

<domain>
## Phase Boundary

Phase 9 routes read business tools through a `BusinessToolService` facade using the trusted
`ToolCallContext` (`tool_context.v2`) and typed `ToolResult` (`tool_result.v2`) contracts from
`docs/agent-architecture-spec.md`. Read tools must go through the facade; nodes must stop calling
repo/tool internals directly. Write/action execution stays outside this facade.

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
- **Reuse:** the **adapter layer** (`get_order_adapter`, `get_refund_case_adapter`,
  `get_ticket_adapter`, `search_policy_adapter`) and tenant-scoped fetch logic; the
  **evidence-ref extraction** (`_evidence_refs_from_data`) and summary-field projection that
  avoids exposing raw upstream payloads. These align with Phase 9 success criteria.
- **Replace:** `ToolInvocationContext` (5 fields) must be replaced by the spec `ToolCallContext`
  (`tool_context.v2`, ~18 fields incl. permissions, merchant_scope, thread_id/run_id/trace_id,
  tool_call_id, deadline_at, idempotency_key, policy_snapshot_ref). The 2-state
  `ToolExecutionResult` (success/error) must be replaced by the 9+ state `ToolResult`
  (`tool_result.v2`: success/partial_success/not_found/permission_denied/timeout/unavailable/
  conflict/invalid_request/invalid_response).
- **Drop:** the `investigator` / `allowed_in_investigator` / `INVESTIGATOR_TOOL_NAMES` whitelist
  semantics. The new architecture has no bounded-investigator caller; do not carry that concept
  into the facade.
- **Do NOT** assume the existing registry already satisfies any Phase 9 contract. The spec
  (Section ~90) records it as current evidence with the explicit gap: "main graph nodes still
  call concrete tool functions directly, not through BusinessToolService."

**Why this is locked here:** to claim the orphaned prior-line code (no roadmap phase currently
owns it) and to stop the planner from either re-building the adapters from scratch or being
misled by the obsolete investigator whitelist / 2-state result semantics.

### Open for discuss-phase
- Exact `BusinessToolService` module location (spec suggests `src/business_tools/service.py`).
- Whether any facade persistence/audit table is introduced (if yes, Phase 9 owns its
  migration/read-switch/rollback per decomposition schema-ownership rules; if no, record `N/A`).
- Per-tool timeout/partial-success handling and fallback-vs-clarification routing.
</decisions>

<canonical_refs>
## Canonical References

Downstream agents MUST read these before planning or implementing.

- `docs/agent-architecture-spec.md` — `ToolCallContext`/`ToolRequest`/`ToolResult` v2 definitions
  (~line 1323), `BusinessToolService.fetch_context` (~line 584), current-evidence note (~line 90),
  Phase 9 row in the phase table (~line 2733), `business_context_fetch` node contract (~line 828).
- `docs/agent-architecture-phase-decomposition.md` — Phase 9 boundary, dependency (Phase 7),
  schema-ownership rule for any introduced facade persistence.
- `.planning/phases/07-contract-baseline/07-CONTRACT-BASELINE.md` — coverage matrix and follow-up
  register entries that name Phase 9 as owner.
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
