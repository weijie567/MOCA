---
phase: 48
slug: narrow-long-term-explicit-preference-memory
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-04
verified: 2026-07-04
---

# Phase 48 - Security

Per-phase security verification for narrowing long-term memory to explicit preference memory.

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| contract -> implementation | Normative memory contract controls allowed source policy, write paths, and retrieval semantics. | memory source types, review status, prompt-visible memory |
| plan artifacts -> execution | Executors follow Phase 48 plan commands and file instructions. | pytest commands, storage identity constraints |
| source type -> long-term policy | Source provenance controls publish, review, or skip decisions. | `source_type`, `memory_kind`, PII class |
| candidate -> repository insert | Service must not insert skipped, non-preference, tombstoned, PII-blocked, or hard-rule candidates. | long-term write candidates, audit events |
| ordinary chat/admin API -> long-term writes | Chat and admin entry points can create durable prompt context. | user text, trusted merchant scope, admin token scopes |
| repository -> prompt context | Retrieved rows become prompt-visible contextual memory. | reviewed long-term memory rows |
| review queue -> published memory | Human approval converts review candidates into prompt-visible rows. | review action, source conversion |

## Threat Register

| Plan | Threat ID | Category | Component | Disposition | Status | Evidence |
|------|-----------|----------|-----------|-------------|--------|----------|
| 48-01 | T-48-01 | T | `docs/contract-spec.md` | mitigate | closed | `docs/contract-spec.md:1500` defines explicit preference-only long-term memory; `docs/contract-spec.md:1502`-`1508` restricts published source types and converts approved semantic candidates to `human_reviewed`; `docs/contract-spec.md:1510`-`1516` rejects broad durable facts and preserves legacy storage identity only. |
| 48-01 | T-48-02 | T/I | `tests/memory/test_phase48_long_term_preference_alignment.py` | mitigate | closed | `tests/memory/test_phase48_long_term_preference_alignment.py:65`-`106` protects storage table identities and scans Phase 48 plans for destructive storage instructions. |
| 48-01 | T-48-03 | R | Phase 48 plan artifacts | mitigate | closed | `tests/memory/test_phase48_long_term_preference_alignment.py:109`-`117` enforces `UV_CACHE_DIR=/tmp/uv-cache uv run pytest` for Phase 48 pytest commands. |
| 48-01 | T-48-04 | I/E | `docs/memory-contract-delta.md` | mitigate | closed | `docs/memory-contract-delta.md:83`-`118` defines explicit preference-only target semantics and rejects old durable long-term targets; `tests/architecture/test_memory_contract_delta.py:80`-`94` forbids older durable fact/pattern target assertions. |
| 48-02 | T-48-03 | T/E | `src/memory/policy.py` | mitigate | closed | `src/memory/policy.py:32`-`53` defines the published allowlist and disallowed long-term sources; `src/memory/policy.py:100`-`131` writes, reviews, or skips by source type. |
| 48-02 | T-48-04 | T | `src/memory/long_term.py` | mitigate | closed | `src/memory/long_term.py:122`-`154` skips non-preference kinds and source-policy rejects before insertion; `tests/memory/test_long_term_memory_service.py:137`-`203` verifies no insert plus skip audit events. |
| 48-02 | T-48-05 | I | `src/memory/semantic_episode.py` | mitigate | closed | `src/memory/semantic_episode.py:20`-`47` defines only `preference_candidate`; `src/memory/semantic_episode.py:66`-`78` converts candidates to `memory_kind="preference"`; static guard at `tests/memory/test_phase48_long_term_preference_alignment.py:120`-`126` rejects pattern/similar/strategy projection. |
| 48-02 | T-48-06 | R | `MemoryWriteEvent` emission | mitigate | closed | Skip event helper at `src/memory/long_term.py:600`-`623` reuses `MemoryWriteEvent` shape; repository event persistence at `src/memory/repository.py:305`-`338` records decision, reason, policy version, blocked-by, authority class, and source ref. |
| 48-03 | T-48-06 | S/T | `preference_capture.py` phrase gate | mitigate | closed | `src/memory/preference_capture.py:18`-`26` defines deterministic phrase allowlist; `src/memory/preference_capture.py:67`-`76` returns `None` without a matched phrase and content. |
| 48-03 | T-48-07 | E/I | merchant scope resolution | mitigate | closed | `src/memory/preference_capture.py:116`-`139` builds chat preference candidates only with `scope_type="merchant"`; `src/memory/preference_capture.py:150`-`166` resolves only trusted merchant scope; `src/memory/write_service.py:312`-`326` blocks state long-term candidates unless review-required, merchant-scoped, and trusted-context allowed. |
| 48-03 | T-48-08 | E | admin preference API | mitigate | closed | `src/api/routers/memory.py:67`-`76` requires `memory:write` and admin assertion; `src/api/routers/memory.py:456`-`486` enforces admin role and tenant/merchant scope validation; `src/auth/jwt.py:13`-`27` grants `memory:write` only to admin defaults. |
| 48-03 | T-48-09 | T | soft preference validation | mitigate | closed | `src/memory/preference_capture.py:27`-`39` lists hard-rule markers; `src/memory/preference_capture.py:79`-`86` returns `hard_rule_not_preference`; API rejects invalid preference text at `src/api/routers/memory.py:77`-`86`; service also skips hard-rule candidates at `src/memory/long_term.py:133`-`143`. |
| 48-03 | T-48-10 | I/R | long-term service write | mitigate | closed | Existing write gates are still used: tombstone and PII skips at `src/memory/long_term.py:61`-`121`, policy skip at `src/memory/long_term.py:145`-`154`, and audit event persistence at `src/memory/repository.py:305`-`338`; admin API routes through `LongTermMemoryService.write_memory` at `src/api/routers/memory.py:106`-`108`. |
| 48-04 | T-48-09 | I | `LongTermMemoryRepository.retrieve_profile_memory` | mitigate | closed | `src/memory/repository.py:632`-`685` filters prompt retrieval by tenant/scope, `memory_kind == "preference"`, `PUBLISHED_LONG_TERM_SOURCE_TYPES`, published review status, current, prompt-safe PII, expiry, deletion, and tombstone; regression at `tests/memory/test_long_term_memory_repository.py:207`-`303` covers allowed/denied rows. |
| 48-04 | T-48-10 | T/R | `LongTermMemoryService.approve_memory` | mitigate | closed | `src/memory/long_term.py:237`-`277` rejects non-preference approval, rejects hard-rule approval, converts approved source to `human_reviewed`, updates source identity, and emits write event; regressions at `tests/memory/test_long_term_memory_service.py:612`-`656` and `740`-`773`. |
| 48-04 | T-48-11 | T | `supersede_memory`, `forget_memory` | mitigate | closed | Explicit tombstone/delete paths at `src/memory/long_term.py:308`-`371`; explicit supersede path at `src/memory/long_term.py:376`-`566`; regressions for supersede, no-auto-merge, tombstone rewrite blocking, and pending supersede at `tests/memory/test_long_term_memory_service.py:850`-`1110`. |
| 48-04 | T-48-12 | E/I | reviewed memory prompt context | mitigate | closed | Boundary docs at `docs/memory-contract-delta.md:69`-`79`; reviewed context tests exclude unpublished/non-authoritative memory at `tests/memory/test_reviewed_memory_context_boundary.py:480`-`549` and prove supersede prompt-currentness at `tests/memory/test_reviewed_memory_context_boundary.py:640`-`702`; UAT confirms authority boundaries at `48-UAT.md:39`-`47`. |
| 48-04 | T-48-13 | R | final validation | mitigate | closed | Architecture debt trace records Phase 48 narrowing at `.planning/ARCHITECTURE-DEBT.md:288`-`316`; fresh local validation used the approved entrypoint and passed: `UV_CACHE_DIR=/tmp/uv-cache uv run pytest ... -q` -> `155 passed, 3 warnings` on 2026-07-04. |

## Accepted Risks Log

No accepted risks.

## Transfer Documentation

No transferred threats.

## Unregistered Flags

None. The Phase 48 summaries, review, and UAT artifacts contain no `## Threat Flags` section or unmatched threat flag entries.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | ASVS Level | Run By |
|------------|---------------|--------|------|------------|--------|
| 2026-07-04 | 18 | 18 | 0 | 1 | gsd-security-auditor |

## Verification Commands

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase48_long_term_preference_alignment.py tests/architecture/test_memory_contract_delta.py tests/memory/test_memory_policy.py tests/memory/test_long_term_memory_service.py tests/memory/test_long_term_memory_repository.py tests/memory/test_memory_write_service.py tests/memory/test_semantic_episode_projection.py tests/memory/test_reviewed_memory_context_boundary.py tests/agent/test_memory_write_node.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_memory_evidence_boundary.py tests/test_memory_review_api.py -q
```

Result: `155 passed, 3 warnings in 150.84s`.

## Sign-Off

- [x] All threats have a disposition.
- [x] Accepted risks documented.
- [x] Threat flags incorporated.
- [x] `threats_open: 0` confirmed.
- [x] `status: verified` set in frontmatter.

Approval: verified 2026-07-04.
