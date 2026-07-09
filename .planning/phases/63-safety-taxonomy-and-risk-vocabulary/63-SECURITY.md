---
phase: 63
slug: safety-taxonomy-and-risk-vocabulary
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-10
updated: 2026-07-10
---

# Phase 63 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| user/LLM text -> taxonomy helpers | Untrusted strings are normalized before they become action IDs or routing decisions. | User text, LLM action/risk labels |
| taxonomy owner -> downstream graph nodes | A shared registry becomes the source of truth for safety decisions in risk, draft, intent, and routing nodes. | Action aliases, executable action ids, risk vocabulary |
| LLM risk output -> backend risk policy | LLM `RiskAssessment` remains advisory and is normalized before routing/action decisions. | LLM risk assessment payload |
| risk_gate -> approval/action path | Risk gate creates proposed actions, hashes, snapshots, risk decisions, and approval/auto-allowed bindings. | Proposed action, risk decision, snapshot refs |
| proposed_action -> ToolPlatform args | Proposed action type is untrusted until canonical executable validation passes. | Action draft payload |
| ordinary chat text -> pre-route policy | User text can look like approval/action commands but must not become trusted approval truth. | Chat text, requested operation |
| future source edits -> safety taxonomy | Static tests guard against reintroducing drift-prone local source-of-truth sets. | Source changes |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-63-01 | Tampering | `src/agent/safety/taxonomy.py` | mitigate | Immutable descriptors/read-only maps; `tests/agent/test_safety_taxonomy.py` asserts immutability. | closed |
| T-63-02 | Elevation of Privilege | `manual_review` / `blocked` classification | mitigate | `manual_review` and `blocked` are dispositions only and excluded from `EXECUTABLE_ACTION_TYPES`. | closed |
| T-63-03 | Spoofing | action keyword alias matching | mitigate | Registry-owned aliases and approval-chat hard negatives are covered by taxonomy tests. | closed |
| T-63-04 | Information Disclosure | taxonomy test data | accept | Unit tests use synthetic strings only and do not touch tenant/customer data. | closed |
| T-63-05 | Tampering | `risk_gate._build_proposed_action` | mitigate | Only canonical executable actions create proposed actions; disposition-shaped recommendations fail closed before snapshot binding. | closed |
| T-63-06 | Elevation of Privilege | `risk_assessment.risk_level` | mitigate | Risk gate emits severity-only `risk_level` plus explicit `risk_disposition`; tests forbid new `manual_review`/`blocked` severity output. | closed |
| T-63-07 | Tampering | LLM risk output | mitigate | Deterministic rule match and verification gates remain authoritative after LLM assessment. | closed |
| T-63-08 | Repudiation | `RiskDecisionV1` binding | mitigate | Action payload hash, safety snapshot hash, and risk decision binding tests remain green. | closed |
| T-63-09 | Elevation of Privilege | `action_draft.action_draft` | mitigate | Explicit `manual_review` / `blocked` requests return safe non-executable errors before ToolPlatform invocation. | closed |
| T-63-10 | Tampering | action type canonicalization | mitigate | `action_draft` and `risk_gate` use `src.agent.safety.taxonomy` helpers; local action sets/functions removed. | closed |
| T-63-11 | Repudiation | approval/auto-allowed binding | mitigate | Phase 34 binding tests remain green; hash/snapshot matching semantics unchanged. | closed |
| T-63-12 | Elevation of Privilege | external execution scope | mitigate | Phase 63 adds no real external execution, no new write tools, and no service-level broadening. | closed |
| T-63-13 | Spoofing | `detect_pre_route` | mitigate | Approval-chat-not-trusted and policy-question hard negatives run before taxonomy action keyword matching. | closed |
| T-63-14 | Elevation of Privilege | `_action_bound_or_high_risk` | mitigate | Routing derives action/high-risk behavior from `IntentPolicyRegistry` and fails closed on registry errors. | closed |
| T-63-15 | Tampering | `_policy_evidence_required` | mitigate | Routing evidence policy is registry-derived after trusted overrides; tests cover derivation and exception behavior. | closed |
| T-63-16 | Denial of Service | registry exceptions | mitigate | Routing helpers catch registry exceptions and choose safe clarification/fail-closed paths, not unsafe action paths. | closed |
| T-63-17 | Tampering | migrated caller modules | mitigate | Static architecture guard forbids duplicate taxonomy constants/functions outside canonical owner. | closed |
| T-63-18 | Repudiation | `.planning/ARCHITECTURE-DEBT.md` | mitigate | Debt entries cite source/test paths and approved entrypoint commands. | closed |
| T-63-19 | Elevation of Privilege | future action/status hardening scope | mitigate | Phase 67 deferral for DB/status-machine constraints is recorded; Phase 63 did not add external execution. | closed |
| T-63-20 | Information Disclosure | validation logs | mitigate | Local-validation entries summarize commands/evidence and do not include secrets or raw customer data. | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-63-01 | T-63-04 | Phase 63 taxonomy tests use synthetic action/risk strings only; no tenant/customer data is loaded. | codex-manual-fallback | 2026-07-10 |

---

## Evidence

- `src/agent/safety/taxonomy.py` owns executable action types, non-executable dispositions, aliases, risk severities, and risk dispositions.
- `src/agent/nodes/risk_gate.py` now uses taxonomy helpers, emits `risk_severity` / `risk_disposition`, and blocks non-executable dispositions before proposed action binding.
- `src/agent/nodes/action_draft.py` validates executable action types before ToolPlatform invocation.
- `src/agent/intent_policy.py` and `src/agent/routing.py` derive action-bound/evidence-required routing from registries and fail closed on registry errors.
- `src/agent/nodes/recommendation_generation.py` consumes `INTENT_POLICY_REGISTRY.requires_evidence(...)` after the review-loop fix.
- `tests/architecture/test_safety_taxonomy_boundaries.py` prevents migrated callers from recreating local safety taxonomy sources.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-10 | 20 | 20 | 0 | codex-manual-fallback |

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/agent/test_safety_taxonomy.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/approvals/test_hash_binding.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_safety_taxonomy_boundaries.py tests/agent/test_nodes/test_recommendation_generation.py -q --tb=short` -> `1428 passed, 1 warning`
- `UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agent/safety src/agent/nodes/risk_gate.py src/agent/nodes/action_draft.py src/agent/nodes/recommendation_generation.py src/agent/intent_policy.py src/agent/routing.py tests/agent/test_safety_taxonomy.py tests/agent/test_nodes/test_risk_gate.py tests/agent/test_phase22_action_boundary.py tests/test_execute_action.py tests/actions/test_action_draft_v2.py tests/actions/test_phase34_action_draft_bindings.py tests/agent/test_intent_routing.py tests/agent/test_intent_policy_registry.py tests/approvals/test_hash_binding.py tests/architecture/test_action_draft_boundaries.py tests/architecture/test_safety_taxonomy_boundaries.py tests/agent/test_nodes/test_recommendation_generation.py` -> `All checks passed!`

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-10
