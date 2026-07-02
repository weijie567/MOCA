# Phase 39: contract-spec §12.5/§12.6 Reconciliation - Research

**Researched:** 2026-07-02 [VERIFIED: system date]
**Domain:** MOCA tool-platform contract documentation reconciliation [VERIFIED: .planning/ROADMAP.md]
**Confidence:** HIGH [VERIFIED: source/doc/code cross-checks listed in Sources]

<user_constraints>
## User Constraints

### Locked Decisions
- Phase 39 is TPH-02 only: `docs/contract-spec.md` §12.5/§12.6 must catch up to implemented contract fields, and the phase must not redefine, widen, or rename §8.0 `TrustedContext`-projected fields. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: .planning/REQUIREMENTS.md]
- The protected §8.0 `ToolCallContext` identity/scope/permission projection fields are `tenant_id`, `user_id`, `role`, `permissions`, `merchant_scope`, `session_id`, `thread_id`, `run_id`, and `trace_id`. [CITED: docs/contract-spec.md:37-39] [CITED: docs/contract-spec.md:149-159] [VERIFIED: .planning/ROADMAP.md]
- Phase 39 should be spec/docs reconciliation only unless research proves otherwise; avoid production code changes. [VERIFIED: user prompt] [VERIFIED: .planning/ROADMAP.md]
- Planning must re-check whether commit `4dcb673` incidentally modified §12.5/§12.6 before editing and must reconcile against the current on-disk file. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: user prompt]
- MOCA validation commands must use `uv run ...` or `.venv/bin/...`; bare `pytest` and bare `python -m pytest` are invalid verification entrypoints. [VERIFIED: AGENTS.md] [VERIFIED: CLAUDE.md]
- Spec changes for this phase must pass the dual-AI review workflow: `gsd-plan-checker`, Codex cross-review, and Claude/Codex adjudication according to the active project wording. [VERIFIED: AGENTS.md] [VERIFIED: CLAUDE.md] [VERIFIED: .planning/ROADMAP.md]

### Claude's Discretion
- No phase `CONTEXT.md` exists, so there are no additional discuss-phase discretion items. [VERIFIED: gsd-sdk query init.phase-op 39]
- Research recommends one spec-only plan because the file surface is a single normative document plus validation/review checks, not multiple service boundaries or implementation ownership domains. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: docs/contract-spec.md:1219-1398]

### Deferred Ideas (OUT OF SCOPE)
- New tools, new executors, new policy gates, action output hardening, high-blast `ToolResultV2` envelope changes, and domain merchant-scope enforcement rebuilds are out of scope for v2.1 / Phase 39. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: .planning/STATE.md]
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TPH-02 | Reconcile `docs/contract-spec.md` §12.5/§12.6 normative type definitions with implemented tool contract fields, adding the implemented-but-unspecified fields without redefining/widening/renaming §8.0 identity fields. [VERIFIED: .planning/REQUIREMENTS.md] | The gap table below maps current spec snippets to `src/tools/contracts.py`, `src/tools/catalog.py`, `src/tools/policy.py`, `src/tools/runtime.py`, and `src/tools/platform.py`; validation commands verify doc-only scope and protected identity fields. [VERIFIED: src/tools/contracts.py:13-36] [VERIFIED: src/tools/catalog.py:14-32] [VERIFIED: src/tools/policy.py:374-464] |
</phase_requirements>

## Summary

Phase 39 should update `docs/contract-spec.md` §12.5 and §12.6 so the normative type definitions reflect the already-implemented tool platform contract fields. [VERIFIED: .planning/ROADMAP.md] The implementation already has the target fields in `ToolCallContext`, `ToolDescriptor`, and `ToolPolicyDecision`; Phase 39 should not edit production code to create or rename these fields. [VERIFIED: src/tools/contracts.py:13-36] [VERIFIED: src/tools/catalog.py:14-32] [VERIFIED: src/tools/contracts.py:161-185]

The main risk is accidentally treating §12.5 `ToolCallContext` as an opportunity to redefine identity/scope semantics. [CITED: docs/contract-spec.md:1221-1242] The spec already says the identity/scope/permission fields are §8.0 `TrustedContext` projections and not redefined in §12.5; the missing Phase 39 fields are tool-call-local fields: `effective_at`, `approval_ref`, and `safety_snapshot_ref`. [CITED: docs/contract-spec.md:1221-1242] [VERIFIED: src/tools/contracts.py:13-36]

Commit `4dcb6733a2144f001813c1bdbcaaf6b0d26c2e3b` touched `docs/contract-spec.md`, but the only displayed `docs/contract-spec.md` hunk in that commit is around `memory_write_events` in the memory/data-model section, not around §12.5 or §12.6. [VERIFIED: git show --stat 4dcb673] [VERIFIED: git show --unified=80 4dcb673 -- docs/contract-spec.md] Planning should still start from the current on-disk lines at §12.5/§12.6 because the file has evolved through Phase 38-adjacent documentation and review artifacts. [VERIFIED: docs/contract-spec.md:1219-1398] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-REVIEW.md]

**Primary recommendation:** Create one `39-01-PLAN.md` spec-only plan that edits `docs/contract-spec.md`, runs structural doc diffs plus focused existing tests, and completes the dual-review gate before marking TPH-02 complete. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: AGENTS.md]

## Project Constraints (from CLAUDE.md)

