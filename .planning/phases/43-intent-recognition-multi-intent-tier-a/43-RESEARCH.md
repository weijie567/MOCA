# Phase 43: Intent Recognition Multi-Intent Tier A - Research

**Researched:** 2026-07-02
**Domain:** Intent recognition policy / LangGraph agent routing
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

Source for this entire section: [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md]

### Locked Decisions

#### Locked Scope
- Add `TaskStep` and `TaskPlan` frozen dataclasses in `src/agent/intent_policy.py` beside the Phase 42 intent-layer contracts.
- Build a deterministic `TaskPlan` from the existing single LLM result (`primary_intent`, `secondary_intents`, `requested_operation`, `candidate_slots`) plus existing keyword signals. Do not add another LLM call.
- Preserve `IntentResultV3`, `docs/contract-spec.md`, and `src/agent/prompts.py` unchanged unless implementation discovers a direct conflict; if that happens, stop and report instead of editing them.
- Keep MOCA's existing five-tier `RiskTierLiteral`; do not introduce R0-R3 or any replacement risk taxonomy.
- Add `task_plan: dict | None` and `deferred_steps: list[dict]` to `AgentState` only. `AgentState` is `total=False`, so additive fields are safe.

#### Task Plan Contract
- `TaskStep.step_id` uses stable readable IDs (`s1`, `s2`, `s3`).
- `TaskStep.intent` is an `IntentLiteral`; `operation` is a `RequestedOperationLiteral`; `entities` carries that step's slots/entities; `depends_on` records upstream step IDs; `relation` is one of `root`, `dependency`, `modifier`, or `parallel`.
- `TaskPlan.steps` contains normalized executable/deferred steps only. Modifier relations are folded/dropped before final `steps`, so `relation="modifier"` must not appear in final steps.
- `TaskPlan.terminal_step_id` points at the user's terminal delivery step and must refer to a real step.
- Plan size limit is 3 steps. Invalid plans fail closed to the existing single-intent path and trace `plan_invalid_fallback_single`.

#### Normalization Rules
- The root step is the Phase 42 semantic effective intent/operation.
- Candidate secondary steps come from `IntentResultV3.secondary_intents`.
- `small_talk` as secondary is dropped and traced as `modifier_dropped:small_talk`.
- Secondary `complaint_escalation` is folded only when the root intent is one of `compensation_suggestion`, `refund_troubleshooting`, `ticket_reply_draft`, `order_status_inquiry`, or `policy_qa`; trace `modifier_folded:complaint_as_severity`.
- Folded complaint severity must leave a visible final-response safety note even when no deferred steps exist.
- `order_status_inquiry`, `refund_troubleshooting`, `policy_qa`, `ticket_reply_draft`, `compensation_suggestion`, `appeal_or_unban`, and `action_request` as secondary intents must remain independent steps unless another explicit locked rule says otherwise.
- Same-intent parallel mentions should merge into one step with combined entities where the existing entity shape allows this without losing data.

#### Execution Semantics
- The executable prefix is the contiguous prefix from `s1` whose per-step `resolve_risk_decision(...).tier == "read_only"`.
- The current turn's effective single-intent fields remain the executable prefix's last step when the prefix is non-empty; if the prefix is empty, keep `s1` as the effective single-intent step and defer the rest.
- Every step after the executable prefix goes into `deferred_steps`.
- Draft, execute, escalation, approval, and other non-read-only work in `deferred_steps` must not run in this turn.
- Existing `route_after_intent`, `route_after_slots`, investigate, clarification, and risk surfaces should continue consuming the same single effective fields.

#### Trace And Response
- `classification_trace` must include serialized `task_plan`, `executable_prefix`, `deferred_steps`, and `plan_normalization`.
- Final responses must visibly list deferred user requests and ask whether to continue.
- Deferred-step presentation is separate from `clarification_request` / missing-slot clarification and must not reuse the same reason channel.
- Folded complaint severity must be visible as a correction affordance, for example "已按'投诉情绪'处理本次诉求，如需正式升级请告知".

#### Tests And Verification
- Add focused non-DB tests covering N=1 equivalence, dependency deferral, complaint folding plus safety note, independent-query non-folding, high-risk deferral, fail-closed fallback, deferred response visibility, and small-talk dropping.
- Required verification commands:
  - `uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/architecture/test_phase32_static_contract.py -q`
  - `uv run ruff check src/agent tests/agent`
- MOCA forbids bare `pytest` and bare `python -m pytest`.

### Claude's Discretion

- Exact helper/function names are implementation discretion, except the dataclass field names are contractual.
- Exact Chinese final-response phrasing is implementation discretion as long as each deferred intent is visible and the response asks whether to continue.
- Plan split is planner discretion, but the first version must respect MOCA plan granularity rules: if implementation spans contracts, classification wiring, final-response presentation, and verification, split into dependency-ordered plans rather than one oversized plan.

