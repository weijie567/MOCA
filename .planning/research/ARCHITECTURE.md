# Architecture Research: MOCA

## System Overview

MOCA is a single-graph, multi-node AI agent system for e-commerce merchant operations. The system receives a user question (typically about refunds/orders), orchestrates data retrieval and knowledge base search via LangGraph, enforces approval workflows for high-risk actions, and returns evidence-cited answers with full audit trails.

The core data flow is: **FastAPI receives request -> LangGraph orchestrates the agent graph -> graph nodes call tools and RAG -> approval node interrupts if needed -> results written to audit log -> response returned**.

Key architectural principle: keep the number of moving parts minimal for a solo developer learning these tools. One Postgres database handles business data, vector search (pgvector), state checkpointing, and audit logs. Redis handles session cache and rate limiting. LangGraph handles all orchestration including the approval interrupt/resume pattern.

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────────┐
│   Frontend  │────▶│  FastAPI (API)   │────▶│  LangGraph (Orchestrator)   │
└─────────────┘     └──────────────────┘     └─────────────────────────────┘
                           │                        │         │         │
                           │                        ▼         ▼         ▼
                           │                    ┌───────┐ ┌───────┐ ┌────────┐
                           │                    │ Tools │ │  RAG  │ │Approval│
                           │                    └───┬───┘ └───┬───┘ └────┬───┘
                           │                        │         │          │
                           ▼                        ▼         ▼          ▼
                    ┌─────────────┐          ┌─────────────────────────────┐
                    │    Redis    │          │  PostgreSQL + pgvector       │
                    │(cache/rate) │          │  (data + vectors + audit)   │
                    └─────────────┘          └─────────────────────────────┘
```

## Components

### FastAPI Service Layer

- **Responsibility**: HTTP API gateway, authentication, request validation, routing to agent graph, serving approval endpoints, exposing audit logs
- **Boundary**: Does NOT contain business logic or orchestration logic. Does NOT call LLM directly. Does NOT manage graph state.
- **Inputs**: HTTP requests with JWT tokens, user questions, approval decisions
- **Outputs**: JSON responses (agent results, approval status, audit records)
- **Key design decisions**:
  - Single `apps/api/` application, not a microservice split
  - OAuth2 scopes for coarse-grained authorization (`ticket.read`, `refund.propose`, `compensation.approve`)
  - Dependency injection for DB sessions, current user, and agent graph runner
  - Streaming support via SSE for real-time agent execution updates
  - Router structure: `agent/`, `approvals/`, `audit/`, `tools/` (direct tool access for testing), `rag/` (direct search for testing)

### LangGraph Orchestrator

- **Responsibility**: Manages the agent execution graph — routing, tool calling, RAG retrieval, approval interrupts, state persistence
- **Boundary**: Does NOT handle HTTP concerns. Does NOT manage auth. Does NOT directly access the database (uses tools for that).
- **Inputs**: `AgentState` containing user question, context (order_id, tenant_id, user role), conversation history
- **Outputs**: Updated `AgentState` with answer, evidence citations, tool call results, approval status
- **Key design decisions**:
  - Single compiled graph for the refund troubleshooting flow
  - State checkpointed to Postgres via LangGraph's `PostgresSaver`
  - `interrupt_before` on the approval node for human-in-the-loop
  - Thread-based execution: each conversation is a thread with persistent state

### Tool Layer

- **Responsibility**: Provides structured, schema-defined tools that the LLM can call to read/write business systems
- **Boundary**: Does NOT make decisions. Does NOT call other tools. Each tool is a single atomic operation.
- **Inputs**: Typed parameters (e.g., `order_id: str`, `amount: float`)
- **Outputs**: Structured result dict with status, data, and error info
- **Key design decisions**:
  - All tools are simulated (no real payment systems) but with realistic latency and error modes
  - Each tool has a Pydantic schema for input validation
  - Tools are decorated with `@tool` from LangChain for LLM compatibility
  - Tools enforce permission checks using the current user context from state
  - Error handling: tools return structured errors, never raise exceptions to the graph

### RAG Pipeline

- **Responsibility**: Ingests knowledge base documents offline; retrieves relevant evidence online with citations
- **Boundary**: Does NOT make business decisions. Does NOT execute actions. Only retrieves and ranks evidence.
- **Inputs**: (Offline) document files; (Online) search query + metadata filters
- **Outputs**: Ranked list of chunks with doc_id, chunk_id, relevance score, and source text
- **Key design decisions**:
  - Offline ingestion via LlamaIndex: parse -> chunk -> embed -> store in pgvector
  - Online retrieval is a custom function (not LlamaIndex runtime) for control and simplicity
  - Dense retrieval via pgvector HNSW + optional BM25-style keyword matching in SQL
  - Metadata filtering: `audience_scope`, `effective_date`, `risk_level` as pre-filters
  - Reranking: simple cross-encoder rerank for top-k results (can be a lightweight model or LLM-based)

### Approval Workflow

- **Responsibility**: Interrupts graph execution when a high-risk action is proposed, persists the pending state, resumes after human decision
- **Boundary**: Does NOT execute the action itself. Does NOT decide whether to approve (that's the human's job). Only gates execution.
- **Inputs**: Proposed action with risk assessment, current user permissions, threshold config
- **Outputs**: Approval decision (approved/rejected/modified) that feeds back into graph state
- **Key design decisions**:
  - Implemented as a graph node that uses LangGraph's `interrupt()` function
  - Approval request persisted to `approval_requests` table with status tracking
  - Resume via API endpoint that calls `graph.invoke(None, config)` with the same thread_id
  - Risk thresholds configurable per action type (e.g., compensation > 10 CNY requires manager approval)

### Audit Logger

- **Responsibility**: Records the complete execution trace of every agent run for replay and compliance
- **Boundary**: Does NOT block execution. Does NOT make decisions. Append-only.
- **Inputs**: Events from graph execution (node entries/exits, tool calls, LLM calls, approval decisions)
- **Outputs**: Structured audit records in `audit_logs` and `agent_steps` tables
- **Key design decisions**:
  - Implemented via LangGraph callbacks/listeners, not inline in business logic
  - Each step records: `run_id`, `node_name`, `input`, `output`, `duration_ms`, `token_usage`, `timestamp`
  - Linked to OTel trace_id for cross-system correlation
  - Immutable: no UPDATE/DELETE on audit tables

## Data Flow

Step-by-step flow from user input to final response:

```
1. User submits question via frontend
   POST /api/v1/agent/runs {order_id, question, tenant_id}

