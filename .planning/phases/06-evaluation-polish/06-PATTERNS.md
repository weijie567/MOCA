# Phase 6: Evaluation & Polish - Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** 14
**Analogs found:** 10 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `evaluation/golden/rag_cases.jsonl` | config | — | `eval/golden_rag_queries.jsonl` | exact (migrate) |
| `evaluation/golden/agent_cases.jsonl` | config | — | `evals/golden_set_phase3.json` | exact (expand) |
| `scripts/eval_rag.py` | utility | batch | `scripts/eval_rag_hit_at_5.py` | exact (refactor) |
| `scripts/eval_agent.py` | utility | batch | `scripts/smoke_agent_live.py` | role-match |
| `scripts/eval_all.py` | utility | batch | `scripts/eval_rag_hit_at_5.py` | role-match |
| `scripts/demo_phase6.sh` | utility | request-response | — | no analog |
| `.github/workflows/ci.yml` | config | — | — | no analog |
| `README.md` | config | — | `README.md` (existing) | exact (rewrite) |
| `docs/demo-walkthrough.md` | config | — | — | no analog |
| `docs/evaluation.md` | config | — | — | no analog |
| `docs/architecture.md` | config | — | — | no analog |
| `docs/security-and-permission.md` | config | — | — | no analog |
| `evaluation/reports/latest.json` | config | — | — | no analog (generated) |
| `evaluation/reports/latest.md` | config | — | — | no analog (generated) |

## Pattern Assignments

### `scripts/eval_rag.py` (utility, batch)

**Analog:** `scripts/eval_rag_hit_at_5.py`

**Imports pattern** (lines 1-31):
```python
"""RAG Hit@5 evaluation script.

Usage:
    uv run python scripts/eval_rag.py
    uv run python scripts/eval_rag.py --golden-set evaluation/golden/rag_cases.jsonl
    uv run python scripts/eval_rag.py --threshold 0.85
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Tenant
from src.db.session import SessionLocal
from src.rag.embedder import EmbeddingService
from src.rag.retriever import Retriever
from src.rag.schemas import RetrievalResult
from src.repositories.policy_chunk_repo import PolicyChunkRepository
```

**CLI argument pattern** (lines 51-62):
```python
def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAG Hit@5 Evaluation")
    parser.add_argument("--golden-set", default=DEFAULT_GOLDEN_SET, help="Path to JSONL golden set")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Minimum accepted score")
    parser.add_argument("--tenant-id", help="Tenant UUID (default: first active tenant)")
    parser.add_argument(
        "--diagnostic-top-k",
        type=int,
        default=5,
        help="Diagnostic-only evidence depth for failed cases; official scoring remains top_k=5",
    )
    return parser
```

**JSONL loading pattern** (lines 65-66):
```python
def _load_cases(path: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
```

**Per-category scoring pattern** (lines 69-74):
```python
def _record_category(per_category: dict[str, dict[str, int]], category: str, hit: bool) -> None:
    if category not in per_category:
        per_category[category] = {"total": 0, "hit": 0}
    per_category[category]["total"] += 1
    if hit:
        per_category[category]["hit"] += 1
```

**Case scoring pattern** (lines 91-115):
```python
def _score_case(case: dict[str, Any], result: RetrievalResult) -> dict[str, Any]:
    expected_chunks = list(case.get("expected_chunk_ids", []))
    expected_docs = set(case.get("expected_doc_ids", []))
    got_chunks = [evidence.chunk_id for evidence in result.evidence]
    got_docs = {evidence.doc_key for evidence in result.evidence}
    expected_doc_id_hit = bool(expected_docs & got_docs)

    if case.get("should_fallback"):
        hit = result.retrieval_status == "no_evidence"
        reason = "fallback_no_evidence" if hit else "should_fallback_but_got_results"
    else:
        hit = bool(set(expected_chunks) & set(got_chunks))
        reason = "expected_chunk_in_top5" if hit else "expected_chunk_not_in_top5"

    return {
        "hit": hit,
        "reason": reason,
        ...
    }
```

**Exit code pattern** (lines 236-241):
```python
    if hit_at_5 < args.threshold or fallback_acc < args.threshold:
        print("\nFAIL: Below threshold")
        sys.exit(1)

    print("\nPASS")
    sys.exit(0)
```

**Async main entry pattern** (lines 244-245):
```python
if __name__ == "__main__":
    asyncio.run(main())
```

**Key refactor delta:** Output JSON report to `evaluation/reports/` instead of print-only. Change default golden set path to `evaluation/golden/rag_cases.jsonl`. Add `--output` arg for JSON report path.

---

### `scripts/eval_agent.py` (utility, batch)

**Analog:** `scripts/smoke_agent_live.py`

**Imports pattern** (lines 11-18):
```python
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime
```

**Deterministic ID pattern** (lines 21-25):
```python
MOCA_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0d02b2c3d479")

def deterministic_id(entity_type: str, key: str) -> uuid.UUID:
    return uuid.uuid5(MOCA_NAMESPACE, f"{entity_type}:{key}")
```