### Deferred Ideas (OUT OF SCOPE)

- Tier B automatic dependency execution (`read -> read`, `read -> draft`) is deferred until tier A data/evals justify it.
- Tier C full DAG, resume, interruption, parallel execution, and per-step approval gates are deferred.
- ID-02 confidence calibration remains open; the existing `calibrated_confidence` placeholder is not a calibration implementation.
- Any contract-spec update, prompt few-shot change, or `IntentResultV3` schema change is out of scope for Phase 43.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IDR-02 | Preserve multi-intent utterances as bounded Tier A `TaskPlan` while keeping the existing single-intent route contract intact. | Implement in `intent_policy.py`, `state.py`, `classify_intent.py`, `receive_request.py`, and `final_response.py`; validate with focused policy/node/graph tests plus the required regression command. [VERIFIED: .planning/REQUIREMENTS.md:30; src/agent/intent_policy.py:47; src/agent/nodes/classify_intent.py:315; src/agent/nodes/final_response.py:647] |
</phase_requirements>

## Summary

Phase 43 should be planned as an additive backend change on top of Phase 42's existing semantic/risk/clarification layers: add `TaskStep`/`TaskPlan` contracts and deterministic plan helpers in `intent_policy.py`, then wire serialized `task_plan` and `deferred_steps` through classification state and final-response presentation without changing `IntentResultV3`, prompts, route keys, or risk-tier enums. [VERIFIED: .planning/ROADMAP.md:143; src/agent/intent_policy.py:47; src/agent/schemas.py:63; src/agent/routing.py:36]

The current single-intent data flow is already centralized: `classify_intent` calls one structured LLM returning `IntentResultV3`, `intent_result_to_state` resolves effective semantic/risk/clarification state, then `route_after_intent` and `route_after_slots` consume only the single effective fields. [VERIFIED: src/agent/nodes/classify_intent.py:660; src/agent/nodes/classify_intent.py:315; src/agent/routing.py:219; src/agent/routing.py:253]

The main planning risk is not the dataclass contract; it is compatibility with existing guards and presentation branches. `detect_pre_route` currently marks "同时/以及/顺便" multi-target wording as `multi_target_request` requiring clarification, and `final_response` has multiple early returns that must all receive deferred/safety-note decoration. [VERIFIED: src/agent/intent_policy.py:521; src/agent/routing.py:229; src/agent/nodes/final_response.py:656]

**Primary recommendation:** Plan this as three dependency-ordered units: policy contracts/normalization, classify-state execution-prefix wiring, then response/reset/tests; do not collapse it into one large plan because AGENTS.md requires split plans for multi-surface phase work. [VERIFIED: AGENTS.md:55; .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md]

## Project Constraints (from CLAUDE.md and AGENTS.md)

