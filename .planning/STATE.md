---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Core Subsystem Hardening
status: active
stopped_at: Phase 59 gap closure planning pending
last_updated: "2026-07-08T16:23:15+08:00"
last_activity: 2026-07-08 -- v2.1 milestone audit found archive gaps; Phase 59 and Phase 60 registered for gap closure
progress:
  total_phases: 25
  completed_phases: 23
  total_plans: 80
  completed_plans: 80
  percent: 92
---

# Project State: MOCA

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-07-07)

**Core value:** Retrieve relevant business facts and policy evidence, provide evidence-backed guidance, and ensure risky actions pass explicit approval and execution safety contracts.
**Current focus:** Phase 59 pending planning — approval-resume-terminal-memory-finalization

## Rescope note (2026-07-02)

- v2.1 was originally scoped/named "Tool Platform Hardening" (Phase 37-41). It is rescoped to **Core Subsystem Hardening**: a long-lived umbrella for cleaning up architecture debt across the four core subsystems tracked in `.planning/ARCHITECTURE-DEBT.md` (tool call / intent recognition / RAG / memory).
- **Standing rule (avoids re-asking each time):** work that *fixes existing-subsystem defects or clears architecture debt* is appended as the next integer phase inside v2.1 (42, 43, …) — no new milestone. A **new milestone** is opened only for a genuinely new user-facing product capability (not a defect fix). Tool platform is the first subsystem cleared; intent recognition is the second.

## Current Position

Phase: 59 — PENDING PLANNING
Plan: 0 of 0
Status: Gap closure phases registered from `.planning/v2.1-MILESTONE-AUDIT.md`; Phase 59 should be planned next
Last activity: 2026-07-08 -- v2.1 milestone audit found formal verification, validation, and approval-resume terminal memory finalization gaps
Next: Run `$gsd-plan-phase 59`.

Progress: [█████████░] 92%

Planning files: `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/MILESTONES.md`, and archived milestone files.

## Current Milestone Context

- v2.1 is a bounded, pre-scoped cleanup of the tool-call platform's contract debt and implementation gaps, not a new user-facing feature.
- Primary accepted tool-contract reference: `docs/contract-spec.md` §12.5/§12.6 and §8.0. All tool contract code lives under `src/tools/` (catalog.py, contracts.py, runtime.py, policy.py, platform.py, projection.py, executors/). If a phase finds spec/source/product conflict, it must record a spec delta / MVP scope / deferral before implementation.
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
| 45. Memory Lifecycle Wiring for Case Working Context (MEM-01, MEM-02) | 4/4 | Complete |
| 46. Session Context Repositioning (MEM-03) | 3/3 | Complete |
| 47. Case Precedent Repositioning and Closed-Case Candidate Generation (MEM-04) | 4/4 | Complete |
| 48. Narrow Long-Term Explicit Preference Memory (MEM-05) | 4/4 | Complete |
| 48.1. Memory Context Compatibility Debt Cleanup (MEM-COMPAT-01) | 4/4 | Complete |
| 49. Investigate Bounded ReAct Loop Migration (GAD-01-IMPL) | 4/4 | Complete with replay parent-operation limitation |
| 50. Canonical Agent Graph Migration Spec and Guardrails (CAGM-01) | 0/0 | Complete (spec-only); implementation phases pending |
| 51. Canonical Graph Baseline Guardrails and Migration Matrix (CAGM-02) | 3/3 | Complete |
| 52. Safety Pre-route Node (CAGM-03) | 3/3 | Complete |
| 53. Session Context Before Intent and Contextual Intent Resolve (CAGM-04) | 3/3 | Complete |
| 54. Slot Resolution Gate Cutover (CAGM-05) | 3/3 | Complete |
| 55. Memory Context Load Cutover (CAGM-06) | 3/3 | Complete |
| 56. Recommendation Generation and RAG Claim Status Alignment (CAGM-07) | 4/4 | Complete |
| 57. Risk Gate and Approval Gate Canonicalization (CAGM-08) | 5/5 | Complete |
| 58. Canonical Graph Cutover and No-Debt Cleanup (CAGM-09) | 10/10 | Complete; broad validation, classifier, frontend build/test, metadata proof passed |
| 59. Approval Resume Terminal Memory Finalization (MEM-01, MEM-02, MEM-03, CAGM-08, CAGM-09) | 0/0 | Pending planning |
| 60. v2.1 Archive Evidence Closure (TPH-03, TPH-04, IDR-02, MEM-COMPAT-01, GAD-01-IMPL, CAGM-01, CAGM-07) | 0/0 | Pending planning |

