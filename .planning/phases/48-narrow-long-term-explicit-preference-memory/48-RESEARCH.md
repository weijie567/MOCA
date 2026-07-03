# Phase 48: Narrow Long-Term Explicit Preference Memory - Research

**Researched:** 2026-07-04
**Mode:** local orchestrator fallback
**Reason:** The current client did not expose multi-agent spawn tools for `gsd-phase-researcher`; this file is based on direct repository inspection with `rg`/`sed` and the locked Phase 48 discussion context.

## Research Complete

Phase 48 should be implemented as a semantic and runtime narrowing of the existing `long_term_memories` store, not as a table migration. The current table/model identity is already tied to memory identity, tombstone, review, replay, and eval contracts. The safe implementation path is:

1. Update the normative contract first so `docs/contract-spec.md` Section 13.3 no longer describes broad durable facts or deterministic tool facts as long-term memory.
2. Narrow long-term write policy and service insertion so only preference candidates can create long-term rows.
3. Keep the existing `memory_write_candidates` seam, but add deterministic explicit user preference capture before write.
4. Add a minimal admin-only preference save API rather than overloading pending review.
5. Keep `needs_long_term_memory` / `memory_context_load` retrieval, but filter retrieved rows to published preference rows with source types `explicit_user_preference`, `explicit_admin_preference`, or `human_reviewed`.
6. Preserve `long_term_memories`, `memory_type='long_term_fact'`, tombstone identity, supersede identity, and legacy graph node aliases.

## Current Code Facts

### Contract And Documentation

- `docs/contract-spec.md` Section 13.3 currently describes long-term memory as durable scoped facts and mentions deterministic tool facts marked durable. This conflicts with Phase 48.
- `docs/memory-contract-delta.md` still documents `durable_profile_fact`, `merchant_pattern`, and `operational_constraint` as long-term semantics and says deterministic durable tool results may auto-publish. This must be superseded.
- `docs/architecture-overview.md` already contains a high-level phrase for long-term explicit preference memory, but some older node text still calls `long_term_memory_retrieve` an empty or future adapter.
- `tests/architecture/test_memory_contract_delta.py` currently asserts broad durable semantics. It must be updated together with the docs so tests do not preserve the old target contract.

### Source Policy And Schemas

- `src/memory/policy.py` currently auto-approves long-term source types:
  - `explicit_user_preference`
  - `explicit_admin_preference`
  - `human_reviewed`
  - `deterministic_tool_result`
  - `confirmed_business_outcome`
  - `approved_approval_state`
- It also has durable source downgrades for current business objects. Phase 48 should remove this long-term durable-fact branch from the prompt-published path.
- `src/memory/schemas.py` still defines broad `LongTermMemoryKind = Literal["fact", "preference", "constraint", "pattern"]` and broad source types. The database check constraint also allows those kinds. A no-migration Phase 48 should preserve DB compatibility while setting `LongTermMemoryWriteCandidate.memory_kind` default to `preference` and enforcing preference-only writes/retrieval in service/repository tests.

### Write Service

- `src/memory/write_service.py::MemoryWriteService.propose_candidates(...)` defaults to session candidates only.
- Long-term and case candidates are currently accepted only through explicit `state["memory_write_candidates"]`, which is a useful safe seam.
- `_explicit_memory_type(...)` treats any dict with `content` and `source_type` as long-term, so Phase 48 should add guardrails in long-term policy/service, not rely on caller discipline.
- `src/agent/nodes/memory_write.py` currently calls `propose_candidates(state)` without `trusted_context`. Explicit user preference capture needs trusted merchant scope, so the node and service should pass `configurable.get("trusted_context")` into candidate proposal.

### Semantic Episode Projection

- `src/memory/semantic_episode.py` currently projects four kinds into long-term candidates:
  - `cross_case_pattern`
  - `similar_case_hint`
  - `strategy_hint`
  - `preference_candidate`
- All use `source_type="semantic_episode_candidate"` and `to_long_term_memory_candidate()`.
- Phase 48 should project only `preference_candidate` to a `needs_review` long-term candidate. Pattern, similar-case, and strategy material should not enter long-term memory.

### Long-Term Service And Review

- `src/memory/long_term.py::write_memory(...)` already handles tombstone, blocked PII, duplicate active rows, pending review rows, audit events, delete, forget, and supersede.
- The service does not currently skip non-preference memory kinds.
- If `long_term_memory_policy_decision(...)` ever returns `decision="skip"` for non-PII policy reasons, `write_memory(...)` must explicitly return a skipped result before insertion. Today only PII/tombstone/duplicate/expired branches skip.
- `approve_memory(...)` approves a pending row in place without changing `source_type`. Phase 48 needs approval to publish reviewed candidates as `human_reviewed`, especially for `semantic_episode_candidate`.

### Retrieval

