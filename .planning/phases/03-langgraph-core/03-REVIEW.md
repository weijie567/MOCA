---
phase: 03-langgraph-core
reviewed: 2026-05-11T08:36:33Z
depth: standard
files_reviewed: 44
files_reviewed_list:
  - .env.example
  - evals/golden_set_phase3.json
  - pyproject.toml
  - rules/risk_rules.yaml
  - scripts/smoke_agent_live.py
  - src/agent/__init__.py
  - src/agent/graph.py
  - src/agent/nodes/__init__.py
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/classify_intent.py
  - src/agent/nodes/extract_slots.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/load_business_context.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/retrieve_policy_evidence.py
  - src/agent/prompts.py
  - src/agent/schemas.py
  - src/agent/state.py
  - src/agent/tools/__init__.py
  - src/agent/tools/get_order.py
  - src/agent/tools/get_refund_case.py
  - src/agent/tools/get_ticket.py
  - src/agent/tools/search_policy.py
  - src/agent/trace.py
  - src/api/main.py
  - src/api/routers/agent.py
  - src/api/schemas/agent.py
  - src/auth/permissions.py
  - src/config.py
  - src/db/migrations/versions/003_agent_tables.py
  - src/db/models.py
  - tests/agent/__init__.py
  - tests/agent/conftest.py
  - tests/agent/test_graph.py
  - tests/agent/test_nodes/__init__.py
  - tests/agent/test_nodes/test_classify_intent.py
  - tests/agent/test_nodes/test_generate_recommendation.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_nodes/test_retrieve_policy_evidence.py
  - tests/agent/test_tools/__init__.py
  - tests/agent/test_tools/test_get_order.py
  - tests/agent/test_tools/test_get_refund_case.py
  - tests/agent/test_tools/test_search_policy.py
findings:
  critical: 1
  warning: 5
  info: 0
  total: 6
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-11T08:36:33Z
**Depth:** standard
**Files Reviewed:** 44
**Status:** issues_found

## Summary

Reviewed the Phase 03 LangGraph agent, API integration, trace persistence, migrations, risk rules, smoke script, and agent tests. The main concern is an authorization gap in the agent tool path: it bypasses merchant-level checks already enforced by the REST routes. I also found trace contract mismatches, ticket lookup identifier drift, error handling that turns infrastructure failures into "insufficient evidence", and test/smoke gaps that would miss these regressions.

## Critical Issues

### CR-01: Agent Tools Bypass Merchant-Level Authorization

**File:** `src/agent/tools/get_order.py:36`, `src/agent/tools/get_refund_case.py:36`, `src/agent/tools/get_ticket.py:36`
**Issue:** The agent tools receive `user_id` and `role` but immediately discard them, then fetch records using tenant scope only. The REST routes enforce merchant ownership before returning order, refund, or ticket data (`src/api/routers/orders.py:31`, `src/api/routers/refund_cases.py:49`, `src/api/routers/tickets.py:47`), but `POST /agent/chat` can call these tools with only `agent:chat`. A merchant user in the same tenant can therefore ask the agent about another merchant's order/refund/ticket and leak buyer/order/support data into `business_context` and the LLM prompt.
**Fix:**
```python
# Apply the same ownership check in every business-data tool.
from sqlalchemy import select
from src.db.models import Order, User

async def _merchant_allowed(session, *, user_id: str, tenant_uuid, merchant_id) -> bool:
    user = (
        await session.execute(
            select(User).where(User.id == UUID(user_id), User.tenant_id == tenant_uuid)
        )
    ).scalar_one_or_none()
    if user is None:
        return False
    return user.role != "merchant" or user.merchant_id == merchant_id

# get_order: after result is loaded
order = result["order"]
if not await _merchant_allowed(session, user_id=user_id, tenant_uuid=tenant_uuid, merchant_id=order.merchant_id):
    return _tool_error("FORBIDDEN", "Merchant access is limited to the merchant's own orders", retryable=False, should_stop=True)
```

Add equivalent checks for refund cases and tickets by resolving `Order.merchant_id` from `refund_case.order_id` / `ticket.order_id`, and add tests proving merchant users cannot read another merchant's records through the agent tools.

## Warnings

### WR-01: Trace Summary Drops Tool Calls and Evidence Counts

