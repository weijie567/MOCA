# MOCA — Merchant Operations Collaborative Agent

## What This Is

A production-grade AI agent for e-commerce/local-life platforms that helps merchants and support staff handle refund disputes, rule inquiries, and compensation decisions. It integrates with business systems (orders, refunds, tickets, coupons), retrieves evidence from a knowledge base, and enforces approval workflows for high-risk actions — all with full audit trails.

Built as an open-source portfolio project demonstrating enterprise Agent engineering and product thinking for AI/Agent engineer and product manager roles at top-tier internet companies.

## Core Value

When a merchant or support agent asks about a refund issue, the system must retrieve relevant business data and rules, provide an evidence-backed answer, and ensure any risky action goes through approval before execution — never silently executing something irreversible.

## Requirements

### Validated

- [x] Docker Compose one-command startup for local infrastructure and FastAPI baseline (validated in Phase 1)
- [x] Role-based access control for support/reviewer/manager style API scopes (validated in Phase 1)
- [x] Demo data seed script populates realistic synthetic Chinese business data (validated in Phase 1)
- [x] Knowledge base ingestion, pgvector retrieval, top-5 evidence, citation validation, and DB-backed RAG Hit@5 baseline (validated in Phase 2)

### Active

- [ ] Agent can accept a refund/order question and return an evidence-cited answer
- [ ] Agent retrieves order, refund, and ticket data via structured tool calls
- [ ] Agent searches knowledge base (refund rules, SOPs) and cites specific documents
- [ ] High-risk actions (compensation > threshold, refund override) trigger approval workflow
- [ ] Approval interrupts graph execution; resumes after human decision
- [ ] All agent runs produce audit logs (input, evidence, tools called, approval chain)
- [ ] Simple frontend allows submitting questions and viewing agent responses

### Out of Scope

- Second scenario (creator appeals) — defer to polish phase
- MCP protocol layer — adds complexity without MVP value
- Kubernetes / production deployment — Docker Compose sufficient for demo
- Celery / async workers — LangGraph handles the flow; no separate queue needed for MVP
- LangSmith integration — OTel traces sufficient; LangSmith is optional enhancement
- Mobile app or native clients — web only
- Real payment/refund execution — all tools are simulated
- Multi-tenant SaaS deployment — single-tenant demo with role separation

## Context

**Target audience for the project itself:** Hiring managers and technical interviewers at internet companies (Alibaba, ByteDance, Meituan, JD, etc.) evaluating candidates for AI/Agent engineer and AI product manager roles.

**What this proves:**
- Agent engineering: LangGraph state machines, human-in-the-loop, tool orchestration, RAG with citations
- Product thinking: scenario analysis, user journeys, permission models, success metrics, risk mitigation
- Engineering maturity: Docker Compose reproducibility, structured APIs, audit trails, evaluation framework

**Tech stack (simplified from research report):**
- Orchestration: LangGraph (state machine, interrupt/resume, memory)
- API layer: FastAPI (OAuth2 scopes, dependency injection, OpenAPI docs)
- Database: PostgreSQL + pgvector (business data + vector search + RLS in one system)
- Cache: Redis (session cache, rate limiting)
- Model: OpenAI-compatible API (cloud or local vLLM)
- RAG: LlamaIndex for offline ingestion; custom retrieval chain online
- Frontend: Simple React/Next.js interface
- Infra: Docker Compose for local; no K8s in MVP
- Observability: Basic OTel tracing (polish phase: Prometheus + Grafana)

**Key differentiation from typical chatbot projects:**
- Not a chatbot — it's a business process agent that reads systems, enforces approvals, executes actions, and audits everything
- Evidence-first: every answer cites specific documents or data records
- Interrupt/resume: approval workflow is a first-class graph node, not an if/else hack
- Auditable: every run is replayable from audit logs

## Current State

- Phase 1 Foundation is complete: local infrastructure, schema, seed data, auth/scopes, repository layer, and CRUD/tool-call foundations are in place.
- Phase 2 RAG Pipeline is complete: 15 Chinese policy documents are chunked and embedded, `/api/v1/search/` returns tenant-filtered evidence with citation metadata, and live DB-backed EVAL-02 passes at Hit@5 83.3% with fallback accuracy 100.0%.
- Next phase is Phase 3 LangGraph Core: connect read tools, RAG evidence, trace logging, and same-thread memory into the read-only agent happy path.

## Constraints

- **Timeline**: 4 weeks to MVP core (full-time), 2 weeks polish (frontend + eval) — 6 weeks total
- **Learning curve**: LangGraph, FastAPI, pgvector are new — architecture must stay simple enough to learn while building
- **Solo developer**: no team; must avoid over-engineering
- **Demo-first**: everything must be runnable with `docker compose up` and demonstrable in 10 minutes
- **Open source**: all data must be synthetic/anonymized; no real PII; compliant with Chinese data protection laws

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Single graph, multi-node over multi-agent | Simpler to build, debug, and explain; multi-agent adds complexity without MVP value | — Pending |
| pgvector over Milvus/Weaviate | One-command reproducibility; business data + vectors + RLS in same DB | Adopted in Phase 2 |
| No Celery/queue system | LangGraph's durable execution handles the async flow; separate queue is premature | Adopted for Phase 2 ingestion/eval CLI; revisit only if Phase 3/4 needs background work |
| Chinese demo data, English README | Targets Chinese internet companies but accessible to global open-source community | — Pending |
| Approval as graph node, not external middleware | Demonstrates LangGraph's core strength; more impressive in interviews | — Pending |
| Simple frontend over pure API | 10-minute demo needs visual impact; keeps PM angle visible | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-11 after Phase 2 completion*