- `src/memory/repository.py::retrieve_profile_memory(...)` filters published review status, current rows, prompt-safe PII, tombstones, deletion, expiry, tenant, and scope.
- It does not filter `memory_kind == "preference"` or published source types.
- `src/memory/context_service.py::load_reviewed_memory_context(...)` already calls `retrieve_profile_memory(...)` under trusted merchant scopes. This is the correct seam to keep.

### API

- `src/api/routers/memory.py` has pending review and long-term/case approve/reject/delete/forget endpoints.
- Review endpoints require `approvals:review` and role `admin` or `manager`.
- Phase 48 admin preference save should be stricter than review: role `admin` plus an explicit memory-write scope. Current `ROLE_SCOPES["admin"]` does not include such a scope, so add `memory:write`.

## Implementation Implications

### No Migration By Default

The plan should not narrow the DB check constraint for `LongTermMemory.memory_kind` because that would require migration review and could collide with replay/eval identity expectations. Runtime/service/retrieval tests can enforce the new target semantics without touching table identity.

### Policy Should Be Explicit

Add a published-source allowlist for long-term memory:

```python
PUBLISHED_LONG_TERM_SOURCE_TYPES = frozenset(
    {"explicit_user_preference", "explicit_admin_preference", "human_reviewed"}
)
REVIEW_REQUIRED_LONG_TERM_SOURCE_TYPES = frozenset({"semantic_episode_candidate"})
```

Disallowed source types such as `deterministic_tool_result`, `confirmed_business_outcome`, `approved_approval_state`, `llm_candidate`, `summary_candidate`, `cross_case_pattern_candidate`, and `behavior_inference` should not create published prompt-usable long-term rows. Automatic candidates other than semantic preference candidates should be skipped or rejected before insertion.

### Explicit User Phrase Gate

The deterministic gate should accept narrow phrases such as:

- `remember this preference`
- `save this preference`
- `use this going forward`
- `记住这个偏好`
- `保存这个偏好`
- `以后按这个`
- `之后按这个`

Ordinary statements such as `I like concise updates` or `商家喜欢简短回复` must not write long-term memory.

### Soft Preference Boundary

Allowed preference text can include soft operational hints:

- `Prefer calming explanatory wording in low-amount refund scenarios.`
- `低金额退款场景优先使用安抚性解释。`

Hard rules must be rejected as memory:

- `must refund`
- `must reject`
- `always approve`
- `必须退款`
- `必须拒绝`
- `一律通过`

### Scope

Default chat-captured preferences should use merchant scope only when a trusted merchant scope is available and unambiguous. Tenant scope should be admin-save only. User-specific scope remains post-Phase 48.

## Validation Architecture

### Test Infrastructure

- Framework: pytest through `uv`.
- Approved command prefix: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest`.
- Avoid bare `pytest` and bare `python -m pytest`.

### Primary Test Targets

- `tests/memory/test_phase48_long_term_preference_alignment.py`
- `tests/architecture/test_memory_contract_delta.py`
- `tests/memory/test_memory_policy.py`
- `tests/memory/test_long_term_memory_service.py`
- `tests/memory/test_long_term_memory_repository.py`
- `tests/memory/test_memory_write_service.py`
- `tests/memory/test_semantic_episode_projection.py`
- `tests/memory/test_reviewed_memory_context_boundary.py`
- `tests/agent/test_memory_write_node.py`
- `tests/agent/test_reviewed_memory_context_retrieve.py`
- `tests/agent/test_memory_evidence_boundary.py`
- `tests/test_memory_review_api.py`

### Full Phase Gate

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest \
  tests/memory/test_phase48_long_term_preference_alignment.py \
  tests/architecture/test_memory_contract_delta.py \
  tests/memory/test_memory_policy.py \
  tests/memory/test_long_term_memory_service.py \
  tests/memory/test_long_term_memory_repository.py \
  tests/memory/test_memory_write_service.py \
  tests/memory/test_semantic_episode_projection.py \
  tests/memory/test_reviewed_memory_context_boundary.py \
  tests/agent/test_memory_write_node.py \
  tests/agent/test_reviewed_memory_context_retrieve.py \
  tests/agent/test_memory_evidence_boundary.py \
  tests/test_memory_review_api.py \
  -q
```

### Security Focus

- Spoofing: ordinary chat must not create admin or tenant-scope preferences.
- Tampering: review approval must publish reviewed candidates as `human_reviewed`, not preserve automatic source types as published prompt memory.
- Information disclosure: PII classifications `sensitive` and `prohibited` must skip writes and retrieval.
- Elevation of privilege: admin save must require admin role plus explicit `memory:write` scope.
- Repudiation: all writes, skips, approvals, tombstones, and supersedes must emit memory write events.

## Plan Split Recommendation

1. `48-01`: Contract/docs/static semantic locks.
2. `48-02`: Source policy/schema/service guardrails and semantic episode narrowing.
3. `48-03`: Explicit user phrase capture and admin-only save API/service.
4. `48-04`: Retrieval narrowing, approval publish-as-human-reviewed, supersede/tombstone validation, and final architecture-debt/docs checks.