- Validation commands must use `uv run pytest ...`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`, or the repo `.venv` entrypoint; bare `pytest` and bare `python -m pytest` are invalid in MOCA. [VERIFIED: AGENTS.md:24]
- Ruff and ad hoc Python tooling should prefer `uv run ...` or `.venv/bin/...` to avoid PATH pollution. [VERIFIED: AGENTS.md:26]
- Intent-recognition subsystem design defects or fixes discovered during implementation must be appended to `.planning/ARCHITECTURE-DEBT.md` with evidence and status. [VERIFIED: CLAUDE.md:9; AGENTS.md:16]
- Local debug, startup, UI/API, RAG/agent/memory/tool failures found during validation must be recorded in `.planning/LOCAL-VALIDATION-ISSUES.md`. [VERIFIED: CLAUDE.md:5; AGENTS.md:11]
- Phase-level planning must split work when it crosses multiple ownership domains, waves, or verification gates; one oversized plan covering contracts, migration/wiring, presentation, security boundary, and final verification is a blocker. [VERIFIED: AGENTS.md:55]
- Phase 43 must go through full plan-phase, plan-checker, and Codex cross-review before execution. [VERIFIED: .planning/STATE.md:31; .planning/STATE.md:69]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Task plan contracts and normalization | API / Backend | - | Existing intent contracts and policy helpers live in `src/agent/intent_policy.py`; Phase 43 locked `TaskStep`/`TaskPlan` placement is beside those contracts. [VERIFIED: src/agent/intent_policy.py:47; .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md] |
| Single LLM result to effective current-turn state | API / Backend | LLM provider boundary | `classify_intent` owns the single structured LLM call and `intent_result_to_state` converts `IntentResultV3` to state. [VERIFIED: src/agent/nodes/classify_intent.py:660; src/agent/nodes/classify_intent.py:683] |
| Read-only prefix gating | API / Backend | Risk policy layer | The phase requires per-step `resolve_risk_decision(...).tier == "read_only"`; existing risk policy is in `IntentPolicyRegistry.resolve_risk_decision`. [VERIFIED: src/agent/intent_policy.py:257; src/agent/intent_policy.py:722; .planning/ROADMAP.md:153] |
| Existing route contract preservation | API / Backend | LangGraph routing | Routers consume `primary_intent`, `requested_operation`, confidence, slots, and hints; they do not know about a multi-step plan today. [VERIFIED: src/agent/routing.py:219; src/agent/routing.py:253] |
| Deferred confirmation rendering | API / Backend | User response surface | `final_response` is deterministic-template code with multiple return branches that produce user-visible text. [VERIFIED: src/agent/nodes/final_response.py:647] |
| Missing-slot clarification separation | API / Backend | Clarification node | `clarification_gate` owns `ClarificationRequest` and reason channels; deferred steps must remain separate from this channel. [VERIFIED: src/agent/nodes/clarification_gate.py:17; .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md] |

## Standard Stack

### Core

| Library / Contract | Version | Purpose | Why Standard |
|--------------------|---------|---------|--------------|
| Python | requires `>=3.12`; local `3.12.13` | Runtime for agent code and tests | The project declares Python 3.12+ and local `uv run python --version` returns 3.12.13. [VERIFIED: pyproject.toml:5; command `uv run python --version`] |
| `dataclasses.dataclass(frozen=True)` | stdlib | Immutable internal contracts for `TaskStep` and `TaskPlan` | Phase 42 contracts already use frozen dataclasses for semantic/risk/clarification policy state. [VERIFIED: src/agent/intent_policy.py:18; src/agent/intent_policy.py:47] |
| `typing_extensions.TypedDict` `AgentState` | current repo contract | Additive graph state fields | `AgentState` is `total=False` and has an explicit ephemeral reset section for per-turn fields. [VERIFIED: src/agent/state.py:55; src/agent/state.py:70] |
| Pydantic | local `2.13.4` | Keep `IntentResultV3` as strict wire schema | `IntentResultV3` is a Pydantic model with `extra="forbid"` and is out of scope for changes. [VERIFIED: src/agent/schemas.py:63; command `uv run python -c importlib.metadata`] |
| LangGraph | local `1.1.10`; pyproject `>=0.4` | Existing graph orchestration | Phase 43 preserves existing graph routes rather than introducing a plan executor. [VERIFIED: pyproject.toml:19; src/agent/graph.py:293; command `uv run python -c importlib.metadata`] |

### Supporting

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| pytest | local `9.0.3`; pyproject `>=8.0` | Unit/integration/regression tests | Use through `uv run pytest ...` only. [VERIFIED: pyproject.toml:36; command `uv run pytest --version`; AGENTS.md:24] |
| pytest-asyncio | local `1.3.0`; pyproject `>=0.23` | Async node tests | Existing async agent-node tests use `pytest.mark.asyncio`. [VERIFIED: pyproject.toml:37; tests/agent/test_nodes/test_classify_intent.py:33; command `uv run python -c importlib.metadata`] |
| ruff | local `0.15.12`; pyproject `>=0.5` | Linting | Use `uv run ruff check src/agent tests/agent`. [VERIFIED: pyproject.toml:39; command `uv run ruff --version`; .planning/intent-multi-a-codex-brief.md] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Deterministic `TaskPlan` from `IntentResultV3` | New LLM plan-decomposition call | Forbidden by locked scope and would add a new model boundary. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md] |
| Additive `task_plan` / `deferred_steps` state fields | Change `IntentResultV3` schema | Forbidden; `IntentResultV3` is a strict wire schema and must remain unchanged. [VERIFIED: src/agent/schemas.py:63; .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md] |
| Existing five risk tiers | R0-R3 risk enum | Forbidden; `RiskTierLiteral` currently has five values and must remain the risk coordinate system. [VERIFIED: src/agent/schemas.py:30; .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md] |

**Installation:** No new package install is needed for Phase 43; use the existing `uv` environment. [VERIFIED: pyproject.toml:34; command `uv --version`]

## Architecture Patterns

### System Architecture Diagram

```text
User turn
  -> receive_request
       resets per-turn state, must also reset task_plan/deferred_steps
  -> classify_intent
       detect_pre_route
       -> existing single structured LLM call -> IntentResultV3
       -> semantic effective root via existing registry precedence
       -> build_task_plan(root + secondary_intents + keyword_signals + candidate_slots)
            -> normalize modifiers
            -> validate <= 3 steps and terminal_step_id
            -> fail closed to single-intent state on invalid plan
       -> resolve per-step risk with IntentPolicyRegistry.resolve_risk_decision
       -> choose executable read-only prefix
       -> write effective single-intent fields for existing routers
       -> write task_plan/deferred_steps/classification_trace
  -> existing route_after_intent / route_after_slots
       -> clarification_gate OR session_memory_load/investigate/RAG OR final_response
  -> final_response
       -> render existing response branch
       -> append deferred-step confirmations and complaint-folding safety note
  -> User-visible response
