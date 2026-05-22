# Phase 6: Evaluation & Polish — Research

**Date:** 2026-05-19
**Status:** Complete

---

## 1. Existing Evaluation Assets

### RAG Golden Set (`eval/golden_rag_queries.jsonl`)
- **14 cases**, JSONL format
- Categories: refund_rule (5), sop (3), faq (2), boundary (2), fallback (2)
- Fields: query, expected_doc_ids, expected_chunk_ids, category, difficulty, should_fallback
- Well-structured, stable — per D-01b, keep as-is, migrate path only

### Agent Golden Set (`evals/golden_set_phase3.json`)
- **15 cases**, JSON array format
- Categories: policy_qa (3), refund_troubleshooting (3), compensation_suggestion (2), insufficient_evidence (3), cross_turn_isolation (2), intent_edge_case (2)
- Fields: id, category, query, thread_id, expected_intent, expected_final_status, expected_evidence_present, expected_tools_called, notes
- Some cases have extra fields: expected_risk_level, expected_recommended_action
- **Missing categories per D-01d:** approval_required, permission_denied, approval_approved, approval_rejected, tool_failure_or_not_found, normal_policy_qa (rename from policy_qa)

### RAG Eval Script (`scripts/eval_rag_hit_at_5.py`)
- 246 lines, mature implementation
- Async, uses real DB (SessionLocal + Retriever + EmbeddingService)
- Scoring: Hit@5 (chunk intersection) + fallback accuracy (retrieval_status == "no_evidence")
- Per-category breakdown, diagnostic mode (extended top_k for failures)
- Exit code: 0 = pass, 1 = fail (threshold-based)
- **Refactor needed:** rename to `eval_rag.py`, output JSON report instead of print-only, accept `evaluation/golden/rag_cases.jsonl` as default path

### Smoke Agent Live (`scripts/smoke_agent_live.py`)
- 3 test cases, requires real LLM (DASHSCOPE_API_KEY)
- Uses `build_graph()` + `build_trace_summary()` directly
- Validates: intent match, final_status match, evidence_count minimum
- **Reusable pattern** for `eval_agent.py` — same invocation style but with FakeLLM for CI

---

## 2. Agent Architecture (for eval design)

### Graph Nodes (10 total)
```
receive_request → classify_intent → extract_slots → load_business_context
→ retrieve_policy_evidence → generate_recommendation → assess_risk_and_approval
→ [approval_gate | execute_action | final_response]
```

### Routing Logic
- `route_after_risk`: approval_required → approval_gate; proposed_action → execute_action; else → final_response
- `route_after_approval`: approve → execute_action; reject → final_response

### Trace Summary Fields (from `build_trace_summary`)
- run_id, intent, nodes_executed, tools_called, evidence_count, risk_level, total_latency_ms, final_status

### Final Status Derivation (`_derive_final_status`)
- recommended_action in {insufficient_evidence, citation_invalid} → "insufficient_evidence"
- node_errors present → "error"
- final_response present → "completed"
- else → "error"

---

## 3. API Endpoints (for demo curl commands)

| Endpoint | Method | Auth Scope | Purpose |
|----------|--------|-----------|---------|
| `/api/v1/auth/token` | POST | — | Get JWT token |
| `/api/v1/agent/chat` | POST | agent:chat | Submit query |
| `/api/v1/approvals/{id}/decide` | POST | approvals:review | Approve/reject |
| `/api/v1/orders/{id}` | GET | orders:read | Get order |
| `/api/v1/refund-cases/{id}` | GET | refunds:read | Get refund case |
| `/api/v1/search` | POST | knowledge:read | RAG search |
| `/api/v1/agent-runs` | GET | — | List runs |
| `/api/v1/traces/{run_id}` | GET | — | Get trace |

### Permission Denied Scenarios
- Missing scope → 403 `{"code": "FORBIDDEN", "message": "Insufficient scopes", "details": {"missing_scopes": [...]}}`
- Wrong role for approval → 403 `{"code": "FORBIDDEN", "message": "Insufficient role for approval"}`
- Self-approval → 403 `{"code": "SELF_APPROVAL"}`

---

## 4. Test Infrastructure

### FakeLLM Pattern (`tests/agent/conftest.py`)
- Deterministic structured output via `with_structured_output(schema)` → `schema.model_validate(response_dict)`
- Fixtures: fake_llm_intent, fake_llm_slots, fake_llm_recommendation, fake_llm_risk, fake_llm_final
- Each fixture returns predetermined response matching the Pydantic schema

### Test Coverage
- 46 test files total
- Agent: per-node tests, graph integration, trace, tools
- Interception rate: validates all 3 HR rules + LR-01 + policy_qa routing
- RAG: chunker, embedder, retriever, ingestion, search integration, eval

### CI-Compatible Patterns
- Tests use `MemorySaver` (in-memory checkpointer) instead of Postgres
- FakeLLM eliminates LLM API dependency
- `conftest.py` at root provides shared fixtures

---

## 5. CI Configuration Status

