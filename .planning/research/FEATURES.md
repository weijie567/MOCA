# Features Research: MOCA

## Table Stakes
Features that must exist or the project looks like a demo/toy.

### Structured Tool Calls for Business Data Retrieval
- **What**: Agent calls typed tools (get_order, get_refund, get_ticket) that return structured JSON from the database, not free-text hallucinations.
- **Why table stakes**: Any interviewer will immediately ask "how does it get real data?" If the agent only generates text without grounding in actual records, it's indistinguishable from a prompt wrapper. Structured tool calls prove the agent operates on real systems.
- **Complexity**: Medium
- **Dependencies**: Database schema with orders/refunds/tickets; FastAPI endpoints or direct DB access layer; LangGraph tool node definition.

### Evidence-Cited Answers (RAG with Source Attribution)
- **What**: Every factual claim in the agent's response links back to a specific knowledge base document (rule ID, SOP section) or data record (order number, refund ID).
- **Why table stakes**: Citation is what separates "AI that helps" from "AI that hallucinates." In regulated e-commerce operations, unsourced answers are useless. Interviewers at Alibaba/Meituan will expect this because their internal systems already do it.
- **Complexity**: Medium
- **Dependencies**: pgvector knowledge base with chunk-level metadata; retrieval chain that returns source references; response formatting that renders citations.

### Human-in-the-Loop Approval Workflow
- **What**: When the agent determines an action is high-risk (compensation above threshold, refund override), it pauses execution, creates an approval request, and only resumes after a human approves or rejects.
- **Why table stakes**: This is the project's core differentiator claim. Without it actually working end-to-end (interrupt → persist state → resume), the project fails to deliver on its own premise.
- **Complexity**: High
- **Dependencies**: LangGraph interrupt/resume mechanism; persistent state (checkpointer); approval state machine; notification to reviewer; resume logic that picks up where it left off.

### Audit Trail
- **What**: Every agent run logs: user input, tools called with arguments, retrieved evidence, LLM reasoning steps, approval decisions, final output. Stored in a queryable format.
- **Why table stakes**: Enterprise agents without audit trails are toys. This is the minimum bar for any system that touches financial operations. Interviewers will ask "how do you debug a bad decision?" and "how do you prove compliance?"
- **Complexity**: Medium
- **Dependencies**: Structured logging schema; write-on-every-step middleware in the graph; query API to retrieve run history.

### Docker Compose One-Command Startup
- **What**: `docker compose up` brings up the entire system (API, DB, Redis, frontend) with seed data, ready for demo in under 2 minutes.
- **Why table stakes**: If the interviewer can't run it, it doesn't exist. Every portfolio project that requires 15 manual setup steps gets abandoned during review.
- **Complexity**: Medium
- **Dependencies**: Dockerfiles for each service; compose file with health checks and dependency ordering; seed script that runs on first boot; environment variable defaults that work out of the box.

### Realistic Demo Data (Chinese Business Context)
- **What**: Seed script populates orders, merchants, refund cases, knowledge base documents with realistic Chinese e-commerce data (product names, merchant names, refund reasons, platform rules).
- **Why table stakes**: Empty databases or "John Doe bought Widget A" data signals the candidate doesn't understand the domain. Chinese internet company interviewers expect to see familiar patterns (Taobao-style order flows, Meituan-style dispute categories).
- **Complexity**: Low
- **Dependencies**: Database schema must be finalized first; knowledge base documents (markdown/PDF) for rules and SOPs.

### Conversation Memory (Within Session)
- **What**: Agent maintains context within a conversation session. User can ask follow-up questions ("what about the other order?") without re-stating everything.
- **Why table stakes**: Without session memory, every interaction is isolated and the UX feels broken. LangGraph's built-in memory makes this straightforward.
- **Complexity**: Low
- **Dependencies**: LangGraph checkpointer (already needed for approval workflow); session ID management in API layer.

### Basic Role-Based Access Control
- **What**: Different roles (merchant, support_agent, reviewer, manager) see different data and can perform different actions. Merchants can't approve their own refunds. Only managers can override thresholds.
- **Why table stakes**: Any enterprise system without access control is a prototype. For a PM-angle portfolio piece, permission modeling is expected.
- **Complexity**: Medium
- **Dependencies**: User/role table; FastAPI OAuth2 scopes or dependency-based guards; LangGraph conditional edges that check permissions before tool execution.

## Differentiators
Features that make this project stand out in interviews.

### Graph Visualization of Agent Execution
- **What**: Visual representation (in frontend or exportable) showing the actual LangGraph execution path: which nodes fired, what tools were called, where approval interrupted, how it resumed. Not a static diagram — reflects the actual run.
- **Why differentiating**: Most portfolio projects show input/output. Showing the execution graph proves you understand the internals and makes the system debuggable. Interviewers can see the state machine in action.
- **Complexity**: Medium
- **Dependencies**: LangGraph execution trace export; frontend component to render DAG; mapping from trace events to visual nodes.

