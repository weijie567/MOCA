# Codebase Concerns

**Analysis Date:** 2026-05-09

## Tech Debt

**Repository skeleton not started:**
- Issue: The repository contains project planning and research only; there is no implementation scaffold for API, frontend, data, or infrastructure
- Why: Planning was completed before any code generation began
- Impact: Requirements appear mature, but execution risk is still entirely unproven
- Fix approach: Start Phase 1 by locking repository structure, manifests, Docker Compose, schema location, and seed-data workflow

**Planning duplication across files:**
- Issue: Core value, target stack, and scenario framing are repeated across `deep-research-report.md`, `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, and `.planning/ROADMAP.md`
- Why: Each artifact optimizes for a different planning step
- Impact: Drift is likely once implementation forces tradeoffs
- Fix approach: Keep one canonical architecture decision record or README summary, and let other docs reference it

## Known Bugs

**Unwanted Finder artifacts committed locally:**
- Symptoms: `.DS_Store` exists at repository root and inside `.planning/`
- Trigger: Browsing the repo in Finder on macOS
- Workaround: Remove the files and ignore them in `.gitignore`
- Root cause: No repo-level hygiene for OS-generated files

## Security Considerations

**Secrets contract not defined:**
- Risk: The first implementation phase may introduce ad hoc environment variables and unsafe local secrets handling
- Current mitigation: None; there is no `.env.example` or secret-loading policy
- Recommendations: Define environment keys and local/dev secret handling before adding service clients

**Authorization complexity already high on paper:**
- Risk: Roles, approval rules, tenant boundaries, and audit requirements are specified before code exists, making it easy to underbuild the security layer
- Current mitigation: Requirements explicitly call for scopes, risk gating, and tenant filtering
- Recommendations: Build auth and audit primitives before agent orchestration to avoid insecure retrofits

## Performance Bottlenecks

**Planning-to-build gap:**
- Problem: The documented scope is large for a six-week MVP and a solo developer
- Measurement: 62 v1 requirements across 6 phases, with backend, RAG, frontend, approvals, and evaluation all planned
- Cause: The design optimizes for interview breadth as much as for delivery focus
- Improvement path: Phase 3 narrowed to read-only happy path; write tools and eval reporting moved to Phase 4/6

## Fragile Areas

**Requirement ambition vs repository maturity:**
- Why fragile: The documents are specific enough to create false confidence, but there is no code to test whether the architecture remains simple in practice
- Common failures: Over-scaffolding, premature abstractions, and phase slippage
- Safe modification: Enforce thin vertical slices instead of building all infrastructure upfront
- Test coverage: None

**Language consistency:**
- Why fragile: English framing documents and Chinese requirement bodies will affect naming, prompts, UI copy, and dataset conventions
- Common failures: Inconsistent API fields, mixed-language fixtures, and confusing demo UX
- Safe modification: Declare a repo language policy now
- Test coverage: None

## Scaling Limits

**Implementation bandwidth:**
- Current capacity: One planning-focused solo developer
- Limit: Parallel backend, retrieval, frontend, auth, and evaluation work will quickly exceed the intended MVP window
- Symptoms at limit: Half-built infrastructure, incomplete demo flow, and weak finish quality
- Scaling path: Cut scope to one end-to-end refund scenario and postpone secondary capabilities aggressively

## Dependencies at Risk

**Undecided code scaffold:**
- Risk: The repo has no committed package/runtime baseline, so Phase 1 could burn time on setup decisions that should already be settled
- Impact: All downstream work is blocked by bootstrap churn
- Migration plan: Commit a minimal scaffold with one language/runtime choice and hold the line through MVP

## Missing Critical Features

**Root onboarding document:**
- Problem: No `README.md` explains what the repo is, how to navigate `.planning/`, or what has and has not been built
- Current workaround: Read `deep-research-report.md` and `.planning/*.md` manually
- Blocks: Fast onboarding, external review, and open-source credibility
- Implementation complexity: Low

**Executable proof:**
- Problem: No source code, no tests, no containers, no API contract files
- Current workaround: Planning documents describe intended behavior
- Blocks: Any real validation of feasibility, cost, or demo quality
- Implementation complexity: High

## Test Coverage Gaps

**Entire implementation surface:**
- What's not tested: Everything runtime-related
- Risk: Requirements quality may hide build and integration risk until late
- Priority: High
- Difficulty to test: Moderate once the first scaffold exists

---
*Concerns audit: 2026-05-09*
*Update as code lands and planning risks are retired*
