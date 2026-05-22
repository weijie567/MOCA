---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: v1.0 milestone complete
last_updated: "2026-05-22T09:44:11.657Z"
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 36
  completed_plans: 36
  percent: 100
---

# Project State: MOCA

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-22)

**Core value:** When a merchant or support agent asks about a refund issue, the system must retrieve relevant business data and rules, provide an evidence-backed answer, and ensure any risky action goes through approval before execution.
**Current focus:** Planning next milestone

## Current Status

- **Active phase:** none
- **Phase status:** v1.0 is archived; no active phase.
- **Blockers:** None.
- **Milestone:** v1.0 complete and archived — all 6 roadmap phases executed and verified.

## Deferred Items

Items acknowledged at milestone close on 2026-05-22:

| Category | Item | Status |
|----------|------|--------|
| UAT audit artifact | Phase 02 `02-HUMAN-UAT.md` | resolved, 0 pending scenarios |
| UAT audit artifact | Phase 03 `03-HUMAN-UAT.md` | resolved, 0 pending scenarios |
| UAT audit artifact | Phase 05 `05-HUMAN-UAT.md` | passed, 0 pending scenarios |
| Verification audit artifact | Phase 01 `01-VERIFICATION.md` | historical `human_needed`; later STATE/PROJECT/ROADMAP evidence marks Phase 1 complete |

## Phase History

- **Phase 1: Foundation** — Complete on 2026-05-10
  - Plans completed: 5/5
  - Verification: `01-VERIFICATION.md`
  - Validation: `01-VALIDATION.md`
  - Human UAT: `01-HUMAN-UAT.md`
  - Security: `01-SECURITY.md` (`threats_open: 0`)
  - Tests: `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest -q --tb=short` — 12 passed
- **Phase 2: RAG Pipeline** — Complete on 2026-05-11
  - Plans completed: 7/7
  - Gap closure plan: `07-PLAN.md` (status: `complete`)
  - Latest plan summary: `.planning/phases/02-rag-pipeline/07-SUMMARY.md`
  - Verification: `02-VERIFICATION.md` plus `07-RETRIEVAL-AUDIT.md`; live Hit@5 now passes
  - Human UAT: `02-HUMAN-UAT.md` (3 passed, 0 failed)
  - Code review: `02-REVIEW.md`; fixes recorded in `02-REVIEW-FIX.md`
  - Tests: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` — 50 passed
  - Live checks: real `DASHSCOPE_API_KEY` ingestion passed; Plan 07 DB-backed Hit@5 passed at 83.3% with fallback accuracy 100.0%
- **Phase 3: LangGraph Core** — Complete on 2026-05-11
  - Plans completed: 6/6
  - Latest plan summary: `.planning/phases/03-langgraph-core/03-06-SUMMARY.md`
  - Human UAT: `03-HUMAN-UAT.md` (3 passed, 0 failed)
  - Conversational UAT: `03-UAT.md` (5 passed, 0 issues, 0 blocked)
  - Code review: `03-REVIEW.md` (clean)
  - Tests: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` — 89 passed
  - Live checks: real DashScope/API-backed Swagger UAT passed for policy QA, refund troubleshooting, no-evidence fallback, same-thread evidence gating, and trace persistence
- **Phase 4: Approval Workflow & Audit** — Complete on 2026-05-17
  - Plans completed: 6/6
  - Latest plan summary: `.planning/phases/04-approval-workflow-audit/04-06-SUMMARY.md`
  - Verification: `04-VERIFICATION.md` (`status: passed`)
  - Code review: `04-REVIEW.md`; fixes recorded in `04-REVIEW-FIX.md`
  - Tests: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` — 164 passed
  - Validation: approval interrupt/resume, approve/reject handling, low-risk bypass, idempotent action draft creation, trace replay, and 100% high-risk interception across HR-01, HR-02, and HR-03
- **Phase 5: Frontend & SSE** — Complete on 2026-05-18
  - Plans completed: 8/8
  - Latest plan summary: `.planning/phases/05-frontend-sse/05-08-SUMMARY.md`
  - Verification: `05-VERIFICATION.md` (`status: passed`)
  - Human UAT: `05-HUMAN-UAT.md` (3 passed, 0 issues)
  - Code review: `05-REVIEW.md`; fixes recorded in `05-REVIEW-FIX.md`
  - Security: `05-SECURITY.md` (`status: verified`)
  - Tests: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` — 176 passed, 1 warning
  - Validation: browser happy path chat, cross-role approval flow, Docker demo stack, SSE streaming, pending approval UI, and failure recovery all passed
