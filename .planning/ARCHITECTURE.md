# MOCA System Architecture

> **Design Contract** — This document is the single source of truth for implementation decisions.
> All other planning docs defer to this file when there's a conflict.

## MVP Scope Contract

| Decision | Conclusion | Rationale |
|----------|-----------|-----------|
| Frontend | Minimal shell in Phase 5 (chat + approval + step panel) | Demo needs visual impact, but backend must work first |
| SSE | Phase 5; Phase 3 uses synchronous response | Avoid premature complexity while learning LangGraph |
| Session memory | Same-thread context via LangGraph checkpointer; no cross-session | Checkpointer gives this for free; cross-session is v2 |
| Directory | `src/` | Single convention, no ambiguity |
| Approval mechanism | `interrupt()` only | Newer API, cleaner than `interrupt_before` |
| Multi-tenant | `tenant_id` in all tables; app-layer filtering in MVP | Fields ready for RLS upgrade; README states this explicitly |
| High concurrency | Not promised; architecture supports scale-out path | MVP targets demo load only |

## System Architecture (Converged)

```mermaid
flowchart LR
    U[商家运营 / 平台客服 / 审批人] --> FE[Web UI or Swagger]
    FE --> API[FastAPI API Layer]

    API --> AUTH[JWT / OAuth2 Scopes]
    API --> G[LangGraph Orchestrator]

    G --> T[Tool Layer]
    G --> R[RAG Service]
    G --> AP[Approval Gate]
    G --> AUD[Audit / Trace Writer]

    T --> REPO[Repository / Data Access]
    R --> REPO
    AP --> REPO
    AUD --> REPO

    REPO --> PG[(PostgreSQL 16 + pgvector)]
    API --> REDIS[(Redis 7 — Cache / Rate Limit)]

    R --> KB[Knowledge Base Ingestion<br/>LlamaIndex offline]
    KB --> PG

    G --> LLM[OpenAI-compatible Model]
    API --> OBS[Observability Hooks]
    G --> OBS
    AUD --> OBS
```

## LangGraph Execution Flow

```mermaid
graph TD
    START([User Question]) --> ROUTER

    ROUTER{Router Node<br/>LLM Intent Classification}
    ROUTER -->|query_only| RETRIEVER
    ROUTER -->|needs_tools| TOOL_CALLER
    ROUTER -->|needs_action| TOOL_CALLER

    TOOL_CALLER[Tool Caller<br/>get_order / get_refund / get_ticket]
    TOOL_CALLER --> RETRIEVER

    RETRIEVER[Retriever<br/>pgvector + Metadata Filter + Citation Validator]
    RETRIEVER --> REASONER

    REASONER{Reasoner<br/>LLM Evidence Synthesis}
    REASONER -->|no_action| RESPONSE
    REASONER -->|action_proposed| RISK_CHECK

    RISK_CHECK{Risk Check<br/>Rule-based — rules/risk_rules.yaml}
    RISK_CHECK -->|within_authority| EXECUTOR
    RISK_CHECK -->|needs_approval| APPROVAL_NODE

    APPROVAL_NODE[Approval Node<br/>interrupt&#40;&#41; — checkpoint to Postgres]
    APPROVAL_NODE -->|approved| EXECUTOR
    APPROVAL_NODE -->|rejected| RESPONSE

    EXECUTOR[Executor<br/>Write Tools + Rollback Info]
    EXECUTOR --> RESPONSE

    RESPONSE[Response Node<br/>Assemble Output + Write Audit]
    RESPONSE --> END_NODE([Return to User])

    style APPROVAL_NODE fill:#f9a825,stroke:#f57f17,color:#000
    style RISK_CHECK fill:#ffcc80,stroke:#ef6c00,color:#000
    style ROUTER fill:#81d4fa,stroke:#0277bd,color:#000
    style REASONER fill:#81d4fa,stroke:#0277bd,color:#000
```

## Data Flow — End to End

