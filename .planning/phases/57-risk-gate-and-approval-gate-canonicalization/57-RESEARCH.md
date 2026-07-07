# Phase 57: Risk Gate and Approval Gate Canonicalization - Research

**Researched:** 2026-07-07 [VERIFIED: system date]
**Domain:** Canonical LangGraph risk/approval boundary migration for CAGM-08 [VERIFIED: .planning/REQUIREMENTS.md:49-61]
**Confidence:** HIGH - phase scope, current code surfaces, prior handoffs, test families, and runtime state categories were source-audited in this session. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:6-12]

<user_constraints>
## User Constraints (from CONTEXT.md)

Source: `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md` lines 15-49 and 112-116. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:15]

### Locked Decisions

## Implementation Decisions

### Canonical risk node cutover
- **D-57-01:** Active `StateGraph.add_node(...)` registration must use `risk_gate`, not `assess_risk_and_approval`.
- **D-57-02:** Active conditional edge path maps from `claim_verify` and `approval_gate` edit rerisk paths must route the `risk_gate` route value to the active `risk_gate` node.
- **D-57-03:** Current-run router return values must not point to `assess_risk_and_approval` after cutover. Historical compatibility may be projection-only and must be labeled non-current.
- **D-57-04:** The existing `assess_risk_and_approval` behavior may be reused only as a narrow implementation compatibility layer if the plan records legacy surface, canonical owner, reason, trace projection, validation, and `DELETE_BY_PHASE_58`. It must not remain the active graph registration after Phase 57.

### Risk gate authority
- **D-57-05:** `risk_gate` owns risk assessment, deterministic risk-rule overrides, proposed action creation, action safety snapshot binding, approval-plan creation, blocked/manual-review outcomes, and auto-allowed draft binding.
- **D-57-06:** `risk_gate` must continue to fail closed when claim verification, evidence, action payload hash, safety snapshot ref/hash, policy/risk/retrieval versions, or approval-plan bindings are missing or invalid.
- **D-57-07:** LLM output may assist draft/risk wording only through the existing structured-output path; final risk lowering, approval requirement, blocked/manual decisions, snapshot binding, and route choice stay deterministic or fail closed.
- **D-57-08:** `llm_outputs`, trace steps, node errors, API payload extraction, and eval/frontend/runtime vocabulary for current runs should use `risk_gate`. Any legacy `assess_risk_and_approval` key must be compatibility-only and cannot become current-run authority.

### Approval gate separation
- **D-57-09:** `approval_gate` handles approval interrupt/request resume behavior only: request payload display, pending self-loop, trusted accept/approve resume, edit/superseded rerisk, respond/needs-info interrupted lifecycle, and rejected/expired/invalid finalization.
- **D-57-10:** `approval_gate` must not decide risk, lower risk, create new action recommendations, create safety snapshots, or reinterpret ordinary chat approval text.
- **D-57-11:** Trusted edit resume must route to `risk_gate` for rerisk. New current-run `resume_route` values from ApprovalService/API should be canonical `risk_gate`.
- **D-57-12:** If existing persisted approvals or historical traces still contain `resume_route == "assess_risk_and_approval"`, compatibility handling must be explicit, tested, and marked for Phase 58 deletion. It cannot be the normal current-run path.

### Trusted approval boundary
- **D-57-13:** Ordinary chat approval text cannot become trusted approval. The only trusted approval entry is the authenticated approval API/inbox command path that constructs server-side `TrustedApprovalResultV1` data with tenant/user/role, approval id, expected versions, payload hash, and safety snapshot hash.
- **D-57-14:** Tests must preserve the existing safety-pre-route and intent-policy behavior where ordinary chat `approval_decision` or approval-like wording is unsupported/untrusted and cannot enter `approval_gate`, `action_draft`, or trusted graph resume.

### Planning and validation shape
- **D-57-15:** Planning should be split into multiple ordered plans, not one large plan. Expected boundaries are: canonical `risk_gate` callable and compatibility contract; active graph/router/baseline cutover; trusted approval resume and risk/approval separation hardening; vocabulary/API/frontend/eval/docs/debt/validation closeout.
- **D-57-16:** Phase 57 must preserve Phase 56 RAG/claim fail-closed behavior and Phase 58 final cleanup scope. It must not delete every historical `assess_risk_and_approval` reference unless that deletion is explicitly safe and in scope.
- **D-57-17:** Verification commands must use MOCA-approved entrypoints such as `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`; bare `pytest` and bare `python -m pytest` are invalid.

### Claude's Discretion

### the agent's Discretion
- Exact module structure is left to the planner as long as active graph identity is canonical and legacy compatibility is narrow, explicit, and Phase 58-scoped.
- Exact names for compatibility metadata constants are implementation discretion.
- Exact API/frontend display copy is implementation discretion as long as current-run identity is `risk_gate` and historical projection remains distinguishable.

### Deferred Ideas (OUT OF SCOPE)

## Deferred Ideas

- Final deletion of all active compatibility aliases, historical projections, and remaining migration-era legacy references belongs to Phase 58.
- External action execution after `action_draft` remains out of current runtime scope unless a later spec changes the target graph.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAGM-08 | `risk_gate` replaces active `assess_risk_and_approval` graph naming and preserves separation between deterministic risk/action policy decisions and `approval_gate` pending/trusted-resume state machine. [VERIFIED: .planning/REQUIREMENTS.md:60] | Current graph registration, route maps, node implementation, approval service/API resume, projection, frontend/eval, and test families are mapped below. [VERIFIED: src/agent/graph.py:271] |
</phase_requirements>

## Summary