- Append any local debugging, startup, verification, UI, API, RAG/agent/memory/tool-call errors to `.planning/LOCAL-VALIDATION-ISSUES.md` in Chinese after handling them. [VERIFIED: CLAUDE.md]
- Use the dual-AI workflow for phase-level plans and larger changes: GSD-native review first, then Codex cross-review, then adjudication against repository evidence. [VERIFIED: CLAUDE.md] [VERIFIED: AGENTS.md]
- `docs/contract-spec.md` is the sole normative contract source, but it defines contract semantics rather than implementation details; phase implementation scope controls what lands. [VERIFIED: CLAUDE.md] [VERIFIED: AGENTS.md]
- If implementation and spec disagree, do not silently diverge; either fix the spec or record an explicit MVP/target-state scope note. [VERIFIED: CLAUDE.md] [VERIFIED: AGENTS.md]
- MOCA validation commands must use `uv run pytest`, `uv run ruff`, or `.venv/bin/...`; bare `pytest` / bare `python -m pytest` results are invalid. [VERIFIED: AGENTS.md]
- Phase-level planning must check granularity before writing one large plan; split plans only when multiple service boundaries, ownership domains, waves, or verification gates are present. [VERIFIED: AGENTS.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| §12.5 `ToolCallContext` documentation reconciliation | Contract Spec / API-Backend | Trusted Context boundary | `ToolCallContext` is implemented in backend Pydantic code and its identity fields are projections of §8.0 `TrustedContext`. [VERIFIED: src/tools/contracts.py:13-36] [CITED: docs/contract-spec.md:37-39] |
| §12.6 `ToolDescriptor` catalog documentation reconciliation | Contract Spec / API-Backend | ToolCatalog | `ToolDescriptor` is created from catalog declarations and includes executor/exposure/action-safety metadata. [VERIFIED: src/tools/catalog.py:14-32] [VERIFIED: src/tools/catalog.py:369-387] |
| §12.6 `ToolPolicyDecision` documentation reconciliation | Contract Spec / API-Backend | ToolPolicyEngine / ToolRuntime | `ToolPolicyDecision` is emitted by visibility/runtime auth paths and carries runtime availability metadata. [VERIFIED: src/tools/contracts.py:161-185] [VERIFIED: src/tools/policy.py:314-327] [VERIFIED: src/tools/runtime.py:227-240] |
| `event_family="action"` documentation reconciliation | Contract Spec / API-Backend | ToolPlatform / action executor bucket | Catalog declares the write action descriptor with `event_family="action"`, and `ToolPlatform.event_family()` maps that to `"action"`. [VERIFIED: src/tools/catalog.py:325-363] [VERIFIED: src/tools/platform.py:139-150] |
| Validation and review gate | Planning / QA | API-Backend tests | Existing tests already cover identity-boundary construction, descriptor metadata, runtime gates, and policy decision envelope behavior. [VERIFIED: tests/architecture/test_trusted_context_boundaries.py:58-82] [VERIFIED: tests/tools/test_catalog.py:218-225] [VERIFIED: tests/tools/test_tool_platform.py:442-478] |

## Field-By-Field Gap Table

### §12.5 `ToolCallContext`

| Field | Implemented Type / Semantics | Current §12.5 Status | Research Finding | Planner Action |
|-------|------------------------------|----------------------|------------------|----------------|
| `schema_version` | `Literal["tool_context.v2"]`, default `"tool_context.v2"`. [VERIFIED: src/tools/contracts.py:16] | Present. [CITED: docs/contract-spec.md:1224-1225] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: .planning/REQUIREMENTS.md] |
| `tenant_id` | Trusted identity field. [VERIFIED: src/tools/contracts.py:17] | Present and identified as §8.0 projection. [CITED: docs/contract-spec.md:1221-1230] | Locked identity/scope field. [CITED: docs/contract-spec.md:37-39] | Do not redefine, widen, or rename. [VERIFIED: .planning/ROADMAP.md] |
| `user_id` | Trusted identity field. [VERIFIED: src/tools/contracts.py:18] | Present and identified as §8.0 projection. [CITED: docs/contract-spec.md:1221-1228] | Locked identity/scope field. [CITED: docs/contract-spec.md:37-39] | Do not redefine, widen, or rename. [VERIFIED: .planning/ROADMAP.md] |
| `role` | Trusted role field. [VERIFIED: src/tools/contracts.py:19] | Present and identified as §8.0 projection. [CITED: docs/contract-spec.md:1221-1229] | Locked identity/scope field. [CITED: docs/contract-spec.md:37-39] | Do not redefine, widen, or rename. [VERIFIED: .planning/ROADMAP.md] |
| `permissions` | Trusted permission token list. [VERIFIED: src/tools/contracts.py:20] | Present and identified as §8.0 projection. [CITED: docs/contract-spec.md:1221-1230] | Locked identity/scope/permission projection. [CITED: docs/contract-spec.md:43-50] | Do not redefine, widen, or rename. [VERIFIED: .planning/ROADMAP.md] |
| `merchant_scope` | `dict[str, Any] \| list[str]` in implementation. [VERIFIED: src/tools/contracts.py:21] | Present as `dict[str, Any]` with comment. [CITED: docs/contract-spec.md:1229-1231] | The implementation accepts legacy list merchant scope, but Phase 39 must not use this to widen §8.0 semantics. [VERIFIED: src/tools/contracts.py:21] [CITED: docs/contract-spec.md:57-68] | Preserve §8.0 semantics; if documenting implementation type, state it as compatibility input shape, not a TrustedContext redefinition. [VERIFIED: tests/tools/test_tool_platform.py:124-160] |
| `session_id` | Optional trusted session field. [VERIFIED: src/tools/contracts.py:22] | Present. [CITED: docs/contract-spec.md:1231] | Locked identity/session projection. [CITED: docs/contract-spec.md:43-55] | Do not redefine. [VERIFIED: .planning/ROADMAP.md] |
| `thread_id` | Trusted thread field. [VERIFIED: src/tools/contracts.py:23] | Present. [CITED: docs/contract-spec.md:1232] | Locked identity/session projection. [CITED: docs/contract-spec.md:43-55] | Do not redefine. [VERIFIED: .planning/ROADMAP.md] |
| `run_id` | Trusted run field. [VERIFIED: src/tools/contracts.py:24] | Present. [CITED: docs/contract-spec.md:1233] | Locked identity/run projection. [CITED: docs/contract-spec.md:43-55] | Do not redefine. [VERIFIED: .planning/ROADMAP.md] |
| `trace_id` | Trusted trace field. [VERIFIED: src/tools/contracts.py:25] | Present. [CITED: docs/contract-spec.md:1234] | Locked identity/trace projection. [CITED: docs/contract-spec.md:43-55] | Do not redefine. [VERIFIED: .planning/ROADMAP.md] |
| `request_id` | Tool-call-local request correlation. [VERIFIED: src/tools/contracts.py:26] [VERIFIED: src/platform/context_projections.py:86-122] | Present. [CITED: docs/contract-spec.md:1235] | No gap. [VERIFIED: source/spec comparison] | Keep as tool-call-local. [CITED: docs/contract-spec.md:1221] |
| `tool_call_id` | Tool-call-local logical call id. [VERIFIED: src/tools/contracts.py:27] | Present. [CITED: docs/contract-spec.md:1236] | No gap. [VERIFIED: source/spec comparison] | Keep existing uniqueness rule. [CITED: docs/contract-spec.md:1302-1305] |
| `caller_node` | Tool-call-local caller. [VERIFIED: src/tools/contracts.py:28] | Present. [CITED: docs/contract-spec.md:1237] | No gap. [VERIFIED: source/spec comparison] | Keep as runtime auth input. [VERIFIED: src/tools/policy.py:102-119] |
| `deadline_at` | Optional deadline. [VERIFIED: src/tools/contracts.py:29] | Present. [CITED: docs/contract-spec.md:1238] | No gap. [VERIFIED: source/spec comparison] | Keep existing retry/deadline rule. [CITED: docs/contract-spec.md:1305] |
| `effective_at` | `str \| None`, tool-call-local effective time. [VERIFIED: src/tools/contracts.py:30] [VERIFIED: src/platform/context_projections.py:93-116] | Missing from §12.5 code block. [CITED: docs/contract-spec.md:1224-1242] | Required Phase 39 addition; it is not a §8.0 identity field. [VERIFIED: .planning/REQUIREMENTS.md] [CITED: docs/contract-spec.md:153-154] | Add to §12.5 `ToolCallContext` as tool-call-local / run-derived field, not TrustedContext identity. [VERIFIED: src/platform/context_projections.py:86-122] |
| `attempt` | Current attempt count, default `1`. [VERIFIED: src/tools/contracts.py:31] | Present. [CITED: docs/contract-spec.md:1239] | No gap. [VERIFIED: source/spec comparison] | Do not change. [CITED: docs/contract-spec.md:1305] |
| `max_attempts` | Per-tool maximum attempts, default `1`. [VERIFIED: src/tools/contracts.py:32] | Present. [CITED: docs/contract-spec.md:1240] | No gap. [VERIFIED: source/spec comparison] | Do not change. [CITED: docs/contract-spec.md:1305] |
| `idempotency_key` | Optional tool-call-local idempotency key. [VERIFIED: src/tools/contracts.py:33] | Present. [CITED: docs/contract-spec.md:1241] | No gap. [VERIFIED: source/spec comparison] | Keep; required by action safety gate when descriptor requires it. [VERIFIED: src/tools/policy.py:164-171] |
| `approval_ref` | `str \| None`, action approval reference. [VERIFIED: src/tools/contracts.py:34] [VERIFIED: src/platform/context_projections.py:97-120] | Missing from §12.5 code block. [CITED: docs/contract-spec.md:1224-1242] | Required Phase 39 addition; runtime approval gate checks it when `descriptor.requires_approval` is true. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: src/tools/policy.py:144-152] | Add to §12.5 as tool-call-local/action-safety field, not identity/scope. [VERIFIED: src/tools/policy.py:144-152] |
| `safety_snapshot_ref` | `str \| None`, action safety snapshot reference. [VERIFIED: src/tools/contracts.py:35] [VERIFIED: src/platform/context_projections.py:98-121] | Missing from §12.5 code block. [CITED: docs/contract-spec.md:1224-1242] | Required Phase 39 addition; runtime safety snapshot gate checks it when `descriptor.requires_safety_snapshot` is true. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: src/tools/policy.py:154-162] | Add to §12.5 as tool-call-local/action-safety field, not identity/scope. [VERIFIED: src/tools/policy.py:154-162] |
| `policy_snapshot_ref` | Optional policy snapshot reference. [VERIFIED: src/tools/contracts.py:36] | Present. [CITED: docs/contract-spec.md:1242] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |

