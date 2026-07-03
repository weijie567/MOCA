---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Core Subsystem Hardening
status: executing
stopped_at: Completed 45-01-PLAN.md
last_updated: "2026-07-03T05:11:32.018Z"
last_activity: 2026-07-03 -- Phase 45 plan 45-01 completed
progress:
  total_phases: 9
  completed_phases: 8
  total_plans: 26
  completed_plans: 23
  percent: 88
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-01)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Phase 45 — memory-lifecycle-wiring-for-case-working-context

## Rescope note (2026-07-02)

- v2.1 was originally scoped/named "Tool Platform Hardening" (Phase 37-41). It is rescoped to **Core Subsystem Hardening**: a long-lived umbrella for cleaning up architecture debt across the four core subsystems tracked in `.planning/ARCHITECTURE-DEBT.md` (tool call / intent recognition / RAG / memory).
- **Standing rule (avoids re-asking each time):** work that *fixes existing-subsystem defects or clears architecture debt* is appended as the next integer phase inside v2.1 (42, 43, …) — no new milestone. A **new milestone** is opened only for a genuinely new user-facing product capability (not a defect fix). Tool platform is the first subsystem cleared; intent recognition is the second.

## Current Position

Phase: 45 (memory-lifecycle-wiring-for-case-working-context) — EXECUTING
Plan: 2 of 4
Status: Ready to execute
Last activity: 2026-07-03 -- Phase 45 plan 45-01 completed
Next: Execute Phase 45 plan 45-02 for active CWC read and run_auto thread-case link wiring.

Progress: [█████████░] 88%

Planning files: `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/MILESTONES.md`, and archived milestone files.

## Current Milestone Context

- v2.1 is a bounded, pre-scoped cleanup of the tool-call platform's contract debt and implementation gaps, not a new user-facing feature.
- Sole normative contract source: `docs/contract-spec.md` §12.5/§12.6 and §8.0. All tool contract code lives under `src/tools/` (catalog.py, contracts.py, runtime.py, policy.py, platform.py, projection.py, executors/).
- Blast-radius tiering drives sequencing: `ToolResultV2` and `ToolCallContext` are HIGH (7 external consumers); `ToolInvocationOutcome` / `ToolViewV1` / `ToolPolicyDecision` are effectively src/tools-internal (LOW). Defer HIGH-blast-radius envelope field changes; keep v2.1 to `output_schema` (data-shape) enforcement and internal refactors.
- `ToolCallContext` §8.0 identity fields (`tenant_id/user_id/role/permissions/merchant_scope/session_id/thread_id/run_id/trace_id`) are locked — MUST NOT redefine, widen, or rename. Off-limits.
- Domain-level ownership/scope enforcement already lives in BusinessFactService (`_merchant_scope_allows` + no-leak) — not a gap, do not rebuild.
- `docs/contract-spec.md` was just touched by prior memory-alignment work (commit `4dcb673`); Phase 39 planning must re-check whether §12.5/§12.6 were incidentally modified before editing.
- Code implementation is delegated to Codex per the dual-AI workflow; Claude is plan designer and adjudicator. These are planning/spec phases.
- TPH-02 (spec edit) must go through the dual-AI review workflow (`gsd-plan-checker` + Codex cross-review + Claude adjudication).
- Phase 40 closes source-confirmed validation/backstop gaps left after TPH-01: action output schema hardening, domain-scope marker backstop tests, and JSON Schema subset/meta guard alignment. It must not change `ToolResultV2`, `ToolCallContext` §8.0 identity fields, BusinessFactService ownership runtime semantics, `docs/contract-spec.md`, or `UnifiedToolManager` compatibility behavior.

## Current Roadmap

| Phase | Plans | Status |
|-------|-------|--------|
| 37. Tool Declaration + Runtime/Policy Internal Consolidation (TPH-03, TPH-04) | 3/3 | Complete; DB-backed pytest pending |
| 38. output_schema Declaration + Runtime Output-Validation Enforcement (TPH-01) | 3/3 | Complete; DB-backed pytest passed |
| 39. contract-spec §12.5/§12.6 Reconciliation (TPH-02) | 1/1 | Complete |
| 40. Tool Contract Validation Hardening (TPH-05) | 3/3 | Complete |
| 41. Tool Platform Legacy Manager Cleanup (TPH-06) | 4/4 | Complete |
| 42. Intent Recognition Three-Layer Decoupling (IR-01) | 1/1 | Complete (retroactively registered) |
| 43. Intent Recognition Multi-Intent Tier A (IDR-02) | 3/3 | Complete |
| 44. Memory Layering — Case Working Context + thread-case Many-to-Many (MEM-01, MEM-02) | 4/4 | Complete |

