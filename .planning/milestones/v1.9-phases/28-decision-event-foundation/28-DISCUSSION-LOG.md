# Phase 28: Decision Event Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `28-CONTEXT.md` - this log preserves the alternatives considered.

**Date:** 2026-06-23
**Phase:** 28-decision-event-foundation
**Areas discussed:** Envelope contract surface, Emitter API and trusted identity source, Reason-code and version placement convention, Redaction/resource refs/initial coverage

---

## Envelope Contract Surface

| Option | Description | Selected |
| --- | --- | --- |
| Add explicit Pydantic schema | Add `DecisionEventEnvelopeV1` with strict minimal envelope validation. | yes |
| Keep dict projection with tests only | Continue relying on `ReplayService.project_minimal_event()` dict shape. |  |
| Document/plan constraint only | Do not add code-level contract. |  |

**User's choice:** Add explicit `DecisionEventEnvelopeV1` Pydantic schema.

**Notes:** Existing `ReplayService.project_minimal_event()` dict projection and `src.agent.events` wrapper are too implicit for a foundation contract.

| Option | Description | Selected |
| --- | --- | --- |
| `src/replay/decision_events.py` | Replay-owned decision event boundary. | yes |
| `src/platform/` | Platform-wide location. |  |
| `src/replay/schemas.py` | Add beside `ReplayEventV3`. |  |

**User's choice:** Place the schema in `src/replay/decision_events.py`.

**Notes:** `docs/contract-spec.md` assigns `DecisionEventEnvelopeV1`, `emit_decision_event`, and replay lifecycle ownership to Observability / Replay.

| Option | Description | Selected |
| --- | --- | --- |
| Strict envelope plus basic conditional validation | Required fields, `extra="forbid"`, event registry, and operation lifecycle `operation_id` checks. | yes |
| Field presence only | Only check minimal field presence. |  |
| Loose emitter convention | Rely on writer discipline. |  |

**User's choice:** Strict envelope with basic conditional validation.

**Notes:** Do not implement parent/attempt pairing in Phase 28.

| Option | Description | Selected |
| --- | --- | --- |
| No DB schema change | Reuse existing `agent_trace_events` and ORM model. | yes |
| Small migration only if required | Add only missing constraints/columns. |  |
| New or rebuilt base event table | Create a new table or replace current storage. |  |

**User's choice:** No DB schema change.

**Notes:** Existing table already supports minimal and V3 rows; Phase 28 should add facade, emitter, and tests.

---

## Emitter API And Trusted Identity Source

| Option | Description | Selected |
| --- | --- | --- |
| Add `emit_decision_event(...)` in replay boundary | New replay-owned entrypoint calling `ReplayService.append_event(...)`. | yes |
| Enhance `src.agent.events.emit_event` only | Keep ownership in agent wrapper. |  |
| Use `ReplayService.append_event(...)` directly | No emitter API. |  |

**User's choice:** Add `emit_decision_event(...)` in `src/replay/decision_events.py`.

**Notes:** `src.agent.events.emit_event` remains a compatibility wrapper.

| Option | Description | Selected |
| --- | --- | --- |
| Receive `ReplayContext` / trusted projection | Identity from Phase 27 trusted projection. | yes |
| Explicit run/tenant/thread IDs | Caller passes identity fields manually. |  |
| Read from `AgentState` | Pull identity from graph state. |  |

**User's choice:** Prefer `ReplayContext` / trusted projection as the identity source.

**Notes:** Caller-built identity bypasses the trusted identity path.

| Option | Description | Selected |
| --- | --- | --- |
| Migrate thin wrapper and key path | Route `src.agent.events.emit_event` through the new entrypoint. | yes |
| Add new emitter only | Existing writers unchanged. |  |
| Broadly migrate all writers | Rewrite all current call sites. |  |

**User's choice:** Migrate the thin wrapper and key path only.

**Notes:** Avoid turning Phase 28 into a broad cross-service migration.