### §12.6 `ToolDescriptor`

| Field / Value | Implemented Type / Semantics | Current §12.6 Status | Research Finding | Planner Action |
|---------------|------------------------------|----------------------|------------------|----------------|
| `name` | Tool name. [VERIFIED: src/tools/catalog.py:17] | Present. [CITED: docs/contract-spec.md:1317-1318] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `description` | Prompt-safe descriptor description defaulting to empty string. [VERIFIED: src/tools/catalog.py:18] | Missing from §12.6 `ToolDescriptor` code block, but present in `ToolView`. [CITED: docs/contract-spec.md:1317-1334] | This mismatch exists, but TPH-02 success criteria do not list `ToolDescriptor.description`; do not expand scope unless planner deliberately treats it as incidental doc cleanup. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: src/tools/catalog.py:18] | Leave unchanged or add only if plan explicitly scopes it; avoid expanding beyond TPH-02. [VERIFIED: .planning/REQUIREMENTS.md] |
| `kind` | `Literal["read", "retrieval", "write"]`. [VERIFIED: src/tools/catalog.py:19] | Present. [CITED: docs/contract-spec.md:1319] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `input_schema` | `dict[str, Any]`. [VERIFIED: src/tools/catalog.py:20] | Present. [CITED: docs/contract-spec.md:1320] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `output_schema` | `dict[str, Any]`, schema for `ToolResultV2.data`. [VERIFIED: src/tools/catalog.py:21] | Present. [CITED: docs/contract-spec.md:1321] | Semantics now reflect Phase 38 strict data-shape enforcement. [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-VERIFICATION.md] | Keep the field; optionally update stale row text that says schemas land in Phase 9 if the plan includes row cleanup. [CITED: docs/contract-spec.md:1396-1407] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-02-SUMMARY.md] |
| `risk_level` | `Literal["read", "retrieval", "write"]`. [VERIFIED: src/tools/catalog.py:22] | Present. [CITED: docs/contract-spec.md:1322] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `side_effect` | `Literal["none", "read_only", "retrieval", "write"]` in descriptor. [VERIFIED: src/tools/catalog.py:23] | Present. [CITED: docs/contract-spec.md:1323] | No gap in descriptor type; internal declaration rows use no `"none"` value today. [VERIFIED: src/tools/catalog.py:176-191] | Do not change implementation. [VERIFIED: .planning/ROADMAP.md] |
| `required_permission` | Namespaced permission token. [VERIFIED: src/tools/catalog.py:24] | Present. [CITED: docs/contract-spec.md:1324] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `caller_allowlist` | Caller allowlist. [VERIFIED: src/tools/catalog.py:25] | Present. [CITED: docs/contract-spec.md:1325] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `event_family` | `Literal["tool_call_*", "rag_retrieval_*", "action"] \| None`. [VERIFIED: src/tools/catalog.py:26] | Present but missing `"action"` and `None`. [CITED: docs/contract-spec.md:1326] | Required Phase 39 addition for `action`; current write action uses `event_family="action"`. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: src/tools/catalog.py:325-363] | Update §12.6 literal to include `"action"` and decide whether to document `None` because implementation allows it, while default catalog rows all set non-`None` values. [VERIFIED: src/tools/catalog.py:14-32] [VERIFIED: runtime field inventory via uv run python] |
| `resource_type` | `str \| None`. [VERIFIED: src/tools/catalog.py:27] | Present. [CITED: docs/contract-spec.md:1327] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `executor` | `Literal["business", "knowledge", "memory", "action"] \| None`. [VERIFIED: src/tools/catalog.py:28] | Missing from §12.6 `ToolDescriptor` code block. [CITED: docs/contract-spec.md:1317-1328] | Required Phase 39 addition; runtime dispatch selects executor bucket via descriptor. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: src/tools/runtime.py:132-153] | Add to §12.6 `ToolDescriptor`. [VERIFIED: src/tools/catalog.py:28] |
| `exposure` | `Literal["planner_visible", "node_only", "internal"]`, default `planner_visible`. [VERIFIED: src/tools/catalog.py:29] | Missing from §12.6 `ToolDescriptor` code block. [CITED: docs/contract-spec.md:1317-1328] | Required Phase 39 addition; visibility and investigate-name filtering use it. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: src/tools/policy.py:297-300] [VERIFIED: src/tools/catalog.py:394-402] | Add to §12.6 `ToolDescriptor`. [VERIFIED: src/tools/catalog.py:29] |
| `requires_approval` | `bool`, default `False`. [VERIFIED: src/tools/catalog.py:30] | Missing from §12.6 `ToolDescriptor` code block. [CITED: docs/contract-spec.md:1317-1328] | Required Phase 39 addition; policy has an approval gate. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: src/tools/policy.py:144-152] | Add to §12.6 `ToolDescriptor`. [VERIFIED: src/tools/catalog.py:30] |
| `requires_safety_snapshot` | `bool`, default `False`. [VERIFIED: src/tools/catalog.py:31] | Missing from §12.6 `ToolDescriptor` code block. [CITED: docs/contract-spec.md:1317-1328] | Required Phase 39 addition; `create_coupon_grant_draft` sets it `True` and policy has a safety snapshot gate. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: src/tools/catalog.py:360-363] [VERIFIED: src/tools/policy.py:154-162] | Add to §12.6 `ToolDescriptor`. [VERIFIED: src/tools/catalog.py:31] |
| `requires_idempotency_key` | `bool`, default `False`. [VERIFIED: src/tools/catalog.py:32] | Missing from §12.6 `ToolDescriptor` code block. [CITED: docs/contract-spec.md:1317-1328] | Required Phase 39 addition; `create_coupon_grant_draft` sets it `True` and policy has an idempotency gate. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: src/tools/catalog.py:360-363] [VERIFIED: src/tools/policy.py:164-171] | Add to §12.6 `ToolDescriptor`. [VERIFIED: src/tools/catalog.py:32] |

### §12.6 `ToolPolicyDecision`

| Field | Implemented Type / Semantics | Current §12.6 Status | Research Finding | Planner Action |
|-------|------------------------------|----------------------|------------------|----------------|
| `schema_version` | `Literal["tool_policy_decision.v1"]`, default `"tool_policy_decision.v1"`. [VERIFIED: src/tools/contracts.py:172] | Present. [CITED: docs/contract-spec.md:1336-1337] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `tool_name` | Tool name. [VERIFIED: src/tools/contracts.py:173] | Present. [CITED: docs/contract-spec.md:1338] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `caller` | Caller node. [VERIFIED: src/tools/contracts.py:174] | Present. [CITED: docs/contract-spec.md:1339] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `decision_stage` | `Literal["visibility", "runtime_auth"]`. [VERIFIED: src/tools/contracts.py:175] | Present. [CITED: docs/contract-spec.md:1340] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `decision` | `Literal["visible", "hidden", "allowed", "denied"]`. [VERIFIED: src/tools/contracts.py:176] | Present. [CITED: docs/contract-spec.md:1341] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `reason_codes` | Validated list of core or namespaced reason codes. [VERIFIED: src/tools/contracts.py:177] [VERIFIED: src/tools/policy.py:18-39] | Present. [CITED: docs/contract-spec.md:1342] | No gap in field; current core reason codes include action-safety/runtime availability reasons. [VERIFIED: src/tools/policy.py:18-39] | Avoid creating freeform reason-code spec text inconsistent with validator. [VERIFIED: tests/tools/test_tool_platform.py:491-504] |
| `required_scopes` | Required permission/scope tokens. [VERIFIED: src/tools/contracts.py:178] | Present. [CITED: docs/contract-spec.md:1343] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `matched_scope` | Optional matched scope. [VERIFIED: src/tools/contracts.py:179] | Present. [CITED: docs/contract-spec.md:1344] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `policy_version` | Policy version string. [VERIFIED: src/tools/contracts.py:180] | Present. [CITED: docs/contract-spec.md:1345] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `data_classification` | `Literal["public", "internal", "sensitive", "restricted"]`. [VERIFIED: src/tools/contracts.py:181] | Present. [CITED: docs/contract-spec.md:1346] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `resource_scope_binding` | Optional resource binding. [VERIFIED: src/tools/contracts.py:182] | Present. [CITED: docs/contract-spec.md:1347] | No gap. [VERIFIED: source/spec comparison] | Do not change. [VERIFIED: source/spec comparison] |
| `runtime_available` | `bool \| None`, records tool availability in visibility/runtime decisions. [VERIFIED: src/tools/contracts.py:183] [VERIFIED: src/tools/policy.py:263-327] | Missing from §12.6 `ToolPolicyDecision` code block. [CITED: docs/contract-spec.md:1336-1348] | Required Phase 39 addition; visibility decisions set it from availability map and runtime unavailable denials set it false. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: src/tools/policy.py:314-327] [VERIFIED: src/tools/runtime.py:135-149] | Add to §12.6 `ToolPolicyDecision`. [VERIFIED: src/tools/contracts.py:183] |
| `availability_summary` | `str \| None`, safe availability explanation. [VERIFIED: src/tools/contracts.py:184] [VERIFIED: src/tools/policy.py:310-327] | Missing from §12.6 `ToolPolicyDecision` code block. [CITED: docs/contract-spec.md:1336-1348] | Required Phase 39 addition; policy/runtime populate safe unavailable summaries. [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: src/tools/policy.py:310-327] [VERIFIED: src/tools/runtime.py:139-149] | Add to §12.6 `ToolPolicyDecision`. [VERIFIED: src/tools/contracts.py:184] |

