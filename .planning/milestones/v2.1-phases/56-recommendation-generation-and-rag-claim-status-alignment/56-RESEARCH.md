# Phase 56: Recommendation Generation and RAG Claim Status Alignment - Research

**Researched:** 2026-07-07 [VERIFIED: system date]
**Domain:** Backend LangGraph graph canonicalization, RAG evidence gating, and material-claim verification [VERIFIED: .planning/ROADMAP.md:446-457]
**Confidence:** HIGH for codebase facts, MEDIUM for live runtime-state inventory [VERIFIED: src/agent/graph.py:278-389; ASSUMED: live DB contents not queried]

<user_constraints>
## User Constraints (from CONTEXT.md)

Source for this entire copied block: [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:6-110]

### Locked Decisions

## Implementation Decisions

### Active recommendation node cutover
- **D-56-01:** Active `StateGraph.add_node(...)` registration must use `recommendation_generation`, not `generate_recommendation`.
- **D-56-02:** Conditional edge path maps from `investigate` and `rag_context_build` must route the `recommendation_generation` route value to the active `recommendation_generation` node. The active route source for `route_after_recommendation` must also be `recommendation_generation`.
- **D-56-03:** Existing `src/agent/nodes/generate_recommendation.py` behavior may be reused only as an implementation compatibility layer if the plan records legacy surface, canonical owner, reason, trace projection, validation, and delete phase. It must not remain the active graph registration after Phase 56.
- **D-56-04:** `generate_recommendation` compatibility should be scoped narrowly to imports/tests/historical trace projection. Do not do a destructive repository-wide rename of every historical mention.

### RAG context fail-closed semantics
- **D-56-05:** `rag_context_build` status vocabulary must remain finite and machine-readable, aligned with `VerifiedEvidencePackageV1.status`: `not_required`, `verified`, `partial`, `no_evidence`, `unauthorized`, `stale`, `conflict`, `invalid_hash`, `invalid_scope`, and `build_error`.
- **D-56-06:** `route_after_rag_context` must fail closed to a safe terminal/clarification path for missing or unknown status and for unsafe evidence states. `partial` may proceed only for low-risk answer-only/policy-QA style generation, not action-bound or high-risk flows.
- **D-56-07:** Unauthorized, stale, conflict, invalid hash, invalid scope, no evidence, malformed package, and build error states must not be promotable to `evidence_refs`, approval snapshots, risk lowering, approval, or action draft authority.

### Claim verification hard gate
- **D-56-08:** Every material claim, user-visible policy/business/action claim, or proposed action from `recommendation_generation` must pass through `claim_verify`.
- **D-56-09:** `recommendation_generation` can write draft text, candidate `material_claims`, candidate `proposed_action`, `missing_info`, and citation-validated `evidence_refs`. It cannot mark evidence verified, write `claim_verification_bundle`, clear `blocked_claims`, or decide that a claim is safe.
- **D-56-10:** `route_after_claim_verify` may proceed toward the current Phase 57-owned risk node only when the canonical claim bundle allows it: `route == "continue"`, `overall_status in {"verified", "not_required"}`, no blocked claims, and action claims explicitly allow action recommendation when present.
- **D-56-11:** Existing legacy projection fields such as `verification_route`, `verifier_status`, and `verifier_reason_codes` can remain compatibility outputs, but they cannot override or bypass `claim_verification_bundle`.

### Final wording and safe termination
- **D-56-12:** Safe terminal wording must distinguish insufficient evidence, unsafe/invalid RAG context, unsupported claim, manual review, and verifier error where those states are available. User-visible final text must not imply verified policy/business/action authority when gates failed.
- **D-56-13:** `final_response` should consume only safe projections from `verified_evidence_package` and `claim_verification_bundle`; debug/verifier projections must not leak.

### Planning and validation shape
- **D-56-14:** Planning should be split into multiple ordered plans, not one large plan. Expected boundaries are: canonical node/wrapper contract; active graph/router/baseline cutover; RAG/claim status fail-closed alignment; vocabulary/API/docs/debt/validation closeout.
- **D-56-15:** Phase 56 must preserve Phase 55 memory authority boundaries and Phase 57 risk/approval scope. Tests should prove `assess_risk_and_approval` remains the Phase 57 active legacy row until Phase 57.
- **D-56-16:** All verification commands must use MOCA-approved entrypoints such as `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`; bare `pytest` and bare `python -m pytest` are invalid.

### Claude's Discretion

### the agent's Discretion
- Exact wrapper/module naming is left to the planner as long as active graph registration and trace projection are canonical.
- Exact low-risk `partial` status predicate may be refined from current code, but it must stay deterministic and action-bound flows must fail closed.
- Exact safe final-response copy is implementation discretion as long as it truthfully reflects gate outcomes.

### Deferred Ideas (OUT OF SCOPE)

## Deferred Ideas

- `assess_risk_and_approval -> risk_gate` active graph rename and approval/risk responsibility split remain Phase 57 scope.
- Final deletion of compatibility aliases/wrappers/historical display rows remains Phase 58 scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAGM-07 | `recommendation_generation` replaces active `generate_recommendation` graph naming, and RAG/claim fail-closed statuses are aligned so unsafe evidence or unsupported material/action claims cannot enter action paths. [VERIFIED: .planning/REQUIREMENTS.md:53-61] | Active graph/router/baseline facts, strict RAG/claim schemas, existing node behavior, and validation gaps are mapped below. [VERIFIED: src/agent/graph.py:282-389; src/knowledge/schemas.py:73-195; tests/architecture/graph_baseline.py:31-116] |
</phase_requirements>

## Summary

Phase 56 is primarily a backend graph/runtime-safety phase, not a product feature phase. The active graph still registers `generate_recommendation`, and both `investigate` and `rag_context_build` currently map the canonical route value `recommendation_generation` to that legacy destination. [VERIFIED: src/agent/graph.py:290-351] The target contract requires the active registered node key to be `recommendation_generation`, followed by `claim_verify`, while Phase 57 still owns the later `assess_risk_and_approval -> risk_gate` rename. [VERIFIED: docs/contract-spec.md:444-462; .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:9-12]

The existing RAG/claim implementation is a good foundation: `rag_context_build` writes `rag_context_status`, `verified_evidence_package`, `citation_map`, and `evidence_map`; `generate_recommendation` already gates on verified package status, validates citation membership, emits `MaterialClaimV1`-shaped claims with `generated_from_step="recommendation_generation"`, and writes `evidence_refs` only from validated refs; `claim_verify` writes `claim_verification_bundle`, `blocked_claims`, `safe_support_refs`, and compatibility verifier fields. [VERIFIED: src/agent/nodes/rag_context_build.py:248-260; src/agent/nodes/generate_recommendation.py:179-277; src/agent/nodes/generate_recommendation.py:633-677; src/agent/nodes/claim_verify.py:56-73]

The main safety gap is not absence of gates; it is alignment and authority hardening. `route_after_claim_verify` currently routes to the Phase 57 risk node when a `proposed_action` exists and the bundle is `verified/continue`, even if no action-claim result explicitly allows the action recommendation; Phase 56 decision D-56-10 requires explicit action-claim allowance when action claims are present. [VERIFIED: src/agent/routing.py:580-592; .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:29-33]

**Primary recommendation:** Split Phase 56 into four ordered plans: canonical node/wrapper contract, active graph/router/baseline cutover, RAG/claim fail-closed hardening, then vocabulary/API/docs/debt/validation closeout. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:39-42; AGENTS.md:55-60]

## Project Constraints (from CLAUDE.md)

