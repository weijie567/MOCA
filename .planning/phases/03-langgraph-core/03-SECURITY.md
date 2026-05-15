---
phase: "03"
slug: langgraph-core
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-15T13:18:19Z
updated: 2026-05-15T13:18:19Z
---

# Phase 03 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| env -> Settings | DashScope credentials are loaded from the local environment and must not be logged or committed. | API key / secret |
| HTTP request -> agent endpoint | User query and thread_id are untrusted request data; identity and tenant come from JWT-authenticated `User`. | Query text / thread key |
| JWT user -> AgentState | API layer constructs `tenant_id`, `user_id`, and `role`; graph nodes consume these values for tool calls. | Authenticated identity |
| node -> read tool -> repository | Nodes invoke read-only tools; repositories enforce tenant and merchant scoping. | Order/refund/ticket records |
| LLM output -> recommendation_draft | Model-produced citations and risk fields must be validated or deterministically overridden before use. | Structured model output |
| retrieved evidence -> checkpointer state | Same-thread memory stores compact evidence refs only, not full chunks, prompts, or business records. | Citation metadata |
| graph output -> trace writer -> DB | Final graph state is normalized into AgentRun/AgentStep audit rows; response summary must remain minimal. | Trace and audit metadata |
| test fixtures -> production code | Fake LLMs and synthetic golden-set cases must remain test-only. | Synthetic test data |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-03-01 | Information Disclosure | `Settings.dashscope_api_key` | mitigate | `src/config.py` uses an empty default; `.env.example` contains only `your-dashscope-api-key-here`; no source path logs the key. | closed |
| T-03-02 | Tampering | `003_agent_tables` migration | accept | Accepted risk: Alembic version tracking plus `down_revision="002_rag_pipeline"` and `downgrade()` provide rollback; no runtime mitigation required. | closed |
| T-03-03 | Elevation of Privilege | `get_order` / `get_refund_case` / `get_ticket` | mitigate | Tools parse tenant UUIDs, query repositories with tenant scope, enforce merchant ownership with `merchant_can_access()`, and return `FORBIDDEN` for same-tenant cross-merchant access. | closed |
| T-03-04 | Information Disclosure | `get_ticket` tool | mitigate | `get_ticket()` returns ticket number, status, channel, and summary only; PII-heavy `messages` are excluded and covered by tests. | closed |
| T-03-05 | Spoofing | `AgentState.tenant_id` | mitigate | `src/api/routers/agent.py` builds input state from authenticated `User.tenant_id`, `User.id`, and `User.role`; user query text cannot set tenant identity. | closed |
| T-03-06 | Tampering | `generate_recommendation` citation validation | mitigate | `validate_citations()` rejects cited chunk IDs absent from current retrieval results; invalid refs are stripped before final response or memory persistence. | closed |
| T-03-07 | Information Disclosure | `receive_request` per-turn reset | mitigate | `receive_request()` resets ephemeral business context, retrieved evidence, recommendations, risk assessment, final response, tool results, LLM outputs, and node errors each turn. | closed |
| T-03-08 | Denial of Service | LLM timeout | mitigate | LLM clients use `settings.llm_timeout_seconds`; LLM nodes attempt bounded retries and return structured fallback state with `node_errors` on exhaustion. | closed |
| T-03-09 | Elevation of Privilege | `assess_risk_and_approval` | mitigate | Risk rules load from `rules/risk_rules.yaml`; deterministic high-risk overrides run after model output so the LLM cannot downgrade matched high-risk actions. | closed |
| T-03-10 | Information Disclosure | `build_trace_summary` | mitigate | API trace summary returns run_id, intent, node names, tool names, evidence_count, risk_level, latency, and final_status only; no prompts, tool outputs, or full evidence text. | closed |
| T-03-11 | Spoofing | `ChatRequest.thread_id` | mitigate | Checkpointer thread IDs are scoped as `tenant_id:user_id:thread_id`; raw thread_id is not trusted as an auth boundary. | closed |
| T-03-12 | Denial of Service | `graph.ainvoke` timeout/fallback | mitigate | Graph execution is composed of bounded tool/LLM calls and the endpoint catches graph exceptions, returning a structured fallback and best-effort error AgentRun. | closed |
| T-03-13 | Information Disclosure | Trace write failure path | mitigate | Trace persistence failures roll back the DB session and do not alter or expose the successful user response; graph invocation failures use a generic fallback message. | closed |
| T-03-14 | Information Disclosure | `evals/golden_set_phase3.json` | accept | Accepted risk: golden-set entries are synthetic Chinese support/order cases and contain no real user IDs or real PII. | closed |
| T-03-15 | Tampering | FakeLLM in CI | accept | Accepted risk: `FakeLLM` lives under `tests/agent`; production `src/` paths do not import it, and live provider execution remains opt-in through local credentials. | closed |
| T-03-GAP-01 | Information Disclosure | `AgentState.evidence_refs` | mitigate | Retrieval/recommendation persist compact refs only: doc_key, chunk_id, title/section, confidence, and retrieved_at; no full chunk text, prompts, orders, or tool outputs are stored in memory refs. | closed |
| T-03-GAP-02 | Tampering | `trace_steps.tools_called` | mitigate | Trace tool names come from bounded node-produced read-only tool calls; `write_agent_steps()` normalizes them into existing DB fields and regression tests query persisted rows by run_id. | closed |
| T-03-GAP-03 | Repudiation | AgentStep query by run_id | mitigate | DB-backed tests assert AgentStep rows retain step index, tool names, and evidence refs for audit replay by run_id. | closed |
| T-03-GAP-04 | Information Disclosure | Retained evidence memory | mitigate | Same-thread memory tests prove retained evidence refs do not override current-turn no-evidence behavior; final answers remain gated by current retrieved evidence and validated draft citations. | closed |
| T-03-GAP-05 | Elevation of Privilege | Phase 3 graph behavior | accept | Accepted risk: Phase 3 intentionally remains read-only and adds no write tools, approval interrupts, or action execution; Phase 4 owns approval/write behavior. | closed |