## §8.0 Identity/Scope Separation

| Category | Fields | Source / Rule | Phase 39 Handling |
|----------|--------|---------------|-------------------|
| Locked `TrustedContext` projections | `tenant_id`, `user_id`, `role`, `permissions`, `merchant_scope`, `session_id`, `thread_id`, `run_id`, `trace_id`. [CITED: docs/contract-spec.md:43-55] [CITED: docs/contract-spec.md:149-159] | §8.0 owns trusted identity/scope semantics, and `ToolCallContext` must not redefine/widen/rename these fields. [CITED: docs/contract-spec.md:37-39] | Preserve existing §12.5 statement that these are §8.0 projections; do not add new semantics in §12.5. [CITED: docs/contract-spec.md:1221] |
| Tool-call-local execution fields already in §12.5 | `request_id`, `tool_call_id`, `caller_node`, `deadline_at`, `attempt`, `max_attempts`, `idempotency_key`, `policy_snapshot_ref`. [CITED: docs/contract-spec.md:1235-1242] | Caller/projection helpers inject these fields. [VERIFIED: src/platform/context_projections.py:86-122] | Keep as local fields. [VERIFIED: src/tools/contracts.py:26-36] |
| Tool-call-local fields missing from §12.5 | `effective_at`, `approval_ref`, `safety_snapshot_ref`. [VERIFIED: src/tools/contracts.py:30-35] | Projection helper accepts and passes these into `ToolCallContext`; policy gates consume approval/safety refs. [VERIFIED: src/platform/context_projections.py:93-121] [VERIFIED: src/tools/policy.py:144-162] | Add to §12.5 code block and local-field explanation; explicitly keep them outside §8.0 identity semantics. [VERIFIED: .planning/REQUIREMENTS.md] |

## Commit `4dcb673` Check

| Check | Evidence | Result |
|-------|----------|--------|
| Did commit `4dcb673` touch `docs/contract-spec.md`? | `git show --stat --oneline 4dcb673` reports `docs/contract-spec.md | 5 +-`. [VERIFIED: git show --stat 4dcb673] | Yes, the file was touched. [VERIFIED: git show --stat 4dcb673] |
| Did the displayed `docs/contract-spec.md` diff hunk touch §12.5/§12.6? | `git show --unified=80 4dcb673 -- docs/contract-spec.md` displayed a hunk around `memory_write_events`, changing `schema_version` default to `memory_write_event.v3` and adding `policy_version`, `blocked_by_json`, and `authority_class`. [VERIFIED: git show --unified=80 4dcb673 -- docs/contract-spec.md] | No relevant §12.5/§12.6 change found in that commit diff. [VERIFIED: git show --unified=80 4dcb673 -- docs/contract-spec.md] |
| Does current on-disk §12.5/§12.6 still have gaps? | Current lines show §12.5 lacks `effective_at`, `approval_ref`, and `safety_snapshot_ref`; §12.6 lacks descriptor executor/exposure/safety fields, `action` event family, and policy availability fields. [CITED: docs/contract-spec.md:1219-1398] [VERIFIED: src/tools/contracts.py:13-36] [VERIFIED: src/tools/catalog.py:14-32] [VERIFIED: src/tools/contracts.py:161-185] | Yes; Phase 39 should reconcile current on-disk spec. [VERIFIED: source/spec comparison] |

## Standard Stack

### Core

| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| Markdown in `docs/contract-spec.md` | n/a | Normative contract source for §8.0, §12.5, and §12.6. [CITED: docs/contract-spec.md:37-39] [CITED: docs/contract-spec.md:1219-1398] | Phase 39 is a spec reconciliation phase and should edit this source, not production code. [VERIFIED: .planning/ROADMAP.md] |
| Pydantic | 2.13.4 | Defines implemented contract models and `model_fields` inventories used for reconciliation. [VERIFIED: uv run python field inventory] | Existing contracts use `BaseModel` with `extra="forbid"` for tool DTO shapes. [VERIFIED: src/tools/contracts.py:13-231] [VERIFIED: src/tools/catalog.py:14-32] |
| pytest | 9.0.3 | Existing focused regression and architecture tests for trusted context boundaries, catalog metadata, policy decision shape, and runtime gates. [VERIFIED: uv run python -c import pytest] [VERIFIED: tests/architecture/test_trusted_context_boundaries.py:58-82] [VERIFIED: tests/tools/test_tool_platform.py:442-546] | Phase 39 should reuse existing tests instead of adding runtime behavior tests for a docs-only change. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-REVIEW.md] |
| Ruff | 0.15.12 | Project lint entrypoint for Python files if any test/docs helper is added. [VERIFIED: uv run ruff --version] | MOCA requires `uv run ruff` rather than PATH-dependent tooling. [VERIFIED: AGENTS.md] |
| Git | available | Commit/diff evidence for `4dcb673`, doc-only surface, and whitespace checks. [VERIFIED: git show 4dcb673] [VERIFIED: git status --short] | Phase 39 needs exact diff checks before/after editing. [VERIFIED: .planning/ROADMAP.md] |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| `rg` | available | Locate §12.5/§12.6 fields and verify final spec mentions. [VERIFIED: rg scans in research] | Use for structural acceptance checks after the spec edit. [VERIFIED: AGENTS.md] |
| `uv` | 0.11.2 | Project-approved command runner. [VERIFIED: uv --version] | Use for every Python test/lint command. [VERIFIED: AGENTS.md] |
| Python | 3.13.3 active via local environment probe; project requires `>=3.12`. [VERIFIED: python3 --version] [VERIFIED: pyproject.toml] | Runtime model-field introspection and tests. [VERIFIED: uv run python field inventory] | Use only via `uv run python ...` or `.venv/bin/python ...` for validation scripts. [VERIFIED: AGENTS.md] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Editing production models | Add fields to `src/tools/contracts.py` or `src/tools/catalog.py`. [VERIFIED: src/tools/contracts.py:13-36] [VERIFIED: src/tools/catalog.py:14-32] | Do not use; implementation already has required fields and Phase 39 is spec-catches-up-to-code. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: .planning/REQUIREMENTS.md] |
| Adding new generated spec tests | Create a parser that compares docs code blocks to Pydantic models. [ASSUMED] | Not necessary for one doc reconciliation; existing model-field inventory and focused tests are enough unless planner wants durable doc drift checks. [VERIFIED: source/spec comparison] |
| Running DB-backed Phase 38 full relevant suite | Re-run `uv run pytest ...` with compose PostgreSQL. [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-VERIFICATION.md] | Optional; Phase 39 doc-only validation should not require PostgreSQL unless code changes occur. [VERIFIED: .planning/ROADMAP.md] |

