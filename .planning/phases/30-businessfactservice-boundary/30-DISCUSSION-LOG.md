# Phase 30: BusinessFactService Boundary - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `30-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-06-27
**Phase:** 30-businessfactservice-boundary
**Areas discussed:** Service boundary and ownership, result contracts, scope proof and no-leak semantics, ToolPlatform integration, verification strategy
**Mode:** `$gsd-next` routed to `$gsd-discuss-phase 30`; interactive question UI unavailable, so conservative defaults were selected per Codex skill fallback.

---

## Service Boundary And Ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Add `BusinessFactService` under `src/business/` and make it the new authority while keeping compatibility wrappers | Aligns with `contract-spec.md` ownership and minimizes code churn. | yes |
| Keep extending `BusinessToolService` as the main authority | Lower churn but keeps tool facade and domain service concepts conflated. | |
| Create a separate package/service boundary outside `src/business/` now | More architectural separation, but premature for modular monolith phase. | |

**Chosen default:** Add `BusinessFactService` under `src/business/`, keeping `BusinessToolService` as compatibility/tool-facing adapter only where needed.

---

## Result Contracts

| Option | Description | Selected |
|--------|-------------|----------|
| Add dedicated `BusinessFactResultV1` and keep `ToolResultV2` as wrapper/transport | Matches Phase 30 contract and keeps domain result independent from ToolPlatform. | yes |
| Reuse `ToolResultV2` as the only fact result | Smaller change, but leaves no stable domain service result contract. | |
| Defer result schema until Phase 33 claim verification | Too late; Phase 33 depends on scoped `BusinessFactRefV1` authority from Phase 30. | |

**Chosen default:** Add dedicated `BusinessFactResultV1`; convert/wrap into `ToolResultV2` only at the tool boundary.

---

## Scope Proof And No-Leak Semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Enforce domain ownership proof in `BusinessFactService` before emitting facts/refs | Resolves Phase 29 `requires_domain_scope_check` marker and Phase 29.5 deferred item. | yes |
| Keep raw integration `merchant_can_access` as final authority | Already improved in Phase 29.5, but remains an interim seam rather than service boundary. | |
| Preserve API 403/404 semantics directly in tool/service results | Would leak existence semantics into agent/tool paths. | |

**Chosen default:** Service/tool paths must no-leak: denied reads emit no facts, no refs, no prompt-visible business summaries, and safe generic errors.

---

## ToolPlatform Integration

| Option | Description | Selected |
|--------|-------------|----------|
| ToolPlatform -> BusinessToolExecutor -> BusinessFactService | Keeps Phase 29 runtime gates while moving domain proof behind the business service. | yes |
| Graph calls BusinessFactService directly from `investigate` | Could work eventually, but bypasses ToolPlatform planner/runtime contracts in this phase. | |
| Keep UnifiedToolManager behavior unchanged | Compatibility-safe but would not close the boundary. | |

**Chosen default:** Business tools should flow through ToolPlatform runtime gates and delegate domain facts to `BusinessFactService`.

---

## Verification Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| RED tests first for schema, service, no-leak, and marker enforcement | Matches GSD phase pattern and makes boundary regressions explicit. | yes |
| Direct implementation followed by broad regression | Faster initially but risks missing subtle authority leaks. | |
| Only update existing tests opportunistically | Insufficient for a platform boundary phase. | |

**Chosen default:** Start with focused RED tests, then implement contracts and integration, then run focused and affected regression suites.

---

## Agent Discretion

- Exact module/file split.
- Exact error code names and result-to-tool conversion names.
- Whether unsupported `get_logistics` / `get_merchant_risk` are minimally implemented as typed unavailable service reads or made consistently unavailable at catalog/runtime.
- Exact route migration depth, as long as current business fact authority and tool/graph boundaries are closed.

## Deferred Ideas

- Memory, graph, RAG claim verification, approval/action, replay/eval, and DB/RLS follow-up work remain assigned to later phases per ROADMAP and Phase 29.5 deferred todos.
