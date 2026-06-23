# Phase 29: Tool Platform Boundary - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `29-CONTEXT.md` -- this log preserves the alternatives considered.

**Date:** 2026-06-23
**Phase:** 29 - Tool Platform Boundary
**Areas discussed:** Planner-visible ToolView surface, ToolPolicyDecision semantics, ToolPlatform and runtime boundary split, ToolResultProjector and graph-state projection

---

## Planner-visible ToolView Surface

### ToolView Exposure

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal capability view | Expose only `name`, `description`, prompt-safe `input_schema`, `safe_usage_notes`, and `result_contract_version`. | yes |
| View with safety labels | Also expose read-only safety labels such as `kind` or `data_classification`. | |
| Near-descriptor view | Expose more descriptor metadata and rely on prompt constraints. | |

**User's choice:** Minimal capability view.
**Notes:** Read/retrieval/action guidance may appear only in controlled `safe_usage_notes`, not as raw policy/runtime fields.

### Input Schema Projection

| Option | Description | Selected |
|--------|-------------|----------|
| Keep argument shape but strip internal policy details | Preserve field names, types, required fields, basic constraints, and short descriptions. Strip defaults, examples, internal validation notes, permission/resource policy, and adapter/upstream details. | yes |
| Only keep field names and required fields | Most conservative, but likely increases invalid calls. | |
| Reuse descriptor input schema directly | Simple but risks future prompt leakage. | |

**User's choice:** Keep argument shape but strip internal policy details.
**Notes:** `ToolView.input_schema` is a prompt-safe projection, not raw descriptor passthrough.

### Runtime Availability

| Option | Description | Selected |
|--------|-------------|----------|
| Hide unavailable tools by default | Planner sees only policy-visible and runtime-available tools. | yes |
| Show unavailable tools with notes | Planner sees target capability but may get unavailable results. | |
| Show by descriptor/exposure only | Runtime handles unavailable results. | |

**User's choice:** Hide unavailable tools by default.
**Notes:** `ToolView` visibility equals policy visibility intersected with runtime availability. Unavailable is a health/availability reason, not a policy denial.

### Hidden Decision Recording

| Option | Description | Selected |
|--------|-------------|----------|
| Record all catalog tools' visibility decisions | Full low-payload visibility decision set for visible, hidden, and unavailable tools. | yes |
| Only record visible tools | Lower volume but cannot explain hidden tools. | |
| Record hidden/unavailable only in debug/test mode | Lower production volume but weaker replay/audit coverage. | |

**User's choice:** Record all catalog tools' visibility decisions.
**Notes:** Prefer batch visibility events. Payload must not include raw descriptor, full input schema, executor refs, adapter/upstream details, or internal permission notes.

---

## ToolPolicyDecision Semantics

### Reason Codes

| Option | Description | Selected |
|--------|-------------|----------|
| Small stable enum plus extensible prefixes | Stable Phase 29 core enum with `<namespace>.<snake_case>` extension codes. | yes |
| Free snake_case strings | Flexible but weak for eval/contract tests. | |
| Global strict allowlist | Most controlled but high maintenance across later phases. | |

**User's choice:** Small stable enum plus extensible prefixes.
**Notes:** Core codes are stage-aware and contract-tested. Runtime-only codes must not appear in visibility decisions.

### Decision Event Relationship

| Option | Description | Selected |
|--------|-------------|----------|
| Domain schema embedded in event payload | Generate `ToolPolicyDecision`, then write through Phase 28 envelope payload. | yes |
| Direct event payload fields only | Less code but no reusable tool policy object. | |
| Each decision as full envelope extension | High granularity but heavier and risks parallel envelope design. | |

**User's choice:** Domain schema embedded in event payload.
**Notes:** `ToolPolicyDecision` is not the event envelope. Visibility can batch; runtime auth is usually per invoke.

### Version, Classification, Scope Binding

| Option | Description | Selected |
|--------|-------------|----------|
| Descriptor plus policy engine derived | Descriptor supplies static inputs; policy engine supplies version/semantics; runtime supplies per-call binding. | yes |
| All descriptor-declared | Simple but static declarations can be mistaken for per-call authorization facts. | |
| All runtime-inferred | Flexible but weakens catalog as single source. | |

**User's choice:** Descriptor plus policy engine derived.
**Notes:** Runtime auth must include per-call `resource_scope_binding` where applicable.

### Runtime Denial Return

| Option | Description | Selected |
|--------|-------------|----------|
| Safe `ToolResultV2` plus decision event | Denials return graph-compatible safe errors and also write runtime auth decisions. | yes |
| Raise `ToolPolicyError` | Hard boundary but larger graph/error handling change. | |
| Return `ToolPolicyDecision` instead of `ToolResultV2` | Pure policy semantics but breaks existing graph result flow. | |

**User's choice:** Safe `ToolResultV2` plus decision event.
**Notes:** Programmer/contract failures may raise; normal policy denials should fail closed through safe tool result statuses.

