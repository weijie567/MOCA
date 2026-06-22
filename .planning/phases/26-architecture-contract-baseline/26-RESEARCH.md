<!-- markdownlint-disable MD013 -->

# Phase 26: Architecture Contract Baseline - Research

**Researched:** 2026-06-22
**Domain:** Architecture/spec/eval contract baseline for MOCA v1.9 Agent Platform Foundation
**Confidence:** HIGH

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions [VERIFIED: .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md]

#### Architecture Direction

- MOCA should use a microservice-ready modular monolith: boundaries should be clear enough to split later, but physical microservice deployment is not part of v1.9.
- Full real external execution remains deferred. v1.9 hardens action draft, approval, evidence, claim verification, and safety snapshot boundaries only.
- `docs/contract-spec.md` remains the normative contract source. `docs/target-agent-platform-architecture-plan.md` records target architecture and rationale, but any executable contract must either already exist in `contract-spec.md` or be explicitly synchronized there.
- Phase 26 should not treat current implementation compromises as normative truth. If implementation and spec differ, the phase should record whether the spec is wrong or the implementation is intentionally partial/MVP.

#### Phase 26 Deliverables

- Confirm `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, and `docs/eval-test-plan.md` agree on target graph vocabulary, AgentState fields, RAG context build, claim verification, tool policy decisions, business fact result contracts, decision events, approval/action boundary, and eval gate levels.
- Make module ownership actionable: for each platform/domain service, define owned schemas/tables/events, public methods, allowed downstream dependencies, and forbidden imports or access patterns.
- Preserve legacy alias mappings where needed, especially graph node/router vocabulary migration from old names to target names.
- Make future implementation order executable without requiring physical microservices or full real execution.
- Record any remaining spec delta, MVP scope note, or deferred item with a named target phase. Do not use vague "later" wording.

#### GSD Metadata Decision

- `gsd-sdk query init.new-milestone`, `state.load`, `roadmap.analyze`, and `init.plan-phase 26` now read v1.9 correctly after ROADMAP/MILESTONES format repair.
- `gsd-sdk query validate.health` still reports non-blocking warnings because old completed Phase 24/24.x/25 directories remain in `.planning/phases` and future Phase 26-35 directories are not all present.
- Do not use `phases.clear --confirm`; it deletes instead of archiving.
- Old phase directory archival is captured as a separate pending cleanup todo and should not block Phase 26 planning.

### Claude's Discretion

None present in `26-CONTEXT.md`; planning discretion should stay within the locked docs/spec/eval baseline boundary. [VERIFIED: .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md]

### Deferred Ideas (OUT OF SCOPE) [VERIFIED: .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md]

- Archive old completed Phase 24/24.x/25 directories into milestone-specific phase archives after Phase 26 planning is stable.
- Physical microservice extraction is a deployment decision after the modular monolith boundaries are proven.
- Full real external action execution remains deferred beyond v1.9.
</user_constraints>

## Project Constraints (from CLAUDE.md and AGENTS.md)

- Debug/startup/validation/UI/API/RAG/agent/memory/tool-call issues found during MOCA local work must be appended to `.planning/LOCAL-VALIDATION-ISSUES.md` after handling, with symptom, reproduction, evidence, root cause/current judgment, handling, residual issue, and next entry point. [VERIFIED: CLAUDE.md; AGENTS.md]
- Phase-level planning and larger changes use the project cross-review workflow: GSD-native review first, then independent Codex cross-check, and all review findings must be verified against repository code/docs/tests before acceptance. [VERIFIED: CLAUDE.md; AGENTS.md]
- Small fixes skip the cross-review workflow, but Phase 26 is explicitly phase-level planning, so the workflow applies to the later PLAN.md review. [VERIFIED: AGENTS.md; .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md]
- `docs/contract-spec.md` is the only normative contract source; it defines contract semantics, while phase implementation details and scope remain phase decisions. [VERIFIED: CLAUDE.md; AGENTS.md; docs/contract-spec.md]
- If phase implementation and spec diverge, the divergence must be recorded as either a spec correction or an intentional MVP/partial implementation note, not silently accepted. [VERIFIED: CLAUDE.md; AGENTS.md]
- Deferred items must name a target phase such as `post-Phase 17`; vague "later" wording is forbidden. [VERIFIED: CLAUDE.md; AGENTS.md]

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
| --- | --- | --- |
| APF-01 | The target architecture plan, `contract-spec.md`, and eval plan define the same target graph vocabulary, service boundaries, AgentState RAG/claim fields, tool policy decisions, business fact results, and decision event foundation. | Use the APF-01 alignment matrix pattern below to verify `docs/contract-spec.md` as normative source, `docs/target-agent-platform-architecture-plan.md` as target/rationale, and `docs/eval-test-plan.md` as gate matrix. [VERIFIED: .planning/REQUIREMENTS.md; docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md; docs/eval-test-plan.md] |
| APF-02 | Each platform/domain module has explicit ownership over schemas, repositories/adapters, public methods, downstream dependencies, forbidden imports, and decision events. | Use the APF-02 ownership expansion pattern below, starting from the architecture plan module matrix and syncing executable contracts back to `docs/contract-spec.md` when needed. [VERIFIED: .planning/REQUIREMENTS.md; docs/target-agent-platform-architecture-plan.md; docs/contract-spec.md] |

</phase_requirements>

## Summary

Phase 26 is a docs/spec/eval baseline phase, not a runtime implementation phase: its job is to make APF-01 and APF-02 executable for later phases by aligning `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, and `docs/eval-test-plan.md`. [VERIFIED: .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md; .planning/ROADMAP.md; .planning/REQUIREMENTS.md]

The primary planning risk is contract drift: the architecture plan contains target shapes and rationale, but `docs/contract-spec.md` is the only normative contract source, and any executable schema, node, router, AgentState field, tool decision, business fact result, or decision event must either already exist there or be explicitly synchronized there. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md; CLAUDE.md]

The planner should create focused documentation tasks: an APF-01 cross-document alignment pass, an APF-02 module ownership pass, a legacy alias/deferred-delta pass, and a validation/review pass that proves no runtime code or deployment scope was introduced. [VERIFIED: .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md; .planning/ROADMAP.md; AGENTS.md]

