# Phase 10: State Lifecycle + Routing Migration - Research

**Researched:** 2026-06-11
**Domain:** LangGraph state lifecycle enforcement, deterministic router totality, bounded-loop investigate node merge
**Confidence:** HIGH (all findings verified against live repo + canonical spec; no external library uncertainty)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Phase 10 absorbs the investigation merge. The three investigation nodes collapse into one registered `investigate` node; they become internal conceptual sub-capabilities still callable inside the loop. Externally `investigate` is a single deterministic node (fixed in/out edges + single `route_after_investigate`).
- **D-02:** Rationale for merge (not three-nodes-each-looping): the target scenario is cross-data-source dynamic investigation ("check logistics, then decide whether to pull policy") — three fixed-chained nodes cannot express cross-node dynamics at the router layer.
- **D-03:** `max_iterations` hard cap, enforced; on hit, lifecycle status stays `completed` but `termination_reason=max_iterations_reached` is written.
- **D-04:** Loop allowlist contains read-only tools only (union of the three old node allowlists: get_order, get_refund_case, get_ticket, get_logistics, get_merchant_risk, search_policy, search_sop, search_case_memory). Loop never calls allowlist-external or any write tool.
- **D-05:** Every loop tool/RAG call emits an independent trace event (§17.2).
- **D-06:** Loop produces only `proposed_action` candidates; never touches a write tool; never bypasses risk/approval/executor gates.
- **D-07:** Externally deterministic — loop does not change the node's outward routing contract.
- **D-08:** permission denied is **fine-grained, NOT one-shot-to-final**. Blocks only the part of the answer that depends on the denied resource; facts legitimately obtained in the same loop are preserved. Denied resources must not appear in the reply and must not leak via inference. TrustedContext scope checks remain (`docs/contract-spec.md:935-937`). This REPLACES the §9 draft's placeholder one-shot `permission denied -> final`.
- **D-09:** Classify by call nature: `search_policy` / `search_sop` → `rag_retrieval_*`; `get_*` → `tool_call_*`. A single operation does NOT emit both event families.
- **D-10:** `search_case_memory` emits `rag_retrieval_*` (retrieval call by nature). Planner/Phase 15 to confirm pairing.
- **D-11:** `termination_reason` is added to §9.4 `investigate` State writes AND §10.1 canonical field registry, reset each turn. The router reads it from state (routers do not read trace payload).
- **D-12:** `max_iterations` configured per-intent (GAD-02 field) + a global hard ceiling backstop. Default 3 / ceiling 5 are **discussion parameters only, NOT normative** — final values set during planning/eval. NOT per-tenant.

### Claude's Discretion
- **CD-01:** `long_term_memory_retrieve` stays an independent node (`fixed -> investigate`), NOT merged into the loop. Its identity/scope semantics belong to Phase 16; it is a pre-load, not fetch-on-demand. Planner may proceed unless evidence contradicts.
- **CD-02:** `iteration` annotation lands in the Phase 10 emitter at first emit (not deferred to Phase 15), placed in `redacted_payload` (not envelope top-level). Non-schema-breaking.

### Deferred Ideas (OUT OF SCOPE)
- max_iterations default/ceiling exact values → planning/eval (D-12 sets shape, not final numbers).
- migration-plan.md:16 "不引入自由 ReAct" acceptance line → reword during spec promotion only; not a Phase 10 code task.
- Spec promotion sequencing (raising §9 draft into contract-spec) — **already done** (commit ad17301); see State of the Art.
- Multi-step QA evidence retrieval (GAD-02 future option) — separate deferred option, not Phase 10.

### Hard Red Line (do not weaken)
Write-action side (refund/coupon/ban/unban/close_ticket) stays deterministic + human-reviewed. Write tools are never called directly by the LLM. The bounded loop exists ONLY on the read-only investigation side and must never reach a write tool or bypass `risk_gate` / `approval_gate` / `action_draft` / `action_execution`.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STATE-01 | AgentState lifecycle enforces trusted writers, reset, merge, persistence, and cross-scope isolation. | §10.1 lifecycle matrix + canonical field registry (contract-spec.md:554-624) define every field's writer/reset/merge/persist. Current `receive_request` reset (src/agent/nodes/receive_request.py) is the seam to formalize. Identity fields (`tenant_id/user_id/role/thread_id`) are trusted-replace-only. |
| STATE-02 | Trusted identity/approval/action fields cannot be overwritten by user or LLM output. | §10.1 matrix marks Identity/Risk-approval/Action groups "never overwritten by LLM". `route_after_intent` already treats any `approval_decision` value as "untrusted invalid state" (contract-spec.md:387). IntentResultV3 adapter (§10.4) forbids whole-object merge of LLM output into state. |
| ROUTE-01 | Routers are deterministic, total, side-effect free, and return only valid node keys. | §9.0 defines canonical 7-router set; §9.5 router contract table gives inputs/precedence/outputs/safe-default for each. Current code has only 2 of 7 routers (route_after_risk, route_after_approval in graph.py:36-52). |
| ROUTE-02 | Invalid or unsafe state routes to explicit safe fallback. | §9.5 "safe default" column: each router's fallback (most → `clarification_gate` or insufficient `final_response`). `route_after_investigate` safe-final on retrieval error/no/insufficient evidence (contract-spec.md:389). |
</phase_requirements>