**Graph invocation pattern** (lines 84-104):
```python
async with AsyncPostgresSaver.from_conn_string(settings.checkpointer_database_url) as checkpointer:
    await checkpointer.setup()
    graph = build_graph(checkpointer)

    for i, case in enumerate(test_cases, 1):
        async with session_factory() as session:
            scoped_thread_id = f"{tenant_id}:{user_id}:{case['thread_id']}:{run_suffix}"
            config = {"configurable": {"thread_id": scoped_thread_id, "session": session}}
            input_state = {
                "user_query": case["query"],
                "thread_id": case["thread_id"],
                "tenant_id": tenant_id,
                "user_id": user_id,
                "role": "support_agent",
            }
            result = await asyncio.wait_for(
                graph.ainvoke(input_state, config),
                timeout=case_timeout_seconds,
            )
```

**Assertion pattern** (lines 106-126):
```python
summary = build_trace_summary(result["current_run_id"], result, 0)
if case.get("expected_intent") and result.get("current_intent") != case["expected_intent"]:
    _print_case_diagnostics(result)
    raise AssertionError(
        f"intent mismatch: expected {case['expected_intent']}, got {result.get('current_intent')}"
    )
if (
    case.get("expected_final_status")
    and summary["final_status"] != case["expected_final_status"]
):
    _print_case_diagnostics(result)
    raise AssertionError(
        "final status mismatch: "
        f"expected {case['expected_final_status']}, got {summary['final_status']}"
    )
```

**Diagnostics pattern** (lines 28-37):
```python
def _print_case_diagnostics(result: dict) -> None:
    diagnostic = {
        "intent": result.get("current_intent"),
        "recommendation_draft": result.get("recommendation_draft"),
        "risk_assessment": result.get("risk_assessment"),
        "node_errors": result.get("node_errors"),
        "retrieved_evidence_status": (result.get("retrieved_evidence") or {}).get("data", {}).get("retrieval_status"),
        "retrieved_evidence_count": len((result.get("retrieved_evidence") or {}).get("data", {}).get("evidence") or []),
    }
    print(json.dumps(diagnostic, ensure_ascii=False, indent=2, default=str), flush=True)
```

**Key adaptation:** Use FakeLLM (from `tests/agent/conftest.py`) + MemorySaver instead of real LLM + Postgres for CI path. Load cases from `evaluation/golden/agent_cases.jsonl`. Output JSON report. Add scoring for new fields: expected_tools, expected_approval_required, expected_response_contains, must_not_contain.

---

### `scripts/eval_all.py` (utility, batch)

**Analog:** `scripts/eval_rag_hit_at_5.py` (orchestration pattern)

**Pattern:** Thin orchestrator that imports and calls `eval_rag.py` and `eval_agent.py` programmatically, merges results into a unified JSON report, writes to `evaluation/reports/latest.json` + renders `latest.md` from JSON.

**Entry pattern:**
```python
"""Unified evaluation runner.

Usage:
    uv run python scripts/eval_all.py
    uv run python scripts/eval_all.py --output evaluation/reports/latest.json

Exits 0 if all thresholds pass, 1 otherwise.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
```

**Exit code pattern** (same as eval_rag):
```python
if overall_status == "fail":
    sys.exit(1)
sys.exit(0)
```

---

### `evaluation/golden/agent_cases.jsonl` (config, data)

**Analog:** `evals/golden_set_phase3.json`

**Existing case structure** (per case):
```json
{
  "id": "GS-01",
  "category": "policy_qa",
  "query": "平台的退款超时处理规则是什么？",
  "thread_id": "gs-thread-01",
  "expected_intent": "policy_qa",
  "expected_final_status": "completed",
  "expected_evidence_present": true,
  "expected_tools_called": [],
  "notes": "Standard refund timeout policy question; answer must cite policy evidence."
}
```

**New fields to add per D-01e:**
```json
{
  "id": "GS-16",
  "category": "approval_required",
  "query": "...",
  "thread_id": "gs-thread-16",
  "expected_intent": "compensation_suggestion",
  "expected_final_status": "completed",
  "expected_evidence_present": true,
  "expected_tools_called": ["get_order"],
  "expected_approval_required": true,
  "expected_permission_result": "granted",
  "expected_evidence_doc_keys": ["high_amount_approval"],
  "expected_response_contains": ["审批"],
  "must_not_contain": [],
  "notes": "..."
}
```

**Format change:** Convert from JSON array to JSONL (one JSON object per line).

---

### `evaluation/golden/rag_cases.jsonl` (config, data)

**Analog:** `eval/golden_rag_queries.jsonl` — direct copy, no content change.

**Case structure:**
```json
{"query": "买家申请七天无理由退款...", "expected_doc_ids": ["refund_policy"], "expected_chunk_ids": ["refund_policy_001"], "category": "refund_rule", "difficulty": "easy", "should_fallback": false}
```

---