2. FastAPI authenticates (JWT), authorizes (scopes), creates run record
   → Extracts user role, tenant_id, permissions

3. FastAPI invokes LangGraph with initial state
   → graph.ainvoke(initial_state, config={thread_id, checkpointer})

4. ROUTER NODE: LLM classifies intent
   → "query_only" | "needs_tools" | "needs_action"
   → Routes to appropriate next node

5. RETRIEVER NODE: Searches knowledge base
   → Rewrites query for retrieval
   → Calls pgvector similarity search with metadata filters
   → Returns top-k chunks with citations

6. TOOL_CALLER NODE: Executes business data lookups
   → LLM decides which tools to call (get_order, get_refund_case, etc.)
   → Tools execute and return structured data
   → Results accumulated in state

7. REASONER NODE: Synthesizes answer with evidence
   → LLM generates response citing specific docs and data
   → If action needed: generates action proposal with risk assessment

8. RISK_CHECK NODE: Evaluates if action exceeds user's authority
   → Compares proposed action against threshold config
   → If within authority: routes to EXECUTOR
   → If exceeds authority: routes to APPROVAL

9a. APPROVAL NODE (if triggered): Interrupts execution
    → Writes approval_request to DB
    → Graph state checkpointed to Postgres
    → Returns {status: "waiting_approval", approval_request_id}
    → [PAUSE — human reviews and decides via API]
    → On resume: reads decision, routes to EXECUTOR or REJECTED

9b. EXECUTOR NODE: Performs the approved action
    → Calls write tools (create_coupon_grant, update_ticket_status)
    → Records compensation/rollback info

10. RESPONSE NODE: Assembles final output
    → Combines: answer text + evidence citations + actions taken + rollback options
    → Writes complete audit log entry

11. FastAPI returns response to frontend
    → {run_id, status, summary, evidence[], actions[], audit_url}
```

## LangGraph Design

### State Schema

```python
from typing import TypedDict, Literal, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # Core conversation
    messages: Annotated[list, add_messages]
    
    # Request context (set once at start)
    run_id: str
    tenant_id: str
    user_id: str
    user_role: str  # merchant_user | support_agent | risk_reviewer | ops_manager
    scene: str      # refund_triage | rule_inquiry | compensation_request
    
    # Business context (accumulated by tools)
    order_data: dict | None
    refund_data: dict | None
    ticket_data: dict | None
    
    # RAG results
    evidence: list[dict]  # [{doc_id, chunk_id, text, score}]
    
    # Tool execution tracking
    tool_calls: list[dict]  # [{tool_name, input, output, duration_ms}]
    
    # Action and approval
    proposed_action: dict | None  # {action_type, params, risk_level}
    approval_decision: dict | None  # {approved, comment, approver_id}
    executed_actions: list[dict]  # [{action_type, result, rollback_action}]
    
    # Routing
    intent: str | None  # query_only | needs_tools | needs_action
    next_node: str | None
    
    # Final output
    answer: str | None
    citations: list[dict]
