# Phase 63: Safety Taxonomy And Risk Vocabulary - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 63-safety-taxonomy-and-risk-vocabulary
**Mode:** `$gsd-discuss-phase 63 --auto`
**Areas discussed:** Taxonomy ownership, risk severity/disposition split, safety routing, extraction boundaries, tests and migration

---

## Taxonomy Ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Single taxonomy owner | Create a registry/helper owner consumed by risk, draft, and intent code. | ✓ |
| Keep local sets with parity tests | Keep implementation local but add tests to detect drift. | |
| Broad action-platform redesign | Rework action execution and approval architecture now. | |

**Auto choice:** Single taxonomy owner.
**Notes:** Recommended because Phase 63's goal is to prevent drift between `risk_gate`, `action_draft`, and `intent_policy`. Broad action execution redesign is out of scope.

---

## Risk Severity And Disposition

| Option | Description | Selected |
|--------|-------------|----------|
| Split severity and disposition | Model low/medium/high separately from manual-review/blocked/approval routing. | ✓ |
| Keep overloading `risk_level` | Continue writing disposition strings into risk-level fields. | |
| Replace all approval schemas immediately | Do a breaking schema migration across approval/action storage. | |

**Auto choice:** Split severity and disposition.
**Notes:** Recommended because `RiskAssessment` allows only `low|medium|high`, while runtime code writes `manual_review` and `blocked`. Compatibility fields can remain during migration.

---

## Safety Routing

| Option | Description | Selected |
|--------|-------------|----------|
| Derive from policy definitions/registry | Evidence-required and action-bound routing consumes one policy source. | ✓ |
| Keep routing fallback sets | Keep hand-written runtime fallback sets. | |
| Move safety routing to LLM | Let classifier output decide safety route directly. | |

**Auto choice:** Derive from policy definitions/registry.
**Notes:** Recommended because existing `INTENT_DEFINITIONS` already carries evidence and risk metadata, and safety routes must remain backend deterministic.

---

## Extraction Boundaries

| Option | Description | Selected |
|--------|-------------|----------|
| Centralize named deterministic helpers | Share action aliases and money/risk extraction assumptions where useful. | ✓ |
| Leave duplicated regex/keywords | Keep extraction behavior local to each node. | |
| Add broad natural-language executor | Convert arbitrary action text into executable actions. | |

**Auto choice:** Centralize named deterministic helpers.
**Notes:** Recommended only for bounded taxonomy/extraction assumptions. Arbitrary action execution remains out of scope and unsafe.

---

## Tests And Migration

| Option | Description | Selected |
|--------|-------------|----------|
| TDD parity first, then migrate callers | Capture current behavior, add registry/helpers, migrate call sites, then add drift guards. | ✓ |
| Refactor first, test later | Move code before proving current behavior. | |
| Large single plan | Put taxonomy, risk schema, routing, tests, and docs into one plan. | |

**Auto choice:** TDD parity first, then migrate callers.
**Notes:** Recommended because this phase touches safety-critical behavior. Plans should be split if multiple boundaries are involved.

---

## the agent's Discretion

- Exact module/package name for the taxonomy owner.
- Whether compatibility helpers are dataclasses, Pydantic models, enums, or plain frozen mappings.
- Exact plan split, as long as plan granularity remains small enough for review and execution.

## Deferred Ideas

- RAG risk labels stay Phase 64.
- Trace/event/console labels stay Phase 65.
- Dev/test/config hygiene stays Phase 66.
- Broader state-machine registry/DB CHECK hardening stays suggested Phase 67.
