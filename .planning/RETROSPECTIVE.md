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

## Milestone: v1.1 — Agent Architecture Migration

**Shipped:** 2026-06-17
**Phases:** 11 | **Plans:** 62 | **Task markers:** 362

### What Was Built

- Explicit KnowledgeService and BusinessToolService facades with canonical evidence/tool contracts.
- Deterministic AgentState lifecycle, trusted fields, routing totality, intent/clarification gates, and safe fallback behavior.
- PostgreSQL-authoritative session memory with CAS and safe same-thread continuity.
- Versioned approval lifecycle, immutable ActionSafetySnapshot binding, draft-only demo action boundary, and ReplayEventV3 event-store replay.
- Memory Foundation V2: conversation log, layered tool call/result storage, WorkingStateV1, thread summaries, ContextAssembler, token budgeting, and replay/audit/conversation ID alignment.
- Final readiness closure: formal Phase 7/10 verification and owner disposition for tenant-over-global target policy scope.

### What Worked

- Architecture-first planning kept approval, action, replay, memory, and external execution ownership clear.
- Cross-AI/code-review loops caught real risks, including migration rollback and concurrent first-message thread creation.
- Formal readiness audit before Phase 16 prevented ownerless `KNOW-02` and missing verification artifacts from leaking into long-term memory work.
- Focused regression suites stayed fast enough to run during closure while still covering state/routing, knowledge, replay, and memory boundaries.

### What Was Inefficient

- Some early phases completed before the later formal verification convention existed, requiring Phase 15.2 to backfill evidence artifacts.
- `roadmap.analyze` did not fully account for decimal Phase 15.2, so readiness required manual cross-checks.
- Historical Nyquist validation files remained uneven; the milestone passed after formal verification closure, but validation hygiene should be refreshed earlier next time.

### Patterns Established

- Treat `DEFERRED_WITH_OWNER` as acceptable only with owner, rationale, dependency, and acceptance gate.
- Do not implement target-state scope merely to satisfy an audit when schema/runtime semantics show it belongs to a later phase.
- Keep phase closure commits separate from next-phase planning so archive boundaries stay reviewable.
- Use focused milestone smoke suites plus integration checker output as readiness evidence, then record exact commands in archive artifacts.

### Key Lessons

1. Milestone readiness audits should run before entering large new domains like long-term memory.
2. Verification artifacts are not bookkeeping; missing artifacts create real ambiguity even when code probably works.
3. Ownerless deferrals are blockers. Named target-state deferrals are acceptable when backed by rationale and acceptance gates.
4. Decimal insertion phases are useful for closure work, but tooling may need manual verification around them.

### Cost Observations

- Model mix: quality profile across planning, execution, review, and audit.
- Sessions: multi-session milestone execution from 2026-05-28 to 2026-06-17.
- Notable: The highest leverage came from short closure phases and targeted smoke suites rather than expanding implementation scope.

---

## Milestone: v1.3 — RAG Hybrid Retrieval

**Shipped:** 2026-06-18
**Phases:** 1 | **Plans:** 1 | **Tasks:** 6

### What Was Built

- Retrieval-only `PolicyChunk.search_text` plus generated PostgreSQL `search_vector`.
- PostgreSQL full-text and pg_trgm indexes alongside existing pgvector search.
- Deterministic Chinese/domain tokenizer for refund/support policy retrieval.
- Dense, sparse, and fuzzy policy retrieval channels fused through RRF.
- Scope-filtered retrieval across tenant, doc type, risk level, and effective date before channel contribution.
- Eval/debug hybrid trace fields that do not enter prompts, API serialization, or `EvidenceRefV1`.

### What Worked

- Keeping Phase 20 narrow made it possible to ship hybrid retrieval without pulling in OCR, citation-block storage, verifier, reranker, or external backend scope.
- The evidence-boundary rule was simple and durable: raw citation content stays in `PolicyChunk.content`; retrieval enrichment stays in `search_text`.
- Focused test slices were effective checkpoints for tokenizer behavior, ingestion boundaries, channel filtering, RRF confidence separation, eval diagnostics, and full regression.
- The secure-phase audit had concrete threat IDs from the plan, so closure was evidence-based instead of broad security hand-waving.

### What Was Inefficient

- The resumed session inherited uncommitted implementation state, so ideal red/green/refactor task boundaries could not be reconstructed exactly.
- `roadmap.analyze` and milestone helper tooling still misread milestone scope when older completed milestone details remain expanded in `ROADMAP.md`.
- A standalone v1.3 milestone audit was not present before archive; closure relied on phase-level validation, UAT, security, and full pytest evidence.

### Patterns Established

- Use owner-named future RAG phases for deferrals: Phase 21 ingestion/OCR, Phase 22 context/hallucination control, Phase 23 reranker/query rewrite, and Phase RAG-5 external backend.
- Keep RRF as an ordering signal and normalized confidence as the contract-facing evidence score.
- Keep hybrid trace fields as internal diagnostics with explicit API serialization exclusion.
- Treat business facts and policy evidence as separate authority sources even inside retrieval/eval tooling.

### Key Lessons