```

All arrows and components above map to existing source ownership except the new `TaskPlan` helpers and response decorator. [VERIFIED: src/agent/nodes/receive_request.py:45; src/agent/nodes/classify_intent.py:660; src/agent/routing.py:70; src/agent/nodes/final_response.py:647]

### Recommended Project Structure

```text
src/agent/
  intent_policy.py                 # TaskStep/TaskPlan, normalization, prefix helpers
  state.py                         # additive task_plan/deferred_steps annotations
  nodes/classify_intent.py         # build/serialize plan and write effective fields
  nodes/receive_request.py         # reset per-turn plan/deferred state
  nodes/final_response.py          # append deferred confirmations/safety notes
tests/agent/
  test_intent_task_plan.py         # focused non-DB policy/normalization tests
  test_nodes/test_classify_intent.py
  test_nodes/test_final_response.py
  test_nodes/test_receive_request.py
```

This structure keeps plan construction in the policy layer and state wiring/presentation in existing nodes. [VERIFIED: src/agent/intent_policy.py; src/agent/nodes/classify_intent.py; tests/agent/test_nodes/test_classify_intent.py]

### Pattern 1: Add Contracts Beside Phase 42 Dataclasses

**What:** Add frozen `TaskStep` and `TaskPlan` next to `SemanticIntent`, `RiskDecision`, and `ClarificationDecision`; serialize them before storing in `AgentState`. [VERIFIED: src/agent/intent_policy.py:47; src/agent/state.py:55]

**When to use:** Use for internal policy output only; do not put dataclass objects directly into graph state or traces. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md]

```python
# Source: src/agent/intent_policy.py current dataclass pattern
@dataclass(frozen=True)
class TaskStep:
    step_id: str
    intent: IntentLiteral
    operation: RequestedOperationLiteral
    entities: Mapping[str, Any]
    depends_on: tuple[str, ...]
    relation: Literal["root", "dependency", "modifier", "parallel"]
