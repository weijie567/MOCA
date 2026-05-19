# Phase 6: Evaluation & Polish - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Final validation and presentation layer for the MOCA project. Expand evaluation coverage to a comprehensive golden set, validate all metrics end-to-end, produce interview-ready README and demo materials, and establish a CI baseline. No new business features — only small fixes needed for evaluation/demo reproducibility.

</domain>

<decisions>
## Implementation Decisions

### D-01: Golden Set Architecture — Layered Evaluation
- **D-01a:** Retain two separate golden sets, do not merge physically.
- **D-01b:** RAG golden set (14 cases) stays stable in `evaluation/golden/rag_cases.jsonl`. Only expand if new knowledge docs are added or retrieval gaps discovered.
- **D-01c:** Agent golden set expands from 15 to 30-35 cases in `evaluation/golden/agent_cases.jsonl`.
- **D-01d:** Agent case categories: normal_policy_qa, refund_troubleshooting, compensation_suggestion, approval_required, permission_denied, approval_approved, approval_rejected, missing_context, low_confidence_no_evidence, tool_failure_or_not_found.
- **D-01e:** Agent case fields: expected_intent, expected_tools, expected_status, expected_approval_required, expected_permission_result, expected_evidence_doc_keys, expected_response_contains, must_not_contain.
- **D-01f:** RAG case fields remain: query, expected_doc_ids, expected_chunk_ids, expected_hit_k, category.

### D-02: Evaluation Scripts & Report
- **D-02a:** Three scripts: `scripts/eval_rag.py`, `scripts/eval_agent.py`, `scripts/eval_all.py`.
- **D-02b:** `eval_all.py` outputs `evaluation/reports/latest.json` + `evaluation/reports/latest.md`.
- **D-02c:** JSON is source of truth. Markdown is rendered FROM JSON (never computed independently).
- **D-02d:** CI uses `eval_all.py` exit code only (exit 0 = pass, exit 1 = fail). No Markdown grep.
- **D-02e:** JSON schema includes: overall_status, generated_at, rag_eval_summary, agent_eval_summary, thresholds, failed_cases, warning_cases, metrics, baseline_comparison.
- **D-02f:** Optional timestamped reports: `evaluation/reports/YYYY-MM-DD_HH-MM-SS.{json,md}`.
- **D-02g:** Baseline: save `baseline.json`, support simple diff with `latest.json`. No trend graphs or dashboards.

### D-03: Pass/Fail Thresholds
- **D-03a:** RAG: Hit@5 >= 85%, critical policy cases must hit expected evidence.
- **D-03b:** Agent: permission/approval/rejection cases must 100% pass.
- **D-03c:** Agent: intent/route accuracy >= 90%.
- **D-03d:** Agent: evidence citation rate >= 85%.
- **D-03e:** Agent: final response groundedness >= 85%.

### D-04: README Structure — Layered (展示 + 技术)
- **D-04a:** Upper half serves interviewers (1-2 min scan): project overview, key capabilities, architecture diagrams, demo link, eval summary.
- **D-04b:** Lower half serves developers: quick start, repo structure, technical notes linking to docs/.
- **D-04c:** 2 Mermaid diagrams: System Architecture + Agent Workflow.
- **D-04d:** No image files. No metrics badges as blocking requirement (optional).
- **D-04e:** README sections: Project Overview, Key Capabilities, Architecture Diagram, 10-Minute Demo, Evaluation Summary, Quick Start, Repository Structure, Technical Notes, Current Scope and Limitations.

### D-05: Documentation Split
- **D-05a:** `docs/demo-walkthrough.md` — 10-minute demo flow with curl examples and interview talking points.
- **D-05b:** `docs/evaluation.md` — golden set design, metrics, thresholds, CI logic.
- **D-05c:** `docs/architecture.md` — system architecture and agent workflow detail.
- **D-05d:** `docs/security-and-permission.md` — RBAC, approval, audit, risk boundaries.

