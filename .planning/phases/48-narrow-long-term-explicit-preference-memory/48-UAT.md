---
status: complete
phase: 48-narrow-long-term-explicit-preference-memory
source:
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-01-SUMMARY.md
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-02-SUMMARY.md
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-03-SUMMARY.md
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-04-SUMMARY.md
started: 2026-07-04T02:44:33Z
updated: 2026-07-04T02:48:41Z
---

## Current Test

[testing complete]

## Tests

### 1. Published Long-Term Memory Contract
expected: The Phase 48 contract and architecture docs describe prompt-facing long-term memory as explicit preference-only. Durable facts, policy rules, action authority, run summaries, strategy hints, semantic patterns, tool results, and business state are excluded. The legacy storage/table identity `long_term_fact` is still documented as a storage label only, not permission to publish facts.
result: pass
verified_by: automated static contract/docs scan and Phase 48 static guard tests

### 2. Source Policy and Semantic Episode Projection
expected: Long-term writes auto-publish only explicit user preferences, explicit admin preferences, or human-reviewed preferences. Non-preference and disallowed long-term sources are skipped before insert. Semantic episodes can only produce `semantic_episode_candidate` needs-review preference candidates; they do not publish facts, patterns, strategy hints, or run summaries directly.
result: pass
verified_by: tests/memory/test_memory_policy.py, tests/memory/test_long_term_memory_service.py, tests/memory/test_semantic_episode_projection.py

### 3. Deterministic Chat Preference Capture
expected: Chat-origin preference memory is created only when the user uses deterministic explicit phrases such as "记住这个偏好", "以后按这个", or "保存这个偏好". The resulting candidate is merchant-scoped from trusted context, uses `source_type="explicit_user_preference"`, and ordinary preference-like chat without the explicit gate creates no long-term candidate.
result: pass
verified_by: tests/memory/test_memory_write_service.py and tests/agent/test_memory_write_node.py

### 4. Admin Preference Save API
expected: Admin users with the `memory:write` scope can save merchant- or tenant-scoped long-term preferences through the admin API as `explicit_admin_preference`. Tenant-scoped preferences are admin-only, invalid scopes are rejected, and admin-created preferences are direct published writes rather than pending review candidates.
result: pass
verified_by: tests/test_memory_review_api.py and auth/API source scan

### 5. Review Publishing, Retrieval, and Lifecycle
expected: Review approval of a needs-review preference candidate publishes it as `human_reviewed`; approving non-preference long-term memory returns a controlled API error and does not publish. Prompt-facing retrieval returns only current, non-tombstoned published preference rows from allowed sources. Corrections use explicit supersede/tombstone lifecycle, and similar preferences are not auto-merged.
result: pass
verified_by: tests/memory/test_long_term_memory_service.py, tests/memory/test_long_term_memory_repository.py, tests/memory/test_reviewed_memory_context_boundary.py, tests/test_memory_review_api.py

### 6. Review Authorization and Candidate Provenance Guards
expected: Memory review APIs are admin-only; manager/support users cannot review tenant-wide memory. State-origin memory candidates cannot self-claim admin or human-reviewed provenance, and closed-case case-memory candidates must carry complete normalized `refund_case` source provenance before entering review.
result: pass
verified_by: tests/test_memory_review_api.py, tests/memory/test_memory_write_service.py, tests/agent/test_memory_write_node.py

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Automated Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_write_node.py tests/architecture/test_memory_contract_delta.py tests/memory/test_long_term_memory_repository.py tests/memory/test_long_term_memory_service.py tests/memory/test_memory_policy.py tests/memory/test_memory_write_service.py tests/memory/test_phase48_long_term_preference_alignment.py tests/memory/test_reviewed_memory_context_boundary.py tests/memory/test_semantic_episode_projection.py tests/test_memory_review_api.py -q` -> 130 passed, 1 existing LangGraph deprecation warning.
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/memory/policy.py src/memory/schemas.py src/memory/long_term.py src/memory/semantic_episode.py src/memory/preference_capture.py src/memory/write_service.py src/agent/nodes/memory_write.py src/api/routers/memory.py src/api/schemas/memory.py src/auth/jwt.py src/auth/permissions.py tests/memory/test_memory_policy.py tests/memory/test_long_term_memory_service.py tests/memory/test_semantic_episode_projection.py tests/memory/test_phase48_long_term_preference_alignment.py tests/memory/test_memory_write_service.py tests/agent/test_memory_write_node.py tests/test_memory_review_api.py tests/memory/test_long_term_memory_repository.py tests/memory/test_reviewed_memory_context_boundary.py tests/architecture/test_memory_contract_delta.py` -> pass.
- Static evidence scan confirmed explicit preference-only contract language, long-term published source allowlist, semantic episode review-only candidate source, admin `memory:write` API path, admin-only review role gate, and closed-case source provenance guards.

## Gaps

[none yet]