```

### Nodes

| Node | Role | Key Logic |
|------|------|-----------|
| `router` | Classify user intent, decide execution path | LLM call with few-shot examples for intent classification |
| `retriever` | Search knowledge base for relevant rules/docs | Query rewrite + pgvector search + metadata filter |
| `tool_caller` | Execute business data lookups | LLM decides tools; tools execute with error handling |
| `reasoner` | Synthesize evidence into answer or action proposal | LLM generates cited response; proposes action if needed |
| `risk_check` | Evaluate if proposed action needs approval | Rule-based threshold check (no LLM needed) |
| `approval` | Interrupt for human decision | `interrupt()` call; state persisted; resumes on API call |
| `executor` | Perform approved actions via write tools | Execute action tools; record rollback info |
| `response` | Assemble final output and write audit | Format response; write audit_logs entry |

### Edges

```python
from langgraph.graph import StateGraph, END

graph = StateGraph(AgentState)

# Add nodes
graph.add_node("router", router_node)
graph.add_node("retriever", retriever_node)
graph.add_node("tool_caller", tool_caller_node)
graph.add_node("reasoner", reasoner_node)
graph.add_node("risk_check", risk_check_node)
graph.add_node("approval", approval_node)
graph.add_node("executor", executor_node)
graph.add_node("response", response_node)

# Entry point
graph.set_entry_point("router")

# Conditional routing from router
graph.add_conditional_edges("router", route_by_intent, {
    "query_only": "retriever",
    "needs_tools": "tool_caller",
    "needs_action": "tool_caller",
})

# Sequential flow for data gathering
graph.add_edge("tool_caller", "retriever")
graph.add_edge("retriever", "reasoner")

# Conditional from reasoner
graph.add_conditional_edges("reasoner", check_action_needed, {
    "no_action": "response",
    "action_proposed": "risk_check",
})

# Conditional from risk_check
graph.add_conditional_edges("risk_check", check_approval_needed, {
    "within_authority": "executor",
    "needs_approval": "approval",
})

# After approval decision
graph.add_conditional_edges("approval", check_approval_result, {
    "approved": "executor",
    "rejected": "response",
})

# Executor always goes to response
graph.add_edge("executor", "response")

# Response is terminal
graph.add_edge("response", END)
```

### Interrupt Points

| Interrupt | Mechanism | Resume Trigger |
|-----------|-----------|----------------|
| Approval required | `interrupt()` in approval node | `POST /api/v1/approvals/{id}/approve` calls `graph.ainvoke(None, config)` |
| Human clarification needed (future) | `interrupt()` in reasoner node | User sends follow-up message |

LangGraph's `interrupt()` function (available since v0.2.x) is the preferred mechanism over the older `interrupt_before`/`interrupt_after` config. When `interrupt()` is called:
1. The current node's execution pauses
2. State is checkpointed to the PostgresSaver
3. The graph returns a partial result with interrupt metadata
4. On resume, execution continues from the interrupted node with updated state

## Build Order

Recommended implementation sequence for the 4-week MVP:

### Week 1: Foundation (no LLM yet)

**Rationale**: Get the infrastructure running first so every subsequent week can build on a working system.

1. Docker Compose with Postgres (+ pgvector extension) and Redis
2. FastAPI skeleton with health check, CORS, basic error handling
3. Database schema: `orders`, `refund_cases`, `tickets`, `users`, `roles`
4. Seed script: generate 50-100 realistic Chinese demo records
5. Basic CRUD endpoints for orders/refunds/tickets (these become the tool backends)
6. Simple JWT auth with hardcoded demo users (merchant, support, manager)

**Verification**: `docker compose up` starts everything; Swagger UI shows working endpoints.

### Week 2: RAG Pipeline

**Rationale**: RAG is independent of the agent graph and can be built/tested in isolation. Having it ready means the graph can use it immediately.

1. Create 20-30 knowledge base documents (refund rules, SOPs, FAQs in Chinese)
2. LlamaIndex ingestion script: parse markdown -> chunk by heading -> embed -> store in pgvector
3. Retrieval function: query embedding + cosine similarity + metadata filter
4. `POST /api/v1/rag/search` endpoint for testing retrieval quality
5. Basic eval: 10 test queries with expected doc matches

**Verification**: Given a refund question, the search endpoint returns relevant rule chunks.

### Week 3: LangGraph Core

**Rationale**: With tools (week 1 endpoints) and RAG (week 2) ready, the graph can be wired up end-to-end.

1. Define `AgentState` TypedDict
2. Implement tool wrappers: `get_order`, `get_refund_case`, `get_ticket`, `search_knowledge_base`
3. Implement nodes: `router`, `retriever`, `tool_caller`, `reasoner`, `response`
4. Wire up the graph (without approval path initially)
5. `POST /api/v1/agent/runs` endpoint that invokes the graph
6. PostgresSaver for state checkpointing
7. Basic audit logging (write `agent_runs` and `agent_steps` records)

**Verification**: Submit a refund question -> get back an evidence-cited answer with tool call traces.

### Week 4: Approval + Polish

**Rationale**: The approval flow is the project's differentiator. With the happy path working, add the interrupt/resume pattern.

1. `approval_requests` table and API endpoints
2. `risk_check` node with configurable thresholds
3. `approval` node using `interrupt()`
4. `executor` node for write actions (simulated coupon grant, status update)
5. Resume endpoint: `POST /api/v1/approvals/{id}/approve` -> resumes graph
6. Audit log enrichment: full trace with approval chain
7. End-to-end test: question -> tools -> evidence -> approval interrupt -> approve -> execute -> audit

**Verification**: A compensation request that exceeds threshold pauses for approval; after approval, execution completes and audit log shows the full chain.

## Key Patterns

### Pattern: Tool as Thin Wrapper

Every tool follows the same structure: validate input -> call data layer -> return structured result. Tools never raise exceptions to the graph; they return error objects.

```python
@tool
def get_order(order_id: str, state: AgentState) -> dict:
    """Retrieve order details by order ID."""
    # Permission check
    if not can_access_order(state["user_role"], state["tenant_id"], order_id):
        return {"status": "error", "error": "permission_denied"}
    # Data fetch
    order = db.query(Order).filter_by(id=order_id).first()
    if not order:
        return {"status": "error", "error": "not_found"}
    return {"status": "ok", "data": order.to_dict()}
