---
phase: 31
slug: memory-platform-boundary
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-28T10:57:16Z
updated: 2026-06-28T10:57:16Z
---

# Phase 31 - Security

Per-phase security contract: threat register, accepted risks, and audit trail for the memory platform boundary.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| memory DTO -> authority DTO | Contextual memory refs cross into evidence/business/approval/action/replay validators and must be rejected. | Contextual memory refs/status refs |
| session context -> prompt context | Same-thread summaries, messages, tool summaries, and slots become prompt context but not authority. | Session continuity context |
| TrustedContext -> reviewed memory service | Trusted tenant/user/merchant/resource scope controls reviewed memory retrieval. | Reviewed long-term/case memory scopes |
| memory lifecycle services -> prompt projection | Only reviewed, prompt-safe, unexpired, non-deleted, non-tombstoned memory can become contextual prompt input. | Prompt-facing reviewed memory items |
| target node -> legacy aliases | Legacy `long_term_memory` / `case_memory` aliases must mirror guarded target output, not bypass it. | Compatibility graph outputs |
| memory write side effect -> main path | Write failures/timeouts must not roll back final response, approval, or action state. | Memory write status and fallback metadata |
| memory contextual refs -> claim verifier | Contextual-only memory refs/status refs must be rejected as authority by verifier defenses. | Material claim verifier inputs |
| validation suite -> local DB | DB-backed tests must run serially to avoid shared metadata races. | Local test database state |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-31-cross-merchant | I | session/reviewed memory prompt context | mitigate | Session filtering rejects cross-merchant context; reviewed memory requires trusted merchant or case scope; tests cover session isolation, reviewed memory isolation, and wildcard/static scope guards. Evidence: `src/agent/nodes/session_context_load.py`, `src/memory/context_service.py`, `tests/memory/test_session_memory_isolation.py`, `tests/memory/test_reviewed_memory_context_boundary.py`, `tests/tools/test_merchant_scope_static.py`. | closed |
| T-31-authority-forgery | S/T | memory refs/status refs and verifier | mitigate | Memory refs/status DTOs are hard-coded contextual-only; verifier filters contextual refs, status refs, citation maps, and safe refs before authority support; tests cover DTO/import boundaries and citation-map bypass. Evidence: `src/memory/context_refs.py`, `src/agent/rag_context/verifier.py`, `tests/agent/test_memory_evidence_boundary.py`, `tests/agent/rag_context/test_authority_boundaries.py`. | closed |
| T-31-pii-leakage | I | session/reviewed prompt projection and memory write | mitigate | Reviewed/session prompt surfaces use allowlisted sanitized projection; memory write classifies explicit slots, unresolved questions, session summary, and final response before persistence; tests cover PII-blocked paths. Evidence: `src/memory/context_service.py`, `src/agent/context/projectors.py`, `src/agent/nodes/memory_write.py`, `tests/agent/test_memory_write_node.py`. | closed |
| T-31-tombstone-revival | T/R | reviewed memory lifecycle | mitigate | Reviewed context delegates to lifecycle-aware long-term/case services instead of direct repository queries; lifecycle exclusions and tombstone blocking are covered by reviewed memory, tombstone, and case retrieval tests. Evidence: `src/memory/context_service.py`, `tests/memory/test_reviewed_memory_context_boundary.py`, `tests/memory/test_memory_tombstones.py`, `tests/memory/test_case_memory_retrieval.py`. | closed |
| T-31-replay-confusion | R/T | memory status refs vs replay truth | mitigate | Status refs are contextual-only DTOs, not replay truth; verifier rejects contextual memory schema versions as authority; tests cover replay and authority rejection. Evidence: `src/memory/context_refs.py`, `src/agent/rag_context/verifier.py`, `tests/agent/test_memory_evidence_boundary.py`. | closed |
| T-31-write-rollback | D/T | `memory_write` and `memory_write_decision.v2` | mitigate | Write, skip, timeout, and error paths preserve final response and emit `memory_write_decision.v2`; state/reset fields prevent stale decisions from leaking across turns; tests cover failure, timeout, PII, and reset paths. Evidence: `src/agent/nodes/memory_write.py`, `src/memory/context_service.py`, `src/agent/state.py`, `src/agent/nodes/receive_request.py`, `tests/agent/test_memory_write_node.py`, `tests/agent/test_nodes/test_receive_request.py`. | closed |

---

## Accepted Risks Log

No phase-level accepted risks.

Notes:

- Some intermediate plan slices marked threats as accepted because that slice did not own the mitigation.
- The completed Phase 31 implementation closes those items through later plans, so no accepted risk remains open at phase level.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-28 | 6 | 6 | 0 | gsd-security-auditor |

### Security Audit 2026-06-28

| Metric | Count |
|--------|-------|
| Threats found | 6 |
| Closed | 6 |
| Open | 0 |

Auditor result: `## SECURED`.

Unregistered flags: none. Phase 31 summaries reported no unmapped threat flags and no new threat surface outside the plan register.

---

## Verification Evidence

- Security auditor verified all 6 registered threats as closed against the live codebase and tests.
- Phase 31 UAT is complete with `6 passed, 0 issues`.
- Phase 31 clean code review is `status: clean`, with `0` findings at deep depth.
- Focused Phase 31 verification suite passed: `129 passed, 3 warnings`.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-28
