---
phase: 13
slug: approval-state-machine
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-15
---

# Phase 13 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest tests/approvals tests/architecture/test_approval_boundaries.py -q --tb=short` |
| **Full suite command** | `uv run pytest -q --tb=short` |
| **Migration command** | `uv run alembic upgrade head` |
| **Estimated runtime** | Focused suite measured during execution; full suite project-dependent |

---

## Sampling Rate

- **After every task commit:** Run the focused pytest command for touched Phase 13 files plus `uv run ruff check <touched paths>`.
- **After every plan wave:** Run `uv run pytest tests/approvals tests/architecture/test_approval_boundaries.py tests/test_approval_api.py tests/test_approval_integration.py tests/agent/test_events.py -q --tb=short`.
- **Before `$gsd-verify-work`:** Run `uv run alembic upgrade head`, the focused Phase 13 suite, and `uv run pytest -q --tb=short`.
- **Max feedback latency:** No three consecutive task commits may skip automated verification.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-W0-01 | 13-01 | 0 | SNAPSHOT-01 | T13-02 / T13-05 | Canonical `proposed_action.v1` bytes are stable; unknown fields, float money, datetime precision, key order, and absent/null differences fail closed. | golden unit | `uv run pytest tests/approvals/test_canonical_hash.py -q --tb=short` | no | pending |
| 13-W0-02 | 13-01 | 0 | SNAPSHOT-01 | T13-02 / T13-05 | `ActionSafetySnapshot` strips `EvidenceRefV1.score`, retains `rank`, sorts evidence canonically, and produces stable snapshot hash bytes. | golden unit | `uv run pytest tests/approvals/test_snapshots.py -q --tb=short` | no | pending |
| 13-W0-03 | 13-03 | 0 | APPROVAL-01 | T13-02 / T13-06 / T13-07 | Stale request, level, assignment, revision, wrong tenant, self-approval, and wrong binding all fail closed without orphan decision/event rows. | DB integration | `uv run pytest tests/approvals/test_service_transitions.py -q --tb=short` | no | pending |
| 13-W0-04 | 13-03 / 13-04 | 0 | APPROVAL-01 | T13-07 | Single-level runtime uses request/level/assignment/decision tables and approves only when required levels complete. | DB/API integration | `uv run pytest tests/approvals/test_single_level_runtime.py -q --tb=short` | no | pending |
| 13-W0-05 | 13-05 | 0 | APPROVAL-02 | T13-01 / T13-03 | `respond` enters `needs_info`, binds clarification identity/scope/version, keeps the run interrupted, and cannot resume old revision into action. | service/API integration | `uv run pytest tests/approvals/test_needs_info_resume.py -q --tb=short` | no | pending |
| 13-W0-06 | 13-02 / 13-03 | 0 | APPROVAL-03 | T13-07 | Multi-level-compatible schema covers `any_one` and `all` modes while runtime stays single-level. | contract integration | `uv run pytest tests/approvals/test_multi_level_contract.py -q --tb=short` | no | pending |
| 13-W0-07 | 13-06 | 0 | APPROVAL-03 | T13-09 | SLA scanner is disabled by default at Phase 13 exit and has event-shape tests without active scheduling side effects. | unit/integration | `uv run pytest tests/approvals/test_sla_scanner.py -q --tb=short` | no | pending |
| 13-W0-08 | 13-03 | 0 | SNAPSHOT-01 | T13-02 | Changed payload, snapshot hash, evidence hash/ref/rank, policy/risk/retrieval config version, or missing snapshot rejects approval/action authorization. | service integration | `uv run pytest tests/approvals/test_hash_binding.py -q --tb=short` | no | pending |
| 13-W0-09 | 13-06 | 0 | APPROVAL-01, APPROVAL-02, APPROVAL-03, SNAPSHOT-01 | T13-04 / T13-05 | Approval events register on the minimal envelope, include actor/metadata/resource refs, and never include raw prompt, args, payload, tool output, secrets, or PII-heavy fields. | event integration | `uv run pytest tests/approvals/test_events.py tests/agent/test_events.py -q --tb=short` | partial | pending |
| 13-W0-10 | 13-02 | 0 | APPROVAL-01, SNAPSHOT-01 | T13-08 | Migration report, legacy non-executable rows, risk_level/risk_rule_ref, respond/edit decision columns, event metadata/resource columns, indexes, constraints, and live DB current/head sanity are verified. | migration integration | `uv run pytest tests/approvals/test_migration_contract.py -q --tb=short` | no | pending |
| 13-W0-11 | 13-07 | 0 | ALL | T13-01 / T13-10 | API routers and agent run routers do not import legacy approval transition paths or perform direct approval mutations. | static architecture | `uv run pytest tests/architecture/test_approval_boundaries.py -q --tb=short` | no | pending |

