---
phase: 39-contract-spec-12-5-12-6-reconciliation
slug: contract-spec-12-5-12-6-reconciliation
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-02
---

# Phase 39 — Security

Per-phase security contract: threat register, mitigation evidence, accepted risks, and audit trail for the Phase 39 docs-only contract-spec reconciliation.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| §8.0 TrustedContext -> §12.5 ToolCallContext | Trusted identity/scope fields are projected into tool context and must not be re-owned by §12.5. | Tenant, user, role, permission, merchant scope, session/thread/run/trace identity. |
| ToolDescriptor -> ToolView prompt surface | Descriptor metadata includes internal executor/exposure/safety fields that must not become prompt-visible fields. | Catalog/runtime metadata, prompt-safe planner capability views. |
| ToolPolicyDecision -> runtime authorization | Runtime availability metadata clarifies executor availability without making planner visibility equivalent to runtime authorization. | Policy decision metadata, runtime availability state, reason codes. |
| Action safety refs -> write tool invocation | Approval/safety/idempotency references are local action-safety inputs, not identity or permission substitutes. | Approval refs, safety snapshot refs, idempotency keys, write-tool context. |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-39-01 | Spoofing / Elevation of Privilege | `docs/contract-spec.md` §12.5 | mitigate | §12.5 preserves the existing statement that identity/scope/permission fields are §8.0 `TrustedContext` projections; Phase 39 verification confirms no changed type lines for `tenant_id`, `user_id`, `role`, `permissions`, `merchant_scope`, `session_id`, `thread_id`, `run_id`, or `trace_id`. | closed |
| T-39-02 | Information Disclosure | `ToolDescriptor` metadata in §12.6 | mitigate | §12.6 keeps `ToolView` as the prompt-safe planner surface and states `ToolPlatform.visible_tools` must expose only `ToolView`, not raw adapter, hidden side-effect capability, internal permission reason, raw exception shape, or prompt-unsafe fields. Review `39-REVIEW.md` is clean. | closed |
| T-39-03 | Tampering / Elevation of Privilege | `ToolPolicyDecision.runtime_available` / `availability_summary` | mitigate | §12.6 adds availability fields while preserving the rule that planner visibility is not runtime authorization; runtime authorization gate tests passed in Phase 39 validation. | closed |
| T-39-04 | Tampering / Repudiation | `approval_ref`, `safety_snapshot_ref`, `idempotency_key` | mitigate | §12.5 documents `approval_ref` and `safety_snapshot_ref` as tool-call-local/action-safety fields, while §12.6 keeps write descriptors node-only with approval/snapshot/idempotency requirements; focused catalog/runtime tests passed. | closed |
| T-39-05 | Repudiation | Commit/spec reconciliation evidence | mitigate | `39-01-SUMMARY.md` records pre-edit evidence for commit `4dcb673`, docs-only diff proof, structural validation, and dual-AI review/adjudication evidence; `39-VERIFICATION.md` passed 5/5 must-haves. | closed |

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-02 | 5 | 5 | 0 | Codex / gsd-secure-phase |

---

## Verification Evidence

- `39-01-SUMMARY.md` `## Threat Flags`: None; implementation diff was documentation-only and introduced no new endpoint, auth path, file access path, or trust-boundary code surface.
- `39-REVIEW.md`: `status: clean`, 0 findings after review fixes.
- `39-VERIFICATION.md`: `status: passed`, 5/5 must-haves verified.
- Phase 39 validation evidence includes `uv run pytest tests/architecture/test_trusted_context_boundaries.py tests/tools/test_catalog.py tests/tools/test_tool_platform.py -q` -> `72 passed, 1 warning`.
- Review-specific validation includes `uv run pytest tests/tools/test_catalog.py::test_action_descriptor_is_node_only_and_requires_idempotency tests/agent/test_graph.py::test_graph_compiles_with_investigate tests/agent/test_graph.py::test_requested_operation_execute_action_remains_intent_taxonomy_value -q` -> `3 passed, 2 warnings`.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-02
