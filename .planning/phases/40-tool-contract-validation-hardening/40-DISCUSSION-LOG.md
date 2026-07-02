# Phase 40: Tool Contract Validation Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-02
**Phase:** 40-tool-contract-validation-hardening
**Areas discussed:** action output schema, domain-scope marker backstop, JSON Schema subset, UnifiedToolManager scope

---

## Action Output Schema

| Option | Description | Selected |
|--------|-------------|----------|
| Strict action output schema | Derive `create_coupon_grant_draft` output schema from the real `ActionService` payload and fail closed on drift. | yes |
| Leave generic | Keep `_GENERIC_OBJECT_SCHEMA` because action output hardening was outside TPH-01. | |
| Full all-tool rewrite | Invent strict schemas for unavailable/no-data tools too. | |

**User's choice:** Strict action output schema.
**Notes:** `get_logistics`, `get_merchant_risk`, and `search_sop` remain strict no-data schemas until they produce real payloads.

---

## Ownership Marker Backstop

| Option | Description | Selected |
|--------|-------------|----------|
| Architecture/backstop test | Keep runtime split and add tests ensuring domain marker tools stay behind BusinessFactService merchant-scope/no-leak enforcement. | yes |
| Policy DB lookup | Move resource ownership lookup into `ToolPolicyEngine`. | |
| Executor base enforcement | Make marker consumption a runtime base-class requirement now. | |

**User's choice:** Architecture/backstop test.
**Notes:** Runtime ownership belongs at the data boundary; policy remains IO-free.

---

## JSON Schema Subset

| Option | Description | Selected |
|--------|-------------|----------|
| Extend local subset + meta guard | Add missing advertised keywords and fail descriptor schemas that use unsupported keywords. | yes |
| Add `jsonschema` dependency | Replace local validator with full JSON Schema library. | |
| Leave as-is | Accept that some prompt-safe schema keywords would be silently ignored. | |

**User's choice:** Extend local subset + meta guard.
**Notes:** Include `maxLength`, `minimum`, `maximum`, and `exclusiveMaximum`; apply numeric bounds to integer and number.

---

## UnifiedToolManager Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Defer API cleanup | Keep `UnifiedToolManager` compatibility untouched in Phase 40 and handle removal in a separate breaking cleanup phase. | yes |
| Remove now | Delete the compatibility adapter as part of validation hardening. | |
| Long-term deprecate | Add warnings but keep dual entrypoints indefinitely. | |

**User's choice:** Defer API cleanup.
**Notes:** Source confirms `UnifiedToolManager` is exported and documented as a legacy compatibility adapter, so removal requires a separate API decision/spec phase.

---

## the agent's Discretion

- Exact architecture-test placement and helper names.
- Exact strictness depth for nested dynamic action payload objects, bounded by the rule that raw/debug fields must fail.

## Deferred Ideas

- `UnifiedToolManager` breaking cleanup/API removal.
- Runtime executor-base consumption of `requires_domain_scope_check`.
- Full JSON Schema draft support or `jsonschema` dependency.