Phase 57 is a canonical graph identity cutover, not a risk-policy redesign. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:9] The current risk/action policy implementation lives behind `assess_risk_and_approval`, and the active graph still registers and routes that legacy node from `claim_verify` and approval edit resume paths. [VERIFIED: src/agent/graph.py:281] [VERIFIED: src/agent/graph.py:347] [VERIFIED: src/agent/graph.py:365] The target architecture requires the active registered node and current-run route vocabulary to be `risk_gate`, while any retained `assess_risk_and_approval` surface must be compatibility-only and Phase 58-scoped. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md]

The highest-risk seam is the boundary between action-risk policy and trusted approval resume. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:30] `risk_gate` should own risk assessment, deterministic overrides, proposed action creation, snapshot binding, approval-plan creation, blocked/manual-review outcomes, and auto-allowed action binding. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:24] `approval_gate` should stay an interrupt/resume state machine that validates trusted approval payload shape and does not lower risk, create actions, create snapshots, or reinterpret ordinary chat approval text. [VERIFIED: src/agent/nodes/approval_gate.py:26] [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:31]

Planning should split into four ordered plans: canonical callable and compatibility contract; active graph/router/baseline cutover; trusted approval resume plus separation hardening; and vocabulary/API/frontend/eval/docs/debt closeout. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:40] This phase should not remove every historical legacy reference; Phase 58 owns final deletion. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:42]

**Primary recommendation:** Make `risk_gate` the only active current-run graph node/route value, keep any `assess_risk_and_approval` adapter as a narrow `DELETE_BY_PHASE_58` compatibility surface, and prove the trusted approval API remains the only source of `TrustedApprovalResultV1`. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:18]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Risk assessment and action-risk routing | API / Backend graph runtime | Database / Storage for persisted trace/snapshot refs | The risk logic is implemented in graph nodes and routers, and it writes risk decisions, action hashes, safety snapshot refs, and trace/node errors into state/persistence. [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:608] [VERIFIED: src/agent/state.py:135] |
| Approval request creation and trusted resume | API / Backend approval service | Frontend for display/decision submission | `ApprovalService` creates and decides approval requests; the API constructs trusted decision commands and resumes the graph with server-side payloads. [VERIFIED: src/approvals/service.py:80] [VERIFIED: src/api/routers/approvals.py:55] |
| Approval interrupt display | Browser / Client | API / Backend SSE payload extraction | The API emits `approval_gate` events from graph interrupts, and frontend timeline display maps node names to user-facing labels. [VERIFIED: src/api/routers/agent_runs.py:708] [VERIFIED: frontend/src/components/timeline/TimelineStep.tsx:5] |
| Canonical graph vocabulary/projection | API / Backend projection layer | Frontend/eval consumers | `graph_vocabulary.py` distinguishes runtime nodes and compatibility aliases, and trace APIs project stored implementation node names to target vocabulary. [VERIFIED: src/agent/graph_vocabulary.py:55] [VERIFIED: src/repositories/trace_repo.py:67] |
| Historical compatibility for stored legacy names | API / Backend projection/retry adapters | Database / Storage | Historical trace rows can carry old node names, and approval event metadata can store old `resume_route` values read during retry handling. [VERIFIED: src/db/models.py:1178] [VERIFIED: src/db/models.py:1077] |

## Project Constraints (from CLAUDE.md)

- Local debugging, startup, UI/manual validation, API testing, RAG/agent/memory/tool-call investigation errors must be appended to `.planning/LOCAL-VALIDATION-ISSUES.md` after handling. [VERIFIED: CLAUDE.md:5]
- Core subsystem design defects or fixes in tool calls, RAG, memory, or intent recognition must be appended to `.planning/ARCHITECTURE-DEBT.md`; target contract facts and implementation facts must be kept distinct. [VERIFIED: CLAUDE.md:9]
- Phase-level plans and larger changes use the dual review workflow: GSD plan checker first, then independent Codex cross-review, then adjudication against real repo code/tests/docs. [VERIFIED: CLAUDE.md:17]
- Phase-level planning must split work when it spans multiple service boundaries, ownership domains, waves, or verification gates; one giant plan covering contract, implementation, compatibility, callers, security, and final validation is a blocker. [VERIFIED: AGENTS.md:55]
- Tests and development tools must use MOCA-approved entrypoints such as `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, `.venv/bin/pytest ...`, or `uv run ...`; bare `pytest` and bare `python -m pytest` are invalid evidence. [VERIFIED: AGENTS.md:24]
- `docs/contract-spec.md` is accepted contract context but defines semantics rather than implementation detail; if phase implementation and spec diverge, the phase must leave a decision trace instead of silently deviating. [VERIFIED: CLAUDE.md:73]

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.13 | Runtime for graph, API, schemas, tests | Project requires Python `>=3.12`, and `uv run python --version` returned 3.12.13. [VERIFIED: pyproject.toml:5] [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run python --version`] |
| LangGraph | 1.1.10 | StateGraph nodes, conditional edges, interrupt/resume command flow | The graph code imports `StateGraph`, `START`, `END`, `interrupt`, and `Command`; installed package metadata reports 1.1.10. [VERIFIED: src/agent/graph.py:8] [VERIFIED: `uv run python -c import importlib.metadata`] |
| Pydantic | 2.13.4 | Structured validation for risk, approval, and trusted resume schemas | Approval and risk schemas are Pydantic models; installed package metadata reports 2.13.4. [VERIFIED: src/approvals/schemas.py:32] [VERIFIED: `uv run python -c import importlib.metadata`] |
| FastAPI | 0.136.1 | Approval and agent-run HTTP/SSE API layer | Approval API routers use FastAPI router/dependency primitives; installed package metadata reports 0.136.1. [VERIFIED: src/api/routers/approvals.py:1] [VERIFIED: `uv run python -c import importlib.metadata`] |
| SQLAlchemy | 2.0.49 | ORM models for approval events, agent steps, approval requests, snapshots | Runtime state inventory depends on ORM models for stored JSON and trace node names; installed package metadata reports 2.0.49. [VERIFIED: src/db/models.py:1077] [VERIFIED: `uv run python -c import importlib.metadata`] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.3 | Test runner | Use for all phase verification through `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --version`] |
| pytest-asyncio | 1.3.0 | Async API/service tests | Use for approval API/service and graph async tests. [VERIFIED: `uv run python -c import importlib.metadata`] |
| ruff | 0.15.12 | Lint/format checking | Use through `UV_CACHE_DIR=/tmp/uv-cache uv run ruff ...` if the planner adds lint gates. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff --version`] |
| sse-starlette | 3.4.4 | SSE event streaming for agent runs | Agent run API emits stream events; installed package metadata reports 3.4.4. [VERIFIED: src/api/routers/agent_runs.py] [VERIFIED: `uv run python -c import importlib.metadata`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New risk rules engine | Keep `rules/risk_rules.yaml` and existing deterministic helper | The current implementation already loads YAML risk rules and applies deterministic overrides; replacing the rules engine would exceed Phase 57 scope. [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:95] |
| New approval trust parser | Existing `ApprovalService` plus `TrustedApprovalResultV1.model_validate` | Trusted approval is already server-constructed and schema-validated; a parser for ordinary chat text would violate D-57-13/D-57-14. [VERIFIED: src/approvals/service.py:722] [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:36] |
| Data migration of old trace node names | Projection compatibility through `graph_vocabulary.py` | Stored historical node names can be projected without mutating audit history; Phase 58 owns final no-debt cleanup. [VERIFIED: src/agent/graph_vocabulary.py:219] [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:112] |

**Installation:**
```bash
uv sync
```
[VERIFIED: pyproject.toml:5]

**Version verification:** Versions above were verified from the active project environment with `UV_CACHE_DIR=/tmp/uv-cache uv run ...`; no package version in this research relies on training-data memory. [VERIFIED: AGENTS.md:24]

## Architecture Patterns

### System Architecture Diagram

```text
User message / approval API command
        |
        v