Sequencing rationale: Phase 37 consolidates the registry and converges runtime/policy internals with no external contract change (LOW blast radius). Phase 38 declares `output_schema` in that consolidated registry and enforces it through the shared failure path. Phase 39 reconciles the spec to the final implemented state via dual-AI review. Phase 40 closes the source-confirmed validation/backstop gaps intentionally deferred or left advisory after Phase 38/39. Phase 41 then handles the explicit breaking cleanup/API decision to remove the `UnifiedToolManager` legacy compatibility adapter.

Phase 42 moves to the second subsystem (intent recognition): it splits intent classification into three explicit single-direction layers (semantic / risk-authorization / clarification), fixing ID-01 (keyword override of LLM) and ID-03 (three-dimension coupling) per `.planning/ARCHITECTURE-DEBT.md`. The code was implemented + verified before formal registration, so Phase 42 is **retroactively registered**: it has CONTEXT / VERIFICATION plus a record-only `42-01-PLAN.md` / `42-01-SUMMARY.md` pair anchored to commit `a0a98e4`, but no PLAN-REVIEW (it did not go through plan-then-execute). Multi-intent tier A (ID-04) is the next intent phase and WILL go through the full plan-phase + plan-checker + Codex review flow.

Phase 44 moves to the memory subsystem: it adds the durable Case Working Context layer and additive thread-case many-to-many association while preserving `case_memories`, `long_term_memories`, and `conversation_threads.case_id`. Graph lifecycle auto-update/read-active wiring is explicitly deferred to Phase 45.

## Last Milestone Context

- v2.0 Merchant Scope Hardening delivered Phase 36 (merchant-scope DB hardening / role cleanup) on 2026-06-30. Its remaining same-merchant trace/replay authorization scope stays future work and is not part of v2.1.
- v1.9 Agent Platform Foundation (Phases 26-35.1) shipped and archived on 2026-06-30. It landed the descriptor-driven `ToolView`, runtime `ToolPolicyDecision`, safe tool result projection, and ToolPlatform boundary that v2.1 now hardens.
- `docs/contract-spec.md` is the normative source. Preserve v1.9 service-boundary contracts unless a phase explicitly records a spec delta.
- Memory remains contextual only; policy evidence, business facts, approval/action authority, and replay truth keep their own authoritative services and schemas.

## Performance Metrics

**v1.9 shipped scope:** 12 phases, 19 v1 requirements, 51/51 phase plans complete. Milestone audit status: archived.
**v2.0 shipped scope:** Phase 36 (6/6 plans complete).
**Phase 38 plan 38-01:** 3 min, 2 tasks, 2 files modified; nullable validator and scoped-set contract complete.
**Phase 38 plan 38-02:** 3 min, 2 tasks, 2 files modified; catalog real output schemas and payload validation complete.
**Phase 38 plan 38-03:** 4 min, 2 tasks, 3 files modified; runtime invalid-response enforcement and high-blast consumer sweep complete, with DB-backed pytest passing after compose PostgreSQL startup.
**Phase 39 plan 39-01:** 4 min, 3 tasks, 2 files modified; docs-only contract-spec reconciliation for TPH-02 complete.
**Phase 40 plan 40-01:** strict action output schema for `create_coupon_grant_draft` complete; catalog/action fake tests passed.
**Phase 40 plan 40-02:** validator `maxLength` and numeric bounds plus descriptor schema meta guard complete; catalog tests passed.
**Phase 40 plan 40-03:** ownership marker business-boundary backstop and final protected no-diff verification complete; `tests/tools/ tests/architecture/` passed with 147 passed, 1 skipped.
**Phase 41 plan 41-01:** contract-spec/catalog legacy manager wording removed, `_side_effect_allowed` moved to policy, and focused architecture tests passed.
**Phase 41 plan 41-02:** production legacy manager unwrapping removed and focused tests migrated to platform-native fakes; focused pytest and ruff passed.
**Phase 41 plan 41-03:** `UnifiedToolManager` adapter/public export deleted, compatibility tests removed after ToolPlatform coverage migration, and architecture guard tests passed.
**Phase 41 plan 41-04:** implementation review, final verification, and Claude light closure handoff complete; final tests and no-legacy grep passed.
**Phase 44:** 4/4 plans complete; migrations 021/022, CWC repository/service, thread-case M:N lifecycle, contract alignment, clean code review, and verification passed. Final Phase 44 surface: `51 passed, 5 warnings`; `alembic heads` = `022_case_working_context (head)`.
**Phase 45 plan 45-01:** 5 min, 2 tasks, 6 files modified; contextual CWC lifecycle refs and graph/API-neutral adapter foundation complete.