### Evaluation Framework with Automated Test Cases
- **What**: A suite of test scenarios (happy path refund, edge case denial, threshold boundary, multi-step approval) that run the agent end-to-end and score outputs on correctness, citation accuracy, and appropriate tool usage.
- **Why differentiating**: Shows engineering maturity beyond "it works in demo." Proves the candidate thinks about reliability, regression, and continuous improvement. Very few portfolio projects include eval frameworks.
- **Complexity**: Medium-High
- **Dependencies**: Test scenario definitions (input + expected behavior); scoring functions; CI-compatible runner; baseline results to compare against.

### Structured Reasoning Trace (Chain-of-Thought Logging)
- **What**: Agent's internal reasoning (why it chose to escalate, why it selected this rule over that one) is captured as structured data, not just raw LLM output. Stored alongside the audit trail.
- **Why differentiating**: Demonstrates understanding of agent observability and explainability. When an interviewer asks "why did it make this decision?", you can show the exact reasoning chain, not just the final answer.
- **Complexity**: Low-Medium
- **Dependencies**: Prompt engineering to elicit structured reasoning; parsing layer to extract reasoning steps; storage in audit schema.

### Approval Workflow with Escalation Tiers
- **What**: Not just binary approve/reject. Multiple tiers: auto-approve (low risk), single reviewer (medium risk), manager escalation (high risk), with configurable thresholds. Timeout handling if reviewer doesn't respond.
- **Why differentiating**: Shows product thinking beyond basic implementation. Demonstrates understanding of real operational workflows where not everything needs the same level of scrutiny.
- **Complexity**: Medium
- **Dependencies**: Risk scoring logic; tier configuration; timeout mechanism (could be simple polling or Redis TTL); escalation state transitions in the graph.

### OpenTelemetry Tracing with Span Correlation
- **What**: Every agent run produces OTel traces with proper span hierarchy: top-level run → LLM call → tool execution → DB query. Traces are viewable in Jaeger or similar.
- **Complexity**: Medium
- **Why differentiating**: Proves production engineering mindset. Most AI projects have zero observability. Being able to show latency breakdown, error rates, and trace correlation in a demo is impressive.
- **Dependencies**: OTel SDK integration in FastAPI and LangGraph; Jaeger container in Docker Compose; span context propagation through async boundaries.

### Configurable Business Rules Engine
- **What**: Refund thresholds, approval tiers, auto-approve conditions are defined in a configuration layer (YAML or DB table), not hardcoded. Agent reads rules dynamically.
- **Why differentiating**: Shows the system is adaptable without code changes. Demonstrates understanding that business rules change frequently in e-commerce operations.
- **Complexity**: Low-Medium
- **Dependencies**: Rules schema definition; loader that the agent consults; admin UI or API to modify rules (optional for MVP, but the architecture should support it).

### Streaming Responses with Progressive Disclosure
- **What**: Agent streams its response token-by-token to the frontend, and progressively reveals: "Retrieving order data..." → "Found 2 relevant rules..." → "Recommendation: ..." rather than blocking until complete.
- **Why differentiating**: Shows attention to UX and real-world latency management. LLM calls take seconds; streaming makes the system feel responsive. Demonstrates SSE/WebSocket competence.
- **Complexity**: Medium
- **Dependencies**: FastAPI streaming response (SSE); LangGraph streaming callbacks; frontend that renders progressive updates.

## Anti-Features (Do NOT Build)
Things to explicitly exclude from MVP.

### Multi-Agent Architecture
- **What it is**: Multiple specialized agents (refund agent, knowledge agent, approval agent) communicating via message passing or shared state.
- **Why exclude**: Adds massive complexity with no demo benefit. A single LangGraph with well-defined nodes achieves the same outcome and is far easier to debug, explain, and demonstrate. Multi-agent is a buzzword that impresses less than a well-executed single graph.
- **When to add**: Never for this project scope. Only if adding a genuinely independent scenario (e.g., creator appeals) that can't share state with refund flow.

### Real Payment/Refund Execution
- **What it is**: Actually processing refunds through payment gateways or modifying real financial records.
- **Why exclude**: Massive liability, compliance burden, and zero interview value. Simulated execution with clear "this would execute X" messaging is sufficient and safer.
- **When to add**: Never. This is a demo system.

### Natural Language Rule Authoring
- **What it is**: Letting users define business rules in natural language that the system interprets and enforces.
- **Why exclude**: Extremely hard to make reliable. Rule interpretation ambiguity creates more problems than it solves. Structured rule configuration is more trustworthy and demonstrable.
- **When to add**: Polish phase at earliest, and only if the structured rules engine is solid.