---

## ToolPlatform And Runtime Boundary Split

### Component Split

| Option | Description | Selected |
|--------|-------------|----------|
| ToolPlatform facade plus internal helpers | Smallest public API split. | |
| Refactor UnifiedToolManager as final public boundary | Less churn but keeps old abstraction central. | |
| Explicit ToolPlatform, ToolPolicyEngine, ToolRuntime, ToolResultProjector components | Clear target platform boundaries with constrained scope. | yes |

**User's choice:** Constrained version of explicit component split.
**Notes:** The user chose target component boundaries now, while explicitly limiting Phase 29 from becoming a full future-runtime rewrite.

### Runtime Capability Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal mandatory runtime chain | Input validation, runtime auth, side-effect and required-field gates, dispatch, output validation, projection, event. | yes |
| Full target runtime | Adds generic timeout wrapper, retry policy, rate limit, artifact persistence, feature flags. | |
| Policy/auth only | Avoids execution-chain refactor but leaves runtime boundary incomplete. | |

**User's choice:** Minimal mandatory runtime chain.
**Notes:** Existing `deadline_at` and `max_attempts` semantics are reused; no new generic retry/rate-limit/artifact infrastructure in Phase 29.

### Resource Scope Authorization

| Option | Description | Selected |
|--------|-------------|----------|
| Tool-level resource binding plus basic scope check | Bind obvious args and deny clear scope violations; domain checks remain Phase 30. | yes |
| Full business resource authorization | Stronger but crosses into BusinessFactService scope. | |
| Permission only, no resource binding | Too weak for APF-07. | |

**User's choice:** Tool-level resource binding plus basic scope check.
**Notes:** Runtime must not pretend order/refund/ticket ownership is verified when it requires domain lookup.

### Graph Migration Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Migrate only the tool-platform integration point | `investigate` uses `visible_tools(...)` and `invoke(...)`; loop semantics stay. | yes |
| Also refactor the investigate planner loop | Cleaner target structure but belongs to graph migration. | |
| Do not touch investigate | Safer but does not prove planner view on real graph path. | |

**User's choice:** Migrate only the tool-platform integration point.
**Notes:** Broader planner-loop and target graph migration belongs to Phase 32.

---

## ToolResultProjector And Graph-state Projection

### Projection Layers

| Option | Description | Selected |
|--------|-------------|----------|
| Four projection layers without new artifact store | `normalized_result`, prompt projection, audit/resource refs, debug projection, optional raw ref/hash. | yes |
| Prompt summary only | Too small; leaves graph/audit/debug projection scattered. | |
| Full raw artifact plus normalized/prompt/replay artifact store | Target-rich but too much storage infrastructure for Phase 29. | |

**User's choice:** Four projection layers without new artifact store.
**Notes:** Reserve raw artifact refs/hashes only; no DB schema or artifact store commitment.

### Raw Data In Graph State

| Option | Description | Selected |
|--------|-------------|----------|
| Never directly; projector required | All `ToolResultV2.data` is untrusted/raw-ish and must be projected. | yes |
| Allow read-tool data directly | Easier but read tools can still contain PII or prompt injection. | |
| Only prohibit write-tool data | Inconsistent boundary and weaker tests. | |

**User's choice:** Never directly; projector required.
**Notes:** Read/retrieval/write all require projection before graph consumption.

### Prompt Projection Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Structured object plus derived short text | Contract fields plus bounded `text_for_prompt` compatibility. | yes |
| Short text only | Compatible but weaker for field-level leakage tests. | |
| Summarize normalized_result directly into prompt | Rich but too risky. | |

**User's choice:** Structured object plus derived short text.
**Notes:** Prompts consume `text_for_prompt` or structured prompt projection, not `normalized_result` or raw `data`.

### Decision/Event Refs

| Option | Description | Selected |
|--------|-------------|----------|
| Produce refs but do not write events | Projector links result/projection to policy decision/event refs without owning emission. | yes |
| Projector writes projection events | More complete but overlaps event ownership. | |
| Do not include decision/event refs | Simpler but weak replay linkage. | |

**User's choice:** Produce refs but do not write events.
**Notes:** Projection-level events are deferred to Phase 35 if needed.

---

## the agent's Discretion

- Exact module paths, class signatures, helper names, event names, and test file splits.
- Exact `debug_projection` shape, as long as it is not prompt input and does not leak raw/private fields.

## Deferred Ideas

- Full investigate planner-loop and target graph migration -- Phase 32.
- Business fact authority and domain ownership checks -- Phase 30.
- Generic retry/rate-limit/feature-flag/runtime policy infrastructure -- future phase if needed.
- Raw artifact store / DB-backed artifact persistence -- future scope.
- Projection-level replay events -- Phase 35 if needed.
- Dynamic external tool/MCP discovery -- APF-FUT-03.
