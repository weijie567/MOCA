# MOCA — Merchant Operations Collaborative Agent

## What This Is

A production-grade AI agent for e-commerce/local-life platforms that helps merchants and support staff handle refund disputes, rule inquiries, and compensation decisions. It integrates with business systems (orders, refunds, tickets, coupons), retrieves evidence from a knowledge base, and enforces approval workflows for high-risk actions — all with full audit trails.

Built as an open-source portfolio project demonstrating enterprise Agent engineering and product thinking for AI/Agent engineer and product manager roles at top-tier internet companies.

## Core Value

When a merchant or support agent asks about a refund issue, the system must retrieve relevant business data and rules, provide an evidence-backed answer, and ensure any risky action goes through approval before execution — never silently executing something irreversible.

## Current Milestone: v1.1 Agent Architecture Migration

**Goal:** Migrate the existing deterministic agent toward explicit, testable contracts for knowledge, business tools, state/routing, intent/clarification, memory, approvals, actions, replay, schema rollout, and evaluation without weakening the shipped v1.0 safety boundary.

**Target features:**
- KnowledgeService and BusinessToolService facades with canonical evidence/tool contracts.
- Enforced AgentState lifecycle, trusted fields, router totality, and safe invalid-state fallback.
- Versioned approval lifecycle and immutable ActionSafetySnapshot binding.
- Strict demo draft boundary followed by separately owned future external execution.
- PostgreSQL-authoritative session memory CAS, with optional Redis hot cache and long-term/case memory independently deferred.
- ReplayEventV3, lifecycle finalizer, redaction/retention, migration rollout, contract tests, golden flows, and blocking eval gates.

## Requirements

### Validated

- [x] Docker Compose one-command startup for local infrastructure and FastAPI baseline (validated in Phase 1)
- [x] Role-based access control for support/reviewer/manager style API scopes (validated in Phase 1)
- [x] Demo data seed script populates realistic synthetic Chinese business data (validated in Phase 1)
- [x] Knowledge base ingestion, pgvector retrieval, top-5 evidence, citation validation, and DB-backed RAG Hit@5 baseline (validated in Phase 2)
- [x] Agent accepts refund/order questions, retrieves business context and policy evidence, and returns evidence-cited answers (validated in Phase 3)
- [x] Structured read tools retrieve order, refund, and ticket data for agent reasoning (validated in Phase 3)
- [x] Agent runs produce trace records for nodes, tool calls, evidence, and same-thread memory (validated in Phase 3)
- [x] High-risk actions trigger approval workflow interruption instead of direct execution (validated in Phase 4)
- [x] Approval decisions resume or halt graph execution through LangGraph interrupt/resume (validated in Phase 4)
- [x] Approval workflow creates auditable action drafts and exposes run-level trace replay (validated in Phase 4)
- [x] Simple frontend allows submitting questions, viewing streamed agent responses, inspecting evidence/trace details, and handling approvals (validated in Phase 5)
- [x] Final evaluation and polish expands the golden set, validates end-to-end metrics, and prepares demo/README materials (validated in Phase 6)
- [x] v1.1 contract baseline inventories current evidence, target contracts, phase owners, follow-up gates, and downstream readiness (validated in Phase 7)
- [x] v1.1 KnowledgeService and BusinessToolService boundaries are explicit and verified (validated in Phases 8-9)
- [x] v1.1 state/router and intent/clarification contracts are deterministic and tested (validated in Phases 10-11)
- [x] v1.1 PostgreSQL-authoritative session memory uses CAS, safe same-thread slot continuity, evidence/action authority separation, and explicit Redis deferral (validated in Phase 12)
- [x] v1.1 approval lifecycle and ActionSafetySnapshot binding are versioned, immutable, and verified (validated in Phase 13)
- [x] v1.1 demo action boundary creates durable drafts only, binds exact payload/hash/snapshot data, and fails closed without trusted approval permission (validated in Phase 14)
- [x] v1.1 replay contract stores and reads ReplayEventV3 facts with lifecycle finalization, shared sequence allocation, operation pairing, redaction/retention, `/replay` read-switch, and `/trace` fallback (validated in Phase 15)

### Active

