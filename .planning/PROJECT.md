# MOCA — Merchant Operations Collaborative Agent

## What This Is

A production-grade AI agent for e-commerce/local-life platforms that helps merchants and support staff handle refund disputes, rule inquiries, and compensation decisions. It integrates with business systems (orders, refunds, tickets, coupons), retrieves evidence from a knowledge base, and enforces approval workflows for high-risk actions — all with full audit trails.

Built as an open-source portfolio project demonstrating enterprise Agent engineering and product thinking for AI/Agent engineer and product manager roles at top-tier internet companies.

## Core Value

When a merchant or support agent asks about a refund issue, the system must retrieve relevant business data and rules, provide an evidence-backed answer, and ensure any risky action goes through approval before execution — never silently executing something irreversible.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Agent can accept a refund/order question and return an evidence-cited answer
- [ ] Agent retrieves order, refund, and ticket data via structured tool calls
- [ ] Agent searches knowledge base (refund rules, SOPs) and cites specific documents
- [ ] High-risk actions (compensation > threshold, refund override) trigger approval workflow
- [ ] Approval interrupts graph execution; resumes after human decision
- [ ] All agent runs produce audit logs (input, evidence, tools called, approval chain)
- [ ] Simple frontend allows submitting questions and viewing agent responses
- [ ] Role-based access control (merchant, support, reviewer, manager)
- [ ] Demo data seed script populates realistic Chinese business data
- [ ] Docker Compose one-command startup for full local environment

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
| pgvector over Milvus/Weaviate | One-command reproducibility; business data + vectors + RLS in same DB | — Pending |
| No Celery/queue system | LangGraph's durable execution handles the async flow; separate queue is premature | — Pending |
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
*Last updated: 2026-05-09 after design convergence review*