receive_request -> safety_pre_route -> session_context_load -> contextual_intent_resolve
        |                    |
        |                    +-> unsafe / unsupported / ordinary approval-like chat -> final_response
        v
slot_resolution_gate -> memory_context_load -> investigate -> recommendation_generation -> claim_verify
        |                                                                    |
        |                                                                    +-> no verified action / unsafe claim -> final_response
        v
risk_gate
        |
        +-> blocked/manual-review/fail-closed -> final_response
        |
        +-> approval_required with snapshot/hash/approval_plan -> approval_gate
        |                                                        |
        |                                                        +-> pending/needs_info -> approval_gate
        |                                                        +-> trusted edit -> risk_gate
        |                                                        +-> trusted approve -> action_draft
        |                                                        +-> reject/expire/invalid -> final_response
        |
        +-> auto_allowed with verified binding -> action_draft
```

This diagram is the target Phase 57 current-run flow: `risk_gate` is the active action-risk decision owner, while `approval_gate` only manages interrupt/resume lifecycle. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:24] [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:30]

### Recommended Project Structure

```text
src/
  agent/
    graph.py                         # active StateGraph node registration and route maps [VERIFIED: src/agent/graph.py:271]
    routing.py                       # deterministic route return values after claim verification [VERIFIED: src/agent/routing.py:534]
    graph_vocabulary.py              # runtime vs compatibility alias projection [VERIFIED: src/agent/graph_vocabulary.py:55]
    nodes/
      risk_gate.py                   # canonical risk/action callable after Phase 57 [ASSUMED]
      assess_risk_and_approval.py    # optional Phase 58-scoped compatibility import surface [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:1097]
      approval_gate.py               # approval interrupt/resume node only [VERIFIED: src/agent/nodes/approval_gate.py:26]
  approvals/
    schemas.py                       # RiskDecisionV1, ApprovalRequestCreateCommand, TrustedApprovalResultV1 [VERIFIED: src/approvals/schemas.py:32]
    service.py                       # trusted approval state machine and resume payloads [VERIFIED: src/approvals/service.py:66]
  api/routers/
    approvals.py                     # authenticated approval decisions and graph resume [VERIFIED: src/api/routers/approvals.py:55]
    agent_runs.py                    # SSE/node payload projection [VERIFIED: src/api/routers/agent_runs.py:708]
tests/
  architecture/
    graph_baseline.py                # static active/target graph baseline [VERIFIED: tests/architecture/graph_baseline.py:11]
    test_canonical_graph_baseline.py # canonical graph guardrails [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:19]
  agent/
    test_graph.py                    # graph integration and ordinary chat approval safety [VERIFIED: tests/agent/test_graph.py:1116]
    test_nodes/test_risk_gate.py     # recommended canonical node tests after migration [ASSUMED]
