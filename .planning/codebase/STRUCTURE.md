# Codebase Structure

**Analysis Date:** 2026-06-05

## Directory Layout

```text
MOCA/
├── src/                     # Python backend source
│   ├── api/                 # FastAPI app, routers, schemas, dependencies
│   ├── agent/               # LangGraph state, graph, nodes, trace, rag_context, tool registry
│   ├── approvals/           # Approval-domain schemas, snapshots, services, and state machine logic
│   ├── auth/                # JWT and permission helpers
│   ├── business/            # BusinessFactService plus business fact/query contracts and registry-backed schemas
│   ├── common/              # Domain-independent canonical helpers shared across phases
│   ├── conversation/        # Conversation log and safe tool call/result persistence services
│   ├── db/                  # SQLAlchemy models, session, Alembic migrations
│   ├── knowledge/           # Canonical policy evidence contracts and KnowledgeService facade
│   ├── memory/              # Session, long-term/case/CWC memory schemas, lifecycle adapters, repositories, services, identity, and tombstone helpers
│   ├── platform/            # TrustedContextFactory, canonical trusted context, and service-safe projection helpers
│   ├── rag/                 # Chunking, embedding, retrieval, citation validation
│   ├── replay/              # ReplayEventV3 schemas, validators, and replay event service boundary
│   ├── tools/               # Business tool contracts, descriptors, manager, and adapters
│   └── repositories/        # Database access layer
├── tests/                   # Backend unit, API, integration, agent, and RAG tests
├── frontend/                # Vite React TypeScript UI
├── scripts/                 # Seed, ingest, eval, smoke, and diagnostic scripts
├── data/policies/           # Synthetic policy knowledge-base documents
├── evaluation/              # Golden agent/RAG evaluation cases
├── eval/ and evals/         # Additional evaluation fixtures
├── rules/                   # Risk and approval rule configuration
├── docs/                    # Architecture, security, evaluation, and demo docs
├── .planning/               # GSD planning, phase artifacts, and codebase maps
├── docker-compose.yml       # Local service orchestration
├── Dockerfile               # Backend container image
├── pyproject.toml           # Python project and tool config
├── uv.lock                  # Python lockfile
└── README.md                # Project overview and run guidance
```

## Directory Purposes

**`src/api/`:**
- FastAPI app factory and middleware in `main.py`
- Versioned routers for auth, orders, refund cases, tickets, search, agent chat, approvals, traces, and agent runs
- Pydantic response/request schemas under `src/api/schemas/`

**`src/agent/`:**
- LangGraph orchestration in `graph.py`
- Shared state and schemas in `state.py` and `schemas.py`
- Node implementations under `src/agent/nodes/`
- Phase 22/33 RAG reasoning context kernel under `src/agent/rag_context/`, including material claim verification and deterministic domain hard-rule checks
- Trace persistence helpers in `trace.py`
- Tool contracts, registry, adapters, and concrete tools under `src/agent/tools/`

**`src/common/` and `src/approvals/`:**
- `src/common/canonical_hash.py` owns CanonicalHashProfile v1 and shared canonical JSON/hash input bytes
- `src/approvals/snapshots.py` owns ActionSafetySnapshot v1 projection and immutable hash computation
- `src/approvals/schemas.py` centralizes approval-domain schema version literals

**`src/knowledge/`, `src/business/`, `src/memory/`, and `src/tools/`:**
- Phase 8-16 domain facades and contracts for policy evidence, business reads, session memory, reviewed long-term/case memory schema/lifecycle, Case Working Context lifecycle boundaries, tombstone no-rewrite behavior, and tool invocation
- `src/knowledge/schemas.py` owns EvidenceRefV1 and canonical evidence projection reused by approval snapshots
- `src/business/schemas.py` owns BusinessContextV1 and BusinessFactResultV1; `src/business/query/registry.py` owns business-query descriptor allowlists, and `src/business/query/schemas.py` owns strict BusinessQuerySpec/result/context/cursor contracts re-exported through `src/business/schemas.py`; `src/business/service.py` contains BusinessFactService as the current-business-fact domain boundary beside the BusinessToolService compatibility facade

**`src/platform/`:**
- Phase 27 trusted context boundary for canonical `TrustedContext`, exact `MerchantScopeV1`, `TrustedContextFactory`, and service-safe projection helpers
- Projects trusted identity/scope into tool, knowledge, memory, approval, replay, intent policy, and AgentState compatibility contexts