- Any local debugging, startup, validation, UI/API test, RAG/agent/memory/tool-call investigation failure must be appended to `.planning/LOCAL-VALIDATION-ISSUES.md` in Chinese with symptom, reproduction, evidence, root-cause judgment, handling, residual issue, and next entry point. [VERIFIED: CLAUDE.md:5-7; AGENTS.md:12-14]
- Changes touching RAG must append confirmed subsystem-level bugs, design defects, compromises, or completed fixes to `.planning/ARCHITECTURE-DEBT.md` with status, evidence, and residual risk. [VERIFIED: CLAUDE.md:9-15; AGENTS.md:16-22]
- Phase-level planning must use GSD plan flow plus independent cross-review; larger plan or code changes must be verified against real repository code and tests rather than accepted blindly. [VERIFIED: CLAUDE.md:17-45; AGENTS.md:31-66]
- If a phase touches multiple service boundaries, ownership domains, waves, or verification gates, it must be split into multiple numbered plans before execution. [VERIFIED: AGENTS.md:55-60]
- MOCA tests must not use bare `pytest` or bare `python -m pytest`; accepted commands use `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, `uv run pytest ...`, or `.venv/bin/pytest ...` after verifying the venv belongs to the repo. [VERIFIED: AGENTS.md:24-29]
- `docs/contract-spec.md` is the accepted contract reference for target semantics, but it describes target contract, not automatically implemented facts; implementation/spec conflicts must be recorded as spec fix or MVP/defer note. [VERIFIED: CLAUDE.md:73-81; AGENTS.md:94-102]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Active `recommendation_generation` node registration | API / Backend graph orchestration | Trace/API projection | `StateGraph.add_node(...)` and `add_conditional_edges(...)` live in backend graph assembly, while trace/API projection must keep historical rows readable. [VERIFIED: src/agent/graph.py:278-389; src/api/routers/agent_runs.py:1140-1152] |
| Recommendation generation behavior | API / Backend node | LLM provider | The node consumes business/evidence/memory context and structured LLM output, with no direct tool allowlist. [VERIFIED: docs/contract-spec.md:637; docs/contract-spec.md:1195-1204] |
| RAG evidence status | API / Backend knowledge boundary | Database / Storage | `rag_context_build` constructs a verified evidence package from candidate refs and trusted knowledge context; persisted/evaluable refs flow through AgentStep/replay surfaces. [VERIFIED: src/agent/nodes/rag_context_build.py:24-55; docs/contract-spec.md:896-898] |
| Claim verification | API / Backend knowledge boundary | Database / Storage | `claim_verify` delegates to `PolicyKnowledgeService.verify_claims(...)`, which normalizes material claims and returns strict `ClaimVerificationBundleV1`. [VERIFIED: src/agent/nodes/claim_verify.py:19-37; src/knowledge/service.py:508-612] |
| Safe final wording and projection | API / Backend response node | Frontend display | `final_response` builds safe verification payloads from claim/RAG bundles, while API/SSE surfaces expose node messages and target node projection. [VERIFIED: src/agent/nodes/final_response.py:403-470; src/api/routers/agent_runs.py:56-70; src/api/routers/agent_runs.py:1140-1152] |
| Compatibility ledger and migration docs | Planning/docs | API / Backend trace projection | Phase 50 requires every temporary compatibility surface to record legacy surface, owner, reason, projection, validation, and delete phase. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:179-192] |

## Recommended Plan Split

| Plan | Scope | Key Files | Required Proof |
|------|-------|-----------|----------------|
| `56-01` | Canonical node/wrapper contract: introduce `recommendation_generation` as canonical callable/module identity while keeping narrow `generate_recommendation` import/test compatibility. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:18-23] | `src/agent/nodes/recommendation_generation.py` (new or equivalent), `src/agent/nodes/generate_recommendation.py`, `tests/agent/test_nodes/test_generate_recommendation.py`, optional new canonical node tests. [VERIFIED: src/agent/nodes/generate_recommendation.py:173-277; tests/agent/test_nodes/test_generate_recommendation.py:566-625] | Canonical active callable emits canonical trace/output identity for new runs; legacy import tests still pass or are explicitly re-scoped. [VERIFIED: src/agent/nodes/generate_recommendation.py:79-96; src/agent/nodes/generate_recommendation.py:260-277] |
| `56-02` | Active graph/router/baseline cutover: graph registers `recommendation_generation`; route maps target it; `route_after_recommendation` source becomes canonical; Phase 57 row remains active. [VERIFIED: src/agent/graph.py:330-365; .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:39-42] | `src/agent/graph.py`, `tests/architecture/graph_baseline.py`, `tests/architecture/test_canonical_graph_baseline.py`, `tests/agent/test_graph.py`. [VERIFIED: tests/architecture/graph_baseline.py:31-116; tests/architecture/test_canonical_graph_baseline.py:63-151] | `graph_add_node_names()` contains `recommendation_generation` and not `generate_recommendation`; active legacy map contains only `assess_risk_and_approval`; route maps no longer send canonical route values to legacy destination. [VERIFIED: tests/architecture/graph_baseline.py:143-199] |
| `56-03` | RAG/claim fail-closed alignment: source RAG statuses from strict schema, ensure malformed/unknown/unsafe RAG statuses cannot promote evidence or action authority, and require action-claim allowance before risk route. [VERIFIED: src/knowledge/schemas.py:73-107; src/agent/routing.py:553-592] | `src/agent/routing.py`, `src/agent/nodes/rag_context_build.py`, `src/agent/nodes/claim_verify.py`, `tests/agent/test_rag_context_routing.py`, `tests/agent/rag_context/test_routing.py`, `tests/knowledge/test_verified_evidence_package.py`, `tests/knowledge/test_claim_verification_bundle.py`. [VERIFIED: tests/agent/test_rag_context_routing.py:13-96; tests/agent/rag_context/test_routing.py:182-337] | Unknown/missing RAG statuses and unsafe statuses return safe final/clarification paths; `partial` cannot enter action/high-risk generation; `proposed_action` cannot reach risk unless action claim verification explicitly allows it when action claims exist. [VERIFIED: src/agent/routing.py:557-566; src/agent/routing.py:580-592] |
| `56-04` | Compatibility ledger, API/SSE/frontend/eval/docs/debt, and final validation closeout: add Phase 56 vocabulary alias metadata, update current-source docs, update timeline labels and eval scripts if they represent current runtime, and record retained/deleted compatibility surfaces. [VERIFIED: src/agent/graph_vocabulary.py:41-171; src/api/routers/agent_runs.py:56-70; frontend/src/components/timeline/TimelineStep.tsx:5-15] | `src/agent/graph_vocabulary.py`, `src/api/routers/agent_runs.py`, `frontend/src/components/timeline/TimelineStep.tsx`, `scripts/eval_agent.py`, `docs/current-langgraph-architecture.md`, `.planning/ARCHITECTURE-DEBT.md`, validation artifact. [VERIFIED: docs/current-langgraph-architecture.md:88-107; scripts/eval_agent.py:412-520] | Current-run display supports `recommendation_generation`; historical `generate_recommendation` remains readable through projection; docs/debt distinguish current source facts from target contract and Phase 58 cleanup. [VERIFIED: src/api/routers/agent_runs.py:1140-1152; .planning/ARCHITECTURE-DEBT.md:443-464] |

## Standard Stack

### Core

| Library / Component | Version | Purpose | Why Standard |
|---------------------|---------|---------|--------------|
| Python | 3.12.13 | Runtime and test entrypoint. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run python --version` on 2026-07-07] | Project requires Python `>=3.12`, and MOCA forbids bare local Python test entrypoints. [VERIFIED: pyproject.toml:5; AGENTS.md:24-29] |
| LangGraph | 1.1.10 installed; `pyproject.toml` requires `langgraph>=0.4` | Backend graph assembly with `StateGraph`, `START`, `END`, and `RetryPolicy`. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run python -c importlib.metadata` on 2026-07-07; src/agent/graph.py:18-20] | Existing graph uses LangGraph `StateGraph` and conditional edges; no new orchestration library is needed. [VERIFIED: src/agent/graph.py:278-389] |
| Pydantic | 2.13.4 installed | Strict DTO validation for evidence packages, material claims, and claim bundles. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run python -c importlib.metadata` on 2026-07-07; src/knowledge/schemas.py:14-15] | Existing schemas forbid extra fields and pin status/route literals. [VERIFIED: src/knowledge/schemas.py:126-195; tests/knowledge/test_verified_evidence_package.py:137-180; tests/knowledge/test_claim_verification_bundle.py:151-173] |
| pytest / pytest-asyncio | pytest 9.0.3, pytest-asyncio 1.3.0 installed | Unit, async, graph, architecture, and API regression tests. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run python -c importlib.metadata` on 2026-07-07] | Project validation strategy uses pytest with `pyproject.toml` config and approved `uv run` entrypoints. [VERIFIED: pyproject.toml:34-55; .planning/phases/55-memory-context-load-cutover/55-VALIDATION.md:16-24] |
| Ruff | 0.15.12 installed | Source/test linting for closeout. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run python -c importlib.metadata` on 2026-07-07] | Prior Phase 55 closeout used Ruff as a required final check. [VERIFIED: .planning/phases/55-memory-context-load-cutover/55-VERIFICATION.md:71-75] |