---

## Threat References

| Threat Ref | Threat | Required Mitigation |
|------------|--------|---------------------|
| T13-01 | Forged approval decision through ordinary chat, LLM output, or client JSON | Only authenticated trusted API/inbox adapters construct `ApprovalDecisionCommand`; service produces `approval_result.v1`. |
| T13-02 | Stale or replayed approval executes changed action/evidence/config | Exact `action_payload_hash + safety_snapshot_hash` plus expected request/level/assignment versions and revision invalidation. |
| T13-03 | Approval `respond` resumes old revision into action | `respond` writes `needs_info`, binds clarification ref/scope/version, and requires revalidated revision before any resume into risk/approval. |
| T13-04 | Cross-tenant approval access or decision | Tenant-scoped lookup plus redundant tenant/run/revision/version mismatch transaction tests. |
| T13-05 | Raw prompt, tool args, action payload, secrets, or PII leak in snapshot/event | Store only IDs, refs, hashes, versions, enums, and safe summaries; extend redaction tests. |
| T13-06 | Self-approval | `ApprovalPolicy` rejects `requested_by == actor_id` unless an explicit audited break-glass policy exists. |
| T13-07 | Invalid assignment/level/request binding or double approval under concurrency | Transaction order lock/CAS request -> level -> assignment -> insert decision/event, with rollback on mismatch. |
| T13-08 | Legacy v1 approval row authorizes action without v2 hashes | Historical v1 rows are display/reject/cancel/expire/supersede only until revalidated into a v2 revision. |
| T13-09 | SLA scanner expires/resumes without replay coverage | Scanner remains feature-disabled in Phase 13; Phase 15 owns enablement gate. |
| T13-10 | Router-owned transition path persists beside service | Static boundary tests forbid direct repository transition imports/mutations outside `src/approvals`. |

---

## Wave 0 Requirements

- [ ] `tests/approvals/test_canonical_hash.py` - SNAPSHOT-01 golden sample and negative canonicalization.
- [ ] `tests/approvals/test_snapshots.py` - SNAPSHOT-01 `ActionSafetySnapshot` builder/projection/golden bytes.
- [ ] `tests/approvals/test_service_transitions.py` - APPROVAL-01 CAS, stale revision, self-approval, wrong tenant, wrong binding.
- [ ] `tests/approvals/test_single_level_runtime.py` - APPROVAL-03 single-level runtime through target model.
- [ ] `tests/approvals/test_needs_info_resume.py` - APPROVAL-02 `respond` and `attach_info` behavior.
- [ ] `tests/approvals/test_multi_level_contract.py` - APPROVAL-03 schema-compatible `any_one`/`all` contract.
- [ ] `tests/approvals/test_sla_scanner.py` - APPROVAL-03 disabled-by-default scanner and event shape.
- [ ] `tests/approvals/test_hash_binding.py` - SNAPSHOT-01 payload/snapshot/evidence/config mismatch fail-closed behavior.
- [ ] `tests/approvals/test_events.py` - approval event registration, actor/resource refs, and redaction.
- [ ] `tests/approvals/test_migration_contract.py` - migration report, legacy non-executable rows, indexes/constraints, current/head sanity.
- [ ] `tests/architecture/test_approval_boundaries.py` - no router direct transition imports/mutations and no graph/action adapter bypass.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Production/staging legacy approval row count | APPROVAL-01, SNAPSHOT-01 | Only the local Docker DB is available in this workspace. | Before deployment, run the migration report against the target environment and confirm historical v1 rows are marked non-executable unless revalidated into v2. |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Sampling continuity rule is defined.
- [x] Wave 0 covers all missing test files from research.
- [x] No watch-mode flags.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** pending