```

### Pattern 1: Canonical Active Node With Narrow Legacy Compatibility

**What:** Register `risk_gate` in the active graph and use `risk_gate` as the current-run route value; if the old callable is reused, wrap or re-export it behind a canonical owner with explicit `DELETE_BY_PHASE_58` metadata. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:18]

**When to use:** Use this in Plan 57-01 and Plan 57-02 before changing approval API resume behavior. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:40]

**Implementation notes:** Current `graph.py` imports and registers `assess_risk_and_approval`; this must become a canonical `risk_gate` registration. [VERIFIED: src/agent/graph.py:23] [VERIFIED: src/agent/graph.py:281]

### Pattern 2: Route Values Equal Active Graph Node Keys

**What:** `route_after_claim_verify`, `route_after_approval`, and conditional edge path maps should all use the same canonical `risk_gate` string. [VERIFIED: src/agent/routing.py:534] [VERIFIED: src/agent/graph.py:347]

**When to use:** Use when converting the active graph cutover and architecture baseline tests. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:97]

**Implementation notes:** Current `_CLAIM_VERIFY_ROUTES` only allows `assess_risk_and_approval` and `final_response`, and `_route_after_claim_verify` returns the legacy value for verified action/risk paths. [VERIFIED: src/agent/routing.py:28] [VERIFIED: src/agent/routing.py:581]

### Pattern 3: Trusted Approval Resume Is Server-Constructed

**What:** Approval decisions enter the graph through the authenticated approval API/inbox path, not ordinary chat text. [VERIFIED: src/api/routers/approvals.py:55] The API builds `ApprovalDecisionCommand`, `ApprovalService` validates request/action/snapshot/version state, and the graph resumes with a server-constructed `TrustedApprovalResultV1`. [VERIFIED: src/approvals/service.py:194] [VERIFIED: src/approvals/schemas.py:198]

**When to use:** Use for Plan 57-03, especially edit rerisk and retry compatibility. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:30]

**Implementation notes:** Current edit decisions emit and return `resume_route="assess_risk_and_approval"`; Phase 57 should make new current-run edit resume route `risk_gate` and retain explicit compatibility for old persisted values. [VERIFIED: src/approvals/service.py:542] [VERIFIED: src/approvals/service.py:566]

### Pattern 4: Fail-Closed Binding Chain

**What:** Risk/action flow must fail closed when claim verification, evidence refs, action payload hash, safety snapshot ref/hash, policy/risk/retrieval versions, approval plan, or binding checks are missing or invalid. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:25]

**When to use:** Use for node migration tests and graph routing tests. [VERIFIED: tests/test_graph_routing.py:493]

**Implementation notes:** Current risk node clears proposed action, approval plan, auto binding, safety snapshot, and final response on blocked/fail-closed paths; these semantics must survive the rename. [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:250] [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:750]

### Anti-Patterns to Avoid

- **Dual active risk routes:** Do not accept both `risk_gate` and `assess_risk_and_approval` as normal current-run route values; historical compatibility must be separate and labeled. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:21]
- **Approval gate deciding risk:** Do not move deterministic risk lowering, action creation, snapshot creation, or approval-plan creation into `approval_gate`. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:31]
- **Chat approval parsing:** Do not parse ordinary user chat text into trusted approval results. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:36]
- **Historical trace rewrite by default:** Do not rewrite stored trace rows just to hide old names; use projection compatibility unless a separate migration decision is made. [VERIFIED: src/repositories/trace_repo.py:67]
- **Single giant plan:** Do not create one Phase 57 plan covering callable migration, graph cutover, approval API, frontend/eval, docs, and validation. [VERIFIED: AGENTS.md:55] [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:40]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Graph baseline inspection | Ad hoc grep-only graph parser | Existing AST/static helpers in `tests/architecture/graph_baseline.py` | Baseline tests already encode active nodes, target nodes, legacy map, route maps, and exact graph checks. [VERIFIED: tests/architecture/graph_baseline.py:138] |
| Approval trusted resume validation | Custom dict checks scattered across graph/API | `TrustedApprovalResultV1`, `ApprovalDecisionCommand`, and existing `ApprovalService` | The service already validates request state, actor, action payload hash, snapshot, versions, and pending status. [VERIFIED: src/approvals/service.py:194] |
| Risk/approval schema validation | New JSON validator | Existing Pydantic models in `src/approvals/schemas.py` | Current risk, approval request, decision, and trusted result schemas are already modeled and validated. [VERIFIED: src/approvals/schemas.py:32] |
| Risk rules | New policy engine | Existing `rules/risk_rules.yaml` plus `_deterministic_high_rule` | Existing rules are loaded from YAML and applied deterministically before binding. [VERIFIED: rules/risk_rules.yaml] [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:95] |
| Trace vocabulary compatibility | One-off API/frontend string replacements only | `src/agent/graph_vocabulary.py` projection and tests | The vocabulary layer already models runtime nodes vs compatibility aliases and target projections. [VERIFIED: src/agent/graph_vocabulary.py:55] |

**Key insight:** The complex part is not renaming a node; it is keeping risk/action authority, trusted approval resume, persisted historical compatibility, and current-run graph identity separate. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:24]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | `agent_steps.node_name` can store historical node names, and trace repository projection maps implementation names to target vocabulary. [VERIFIED: src/db/models.py:1178] [VERIFIED: src/repositories/trace_repo.py:67] | Do not bulk rewrite historical trace rows in Phase 57; update projection so old `assess_risk_and_approval` rows remain historical/compatibility while current runs emit `risk_gate`. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:21] |
| Stored data | `approval_events.metadata_json` can store `resume_route`, and API retry handling reads stored edit metadata requiring the legacy route today. [VERIFIED: src/db/models.py:1077] [VERIFIED: src/api/routers/approvals.py:570] | New events should store `risk_gate`; retry/compatibility code should accept or translate persisted legacy edit `resume_route` explicitly and mark it `DELETE_BY_PHASE_58`. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:33] |
| Live service config | The active graph object is retrieved from `request.app.state.agent_graph` during approval resume, so running app processes need restart/rebuild after code cutover. [VERIFIED: src/api/routers/approvals.py:281] | Add deployment/runtime verification that the active app graph contains `risk_gate`, not stale `assess_risk_and_approval`. [ASSUMED] |
| Live service config | No external UI/database-managed service config containing `assess_risk_and_approval`, `risk_gate`, or `approval_gate` was found in `data/`, `.env*`, Docker/Makefile, GitHub config, or `scripts/study`. [VERIFIED: `rg -n assess_risk_and_approval|risk_gate|approval_gate .env .env.* docker-compose.yml Dockerfile Makefile .github data scripts/study`] | None for external service config. [VERIFIED: same rg audit] |
| OS-registered state | `launchctl list` showed unrelated `com.moca.study.*` jobs and no Phase 57 graph key names. [VERIFIED: `launchctl list | rg 'MOCA|moca|assess_risk_and_approval|risk_gate|approval_gate'`] | None for OS-registered graph state. [VERIFIED: same launchctl audit] |
| Secrets/env vars | No `.env*` hit for `assess_risk_and_approval`, `risk_gate`, or `approval_gate`. [VERIFIED: `rg -n assess_risk_and_approval|risk_gate|approval_gate .env .env.*`] | No secret/env var rename required. [VERIFIED: same rg audit] |
| Build artifacts | `moca.egg-info/SOURCES.txt` lists `src/agent/nodes/assess_risk_and_approval.py` and `src/agent/nodes/approval_gate.py`. [VERIFIED: moca.egg-info/SOURCES.txt:53] | If Phase 57 adds `risk_gate.py` or changes package sources, refresh installed metadata with `uv sync` or editable reinstall and verify `moca.egg-info/SOURCES.txt` includes the canonical module. [ASSUMED] |

**Nothing found in category:** No runtime database was queried directly in this research; stored-data findings are model/schema-based and should be treated as code-verified surfaces rather than a live production data census. [VERIFIED: src/db/models.py:1077]

## Common Pitfalls

### Pitfall 1: Renaming the Node But Leaving Router Values Legacy

**What goes wrong:** `StateGraph.add_node("risk_gate", ...)` exists but routers still return `assess_risk_and_approval`, causing path-map misses or dual-route behavior. [VERIFIED: src/agent/routing.py:581]

**Why it happens:** Route returns, graph path maps, and architecture baseline fixtures are spread across `graph.py`, `routing.py`, and architecture tests. [VERIFIED: src/agent/graph.py:347] [VERIFIED: tests/architecture/graph_baseline.py:95]

**How to avoid:** Convert active node registration, claim verification path map, approval edit path map, `_CLAIM_VERIFY_ROUTES`, route assertions, and architecture baseline in one ordered plan. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:18]

**Warning signs:** Tests still assert `claim_verify -> assess_risk_and_approval` or `approval_gate -> assess_risk_and_approval`. [VERIFIED: tests/agent/test_graph.py:976] [VERIFIED: tests/agent/test_graph.py:1001]

### Pitfall 2: Moving Risk Authority Into `approval_gate`

**What goes wrong:** Approval edit or approve paths start creating/rerisking actions in `approval_gate`, blurring pending/trusted-resume lifecycle with deterministic risk policy. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:31]

**Why it happens:** Edit resume currently routes back to the risk node using `resume_route`, so it is tempting to make `approval_gate` decide the rerisk result. [VERIFIED: src/approvals/service.py:542]

**How to avoid:** Keep `approval_gate.py` as interrupt payload validation and trusted resume result validation only; use `risk_gate` for edited action rerisk. [VERIFIED: src/agent/nodes/approval_gate.py:26] [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:33]

**Warning signs:** `approval_gate.py` imports risk rules, action snapshot helpers, approval-plan builders, or `ApprovalService.decide`. [VERIFIED: src/agent/nodes/approval_gate.py:1]

### Pitfall 3: Treating Ordinary Chat Approval as Trusted

**What goes wrong:** A user says "approved" in chat and the graph treats it like an authenticated approval decision. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:36]

**Why it happens:** The same conceptual action "approve" appears in natural-language chat and authenticated approval command flows. [VERIFIED: src/agent/prompts.py:15]

**How to avoid:** Preserve safety-pre-route and intent-policy tests that keep ordinary approval-like wording unsupported/untrusted before `approval_gate`, `action_draft`, or trusted graph resume. [VERIFIED: tests/agent/test_nodes/test_safety_pre_route.py:103] [VERIFIED: tests/agent/test_graph.py:1116]

**Warning signs:** New tests make chat `approval_decision` enter `approval_gate` or inject `approval_result` directly without API/service construction. [VERIFIED: tests/agent/test_clarification_gate.py:68]

### Pitfall 4: Breaking Stored Edit Retry Compatibility

**What goes wrong:** New code only accepts `risk_gate`, and existing persisted edit events with `resume_route == "assess_risk_and_approval"` cannot be retried. [VERIFIED: src/api/routers/approvals.py:570]

**Why it happens:** The retry path reconstructs terminal decision results from stored event metadata and currently checks for the legacy route. [VERIFIED: src/api/routers/approvals.py:570]

**How to avoid:** Treat persisted legacy `resume_route` as historical compatibility, test it, and annotate it for Phase 58 deletion; new events should emit `risk_gate`. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:33]

**Warning signs:** `tests/test_approval_api.py` edit retry tests are simply deleted instead of rewritten for current/legacy behavior. [VERIFIED: tests/test_approval_api.py:916]

### Pitfall 5: Projection Closeout Misses UI/Eval Consumers

**What goes wrong:** Backend active graph is canonical, but SSE payload extraction, frontend timeline labels, eval scripts, or docs still display the legacy node as current. [VERIFIED: src/api/routers/agent_runs.py:1175] [VERIFIED: frontend/src/components/timeline/TimelineStep.tsx:5] [VERIFIED: scripts/eval_agent.py:60]

**Why it happens:** Current-run vocabulary is duplicated across API display labels, frontend timeline labels, eval patches, latency diagnostics, graph vocabulary, and docs. [VERIFIED: src/api/routers/agent_runs.py:56] [VERIFIED: scripts/diagnose_latency.py:112]

**How to avoid:** Assign a final closeout plan to update projection/API/frontend/eval/docs/debt after graph cutover tests pass. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:40]

**Warning signs:** `rg "assess_risk_and_approval"` still finds current-run display, eval runtime, or active baseline usage without a compatibility label. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-04-SUMMARY.md]

## Code Examples

Verified patterns from current sources and recommended Phase 57 adaptations:

### Active Graph Registration and Path Map

```python
# Recommended Phase 57 pattern; current source registers the legacy name. [VERIFIED: src/agent/graph.py:271]
workflow.add_node("risk_gate", risk_gate)
workflow.add_conditional_edges(
    "claim_verify",
    route_after_claim_verify,
    {
        "risk_gate": "risk_gate",
        "final_response": "final_response",
    },
)
workflow.add_conditional_edges(
    "approval_gate",
    route_after_approval,
    {
        "approval_gate": "approval_gate",
        "risk_gate": "risk_gate",
        "action_draft": "action_draft",
        "final_response": "final_response",
    },
)
```

The planner should verify this against actual `graph.py` edit locations, because current code maps claim verification and approval edit paths to `assess_risk_and_approval`. [VERIFIED: src/agent/graph.py:347] [VERIFIED: src/agent/graph.py:365]

### Claim Verification Route Value

```python
# Recommended Phase 57 pattern; current allowed set and return value are legacy. [VERIFIED: src/agent/routing.py:28]
_CLAIM_VERIFY_ROUTES = {"risk_gate", "final_response"}