```

### Pattern 2: Build Plan After Semantic Root, Before Route Decision

**What:** Build the plan in `intent_result_to_state` after `_apply_pre_route_to_semantic` establishes the effective root, but before `route_after_intent(update)` records the route decision. [VERIFIED: src/agent/nodes/classify_intent.py:323; src/agent/nodes/classify_intent.py:379]

**Why:** The route decision must reflect the executable prefix's effective single-intent fields, not the raw LLM primary or unnormalized secondary list. [VERIFIED: .planning/ROADMAP.md:149; src/agent/routing.py:219]

```python
# Source: src/agent/nodes/classify_intent.py current conversion point
semantic_before_pre_route = _semantic_from_llm_result(result, user_query)
semantic, pre_route_overrides = _apply_pre_route_to_semantic(semantic_before_pre_route, pre_route)
task_plan, plan_trace = build_task_plan(semantic, result, user_query)
effective_semantic, executable_prefix, deferred_steps = select_executable_prefix(task_plan, ...)
```

### Pattern 3: Use Risk Policy for Prefix Gating

**What:** For each normalized step, call `INTENT_POLICY_REGISTRY.resolve_risk_decision(step.intent, step.operation, ...)` and include only the contiguous prefix with tier `read_only`. [VERIFIED: src/agent/intent_policy.py:257; src/agent/intent_policy.py:722]

**Why:** Hard-coding operation names would bypass the Phase 42 risk layer and violate the locked decision to preserve the existing risk taxonomy. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md; tests/agent/test_intent_routing.py:310]

### Pattern 4: Decorate Final Response Through One Helper

**What:** Add one helper that appends deferred-step text and complaint-folding safety notes, then call it before every `final_response` return that emits user-visible text. [VERIFIED: src/agent/nodes/final_response.py:656; src/agent/nodes/final_response.py:671; src/agent/nodes/final_response.py:690; src/agent/nodes/final_response.py:720; src/agent/nodes/final_response.py:725; src/agent/nodes/final_response.py:741; src/agent/nodes/final_response.py:751]

**Why:** Multiple early returns mean a single branch edit would silently miss clarification, verification, retrieval-error, insufficient-evidence, business-fact, or completed-response paths. [VERIFIED: src/agent/nodes/final_response.py:647]

## No-Go Boundaries

- Do not add a second LLM call for planning or decomposition. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md]
- Do not change `IntentResultV3`, `docs/contract-spec.md`, or `src/agent/prompts.py`; stop and report if a direct conflict is found. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md; src/agent/schemas.py:63; src/agent/prompts.py:1]
- Do not implement automatic read-to-draft, read-to-action, dependency-chain, DAG, resume, interruption, or parallel execution behavior. [VERIFIED: .planning/intent-multi-a-codex-brief.md; .planning/ARCHITECTURE-DEBT.md:156]
- Do not replace `RiskTierLiteral` or introduce R0-R3 risk enums. [VERIFIED: src/agent/schemas.py:30; .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md]
- Do not reuse `clarification_request` or `multi_target_request` as the deferred-step presentation channel. [VERIFIED: src/agent/nodes/clarification_gate.py:47; .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Read-only prefix safety | Operation-name whitelist | `resolve_risk_decision(...).tier == "read_only"` | Existing risk policy owns operation/intent/channel safety and is already regression-tested. [VERIFIED: src/agent/intent_policy.py:722; tests/agent/test_intent_routing.py:310] |
| Secondary operation inference | New unrelated mapping table | Existing `_operation_for_selected_intent` semantics or a small public wrapper in `intent_policy.py` | Current selected-intent operation coercion already maps complaint/appeal to `escalate`, compensation to `draft_action`, and reply draft to `draft_reply`. [VERIFIED: src/agent/intent_policy.py:828] |
| Deferred display | Per-branch bespoke text | Shared final-response decoration helper | `final_response` has multiple early returns; one helper avoids branch drift. [VERIFIED: src/agent/nodes/final_response.py:647] |
| Per-turn stale state prevention | Rely on absent fields | Reset `task_plan` and `deferred_steps` in `receive_request` | `receive_request` is the existing per-turn reset owner. [VERIFIED: src/agent/nodes/receive_request.py:45] |
| Multi-intent decomposition | New model prompt or prompt edits | Deterministic derivation from existing `IntentResultV3` and keyword signals | Prompt/schema changes and new LLM calls are out of scope. [VERIFIED: src/agent/schemas.py:78; src/agent/intent_policy.py:571; .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md] |

**Key insight:** Phase 43 is a recognition-and-deferral feature; execution safety remains centralized in the existing risk and routing layers. [VERIFIED: .planning/ARCHITECTURE-DEBT.md:148; .planning/ARCHITECTURE-DEBT.md:156]

## Common Pitfalls

### Pitfall 1: `multi_target_request` Blocks Valid Tier A Plans

**What goes wrong:** User text containing "同时", "以及", or "顺便" can set `pre_route.disposition="multi_target_request"` with `requires_clarification=True`, causing routing to `clarification_gate` before a safe read-only prefix runs. [VERIFIED: src/agent/intent_policy.py:521; src/agent/routing.py:229; src/agent/routing.py:240]

**How to avoid:** For a valid `TaskPlan`, neutralize only the legacy multi-target clarification guard for that current turn; do not neutralize approval or safety-sensitive pre-route guards. [VERIFIED: src/agent/intent_policy.py:530; src/agent/intent_policy.py:540; .planning/ROADMAP.md:153]

### Pitfall 2: Storing Dataclasses in State

**What goes wrong:** LangGraph state and traces expect plain JSON-like dictionaries/lists; frozen dataclasses should be serialized before storing. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md; src/agent/nodes/classify_intent.py:129]

**How to avoid:** Add explicit serializers for `TaskStep`, `TaskPlan`, `executable_prefix`, `deferred_steps`, and `plan_normalization`. [VERIFIED: src/agent/nodes/classify_intent.py:129]

### Pitfall 3: Breaking N=1 Equivalence

**What goes wrong:** Adding plan state can accidentally alter `primary_intent`, `requested_operation`, `risk_tier`, `route_decision`, or required slots on the dominant single-intent path. [VERIFIED: .planning/ROADMAP.md:149; tests/agent/test_nodes/test_classify_intent.py:33]

**How to avoid:** Write N=1 tests that compare existing effective fields and route decision, and run the existing intent regression suite. [VERIFIED: .planning/intent-multi-a-codex-brief.md:114; tests/agent/test_intent_routing.py:310]

### Pitfall 4: Deferred Text Missing on Early Returns

**What goes wrong:** `final_response` may return before reaching the completed-response branch, so deferred confirmations can disappear for clarification, verification, no-evidence, business-fact, or error paths. [VERIFIED: src/agent/nodes/final_response.py:656; src/agent/nodes/final_response.py:671; src/agent/nodes/final_response.py:690; src/agent/nodes/final_response.py:720]

**How to avoid:** Use a single decorator helper before each return and update `llm_outputs["final_response"]["response_text"]` consistently when that key exists. [VERIFIED: src/agent/nodes/final_response.py:675; src/agent/nodes/final_response.py:712; src/agent/nodes/final_response.py:755]

### Pitfall 5: Treating Modifier Folding as Lossless

**What goes wrong:** Folding secondary `complaint_escalation` can hide a real escalation request if the model misclassified terminal intent. [VERIFIED: .planning/ARCHITECTURE-DEBT.md:142; .planning/intent-multi-a-codex-brief.md:85]

**How to avoid:** Fold only the locked whitelist and always show the complaint safety note when `modifier_folded:complaint_as_severity` appears. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md]

## Code Examples

### Plan Construction Contract

```python
# Source: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md
plan = build_task_plan(semantic, result, user_query)
if plan is None:
    plan_trace = {"fallback": "plan_invalid_fallback_single"}
    effective = semantic