*Status: open · closed*  
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-03-01 | T-03-02 | Migration tampering risk is accepted because Alembic version tracking, correct down_revision, and downgrade support are sufficient for this schema-only change. | Codex security audit | 2026-05-15 |
| AR-03-02 | T-03-14 | Golden-set data is synthetic test data only; no production customer/order identifiers are included. | Codex security audit | 2026-05-15 |
| AR-03-03 | T-03-15 | FakeLLM is test-only and absent from production import paths; live provider execution is explicitly manual/local. | Codex security audit | 2026-05-15 |
| AR-03-04 | T-03-GAP-05 | Phase 3 is scoped to the read-only happy path; approval interruptions and write tools are intentionally deferred to Phase 4. | Codex security audit | 2026-05-15 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-15 | 20 | 20 | 0 | Codex |

---

## Security Audit 2026-05-15

| Metric | Count |
|--------|-------|
| Threats found | 20 |
| Closed | 20 |
| Open | 0 |

### Evidence Reviewed

- Threat models from `03-01-PLAN.md` through `03-06-PLAN.md`
- Summary threat flags from `03-01-SUMMARY.md` through `03-06-SUMMARY.md`
- Source files under `src/agent`, `src/api/routers/agent.py`, `src/api/main.py`, `src/config.py`, and migration `003_agent_tables.py`
- Regression tests under `tests/agent/test_tools`, `tests/agent/test_nodes`, `tests/agent/test_graph.py`, and `tests/agent/test_trace.py`

### Verification Commands

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q --tb=short` — previously passed with 89 tests during Phase 3 live verification closure
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src tests scripts` — previously passed during Phase 3 live verification closure
- `gsd-sdk query verify.schema-drift "03" --raw` — passed during secure-phase audit

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-15