## Summary

Phase 10 is a **migration phase**, not greenfield. The live graph in `src/agent/graph.py` still runs the **v1.0 linear node vocabulary** (`receive_request → classify_intent → extract_slots → load_business_context → retrieve_policy_evidence → generate_recommendation → assess_risk_and_approval → ...`) with only **two routers** (`route_after_risk`, `route_after_approval`). The canonical target in `docs/contract-spec.md` §9 defines a **16-node set with 7 routers** and a merged `investigate` node. The gap between live code and target contract is large — the planner must scope which parts of the gap Phase 10 actually closes versus what later phases own.

The three things this phase delivers (per CONTEXT.md): (1) AgentState lifecycle enforcement per §10.1, (2) deterministic router totality per §9.5, and (3) the investigate agentic merge collapsing `load_business_context` + `retrieve_policy_evidence` + (a not-yet-existing case-memory node) into one bounded-loop `investigate` node with a single `route_after_investigate`.

**Two dependency facts the planner must confront before sequencing anything:**
1. **Phase 9 (BusinessToolService) is implemented.** `src/business_tools/service.py` provides `BusinessToolService.invoke_tool(...)` and `fetch_context(...)`; Phase 10 must consume this facade as the business executor behind a unified tool manager, rather than letting `investigate` branch directly to multiple services.
2. **Phase 8 is "In Progress" (4/6 plans on the ROADMAP table; STATE.md shows gap-closure executed).** `PolicyKnowledgeService` exists and is callable from `retrieve_policy_evidence.py` `[VERIFIED: src/knowledge/service.py:21]`.

**Primary recommendation:** Phase 9 has landed, so Phase 10 should add a `UnifiedToolManager` node-facing dispatch layer whose executors delegate to BusinessToolService, KnowledgeService, and future MemoryService. The safest decomposition follows migration-plan.md's already-defined **10a/10b/10c internal slices**: 10a = trusted-context + state lifecycle reset/property tests; 10b = routing + slot seam totality/determinism + empty-adapter; 10c = minimal event emitter/allocator/base table. The investigate merge spans 10b (routing) and 10c (per-call events), and the unified tool manager prevents the loop from growing ad hoc per-service branches.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| AgentState reset/merge rules | Agent orchestration (state.py + receive_request) | — | State contract is graph-internal; lifecycle owned by the node that resets (`receive_request`) and the TypedDict shape (`state.py`). |
| Trusted-field write protection | API/auth boundary + Agent orchestration | — | Identity/scope injected by trusted config (`config["configurable"]`); LLM-facing nodes must not overwrite. §8.0 TrustedContext is the trust root. |
| Router determinism/totality | Agent orchestration (graph.py routers) | — | Routers are pure functions over state; no I/O, no service calls. |
| investigate bounded loop | Agent orchestration (new investigate node) | UnifiedToolManager + service executors | The loop owns iteration/termination/planner control flow and CALLS one manager; manager executors call BusinessToolService / KnowledgeService / future MemoryService. |
| Read/retrieval tool execution | UnifiedToolManager executor layer | Service + DB/repo tier | Per §8.4/§12.4, business reads go through the Phase 9 facade and policy/RAG goes through KnowledgeService, but the node-facing dispatch path is one manager. Nodes don't touch repos or service-specific tool functions directly. |
| Minimal event emit + sequence allocator | Persistence/observability tier (new) | Agent orchestration (emit call sites) | §17.2 assigns Phase 10 ownership of envelope, base table, allocator, append API. |
| permission-denied scoping | Agent orchestration (route_after_investigate + investigate) | Service layer (tool returns permission error) | Tool reports the denial; router/node decides fine-grained blocking (D-08). |

## Standard Stack

This is an internal refactor of an existing Python/LangGraph codebase. No new libraries are needed. Verified existing stack:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | >=0.4 | StateGraph, conditional edges, checkpointer | Already the orchestration engine `[VERIFIED: pyproject.toml:19]` |
| langgraph-checkpoint-postgres | >=2.0 | AsyncPostgresSaver persistence | Already wired in graph.py:16 `[VERIFIED]` |
| pydantic | (in deps) | BusinessContextV1, KnowledgeSearchResult schemas | Existing schema layer uses BaseModel `[VERIFIED: src/knowledge/schemas.py]` |
| sqlalchemy + alembic | alembic>=1.13 | DB models + migrations (for new event table) | Existing migration chain 001-005 `[VERIFIED: src/db/migrations/versions/]` |
| pytest + pytest-asyncio | pytest>=8.0, asyncio_mode="auto" | Test framework | `[VERIFIED: pyproject.toml:29-48]` |