- **Phase 6: Evaluation & Polish** — Complete on 2026-05-22
  - Plans completed: 4/4
  - Latest plan summary: `.planning/phases/06-evaluation-polish/06-04-SUMMARY.md`
  - Verification: `06-VERIFICATION.md` (`status: passed`, 23/23 must-haves)
  - Code review: `06-REVIEW.md`; fixes recorded in `06-REVIEW-FIX.md`
  - Tests: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -x --ignore=tests/integration -q --tb=short` — 164 passed, 1 warning
  - Evaluation: deterministic agent eval passed with 35/35 cases and compiled graph contract pass; schema drift check passed

## Session Notes

- 2026-05-22: Completed Phase 6 Evaluation & Polish. Added final golden sets, RAG/agent/all evaluation scripts, CI workflow, demo script, README rewrite, and docs for demo walkthrough, evaluation, architecture, and security. Code review findings were fixed, verifier passed 23/23 must-haves, deterministic agent eval passed 35/35, schema drift passed, and full non-integration pytest passed with 164 tests.
- 2026-05-18: Completed Phase 5 after browser/compose human UAT passed. `05-VERIFICATION.md` is `passed` with 29/29 automated truths verified and 3/3 human UAT items passed. Final checks: `uv run pytest -q --tb=short` 176 passed, 1 warning; `uv run ruff check src tests` passed; `npm run lint` passed; `npm run build` passed; `docker compose config --quiet` passed.
- 2026-05-17: Executed Phase 5 gap closure plans 05-05 through 05-08. Closed duplicate SSE execution with a pending-run claim guard, fixed demo JWT role mapping and compose proxy routing, added pending approvals UI and API failure recovery, cleared frontend lint blockers, and recorded `05-REVIEW-FIX.md`.
- 2026-05-16: Added Phase 4 planning prerequisite for live agent latency diagnosis. Phase 3 UAT passed functionally, but live Swagger calls took roughly 90-200 seconds; Phase 4 planning must first instrument per-node latency and diagnose slow nodes/retries/provider latency before choosing optimization strategies.
- 2026-05-16: Executed Phase 4 Plan 03. Added approval_gate interrupt/resume node, execute_action node, create_coupon_grant_draft tool, approval outcome final responses, conditional graph routing, and 19 focused approval workflow tests. Verification: approval tests 14 passed, agent tests 43 passed, ruff passed, and graph compile passed.
- 2026-05-16: Executed Phase 4 Plan 05. Added TraceRepository, GET /api/v1/agent-runs/{run_id}/trace, sanitized trace response schema, and 7 trace API tests. Verification: trace API tests 7 passed and ruff passed.
- 2026-05-16: Executed Phase 4 Plan 06. Added MemorySaver-backed approval integration tests and high-risk interception validation. Verification: targeted approval/interception tests 13 passed, full test suite 164 passed, ruff passed, and high-risk interception rate is 3/3.
- 2026-05-16: Completed Phase 3 conversational UAT after fixing Swagger OAuth token flow, default `agent:chat` scopes, and settings-backed DashScope embedding credentials. `03-UAT.md` is complete with 5/5 passed: policy QA, refund troubleshooting, no-evidence fallback, same-thread evidence gating, and DB trace/evidence_refs persistence.
- 2026-05-10: Completed Phase 2 Plan 03. Added policy document/chunk repositories, ingestion service, dry-run ingestion CLI, and 15 Chinese policy documents. Verification: `UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev pytest -q --tb=short` — 22 passed.
- 2026-05-10: Completed Phase 2 Plan 04. Added tenant-scoped retriever confidence scoring, citation validator, authenticated search endpoint, and mocked retrieval tests. Verification: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` - 31 passed; ruff passed for Plan 04 files.
- 2026-05-10: Completed Phase 2 Plan 05. Added calibrated RAG golden set, Hit@5 eval script, deterministic search integration tests, and DashScope env docs. Verification: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` — 35 passed.
- 2026-05-10: Completed Phase 2 code review fixes. Fixed migration doc_key backfill, demo seed doc_key, tenant-safe vector joins, settings-backed embedding config, and sanitized generic 500 responses. Verification: ruff passed, targeted tests 8 passed, full pytest 39 passed, `alembic upgrade head` passed, `seed_demo.py --reset` passed.
- 2026-05-10: Phase 2 verifier returned `human_needed`: implementation verified, but live external embedding ingestion, RAG Hit@5, and live search endpoint relevance require human/API-key validation.
- 2026-05-10: Ran live DashScope verification. Policy ingestion passed with 15 documents and 90 embedded chunks. Authenticated search passed on sampled refund/filter/fallback cases. RAG Hit@5 failed at 58.3% against the 80% threshold, so Phase 2 needs gap closure.
- 2026-05-11: Planned Phase 2 gap closure as `06-PLAN.md`. Plan checker passed after revision; execution should run `$gsd-execute-phase 2 --gaps-only`.
- 2026-05-11: Executed Plan 06. Added eval diagnostics and deterministic scoring tests, but did not alter the golden set because live diagnostics found only one answer-bearing calibration candidate; Hit@5 would improve from 7/12 to at most 8/12, below the required 10/12. Next step is a retrieval-improvement plan, not further golden-set calibration.
- 2026-05-11: Executed Plan 07. Enriched policy embedding input, added deterministic hybrid reranking and support-domain fallback guard, re-ingested 90 chunks, and closed EVAL-02 with live Hit@5 83.3% and fallback accuracy 100.0%.
- 2026-05-11: Executed Phase 3 Plan 01. Added LangGraph/LangChain/psycopg dependencies, GLM/DashScope settings, derived checkpointer URL, AgentRun/AgentStep models, and migration 003. Verification: config import passed, model import passed, `alembic upgrade head` passed, and `pytest -q --tb=short` passed with 50 tests.
- 2026-05-11: Executed Phase 3 Plan 02. Added AgentState, structured Pydantic output schemas, static English prompts, and four read-only tenant-scoped tool wrappers. Verification: agent imports passed, ruff passed, `get_ticket.py` has no `messages` reference, and `pytest -q --tb=short` passed with 50 tests.
- 2026-05-11: Executed Phase 3 Plan 03. Added eight async LangGraph nodes, `rules/risk_rules.yaml`, fixed `build_graph()`, no-evidence LLM skip, citation validation, and safe LLM fallbacks. Verification: graph assembly import passed, ruff passed, and `pytest -q --tb=short` passed with 50 tests.
- 2026-05-11: Executed Phase 3 Plan 04. Added `POST /api/v1/agent/chat`, `agent:chat` OAuth scope, AgentRun/AgentStep trace persistence helpers, scoped checkpointer thread keys, and FastAPI lifespan setup. Verification: integration wiring passed, ruff passed, and `pytest -q --tb=short` passed with 50 tests.
- 2026-05-11: Executed Phase 3 Plan 05. Added FakeLLM fixtures, agent tool/node tests, MemorySaver graph integration tests, `scripts/smoke_agent_live.py`, and 15 synthetic golden-set cases. Verification: agent tests passed with 24 tests, full pytest passed with 74 tests, golden-set JSON validated, and smoke script syntax parsed.
- 2026-05-11: Executed Phase 3 Plan 06 gap closure. Persisted tools_called-derived AgentStep tool names, trace evidence refs, and same-thread compact evidence memory. Verification: agent tests passed with 36 tests, full pytest passed with 86 tests, and ruff passed.
- 2026-05-15: Closed Phase 3 live verification. Hardened DashScope citation prompting, policy-QA risk handling, deterministic citation final responses, and live smoke assertions. Verification: live smoke 3/3 passed, full pytest 89 passed, and ruff passed.

## Decisions

- Plan 04: Retriever emits structured evidence and fallback state only; answer generation remains downstream.
- Plan 04: Citation validation is deterministic field matching against retrieved chunk IDs, with no LLM judge.
- Plan 04: `knowledge:read` is granted to existing role scopes so the protected search endpoint is usable after login.
- Plan 05: Golden expected_chunk_ids were calibrated against the current zero-based heading chunker output instead of leaving placeholder IDs.
- Plan 05: The RAG eval script uses SessionLocal and the production Retriever/PolicyChunkRepository path for realistic DB-backed scoring.
- Plan 07: Evidence scores remain vector similarity scores; hybrid ranking only changes final ordering.
- Plan 07: Out-of-domain fallback is protected by a deterministic support-domain guard while preserving MIN_SIMILARITY_THRESHOLD = 0.55.
- Plan 07: EVAL-02 is closed by live exact expected_chunk_ids Hit@5 >= 80%, not by doc-only scoring or label changes.
- Plan 03-01: Migration 003 uses down_revision 002_rag_pipeline to match the repository's actual Alembic chain.
- Plan 03-01: checkpointer_database_url is a derived Settings property, not an env-loaded pydantic field.
- Plan 03-02: Tool wrappers validate UUID-shaped tenant/resource IDs before repository access and return VALIDATION_ERROR for malformed IDs.
- Plan 03-02: Ticket tool output intentionally excludes messages because ticket conversation history can contain PII.
- Plan 03-03: No-evidence retrieval sets `recommendation_draft.recommended_action` to `insufficient_evidence`, causing recommendation generation to skip the LLM call.
- Plan 03-03: Risk assessment loads thresholds from `rules/risk_rules.yaml` and applies deterministic high-risk overrides after the LLM result.
- Plan 03-03: LLM provider failures return structured node errors and safe fallbacks inside nodes rather than relying only on graph-level retries.
- Plan 03-04: The checkpointer thread key is tenant_id:user_id:thread_id to prevent same thread_id memory sharing across users or tenants.
- Plan 03-04: Graph invocation failures still attempt to persist an AgentRun error row, but trace persistence failures are rolled back and never exposed to the caller.
- Plan 03-04: A narrow OAuth2 model scopes alias preserves compatibility with the plan verification while keeping FastAPI's canonical password-flow scopes intact.

- Plan 03-05 tests patch node-local _get_llm factories rather than constructing real ChatOpenAI clients, preserving CI isolation from live LLM APIs.
- Plan 03-05 graph integration tests use MemorySaver and node-imported tool monkeypatches so the compiled graph is exercised without Postgres or external embeddings.
- Plan 03-05 golden set uses synthetic order numbers and Chinese support queries only; no real PII is included.
- Plan 03-06: Used existing AgentStep columns for tools_called and evidence_refs; no migration was added.
- Plan 03-06: Retained evidence_refs are persistent memory references only; current-turn no-evidence still produces insufficient_evidence.
- Phase 03 live smoke uses seeded demo tenant/user/order data and unique scoped checkpointer thread IDs.
- Phase 03 final responses are deterministic citation templates based on validated recommendation refs, avoiding an extra provider-dependent structured output step.
- Plan 04-01: Latency metrics store only model, provider, and context_chars; prompt/message text is never persisted in metrics_json.
- Plan 04-03: High-risk routing is enforced immediately after risk assessment; approval_required=True routes only to approval_gate.
- Plan 04-03: Rejected approvals resume the graph and route directly to final_response; execute_action is not called.
- Plan 04-03: The final_response node remains deterministic-template based, so approval outcomes are appended to template output instead of added to LLM messages.
- Plan 04-05: TraceResponse intentionally excludes AgentRun.input_query and AgentRun.final_response to reduce trace information leakage.
- Plan 04-05: Trace access is owner-or-supervisor within tenant; cross-tenant lookups return 404 before ownership checks.
- Plan 04-05: Supervisor trace access includes admin, manager, supervisor, and approval_manager roles to align with the existing approval API role vocabulary.
- Plan 04-06: Approval integration fixtures use the existing manager approver role because the approval API currently authorizes admin and manager roles.
- Plan 04-06: Integration tests use real LangGraph MemorySaver interrupt/resume with mocked LLM and policy search boundaries only.