### Supporting

| Library / Component | Version | Purpose | When to Use |
|---------------------|---------|---------|-------------|
| `src.agent.graph_vocabulary` | Repository component | Runtime vs compatibility alias projection for traces/API. [VERIFIED: src/agent/graph_vocabulary.py:13-21; src/agent/graph_vocabulary.py:197-207] | Use for `generate_recommendation -> recommendation_generation` historical projection instead of rewriting stored trace rows. [VERIFIED: docs/current-langgraph-architecture.md:88-107] |
| `tests/architecture/graph_baseline.py` | Repository component | AST-based graph node and route-map inspection. [VERIFIED: tests/architecture/graph_baseline.py:143-199] | Use for active node and route-map proof after graph cutover. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:93-151] |
| `PolicyKnowledgeService` | Repository service | Builds verified evidence packages and claim verification bundles. [VERIFIED: src/knowledge/service.py:487-612] | Use through `rag_context_build` and `claim_verify`; do not move verification ownership into generation. [VERIFIED: src/agent/nodes/rag_context_build.py:37-55; src/agent/nodes/claim_verify.py:21-37] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New RAG/claim library | External verifier framework | Not recommended: Phase 56 scope is alignment of existing strict DTOs, routers, graph naming, and compatibility surfaces, not replacement of evidence or verifier services. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:96-100; src/knowledge/schemas.py:73-195] |
| Destructive repo-wide rename | Rename every `generate_recommendation` mention | Not allowed: Phase 56 context explicitly says to keep narrow import/test/historical trace compatibility and avoid destructive historical renames. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:18-23] |
| One large plan | Single `56-01-PLAN.md` | Not allowed by phase decisions and AGENTS plan granularity constraints because this phase crosses graph, node, router, API/projection, docs/debt, and validation boundaries. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:39-42; AGENTS.md:55-60] |

**Installation:** No new packages are recommended. [VERIFIED: pyproject.toml:6-40; .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:96-100]

```bash
# No install step for Phase 56.
UV_CACHE_DIR=/tmp/uv-cache uv run python --version
```

**Version verification:** Versions were checked with `UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'from importlib.metadata import version; ...'` on 2026-07-07. [VERIFIED: local command output]

## Architecture Patterns

### System Architecture Diagram

```text
investigate
  -> route_after_investigate
    -> rag_context_build
       -> route_after_rag_context
          -> recommendation_generation
             -> route_after_recommendation
                -> claim_verify
                   -> route_after_claim_verify
                      -> assess_risk_and_approval (Phase 57 legacy active risk node)
                      -> final_response
          -> clarification_gate / final_response
    -> recommendation_generation (only when policy evidence is not required)
    -> clarification_gate / final_response

Compatibility side path:
historical/import/test `generate_recommendation`
  -> graph_vocabulary projection
  -> canonical target `recommendation_generation`
  -> delete no later than Phase 58
```

This diagram uses active Phase 56 target flow and intentionally leaves `assess_risk_and_approval` as the Phase 57-owned active risk node. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:39-42; src/agent/graph.py:358-383]

### Recommended Project Structure

```text
src/agent/nodes/
  recommendation_generation.py       # canonical active graph callable
  generate_recommendation.py          # narrow legacy import/test compatibility surface until Phase 58
src/agent/
  graph.py                            # active StateGraph registration and route maps
  routing.py                          # deterministic fail-closed route functions
  graph_vocabulary.py                 # runtime/compat trace/API projection
tests/architecture/
  graph_baseline.py
  test_canonical_graph_baseline.py
tests/agent/
  test_graph.py
  test_graph_vocabulary.py
  test_rag_context_routing.py
  rag_context/test_routing.py
tests/knowledge/
  test_verified_evidence_package.py
  test_claim_verification_bundle.py
```

This structure follows existing repository ownership: graph assembly in `src/agent/graph.py`, deterministic routing in `src/agent/routing.py`, RAG/claim DTOs and services in `src/knowledge`, and static graph guardrails in `tests/architecture`. [VERIFIED: src/agent/graph.py:278-389; src/agent/routing.py:509-592; src/knowledge/schemas.py:73-195; tests/architecture/graph_baseline.py:143-199]

### Pattern 1: Canonical Active Node With Narrow Legacy Projection

**What:** Register the canonical node key in `StateGraph`, keep any legacy implementation/import surface outside active graph registration, and record the legacy surface in `graph_vocabulary.py` with delete-by metadata. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:179-192; src/agent/graph_vocabulary.py:41-55]

**When to use:** Use for `generate_recommendation -> recommendation_generation`, matching the Phase 55 pattern for `long_term_memory_retrieve -> memory_context_load`. [VERIFIED: docs/current-langgraph-architecture.md:104-107; .planning/ARCHITECTURE-DEBT.md:443-464]

**Example:**

```python
# Source pattern: src/agent/graph.py:330-357, adapted for Phase 56 target.
builder.add_node("recommendation_generation", recommendation_generation, retry_policy=_llm_retry)
builder.add_conditional_edges(
    "rag_context_build",
    route_after_rag_context,
    {
        "recommendation_generation": "recommendation_generation",
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
    },
)
builder.add_conditional_edges(
    "recommendation_generation",
    route_after_recommendation,
    {"claim_verify": "claim_verify", "final_response": "final_response"},
)
```

### Pattern 2: Router Wrapper Fails Closed on Exception or Unknown Route

**What:** Public `route_after_*` wrappers catch exceptions and only return route values from finite allowlists. [VERIFIED: src/agent/routing.py:509-550]

**When to use:** Preserve and extend this pattern for RAG and claim verification alignment. [VERIFIED: src/agent/routing.py:531-550]

**Example:**

```python
# Source: src/agent/routing.py:531-539
def route_after_rag_context(state: AgentState) -> str:
    try:
        route = _route_after_rag_context(state)
    except Exception:
        return "final_response"
    if route in _RAG_CONTEXT_ROUTES:
        return route
    return "final_response"
```

### Pattern 3: Strict DTOs Own Status Vocabularies

**What:** RAG and claim status literals are defined in `src/knowledge/schemas.py` and enforced by Pydantic models with `extra="forbid"`. [VERIFIED: src/knowledge/schemas.py:73-107; src/knowledge/schemas.py:126-195]