```mermaid
sequenceDiagram
    participant U as User / Frontend
    participant API as FastAPI
    participant G as LangGraph
    participant T as Tools
    participant REPO as Repository Layer
    participant R as RAG (pgvector)
    participant DB as PostgreSQL
    participant MGR as Approver

    U->>API: POST /api/v1/agent/runs {order_id, question}
    API->>API: JWT验证 + scope检查
    API->>DB: 创建 agent_run (run_id, trace_id)
    API->>G: invoke(initial_state, config)

    G->>G: Router: 意图分类
    G->>T: Tool Caller: get_order(order_id)
    T->>REPO: OrderRepository.get_by_id()
    REPO->>DB: SELECT with tenant_id filter
    DB-->>REPO: order record
    REPO-->>T: order data
    T-->>G: {status: ok, data: {...}}

    G->>R: Retriever: 检索退款规则
    R->>DB: pgvector cosine similarity + metadata filter
    DB-->>R: top-5 chunks
    R->>R: Citation Validator: verify doc_ids exist
    R-->>G: evidence[{doc_id, chunk_id, text, score}]

    G->>G: Reasoner: 综合证据生成回答

    alt Low Risk (query only)
        G-->>API: {answer, evidence[], tool_calls[]}
        API-->>U: 200 OK
    end

    alt High Risk (needs approval)
        G->>G: Risk Check: exceeds threshold (rules/risk_rules.yaml)
        G->>REPO: ApprovalRepository.create()
        REPO->>DB: INSERT approval_request
        G->>DB: Checkpoint state (PostgresSaver)
        G-->>API: {status: waiting_approval, approval_request_id}
        API-->>U: 202 Accepted

        MGR->>API: POST /approvals/{id}/approve
        API->>REPO: ApprovalRepository.update(approved)
        API->>G: Command(resume={approved: true})
        G->>T: Executor: create_coupon_grant_draft
        T->>REPO: CouponRepository.create_draft()
        REPO->>DB: INSERT with idempotency_key
        G->>DB: Write audit_logs
        G-->>API: {answer, evidence[], actions[], audit_url}
        API-->>U: 200 OK
    end

    alt No Evidence
        G->>G: Retriever: confidence below threshold
        G->>G: Reasoner: refuse to generate conclusion
        G-->>API: {status: no_evidence, missing_info: [...]}
        API-->>U: 200 OK (graceful degradation)
    end
```

## Database Schema

```mermaid
erDiagram
    tenants ||--o{ merchants : has
    tenants ||--o{ users : has
    users ||--o{ user_roles : has
    roles ||--o{ user_roles : has

    merchants ||--o{ orders : places
    orders ||--o{ refund_cases : has
    orders ||--o{ tickets : has

    tenants ||--o{ policy_documents : owns
    policy_documents ||--o{ policy_chunks : contains

    agent_runs ||--o{ agent_steps : contains
    agent_runs ||--o{ approval_requests : triggers
    approval_requests ||--o{ approval_steps : has
    agent_runs ||--o{ audit_logs : produces
    agent_runs ||--o{ llm_usage_events : tracks

    tenants {
        uuid id PK
        string name
        string status
    }
    merchants {
        uuid id PK
        uuid tenant_id FK
        string merchant_name
        string category
        string risk_level
    }
    orders {
        uuid id PK
        uuid tenant_id FK
        uuid merchant_id FK
        string order_no
        decimal amount
        string status
        timestamp created_at
        timestamp delivered_at
    }
    refund_cases {
        uuid id PK
        uuid tenant_id FK
        uuid order_id FK
        string reason_code
        string status
        decimal requested_amount
        timestamp created_at
    }
    tickets {
        uuid id PK
        uuid tenant_id FK
        uuid order_id FK
        uuid refund_case_id FK
        string channel
        string status
        text summary
        timestamp created_at
    }
    policy_documents {
        uuid id PK
        uuid tenant_id FK
        string doc_type
        string title
        date effective_date
        string risk_level
        int version
    }
    policy_chunks {
        uuid id PK
        uuid tenant_id FK
        uuid doc_id FK
        string chunk_id
        string section
        text content
        string risk_level
        date effective_date
        vector embedding
    }
    agent_runs {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        string scene
        string status
        string trace_id
        timestamp started_at
        timestamp ended_at
    }
    agent_steps {
        uuid id PK
        uuid run_id FK
        string node_name
        string status
        int duration_ms
        jsonb input_json
        jsonb output_json
    }
    approval_requests {
        uuid id PK
        uuid run_id FK
        string action_type
        string risk_level
        string status
        string approver_role
        timestamp created_at
    }
    approval_steps {
        uuid id PK
        uuid approval_request_id FK
        uuid approver_id FK
        string decision
        text comment
        timestamp created_at
    }
    audit_logs {
        uuid id PK
        uuid run_id FK
        string event_type
        jsonb payload_json
        timestamp created_at
    }
    llm_usage_events {
        uuid id PK
        uuid run_id FK
        string model
        int prompt_tokens
        int completion_tokens
        decimal cost
        int latency_ms
    }
```

## State Enumerations

