# Architecture

**Analysis Date:** 2026-06-05

## Pattern Overview

**Overall:** Full-stack merchant operations agent prototype with a Python FastAPI backend, LangGraph agent workflow, Postgres-backed persistence, RAG policy retrieval, human approval interrupts, and a React frontend.

**Key Characteristics:**
- API-first backend with explicit schemas and trace IDs
- Domain repositories isolate database access from routes and tools
- LangGraph nodes implement a single refund/merchant-ops workflow
- RAG evidence and citation validation are first-class safety inputs
- High-risk actions move through approval requests and graph resume
- Tool registry now has typed metadata, caller authorization, side-effect/risk constraints, and contract tests

## Layers

**Frontend Layer:**
- Purpose: Operator-facing chat, timeline, evidence, and trace display
- Contains: `frontend/src/App.tsx`, `frontend/src/components/`, `frontend/src/hooks/`, `frontend/src/lib/`
- Depends on: Backend REST and SSE endpoints

**API Layer:**
- Purpose: HTTP contract, auth dependencies, error shape, trace middleware, and route composition
- Contains: `src/api/main.py`, `src/api/routers/`, `src/api/schemas/`, `src/api/deps.py`
- Depends on: Repositories, auth helpers, agent graph, RAG services

**Agent Layer:**
- Purpose: Orchestrate merchant support reasoning, evidence retrieval, risk assessment, approval interrupt, action execution, and final response
- Contains: `src/agent/graph.py`, `src/agent/state.py`, `src/agent/nodes/`, `src/agent/tools/`, `src/agent/trace.py`
- Depends on: LangGraph, repositories, RAG, tool registry, approval persistence

**RAG Layer:**
- Purpose: Ingest policy documents, chunk knowledge, embed/search evidence, validate citations
- Contains: `src/rag/`, `data/policies/`, `scripts/ingest_policies.py`, evaluation fixtures
- Depends on: Policy document/chunk repositories and vector storage

**Persistence Layer:**
- Purpose: Tenant-scoped business data, audit logs, policy documents/chunks, agent runs/steps, approval requests/steps, and action drafts
- Contains: `src/db/models.py`, `src/db/session.py`, `src/db/migrations/`, `src/repositories/`
- Depends on: PostgreSQL, pgvector, SQLAlchemy, Alembic

**Replay / Observability Layer:**
- Purpose: Own replay contract schemas, consolidated event registry validation, and V3 event-store expansion over `agent_trace_events`
- Contains: `src/replay/`, `src/db/migrations/versions/010_replay_event_v3.py`, `AgentTraceEvent`
- Depends on: Phase 10 minimal event envelope and Phase 13/14 approval/action event additions

**Conversation Memory Layer:**
- Purpose: Persist conversation facts and safe tool call/result records without replacing business, policy, approval/action, or replay authorities
- Contains: `src/conversation/`, `conversation_threads`, `conversation_messages`, `tool_calls`, and `tool_results`
- Depends on: SQLAlchemy session, Phase 15.1 conversation schema, and prompt-safe tool storage contracts from `src/tools/contracts.py`

**Planning and Verification Layer:**
- Purpose: Requirements, phase plans, review/security/UAT artifacts, architecture docs, and evaluation criteria
- Contains: `.planning/`, `docs/`, `evaluation/`, `eval/`, `evals/`

## Data Flow

**Authenticated API Flow:**
1. Client sends request with bearer token.
2. `src/api/main.py` assigns `trace_id` and routes request.
3. Route dependency resolves current user and scopes.
4. Router calls repository, RAG service, or agent graph.
5. Response returns standard `ApiResponse` shape with trace context.

**Agent Chat Flow:**
1. Agent run is created through `/api/v1/agent` or `/api/v1/agent-runs`.
2. LangGraph starts with request state and tenant/user context.
3. Nodes classify intent, load business context, retrieve policy evidence, generate recommendation, assess risk, and decide approval.
4. Low-risk read paths produce a final response directly.
5. High-risk actions create approval state and interrupt through LangGraph.
6. Approval decision resumes the graph and records approval/action/trace events.

