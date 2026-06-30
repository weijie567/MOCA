---
created: 2026-06-22T13:06:19.271Z
title: Archive old phase directories
area: planning
files:
  - .planning/phases
  - .planning/milestones
  - .planning/ROADMAP.md
  - .planning/STATE.md
---

## Problem

After starting v1.9 Agent Platform Foundation, `.planning/phases/` still contains completed Phase 24, Phase 24.x, and Phase 25 directories. `gsd-sdk query init.new-milestone`, `state.load`, `roadmap.analyze`, and `init.plan-phase 26` now read the correct v1.9 state, but `gsd-sdk query validate.health` still reports non-blocking warnings because old phase directories remain active while future Phase 26-35 directories are not all present.

## Solution

Handle as a separate cleanup task after Phase 26 planning is stable. Archive old completed directories into milestone-specific folders such as `.planning/milestones/v1.7-phases/` and `.planning/milestones/v1.8-phases/`, then rerun GSD health checks. Do not use `phases.clear --confirm`; it deletes instead of archiving.

## Completion

Completed on 2026-06-30 via `$gsd-cleanup`.

- Archived Phase 24 and Phase 24.x directories into `.planning/milestones/v1.7-phases/`.
- Archived Phase 25 into `.planning/milestones/v1.8-phases/`.
- Archived Phase 26 through Phase 35.1 into `.planning/milestones/v1.9-phases/`.
- Left backlog item `999.1-evaluate-mem0-as-optional-backend-behind-memorycontextservic` in `.planning/phases/`.
- Verification entry points: `find .planning/phases -maxdepth 1 -mindepth 1 -type d -print` and `gsd-tools.cjs audit-open`.