1. Retrieval-quality upgrades should start with schema/search-text boundaries before adding rerankers or external search systems.
2. Sparse/fuzzy retrieval must share the same trusted filters as dense retrieval before fusion; post-fusion filtering is too late.
3. Diagnostic richness is useful only if it stays out of evidence contracts and prompts by default.
4. Milestone archive tooling needs stricter current-milestone detection once multiple completed milestones remain in the active ROADMAP file.

### Cost Observations

- Model mix: quality profile with focused execution, verification, and security review.
- Sessions: resumed execution and closure on 2026-06-18.
- Notable: The highest leverage came from narrow threat models and focused regression slices rather than broad RAG scope expansion.

---

## Milestone: v1.4 — RAG Production Ingestion + OCR

**Shipped:** 2026-06-19
**Phases:** 1 | **Plans:** 9 | **Task markers:** 18

### What Was Built

- Project-owned parser DTOs, parser registry routing, source guards, and deterministic Markdown/plain-text synthetic source blocks.
- Durable source-block and ingestion-job persistence with chunk provenance refs and safe parser/OCR job trace projection.
- Block-aware and table-aware chunking with retrieval-only `search_text` enrichment while preserving canonical citation text and `EvidenceRefV1.text_hash`.
- Local PDF, DOCX, image, scanned-PDF, and OCR adapters with Tesseract `chi_sim+eng` preflight and deterministic confidence thresholds.
- Verified source-block provenance lookup that checks tenant, evidence id, and canonical text hash before exposing maintainer/debug metadata.
- Boundary regression coverage across evidence refs, API evidence serialization, prompts, memory, approval/action snapshots, replay payloads, Tool System facts, and v1.3 hybrid retrieval.

### What Worked

- Separating source provenance from evidence authority kept Phase 21 large but still bounded.
- The two-pass review loop caught real parser/OCR safety issues before archive: hidden PDF text, table metadata sanitizer bypasses, OCR word-box text, malformed OCR dicts, malicious `doc_key`, and ingestion-job trace revalidation.
- Running the dependency-only gates after local setup removed ambiguity from final acceptance: native `chi_sim+eng` OCR and live pgvector migration round trip both passed.
- Keeping Phase 22/23/RAG-5 deliverables out of Phase 21 prevented ingestion work from expanding into hallucination control, reranking, or backend replacement.

### What Was Inefficient

- GSD milestone auto-detection still misread older expanded completed milestone details in `ROADMAP.md`, so v1.4 archive creation required manual correction.
- Plan review needed multiple rounds because validation maps, xfail ownership, and scope guards were initially too coarse for a 9-plan phase.
- Parser/OCR safety looked green under focused tests until adversarial code review checked the metadata-to-chunk paths, so table/OCR metadata needs first-class threat tests earlier.

### Patterns Established

- Treat parser/OCR output as hostile data even after it becomes structured metadata; sanitize both visible text and metadata values before persistence.
- Keep `doc_key` and source-block IDs as validated internal identifiers, never as free-form source metadata.
- Persist source provenance, but expose it only through tenant/hash-verified maintainer lookup.
- Run dependency-only gates before archive when local setup is feasible, then update acceptance artifacts from dependency-only to accepted.

### Key Lessons

1. Parser security is not only about extracted text; table cells, word boxes, source IDs, and job traces can all become indirect evidence or prompt inputs.
2. Archive tooling should not infer the current milestone from broad roadmap prose when older completed milestones remain expanded.
3. Large RAG phases need owner-tasked xfail inventories and validation maps that match actual task IDs.
4. Optional runtime dependencies are acceptable only when fail-closed behavior and post-dependency verification are both recorded.

### Cost Observations

- Model mix: quality profile across plan review, execution, code review, security verification, and archive repair.
- Sessions: multi-session planning, execution, review, and closure from 2026-06-18 to 2026-06-19.
- Notable: The highest leverage came from adversarial metadata-boundary review after the focused test suite was already green.

---

## Milestone: v1.5 — RAG Context Builder + Hallucination Control

**Shipped:** 2026-06-19
**Phases:** 1 | **Plans:** 6 | **Task markers:** 18

### What Was Built

- Prompt-safe `RagContextBundle` construction with canonical evidence re-fetch, tenant/scope/hash/freshness/latest-version validation, citation maps, dedupe/merge traceability, exclusion reasons, and budget traces.
- Typed `MaterialClaim` authority contracts for policy claims, business fact claims, and action recommendation claims.
- Deterministic Level 1/2 verification plus risk-triggered, budgeted, fail-closed Level 3 semantic verification.
- Backend-owned route control for allow, regenerate-route, refusal/insufficient evidence, and manual review without model-selected safety routing.
- Recommendation, graph, action-boundary, approval, and final-response integration that blocks non-allow verifier outcomes from creating action state.
- Deterministic hallucination-control eval metrics with a 24-case golden dataset, 5 production-verifier cases, aggregate/redacted reporting, and no live provider dependency.

### What Worked