**Tool Flow:**
1. Tool registry receives typed input, caller context, and tool metadata.
2. Registry validates schema, caller permissions, allowed caller class, side-effect category, and risk metadata.
3. Adapter calls repository/RAG behavior.
4. Tool output is normalized into evidence refs, data, errors, and execution metadata.
5. Investigate persists tool calls/results through `ConversationService` when a DB session is available.
6. AgentState receives `ToolResultPromptSummary` refs/summaries, not full `ToolResultV2.data` dumps.

**Approval Snapshot Hash Flow:**
1. Proposed action material is canonicalized with `CanonicalHashProfile v1` from `src/common/canonical_hash.py`.
2. `src/approvals/snapshots.py` builds `ActionSafetySnapshot` from refs, hashes, policy/risk/retrieval versions, and canonical `EvidenceRefV1` values.
3. Snapshot hash projection strips evidence `score`, retains `rank`, applies rank-aware evidence sorting, and computes `immutable_hash`.
4. Later approval/action/replay consumers validate exact action payload and safety snapshot hashes rather than defining local serializers.

**RAG Flow:**
1. Policy markdown files are ingested and chunked.
2. Chunks are stored with metadata and embeddings.
3. Search retrieves evidence by query and tenant/policy metadata.
4. Citation validator checks that generated references map to available evidence.

## Key Abstractions

- `AgentState` - Shared graph state passed through LangGraph nodes
- `AgentRun` / `AgentStep` - Run-level and node-level execution trace persistence
- `ApprovalRequest` / `ApprovalStep` - Human review lifecycle for high-risk actions
- `ActionDraft` - Idempotent proposed/executed action record
- `ToolRegistryEntry` - Typed registry metadata for tool risk, side effects, caller permissions, schemas, and visibility
- `ToolInvocationContext` - Caller/tenant/run context for tool execution authorization
- `ToolResultPromptSummary` - Prompt-safe tool result projection with refs/status/summary and no raw tool payload data
- `ConversationService` - Conversation log and tool call/result persistence boundary for Phase 15.1 memory foundation
- `CanonicalHashProfile v1` - Shared canonical JSON and hash input byte contract for approval/action/replay hashes
- `ActionSafetySnapshot` - Immutable approval/action safety snapshot over proposed action hash, evidence refs, and config versions
- `ReplayEventV3` / `ReplayResponseV3` - Strict Phase 15 replay audit contract over event-store rows
- `EvidenceItem` / retrieval schemas - RAG grounding contract
- `ApiResponse` - Standard response envelope

## Entry Points

- API app: `src/api/main.py`
- Graph builder: `src/agent/graph.py`
- Approval decision route: `src/api/routers/approvals.py`
- Agent streaming/runs routes: `src/api/routers/agent.py`, `src/api/routers/agent_runs.py`
- Search route: `src/api/routers/search.py`
- Canonical hash helper: `src/common/canonical_hash.py`
- Approval snapshot helper: `src/approvals/snapshots.py`
- Frontend app: `frontend/src/App.tsx`
- Seed script: `scripts/seed_demo.py`
- Eval scripts: `scripts/eval_*.py`

## Error Handling

**Current strategy:**
- API middleware attaches trace IDs and returns standardized error payloads.
- Routers raise FastAPI HTTP errors for auth, tenant, not-found, and conflict cases.
- Tool registry converts validation and execution failures into structured tool errors.
- Agent nodes record trace steps and preserve evidence/approval context.

**Important behavior:**
- Tenant isolation is enforced in routes/repositories and covered by integration tests.
- Approval decisions reject self-approval, expired approvals, duplicate decisions, and invalid reviewer permissions.
- RAG failures should degrade toward no-evidence/fallback behavior rather than unsafe execution.

## Cross-Cutting Concerns

**Traceability:**
- `trace_id`, `run_id`, node trace steps, approval events, and action drafts are persisted and exposed through trace APIs.

**Safety:**
- High-risk recommendations require approval.
- Tool metadata distinguishes read/retrieval/write/approval side effects.
- Investigator-visible tools are constrained to non-mutating behavior.

**Tenant Boundaries:**
- Tenant IDs are present across business and agent records.
- API tests cover cross-tenant not-found/forbidden behavior.

**Evaluation:**
- Golden RAG and agent cases exist under `evaluation/`, `eval/`, and `evals/`.
- Scripts support evaluation and smoke validation.

---
*Architecture analysis: 2026-06-05*
*Refresh when graph nodes, tool contracts, persistence schema, or API ownership boundaries change*