**Primary recommendation:** Plan one docs-only contract baseline that updates or verifies the three canonical docs, adds an explicit ownership/alignment verification artifact if useful, and gates acceptance on APF-01/APF-02 coverage plus GSD/Markdown checks. [VERIFIED: .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md; .planning/config.json]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
| --- | --- | --- | --- |
| APF-01 cross-document baseline | Documentation / Contract | API / Backend contracts | Phase 26 owns docs/spec/eval alignment before implementation; backend contracts are described, not implemented. [VERIFIED: .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md; .planning/ROADMAP.md] |
| Target graph vocabulary and legacy aliases | Documentation / Contract | API / Backend graph runtime | The canonical registered node/router set and legacy alias mapping live in `contract-spec.md` Section 9; later graph implementation phases consume them. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| AgentState RAG/claim fields | Documentation / Contract | API / Backend AgentState | The canonical field registry and writer boundaries live in `contract-spec.md` Section 10; Phase 26 should align docs, not add fields to code. [VERIFIED: docs/contract-spec.md; .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md] |
| Tool policy decisions | Documentation / Contract | API / Backend ToolPlatform | `ToolView`, `ToolPolicyDecision`, `ToolCatalog`, and `UnifiedToolManager` are normative in `contract-spec.md` Section 12.6, while later phases implement them. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| Business fact results | Documentation / Contract | API / Backend domain services | `BusinessFactResultV1`, `BusinessContextV1`, and `BusinessFactRefV1` are normative contracts for future BusinessFactService/domain reads. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| RAG context build and claim verification | Documentation / Contract | API / Backend KnowledgeService | Candidate retrieval, verified evidence package construction, and claim verification are separated in the normative RAG/claim contracts. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| Decision event foundation and eval gates | Documentation / Contract | API / Backend Observability/Replay | `DecisionEventEnvelopeV1` uses the minimal event envelope, and eval gate levels are documented in the eval plan for later phases. [VERIFIED: docs/contract-spec.md; docs/eval-test-plan.md] |
| Physical deployment | Out of scope | Deployment / Operations | Physical microservice extraction is explicitly deferred beyond v1.9. [VERIFIED: .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md; .planning/REQUIREMENTS.md] |
| Full real external execution | Out of scope | External integrations | Full real execution with outbox/reconciliation/compensation is explicitly deferred; v1.9 preserves action draft and approval boundaries only. [VERIFIED: .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md; .planning/REQUIREMENTS.md] |

## Standard Stack

### Core

| Library / Tool | Version | Purpose | Why Standard |
| --- | --- | --- | --- |
| Markdown docs in `docs/` and `.planning/` | n/a | Normative architecture/spec/eval baseline | Phase 26 deliverables are document and verification artifacts, not runtime code. [VERIFIED: .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md] |
| `docs/contract-spec.md` | n/a | Normative contract source | This file declares itself the only normative MOCA agent architecture contract source, and project rules reinforce that boundary. [VERIFIED: docs/contract-spec.md; CLAUDE.md; AGENTS.md] |
| `gsd-sdk` | v0.1.0 | Phase metadata and GSD health checks | `init.phase-op 26`, `roadmap.get-phase 26`, and `validate.health` are available and returned Phase 26 context. [VERIFIED: command output `gsd-sdk --version`; `gsd-sdk query init.phase-op 26`; `gsd-sdk query roadmap.get-phase 26`; `gsd-sdk query validate.health`] |
| `rg` | available at `/opt/homebrew/bin/rg` | Contract drift and source lookup | Project rules prefer `rg`/grep for verification, and `rg` is installed. [VERIFIED: AGENTS.md; command output `command -v rg`] |

### Supporting

| Library / Tool | Version | Purpose | When to Use |
| --- | --- | --- | --- |
| `markdownlint-cli2` | v0.22.1, markdownlint v0.40.0 | Markdown formatting gate | Use through `npx --yes markdownlint-cli2` on touched docs if the plan edits Markdown. [VERIFIED: command output `npx --yes markdownlint-cli2 --version`] |
| `pytest` | 8.4.2 | Existing Python contract test framework | Use only if a planner explicitly justifies code-level helpers/tests; docs-only Phase 26 should not require runtime tests. [VERIFIED: command output `pytest --version`; pyproject.toml; .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md] |
| Python | 3.13.3 installed, project requires `>=3.12` | Existing backend runtime/test environment | Use for existing test commands only if code or test files are touched. [VERIFIED: command output `python3 --version`; pyproject.toml] |
| Node/npm/npx | Node v25.9.0, npm 11.12.1 | Markdown lint and frontend tooling host | Use for `npx` docs checks; frontend build/test is out of scope unless Phase 26 adds UI work, which it should not. [VERIFIED: command output `node --version`; `npm --version`; frontend/package.json; .planning/phases/26-architecture-contract-baseline/26-CONTEXT.md] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
| --- | --- | --- |
| `contract-spec.md` as normative source | Architecture plan as executable source | Rejected by locked decisions and spec header; architecture plan is target/rationale and proposed delta unless synchronized. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md; 26-CONTEXT.md] |
| Modular monolith baseline | Physical microservices | Rejected for v1.9; deployment split is deferred until boundaries are proven. [VERIFIED: 26-CONTEXT.md; .planning/REQUIREMENTS.md] |
| Docs-only baseline | Runtime code implementation | Rejected for Phase 26; implementation phases start after the baseline. [VERIFIED: 26-CONTEXT.md; .planning/ROADMAP.md] |
| Real external action execution | Action draft/approval/safety boundary hardening | Real execution is deferred; Phase 26 should preserve no-real-execution scope. [VERIFIED: 26-CONTEXT.md; .planning/REQUIREMENTS.md] |

**Installation:**

No persistent dependency install is recommended for Phase 26. Use existing tools and `npx --yes markdownlint-cli2` for an on-demand Markdown lint check. [VERIFIED: pyproject.toml; frontend/package.json; command output `npx --yes markdownlint-cli2 --version`]

**Version verification:**

```bash
gsd-sdk --version
pytest --version
python3 --version
node --version
npm --version
npx --yes markdownlint-cli2 --version
```