if _claim_bundle_allows_action(claim_bundle) and (
    _has_verified_action_recommendation(state) or _recommendation_signals_risk(state)
):
    return "risk_gate"
```

The route should remain claim/evidence fail-closed and only enter risk when Phase 56 verified-action support is present. [VERIFIED: src/agent/routing.py:581] [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-03-SUMMARY.md]

### Approval Edit Resume Compatibility

```python
# Recommended Phase 57 constants; exact names are planner discretion. [ASSUMED]
CANONICAL_RISK_ROUTE = "risk_gate"
LEGACY_RISK_ROUTE = "assess_risk_and_approval"  # DELETE_BY_PHASE_58

def is_risk_reroute(route: str | None, *, historical: bool = False) -> bool:
    if route == CANONICAL_RISK_ROUTE:
        return True
    return historical and route == LEGACY_RISK_ROUTE
```

Current new edit decisions return `resume_route="assess_risk_and_approval"` and API resume checks the same value, so Plan 57-03 must convert new current-run values while keeping stored historical compatibility explicit. [VERIFIED: src/approvals/service.py:566] [VERIFIED: src/api/routers/approvals.py:756]

### Graph Vocabulary Projection

```python
# Recommended Phase 57 intent; current entry maps legacy -> risk_gate as compatibility alias. [VERIFIED: src/agent/graph_vocabulary.py:166]
GraphNodeContract(
    runtime_name="risk_gate",
    target_name="risk_gate",
    status=TargetGraphStatus.RUNTIME,
    runnable=True,
)
GraphNodeContract(
    runtime_name="assess_risk_and_approval",
    target_name="risk_gate",
    status=TargetGraphStatus.COMPATIBILITY_ALIAS,
    runnable=False,
    reason_codes=(
        "LEGACY_RISK_GATE_COMPATIBILITY_DELETE_BY_PHASE_58",
    ),
)
```

Planner should choose exact reason-code names, but it must preserve the distinction between current runtime and historical compatibility alias. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:21]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct active legacy node names stayed in graph registration and path maps | Each CAGM phase cuts one active node to canonical graph identity while preserving explicit compatibility | Phase 51-56 established baseline and prior cutover patterns; Phase 57 applies the same pattern to risk/approval. [VERIFIED: .planning/ROADMAP.md:39] [VERIFIED: .planning/ROADMAP.md:44] | Planner should use the Phase 56 graph cutover/projection/docs closeout pattern, not invent a one-off migration. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-02-SUMMARY.md] |
| `assess_risk_and_approval` active runtime route | `risk_gate` active runtime route, with legacy row only for compatibility until Phase 58 | Phase 57 target [VERIFIED: .planning/ROADMAP.md:45] | Active graph should no longer register legacy risk node after Phase 57. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:18] |
| Approval edit resume routes back to legacy risk node | New edit resume routes to `risk_gate`, old persisted route compatibility remains explicit | Phase 57 target [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:33] | Approval API/service tests must cover both new current route and stored legacy retry. [VERIFIED: src/api/routers/approvals.py:570] |

**Deprecated/outdated:**
- Active `StateGraph.add_node("assess_risk_and_approval", ...)` is outdated after Phase 57 and should become incompatible with active graph baseline tests. [VERIFIED: src/agent/graph.py:281]
- Current-run `route_after_claim_verify` return value `assess_risk_and_approval` is outdated after Phase 57 and should be rejected outside historical compatibility. [VERIFIED: src/agent/routing.py:581]
- Frontend/eval/API display treating `assess_risk_and_approval` as current runtime vocabulary is outdated after Phase 57. [VERIFIED: frontend/src/components/timeline/TimelineStep.tsx:5] [VERIFIED: scripts/eval_agent.py:60]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Creating a new `src/agent/nodes/risk_gate.py` is the cleanest canonical module structure; the planner may instead keep implementation in the old file behind a canonical export if compatibility metadata is explicit. [ASSUMED] | Recommended Project Structure | Low - user decisions allow exact module structure discretion. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:45] |
| A2 | Running app processes need restart/rebuild after graph cutover because `request.app.state.agent_graph` holds the active graph object. [ASSUMED] | Runtime State Inventory | Medium - if deployment hot-swaps app state differently, the plan should adapt the operational verification step. |
| A3 | Refreshing `moca.egg-info/SOURCES.txt` through `uv sync` or editable reinstall is sufficient if package source metadata changes. [ASSUMED] | Runtime State Inventory | Low - if project packaging differs, the planner can replace this with the actual packaging refresh command. |

## Open Questions

1. **Should Plan 57-01 create a new `risk_gate.py` file or keep a canonical export from the existing legacy module?**
   - What we know: User decisions leave exact module structure to planner discretion. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:45]
   - What's unclear: Whether the planner prefers minimal diff or clearer Phase 58 deletion. [ASSUMED]
   - Recommendation: Prefer a new `risk_gate.py` canonical owner and keep `assess_risk_and_approval.py` as a narrow import/compatibility shim if needed. [ASSUMED]

2. **Should historical DB rows be migrated?**
   - What we know: Stored `AgentStep.node_name` and approval event metadata can contain legacy values, and context allows historical compatibility until Phase 58. [VERIFIED: src/db/models.py:1178] [VERIFIED: src/db/models.py:1077] [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:33]
   - What's unclear: Whether a production data cleanup is desired before Phase 58. [ASSUMED]
   - Recommendation: Do not migrate historical rows in Phase 57; project old values through compatibility and delete remaining aliases in Phase 58. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:112]

3. **How much doc/spec editing belongs in Phase 57 versus Phase 58?**
   - What we know: Phase 57 should update current-source docs and closeout artifacts for the new active identity, while Phase 58 owns final no-debt cleanup. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:40]
   - What's unclear: The exact docs list may change if the planner finds additional `assess_risk_and_approval` hits. [ASSUMED]
   - Recommendation: Include docs that describe current runtime identity in Phase 57; leave explicit compatibility deletion and no-debt ledger closure to Phase 58. [VERIFIED: .planning/ROADMAP.md:45]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Approved test/runtime entrypoint | yes | 0.11.2 | `.venv/bin/...` only after confirming it belongs to this repo. [VERIFIED: AGENTS.md:24] |
| Python | Runtime/tests | yes | 3.12.13 | None needed. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run python --version`] |
| pytest | Validation | yes | 9.0.3 | None; use approved `uv run pytest` entrypoint. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --version`] |
| pytest-asyncio | Async graph/API tests | yes | 1.3.0 | None needed. [VERIFIED: `uv run python -c import importlib.metadata`] |
| ruff | Optional lint gate | yes | 0.15.12 | Skip lint only if planner keeps validation to tests. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run ruff --version`] |
| Docker | Optional DB/service support | yes | 29.4.2 | Use existing local test fixtures if DB-backed tests do not require Docker. [VERIFIED: `docker --version`] |
| `psql` CLI | Manual DB inspection only | no | - | Use SQLAlchemy/repository tests or Docker/postgres tooling if live DB inspection becomes necessary. [VERIFIED: `command -v psql`] |

