---
phase: 48-narrow-long-term-explicit-preference-memory
verified: 2026-07-08T12:04:08Z
status: passed
score: source-backed
requirements:
  - MEM-05
evidence_sources:
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-01-SUMMARY.md
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-02-SUMMARY.md
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-03-SUMMARY.md
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-04-SUMMARY.md
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-VALIDATION.md
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-SECURITY.md
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-UAT.md
  - .planning/phases/48-narrow-long-term-explicit-preference-memory/48-REVIEW.md
---

# Phase 48 Formal Verification

## Verification Scope

This artifact closes the archive evidence gap for Phase 48. MEM-05 is verified as implemented: published long-term memory is explicit preference-only, scoped through approved user/admin/reviewed sources, and does not expand into business state, policy authority, approval authority, action authority, replay authority, run summaries, strategy hints, or broad semantic memory.

No command rerun was required for this archive artifact. Existing validation evidence is recorded with MOCA-approved commands using `UV_CACHE_DIR=/tmp/uv-cache uv run ...`.

## Observable Truths

| Truth | Status | Evidence |
| --- | --- | --- |
| Published long-term memory is explicit preference-only. | passed | `48-01-SUMMARY.md` records the contract decision; `src/memory/policy.py:32` defines `PUBLISHED_LONG_TERM_SOURCE_TYPES`; `src/memory/repository.py:672` filters retrieval to `memory_kind == "preference"`. |
| Allowed published source types are `explicit_user_preference`, `explicit_admin_preference`, and `human_reviewed`. | passed | `src/memory/policy.py:32`-`36`; `tests/memory/test_long_term_memory_repository.py:297`-`301`; `tests/architecture/test_memory_contract_delta.py:138`-`140`. |
| Semantic episode output is not prompt-published directly; it remains a needs-review preference candidate. | passed | `src/memory/policy.py:41`; `tests/memory/test_long_term_memory_service.py:613`; `tests/test_memory_review_api.py:57`-`61`. |
| Non-preference long-term writes skip before insert. | passed | `src/memory/long_term.py:122`; `tests/memory/test_long_term_memory_service.py:172` and `tests/memory/test_long_term_memory_service.py:186`. |
| Chat writes require deterministic explicit preference phrases and trusted merchant scope. | passed | `src/memory/preference_capture.py:103`; `src/memory/preference_capture.py:127`-`131`; `tests/memory/test_memory_write_service.py:221`-`233`. |
| Admin preference writes use the admin API and `memory:write` authorization, then publish as `explicit_admin_preference`. | passed | `src/api/routers/memory.py:93`-`97`; `src/api/routers/memory.py:120`; `tests/test_memory_review_api.py:290`-`295`; `src/auth/permissions.py:27`. |
| Review approval publishes valid candidates as `human_reviewed`, and non-preference approval is controlled. | passed | `src/memory/long_term.py:249`; `src/memory/long_term.py:253`-`259`; `tests/memory/test_long_term_memory_service.py:646`-`655`; `tests/test_memory_review_api.py:188`-`189`. |
| Prompt-facing retrieval filters by preference kind, allowed source type, currentness, and tombstone/deletion state. | passed | `src/memory/repository.py:672`-`673`; `tests/memory/test_long_term_memory_repository.py:221`-`301`. |
| Memory remains contextual-only authority. | passed | `src/memory/policy.py:27`; `src/memory/long_term.py:596`; `tests/memory/test_long_term_memory_service.py:172`; `tests/architecture/test_memory_contract_delta.py:127`. |

## Requirement Coverage

| Requirement | Verification |
| --- | --- |
| MEM-05 | Covered by the Phase 48 summaries, validation, security, UAT, and review artifacts plus current source/test spot checks. Explicit preference-only contract, source policy, deterministic user/admin write paths, retrieval filtering, human-reviewed publication, and lifecycle behavior are implemented and verified. |

## Command Evidence

Existing validation evidence uses approved MOCA entrypoints:

- `48-VALIDATION.md` records the full Phase 48 gate using `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ... -q`.
- `48-SECURITY.md` records the security verification command using `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ... -q`.
- `48-REVIEW.md` records reviewed command evidence using `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ...`.

This verification file intentionally does not introduce bare `pytest` or bare `python -m pytest` commands.

## Evidence Anchors

- `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-01-SUMMARY.md:36` - Long-term memory narrowed to explicit preferences.
- `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-02-SUMMARY.md:35` - Published source allowlist and pre-insert skip behavior.
- `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-03-SUMMARY.md:35` - Deterministic explicit user/admin preference write paths.
- `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-04-SUMMARY.md:35` - Retrieval, review, supersede, and tombstone lifecycle completion.
- `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-VALIDATION.md:33` - Per-task validation row for non-preference and disallowed source skips.
- `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-SECURITY.md:34` - Trust boundary and threat register evidence for explicit preference-only memory.
- `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-UAT.md:13` - UAT status source for Phase 48 behavior.
- `.planning/phases/48-narrow-long-term-explicit-preference-memory/48-REVIEW.md:35` - Deep review found no current issues.
- `src/memory/policy.py:32` - Published long-term source allowlist.
- `src/memory/long_term.py:122` - Non-preference skip before insert.
- `src/memory/long_term.py:249` - Approval rejects non-preference candidates.
- `src/memory/repository.py:672` - Prompt-facing retrieval filters to preference rows.
- `src/memory/preference_capture.py:127` - Explicit user preference candidate writes `memory_kind="preference"`.
- `src/api/routers/memory.py:93` - Admin API writes `memory_kind="preference"`.
- `tests/memory/test_phase48_long_term_preference_alignment.py:133` - Static guard checks retrieval source policy.
- `tests/memory/test_long_term_memory_repository.py:297` - Retrieval result source allowlist assertion.
- `tests/memory/test_long_term_memory_service.py:613` - Reviewed semantic candidate publication regression.
- `tests/test_memory_review_api.py:290` - Admin API returns `explicit_admin_preference`.

## Accepted Limitations

None for MEM-05. Legacy storage/table identity labels remain compatibility details, not authority to publish facts or broad durable memory.

## Final Status

passed - Phase 48 has source-backed formal verification for MEM-05 archive closure.