**When to use:** Use these schemas as the finite vocabulary source; add router/schema drift tests instead of duplicating free-form strings. [VERIFIED: tests/knowledge/test_verified_evidence_package.py:97-180; tests/knowledge/test_claim_verification_bundle.py:101-173]

**Example:**

```python
# Source: src/knowledge/schemas.py:73-89
RAG_CONTEXT_STATUSES = (
    "not_required",
    "verified",
    "partial",
    "no_evidence",
    "unauthorized",
    "stale",
    "conflict",
    "invalid_hash",
    "invalid_scope",
    "build_error",
)
```

### Pattern 4: Generation Writes Claims, Claim Verify Decides Safety

**What:** Recommendation generation may produce candidate material claims and validated evidence refs, but `claim_verify` writes the bundle, blocked claims, safe refs, and compatibility verifier fields. [VERIFIED: src/agent/nodes/generate_recommendation.py:255-277; src/agent/nodes/claim_verify.py:56-73]

**When to use:** Keep `recommendation_generation` from importing verifier services or writing verifier-owned fields. [VERIFIED: tests/agent/test_nodes/test_generate_recommendation.py:570-584; docs/contract-spec.md:919-921]

**Example:**

```python
# Source: src/agent/nodes/claim_verify.py:61-72
return {
    "claim_verification_bundle": bundle_data,
    "blocked_claims": list(bundle.blocked_claims),
    "safe_support_refs": safe_support_refs,
    "verifier_status": bundle.overall_status,
    "verification_route": _legacy_verification_route(bundle),
    "verifier_reason_codes": list(bundle.reason_codes),
    "verifier_safe_citation_refs": safe_ref_ids,
    "trace_steps": (state.get("trace_steps") or []) + [_trace_step(bundle, started_at)],
}
```

### Anti-Patterns to Avoid

- **Changing `assess_risk_and_approval` to `risk_gate` in Phase 56:** Phase 57 owns that active rename, and Phase 56 tests must preserve the Phase 57 legacy row. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:39-42; .planning/ROADMAP.md:462-476]
- **Repo-wide destructive rename of `generate_recommendation`:** The context explicitly scopes compatibility to imports/tests/historical trace projection and says not to rewrite every historical mention. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:18-23]
- **Letting legacy `verification_route="allow"` override missing/blocked `claim_verification_bundle`:** Phase 56 allows legacy projection fields only as compatibility outputs; they cannot bypass canonical bundle gates. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:29-33; src/agent/routing.py:580-592]
- **Treating `rag_context_build` as claim support verification:** The target docs distinguish evidence package construction from post-generation claim verification. [VERIFIED: docs/target-agent-platform-architecture-plan.md:425; docs/contract-spec.md:491-500]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RAG status vocabulary | New string enums inside router tests | `src.knowledge.schemas.RAG_CONTEXT_STATUSES` / `VerifiedEvidencePackageV1.status` | Existing schemas pin exact statuses and reject unknown statuses. [VERIFIED: src/knowledge/schemas.py:73-102; tests/knowledge/test_verified_evidence_package.py:97-180] |
| Claim bundle semantics | Custom dict checks spread across graph/node code | `ClaimVerificationBundleV1` plus `PolicyKnowledgeService.verify_claims(...)` | Existing service normalizes claims, validates package status, orders action claims after dependencies, and returns strict route/status fields. [VERIFIED: src/knowledge/service.py:508-612] |
| Active graph drift detection | Text grep-only graph checks | `tests/architecture/graph_baseline.py` AST helpers | Existing helpers inspect `add_node(...)`, `add_edge(...)`, and `add_conditional_edges(...)` source shapes. [VERIFIED: tests/architecture/graph_baseline.py:143-199] |
| Trace/API compatibility projection | Ad hoc response rewriting | `src.agent.graph_vocabulary.target_graph_name()` and `project_trace_step_for_contract()` | Existing API/SSE code already adds `target_node_name` without rewriting original node name. [VERIFIED: src/agent/graph_vocabulary.py:185-207; src/api/routers/agent_runs.py:1140-1152] |
| Citation membership | LLM self-attestation | `validate_membership(...)` inside generation | Existing generation validates cited evidence IDs against verified package evidence models and drops invalid refs or fails closed. [VERIFIED: src/agent/nodes/generate_recommendation.py:211-258] |

**Key insight:** Phase 56 should align authoritative boundaries already present in code; custom one-off string checks or broad renames would increase drift across graph, trace, API, and tests. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:76-92; src/agent/routing.py:509-592]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | Historical AgentStep/trace/API rows may contain `generate_recommendation` as implementation node; current docs explicitly treat legacy names as possible historical trace/import/test surfaces. [VERIFIED: docs/current-langgraph-architecture.md:88-107; ASSUMED: live DB may contain historical `generate_recommendation` rows] | Code compatibility/projection required; do not plan a data migration unless a separate production DB audit requests it. [VERIFIED: src/agent/graph_vocabulary.py:197-207; src/api/routers/agent_runs.py:1140-1152] |
| Live service config | No repository config, Docker, `.planning/config.json`, or scripts source was found that registers `generate_recommendation` as an external service name; eval/diagnostic scripts do contain legacy node labels. [VERIFIED: repository `rg -n "generate_recommendation|recommendation_generation" .env* docker* Dockerfile* docker-compose* scripts src tests docs .planning --glob '!uv.lock'`; scripts/eval_agent.py:133-145; scripts/eval_agent.py:412-520] | Update scripts only if they are current validation surfaces for Phase 56; otherwise mark historical/dev compatibility. [VERIFIED: scripts/eval_agent.py:504-520] |
| OS-registered state | None found in repository files; no OS scheduler, launchd, pm2, or systemd registration was discovered in the workspace scan. [VERIFIED: repository `rg` audit; ASSUMED: no external OS registrations outside repo were queried] | No code task unless user reports an external runtime registration. [ASSUMED] |
| Secrets/env vars | No secret/env var name with `generate_recommendation` was found in repository-scoped env/config search. [VERIFIED: repository `rg -n "generate_recommendation|recommendation_generation" .env* ... --glob '!uv.lock'`] | None. [VERIFIED: same repository search] |
| Build artifacts | `moca.egg-info` and many `__pycache__` directories exist; these are build/test artifacts and are not authoritative source. [VERIFIED: `find . -maxdepth 3 \( -name '*egg-info' -o -name '__pycache__' ... \) -print`] | Do not plan source changes in artifacts; optional cleanup/reinstall can be deferred unless tests import stale bytecode unexpectedly. [VERIFIED: same artifact scan] |

## Compatibility Ledger Recommendations

