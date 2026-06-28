---
phase: 31-memory-platform-boundary
reviewed: 2026-06-28T08:32:55Z
depth: deep
files_reviewed: 24
files_reviewed_list:
  - src/agent/context/projectors.py
  - src/agent/nodes/long_term_memory_retrieve.py
  - src/agent/nodes/memory_write.py
  - src/agent/nodes/receive_request.py
  - src/agent/nodes/reviewed_memory_context_retrieve.py
  - src/agent/nodes/session_context_load.py
  - src/agent/nodes/session_memory_load.py
  - src/agent/rag_context/verifier.py
  - src/agent/state.py
  - src/memory/__init__.py
  - src/memory/context_refs.py
  - src/memory/context_service.py
  - src/memory/schemas.py
  - src/memory/session_bundle.py
  - tests/agent/rag_context/test_authority_boundaries.py
  - tests/agent/test_memory_evidence_boundary.py
  - tests/agent/test_memory_write_node.py
  - tests/agent/test_nodes/test_receive_request.py
  - tests/agent/test_reviewed_memory_context_retrieve.py
  - tests/agent/test_session_memory_load.py
  - tests/memory/test_context_refs.py
  - tests/memory/test_reviewed_memory_context_boundary.py
  - tests/memory/test_session_memory_bundle.py
  - tests/memory/test_session_memory_isolation.py
findings:
  critical: 2
  warning: 1
  info: 0
  total: 3
status: issues_found
---

# Phase 31: Code Review Report

**Reviewed:** 2026-06-28T08:32:55Z
**Depth:** deep
**Files Reviewed:** 24
**Status:** issues_found

## Summary

本次 deep review 覆盖了 Phase 31 的 memory DTO、MemoryContextService facade、session/reviewed memory graph nodes、per-turn reset、prompt projector、memory write decision、verifier authority boundary，以及对应测试。

发现 2 个 Critical 和 1 个 Warning。核心风险集中在：contextual-only memory ref 仍可经 `citation_map` 被 verifier 当成 policy evidence；session memory write 会持久化未参与 PII 分类的 `unresolved_questions`；reviewed memory retrieval 会使用 classifier 的 `candidate_slots` 这个 LLM 输出建立 merchant retrieval scope。

## Critical Issues

### CR-01: contextual-only memory ref 可通过 citation_map 被当成 policy evidence 支持 claim

**File:** `src/agent/rag_context/verifier.py:573`

**Issue:** `_active_source_evidence_ids()` 只从 `contextual_sources` 收集 contextual memory ref id，然后无条件接收 `citation_map[*].source_evidence_ids` 和 `verifier_context.safe_refs`。同时 `_claim_evidence_snippets()` 在 `src/agent/rag_context/verifier.py:605` 也不排除来自 contextual memory citation 的 snippet。实测把 `reviewed_memory_ref.v1` 放入 `citation_map.evidence_ref`，并让 claim 引用同一个 `source_evidence_ids`，当前 verifier 返回 `supported`，`safe_support_refs == ["mem-ref-1"]`。这违反 Phase 31 D-11/D-12：memory refs/status refs 不能进入 evidence/citation authority path。

**Fix:**
```python
def _entry_is_contextual_memory(entry: Mapping[str, Any]) -> bool:
    evidence_ref = entry.get("evidence_ref")
    return isinstance(evidence_ref, Mapping) and _is_contextual_memory_ref_or_status(evidence_ref)


def _active_source_evidence_ids(context: Mapping[str, Any]) -> list[str]:
    evidence_ids: list[str] = []
    contextual_memory_ref_ids = set(_contextual_memory_ref_ids(context))
    for entry in _citation_entries(context):
        if _entry_is_contextual_memory(entry):
            contextual_memory_ref_ids.update(str(value) for value in entry.get("source_evidence_ids") or [])
            continue
        ...
    return _unique(ref for ref in evidence_ids if ref not in contextual_memory_ref_ids)


def _claim_evidence_snippets(claim: MaterialClaim, context: Mapping[str, Any]) -> list[dict[str, Any]]:
    contextual_memory_ref_ids = set(_contextual_memory_ref_ids(context))
    ...
    if str(snippet.get("evidence_id") or "") in contextual_memory_ref_ids:
        continue
```

