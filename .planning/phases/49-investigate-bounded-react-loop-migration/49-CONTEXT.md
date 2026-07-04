# Phase 49: Investigate Bounded ReAct Loop Migration - Context

**Gathered:** 2026-07-04
**Status:** Ready for planning
**Source:** User phase prompt + live repository audit

<domain>
## Phase Boundary

Phase 49 migrates only `src/agent/nodes/investigate.py` from legacy deterministic main planning to the bounded read-only ReAct loop contract already defined in `docs/contract-spec.md` §9.4.

The core constraint is:

> Only migrate `src/agent/nodes/investigate.py` from legacy deterministic planner control to a bounded read-only ReAct loop matching `contract-spec.md` §9.4. Do not modify intent modules, memory writers, risk/approval/action chains, active slot ownership, or `contract-spec.md`.

External graph shape is not redesigned. ReAct exists only inside the single registered `investigate` node. Routers remain deterministic. `route_after_investigate` and all downstream evidence/claim/risk/approval/action gates remain outside planner authority.
</domain>

<decisions>
## Locked Decisions

### Three Trust Boundaries

- Entry boundary: deterministic nodes plus `contextual_intent_resolve` as LLM candidate + deterministic `IntentPolicyEngine` adjudication. LLM does not authorize identity, permissions, safety tier, or slot gate behavior.
- Middle boundary: only `investigate` contains a read-only bounded ReAct loop. The planner may choose one allowed read/retrieval tool per iteration.
- Exit boundary: evidence validation, claim verification, risk, approval, action draft, and action execution are fail-closed. LLM cannot override these gates.

### observation->slot 回流

- Selected option: A, loop-local.
- Discovered identifiers live only in the current investigate loop scratchpad.
- Do not write `state["active_slots"]`.
- Do not write `extracted_slots` or `candidate_slots`.
- Do not change field registry ownership.
- Do not change `contract-spec.md` §9.4.
- Do not touch memory Phase 44-48 CWC/session/case/long-term schemas or writers.

### Planner Authority

- Planner freedom is only "choose the next read/retrieval tool" or "stop".
- Planner cannot authorize actions.
- Planner cannot emit routing decisions.
- Planner cannot write `evidence_refs`.
- Planner cannot bypass `claim_verify`, `risk_gate`, `approval_gate`, `action_draft`, or `action_execution`.

### Fallback

- Current deterministic `plan_next_step` is retained as a safety fallback, not deleted first.
- Fallback triggers only when the LLM planner is unavailable, times out, emits malformed/invalid output, selects an invalid/write/unavailable tool, or emits invalid args.
- Fallback remains read-only and still goes through `ToolPlatform.invoke(...)`.
- Fallback is a safety net, not a second main controller competing with the LLM planner.
</decisions>

<canonical_refs>
## Canonical References

Downstream agents MUST read these before implementing.

### Normative Contract

- `docs/contract-spec.md` §9.4 — `investigate` node contract and bounded-loop 8-point contract.
- `docs/contract-spec.md` §9.5 — router contract table; routers are deterministic and side-effect-free.
- `docs/contract-spec.md` §12.4 — node-level investigate allowlist with 8 read/retrieval tools.
- `docs/contract-spec.md` §17.2 — loop tool/RAG iteration and replay rules.
- `docs/contract-spec.md` AgentState field registry — `active_slots` writer is slot/memory ownership, not investigate.

### Current Implementation

- `src/agent/nodes/investigate.py` — current deterministic `plan_next_step`, existing bounded loop shell, `ToolPlatform.invoke(...)` call path, `_case_slots`, `_accumulate_tool_result`, event emission, retrieval status handling.
- `src/tools/catalog.py` — single-source tool declarations; all eight read/retrieval investigate tools are declared.
- `src/tools/platform.py`, `src/tools/runtime.py`, `src/tools/policy.py`, `src/tools/projection.py` — ToolPlatform, runtime auth, visibility, input validation, and projection boundary.
- `src/tools/executors/knowledge.py`, `src/tools/executors/memory.py`, `src/business/service.py` — current executor availability for `search_policy`, `search_sop`, `search_case_memory`, `get_logistics`, and `get_merchant_risk`.

### Planning Baseline

- `.planning/DEFERRED-DECISIONS.md` GAD-01 — status is `SPEC_PROMOTED` + `IMPLEMENTATION_PENDING`; loop-local slot decision is recorded.
- `.planning/AGENTIC-INVESTIGATION-DISCUSSION.md` §8 — 2026-07 audit says spec is promoted, implementation still legacy deterministic.
- `docs/target-agent-platform-architecture-plan.md` §6 — trust-boundary reading guide; not normative beyond `contract-spec.md`.
- `.planning/phases/44-*` through `.planning/phases/48.1-*` — memory boundary reference only. Do not pull memory lifecycle/writer work into Phase 49.
</canonical_refs>

<repo_audit>
## Live Repository Audit

Commands run on 2026-07-04:

```bash
git status --short
git branch --show-current
rg -n 'def plan_next_step|deterministic investigation fallback|ToolPlatform.invoke|_case_slots|_accumulate' src/agent/nodes/investigate.py
rg -n 'active_slots|extracted_slots|candidate_slots' src/agent/nodes src/agent/state.py src -g '*.py'
rg -n 'get_order|get_refund_case|get_ticket|get_logistics|get_merchant_risk|search_policy|search_sop|search_case_memory' src tests docs/contract-spec.md
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_investigate.py -q
```

Observed facts:

- Current branch: `main`.
- Pre-existing uncommitted docs before Phase 49 planning: `.planning/AGENTIC-INVESTIGATION-DISCUSSION.md`, `.planning/DEFERRED-DECISIONS.md`, `docs/target-agent-platform-architecture-plan.md`. These are baseline design artifacts and must not be mixed with implementation changes.
- `investigate.py` has `plan_next_step(...)` and reason string `deterministic investigation fallback`.
- `investigate.py` already has a loop shell with `max_iterations`, `deadline_at`, `max_attempts`, `ToolPlatform.visible_tools(...)`, `ToolPlatform.invoke(...)`, projection accumulation, and per-tool event iteration fields.
- `investigate.py` does not call an LLM planner today.
- `plan_next_step(...)` currently scans four candidates: `get_order`, `get_refund_case`, `get_ticket`, `search_policy`.
- `ToolCatalog` declares all eight investigate read/retrieval tools.
- `KnowledgeToolExecutor.has_tool(...)` currently exposes only `search_policy`; `search_sop` is declared but not available with the real knowledge executor.
- `BusinessFactService` exposes `get_logistics` and `get_merchant_risk` as unavailable no-data business reads.
- `MemoryToolExecutor` exposes `search_case_memory` through `CaseMemoryService.retrieve_reviewed(...)`.
- Focused investigate tests passed: `36 passed, 1 warning`.
</repo_audit>

<expected_diff>
## Expected Diff

- `src/agent/nodes/investigate.py`
- Optional investigate-local helper/schema files if implementation keeps the node file small, for example `src/agent/nodes/investigate_planner.py`
- `src/tools/projection.py` only if loop-local slot discovery needs additional prompt-safe structured identifiers in projected observations
- `src/tools/executors/knowledge.py` only if 8-tool planner visibility requires `search_sop` to be executor-visible as an unavailable/read-only retrieval stub
- `src/agent/events.py` / replay tests only if parent operation propagation is required to satisfy §17.2 trace/replay metadata
- `tests/agent/test_nodes/test_investigate.py`
- Targeted graph/regression tests under `tests/agent/`, `tests/replay/`, `tests/tools/`, and static architecture tests as needed
- `.planning/ARCHITECTURE-DEBT.md` and the Phase 49 summary/validation docs after implementation

## Forbidden Diff

- `docs/contract-spec.md` unless a true spec blocker is found; if found, stop and report.
- Intent classifier schema/contracts: `IntentResultV3`, `TaskPlan`, `primary_intent`, `requested_operation`, `required_slots`, `routing_hints`, `contextual_intent_resolve`.
- Memory Phase 44-48 schema/service/repository/writer contracts, except tests may import existing public APIs.
- `active_slots` field registry ownership or writer behavior.
- `MemoryService` writer ownership.
- `risk_gate`, `approval_gate`, `action_draft`, action executor logic, or write tools.
- Graph router contracts or route decisions.
- New write tools.
- ReAct expansion into `policy_qa`, fact QA, general chat, or graph-level routers.
</expected_diff>

<no_go_checklist>
## No-Go Checklist

Before execution and before final merge, verify:

- [ ] `git status --short` shows no unrelated implementation changes mixed into Phase 49.
- [ ] `! rg -n "active_slots.*=" src/agent/nodes/investigate.py` proves no investigate writer.
- [ ] `rg -n "evidence_refs" src/agent/nodes/investigate.py` is manually inspected and shows no authoritative top-level `evidence_refs` writer from investigate.
- [ ] `! rg -n "BusinessFactService|PolicyKnowledgeService|CaseMemoryService|RefundRepository|OrderRepository" src/agent/nodes/investigate.py` proves no direct service/repository dispatch bypassing ToolPlatform. Existing conversation repository/service imports for trace persistence are allowed only if they do not dispatch business/knowledge/memory tools.
- [ ] `! rg -n "create_coupon_grant_draft|issue_coupon|partial_refund|full_refund|close_ticket|escalate_ticket|manual_review" src/agent/nodes/investigate.py` proves write tools are not production-reachable from investigate.
- [ ] `rg -n "create_coupon_grant_draft|write tool|write-tool" tests/agent/test_nodes/test_investigate.py` proves write-tool rejection is covered by tests.
- [ ] The 8 allowed tool names are covered by tests or explicit static validation.
- [ ] Prompt/planner context does not include raw tool payloads or projection forbidden sentinel keys.
- [ ] Memory Phase 44-48.1 regression commands are run through `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.
</no_go_checklist>

<review_checklist>
## Dual Review Checklist

GSD plan-checker and Codex/Claude cross-review must explicitly check:

- [ ] Plan granularity: four plans, single goal per plan, dependency order is 49-01 -> 49-02 -> 49-03 -> 49-04.
- [ ] Main control path is LLM planner; deterministic planner is fallback only.
- [ ] Planner output cannot contain batch plans, route decisions, approval/risk/action decisions, or write tool requests.
- [ ] Tool selection is constrained to the §12.4 8-tool allowlist and validated against descriptor input schemas before dispatch.
- [ ] ToolPlatform remains the only graph-facing dispatch path.
- [ ] `loop-local discovered slots` are a local scratchpad only, not graph state, memory, field registry, or session memory.
- [ ] Projection layer is the prompt-injection and raw-payload boundary.
- [ ] `policy-only` paths do not require business context.
- [ ] `max_iterations_reached` does not force `retrieval_status=insufficient` or erase real evidence strength.
- [ ] Trace/replay events preserve per-iteration identity and do not leak args/raw payload.
- [ ] No forbidden diff areas are modified.
- [ ] Memory Phase 44-48 and intent Phase 43 focused regressions remain green.
</review_checklist>
