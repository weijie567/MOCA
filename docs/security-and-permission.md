# MOCA Security and Permission Model

## Authentication

MOCA uses JWT access tokens issued through the OAuth2 password flow:

```bash
curl -s -X POST "$BASE_URL/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=cs_zhang&password=moca2024"
```

The token payload includes user ID, username, role, tenant ID, expiration, and derived scopes. `src/auth/jwt.py` maps roles to scopes, and `src/auth/permissions.py` validates tokens on protected endpoints.

## Role-Based Access Control

| Role | Scopes | Description |
| --- | --- | --- |
| `admin` | `orders:read`, `refunds:read`, `tickets:read`, `knowledge:read`, `agent:chat`, `approvals:review`, `seed:write`, `admin:debug` | Full administrative demo role |
| `support` | `orders:read`, `refunds:read`, `tickets:read`, `knowledge:read`, `agent:chat` | Support agent role used by `cs_zhang`; can ask questions but cannot approve |
| `manager` | `orders:read`, `refunds:read`, `tickets:read`, `knowledge:read`, `agent:chat`, `approvals:review` | Reviewer role used by `mgr_li`; can decide approvals |
| `merchant` | `orders:read`, `refunds:read`, `tickets:read`, `knowledge:read`, `agent:chat` | Merchant-facing demo role |

FastAPI `Security(...)` dependencies enforce scopes at the endpoint boundary. Missing scopes return 403 with a `missing_scopes` detail. Approval decisions also require an allowed role, not only the `approvals:review` scope.

## Approval Workflow

High-risk actions interrupt the LangGraph workflow before any simulated action draft is created.

The approval flow is:

1. The agent reaches `assess_risk_and_approval`.
2. Risk logic marks the proposed action as requiring approval.
3. `approval_gate` interrupts execution with approval metadata.
4. The API persists an `ApprovalRequest` and returns `approval_id`.
5. A manager or admin calls `POST /api/v1/approvals/{approval_id}/decide`.
6. The approval API resumes the graph with `Command(resume=...)`.
7. Approved decisions route to `execute_action`; rejected decisions route to `final_response`.

Only `admin` and `manager` roles can decide approvals. Self-approval is explicitly blocked: the user who requested the approval cannot approve their own request.

## Risk Rules Configuration

Risk rules are configured in `rules/risk_rules.yaml`.

Current high-risk rules:

| Rule | Condition | Effect |
| --- | --- | --- |
| `HR-01` | `compensation_amount > 500` CNY | Requires approval for large compensation |
| `HR-02` | `recommended_action` contains `full_refund` and `order_status == delivered` | Requires approval for full refund override on delivered orders |
| `HR-03` | `merchant_risk_level == high` | Requires approval for high-risk merchant cases |

Current medium and low-risk rules:

| Rule | Condition | Effect |
| --- | --- | --- |
| `MR-01` | `recommended_action` contains `partial_refund` | Marks partial refund as medium risk |
| `MR-02` | compensation between 100 and 500 CNY | Marks moderate compensation as medium risk |
| `MR-03` | refund case older than 30 days | Marks stale cases as medium risk |
| `LR-01` | default | Standard low-risk path |

The demo compensation scenario uses 600 CNY so it crosses the configured `HR-01` threshold.

## Audit Trail

Every agent execution records:

- `AgentRun`: run ID, tenant ID, user ID, thread ID, input query, final response, final status, latency, token count where available.
- `AgentStep`: graph node, status, latency, tool calls, evidence refs, and node metrics.
- `ApprovalRequest`: proposed action, risk level, risk reason, requested user, decision, reviewer, timestamps, and reason.
- `ApprovalStep`: approval lifecycle events such as created, approved, rejected, expired, and resumed.
- `ActionDraft`: simulated action output for auditable write paths.

Trace replay is queryable at:

```text
GET /api/v1/agent-runs/{run_id}/trace
```

The trace response is intentionally summarized. It exposes operational review data such as nodes, approvals, action drafts, and timeline events, but it does not expose provider credentials or raw secrets.

## Tenant Isolation

Repository and API queries filter by `tenant_id`. A token includes tenant context, and protected endpoints load records within the current user's tenant.

Workflow checkpoints are scoped by checkpoint thread key:

```text
tenant_id:user_id:thread_id
```

This prevents two tenants, or two users in the same tenant, from sharing LangGraph checkpoint state just because they chose the same client thread ID. Target session memory uses the same tenant/user/thread isolation concept, but its authoritative store is the PostgreSQL `session_memories` contract with CAS; Redis, if introduced, is only a non-authoritative TTL hot cache.

Cross-tenant trace lookups return 404 when the run does not exist in the caller's tenant. Existing in-tenant runs still require owner or supervisor access; otherwise the API returns 403.

## Risk Boundaries

- Real payments, refunds, and coupons are not executed. The system creates simulated action drafts only.
- Demo credentials are public synthetic credentials, not production secrets.
- API keys, database URLs, JWT secrets, and provider tokens should live in environment variables and must not be committed.
- Public documentation may describe architecture and security controls, but should not include live credentials, private URLs, or production tenant data.