These commands were run during research; no `npm view` package version verification is needed because the recommendation does not add any persistent npm package. [VERIFIED: command outputs listed in Sources]

## Architecture Patterns

### System Architecture Diagram

```text
Phase 26 inputs
  -> CONTEXT locked decisions
  -> APF-01/APF-02 requirements
  -> ROADMAP success criteria
  -> contract-spec normative contracts
  -> target architecture rationale
  -> eval gate matrix
  -> local validation caveats

Contract baseline process
  -> APF-01 alignment matrix
       -> graph vocabulary and aliases
       -> AgentState RAG/claim fields
       -> ToolPolicyDecision and ToolView
       -> BusinessFactResultV1 / BusinessFactRefV1
       -> DecisionEventEnvelopeV1
       -> approval/action no-real-execution boundary
       -> eval gate levels
  -> APF-02 ownership matrix
       -> owned schemas/tables/events
       -> public methods
       -> allowed downstream dependencies
       -> forbidden imports/access patterns
       -> decision events
  -> delta decisions
       -> sync executable contract into contract-spec
       -> record MVP scope or named deferred phase
       -> preserve legacy aliases

Phase 26 outputs
  -> updated docs and/or phase verification artifact
  -> no runtime code changes unless explicitly justified
  -> later phases 27-35 can plan implementation in dependency order
```

This diagram models Phase 26 data flow through planning artifacts, not runtime request flow, because the phase is locked as a planning/docs/spec baseline. [VERIFIED: 26-CONTEXT.md; .planning/ROADMAP.md]

### Recommended Project Structure

```text
.planning/phases/26-architecture-contract-baseline/
├── 26-CONTEXT.md              # Locked phase decisions already present
├── 26-RESEARCH.md             # This research output
├── 26-01-PLAN.md              # Planner output should be docs-only
└── 26-BASELINE-CHECKLIST.md   # Optional verification artifact if PLAN.md needs a concrete alignment matrix

docs/
├── contract-spec.md                           # Normative contract source
├── target-agent-platform-architecture-plan.md # Target architecture and rationale
└── eval-test-plan.md                          # Eval gate levels, matrix, golden cases
```

The optional checklist is a planning recommendation; if the planner can encode the matrix directly in existing docs and PLAN.md acceptance checks, a separate file is not required. [VERIFIED: 26-CONTEXT.md; docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md; docs/eval-test-plan.md]

### Pattern 1: Normative Contract First

**What:** Treat `docs/contract-spec.md` as the write target for executable cross-module contracts, and treat architecture/eval docs as target rationale or gate guidance unless their content is synchronized into the spec. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md; CLAUDE.md]

**When to use:** Use this pattern for graph vocabulary, AgentState fields, RAG/claim bundles, tool policy decisions, business fact refs/results, and decision event envelopes. [VERIFIED: docs/contract-spec.md]

**Example:**

```markdown
| Contract item | contract-spec.md status | architecture plan status | eval-test-plan status | Phase 26 action |
| --- | --- | --- | --- | --- |
| `ToolPolicyDecision` | Normative in Section 12.6 | Target/rationale in Section 10.6 | Gate row covers visibility/runtime auth | Verify names/enums match; sync only if drift is found |
```

Source: `docs/contract-spec.md` Sections 0.1 and 12.6, `docs/target-agent-platform-architecture-plan.md` Section 10.6, `docs/eval-test-plan.md` Section 20.1. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md; docs/eval-test-plan.md]

### Pattern 2: Ownership Matrix Expansion

**What:** Expand each platform/domain module from the architecture plan into concrete ownership of schemas/tables/events, public methods, allowed downstream dependencies, forbidden imports/access patterns, and decision event obligations. [VERIFIED: .planning/REQUIREMENTS.md; docs/target-agent-platform-architecture-plan.md]

**When to use:** Use this for `RunOrchestrator`, `TrustedContextFactory`, `IntentService`, `MemoryContextService`, `ToolPlatform`, `KnowledgeService`, `BusinessFactService`, `ApprovalService`, `ActionDraftService / ExecutionBoundary`, and `Observability / Replay`. [VERIFIED: docs/target-agent-platform-architecture-plan.md]

**Example:**

```markdown
| Module | Owns schemas/tables/events | Public methods | Allowed dependencies | Forbidden imports/access | Decision events |
| --- | --- | --- | --- | --- | --- |
| `BusinessFactService` | `BusinessFactResultV1`, `BusinessFactRefV1`, domain read adapters | `get_order`, `get_refund_case`, `get_ticket`, `fetch_context` | owned business repositories/adapters, ToolPlatform dispatch boundary | graph node direct repository reads; memory/RAG/LLM substituted facts | business fact read decision and safe error events |
```

Source: APF-02, architecture plan Section 5.2, contract spec Sections 8.4 and 12.5. [VERIFIED: .planning/REQUIREMENTS.md; docs/target-agent-platform-architecture-plan.md; docs/contract-spec.md]

### Pattern 3: Legacy Alias Registry

**What:** Preserve explicit target-to-legacy mappings for graph node/router vocabulary until the implementation migration lands, and forbid semantic drift under alias names. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]

**When to use:** Use this when checking `intent_classification -> contextual_intent_resolve`, `session_memory_load -> session_context_load`, `long_term_memory_retrieve -> memory_context_load`, `route_after_intent -> route_after_contextual_intent`, and `route_after_slots -> route_after_slot_resolution`. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]

**Example:**

```markdown
| Target canonical name | Legacy alias | Allowed until | Constraint |
| --- | --- | --- | --- |
| `session_context_load` | `session_memory_load` | Phase 32 graph migration | Trace/eval projection must map to target name and must not widen semantics |
```

Source: `docs/contract-spec.md` Section 9.0 and architecture plan Section 3.1. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]

### Pattern 4: Eval Gate Classification

**What:** Classify each future platform contract as dev-contract, release, or monitoring gate, and do not claim production-grade capability from small docs checks or unit tests alone. [VERIFIED: docs/eval-test-plan.md; docs/target-agent-platform-architecture-plan.md]