### Multi-Language / i18n Support
- **What it is**: Full internationalization of the interface and agent responses.
- **Why exclude**: The demo targets Chinese internet companies with Chinese data. English README is sufficient for GitHub visibility. Building i18n infrastructure is pure overhead for MVP.
- **When to add**: Polish phase if targeting international companies.

### Custom Model Fine-Tuning
- **What it is**: Fine-tuning a model specifically for merchant operations tasks.
- **Why exclude**: Requires training data, compute budget, and evaluation infrastructure that dwarfs the rest of the project. Prompt engineering + RAG achieves 90% of the benefit for a demo.
- **When to add**: Never for portfolio. Mention as "production enhancement" in documentation.

### Real-Time Notifications (Push)
- **What it is**: WebSocket push notifications when approval requests arrive, when status changes, etc.
- **Why exclude**: Polling or manual refresh is sufficient for a demo with one user. Push notification infrastructure (WebSocket management, connection state, reconnection) adds complexity without demo impact.
- **When to add**: Polish phase, and only if the demo flow feels broken without it.

### Analytics Dashboard
- **What it is**: Charts showing refund trends, agent accuracy over time, approval turnaround metrics.
- **Why exclude**: Requires meaningful historical data that a demo won't have. Static seed data makes dashboards look fake. The evaluation framework serves the "metrics" angle better.
- **When to add**: Polish phase with synthetic historical data generation.

### MCP (Model Context Protocol) Layer
- **What it is**: Exposing tools via Anthropic's MCP protocol for interoperability with other AI systems.
- **Why exclude**: Adds an abstraction layer that doesn't improve the demo. The interviewer cares about the agent working correctly, not protocol compatibility. MCP is still early-stage and adds learning burden.
- **When to add**: Polish phase if targeting Anthropic-ecosystem roles specifically.

### Kubernetes / Production Deployment
- **What it is**: Helm charts, K8s manifests, production-grade infrastructure.
- **Why exclude**: Docker Compose is the right abstraction for "run it locally in 2 minutes." K8s signals over-engineering for a demo and makes it harder for interviewers to run.
- **When to add**: Only if deploying a live demo instance (could use a simple cloud VM with Docker Compose instead).

## Feature Dependencies

Build order (critical path):

```
Layer 0 — Foundation (no agent logic yet):
├── Database schema (orders, refunds, tickets, users, roles)
├── Docker Compose skeleton (Postgres, Redis, API shell)
├── Seed data script
└── FastAPI project structure with auth

Layer 1 — Core Agent (minimal viable agent):
├── LangGraph graph definition (single node: LLM + tools)
├── Tool implementations (get_order, get_refund, get_ticket)
├── Basic conversation endpoint (POST /chat)
└── Session memory via LangGraph checkpointer
    └── Depends on: Layer 0

Layer 2 — Knowledge & Citations:
├── Knowledge base ingestion (rules/SOPs → pgvector)
├── Retrieval tool (search_knowledge_base)
├── Citation formatting in responses
└── Depends on: Layer 1

Layer 3 — Approval Workflow:
├── Risk assessment logic (threshold detection)
├── Approval interrupt node in graph
├── Approval state persistence
├── Resume-after-approval logic
├── Reviewer notification (API-based, not push)
└── Depends on: Layer 1, Layer 0 (roles)

Layer 4 — Audit & Observability:
├── Audit trail middleware (logs every step)
├── Audit query API
├── OTel tracing integration
└── Depends on: Layer 1, Layer 3

Layer 5 — Frontend:
├── Chat interface
├── Approval queue view (for reviewers)
├── Audit log viewer
├── Role-based UI routing
└── Depends on: Layers 1-4 (API contracts)

Layer 6 — Evaluation & Polish:
├── Eval test suite
├── Graph visualization
├── Streaming responses
├── Escalation tiers
└── Depends on: Layers 1-5 stable
```

### Key Dependency Insights

1. **Approval workflow depends on checkpointer** — the same persistence mechanism that enables conversation memory also enables interrupt/resume. Build memory first, approval second.

2. **Citations depend on retrieval quality** — invest in chunking strategy and metadata before building the citation UI. Bad retrieval makes citations useless.

3. **Audit trail should be built INTO the graph, not bolted on** — adding audit logging after the graph is built requires touching every node. Design the middleware pattern in Layer 1 even if you don't persist until Layer 4.

4. **Frontend is last but API contracts are early** — define OpenAPI schemas in Layer 1 so frontend work can parallelize later. Don't let frontend drive API design.

5. **Eval framework validates everything else** — it's listed last but should be started in Layer 2 (simple happy-path tests) and grown incrementally. Don't wait until "everything works" to start testing.
