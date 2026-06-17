---
phase: 08-knowledge-facade
reviewed: 2026-06-07T08:30:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - src/agent/nodes/assess_risk_and_approval.py
  - src/agent/nodes/final_response.py
  - src/agent/nodes/generate_recommendation.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/retrieve_policy_evidence.py
  - src/agent/state.py
  - src/agent/trace.py
  - src/api/routers/agent_runs.py
  - src/knowledge/__init__.py
  - src/knowledge/adapters.py
  - src/knowledge/citation.py
  - src/knowledge/config.py
  - src/knowledge/schemas.py
  - src/knowledge/service.py
  - src/knowledge/text_hash.py
  - src/rag/ingestion.py
  - src/repositories/policy_document_repo.py
  - tests/agent/test_nodes/test_generate_recommendation.py
  - tests/agent/test_nodes/test_retrieve_policy_evidence.py
  - tests/knowledge/test_facade_status.py
  - tests/knowledge/test_effective_time.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-06-07T08:30:00Z
**Depth:** standard
**Status:** issues_found

## Summary

Fresh review of the on-disk knowledge-facade code, cross-checked against the three findings from the prior review (07:18). Verification against current code:

- Prior WR-02 (effective-time filtering after candidate truncation): FIXED. `PolicyChunkRepository.search_similar` now applies `WHERE PolicyChunk.effective_date <= effective_date` inside the SQL before `LIMIT top_k` (src/repositories/policy_chunk_repo.py:71-72), and the adapter keeps a redundant in-memory guard (src/knowledge/adapters.py:96-98). Locked by `tests/knowledge/test_effective_time.py::test_effective_filter_precedes_top_k_truncation` and `::test_effective_date_passed_to_repository`.
- Prior WR-03 (`allow_partial_evidence` ignored): FIXED. `PolicyKnowledgeService.search` now downgrades `partial_evidence` to `no_evidence` with empty refs when the flag is false (src/knowledge/service.py:55-63). Covered by `tests/knowledge/test_facade_status.py::test_partial_evidence_suppressed_when_disallowed` and `::test_partial_evidence_preserved_when_allowed`.
- Prior WR-01 (recommendation node receives no policy content): STILL HOLDS. The 08-07 gap-closure did not touch it. Re-raised as WR-01 below.

Two warnings and one info item remain. No critical issues. No source files were modified during this review. Findings below are reasoned from code reading; I did not execute the test suite in this pass.

## Warnings

### WR-01: Recommendation generation never receives policy evidence text

**File:** `src/agent/nodes/generate_recommendation.py:73-101, 116-137`
**Issue:** The `generate_recommendation` node builds the LLM prompt from `EvidenceRefV1` projections only. `EvidenceRefV1` (src/knowledge/schemas.py:31-69) carries `text_hash` but no policy text/content. `_summarize_evidence` (lines 73-85) emits only `doc_key`, `chunk_id`, `evidence_id`, `policy_version`, `score`; `_allowed_citation_objects` (lines 88-100) emits `doc_key`, `chunk_id`, `evidence_id`, plus `title`/`section` that are never populated on `EvidenceRefV1` and resolve to `""`. The model is asked to produce a policy-grounded recommendation and cite evidence while seeing zero policy substance. `validate_membership` (src/knowledge/citation.py) is membership-only by design (D-C1/D-C2) and only checks that cited ids exist, so it cannot compensate. No layer supplies the policy text. This was flagged in the prior review and remains unaddressed after 08-07.
**Fix:** Carry the chunk text (or a bounded snippet) from the adapter into the recommendation prompt, kept out of the persisted/canonical `EvidenceRefV1` projection so the hash-only contract stays intact. Sketch:
```python
# retrieve_policy_evidence: attach transient text alongside canonical refs
new_refs = [
    {**ref.model_dump(), "text": chunk_text_by_id[ref.evidence_id]}
    for ref in result.evidence_refs
]
# generate_recommendation._summarize_evidence: include the text
items.append({..., "text": item.get("text") or ""})
```
Strip the transient `text` before persistence so `canonical_evidence_projection` and stored `evidence_refs` stay hash-only. Add an integration test whose recommendation depends on a distinctive rule present only in the retrieved policy text.

### WR-02: Partial citation failure persists a stale `citation_validation.is_valid=False` on an accepted recommendation

**File:** `src/agent/nodes/generate_recommendation.py:166-188`
**Issue:** When `validate_membership` returns `is_valid=False` because the single `rec-1` claim cites a mix of member and non-member evidence ids, the code drops the invalid ids and refs (lines 173-178) but only flips the action to `citation_invalid` when *all* refs were dropped (line 179). If at least one valid ref survives, `recommended_action` keeps the model's original value while `draft["citation_validation"]` is stored as the pre-drop result with `is_valid=False` (line 183) without re-validation. `final_response`/`_derive_final_status` (src/agent/trace.py:223-232) key off `recommended_action`, so the run is reported as `completed` while its persisted citation audit record claims the citations were invalid. The two existing tests cover only the all-pass and all-fail cases, not this mixed path.
**Fix:** Re-run membership validation on the surviving citations before persisting, so the stored record matches the emitted draft:
```python
if not draft["evidence_refs"]:
    draft["recommended_action"] = "citation_invalid"
    draft["missing_info"] = ["Citation membership validation failed"]
    draft["confidence"] = 0.0
else:
    claims = [{"claim_id": "rec-1", "claim_text": draft["reasoning_summary"],
               "cited_evidence_ids": cited_evidence_ids}]
    validation = validate_membership(claims, evidence_models)
draft["citation_validation"] = validation.model_dump()
```
Add a test where the model cites one valid and one invalid evidence id.

## Info

### IN-01: Redundant and overly broad exception tuple in node retry loops

**File:** `src/agent/nodes/generate_recommendation.py:203`, `src/agent/nodes/assess_risk_and_approval.py:274`
**Issue:** Both retry loops catch `(ValidationError, ValueError, TimeoutError, Exception)`. Since `Exception` is the base of the other three, the tuple is redundant, and the handler catches every non-system exception, masking programming errors (e.g. `KeyError`, `AttributeError`) as transient validation failures that get retried once then folded into a generic fallback draft.
**Fix:** Either narrow to the genuinely transient/validation cases (`except (ValidationError, ValueError, TimeoutError) as exc:`) and let unexpected errors propagate, or keep a single `except Exception as exc:` with a comment that the catch-all is intentional. Drop the redundant tuple members either way.

---

_Reviewed: 2026-06-07T08:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