**When to use:** Use this for all APF-01/APF-02 alignment work that touches security, permissions, evidence, approval, action, replay, or eval claims. [VERIFIED: docs/eval-test-plan.md; .planning/REQUIREMENTS.md]

**Example:**

```markdown
| Contract | Gate level | Phase 26 baseline decision |
| --- | --- | --- |
| `ToolPolicyDecision` visibility/runtime auth | Dev-contract before phase merge | Later ToolPlatform phase must test visible/hidden/allowed/denied with reason codes |
| High-risk action-bound calibration | Release before production path | Keep guarded/MVP if statistical gate is not demonstrated |
```

Source: `docs/eval-test-plan.md` Sections 20.0 and 20.1. [VERIFIED: docs/eval-test-plan.md]

### Anti-Patterns to Avoid

- **Architecture plan as normative source:** It contradicts the contract-spec authority rule; sync executable deltas into `contract-spec.md` instead. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]
- **Runtime implementation in Phase 26:** It violates the locked phase boundary and will blur later Phase 27-35 ownership. [VERIFIED: 26-CONTEXT.md; .planning/ROADMAP.md]
- **Physical microservice tasks:** They violate the v1.9 modular monolith decision. [VERIFIED: 26-CONTEXT.md; .planning/REQUIREMENTS.md]
- **Full real external execution tasks:** They violate the deferred execution decision; keep action draft and approval boundaries only. [VERIFIED: 26-CONTEXT.md; .planning/REQUIREMENTS.md]
- **New field/node/schema without spec delta:** The spec delta rule explicitly forbids silent widening or renaming of executable contracts. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]
- **Using current implementation compromise as truth:** Project rules require recording whether the spec is wrong or implementation is intentionally MVP/partial. [VERIFIED: CLAUDE.md; AGENTS.md; 26-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
| --- | --- | --- | --- |
| Contract authority | A parallel "architecture contract" outside `contract-spec.md` | Amend or map to `docs/contract-spec.md` | The spec is the only normative source; parallel docs create drift. [VERIFIED: docs/contract-spec.md; CLAUDE.md] |
| Module boundaries | Informal service boxes without owned schemas/events/import rules | APF-02 ownership matrix | APF-02 requires explicit ownership of schemas, repositories/adapters, public methods, downstream dependencies, forbidden imports, and decision events. [VERIFIED: .planning/REQUIREMENTS.md] |
| Graph migration | Ad hoc rename of nodes/routers | Legacy alias registry | Contract spec already defines canonical node/router vocabulary and legacy aliases. [VERIFIED: docs/contract-spec.md] |
| Tool policy | Boolean allowlist scattered across manager/node/prompt | `ToolCatalog`, `ToolView`, `ToolPolicyDecision`, `UnifiedToolManager` contract | The normative contract separates planner visibility from runtime authorization. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| Business facts | Tool summaries, memory, RAG, or LLM inference as current facts | `BusinessFactResultV1` / `BusinessFactRefV1` through BusinessFactService/domain public methods | Contract spec forbids using RAG evidence or memory to prove current order/refund/ticket facts. [VERIFIED: docs/contract-spec.md] |
| RAG evidence | Candidate retrieval refs directly in prompt/action path | `VerifiedEvidencePackageV1` plus `ClaimVerificationBundleV1` | Candidate refs, verified packages, and claim support are distinct contracts. [VERIFIED: docs/contract-spec.md] |
| Decision/replay foundation | Service-specific event envelopes | `DecisionEventEnvelopeV1` backed by `minimal_event_envelope.v1` | Contract spec forbids parallel event envelopes and requires unified sequence/redaction rules. [VERIFIED: docs/contract-spec.md] |
| GSD archive cleanup | `phases.clear --confirm` or cleanup inside Phase 26 | Separate cleanup todo after Phase 26 planning is stable | Context says `phases.clear --confirm` deletes instead of archiving and old archive cleanup must not block Phase 26. [VERIFIED: 26-CONTEXT.md; .planning/STATE.md] |

**Key insight:** Phase 26 should hand later phases stable contracts and ownership gates, not build temporary runtime implementations that later need to be reclassified or unwound. [VERIFIED: 26-CONTEXT.md; .planning/ROADMAP.md; docs/target-agent-platform-architecture-plan.md]

## Runtime State Inventory

Scope classification: Phase 26 mentions legacy graph vocabulary migration, but the locked boundary is docs/spec/eval baseline only, so no runtime migration, datastore rewrite, service config update, OS registration update, or package reinstall should be planned for this phase. [VERIFIED: 26-CONTEXT.md; .planning/ROADMAP.md]

| Category | Items Found | Action Required |
| --- | --- | --- |
| Stored data | None in Phase 26 scope; this research did not identify any datastore record that Phase 26 must mutate because runtime implementation is out of scope. [VERIFIED: 26-CONTEXT.md] | None; if a later implementation phase changes stored node names or event names, that phase must perform its own runtime inventory. [VERIFIED: 26-CONTEXT.md; docs/contract-spec.md] |
| Live service config | None in Phase 26 scope; no external service configuration changes are part of the locked deliverables. [VERIFIED: 26-CONTEXT.md] | None. [VERIFIED: 26-CONTEXT.md] |
| OS-registered state | None in Phase 26 scope; no OS task/service registration changes are part of the locked deliverables. [VERIFIED: 26-CONTEXT.md] | None. [VERIFIED: 26-CONTEXT.md] |
| Secrets/env vars | None in Phase 26 scope; no secret or environment variable rename is part of APF-01/APF-02. [VERIFIED: .planning/REQUIREMENTS.md; 26-CONTEXT.md] | None. [VERIFIED: 26-CONTEXT.md] |
| Build artifacts | None in Phase 26 scope; the phase should not change package names or runtime code artifacts. [VERIFIED: 26-CONTEXT.md] | None. [VERIFIED: 26-CONTEXT.md] |

**Nothing found in category:** Each category above is explicitly out of scope for Phase 26 because the phase is documentation/spec/eval baseline work. [VERIFIED: 26-CONTEXT.md]

## Common Pitfalls

### Pitfall 1: Treating `target-agent-platform-architecture-plan.md` as Executable Contract

**What goes wrong:** A later plan updates architecture rationale but leaves `contract-spec.md` unchanged, creating a contract that implementation phases cannot rely on. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]