**Missing dependencies with no fallback:**
- None for research/planning. [VERIFIED: environment probes above]

**Missing dependencies with fallback:**
- `psql` CLI is missing; Phase 57 can rely on repository/API tests unless live DB inspection is explicitly required. [VERIFIED: `command -v psql`]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 with pytest-asyncio 1.3.0 [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest --version`] |
| Config file | `pyproject.toml` pytest/ruff config [VERIFIED: pyproject.toml:50] |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py -q --tb=short` [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:19] |
| Full suite command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/architecture/test_phase34_approval_action_boundaries.py tests/architecture/test_approval_boundaries.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_nodes/test_assess_risk_and_approval.py tests/agent/test_phase22_action_boundary.py tests/test_approval_gate.py tests/test_approval_api.py tests/agent/test_graph_vocabulary.py tests/test_agent_runs_api.py -q --tb=short` [VERIFIED: current test files] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CAGM-08 | Active graph registers `risk_gate`, not `assess_risk_and_approval`; claim and approval edit path maps route `risk_gate`. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:18] | architecture/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py -q --tb=short` | yes, update required [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:19] |
| CAGM-08 | `risk_gate` preserves current risk/action fail-closed, snapshot binding, approval plan, and auto-allowed binding behavior. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:24] | unit/integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_nodes/test_assess_risk_and_approval.py tests/test_graph_routing.py tests/agent/test_phase22_action_boundary.py -q --tb=short` | yes, likely rename/add canonical test file [VERIFIED: tests/agent/test_nodes/test_assess_risk_and_approval.py:243] |
| CAGM-08 | Approval edit resume emits `risk_gate` for new current runs and keeps explicit legacy retry compatibility. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:33] | API/service | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_approval_api.py tests/test_approval_gate.py tests/test_graph_routing.py -q --tb=short` | yes, update required [VERIFIED: tests/test_approval_api.py:820] |
| CAGM-08 | Ordinary chat approval-like text stays unsupported/untrusted and cannot enter `approval_gate`, `action_draft`, or trusted graph resume. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:36] | safety/regression | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph.py tests/agent/test_nodes/test_safety_pre_route.py tests/agent/test_intent_routing.py tests/agent/test_clarification_gate.py -q --tb=short` | yes [VERIFIED: tests/agent/test_graph.py:1116] |
| CAGM-08 | Current-run vocabulary/API/frontend/eval surfaces use `risk_gate`, and legacy key appears only as compatibility/historical. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:28] | projection/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/test_agent_runs_api.py -q --tb=short` | yes [VERIFIED: tests/agent/test_graph_vocabulary.py:89] |