### Supporting (for property/totality testing)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hypothesis | NOT currently a dependency | Property-based testing for router totality + state lifecycle | Recommended for ROUTE-01 totality and STATE-01 reset property tests. `[VERIFIED: not in pyproject.toml]` — planner must decide to add it or hand-roll exhaustive table tests. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hypothesis property tests | Hand-rolled parametrized table tests over enumerated state variants | No new dep, but totality coverage is only as good as the hand-enumerated cases; hypothesis fuzzes the input space and is the stronger evidence for "total for valid state, safe for invalid state". Spec/migration-plan calls for "property tests" explicitly (10a/10b). |

**Installation (if hypothesis chosen):**
```bash
# add to pyproject.toml [project.optional-dependencies] or dev deps, pinned:
# "hypothesis>=6.100,<7"
uv pip install 'hypothesis>=6.100,<7'   # or the project's existing install path
```
`[ASSUMED]` exact hypothesis version — verify latest 6.x at plan time with `pip index versions hypothesis`. Pin before adding.

## Architecture Patterns

### System Architecture Diagram (target investigate segment)

```
                    receive_request (resets ephemeral state, mints run_id)
                            │
                    normalize_input / intent_classification
                            │
                    route_after_intent ──► clarification_gate (low confidence)
                            │            ──► final_response (small_talk/unsupported)
                            ▼
                    session_memory_load ──► slot_extraction ──► resolve_slots (helper)
                            │
                    route_after_slots ──► clarification_gate (missing required slots)
                            │
        (CD-01) long_term_memory_retrieve ──fixed──► investigate
                            │
            ┌───────────────▼──────────────────────────────────┐
            │  investigate  (single registered node)            │
            │  ┌─────────── bounded tool loop ──────────────┐   │
            │  │ LLM picks next read-only tool/RAG call      │   │
            │  │  from §12.4 allowlist                       │   │
            │  │   get_* ──► tool_call_* event (D-09)        │   │
            │  │   search_* ──► rag_retrieval_* event (D-09) │   │
            │  │  enforce max_iterations (D-03)              │   │
            │  │  on cap hit: termination_reason=            │   │
            │  │            max_iterations_reached           │   │
            │  └─────────────────────────────────────────────┘  │
            │  writes: business_context, policy_evidence,        │
            │  retrieved_evidence, retrieval_status, best_score, │
            │  case_memory, tool_results, termination_reason     │
            │  NEVER writes evidence_refs (citation validator)   │
            └───────────────┬───────────────────────────────────┘
                            ▼
                    route_after_investigate  (deterministic, reads STATE only)
                    ├─ permission denied → final_response (fine-grained, D-08)
                    ├─ missing required facts → clarification_gate
                    ├─ fact-only intent + facts present → final (business_fact_response)
                    ├─ retrieval error/no/insufficient evidence → final (insufficient_evidence_response)
                    └─ else → recommendation_generation
                            │
                    ... (risk_gate / approval_gate / action_draft / action_execution unchanged red line)
                            ▼
                    final_response → memory_write → trace_close
```

### Recommended Project Structure (delta only — match existing layout)
```
src/agent/
├── state.py            # ADD termination_reason, retrieval_status, best_score, policy_evidence,
│                       #   case_memory, primary_intent/requested_operation (align to §10.1 registry)
├── graph.py            # REPLACE linear edges with conditional routing; register investigate node + 7 routers
├── routing.py          # NEW (suggested): pure router functions + resolve_slots helper, importable for unit tests
├── nodes/
│   ├── investigate.py  # NEW: merged bounded-loop node (absorbs load_business_context + retrieve_policy_evidence)
│   ├── receive_request.py  # UPDATE reset list to match §10.1 ephemeral field set
│   └── (load_business_context.py / retrieve_policy_evidence.py become loop-internal helpers or are removed)
├── trace.py            # extend OR add emitter for minimal event envelope (§17.2 Phase 10 ownership)
└── events.py           # NEW (suggested): minimal event envelope emitter + per-run sequence allocator
src/db/migrations/versions/
└── 006_*.py            # NEW: minimal event base table (agent_trace_events initial column subset)
```

### Pattern 1: Pure router functions, separately importable
**What:** Router functions take `state` and return a node-key string with no I/O.
**When to use:** All 7 canonical routers.
**Example (current pattern, already correct shape):**
```python
# Source: src/agent/graph.py:36-44 [VERIFIED]
def route_after_risk(state: AgentState) -> str:
    risk = state.get("risk_assessment") or {}
    proposed = state.get("proposed_action")
    if risk.get("approval_required"):
        return "approval_gate"
    if proposed:
        return "execute_action"
    return "final_response"
```
The existing routers are already pure and side-effect free. ROUTE-01/02 work is: (a) add the 5 missing routers, (b) prove totality + safe-fallback with tests, (c) ensure each returns only keys present in the `add_conditional_edges` mapping.

### Pattern 2: Per-turn ephemeral reset (the STATE-01 seam)
**What:** `receive_request` returns a dict that nulls/resets all turn-scoped fields so checkpointer memory cannot leak stale context.
**Source:** `src/agent/nodes/receive_request.py:13-52` `[VERIFIED]`. Note it currently resets Phase-7 dormant `investigation_*` fields and does NOT reset the new §10.1 fields (`termination_reason`, `retrieval_status`, `best_score`, `policy_evidence`, `case_memory`) because they don't exist yet. The reset list must be updated in lockstep with the TypedDict additions.