| Legacy Surface | Canonical Owner | Phase 56 Recommendation | Delete Phase |
|----------------|-----------------|-------------------------|--------------|
| Active graph node `generate_recommendation` | `recommendation_generation` | Remove from active `StateGraph.add_node(...)` and route-map destinations in Phase 56. [VERIFIED: src/agent/graph.py:290-351; .planning/ROADMAP.md:453-457] | Phase 56 for active graph debt. [VERIFIED: tests/architecture/graph_baseline.py:51-56] |
| `src/agent/nodes/generate_recommendation.py` import/test surface | `recommendation_generation` | Keep as narrow compatibility wrapper or legacy module only if plan records surface, reason, trace projection, validation, and delete phase. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:179-192; .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:18-23] | Phase 58. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:104-108] |
| `llm_outputs["generate_recommendation"]` and trace step `node="generate_recommendation"` | `recommendation_generation` | New active runs should emit canonical output/trace identity or project canonically; historical rows should remain readable through graph vocabulary/API projection. [VERIFIED: src/agent/nodes/generate_recommendation.py:79-96; src/agent/nodes/generate_recommendation.py:260-277; src/agent/graph_vocabulary.py:197-207] | Phase 58 for legacy projection cleanup if no longer needed. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:229-250] |
| API/SSE node labels and payload extraction keyed to `generate_recommendation` | `recommendation_generation` | Add canonical `recommendation_generation` support while retaining legacy display fallback. [VERIFIED: src/api/routers/agent_runs.py:56-70; src/api/routers/agent_runs.py:1191-1195] | Phase 58 for legacy display cleanup. [VERIFIED: docs/current-langgraph-architecture.md:88-107] |
| Frontend timeline local node messages | `recommendation_generation` | Add `recommendation_generation` label if current UI consumes node names from SSE; retain legacy label if historical events are displayed. [VERIFIED: frontend/src/components/timeline/TimelineStep.tsx:5-15] | Phase 58 for legacy display cleanup. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:104-108] |
| Eval/diagnostic scripts using `generate_recommendation` | `recommendation_generation` | Update current graph-contract/eval paths to canonical node where they assert current runtime; keep explicit historical fixtures only where labelled. [VERIFIED: scripts/eval_agent.py:412-520; scripts/diagnose_latency.py:90-110] | Phase 58 for historical fixture cleanup if needed. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:229-250] |
| `assess_risk_and_approval` active node and route destination | `risk_gate` | Do not rename in Phase 56; preserve as only active legacy row after recommendation cutover. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:39-42; tests/architecture/graph_baseline.py:57-61] | Phase 57. [VERIFIED: .planning/ROADMAP.md:462-476] |

## Common Pitfalls

### Pitfall 1: Updating Router Return Values But Not Graph Path Maps

**What goes wrong:** `route_after_investigate` and `route_after_rag_context` already return `recommendation_generation`, but the graph currently maps that route value to `generate_recommendation`. [VERIFIED: src/agent/routing.py:553-566; src/agent/routing.py:708-750; src/agent/graph.py:330-348]

**Why it happens:** Route values and active graph destination names are separate in LangGraph `add_conditional_edges(...)`. [VERIFIED: src/agent/graph.py:330-348]

**How to avoid:** Update active graph path maps and architecture baseline together. [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:93-151]

**Warning signs:** `tests/architecture/graph_baseline.py` still contains `"recommendation_generation": "generate_recommendation"` after Plan 56-02. [VERIFIED: tests/architecture/graph_baseline.py:85-99]

### Pitfall 2: Treating `proposed_action` Alone as Claim Verification Success

**What goes wrong:** A `verified/continue` bundle with `proposed_action` but no explicit action-claim allowance can currently route toward risk. [VERIFIED: src/agent/routing.py:580-592; tests/agent/rag_context/test_routing.py:205-267]

**Why it happens:** `_route_after_claim_verify` currently treats `_has_proposed_action(state)` as sufficient for risk routing once the bundle status is `verified/continue`. [VERIFIED: src/agent/routing.py:580-592]

**How to avoid:** Require explicit `action_recommendation` claim result with `allows_action_recommendation is True` when a proposed action or action claim is present. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:29-33; src/agent/routing.py:641-650]

**Warning signs:** Tests still expect `route_after_claim_verify({"claim_verification_bundle": {"overall_status": "verified", "route": "continue"}, "proposed_action": {...}}) == "assess_risk_and_approval"` without action claim result. [VERIFIED: tests/agent/rag_context/test_routing.py:205-267]

### Pitfall 3: Letting RAG Status Drift Between Router and Schema

**What goes wrong:** `src/agent/routing.py` duplicates the finite RAG status set instead of deriving it directly from `src.knowledge.schemas.RAG_CONTEXT_STATUSES`. [VERIFIED: src/agent/routing.py:23-34; src/knowledge/schemas.py:73-84]

**Why it happens:** Both definitions currently match, but future changes can diverge silently. [VERIFIED: src/agent/routing.py:23-34; tests/agent/test_rag_context_routing.py:13-31]

**How to avoid:** Import or test equality against schema statuses. [VERIFIED: tests/agent/test_rag_context_routing.py:7-31]

**Warning signs:** A new status appears in `VerifiedEvidencePackageV1.status` tests but not in router totality tests. [VERIFIED: tests/knowledge/test_verified_evidence_package.py:97-180]

### Pitfall 4: Leaking Debug or Verifier Projections Into User/API Surfaces

**What goes wrong:** `verified_evidence_package.debug_projection` or claim verifier debug payloads could leak through final/API/trace projections if safe projection boundaries are bypassed. [VERIFIED: src/agent/nodes/final_response.py:35-46; tests/test_agent_runs_api.py:466-487; tests/test_trace_api.py:640-657]

**Why it happens:** The package intentionally carries prompt/verifier/replay/debug projections with different audiences. [VERIFIED: src/knowledge/schemas.py:126-145; docs/contract-spec.md:896-898]

**How to avoid:** Keep `final_response` and API projection consuming only safe fields and add regression cases for Phase 56-specific gate failures. [VERIFIED: src/agent/nodes/final_response.py:403-470]

**Warning signs:** Tests assert `"DEBUG_PROJECTION_SHOULD_NOT_LEAK"` or `"VERIFIER_PROJECTION_SHOULD_NOT_LEAK"` appears in response/API output. [VERIFIED: tests/test_agent_runs_api.py:466-487; tests/test_trace_api.py:640-657]

### Pitfall 5: Planning Phase 57 or Phase 58 Early

**What goes wrong:** Renaming `assess_risk_and_approval` to `risk_gate` or deleting all compatibility aliases in Phase 56 would violate phase boundaries. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:104-108; .planning/ROADMAP.md:462-489]

**Why it happens:** Phase 56 moves one active legacy graph row, while the final no-debt gate remains later. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:164-177; .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:229-250]

**How to avoid:** After Phase 56, architecture baseline should show `recommendation_generation` as active runtime and `assess_risk_and_approval` as the remaining active legacy row. [VERIFIED: tests/architecture/graph_baseline.py:51-61]

**Warning signs:** `MIGRATION_MODE_LEGACY_NODE_MAP` is empty in Phase 56, or `risk_gate` is registered in active graph before Phase 57. [VERIFIED: tests/architecture/graph_baseline.py:51-61; .planning/ROADMAP.md:462-476]

## Code Examples

### Source-Verified Fail-Closed RAG Router

```python
# Source: src/agent/routing.py:553-566
def _route_after_rag_context(state: AgentState) -> str:
    if _missing_required_validation_inputs(state):
        return "clarification_gate"

    status = _rag_context_status(state)
    if status not in RAG_CONTEXT_STATUSES:
        return "final_response"
    if status == "verified":
        return "recommendation_generation"
    if status == "not_required":
        return "recommendation_generation" if not _policy_evidence_required(state) else "final_response"
    if status == "partial":
        return "recommendation_generation" if _partial_rag_context_can_generate(state) else "final_response"
    return "final_response"
```

### Source-Verified Claim Bundle Gate To Strengthen

```python
# Source: src/agent/routing.py:580-592
def _route_after_claim_verify(state: AgentState) -> str:
    if _claim_verify_has_blocked_claims(state):
        return "final_response"
    bundle = _claim_verification_bundle(state)
    if not bundle:
        return "final_response"
    route = bundle.get("route")
    overall_status = bundle.get("overall_status")
    if route != "continue" or overall_status not in {"verified", "not_required"}:
        return "final_response"
    if _has_proposed_action(state) or _has_risk_signal(state) or _has_verified_action_recommendation(state):
        return "assess_risk_and_approval"
    return "final_response"
```

