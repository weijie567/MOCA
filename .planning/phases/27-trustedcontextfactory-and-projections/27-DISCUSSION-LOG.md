# Phase 27: TrustedContextFactory and Projections - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `27-CONTEXT.md` -- this log preserves the auto-selected alternatives considered.

**Date:** 2026-06-22
**Phase:** 27 - TrustedContextFactory and Projections
**Mode:** `$gsd-discuss-phase 27 --auto`
**Areas discussed:** Canonical context source, projection APIs, integration scope, intent/slot registry freeze, verification strategy

---

## Canonical Context Source

| Option | Description | Selected |
| --- | --- | --- |
| Exact `contract-spec.md` §8.0 canonical field set | Implement `TrustedContext` with only the normative identity/scope/run fields and reject projection-local widening. | yes |
| Compatibility-shaped context with request/projection metadata included | Easier migration, but violates APF-03/APF-04 no-widening requirements. | no |
| Let existing AgentState remain the source | Least code, but checkpointed state can carry stale permissions/scope and is not a trusted auth boundary. | no |

**Auto choice:** Exact `contract-spec.md` §8.0 canonical field set.
**Notes:** `request_id`, `effective_at`, `channel`, and version metadata are explicitly projection-local or metadata.

---

## Projection APIs

| Option | Description | Selected |
| --- | --- | --- |
| Add explicit service projection methods | Derive `ToolCallContext`, `KnowledgeContext`, `MemoryContext`, `ApprovalContext`, `ReplayContext`, and `IntentPolicyContext` from one canonical trusted source. | yes |
| Keep each module constructing context locally | Lower immediate effort, but repeats the current gap this phase is meant to close. | no |
| Only implement tool and knowledge projections | Covers current code seams, but leaves memory/approval/replay/intent without the common foundation promised by APF-04. | no |

**Auto choice:** Add explicit service projection methods.
**Notes:** Existing public schemas should remain compatible where possible, especially `tool_context.v2` and `KnowledgeContext`.

---

## Integration Scope

| Option | Description | Selected |
| --- | --- | --- |
| Minimal compatibility-preserving integration | Add factory and update current construction seams enough to prove usage without broad graph/service rewrites. | yes |
| Full graph and platform service migration | More complete, but belongs across Phases 29-35 and would exceed Phase 27 boundary. | no |
| Docs-only contract clarification | Too weak for APF-03/APF-04, which require factory and projection behavior. | no |

**Auto choice:** Minimal compatibility-preserving integration.
**Notes:** Prompt projectors stay prompt-safe text projectors and should not become trusted identity authority.

---

## Intent and Slot Registry Freeze

| Option | Description | Selected |
| --- | --- | --- |
| Read-only registry wrappers over existing policy data | Freezes catalog shape for downstream phases without changing runtime intent behavior. | yes |
| Defer all registry work to Phase 32 | Leaves Tool/Memory/RAG phases free to invent temporary policy shapes. | no |
| Rewrite intent routing now | Out of scope for Phase 27 and belongs to Phase 32 graph migration. | no |

**Auto choice:** Read-only registry wrappers over existing policy data.
**Notes:** The registry should expose stable read APIs over `INTENT_DEFINITIONS`, `REQUIRED_SLOT_POLICY`, route policy, and precedence data.

---

## Verification Strategy

| Option | Description | Selected |
| --- | --- | --- |
| Contract + projection + focused integration tests | Directly proves APF-03/APF-04 and catches no-widening regressions. | yes |
| Only unit-test the factory | Misses current construction seams and projection leakage risks. | no |
| Rely on existing graph/tool tests | Existing tests do not prove a single trusted source or projection-local metadata boundaries. | no |

**Auto choice:** Contract + projection + focused integration tests.
**Notes:** Tests should explicitly prove canonical fields are exact and projection-local fields do not leak.

---

## the agent's Discretion

- Exact module path, method names, and task split can be decided during planning.
- Migration should stay small and verify thoroughly.
- No deferred ideas were folded into Phase 27 scope.

## Deferred Ideas

- Phase 28 decision event envelope.
- Phase 29 tool policy/runtime platform.
- Phase 30 business fact authority.
- Phase 31 memory platform.
- Phase 32 intent graph migration.
- Phase 33 RAG/claim verification.
- Phase 34 approval/action boundary hardening.
- Phase 35 replay/eval hardening.