Sequencing rationale: Phase 37 consolidates the registry and converges runtime/policy internals with no external contract change (LOW blast radius). Phase 38 declares `output_schema` in that consolidated registry and enforces it through the shared failure path. Phase 39 reconciles the spec to the final implemented state via dual-AI review. Phase 40 closes the source-confirmed validation/backstop gaps intentionally deferred or left advisory after Phase 38/39. Phase 41 then handles the explicit breaking cleanup/API decision to remove the `UnifiedToolManager` legacy compatibility adapter.

Phase 42 moves to the second subsystem (intent recognition): it splits intent classification into three explicit single-direction layers (semantic / risk-authorization / clarification), fixing ID-01 (keyword override of LLM) and ID-03 (three-dimension coupling) per `.planning/ARCHITECTURE-DEBT.md`. The code was implemented + verified before formal registration, so Phase 42 is **retroactively registered**: it has CONTEXT / VERIFICATION plus a record-only `42-01-PLAN.md` / `42-01-SUMMARY.md` pair anchored to commit `a0a98e4`, but no PLAN-REVIEW (it did not go through plan-then-execute). Multi-intent tier A (ID-04) is the next intent phase and WILL go through the full plan-phase + plan-checker + Codex review flow.

Phase 44 moves to the memory subsystem: it adds the durable Case Working Context layer and additive thread-case many-to-many association while preserving `case_memories`, `long_term_memories`, and `conversation_threads.case_id`. Graph lifecycle auto-update/read-active wiring is explicitly deferred to Phase 45.

Phase 49 moved the `investigate` node internals from deterministic main planning to a bounded read-only ReAct loop. Outer graph routers remained deterministic, observation→slot回流 stayed loop-local only, ToolPlatform remained the sole dispatch path, and intent/memory/risk/approval/action contracts stayed out of scope.

Phase 50 completed the remaining canonical Agent Graph migration charter by locking a migration SPEC and guardrails before runtime rewiring. It treats `docs/contract-spec.md` §9 as the primary accepted contract reference, `docs/target-agent-platform-architecture-plan.md` §6.1 as the readable target graph view, and `50-SPEC.md` as the execution charter for future migration phases.

Phases 51-58 are registered as macro implementation phases for the canonical Agent Graph migration. They must each read Phase 50 SPEC before planning, and each detailed PLAN must be generated against the then-current source state rather than prewritten now.

Phases 59-60 are registered from `.planning/v2.1-MILESTONE-AUDIT.md` as milestone gap-closure work. Phase 59 closes the runtime approval-resume terminal memory finalization gap before Phase 60 refreshes formal verification and validation evidence for the archive gate.

## Last Milestone Context