### Pattern 3: Trusted context from `config["configurable"]`, not state-mergeable
**What:** Identity/session injected via `RunnableConfig`, read by nodes, never written by LLM output.
**Source:** `retrieve_policy_evidence.py:93-110` reads `session`, `merchant_scope` from `config["configurable"]` `[VERIFIED]`. STATE-02 formalizes that LLM/user input cannot reach these fields.

### Anti-Patterns to Avoid
- **Router doing I/O:** A router that calls a service or DB breaks side-effect-freedom (ROUTE-01). Keep all fetching inside `investigate`.
- **investigate writing `evidence_refs`:** Explicitly forbidden (contract-spec.md:378, 624). Only `recommendation_generation`/citation validator writes `evidence_refs`. The loop writes `policy_evidence`/`retrieved_evidence`/`retrieval_status`/`best_score` only.
- **Mixing `retrieval_status` and `termination_reason`:** They are separate fields with separate meaning (contract-spec.md:183, 374). Hitting max_iterations must NOT force `retrieval_status=no_evidence` — status reflects real accumulated evidence (D-03).
- **Whole-object LLM merge into state:** §10.4 forbids merging IntentResultV3 wholesale; use an explicit field-by-field adapter.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Read-tool execution + tenant/permission scoping | Custom per-tool DB access or per-service branching inside investigate | UnifiedToolManager -> BusinessToolService executor (§8.4) — implemented dependency | BusinessToolService owns business permission/scope/not_found/timeout/partial-success/invalid-response contracts, while the manager owns node-facing descriptor/allowlist/schema dispatch. Re-implementing raw business-tool access in the loop duplicates and diverges. |
| Policy/SOP retrieval | Direct `PolicyKnowledgeService.search` from investigate | UnifiedToolManager -> KnowledgeToolExecutor -> existing `PolicyKnowledgeService.search` | KnowledgeService already returns status/best_score/evidence_refs per §8.3 `[VERIFIED]`; it should be hidden behind the same node-facing manager as business tools. |
| Per-run monotonic sequence | Ad-hoc counter in state | Phase-10-owned sequence allocator (§17.2, must be concurrency-safe + monotonic) | Spec requires "strictly monotonic per run_id, continues after resume". migration-plan 10c calls for "allocator concurrency/monotonic sequence tests". |
| Property/totality test fuzzing | Manual enumerated cases only | hypothesis (if added) | Stronger totality evidence; spec explicitly says "property tests". |

**Key insight:** The largest hand-roll risk is the `investigate` loop growing node-local tool dispatch branches. The planner must NOT let Phase 10 call BusinessToolService for some tools, PolicyKnowledgeService for others, and future MemoryService through a third branch. Add one unified manager with executor adapters.

## Runtime State Inventory

This is a refactor/rename + state-contract migration. Grep finds files; it does not find runtime/registered state. Explicit findings:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data (checkpointer) | LangGraph `AsyncPostgresSaver` persists `AgentState` per `tenant_id:user_id:thread_id` thread `[VERIFIED: graph.py:16, contract-spec.md:642]`. Existing threads carry the OLD state shape (no `termination_reason` etc., and Phase-7 `investigation_*` fields). | TypedDict is `total=False`, so added fields default-absent — **reads tolerate old checkpoints**. But removing/renaming fields (`current_intent`→`primary_intent`) risks readers hitting absent keys on resumed old threads. Decide: keep backward-compatible reads or accept that pre-Phase-10 threads are not resumed. Code edit, not data migration (no migration script for checkpoint blobs is in scope). |
| Live service config | None for Phase 10. No external workflow/dashboard/ACL stores the node names. The graph is rebuilt from code at startup (`build_graph`). | None — verified: node names live only in `src/agent/graph.py` and `nodes/`, plus spec/trace docstrings. |
| OS-registered state | None. No scheduler/pm2/systemd registration references investigation node names. | None — verified by rg over src/. |
| Secrets / env vars | None reference investigation node names or the renamed fields. Trusted context (`tenant_id`, `merchant_scope`, `session`) flows via `config["configurable"]`, injected by API/auth, not env-keyed by node name. | None. |
| Build artifacts / DB schema | `AgentRun` / `AgentStep` tables persist `node_name` strings from `trace_steps` (trace.py:68,135). Old runs have rows with `node_name="load_business_context"` / `"retrieve_policy_evidence"`. New runs will write `node_name="investigate"`. There is NO `agent_trace_events` table yet `[VERIFIED: src/db/models.py has only AgentRun/AgentStep]`. | (a) NEW alembic migration `006` for the minimal-event base table (Phase 10 §17.2 ownership). (b) Historical AgentStep rows keep old node_name strings — acceptable (audit history), no backfill required for Phase 10. (c) `build_trace_summary` (trace.py:187) and `_derive_final_status` read `recommendation_draft.recommended_action` and `current_intent` — these consumers must be updated if those fields are renamed. |