**Installation:** No new package installation is recommended for Phase 39. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: pyproject.toml]

**Version verification:** Python package/runtime versions were verified locally with `uv run python -c "import pydantic, pytest; ..."`, `uv run ruff --version`, and `uv --version`. [VERIFIED: command outputs in research session]

## Architecture Patterns

### System Architecture Diagram

```text
Current implementation models
  src/tools/contracts.py
  src/tools/catalog.py
  src/tools/policy.py
  src/tools/runtime.py
        |
        v
Field inventory + source/spec comparison
        |
        +--> §8.0 locked identity fields? ---- yes ---> preserve wording; do not redefine
        |                                      |
        |                                      no
        v
§12.5 / §12.6 doc patch in docs/contract-spec.md
        |
        v
Structural verification
  - required fields present
  - protected identity fields unchanged
  - doc-only diff unless explicitly justified
        |
        v
Dual review gate
  gsd-plan-checker -> Codex cross-review -> adjudication
```

This flow reflects the phase goal: implementation is source evidence, `docs/contract-spec.md` is the normative document to update, and §8.0 identity semantics remain upstream-owned. [VERIFIED: .planning/ROADMAP.md] [CITED: docs/contract-spec.md:37-39] [VERIFIED: src/tools/contracts.py:13-36]

### Recommended Project Structure

```text
docs/
└── contract-spec.md      # sole expected spec edit surface for Phase 39
tests/
├── architecture/         # existing trusted-context boundary tests
└── tools/                # existing catalog/policy/runtime contract tests
.planning/phases/39-contract-spec-12-5-12-6-reconciliation/
└── 39-01-PLAN.md         # recommended single plan
```

The expected implementation file surface is `docs/contract-spec.md`; tests are existing validation surfaces unless the planner adds doc drift tests intentionally. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: tests/architecture/test_trusted_context_boundaries.py:58-82] [VERIFIED: tests/tools/test_catalog.py:218-225]

### Pattern 1: Spec Catches Up To Code

**What:** Treat implemented Pydantic/catalog fields as evidence, then patch only the normative type-definition snippets and nearby rules that are stale. [VERIFIED: src/tools/contracts.py:13-36] [VERIFIED: src/tools/catalog.py:14-32] [CITED: docs/contract-spec.md:1219-1398]

**When to use:** Use for TPH-02 because Phase 37/38 intentionally left `docs/contract-spec.md` untouched while implementation reached the final v2.1 shape. [VERIFIED: .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-03-SUMMARY.md] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-REVIEW.md]

**Example:**

```python
# Source: src.tools.contracts.ToolCallContext [VERIFIED: src/tools/contracts.py:13-36]
class ToolCallContext(BaseModel):
    effective_at: str | None = None
    approval_ref: str | None = None
    safety_snapshot_ref: str | None = None
```

### Pattern 2: Keep Identity Fields Upstream-Owned

**What:** Preserve §12.5 wording that identity/scope/permission fields are projections of §8.0 `TrustedContext`; add missing local fields separately. [CITED: docs/contract-spec.md:37-39] [CITED: docs/contract-spec.md:1221]

**When to use:** Use whenever editing the `ToolCallContext` code block or explanatory paragraph. [VERIFIED: .planning/REQUIREMENTS.md]

**Example:**

```text
Locked identity/scope/permission fields:
tenant_id, user_id, role, permissions, merchant_scope,
session_id, thread_id, run_id, trace_id

Tool-call-local additions for Phase 39:
effective_at, approval_ref, safety_snapshot_ref
```

The separation above is required by §8.0 projection rules and TPH-02. [CITED: docs/contract-spec.md:149-159] [VERIFIED: .planning/REQUIREMENTS.md]

### Pattern 3: Validate With Field Inventory And Diff Checks

**What:** Use runtime field inventory, `rg`, `git diff`, and focused tests to prove doc-only reconciliation. [VERIFIED: uv run python field inventory] [VERIFIED: rg scans in research] [VERIFIED: git status --short]

**When to use:** Use before final review and before TPH-02 is marked complete. [VERIFIED: .planning/ROADMAP.md]

**Example:**

```bash
uv run python - <<'PY'
from src.tools.contracts import ToolCallContext, ToolPolicyDecision
from src.tools.catalog import ToolDescriptor
for model in (ToolCallContext, ToolDescriptor, ToolPolicyDecision):
    print(model.__name__, sorted(model.model_fields))
PY
```

This command uses the project-approved `uv run` entrypoint and avoids bare Python validation. [VERIFIED: AGENTS.md]

### Anti-Patterns to Avoid

- **Treating §12.5 as a new identity schema:** §8.0 already owns identity/scope/permission semantics, and §12.5 must not redefine them. [CITED: docs/contract-spec.md:37-39] [CITED: docs/contract-spec.md:1221]
- **Changing production models during spec reconciliation:** The required fields already exist in implementation. [VERIFIED: src/tools/contracts.py:13-36] [VERIFIED: src/tools/catalog.py:14-32] [VERIFIED: src/tools/contracts.py:161-185]
- **Adding new action output semantics:** Phase 38 deliberately left `create_coupon_grant_draft` on generic action output schema because action output hardening is outside TPH-01/TPH-02. [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-02-SUMMARY.md] [VERIFIED: src/tools/catalog.py:325-363]
- **Using bare test commands:** Bare `pytest` or bare `python -m pytest` is invalid MOCA verification. [VERIFIED: AGENTS.md]
- **Staging unrelated dirty local logs:** The worktree currently has `.planning/LOCAL-VALIDATION-ISSUES.md` modified before Phase 39 research output; Phase 39 should not stage unrelated local validation logs unless it adds a new required entry. [VERIFIED: git status --short]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Field inventory | A manually guessed list of implemented fields. [ASSUMED] | `uv run python` over `model.model_fields` and `ToolCatalog().descriptors()`. [VERIFIED: uv run python field inventory] | The implementation is already Pydantic/catalog-backed, so runtime introspection is exact for current code. [VERIFIED: src/tools/contracts.py:13-231] [VERIFIED: src/tools/catalog.py:405-424] |
| Spec drift detection | A new parser for this single phase. [ASSUMED] | `rg` required names, `git diff -- docs/contract-spec.md`, and focused tests. [VERIFIED: rg scans in research] [VERIFIED: git diff usage in Phase 38 summaries] | The phase is doc-only and has one expected file surface. [VERIFIED: .planning/ROADMAP.md] |
| Identity semantics | A new `ToolCallContext` identity table in §12.5. [ASSUMED] | Cross-reference §8.0 and preserve the existing projection wording. [CITED: docs/contract-spec.md:37-39] [CITED: docs/contract-spec.md:1221] | §8.0 is the canonical trusted identity/scope owner. [CITED: docs/contract-spec.md:37-39] |
| Runtime behavior proof | New executor or policy implementation. [ASSUMED] | Existing tests in `tests/tools/test_tool_platform.py`, `tests/tools/test_catalog.py`, and `tests/architecture/test_trusted_context_boundaries.py`. [VERIFIED: tests/tools/test_tool_platform.py:442-546] [VERIFIED: tests/tools/test_catalog.py:218-225] [VERIFIED: tests/architecture/test_trusted_context_boundaries.py:58-82] | Implementation behavior already passed Phase 38 verification and review. [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-VERIFICATION.md] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-REVIEW.md] |

**Key insight:** Phase 39 is not a runtime hardening phase; it is a documentation reconciliation phase whose safety depends on faithfully reflecting current backend contracts while preserving §8.0 ownership. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: .planning/REQUIREMENTS.md] [CITED: docs/contract-spec.md:37-39]