Phase 56 should strengthen the final `if` condition so proposed actions cannot proceed without explicit verified action-claim allowance when action claims are present. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:29-33]

### Source-Verified Strict Claim Bundle

```python
# Source: src/knowledge/schemas.py:185-195
class ClaimVerificationBundleV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["claim_verification_bundle.v1"] = "claim_verification_bundle.v1"
    overall_status: ClaimBundleOverallStatus
    route: ClaimBundleRoute
    claim_results: list[ClaimVerificationResultV1] = Field(default_factory=list)
    blocked_claims: list[str] = Field(default_factory=list)
    safe_support_refs: list[EvidenceRefV1] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    verifier_policy_version: str
```

### Recommended Phase 56 Vocabulary Alias Pattern

```python
# Source pattern: src/agent/graph_vocabulary.py:48-55 and :99-114.
_PHASE56_RECOMMENDATION_ALIAS_REASON_CODES = (
    "PHASE_56_COMPATIBILITY_ALIAS",
    "HISTORICAL_TRACE_PROJECTION",
    "IMPORT_TEST_COMPATIBILITY",
    "DELETE_BY_PHASE_58",
)
```

## State of the Art

| Old Approach | Current / Target Approach | When Changed | Impact |
|--------------|---------------------------|--------------|--------|
| Active legacy `generate_recommendation` registered in graph | Active canonical `recommendation_generation` registered in graph | Phase 56 target [VERIFIED: .planning/ROADMAP.md:446-457] | Closes CAGM-07 active node debt while preserving narrow compatibility surfaces. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:18-23] |
| Route value `recommendation_generation` mapped to `generate_recommendation` destination | Route value and destination both canonical | Phase 56 target [VERIFIED: src/agent/graph.py:330-348] | Removes active route-map legacy destination without changing router return vocabulary. [VERIFIED: src/agent/routing.py:21-35] |
| Claim action path can be triggered by `proposed_action` once bundle is `verified/continue` | Action path requires canonical bundle success plus explicit action-claim allowance when action claims are present | Phase 56 target [VERIFIED: src/agent/routing.py:580-592; .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:29-33] | Prevents unsupported action claims from entering risk/approval/action paths. [VERIFIED: docs/contract-spec.md:666-667] |
| Phase 55 left Phase 56/57 active legacy rows open | Phase 56 should close only recommendation row and leave Phase 57 row | Phase 55 verification handoff [VERIFIED: .planning/phases/55-memory-context-load-cutover/55-VERIFICATION.md:20-31; .planning/phases/55-memory-context-load-cutover/55-VERIFICATION.md:95-97] | Prevents accidental Phase 57/58 scope bleed. [VERIFIED: .planning/ROADMAP.md:462-489] |

**Deprecated/outdated for Phase 56:**

- Treating `generate_recommendation` as the active registered graph node is outdated after Phase 56 planning starts. [VERIFIED: .planning/ROADMAP.md:453-457]
- Treating RAG evidence package status as equivalent to generated-claim support is invalid; `claim_verify` owns post-generation material claim support. [VERIFIED: docs/target-agent-platform-architecture-plan.md:425; docs/contract-spec.md:636-638]
- Using bare `pytest` or bare `python -m pytest` is invalid validation in MOCA. [VERIFIED: AGENTS.md:24-29]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Live/local/production DB may contain historical `generate_recommendation` trace rows, but no live DB was queried during research. [ASSUMED] | Runtime State Inventory | If false, compatibility projection is still harmless; if true and projection is omitted, historical traces/API views may regress. |
| A2 | No external OS service registrations outside the repository embed `generate_recommendation`. [ASSUMED] | Runtime State Inventory | If false, an operator must update external service labels; code changes alone would not fully align runtime naming. |

## Open Questions (RESOLVED)

1. **Should frontend timeline display be included in Phase 56 or left as historical UI compatibility?** [VERIFIED: frontend/src/components/timeline/TimelineStep.tsx:5-15]
   - RESOLVED: Include frontend/API label support in Plan `56-04`; current-run `recommendation_generation` labels must be supported while legacy `generate_recommendation` display remains readable until Phase 58.
   - What we know: Backend API/SSE currently has a `generate_recommendation` node message and target projection, and frontend has a local `generate_recommendation` message. [VERIFIED: src/api/routers/agent_runs.py:56-70; src/api/routers/agent_runs.py:1140-1152; frontend/src/components/timeline/TimelineStep.tsx:5-15]
   - What's unclear: Whether frontend currently receives `target_node_name` or uses only `node_name` for display in all views. [ASSUMED]
   - Recommendation: Include frontend/API label support in Plan `56-04` if current-run node names become canonical; retain legacy display fallback until Phase 58. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:104-108]

2. **Should `recommendation_generation` dual-write `llm_outputs["generate_recommendation"]` for compatibility?** [VERIFIED: src/agent/nodes/generate_recommendation.py:260-277; src/agent/nodes/generate_recommendation.py:415-423]
   - RESOLVED: Plan `56-01` requires active canonical behavior to write `llm_outputs["recommendation_generation"]` and not add a new `llm_outputs["generate_recommendation"]`; any legacy surface is narrow import/test compatibility only.
   - What we know: Active legacy implementation writes `llm_outputs["generate_recommendation"]`. [VERIFIED: src/agent/nodes/generate_recommendation.py:260-277]
   - What's unclear: Which downstream consumers read that exact key outside tests and historical trace views. [VERIFIED: repository `rg -n "llm_outputs.*generate_recommendation|generate_recommendation" --glob '!uv.lock'`; ASSUMED: not all runtime consumers were dynamically exercised]
   - Recommendation: Prefer canonical `llm_outputs["recommendation_generation"]` for active runs and keep a documented legacy mirror only if tests/API readers prove it is needed. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:179-192]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | MOCA-approved Python/test entrypoint | yes | 0.11.2 | `.venv/bin/pytest` only after confirming repo venv. [VERIFIED: `uv --version`; AGENTS.md:24-29] |
| Python via `uv run` | Source/test execution | yes | 3.12.13 | None needed. [VERIFIED: `UV_CACHE_DIR=/tmp/uv-cache uv run python --version`] |
| `pytest` | Unit/architecture/API tests | yes | 9.0.3 | None; must use `uv run`. [VERIFIED: local importlib.metadata command; AGENTS.md:24-29] |
| `pytest-asyncio` | Async node/service tests | yes | 1.3.0 | None. [VERIFIED: local importlib.metadata command] |
| `langgraph` | Graph runtime | yes | 1.1.10 | No alternative recommended. [VERIFIED: local importlib.metadata command; src/agent/graph.py:18-20] |
| `pydantic` | Strict DTO validation | yes | 2.13.4 | No alternative recommended. [VERIFIED: local importlib.metadata command; src/knowledge/schemas.py:14-15] |
| `ruff` | Lint closeout | yes | 0.15.12 | None. [VERIFIED: local importlib.metadata command] |
| `rg` | Source audit | yes | 14.1.1 | Use slower grep only if missing. [VERIFIED: `rg --version`] |

**Missing dependencies with no fallback:** None found. [VERIFIED: local environment audit commands]

**Missing dependencies with fallback:** None found. [VERIFIED: local environment audit commands]

## Validation Architecture

