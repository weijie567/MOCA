# Phase 11: Intent / Clarification - Research

**Researched:** 2026-06-14 [VERIFIED: environment current_date]
**Domain:** LangGraph ordinary-chat intent routing, slot completeness, and clarification safety [VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md]
**Confidence:** HIGH for project contracts and code seams; MEDIUM for external framework guidance because only public docs and installed versions were checked [VERIFIED: docs/contract-spec.md; VERIFIED: src/agent/graph.py; CITED: https://docs.langchain.com/oss/python/langgraph/graph-api]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Copied from `.planning/phases/11-intent-clarification/11-CONTEXT.md` decisions section. [VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md]

- **D-01:** Adopt the `agents-from-scratch-ts` triage routing pattern at the structural level: classify first, then route. Apply this as a MOCA domain triage pattern, not as email-domain intent names or prompts.
- **D-02:** Adopt the LangGraph adaptive RAG structured router pattern: use Pydantic `BaseModel` schemas with `Literal[...]` fields for intent/router outputs. Do not parse free-form strings from the model for routing.
- **D-03:** Adopt the `agent-inbox` boundary idea: ordinary chat clarification and approval respond/decision are separate contracts. Ordinary clarification may collect missing business/user information; approval `respond` / `needs_info` remains a trusted approval lifecycle path.
- **D-04:** Do not use the customer-support notebook, email-domain prompt content, free tool-loop behavior, or memory-driven triage preferences as Phase 11 core design inputs.
- **D-05:** Reference repositories are planning constraints only. Phase 11 should not copy their domain prompt text, mailbox workflow, or agent loop structure into MOCA.
- **D-06:** Extend the current `IntentResult` into an `IntentResultV3` contract with at least `schema_version`, `primary_intent`, `requested_operation`, `confidence`, `calibrated_confidence`, `secondary_intents`, `required_slots`, `candidate_slots`, `routing_hints`, `classifier_version`, `calibration_version`, and `reason_codes`.
- **D-07:** `primary_intent` captures domain semantics; `requested_operation` captures what the user asks the system to do. Write/escalation operations must route to safety paths without overwriting the most specific domain intent.
- **D-08:** `candidate_slots` from intent classification are hints only. They must not satisfy slot completeness and must not overwrite `extracted_slots` or `active_slots`.
- **D-09:** Phase 11 must implement a deterministic pre-router before or alongside LLM classification for safety-sensitive ordinary text. Action/write/escalation/approval-looking text cannot be allowed to bypass safe routing through ordinary LLM classification.
- **D-10:** The precedence table in `docs/contract-spec.md` §11.2 is the source of truth for conflicts: specialized domain intents beat generic `action_request`, while `requested_operation` preserves action/write/escalation safety implications.
- **D-11:** Any apparent approval decision in ordinary chat is untrusted invalid state for the ordinary graph. It may become unsupported/clarification or a normal domain request, but never a trusted approval decision.
- **D-12:** Required-slot policy uses structured expressions with `all_of`, `any_of`, and `optional`; completeness is deterministic and evaluated after current explicit slots plus allowed session slots are resolved.
- **D-13:** Missing required slots route to ordinary `clarification_gate` with a concrete `clarification_request` object. The gate should ask for the minimal missing information needed to continue.
- **D-14:** Phase 11 upgrades the Phase 10 `clarification_gate` stub for ordinary clarification only. It must not handle approval `respond`, `needs_info`, old approval revision resume, or trusted approval lifecycle state.
- **D-15:** Split Phase 11 into at least these five small plans: `11-01` `IntentResultV3` schema + prompt contract; `11-02` deterministic pre-router + intent precedence; `11-03` `RequiredSlotExpression` + `route_after_intent` / `route_after_slots`; `11-04` ordinary clarification gate; `11-05` intent consistency manifest + golden tests.
- **D-16:** Each plan should explicitly include these references and exclusions: use `agents-from-scratch-ts` triage routing pattern, use LangGraph adaptive RAG structured output routing, exclude email prompts/free tool loop/memory-updated triage preferences, and preserve the safety constraint that ordinary chat cannot create `approval_result`, resume commands, or trusted approval decisions.
- **D-17:** Phase 11 must implement the `IntentResultV3 -> AgentState` mapping from `docs/contract-spec.md` §10.4 through an explicit adapter. It must not whole-object merge classifier output into `AgentState`.
- **D-18:** `confidence` writes only to `intent_confidence`. `calibrated_confidence` writes only to intent eval metadata under `llm_outputs`, together with `classifier_version` and `calibration_version`; it must not overwrite `intent_confidence`.
- **D-19:** `secondary_intents`, `required_slots`, `routing_hints`, and `candidate_slots` are schema-validated replace writes. `candidate_slots` remain slot-extraction hints only and must not satisfy completeness or overwrite `extracted_slots` / `active_slots`.
- **D-20:** The intent node must not write final answers, `extracted_slots`, `active_slots`, `risk_signals`, `approval_result`, trusted approval versions, resume commands, or tool/action outputs.
- **D-21:** `intent-golden.v1` is not optional polish. Phase 11 planning must include dataset version/hash ownership and explicit blocking/non-blocking gate semantics for intent, slot, clarification, and safety-route tests.
- **D-22:** M6 is a release gate for enabling safety-sensitive confidence-assisted routing, not a Phase 12 migration phase. Phase 11 must preserve the mapping from its artifacts to the M6 release checklist.
- **D-23:** Critical classes `critical_write`, `approval_decision`, `appeal_or_unban`, and `complaint_escalation` require per-class coverage. Each class must meet the coverage manifest minimum before it can pass; pooled metrics cannot substitute for per-class gates.
- **D-24:** Wilson gate output must use the spec-defined one-sided 95% Wilson false-negative upper bound and fixed gate status precedence: coverage missing/incomplete/invalid, below per-class minimum, false negatives present, Wilson upper exceeded, then passed. Insufficient sample size must produce `statistical_gate_not_demonstrated`, not pass.
- **D-25:** Phase 11 must maintain a machine-readable intent consistency manifest, but it is not a runtime `IntentRegistry` and must not become the source of truth for runtime routing.
- **D-26:** The manifest checker must verify every ordinary-chat taxonomy intent against the source-of-truth tables: §11.2 precedence, §11.3 required slots, §9.3 intent-level routing, evidence sufficiency coverage where applicable, and `intent-golden.v1` positive/negative examples.
- **D-27:** `small_talk` and `unsupported` may set `in_evidence_table=false` only when tests also prove they are exempt because they route directly via the intent-level routing table and do not enter `route_after_investigate`.
- **D-28:** CI/contract tests must fail on missing manifest coverage, stale dataset/hash metadata, or manifest claims that are not backed by the corresponding source-of-truth tables.
- **D-29:** GAD-02 is a Phase 11 planning input: future new intents are allowed only through an explicit admission rule covering `risk_level`, `response_mode`, `tool_allowlist`, `bounded_loop_allowed`, `max_iterations`, `routing_precedence`, and audit/replay requirements. No new intent may inherit those fields by default or be batch-enabled.
- **D-30:** GAD-03 is a Phase 11 planning input: current MVP should confirm existing coverage for `policy_qa`, order/business fact QA, and `advise` / support advice terminal paths. Phase 11 must not add a new generic QA intent or change response mode just to represent these already-covered read-only endpoints.
- **D-31:** Any future multi-step read-only QA expansion remains a separate deferred option and must re-apply GAD-01 guardrails plus GAD-02 admission rules before it is promoted into spec or implementation.

### Claude's Discretion
Copied from `.planning/phases/11-intent-clarification/11-CONTEXT.md` discretion section. [VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md]

- Exact module names for helper schemas, registry files, manifest location, and test fixture organization may follow existing codebase conventions, as long as source-of-truth boundaries and safety tests remain explicit.
- Exact confidence thresholds may start from `docs/contract-spec.md` defaults; tuning is allowed only through golden/eval evidence and must not authorize action routing by confidence alone.

### Deferred Ideas (OUT OF SCOPE)
Copied from `.planning/phases/11-intent-clarification/11-CONTEXT.md` deferred section. [VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md]

- Trusted approval lifecycle, approval `respond` / `needs_info` resume, approval version CAS, and old-revision invalidation remain Phase 13.
- PostgreSQL-backed session memory CAS and safe slot inheritance remain Phase 12. Phase 11 may define deterministic slot expression evaluation but should not claim real continuity.
- ActionSafetySnapshot, durable action draft binding, demo action executor boundary, and external execution remain later phases.
- Free tool loop for write/actions remains explicitly out of scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INTENT-01 | Intent precedence and requested-operation safety routing are deterministic and tested. [VERIFIED: .planning/REQUIREMENTS.md] | Implement `IntentResultV3`, deterministic pre-router, `route_after_intent`, graph conditional edges, and golden precedence tests. [VERIFIED: docs/contract-spec.md §9.5/§10.4/§11.2; VERIFIED: src/agent/graph.py] |
| INTENT-02 | RequiredSlotExpression and slot completeness rules are enforced. [VERIFIED: .planning/REQUIREMENTS.md] | Add `RequiredSlotExpression`, deterministic completeness helper, `route_after_slots`, and slot/clarification tests for `all_of`, `any_of`, `optional`, and candidate-slot non-use. [VERIFIED: docs/contract-spec.md §10/§11.3; VERIFIED: src/agent/nodes/extract_slots.py] |
| CLARIFY-01 | Ordinary clarification and trusted approval `needs_info` resume remain separate contracts. [VERIFIED: .planning/REQUIREMENTS.md] | Upgrade `clarification_gate` only for ordinary chat and add negative tests proving chat cannot write `approval_result`, issue `Command(resume=...)`, or produce trusted approval decisions. [VERIFIED: docs/contract-spec.md §9.6/§11.5; VERIFIED: src/agent/nodes/clarification_gate.py; CITED: https://docs.langchain.com/oss/python/langgraph/interrupts] |
</phase_requirements>

## Summary

Phase 11 should be planned as a five-plan code/config/eval phase on top of the completed Phase 10 graph foundation: V3 intent schema and adapter, deterministic safety pre-router, slot expression/router layer, ordinary clarification, and manifest/golden gate artifacts. [VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md; VERIFIED: .planning/phases/10-state-lifecycle-routing-migration/10-05-SUMMARY.md]

The current code is ready for this boundary but not yet implementing it: `src/agent/schemas.py` has a small `IntentResult`, `src/agent/nodes/classify_intent.py` uses structured output but writes `current_intent` / `last_intent`, `src/agent/graph.py` still routes linearly through session memory and slots before `investigate`, and `src/agent/routing.py` only has `route_after_investigate`. [VERIFIED: src/agent/schemas.py; VERIFIED: src/agent/nodes/classify_intent.py; VERIFIED: src/agent/graph.py; VERIFIED: src/agent/routing.py]

**Primary recommendation:** implement explicit field-by-field adapters and pure routers first, then graph wiring and eval/manifest gates; do not let ordinary chat touch approval resume or trusted approval state. [VERIFIED: docs/contract-spec.md §9.5/§9.6/§10.4/§11.7]

## Project Constraints (from CLAUDE.md)

- `docs/contract-spec.md` is the unique normative MOCA contract source; implementation plans must not silently diverge from it. [VERIFIED: CLAUDE.md; VERIFIED: docs/contract-spec.md]
- Spec target text is not proof of implementation; phase plans must check current code and record any intentional MVP deviation. [VERIFIED: CLAUDE.md; VERIFIED: docs/agent-architecture-phase-decomposition.md §1]
- Phase-level plans and large changes use a Claude/Codex cross-review workflow; Codex is expected to execute larger structural code changes. [VERIFIED: CLAUDE.md]
- Review and research should use `rg`/grep to locate evidence and clearly separate confirmed facts from unsupported claims. [VERIFIED: CLAUDE.md]
- No `AGENTS.md` exists in this repository, and no project-local `.claude/skills/` or `.agents/skills/` skill files were found. [VERIFIED: `test -f AGENTS.md`; VERIFIED: `find .claude .agents -maxdepth 3 -type f -name SKILL.md`]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| IntentResultV3 schema and adapter | API / Backend | LLM provider boundary | Intent output is untrusted model output that must be schema-validated and mapped into `AgentState` through code. [VERIFIED: docs/contract-spec.md §10.4; VERIFIED: src/agent/nodes/classify_intent.py] |
| Deterministic pre-router and precedence | API / Backend | Frontend Server: none | Routing is a pure backend graph/router concern and must not depend on UI or model free text. [VERIFIED: docs/contract-spec.md §9.5/§11.2] |
| Required-slot expressions and completeness | API / Backend | Database / Storage in Phase 12 only | Phase 11 owns deterministic expression evaluation; durable session-memory CAS remains Phase 12. [VERIFIED: docs/contract-spec.md §10.2/§11.3; VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md] |
| Ordinary clarification gate | API / Backend | Browser / Client displays final response only | The graph writes `clarification_request` and a safe final-response candidate; approval `needs_info` is not this path. [VERIFIED: docs/contract-spec.md §9.4/§11.5; VERIFIED: src/agent/nodes/clarification_gate.py] |
| Intent consistency manifest and golden gate | API / Backend | CI / eval tooling | Manifest and dataset/hash gates are test artifacts, not runtime routing sources. [VERIFIED: docs/contract-spec.md §11.4/§11.7] |
| Trusted approval decisions and resume | API / Backend, but later Phase 13 | — | Approval decisions must enter only through authenticated approval API/inbox adapters, not ordinary chat. [VERIFIED: docs/contract-spec.md §9.6; VERIFIED: .planning/ROADMAP.md] |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | >=3.12 project requirement; local shell Python is 3.13.3 | Runtime language | Project requires Python >=3.12 and current local runtime satisfies it. [VERIFIED: pyproject.toml; VERIFIED: `python --version`] |
| Pydantic | 2.13.4 | `IntentResultV3`, `RequiredSlotExpression`, manifest and eval result validation | Pydantic models validate untrusted data into typed structures and support JSON schema generation. [VERIFIED: uv.lock; VERIFIED: `uv run python importlib.metadata`; CITED: https://pydantic.dev/docs/validation/latest/concepts/models/] |
| LangGraph | 1.1.10 | StateGraph nodes, conditional edges, checkpointer-backed graph execution | LangGraph models workflows with state, nodes, and edges; conditional edges are the right routing mechanism when no state update is needed. [VERIFIED: uv.lock; VERIFIED: `uv run python importlib.metadata`; CITED: https://docs.langchain.com/oss/python/langgraph/graph-api] |
| LangChain structured output / langchain-openai | langchain-openai 1.2.1, langchain-core 1.3.3 | Pydantic structured LLM outputs | LangChain structured output supports Pydantic schemas and `Literal` fields, avoiding natural-language parsing. [VERIFIED: uv.lock; CITED: https://docs.langchain.com/oss/python/langchain/structured-output] |
| pytest / pytest-asyncio | pytest 9.0.3, pytest-asyncio 1.3.0 | Unit, async node, router, graph tests | Existing tests use pytest async fixtures and fake LLM seams. [VERIFIED: pyproject.toml; VERIFIED: tests/agent/conftest.py; VERIFIED: `uv run python importlib.metadata`] |

### Supporting
| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| uv | 0.11.2 | Dependency and test command runner | Use for all validation commands. [VERIFIED: `uv --version`; VERIFIED: pyproject.toml] |
| Ruff | 0.15.12 | Python linting | Run after modifying `src/agent` or tests. [VERIFIED: `uv run ruff --version`; VERIFIED: pyproject.toml] |
| Docker Compose Postgres/Redis | Postgres service uses `pgvector/pgvector:pg16`; Redis service uses `redis:7-alpine` | Integration test backing services | Existing DB container is healthy; host `pg_isready` is absent, but `docker compose exec postgres pg_isready` succeeds. [VERIFIED: docker-compose.yml; VERIFIED: `docker compose ps`; VERIFIED: `docker compose exec postgres pg_isready`] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic `BaseModel` + `Literal` | Free-form JSON or string parsing | Rejected by D-02 because routing output must be schema constrained. [VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md; CITED: https://docs.langchain.com/oss/python/langchain/structured-output] |
| LangGraph conditional edges | `Command(goto=...)` from intent/slot nodes | Conditional edges fit pure routing; `Command` should be reserved for node update + routing or trusted interrupt resume flows. [CITED: https://docs.langchain.com/oss/python/langgraph/graph-api; VERIFIED: docs/contract-spec.md §9.5] |
| Runtime `IntentRegistry` | Machine-readable consistency manifest | Rejected by D-25 because runtime source of truth remains spec tables and code routers, while manifest checks coverage only. [VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md; VERIFIED: docs/contract-spec.md §11.7] |

**Installation / sync:** [VERIFIED: pyproject.toml]
```bash
uv sync --extra dev
```

**Version verification:** local installed versions were verified with `uv run python -c "from importlib.metadata import version; ..."` and lockfile upload metadata was checked in `uv.lock`; external registry currency was not required because Phase 11 should not change dependency constraints. [VERIFIED: uv.lock; VERIFIED: command output]

## Architecture Patterns

### System Architecture Diagram

```text
User ordinary chat
  -> API/auth injects trusted tenant/user/thread/run context
  -> receive_request resets turn fields
  -> intent_classification
       -> deterministic safety pre-router
       -> Pydantic IntentResultV3 structured LLM output
       -> explicit IntentResultV3 -> AgentState adapter
  -> route_after_intent
       -> low confidence or invalid approval-looking state -> clarification_gate
       -> small_talk / unsupported -> final_response
       -> no-slot policy investigation -> investigate
       -> slot-required domain/action path -> session_memory_load
  -> slot_extraction
       -> resolve_slots(current explicit slots, empty Phase-10 session view)
  -> route_after_slots
       -> missing RequiredSlotExpression groups -> clarification_gate
       -> complete slots -> investigate or long_term_memory_retrieve seam
  -> investigate -> route_after_investigate -> recommendation/final/clarification
  -> later risk/approval/action paths as already wired

Trusted approval API / inbox command
  -> authenticate + validate approval ids/versions
  -> ApprovalService + graph resume
  -> NOT ordinary chat, NOT clarification_gate
```

Diagram source: contract routing/state sections and current graph wiring. [VERIFIED: docs/contract-spec.md §9.2/§9.5/§9.6; VERIFIED: src/agent/graph.py]

### Recommended Project Structure

```text
src/agent/
├── schemas.py                  # IntentResultV3, RequiredSlotExpression, existing agent output schemas [VERIFIED: src/agent/schemas.py]
├── intent_policy.py             # deterministic taxonomy, precedence, slot-policy, admission metadata [RECOMMENDED: follows D-15/CD discretion]
├── routing.py                   # route_after_intent, route_after_slots, existing route_after_investigate [VERIFIED: src/agent/routing.py]
├── nodes/
│   ├── classify_intent.py       # structured output + explicit adapter [VERIFIED: src/agent/nodes/classify_intent.py]
│   ├── extract_slots.py         # current slot extraction, updated to consume candidate hints only [VERIFIED: src/agent/nodes/extract_slots.py]
│   └── clarification_gate.py    # ordinary clarification only [VERIFIED: src/agent/nodes/clarification_gate.py]
eval/intent/
├── intent-golden.v1.json        # immutable dataset + expected route/slots/forbidden behavior [RECOMMENDED: docs/contract-spec.md §11.4]
├── coverage-manifest.v1.json    # per-class minimum coverage/hash metadata [RECOMMENDED: docs/contract-spec.md §11.4]
└── intent-consistency.v1.json   # manifest checked against source-of-truth tables [RECOMMENDED: docs/contract-spec.md §11.7]
tests/agent/
├── test_intent_adapter.py
├── test_intent_routing.py
├── test_required_slots.py
├── test_clarification_gate.py
└── test_intent_manifest.py
```

### Pattern 1: Field-by-Field Intent Adapter
**What:** Validate `IntentResultV3`, then write only allowed AgentState fields through an adapter. [VERIFIED: docs/contract-spec.md §10.4]

**When to use:** Every classifier result, including deterministic pre-router overlays and LLM structured output. [VERIFIED: docs/contract-spec.md §10.4/§11.6]

```python
class IntentResultV3(BaseModel):
    schema_version: Literal["intent_result.v3"] = "intent_result.v3"
    primary_intent: Intent
    requested_operation: RequestedOperation
    confidence: float = Field(ge=0.0, le=1.0)
    calibrated_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    required_slots: RequiredSlotExpression
    candidate_slots: dict[str, Any] = Field(default_factory=dict)
    secondary_intents: list[Intent] = Field(default_factory=list)
    routing_hints: dict[str, Any] = Field(default_factory=dict)
    classifier_version: str
    calibration_version: str | None = None
    reason_codes: list[str] = Field(default_factory=list)

def intent_result_to_state(result: IntentResultV3, prior_llm_outputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "primary_intent": result.primary_intent,
        "requested_operation": result.requested_operation,
        "intent_confidence": result.confidence,
        "secondary_intents": result.secondary_intents,
        "required_slots": result.required_slots.model_dump(),
        "candidate_slots": result.candidate_slots,
        "routing_hints": result.routing_hints,
        "llm_outputs": {
            **prior_llm_outputs,
            "intent_classification": {
                "eval_metadata": {
                    "calibrated_confidence": result.calibrated_confidence,
                    "classifier_version": result.classifier_version,
                    "calibration_version": result.calibration_version,
                }
            },
        },
    }
```
Source: MOCA mapping contract plus Pydantic/LangChain structured-output docs. [VERIFIED: docs/contract-spec.md §10.4/§11.6; CITED: https://pydantic.dev/docs/validation/latest/concepts/models/; CITED: https://docs.langchain.com/oss/python/langchain/structured-output]

### Pattern 2: Pure Routers in `src/agent/routing.py`
**What:** Add `route_after_intent` and `route_after_slots` as deterministic functions that read state and return only valid graph keys. [VERIFIED: docs/contract-spec.md §9.5; VERIFIED: src/agent/routing.py]

**When to use:** For routing after classifier and after slot resolution; do not call LLMs, repositories, or services from routers. [VERIFIED: docs/contract-spec.md §9.5]

```python
def route_after_intent(state: AgentState) -> str:
    if _approval_decision_like(state):
        return "clarification_gate"
    if _low_confidence(state):
        return "clarification_gate"
    if _direct_response_intent(state):
        return "final_response"
    if _requires_slots(state):
        return "session_memory_load"
    return "investigate"
```
Source: current `route_after_investigate` pattern and contract router table. [VERIFIED: src/agent/routing.py; VERIFIED: docs/contract-spec.md §9.5]

### Pattern 3: Conditional Edges for Pure Routing
**What:** Replace linear `classify_intent -> session_memory_load` and `extract_slots -> investigate` edges with conditional edges. [VERIFIED: src/agent/graph.py; VERIFIED: docs/contract-spec.md §9.2/§9.5]

**When to use:** Use conditional edges when routing without state updates; LangGraph docs distinguish that from `Command` for update+goto. [CITED: https://docs.langchain.com/oss/python/langgraph/graph-api]

```python
builder.add_conditional_edges(
    "classify_intent",
    route_after_intent,
    {
        "clarification_gate": "clarification_gate",
        "final_response": "final_response",
        "investigate": "investigate",
        "session_memory_load": "session_memory_load",
    },
)
builder.add_conditional_edges(
    "extract_slots",
    route_after_slots,
    {
        "clarification_gate": "clarification_gate",
        "investigate": "investigate",
        "long_term_memory_retrieve": "investigate",  # until the empty seam is registered
    },
)
```
Source: current graph assembly and LangGraph Graph API. [VERIFIED: src/agent/graph.py; CITED: https://docs.langchain.com/oss/python/langgraph/graph-api]

### Anti-Patterns to Avoid
- **Whole-object merge of classifier output:** this can let LLM output write forbidden fields such as `approval_result` or slot state. [VERIFIED: docs/contract-spec.md §10.4; VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md]
- **Treating `approval_request` as a normal ordinary-chat intent:** current prompt and schema include `approval_request`, but Phase 11 must remove or quarantine it so chat cannot produce trusted approval decisions. [VERIFIED: src/agent/prompts.py; VERIFIED: src/agent/schemas.py; VERIFIED: docs/contract-spec.md §11.1]
- **Candidate slots completing requirements:** `candidate_slots` are hints for slot extraction only. [VERIFIED: docs/contract-spec.md §10.4; VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md]
- **Using `Command(resume=...)` for ordinary clarification:** LangGraph resume is the interrupt-resume mechanism; ordinary chat continuation should be a new/plain input turn, not a trusted resume. [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts; VERIFIED: docs/contract-spec.md §9.6]
- **Making the manifest a runtime registry:** the manifest checks consistency but must not replace source-of-truth tables or routers. [VERIFIED: docs/contract-spec.md §11.7]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured LLM parsing | Regex/string parsing of classifier JSON | Pydantic `BaseModel` + `Literal` through LangChain structured output | Validated structured output is required by D-02 and supported by LangChain/Pydantic. [VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md; CITED: https://docs.langchain.com/oss/python/langchain/structured-output] |
| Router side effects | Routers that call LLM/tool/database | Pure router functions under `src/agent/routing.py` | Contract requires deterministic side-effect-free routers. [VERIFIED: docs/contract-spec.md §9.5] |
| Slot expression evaluation | Ad hoc prompt-only “missing slot” decisions | Deterministic `RequiredSlotExpression` helper | Completeness rules for `all_of`, `any_of`, and `optional` are defined in the spec. [VERIFIED: docs/contract-spec.md §10/§11.3] |
| Approval-like chat handling | Chat-created `approval_result` or `Command(resume=...)` | Trusted approval API/inbox adapter in Phase 13 | Approval decisions require authentication, versions, and trusted-origin markers. [VERIFIED: docs/contract-spec.md §9.6; CITED: https://docs.langchain.com/oss/python/langgraph/interrupts] |
| Wilson gate math | Informal percentage thresholds or pooled metrics | Spec-defined one-sided 95% Wilson upper bound helper and per-class manifest | M6 gate semantics and status precedence are normative. [VERIFIED: docs/contract-spec.md §11.4] |

**Key insight:** Phase 11 safety depends less on model accuracy than on deterministic boundaries around what model output is allowed to write and where routing can go. [VERIFIED: docs/contract-spec.md §9.5/§10.4/§11.4]

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Postgres has `agent_runs`, `agent_steps`, approval tables, and LangGraph checkpoint tables; live `moca` DB has 9 `agent_runs`, 56 `agent_steps`, 663 `checkpoints`, and 3606 `checkpoint_writes`. [VERIFIED: `docker compose exec postgres psql -U moca -d moca -c "\\dt"`; VERIFIED: count queries] | Keep backward-compatible reads for `current_intent` and historical node names; no Phase 11 data migration/backfill required unless planner chooses to rewrite checkpoint blobs, which is not recommended. [VERIFIED: src/agent/routing.py fallback reads; VERIFIED: .planning/phases/10-state-lifecycle-routing-migration/10-01-PLAN.md] |
| Stored historical traces | Existing `agent_steps.node_name` rows include old nodes `load_business_context` and `retrieve_policy_evidence`. [VERIFIED: agent_steps node_name query] | Preserve history; update new graph/tests without backfilling historical audit rows. [VERIFIED: .planning/phases/10-state-lifecycle-routing-migration/10-05-SUMMARY.md] |
| Live service config | Docker Compose services are Postgres and Redis and both are healthy; no UI-only external service config was found for intent classification. [VERIFIED: docker-compose.yml; VERIFIED: `docker compose ps`] | No service config migration. [VERIFIED: docs/migration-plan.md Phase 11 row names rollback as classifier prompt rollback, not service migration] |
| OS-registered state | No project-specific launchd/systemd/pm2 registration was found during repository scan. [VERIFIED: no matching project files under repository; LOW external OS audit because system-wide registrations were not enumerated] | None for planning; if executor touches daemon setup, re-audit OS registrations then. [ASSUMED] |
| Secrets/env vars | `.env` and `.env.example` exist; code uses `settings.llm_model`, `dashscope_api_key`, `embedding_base_url`, and no Phase 11-specific env var names were identified. [VERIFIED: `find . -maxdepth 3 -name '.env*'`; VERIFIED: src/agent/nodes/classify_intent.py] | Do not rename secret keys in Phase 11. [VERIFIED: docs/migration-plan.md Phase 11 rollback/non-goals] |
| Build artifacts | `moca.egg-info` exists at repo root. [VERIFIED: `ls`] | No package rename; no artifact cleanup required for Phase 11. [VERIFIED: pyproject.toml project name unchanged] |

## Common Pitfalls

### Pitfall 1: `current_intent` / `primary_intent` Drift
**What goes wrong:** New code writes only `primary_intent` while older readers and trace summaries still read `current_intent`. [VERIFIED: src/agent/nodes/classify_intent.py; VERIFIED: src/agent/trace.py; VERIFIED: src/agent/tools/unified.py]
**Why it happens:** Phase 10 intentionally preserved `current_intent` compatibility and left the live rename to Phase 11. [VERIFIED: .planning/phases/10-state-lifecycle-routing-migration/10-01-PLAN.md]
**How to avoid:** Plan an adapter that writes canonical fields and either writes transitional `current_intent` or updates all readers atomically with backward-compatible fallback. [VERIFIED: src/agent/routing.py already reads `primary_intent` fallback to `current_intent`]
**Warning signs:** Tests passing only because graph fixtures still assert `current_intent`. [VERIFIED: tests/agent/test_graph.py]

### Pitfall 2: Approval Decision Leakage Through Chat
**What goes wrong:** Ordinary text like “approve APR-1” becomes `approval_result` or a trusted resume payload. [VERIFIED: docs/contract-spec.md §9.6/§11.1]
**Why it happens:** The current classifier schema and prompt include `approval_request` as an ordinary intent. [VERIFIED: src/agent/schemas.py; VERIFIED: src/agent/prompts.py]
**How to avoid:** Remove `approval_request` from ordinary classifier output, route approval-looking chat to unsupported/clarification/safe domain request, and add negative tests for `approval_result`, `Command(resume=...)`, trusted versions, and decision markers. [VERIFIED: docs/contract-spec.md §9.6/§11.1; CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]
**Warning signs:** Any Phase 11 ordinary-chat test constructs `approval_result` from classifier output. [VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md]

### Pitfall 3: Slot Completeness From Candidate Hints
**What goes wrong:** `candidate_slots` bypass `slot_extraction` and make `route_after_slots` think a required target is complete. [VERIFIED: docs/contract-spec.md §10.4]
**Why it happens:** Classifier output often sees identifiers, but spec deliberately treats those as hints only. [VERIFIED: docs/contract-spec.md §10.4/§11.6]
**How to avoid:** Test that candidate-only `order_id`/`refund_case_id` does not satisfy `RequiredSlotExpression`; only `extracted_slots` plus allowed `session_memory.active_slots` can pass. [VERIFIED: docs/contract-spec.md §9.5/§10.4]
**Warning signs:** `route_after_slots` reads `candidate_slots`. [VERIFIED: docs/contract-spec.md §9.5 says reads exclude `candidate_slots`]

### Pitfall 4: Graph Edge Drift
**What goes wrong:** Adding `route_after_intent` but leaving the static `classify_intent -> session_memory_load` edge makes every request still load slots and investigate. [VERIFIED: src/agent/graph.py]
**Why it happens:** LangGraph static edges still execute even if a node also returns dynamic control flow; docs warn not to mix routing styles for one node. [CITED: https://docs.langchain.com/oss/python/langgraph/graph-api]
**How to avoid:** Replace static edges with `add_conditional_edges` and extend router-key coverage tests. [VERIFIED: tests/agent/test_graph.py; CITED: https://docs.langchain.com/oss/python/langgraph/graph-api]
**Warning signs:** `policy_qa` still goes through `session_memory_load` and `extract_slots` in full-graph tests. [VERIFIED: tests/agent/test_graph.py current assertions]

### Pitfall 5: Eval Gate Treated as Later Polish
**What goes wrong:** Classifier/routing code lands without `intent-golden.v1`, dataset hash ownership, per-class gates, or manifest checker. [VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md D-21..D-28]
**Why it happens:** Runtime implementation feels complete before M6 confidence-assisted safety gates are demonstrable. [VERIFIED: docs/contract-spec.md §11.4]
**How to avoid:** Put manifest/golden work in plan `11-05` and make missing/stale metadata fail contract tests. [VERIFIED: docs/contract-spec.md §11.4/§11.7]
**Warning signs:** Only pooled accuracy is reported for critical classes. [VERIFIED: docs/contract-spec.md §11.4]

## Code Examples

### RequiredSlotExpression Completeness
```python
def missing_required_slots(expr: RequiredSlotExpression, slots: dict[str, Any]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for slot in expr.all_of:
        if not slots.get(slot):
            missing.append({"all_of": [slot]})
    for group in expr.any_of:
        if not any(slots.get(slot) for slot in group):
            missing.append({"any_of": group})
    return missing
```
Source: spec completeness rule; implementation should preserve `A or B` groups instead of reporting both as separately required. [VERIFIED: docs/contract-spec.md §10/§11.3]

### Wilson Gate Helper
```python
Z_ONE_SIDED_95 = 1.6448536269514722

def wilson_upper(false_negatives: int, n: int) -> float:
    phat = false_negatives / n
    denominator = 1 + Z_ONE_SIDED_95**2 / n
    center = phat + Z_ONE_SIDED_95**2 / (2 * n)
    margin = Z_ONE_SIDED_95 * ((phat * (1 - phat) / n) + (Z_ONE_SIDED_95**2 / (4 * n**2))) ** 0.5
    return (center + margin) / denominator
```
Source: normative M6 gate formula. [VERIFIED: docs/contract-spec.md §11.4]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-form or small enum `IntentResult` with `intent/confidence/reasoning` | Pydantic `IntentResultV3` with separated `primary_intent` and `requested_operation` | Phase 11 target contract from 2026-06-14 context | Plan must replace schema/prompt and adapter rather than append fields opportunistically. [VERIFIED: src/agent/schemas.py; VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md] |
| Linear graph after intent | Conditional route after intent and slots | Contract target in `docs/contract-spec.md` §9 | Plan must rewire graph and router-key tests. [VERIFIED: docs/contract-spec.md §9.2/§9.5; VERIFIED: src/agent/graph.py] |
| Ordinary classifier can output `approval_request` | Approval command is API/inbox-only; chat approval-looking text is untrusted | Contract target in `docs/contract-spec.md` §9.6/§11.1 | Prompt/schema must not expose trusted approval decision values. [VERIFIED: src/agent/prompts.py; VERIFIED: docs/contract-spec.md §9.6/§11.1] |
| Pooled intent safety metrics | Per-critical-class Wilson gate with coverage manifest | Contract target in `docs/contract-spec.md` §11.4 | `11-05` must create or verify machine-readable eval artifacts. [VERIFIED: docs/contract-spec.md §11.4] |

**Deprecated/outdated:**
- `approval_request` as an ordinary chat intent is outdated for Phase 11 and conflicts with the target ordinary/trusted boundary. [VERIFIED: src/agent/schemas.py; VERIFIED: docs/contract-spec.md §11.1]
- Prompt examples that ask the LLM to classify “approve/reject/escalate/review risky action” as `approval_request` are outdated for Phase 11. [VERIFIED: src/agent/prompts.py; VERIFIED: docs/contract-spec.md §9.6]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No project-specific OS-registered state exists outside the repository. | Runtime State Inventory | Low/medium: if launchd/systemd/pm2 state embeds old prompt/schema names, planner may omit an operational update. |

## Open Questions

1. **Should the transitional adapter keep writing `current_intent` during Phase 11?** [VERIFIED: src/agent/trace.py; VERIFIED: tests/agent/test_graph.py]
   - What we know: live code and tests still read `current_intent`, while the contract wants `primary_intent`. [VERIFIED: src/agent/nodes/classify_intent.py; VERIFIED: docs/contract-spec.md §10.4]
   - What's unclear: whether planner wants an atomic reader migration or a compatibility window. [ASSUMED]
   - Recommendation: keep read fallback and add tests proving canonical fields are written; optionally keep `current_intent` as transitional compatibility until all readers are updated. [VERIFIED: .planning/phases/10-state-lifecycle-routing-migration/10-01-PLAN.md]

2. **Where should eval artifacts live?** [VERIFIED: repository currently has `eval/`, `evals/`, and `evaluation/` directories]
   - What we know: the repo already has multiple evaluation directories. [VERIFIED: `ls`]
   - What's unclear: preferred consolidation path. [ASSUMED]
   - Recommendation: choose one Phase 11-owned path, preferably `eval/intent/`, and make tests reference it explicitly. [RECOMMENDED: codebase convention needs planner decision]

3. **Should `long_term_memory_retrieve` be registered now or route key mapped to `investigate` until Phase 16?** [VERIFIED: docs/contract-spec.md §9.5; VERIFIED: src/agent/graph.py]
   - What we know: route table allows `long_term_memory_retrieve`, but Phase 16 owns real long-term/case memory and current graph does not register that node. [VERIFIED: docs/agent-architecture-phase-decomposition.md; VERIFIED: src/agent/graph.py]
   - What's unclear: whether Phase 11 should add an empty registered seam or map route to `investigate`. [ASSUMED]
   - Recommendation: keep this out of critical Phase 11 path unless a router test requires the canonical key; document any mapping as a deviation/compatibility decision. [VERIFIED: .planning/phases/11-intent-clarification/11-CONTEXT.md CD discretion]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Runtime/tests | yes | 3.13.3 shell; project requires >=3.12 | Use `uv run python` for environment consistency. [VERIFIED: `python --version`; VERIFIED: pyproject.toml] |
| uv | Test/lint runner | yes | 0.11.2 | None needed. [VERIFIED: `uv --version`] |
| Docker | Integration DB services | yes | Docker CLI present | None needed. [VERIFIED: `command -v docker`] |
| Postgres service | Integration tests and checkpointer | yes | pgvector/pgvector:pg16 container healthy | Use `docker compose up postgres` if stopped. [VERIFIED: docker-compose.yml; VERIFIED: `docker compose ps`] |
| Host `pg_isready` | Optional service probe | no | — | Use `docker compose exec postgres pg_isready`. [VERIFIED: `pg_isready`; VERIFIED: docker exec pg_isready] |
| Context7 MCP | External library docs | no Context7 MCP tools exposed | — | Used official web docs instead. [VERIFIED: available tool list; CITED: LangGraph/LangChain/Pydantic docs] |
| Graphify | Knowledge graph context | disabled | — | Used direct code/doc grep. [VERIFIED: `gsd-tools graphify status`] |

**Missing dependencies with no fallback:** None for planning Phase 11. [VERIFIED: environment probes]

**Missing dependencies with fallback:** host `pg_isready` and Context7 MCP have viable fallbacks. [VERIFIED: environment probes; CITED: official docs fetched via web]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 with pytest-asyncio 1.3.0 [VERIFIED: uv.lock; VERIFIED: importlib.metadata] |
| Config file | `pyproject.toml` with `asyncio_mode = "auto"` [VERIFIED: pyproject.toml] |
| Quick run command | `uv run pytest tests/agent/test_nodes/test_classify_intent.py tests/test_graph_routing.py tests/agent/test_graph.py -q` [VERIFIED: existing test files] |
| Full suite command | `uv run pytest -q` [VERIFIED: Phase 10 summary reports full suite passed at 443 tests] |
| Lint command | `uv run ruff check src/agent tests/agent tests/test_graph_routing.py` [VERIFIED: pyproject.toml; VERIFIED: ruff version] |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| INTENT-01 | V3 adapter writes only allowed fields; deterministic pre-router handles precedence and approval-looking chat safely | unit/golden | `uv run pytest tests/agent/test_intent_adapter.py tests/agent/test_intent_routing.py -q` | no, Wave 0 [VERIFIED: `rg --files tests`] |
| INTENT-01 | Graph uses `route_after_intent` edge targets and does not force all traffic through slots | integration | `uv run pytest tests/agent/test_graph.py -q` | yes, extend [VERIFIED: tests/agent/test_graph.py] |
| INTENT-02 | `RequiredSlotExpression` completeness enforces `all_of`, `any_of`, and optional semantics | unit | `uv run pytest tests/agent/test_required_slots.py -q` | no, Wave 0 [VERIFIED: `rg --files tests`] |
| INTENT-02 | Candidate slots cannot satisfy completeness or overwrite active/extracted slots | unit/integration | `uv run pytest tests/agent/test_required_slots.py tests/agent/test_nodes/test_classify_intent.py -q` | partial, extend classify test [VERIFIED: tests/agent/test_nodes/test_classify_intent.py] |
| CLARIFY-01 | Ordinary clarification writes `clarification_request` and safe response only | unit | `uv run pytest tests/agent/test_clarification_gate.py -q` | no, Wave 0 [VERIFIED: src/agent/nodes/clarification_gate.py] |
| CLARIFY-01 | Ordinary chat cannot create `approval_result`, trusted versions, or resume commands | negative integration | `uv run pytest tests/agent/test_intent_routing.py tests/test_approval_integration.py -q` | partial, add tests [VERIFIED: tests/test_approval_integration.py] |
| INTENT-01/02/CLARIFY-01 | Manifest/dataset hash/gate metadata and per-class Wilson semantics | contract/eval | `uv run pytest tests/agent/test_intent_manifest.py -q` | no, Wave 0 [VERIFIED: docs/contract-spec.md §11.4/§11.7] |

### Sampling Rate
- **Per task commit:** run the focused test file for the changed seam plus `uv run ruff check <changed files>`. [VERIFIED: existing Phase 10 testing pattern]
- **Per wave merge:** run `uv run pytest tests/agent/test_nodes/test_classify_intent.py tests/test_graph_routing.py tests/agent/test_graph.py -q`. [VERIFIED: existing files]
- **Phase gate:** run `uv run pytest -q` plus the new manifest/eval test command. [VERIFIED: .planning/config.json `nyquist_validation=true`; VERIFIED: docs/eval-test-plan.md]

### Wave 0 Gaps
- [ ] `tests/agent/test_intent_adapter.py` covers `IntentResultV3 -> AgentState`, no whole-object merge, confidence/calibrated-confidence separation, and forbidden writes. [VERIFIED: docs/contract-spec.md §10.4]
- [ ] `tests/agent/test_intent_routing.py` covers deterministic pre-router, precedence conflicts, low-confidence gates, approval-looking chat invalid state, and valid router keys. [VERIFIED: docs/contract-spec.md §9.5/§11.2]
- [ ] `tests/agent/test_required_slots.py` covers `all_of`, `any_of`, `optional`, current explicit slot precedence, empty Phase-10 session adapter, and candidate-slot non-completeness. [VERIFIED: docs/contract-spec.md §10/§11.3]
- [ ] `tests/agent/test_clarification_gate.py` covers minimal ordinary questions, `clarification_request_id`, blocked nodes, no permission/tool error leakage, and no approval lifecycle writes. [VERIFIED: docs/contract-spec.md §11.5; VERIFIED: src/agent/nodes/clarification_gate.py]
- [ ] `tests/agent/test_intent_manifest.py` covers source-of-truth coverage, stale dataset/hash metadata, `small_talk`/`unsupported` evidence exemptions, and Wilson status precedence. [VERIFIED: docs/contract-spec.md §11.4/§11.7]
- [ ] `eval/intent/intent-golden.v1.json`, `coverage-manifest.v1.json`, and `intent-consistency.v1.json` need owner/version/hash fields. [VERIFIED: docs/contract-spec.md §11.4/§11.7]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no new auth in Phase 11 | Preserve trusted approval API boundary; do not implement approval decisions in chat. [VERIFIED: docs/contract-spec.md §9.6] |
| V3 Session Management | limited | Ordinary clarification may correlate same-thread unresolved questions, but Postgres session CAS is Phase 12. [VERIFIED: docs/contract-spec.md §11.5; VERIFIED: .planning/ROADMAP.md] |
| V4 Access Control | yes | Treat ordinary chat as untrusted; never allow it to set trusted identity, approval versions, or resume commands. [VERIFIED: docs/contract-spec.md §8.0/§9.6] |
| V5 Input Validation | yes | Pydantic `BaseModel` + `Literal`, explicit adapter, deterministic slot expressions. [VERIFIED: docs/contract-spec.md §10.4/§11.6; CITED: https://pydantic.dev/docs/validation/latest/concepts/models/] |
| V6 Cryptography | yes for hashes only | Use standard SHA-256 strings for dataset/coverage hashes; do not hand-roll crypto beyond deterministic hash computation. [VERIFIED: docs/contract-spec.md §11.4] |

### Known Threat Patterns for Phase 11

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| User text impersonates approval decision | Spoofing / Elevation of Privilege | Deterministic pre-router + classifier schema excludes `approval_decision`; negative tests assert no `approval_result` or resume. [VERIFIED: docs/contract-spec.md §9.6/§11.1] |
| LLM structured output includes extra trusted fields | Tampering | Pydantic schema with `extra="forbid"` where practical plus field-by-field adapter. [VERIFIED: docs/contract-spec.md §10.4; VERIFIED: src/agent/schemas.py uses `ConfigDict(extra="forbid")` in `InvestigationResult`] |
| Missing slot route proceeds to tools/actions | Tampering / Information Disclosure | `route_after_slots` evaluates deterministic completeness and routes missing groups to ordinary clarification. [VERIFIED: docs/contract-spec.md §9.5/§11.3] |
| Low-confidence high-risk request proceeds as read-only | Elevation of Privilege | Precedence and confidence safety gates route to clarification/risk path, never confidence-only action route. [VERIFIED: docs/contract-spec.md §11.4] |
| Manifest claims coverage without source support | Repudiation | CI checker verifies manifest against spec-derived tables and golden examples; stale dataset/hash fails. [VERIFIED: docs/contract-spec.md §11.7] |

## Sources

### Primary (HIGH confidence)
- `.planning/phases/11-intent-clarification/11-CONTEXT.md` — locked decisions, plan split, safety boundary, deferred scope. [VERIFIED]
- `.planning/REQUIREMENTS.md` — INTENT-01, INTENT-02, CLARIFY-01. [VERIFIED]
- `.planning/ROADMAP.md` — Phase 11 scope/dependencies and downstream Phase 12/13 ownership. [VERIFIED]
- `.planning/STATE.md` — current phase position and Phase 10 completion. [VERIFIED]
- `.planning/phases/10-state-lifecycle-routing-migration/10-CONTEXT.md` and `10-05-SUMMARY.md` — Phase 10 graph foundation and Phase 11 readiness. [VERIFIED]
- `docs/contract-spec.md` §9.3-§9.6, §10.1/§10.4, §11.1-§11.7 — normative contracts. [VERIFIED]
- `docs/agent-architecture-phase-decomposition.md` — readiness, coverage, phase ownership, follow-up register. [VERIFIED]
- `docs/migration-plan.md` — Phase 11 outputs/tests/rollback and planning traceability requirements. [VERIFIED]
- `docs/eval-test-plan.md` — contract tests, golden flows, eval dataset requirements. [VERIFIED]
- `.planning/DEFERRED-DECISIONS.md` — GAD-02 and GAD-03 carry-forward. [VERIFIED]
- `src/agent/schemas.py`, `src/agent/nodes/classify_intent.py`, `src/agent/prompts.py`, `src/agent/state.py`, `src/agent/routing.py`, `src/agent/graph.py`, `src/agent/nodes/clarification_gate.py`, `src/agent/nodes/extract_slots.py` — implementation seams. [VERIFIED]
- `tests/agent/test_graph.py`, `tests/test_graph_routing.py`, `tests/agent/test_nodes/test_classify_intent.py`, `tests/agent/conftest.py`, `tests/conftest.py` — established test patterns. [VERIFIED]

### Secondary (MEDIUM confidence)
- LangGraph Graph API docs — state/nodes/edges, conditional edge versus `Command` routing, compile behavior. [CITED: https://docs.langchain.com/oss/python/langgraph/graph-api]
- LangGraph Interrupts docs — `Command(resume=...)` semantics and same-thread resume requirements. [CITED: https://docs.langchain.com/oss/python/langgraph/interrupts]
- LangGraph Test docs — compile-with-checkpointer and node/edge testing patterns. [CITED: https://docs.langchain.com/oss/python/langgraph/test]
- LangChain structured output docs — Pydantic schema structured outputs and `Literal` examples. [CITED: https://docs.langchain.com/oss/python/langchain/structured-output]
- Pydantic model docs — `BaseModel` validation semantics. [CITED: https://pydantic.dev/docs/validation/latest/concepts/models/]

### Tertiary (LOW confidence)
- OS-level registration absence is based on repository scan only; no system-wide launchd/systemd enumeration was performed. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — local versions verified via `uv.lock` and import metadata; no dependency upgrades recommended. [VERIFIED: uv.lock; VERIFIED: command output]
- Architecture: HIGH — governed by normative contract and current code seams. [VERIFIED: docs/contract-spec.md; VERIFIED: src/agent/graph.py]
- Pitfalls: HIGH — each pitfall is backed by current code or normative safety requirements. [VERIFIED: src/agent/*; VERIFIED: docs/contract-spec.md]
- External docs: MEDIUM — official docs were checked, but Context7 MCP was unavailable in this environment. [CITED: LangGraph/LangChain/Pydantic docs; VERIFIED: graphify/Context7 availability]

**Research date:** 2026-06-14 [VERIFIED: environment current_date]
**Valid until:** 2026-07-14 for project contracts; 2026-06-21 for external LangGraph/LangChain docs because those APIs are fast-moving. [ASSUMED]
