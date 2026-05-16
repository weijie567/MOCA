# Roadmap: MOCA

**Phases:** 6
**Requirements:** 62
**Coverage:** 100%
**Timeline:** 6 weeks (4 weeks MVP core + 2 weeks polish)

---

## Phase 1: Foundation

**Status:** Complete
**Goal:** Docker Compose starts all services, database schema is complete, FastAPI serves authenticated CRUD endpoints with realistic seed data, repository layer established.
**Duration:** ~7 days
**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08, INFR-01, INFR-02, INFR-03, INFR-04, INFR-05, TOOL-01, TOOL-02, TOOL-03, TOOL-06, TOOL-07, TOOL-08
**UI hint:** no

### Success Criteria
1. `docker compose up` starts Postgres (with pgvector), Redis, and FastAPI; all healthchecks pass within 60 seconds
2. Seed script populates tenants, users, roles, merchants, orders, refund_cases, tickets, policy_documents with realistic Chinese data; at least 80 orders, 30 refund cases, 15 knowledge documents
3. Swagger UI shows working endpoints for get_order, get_refund_case, get_ticket_history with proper input/output schemas; all responses include tenant_id filtering via repository layer
4. JWT auth with OAuth2 scopes works; requests without valid token return 401; requests with insufficient scope return 403
5. Every tool call logs tool_call_id, run_id, tenant_id, user_id, latency_ms, status to the database; write operations accept idempotency_key
6. Repository layer exists between tools and DB; README.md, .gitignore, .env.example present

---

## Phase 2: RAG Pipeline

**Status:** Complete
**Goal:** Knowledge documents are chunked, embedded, and retrievable via pgvector; search endpoint returns relevant rule chunks with metadata filtering, confidence scoring, and citation validation.
**Duration:** ~5 days
**Requirements:** EVAL-01, EVAL-02, INFR-06, RAG-01, RAG-02, RAG-03, RAG-04, RAG-06, RAG-07
**UI hint:** no

### Success Criteria
1. CLI ingestion script processes 15-30 Chinese knowledge documents (refund rules, compensation rules, SOP, FAQ), chunks them structurally by heading, generates embeddings, and stores in pgvector with HNSW index
2. Each chunk record contains doc_id, chunk_id, title, section, text, doc_type, risk_level, effective_date metadata; retrieval supports filtering by tenant_id, doc_type, risk_level
3. Search endpoint returns top-5 relevant chunks for a query; golden set of 10+ test queries achieves measurable Hit@5 score
4. Citation validator verifies that any doc_id/chunk_id referenced in output actually exists in retrieval results
5. When no chunk exceeds the confidence threshold, the system returns a no-evidence fallback response instead of fabricated content

---

## Phase 3: LangGraph Core

**Status:** Complete
**Goal:** Submit a refund question and receive an evidence-cited answer with full execution trace, tool calls, and same-thread memory — the complete read-only happy path without approval interruption.
**Duration:** ~8 days
**Requirements:** AGNT-01, AGNT-02, AGNT-03, AGNT-04, AGNT-05, AGNT-06, AGNT-08, INFR-09, RAG-05, SAFE-06, SAFE-08
**UI hint:** no
**Plans:** 6 plans

Plans:
- [x] 03-01-PLAN.md — Dependencies + Config + AgentRun/AgentStep DB models + migration
- [x] 03-02-PLAN.md — AgentState TypedDict + Pydantic schemas + prompts + 4 tool wrappers
- [x] 03-03-PLAN.md — 8 LangGraph nodes + graph assembly + risk_rules.yaml
- [x] 03-04-PLAN.md — Trace persistence + POST /api/v1/agent/chat + FastAPI lifespan
- [x] 03-05-PLAN.md — Test suite (per-node + tools + graph integration + failure paths + golden set)
- [x] 03-06-PLAN.md — Gap closure for AgentStep tool/evidence persistence and same-thread evidence memory

### Success Criteria
1. Agent accepts a refund question, identifies intent, loads business context via read tools (get_order, get_refund_case, get_ticket), retrieves knowledge base evidence, and returns a structured response with evidence list citing specific doc_id/chunk_id (validated by citation validator)
2. Execution trace records all graph nodes traversed, tool calls made, evidence referenced; trace is queryable by run_id
3. Same-thread conversation remembers order_id, refund_case_id, previously retrieved evidence via LangGraph checkpointer
4. Agent refuses to give definitive conclusions when evidence is insufficient; returns missing_info list
5. LLM/DB/tool timeout produces graceful degradation (structured error response), not a crash

---

## Phase 4: Approval Workflow & Audit

**Goal:** High-risk actions trigger approval interruption via `interrupt()`, human decision resumes or halts execution, write tools operational, full audit chain is queryable and replayable.
**Duration:** ~7 days
**Requirements:** AGNT-02a, EVAL-05, EVAL-08, SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05, SAFE-07, TOOL-04, TOOL-05, TOOL-09
**UI hint:** no
**Plans:** 3/6 complete

