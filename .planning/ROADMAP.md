# Roadmap: MOCA

**Phases:** 4
**Requirements:** 59
**Coverage:** 100%

## Phase 1: Foundation

**Goal:** Docker Compose starts all services, database schema is complete, FastAPI serves authenticated CRUD endpoints with realistic seed data.
**Duration:** ~7 days
**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08, INFR-01, INFR-02, INFR-03, INFR-04, INFR-05, INFR-08, TOOL-01, TOOL-02, TOOL-03, TOOL-06, TOOL-07, TOOL-08
**UI hint:** no

### Success Criteria
1. `docker compose up` starts Postgres (with pgvector), Redis, and FastAPI; all healthchecks pass within 60 seconds
2. Seed script populates tenants, users, roles, merchants, orders, refund_cases, tickets, policy_documents, and policy_chunks with realistic Chinese data; at least 50 orders and 10 knowledge documents exist
3. Swagger UI shows working endpoints for get_order, get_refund_case, get_ticket_history with proper input/output schemas; all responses include tenant_id filtering
4. JWT auth with OAuth2 scopes works; requests without valid token return 401; requests with insufficient scope return 403
5. Every tool call logs tool_call_id, run_id, tenant_id, user_id, latency_ms, status to the database; write operations accept idempotency_key

---

## Phase 2: RAG Pipeline

**Goal:** Knowledge documents are chunked, embedded, and retrievable via pgvector; search endpoint returns relevant rule chunks with metadata filtering and confidence scoring.
**Duration:** ~5 days
**Requirements:** EVAL-01, EVAL-02, INFR-06, RAG-01, RAG-02, RAG-03, RAG-04, RAG-06
**UI hint:** no

### Success Criteria
1. CLI ingestion script processes Chinese knowledge documents (refund rules, compensation rules, SOP, FAQ), chunks them structurally, generates embeddings, and stores in pgvector with HNSW index
2. Each chunk record contains doc_id, chunk_id, title, section, text, doc_type, risk_level, effective_date metadata; retrieval supports filtering by tenant_id, doc_type, risk_level
3. Search endpoint returns top-5 relevant chunks for a query; golden set of 10+ test queries achieves measurable Hit@5 score
4. When no chunk exceeds the confidence threshold, the system returns a no-evidence fallback response instead of fabricated content

---

## Phase 3: LangGraph Core

**Goal:** Submit a refund question and receive an evidence-cited answer with full execution trace, tool calls, and session memory — the complete happy path without approval interruption.
**Duration:** ~8 days
**Requirements:** AGNT-01, AGNT-02, AGNT-03, AGNT-04, AGNT-05, AGNT-06, AGNT-07, AGNT-08, EVAL-03, EVAL-04, EVAL-06, EVAL-07, INFR-07, RAG-05, SAFE-06, SAFE-07, SAFE-08, TOOL-04, TOOL-05
**UI hint:** no

### Success Criteria
1. Agent accepts a refund question, identifies intent, loads business context via tool calls, retrieves knowledge base evidence, and returns a structured response with evidence list citing specific doc_id/chunk_id
2. Execution trace records all graph nodes traversed, tool calls made, evidence referenced, and risk assessment; trace is queryable by run_id
3. Multi-turn conversation within a session remembers order_id, refund_case_id, previously retrieved evidence, and prior conclusions without re-querying
4. SSE endpoint streams progressive status updates (reading order, searching rules, generating answer); agent refuses to give definitive conclusions when evidence is insufficient
5. Evaluation framework scores tool selection accuracy, citation accuracy, task completion rate, and latency/token cost against golden set; results output as JSON/Markdown report

---

## Phase 4: Approval Workflow & Polish

**Goal:** High-risk actions trigger approval interruption, human decision resumes or halts execution, frontend provides a complete demo experience, and all evaluation metrics meet targets.
**Duration:** ~8 days
**Requirements:** EVAL-05, EVAL-08, FRNT-01, FRNT-02, FRNT-03, FRNT-04, SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05, TOOL-09
**UI hint:** yes

### Success Criteria
1. Agent automatically classifies action risk level; high-risk actions (compensation above threshold, refund override) trigger LangGraph interrupt and create an approval_request record
2. Approval API allows reviewer to approve or reject; approval resumes graph execution and completes the action; rejection stops execution and returns reason to user
3. Frontend chat interface submits questions and displays evidence-cited answers with execution step panel; approval interface shows pending requests with approve/reject buttons
4. High-risk action interception rate is 100% across all golden set test cases — no high-risk action executes without approval

---

*Roadmap created: 2026-05-09*
*Build order rationale: Foundation must be solid (async patterns, healthchecks) because every subsequent phase builds on it. RAG before graph because retrieval quality must be validated in isolation. Approval last because it depends on the happy path working first.*