**File:** `src/agent/trace.py:95`
**Issue:** `build_trace_summary()` looks for `step["tool_name"]`, but graph nodes record `tools_called` lists (`src/agent/nodes/load_business_context.py:24`, `src/agent/nodes/retrieve_policy_evidence.py:25`). It also counts `retrieved.get("evidence")`, while `search_policy()` nests evidence under `retrieved_evidence["data"]["evidence"]`. API responses will report `tools_called: []` and `evidence_count: 0` even when tools ran and evidence was retrieved, breaking the response contract and golden-set expectations.
**Fix:**
```python
tools_called: list[str] = []
for step in trace_steps:
    tools_called.extend(step.get("tools_called") or [])
    if step.get("tool_name"):
        tools_called.append(step["tool_name"])

retrieved = final_state.get("retrieved_evidence") or {}
retrieval_data = retrieved.get("data") or retrieved
evidence_count = len(retrieval_data.get("evidence") or [])
```

Update `tests/agent/test_graph.py:test_trace_summary_shape` to assert non-empty `tools_called` and the expected evidence count for a happy path.

### WR-02: Ticket Tool Uses UUID While Public Ticket Identifiers Are Ticket Numbers

**File:** `src/agent/tools/get_ticket.py:39`
**Issue:** `get_ticket()` parses `ticket_id` as a UUID and calls `repo.get_by_id()`, but the public ticket API and repository expose ticket lookup by `ticket_no` (`src/api/routers/tickets.py:21`, `src/api/routers/tickets.py:30`). A user who asks about `TK-TEST-001` will get `VALIDATION_ERROR` instead of ticket context, even though that is the identifier exposed elsewhere.
**Fix:**
```python
try:
    ticket_uuid = UUID(ticket_id)
except ValueError:
    ticket_uuid = None

repo = TicketRepository(session)
if ticket_uuid is not None:
    ticket = await repo.get_by_id(ticket_uuid, tenant_uuid)
else:
    ticket = await repo.get_by_ticket_no(ticket_id, tenant_uuid)
```

Add tests for both UUID relation-hint lookup and direct `ticket_no` lookup.

### WR-03: Retrieval Infrastructure Errors Become Insufficient-Evidence Answers

**File:** `src/agent/nodes/retrieve_policy_evidence.py:70`
**Issue:** Any `search_policy()` error, including DB timeout or embedding/search failure, triggers the same `insufficient_evidence` recommendation as a real no-evidence result. The trace step is still marked `completed`, and no `node_errors` entry is recorded. Users can receive "knowledge base has no evidence" when the actual problem is an infrastructure failure.
**Fix:**
```python
if result.get("status") == "error":
    return {
        "retrieved_evidence": result,
        "node_errors": (state.get("node_errors") or []) + [
            {"node": "retrieve_policy_evidence", "error": result.get("error"), "retry_count": 0}
        ],
        "trace_steps": (state.get("trace_steps") or []) + [_trace_step("error", started_at)],
    }
```

Keep the insufficient-evidence draft only for successful searches with `retrieval_status == "no_evidence"` or low scores, and add a test for `DB_TIMEOUT`.

### WR-04: Deterministic Full-Refund Risk Rule Cannot Match Chinese Recommendations

**File:** `src/agent/nodes/assess_risk_and_approval.py:94`
**Issue:** The deterministic high-risk override checks for the literal token `"full_refund"` in `recommended_action`, while the recommendation prompt requires Chinese output. A delivered-order recommendation like `"建议全额退款"` will not match `HR-02` from `rules/risk_rules.yaml:12`, leaving a high-risk rule dependent on the LLM classification instead of the deterministic guardrail.
**Fix:**
```python
FULL_REFUND_TERMS = ("full_refund", "全额退款", "全额退", "整单退款")

if (
    "full_refund" in condition
    and any(term in action for term in FULL_REFUND_TERMS)
    and order.get("status") == "delivered"
):
    return rule
```

Preferably make `recommended_action` a structured enum plus localized display text, then evaluate rules against the enum. Add a unit test for delivered order + Chinese full-refund wording.

### WR-05: Live Smoke Script Can Pass Without Verifying the Live Agent Path

**File:** `scripts/smoke_agent_live.py:54`
**Issue:** The script says it requires a running Postgres DB, but it passes `AsyncMock()` as the graph session. It also prints `PASS` for any successful `graph.ainvoke()` without checking `expected_intent` or `expected_final_status`. This can pass while policy search is not using a real DB session or while the agent returns the wrong result.
**Fix:**
```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

engine = create_async_engine(settings.database_url)
session_factory = async_sessionmaker(engine, expire_on_commit=False)

async with session_factory() as session:
    config = {"configurable": {"thread_id": case["thread_id"], "session": session}}
    result = await graph.ainvoke(input_state, config)
    if case.get("expected_intent") and result.get("current_intent") != case["expected_intent"]:
        raise AssertionError(f"intent mismatch: {result.get('current_intent')}")
```

Also assert expected final status via `build_trace_summary()` and exit non-zero on any failed case.

---

_Reviewed: 2026-05-11T08:36:33Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