Historical execution metrics are archived in milestone files and `.planning/MILESTONES.md`.

## Quick Tasks Completed

| Date | Quick ID | Task | Status |
|------|----------|------|--------|
| 2026-06-21 | 260621-lgq | MOCA memory long-term/case hardening | Complete |
| 2026-07-03 | fast | Refresh Phase 44 state metrics and reconcile GSD state accounting | Complete |

## Accumulated Context

### Decisions

- v2.1 groups four requirements into three dependency-ordered phases: Phase 37 (TPH-03 registry + TPH-04 runtime/policy internal refactors, no contract change), Phase 38 (TPH-01 output_schema declaration + enforcement), Phase 39 (TPH-02 spec reconciliation via dual-AI review).
- Registry consolidation (TPH-03) lands before output_schema work (TPH-01) because `output_schema` is most naturally declared in the same single-source registry.
- TPH-01 is `output_schema` (data-shape) enforcement only and MUST NOT alter the `ToolResultV2` envelope shape (HIGH blast radius, 7 external consumers).
- TPH-02 is a spec-catches-up-to-code edit and MUST go through the dual-AI review workflow; planning must first re-check commit `4dcb673`'s effect on §12.5/§12.6.
- `ToolCallContext` §8.0 identity fields are off-limits across all phases; domain ownership/scope enforcement in BusinessFactService is not rebuilt.
- Phase 37 plan 37-01 completed TPH-03 by making `_IDENTIFIER_SCHEMAS` and `INVESTIGATE_TOOL_NAMES` derived from catalog declarations/descriptors while preserving external contract shapes.
- Phase 37 plan 37-02 completed the runtime-helper portion of TPH-04 by routing all current `ToolRuntime.invoke` failure exits through `_fail(...)`; 37-03 completed policy gate sequencing and the final contract sweep.
- Phase 37 plan 37-03 completed the policy-gate portion of TPH-04 with ordered `RuntimeAuthGate` declarations and preserved external contract field sets. Full DB-backed pytest awaits local PostgreSQL.
- Phase 38 planning split TPH-01 into three dependency-ordered plans: validator support, catalog `output_schema` declarations, and runtime invalid-response enforcement/sweep. Strict no-data schemas are resolved for no-data tools, while action-tool output remains generic and out of scope until later action-output hardening.
- Phase 38 plan 38-01 keeps nullable/type-list schema validation in the existing local `validate_json_value` helper instead of adding a new JSON Schema dependency.
- Phase 38 plan 38-01 locks TPH-01 scope to the eight read/retrieval planner-visible tools and keeps `create_coupon_grant_draft` outside this plan.
- Phase 38 plan 38-01 requires list-union validation to return immediately after the first successful candidate schema.
- Phase 38 plan 38-02 makes _ToolDeclaration.output_schema the single catalog source for ToolDescriptor.output_schema.
- Phase 38 plan 38-02 keeps create_coupon_grant_draft on the generic action output schema because action output hardening is outside TPH-01.
- Phase 38 plan 38-02 uses strict no-data output schemas for get_logistics, get_merchant_risk, and search_sop until future executor/product scope defines real payloads.
- Phase 38 plan 38-03 confirms runtime output_schema failures map to safe invalid_response results through ToolPlatform, with ToolResultV2 envelope fields unchanged.
- Phase 38 plan 38-03 verifies DB-backed business/service and memory/search real-path coverage under compose PostgreSQL; fake-executor runtime tests and focused non-DB high-blast regressions remain fast proxy coverage.
- Phase 39 preserved §8.0 as the owner of ToolCallContext identity/scope/permission semantics.
- Phase 39 documented ToolCallContext.effective_at as str | None because the implemented Pydantic model uses str | None.
- Phase 39 documented ToolDescriptor.description: str = empty-string default because exact current model parity was required.
- Phase 40 must keep `UnifiedToolManager` cleanup out of scope; that API compatibility decision is a separate breaking cleanup phase.
- Phase 40 must keep `docs/contract-spec.md` unchanged unless implementation discovers the spec itself is wrong; if spec changes become necessary, stop and run the dual-AI spec review workflow.
- Phase 41 owns the `UnifiedToolManager` breaking cleanup/API decision. It must update `docs/contract-spec.md`, production injection seams, tests, and public exports consistently, and it must receive implementation code review before v2.1 archive.
- Phase 41 plan 41-01 completed the spec/API cleanup and helper relocation; 41-03 later deleted `src/tools/manager.py` and completed final no-manager reference cleanup.
- Phase 41 plan 41-02 completed production seam and targeted fake migration; production graph nodes now use `tool_platform` / `action_tool_platform` injection without legacy manager unwrapping.
- Phase 41 plan 41-03 deleted the legacy adapter and public export; `src.tools.manager_results` remains an allowed helper and is not the removed manager API.
- Phase 41 plan 41-04 completed the code-review/verification gate for TPH-06 and left a bounded Claude light closure review handoff.
- Phase 45 Plan 01 trusted case-ref extraction accepts active_slots, extracted_slots, and explicitly enabled business_context only; candidate_slots and memory surfaces are ignored.
- Phase 45 Plan 01 keeps CWC lifecycle contracts contextual-only and separates them from evidence/business/action/replay authority DTOs.
- Phase 45 Plan 01 active CWC payloads derive refs only from persisted row fields and hydrate content through the Phase 44 helper.