**Why it happens:** The architecture plan contains detailed target shapes, but its header says conflicting executable content must be synchronized into the spec. [VERIFIED: docs/target-agent-platform-architecture-plan.md]

**How to avoid:** Every APF-01 task should identify the normative location in `contract-spec.md` or explicitly add a spec delta/MVP note. [VERIFIED: docs/contract-spec.md; 26-CONTEXT.md]

**Warning signs:** PLAN.md acceptance criteria say "architecture plan updated" without a matching "contract-spec verified or updated" check. [VERIFIED: docs/contract-spec.md; 26-CONTEXT.md]

### Pitfall 2: Letting Phase 26 Become Runtime Implementation

**What goes wrong:** The plan adds code tasks for services, graph nodes, external execution, or microservice deployment, stealing scope from Phases 27-35. [VERIFIED: .planning/ROADMAP.md; 26-CONTEXT.md]

**Why it happens:** The baseline docs describe target runtime architecture in depth. [VERIFIED: docs/target-agent-platform-architecture-plan.md]

**How to avoid:** Use "verify/update docs and acceptance gates" tasks, and add a final review check that no code files changed unless explicitly justified. [VERIFIED: 26-CONTEXT.md]

**Warning signs:** PLAN.md includes migrations, service classes, graph rewiring, adapters, Docker/Kubernetes, outbox workers, or external action dispatch. [VERIFIED: 26-CONTEXT.md; .planning/REQUIREMENTS.md]

### Pitfall 3: Missing Legacy Alias Coverage

**What goes wrong:** Later implementation phases rename graph nodes or routers without preserving trace/eval/replay mappings. [VERIFIED: docs/contract-spec.md; 26-CONTEXT.md]

**Why it happens:** Target canonical vocabulary and current implementation names can coexist until graph migration finishes. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]

**How to avoid:** Require a legacy alias table for each target node/router with old name, target name, allowed duration/target phase, and non-drift constraint. [VERIFIED: docs/contract-spec.md; 26-CONTEXT.md]

**Warning signs:** New names appear in one doc but not the other, or target aliases are described as implementation facts rather than migration mappings. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]

### Pitfall 4: Confusing Business Facts With Policy Evidence

**What goes wrong:** A baseline task lets `EvidenceRefV1`, RAG, memory, or LLM inference satisfy current order/refund/ticket fact requirements. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md]

**Why it happens:** Tool results, business fact refs, RAG evidence refs, and claim verifier outputs all appear in the same agent flow. [VERIFIED: docs/contract-spec.md]

**How to avoid:** Keep `BusinessFactResultV1` / `BusinessFactRefV1` separate from `EvidenceRefV1`, and require claim verification to cite the correct reference type. [VERIFIED: docs/contract-spec.md]

**Warning signs:** Documentation says "RAG/memory proves the order/refund/ticket fact" or "business fact ref satisfies policy evidence." [VERIFIED: docs/contract-spec.md]

### Pitfall 5: Blurring Eval Gate Levels

**What goes wrong:** A future phase claims production readiness from dev-contract checks, or blocks all development on release/monitoring thresholds. [VERIFIED: docs/eval-test-plan.md]

**Why it happens:** The eval plan intentionally defines dev-contract, release, and monitoring gates for different stages. [VERIFIED: docs/eval-test-plan.md]

**How to avoid:** Phase 26 should align each boundary to a gate level and leave statistical release gates for phases that claim production/high-risk capability. [VERIFIED: docs/eval-test-plan.md; docs/target-agent-platform-architecture-plan.md]

**Warning signs:** PLAN.md acceptance criteria use generic "eval passes" language without specifying gate level. [VERIFIED: docs/eval-test-plan.md]

### Pitfall 6: Treating GSD `validate.health` Warnings as Phase 26 Blockers

**What goes wrong:** The planner spends Phase 26 archiving old Phase 24/25 directories or creating all future phase directories. [VERIFIED: 26-CONTEXT.md; .planning/LOCAL-VALIDATION-ISSUES.md]

**Why it happens:** `validate.health` currently returns degraded status with non-blocking W002/W006 warnings. [VERIFIED: command output `gsd-sdk query validate.health`; .planning/LOCAL-VALIDATION-ISSUES.md]

**How to avoid:** Record the warnings in validation notes, but keep cleanup as a separate todo. [VERIFIED: 26-CONTEXT.md; .planning/STATE.md]

**Warning signs:** PLAN.md includes `phases.clear --confirm`, archive cleanup, or future directory creation as a prerequisite for APF-01/APF-02. [VERIFIED: 26-CONTEXT.md]

## Code Examples

Verified planning patterns from local sources:

### APF-01 Alignment Matrix

```markdown
| Contract Area | contract-spec.md | architecture plan | eval-test-plan | Drift? | Phase 26 action |
| --- | --- | --- | --- | --- | --- |
| Graph vocabulary and legacy aliases | Section 9.0-9.5 | Sections 3.1 and 6 | Node/router rows in Section 20.1 | no/yes | verify or sync spec |
| AgentState RAG/claim fields | Section 10 | Sections 11.8-11.10 | RAG/claim rows in Section 20.1 | no/yes | verify writer/readers/reset text |
| Tool policy decisions | Section 12.6 | Section 10.6 | Tool policy row in Section 20.1 | no/yes | verify `ToolView` and `ToolPolicyDecision` names/enums |
| Business fact results | Sections 8.4 and 12.5 | Section 12 | Business fact row in Section 20.1 | no/yes | verify `BusinessFactResultV1` and `BusinessFactRefV1` separation |
| Decision events | Section 17.2 | Section 14 | Decision event/replay row in Section 20.1 | no/yes | verify envelope, sequence, redaction, event ownership |
```

Source: Phase 26 success criteria and the three baseline docs. [VERIFIED: .planning/ROADMAP.md; docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md; docs/eval-test-plan.md]

### APF-02 Ownership Matrix