### Sampling Rate

- **Per task commit:** Run the narrow test command for the touched surface; all commands must use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`. [VERIFIED: AGENTS.md:24]
- **Per wave merge:** Run the quick command plus the plan-specific family above. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:40]
- **Phase gate:** Run the full suite command above and a static `rg "assess_risk_and_approval"` review classifying each remaining hit as historical compatibility, test fixture, or Phase 58 deletion. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:42]

### Wave 0 Gaps

- [ ] `tests/agent/test_nodes/test_risk_gate.py` - canonical node test module or renamed coverage for CAGM-08 current node identity. [ASSUMED]
- [ ] `tests/architecture/test_phase57_risk_gate_canonicalization.py` - optional focused static guard that rejects active current-run `assess_risk_and_approval` registration/routes after Phase 57. [ASSUMED]
- [ ] Update `tests/architecture/graph_baseline.py` current graph baseline so the sole remaining active legacy row for risk is removed and any retained alias is compatibility-only. [VERIFIED: tests/architecture/graph_baseline.py:51]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | Approval decisions enter through authenticated API dependency and server-side `ApprovalDecisionCommand`. [VERIFIED: src/api/routers/approvals.py:55] |
| V3 Session Management | partial | Graph resume uses server-side run/config context rather than trusting client-supplied graph state. [VERIFIED: src/api/routers/approvals.py:281] |
| V4 Access Control | yes | Approval service checks request/action binding, actor identity, pending status, versions, and policy assignment before deciding. [VERIFIED: src/approvals/service.py:194] |
| V5 Input Validation | yes | Use Pydantic schemas for risk decisions, approval commands, approval results, and trusted resume payloads. [VERIFIED: src/approvals/schemas.py:32] |
| V6 Cryptography | yes | Do not hand-roll hashing; preserve existing action payload hash and safety snapshot hash verification surfaces. [VERIFIED: src/agent/nodes/action_draft.py:237] |

### Known Threat Patterns for Risk/Approval Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Chat spoofing approval | Spoofing/Elevation of privilege | Ordinary approval-like chat stays unsupported/untrusted; only authenticated API/inbox path constructs `TrustedApprovalResultV1`. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:36] |
| Resume payload tampering | Tampering | Validate tenant/run/approval id, payload hash, snapshot ref/hash, and config versions before graph resume/action draft. [VERIFIED: src/agent/graph.py:246] [VERIFIED: src/agent/nodes/action_draft.py:237] |
| Approval edit bypasses rerisk | Elevation of privilege | Trusted edit resume must route to `risk_gate`, not directly to `action_draft`. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:33] |
| Missing evidence enters action path | Tampering | Claim verification/evidence/action binding gaps fail closed before approval/action. [VERIFIED: src/agent/nodes/assess_risk_and_approval.py:159] |
| Stale compatibility alias becomes current authority | Repudiation/Tampering | Label legacy route handling historical-only and `DELETE_BY_PHASE_58`; architecture tests should reject active legacy registration. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:21] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md` - locked user decisions, phase boundary, integration points, and deferred scope. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:1]
- `.planning/REQUIREMENTS.md` - CAGM-08 requirement and Phase 57 pending status. [VERIFIED: .planning/REQUIREMENTS.md:60]
- `.planning/ROADMAP.md` - Phase 57 roadmap entry and Phase 51-58 dependency context. [VERIFIED: .planning/ROADMAP.md:45]
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` - canonical graph migration charter, target nodes, compatibility policy, validation matrix. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md]
- `.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-02-SUMMARY.md`, `56-03-SUMMARY.md`, `56-04-SUMMARY.md` - prior cutover, claim/risk route handoff, and projection/docs closeout pattern. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-02-SUMMARY.md]
- `src/agent/graph.py`, `src/agent/routing.py`, `src/agent/nodes/assess_risk_and_approval.py`, `src/agent/nodes/approval_gate.py` - current active graph/routing/node surfaces. [VERIFIED: src/agent/graph.py:271]
- `src/approvals/service.py`, `src/approvals/schemas.py`, `src/api/routers/approvals.py`, `src/api/routers/agent_runs.py` - approval service/API/trusted resume/display surfaces. [VERIFIED: src/approvals/service.py:66]
- `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`, `tests/agent/test_graph.py`, `tests/test_graph_routing.py`, `tests/test_approval_api.py`, `tests/test_approval_gate.py` - validation surfaces. [VERIFIED: tests/architecture/graph_baseline.py:11]
- `AGENTS.md` and `CLAUDE.md` - MOCA project workflow, test entrypoint, plan granularity, debt/local validation logging rules. [VERIFIED: AGENTS.md:24] [VERIFIED: CLAUDE.md:5]

### Secondary (MEDIUM confidence)

- Installed package metadata via `uv run python -c import importlib.metadata` for versions. [VERIFIED: local environment command]
- Runtime state grep audits over `.env*`, Docker/Makefile/GitHub config, `data/`, `scripts/study`, `moca.egg-info`, and `.pytest_cache`. [VERIFIED: local rg commands]

### Tertiary (LOW confidence)

- Assumptions A1-A3 above: module structure preference, process restart operational detail, and packaging metadata refresh command. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from `pyproject.toml`, imports, and installed environment metadata. [VERIFIED: pyproject.toml:5]
- Architecture: HIGH - verified from phase context, canonical migration spec, current graph/node/API code, and prior Phase 56 summaries. [VERIFIED: .planning/phases/57-risk-gate-and-approval-gate-canonicalization/57-CONTEXT.md:78]
- Pitfalls: HIGH - each pitfall maps to a current code/test surface or locked decision. [VERIFIED: src/agent/graph.py:347]
- Runtime state: MEDIUM - code schemas and local config/artifact greps were verified, but no live production database census was performed. [VERIFIED: src/db/models.py:1077]
- Security: HIGH - trusted approval and ordinary chat boundaries are source/test-backed. [VERIFIED: src/api/routers/approvals.py:55] [VERIFIED: tests/agent/test_graph.py:1116]

**Research date:** 2026-07-07 [VERIFIED: system date]
**Valid until:** 2026-07-14 for active implementation surfaces, because Phase 57/58 graph migration code is fast-moving. [ASSUMED]