Plans:
- [x] 04-01-PLAN.md — Latency Instrumentation & Diagnostic Script
- [x] 04-02-PLAN.md — Approval Tables and State Extensions
- [x] 04-03-PLAN.md — Approval Gate Node + Execute Action Node + Graph Topology
- [ ] 04-04-PLAN.md
- [ ] 04-05-PLAN.md
- [ ] 04-06-PLAN.md

### Phase 4 Planning Prerequisite: Agent Latency Diagnosis

Before implementing approval workflow changes, create a diagnostic-first performance plan for the live Phase 3 agent path. Phase 3 UAT correctness passed, but live Swagger calls took roughly 90-200 seconds. Treat this as a Phase 4 prerequisite because approval workflow and frontend demo work will amplify perceived latency if the slow nodes are not understood.

Required diagnostic scope:
- Record real `latency_ms` for each graph node, not just total request latency.
- Identify whether the slow path is `classify_intent`, `extract_slots`, `retrieve_policy_evidence`, `generate_recommendation`, `assess_risk_and_approval`, `final_response`, provider retry behavior, DashScope latency, Swagger/request waiting, or prompt/context size.
- Do not start with optimization changes. First produce evidence showing which node(s) dominate latency and whether retries/timeouts are occurring.
- Evaluate optimization options after diagnosis: smaller model for classify/extract/risk, merging adjacent LLM nodes, skipping downstream LLM work on no-evidence paths, adding streaming or progressive status updates, and setting reasonable timeout/degradation behavior.
- Preserve Phase 3 correctness gates: evidence-cited answers, no-evidence fallback, same-thread evidence gating, and trace/audit persistence.

### Success Criteria
1. Agent automatically classifies action risk level using rules/risk_rules.yaml; high-risk actions (compensation above threshold, refund override) trigger LangGraph `interrupt()` and create an approval_request record
2. Approval API allows reviewer to approve or reject; approval resumes graph execution via `Command(resume=...)` and completes the action; rejection stops execution and returns reason to user
3. High-risk action interception rate is 100% across all golden set test cases — no high-risk action executes without approval
4. Error scenarios demonstrable: permission denied, approval rejected, tool timeout, no evidence — all produce structured responses
5. Audit logs capture complete chain: input → tools → evidence → risk assessment → approval → execution → output; queryable by run_id

---

## Phase 5: Frontend & SSE

**Goal:** Minimal frontend provides a complete demo experience with chat interface, approval operations, and execution step visibility; SSE or polling for progressive updates.
**Duration:** ~5 days
**Requirements:** AGNT-07, FRNT-01, FRNT-02, FRNT-03, FRNT-04
**UI hint:** yes

### Success Criteria
1. Chat interface submits refund/order questions and displays evidence-cited answers with source attribution
2. Approval interface shows pending approval requests with approve/reject buttons; actions update in real-time
3. Execution step panel shows Agent current stage, tools called, evidence retrieved, and approval status
4. SSE or polling endpoint streams progressive status updates ("reading order", "searching rules", "waiting approval")
5. No complex graph node animations; step panel uses simple status indicators

---

## Phase 6: Evaluation & Polish

**Goal:** Expand evaluation coverage to full golden set, validate all metrics end-to-end, produce interview-ready README and demo materials, establish CI baseline. (Note: Phase 2 establishes RAG eval baseline with Hit@5; Phase 4 validates interception rate. Phase 6 is the final comprehensive validation and reporting pass.)
**Duration:** ~5 days
**Requirements:** EVAL-03, EVAL-04, EVAL-06, EVAL-07, INFR-07, INFR-08
**UI hint:** no

### Success Criteria
1. Golden set expanded to 25-40 cases covering: rule Q&A, refund troubleshooting, compensation suggestion, approval trigger, no-evidence fallback, permission denied, approval rejected
2. Automated evaluation script produces scored report: RAG Hit@5, citation accuracy, tool selection accuracy, task completion rate, high-risk interception rate (must be 100%), average latency, token cost
3. CI runs lint (ruff) + unit tests; integration and eval scripts available locally
4. README.md complete: one-line intro, architecture diagram, quick start, demo accounts, core flow demo, metrics, security note, roadmap
5. Demo script documented (docs/demo-script.md): 10-minute walkthrough covering happy path + approval + rejection + no-evidence

---

*Roadmap updated: 2026-05-09*
*Change: Split original Phase 4 into Phase 4 (Approval), Phase 5 (Frontend), Phase 6 (Eval+Polish) per architecture review recommendation. This gives frontend and evaluation dedicated time instead of competing with approval complexity in the same week.*

*Build order rationale: Foundation must be solid (async patterns, healthchecks, repository layer) because every subsequent phase builds on it. RAG before graph because retrieval quality must be validated in isolation. Graph before approval because the happy path must work first. Frontend after backend is stable. Evaluation last because it validates everything.*
