# MOCA Evaluation Methodology

## Overview

MOCA uses a two-layer evaluation approach:

1. **RAG retrieval quality** checks whether the policy retriever returns expected evidence chunks for Chinese refund, SOP, FAQ, boundary, and fallback questions.
2. **Agent end-to-end behavior** checks whether the workflow selects the right intent, calls the expected tools, requires approval for high-risk actions, preserves citations, and completes safety-critical paths.

The evaluation files are local project assets, not external services. Golden cases live under `evaluation/golden/`, scripts live under `scripts/`, and generated reports live under `evaluation/reports/`.

## Why FakeLLM (Deterministic Evaluation)

The default agent evaluation mode is deterministic. `scripts/eval_agent.py` uses FakeLLM-compatible structured outputs to validate graph contracts without calling a live model. This proves that the scoring harness, golden-set schema, route assertions, approval logic, permission checks, and report generation behave predictably.

FakeLLM mode validates workflow determinism, not model quality. It is useful for CI-compatible development because it avoids provider latency, cost, and network variance. Live model integration is still supported through `make eval-live`, which requires `DASHSCOPE_API_KEY` and is intended as an optional local smoke test.

`scripts/seed_demo.py --reset` keeps business data reproducible across runs, including demo tenants, users, orders, refund cases, tickets, and policy documents.

## Golden Set Design

### RAG Golden Set

Path: `evaluation/golden/rag_cases.jsonl`

The RAG set contains 14 cases across five categories:

| Category | Purpose |
| --- | --- |
| `refund_rule` | Tests retrieval of refund policy rules |
| `sop` | Tests support procedure and operational guidance retrieval |
| `faq` | Tests common merchant/support questions |
| `boundary` | Tests edge cases near policy boundaries |
| `fallback` | Tests no-evidence behavior for unsupported queries |

Each case records the query, expected document IDs, expected chunk IDs, category, expected hit depth, and whether the correct result is fallback.

### Agent Golden Set

Path: `evaluation/golden/agent_cases.jsonl`

The agent set contains 35 cases across ten categories:

| Category | Purpose |
| --- | --- |
| `normal_policy_qa` | Evidence-backed answers to policy questions |
| `refund_troubleshooting` | Order/refund/ticket lookup plus policy reasoning |
| `compensation_suggestion` | Compensation recommendations across risk levels |
| `approval_required` | High-risk actions that must interrupt for approval |
| `permission_denied` | API-level denial for insufficient scope or role |
| `approval_approved` | Resume path after manager approval |
| `approval_rejected` | Resume path after manager rejection |
| `missing_context` | Missing order/refund details requiring clarification |
| `low_confidence_no_evidence` | Unsupported questions that should not hallucinate |
| `tool_failure_or_not_found` | Invalid IDs and controlled tool failure outcomes |

Safety-critical categories, especially approval, permission, and rejection paths, require a 100% pass rate. Matching details for Chinese text normalization, seed IDs, and expected substrings are documented in `evaluation/golden/MATCHING_RULES.md`.

## Metrics

### RAG Metrics

- **Hit@5:** A case passes when at least one expected `chunk_id` appears in the top five retrieved evidence chunks.
- **Fallback Accuracy:** A fallback case passes when retrieval returns a no-evidence status instead of irrelevant evidence.

### Agent Metrics

- **Intent Accuracy:** The evaluated intent matches `expected_intent`.
- **Tool Selection Accuracy:** Expected tools are contained in the actual tool-call set.
- **Task Completion Rate:** The run reaches the expected final status.
- **Citation Rate:** Expected evidence document keys are present where evidence is required.
- **Safety Critical Pass Rate:** Approval, rejection, and permission-denied categories pass all required checks.
- **Average Latency:** Measured in live mode; reported as `null` in deterministic CI mode.
- **Token Cost:** Meaningful only in live mode; deterministic CI mode reports token usage as `0`.

## Thresholds

| Metric | Threshold | Rationale |
| --- | ---: | --- |
| RAG Hit@5 | >= 85% | Retrieval must reliably surface expected policy evidence in the top five results |
| RAG fallback accuracy | >= 85% | Unsupported questions must avoid fabricated evidence |
| Agent intent accuracy | >= 90% | Routing mistakes directly affect tool use and risk assessment |
| Agent tool selection accuracy | >= 85% | The workflow must call required business tools before answering |
| Agent citation rate | >= 85% | Evidence-backed answers must preserve policy grounding |
| Safety critical pass rate | == 100% | Approval, rejection, and permission checks cannot fail silently |

## Running Evaluations

```bash
make eval
```

Runs the unified evaluator and writes `evaluation/reports/latest.json` plus `evaluation/reports/latest.md`.

```bash
make eval-rag
```

Runs only the RAG evaluator. This path is DB-backed and requires migrated, seeded PostgreSQL/pgvector data.

```bash
make eval-agent
```

Runs only the deterministic agent evaluator in CI-compatible mode.

```bash
make eval-live
```

Runs agent evaluation in live mode. This requires `DASHSCOPE_API_KEY` and is optional local validation, not a Phase 6 CI pass/fail requirement.

```bash
make eval-baseline
```

Saves the current unified report as `evaluation/reports/baseline.json` for future comparison.

## Phase 35 Replay/Eval Gates

Phase 35 replay/eval gate artifacts are discoverable through these paths:

- `eval/replay/phase35-coverage-matrix.v1.json`
- `eval/replay/dev-contract-manifest.v1.json`
- `eval/replay/release-gate.v1.json`
- `eval/replay/release-smoke-cases.v1.json`
- `eval/replay/monitoring-gate.v1.json`

Approved Phase 35 command entrypoints:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/replay/test_phase35_coverage_matrix.py -q --tb=short
```

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase35_release_monitoring_manifests.py -q --tb=short
```

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/eval/test_phase35_replay_eval_gates.py tests/architecture/test_phase35_replay_eval_boundaries.py -q --tb=short
```

The `dev-contract` gates block Phase 35. Release gate status
`statistical_gate_not_demonstrated` and monitoring statuses `pending`,
`not_applicable`, or `sample_only` do not block Phase 35 unless they expose a
deterministic forbidden-behavior regression.

Phase 35 includes limited release smoke cases for `intent_hard_negatives`,
`rag_claim_support`, and `approval_action_safety`. These smoke cases do not
claim production-level sample size, release-scale statistical thresholds, or
production telemetry has been demonstrated.

## Report Format

`evaluation/reports/latest.json` is the source of truth. It contains:

- `overall_status`
- `generated_at`
- `rag_eval_summary`
- `agent_eval_summary`
- `thresholds`
- `failed_cases`
- `warning_cases`
- `metrics`
- `baseline_comparison`

`evaluation/reports/latest.md` is rendered from the JSON report for human review. It is not recomputed independently, so CI or local automation should rely on the JSON status and process exit code.

If `evaluation/reports/baseline.json` is missing, the unified runner records a warning rather than failing the evaluation.

## CI Integration

The GitHub Actions workflow runs lint and unit tests only:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/ -x --ignore=tests/integration -q --tb=short
```

Evaluation scripts remain local commands because the full RAG path requires a migrated and seeded database with pgvector. This keeps CI pure, fast, and independent of DB, embedding, and LLM services while preserving full local evaluation coverage.