**`src/conversation/`:**
- Phase 15.1 conversation memory boundary for safe user/assistant/tool message append and tool call/result persistence
- `ConversationService` owns raw payload/key rejection for messages, tool argument hashing, and prompt-safe tool result summaries
- `ConversationRepository` owns tenant/thread scoped writes to conversation, `tool_calls`, and `tool_results` tables

**`src/replay/`:**
- Phase 15 replay contract owner for strict ReplayEventV3/ReplayResponseV3 schemas, replay event registry validation, redaction/retention rules, and the ReplayService append/projection/allocation boundary
- Lifecycle, operation-pairing, and `/replay` API behavior are planned in later Phase 15 slices

**`src/db/` and `src/repositories/`:**
- ORM models for tenants, users, orders, refund cases, tickets, policy docs/chunks, audit logs, agent runs, approvals, action drafts, agent steps, replay/conversation records, reviewed memory tables, tombstones, and memory write events
- Alembic migrations through `013_long_term_case_memory`
- Repository classes that keep route and tool logic away from raw SQL

**`src/rag/`:**
- Policy ingestion, chunking, embedding, retrieval, and citation validation
- Search route and tool paths reuse this layer

**`frontend/`:**
- React UI with chat, timeline, details tabs, auth hook, API/SSE helpers, and reusable UI primitives

**`tests/`:**
- Backend test coverage across API routes, auth/tenant isolation, RAG, graph routing, approval flow, trace API, latency instrumentation, and Phase 7 tool registry contracts
- Agent-specific tests split under `tests/agent/test_nodes/` and `tests/agent/test_tools/`

## Key File Locations

**Entry Points:**
- Backend API: `src/api/main.py`
- Agent graph: `src/agent/graph.py`
- Frontend app: `frontend/src/App.tsx`
- Frontend bootstrap: `frontend/src/main.tsx`
- Local seed: `scripts/seed_demo.py`
- Policy ingest: `scripts/ingest_policies.py`

**Configuration:**
- Python project: `pyproject.toml`
- Backend settings: `src/config.py`
- Environment example: `.env.example`
- Local services: `docker-compose.yml`
- Frontend build: `frontend/vite.config.ts`

**Core Logic:**
- API routers: `src/api/routers/`
- Agent nodes: `src/agent/nodes/`
- Tool registry and contracts: `src/agent/tools/contracts.py`, `src/agent/tools/registry.py`
- Canonical hash: `src/common/canonical_hash.py`
- Approval snapshots: `src/approvals/snapshots.py`
- Replay schemas/service: `src/replay/schemas.py`, `src/replay/service.py`
- Trusted context contracts/projections: `src/platform/trusted_context.py`, `src/platform/context_projections.py`
- Evidence contracts: `src/knowledge/schemas.py`
- Approval and trace models: `src/db/models.py`
- RAG retrieval: `src/rag/retriever.py`

**Testing:**
- Backend tests: `tests/`
- Agent node tests: `tests/agent/test_nodes/`
- Agent tool tests: `tests/agent/test_tools/`
- Frontend hook test: `frontend/src/hooks/useAgentRun.test.ts`

## Naming Conventions

**Python:**
- Snake_case modules and test files
- Repository classes named by domain, such as `OrderRepository` and `ApprovalRepository`
- Pydantic schemas grouped by API or agent domain

**Frontend:**
- PascalCase React components
- TypeScript modules grouped by component domain, hooks, API helpers, and event types

**Planning:**
- Canonical `.planning/` docs use uppercase names
- Phase artifacts use phase-prefixed names such as `07-RESEARCH.md`

## Where to Add New Code

- New API endpoint: `src/api/routers/` plus schema in `src/api/schemas/`
- New DB access behavior: `src/repositories/` plus model/migration if schema changes
- New approval/snapshot behavior: `src/approvals/`
- New replay contract/service behavior: `src/replay/`
- New conversation/tool-result persistence behavior: `src/conversation/`
- New trusted identity/scope or service projection behavior: `src/platform/`
- New business query descriptor/schema behavior: `src/business/query/`
- New memory lifecycle adapter or CWC boundary behavior: `src/memory/`
- New shared canonical/hash helper: `src/common/`
- New agent node: `src/agent/nodes/` and graph wiring in `src/agent/graph.py`
- New post-retrieval reasoning context behavior: `src/agent/rag_context/`
- New tool: `src/agent/tools/` plus registry metadata and contract tests
- New RAG behavior: `src/rag/` plus search/RAG tests
- New UI view: `frontend/src/components/` or `frontend/src/hooks/`
- New evaluation: `evaluation/`, `eval/`, `evals/`, or `scripts/eval_*.py` depending on scope

---
*Structure analysis: 2026-06-05*
*Refresh when directories, entry points, or ownership boundaries change*