- v2.0 Merchant Scope Hardening delivered Phase 36 (merchant-scope DB hardening / role cleanup) on 2026-06-30. Its remaining same-merchant trace/replay authorization scope stays future work and is not part of v2.1.
- v1.9 Agent Platform Foundation (Phases 26-35.1) shipped and archived on 2026-06-30. It landed the descriptor-driven `ToolView`, runtime `ToolPolicyDecision`, safe tool result projection, and ToolPlatform boundary that v2.1 now hardens.
- `docs/contract-spec.md` is the primary accepted contract reference. Preserve v1.9 service-boundary contracts unless a phase explicitly records a spec delta / MVP scope / deferral.
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
| Phase 45 P02 | 10min | 3 tasks | 8 files |
| Phase 45 P03 | 13min | 3 tasks | 6 files |
| Phase 45 P04 | 10min | 3 tasks | 6 files |
| Phase 46 P01 | 3 min | 2 tasks | 4 files |
| Phase 46 P02 | 5 min | 2 tasks | 2 files |
| Phase 46 P03 | 8 min | 2 tasks | 8 files |
| Phase 47 P01 | 6 min | 2 tasks | 9 files |
| Phase 47 P02 | 11 min | 2 tasks | 6 files |
| Phase 47 P03 | 21 min | 3 tasks | 5 files |
| Phase 47 P04 | 19 min | 2 tasks | 11 files |
| Phase 48 P01 | 20 min | 2 tasks | 6 files |
| Phase 48 P02 | 11 min | 2 tasks | 9 files |
| Phase 48 P03 | 12 min | 2 tasks | 11 files |
| Phase 48 P04 | 19 min | 3 tasks | 8 files |
| Phase 57 P01 | 7min | 2 tasks | 6 files |
| Phase 57 P02 | 22min | 2 tasks | 15 files |
| Phase 57 P03 | 21min | 2 tasks | 11 files |
| Phase 57 P04 | 32m | 2 tasks | 16 files |
| Phase 57 P05 | 24m | 2 tasks | 8 files |

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
- Phase 45 Plan 02: Read-seam thread-case linking uses session.begin_nested() and never rolls back the shared graph session directly.
- Phase 45 Plan 02: CWC identity for memory_context_load comes only from trusted_context plus trusted case refs in state; missing identity yields explicit skipped status.
- Phase 45 Plan 02: Active CWC remains separate from reviewed case_memory and is exposed through additive state and memory_context_bundle fields.
- Terminal CWC projection uses only deterministic prompt-safe summaries and refs; no LLM summarizer or raw tool/policy payload enters CWC.
- Completed-run CWC writeback runs after assistant message/thread summary commit and existing memory_write side effect, then reports CWC status separately.
- Lifecycle writeback dedupes read-seam run_auto thread-case links before writing CWC.
- Phase 45 Plan 04 closes active CWC read, run_auto thread-case link caller, and terminal CWC writeback while keeping DEFER-1/2/3 as future memory redesign phases.
- 45-VALIDATION.md compliance flags were set true only after targeted pytest, ruff, and alembic heads passed.
- Phase 46 Plan 01 documents session_memories as same-thread temporary conversational context only after CWC; prompt hints remain contextual pointers, not evidence/business/approval/action/replay authority.
- Phase 46 Plan 01 documents planner-facing search_case_memory as CaseMemoryService.retrieve_reviewed over reviewed case memory; LegacySessionPrecedentSearchService remains legacy/debug-only.
- Phase 46 Plan 01 carries DEFER-2 -> Phase 47 and DEFER-3 -> Phase 48 by name without implementing either scope.
- Phase 46 Plan 02 scopes CWC fallback scans to lifecycle/read helper paths and does not ban legitimate CaseMemoryService usage in the reviewed-memory retrieval path.
- Phase 46 Plan 02 requires runnable Phase 46 pytest snippets to use the approved uv entrypoint while treating prose examples as non-command text.
- MEM-03 completed when Phase 46 Plan 03 behavioral validation passed.
- Phase 46 Plan 03 strips raw authority ref fields from session bundle tool summaries through prompt-safe allowlists.
- MEM-03 validation flags are set only after approved uv pytest commands passed.
- Phase 46 completed without migrations, Phase 47 precedent generation, Phase 48 preference memory, CWC fallback, or ReAct/global active_slots writer.
- Phase 47 Plan 01: closed_case_cwc_candidate is a CaseMemorySourceType and is review-required only.
- Phase 47 Plan 01: MemorySourceRefV1 and ALLOWED_SOURCE_REF_KEYS stay fixed; close/CWC identity uses existing event_id and outcome_id.
- Phase 47 Plan 01: static migration checks use src/db/migrations/versions, the repository's actual Alembic revision directory.
- Phase 47 Plan 02: terminal refund-case statuses are exactly closed, refunded, and rejected for closed-case precedent generation.
- Phase 47 Plan 02: merchant scope is used only when RefundCase -> Order.merchant_id resolves; unresolved merchant falls back to exact case scope, never tenant scope.
- Phase 47 Plan 02: closed-case CWC projection builds a prompt-safe CaseMemoryWriteCandidate but does not submit it; governed write lifecycle remains 47-03.
- Phase 47 Plan 02: CWC policy refs map to existing case-memory policy ref keys doc_key, chunk_id, and policy_version.
- Phase 47 Plan 03: terminal closed-case CWC projections persist only through CaseMemoryService.submit_case_memory_candidate and produce needs_review candidates.
- Phase 47 Plan 03: PII-blocked CWC rows submit fixed non-sensitive candidates so existing case-memory service emits pii_blocked skip events without inserting rows.
- Phase 47 Plan 03: generated candidates are pending-review visible but excluded from reviewed retrieval until approval; approval preserves mapped policy refs doc_key, chunk_id, and policy_version.
- Phase 47 Plan 04 keeps ToolCallContext case-id-free; planner-facing search_case_memory scopes reviewed retrieval from tenant/user/thread/merchant context only.
- Phase 47 Plan 04 keeps closed-case candidate source identity in source_ref_json.business_object_type/business_object_id while reusable retrieval uses CaseMemory.scope_type/scope_id.
- Phase 47 Plan 04 records DEFER-2 delivered by Phase 47 and preserves DEFER-3 as Phase 48 explicit preference memory scope.
- Phase 48 planning split MEM-05 into four serial plans: contract/docs/static locks, source policy and semantic-episode narrowing, explicit chat/admin preference writes, and retrieval/review/correction/final validation.
- Phase 48 Plan 01 completed the target contract/static lock: published long-term memory is explicit preference-only, allowed published source types are `explicit_user_preference`, `explicit_admin_preference`, and `human_reviewed`, and `memory_type='long_term_fact'` is legacy storage identity only.
- Phase 48 Plan 02 completed source policy/service guards: only explicit user/admin/human-reviewed long-term sources auto-publish; `semantic_episode_candidate` remains needs-review preference candidate only; non-preference and disallowed source writes skip before insert with audit events.
- Phase 48 Plan 03 completed explicit write paths: deterministic chat phrases create trusted merchant-scoped `explicit_user_preference` only, admin `memory:write` can directly save `explicit_admin_preference`, and tenant scope is admin-only.
- Phase 48 Plan 04 completed retrieval/review/correction closeout: prompt-facing retrieval is preference/source filtered, reviewed candidates publish as `human_reviewed`, non-preference approval is a controlled error, supersede/tombstone/no-auto-merge lifecycle is locked, and the full Phase 48 gate passed.
- Phase 57 Plan 01 created risk_gate as a canonical wrapper over the existing risk/action implementation rather than moving policy logic between modules.
- Phase 57 Plan 01 kept assess_risk_and_approval importable only as Phase 58-scoped import/test compatibility with explicit alias metadata.
- Phase 57 Plan 01 left active graph registration and router cutover untouched for Plan 57-02.
- Phase 57 Plan 02 cut active graph registration, claim router values, and approval edit rerisk resume payloads to canonical `risk_gate` without adding a risk self-loop.
- Phase 57 Plan 02 preserved `action_draft`'s allowed action-claim gate by representing approved resume reconciliation as an approval-service-owned action recommendation claim.
- 57-03: Persisted legacy approval edit retry metadata is normalized to canonical risk_gate before graph resume; fresh/current legacy resume_route is not accepted as authority.
- 57-03: receive_request clears stale approval/risk/action authority fields at new-turn intake for approval-like chat safety.
- 57-03: approval_gate validates TrustedApprovalResultV1 plus tenant/run/hash bindings before setting approval_result.
- Phase 57 Plan 04 treats risk_gate as the only current runtime risk node while preserving assess_risk_and_approval only as labeled historical projection until Phase 58.
- Phase 57 Plan 05: Current-source docs use risk_gate for active graph/current route/current resume authority; assess_risk_and_approval remains historical compatibility or Phase 58 cleanup context.
- Phase 57 Plan 05: Static legacy-hit classification excludes 57-VALIDATION.md itself to avoid recursive self-counting while classifying all other assess_risk_and_approval hits.
- Phase 57 Plan 05: Phase 34 architecture guard now treats assess_risk_and_approval as a non-runnable Phase 57 compatibility alias.

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
- Phase 46 added: Session Context Repositioning.
- Phase 47 added: Case Precedent Repositioning and Closed-Case Candidate Generation.
- Phase 48 added: Narrow Long-Term Explicit Preference Memory.
- Phase 48.1 inserted after Phase 48: Memory Context Compatibility Debt Cleanup (URGENT).
- Phase 49 added: Investigate Bounded ReAct Loop Migration.
- Phase 50 added: Canonical Agent Graph Migration Spec and Guardrails.
- Phase 51-58 added: Canonical Agent Graph runtime migration macro phases from Phase 50 SPEC.

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

