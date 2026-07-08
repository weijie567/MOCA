# Roadmap: MOCA

## Milestones

- ✅ **v2.1 Core Subsystem Hardening** — Phases 37-60 plus inserted Phase 48.1 (shipped 2026-07-08). Archive: `.planning/milestones/v2.1-ROADMAP.md`
- ✅ **v2.0 Merchant Scope Hardening** — Phase 36 (shipped 2026-06-30). Archive: `.planning/milestones/v2.0-ROADMAP.md`
- ✅ **v1.9 Agent Platform Foundation** — Phases 26-35.1 (shipped 2026-06-30). Archive: `.planning/milestones/v1.9-ROADMAP.md`
- ✅ **v1.8 Intent Routing Safety Hardening** — Phase 25 (shipped 2026-06-21). Archive: `.planning/milestones/v1.8-phases/`
- ✅ Earlier milestones v1.0-v1.7 — archived under `.planning/milestones/`

## Current Planning State

No active milestone is defined. Start the next milestone with `$gsd-new-milestone`, which will create fresh requirements and a new current roadmap section.

## Last Completed Milestone: v2.1 Core Subsystem Hardening

**Status:** shipped 2026-07-08
**Scope:** Phases 37-60 plus inserted Phase 48.1
**Plans:** 87/87 complete
**Requirements:** 24/24 complete
**Audit:** `.planning/milestones/v2.1-MILESTONE-AUDIT.md` — `passed` / `archive_ready`

**Delivered:**

- Consolidated ToolPlatform declarations, runtime output-schema validation, failure handling, policy gates, and legacy manager cleanup.
- Decoupled intent recognition and preserved multi-intent utterances through bounded `TaskPlan` semantics without weakening the single-intent route contract.
- Rebuilt memory layering around Case Working Context, thread-case M:N linkage, session-context boundaries, reviewed case precedent generation, explicit preference-only long-term memory, and memory compatibility cleanup.
- Migrated `investigate` to a bounded read-only ReAct loop and completed the canonical 15-node Agent Graph cutover with legacy runtime route/name cleanup.
- Aligned recommendation/RAG claim fail-closed behavior, canonical `risk_gate`/`approval_gate` behavior, and approval-resume terminal memory finalization.
- Closed archive evidence gaps with formal verification, Nyquist validation, UAT, security signoff, and a passed v2.1 milestone audit.

**Accepted follow-ups:**

- Phase 49 bounded ReAct replay parent-operation identity remains an accepted limitation for a future replay/event hardening milestone if needed.
- Historical legacy graph-name references remain accepted only as historical/test/documentation refs after Phase 58 cleanup.
- Legacy `/api/v1/agent/chat` background `memory_write` compatibility remains outside the current `agent-runs` frontend lifecycle.
- GSD tooling/reporting debt: `gsd-sdk query init.milestone-op` can report missing legacy audit agents even when the main orchestrator can run `gsd-integration-checker`.

## Next

Run `$gsd-new-milestone` to define the next version. Phase numbering should continue after Phase 60 unless the new milestone explicitly inserts decimal or backlog work.
