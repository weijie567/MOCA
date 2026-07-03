---
phase: 46
slug: session-context-repositioning
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-03
---

# Phase 46 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py -x -q` |
| **Existing smoke command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py -x -q` |
| **Full suite command** | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py tests/memory/test_session_memory_schema.py tests/memory/test_session_memory_service.py tests/memory/test_session_memory_repository.py tests/memory/test_session_memory_bundle.py tests/memory/test_memory_context_bundle.py tests/agent/test_session_memory_load.py tests/agent/test_session_memory_integration.py tests/agent/test_reviewed_memory_context_retrieve.py tests/agent/test_memory_evidence_boundary.py tests/tools/test_catalog.py tests/memory/test_phase45_contract_alignment.py -q` |
| **Estimated runtime** | Fast static smoke target <30 seconds where possible; full targeted suite ~60-180 seconds with local PostgreSQL available |

---

## Sampling Rate

- **After every task commit:** Run `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py -x -q` once the file exists; before Wave 0 exists, use the existing Phase 45 smoke command for protected red lines.
- **After every plan wave:** Run the targeted suite for the affected surface.
- **Before `$gsd-verify-work`:** Full targeted suite plus all new Phase 46 tests must be green.
- **Max feedback latency:** <30 seconds target for static task-level feedback where possible; 180 seconds allowed for DB-backed final gates.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 46-W0-01 | 46-02 | 0 | MEM-03 | T-46-01 | `session_memories` remains tenant/user/thread scoped and has no `case_id` ownership drift | static contract | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py::test_session_memories_remains_thread_scoped_without_case_id -q` | no; Wave 0 creates it | pending |
| 46-W0-02 | 46-02 | 0 | MEM-03 | T-46-02 / T-46-03 | Session hints do not produce evidence/current-fact/approval/action/replay authority | static + behavioral | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_memory_evidence_boundary.py tests/memory/test_phase46_session_context_alignment.py -q` | partial; Wave 0 adds static file | pending |
| 46-W0-03 | 46-02 | 0 | MEM-03 | T-46-04 | `search_case_memory` stays reviewed case memory, not session-derived precedent | static + unit | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/tools/test_catalog.py::test_search_case_memory_descriptor_names_reviewed_case_memory_store tests/memory/test_phase46_session_context_alignment.py::test_search_case_memory_uses_reviewed_case_memory_service -q` | partial; Wave 0 adds executor assertion | pending |
| 46-W0-04 | 46-02 | 0 | MEM-03 | T-46-05 | Session memory is not CWC fallback | static + integration | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py tests/agent/test_reviewed_memory_context_retrieve.py tests/memory/test_phase46_session_context_alignment.py -q` | partial; Phase 45 exists, Wave 0 adds Phase 46 references | pending |
| 46-W0-05 | 46-01 / 46-03 | 0 | MEM-03 | T-46-06 | Phase 47 and Phase 48 remain named defers and are not implemented by Phase 46 | static docs | `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase46_session_context_alignment.py::test_phase47_and_phase48_defers_remain_named -q` | no; Wave 0 creates it | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/memory/test_phase46_session_context_alignment.py` - static MEM-03 boundary checks for schema identity, authority separation, reviewed precedent separation, CWC fallback prevention, doc wording, and defer carry-forward.
- [ ] Optional doc wording assertions inside the new file - cover stale `search_case_memory` wording in `docs/current-implementation-map.md` and `docs/architecture-overview.md` only if Phase 46 edits those non-normative docs.
- [x] Existing infrastructure covers pytest, pytest-asyncio, async DB fixtures, and local PostgreSQL through compose.

---

## Manual-Only Verifications

All planned Phase 46 behaviors should have automated verification. Manual review is limited to reading plan/checker output and confirming intentional defers remain documented.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify.
- [ ] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [ ] Fast smoke feedback latency target < 30s where possible; final DB-backed gate may take 60-180s.
- [ ] `nyquist_compliant: true` set in frontmatter after execution proves coverage.

**Approval:** pending
