---
phase: 45
slug: memory-lifecycle-wiring-for-case-working-context
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-03
verified: 2026-07-03
---

# Phase 45 - Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| graph/API state -> lifecycle adapter | Model-influenced run state is filtered before selecting CWC case scope. | case refs, tenant/user/thread/run IDs |
| trusted graph config -> lifecycle adapter | Only `trusted_context` supplies tenant/user/thread/run identity for read-seam link/read calls. | trusted runtime identity |
| lifecycle adapter -> thread_case_links | Runtime state creates durable tenant-scoped thread-case associations only after case resolution. | `tenant_id`, `thread_id`, `refund_cases.id`, `run_id` |
| lifecycle adapter -> memory context bundle | Active CWC enters agent state as contextual-only data. | prompt-safe working context and status refs |
| final_state -> CWC projection | Terminal run state is reduced to deterministic refs/summaries before persistence. | summaries, source refs, projected CWC content |
| finalizer -> CWC write service | Terminal lifecycle calls audited memory write service after response artifacts are durable. | CWC write candidate |
| CWC service result -> finalizer trace | Memory side-effect status is reported without changing the user-visible response. | status, reason code, memory ID/version |
| implementation -> normative contract | Runtime behavior is reflected in docs and contract tests without overstating authority. | contract text and red-line tests |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| 45-01/T-45-01 | S/I | `trusted_case_ref_from_state`, `resolve_case_id` | mitigate | Case refs are read only from trusted slots plus terminal business context when enabled; candidate/session/case memory sources are ignored; tenant-scoped resolver gates scope. Evidence: `src/memory/case_working_context_lifecycle.py:731`, `tests/agent/test_case_working_context_lifecycle.py:141`. | closed |
| 45-01/T-45-02 | E | `MemoryContextBundle`, CWC refs/status | mitigate | CWC DTOs carry `authority_class="contextual_only"` and tests reject authority DTO imports. Evidence: `src/memory/context_refs.py:43`, `src/memory/context_refs.py:91`, `tests/memory/test_context_refs.py:128`, `tests/memory/test_phase45_contract_alignment.py:55`. | closed |
| 45-01/T-45-03 | I | CWC active payload projection | mitigate | Active payload uses `hydrate_content(row)` plus `CaseWorkingContextRef`; no raw policy/tool/action/replay authority body is introduced. Evidence: `src/memory/case_working_context_lifecycle.py:793`, `tests/agent/test_case_working_context_lifecycle.py:193`. | closed |
| 45-01/T-45-04 | D | terminal response path | mitigate | Lifecycle status models represent skip/error reasons without raising through terminal response flow. Evidence: `src/memory/context_refs.py:91`, `src/api/services/agent_run_memory.py:199`. | closed |
| 45-01/T-45-05 | R | lifecycle status/audit bridge | mitigate | Status/result carries run, case, resolve/link/read/write status, and reason code; finalizer trace records CWC status fields. Evidence: `src/memory/context_refs.py:91`, `src/api/services/agent_run_memory.py:118`. | closed |
| 45-01/T-45-06 | T | CWC conflict overwrite | mitigate | Terminal write path reads active version and passes `expected_version`; service conflicts skip without overwrite. Evidence: `src/memory/case_working_context_lifecycle.py:255`, `src/memory/case_working_context.py:113`, `tests/memory/test_case_working_context_service.py:453`. | closed |
| 45-02/T-45-01 | S/I | `reviewed_memory_context_retrieve`, `link_and_load_active` | mitigate | Read seam parses identity from `trusted_context`, resolves case tenant-scoped, and reads CWC by `(tenant_id, case_id)`. Evidence: `src/agent/nodes/reviewed_memory_context_retrieve.py:106`, `src/memory/case_working_context_lifecycle.py:96`, `src/memory/case_working_context.py:48`. | closed |
| 45-02/T-45-02 | E | `case_working_context`, `memory_context_bundle` | mitigate | Additive state/bundle fields stay separate from evidence/business fact/approval/action/replay authority. Evidence: `src/agent/state.py:124`, `src/agent/nodes/reviewed_memory_context_retrieve.py:263`, `tests/memory/test_phase45_contract_alignment.py:127`. | closed |
| 45-02/T-45-03 | I | active CWC payload | mitigate | CWC is not sourced from `case_memories`, candidate slots, raw payloads, or policy body text; red-line tests guard this. Evidence: `src/memory/case_working_context_lifecycle.py:731`, `tests/memory/test_phase45_contract_alignment.py:136`. | closed |
| 45-02/T-45-04 | D | memory_context_load path | mitigate | Read-seam link is wrapped in `session.begin_nested()` and failures return explicit error status without aborting the graph session. Evidence: `src/memory/case_working_context_lifecycle.py:145`, `src/memory/case_working_context_lifecycle.py:155`, `tests/agent/test_case_working_context_lifecycle.py:808`. | closed |
| 45-02/T-45-05 | R | thread-case lifecycle auditability | mitigate | Read/terminal links use `link_source="run_auto"` and `linked_by_run_id=current_run_id`; status records link outcome. Evidence: `src/memory/case_working_context_lifecycle.py:146`, `src/memory/case_working_context_lifecycle.py:369`, `tests/agent/test_case_working_context_lifecycle.py:522`. | closed |
| 45-02/T-45-06 | T | active CWC conflict/overwrite | mitigate | 45-02 is read/link only; content write is isolated to terminal writeback and service conflict semantics. Evidence: `src/memory/case_working_context_lifecycle.py:96`, `src/memory/case_working_context_lifecycle.py:189`. | closed |
| 45-03/T-45-01 | S/I | `write_after_terminal_success` | mitigate | Terminal path resolves tenant-scoped case identity, links by tenant/user/thread/run, and service asserts run/case tenant ownership. Evidence: `src/memory/case_working_context_lifecycle.py:213`, `src/memory/case_working_context_service.py:58`, `src/memory/case_working_context_service.py:64`. | closed |
| 45-03/T-45-02 | E | terminal CWC content | mitigate | Projection builds only `CaseWorkingContextContentV1` with contextual-only schema and no authority DTOs. Evidence: `src/memory/case_working_context_lifecycle.py:463`, `tests/memory/test_phase45_contract_alignment.py:55`. | closed |
| 45-03/T-45-03 | I | deterministic projection | mitigate | Projection consumes prompt-safe summaries/refs, policy identifiers only, and PII classification before service write. Evidence: `src/memory/case_working_context_lifecycle.py:537`, `src/memory/case_working_context_lifecycle.py:577`, `src/memory/case_working_context_lifecycle.py:662`, `tests/memory/test_phase45_contract_alignment.py:127`. | closed |
| 45-03/T-45-04 | D | `finalize_completed_agent_run_memory` | mitigate | Assistant message/thread summary commit happens before CWC side effects; CWC exceptions become side-effect status. Evidence: `src/api/services/agent_run_memory.py:81`, `src/api/services/agent_run_memory.py:96`, `src/api/services/agent_run_memory.py:227`, `tests/test_agent_runs_api.py:2447`. | closed |
| 45-03/T-45-05 | R | CWC write audit/replay | mitigate | Source refs bind run/agent run/refund case identity and service emits `memory_write_events(memory_type="case_working_context")`. Evidence: `src/memory/case_working_context_lifecycle.py:506`, `src/memory/case_working_context_service.py:76`, `tests/memory/test_case_working_context_service.py:445`. | closed |
| 45-03/T-45-06 | T | CWC expected_version | mitigate | Adapter reads active version, passes `expected_version`, and service returns conflict/skip without overwrite. Evidence: `src/memory/case_working_context_lifecycle.py:255`, `src/memory/case_working_context.py:113`, `tests/test_agent_runs_api.py:2533`. | closed |
| 45-04/T-45-01 | S/I | contract/spec and tests | mitigate | Contract/static tests assert tenant-scoped `refund_cases.id` semantics and no cross-tenant fallback. Evidence: `docs/contract-spec.md`, `tests/memory/test_phase45_contract_alignment.py:82`, `tests/agent/test_case_working_context_lifecycle.py:934`. | closed |
| 45-04/T-45-02 | E | docs, AgentState registry, red-line tests | mitigate | Spec and tests keep CWC contextual-only and forbid promotion into evidence/policy/approval/action/replay authority. Evidence: `docs/contract-spec.md`, `src/agent/state.py:124`, `tests/memory/test_phase45_contract_alignment.py:55`. | closed |
| 45-04/T-45-03 | I | red-line tests and validation | mitigate | Static tests reject LLM/summarizer projection, policy body text/raw payload persistence, and invalid test entrypoints; PII block coverage is automated. Evidence: `tests/memory/test_phase45_contract_alignment.py:127`, `tests/memory/test_phase45_contract_alignment.py:201`, `tests/test_agent_runs_api.py:2490`. | closed |
| 45-04/T-45-04 | D | finalizer contract and tests | mitigate | Tests require response artifact preservation on CWC error, PII block, and conflict. Evidence: `tests/test_agent_runs_api.py:2447`, `tests/test_agent_runs_api.py:2490`, `tests/test_agent_runs_api.py:2533`. | closed |
| 45-04/T-45-05 | R | memory_write_events and planning ledgers | mitigate | CWC write service records audit events and finalizer trace/status fields carry reason codes; Phase 45 verification records exact commands. Evidence: `src/memory/case_working_context_service.py:76`, `src/api/services/agent_run_memory.py:118`, `.planning/phases/45-memory-lifecycle-wiring-for-case-working-context/45-VERIFICATION.md`. | closed |
| 45-04/T-45-06 | T | conflict tests and contract | mitigate | Conflict semantics are enforced in repository/service tests and contract alignment; conflicts do not overwrite active CWC. Evidence: `src/memory/case_working_context.py:113`, `tests/memory/test_case_working_context_service.py:453`, `tests/test_agent_runs_api.py:2533`. | closed |