| Table | Field | Allowed Values | Notes |
|-------|-------|---------------|-------|
| orders | status | `pending`, `paid`, `shipped`, `delivered`, `completed`, `cancelled`, `refunding` | `refunding` = refund in progress |
| refund_cases | status | `submitted`, `reviewing`, `approved`, `rejected`, `refunded`, `closed` | Terminal: `refunded`, `rejected`, `closed` |
| tickets | status | `open`, `in_progress`, `resolved`, `closed` | |
| approval_requests | status | `pending`, `approved`, `rejected`, `expired` | `expired` = timed out without decision |
| agent_runs | status | `running`, `waiting_approval`, `completed`, `failed`, `timeout` | |
| agent_steps | status | `running`, `completed`, `failed`, `skipped` | |
| tenants | status | `active`, `suspended` | |
| merchants | risk_level | `low`, `medium`, `high` | Affects approval threshold |
| policy_documents | doc_type | `refund_rule`, `compensation_sop`, `appeal_process`, `coupon_rule`, `high_risk_list` | |
| policy_documents | risk_level | `low`, `medium`, `high` | Indicates sensitivity of the rule |

**Amount precision:** All monetary fields use `DECIMAL(12,2)`, CNY assumed. Approval threshold defined in `rules/risk_rules.yaml`.

**Approval timeout:** Default 24h; configurable per action_type in `rules/risk_rules.yaml`. Expired approvals do not auto-resume — they require re-submission.

## Directory Structure (Converged)

```mermaid
graph LR
    subgraph "MOCA/"
        DC[docker-compose.yml]
        PP[pyproject.toml]
        ENV[.env.example]
        MK[Makefile]
        RM[README.md]
    end

    subgraph "src/"
        API[api/]
        AGENT[agent/]
        TOOLS[tools/]
        RAG_DIR[rag/]
        DB_DIR[db/]
        AUTH_DIR[auth/]
        REPOS[repositories/]
        OBS_DIR[observability/]
        RULES[rules/]
        CFG[config.py]
    end

    subgraph "Other"
        SCRIPTS[scripts/]
        KB[knowledge_base/]
        TESTS[tests/]
        EVAL_DIR[eval/]
        DOCS[docs/]
    end
```

```text
MOCA/
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── alembic.ini
│
├── src/
│   ├── api/
│   │   ├── main.py                 # FastAPI app factory
│   │   ├── deps.py                 # DI: db session, auth, graph runner
│   │   ├── routers/
│   │   │   ├── agent.py            # POST /agent/runs
│   │   │   ├── approvals.py        # POST /approvals/{id}/approve|reject
│   │   │   ├── audit.py            # GET /audit-logs?run_id=
│   │   │   └── rag.py              # POST /rag/search (dev/test)
│   │   └── schemas/
│   │       ├── agent.py
│   │       └── approval.py
│   │
│   ├── agent/
│   │   ├── graph.py                # Graph definition + compilation
│   │   ├── state.py                # AgentState TypedDict
│   │   ├── nodes/
│   │   │   ├── router.py
│   │   │   ├── retriever.py
│   │   │   ├── tool_caller.py
│   │   │   ├── reasoner.py
│   │   │   ├── risk_check.py
│   │   │   ├── approval.py         # Uses interrupt() only
│   │   │   ├── executor.py
│   │   │   └── response.py
│   │   └── prompts/
│   │       ├── router.py
│   │       └── reasoner.py
│   │
│   ├── tools/
│   │   ├── base.py                 # ToolResult schema, error handling
│   │   ├── order.py
│   │   ├── refund.py
│   │   ├── ticket.py
│   │   ├── coupon.py
│   │   └── approval_tool.py
│   │
│   ├── repositories/               # Data access layer (tools -> repos -> db)
│   │   ├── base.py
│   │   ├── order_repo.py
│   │   ├── refund_repo.py
│   │   ├── ticket_repo.py
│   │   ├── approval_repo.py
│   │   └── audit_repo.py
│   │
│   ├── rag/
│   │   ├── ingest.py               # LlamaIndex offline pipeline
│   │   ├── retrieve.py             # Online: pgvector SQL via SQLAlchemy
│   │   ├── citation_validator.py   # Verify cited doc_ids exist in results
│   │   └── schemas.py
│   │
│   ├── db/
│   │   ├── models.py               # SQLAlchemy 2.0 async models
│   │   ├── session.py              # async engine + session factory
│   │   └── migrations/             # Alembic
│   │
│   ├── auth/
│   │   ├── jwt.py
│   │   └── permissions.py
│   │
│   ├── observability/              # Trace ID, metrics, logging hooks
│   │   ├── trace.py                # run_id / trace_id / step_id generation
│   │   ├── metrics.py              # latency, token, cost recording
│   │   └── audit_callback.py       # LangGraph callback for audit
│   │
│   ├── rules/                      # Externalized configuration
│   │   ├── risk_rules.yaml         # Thresholds per action type
│   │   └── permission_matrix.yaml  # Role -> scope mappings
│   │
│   └── config.py                   # pydantic-settings
│
├── scripts/
│   ├── seed_data.py
│   └── ingest_kb.py
│
├── knowledge_base/                 # Chinese policy documents (markdown)
│   ├── refund_rules.md
│   ├── compensation_sop.md
│   ├── merchant_faq.md
│   └── ...
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── conftest.py
│
├── eval/
│   ├── golden_set.yaml
│   └── reports/
│
└── docs/
    ├── architecture.md             # This file (symlink or copy)
    ├── adr/                        # Architecture Decision Records
    │   └── 001-single-graph.md
    └── demo-script.md              # 10-minute demo walkthrough
```