else:
    prefix, deferred = executable_prefix_for_plan(plan, role=role, channel=channel, routing_hints=routing_hints)
    effective = prefix[-1] if prefix else plan.steps[0]
```

### Response Decoration Shape

```python
# Source: src/agent/nodes/final_response.py existing deterministic-template returns
response_text = _append_deferred_confirmations(
    response_text,
    deferred_steps=state.get("deferred_steps") or [],
    plan_normalization=(state.get("classification_trace") or {}).get("plan_normalization") or [],
)
```

## State of the Art

| Old Approach | Current Phase Approach | When Changed | Impact |
|--------------|------------------------|--------------|--------|
| Single winner from primary + secondary + keyword candidates | Bounded ordered `TaskPlan` plus effective single-intent compatibility fields | Phase 43 planned on 2026-07-02 | Fixes silent secondary-intent loss while keeping existing routers intact. [VERIFIED: .planning/ARCHITECTURE-DEBT.md:135; .planning/ROADMAP.md:143] |
| Multi-target wording routes to clarification | Valid Tier A plan should run safe read-only prefix and defer later steps | Phase 43 implementation requirement | Planner must explicitly handle the existing `multi_target_request` guard. [VERIFIED: src/agent/intent_policy.py:521; .planning/REQUIREMENTS.md:30] |
| Risk tier derived from selected single intent/operation | Per-step risk decision gates executable prefix, then effective fields preserve single route contract | Phase 43 implementation requirement | Prevents automatic draft/action execution while preserving route consumers. [VERIFIED: src/agent/intent_policy.py:722; .planning/ROADMAP.md:153] |

**Deprecated/outdated for Phase 43:**
- Treating `secondary_intents` as only precedence candidates is the ID-04 failure mode to fix. [VERIFIED: .planning/ARCHITECTURE-DEBT.md:135; src/agent/intent_policy.py:613]
- Treating every multi-target utterance as a clarification is incompatible with valid Tier A multi-intent handling. [VERIFIED: src/agent/intent_policy.py:521; .planning/REQUIREMENTS.md:30]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `uv` | Test/lint entrypoint | yes | 0.11.2 | None needed. [VERIFIED: command `uv --version`] |
| Python | Runtime/tests | yes | 3.12.13 via `uv run` | None needed. [VERIFIED: command `uv run python --version`] |
| pytest | Validation | yes | 9.0.3 | None; must run through `uv run`. [VERIFIED: command `uv run pytest --version`; AGENTS.md:24] |
| ruff | Lint | yes | 0.15.12 | None; must run through `uv run`. [VERIFIED: command `uv run ruff --version`; AGENTS.md:26] |

**Missing dependencies with no fallback:** None found for this repo-only phase. [VERIFIED: command outputs above]

**Missing dependencies with fallback:** None found for this repo-only phase. [VERIFIED: command outputs above]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 with pytest-asyncio 1.3.0 [VERIFIED: command `uv run pytest --version`; command `uv run python -c importlib.metadata`] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"` [VERIFIED: pyproject.toml:54] |
| Quick run command | `uv run pytest tests/agent/test_intent_task_plan.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_nodes/test_final_response.py tests/agent/test_nodes/test_receive_request.py -q` [VERIFIED: existing test layout under tests/agent; Wave 0 must add `test_intent_task_plan.py`] |
| Full suite command | `uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_policy_registry.py tests/agent/test_intent_golden_contract.py tests/agent/test_intent_routing.py tests/agent/test_nodes/test_classify_intent.py tests/agent/test_graph.py tests/architecture/test_phase32_static_contract.py -q` [VERIFIED: .planning/intent-multi-a-codex-brief.md] |
| Lint command | `uv run ruff check src/agent tests/agent` [VERIFIED: .planning/intent-multi-a-codex-brief.md] |