### `README.md` (config, rewrite)

**Analog:** existing `README.md`

**Current structure** (30 lines, minimal):
```markdown
# MOCA

MOCA is a demo-first backend for merchant refund operations...

## Quick Start
## Local Commands
## Demo Accounts
```

**Target structure per D-04e:** Project Overview, Key Capabilities, Architecture Diagram (Mermaid), 10-Minute Demo, Evaluation Summary, Quick Start, Repository Structure, Technical Notes, Current Scope and Limitations.

---

## Shared Patterns

### FakeLLM for CI Isolation
**Source:** `tests/agent/conftest.py` (lines 11-35)
**Apply to:** `scripts/eval_agent.py` (CI-compatible path)
```python
class FakeLLM:
    """Deterministic fake LLM for CI."""

    def __init__(self, response_dict: dict[str, Any]):
        self._response = response_dict

    async def ainvoke(self, messages, **kwargs):
        from langchain_core.messages import AIMessage
        return AIMessage(content=json.dumps(self._response, ensure_ascii=False))

    def with_structured_output(self, schema):
        fake = self
        class _Wrapper:
            async def ainvoke(self, messages, **kwargs):
                if issubclass(schema, BaseModel):
                    return schema.model_validate(fake._response)
                return fake._response
        return _Wrapper()
```

### Trace Summary Construction
**Source:** `src/agent/trace.py` (lines 187-216)
**Apply to:** `scripts/eval_agent.py` (for extracting assertion targets)
```python
def build_trace_summary(run_id: str, final_state: dict[str, Any], total_latency_ms: int) -> dict[str, Any]:
    trace_steps = final_state.get("trace_steps") or []
    nodes_executed = [str(step.get("node") or "unknown") for step in trace_steps]
    tools_called: list[str] = []
    for step in trace_steps:
        tools_called.extend(str(tool) for tool in (step.get("tools_called") or []))
        if step.get("tool_name"):
            tools_called.append(str(step["tool_name"]))
    ...
    return {
        "run_id": run_id,
        "intent": final_state.get("current_intent") or "unknown",
        "nodes_executed": nodes_executed,
        "tools_called": tools_called,
        "evidence_count": evidence_count,
        "risk_level": risk.get("risk_level") or "unknown",
        "total_latency_ms": total_latency_ms,
        "final_status": _derive_final_status(final_state),
    }
```

### Deterministic ID Generation
**Source:** `scripts/seed_demo.py` (lines 33-37)
**Apply to:** `scripts/eval_agent.py`, `scripts/demo_phase6.sh`
```python
MOCA_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0d02b2c3d479")

def deterministic_id(entity_type: str, key: str) -> uuid.UUID:
    return uuid.uuid5(MOCA_NAMESPACE, f"{entity_type}:{key}")
```

### Async DB Session Pattern
**Source:** `scripts/eval_rag_hit_at_5.py` (lines 185-192)
**Apply to:** `scripts/eval_rag.py`, `scripts/eval_agent.py`
```python
async with SessionLocal() as session:
    tenant_id = await resolve_tenant_id(session, args.tenant_id)
    retriever = Retriever(
        chunk_repo=PolicyChunkRepository(session),
        embedder=EmbeddingService(),
    )
```

### Script Docstring + argparse Convention
**Source:** `scripts/eval_rag_hit_at_5.py` (lines 1-11)
**Apply to:** All new scripts
```python
"""[Script description].

Usage:
    uv run python scripts/[name].py
    uv run python scripts/[name].py --[option] [value]

Requires [prerequisites].
Exits non-zero if [failure condition].
"""
```

### Makefile Command Convention
**Source:** `Makefile`
**Apply to:** Add new targets for eval
```makefile
eval:
	uv run python scripts/eval_all.py

eval-rag:
	uv run python scripts/eval_rag.py

eval-agent:
	uv run python scripts/eval_agent.py
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `scripts/demo_phase6.sh` | utility | request-response | No shell scripts exist in the project; curl-based demo is new pattern |
| `.github/workflows/ci.yml` | config | — | No CI configuration exists yet; create from scratch |
| `docs/demo-walkthrough.md` | config | — | No docs/ directory exists; new documentation layer |
| `docs/evaluation.md` | config | — | No docs/ directory exists |
| `docs/architecture.md` | config | — | No docs/ directory exists |
| `docs/security-and-permission.md` | config | — | No docs/ directory exists |
| `evaluation/reports/latest.json` | config | — | Generated output from eval_all.py; schema defined in D-02e |
| `evaluation/reports/latest.md` | config | — | Generated output rendered from JSON |

**For files with no analog:** Planner should use RESEARCH.md patterns (Section 9 for demo script, Section 5 for CI) and D-02e for report JSON schema.

---

## Metadata

**Analog search scope:** `scripts/`, `eval/`, `evals/`, `tests/agent/`, `src/agent/`, `Makefile`, `README.md`
**Files scanned:** 8 analog files read in full
**Pattern extraction date:** 2026-05-19
