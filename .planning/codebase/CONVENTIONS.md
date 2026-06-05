# Coding Conventions

**Analysis Date:** 2026-06-05

## Naming Patterns

**Python source:**
- Modules and files use snake_case.
- API routers are grouped by business domain: `orders`, `refund_cases`, `tickets`, `approvals`, `agent_runs`, `traces`.
- Repositories use domain names and `*Repository` classes.
- Tests use `test_*.py` names and descriptive `test_*` functions.

**Agent code:**
- Graph nodes live in `src/agent/nodes/` and are named by workflow step, such as `classify_intent`, `retrieve_policy_evidence`, and `assess_risk_and_approval`.
- Tool code lives in `src/agent/tools/` and separates contracts, adapters, registry, authorization, and concrete tool behavior.

**Frontend source:**
- React components use PascalCase.
- Hooks use `use*` naming.
- Shared API/SSE helpers live under `frontend/src/lib/`.

**Planning docs:**
- Canonical planning docs use uppercase names.
- Phase files use phase-prefixed names such as `07-VALIDATION.md`.

## Code Style

**Python:**
- Ruff configured in `pyproject.toml` with line length 120 and Python 3.12 target.
- Async-first database and API code.
- Pydantic models define API, RAG, and tool contracts.

**Frontend:**
- TypeScript React with Vite.
- Tailwind-based styling with reusable UI components in `frontend/src/components/ui/`.

**Documentation:**
- Mixed English and Chinese content exists; user-facing and domain examples often use Chinese.
- Requirement and phase artifacts maintain explicit IDs and verification summaries.

## Import Organization

**Observed pattern:**
- Standard library imports first, then third-party imports, then `src.*` imports.
- Routes import schemas, dependencies, repositories, and domain helpers explicitly.
- Tests import app/session fixtures and domain helpers from `tests/conftest.py` or agent-specific fixtures.

## Error Handling

**API:**
- Standard response envelope through `ApiResponse`.
- Middleware attaches trace IDs and handles errors consistently.
- Route errors use FastAPI `HTTPException` for auth, permission, conflict, tenant isolation, and not-found cases.

**Agent/tools:**
- Tool registry validates inputs and catches/normalizes execution failures.
- Agent nodes append trace steps and preserve enough state for review/debugging.
- Approval flow uses explicit conflict handling for expired, duplicate, or unauthorized decisions.

## Logging and Traceability

**Current convention:**
- Prefer persisted trace events over ad hoc print/log output.
- Runtime trace concepts include `trace_id`, `run_id`, graph node names, approval events, action drafts, latency, and final status.
- Trace output exposed through agent-run APIs should avoid leaking investigation-only internal fields.

## Comments

**Preferred style:**
- Comments should explain business invariants, safety constraints, or non-obvious graph/tool behavior.
- Avoid comments that restate simple code mechanics.

## Function Design

**Backend:**
- Keep route handlers thin.
- Put persistence in repositories.
- Keep Pydantic schemas as explicit request/response boundaries.

**Agent:**
- Keep each graph node focused on one workflow responsibility.
- Tool invocations should go through registry/adapter paths rather than direct ad hoc calls.
- Write/approval-capable tools must carry explicit risk and side-effect metadata.

**Frontend:**
- Keep API/SSE details in hooks/libs, not deeply embedded in visual components.
- Components should be organized by UI region: chat, timeline, details, layout, primitives.

## Module Design

**Established modules:**
- `api` for HTTP surface
- `agent` for orchestration and tool behavior
- `auth` for JWT/scope checks
- `db` for models/session/migrations
- `repositories` for persistence operations
- `rag` for policy retrieval and citation safety

**Additions should follow existing boundaries:**
- Do not put database queries in agent nodes or route handlers when a repository exists.
- Do not bypass tool registry for agent tool execution.
- Do not introduce new response envelopes unless replacing `ApiResponse` project-wide.

## Convention Risks

- `.planning/codebase` can drift after phases unless map refresh is part of closeout.
- Mixed Chinese/English docs are acceptable, but API field names should remain stable English identifiers.
- Frontend and backend have separate toolchains; keep run/test commands documented together.

---
*Convention analysis: 2026-06-05*
*Refresh when style, module boundaries, or tool/API contracts change*