```

### Pattern: Evidence Accumulation

State accumulates evidence from multiple sources. The reasoner node receives all evidence and must cite specific items in its response.

```python
# In retriever node
state["evidence"].extend([
    {"source": "knowledge_base", "doc_id": "kb_12", "chunk_id": "c_44", "text": "..."}
])

# In tool_caller node  
state["evidence"].extend([
    {"source": "tool", "tool_name": "get_order", "record_id": "ORD_001", "data": {...}}
])
```

### Pattern: Interrupt-Resume via Checkpoint

The approval flow uses LangGraph's native checkpoint + interrupt mechanism. No external queue or polling needed.

```python
# In approval node
def approval_node(state: AgentState) -> AgentState:
    # Persist approval request to DB
    request = create_approval_request(state["proposed_action"], state["run_id"])
    
    # Interrupt — graph pauses here, state is checkpointed
    decision = interrupt({
        "approval_request_id": request.id,
        "proposed_action": state["proposed_action"],
        "message": "Awaiting manager approval"
    })
    
    # When resumed, `decision` contains the approval result
    state["approval_decision"] = decision
    return state
```

Resume from API:
```python
# In FastAPI endpoint
@router.post("/approvals/{request_id}/approve")
async def approve(request_id: str, body: ApprovalBody, user: User = Depends(get_current_user)):
    # Update DB record
    update_approval_request(request_id, approved=True, comment=body.comment)
    
    # Resume the graph with the decision
    config = {"configurable": {"thread_id": approval_request.thread_id}}
    result = await graph.ainvoke(
        Command(resume={"approved": True, "comment": body.comment, "approver_id": user.id}),
        config
    )
    return result
```

### Pattern: Audit as Callback

Audit logging is implemented as a LangGraph callback, not inline in node logic. This keeps nodes focused on business logic.

```python
class AuditCallback(BaseCallbackHandler):
    def on_chain_start(self, run_id, inputs, **kwargs):
        # Record node entry
        
    def on_tool_end(self, output, run_id, **kwargs):
        # Record tool result
        
    def on_llm_end(self, response, run_id, **kwargs):
        # Record token usage
```

### Pattern: Layered Auth

Authentication and authorization happen at two levels:
1. **API level** (FastAPI dependencies): JWT validation, scope checking
2. **Tool level** (within graph execution): data access checks using state context

```python
# API level — FastAPI dependency
async def require_scope(scope: str):
    def checker(token: str = Depends(oauth2_scheme)):
        payload = decode_jwt(token)
        if scope not in payload["scopes"]:
            raise HTTPException(403)
        return payload
    return checker