### Phase Requirements To Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| IDR-02 | N=1 plan preserves `primary_intent`, `requested_operation`, `risk_tier`, and route decision | unit | `uv run pytest tests/agent/test_intent_task_plan.py::test_single_intent_plan_preserves_effective_fields -q` | no, Wave 0 add [VERIFIED: .planning/intent-multi-a-codex-brief.md:114] |
| IDR-02 | Dependency example defers `ticket_reply_draft` after read prefix | unit/integration | `uv run pytest tests/agent/test_intent_task_plan.py::test_read_then_reply_draft_defers_second_step -q` | no, Wave 0 add [VERIFIED: .planning/intent-multi-a-codex-brief.md:116] |
| IDR-02 | Complaint secondary folds only on whitelist and final response shows safety note | unit + node | `uv run pytest tests/agent/test_intent_task_plan.py::test_complaint_modifier_folded_with_safety_note tests/agent/test_nodes/test_final_response.py::test_final_response_appends_complaint_modifier_note -q` | no, Wave 0 add [VERIFIED: .planning/intent-multi-a-codex-brief.md:116] |
| IDR-02 | Independent query/draft/action secondary intents remain explicit steps | unit | `uv run pytest tests/agent/test_intent_task_plan.py::test_independent_secondary_intents_are_not_folded -q` | no, Wave 0 add [VERIFIED: .planning/intent-multi-a-codex-brief.md:117] |
| IDR-02 | Execute/draft/escalate after read prefix go to `deferred_steps` and are not routed/executed in current turn | unit + graph smoke | `uv run pytest tests/agent/test_intent_task_plan.py::test_high_risk_second_step_deferred tests/agent/test_graph.py -q` | partial, Wave 0 add focused test [VERIFIED: tests/agent/test_graph.py:53; .planning/intent-multi-a-codex-brief.md:119] |
| IDR-02 | Invalid plan fails closed and traces `plan_invalid_fallback_single` | unit | `uv run pytest tests/agent/test_intent_task_plan.py::test_invalid_plan_fails_closed_to_single_intent -q` | no, Wave 0 add [VERIFIED: .planning/intent-multi-a-codex-brief.md:119] |
| IDR-02 | Deferred confirmations are visible in all final-response branches | node | `uv run pytest tests/agent/test_nodes/test_final_response.py -q` | yes, extend [VERIFIED: tests/agent/test_nodes/test_final_response.py:46; src/agent/nodes/final_response.py:647] |
| IDR-02 | `small_talk` secondary drops and traces modifier drop | unit | `uv run pytest tests/agent/test_intent_task_plan.py::test_small_talk_secondary_dropped -q` | no, Wave 0 add [VERIFIED: .planning/intent-multi-a-codex-brief.md:120] |

### Sampling Rate

- **Per task commit:** Run the smallest focused `uv run pytest ... -q` command for touched tests plus `uv run ruff check` on touched package paths. [VERIFIED: AGENTS.md:24; .planning/config.json:15]
- **Per wave merge:** Run the full required suite and ruff command from the phase brief. [VERIFIED: .planning/intent-multi-a-codex-brief.md]
- **Phase gate:** Full required suite and ruff command must be green before `/gsd-verify-work`. [VERIFIED: .planning/config.json:19; .planning/intent-multi-a-codex-brief.md]

### Wave 0 Gaps

- [ ] `tests/agent/test_intent_task_plan.py` covers policy/normalization/prefix/fail-closed cases. [VERIFIED: no existing `task_plan` tests found by `rg task_plan src tests`]
- [ ] `tests/agent/test_nodes/test_final_response.py` needs deferred-confirmation and complaint-safety-note branch coverage. [VERIFIED: tests/agent/test_nodes/test_final_response.py:46]
- [ ] `tests/agent/test_nodes/test_receive_request.py` needs reset coverage for `task_plan` and `deferred_steps`. [VERIFIED: tests/agent/test_nodes/test_receive_request.py:7; src/agent/nodes/receive_request.py:61]
- [ ] Existing graph route tests should remain unchanged unless a focused smoke test is needed for "read path + deferred draft note" behavior. [VERIFIED: tests/agent/test_graph.py:53]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no direct change | No auth/session changes in Phase 43 scope. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md; ASSUMED: ASVS category mapping] |
| V3 Session Management | no direct change | Additive per-turn fields must reset in `receive_request` to avoid checkpoint leakage. [VERIFIED: src/agent/nodes/receive_request.py:45; ASSUMED: ASVS category mapping] |
| V4 Access Control | yes | Preserve approval/action boundaries; deferred non-read-only work must not execute in current turn. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md; tests/agent/test_nodes/test_final_response.py:35; ASSUMED: ASVS category mapping] |
| V5 Input Validation | yes | Keep strict `IntentResultV3` unchanged and validate new plan fields against existing literals. [VERIFIED: src/agent/schemas.py:8; src/agent/schemas.py:21; src/agent/schemas.py:63; ASSUMED: ASVS category mapping] |
| V6 Cryptography | no direct change | Phase 43 adds no cryptographic behavior. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md; ASSUMED: ASVS category mapping] |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt/schema injection trying to write forbidden state | Tampering | Keep `IntentResultV3` strict and keep `FORBIDDEN_STATE_WRITES` filtering in classify conversion. [VERIFIED: src/agent/schemas.py:71; src/agent/nodes/classify_intent.py:55; src/agent/nodes/classify_intent.py:414; ASSUMED: STRIDE category mapping] |
| High-risk secondary request hidden behind read request | Elevation of privilege | Per-step risk gate and defer all later non-read-only steps. [VERIFIED: .planning/ROADMAP.md:153; src/agent/intent_policy.py:722; ASSUMED: STRIDE category mapping] |
| Stale deferred state leaking across turns | Information disclosure / Tampering | Reset `task_plan` and `deferred_steps` in `receive_request`. [VERIFIED: src/agent/nodes/receive_request.py:45; ASSUMED: STRIDE category mapping] |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ASVS and STRIDE category mapping labels are used as a security-review taxonomy, not as repo-owned implementation facts. | Security Domain | Security review may prefer different category labels; implementation controls remain repo-verified. |

