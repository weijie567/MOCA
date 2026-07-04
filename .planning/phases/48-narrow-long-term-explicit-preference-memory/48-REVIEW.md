---
phase: 48-narrow-long-term-explicit-preference-memory
reviewed: 2026-07-04T01:03:24Z
depth: deep
files_reviewed: 25
files_reviewed_list:
  - docs/architecture-overview.md
  - docs/contract-spec.md
  - docs/memory-contract-delta.md
  - src/agent/nodes/memory_write.py
  - src/api/routers/memory.py
  - src/api/schemas/memory.py
  - src/auth/jwt.py
  - src/auth/permissions.py
  - src/memory/long_term.py
  - src/memory/policy.py
  - src/memory/preference_capture.py
  - src/memory/repository.py
  - src/memory/schemas.py
  - src/memory/semantic_episode.py
  - src/memory/write_service.py
  - tests/agent/test_memory_write_node.py
  - tests/architecture/test_memory_contract_delta.py
  - tests/memory/test_long_term_memory_repository.py
  - tests/memory/test_long_term_memory_service.py
  - tests/memory/test_memory_policy.py
  - tests/memory/test_memory_write_service.py
  - tests/memory/test_phase48_long_term_preference_alignment.py
  - tests/memory/test_reviewed_memory_context_boundary.py
  - tests/memory/test_semantic_episode_projection.py
  - tests/test_memory_review_api.py
findings:
  critical: 1
  warning: 1
  info: 1
  total: 3
status: issues_found
---

# Phase 48: Code Review Report

**Reviewed:** 2026-07-04T01:03:24Z
**Depth:** deep
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Deep review covered the Phase 48 memory contract docs, write facade, long-term memory service/repository, admin/review API, policy rules, semantic episode projection, and related tests. The main risk is that the new multi-type write facade trusts explicit candidates already present in agent state too much: those candidates are Pydantic-shaped, but not bound back to the current run, tenant, actor path, or trusted merchant scope before write.

## Critical Issues

### CR-01: State-provided memory candidates can bypass tenant, run, and publish-source boundaries

**File:** `src/memory/write_service.py:74`
**Issue:** `propose_candidates()` appends `state["memory_write_candidates"]` after `_coerce_explicit_candidate()` validates only schema shape. `_state_explicit_candidate_allowed()` blocks `explicit_admin_preference` and tenant-scoped `explicit_user_preference`, but it does not require `candidate.tenant_id == state["tenant_id"]`, `candidate.run_id == state["current_run_id"]`, trusted merchant-scope membership, or a review-required source type for state-origin candidates. Because `apply_policy_and_write_candidate()` then routes long-term/case candidates unchanged to the underlying services, any upstream state writer can smuggle a `human_reviewed` long-term candidate, a cross-tenant candidate, or a tenant-scope published preference through the post-response memory side effect. This violates the contract that `memory_write_candidates` are a validated replace field and that tenant-scope/admin/human-reviewed publication is confined to trusted paths.
**Fix:**
```python
def _explicit_candidates(
    value: Any,
    *,
    state: Mapping[str, Any],
    requested_types: Sequence[str] | None,
    trusted_context: Any | None,
) -> list[MemoryWriteCandidate]:
    state_tenant_id = uuid.UUID(str(state["tenant_id"]))
    state_run_id = uuid.UUID(str(state["current_run_id"]))
    candidates: list[MemoryWriteCandidate] = []
    for item in _candidate_items(value):
        candidate = _coerce_explicit_candidate(item)
        if candidate is None or not _candidate_type_allowed(candidate, requested_types=requested_types):
            continue
        if not _state_candidate_identity_allowed(
            candidate,
            tenant_id=state_tenant_id,
            run_id=state_run_id,
            trusted_context=trusted_context,
        ):
            continue
        candidates.append(candidate)
    return candidates
```

Also make `_state_candidate_identity_allowed()` fail closed for long-term `human_reviewed` / `explicit_admin_preference`, require state-origin long-term candidates to be review-required unless built by the deterministic explicit-user helper, and add regression tests for cross-tenant, wrong-run, tenant-scope, and `human_reviewed` state candidates.

## Warnings

### WR-01: Hard-rule text can be published after review as long-term preference memory

**File:** `src/memory/long_term.py:224`
**Issue:** The explicit user/admin entry points validate soft preference text, but the long-term service/review boundary does not. `write_memory()` accepts `memory_kind="preference"` candidates without checking `validate_soft_preference_text()`, and `approve_memory()` only checks `pending.memory_kind != "preference"` before converting a pending candidate to `human_reviewed`. A `semantic_episode_candidate` containing text like "must refund below 10 yuan" can therefore enter `needs_review` and be approved into prompt-facing long-term memory, despite the contract forbidding policy rules, thresholds, and required execution behavior as long-term memory.
**Fix:** Reuse `validate_soft_preference_text()` at the service boundary. For initial writes, skip non-soft preferences with a policy event such as `reason_code="hard_rule_not_preference"`. For review approval, reject publication before changing source type:
```python
validation = validate_soft_preference_text(pending.content)
if not validation.valid:
    raise ValueError("long-term approval requires soft preference content")
```

Add tests that a hard-rule `semantic_episode_candidate` remains unapproved and unretrievable, and that service-level direct writes cannot publish hard-rule `human_reviewed` content.

## Info

### IN-01: Architecture overview still says Phase 48 explicit preference writes are not implemented

**File:** `docs/architecture-overview.md:98`
**Issue:** The architecture overview now documents reviewed explicit preference retrieval as a seam, but two current-implementation statements still say "`long_term_memory_retrieve` remains empty" and "Phase 48 explicit preference memory narrow write path not implemented" (`docs/architecture-overview.md:98` and `docs/architecture-overview.md:497`). That contradicts the new admin preference API, deterministic explicit user preference capture, and repository-filtered long-term preference retrieval implemented in this phase.
**Fix:** Update those current-state sentences to say the Phase 48 narrow explicit preference write path is implemented, while noting any remaining limitation precisely, such as the legacy graph node name or incomplete full memory-write pipeline.

---

_Reviewed: 2026-07-04T01:03:24Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