- **No `.github/workflows/` directory exists** — must create from scratch
- Tooling available: `uv` (package manager), `ruff` (linter), `pytest` (test runner)
- Python 3.12 target
- Commands:
  - Lint: `uv run ruff check .`
  - Unit tests: `uv run pytest tests/ -x` (excludes integration that need DB)
  - Eval (local only): `uv run python scripts/eval_all.py`

---

## 6. File Migration Plan

| Current Path | Target Path | Format Change |
|-------------|-------------|---------------|
| `eval/golden_rag_queries.jsonl` | `evaluation/golden/rag_cases.jsonl` | None |
| `evals/golden_set_phase3.json` | `evaluation/golden/agent_cases.jsonl` | JSON array → JSONL |
| `scripts/eval_rag_hit_at_5.py` | `scripts/eval_rag.py` | Refactor output to JSON |
| (new) | `scripts/eval_agent.py` | New file |
| (new) | `scripts/eval_all.py` | New file |
| (new) | `evaluation/reports/` | New directory |

---

## 7. Agent Golden Set Expansion Plan

### Current: 15 cases across 6 categories
### Target: 30-35 cases across 10 categories (per D-01d)

| Category | Current | Target | Notes |
|----------|---------|--------|-------|
| normal_policy_qa | 3 (as policy_qa) | 4 | Rename category |
| refund_troubleshooting | 3 | 4 | Add edge cases |
| compensation_suggestion | 2 | 4 | Add low/medium/high risk variants |
| approval_required | 0 | 4 | HR-01, HR-02, HR-03 triggers + boundary |
| permission_denied | 0 | 4 | Missing scope, wrong role, self-approval, no token |
| approval_approved | 0 | 3 | Post-approval execute flow |
| approval_rejected | 0 | 3 | Post-rejection final_response flow |
| missing_context | 0 (was insufficient_evidence) | 3 | Rename + expand |
| low_confidence_no_evidence | 3 (as insufficient_evidence) | 3 | Out-of-domain queries |
| tool_failure_or_not_found | 0 | 3 | Invalid order_id, DB timeout simulation |

**Total: ~35 cases**

### New Fields Needed (per D-01e)
- expected_approval_required (bool)
- expected_permission_result (str: "granted" | "denied_scope" | "denied_role")
- expected_evidence_doc_keys (list[str])
- expected_response_contains (list[str])
- must_not_contain (list[str])

---

## 8. Eval Scoring Design

### RAG Eval (refactor of existing)
- Hit@5: chunk_id intersection with top-5 results
- Fallback accuracy: no_evidence status for should_fallback cases
- Per-category breakdown
- Output: JSON with scores + failed cases

### Agent Eval (new)
- **Intent accuracy:** `result.current_intent == expected_intent`
- **Tool selection:** `set(result.tools_called) ⊇ set(expected_tools)`
- **Final status:** `trace_summary.final_status == expected_final_status`
- **Approval required:** `result.risk_assessment.approval_required == expected_approval_required`
- **Evidence presence:** `trace_summary.evidence_count > 0` when `expected_evidence_present`
- **Response content:** substring match for expected_response_contains / must_not_contain
- **Permission result:** HTTP status code check for permission_denied cases

### Scoring Algorithm
- Deterministic matching (exact match for intent, status, approval_required)
- Set containment for tools (expected ⊆ actual)
- Substring for response content
- Per-category pass rate + overall pass rate
- Safety-critical categories (approval, permission, rejection) must be 100%

---

## 9. Demo Script Design

### Deterministic Path (for CI/demo reproducibility)
- Use FakeLLM or mock responses — same pattern as test fixtures
- Seed data via `scripts/seed_demo.py` (already exists)
- Demo accounts from seed: support_agent (agent:chat), manager (approvals:review)

### 6-7 Scenarios (per D-06c)
1. **Policy QA:** "退款超时规则是什么？" → evidence-cited answer
2. **Refund troubleshooting:** "订单ORD-xxx退款卡在哪里？" → order lookup + policy
3. **Compensation suggestion:** "客户要求补偿600元" → high-risk flagged
4. **Approval trigger:** Same as #3 but show interrupt + pending approval
5. **Permission denied:** Use token without approvals:review scope → 403
6. **Approval rejected:** Manager rejects → final_response with rejection
7. **Trace query:** GET /traces/{run_id} → full execution trace

### Execution
- `scripts/demo_phase6.sh`: sequential curl calls with jq formatting
- `docs/demo-walkthrough.md`: annotated version with interview talking points

---

## 10. Key Technical Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Agent eval requires live DB for tool calls | CI can't run full agent eval | Use FakeLLM + mock tool responses; real eval is local-only |
| Permission denied cases are HTTP-level, not agent-level | Different eval mechanism needed | Split: agent eval tests graph behavior; permission tests are API-level assertions |
| Cross-turn isolation cases need multi-turn invocation | More complex eval harness | Implement as sequential ainvoke calls with same thread_id |
| Golden set expansion may reference non-existent seed data | Eval failures | Verify all order_ids/case_ids exist in seed_demo.py output |
| CI without DB can only run lint + unit tests | Limited CI coverage | Acceptable per D-07b; integration/eval are local scripts |

---

*Research complete. Ready for planning.*