## Common Pitfalls

### Pitfall 1: Redefining Locked Identity Fields

**What goes wrong:** A spec edit adds new type details or compatibility shape language to `tenant_id`, `user_id`, `role`, `permissions`, `merchant_scope`, `session_id`, `thread_id`, `run_id`, or `trace_id`. [VERIFIED: .planning/ROADMAP.md]

**Why it happens:** §12.5 contains the `ToolCallContext` code block, but §8.0 owns the trusted identity contract. [CITED: docs/contract-spec.md:37-39] [CITED: docs/contract-spec.md:1221]

**How to avoid:** Keep a separate locked-field table in the plan and review diff only local-field additions. [VERIFIED: .planning/REQUIREMENTS.md]

**Warning signs:** Diff adds comments or changed types next to the nine protected identity/scope fields. [VERIFIED: docs/contract-spec.md:1224-1242]

### Pitfall 2: Expanding Scope Into Production Code

**What goes wrong:** The plan edits `src/tools/contracts.py`, `src/tools/catalog.py`, `src/tools/policy.py`, or `src/tools/runtime.py` even though required fields already exist. [VERIFIED: src/tools/contracts.py:13-36] [VERIFIED: src/tools/catalog.py:14-32] [VERIFIED: src/tools/policy.py:374-464] [VERIFIED: src/tools/runtime.py:176-190]

**Why it happens:** Spec/code mismatch can look like an implementation bug until current implementation is inventoried. [VERIFIED: source/spec comparison]

**How to avoid:** Make `git diff --name-only` part of acceptance and require explicit justification for any production-code file. [VERIFIED: .planning/ROADMAP.md]

**Warning signs:** Files outside `docs/contract-spec.md` appear in the implementation diff. [VERIFIED: .planning/ROADMAP.md]

### Pitfall 3: Missing `event_family="action"`

**What goes wrong:** §12.6 updates descriptor fields but leaves `event_family` as `Literal["tool_call_*", "rag_retrieval_*"]`. [CITED: docs/contract-spec.md:1326]

**Why it happens:** The read/retrieval tool table dominates §12.6, while the write action descriptor is node-only. [CITED: docs/contract-spec.md:1396-1407] [VERIFIED: src/tools/catalog.py:325-363]

**How to avoid:** Add `"action"` to the `ToolDescriptor.event_family` type and ensure the action row semantics remain node-only. [VERIFIED: src/tools/catalog.py:26] [VERIFIED: src/tools/catalog.py:360-363]

**Warning signs:** Final `rg -n 'event_family: Literal' docs/contract-spec.md` still shows only two values. [CITED: docs/contract-spec.md:1326]

### Pitfall 4: Confusing Planner Visibility With Runtime Availability

**What goes wrong:** The spec omits `runtime_available` / `availability_summary`, making visibility decisions look equivalent to runtime authorization. [VERIFIED: src/tools/contracts.py:183-184] [VERIFIED: src/tools/policy.py:263-327]

**Why it happens:** Current §12.6 `ToolPolicyDecision` block predates the availability metadata. [CITED: docs/contract-spec.md:1336-1348]

**How to avoid:** Add both fields and keep the rule that planner-visible is not runtime-allowed. [CITED: docs/contract-spec.md:1389] [VERIFIED: src/tools/policy.py:374-438]

**Warning signs:** §12.6 still lacks both field names after the doc edit. [CITED: docs/contract-spec.md:1336-1348]

## Code Examples

Verified implementation patterns from local sources:

### Current `ToolDescriptor` Shape

```python
# Source: src/tools/catalog.py [VERIFIED: src/tools/catalog.py:14-32]
class ToolDescriptor(BaseModel):
    event_family: Literal["tool_call_*", "rag_retrieval_*", "action"] | None
    executor: Literal["business", "knowledge", "memory", "action"] | None = None
    exposure: Literal["planner_visible", "node_only", "internal"] = "planner_visible"
    requires_approval: bool = False
    requires_safety_snapshot: bool = False
    requires_idempotency_key: bool = False
```

### Current Action Descriptor Metadata

```python
# Source: src/tools/catalog.py [VERIFIED: src/tools/catalog.py:325-363]
_ToolDeclaration(
    name="create_coupon_grant_draft",
    kind="write",
    event_family="action",
    executor="action",
    exposure="node_only",
    requires_safety_snapshot=True,
    requires_idempotency_key=True,
)
```

### Current `ToolPolicyDecision` Availability Fields

```python
# Source: src/tools/contracts.py [VERIFIED: src/tools/contracts.py:161-185]
class ToolPolicyDecision(BaseModel):
    runtime_available: bool | None = None
    availability_summary: str | None = None
```

### Current Runtime Availability Population