### D-06: Demo Script
- **D-06a:** `docs/demo-walkthrough.md` is the primary demo entry point (human-readable).
- **D-06b:** `scripts/demo_phase6.sh` is the reproducible execution script.
- **D-06c:** 6-7 demo scenarios: policy QA, refund troubleshooting, compensation suggestion, approval trigger, permission denied, approval rejected, trace/evidence query.
- **D-06d:** 10-minute pacing: 1 min problem, 2 min architecture, 4 min live demo, 2 min trace/eval, 1 min summary.
- **D-06e:** Demo does NOT depend on frontend. API/curl only. Frontend screenshots optional in README.
- **D-06f:** Demo script uses deterministic/mock-friendly path, no real LLM dependency.

### D-07: Delivery Boundaries
- **D-07a:** No new business features. Only small fixes for eval/demo/trace reproducibility.
- **D-07b:** CI eval uses deterministic/mock path. Real LLM eval is optional local command only.
- **D-07c:** Trace display in demo: run_id, intent, tool calls, evidence refs, approval decision, final status. No full trace visualization UI.

### Claude's Discretion
- CI workflow file structure (GitHub Actions YAML layout)
- Exact Mermaid diagram content and styling
- Agent eval scoring algorithm internals (deterministic matching vs fuzzy)
- File migration strategy for moving existing golden sets to `evaluation/golden/`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Evaluation Assets
- `eval/golden_rag_queries.jsonl` — Current 14-case RAG golden set (to be migrated to evaluation/golden/)
- `evals/golden_set_phase3.json` — Current 15-case Agent golden set (to be migrated to evaluation/golden/)
- `scripts/eval_rag_hit_at_5.py` — Current RAG eval script (to be refactored into scripts/eval_rag.py)
- `tests/test_rag_eval.py` — RAG eval test

### Project Context
- `.planning/ROADMAP.md` — Phase 6 success criteria and requirements
- `.planning/REQUIREMENTS.md` — EVAL-01, EVAL-03, EVAL-04, EVAL-06, EVAL-07, INFR-07, INFR-08
- `rules/risk_rules.yaml` — Risk thresholds for approval trigger cases

### Codebase Patterns
- `src/moca/agent/` — Agent graph, nodes, tools (for understanding expected behaviors)
- `src/moca/api/` — API endpoints (for demo curl commands)
- `scripts/smoke_agent_live.py` — Existing live smoke test pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/eval_rag_hit_at_5.py`: RAG eval logic — refactor into `scripts/eval_rag.py`
- `evals/golden_set_phase3.json`: Agent golden set structure — extend with new categories
- `scripts/smoke_agent_live.py`: Live agent invocation pattern — reuse for demo script
- `scripts/seed_demo.py`: Demo data seeding — prerequisite for demo reproducibility

### Established Patterns
- Eval scripts use `SessionLocal` and production repository paths for realistic DB-backed scoring
- Tests use FakeLLM fixtures for CI isolation from live LLM APIs
- Agent integration tests use MemorySaver with mocked LLM boundaries

### Integration Points
- `eval_all.py` will import from `eval_rag.py` and `eval_agent.py`
- README references `evaluation/reports/latest.md` for metrics display
- CI workflow calls `uv run python scripts/eval_all.py`

</code_context>

<specifics>
## Specific Ideas

- Agent golden set 扩展时，每个 category 至少 3 cases，safety-critical categories (approval, permission, rejection) 至少 4 cases
- Demo walkthrough 包含面试讲解提示（每步应该怎么解释给面试官）
- README 强调"不是普通 chatbot，而是面向售后/退款/补偿流程的 Agent workflow system"
- Evaluation summary 在 README 中直接展示核心指标数字，不只是链接

</specifics>

<deferred>
## Deferred Ideas

- 复杂趋势图 / 历史 dashboard / 多版本统计 — 超出 Phase 6 scope
- Metrics badge 自动更新 — 可选增强，不阻塞
- 完整 trace visualization UI — 属于 v1.1 增强
- 面试 PPT 生成 — 可后续根据 Mermaid 图单独制作
- Frontend screenshot 嵌入 README — optional，不作为验收条件

</deferred>

---

*Phase: 06-evaluation-polish*
*Context gathered: 2026-05-19*