### Roadmap Evolution

- Phase 25 added and completed: Intent routing safety hardening.
- Phase 26-35 added for v1.9 Agent Platform Foundation.
- Phase 35.1 added to close v1.9 milestone audit gates.
- Phase 36 added and completed for v2.0 Merchant Scope Hardening.
- Phase 37-39 added for v2.1 Tool Platform Hardening (2026-07-01).
- Phase 40 added: Tool Contract Validation Hardening.
- Phase 41 added: Tool Platform Legacy Manager Cleanup.
- Phase 42 and 43 added/completed for intent recognition hardening.
- Phase 44 added/completed for memory layering: Case Working Context plus additive thread-case M:N.
- Phase 45 added: Memory Lifecycle Wiring for Case Working Context.

### Pending Todos

- No active pending todos remain in `.planning/todos/pending/`.
- Optional follow-up from v1.8 remains deferred: pin active slot `confidence` projection before confidence becomes a meaningful provenance field.

### Blockers / Concerns

- Phase 37 final full relevant pytest currently needs local PostgreSQL on `localhost:5432`; without it, DB-backed tests fail during fixture setup. Non-DB focused pytest, contract-shape checks, generic output schema check, spec/contracts empty diff, and ruff passed.
- Phase 38 final DB-backed sweep passed under compose PostgreSQL: `184 passed, 1 warning`.

## Deferred Items

| Category | Item | Status |
|----------|------|--------|
| deferred record | `.planning/todos/deferred/2026-06-17-constrain-agentstate-memory-expansion.md` | future candidate only if Phase 17 is reintroduced |
| future phase | Phase 17 External Action Execution | deferred |
| future phase | Phase RAG-5 Optional External Search Backend | deferred |
| future milestone | Policy Source Operations | deferred |
| future scope | post-Phase 17 Policy Scope | deferred |
| future scope | Same-merchant manager run/trace/replay visibility expansion (post-Phase 36 readiness) | deferred, not part of v2.1 |

## Last Archived Milestone Context

- v1.9 owned Phase 26 through Phase 35.1; all 19 v1.9 requirements are complete and archived.
- v2.0 owned Phase 36; merchant-scope DB hardening and role cleanup complete, with same-merchant trace/replay authorization expansion named as future scope.

## Session Continuity

Last session: 2026-07-03
Stopped at: Completed 45-01-PLAN.md
Resume file: None
Next: Execute Phase 45 plan 45-02 for active CWC read and run_auto thread-case link wiring.

Recent completions: Phase 37-41 tool platform hardening complete and archived-ready; Phase 42 intent recognition three-layer decoupling retroactively registered (commit `a0a98e4`, `1230 passed, 1 skipped`, ruff clean); Phase 43 intent multi-intent tier A complete; Phase 44 memory layering complete with clean review and 15/15 verification.
Next roadmap item: Phase 45 memory lifecycle wiring for graph run-completion CWC auto-update/read-active hooks, or another architecture-debt item inside v2.1.

**Completed Phase:** 44 (Memory Layering — Case Working Context + thread-case Many-to-Many) — 4/4 plans — 2026-07-03

**Planned Phase:** 45 (Memory Lifecycle Wiring for Case Working Context) — 4 plans — 2026-07-03T04:03:48.372Z