```python
# Source: src/tools/runtime.py [VERIFIED: src/tools/runtime.py:135-149]
decision = self._denied_decision(
    tool_name=tool_name,
    ctx=ctx,
    reason_codes=["tool_unavailable"],
    required_scopes=[descriptor.required_permission],
    runtime_available=False,
    availability_summary=f"Tool {tool_name!r} executor is unavailable",
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| §12.6 documented `ToolDescriptor` without executor/exposure/action-safety metadata. [CITED: docs/contract-spec.md:1317-1328] | Implementation descriptor includes `executor`, `exposure`, `requires_approval`, `requires_safety_snapshot`, and `requires_idempotency_key`. [VERIFIED: src/tools/catalog.py:14-32] | Phase 37 established single-source declarations and left spec reconciliation to Phase 39. [VERIFIED: .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-01-SUMMARY.md] | Spec must catch up; code should not be changed. [VERIFIED: .planning/ROADMAP.md] |
| §12.6 documented `event_family` with read/retrieval values only. [CITED: docs/contract-spec.md:1326] | Implementation includes `event_family="action"` for the node-only write action. [VERIFIED: src/tools/catalog.py:325-363] | Phase 37/38 current implementation state. [VERIFIED: src/tools/catalog.py:14-32] | Add `"action"` to the normative type definition. [VERIFIED: .planning/REQUIREMENTS.md] |
| §12.6 documented `ToolPolicyDecision` without availability metadata. [CITED: docs/contract-spec.md:1336-1348] | Implementation carries `runtime_available` and `availability_summary`, and policy/runtime populate them. [VERIFIED: src/tools/contracts.py:183-184] [VERIFIED: src/tools/policy.py:314-327] [VERIFIED: src/tools/runtime.py:135-149] | Current post-Phase 37/38 tool platform. [VERIFIED: .planning/STATE.md] | Add both fields to §12.6. [VERIFIED: .planning/REQUIREMENTS.md] |
| §12.5 documented `ToolCallContext` without `effective_at`, `approval_ref`, or `safety_snapshot_ref`. [CITED: docs/contract-spec.md:1224-1242] | Implementation and projection helper carry these tool-local/action-safety fields. [VERIFIED: src/tools/contracts.py:30-35] [VERIFIED: src/platform/context_projections.py:93-121] | Current implementation before Phase 39. [VERIFIED: src/tools/contracts.py:13-36] | Add fields as local fields without changing §8.0 identity semantics. [VERIFIED: .planning/REQUIREMENTS.md] |
| Phase 38 left docs untouched while hardening `output_schema`. [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-REVIEW.md] | Phase 39 owns spec reconciliation. [VERIFIED: .planning/ROADMAP.md] | Phase 38 verification/review completed on 2026-07-02. [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-VERIFICATION.md] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-REVIEW.md] | Plan should reference Phase 38 final implemented state. [VERIFIED: .planning/STATE.md] |

**Deprecated/outdated:**
- The §12.6 descriptor snippet omitting executor/exposure/action-safety fields is outdated relative to `src/tools/catalog.py`. [CITED: docs/contract-spec.md:1317-1328] [VERIFIED: src/tools/catalog.py:14-32]
- The §12.6 `event_family` literal omitting `"action"` is outdated relative to `create_coupon_grant_draft`. [CITED: docs/contract-spec.md:1326] [VERIFIED: src/tools/catalog.py:325-363]
- The §12.6 `ToolPolicyDecision` snippet omitting runtime availability fields is outdated relative to `src/tools/contracts.py`. [CITED: docs/contract-spec.md:1336-1348] [VERIFIED: src/tools/contracts.py:183-184]
- The §12.5 `ToolCallContext` snippet omitting `effective_at`, `approval_ref`, and `safety_snapshot_ref` is outdated relative to `src/tools/contracts.py`. [CITED: docs/contract-spec.md:1224-1242] [VERIFIED: src/tools/contracts.py:30-35]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A generated docs parser is unnecessary for this single doc-only phase. [ASSUMED] | Standard Stack / Don't Hand-Roll | If wrong, planner may need a Wave 0 doc-drift test before editing. |
| A2 | Manually guessed field lists and new parsers are examples of what not to build. [ASSUMED] | Don't Hand-Roll | Low risk; recommendations are backed by verified runtime field inventory alternatives. |

## Open Questions

1. **Should §8.0 projection table local-field note be updated?**
   - What we know: §8.0 projection table currently lists `request_id` / `tool_call_id` / `caller_node` / `deadline_at` / `attempt` / `idempotency_key` / `policy_snapshot_ref` as tool-call-local fields and does not list `effective_at`, `approval_ref`, or `safety_snapshot_ref`. [CITED: docs/contract-spec.md:149-155]
   - What's unclear: Phase title/success criteria focus on §12.5/§12.6, but leaving the §8.0 note stale may confuse reviewers. [VERIFIED: .planning/ROADMAP.md]
   - Recommendation: Keep the main edit in §12.5/§12.6; allow a minimal §8.0 projection-note update only if it adds the local-field names without redefining §8.0 semantics. [CITED: docs/contract-spec.md:37-39] [VERIFIED: .planning/REQUIREMENTS.md]
2. **Should `ToolDescriptor.description` be added to §12.6?**
   - What we know: implementation includes `description: str = ""`, but TPH-02 success criteria do not list it. [VERIFIED: src/tools/catalog.py:18] [VERIFIED: .planning/REQUIREMENTS.md]
   - What's unclear: Adding it would improve exact model parity, but it is outside the user-listed required field set. [VERIFIED: user prompt]
   - Recommendation: Keep Phase 39 narrow; add `description` only if the planner explicitly scopes "full current model parity" beyond the enumerated TPH-02 fields. [VERIFIED: .planning/ROADMAP.md]
3. **Should §12.6 document `event_family: ... | None`?**
   - What we know: implementation type allows `None`, but all current default catalog descriptors set a non-`None` event family. [VERIFIED: src/tools/catalog.py:26] [VERIFIED: uv run python descriptor inventory]
   - What's unclear: The phase requirement explicitly names `event_family` value `action`, not `None`. [VERIFIED: .planning/REQUIREMENTS.md]
   - Recommendation: Add `"action"` as required; document `None` only if wording says it is an implementation optionality for non-emitting future descriptors, not current catalog behavior. [VERIFIED: src/tools/catalog.py:26] [VERIFIED: .planning/REQUIREMENTS.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Project-approved validation entrypoint. [VERIFIED: AGENTS.md] | yes [VERIFIED: uv --version] | 0.11.2 [VERIFIED: uv --version] | `.venv/bin/...` only after confirming repo venv. [VERIFIED: AGENTS.md] |
| Python | Model-field inventory and pytest runtime. [VERIFIED: uv run python field inventory] | yes [VERIFIED: python3 --version] | 3.13.3 local; project requires `>=3.12`. [VERIFIED: python3 --version] [VERIFIED: pyproject.toml] | Use `.venv/bin/python` only if `uv` is unavailable. [VERIFIED: AGENTS.md] |
| pytest | Focused validation tests. [VERIFIED: tests/tools/test_tool_platform.py] | yes [VERIFIED: uv run python -c import pytest] | 9.0.3 [VERIFIED: uv run python -c import pytest] | None needed. [VERIFIED: pyproject.toml] |
| Ruff | Lint if Python validation helper/test changes occur. [VERIFIED: pyproject.toml] | yes [VERIFIED: uv run ruff --version] | 0.15.12 [VERIFIED: uv run ruff --version] | Skip if docs-only and no Python files changed. [VERIFIED: .planning/ROADMAP.md] |
| PostgreSQL | Optional DB-backed broad regression, not required for recommended Phase 39 doc-only checks. [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-VERIFICATION.md] | not probed in research [VERIFIED: no pg_isready command run] | — | Avoid DB-backed suite unless code changes or reviewer asks; Phase 38 already passed DB-backed full relevant suite. [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-VERIFICATION.md] |

**Missing dependencies with no fallback:**
- None found for the recommended Phase 39 doc-only validation path. [VERIFIED: environment probes listed above]

**Missing dependencies with fallback:**
- PostgreSQL was not probed because Phase 39 should not require DB-backed validation unless code changes occur. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: no pg_isready command run]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 via `uv run pytest`. [VERIFIED: uv run python -c import pytest] |
| Config file | `pyproject.toml` with `[tool.pytest.ini_options] asyncio mode. [VERIFIED: pyproject.toml] |
| Quick run command | `uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/tools/test_catalog.py::test_action_descriptor_is_node_only_and_requires_idempotency tests/tools/test_tool_platform.py::test_tool_policy_decision_is_not_an_event_envelope tests/tools/test_tool_platform.py::test_runtime_auth_gate_sequence_is_declarative_and_ordered -q` [VERIFIED: tests exist] |
| Full suite command | For this doc-only phase, use the quick run plus structural diff checks below; do not require DB-backed broad suite unless code changes. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-VERIFICATION.md] |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| TPH-02 | Required field names appear in §12.5/§12.6 after edit. [VERIFIED: .planning/REQUIREMENTS.md] | structural docs | `rg -n "effective_at|approval_ref|safety_snapshot_ref|executor|exposure|requires_approval|requires_safety_snapshot|requires_idempotency_key|runtime_available|availability_summary|action" docs/contract-spec.md` [VERIFIED: rg available] | yes [VERIFIED: docs/contract-spec.md] |
| TPH-02 | Protected §8.0 identity fields are not redefined/widened/renamed in production code. [VERIFIED: .planning/ROADMAP.md] | architecture | `uv run pytest tests/architecture/test_trusted_context_boundaries.py -q` [VERIFIED: tests/architecture/test_trusted_context_boundaries.py] | yes [VERIFIED: tests/architecture/test_trusted_context_boundaries.py] |
| TPH-02 | Descriptor action-safety metadata remains implemented as researched. [VERIFIED: src/tools/catalog.py:325-363] | unit | `uv run pytest tests/tools/test_catalog.py::test_action_descriptor_is_node_only_and_requires_idempotency -q` [VERIFIED: tests/tools/test_catalog.py:218-225] | yes [VERIFIED: tests/tools/test_catalog.py] |
| TPH-02 | `ToolPolicyDecision` remains a decision sub-object, not a replay event envelope, while availability fields are accepted. [VERIFIED: src/tools/contracts.py:161-185] | unit | `uv run pytest tests/tools/test_tool_platform.py::test_tool_policy_decision_is_not_an_event_envelope -q` [VERIFIED: tests/tools/test_tool_platform.py:442-478] | yes [VERIFIED: tests/tools/test_tool_platform.py] |
| TPH-02 | Runtime action-safety gates still correspond to descriptor/context fields. [VERIFIED: src/tools/policy.py:236-244] | unit | `uv run pytest tests/tools/test_tool_platform.py::test_runtime_auth_gate_sequence_is_declarative_and_ordered tests/tools/test_tool_platform.py::test_runtime_auth_declarative_gates_preserve_multi_denial_reason_order -q` [VERIFIED: tests/tools/test_tool_platform.py:512-546] | yes [VERIFIED: tests/tools/test_tool_platform.py] |
| TPH-02 | Phase diff is docs-only unless explicitly justified. [VERIFIED: .planning/ROADMAP.md] | structural diff | `git diff --name-only -- docs/contract-spec.md src/tools/contracts.py src/tools/catalog.py src/tools/policy.py src/tools/runtime.py tests` [VERIFIED: git available] | n/a [VERIFIED: repository git status] |
| TPH-02 | Commit `4dcb673` was checked before editing. [VERIFIED: .planning/ROADMAP.md] | git evidence | `git show --stat --oneline 4dcb673` and `git show --unified=80 4dcb673 -- docs/contract-spec.md` [VERIFIED: commands run in research] | n/a [VERIFIED: git show 4dcb673] |