**The canonical question — after every repo file is updated, what still has the old strings?**
- Postgres checkpoint blobs for in-flight threads (old AgentState shape) — tolerated by `total=False`, but rename-sensitive readers need guarding.
- `agent_runs`/`agent_steps` historical rows with old `node_name` — audit history, leave as-is.
- Nothing in OS/scheduler/secrets/external services.

## Common Pitfalls

### Pitfall 1: Treating pre-Phase-9 BusinessToolService assumptions as current
**What changed:** Phase 9 now provides `BusinessToolService.fetch_context(...)` and `invoke_tool(...)` in `src/business_tools/service.py`; the earlier no-facade assumption is stale.
**Why it happens:** CONTEXT.md and the spec §8.4 describe the *target* facade; ROADMAP shows Phase 9 at "0/TBD". The CONTEXT was written assuming Phase 9 would land first.
**How to avoid:** Phase 10 should explicitly consume the Phase 9 facade through `UnifiedToolManager`'s business executor, and consume policy/RAG through the manager's knowledge executor. Do not silently fall back to raw read tools or direct per-service branches in the node.
**Warning signs:** A task action inside `investigate` that imports/calls `BusinessToolService`, `PolicyKnowledgeService`, raw `src.agent.tools.get_order`, `get_refund_case`, `get_ticket`, or `search_policy` instead of `UnifiedToolManager`.

### Pitfall 2: Missing investigate allowlist tools
**What goes wrong:** Spec §12.4 allowlist for `investigate` includes `get_logistics`, `get_merchant_risk`, `search_sop`, `search_case_memory`. Phase 9's registry declares these names, but they have no Phase-10-backed business adapter / RAG service / memory service implementation to execute as live data-source work.
**How to avoid:** Keep the full 8-tool allowlist as the contract, but do not build new data sources in Phase 10. Business tools with missing adapters should surface as unavailable through the facade/registry contract; `search_sop` and `search_case_memory` remain loop-level unavailable/future-service cases (case memory is Phase 16 territory).
**Warning signs:** Task creating `get_logistics.py` etc. — that is data-source work likely out of Phase 10 scope.

### Pitfall 3: The live graph is not the spec graph
**What goes wrong:** Plans assume target node names (`intent_classification`, `risk_gate`, `action_draft`, `clarification_gate`, `normalize_input`, `session_memory_load`, `memory_write`, `trace_close`) exist. **None do** `[VERIFIED]`. Live names are `classify_intent`, `assess_risk_and_approval`, `execute_action`, etc.
**Why it happens:** The migration from v1.0 linear graph to the §9 target is incomplete; Phase 10 is where routing migration happens, but the full 16-node set is not all Phase 10's job (clarification=Phase 11, session_memory=Phase 12, approval state machine=Phase 13, action executor=Phase 14, trace_close/full replay=Phase 15).
**How to avoid:** Scope ROUTE-01/02 to the routers Phase 10 can actually make total given current nodes. `route_after_investigate`, `route_after_intent`, `route_after_slots` are the Phase-10-relevant new routers; `clarification_gate` as a *target* exists but may need a minimal stub since Phase 11 owns clarification logic. Confirm the node-set boundary with the planner.

### Pitfall 4: `current_intent` vs `primary_intent` field drift
**What goes wrong:** §10.1 registry names the field `primary_intent`/`requested_operation`; live code writes `current_intent` (`classify_intent.py:77`, `load_business_context.py:38`, routers/tests read `current_intent`). Renaming breaks every reader at once.
**How to avoid:** Either alias or do the rename as one atomic slice with all readers updated (graph.py, all nodes, trace.py:213, tests). This is a cross-file structural change — per project CLAUDE.md大改 line, hand it to Codex as one coordinated edit.

### Pitfall 5: permission-denied leakage (D-08 fine-grained)
**What goes wrong:** A naive implementation either dumps all facts (leaking denied resources) or one-shots to final (losing legitimate facts). D-08 requires the middle path: keep legitimately-obtained facts, suppress denied-resource content AND any inference that would leak it.
**How to avoid:** Model denial at the tool-result level (`BusinessContextV1` already carries `errors` + `missing_required_facts` + `facts` simultaneously, contract-spec.md:173-177). `route_after_investigate` reads these separately. Tests must assert denied resources do not appear in the reply and are not inferable.
**Warning signs:** A single boolean `permission_denied` flag driving the whole route — too coarse for D-08.

## Code Examples

### Existing read-tool call pattern (what the loop will wrap)
```python
# Source: src/agent/nodes/load_business_context.py:50-56 [VERIFIED]
if slots.get("order_id"):
    tools_called.append("get_order")
    result = await get_order(slots["order_id"], tenant_id, user_id, role, session)
    results.append({"tool": "get_order", **result})
    if result.get("status") == "success":
        ctx["order"] = result["data"]
        refs["order_id"] = slots["order_id"]
```

### Existing knowledge retrieval (returns status/best_score — feeds retrieval_status)
```python
# Source: src/agent/nodes/retrieve_policy_evidence.py:125-131 [VERIFIED]
service = PolicyKnowledgeService(LegacyRagKnowledgeAdapter(session))
result = await service.search(request, context)
retrieval_failed = result.status == "error"
gate_triggered = result.status == "no_evidence" or result.best_score < MIN_EVIDENCE_SCORE
# result.status is one of: strong_evidence | partial_evidence | no_evidence | error
#   → maps directly to §10.1 retrieval_status enum
```