```markdown
| Module | Owned schemas/tables/events | Public methods | Allowed downstream dependencies | Forbidden imports/access | Decision events |
| --- | --- | --- | --- | --- | --- |
| `ToolPlatform` | `ToolDescriptor`, `ToolView`, `ToolPolicyDecision`, tool lifecycle events | `visible_tools`, `invoke` | `ToolPolicyEngine`, domain service public methods, artifact store | graph/investigate custom allowlists; raw adapter payload in prompt | visibility/runtime auth decisions |
| `KnowledgeService` | `EvidenceRefV1`, `VerifiedEvidencePackageV1`, claim verifier outputs | `search`, `build_verified_context`, `verify_claims` | policy/chunk repositories, retrieval engine, domain rule verifier plugins | judging current business facts; citation membership as semantic support | evidence validation and claim verification decisions |
| `BusinessFactService` | `BusinessFactResultV1`, `BusinessFactRefV1`, `BusinessContextV1` | `fetch_context`, `get_order`, `get_refund_case`, `get_ticket` | owned business repositories/adapters | graph direct repository access; memory/RAG/LLM substituted facts | business fact read decisions and safe errors |
```

Source: APF-02 plus architecture plan Section 5.2 and contract spec Sections 8.3, 8.4, 12.5, and 12.6. [VERIFIED: .planning/REQUIREMENTS.md; docs/target-agent-platform-architecture-plan.md; docs/contract-spec.md]

### Validation Commands

```bash
gsd-sdk query init.phase-op "26"
gsd-sdk query roadmap.get-phase "26"
gsd-sdk query validate.health
npx --yes markdownlint-cli2 docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md .planning/phases/26-architecture-contract-baseline/26-RESEARCH.md
git diff --check -- docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md .planning/phases/26-architecture-contract-baseline
```

Source: GSD context and available tooling discovered in this session. [VERIFIED: command output `gsd-sdk query init.phase-op 26`; `gsd-sdk query roadmap.get-phase 26`; `gsd-sdk query validate.health`; `npx --yes markdownlint-cli2 --version`]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
| --- | --- | --- | --- |
| Architecture rationale could look executable by itself | `contract-spec.md` is the only normative source, and architecture plan deltas must be synchronized before implementation | Documented in the 2026-06-22 target architecture plan and current contract spec | PLAN.md must verify or update `contract-spec.md`, not only architecture prose. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| RAG retrieval hits treated as usable evidence | Candidate refs -> `VerifiedEvidencePackageV1` -> `ClaimVerificationBundleV1` | Accepted in contract spec Section 0.1 and detailed in Sections 8.3 and 10 | Later implementation plans must keep retrieval, evidence validation, and claim support distinct. [VERIFIED: docs/contract-spec.md] |
| Planner-visible tool implied executable tool | Planner visibility and runtime authorization both produce `ToolPolicyDecision` | Accepted in contract spec Section 12.6 and architecture plan Section 10.6 | Later ToolPlatform plans must test visible/hidden/allowed/denied with reason codes. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| Business facts could be tool summaries or raw domain rows | `BusinessFactResultV1` / `BusinessFactRefV1` are stable contracts and are separate from `EvidenceRefV1` | Accepted in contract spec Sections 8.4 and 12.5 | Later BusinessFactService plans must forbid graph direct repository reads and memory/RAG-substituted facts. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| Replay/decision events could be retrofitted after services | Minimal event envelope/`DecisionEventEnvelopeV1` is a foundation contract before event-emitting phases | Accepted in contract spec Section 17.2 and architecture plan Section 14 | Later phases should emit unified redacted events from the start. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| Eval could be a generic "tests pass" statement | Eval gates are separated into dev-contract, release, and monitoring levels | Eval plan Section 20.0 | PLAN.md should specify gate level per boundary. [VERIFIED: docs/eval-test-plan.md] |

**Deprecated/outdated:**

