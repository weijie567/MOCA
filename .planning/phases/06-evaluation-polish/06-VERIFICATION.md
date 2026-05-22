---
phase: 06-evaluation-polish
verified: 2026-05-22T09:07:13Z
status: passed
score: 23/23 must-haves verified
overrides_applied: 0
gaps: []
---

# Phase 6: Evaluation & Polish Verification Report

**Phase Goal:** Expand evaluation coverage to full golden set, validate all metrics end-to-end, produce interview-ready README and demo materials, establish CI baseline.
**Verified:** 2026-05-22T09:07:13Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Golden set expanded to full final coverage | VERIFIED | `evaluation/golden/rag_cases.jsonl` has 14 cases; `evaluation/golden/agent_cases.jsonl` has 35 cases. Agent set covers all 10 categories, including rule QA, refund troubleshooting, compensation, approval trigger, no-evidence, permission denied, approval approved/rejected, missing context, and tool failure. |
| 2 | Safety-critical golden cases meet required counts | VERIFIED | Category counts: approval_required 4, permission_denied 4, approval_approved 3, approval_rejected 3. |
| 3 | Agent cases use required D-01e schema | VERIFIED | All 35 cases include `id`, `category`, `query`, `expected_intent`, `expected_tools_called`, `expected_approval_required`, `expected_permission_result`, `expected_evidence_doc_keys`, `expected_response_contains`, and `must_not_contain`; no missing fields or duplicate IDs. |
| 4 | Golden cases reference valid seeded data | VERIFIED | `uv run python scripts/validate_golden_seeds.py` passed with `SEED VALIDATION PASSED`; only tool-failure cases use deliberately missing order IDs. |
| 5 | RAG eval reads new golden set and reports Hit@5/category metrics | VERIFIED | `scripts/eval_rag.py` defaults to `evaluation/golden/rag_cases.jsonl`, scores expected chunk intersection/fallback, returns JSON with `hit_at_5`, `fallback_accuracy`, `per_category`, and exits 0/1 by threshold. |
| 6 | Agent eval reads new golden set and scores required dimensions | VERIFIED | `scripts/eval_agent.py` loads `evaluation/golden/agent_cases.jsonl` and scores intent, tool selection, final status, approval flag, evidence presence, response contains, and must-not-contain. |
| 7 | Agent eval graph contract is not purely self-fulfilling | VERIFIED | `scripts/eval_agent.py` invokes `build_graph(MemorySaver())` under patched deterministic dependencies for representative graph-contract categories, uses `graph.ainvoke(...)`, resumes approval cases with `Command(resume=...)`, and fails overall status on graph-contract failures. Orchestrator run reported `graph_contract.status=pass` and `failures=[]`. |
| 8 | Unified eval produces JSON and Markdown reports | VERIFIED | `scripts/eval_all.py` imports `run_rag_eval()` and `run_agent_eval()`, writes `evaluation/reports/latest.json` and `latest.md`, renders Markdown from the JSON report object, and exits on `overall_status`. Synthetic render spot-check passed. |
| 9 | Eval scripts expose latency/token cost behavior | VERIFIED | Agent live mode measures `latency_ms` and extracts token counts; deterministic CI mode reports latency as `null` and tokens as `0`, documented in `docs/evaluation.md`. |
| 10 | Makefile exposes local eval entrypoints | VERIFIED | `Makefile` has `.PHONY` targets `eval`, `eval-rag`, `eval-agent`, `eval-live`, and `eval-baseline`, each calling the expected `uv run python scripts/eval_*.py` command. |
| 11 | CI baseline runs lint and unit tests only | VERIFIED | `.github/workflows/ci.yml` runs `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest tests/ -x --ignore=tests/integration -q --tb=short` on push/PR. No eval scripts or secrets are referenced. |
| 12 | CI-equivalent checks pass | VERIFIED | Orchestrator evidence: Ruff check passed, Ruff format check passed, pytest passed with 164 tests and 1 warning after local Postgres startup, schema drift valid with no issues. |
| 13 | Demo script covers interview flow and fails fast | VERIFIED | `scripts/demo_phase6.sh` has 7 scenarios, `set -euo pipefail`, preflight auth/chat checks, `.success == true` assertions, required run/approval IDs, real permission-denied check, rejection path, and trace query. `bash -n scripts/demo_phase6.sh` passed. |
| 14 | README is interview-ready and linked | VERIFIED | `README.md` has required sections, 159 lines, two Mermaid diagrams, quick start/demo accounts/evaluation summary, and links to demo, evaluation, architecture, and security docs. |
| 15 | Demo walkthrough is documented | VERIFIED | `docs/demo-walkthrough.md` has 7 scenarios, curl examples, interview talking points, expected response highlights, demo accounts, and automated-script instructions. |
| 16 | Evaluation methodology is documented | VERIFIED | `docs/evaluation.md` documents golden sets, metrics, thresholds, local commands, report schema, CI/local split, FakeLLM limitations, latency, and token behavior. |
| 17 | Architecture documentation is accurate | VERIFIED | `docs/architecture.md` includes system/agent Mermaid diagrams, all 10 graph nodes, actual trace endpoint, `text-embedding-v4`, and 1024-dimensional pgvector retrieval shape. |
| 18 | Security/permission documentation is accurate | VERIFIED | `docs/security-and-permission.md` covers JWT/OAuth2, RBAC, approval resume, self-approval blocking, audit trail, tenant isolation, and current `rules/risk_rules.yaml` thresholds. |
| 19 | Code review finding WR-01 is fixed | VERIFIED | Default agent eval now includes compiled LangGraph graph-contract checks and overall status fails if graph-contract failures exist. |
| 20 | Code review finding WR-02 is fixed | VERIFIED | Demo script no longer accepts chat HTTP 500/success=false; it requires successful chat responses, run IDs, approval IDs, and expected permission/rejection/trace shapes before continuing. |
| 21 | Code review finding IN-01 is fixed | VERIFIED | Architecture doc lists DashScope `text-embedding-v4` and 1024-dimensional embeddings. |
| 22 | No blocking placeholder/stub patterns found | VERIFIED | Stub scan found only `return []` in an expected helper branch for permission-denied graph nodes; no TODO/FIXME/placeholder user-facing content in Phase 6 outputs. |
| 23 | Phase 6 requirement IDs are covered | VERIFIED | EVAL-03, EVAL-04, EVAL-06, EVAL-07, INFR-07, and INFR-08 map to implemented scripts, reports, docs, Makefile targets, and CI workflow. EVAL-01 is orphaned in plan metadata but satisfied by the 35-case final golden set. |