Validation is enabled because `.planning/config.json` sets `workflow.nyquist_validation` to `true`. [VERIFIED: .planning/config.json:15-31]

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 with pytest-asyncio 1.3.0. [VERIFIED: local importlib.metadata command] |
| Config file | `pyproject.toml`. [VERIFIED: pyproject.toml:54-55] |
| Quick run command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph_vocabulary.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py -q --tb=short` [VERIFIED: test files exist via `rg --files tests`] |
| Full suite command | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_graph_vocabulary.py tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py tests/agent/test_nodes/test_generate_recommendation.py tests/agent/test_nodes/test_claim_verify.py tests/agent/test_phase22_recommendation_integration.py tests/knowledge/test_facade_integration.py -q --tb=short` [VERIFIED: test files exist via `rg --files tests`] |
| Lint command | `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent src/knowledge src/api tests/architecture tests/agent tests/knowledge tests/test_graph_routing.py tests/test_trace_api.py tests/test_agent_runs_api.py` [VERIFIED: Phase 55 used Ruff closeout; .planning/phases/55-memory-context-load-cutover/55-VERIFICATION.md:71-75] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CAGM-07 | Active graph registers `recommendation_generation`, not `generate_recommendation`; Phase 57 row remains. [VERIFIED: .planning/ROADMAP.md:453-457] | architecture/static | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py -q --tb=short` | yes [VERIFIED: tests/architecture/test_canonical_graph_baseline.py:1-168; tests/agent/test_graph.py:1-1327] |
| CAGM-07 | Route maps from `investigate` and `rag_context_build` target canonical destination. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:18-23] | architecture/static + router | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/test_graph_routing.py -q --tb=short` | yes [VERIFIED: tests/test_graph_routing.py:746-873] |
| CAGM-07 | RAG statuses fail closed for missing/unknown/unsafe states and allow `partial` only for low-risk answer-only/policy-QA flows. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:24-28] | router/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_rag_context_routing.py tests/knowledge/test_verified_evidence_package.py -q --tb=short` | yes [VERIFIED: tests/agent/test_rag_context_routing.py:13-96; tests/knowledge/test_verified_evidence_package.py:97-234] |
| CAGM-07 | Material claims, user-visible claims, and proposed actions pass through `claim_verify`. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:29-33] | router/unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/rag_context/test_routing.py tests/knowledge/test_claim_verification_bundle.py -q --tb=short` | yes [VERIFIED: tests/agent/rag_context/test_routing.py:182-337; tests/knowledge/test_claim_verification_bundle.py:101-523] |
| CAGM-07 | Final/API projection uses safe bundle/package fields and does not leak debug verifier projections. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:35-37] | response/API/trace | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_trace.py tests/test_trace_api.py tests/test_agent_runs_api.py -q --tb=short` | yes [VERIFIED: tests/test_trace_api.py:640-657; tests/test_agent_runs_api.py:466-487] |
| CAGM-07 | Compatibility ledger records `generate_recommendation -> recommendation_generation` and keeps Phase 57/58 boundaries. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:179-192] | static/docs | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_graph_vocabulary.py tests/architecture/test_canonical_graph_baseline.py -q --tb=short` | yes [VERIFIED: tests/agent/test_graph_vocabulary.py:1-180; tests/architecture/test_canonical_graph_baseline.py:63-151] |

### Sampling Rate

- **Per task commit:** Run the quick command above. [VERIFIED: .planning/phases/55-memory-context-load-cutover/55-VALIDATION.md:28-33]
- **Per wave merge:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/architecture/test_canonical_graph_baseline.py tests/agent/test_graph.py tests/test_graph_routing.py tests/agent/test_rag_context_routing.py tests/agent/rag_context/test_routing.py tests/knowledge/test_verified_evidence_package.py tests/knowledge/test_claim_verification_bundle.py tests/agent/test_graph_vocabulary.py -q --tb=short`. [VERIFIED: Phase 55 focused suite pattern; .planning/phases/55-memory-context-load-cutover/55-VALIDATION.md:28-33]
- **Phase gate:** Run the full suite command, Ruff command, artifact command scan, and `UV_CACHE_DIR=/tmp/uv-cache uv run git diff --check`. [VERIFIED: .planning/phases/55-memory-context-load-cutover/55-VERIFICATION.md:69-75]

### Wave 0 Gaps

- [ ] Add or adapt canonical node tests for `recommendation_generation` trace/output identity while keeping legacy import compatibility explicit. [VERIFIED: src/agent/nodes/generate_recommendation.py:79-96; tests/agent/test_nodes/test_generate_recommendation.py:566-625]
- [ ] Update `tests/architecture/graph_baseline.py` and `tests/architecture/test_canonical_graph_baseline.py` to remove active legacy `generate_recommendation` row while preserving `assess_risk_and_approval`. [VERIFIED: tests/architecture/graph_baseline.py:31-116; tests/architecture/test_canonical_graph_baseline.py:63-151]
- [ ] Add graph vocabulary tests for `generate_recommendation -> recommendation_generation` with Phase 56 reason codes and `DELETE_BY_PHASE_58`. [VERIFIED: src/agent/graph_vocabulary.py:41-55; tests/agent/test_graph_vocabulary.py:13-24]
- [ ] Add claim-router negative test where `proposed_action` plus `verified/continue` bundle but no allowed action-recommendation result returns `final_response`. [VERIFIED: src/agent/routing.py:580-592; tests/agent/rag_context/test_routing.py:205-267]
- [ ] Add API/SSE/trace tests for current-run `recommendation_generation` display and legacy `generate_recommendation` historical projection. [VERIFIED: src/api/routers/agent_runs.py:56-70; src/api/routers/agent_runs.py:1140-1152]

### Approved Artifact Command Scan

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -c 'from pathlib import Path; bad=[str(p) for p in Path(".planning/phases/56-recommendation-generation-and-rag-claim-status-alignment").glob("56-*.md") if any(line.strip().startswith(("pytest","python -m pytest")) for line in p.read_text().splitlines())]; assert not bad, bad'
```

This mirrors the Phase 55 artifact command scan style and avoids invalid bare pytest instructions. [VERIFIED: .planning/phases/55-memory-context-load-cutover/55-VALIDATION.md:45-49; AGENTS.md:24-29]

## Security Domain

Security enforcement is enabled because `.planning/config.json` does not set `security_enforcement` to `false`. [VERIFIED: .planning/config.json:1-43]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no direct change | Preserve trusted context injection; Phase 56 must not let user/LLM state override identity. [VERIFIED: docs/contract-spec.md:842-849] |
| V3 Session Management | no direct change | Preserve Phase 55 memory/session context boundaries. [VERIFIED: .planning/phases/55-memory-context-load-cutover/55-VERIFICATION.md:20-31] |
| V4 Access Control | yes | Unauthorized/invalid-scope RAG states fail closed; RAG evidence cannot replace BusinessFact authority for business/action claims. [VERIFIED: src/agent/routing.py:553-566; tests/knowledge/test_claim_verification_bundle.py:176-204; tests/knowledge/test_claim_verification_bundle.py:445-508] |
| V5 Input Validation | yes | Pydantic strict DTOs for `VerifiedEvidencePackageV1`, `MaterialClaimV1`, and `ClaimVerificationBundleV1`. [VERIFIED: src/knowledge/schemas.py:126-195] |
| V6 Cryptography / Integrity | yes, existing evidence integrity | Use existing evidence text hash validation/status mapping; do not hand-roll new hash semantics. [VERIFIED: src/knowledge/schemas.py:32-70; src/knowledge/service.py:727-758] |

