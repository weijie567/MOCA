# Phase 31: Memory Platform Boundary - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `31-CONTEXT.md` - this log preserves the alternatives considered.

**Date:** 2026-06-28
**Phase:** 31-memory-platform-boundary
**Areas discussed:** service boundary vocabulary, load timing, authority refs, merchant scope, write policy depth, replay/audit hooks
**Mode:** `$gsd-discuss-phase 31`; plain-text interactive discussion after all gray areas were selected.

---

## Service Boundary Vocabulary

| Option | Description | Selected |
|--------|-------------|----------|
| Adapter-first `MemoryContextService` | Add a service/facade while preserving most existing graph-facing names. | |
| Full rename migration | Rename node/state/service vocabulary broadly. | partial |
| Schema/test boundary only | Add schemas/tests but leave service and graph-facing names mostly unchanged. | |

**Decision:** Use the selected option in a constrained form: graph-facing target-boundary migration, not whole-repo mechanical rename. Rename or wrap public node/state/projection vocabulary where it clarifies `session_context` vs reviewed `memory_context`; preserve persistence-layer names and storage contracts.

---

## Load Timing

| Option | Description | Selected |
|--------|-------------|----------|
| Two-stage context load | Early same-thread session context; late reviewed long-term/case memory after scope/business context is explicit or trusted. | yes |
| Single upfront load | Load session, long-term, and case memory together early. | |
| Late-only memory | Load all memory only after slots/scope are resolved. | |

**Decision:** Two-stage context load: `session_context_load` early for same-thread continuity, `reviewed_memory_context_retrieve` late for reviewed long-term/case contextual assistance.

---

## Authority Refs

| Option | Description | Selected |
|--------|-------------|----------|
| Typed contextual refs | Memory produces its own contextual-only refs at the source. | yes |
| Prompt/runtime labels | Label memory as non-authoritative in prompts/runtime text only. | |
| Downstream verifier guard | Rely on verifiers to reject memory refs at authority boundaries. | defense-in-depth |

**Decision:** Typed contextual refs are the primary boundary. Downstream verifier deny-lists are required as defense-in-depth. Prompt labels are useful but non-normative.

---

## Merchant Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Deny-first trusted scope | Retrieval scope only from `TrustedContext`, `MerchantScopeV1`, explicit trusted inputs, or trusted business context. | yes |
| Same-merchant sharing by default | Memory shared by default when merchant ids match. | |
| User-only memory | Long-term/session/case memory stays user-bound by default. | |

**Decision:** Deny-first trusted scope with explicit scoped sharing. Merchant-scoped sharing is allowed only for explicitly merchant-scoped, reviewed, PII-safe, non-deleted, non-expired memory that the current actor's trusted merchant scope permits. Global memory is unsupported.

---

## Write Policy Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Boundary plus critical lifecycle tests | Standardize write decision metadata and prove fail-closed lifecycle behavior. | yes |
| Full lifecycle now | Build complete review UI, redaction workflow, APIs, RLS, and memory operations product. | |
| Read boundary only | Only harden retrieval/context boundaries and document write policy. | |

**Decision:** Implement write policy boundary and fail-closed lifecycle coverage. Do not build the full memory operations product in Phase 31.

---

## Replay / Audit Hooks

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal status refs now | Stabilize memory load/retrieve/write status metadata as Phase 35 handoff points. | yes |
| Full replay event coverage now | Emit complete memory lifecycle replay/audit events in Phase 31. | |
| No replay changes | Leave replay/audit untouched until Phase 35. | |

**Decision:** Add audit-ready memory status refs now, but keep them contextual-only and non-authoritative. Full replay event coverage remains Phase 35 work.

---

## Confirmed Repository Basis

- `EvidenceRefV1` is defined in `src/knowledge/schemas.py`.
- `BusinessFactRefV1` is defined in `src/tools/contracts.py`.
- `ApprovalRequestCreateCommand.evidence_refs` is typed as `list[EvidenceRefV1]`.
- `ReplayEventV3` has strict `resource_refs` / `redacted_payload` fields.
- `src/platform/trusted_context.py` defines `TrustedContextFactory` and `MerchantScopeV1`.
- Memory storage models are in `src/db/models.py`, not `src/models`.
- Long-term/case memory already has scope, review, PII, deleted/expired, tombstone, candidate/source identity, and write-event foundations.
- `memory_write_` events are registered in replay validators, while full memory lifecycle replay coverage remains deferred.

## Deferred Ideas

- Full graph vocabulary migration: Phase 32.
- RAG claim verification: Phase 33.
- Approval/action authority binding: Phase 34.
- Full replay/eval coverage: Phase 35.
- Review UI, operator workflow, full memory APIs, DB/RLS redesign, and memory microservice extraction: future hardening.