### Tool result contract (uniform shape, drives permission-denied detection)
```python
# Source: src/agent/tools/get_order.py:11-25 [VERIFIED]
# success: {"status": "success", "data": {...}, "error": {}}
# error:   {"status": "error", "data": {}, "error": {"error_code","message","retryable","should_stop"}}
# permission denial surfaces as a specific error_code → investigate records it per-resource (D-08)
```

### Current router test pattern (extend for totality)
```python
# Source: tests/test_graph_routing.py:6-13 [VERIFIED]
def test_route_after_risk_returns_final_response_for_policy_qa_no_action():
    state = {"current_intent": "policy_qa",
             "risk_assessment": {"approval_required": False},
             "proposed_action": None}
    assert route_after_risk(state) == "final_response"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| §9 draft in `.planning/SECTION-9-AGENTIC-DRAFT.md` (non-normative) | Promoted into `docs/contract-spec.md` (LIVE normative) | commit ad17301 "feat(spec): promote §9 investigate agentic merge into contract-spec" `[VERIFIED: git log]` | **Read contract-spec.md as the source of truth.** The draft is superseded; use it only for design rationale. The draft still lists old three-node vocabulary at line 25 (a `>` quote of the pre-merge state). |
| Three investigation nodes (`business_context_fetch`/`policy_evidence_retrieve`/`case_memory_retrieve`) | Single `investigate` node + `route_after_investigate` | contract-spec.md §9.1 line 215, §9.4 line 362, §9.5 line 389 `[VERIFIED]` | The merge is normatively in the spec now. |
| Draft placeholder `permission denied -> final` (one-shot) | Fine-grained per-resource blocking (D-08) | This session's decision, now in contract-spec.md:334, 389 `[VERIFIED]` | Spec text already reflects D-08. CONTEXT.md and spec agree. |

**Deprecated/outdated in live code (to migrate):**
- Linear edges `load_business_context → retrieve_policy_evidence → generate_recommendation` (graph.py:73-76) — replaced by `investigate → route_after_investigate`.
- Node names `classify_intent`, `assess_risk_and_approval`, `execute_action` — target names are `intent_classification`, `risk_gate`+`approval_gate`, `action_execution`. (Renaming these is arguably beyond Phase 10's STATE/ROUTE scope — confirm boundary.)
- Phase-7 dormant `investigation_result`/`investigation_steps`/`investigation_trigger_reason`/`investigation_path` fields (state.py:78-81) — these were the "future bounded investigator" placeholders. Phase 10 may repurpose or replace them with the real investigate contract.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | hypothesis is the right property-test tool and an acceptable new dev dependency | Standard Stack | Low — could hand-roll table tests; no runtime impact. |
| A2 | Exact latest hypothesis 6.x version unverified | Standard Stack | Low — pin at plan time. |
| A3 | Phase 10 should NOT build the 4 missing data-source tools (get_logistics/get_merchant_risk/search_sop/search_case_memory) | Pitfall 2 | Medium — if planner decides the full allowlist must be live, scope expands significantly. Needs confirmation. |
| A4 | Renaming `current_intent→primary_intent` and live node names is in-scope is UNCERTAIN | Pitfall 3/4, State of the Art | Medium — if out of scope, Phase 10 routers keep reading `current_intent`; if in scope, it's a large coordinated edit. |
| A5 | Pre-Phase-10 checkpoint threads do not need a data migration (total=False tolerates added fields) | Runtime State Inventory | Medium — if old threads must resume cleanly after field renames, additional guarding needed. |
| A6 | `clarification_gate` may be a minimal stub in Phase 10 (Phase 11 owns clarification logic) | Pitfall 3 | Medium — affects whether route_after_intent/slots fallback targets are real nodes. |

## Open Questions (RESOLVED)

1. **Is Phase 9 a hard prerequisite, or does Phase 10 absorb a BusinessToolService seam?**
   - What we know: Phase 9 has only CONTEXT.md, no code. ROADMAP says Phase 10 "Blocked by 8/9". CONTEXT.md assumes the facade exists.
   - What's unclear: Whether the planner sequences Phase 9 first or builds an interim.
   - Recommendation: Resolve before task planning.
   - **RESOLVED:** Phase 9 landed first. Plan 04 consumes `BusinessToolService` through a UnifiedToolManager business executor; no raw-tool interim seam or `blocked_by_phase_9` remains.

2. **What is the exact node-set boundary for Phase 10 vs Phases 11-15?**
   - What we know: The 16-node target spans multiple phases (clarification=11, session_memory=12, approval=13, action=14, trace_close/replay=15).
   - What's unclear: Which target nodes Phase 10 must register (even as stubs) so its routers are total.
   - Recommendation: Phase 10 registers `investigate` + the routers it owns; fallback targets that belong to later phases get minimal safe stubs or route to existing `final_response`.
   - **RESOLVED:** Plan 05 registers `investigate` + the routers it owns; later-phase fallback targets get minimal safe stubs (`clarification_gate`) or route to the existing `final_response`.

3. **Full 8-tool allowlist vs available subset?** (see A3) — needs an explicit decision.
   - **RESOLVED:** Plan 04 registers the full 8-tool §12.4 allowlist; only 4 are available now, the other 4 are registered-but-unavailable (Phase 9 / Phase 16).

4. **Field rename scope** (`current_intent→primary_intent`, live node renames) — in or out of Phase 10? (see A4)
   - **RESOLVED:** Deferred to Phase 11 (CONTEXT). Phase 10 adds `primary_intent`/`requested_operation`; routers read both defensively; no atomic rename in Phase 10.

5. **max_iterations default/ceiling values** — D-12 defers exact numbers to planning/eval. Planner must pick values for tests (D-12 mentions discussion-only 3/5).
   - **RESOLVED:** Plan 04 sets default 3 / ceiling 5 (non-normative per D-12).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL (test DB) | conftest fixtures, checkpointer, new event table | Assumed (conftest builds test DB) `[VERIFIED: tests/conftest.py:30]` | — | none |
| langgraph | graph assembly | ✓ | >=0.4 | — |
| PolicyKnowledgeService | investigate policy retrieval | ✓ | — | — |
| UnifiedToolManager | investigate node-facing tool dispatch | planned in Plan 04 | `src/agent/tools/unified.py` | Single descriptor/allowlist/permission/schema/executor dispatch layer for business, policy, and future memory tools |
| BusinessToolService | business executor dependency | ✓ | `src/business_tools/service.py` | Used behind UnifiedToolManager; do not call raw read tools or BusinessToolService directly from investigate |
| get_logistics / get_merchant_risk / search_sop / search_case_memory tools | full §12.4 investigate allowlist | ✗ | — | Register in allowlist contract but mark unavailable; do not build new data sources in Phase 10 |
| MemoryService (case_memory) | search_case_memory + case_memory state field | ✗ | — | CD-01 keeps long_term_memory separate; case memory is Phase 16 territory — empty/seam only |
| hypothesis | property/totality tests | ✗ | — | Hand-rolled parametrized table tests |

**Missing dependencies with no fallback:** none hard-blocking; Phase 9 BusinessToolService is implemented.

**Missing dependencies with fallback:** the non-backed allowlist operations (`get_logistics`, `get_merchant_risk`, `search_sop`, `search_case_memory`) remain unavailable/future-service cases; MemoryService/case_memory uses an empty seam; hypothesis falls back to table tests.

## Validation Architecture

nyquist_validation is enabled (config.json `workflow.nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (`asyncio_mode="auto"`) `[VERIFIED: pyproject.toml:29-48]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_graph_routing.py -x -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ROUTE-01 | each router deterministic + total + returns valid keys only | unit/property | `pytest tests/test_graph_routing.py -x` | ✅ exists (2 routers); ❌ Wave 0 for 5 new routers + totality |
| ROUTE-02 | invalid/unsafe state → safe fallback | unit | `pytest tests/test_graph_routing.py -k fallback -x` | ❌ Wave 0 |
| STATE-01 | reset/merge/persist per §10.1; cross-scope isolation | unit/property | `pytest tests/agent/test_nodes/test_receive_request.py -x` + new state lifecycle test | ✅ receive_request test exists; ❌ Wave 0 for lifecycle/property + isolation |
| STATE-02 | trusted identity/approval/action fields un-overwritable by LLM/user | unit | `pytest tests/agent/ -k trusted -x` | ❌ Wave 0 |
| D-03 | max_iterations cap enforced; termination_reason written; status not force-degraded | unit | `pytest tests/agent/test_nodes/test_investigate.py -k max_iterations -x` | ❌ Wave 0 |
| D-04/D-06 | loop never calls allowlist-external or write tool; only proposed_action | unit | `pytest tests/agent/test_nodes/test_investigate.py -k allowlist -x` | ❌ Wave 0 |
| D-05/CD-02 | each loop call emits independent event with iteration in redacted_payload | unit | `pytest tests/agent/test_events.py -x` | ❌ Wave 0 |
| D-08 | permission denied blocks only dependent answer; legit facts preserved; no leak | unit | `pytest tests/agent/test_nodes/test_investigate.py -k permission -x` | ❌ Wave 0 |
| D-09/D-10 | get_* → tool_call_*; search_* → rag_retrieval_*; no double-emit | unit | `pytest tests/agent/test_events.py -k classification -x` | ❌ Wave 0 |
| 10c | sequence allocator monotonic + concurrency-safe per run_id | unit/integration | `pytest tests/agent/test_events.py -k sequence -x` | ❌ Wave 0 |
| SC-3 | empty session-memory adapter routing without claiming continuity | unit/integration | `pytest tests/agent/ -k empty_session -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_graph_routing.py tests/agent/test_nodes/ -x -q`
- **Per wave merge:** `pytest -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/agent/test_nodes/test_investigate.py` — covers D-03/D-04/D-06/D-08, replaces test_retrieve_policy_evidence coverage
- [ ] `tests/agent/test_events.py` — covers D-05/D-09/D-10/CD-02/10c (emitter, classification, sequence)
- [ ] `tests/test_state_lifecycle.py` — covers STATE-01/STATE-02 (reset/merge/trusted-field/isolation property tests)
- [ ] Extend `tests/test_graph_routing.py` — 5 new routers + totality + safe-fallback (ROUTE-01/02)
- [ ] `tests/agent/test_empty_session_adapter.py` — covers Success Criterion 3
- [ ] Framework: decide hypothesis install for property tests, or document table-test approach
- [ ] Fixtures: extend `tests/conftest.py` seeded_session if investigate integration tests need order/refund/ticket data (already seeds order/refund_case/ticket — `[VERIFIED: conftest.py:183-215]`)

## Security Domain

security_enforcement is not set to false in config — treat as enabled. This phase is security-relevant (trusted-field protection, RBAC permission denial, tenant isolation).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture/Trust boundaries | yes | §8.0 TrustedContext as trust root; identity from `config["configurable"]`, never LLM/user (§10.1 Identity group) |
| V2 Authentication | no (upstream API/auth owns it; Phase 10 consumes injected identity) | — |
| V4 Access Control | yes | Per-resource RBAC denial (D-08); tenant/merchant scope enforced in tools (authz.py); cross-scope isolation (STATE-01) |
| V5 Input Validation | yes | IntentResultV3 field-by-field adapter (§10.4); no whole-object LLM merge; validated-replace for routing_hints/required_slots |
| V7 Error Handling/Logging | yes | Minimal event envelope `redacted_payload` forbids raw tool output/secret/PII (§17.2); permission-denied must not leak via trace |
| V8 Data Protection | yes | Denied resources must not appear in reply or be inferable (D-08); redaction_policy_version on every event |

### Known Threat Patterns for LangGraph agent + LLM-driven loop
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| LLM overwrites trusted identity/approval field via state | Elevation of Privilege / Tampering | §10.1 trusted-replace-only; STATE-02 tests; `route_after_intent` treats any `approval_decision` as untrusted invalid state |
| LLM picks a write tool inside the loop | Elevation of Privilege | D-04/D-06 read-only allowlist hard cap; loop never reaches risk/approval/executor gates (red line) |
| Unbounded loop / resource exhaustion | Denial of Service | D-03 max_iterations hard cap + global ceiling; termination_reason audit |
| Permission-denied resource leaks via inference | Information Disclosure | D-08 fine-grained blocking; deny content + inference paths; TrustedContext scope check (contract-spec.md:935-937) |
| Cross-tenant data bleed through stale checkpoint state | Information Disclosure | Per-turn reset (receive_request); identity never merged from LLM; tenant-scoped checkpoint key (`tenant_id:user_id:thread_id`) |
| Secret/PII in trace events | Information Disclosure | §17.2 redacted_payload rules; iteration annotation must carry no raw payload |

## Sources

### Primary (HIGH confidence — verified this session)
- `docs/contract-spec.md` §8.4 (151-185), §9.0-9.6 (187-420), §10.1 (554-624), §10.4 (648-661), §11.5 (775-789), §12.4 (859-870), §17.2 (1608-1701) — canonical normative source, read directly
- `src/agent/graph.py` (1-98) — live graph, 2 routers, linear edges
- `src/agent/state.py` (1-91) — live AgentState TypedDict
- `src/agent/nodes/receive_request.py`, `load_business_context.py`, `retrieve_policy_evidence.py` — live reset + investigation nodes
- `src/agent/trace.py` (1-245) — trace persistence (no event emitter yet)
- `src/agent/tools/` (ls), `src/knowledge/service.py:21` — tool/service inventory
- `tests/test_graph_routing.py`, `tests/conftest.py`, `tests/agent/test_nodes/` (ls) — test patterns
- `.planning/STATE.md`, `.planning/ROADMAP.md` (68-76, 145-160), `.planning/REQUIREMENTS.md` (18-21), `docs/migration-plan.md` (10c slices) — phase status + requirements
- `git log` (ad17301) — §9 promotion confirmation
- `.planning/DEFERRED-DECISIONS.md` (GAD-01/GAD-02), `.planning/SECTION-9-DRAFT-REVIEW.md` — design rationale for merge + permission-denied

### Secondary / Tertiary
- None. No web sources needed — this is an internal refactor against a fully-specified canonical contract.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against pyproject.toml and existing imports.
- Architecture/contracts: HIGH — read canonical spec sections directly; live code cross-checked.
- Dependency status: HIGH — `src/business_tools/service.py` provides BusinessToolService; registry declares the full allowlist, with non-backed operations returning unavailable or deferred to future owning services.
- Scope boundary (which nodes/renames Phase 10 owns): MEDIUM — spec spans multiple phases; needs planner confirmation (Open Questions 2-4).
- Pitfalls: HIGH — each grounded in a verified file/line discrepancy.

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (stable internal contract; re-verify if contract-spec.md or phase 8/9 status changes)