- Physical microservices in v1.9 are out of scope; use modular monolith boundaries instead. [VERIFIED: 26-CONTEXT.md; .planning/REQUIREMENTS.md]
- Full real external action execution is out of scope; preserve action draft/approval/safety boundaries only. [VERIFIED: 26-CONTEXT.md; .planning/REQUIREMENTS.md]
- `phases.clear --confirm` is forbidden for old phase cleanup because context says it deletes instead of archiving. [VERIFIED: 26-CONTEXT.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
| --- | --- | --- | --- |
| - | No `[ASSUMED]` factual claims are intentionally used in this research; recommendations are derived from local phase context, repository docs, or command outputs. | All sections | If a source file changes after 2026-06-22, the planner should re-run the listed validation commands. [VERIFIED: command outputs; local docs listed in Sources] |

## Open Questions

1. **Should the alignment matrix live in a separate `26-BASELINE-CHECKLIST.md` artifact or only in edited docs and PLAN.md acceptance checks?**
   - What we know: Phase 26 must prove APF-01/APF-02 coverage and may create verification artifacts. [VERIFIED: 26-CONTEXT.md; .planning/REQUIREMENTS.md]
   - What's unclear: No locked decision names a required verification artifact file. [VERIFIED: 26-CONTEXT.md]
   - Recommendation: Let the planner choose the smallest executable artifact; use a separate checklist if acceptance criteria would otherwise become too diffuse. [VERIFIED: 26-CONTEXT.md]

2. **Should Phase 26 update `docs/contract-spec.md` or only verify current alignment?**
   - What we know: The current spec already claims core graph/RAG/tool/business/event deltas are accepted, but Phase 26 deliverables require confirming alignment and recording any delta/MVP/deferred item. [VERIFIED: docs/contract-spec.md; 26-CONTEXT.md]
   - What's unclear: Research did not exhaustively diff every enum/field across all docs. [VERIFIED: research scope and commands run]
   - Recommendation: PLAN.md should include an explicit drift audit task before any docs edit task. [VERIFIED: 26-CONTEXT.md; docs/contract-spec.md]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
| --- | --- | --- | --- | --- |
| `gsd-sdk` | Phase metadata and health checks | yes | v0.1.0 | Manual `rg`/file reads if a query command fails. [VERIFIED: command output `gsd-sdk --version`; `command -v gsd-sdk`] |
| `rg` | Source/doc verification | yes | path `/opt/homebrew/bin/rg` | `grep` if missing, but not needed here. [VERIFIED: command output `command -v rg`] |
| Python | Existing backend test runtime | yes | 3.13.3; project requires `>=3.12` | None needed for docs-only Phase 26. [VERIFIED: command output `python3 --version`; pyproject.toml] |
| `pytest` | Existing Python test framework | yes | 8.4.2 | Docs-only validation can skip pytest unless code/tests are touched. [VERIFIED: command output `pytest --version`; pyproject.toml; 26-CONTEXT.md] |
| Node/npm/npx | Markdown lint via `npx`; frontend tooling host | yes | Node v25.9.0, npm 11.12.1 | Manual Markdown review if `npx` is unavailable. [VERIFIED: command output `node --version`; `npm --version`; `command -v npx`] |
| `markdownlint-cli2` | Optional Markdown lint | yes via `npx --yes` | v0.22.1, markdownlint v0.40.0 | `git diff --check` plus manual Markdown rendering review. [VERIFIED: command output `npx --yes markdownlint-cli2 --version`] |
| GSD optional agents | Automated GSD validation/review helpers | partially missing | `init.phase-op 26` reported `gsd-integration-checker`, `gsd-nyquist-auditor`, `gsd-ui-auditor`, and `gsd-doc-verifier` missing | Use GSD queries, local grep, Markdown lint, and project cross-review workflow. [VERIFIED: command output `gsd-sdk query init.phase-op 26`; AGENTS.md] |

**Missing dependencies with no fallback:**

- None identified for the docs-only Phase 26 baseline. [VERIFIED: environment command outputs; 26-CONTEXT.md]

**Missing dependencies with fallback:**

- Optional GSD helper agents are missing, but Phase 26 can still be planned with `gsd-sdk` metadata checks, local source verification, and cross-review. [VERIFIED: command output `gsd-sdk query init.phase-op 26`; AGENTS.md]

## Validation Architecture

### Test Framework

| Property | Value |
| --- | --- |
| Framework | `pytest` 8.4.2 for existing Python tests; Phase 26 should primarily use docs/metadata validation. [VERIFIED: command output `pytest --version`; 26-CONTEXT.md] |
| Config file | `pyproject.toml` with `tool.pytest.ini_options.asyncio_mode = "auto"`. [VERIFIED: pyproject.toml] |
| Quick run command | `gsd-sdk query roadmap.get-phase "26"` plus `gsd-sdk query init.phase-op "26"` for metadata, and `git diff --check -- docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md .planning/phases/26-architecture-contract-baseline`. [VERIFIED: command outputs; 26-CONTEXT.md] |
| Full suite command | For docs-only Phase 26, use `npx --yes markdownlint-cli2 docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md .planning/phases/26-architecture-contract-baseline/*.md` plus the GSD metadata commands; do not run broad runtime suites unless code/test files are intentionally touched. [VERIFIED: command output `npx --yes markdownlint-cli2 --version`; 26-CONTEXT.md] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
| --- | --- | --- | --- | --- |
| APF-01 | Baseline docs agree on graph vocabulary, service boundaries, AgentState RAG/claim fields, tool policy decisions, business fact results, and decision event foundation. [VERIFIED: .planning/REQUIREMENTS.md] | docs contract audit + Markdown/GSD checks | `rg -n "VerifiedEvidencePackageV1\|ClaimVerificationBundleV1\|ToolPolicyDecision\|BusinessFactResultV1\|DecisionEventEnvelopeV1\|route_after_rag_context\|route_after_claim_verify" docs/contract-spec.md docs/target-agent-platform-architecture-plan.md docs/eval-test-plan.md` plus Markdown/GSD commands. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md; docs/eval-test-plan.md] | Existing docs yes; dedicated Phase 26 checklist optional. [VERIFIED: file reads] |
| APF-02 | Each platform/domain module has explicit ownership over schemas, repositories/adapters, public methods, downstream dependencies, forbidden imports, and decision events. [VERIFIED: .planning/REQUIREMENTS.md] | docs ownership matrix audit | `rg -n "Module Ownership\|Owns\|forbidden imports\|Decision Event\|BusinessFactService\|ToolPlatform\|KnowledgeService\|Observability" docs/target-agent-platform-architecture-plan.md docs/contract-spec.md` plus manual matrix verification. [VERIFIED: docs/target-agent-platform-architecture-plan.md; docs/contract-spec.md] | Existing architecture matrix yes; expanded APF-02 matrix may need Phase 26 edit. [VERIFIED: docs/target-agent-platform-architecture-plan.md; .planning/REQUIREMENTS.md] |

### Sampling Rate

- **Per task commit:** Run metadata/Markdown/diff checks scoped to touched docs. [VERIFIED: .planning/config.json; command outputs]
- **Per wave merge:** Re-run APF-01/APF-02 `rg` checks and `gsd-sdk query validate.health`; accept known degraded warnings only if they match the documented non-blocking old-phase/future-directory caveat. [VERIFIED: 26-CONTEXT.md; .planning/LOCAL-VALIDATION-ISSUES.md; command output `gsd-sdk query validate.health`]
- **Phase gate:** Confirm no runtime code files changed unless PLAN.md explicitly justified them; verify APF-01/APF-02 coverage and no physical microservice/full-real-execution scope. [VERIFIED: 26-CONTEXT.md; AGENTS.md]

### Wave 0 Gaps

