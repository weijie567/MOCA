---
phase: 46
slug: session-context-repositioning
status: verified
threats_open: 0
asvs_level: 2
created: 2026-07-03
verified: 2026-07-03
---

# Phase 46 - Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| docs -> implementers | Normative and non-normative docs must not grant session context authority or durable cross-case meaning. | Contract wording, roadmap/defer decisions |
| session context -> authority services | Session hints may enter prompt context but must not satisfy policy evidence, business fact, approval/action, replay, or CWC authority checks. | Prompt-safe hint refs and summaries |
| planner-facing memory tool -> reviewed memory | `search_case_memory` must retrieve reviewed case memory, not legacy session-derived precedent. | Case-memory query and reviewed-memory result items |
| session/reviewed memory -> CWC lifecycle | CWC identity must come from trusted case refs and lifecycle code, not raw session or reviewed-memory content. | Case refs, active CWC payload/status |
| memory write side effect -> durable memory layers | Ordinary completed runs may write session context but must not auto-create long-term preference or reviewed case-memory records. | Memory write candidates/results |
| Phase 46 validation -> compliance artifact | Validation flags must be set only after approved-entrypoint commands pass. | Test results and compliance flags |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-46-01 | I | session memory schema/load/write identity | mitigate | `SessionMemory` remains tenant/user/thread scoped with no `case_id`; Phase 46 static guards reject destructive protected table operations; final targeted suite passed. | closed |
| T-46-02 | T/E | session hints as policy evidence | mitigate | Contract wording and tests reject session hints as `EvidenceRefV1`; evidence-boundary behavior preserves `memory_not_policy_authority`. | closed |
| T-46-03 | T | session hints/business refs as current business facts | mitigate | Contract wording and tests reject session/business refs as `BusinessFactRefV1` authority; fresh business tool reads remain required for current facts. | closed |
| T-46-04 | R/T | session memory as reviewed precedent / planner-facing `search_case_memory` | mitigate | `MemoryToolExecutor` uses `CaseMemoryService.retrieve_reviewed`; `LegacySessionPrecedentSearchService` remains legacy/debug-only; architecture diagram label was fixed. | closed |
| T-46-05 | T/R | session/reviewed memory as CWC lifecycle identity or fallback | mitigate | CWC lifecycle uses trusted refs and skips/fail-closes when only session/reviewed context contains tempting case identity. | closed |
| T-46-06 | E/R | session memory as approval/action/replay authority | mitigate | Static and behavioral tests reject approval/action/replay DTO construction or authority satisfaction from session context. | closed |

---

## Evidence

| Threat ID | Evidence |
|-----------|----------|
| T-46-01 | `tests/memory/test_phase46_session_context_alignment.py`; `tests/memory/test_session_memory_schema.py`; `src/db/models.py`; final targeted suite `133 passed, 9 warnings`. |
| T-46-02 | `docs/contract-spec.md`; `tests/agent/test_memory_evidence_boundary.py`; `tests/memory/test_session_memory_bundle.py`; focused post-gap suite `13 passed, 1 warning`. |
| T-46-03 | `docs/contract-spec.md`; `src/memory/session_bundle.py` prompt-safe allowlist projection; `tests/agent/test_memory_evidence_boundary.py`. |
| T-46-04 | `src/tools/executors/memory.py`; `src/memory/search.py`; `docs/architecture-overview.md`; `tests/tools/test_catalog.py`; `tests/memory/test_phase46_session_context_alignment.py`. |
| T-46-05 | `src/memory/case_working_context_lifecycle.py`; `src/agent/nodes/reviewed_memory_context_retrieve.py`; `tests/agent/test_reviewed_memory_context_retrieve.py`. |
| T-46-06 | `tests/memory/test_phase46_session_context_alignment.py`; `tests/agent/test_memory_evidence_boundary.py`; `tests/memory/test_session_memory_bundle.py`. |

---

## Accepted Risks Log

No accepted risks.

---

## Advisory Residuals

| Ref | Status | Notes |
|-----|--------|-------|
| 46-REVIEW WR-01 | advisory | Stale current-implementation-map rows around conversation/tool/thread-summary primitives are outside MEM-03 threat closure and do not grant session context authority. |
| 46-REVIEW WR-03 | advisory | One older prompt-safety assertion mutates `summary` while the bundle reads `prompt_summary`; direct Phase 46 regression tests cover the actual policy-ref input and passed. |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-03 | 6 | 6 | 0 | gsd-security-auditor |

---

## Verification Commands

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py -x -q` -> `9 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_session_memory_bundle.py tests/agent/test_memory_evidence_boundary.py tests/memory/test_memory_write_service.py tests/agent/test_reviewed_memory_context_retrieve.py tests/tools/test_catalog.py tests/memory/test_phase46_session_context_alignment.py -q` -> `87 passed, 3 warnings`
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py tests/memory/test_session_memory_schema.py tests/memory/test_session_memory_service.py tests/memory/test_session_memory_repository.py tests/memory/test_session_memory_bundle.py tests/memory/test_memory_context_bundle.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_memory_evidence_boundary.py tests/tools/test_catalog.py tests/memory/test_phase45_contract_alignment.py tests/memory/test_memory_write_service.py -q` -> `133 passed, 9 warnings`

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-03