Last session: --stopped-at
Stopped at: Phase 58 complete after final validation
Resume file: --resume-file
Next: Run final Phase 58 review/verification workflow if needed, then decide milestone closeout or next registered phase.

Recent completions: Phase 37-41 tool platform hardening complete and archived-ready; Phase 42 intent recognition three-layer decoupling retroactively registered (commit `a0a98e4`, `1230 passed, 1 skipped`, ruff clean); Phase 43 intent multi-intent tier A complete; Phase 44 memory layering complete with clean review and 15/15 verification; Phase 45 memory lifecycle wiring complete with security, UAT, validation, and clean review complete; Phase 46 session context repositioning complete with MEM-03 validated; Phase 47 complete with 47-01 contract/source-policy foundation, 47-02 trusted closed-case projection seam, 47-03 governed case-memory write lifecycle, and 47-04 retrieval/docs/validation closeout; Phase 48 complete with explicit preference contract, source policy/service guards, chat/admin write paths, retrieval/review/correction closeout, clean code review, completed UAT, and security verification (`threats_open: 0`); Phase 49 completed investigate bounded read-only ReAct main path with replay parent-operation limitation; Phase 50 completed canonical Agent Graph migration guardrail SPEC; Phase 51 completed canonical graph baseline guardrails and migration matrix verification; Phase 52 completed explicit `safety_pre_route` runtime node extraction with clean review and 8/8 verification; Phase 53 completed `session_context_load -> contextual_intent_resolve` active graph cutover with clean review, security verification, validation, and 20/20 verification; Phase 54 completed `slot_resolution_gate` active graph cutover with clean review, security verification (`threats_open: 0`), Nyquist validation, and 8/8 verification; Phase 55 completed `memory_context_load` active graph cutover with clean review, review fix, verification, validation, and security verification (`threats_open: 0`); Phase 56 completed `recommendation_generation` active graph cutover, RAG/claim fail-closed alignment, action-boundary review fixes, clean code review, UAT, security verification (`threats_open: 0`), and Nyquist validation; Phase 57 completed `risk_gate` active runtime canonicalization, approval resume separation, projection/docs/validation closeout, and static legacy-hit classification for Phase 58 cleanup; Phase 58 completed final 15-node canonical graph cutover/no-debt cleanup with 10/10 plans, strict classifier `active_runtime_legacy=0`, `current_docs_legacy_authority=0`, `unclassified_rows=0`, broad backend pytest `1812 passed, 1 skipped`, frontend build/test, metadata proof, and CAGM-09 closeout.
Next roadmap item: Final Phase 58 review/verification workflow or milestone closeout decision.

**Completed Phase:** 58 (canonical-graph-cutover-and-no-debt-cleanup) — 10/10 plans — 2026-07-08

**Next Phase:** TBD after final review / milestone closeout decision

**Completed Requirement:** CAGM-09 — Phase 58 — 2026-07-08