- [ ] v1.1 validates each owned contract with migration verification, forbidden-behavior tests, golden flows, and explicit eval gates.

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
- Cache: Redis (optional non-authoritative session hot cache, rate limiting)
- Model: OpenAI-compatible API (cloud or local vLLM)
- RAG: LlamaIndex for offline ingestion; custom retrieval chain online
- Frontend: Simple React + Vite interface
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
- Phase 3 LangGraph Core is complete: read tools, RAG evidence, trace logging, same-thread memory, and the read-only agent happy path are validated.
- Phase 4 Approval Workflow & Audit is complete: high-risk actions interrupt for approval, approve/reject resumes are validated, action drafts are idempotent, trace replay is queryable by run_id, and high-risk interception is 100%.
- Phase 5 Frontend & SSE is complete: the React/Vite demo supports chat submission, progressive SSE timeline updates, evidence/trace inspection, pending approval handling, role switching, and Docker Compose frontend-to-API routing.
- Phase 6 Evaluation & Polish is complete: the golden set now covers 14 RAG cases and 35 deterministic agent cases, evaluation scripts generate reports, CI runs lint/unit checks, and README/demo/security/evaluation docs are polished for the v1.0 demo.
- v1.0 MVP is shipped and archived on 2026-05-22. Full milestone history lives in `.planning/milestones/v1.0-ROADMAP.md` and `.planning/milestones/v1.0-REQUIREMENTS.md`.
- Phase 7 Contract Baseline is complete: the contract inventory, current-vs-target evidence checklist, initial coverage matrix, follow-up register disposition, and readiness verdict are persisted.
- Phase 8 Knowledge Facade is complete: policy evidence retrieval uses the KnowledgeService facade with canonical EvidenceRefV1/citation contracts and verified checkpoint red-line behavior.
- Phase 9 Business Tool Facade is complete: read business tools route through BusinessToolService with trusted ToolCallContext and typed ToolResultV2.
- Phase 10 State Lifecycle + Routing Migration is complete: AgentState lifecycle, trusted-field reset/merge behavior, deterministic routers, empty session-memory adapter, and bounded investigate graph wiring are verified.
- Phase 11 Intent / Clarification is complete: strict intent schema, deterministic pre-router/slot routing, ordinary clarification, and hash-owned golden/manifest gates are verified.
- Phase 12 Session Memory is complete: PostgreSQL-authoritative session memory, CAS merge/conflict behavior, same-thread slot continuity, evidence/action authority separation, post-response bounded writes, and Redis skip decision are verified.
- Phase 13 Approval State Machine is complete: versioned lifecycle, immutable ActionSafetySnapshot binding, trusted API/graph transitions, approval events, SLA scanning, and legacy quarantine are verified.
- Phase 14 Demo Action Executor Boundary is complete: durable draft-only behavior, exact payload/hash/snapshot binding, no-approval fail-closed behavior, trusted write-tool permission ownership, and draft-only final/API wording are verified.
- Phase 15 Replay Event Contract is complete: ReplayEventV3 storage/projection, lifecycle finalization, shared sequence allocation, operation pairing, replay redaction/retention, `/replay` read-switch, `/trace` rollback fallback, and owner-named Phase 17 deferrals are verified.
- Active planning is now ready for Phase 16 Long-term / Case Memory.

## Next Milestone Goals

Define the milestone after v1.1 only after the deferred owner phases 16-17 are explicitly accepted, rescheduled, or carried forward.

## Constraints

- **Timeline**: 4 weeks to MVP core (full-time), 2 weeks polish (frontend + eval) — 6 weeks total
- **Learning curve**: LangGraph, FastAPI, pgvector are new — architecture must stay simple enough to learn while building
- **Solo developer**: no team; must avoid over-engineering
- **Demo-first**: everything must be runnable with `docker compose up` and demonstrable in 10 minutes
- **Open source**: all data must be synthetic/anonymized; no real PII; compliant with Chinese data protection laws

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Single graph, multi-node over multi-agent | Simpler to build, debug, and explain; multi-agent adds complexity without MVP value | Adopted through Phase 6 |
| pgvector over Milvus/Weaviate | One-command reproducibility; business data + vectors + RLS in same DB | Adopted in Phase 2 |
| No Celery/queue system | LangGraph's durable execution handles the async flow; separate queue is premature | Adopted for Phase 2 ingestion/eval CLI; revisit only if Phase 3/4 needs background work |
| Chinese demo data, English README | Targets Chinese internet companies but accessible to global open-source community | Adopted in Phase 6 |
| Approval as graph node, not external middleware | Demonstrates LangGraph's core strength; more impressive in interviews | Adopted in Phase 4 |
| Simple frontend over pure API | 10-minute demo needs visual impact; keeps PM angle visible | Adopted in Phase 5 |
| Keep v1.1 scope fresh | v1.0 requirements are complete and archived; continuing in the same requirements file would mix shipped and future obligations | Adopted after v1.0 archive |
| Replace the previous v1.1 investigation roadmap with Agent Architecture Migration | The architecture spec now defines the authoritative capability sequence and standard Phase 7-17 identities are required for SDK planning | Adopted 2026-06-06 |
| Phase 13-17 architecture-first planning standard | Approval, action, replay, memory, and external execution are tightly coupled; plans must read `docs/phase-13-17-architecture-plan.md`, define owners/contracts first, and delete or quarantine old paths instead of preserving minimum-diff compatibility | Adopted 2026-06-15 |

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
*Last updated: 2026-06-16 after Phase 15 verified complete and Phase 16 became ready to plan*