Add a regression test where `citation_map["C1"]["evidence_ref"]` is `reviewed_memory_ref.v1` / `authority_class="contextual_only"` and the policy claim cites that id; expected outcome must not be `supported`, `safe_support_refs == []`, and reason codes include `memory_contextual_ref_not_policy_authority`. Run with `uv run pytest tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_memory_evidence_boundary.py -q`.

### CR-02: session memory write 会持久化未参与 PII 分类的 unresolved_questions

**File:** `src/agent/nodes/memory_write.py:140`

**Issue:** `_build_candidate()` 把 `_unresolved_questions(state)` 放进 `SessionMemoryWriteCandidate`，而 `MemoryService._insert()` 会把它写入 `unresolved_questions_json`（`src/memory/service.py:203`）。但 `_classify_pii()` 只检查 explicit slot values 和 `final_response`（`src/agent/nodes/memory_write.py:232`），没有检查同一候选里会被持久化的 `unresolved_questions`。最小复现中 `clarification_request.questions == ["请确认手机号 13800138000 是否可联系。"]` 时，结果仍是 `status="written"`、`pii_classification="none"`，敏感手机号进入候选并会被持久化。

**Fix:**
```python
def _build_candidate(state: AgentState) -> SessionMemoryWriteCandidate:
    ...
    explicit_slots = _explicit_slots(state, run_id, intent, now)
    unresolved_questions = _unresolved_questions(state)
    session_summary = _session_summary(intent, explicit_slots)
    pii_classification = _classify_pii(
        state,
        explicit_slots,
        unresolved_questions=unresolved_questions,
        session_summary=session_summary,
    )
    ...
        unresolved_questions=unresolved_questions,
        session_summary=session_summary,


def _classify_pii(
    state: AgentState,
    explicit_slots: dict[str, SessionSlotV1],
    *,
    unresolved_questions: list[str],
    session_summary: str | None,
) -> str:
    values = [slot.value for slot in explicit_slots.values()]
    values.extend(unresolved_questions)
    if session_summary:
        values.append(session_summary)
    ...
```

Add a regression in `tests/agent/test_memory_write_node.py` that injects phone/id/token text through `clarification_request.questions`, asserts the fake `MemoryService` is not called, and expects `memory_write_result.reason_code == "pii_blocked"`. Run with `uv run pytest tests/agent/test_memory_write_node.py -q`.

## Warnings

### WR-01: reviewed memory retrieval uses LLM candidate_slots to create merchant retrieval scope

**File:** `src/agent/nodes/reviewed_memory_context_retrieve.py:185`

**Issue:** `_current_turn_slots()` merges both `extracted_slots` and `candidate_slots`; `candidate_slots` is produced by `classify_intent` from LLM output (`src/agent/nodes/classify_intent.py:220`). Phase 31 plan explicitly says reviewed memory retrieval must not use LLM output to create or widen merchant scope. With `candidate_slots={"merchant_id": "merchant-from-llm"}` and empty `extracted_slots`, the node calls `LongTermMemoryService.retrieve_profile_memory(scopes=[("merchant", "merchant-from-llm")])`. Actor merchant scope is still checked, but the current resource scope can be selected by unvalidated LLM candidate data rather than explicit/current trusted slots.

**Fix:** Restrict reviewed retrieval scope inputs to post-extraction trusted fields only. Do not use `candidate_slots` in `reviewed_memory_context_retrieve`.
```python
def _current_turn_slots(state: AgentState) -> dict[str, Any]:
    extracted = state.get("extracted_slots")
    if not isinstance(extracted, Mapping):
        return {}
    return {str(key): value for key, value in extracted.items() if value not in (None, "")}
```

Add a test where `candidate_slots` contains an allowed merchant, `extracted_slots` is empty, and fake long-term/case services assert they are not called; expected fallback is `memory_scope_not_authority`. Run with `uv run pytest tests/agent/test_reviewed_memory_context_retrieve.py -q`.

---

_Reviewed: 2026-06-28T08:32:55Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