# Tool level — inside tool execution
def can_access_order(user_role: str, tenant_id: str, order_id: str) -> bool:
    order = db.query(Order).filter_by(id=order_id).first()
    if not order:
        return False
    if user_role == "merchant_user":
        return order.tenant_id == tenant_id
    if user_role == "support_agent":
        return order.tenant_id in get_assigned_tenants(user_id)
    return True  # managers/admins
```

### Pattern: Configurable Risk Thresholds

Risk assessment is rule-based (no LLM needed), making it deterministic and testable.

```python
RISK_THRESHOLDS = {
    "coupon_grant": {
        "low": {"max_amount": 5, "approver": None},
        "medium": {"max_amount": 20, "approver": "ops_manager"},
        "high": {"max_amount": float("inf"), "approver": "ops_manager"},
    },
    "refund_override": {
        "any": {"approver": "risk_reviewer"},
    },
}

def assess_risk(action: dict, user_role: str) -> str:
    """Returns: 'proceed' | 'needs_approval'"""
    thresholds = RISK_THRESHOLDS.get(action["type"], {})
    # ... threshold logic
```

## MVP Simplifications

These are intentional scope cuts for the 4-week timeline:

| Full version | MVP simplification | Upgrade path |
|---|---|---|
| Multi-tenant RLS | Single tenant, role-based access only | Add RLS policies in polish phase |
| Hybrid search (dense + BM25) | Dense-only pgvector search | Add `ts_vector` column for BM25 later |
| Streaming responses | Synchronous request/response | Add SSE endpoint in polish phase |
| LangGraph Cloud deployment | Local graph execution in FastAPI process | Extract to separate service later |
| Multiple approval levels | Single-level approval (one approver) | Add multi-step approval chain later |
| Conversation memory across sessions | Stateless per-run (thread = single run) | Add memory summarization later |
| Reranker model | No reranking, rely on embedding quality | Add cross-encoder reranker later |
| Frontend | API-only with Swagger UI for demo | Add React frontend in polish phase |

## File Structure (MVP)

```
MOCA/
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── alembic.ini
├── src/
│   ├── api/
│   │   ├── main.py              # FastAPI app factory
│   │   ├── deps.py              # Dependency injection (db, auth, graph)
│   │   ├── routers/
│   │   │   ├── agent.py         # POST /agent/runs
│   │   │   ├── approvals.py     # POST /approvals/{id}/approve
│   │   │   ├── audit.py         # GET /audit-logs
│   │   │   └── rag.py           # POST /rag/search (testing)
│   │   └── schemas/
│   │       ├── agent.py         # Request/response models
│   │       └── approval.py
│   ├── agent/
│   │   ├── graph.py             # Graph definition and compilation
│   │   ├── state.py             # AgentState TypedDict
│   │   ├── nodes/
│   │   │   ├── router.py
│   │   │   ├── retriever.py
│   │   │   ├── tool_caller.py
│   │   │   ├── reasoner.py
│   │   │   ├── risk_check.py
│   │   │   ├── approval.py
│   │   │   ├── executor.py
│   │   │   └── response.py
│   │   └── prompts/
│   │       ├── router.py        # Intent classification prompt
│   │       └── reasoner.py      # Evidence synthesis prompt
│   ├── tools/
│   │   ├── base.py              # Tool result schema, error handling
│   │   ├── order.py             # get_order
│   │   ├── refund.py            # get_refund_case
│   │   ├── ticket.py            # get_ticket
│   │   ├── coupon.py            # create_coupon_grant
│   │   └── notification.py      # send_notification
│   ├── rag/
│   │   ├── ingest.py            # LlamaIndex ingestion pipeline
│   │   ├── retrieve.py          # Online retrieval function
│   │   └── schemas.py           # Chunk, SearchResult models
│   ├── db/
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── session.py           # DB session factory
│   │   └── migrations/          # Alembic migrations
│   ├── auth/
│   │   ├── jwt.py               # Token encode/decode
│   │   └── permissions.py       # Scope and role checks
│   └── config.py                # Settings via pydantic-settings
├── scripts/
│   ├── seed_data.py             # Generate demo business data
│   └── ingest_kb.py             # Load knowledge base documents
├── knowledge_base/              # Source documents (markdown)
│   ├── refund_rules.md
│   ├── compensation_sop.md
│   └── ...
├── tests/
│   ├── conftest.py
│   ├── test_graph.py            # End-to-end graph tests
│   ├── test_tools.py
│   ├── test_rag.py
│   └── test_approval.py
└── eval/
    └── golden_set.yaml
```