**Score:** 23/23 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `evaluation/golden/rag_cases.jsonl` | RAG golden set | VERIFIED | Exists, 14 valid JSONL cases, required fields and categories present. |
| `evaluation/golden/agent_cases.jsonl` | Agent golden set | VERIFIED | Exists, 35 valid JSONL cases across 10 categories, all D-01e fields present. |
| `evaluation/golden/MATCHING_RULES.md` | Chinese matching rules | VERIFIED | Documents intent/risk/approval/amount/response matching and FakeLLM routing contract. |
| `scripts/validate_golden_seeds.py` | Seed reference validator | VERIFIED | Parses and passes against current golden set. |
| `scripts/eval_rag.py` | RAG evaluator | VERIFIED | DB-backed Hit@5/fallback scorer with JSON output and 0.85 thresholds. |
| `scripts/eval_agent.py` | Agent evaluator | VERIFIED | CI/live modes, metrics, graph contract gate, latency/token fields, JSON output. |
| `scripts/eval_all.py` | Unified evaluator | VERIFIED | Imports both evaluators, builds unified report, writes JSON/Markdown, exits 0/1. |
| `evaluation/reports/.gitkeep` | Reports directory placeholder | VERIFIED | Exists. Generated reports are local outputs, not committed artifacts. |
| `.github/workflows/ci.yml` | CI baseline | VERIFIED | Valid workflow with lint and unit-test jobs only. |
| `scripts/demo_phase6.sh` | Reproducible demo script | VERIFIED | Syntax-valid, executable flow with fail-fast assertions across 7 scenarios. |
| `README.md` | Interview README | VERIFIED | Required sections, diagrams, quick start, eval summary, docs links. |
| `docs/demo-walkthrough.md` | Demo guide | VERIFIED | Seven annotated scenarios and talking points. |
| `docs/evaluation.md` | Evaluation methodology | VERIFIED | Golden sets, metrics, thresholds, report format, CI/local split. |
| `docs/architecture.md` | Architecture guide | VERIFIED | Current stack, graph, node descriptions, data flow, trace persistence. |
| `docs/security-and-permission.md` | Security guide | VERIFIED | RBAC, approvals, audit, tenant isolation, risk rules. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `evaluation/golden/agent_cases.jsonl` | `scripts/seed_demo.py` | Seed IDs | VERIFIED | `scripts/validate_golden_seeds.py` passed. |
| `scripts/eval_all.py` | `scripts/eval_rag.py` | `run_rag_eval()` import | VERIFIED | Import exists at lines 25-26. |
| `scripts/eval_all.py` | `scripts/eval_agent.py` | `run_agent_eval()` import | VERIFIED | Import exists at lines 23-24. |
| `scripts/eval_all.py` | `evaluation/reports/latest.json` | Default output write | VERIFIED | `DEFAULT_OUTPUT` and `write_text(json.dumps(...))` present; SDK pattern miss was manually checked. |
| `scripts/eval_all.py` | `evaluation/reports/latest.md` | Markdown render | VERIFIED | `DEFAULT_MARKDOWN`, `render_markdown()`, and `markdown_path.write_text(...)` present. |
| `.github/workflows/ci.yml` | lint/test commands | Direct uv commands | VERIFIED | Workflow runs Ruff check, Ruff format check, and pytest unit command. |
| `scripts/demo_phase6.sh` | `/api/v1/agent/chat` | curl POST | VERIFIED | Preflight and scenarios 2-4 post to the chat endpoint. |
| `scripts/demo_phase6.sh` | `/api/v1/approvals/{id}/decide` | curl POST | VERIFIED | Permission denied and rejection scenarios use real captured `approval_id`. |
| `scripts/demo_phase6.sh` | `/api/v1/agent-runs/{run_id}/trace` | curl GET | VERIFIED | Trace scenario uses captured `LAST_RUN_ID`. |
| `README.md` | docs files | Markdown links | VERIFIED | README links demo walkthrough, evaluation, architecture, and security docs. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/eval_rag.py` | `cases`, `result`, `report` | JSONL golden set, `Retriever.search(...)`, DB-backed tenant/policy chunks | Yes | VERIFIED |
| `scripts/eval_agent.py` | `cases`, `results`, `graph_contract_failures`, `report` | JSONL golden set, deterministic CI state for all cases, compiled LangGraph contract checks for representative categories, live mode graph for real runs | Yes | VERIFIED |
| `scripts/eval_all.py` | `rag_eval_summary`, `agent_eval_summary`, `report` | `run_rag_eval()` and `run_agent_eval()` imports | Yes | VERIFIED |
| `scripts/demo_phase6.sh` | `AGENT_TOKEN`, `MANAGER_TOKEN`, `APPROVAL_ID`, `LAST_RUN_ID` | Auth/chat/approval/trace API responses parsed with `jq` | Yes, when local API stack is running | VERIFIED |
| `.github/workflows/ci.yml` | CI jobs | GitHub push/PR triggers | Yes | VERIFIED |
| README/docs | Markdown content and links | Checked-in docs and script paths | Static documentation | VERIFIED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Golden-set counts/schema/category coverage | `uv run python -c "...jsonl validation..."` | RAG 14, agent 35, all categories, no missing fields, no duplicate IDs | PASS |
| Seed references are valid | `uv run python scripts/validate_golden_seeds.py` | `SEED VALIDATION PASSED` | PASS |
| Eval scripts parse | `uv run python -c "import ast; ..."` | `syntax OK` | PASS |
| Unified Markdown is rendered from JSON object | `uv run python -c "from scripts.eval_all import ..."` | `pass 40` | PASS |
| Demo script syntax | `bash -n scripts/demo_phase6.sh` | Exit 0 | PASS |
| Agent evaluator graph contract | Orchestrator: `uv run python scripts/eval_agent.py --output /tmp/moca-agent-eval-final.json` | `status=pass`, `graph_contract.status=pass`, `failures=[]` | PASS |
| Lint baseline | Orchestrator: `uv run ruff check .` | Passed | PASS |
| Format baseline | Orchestrator: `uv run ruff format --check .` | Passed | PASS |
| Unit-test baseline | Orchestrator: `uv run pytest tests/ -x --ignore=tests/integration -q --tb=short` | 164 passed, 1 warning | PASS |
| Schema drift | Orchestrator: `gsd-sdk query verify.schema-drift 06` | valid true, no issues | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| EVAL-03 | 06-01, 06-02 | Evaluate citation accuracy | SATISFIED | Agent evaluator computes `citation_rate` from expected evidence doc keys; RAG evaluator scores expected chunks/docs. |
| EVAL-04 | 06-01, 06-02 | Evaluate tool selection accuracy | SATISFIED | Agent evaluator computes `tool_selection_accuracy` from expected vs actual/summarized tools. |
| EVAL-06 | 06-01, 06-02 | Evaluate task completion rate | SATISFIED | Agent evaluator computes `task_completion_rate` via final-status matching. |
| EVAL-07 | 06-02, 06-04 | Evaluate average latency and token cost | SATISFIED | Live mode records latency/tokens; CI mode reports `null`/`0` and docs explain the distinction. |
| INFR-07 | 06-02, 06-04 | Golden-set auto scoring with JSON/Markdown reports | SATISFIED | `eval_rag.py`, `eval_agent.py`, and `eval_all.py` produce JSON; unified runner renders Markdown. |
| INFR-08 | 06-03 | CI lint + unit tests; local integration/eval scripts | SATISFIED | CI workflow runs Ruff and pytest; Makefile exposes local eval/demo targets. |
| EVAL-01 | Orphaned note in REQUIREMENTS.md | Final 25-40 case golden set | SATISFIED | Not listed in Phase 6 plan requirements, but the 35-case agent set satisfies the deferred final-set intent. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/eval_agent.py` | 354 | `return []` | Info | Expected branch for permission-denied cases, where graph nodes should be empty because denial happens before graph entry. Not a stub. |
| `README.md` | 81 | Tool selection target shown as `>= 90%` while script/docs threshold is `>= 85%` | Info | Documentation consistency note only; requirement is to evaluate tool selection, and authoritative thresholds in `scripts/eval_agent.py` and `docs/evaluation.md` are 0.85. |

### Human Verification Required

None. The phase deliverables are static/evaluation/CI artifacts, and the provided orchestrator evidence plus local spot-checks cover the automated phase gate.

### Gaps Summary

No blocking gaps found. The phase goal is achieved: final golden sets exist and validate, evaluation scripts produce structured reports and enforce thresholds, the agent eval includes a compiled-graph contract gate, CI baseline passes, README/docs/demo materials exist and are linked, and code review findings are fixed.

---

_Verified: 2026-05-22T09:07:13Z_
_Verifier: Claude (gsd-verifier)_
