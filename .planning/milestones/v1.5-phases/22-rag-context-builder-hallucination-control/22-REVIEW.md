---
phase: 22-rag-context-builder-hallucination-control
reviewed: 2026-06-19T15:19:45Z
depth: deep
files_reviewed: 6
files_reviewed_list:
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/rag_context/metrics.py
  - tests/agent/test_phase22_action_boundary.py
  - tests/agent/test_nodes/test_generate_recommendation.py
  - evaluation/golden/phase22_hallucination_cases.jsonl
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-06-19T15:19:45Z
**Depth:** deep
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Deep review covered the Phase 22 follow-up files from commit `d49bc85`, including recommendation verification, risk/action boundary clearing, hallucination metrics, focused regressions, and golden cases. The previously reported action dependency, missing-session, stale snapshot, canonical latest/hash/freshness, and non-allow action-boundary gaps are closed in the reviewed code.

Focused verification passed:

- `uv run pytest tests/agent/test_phase22_action_boundary.py tests/agent/test_nodes/test_generate_recommendation.py`
- `uv run pytest tests/agent/rag_context/test_routing.py tests/agent/test_phase22_recommendation_integration.py tests/agent/test_phase22_final_response.py -q`
- `uv run python scripts/eval_phase22_hallucination.py --dataset evaluation/golden/phase22_hallucination_cases.jsonl --fail-thresholds`

One remaining warning is an eval/runtime fidelity gap for OCR/source risk labels: the deterministic golden case covers it, but the production-verifier path can still miss the label shape used by that case.

## Warnings

### WR-01: Production-verifier path ignores OCR risk labels used by the golden case

**File:** `src/agent/rag_context/metrics.py:137`

**Issue:** `_evaluate_production_hallucination_case()` always calls `ContextBuilder.build(..., risk_hints=[])`, while the OCR trap in `evaluation/golden/phase22_hallucination_cases.jsonl:8` represents the safety signal as `input.evidence_refs[].risk_labels=["ocr_low_confidence"]`. The production recommendation path has the same dependency shape at `src/agent/nodes/generate_recommendation.py:632`: it only forwards `state["risk_hints"]` and does not derive safe labels from retrieved evidence items.

That means the current eval passes because `P22-HC-008` uses the deterministic adapter, not the production-verifier adapter. When the same case shape is run through the production adapter with evidence text/canonical metadata, the verifier returns `supported -> allow` instead of `ocr_low_confidence -> manual_review`. This can mask a real safety-routing regression for low-confidence OCR/source-label evidence.

**Fix:** Normalize safe evidence-level labels into `risk_hints` before building production verifier contexts, and add a production-verifier regression for OCR low-confidence routing.

```python
SAFE_RISK_LABELS = {"ocr_low_confidence", "provenance_available", "source_locator_available", "stale_evidence"}

def _risk_hints_from_evidence_refs(refs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    hints = []
    for ref in refs:
        labels = [str(label) for label in ref.get("risk_labels") or [] if str(label) in SAFE_RISK_LABELS]
        if labels and ref.get("evidence_id"):
            hints.append({"evidence_id": str(ref["evidence_id"]), "labels": labels})
    return hints
```

Use that helper in `metrics.py` instead of `risk_hints=[]`, and mirror the same derivation in `generate_recommendation` or ensure the upstream retrieval node always populates `state["risk_hints"]`. Add a golden `evaluation_path: production_verifier` OCR case asserting `expected_verifier_status: ocr_low_confidence` and `expected_route: manual_review`.

---

_Reviewed: 2026-06-19T15:19:45Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