- Splitting Wave 0 RED scaffolds from implementation plans gave the phase strong regression pressure before production code existed.
- Canonical evidence validation in ContextBuilder kept policy support separate from retrieval candidates, source-block provenance, memory, and business facts.
- Treating route decisions as backend-owned state avoided model-selected safety outcomes and made graph/action/final behavior testable.
- The post-review loop caught real edge cases: failed dependency aggregation, missing-session fail-closed behavior, tenant-aware dedupe, stale action snapshot binding, and production-path eval coverage.
- Running UAT checkpoints, security verification, eval, related suites, full non-integration pytest, and Ruff gates before archive made the close decision evidence-based.

### What Was Inefficient

- GSD milestone helper tooling again misread stale/historical planning metadata, creating a bad `STATE.md` frontmatter update that needed manual repair.
- Several artifacts drifted during rapid closeout: `22-06-SUMMARY.md` case counts, `22-VALIDATION.md` planning-time table wording, and an eval script header comment.
- Deep review warnings required follow-up hardening/regression passes after the main implementation was otherwise complete.
- The active roadmap retained full completed Phase 22 detail until archive, which increased the chance of tooling and human readers treating the milestone as still active.

### Patterns Established

- RAG answer/action grounding needs four gates together: canonical evidence validation, authority-separated claims, backend route control, and leakage/eval closure.
- Citation membership is not semantic support; support checks need explicit claim types and authority refs.
- Non-allow verifier outcomes should clear and block action state at every boundary, not only at graph routing.
- Eval reports for safety-sensitive RAG should expose aggregate metrics, threshold failures, and case IDs, not raw verifier prompts or private reasoning.
- Keep production-verifier coverage visible as its own dimension, even when deterministic adapter cases are acceptable for local gates.

### Key Lessons

1. A RAG hallucination-control phase is not just verifier code; it must own context construction, claim authority, route decisions, action boundaries, final wording, and eval leakage together.
2. Latest/current policy version validation must be tested independently from effective-date and text-hash validation.
3. Action recommendation support requires both policy and current business fact authority, and successful support still must not bypass approval/action contracts.
4. Milestone archive tooling needs a compact active roadmap and reliable current milestone metadata, or manual archive repair remains likely.

### Cost Observations

- Model mix: quality profile across planning, implementation, deep code review, verification, security review, and milestone audit.
- Sessions: multi-session Phase 22 execution and closure on 2026-06-19.
- Notable: The highest leverage came from targeted regressions after deep review, especially around route/action boundaries and canonical evidence validation.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | multi-session | 6 | Established phase-by-phase planning, execution, code review, verification, and final archive workflow |
| v1.1 | multi-session | 11 | Established architecture-first contracts, formal readiness audit, and owner-named deferrals before long-term memory |
| v1.3 | resumed closeout | 1 | Established minimal PostgreSQL hybrid retrieval while keeping OCR, verifier, reranker, and external backend scope owner-named and deferred |
| v1.4 | multi-session | 1 | Established production parser/OCR ingestion with source-block provenance while preserving evidence, memory, action, and replay boundaries |
| v1.5 | multi-session | 1 | Established canonical RAG context, authority-separated claim verification, deterministic safety routing, and hallucination-control evals |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 164 non-integration tests in final CI-equivalent gate | Phase 6 verifier passed 23/23 must-haves | Deterministic FakeLLM and JSONL golden-set gates avoid provider dependency in CI |
| v1.1 | 181-test readiness suite plus prior 175-test integration checker suite | Milestone audit passed 32/32 current-scope requirements | Focused smoke suites and formal verification artifacts avoid provider dependency in archive readiness |
| v1.3 | Full regression gate passed with 1002 tests; UAT 7/7; security threats 5/5 closed | Phase 20 requirements complete 11/11 | Tokenizer, schema, RRF, scope, and eval diagnostics covered without provider dependency |
| v1.4 | Full post-dependency regression gate passed with 1136 tests; live migration + OCR gate passed with 28 tests | Milestone audit passed 26/26 requirements, 8/8 integration contracts, 5/5 end-to-end flows | Native OCR and live pgvector migration gates are explicit runtime dependencies, not silent skips |
| v1.5 | Phase 22 related suite 119 passed; full non-integration pytest 1228 passed, 1 skipped; hallucination eval 24 cases | Milestone audit passed 32/32 active requirements, 6/6 integration areas, 8/8 required flows | Deterministic local hallucination eval plus production-verifier case coverage avoid live provider dependency |

### Top Lessons (Verified Across Milestones)

1. Agent systems need separate gates for deterministic contracts, DB-backed integration, and live provider behavior.
2. Human-in-the-loop approval is easiest to reason about when it is a persisted graph state transition, not a side-channel.
3. Demo readiness depends on docs, scripts, and seed data staying synchronized with actual API response shapes.
4. Architecture migrations need explicit owner boundaries and named deferrals before new memory or execution domains begin.
5. RAG retrieval upgrades need a hard citation-identity boundary before adding ranking complexity.
6. Parser/OCR ingestion needs metadata-value sanitization and identifier validation in addition to visible-text sanitization.
7. RAG answer/action grounding needs canonical evidence validation, authority separation, backend-owned route control, and leakage-aware eval as one acceptance gate.
