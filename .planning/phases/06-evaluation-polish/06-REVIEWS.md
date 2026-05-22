---
phase: 6
reviewers: [codex]
reviewed_at: 2026-05-19T12:30:00Z
plans_reviewed: [06-01-PLAN.md, 06-02-PLAN.md, 06-03-PLAN.md, 06-04-PLAN.md]
rounds: 2
---

# Cross-AI Plan Review — Phase 6

## Round 2: Codex Review (Post-Revision)

### Summary

The revisions materially address the four prior high-priority concerns. Plan 01 now adds seed-reference validation and matching-rule documentation. Plan 02 gives a much stronger FakeLLM contract that explicitly ties deterministic outputs to LangGraph routing. Plan 03 adds demo preflight checks. However, several fixes are still plan-level assertions rather than enforceable implementation contracts. The biggest remaining risk is that CI-mode agent evaluation could still pass by synthetic scoring unless the implementation is required to inspect actual graph traces, node transitions, interrupts, and resume paths.

### Previous Concerns Status

| Concern | Status |
|---------|--------|
| Seed ID validation | PARTIALLY RESOLVED — validator added but not wired into Task 2 verify |
| Chinese normalization rules | RESOLVED |
| FakeLLM graph routing | PARTIALLY RESOLVED — contract specified but acceptance lacks trace assertions |
| Demo preflight checks | RESOLVED |

### New Concerns

- **HIGH:** Agent eval acceptance can pass without proving graph routing. Need per-case trace assertions (nodes executed, edges taken, interrupt/resume).
- **HIGH:** Approval approved/rejected cases don't specify how CI mode injects approval decision after interrupt. Must use `Command(resume=...)`.
- **MEDIUM:** Seed validator should also validate RAG golden set (`expected_doc_ids`, `expected_chunk_ids`).
- **MEDIUM:** Chinese numeral example contradicts "not required" statement — remove example.
- **MEDIUM:** Demo jq projection assumes flat response shape — should confirm actual API schema.
- **LOW:** README says "Next.js" but project uses React + Vite.

### Risk Assessment

**Overall risk: MEDIUM** (improved from round 1, same level but different concerns).

---

## Round 1: Codex Review (Original Plans)

### Summary

Phase 6 plan was coherent and well-scoped. Main risks were fixture drift, overly broad agent scoring semantics, README/docs claiming metrics before reproducibly generated, and demo scripts depending on seeded data.

### Key Concerns (all addressed in revision)

- HIGH: Seed data ID validation missing → Added Task 3
- HIGH: Chinese normalization rules missing → Added Task 4 (MATCHING_RULES.md)
- HIGH: FakeLLM replay vs graph routing → Added routing contract table
- HIGH: Demo script brittleness → Added preflight health checks

**Round 1 overall risk: MEDIUM**

---

## Consensus Summary

### Agreed Strengths (both rounds)
- Wave-based dependency ordering is sound
- Deterministic CI path (FakeLLM, no secrets) is correct architecture
- Safety threshold at 100% is non-negotiable and correctly enforced
- README/docs layered structure serves both interviewers and developers
- Seed validation and matching rules are meaningful additions

### Remaining Actionable Items
1. Wire `validate_golden_seeds.py` into Plan 01 Task 2 verify step
2. Add trace-based acceptance criteria to Plan 02 eval_agent.py (nodes_executed assertion)
3. Specify `Command(resume=...)` for approval approved/rejected CI flow
4. Fix "Next.js" → "React + Vite" in Plan 03 README task
5. Remove Chinese numeral example from MATCHING_RULES.md (or note as future)
6. Confirm API response schema in Plan 03 demo script read_first

### Execution Resolution

All remaining actionable items were closed during Phase 6 execution. In addition, the seed validator now checks RAG golden set `expected_doc_ids` and `expected_chunk_ids` against the current `data/policies` corpus and `chunk_markdown()` output, closing the Round 2 medium-risk RAG reference validation concern.

### Divergent Views
(Single reviewer — no divergent views)
