# Phase 3: LangGraph Core — Research

**Researched:** 2026-05-11
**Phase Goal:** Submit a refund question and receive an evidence-cited answer with full execution trace, tool calls, and same-thread memory.

---

## 1. Existing Codebase Assets (Reusable)

### RAG Layer (`src/rag/`)
- **`Retriever.search(query, tenant_id, top_k, doc_type, risk_level)`** → `RetrievalResult`
  - Returns `retrieval_status`: `"strong_evidence"` | `"partial_evidence"` | `"no_evidence"`
  - Returns `evidence: list[EvidenceItem]` with `doc_key`, `chunk_id`, `title`, `section`, `score`, `text`
  - Returns `fallback_message` when no evidence
  - Thresholds: `STRONG_EVIDENCE_THRESHOLD = 0.70`, `MIN_SIMILARITY_THRESHOLD = 0.55`
- **`validate_citations(cited_chunk_ids, retrieval_result)`** → `CitationValidation`
  - Checks all cited chunk_ids exist in retrieval results
  - Returns `is_valid`, `invalid_citations`, `reason`
- **`EvidenceItem`** / **`RetrievalResult`** / **`CitationValidation`** — Pydantic schemas ready to use

### Repositories (`src/repositories/`)
- **`BaseRepository[T]`**: `get_by_id(id, tenant_id)`, `list_all(tenant_id, **filters)` — all tenant-scoped
- **`OrderRepository`**: `get_by_order_no(order_no, tenant_id)`, `get_with_hints(order_no, tenant_id)` — returns order + relation hints (active refund, open ticket)
- **`RefundRepository`**: `get_by_case_no(refund_case_no, tenant_id)`
- **`TicketRepository`**: inherits `BaseRepository[Ticket]` (get_by_id works)
- All repos take `AsyncSession` in constructor

### Auth (`src/auth/`)
- **`get_current_user(security_scopes, token, session)`** — extracts user from JWT, validates scopes
- **`require_roles(allowed_roles)`** — role-based access control decorator
- Existing scopes: `orders:read`, `refunds:read`, `tickets:read`, `knowledge:read`, `approvals:review`
- **Need to add:** `agent:chat` scope for the agent endpoint

### Config (`src/config.py`)
- `Settings` via pydantic-settings, loads from `.env`
- Already has `embedding_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"`
- **Need to add:** `dashscope_api_key`, `llm_model`, `llm_temperature`, `llm_max_tokens`, `llm_timeout_seconds`

### API (`src/api/`)
- `deps.py` provides `get_session`, `get_trace_id`, `get_run_id`
- Existing routers: auth, orders, refund_cases, search, tickets
- **Need to add:** `src/api/routers/agent.py`

### DB Models (`src/db/models.py`)
- Full schema: Tenant, User, Role, UserRole, Merchant, Order, RefundCase, Ticket, PolicyDocument, PolicyChunk, AuditLog
- Pattern: UUID PK, `tenant_id` FK, `TimestampMixin`
- `AuditLog` exists with `run_id`, `trace_id`, `tool_call_id` — but agent trace needs separate `AgentRun`/`AgentStep` tables per D-05
- **Need to add:** `AgentRun`, `AgentStep` models

---

## 2. New Dependencies Required

```toml
# Add to pyproject.toml dependencies
"langgraph>=0.4",
"langgraph-checkpoint-postgres>=2.0",
"langchain-openai>=0.3",
"langchain-core>=0.3",
"psycopg[binary,pool]>=3.1",
```

### Connection String Divergence
- SQLAlchemy uses: `postgresql+asyncpg://moca:moca_dev@localhost:5432/moca`
- PostgresSaver needs: `postgresql://moca:moca_dev@localhost:5432/moca` (psycopg driver)
- Solution: add `checkpointer_database_url` to Settings, or derive from `database_url` by stripping `+asyncpg`

---

## 3. AgentRun / AgentStep Schema (from D-05)

```python
class AgentRun(TimestampMixin, Base):
    __tablename__ = "agent_runs"
    id: UUID PK
    thread_id: str (indexed)
    tenant_id: UUID FK → tenants
    user_id: UUID FK → users
    input_query: Text
    final_status: str  # "completed" | "error" | "insufficient_evidence"
    final_response: Text | None
    started_at: DateTime
    completed_at: DateTime | None
    total_latency_ms: int | None
    total_tokens: int | None
    total_cost: Decimal | None
    error_summary: str | None

class AgentStep(TimestampMixin, Base):
    __tablename__ = "agent_steps"
    id: UUID PK
    run_id: UUID FK → agent_runs
    node_name: str
    step_index: int
    status: str  # "completed" | "error" | "skipped"
    input_summary: JSONB | None
    output_summary: JSONB | None
    tool_name: str | None
    tool_input_summary: JSONB | None
    tool_output_summary: JSONB | None
    model_name: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    evidence_refs: JSONB | None  # list of {doc_key, chunk_id}
    error_message: str | None
    started_at: DateTime
    completed_at: DateTime | None
```