- [ ] Optional `26-BASELINE-CHECKLIST.md` or equivalent PLAN.md acceptance matrix covering APF-01/APF-02 if the planner wants a concrete verification artifact. [VERIFIED: 26-CONTEXT.md; .planning/REQUIREMENTS.md]
- [ ] No dedicated automated docs consistency test exists for APF-01/APF-02; use explicit `rg`/Markdown/GSD checks and manual contract review. [VERIFIED: test file listing; docs reviewed]
- [ ] Treat `gsd-sdk query validate.health` warnings as documented non-blocking caveats, not Wave 0 blockers. [VERIFIED: 26-CONTEXT.md; command output `gsd-sdk query validate.health`]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
| --- | --- | --- |
| V2 Authentication | yes | Trusted identity/scope fields must come from API/auth/run boundaries and cannot be overridden by LLM/user payload. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| V3 Session Management | yes | `session_context_load` and `SessionContextMemory` are same-thread continuity aids, not authority for policy evidence, approval/action, or replay truth. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| V4 Access Control | yes | `ToolPolicyDecision`, `merchant_scope`, `permissions`, KnowledgeContext scope checks, and BusinessFactService scope checks are standard controls. [VERIFIED: docs/contract-spec.md] |
| V5 Input Validation | yes | Stable schemas and typed envelopes such as `ToolResultV2`, `BusinessFactResultV1`, `VerifiedEvidencePackageV1`, and `DecisionEventEnvelopeV1` define validation boundaries. [VERIFIED: docs/contract-spec.md] |
| V6 Cryptography | yes, contract-level only | Canonical hash profile and SHA-256 bindings are specified for approval/action safety; Phase 26 should not implement cryptographic code. [VERIFIED: docs/contract-spec.md; 26-CONTEXT.md] |

### Known Threat Patterns for MOCA Agent Platform Contracts

| Pattern | STRIDE | Standard Mitigation |
| --- | --- | --- |
| LLM/user payload spoofing tenant/user/permission/run context | Spoofing / Elevation of privilege | TrustedContext and projections must be system-injected and never widened by LLM/user payload. [VERIFIED: docs/contract-spec.md] |
| Cross-tenant or merchant scope leakage in tools/RAG/business facts | Information disclosure / Elevation of privilege | `merchant_scope`, permissions, KnowledgeContext filtering, and BusinessFactService scope checks before adapter execution. [VERIFIED: docs/contract-spec.md] |
| Candidate RAG refs used as verified evidence | Tampering / Information disclosure | `rag_context_build` must validate identity/scope/hash/version/effective date into `VerifiedEvidencePackageV1`. [VERIFIED: docs/contract-spec.md] |
| Unsupported policy/action claims reaching user or action path | Tampering / Elevation of privilege | `ClaimVerifier` rules-first hard gates and fail-closed behavior for high-risk/action-bound paths. [VERIFIED: docs/contract-spec.md] |
| Planner-visible tool treated as runtime-authorized | Elevation of privilege | Separate planner visibility and runtime auth decisions with `ToolPolicyDecision`. [VERIFIED: docs/contract-spec.md] |
| Business facts inferred from memory/RAG/LLM | Tampering / Information disclosure | Current business facts must come from BusinessFactService/domain service contracts and `BusinessFactRefV1`. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md] |
| Fake approval chat or mutated action payload executes action | Elevation of privilege / Tampering | Approval/action contracts bind trusted approval result, action payload hash, safety snapshot hash, and exact revision. [VERIFIED: docs/contract-spec.md] |
| Replay/event payload leaks prompt/raw tool/PII/action payload | Information disclosure | `DecisionEventEnvelopeV1` requires redacted payloads and forbids complete prompts, raw tool responses, secrets, and PII. [VERIFIED: docs/contract-spec.md] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/26-architecture-contract-baseline/26-CONTEXT.md` - locked Phase 26 decisions, deliverables, GSD metadata caveats, deferred items. [VERIFIED: local file read]
- `.planning/REQUIREMENTS.md` - APF-01/APF-02 definitions, out-of-scope list, traceability. [VERIFIED: local file read]
- `.planning/ROADMAP.md` - Phase 26 goal, success criteria, phase order. [VERIFIED: local file read; `gsd-sdk query roadmap.get-phase 26`]
- `.planning/STATE.md` - current v1.9 focus, decisions, pending old-phase cleanup todo, non-blocking validation caveat. [VERIFIED: local file read]
- `AGENTS.md` and `CLAUDE.md` - project workflow rules, local issue logging, contract/spec authority rules, cross-review workflow. [VERIFIED: local file read]
- `docs/contract-spec.md` - normative graph, AgentState, RAG/claim, tool, business fact, approval/action, and decision event contracts. [VERIFIED: local file read]
- `docs/target-agent-platform-architecture-plan.md` - target modular monolith architecture, module ownership matrix, rationale, implementation order. [VERIFIED: local file read]
- `docs/eval-test-plan.md` - eval gate levels, contract test matrix, golden flow requirements. [VERIFIED: local file read]
- `.planning/LOCAL-VALIDATION-ISSUES.md` - known GSD metadata/health caveats and validation command pitfalls. [VERIFIED: local file read]
- `.planning/config.json` - Nyquist validation enabled, GSD workflow settings. [VERIFIED: local file read]
- Command outputs: `gsd-sdk query init.phase-op 26`, `gsd-sdk query roadmap.get-phase 26`, `gsd-sdk query validate.health`, `gsd-sdk --version`, `pytest --version`, `python3 --version`, `node --version`, `npm --version`, `npx --yes markdownlint-cli2 --version`. [VERIFIED: commands run during research]

### Secondary (MEDIUM confidence)

- None. No web or external docs were needed because Phase 26 is repository-local docs/spec/eval baseline work. [VERIFIED: 26-CONTEXT.md]

### Tertiary (LOW confidence)

- None. [VERIFIED: Sources above]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - existing tools and docs were verified from local files and command outputs. [VERIFIED: pyproject.toml; frontend/package.json; command outputs]
- Architecture: HIGH - source of truth, target architecture, and eval gates are explicit in local docs. [VERIFIED: docs/contract-spec.md; docs/target-agent-platform-architecture-plan.md; docs/eval-test-plan.md]
- Pitfalls: HIGH - pitfalls are directly derived from locked decisions, project rules, and documented local GSD issues. [VERIFIED: 26-CONTEXT.md; AGENTS.md; CLAUDE.md; .planning/LOCAL-VALIDATION-ISSUES.md]
- Security: MEDIUM - local contract controls are explicit, but ASVS category mapping is a planning classification rather than an external ASVS citation. [VERIFIED: docs/contract-spec.md; .planning/config.json]

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 for this docs baseline, or earlier if `docs/contract-spec.md`, `docs/target-agent-platform-architecture-plan.md`, `docs/eval-test-plan.md`, `.planning/REQUIREMENTS.md`, or Phase 26 context changes. [VERIFIED: local files read on 2026-06-22]
