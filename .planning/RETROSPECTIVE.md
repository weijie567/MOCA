# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-05-22
**Phases:** 6 | **Plans:** 36 | **Tasks:** 94

### What Was Built

- A merchant operations agent that answers refund/rule questions with business context and cited policy evidence.
- A LangGraph workflow with read tools, risk assessment, approval interrupt/resume, action drafts, and run-level trace replay.
- A tenant-scoped FastAPI/Postgres/pgvector backend with deterministic Chinese demo data and reproducible Docker Compose startup.
- A React/Vite support console with SSE progress, evidence and trace panels, role switching, and approval handling.
- A final evaluation layer with golden sets, JSON/Markdown reports, CI lint/unit gates, demo script, README, and technical docs.

### What Worked

- Building in dependency order kept the architecture explainable: foundation, RAG, graph, approval, frontend, then evaluation.
- Deterministic tests and FakeLLM boundaries gave reliable CI coverage without requiring provider keys.
- Treating approval as a graph node made the human-in-the-loop flow auditable and demo-friendly.
- Keeping eval reports and demo docs as first-class deliverables made the project easier to present, not just easier to run.

### What Was Inefficient

- Phase 1 verification stayed marked `human_needed` after later phases effectively proved the stack, which created artifact-audit noise at milestone close.
- Early RAG scoring exposed that a golden-set pass cannot be assumed from implementation correctness; retrieval quality needed a dedicated gap-closure pass.
- Demo/API response shapes drifted across phases, requiring late fixes in the demo script and docs.

### Patterns Established

- Use deterministic contract checks for graph behavior, then reserve live provider/DB checks for local smoke and evaluation commands.
- Keep `docs/` as the deep technical layer and `README.md` as the scan-friendly project showcase.
- Record risk rules, permission boundaries, and trace payload decisions explicitly because they are core to explaining agent safety.

### Key Lessons

1. Verification artifacts need a closure pass after later evidence resolves early `human_needed` states.
2. RAG evaluation should include diagnostics early enough to distinguish retrieval-quality gaps from stale expected labels.
3. Demo scripts should fail fast on response shape mismatches; otherwise they can mask broken core flows.
4. The final milestone should include documentation and evaluation as deliverables, not cleanup afterthoughts.

### Cost Observations

- Model mix: quality profile with Sonnet planner/executor defaults.
- Sessions: multi-session milestone execution across 14 calendar days.
- Notable: The highest return came from using focused verification artifacts and deterministic local gates before live smoke checks.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | multi-session | 6 | Established phase-by-phase planning, execution, code review, verification, and final archive workflow |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 164 non-integration tests in final CI-equivalent gate | Phase 6 verifier passed 23/23 must-haves | Deterministic FakeLLM and JSONL golden-set gates avoid provider dependency in CI |

### Top Lessons (Verified Across Milestones)

1. Agent systems need separate gates for deterministic contracts, DB-backed integration, and live provider behavior.
2. Human-in-the-loop approval is easiest to reason about when it is a persisted graph state transition, not a side-channel.
3. Demo readiness depends on docs, scripts, and seed data staying synchronized with actual API response shapes.