---

## 4. Integration Architecture

### Graph Lifecycle in FastAPI
```
FastAPI lifespan:
  → AsyncPostgresSaver.from_conn_string(checkpointer_url)
  → checkpointer.setup()  (once at startup)
  → compile graph with checkpointer
  → store graph in app.state

POST /api/v1/agent/chat:
  → get_current_user (auth)
  → get_session (for repos + trace writing)
  → graph.ainvoke(input, config={"configurable": {"thread_id": ...}})
  → write AgentRun + AgentSteps to DB
  → return response + trace_summary
```

### Tool Wiring
Tools are NOT LangChain tools. They are plain async functions called deterministically inside nodes:
- `load_business_context` node → calls `get_order`, `get_refund_case`, `get_ticket` directly
- `retrieve_policy_evidence` node → calls `Retriever.search()` directly
- Each tool wrapper: accepts `(id, tenant_id, user_id, role, session)`, returns D-08d format

### Trace Recording
Two options:
1. **LangGraph callback** — attach a custom callback that writes `AgentStep` rows after each node
2. **In-node recording** — each node appends to `state["trace_steps"]`, then a post-graph hook writes all steps

Option 2 is simpler for Phase 3 (no callback API complexity). The `receive_request` node creates the `AgentRun` row, each node appends to `trace_steps`, and a post-invoke function writes all `AgentStep` rows.

---

## 5. Key Technical Decisions

### GLM-5.1 Structured Output Compatibility
- DashScope OpenAI-compatible endpoint supports `response_format: {"type": "json_object"}`
- `langchain-openai` `ChatOpenAI.with_structured_output()` uses this under the hood
- **Risk:** GLM-5.1 may not perfectly follow JSON schema constraints. Mitigation: Pydantic validation + retry with error feedback (already in AI-SPEC 4b.1)
- **Fallback:** prompt-based JSON extraction + `json.loads()` + `model_validate()`

### PostgresSaver Checkpoint Tables
- `checkpointer.setup()` creates `langgraph_checkpoints` and `langgraph_checkpoint_writes` tables automatically
- These are separate from our `agent_runs`/`agent_steps` tables
- No Alembic migration needed for checkpoint tables — LangGraph manages them

### Ephemeral State Reset Pattern
- `receive_request` node must explicitly set all ephemeral fields to None/empty
- This prevents cross-turn contamination (failure mode 2 from AI-SPEC)
- The checkpointer saves everything, but ephemeral fields are overwritten immediately

---

## 6. Testing Strategy

### Fake LLM for CI (D-11b)
```python
class FakeLLM:
    """Returns predetermined structured outputs based on input patterns."""
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses

    async def ainvoke(self, messages, **kwargs):
        # Match input pattern → return predetermined response
        ...
```

### In-Memory Checkpointer for Unit Tests
- `langgraph` provides `MemorySaver` — use for unit tests instead of PostgresSaver
- No DB needed for per-node tests

### Integration Test Structure
- Use real PostgresSaver against test DB
- Seed test data (order, refund_case, policy chunks)
- Assert: final_response exists, intent correct, tools called, evidence_refs present, agent_runs/agent_steps written

---

## 7. Risk & Unknowns

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| GLM-5.1 `with_structured_output` fails silently | Medium | Test in isolation first; implement JSON fallback path |
| PostgresSaver checkpoint size grows with state | Low | D-07c already limits persistent state to refs only |
| DashScope rate limits during concurrent requests | Low | Phase 3 is internal tool, low volume; add retry with backoff later |
| `langgraph-checkpoint-postgres` version incompatibility | Low | Pin version; test setup() on fresh DB |

---

## 8. Implementation Order (Suggested)

1. **Dependencies + Config** — add packages, extend Settings
2. **DB Migration** — AgentRun + AgentStep tables
3. **Agent State + Schemas** — TypedDict, Pydantic output models
4. **Tools** — get_order, get_refund_case, get_ticket, search_policy wrappers
5. **Nodes** — implement 8 nodes one by one (receive → classify → extract → load → retrieve → recommend → risk → final)
6. **Graph Assembly** — StateGraph + edges + checkpointer
7. **Trace Recording** — post-invoke write to agent_runs/agent_steps
8. **API Endpoint** — POST /api/v1/agent/chat
9. **Tests** — per-node unit tests, graph integration test, failure path tests

---

## RESEARCH COMPLETE
