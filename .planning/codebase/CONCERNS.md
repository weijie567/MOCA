# Codebase Concerns

**Analysis Date:** 2026-06-05

## Tech Debt

**Codebase map drift:**
- Issue: `.planning/codebase/*` previously described a planning-only repository even though backend, frontend, tests, docs, and Phase 7 tool contracts now exist.
- Why: Codebase maps were generated early and not refreshed as part of later phase closeout.
- Impact: Planning agents and reviewers can make false assumptions such as “no `src/` or `tests/` exist.”
- Fix approach: Refresh `.planning/codebase` after major phase execution and before planning new phases that depend on architecture state.

**Planning artifact volume:**
- Issue: The repository now contains many phase artifacts, reviews, UAT, security checks, architecture docs, and research notes.
- Why: GSD workflow captures detailed evidence for each phase.
- Impact: Canonical facts can be hard to find, and stale docs can outlive implementation changes.
- Fix approach: Treat `.planning/ARCHITECTURE.md`, `.planning/codebase/*`, `README.md`, and `docs/architecture.md` as the high-level sources that must be refreshed after structural changes.

**Frontend verification lighter than backend:**
- Issue: Backend has broad pytest coverage, while frontend has narrower hook/component coverage.
- Impact: UI regressions, SSE timeline behavior, and responsive layout issues may slip through.
- Fix approach: Standardize frontend `npm test`, `npm run lint`, `npm run build`, and add a minimal browser smoke path.

## Known Bugs

**No current codebase-map blocker found:**
- The stale map issue has been corrected in this refresh.

**Repository hygiene items to watch:**
- `.DS_Store`, `.pytest_cache`, `.ruff_cache`, `.venv`, local `.env`, and generated caches should remain ignored/uncommitted.
- If any are already tracked, remove them only through an explicit cleanup commit.

## Security Considerations

**Approval/tool safety must stay centralized:**
- Risk: Future tools could bypass registry metadata or execute write behavior without approval constraints.
- Current mitigation: Phase 7 added typed tool registry contracts, side-effect metadata, caller authorization, and tests.
- Required habit: New tools must add contract, adapter, authorization, and registry tests.

**Tenant isolation remains a core invariant:**
- Risk: New repositories/routes can accidentally omit tenant filters.
- Current mitigation: Tenant isolation tests exist for core API routes.
- Required habit: Any new business-data route or repository method needs tenant-scoped tests.

**Secrets and model provider config:**
- Risk: `.env` and model credentials can leak into docs, fixtures, or committed config.
- Current mitigation: `.env.example` exists; `.env` is local.
- Required habit: Add environment keys to `.env.example`, not `.env`, and avoid placing secrets in planning artifacts.

## Performance Bottlenecks

**Graph and RAG latency:**
- Problem: Agent runs can include classification, context loading, retrieval, recommendation generation, approval assessment, and execution.
- Measurement: Latency instrumentation tests exist; production-grade SLO monitoring is not yet externalized.
- Improvement path: Keep node-level latency in trace steps, use golden evaluation for RAG changes, and defer complex observability until the MVP path is stable.

**Frontend streaming behavior:**
- Problem: SSE run updates can expose UI/state race conditions.
- Current mitigation: Frontend hook and backend streaming tests exist, but browser-level coverage is light.
- Improvement path: Add an end-to-end smoke scenario around agent run streaming and approval resume.

## Fragile Areas

**LangGraph interrupt/resume semantics:**
- Why fragile: Approval decisions resume a persisted graph thread and must preserve run, user, tenant, and approval context.
- Common failures: Wrong thread ID, duplicate decisions, expired approvals, missing trace continuation.
- Safe modification: Change approval flow only with API, integration, trace, and graph tests.

**Tool registry contracts:**
- Why fragile: Tools are both agent capabilities and safety boundaries.
- Common failures: Missing side-effect metadata, wrong caller visibility, untyped output, write behavior exposed to investigator mode.
- Safe modification: Extend `tests/agent/test_tools/` whenever adding/changing tools.

**RAG evidence integrity:**
- Why fragile: Policy evidence drives recommendations and approval decisions.
- Common failures: No-evidence hallucination, invalid citations, tenant/metadata mismatch, chunking drift.
- Safe modification: Run RAG tests and golden evaluation when changing retrieval, chunking, embeddings, or policy data.

## Scaling Limits

**Local demo architecture:**
- Current capacity: Strong for local prototype and interview-grade proof.
- Limit: Not yet a production deployment with managed secrets, external observability, autoscaling, or provider failover.
- Scaling path: Add OTel/Prometheus/Grafana and provider cost controls only after the end-to-end demo remains stable.

**Documentation maintenance:**
- Current capacity: Rich planning and review trail.
- Limit: More phases will increase stale-document risk unless closeout includes map/doc refresh.
- Scaling path: Add a lightweight drift check command or checklist to phase completion.

## Dependencies at Risk

**Dual toolchain drift:**
- Risk: Python `uv` and frontend npm scripts can evolve independently.
- Impact: One side can pass while the full app no longer builds/runs.
- Mitigation: Keep top-level run/test guidance current and run both backend and frontend checks before milestone closure.

**Model provider assumptions:**
- Risk: OpenAI-compatible model integration can vary by provider, model, token limits, streaming behavior, and cost.
- Impact: Prompt and graph behavior may pass mocked tests but fail live smoke.
- Mitigation: Keep live smoke scripts explicit and separate from default CI.

## Missing Critical Features

**Standard codebase-map refresh gate:**
- Problem: Map refresh was not part of phase closeout.
- Blocks: Accurate planning, review, and future agent context.
- Implementation complexity: Low.

**Browser-level end-to-end test:**
- Problem: Backend tests are strong, but the full frontend/SSE/approval UX is not yet verified as a routine command.
- Blocks: Confidence in demo readiness.
- Implementation complexity: Moderate.

**External observability:**
- Problem: Internal trace persistence exists, but OTel/Prometheus/Grafana are not implemented.
- Blocks: Production-grade monitoring story.
- Implementation complexity: Moderate; should stay deferred until MVP scope is stable.

## Test Coverage Gaps

**Frontend workflow coverage:**
- What's not fully tested: Chat UI, timeline rendering, evidence tab, trace tab, approval UI behavior, responsive layout.
- Risk: Demo-facing regressions.
- Priority: Medium-high.

**Live model/provider behavior:**
- What's not tested by default: Real model latency, token usage, refusal behavior, and provider errors.
- Risk: Mocked graph tests may not expose live provider issues.
- Priority: Medium.

**Full E2E approval path:**
- What's not standardized as one command: Seed data, start services, submit high-risk agent request, approve/reject, resume graph, fetch trace.
- Risk: Pieces pass independently while the demo flow regresses.
- Priority: High for shipping/demo milestones.

---
*Concerns audit: 2026-06-05*
*Refresh as code lands and newly retired risks should be removed from this file*