| Option | Description | Selected |
| --- | --- | --- |
| Fail closed | Refuse to emit without trusted identity. | yes |
| Best-effort partial event | Write available fields. |  |
| Silently skip non-critical events | Drop event on missing identity. |  |

**User's choice:** Fail closed with a testable error.

**Notes:** Partial or silent behavior would break audit/replay trust.

---

## Reason-Code And Version Placement Convention

| Option | Description | Selected |
| --- | --- | --- |
| `reason_codes: list[str]` | Unified list format for all decision payloads. | yes |
| `reason_code` | Keep singular field. |  |
| Allow both | Service-specific choice. |  |

**User's choice:** Standardize on `reason_codes: list[str]`.

**Notes:** Legacy `reason_code` can be normalized by wrappers.

| Option | Description | Selected |
| --- | --- | --- |
| First-seen de-duplication | Preserve business priority order. | yes |
| Alphabetical sorting | Stable sorted snapshots. |  |
| Caller-owned normalization | No shared normalization. |  |

**User's choice:** First-seen de-duplication.

**Notes:** `reason_codes[0]` should preserve primary-reason semantics.

| Option | Description | Selected |
| --- | --- | --- |
| `redacted_payload.versions` | Nested versions object. | yes |
| Flat payload keys | `policy_version`, `model_version`, `tool_version` at payload top level. |  |
| `resource_refs` | Treat versions as resource refs. |  |

**User's choice:** Put versions under `redacted_payload.versions`.

**Notes:** Envelope top level keeps only `redaction_policy_version`.

| Option | Description | Selected |
| --- | --- | --- |
| Basic convention plus tests | Non-empty snake_case, de-duped, no global allowlist. | yes |
| Global allowlist | Every reason code pre-registered. |  |
| No naming restriction | No shared convention. |  |

**User's choice:** Basic convention plus tests.

**Notes:** A global allowlist would prematurely bind later service phases.

---

## Redaction, Resource Refs, And Initial Coverage

| Option | Description | Selected |
| --- | --- | --- |
| Tighten helpers plus focused tests | Foundation helpers and key-path regressions. | yes |
| Add helpers only | No current writer adaptation. |  |
| Rewrite all writer payloads/refs | Broad migration. |  |

**User's choice:** Tighten common helpers plus focused key-path tests.

**Notes:** Establish the foundation without moving later domain migrations into Phase 28.

| Option | Description | Selected |
| --- | --- | --- |
| Stable typed refs / hashes / ids only | No raw payloads, prompts, tool args, user text, PII, or secrets. | yes |
| Allow limited business fields | Store some order/refund identifiers directly. |  |
| Service-specific choice | Each service decides. |  |

**User's choice:** `resource_refs` only contain stable typed refs, hashes, and ids.

**Notes:** Business identifiers should use typed refs, hashes, or business fact / evidence refs when needed.

| Option | Description | Selected |
| --- | --- | --- |
| Check payload and refs | Redaction guard covers both `redacted_payload` and `resource_refs`. | yes |
| Check payload only | Refs rely on review. |  |
| Check approval/action refs only | Partial guard. |  |

**User's choice:** Redaction guard must inspect `resource_refs` too.

**Notes:** Otherwise unsafe data can bypass the redaction boundary through refs.

| Option | Description | Selected |
| --- | --- | --- |
| Contract + negative leakage + wrapper compatibility | Strictness, normalization, leakage, wrapper, and allocator regressions. | yes |
| Happy path emit mainly | Basic successful emission. |  |
| DB/migration mainly | Storage behavior focus. |  |

**User's choice:** Test contract, negative leakage, and wrapper compatibility.

**Notes:** Include sequence allocator non-regression coverage.

---

## The Agent's Discretion

- Exact helper/class names beyond `DecisionEventEnvelopeV1` and `emit_decision_event(...)`.
- Exact test file split.
- Exact explicit error class names for contract and identity failures.

## Deferred Ideas

- Full service-specific event payload migrations remain owned by later Tool, Memory, RAG, Approval, Action, Replay/Eval phases.
