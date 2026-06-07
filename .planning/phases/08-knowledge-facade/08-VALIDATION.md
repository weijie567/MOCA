---
phase: 8
slug: knowledge-facade
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-07
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (asyncio_mode = auto) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/knowledge -q` (new knowledge contract/golden tests) |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~quick: <15s knowledge tests; full suite longer (DB/integration) |

> Final new-test path (`tests/knowledge/` vs flat `tests/test_knowledge_*`) is fixed during planning; update the quick command if the planner chooses flat layout.

---

## Sampling Rate

- **After every task commit:** Run the quick command for the touched area (`uv run pytest tests/knowledge -q`, or the specific node test file).
- **After every plan wave:** Run `uv run pytest`.
- **Before `/gsd-verify-work`:** Full suite must be green, including the BLOCKING citation-membership eval.
- **Max feedback latency:** ~15 seconds for the knowledge contract/golden quick set.

---

## Per-Task Verification Map

> Filled by the planner per task. Every contract boundary the facade introduces maps to a deterministic golden/contract assertion (see RESEARCH §8). Skeleton below; planner replaces with real task IDs.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 8-01-xx | 01 | 1 | KNOW-02 | — | text_hash stable over full normalized chunk text | unit/golden | `uv run pytest tests/knowledge/test_text_hash.py -q` | ❌ W0 | ⬜ pending |
| 8-01-xx | 01 | 1 | KNOW-02 | — | EvidenceRefV1 canonical projection: score stripped, rank-aware sort | unit/golden | `uv run pytest tests/knowledge/test_evidence_projection.py -q` | ❌ W0 | ⬜ pending |
| 8-0x-xx | 0x | x | KNOW-01 | — | strong/partial/no_evidence preserved through facade | contract | `uv run pytest tests/knowledge/test_facade_status.py -q` | ❌ W0 | ⬜ pending |
| 8-0x-xx | 0x | x | KNOW-02 | — | citation membership: evidence_id ∈ evidence_refs verdict | contract/eval | `uv run pytest tests/knowledge/test_citation_membership.py -q` | ❌ W0 | ⬜ pending |
| 8-0x-xx | 0x | x | KNOW-02 | — | effective_at explicit; defaults to run start | contract | `uv run pytest tests/knowledge/test_effective_time.py -q` | ❌ W0 | ⬜ pending |
| 8-0x-xx | 0x | x | KNOW-03 | — | merge dedupes by evidence_id; no_evidence routes to insufficient | node | `uv run pytest tests/agent/test_nodes/test_retrieve_policy_evidence.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/knowledge/__init__.py` + `tests/knowledge/conftest.py` — shared fixtures (sample PolicyDocument/PolicyChunk, deterministic effective_at) for KNOW-01..03
- [ ] Golden fixture files for `evidence_text_hash.v1` and EvidenceRefV1 canonical projection
- [ ] Citation-membership eval dataset (owner = Phase 8) with pinned version + content hash
- [ ] No framework install needed — pytest 8.x + pytest-asyncio already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tenant-over-global precedence | KNOW-02 (deferred) | No global-policy schema in MVP (PolicyDocument.tenant_id NOT NULL); DEFERRED_WITH_OWNER to later policy-scope phase | Not validated in Phase 8 — owner + schema-and-query acceptance gate recorded in plan; no P8 test |
| Semantic groundedness/support | KNOW-02 (deferred) | Separate deferred eval; membership must NOT be treated as semantic support | Owned by separate deferred eval (eval-test-plan §20); not inferred from membership gate |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (new tests/knowledge module + golden fixtures + eval dataset)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s for knowledge quick set
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
