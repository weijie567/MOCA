# External Integrations

**Analysis Date:** 2026-05-09

## APIs & External Services

**Currently implemented:**
- None in repository code; there are no API clients, SDK wrappers, or service configuration files yet

**Planned in documents only:**
- OpenAI-compatible model API for agent inference, referenced in `.planning/PROJECT.md`
- Business-domain tools for orders, refunds, tickets, coupons, and approvals, referenced in `.planning/REQUIREMENTS.md`

## Data Storage

**Currently implemented:**
- No database schema, migration directory, seed scripts, or ORM configuration detected

**Planned in documents only:**
- PostgreSQL + pgvector as the primary store for business data and embeddings
- Redis for cache, session support, and rate limiting

## Authentication & Identity

**Currently implemented:**
- No auth middleware, token handling, or RBAC code present

**Planned in documents only:**
- JWT + OAuth2 scopes for role-aware API access
- Roles including merchant operator, support agent, reviewer, manager, and admin are specified in `.planning/REQUIREMENTS.md`

## Monitoring & Observability

**Currently implemented:**
- None beyond Git history and local GSD metadata

**Planned in documents only:**
- OTel tracing in MVP/polish phases
- Prometheus and Grafana in later hardening work

## CI/CD & Deployment

**Currently implemented:**
- No CI workflows, deployment manifests, or container build files detected

**Planned in documents only:**
- `docker compose up` as the main local demo path
- Kubernetes explicitly deferred from MVP in `.planning/PROJECT.md`

## Environment Configuration

**Current state:**
- No `.env.example` or secrets contract exists
- No documented local bootstrap command in the repository root

**Recommendation baseline for first implementation phase:**
- Define `.env.example` before adding code so service boundaries and secrets are explicit
- Separate local synthetic-data credentials from future production-style settings

## Webhooks & Callbacks

**Currently implemented:**
- None

**Planned in documents only:**
- Approval resume flow and simulated notifications are mentioned, but no transport or retry strategy is defined yet

## Integration Risk Summary

- The repository currently documents many future integrations, but none are constrained by schemas or adapters yet
- The first implementation phase should freeze tool input/output contracts early; otherwise LangGraph, API, and frontend work will drift independently

---
*Integration audit: 2026-05-09*
*Update when the first external client, schema, or service manifest is added*