### Sampling Rate

- **Per task commit:** Run the structural `rg` check and `git diff --name-only` check. [VERIFIED: .planning/ROADMAP.md]
- **Per wave merge:** Run the quick pytest command plus `git diff --check`. [VERIFIED: AGENTS.md] [VERIFIED: tests exist]
- **Phase gate:** Complete `gsd-plan-checker`, Codex cross-review, adjudication, quick pytest command, `rg` required-field check, and docs-only diff check. [VERIFIED: AGENTS.md] [VERIFIED: .planning/ROADMAP.md]

### Wave 0 Gaps

- None for runtime behavior; existing tests cover the relevant policy/catalog/context boundaries. [VERIFIED: tests/architecture/test_trusted_context_boundaries.py:58-82] [VERIFIED: tests/tools/test_catalog.py:218-225] [VERIFIED: tests/tools/test_tool_platform.py:442-546]
- Optional doc-drift parser is not required by current TPH-02 scope. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no direct implementation change. [VERIFIED: .planning/ROADMAP.md] | Preserve trusted-context source rules; do not create auth identity semantics in §12.5. [CITED: docs/contract-spec.md:37-39] |
| V3 Session Management | limited. [VERIFIED: docs/contract-spec.md:43-55] | Preserve `session_id`, `thread_id`, and `run_id` as §8.0 projections. [CITED: docs/contract-spec.md:43-55] |
| V4 Access Control | yes. [VERIFIED: .planning/REQUIREMENTS.md] | Preserve §8.0 `TrustedContext` projection semantics and runtime auth gate documentation. [CITED: docs/contract-spec.md:37-39] [VERIFIED: src/tools/policy.py:236-244] |
| V5 Input Validation | yes for documented schemas, no runtime code change. [VERIFIED: docs/contract-spec.md:1317-1348] | Keep `input_schema` / `output_schema` descriptor semantics aligned with catalog/runtime enforcement. [VERIFIED: src/tools/catalog.py:20-21] [VERIFIED: src/tools/runtime.py:176-190] |
| V6 Cryptography | no direct implementation change. [VERIFIED: .planning/ROADMAP.md] | Do not introduce crypto/hash semantics in this phase; leave action safety hash contracts to existing sections. [VERIFIED: .planning/REQUIREMENTS.md] |

### Known Threat Patterns for Tool Contract Spec Reconciliation

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Identity spoofing via doc ambiguity | Spoofing / Elevation of Privilege | Keep §12.5 identity fields explicitly owned by §8.0 and avoid new local semantics. [CITED: docs/contract-spec.md:37-39] [CITED: docs/contract-spec.md:1221] |
| Prompt exposure of internal descriptor metadata | Information Disclosure | Preserve `ToolViewV1` as the only planner-visible view and keep raw descriptor fields out of prompt views. [VERIFIED: tests/tools/test_tool_platform.py:384-403] [CITED: docs/contract-spec.md:1387] |
| Runtime unavailable tool treated as visible/allowed | Elevation of Privilege / Tampering | Document `runtime_available` and `availability_summary`; keep planner visibility distinct from runtime authorization. [VERIFIED: src/tools/policy.py:263-327] [CITED: docs/contract-spec.md:1389] |
| Action execution without required safety fields | Tampering / Repudiation | Document descriptor safety booleans and local context refs consumed by runtime auth gates. [VERIFIED: src/tools/catalog.py:325-363] [VERIFIED: src/tools/policy.py:144-171] |

## Sources

### Primary (HIGH confidence)
- `docs/contract-spec.md` §8.0, §12.5, §12.6 current on-disk text. [CITED: docs/contract-spec.md:37-159] [CITED: docs/contract-spec.md:1219-1398]
- `src/tools/contracts.py` for `ToolCallContext`, `ToolPolicyDecision`, `ToolResultV2`, `ToolViewV1`, and `ToolInvocationOutcome`. [VERIFIED: src/tools/contracts.py:13-231]
- `src/tools/catalog.py` for `ToolDescriptor`, `_ToolDeclaration`, current default descriptors, action descriptor, and descriptor construction. [VERIFIED: src/tools/catalog.py:14-32] [VERIFIED: src/tools/catalog.py:176-191] [VERIFIED: src/tools/catalog.py:325-387]
- `src/tools/policy.py` for runtime gates, availability population, and action safety checks. [VERIFIED: src/tools/policy.py:18-39] [VERIFIED: src/tools/policy.py:236-244] [VERIFIED: src/tools/policy.py:314-464]
- `src/tools/runtime.py` for executor availability, output-schema `invalid_response`, and runtime availability fields. [VERIFIED: src/tools/runtime.py:56-63] [VERIFIED: src/tools/runtime.py:132-190] [VERIFIED: src/tools/runtime.py:217-240]
- `src/tools/platform.py` for event family mapping and visibility event payloads. [VERIFIED: src/tools/platform.py:139-150] [VERIFIED: src/tools/platform.py:162-185]
- `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md` for Phase 39 scope and constraints. [VERIFIED: .planning/ROADMAP.md] [VERIFIED: .planning/REQUIREMENTS.md] [VERIFIED: .planning/STATE.md]
- Phase 37/38 summaries, verification, and review artifacts. [VERIFIED: .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-01-SUMMARY.md] [VERIFIED: .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-02-SUMMARY.md] [VERIFIED: .planning/phases/37-tool-declaration-runtime-policy-internal-consolidation/37-03-SUMMARY.md] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-01-SUMMARY.md] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-02-SUMMARY.md] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-03-SUMMARY.md] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-VERIFICATION.md] [VERIFIED: .planning/phases/38-output-schema-declaration-runtime-output-validation-enforcem/38-REVIEW.md]
- `AGENTS.md` and `CLAUDE.md` for validation entrypoints and dual-review workflow. [VERIFIED: AGENTS.md] [VERIFIED: CLAUDE.md]
- Git commit evidence for `4dcb673`. [VERIFIED: git show --stat 4dcb673] [VERIFIED: git show --unified=80 4dcb673 -- docs/contract-spec.md]

### Secondary (MEDIUM confidence)
- None; no web/ecosystem search was needed because this phase is repository-local spec reconciliation. [VERIFIED: task scope]

### Tertiary (LOW confidence)
- The optional doc-drift parser recommendation is assumed and should be revisited only if the planner wants durable spec/code drift automation. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - current local versions and project config were verified with `uv run`, `uv --version`, and `pyproject.toml`. [VERIFIED: command outputs in research session] [VERIFIED: pyproject.toml]
- Architecture: HIGH - implementation fields, normative spec sections, and Phase 37/38 summaries all agree that code is current and spec is stale. [VERIFIED: src/tools/contracts.py:13-36] [VERIFIED: src/tools/catalog.py:14-32] [VERIFIED: .planning/STATE.md]
- Pitfalls: HIGH - risks are directly grounded in §8.0 identity ownership, Phase 39 success criteria, and existing tests. [CITED: docs/contract-spec.md:37-39] [VERIFIED: .planning/ROADMAP.md] [VERIFIED: tests/architecture/test_trusted_context_boundaries.py:58-82]

**Research date:** 2026-07-02 [VERIFIED: system date]
**Valid until:** 2026-08-01 unless tool contract models or `docs/contract-spec.md` change before planning. [ASSUMED]