---

## Summary Threat Flags

All Phase 45 summaries report no additional threat flags beyond the plan threat model:

| Summary | Threat Flags |
|---------|--------------|
| `45-01-SUMMARY.md` | None beyond the plan threat model; lifecycle adapter fail-closed sources covered. |
| `45-02-SUMMARY.md` | None beyond the plan threat model; trusted-context link/read boundary implemented. |
| `45-03-SUMMARY.md` | None beyond the plan threat model; final_state projection and finalizer/service boundary implemented. |
| `45-04-SUMMARY.md` | None beyond the plan threat model; docs/static tests only, no new runtime endpoint/auth/file/network surface. |

---

## Verification

| Command | Result |
|---------|--------|
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/memory/test_phase45_contract_alignment.py tests/agent/test_case_working_context_lifecycle.py tests/test_agent_runs_api.py::test_completed_agent_run_finalizer_writes_case_working_context tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_failure_preserves_terminal_rows tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_blocked_preserves_terminal_rows tests/test_agent_runs_api.py::test_agent_run_finalizer_cwc_conflict_preserves_terminal_rows -q` | `46 passed, 1 warning in 19.18s` |
| Phase 45 clean code review | `status: clean`, `0 critical / 0 warning / 0 info` in `45-REVIEW.md` |
| Phase 45 verification | `15/15 must-haves verified` in `45-VERIFICATION.md` |

The single pytest warning is the existing LangGraph `allowed_objects` pending deprecation warning and is not a Phase 45 security finding.

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-03 | 24 | 24 | 0 | Codex (`gsd-secure-phase`) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-03