## Extensibility Architecture

```mermaid
flowchart TD
    A[FastAPI] --> B[LangGraph]
    B --> C[Tool Adapter]
    C --> D[Repository Layer]
    D --> E[(Postgres)]

    B --> F[RAG Retrieval]
    F --> D

    B --> G[Approval Gate]
    G --> D

    B --> AUD[Audit Callback]
    AUD --> D

    H[Future: Worker / Event Bus] -. v2 .-> D
    H -. v2 .-> G
    H -. v2 .-> I[Webhook / Notifications]

    J[Future: OTel Collector] -. v2 .-> K[Prometheus / Grafana]
    AUD -. v2 .-> J
```

## Deployment (MVP)

```mermaid
graph TB
    subgraph "docker-compose.yml"
        PG[postgres:16<br/>+ pgvector extension<br/>:5432]
        REDIS[redis:7-alpine<br/>:6379]
        API[api<br/>FastAPI + Uvicorn<br/>:8000]
        FE[frontend<br/>Next.js<br/>:3000<br/>Phase 5]
    end

    API -->|asyncpg| PG
    API -->|redis-py| REDIS
    FE -.->|HTTP| API

    subgraph "Healthchecks"
        H1[pg_isready -U moca]
        H2[redis-cli ping]
        H3[curl localhost:8000/health]
    end

    PG --- H1
    REDIS --- H2
    API --- H3

    API -->|depends_on: pg healthy, redis healthy| PG
    API -->|depends_on: redis healthy| REDIS
```

## Implementation Timeline (Converged — 6 weeks)

```mermaid
timeline
    title MOCA Implementation Timeline
    Week 1 : Foundation
            : Docker Compose + DB schema + FastAPI skeleton
            : JWT auth + seed data + 3 read tool endpoints
            : Repository layer + healthchecks + .gitignore + README
    Week 2 : RAG Pipeline
            : Knowledge docs (15-30 Chinese) + LlamaIndex ingestion
            : pgvector HNSW + retrieval endpoint + citation validator
            : Golden set (10 queries) + no-evidence fallback
    Week 3 : LangGraph Core
            : AgentState + 6 nodes (no approval yet)
            : Tool wrappers + evidence accumulation + reasoner
            : Audit callback + run_id/trace_id + synchronous endpoint
    Week 4 : Approval + Audit
            : risk_check node + rules/risk_rules.yaml
            : approval node with interrupt() + resume API
            : Executor + audit enrichment + error scenarios
    Week 5 : Frontend + SSE
            : Minimal Next.js chat page + approval page + step panel
            : SSE or polling for progressive updates
            : Timeout/retry/graceful degradation
    Week 6 : Evaluation + Polish
            : Full golden set (25-40 cases) + automated scoring
            : README + demo script + recording
            : CI lint + unit tests + integration smoke
```

## Key Design Patterns

| Pattern | Description | Location |
|---------|-------------|----------|
| Tool as Thin Wrapper | validate → repo call → structured result (never raise) | `src/tools/` |
| Repository Layer | tools → repos → db; enables testing and future swap | `src/repositories/` |
| Evidence Accumulation | State collects evidence from tools + RAG; reasoner cites all | `agent/state.py` |
| Citation Validator | Post-process LLM output; verify cited IDs exist in retrieval | `src/rag/citation_validator.py` |
| Interrupt-Resume | `interrupt()` in approval node; resume via API + Command | `agent/nodes/approval.py` |
| Audit as Callback | LangGraph callback handler, not inline in nodes | `src/observability/audit_callback.py` |
| Layered Auth | API-level (JWT scopes) + Tool-level (tenant/role check) | `src/auth/` + tools |
| Configurable Rules | Risk thresholds in YAML, loaded at startup | `src/rules/risk_rules.yaml` |
| Graceful Degradation | LLM timeout → fallback; no evidence → refuse; tool error → structured error | All layers |
| Idempotent Writes | All write tools accept `idempotency_key` | `src/tools/` + `src/repositories/` |

---

*Architecture converged: 2026-05-09*
*This document resolves all prior conflicts between PROJECT.md, REQUIREMENTS.md, and research/ARCHITECTURE.md.*