## Open Questions (RESOLVED)

1. **RESOLVED — How should valid `TaskPlan` handling neutralize existing `multi_target_request` clarification?**
   - What we know: `detect_pre_route` flags "同时/以及/顺便" as clarification, and Phase 43 requires safe prefix execution plus deferred confirmations. [VERIFIED: src/agent/intent_policy.py:521; .planning/REQUIREMENTS.md:30]
   - Resolution: Clear only the current-turn clarification effect of `multi_target_request` after a valid `TaskPlan` is built: do not set `routing_hints["requires_clarification"]` or `routing_hints["clarification_reason"]` for this disposition, and pass a non-clarifying pre-route value into clarification decision code. Keep the original pre-route in `classification_trace`. Never clear `approval_chat_not_trusted` or `safety_sensitive`. [VERIFIED: src/agent/intent_policy.py:530; src/agent/intent_policy.py:540]

2. **RESOLVED — Should secondary-step operation inference expose a public helper?**
   - What we know: `_operation_for_selected_intent` already maps selected intents to operation defaults, but it is private. [VERIFIED: src/agent/intent_policy.py:828]
   - Resolution: Keep operation inference inside `intent_policy.py` and validate it through the public TaskPlan builder behavior. Do not require tests to import `_operation_for_selected_intent`; the builder can reuse the private helper internally or expose a narrow helper only if implementation needs a non-private seam. [VERIFIED: src/agent/intent_policy.py:828]

3. **RESOLVED — How much same-intent multi-entity merging is safe with current entity shape?**
   - What we know: current slot models mostly use scalar fields, while `IntentResultV3.candidate_slots` is a free dict. [VERIFIED: src/agent/schemas.py:80; src/agent/schemas.py:87]
   - Resolution: Merge duplicate same-intent candidates into one step only when the existing `candidate_slots` shape is already non-lossy, for example list-valued identifier fields already produced by the classifier. Do not invent list-valued IDs from separate scalar slots or change downstream slot consumption. When scalar shape prevents non-lossy entity merging, keep one same-intent step with the available entities and record `same_intent_entity_merge_limited` in plan normalization. [VERIFIED: .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md]

## Sources

### Primary (HIGH confidence)

- `.planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md` - locked decisions, no-go boundaries, tests. [VERIFIED: file read]
- `.planning/intent-multi-a-codex-brief.md` - normative implementation brief and acceptance tests. [VERIFIED: file read]
- `.planning/ARCHITECTURE-DEBT.md` - ID-04 and ID-DESIGN context. [VERIFIED: file read]
- `.planning/REQUIREMENTS.md` - IDR-02 requirement. [VERIFIED: file read]
- `.planning/ROADMAP.md` - Phase 43 goal and success criteria. [VERIFIED: file read]
- `src/agent/intent_policy.py`, `src/agent/nodes/classify_intent.py`, `src/agent/state.py`, `src/agent/routing.py`, `src/agent/nodes/clarification_gate.py`, `src/agent/nodes/final_response.py`, `src/agent/schemas.py`, `src/agent/prompts.py` - implementation surfaces. [VERIFIED: file read and rg]
- `tests/agent/` and `tests/architecture/test_phase32_static_contract.py` - existing validation patterns. [VERIFIED: file read and rg]

### Secondary (MEDIUM confidence)

- Local command outputs for tool availability: `uv --version`, `uv run python --version`, `uv run pytest --version`, `uv run ruff --version`, and package metadata probe. [VERIFIED: command output]
- Knowledge graph context was unavailable because `.planning/graphs/graph.json` does not exist. [VERIFIED: command `ls .planning/graphs/graph.json`]

### Tertiary (LOW confidence)

- ASVS/STRIDE category naming only; no external docs were browsed per user instruction. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from `pyproject.toml`, source imports, and local tool/version commands. [VERIFIED: pyproject.toml; command output]
- Architecture: HIGH - verified from current source flow and Phase 43 locked context. [VERIFIED: src/agent/nodes/classify_intent.py; src/agent/routing.py; .planning/phases/43-intent-recognition-multi-intent-tier-a/43-CONTEXT.md]
- Pitfalls: HIGH for repo-specific pitfalls, LOW only for taxonomy labels in Security Domain. [VERIFIED: src/agent/intent_policy.py:521; src/agent/nodes/final_response.py:647; ASSUMED: ASVS/STRIDE taxonomy]

**Research date:** 2026-07-02
**Valid until:** 2026-08-01 for repo-internal implementation facts; re-check if Phase 42/43 source files change before planning. [VERIFIED: current file reads and git status clean before write]