### Known Threat Patterns for Phase 56

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Legacy node alias bypasses canonical graph gate | Tampering | Active graph registers only `recommendation_generation`; legacy alias exists only through vocabulary/API projection. [VERIFIED: src/agent/graph.py:278-389; src/agent/graph_vocabulary.py:197-207] |
| Unauthorized/stale/conflicting evidence enters action path | Elevation of privilege / Tampering | `route_after_rag_context` returns safe final/clarification path for unsafe statuses; `generate_recommendation` refuses unusable packages. [VERIFIED: src/agent/routing.py:553-566; src/agent/nodes/generate_recommendation.py:327-423] |
| LLM-generated policy/business/action claim skips verifier | Tampering | `route_after_recommendation` sends material claims, proposed action, and user-visible claims to `claim_verify`. [VERIFIED: src/agent/routing.py:569-577; tests/agent/rag_context/test_routing.py:182-202] |
| Proposed action reaches risk without verified action claim support | Elevation of privilege | Strengthen `route_after_claim_verify` to require explicit action-claim `allows_action_recommendation` when action claims/proposed action are present. [VERIFIED: src/agent/routing.py:580-592; .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:29-33] |
| Debug/verifier projection leaks to user/API output | Information disclosure | `final_response` and API projection must consume only safe projections and preserve existing leak tests. [VERIFIED: src/agent/nodes/final_response.py:403-470; tests/test_agent_runs_api.py:466-487; tests/test_trace_api.py:640-657] |
| RAG evidence replaces merchant-scoped business fact authority | Elevation of privilege / Information disclosure | Claim verifier requires BusinessFact refs/results for business/action claims; tests block policy-only support for business/action claims. [VERIFIED: tests/knowledge/test_claim_verification_bundle.py:176-204; tests/knowledge/test_claim_verification_bundle.py:445-508] |

## Threat Model Inputs for Planner

| Threat ID | Threat | Existing Control | Planner Must Add / Verify |
|-----------|--------|------------------|---------------------------|
| T-56-01 | Active graph still exposes `generate_recommendation` as runtime node. [VERIFIED: src/agent/graph.py:290-351] | Baseline tests detect active graph nodes and route maps. [VERIFIED: tests/architecture/graph_baseline.py:143-199] | Plan `56-02` must flip graph registration and baseline assertions. [VERIFIED: .planning/ROADMAP.md:453-457] |
| T-56-02 | Unsafe RAG status promotes to generation/action. [VERIFIED: src/agent/routing.py:553-566] | Router fails closed for unknown/unsafe statuses; generation rejects unusable packages. [VERIFIED: src/agent/routing.py:557-566; src/agent/nodes/generate_recommendation.py:327-423] | Add schema/router drift test and action-bound `partial` regression tests. [VERIFIED: tests/agent/test_rag_context_routing.py:13-96] |
| T-56-03 | Unsupported action claim enters risk/approval/action path. [VERIFIED: src/agent/routing.py:580-592] | Claim bundle validates blocked claims and allowed action recommendation flags. [VERIFIED: src/knowledge/schemas.py:165-195; src/knowledge/service.py:1013-1085] | Add negative router test for proposed action without explicit action-claim allowance. [VERIFIED: tests/agent/rag_context/test_routing.py:205-337] |
| T-56-04 | Legacy verifier fields override canonical claim bundle. [VERIFIED: src/agent/nodes/claim_verify.py:64-73] | `final_response` prefers claim bundle payload over RAG/legacy verifier route payloads. [VERIFIED: src/agent/nodes/final_response.py:403-427] | Add tests that legacy `verification_route=allow` cannot overcome missing/blocked `claim_verification_bundle`. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:29-33] |
| T-56-05 | Phase 57/58 scope is implemented early. [VERIFIED: .planning/ROADMAP.md:462-489] | Phase 56 context explicitly defers risk rename and final cleanup. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:104-108] | Baseline should still show `assess_risk_and_approval` as active legacy row after Phase 56. [VERIFIED: tests/architecture/graph_baseline.py:57-61] |
| T-56-06 | Historical traces become unreadable after active rename. [ASSUMED: live DB may have historical rows] | `target_graph_name` and SSE projection support target node names without rewriting `node_name`. [VERIFIED: src/agent/graph_vocabulary.py:185-207; src/api/routers/agent_runs.py:1140-1152] | Add `generate_recommendation -> recommendation_generation` vocabulary alias and trace/API tests. [VERIFIED: tests/agent/test_graph_vocabulary.py:1-180] |

## Sources

### Primary (HIGH confidence)

- `.planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md` - phase boundaries, decisions, discretion, deferred items, code-context pointers. [VERIFIED: .planning/phases/56-recommendation-generation-and-rag-claim-status-alignment/56-CONTEXT.md:6-110]
- `.planning/ROADMAP.md` - Phase 56 goal, dependency, success criteria, Phase 57/58 boundaries. [VERIFIED: .planning/ROADMAP.md:446-489]
- `.planning/REQUIREMENTS.md` - CAGM-07 requirement and pending status. [VERIFIED: .planning/REQUIREMENTS.md:53-61; .planning/REQUIREMENTS.md:79-104]
- `.planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md` - migration charter, compatibility policy, authority matrix, validation matrix, no-debt gates. [VERIFIED: .planning/phases/50-canonical-agent-graph-migration-spec-and-guardrails/50-SPEC.md:140-250]
- `.planning/phases/55-memory-context-load-cutover/55-VERIFICATION.md` and `55-VALIDATION.md` - prior handoff and approved validation style. [VERIFIED: .planning/phases/55-memory-context-load-cutover/55-VERIFICATION.md:20-31; .planning/phases/55-memory-context-load-cutover/55-VALIDATION.md:16-33]
- `docs/contract-spec.md` - target graph node/router/state writer contracts. [VERIFIED: docs/contract-spec.md:425-669; docs/contract-spec.md:842-921]
- `docs/current-langgraph-architecture.md` - current-source graph and Phase 56 compatibility row. [VERIFIED: docs/current-langgraph-architecture.md:1-115]
- `src/agent/graph.py`, `src/agent/routing.py`, `src/agent/graph_vocabulary.py`, `src/agent/nodes/*.py`, `src/knowledge/schemas.py`, `src/knowledge/service.py` - current implementation facts. [VERIFIED: src/agent/graph.py:278-389; src/agent/routing.py:509-592; src/knowledge/schemas.py:73-195; src/knowledge/service.py:508-612]
- Test suites listed in Validation Architecture - existing behavior and gaps. [VERIFIED: tests/architecture/graph_baseline.py:31-199; tests/agent/test_rag_context_routing.py:13-96; tests/knowledge/test_claim_verification_bundle.py:101-523]

### Secondary (MEDIUM confidence)

- Repository-wide `rg` audit for `generate_recommendation|recommendation_generation`, excluding `uv.lock`, found additional docs, frontend, eval, diagnostic, and archived planning references; these need classification during Plan `56-04`. [VERIFIED: local `rg` audit on 2026-07-07]
- Local environment version checks through `uv run python` and command version probes. [VERIFIED: local command outputs on 2026-07-07]

### Tertiary (LOW confidence)

- Live database or external OS/service registrations were not queried; assumptions are listed in the Assumptions Log. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - versions and project entrypoints were verified in the local environment and `pyproject.toml`. [VERIFIED: pyproject.toml:1-55; local importlib.metadata command]
- Architecture: HIGH - active graph, route maps, and target contracts were verified against source and planning artifacts. [VERIFIED: src/agent/graph.py:278-389; docs/contract-spec.md:444-669]
- RAG/claim status facts: HIGH - schemas, routers, services, and tests were read directly. [VERIFIED: src/knowledge/schemas.py:73-195; src/agent/routing.py:553-592; src/knowledge/service.py:508-612]
- Runtime-state inventory: MEDIUM - repository references were audited, but live DB and external OS/service registrations were not queried. [VERIFIED: local `rg` and `find` audits; ASSUMED: no external registrations]

**Research date:** 2026-07-07 [VERIFIED: system date]
**Valid until:** 2026-08-06 for codebase planning assumptions; re-run source audit if graph/routing changes before planning. [ASSUMED]
