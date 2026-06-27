---
phase: 30
slug: businessfactservice-boundary
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-28
---

# Phase 30 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 with pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/business/test_schemas.py -q --tb=short` |
| **Full suite command** | `uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/business/test_schemas.py tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py -q --tb=short` |
| **Estimated runtime** | ~80 seconds for focused full suite |

---

## Sampling Rate

- **After every task commit:** Run the quick business suite and any test file touched by that task.
- **After every plan wave:** Run the full phase-focused command.
- **Before `$gsd-verify-work`:** Full focused suite must be green; whole suite is recommended because Phase 29.5 ended with whole-suite verification.
- **Max feedback latency:** 90 seconds for focused full suite.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 30-01-01 | 01 | 1 | APF-08 | T-30-01 / T-30-03 | `BusinessFactResultV1` is strict, explicit-null fields are present, and `BusinessFactRefV1` is not `EvidenceRefV1`. | unit | `uv run pytest tests/business/test_schemas.py -q --tb=short` | yes | pending |
| 30-01-02 | 01 | 1 | APF-08 | T-30-01 / T-30-02 | `BusinessFactService` proves scope before emitting facts/refs and uses no-leak `permission_denied`. | service/integration | `uv run pytest tests/business/test_service.py -q --tb=short` | yes | pending |
| 30-01-03 | 01 | 1 | APF-08 | T-30-01 / T-30-05 | Unsupported `get_logistics` / `get_merchant_risk`, invalid adapter responses, timeout/unavailable, and stale paths emit no facts/refs unless service-approved. | service/unit | `uv run pytest tests/business/test_service.py tests/business/test_adapters.py -q --tb=short` | yes | pending |
| 30-01-04 | 01 | 1 | APF-08 | T-30-04 | `BusinessToolExecutor` delegates to `BusinessFactService`; `requires_domain_scope_check` cannot remain annotation-only. | platform/integration | `uv run pytest tests/tools/test_tool_platform.py tests/business/test_service.py -q --tb=short` | yes | pending |
| 30-01-05 | 01 | 1 | APF-08 | T-30-02 / T-30-03 | `investigate`, prompt summaries, `business_context`, and `last_business_context_refs` consume only service-approved facts/refs. | graph/integration | `uv run pytest tests/agent/test_nodes/test_investigate.py -q --tb=short` | yes | pending |
| 30-01-06 | 01 | 1 | APF-08 | T-30-03 | Memory, RAG, LLM/model context, prompt summaries, and raw repository rows cannot substitute missing or denied current business facts. | authority boundary | `uv run pytest tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py -q --tb=short` | yes | pending |
| 30-01-07 | 01 | 1 | APF-08 | T-30-01 / T-30-02 / T-30-05 | Phase-focused regression preserves Phase 29/29.5 tool and merchant-scope behavior. | regression | `uv run pytest tests/business/test_service.py tests/business/test_adapters.py tests/business/test_schemas.py tests/tools/test_tool_platform.py tests/agent/test_nodes/test_investigate.py tests/agent/test_tools/test_get_order.py tests/agent/test_tools/test_get_refund_case.py tests/agent/test_tools/test_get_ticket.py tests/agent/rag_context/test_authority_boundaries.py tests/agent/test_policy_retrieval_ownership.py -q --tb=short` | yes | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/business/test_schemas.py` - add `BusinessFactResultV1` strict schema, status enum, explicit nullable `resource_version` / `data_freshness_at`, `scope_check_result`, `missing_required_facts`, and `safe_errors` tests.
- [ ] `tests/business/test_service.py` - add `BusinessFactService` public method tests for same-merchant allow, same-tenant cross-merchant no-leak deny, cross-tenant fail-closed, missing merchant deny, unknown role deny, and admin cross-merchant allow.
- [ ] `tests/business/test_service.py` / `tests/business/test_adapters.py` - add invalid adapter response, timeout/unavailable, unsupported logistics/risk, and simulated stale behavior tests.
- [ ] `tests/tools/test_tool_platform.py` - add ToolPlatform -> BusinessToolExecutor -> BusinessFactService delegation and `requires_domain_scope_check` enforcement tests.
- [ ] `tests/agent/test_nodes/test_investigate.py` - add graph accumulation tests proving denied/stale/unavailable service results do not populate prompt summaries, facts, or refs.
- [ ] `tests/agent/rag_context/test_authority_boundaries.py` or `tests/agent/test_policy_retrieval_ownership.py` - add raw repository row / prompt summary / memory/RAG substitution negative tests.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | APF-08 | All Phase 30 behaviors have automated verification entry points. | N/A |

---

## Threat References

| Ref | Threat | Required Mitigation |
|-----|--------|---------------------|
| T-30-01 | Cross-merchant identifier probing through order/refund/ticket identifiers. | Generic no-leak `permission_denied`, no facts, no refs, no identifier-bearing safe errors or prompt summaries before scope proof. |
| T-30-02 | Raw adapter payload or repository row leaks into graph/prompt. | Strict `BusinessFactResultV1` projection, raw payload discard, and ToolResultProjector-only prompt surfaces. |
| T-30-03 | RAG, memory, LLM inference, or prompt summaries substitute for current business facts. | Business fact claims require service-approved `BusinessFactRefV1`; policy evidence and memory remain non-authoritative for current facts. |
| T-30-04 | ToolPolicy `requires_domain_scope_check` remains metadata only. | BusinessFactService must perform domain ownership proof before emitting facts/refs for order/refund/ticket identifiers. |
| T-30-05 | Unsupported business reads imply data exists. | `get_logistics` and `get_merchant_risk` return typed unavailable/no-fact/no-ref results or are unavailable through platform availability. |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing APF-08 references identified in research.
- [x] No watch-mode flags.
- [x] Feedback latency target is under 90 seconds for focused full suite.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** ready 2026-06-28
